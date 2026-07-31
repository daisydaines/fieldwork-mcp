"""Hosted HTTP mode: /connect UI + bearer-token MCP.

Fieldwork has no third-party OAuth consent screen (unlike Dropbox/Fathom).
Owners paste an API key once; we mint a bearer token for Streamable HTTP MCP.
"""

from __future__ import annotations

import os
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import ASGIApp

from . import context
from .client import FieldworkClient
from .exceptions import FieldworkAuthError, FieldworkConfigError, FieldworkError
from .server import mcp
from .vault import Vault

CONNECT_HTML = Path(__file__).with_name("connect_page.html")


class BearerVaultMiddleware(BaseHTTPMiddleware):
    """Map Authorization: Bearer <token> -> Fieldwork API key for /mcp* routes."""

    def __init__(self, app: ASGIApp, vault: Vault, *, allow_env_fallback: bool) -> None:
        super().__init__(app)
        self.vault = vault
        self.allow_env_fallback = allow_env_fallback

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not (path == "/mcp" or path.startswith("/mcp/")):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        api_key: str | None = None
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            api_key = self.vault.get_api_key(token)
            if not api_key:
                return JSONResponse({"error": "Invalid or unknown connect token"}, status_code=401)
        elif self.allow_env_fallback and os.environ.get("FIELDWORK_API_KEY"):
            api_key = os.environ.get("FIELDWORK_API_KEY")
        else:
            return JSONResponse(
                {
                    "error": "Missing bearer token. Open /connect to create one, "
                    "or set FIELDWORK_API_KEY for local fallback."
                },
                status_code=401,
            )

        ctx = context.set_api_key(api_key)
        try:
            return await call_next(request)
        finally:
            context.reset_api_key(ctx)


def _public_base(request: Request) -> str:
    override = os.environ.get("FIELDWORK_PUBLIC_BASE_URL", "").rstrip("/")
    if override:
        return override
    return str(request.base_url).rstrip("/")


def register_connect_routes(vault: Vault) -> None:
    @mcp.custom_route("/connect", methods=["GET"], name="connect_page")
    async def connect_page(_: Request) -> Response:
        html = CONNECT_HTML.read_text(encoding="utf-8")
        return HTMLResponse(html)

    @mcp.custom_route("/api/connect", methods=["POST"], name="connect_api")
    async def connect_api(request: Request) -> Response:
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            return JSONResponse({"error": "Expected JSON body"}, status_code=400)

        api_key = str((payload or {}).get("api_key") or "").strip()
        if not api_key:
            return JSONResponse({"error": "api_key is required"}, status_code=400)

        # Verify the key against Fieldwork before storing.
        try:
            profile = await FieldworkClient(api_key=api_key).get_profile()
        except FieldworkAuthError:
            return JSONResponse(
                {"error": "Fieldwork rejected that API key (401/403)."},
                status_code=401,
            )
        except FieldworkConfigError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except FieldworkError as exc:
            return JSONResponse({"error": f"Could not verify key: {exc}"}, status_code=400)

        label = None
        if isinstance(profile, dict):
            label = profile.get("name") or profile.get("email")

        token = vault.create(api_key, label=str(label) if label else None)
        base = _public_base(request)
        mcp_url = f"{base}/mcp"

        return JSONResponse(
            {
                "ok": True,
                "mcp_url": mcp_url,
                "token": token,
                "label": label,
                "claude_code": (
                    f'claude mcp add --transport http fieldwork {mcp_url} '
                    f'--header "Authorization: Bearer {token}"'
                ),
                "mcp_json": {
                    "mcpServers": {
                        "fieldwork": {
                            "url": mcp_url,
                            "headers": {"Authorization": f"Bearer {token}"},
                        }
                    }
                },
            }
        )

    @mcp.custom_route("/healthz", methods=["GET"], name="healthz")
    async def healthz(_: Request) -> Response:
        return JSONResponse({"ok": True, "mode": "hosted-http"})


def run_hosted(transport: str = "streamable-http") -> None:
    """Run Streamable HTTP with /connect + bearer vault middleware."""
    import uvicorn

    vault = Vault()
    register_connect_routes(vault)
    allow_env = os.environ.get("FIELDWORK_MCP_ALLOW_ENV_FALLBACK", "1") == "1"
    app = BearerVaultMiddleware(
        mcp.streamable_http_app(),
        vault,
        allow_env_fallback=allow_env,
    )

    host = os.environ.get("FIELDWORK_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("FIELDWORK_MCP_PORT", "8000"))
    print(
        f"fieldwork-mcp hosted on http://{host}:{port}\n"
        f"  Connect UI: http://{host}:{port}/connect\n"
        f"  MCP:        http://{host}:{port}/mcp",
        flush=True,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")

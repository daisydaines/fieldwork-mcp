"""Read-only HTTP client for the Fieldwork API v3.1.

Safety rails:
- Only GET requests are allowed (writes raise FieldworkReadOnlyError).
- API key is loaded from the environment — never hard-coded.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from .context import get_api_key as get_request_api_key
from .exceptions import (
    FieldworkAPIError,
    FieldworkAuthError,
    FieldworkConfigError,
    FieldworkConnectionError,
    FieldworkNotFoundError,
    FieldworkRateLimitError,
    FieldworkReadOnlyError,
)

DEFAULT_BASE_URL = "https://api3.fieldworkhq.com"
API_PREFIX = "/v3.1"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


class FieldworkClient:
    """Thin GET-only wrapper around Fieldwork's REST API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        auth_scheme: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key or get_request_api_key() or _env("FIELDWORK_API_KEY")
        if not self.api_key:
            raise FieldworkConfigError(
                "FIELDWORK_API_KEY is not set. Copy .env.example to .env and add your key, "
                "or export FIELDWORK_API_KEY before starting the MCP server."
            )

        resolved_base = base_url or _env("FIELDWORK_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
        self.base_url = resolved_base.rstrip("/")
        # Fieldwork accepts the private key via the `api-key` header (confirmed)
        # or `?api_key=` query param. Header is preferred so keys stay out of URLs.
        self.auth_scheme = (
            auth_scheme or _env("FIELDWORK_AUTH_SCHEME", "api-key") or "api-key"
        ).lower()
        if self.auth_scheme not in {"api-key", "query", "token", "bearer"}:
            raise FieldworkConfigError(
                "FIELDWORK_AUTH_SCHEME must be one of: "
                "api-key (default), query, token, bearer."
            )

        timeout_raw = timeout
        if timeout_raw is None:
            timeout_raw = float(_env("FIELDWORK_TIMEOUT_SECONDS", "30") or "30")
        self.timeout = float(timeout_raw)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "fieldwork-mcp/0.1.0 (+https://github.com/PLACEHOLDER/fieldwork-mcp)",
        }
        if self.auth_scheme == "api-key":
            headers["api-key"] = self.api_key or ""
        elif self.auth_scheme == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.auth_scheme == "token":
            headers["Authorization"] = f'Token token="{self.api_key}"'
        # scheme == "query" → auth goes in params, not headers
        return headers

    def _auth_params(self) -> dict[str, str]:
        if self.auth_scheme == "query":
            return {"api_key": self.api_key or ""}
        return {}

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """GET a path under /v3.1. ``path`` may be 'profile' or '/profile'."""
        return await self.request("GET", path, params=params)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        method_upper = method.upper()
        if method_upper != "GET":
            raise FieldworkReadOnlyError(
                f"Refusing {method_upper} {path}: fieldwork-mcp is read-only. "
                "Write tools are intentionally not implemented."
            )

        clean = path if path.startswith("/") else f"/{path}"
        if not clean.startswith(API_PREFIX):
            clean = f"{API_PREFIX}{clean}"
        url = f"{self.base_url}{clean}"

        query = _compact_params(params) or {}
        query.update(self._auth_params())
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers=self._headers(),
                    params=query or None,
                )
        except httpx.TimeoutException as exc:
            raise FieldworkConnectionError(f"Timed out calling Fieldwork: {exc}") from exc
        except httpx.HTTPError as exc:
            raise FieldworkConnectionError(f"Network failure talking to Fieldwork: {exc}") from exc

        return _parse_response(response)

    # --- Convenience endpoints (read-only) ---------------------------------

    async def check_connection(self) -> Any:
        return await self.get("/check_connection")

    async def get_profile(self) -> Any:
        return await self.get("/profile")

    async def search_customers(
        self,
        *,
        query: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        customer_status: str | None = None,
        postal_code: str | None = None,
        updated_after: str | None = None,
    ) -> Any:
        return await self.get(
            "/customers/search",
            params={
                "query": query,
                "page": page,
                "per_page": per_page,
                "start_date": start_date,
                "end_date": end_date,
                "filter[customer_status]": customer_status,
                "filter[postal_code]": postal_code,
                "filter[updated_after]": updated_after,
            },
        )

    async def get_customer(self, customer_id: int) -> Any:
        return await self.get(f"/customers/{int(customer_id)}")

    async def search_customer_by_phone(self, phone: str) -> Any:
        return await self.get("/customers/search_by_phone", params={"phone": phone})

    async def list_customer_notes(
        self,
        customer_id: int,
        *,
        page: int | None = None,
        per_page: int | None = None,
        body_contains: str | None = None,
    ) -> Any:
        return await self.get(
            f"/customers/{int(customer_id)}/notes",
            params={
                "page": page,
                "per_page": per_page,
                "filter[body]": body_contains,
            },
        )

    async def list_materials(self) -> Any:
        return await self.get("/materials")

    async def list_services(self) -> Any:
        return await self.get("/services")

    async def list_service_routes(self, *, ids: list[int] | None = None) -> Any:
        params: dict[str, Any] | None = None
        if ids:
            params = {"filter[ids]": ids}
        return await self.get("/service_routes", params=params)

    async def search_work_orders(
        self,
        *,
        query: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        current_technician: bool | None = None,
        work_pool: bool | None = None,
    ) -> Any:
        return await self.get(
            "/work_orders/search",
            params={
                "query": query,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "per_page": per_page,
                "current_technician": current_technician,
                "work_pool": work_pool,
            },
        )

    async def get_work_order(self, work_order_id: int, *, plain: bool = True) -> Any:
        suffix = "show_plain" if plain else ""
        path = f"/work_orders/{int(work_order_id)}"
        if suffix:
            path = f"{path}/{suffix}"
        return await self.get(path)

    async def get_work_order_service_report(self, work_order_id: int) -> Any:
        return await self.get(f"/work_orders/{int(work_order_id)}/service_report")

    async def list_work_order_unit_records(
        self,
        work_order_id: int,
        *,
        page: int | None = None,
        per_page: int | None = None,
    ) -> Any:
        """Unit records often nest material usage for a completed service."""
        return await self.get(
            f"/work_orders/{int(work_order_id)}/unit_records",
            params={"page": page, "per_page": per_page},
        )

    async def search_invoices(
        self,
        *,
        query: str | None = None,
        customer_id: int | None = None,
        service_location_id: int | None = None,
        page: int | None = None,
        per_page: int | None = None,
    ) -> Any:
        return await self.get(
            "/invoices/search",
            params={
                "query": query,
                "filter[customer_id]": customer_id,
                "filter[service_location_id]": service_location_id,
                "page": page,
                "per_page": per_page,
            },
        )

    async def get_invoice(self, invoice_id: int) -> Any:
        return await self.get(f"/invoices/{int(invoice_id)}")

    async def list_calendar_work_orders(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        with_workpool: bool | None = None,
        only_workpool: bool | None = None,
    ) -> Any:
        return await self.get(
            "/calendar/work_orders_only",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "with_workpool": with_workpool,
                "only_workpool": only_workpool,
            },
        )

    async def get_operations_summary(
        self,
        *,
        start_date: str,
        end_date: str,
        branch_id: int | None = None,
        service_route_id: int | None = None,
    ) -> Any:
        return await self.get(
            "/summary_reports/operations",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "branch_id": branch_id,
                "service_route_id": service_route_id,
            },
        )

    async def get_financial_summary(
        self,
        *,
        start_date: str,
        end_date: str,
        branch_id: int | None = None,
    ) -> Any:
        return await self.get(
            "/summary_reports/financial",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "branch_id": branch_id,
            },
        )


def _compact_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    out: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = value
    return out or None


def _parse_response(response: httpx.Response) -> Any:
    status = response.status_code

    if status == 204:
        return {"status": "ok", "http_status": 204}

    if status in {401, 403}:
        raise FieldworkAuthError(
            f"Authentication failed (HTTP {status}). "
            "Check FIELDWORK_API_KEY. Default auth uses the `api-key` header; "
            "fallback is FIELDWORK_AUTH_SCHEME=query. "
            f"Body: {_safe_body_preview(response)}"
        )

    if status == 404:
        raise FieldworkNotFoundError(
            f"Not found (HTTP 404). Body: {_safe_body_preview(response)}"
        )

    if status == 429:
        retry_after = response.headers.get("Retry-After")
        retry_val = float(retry_after) if retry_after and retry_after.isdigit() else None
        raise FieldworkRateLimitError(
            f"Rate limited by Fieldwork (HTTP 429). Body: {_safe_body_preview(response)}",
            retry_after=retry_val,
        )

    if status >= 400:
        raise FieldworkAPIError(
            f"Fieldwork API error (HTTP {status}): {_safe_body_preview(response)}",
            http_status=status,
            body=_try_json(response),
        )

    if not response.content:
        return {"status": "ok", "http_status": status}

    data = _try_json(response)
    if data is None:
        # Avoid returning huge HTML error pages as tool output.
        text = response.text
        preview = text if len(text) <= 500 else text[:500] + "…"
        raise FieldworkAPIError(
            f"Expected JSON from Fieldwork but got content-type "
            f"{response.headers.get('content-type')!r}: {preview}",
            http_status=status,
            body=preview,
        )
    return data


def _try_json(response: httpx.Response) -> Any | None:
    try:
        return response.json()
    except ValueError:
        return None


def _safe_body_preview(response: httpx.Response, limit: int = 300) -> str:
    """Stringify a response body without echoing secrets from our side."""
    data = _try_json(response)
    if data is not None:
        text = repr(data)
    else:
        text = response.text
    # Never include Authorization values; body shouldn't have our key, but be careful.
    redacted = text.replace(quote(os.environ.get("FIELDWORK_API_KEY", ""), safe=""), "[REDACTED]")
    key = os.environ.get("FIELDWORK_API_KEY", "")
    if key:
        redacted = redacted.replace(key, "[REDACTED]")
    if len(redacted) > limit:
        return redacted[:limit] + "…"
    return redacted
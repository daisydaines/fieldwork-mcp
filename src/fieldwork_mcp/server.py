"""Fieldwork MCP server — read-only tools for Claude, Cursor, and other MCP clients.

This server intentionally exposes GET-only operations. Creating, updating,
canceling, or paying anything in Fieldwork is out of scope for v0.1.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import owner
from .client import FieldworkClient
from .exceptions import (
    FieldworkAPIError,
    FieldworkAuthError,
    FieldworkConfigError,
    FieldworkConnectionError,
    FieldworkError,
    FieldworkNotFoundError,
    FieldworkRateLimitError,
    FieldworkReadOnlyError,
)


def _load_env_files() -> None:
    """Load .env from cwd and from the project checkout (never commit .env)."""
    load_dotenv(Path.cwd() / ".env")
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / ".env").is_file():
            load_dotenv(parent / ".env", override=False)
            break


_load_env_files()

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

mcp = FastMCP(
    "fieldwork-mcp",
    instructions=(
        "You help pest-control / lawn-care business OWNERS use Fieldwork in plain English. "
        "They are not technical — never ask them for endpoint names, IDs, or JSON.\n\n"
        "ALWAYS prefer owner tools (they return an `answer` string — read it out naturally):\n"
        "CUSTOMERS\n"
        "- how_many_customers → how many customers / book of business size\n"
        "- find_customer → find someone by name ('do I have a customer named Smith?')\n"
        "MONEY\n"
        "- who_owes_me_money → unpaid invoices / who owes me / AR\n"
        "- how_much_money → revenue / financial snapshot for a period\n"
        "- how_is_business_doing → jobs completed + production value\n"
        "PRODUCT / CHEMICALS\n"
        "- how_much_product_was_used → usage totals ('how much Alpine this month?')\n"
        "- what_products_do_we_carry → catalog / what chemicals do we have\n"
        "SCHEDULE / ROUTES / TECHS\n"
        "- whats_on_the_schedule → what's on the board this week\n"
        "- who_are_my_technicians → who works here / tech list\n"
        "- how_are_my_routes_doing → jobs per route\n"
        "- who_did_the_most_jobs → top technician / producer\n\n"
        "If the user asks for a Monday morning briefing / weekly snapshot, use the "
        "`monday_morning_briefing` prompt workflow: call how_is_business_doing, "
        "who_owes_me_money, whats_on_the_schedule, how_much_product_was_used, and "
        "who_did_the_most_jobs, then summarize in plain English.\n\n"
        "Only use lower-level search_*/get_* tools when the owner needs one specific record "
        "after an owner tool. This server is READ-ONLY."
    ),
    host=os.environ.get("FIELDWORK_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("FIELDWORK_MCP_PORT", "8000")),
)

F = TypeVar("F", bound=Callable[..., Any])


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _format_error(exc: Exception) -> str:
    if isinstance(exc, FieldworkConfigError):
        return f"Configuration error: {exc}"
    if isinstance(exc, FieldworkAuthError):
        return f"Auth error: {exc}"
    if isinstance(exc, FieldworkNotFoundError):
        return f"Not found: {exc}"
    if isinstance(exc, FieldworkRateLimitError):
        wait = f" Retry after {exc.retry_after}s." if exc.retry_after else ""
        return f"Rate limited: {exc}.{wait}"
    if isinstance(exc, FieldworkConnectionError):
        return f"Connection error: {exc}"
    if isinstance(exc, FieldworkReadOnlyError):
        return f"Read-only guard: {exc}"
    if isinstance(exc, FieldworkAPIError):
        return f"API error (HTTP {exc.http_status}): {exc}"
    if isinstance(exc, FieldworkError):
        return f"Fieldwork error: {exc}"
    return f"Unexpected error: {exc!r}"


def tool_guard(fn: F) -> F:
    """Convert Fieldwork errors into raised RuntimeErrors FastMCP marks as tool errors."""

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — surface cleanly to the agent
            raise RuntimeError(_format_error(exc)) from exc

    return wrapper  # type: ignore[return-value]


def _client() -> FieldworkClient:
    return FieldworkClient()


# --- Diagnostics -----------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def health_check() -> str:
    """Verify Fieldwork credentials. Run this first if other tools fail.

    Calls GET /v3.1/profile. On success returns a small redacted profile summary.
    """
    client = _client()
    profile = await client.get_profile()
    # Slim summary — never echo api_key / auth tokens from the profile payload.
    if isinstance(profile, dict):
        secret_keys = {"api_key", "auth_token", "calls_auth_token"}
        summary = {
            "status": "ok",
            "auth_scheme": client.auth_scheme,
            "base_url": client.base_url,
            "profile_keys": sorted(k for k in profile.keys() if k not in secret_keys),
        }
        for key in (
            "id",
            "user_id",
            "email",
            "name",
            "first_name",
            "last_name",
            "company",
            "role",
        ):
            if key in profile:
                summary[key] = profile[key]
        return _json(summary)
    return _json({"status": "ok", "profile": profile})


# --- Owner questions (plain English) ---------------------------------------


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def how_many_customers() -> str:
    """Answer: "How many customers do I have?", "What's my customer count?"

    Counts every customer in Fieldwork and breaks down by status.
    Prefer this over search_customers for total-count questions.
    """
    return _json(await owner.count_customers(_client()))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def how_much_product_was_used(
    days: int = 30,
    start_date: str | None = None,
    end_date: str | None = None,
    material_name: str | None = None,
) -> str:
    """Answer: "How much product was used?", "What chemicals did we use this month?"

    Totals logged material/chemical usage from completed jobs.

    Args:
        days: Look back this many days ending today (default 30). Ignored if start_date set.
        start_date: Optional YYYY-MM-DD range start.
        end_date: Optional YYYY-MM-DD range end (default today).
        material_name: Optional filter, e.g. "Alpine" or "Taurus".
    """
    return _json(
        await owner.product_usage_summary(
            _client(),
            days=days,
            start_date=start_date,
            end_date=end_date,
            material_name=material_name,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def how_is_business_doing(
    days: int = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Answer: "How is business doing?", "How many jobs did we finish this month?"

    Plain-English operations snapshot (jobs completed, cancelled, production value).
    """
    return _json(
        await owner.business_snapshot(
            _client(),
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def whats_on_the_schedule(
    days: int = 7,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Answer: "What's on the schedule?", "How many jobs this week?"

    Work-order overview for a date range (default 7 days).
    """
    return _json(
        await owner.schedule_overview(
            _client(),
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def find_customer(query: str, limit: int = 10) -> str:
    """Answer: "Do I have a customer named ___?", "Find customer Smith"

    Search customers by name or other Fieldwork search text.
    """
    return _json(await owner.find_customers(_client(), query=query, limit=limit))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def who_owes_me_money(top_n: int = 10) -> str:
    """Answer: "Who owes me money?", "What invoices are unpaid?", "How's my AR?"

    Totals open invoice balances and lists top customers by amount due.
    """
    return _json(await owner.who_owes_me_money(_client(), top_n=top_n))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def how_much_money(
    days: int = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Answer: "How much money did we make?", "What's our revenue this month?"

    Financial summary snapshot for a date range.
    """
    return _json(
        await owner.money_snapshot(
            _client(),
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def who_are_my_technicians() -> str:
    """Answer: "Who are my technicians?", "Who's on my team?", "What routes do I have?"

    Lists technicians, office users, and service routes (no secrets).
    """
    return _json(await owner.who_are_my_technicians(_client()))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def how_are_my_routes_doing(
    days: int = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Answer: "How are my routes doing?", "Which route is busiest?"

    Jobs (and completions) per service route for a date range.
    """
    return _json(
        await owner.how_are_my_routes_doing(
            _client(),
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def who_did_the_most_jobs(
    days: int = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Answer: "Who did the most jobs?", "Who's my top technician?"

    Ranks technicians/routes by completed jobs for a date range.
    """
    return _json(
        await owner.who_did_the_most_jobs(
            _client(),
            days=days,
            start_date=start_date,
            end_date=end_date,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def what_products_do_we_carry() -> str:
    """Answer: "What products do we carry?", "What chemicals are in our catalog?"

    Lists materials/products configured in Fieldwork.
    """
    return _json(await owner.what_products_do_we_carry(_client()))


# --- Customers (specific lookups) ------------------------------------------


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def search_customers(
    query: str | None = None,
    page: int | None = 1,
    per_page: int | None = 25,
    start_date: str | None = None,
    end_date: str | None = None,
    customer_status: str | None = None,
    postal_code: str | None = None,
    updated_after: str | None = None,
) -> str:
    """Search Fieldwork customers.

    Args:
        query: Free-text search (name, email, account bits — whatever Fieldwork indexes).
        page: Page number (default 1).
        per_page: Page size (default 25; keep modest).
        start_date: Optional YYYY-MM-DD (or MM/DD/YYYY) lower bound.
        end_date: Optional YYYY-MM-DD (or MM/DD/YYYY) upper bound.
        customer_status: Optional status filter.
        postal_code: Optional postal/ZIP filter.
        updated_after: Optional updated-after date (YYYY-MM-DD or ISO-8601).
    """
    data = await _client().search_customers(
        query=query,
        page=page,
        per_page=per_page,
        start_date=start_date,
        end_date=end_date,
        customer_status=customer_status,
        postal_code=postal_code,
        updated_after=updated_after,
    )
    return _json(data)


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def get_customer(customer_id: int) -> str:
    """Fetch one customer by ID."""
    return _json(await _client().get_customer(customer_id))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def search_customer_by_phone(phone: str) -> str:
    """Find a customer by phone number."""
    return _json(await _client().search_customer_by_phone(phone))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def list_customer_notes(
    customer_id: int,
    page: int | None = 1,
    per_page: int | None = 25,
    body_contains: str | None = None,
) -> str:
    """List notes on a customer (read-only)."""
    return _json(
        await _client().list_customer_notes(
            customer_id,
            page=page,
            per_page=per_page,
            body_contains=body_contains,
        )
    )


# --- Catalog / routes ------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def list_materials() -> str:
    """List materials/chemicals in the Fieldwork catalog (name, EPA #, etc.)."""
    return _json(await _client().list_materials())


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def list_services() -> str:
    """List service types configured in Fieldwork."""
    return _json(await _client().list_services())


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def list_service_routes() -> str:
    """List service routes (technician routes)."""
    return _json(await _client().list_service_routes())


# --- Work orders / usage ---------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def search_work_orders(
    query: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int | None = 1,
    per_page: int | None = 25,
    current_technician: bool | None = None,
    work_pool: bool | None = None,
) -> str:
    """Search work orders / service appointments.

    Prefer passing start_date and end_date (YYYY-MM-DD) to keep results small.
    """
    return _json(
        await _client().search_work_orders(
            query=query,
            start_date=start_date,
            end_date=end_date,
            page=page,
            per_page=per_page,
            current_technician=current_technician,
            work_pool=work_pool,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def get_work_order(work_order_id: int, plain: bool = True) -> str:
    """Fetch one work order. plain=True uses Fieldwork's show_plain endpoint."""
    return _json(await _client().get_work_order(work_order_id, plain=plain))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def get_work_order_service_report(work_order_id: int) -> str:
    """Fetch the service report for a work order (often includes treatment details)."""
    return _json(await _client().get_work_order_service_report(work_order_id))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def list_work_order_unit_records(
    work_order_id: int,
    page: int | None = 1,
    per_page: int | None = 50,
) -> str:
    """List unit records for a work order.

    This is the main read path for material usage: usages are nested on unit
    records in Fieldwork's API (there is no standalone material-usages index).
    """
    return _json(
        await _client().list_work_order_unit_records(
            work_order_id,
            page=page,
            per_page=per_page,
        )
    )


# --- Invoices / calendar / reports -----------------------------------------


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def search_invoices(
    query: str | None = None,
    customer_id: int | None = None,
    service_location_id: int | None = None,
    page: int | None = 1,
    per_page: int | None = 25,
) -> str:
    """Search invoices."""
    return _json(
        await _client().search_invoices(
            query=query,
            customer_id=customer_id,
            service_location_id=service_location_id,
            page=page,
            per_page=per_page,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def get_invoice(invoice_id: int) -> str:
    """Fetch one invoice by ID."""
    return _json(await _client().get_invoice(invoice_id))


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def list_calendar_work_orders(
    start_date: str | None = None,
    end_date: str | None = None,
    with_workpool: bool | None = None,
    only_workpool: bool | None = None,
) -> str:
    """List calendar work orders for a date range (YYYY-MM-DD)."""
    return _json(
        await _client().list_calendar_work_orders(
            start_date=start_date,
            end_date=end_date,
            with_workpool=with_workpool,
            only_workpool=only_workpool,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def get_operations_summary(
    start_date: str,
    end_date: str,
    branch_id: int | None = None,
    service_route_id: int | None = None,
) -> str:
    """Operations summary report for a date range (ISO dates, e.g. 2026-01-01)."""
    return _json(
        await _client().get_operations_summary(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id,
            service_route_id=service_route_id,
        )
    )


@mcp.tool(annotations=READ_ONLY)
@tool_guard
async def get_financial_summary(
    start_date: str,
    end_date: str,
    branch_id: int | None = None,
) -> str:
    """Financial summary report for a date range (ISO dates, e.g. 2026-01-01)."""
    return _json(
        await _client().get_financial_summary(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id,
        )
    )


@mcp.prompt(
    name="monday_morning_briefing",
    title="Monday morning briefing",
    description=(
        "Owner briefing: business health, who owes money, this week's schedule, "
        "product usage, and top technician. Use the matching owner tools."
    ),
)
def monday_morning_briefing() -> str:
    """Canned workflow an agent can load for a Monday (or any) ops briefing."""
    return (
        "Give me a plain-English Monday morning briefing for my pest control business.\n"
        "1) Call how_is_business_doing for the last 7 days.\n"
        "2) Call who_owes_me_money.\n"
        "3) Call whats_on_the_schedule for the next 7 days.\n"
        "4) Call how_much_product_was_used for the last 7 days.\n"
        "5) Call who_did_the_most_jobs for the last 30 days.\n"
        "Then summarize like you're talking to the owner over coffee — short bullets, "
        "no JSON, no tool names unless they ask."
    )


def main() -> None:
    """CLI entrypoint used by the ``fieldwork-mcp`` console script."""
    transport = os.environ.get("FIELDWORK_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "sse", "streamable-http"}:
        print(
            "fieldwork-mcp: FIELDWORK_MCP_TRANSPORT must be "
            "stdio, sse, or streamable-http",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # Hosted HTTP: /connect UI + bearer vault (Fieldwork has no OAuth popup).
    # API keys come from /connect tokens, so env key is optional here.
    if transport == "streamable-http" and os.environ.get("FIELDWORK_MCP_HOSTED", "1") == "1":
        from .hosted import run_hosted

        run_hosted(transport)
        return

    # Stdio / non-hosted: fail fast if local key missing.
    try:
        FieldworkClient()
    except FieldworkConfigError as exc:
        print(f"fieldwork-mcp: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if transport != "stdio":
        print(
            f"fieldwork-mcp: starting {transport} on "
            f"http://{mcp.settings.host}:{mcp.settings.port}"
            f"{mcp.settings.streamable_http_path if transport == 'streamable-http' else ''}",
            file=sys.stderr,
        )
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
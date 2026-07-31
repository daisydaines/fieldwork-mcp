"""Plain-English business answers for pest-control owners (not API-shaped tools)."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from .client import FieldworkClient


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # ISO datetime
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValueError(f"Could not parse date {value!r}. Use YYYY-MM-DD.") from exc


def _date_range(
    *,
    days: int | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[date, date]:
    end = _parse_date(end_date) or date.today()
    if start_date:
        start = _parse_date(start_date)
        assert start is not None
    else:
        window = days if days is not None else 30
        if window < 1:
            raise ValueError("days must be at least 1")
        start = end - timedelta(days=window - 1)
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    return start, end


async def count_customers(client: FieldworkClient) -> dict[str, Any]:
    """Paginate all customers and return totals + status breakdown."""
    statuses: Counter[str] = Counter()
    total = 0
    page = 1
    per_page = 100

    while True:
        batch = await client.get("/customers", params={"page": page, "per_page": per_page})
        if not isinstance(batch, list) or not batch:
            break
        total += len(batch)
        for row in batch:
            if isinstance(row, dict):
                statuses[str(row.get("status") or "unknown")] += 1
        if len(batch) < per_page:
            break
        page += 1
        if page > 200:  # safety rail (~20k customers)
            break

    status_bits = ", ".join(f"{count} {name}" for name, count in sorted(statuses.items()))
    if status_bits:
        answer = f"You have {total:,} customers ({status_bits})."
    else:
        answer = f"You have {total:,} customers."

    return {
        "answer": answer,
        "total_customers": total,
        "by_status": dict(statuses),
        "pages_scanned": page,
    }


async def _iter_work_orders(
    client: FieldworkClient,
    *,
    start: date,
    end: date,
    max_pages: int = 50,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    per_page = 100
    while page <= max_pages:
        batch = await client.search_work_orders(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            page=page,
            per_page=per_page,
        )
        if not isinstance(batch, list) or not batch:
            break
        out.extend(row for row in batch if isinstance(row, dict))
        if len(batch) < per_page:
            break
        page += 1
    return out


async def _material_usages_for_work_order(
    client: FieldworkClient,
    work_order_id: int,
) -> list[dict[str, Any]]:
    plain = await client.get_work_order(work_order_id, plain=True)
    if not isinstance(plain, dict):
        return []
    appt = plain.get("appointment_occurrence")
    if not isinstance(appt, dict):
        return []
    usages = appt.get("material_usages") or []
    return [u for u in usages if isinstance(u, dict)]


async def product_usage_summary(
    client: FieldworkClient,
    *,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
    material_name: str | None = None,
    max_work_orders: int = 400,
) -> dict[str, Any]:
    """Aggregate product/chemical usage across work orders in a date range."""
    start, end = _date_range(days=days, start_date=start_date, end_date=end_date)
    work_orders = await _iter_work_orders(client, start=start, end=end)
    truncated = len(work_orders) > max_work_orders
    work_orders = work_orders[:max_work_orders]

    # Only completed jobs usually have logged product.
    completed = [w for w in work_orders if str(w.get("status", "")).lower() == "complete"]
    targets = completed or work_orders

    sem = asyncio.Semaphore(8)

    async def one(wo: dict[str, Any]) -> list[dict[str, Any]]:
        wid = wo.get("id")
        if wid is None:
            return []
        async with sem:
            try:
                return await _material_usages_for_work_order(client, int(wid))
            except Exception:  # noqa: BLE001 — skip bad WOs, still return a useful total
                return []

    usage_lists = await asyncio.gather(*(one(wo) for wo in targets))

    # key: (material_name, measurement) -> amount sum + jobs
    amounts: dict[tuple[str, str], float] = defaultdict(float)
    job_hits: dict[tuple[str, str], int] = Counter()
    applications = 0
    needle = material_name.strip().lower() if material_name else None

    for usages in usage_lists:
        seen_keys: set[tuple[str, str]] = set()
        for usage in usages:
            raw_name = usage.get("material_name") or f"material #{usage.get('material_id')}"
            name = str(raw_name).strip()
            measurement = str(usage.get("measurement") or "unit(s)").strip()
            if needle and needle not in name.lower():
                continue
            try:
                amount = float(usage.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            key = (name, measurement)
            amounts[key] += amount
            applications += 1
            seen_keys.add(key)
        for key in seen_keys:
            job_hits[key] += 1

    products = [
        {
            "product": name,
            "amount": round(total, 4),
            "unit": unit,
            "times_used_on_jobs": job_hits[(name, unit)],
        }
        for (name, unit), total in sorted(amounts.items(), key=lambda kv: (-kv[1], kv[0][0]))
    ]

    if not products:
        if needle:
            answer = (
                f"No logged usage of products matching {material_name!r} "
                f"from {start.isoformat()} to {end.isoformat()} "
                f"(scanned {len(targets)} jobs)."
            )
        else:
            answer = (
                f"No product usage was logged on jobs from {start.isoformat()} "
                f"to {end.isoformat()} (scanned {len(targets)} jobs)."
            )
    else:
        lines = [
            f"Product used from {start.isoformat()} to {end.isoformat()} "
            f"across {len(targets)} jobs:"
        ]
        for row in products[:25]:
            lines.append(
                f"- {row['product']}: {row['amount']:g} {row['unit']} "
                f"(on {row['times_used_on_jobs']} jobs)"
            )
        if len(products) > 25:
            lines.append(f"- …and {len(products) - 25} more products")
        if truncated:
            lines.append(
                f"(Stopped after {max_work_orders} jobs — narrow the date range for a full total.)"
            )
        answer = "\n".join(lines)

    return {
        "answer": answer,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "jobs_scanned": len(targets),
        "jobs_with_usage": sum(1 for u in usage_lists if u),
        "application_records": applications,
        "products": products,
        "truncated": truncated,
        "filter_material_name": material_name,
    }


async def business_snapshot(
    client: FieldworkClient,
    *,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Plain-English ops snapshot for an owner."""
    start, end = _date_range(days=days, start_date=start_date, end_date=end_date)
    ops = await client.get_operations_summary(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    if not isinstance(ops, dict):
        return {
            "answer": "Couldn't read the operations summary from Fieldwork.",
            "raw": ops,
        }

    total = ops.get("total_count")
    completed = ops.get("completed_count")
    cancelled = ops.get("cancelled_count")
    missed = ops.get("missed_count")
    completed_value = ops.get("completed_production_value")
    planned_value = ops.get("planned_production_value")

    answer = (
        f"From {start.isoformat()} to {end.isoformat()}: "
        f"{completed} of {total} jobs completed"
        f"{'' if not cancelled else f', {cancelled} cancelled'}"
        f"{'' if not missed else f', {missed} missed'}. "
        f"Completed production value ${float(completed_value or 0):,.2f} "
        f"(planned ${float(planned_value or 0):,.2f})."
    )
    return {
        "answer": answer,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "operations": ops,
    }


async def schedule_overview(
    client: FieldworkClient,
    *,
    days: int | None = 7,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """What's on the schedule for a date range."""
    start, end = _date_range(days=days, start_date=start_date, end_date=end_date)
    # work_orders/search is more reliable than calendar/work_orders_only here
    rows = await _iter_work_orders(client, start=start, end=end)
    statuses: Counter[str] = Counter()
    for row in rows:
        statuses[str(row.get("status") or "unknown")] += 1

    status_bits = ", ".join(f"{n} {s}" for s, n in sorted(statuses.items())) or "none"
    answer = (
        f"Schedule from {start.isoformat()} to {end.isoformat()}: "
        f"{len(rows)} work orders ({status_bits})."
    )
    sample = []
    for row in rows[:10]:
        sample.append(
            {
                "id": row.get("id"),
                "status": row.get("status"),
                "starts_at": row.get("starts_at") or row.get("starts_at_date"),
                "customer_id": row.get("customer_id"),
                "customer_name": row.get("customer_name") or row.get("name"),
                "service_location_name": row.get("service_location_name"),
                "report_number": row.get("report_number"),
            }
        )
    return {
        "answer": answer,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_work_orders": len(rows),
        "by_status": dict(statuses),
        "sample": sample,
    }


# --- More owner questions: customers, money, team, routes -------------------

_SECRET_KEYS = {
    "api_key",
    "auth_token",
    "calls_auth_token",
    "stripe_pk",
    "stripe_sk",
    "password",
    "account_features",
}


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return {
        "id": user.get("id"),
        "name": f"{first} {last}".strip(),
        "email": user.get("email"),
        "phone_number": user.get("phone_number"),
        "job_title": user.get("job_title"),
        "is_technician": bool(user.get("is_technician")),
        "is_admin": bool(user.get("is_admin")),
        "service_route_id": user.get("service_route_id"),
        "service_route_name": user.get("service_route_name"),
        "license_number": user.get("license_number") or None,
    }


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


async def find_customers(
    client: FieldworkClient,
    *,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Find customers by name / search text."""
    q = (query or "").strip()
    if not q:
        raise ValueError("Provide a customer name or search text.")
    limit = max(1, min(int(limit), 25))
    results = await client.search_customers(query=q, page=1, per_page=limit)
    rows = results if isinstance(results, list) else []
    matches = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        matches.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or row.get("customer_name"),
                "status": row.get("status"),
                "account_number": row.get("account_number"),
                "tags": row.get("tags"),
            }
        )
    if not matches:
        answer = f'No customers found matching "{q}".'
    elif len(matches) == 1:
        m = matches[0]
        answer = f"Found customer {m['name']} (#{m['id']}, status: {m['status']})."
    else:
        names = ", ".join(f"{m['name']} (#{m['id']})" for m in matches[:8])
        answer = f'Found {len(matches)} customers matching "{q}": {names}.'
    return {"answer": answer, "query": q, "matches": matches}


async def who_owes_me_money(
    client: FieldworkClient,
    *,
    max_pages: int = 20,
    top_n: int = 10,
) -> dict[str, Any]:
    """Summarize unpaid / partially paid invoices."""
    unpaid_statuses = {"unpaid", "partial", "past_due", "overdue", "partially paid"}
    invoices: list[dict[str, Any]] = []
    page = 1
    per_page = 100
    while page <= max_pages:
        batch = await client.get(
            "/invoices",
            params={"page": page, "per_page": per_page, "sort_direction": "desc"},
        )
        if not isinstance(batch, list) or not batch:
            break
        for inv in batch:
            if not isinstance(inv, dict):
                continue
            status = str(inv.get("status") or "").lower()
            due = _money(inv.get("due_amount"))
            if due > 0 or status in unpaid_statuses:
                invoices.append(inv)
        if len(batch) < per_page:
            break
        page += 1

    total_due = sum(_money(i.get("due_amount")) for i in invoices)
    by_customer: dict[str, float] = defaultdict(float)
    for inv in invoices:
        name = str(inv.get("customer_name") or f"customer #{inv.get('customer_id')}")
        by_customer[name] += _money(inv.get("due_amount"))

    top = sorted(by_customer.items(), key=lambda kv: -kv[1])[: max(1, min(top_n, 25))]
    if not invoices:
        answer = "Nobody currently shows an outstanding invoice balance in Fieldwork."
    else:
        lines = [
            f"{len(invoices)} open invoices totaling ${total_due:,.2f} due.",
            "Top balances:",
        ]
        for name, amount in top:
            lines.append(f"- {name}: ${amount:,.2f}")
        answer = "\n".join(lines)

    return {
        "answer": answer,
        "open_invoice_count": len(invoices),
        "total_due": round(total_due, 2),
        "top_customers": [{"customer": n, "due": round(a, 2)} for n, a in top],
        "pages_scanned": page,
    }


async def money_snapshot(
    client: FieldworkClient,
    *,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Plain-English financial summary for a date range."""
    start, end = _date_range(days=days, start_date=start_date, end_date=end_date)
    fin = await client.get_financial_summary(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    if not isinstance(fin, dict):
        return {
            "answer": "Couldn't read the financial summary from Fieldwork.",
            "raw": fin,
        }

    # Fieldwork's shape can vary — surface known-looking money fields.
    interesting = {
        k: fin.get(k)
        for k in fin
        if any(
            x in k.lower()
            for x in ("revenue", "sales", "invoice", "payment", "collect", "tax", "total")
        )
    }
    bits = []
    for key, value in interesting.items():
        if isinstance(value, (int, float)) or (
            isinstance(value, str) and value.replace(".", "", 1).isdigit()
        ):
            bits.append(f"{key.replace('_', ' ')} ${float(value):,.2f}")
        else:
            bits.append(f"{key.replace('_', ' ')}: {value}")

    if bits:
        answer = (
            f"Financial snapshot from {start.isoformat()} to {end.isoformat()}: "
            + "; ".join(bits[:12])
            + "."
        )
    else:
        answer = (
            f"Got a financial summary for {start.isoformat()} to {end.isoformat()}, "
            "but the fields were unfamiliar — see `financial` in the tool result."
        )
    return {
        "answer": answer,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "financial": fin,
        "highlights": interesting,
    }


async def who_are_my_technicians(client: FieldworkClient) -> dict[str, Any]:
    """List technicians and which route they're on."""
    users = await client.get("/users")
    rows = users if isinstance(users, list) else []
    techs = [_public_user(u) for u in rows if isinstance(u, dict) and u.get("is_technician")]
    office = [
        _public_user(u)
        for u in rows
        if isinstance(u, dict) and not u.get("is_technician")
    ]

    routes = await client.list_service_routes()
    route_rows = []
    if isinstance(routes, list):
        for route in routes:
            if not isinstance(route, dict):
                continue
            user = route.get("user") if isinstance(route.get("user"), dict) else {}
            route_rows.append(
                {
                    "id": route.get("id"),
                    "name": route.get("name"),
                    "active": route.get("active"),
                    "technician": _public_user(user)["name"] if user else None,
                    "technician_id": user.get("id") if user else None,
                }
            )

    if not techs:
        answer = "No users are marked as technicians in Fieldwork."
    else:
        parts = []
        for t in techs:
            route = t.get("service_route_name") or "no route assigned"
            parts.append(f"{t['name']} ({route})")
        answer = f"You have {len(techs)} technicians: " + "; ".join(parts) + "."
        if route_rows:
            active = sum(1 for r in route_rows if r.get("active"))
            answer += f" There are {active} active service routes."

    return {
        "answer": answer,
        "technicians": techs,
        "office_users": office,
        "routes": route_rows,
    }


async def how_are_my_routes_doing(
    client: FieldworkClient,
    *,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Jobs completed per route over a date range."""
    start, end = _date_range(days=days, start_date=start_date, end_date=end_date)
    work_orders = await _iter_work_orders(client, start=start, end=end)
    by_route: Counter[str] = Counter()
    completed_by_route: Counter[str] = Counter()
    for wo in work_orders:
        route_ids = wo.get("service_route_ids") or []
        # list endpoint sometimes only has ids; names may need show_plain — use id label
        if isinstance(route_ids, list) and route_ids:
            label = f"route #{route_ids[0]}"
        else:
            label = "unassigned"
        # Prefer name if present on nested structures
        routes = wo.get("service_routes")
        if isinstance(routes, list) and routes and isinstance(routes[0], dict):
            label = str(routes[0].get("name") or label)
        by_route[label] += 1
        if str(wo.get("status") or "").lower() == "complete":
            completed_by_route[label] += 1

    # Resolve route ids to names when possible
    route_lookup: dict[str, str] = {}
    routes = await client.list_service_routes()
    if isinstance(routes, list):
        for route in routes:
            if isinstance(route, dict) and route.get("id") is not None:
                route_lookup[f"route #{route['id']}"] = str(route.get("name") or route["id"])

    ranked = []
    for label, count in by_route.most_common():
        name = route_lookup.get(label, label)
        ranked.append(
            {
                "route": name,
                "jobs": count,
                "completed": completed_by_route.get(label, 0),
            }
        )

    if not ranked:
        answer = f"No jobs found from {start.isoformat()} to {end.isoformat()}."
    else:
        bits = [f"{r['route']}: {r['completed']}/{r['jobs']} completed" for r in ranked]
        answer = (
            f"Route performance {start.isoformat()} to {end.isoformat()}: "
            + "; ".join(bits)
            + "."
        )
    return {
        "answer": answer,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "routes": ranked,
        "jobs_scanned": len(work_orders),
    }


async def who_did_the_most_jobs(
    client: FieldworkClient,
    *,
    days: int | None = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Rank technicians/routes by completed jobs (from work-order route assignment)."""
    # Fieldwork list payloads are route-centric; use route performance + tech roster.
    route_stats = await how_are_my_routes_doing(
        client, days=days, start_date=start_date, end_date=end_date
    )
    team = await who_are_my_technicians(client)
    route_to_tech = {
        r["name"]: r.get("technician")
        for r in team.get("routes", [])
        if isinstance(r, dict) and r.get("name")
    }

    leaderboard = []
    for row in route_stats.get("routes", []):
        route_name = row["route"]
        leaderboard.append(
            {
                "technician": route_to_tech.get(route_name) or "Unknown",
                "route": route_name,
                "completed_jobs": row["completed"],
                "total_jobs": row["jobs"],
            }
        )
    leaderboard.sort(key=lambda r: (-r["completed_jobs"], r["route"]))

    if not leaderboard:
        answer = "No job activity to rank technicians on for that period."
    else:
        top = leaderboard[0]
        answer = (
            f"Top producer: {top['technician']} on {top['route']} "
            f"with {top['completed_jobs']} completed jobs "
            f"({route_stats['start_date']} to {route_stats['end_date']})."
        )
        if len(leaderboard) > 1:
            rest = ", ".join(
                f"{r['technician']} ({r['completed_jobs']})" for r in leaderboard[1:5]
            )
            answer += f" Next: {rest}."

    return {
        "answer": answer,
        "start_date": route_stats["start_date"],
        "end_date": route_stats["end_date"],
        "leaderboard": leaderboard,
    }


async def what_products_do_we_carry(client: FieldworkClient) -> dict[str, Any]:
    """List materials/chemicals in the catalog."""
    materials = await client.list_materials()
    rows = materials if isinstance(materials, list) else []
    names = []
    for row in rows:
        if isinstance(row, dict):
            name = row.get("name") or row.get("material_name")
            if name:
                names.append(str(name))
    names_sorted = sorted(set(names), key=str.lower)
    if not names_sorted:
        answer = "No materials found in your Fieldwork catalog."
    else:
        preview = ", ".join(names_sorted[:20])
        more = f" (and {len(names_sorted) - 20} more)" if len(names_sorted) > 20 else ""
        answer = f"You have {len(names_sorted)} products/materials on file: {preview}{more}."
    return {
        "answer": answer,
        "product_count": len(names_sorted),
        "products": names_sorted,
    }
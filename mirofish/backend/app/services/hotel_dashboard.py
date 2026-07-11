"""Deterministic hotel dashboard contract built from uploaded source tables.

The narrative report is useful for interpretation, but it is not a stable data
contract.  This module deliberately reads only the uploaded Markdown tables so
dashboard figures always have a traceable source column and never depend on
parsing generated prose.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..utils.file_parser import FileParser


SCHEMA_VERSION = "hotel-dashboard.v1"

CANONICAL_PERFORMANCE = {
    "date", "property", "occupancy_pct", "adr_vnd", "revpar_vnd",
    "room_nights", "revenue_vnd", "booking_pace_pct", "pickup_room_nights",
    "pickup_24h_room_nights", "market_segment", "source", "channel",
    "guest_nationality", "lead_time_days", "cancellations",
    "budget_room_nights", "budget_adr_vnd", "last_year_room_nights",
    "ly_adr_vnd", "on_the_books_room_nights", "stly_otb_room_nights",
}
PMS_PERFORMANCE = {
    "date", "property", "rooms_available", "rooms_sold", "room_revenue",
    "adr", "occupancy", "market_segment", "channel", "guest_nationality",
    "lead_time_days", "cancellations", "budget_occupancy", "budget_adr",
    "ly_occupancy", "ly_adr", "otb_rooms",
}
PROPERTY_REFERENCE = {
    "property", "city", "province", "country", "property_type", "room_count",
    "currency", "timezone",
}
ROOM_INVENTORY = {
    "property", "room_id", "room_type", "floor", "bed_type", "max_guests",
    "size_sqm", "base_rate_vnd",
}
GUEST_FLOW = {
    "date", "property", "bookings_checking_in", "bookings_staying",
    "bookings_checking_out", "guests_checking_in", "guests_staying",
    "guests_checking_out", "staffing_risk_index", "staffing_status",
}

SCHEMAS: Sequence[Tuple[str, set[str]]] = (
    ("canonical_performance", CANONICAL_PERFORMANCE),
    ("pms_performance", PMS_PERFORMANCE),
    ("property_reference", PROPERTY_REFERENCE),
    ("room_inventory", ROOM_INVENTORY),
    ("guest_flow", GUEST_FLOW),
)


def _header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _split_markdown_row(line: str) -> Optional[List[str]]:
    value = line.strip()
    if "|" not in value:
        return None
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith(r"\|"):
        value = value[:-1]

    cells: List[str] = []
    cell: List[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        next_character = value[index + 1] if index + 1 < len(value) else ""
        if character == "\\" and next_character in {"|", "\\"}:
            cell.append(next_character)
            index += 2
            continue
        if character == "|":
            cells.append("".join(cell).strip().replace("<br>", "\n"))
            cell = []
        else:
            cell.append(character)
        index += 1
    cells.append("".join(cell).strip().replace("<br>", "\n"))
    return cells


def _markdown_tables(text: str) -> Iterable[Tuple[List[str], List[Dict[str, str]]]]:
    lines = text.splitlines()
    index = 0
    while index < len(lines) - 1:
        raw_headers = _split_markdown_row(lines[index])
        divider = _split_markdown_row(lines[index + 1])
        if (
            not raw_headers
            or not divider
            or len(raw_headers) != len(divider)
            or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in divider)
        ):
            index += 1
            continue

        headers = [_header(value) for value in raw_headers]
        rows: List[Dict[str, str]] = []
        row_index = index + 2
        while row_index < len(lines):
            cells = _split_markdown_row(lines[row_index])
            if cells is None:
                break
            cells = cells[:len(headers)] + [""] * max(0, len(headers) - len(cells))
            if any(cells):
                rows.append(dict(zip(headers, cells)))
            row_index += 1
        yield headers, rows
        index = row_index


def _schema_for(headers: Sequence[str]) -> Optional[str]:
    available = set(headers)
    return next((name for name, required in SCHEMAS if required <= available), None)


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "null", "none", "-"}:
        return None
    text = text.replace(",", "").replace("%", "")
    text = re.sub(r"^(?:vnd|usd|eur|gbp)\s*", "", text, flags=re.IGNORECASE)
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _count(value: Any) -> Optional[int]:
    parsed = _number(value)
    return int(round(parsed)) if parsed is not None else None


def _percent(value: Any) -> Optional[float]:
    parsed = _number(value)
    if parsed is None:
        return None
    return parsed * 100 if 0 <= parsed <= 1 else parsed


def _date(value: Any) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sum(rows: Iterable[Mapping[str, Any]], key: str) -> Optional[float]:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    return sum(values) if values else None


def _rounded(value: Optional[float], digits: int = 2) -> Optional[float | int]:
    if value is None:
        return None
    rounded = round(value, digits)
    return int(rounded) if rounded == int(rounded) else rounded


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _variance(current: Optional[float], reference: Optional[float]) -> Optional[float]:
    if current is None or reference is None:
        return None
    return current - reference


def _normalize_performance(row: Mapping[str, str], schema: str) -> Optional[Dict[str, Any]]:
    stay_date = _date(row.get("date"))
    property_id = row.get("property", "").strip()
    if not stay_date or not property_id:
        return None

    if schema == "canonical_performance":
        room_nights = _count(row.get("room_nights"))
        revenue = _number(row.get("revenue_vnd"))
        return {
            "source_schema": schema,
            "date": stay_date,
            "property": property_id,
            "rooms_available": None,
            "occupancy_pct": _percent(row.get("occupancy_pct")),
            "room_nights": room_nights,
            "adr": _number(row.get("adr_vnd")),
            "revpar": _number(row.get("revpar_vnd")),
            "revenue": revenue,
            "booking_pace_pct": _percent(row.get("booking_pace_pct")),
            "pickup_room_nights": _count(row.get("pickup_room_nights")),
            "pickup_24h_room_nights": _count(row.get("pickup_24h_room_nights")),
            "market_segment": row.get("market_segment", "").strip() or None,
            "source": row.get("source", "").strip() or None,
            "channel": row.get("channel", "").strip() or None,
            "guest_nationality": row.get("guest_nationality", "").strip() or None,
            "source_lead_time_days": _count(row.get("lead_time_days")),
            "cancellations": _count(row.get("cancellations")),
            "budget_room_nights": _count(row.get("budget_room_nights")),
            "budget_adr": _number(row.get("budget_adr_vnd")),
            "last_year_room_nights": _count(row.get("last_year_room_nights")),
            "last_year_adr": _number(row.get("ly_adr_vnd")),
            "on_the_books_rooms": _count(row.get("on_the_books_room_nights")),
            "stly_otb_rooms": _count(row.get("stly_otb_room_nights")),
            "currency_hint": "VND",
            # The canonical dictionary defines future room_nights as an
            # uploaded performance/OTB measure, not a model point forecast.
            "point_forecast_available": False,
        }

    rooms_available = _count(row.get("rooms_available"))
    budget_occupancy = _percent(row.get("budget_occupancy"))
    last_year_occupancy = _percent(row.get("ly_occupancy"))
    return {
        "source_schema": schema,
        "date": stay_date,
        "property": property_id,
        "rooms_available": rooms_available,
        "occupancy_pct": _percent(row.get("occupancy")),
        "room_nights": _count(row.get("rooms_sold")),
        "adr": _number(row.get("adr")),
        "revpar": None,
        "revenue": _number(row.get("room_revenue")),
        "booking_pace_pct": None,
        "pickup_room_nights": None,
        "pickup_24h_room_nights": None,
        "market_segment": row.get("market_segment", "").strip() or None,
        "source": None,
        "channel": row.get("channel", "").strip() or None,
        "guest_nationality": row.get("guest_nationality", "").strip() or None,
        "source_lead_time_days": _count(row.get("lead_time_days")),
        "cancellations": _count(row.get("cancellations")),
        "budget_room_nights": (
            rooms_available * budget_occupancy / 100
            if rooms_available is not None and budget_occupancy is not None else None
        ),
        "budget_adr": _number(row.get("budget_adr")),
        "last_year_room_nights": (
            rooms_available * last_year_occupancy / 100
            if rooms_available is not None and last_year_occupancy is not None else None
        ),
        "last_year_adr": _number(row.get("ly_adr")),
        "on_the_books_rooms": _count(row.get("otb_rooms")),
        "stly_otb_rooms": None,
        # The documented 17-column PMS contract uses USD. Its future
        # rooms_sold value is OTB, not an expected-final forecast.
        "currency_hint": "USD",
        "point_forecast_available": False,
    }


def _valid_performance(row: Mapping[str, Any]) -> bool:
    """Reject impossible numeric rows before they can affect aggregates."""
    required = ("room_nights", "on_the_books_rooms")
    if any(row.get(key) is None for key in required):
        return False
    if row.get("source_schema") == "pms_performance" and row.get("rooms_available") is None:
        return False
    if row.get("source_schema") == "canonical_performance" and row.get("occupancy_pct") is None:
        return False
    nonnegative = (
        "rooms_available", "room_nights", "adr", "revpar", "revenue",
        # Pickup is a net movement and can legitimately be negative.
        "cancellations",
        "budget_room_nights", "budget_adr", "last_year_room_nights",
        "last_year_adr", "on_the_books_rooms", "stly_otb_rooms",
    )
    if any(row.get(key) is not None and row[key] < 0 for key in nonnegative):
        return False
    if row.get("occupancy_pct") is not None and not 0 <= row["occupancy_pct"] <= 100:
        return False
    if row.get("rooms_available") is not None and row["rooms_available"] <= 0:
        return False
    if (
        row.get("rooms_available") is not None
        and row.get("room_nights") is not None
        and row["room_nights"] > row["rooms_available"]
    ):
        return False
    return True


def _normalize_property(row: Mapping[str, str]) -> Optional[Dict[str, Any]]:
    property_id = row.get("property", "").strip()
    if not property_id:
        return None
    city = row.get("city", "").strip() or None
    return {
        "id": property_id,
        "name": row.get("property_name", "").strip() or None,
        "city": city,
        "province": row.get("province", "").strip() or None,
        "country": row.get("country", "").strip() or None,
        "property_type": row.get("property_type", "").strip() or None,
        "rooms": _count(row.get("room_count")),
        "currency": row.get("currency", "").strip().upper() or None,
        "timezone": row.get("timezone", "").strip() or None,
    }


def _normalize_guest_flow(row: Mapping[str, str]) -> Optional[Dict[str, Any]]:
    stay_date = _date(row.get("date"))
    property_id = row.get("property", "").strip()
    if not stay_date or not property_id:
        return None
    return {
        "date": stay_date,
        "property": property_id,
        "bookings_checking_in": _count(row.get("bookings_checking_in")),
        "bookings_staying": _count(row.get("bookings_staying")),
        "bookings_checking_out": _count(row.get("bookings_checking_out")),
        "guests_checking_in": _count(row.get("guests_checking_in")),
        "guests_staying": _count(row.get("guests_staying")),
        "guests_checking_out": _count(row.get("guests_checking_out")),
        "staffing_risk_index": _number(row.get("staffing_risk_index")),
        "staffing_status": row.get("staffing_status", "").strip() or None,
    }


def _capacity(rows: Sequence[Mapping[str, Any]], property_info: Mapping[str, Any]) -> Optional[int]:
    configured = property_info.get("rooms")
    if configured:
        return int(configured)
    available = [row["rooms_available"] for row in rows if row.get("rooms_available")]
    if available:
        # PMS exports commonly repeat capacity for every segment row.
        return int(max(available))
    implied = [
        row["room_nights"] / (row["occupancy_pct"] / 100)
        for row in rows
        if row.get("room_nights") is not None and row.get("occupancy_pct", 0) > 0
    ]
    return int(round(median(implied))) if implied else None


def _weighted_adr(
    rows: Sequence[Mapping[str, Any]], rooms_key: str, adr_key: str
) -> Optional[float]:
    pairs = [
        (row.get(rooms_key), row.get(adr_key))
        for row in rows
        if row.get(rooms_key) is not None and row.get(adr_key) is not None
    ]
    denominator = sum(rooms for rooms, _ in pairs)
    return sum(rooms * adr for rooms, adr in pairs) / denominator if denominator else None


def _aggregate_daily(
    rows: Sequence[Dict[str, Any]],
    properties: Mapping[str, Dict[str, Any]],
    guest_flow: Mapping[Tuple[date, str], Dict[str, Any]],
    as_of_date: date,
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[date, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["date"], row["property"])].append(row)

    output: List[Dict[str, Any]] = []
    for (stay_date, property_id), source_rows in sorted(grouped.items()):
        capacity = _capacity(source_rows, properties.get(property_id, {}))
        room_nights = _sum(source_rows, "room_nights")
        revenue = _sum(source_rows, "revenue")
        adr = _ratio(revenue, room_nights) or _weighted_adr(source_rows, "room_nights", "adr")
        occupancy = (
            _ratio(room_nights, capacity) * 100
            if room_nights is not None and capacity else _sum(source_rows, "occupancy_pct")
        )
        revpar = _ratio(revenue, capacity) if capacity else _sum(source_rows, "revpar")
        otb = _sum(source_rows, "on_the_books_rooms")
        budget_rooms = _sum(source_rows, "budget_room_nights")
        budget_adr = _weighted_adr(source_rows, "budget_room_nights", "budget_adr")
        budget_revenue = (
            budget_rooms * budget_adr
            if budget_rooms is not None and budget_adr is not None else None
        )
        last_year_rooms = _sum(source_rows, "last_year_room_nights")
        last_year_adr = _weighted_adr(
            source_rows, "last_year_room_nights", "last_year_adr"
        )
        last_year_revenue = (
            last_year_rooms * last_year_adr
            if last_year_rooms is not None and last_year_adr is not None else None
        )
        stly_otb = _sum(source_rows, "stly_otb_rooms")
        point_forecast_available = bool(
            source_rows and all(row.get("point_forecast_available") for row in source_rows)
        )
        forecast_room_nights = room_nights if point_forecast_available else None
        forecast_occupancy = occupancy if point_forecast_available else None
        forecast_adr = adr if point_forecast_available else None
        forecast_revenue = revenue if point_forecast_available else None
        revenue_below_budget = (
            max(budget_revenue - forecast_revenue, 0)
            if budget_revenue is not None and forecast_revenue is not None else None
        )
        risk_index = (
            min(revenue_below_budget / budget_revenue * 100, 100)
            if revenue_below_budget is not None and budget_revenue else None
        )
        flow = guest_flow.get((stay_date, property_id), {})
        output.append({
            "date": stay_date.isoformat(),
            "property": property_id,
            "lead_days": (stay_date - as_of_date).days,
            "data_kind": "source_snapshot" if stay_date > as_of_date else "actual_or_snapshot",
            "rooms_available": capacity,
            "room_nights": _rounded(room_nights),
            "occupancy_pct": _rounded(occupancy),
            "adr": _rounded(adr),
            "revpar": _rounded(revpar),
            "revenue": _rounded(revenue),
            "on_the_books_rooms": _rounded(otb),
            "on_the_books_occupancy_pct": _rounded(
                _ratio(otb, capacity) * 100 if capacity else None
            ),
            # Neither supported upload schema contains explicit expected-final
            # model output. Preserve those fields as unavailable.
            "expected_final_room_nights": _rounded(forecast_room_nights),
            "expected_final_occupancy_pct": _rounded(forecast_occupancy),
            "forecast_adr": _rounded(forecast_adr),
            "forecast_revenue": _rounded(forecast_revenue),
            "forecast_basis": (
                "uploaded_performance_fields" if point_forecast_available else None
            ),
            "forecast_lo50_room_nights": None,
            "forecast_hi50_room_nights": None,
            "forecast_lo80_room_nights": None,
            "forecast_hi80_room_nights": None,
            "forecast_lo50_occupancy_pct": None,
            "forecast_hi50_occupancy_pct": None,
            "forecast_lo80_occupancy_pct": None,
            "forecast_hi80_occupancy_pct": None,
            "budget_room_nights": _rounded(budget_rooms),
            "budget_occupancy_pct": _rounded(
                _ratio(budget_rooms, capacity) * 100 if capacity else None
            ),
            "budget_adr": _rounded(budget_adr),
            "budget_revenue": _rounded(budget_revenue),
            "last_year_room_nights": _rounded(last_year_rooms),
            "last_year_occupancy_pct": _rounded(
                _ratio(last_year_rooms, capacity) * 100 if capacity else None
            ),
            "last_year_adr": _rounded(last_year_adr),
            "last_year_revenue": _rounded(last_year_revenue),
            "stly_otb_rooms": _rounded(stly_otb),
            "pace_vs_stly_pct": _rounded(
                _ratio((otb - stly_otb), stly_otb) * 100
                if otb is not None and stly_otb is not None else None
            ),
            "booking_pace_pct": _rounded(
                _ratio(otb, stly_otb) * 100
                if otb is not None and stly_otb is not None else None
            ),
            "pickup_room_nights": _rounded(_sum(source_rows, "pickup_room_nights")),
            "pickup_24h_room_nights": _rounded(
                _sum(source_rows, "pickup_24h_room_nights")
            ),
            # Canonical pickup is current OTB at seven days before arrival
            # minus the previous daily snapshot (eight days before arrival).
            # It is not a rolling seven-day pickup despite a misleading
            # `pickup7` variable name in the sample generator.
            "pickup_7d_rooms": None,
            "cancellations": _rounded(_sum(source_rows, "cancellations")),
            # The upload contract defines cancellations on the reporting day;
            # it does not provide a seven-day cancellation window.
            "cancellations_7d_rooms": None,
            "rooms_needed_for_budget": _rounded(
                max(budget_rooms - otb, 0)
                if budget_rooms is not None and otb is not None else None
            ),
            "forecast_room_variance_to_budget": _rounded(
                _variance(forecast_room_nights, budget_rooms)
            ),
            "forecast_revenue_variance_to_budget": _rounded(
                _variance(forecast_revenue, budget_revenue)
            ),
            "forecast_room_variance_to_last_year": _rounded(
                _variance(forecast_room_nights, last_year_rooms)
            ),
            "forecast_revenue_variance_to_last_year": _rounded(
                _variance(forecast_revenue, last_year_revenue)
            ),
            "revenue_below_budget": _rounded(revenue_below_budget),
            "revenue_risk_index": _rounded(risk_index),
            "forecast_revision_room_nights": None,
            "forecast_revision_revenue": None,
            "bookings_checking_in": flow.get("bookings_checking_in"),
            "bookings_staying": flow.get("bookings_staying"),
            "bookings_checking_out": flow.get("bookings_checking_out"),
            "guests_checking_in": flow.get("guests_checking_in"),
            "guests_staying": flow.get("guests_staying"),
            "guests_checking_out": flow.get("guests_checking_out"),
            "staffing_risk_index": flow.get("staffing_risk_index"),
            "staffing_status": flow.get("staffing_status"),
        })
    return output


def _breakdown(
    rows: Sequence[Dict[str, Any]],
    dimension: str,
    label: str,
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    scoped = [row for row in rows if start <= row["date"] <= end and row.get(dimension)]
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    totals: Dict[str, float] = defaultdict(float)
    for row in scoped:
        grouped[(row["property"], row[dimension])].append(row)
        totals[row["property"]] += row.get("on_the_books_rooms") or 0

    output = []
    for (property_id, value), source_rows in sorted(grouped.items()):
        source_room_nights = _sum(source_rows, "room_nights")
        cancellations = _sum(source_rows, "cancellations")
        otb = _sum(source_rows, "on_the_books_rooms")
        adr = _weighted_adr(source_rows, "on_the_books_rooms", "adr")
        revenue = otb * adr if otb is not None and adr is not None else None
        stly_otb = _sum(source_rows, "stly_otb_rooms")
        record = {
            "property": property_id,
            label: value,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            # Forward mix is explicitly on-the-books. Keep the uploaded
            # performance measure separately for traceability.
            "room_nights": _rounded(otb),
            "source_room_nights": _rounded(source_room_nights),
            "on_the_books_rooms": _rounded(otb),
            "revenue": _rounded(revenue),
            "adr": _rounded(adr),
            "share_pct": _rounded(
                _ratio(otb, totals[property_id]) * 100
                if totals[property_id] else None
            ),
            "cancellations": _rounded(cancellations),
            "cancellation_rate_pct": _rounded(
                _ratio(cancellations, (otb or 0) + (cancellations or 0)) * 100
                if cancellations is not None and ((otb or 0) + cancellations) else None
            ),
            "pickup_room_nights": _rounded(_sum(source_rows, "pickup_room_nights")),
            "pickup_24h_room_nights": _rounded(
                _sum(source_rows, "pickup_24h_room_nights")
            ),
            "budget_room_nights": _rounded(_sum(source_rows, "budget_room_nights")),
            "last_year_room_nights": _rounded(stly_otb),
            "stly_otb_rooms": _rounded(stly_otb),
            "delta_last_year_pct": _rounded(
                _ratio((otb - stly_otb), stly_otb) * 100
                if otb is not None and stly_otb is not None else None
            ),
        }
        if label == "nationality":
            record["name"] = value
        output.append(record)
    return output


def _risk_level(score: float) -> str:
    if score >= 20:
        return "critical"
    if score >= 10:
        return "high"
    if score >= 5:
        return "watch"
    return "low"


def _risks_and_actions(
    daily: Sequence[Dict[str, Any]], as_of_date: date, currency: Optional[str]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidates = [
        row for row in daily
        if 0 < row["lead_days"] <= 90
        and row.get("pace_vs_stly_pct") is not None
        and row["pace_vs_stly_pct"] <= -5
    ]
    candidates.sort(key=lambda row: (row["pace_vs_stly_pct"], row["date"], row["property"]))
    risks: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    for row in candidates[:20]:
        risk_id = f"pace-gap:{row['property']}:{row['date']}"
        pace_gap_pct = abs(row["pace_vs_stly_pct"])
        room_gap = max((row.get("stly_otb_rooms") or 0) - (row.get("on_the_books_rooms") or 0), 0)
        level = _risk_level(pace_gap_pct)
        risk = {
            "id": risk_id,
            "kind": "risk",
            "severity": "risk" if level in {"high", "critical"} else "watch",
            "level": level,
            "type": "booking_pace_behind_stly",
            "title": f"Booking pace behind same time last year for {row['property']} on {row['date']}",
            "summary": (
                f"The uploaded OTB snapshot is {pace_gap_pct}% behind the same "
                "lead-time snapshot last year for this stay date."
            ),
            "property": row["property"],
            "date_from": row["date"],
            "date_to": row["date"],
            "segment": None,
            "channel": None,
            "trigger": "on_the_books_rooms < stly_otb_rooms",
            "threshold": {
                "metric": "pace_vs_stly_pct",
                "operator": "<=",
                "value": -5,
                "unit": "percent",
            },
            "evidence": {
                "on_the_books_rooms": row.get("on_the_books_rooms"),
                "stly_otb_rooms": row.get("stly_otb_rooms"),
                "pace_vs_stly_pct": row.get("pace_vs_stly_pct"),
                "room_gap_to_stly": room_gap,
                "cancellations": row.get("cancellations"),
            },
            "evidence_label": "Uploaded OTB versus STLY OTB at the same lead time",
            "confidence": None,
            "confidence_basis": "not_available",
            "source": "deterministic_source_data_rule",
        }
        action_id = f"action:{risk_id}"
        action = {
            "id": action_id,
            "risk_id": risk_id,
            "status": "proposed",
            "rule_based": True,
            "scope": {
                "property": row["property"],
                "date_from": row["date"],
                "date_to": row["date"],
                "segment": None,
                "channel": None,
            },
            "recommendation": (
                "Review the rate, inventory, and channel plan for this stay date; "
                "validate pickup and cancellation drivers before changing controls."
            ),
            "rationale": (
                f"The source OTB snapshot is {pace_gap_pct}% behind the uploaded "
                "same-time-last-year snapshot."
            ),
            "impact": None,
            "assumptions": [
                "The OTB and STLY OTB fields use the same lead-time definition.",
                "No rate change should be made without validating current restrictions and demand context.",
            ],
            "owner": None,
            "deadline": None,
        }
        risks.append(risk)
        actions.append(action)
    return risks, actions


def _empty_output(
    *, job_id: str, project_id: str, created_at: str, completed_at: Optional[str],
    output_locale: str, source_files: Sequence[Mapping[str, Any]], warnings: List[str],
    accepted_by_feed: Optional[Mapping[str, int]] = None,
    rejected_by_feed: Optional[Mapping[str, int]] = None,
    source_status: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    accepted_by_feed = accepted_by_feed or {}
    rejected_by_feed = rejected_by_feed or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "available": False,
        "run_metadata": {
            "job_id": job_id,
            "project_id": project_id,
            "as_of": created_at,
            "as_of_basis": "forecast_job_submission_time",
            "generated_at": completed_at,
            "output_locale": output_locale,
            "currency": None,
            "currencies": [],
            "timezone": None,
            "properties": [],
            "source_files": [item.get("filename") for item in source_files],
            "date_from": None,
            "date_to": None,
        },
        "data_status": {
            "status": "unavailable",
            "accepted_rows": sum(accepted_by_feed.values()),
            "rejected_rows": sum(rejected_by_feed.values()),
            "rows_by_feed": {
                key: {
                    "accepted": accepted_by_feed.get(key, 0),
                    "rejected": rejected_by_feed.get(key, 0),
                }
                for key in sorted(set(accepted_by_feed) | set(rejected_by_feed))
            },
            "missing_feeds": ["daily_performance"],
            "optional_missing_feeds": ["property_reference", "guest_flow", "room_inventory"],
            "freshness": [],
            "sources": list(source_status or []),
            "warnings": warnings,
        },
        "daily_forecast": [],
        "breakdowns": {
            "segments": [], "channels": [], "nationalities": [],
            "pace": [], "pickup": [], "guest_flow": [],
        },
        "risks": [],
        "actions": [],
        "model_checks": {
            "last_successful_run": completed_at,
            "historical_forecast_error_rooms": None,
            "historical_forecast_error_pct": None,
            "forecast_bias": None,
            "enough_data_for_point_forecast": False,
            "missing_metrics": [
                "point_forecast", "forecast_intervals", "historical_forecast_error",
                "forecast_bias", "forecast_revision",
            ],
        },
        "capabilities": {
            "hotel_dashboard": False,
            "point_forecast": False,
            "forecast_intervals": False,
            "forecast_revision": False,
            "historical_forecast_error": False,
            "segment_breakdown": False,
            "channel_breakdown": False,
            "nationality_breakdown": False,
            "pace_vs_stly": False,
            "pickup": False,
            "pickup_7d": False,
            "cancellations": False,
            "cancellations_7d": False,
            "guest_flow": False,
            "action_workflow": False,
        },
    }


def build_hotel_dashboard(
    *,
    job_id: str,
    project_id: str,
    file_paths: Sequence[str],
    source_files: Sequence[Mapping[str, Any]],
    created_at: str,
    completed_at: Optional[str],
    output_locale: str = "en",
) -> Dict[str, Any]:
    """Build the versioned dashboard payload from recognized uploaded tables."""
    stored_names = {
        str(item.get("stored_filename")): str(item.get("filename") or item.get("stored_filename"))
        for item in source_files
    }
    performance: List[Dict[str, Any]] = []
    property_rows: List[Dict[str, Any]] = []
    flow_rows: List[Dict[str, Any]] = []
    rooms_by_property: Dict[str, set[str]] = defaultdict(set)
    accepted_by_feed: Dict[str, int] = defaultdict(int)
    rejected_by_feed: Dict[str, int] = defaultdict(int)
    source_status: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for file_path in file_paths:
        path = Path(file_path)
        source_name = stored_names.get(path.name, path.name)
        source_record = {
            "filename": source_name,
            "schemas": [],
            "accepted_rows": 0,
            "rejected_rows": 0,
        }
        try:
            text = FileParser.extract_text(str(path))
        except Exception as exc:
            warnings.append(f"Could not read {source_name}: {exc}")
            source_record["error"] = str(exc)
            source_status.append(source_record)
            continue

        for headers, rows in _markdown_tables(text):
            schema = _schema_for(headers)
            if not schema:
                continue
            source_record["schemas"].append(schema)
            for raw_row in rows:
                normalized: Optional[Dict[str, Any]]
                if schema in {"canonical_performance", "pms_performance"}:
                    normalized = _normalize_performance(raw_row, schema)
                    if normalized and _valid_performance(normalized):
                        performance.append(normalized)
                    else:
                        normalized = None
                elif schema == "property_reference":
                    normalized = _normalize_property(raw_row)
                    if normalized:
                        property_rows.append(normalized)
                elif schema == "guest_flow":
                    normalized = _normalize_guest_flow(raw_row)
                    if normalized:
                        flow_rows.append(normalized)
                else:
                    property_id = raw_row.get("property", "").strip()
                    room_id = raw_row.get("room_id", "").strip()
                    normalized = {"property": property_id, "room_id": room_id} if property_id and room_id else None
                    if normalized:
                        rooms_by_property[property_id].add(room_id)

                if normalized:
                    accepted_by_feed[schema] += 1
                    source_record["accepted_rows"] += 1
                else:
                    rejected_by_feed[schema] += 1
                    source_record["rejected_rows"] += 1
        if not source_record["schemas"]:
            warnings.append(f"No supported hotel table was found in {source_name}.")
        source_record["schemas"] = sorted(set(source_record["schemas"]))
        source_status.append(source_record)

    if performance:
        # The documented import key is stay-date/property/commercial slice.
        # Later rows win deterministically, matching restatement/upsert rules.
        deduplicated: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        duplicate_count = 0
        for row in performance:
            key = (
                row["date"], row["property"], row.get("market_segment"),
                row.get("channel"),
            )
            if key in deduplicated:
                duplicate_count += 1
            deduplicated[key] = row
        performance = list(deduplicated.values())
        if duplicate_count:
            warnings.append(
                f"{duplicate_count} duplicate performance rows were replaced by later rows."
            )

    if not performance:
        return _empty_output(
            job_id=job_id,
            project_id=project_id,
            created_at=created_at,
            completed_at=completed_at,
            output_locale=output_locale,
            source_files=source_files,
            warnings=warnings + ["A recognized daily performance table is required."],
            accepted_by_feed=accepted_by_feed,
            rejected_by_feed=rejected_by_feed,
            source_status=source_status,
        )

    properties = {item["id"]: item for item in property_rows}
    for property_id in sorted({row["property"] for row in performance}):
        item = properties.setdefault(property_id, {
            "id": property_id, "name": None, "city": None, "province": None,
            "country": None, "property_type": None, "rooms": None,
            "currency": None, "timezone": None,
        })
        inventory_count = len(rooms_by_property.get(property_id, set()))
        if not item.get("rooms") and inventory_count:
            item["rooms"] = inventory_count
        elif item.get("rooms") and inventory_count and item["rooms"] != inventory_count:
            warnings.append(
                f"{property_id} property room_count ({item['rooms']}) differs from "
                f"unique room inventory rows ({inventory_count})."
            )

    flow_by_key = {(row["date"], row["property"]): row for row in flow_rows}
    created = _datetime(created_at)
    as_of_date = created.date() if created else datetime.now().date()
    daily = _aggregate_daily(performance, properties, flow_by_key, as_of_date)
    dates = [row["date"] for row in performance]
    date_from = min(dates)
    date_to = max(dates)

    currencies = sorted({item["currency"] for item in properties.values() if item.get("currency")})
    if not currencies:
        currencies = sorted({row["currency_hint"] for row in performance if row.get("currency_hint")})
    if len(currencies) == 1:
        for item in properties.values():
            item["currency"] = item.get("currency") or currencies[0]
    currency = currencies[0] if len(currencies) == 1 else None
    if len(currencies) > 1:
        warnings.append("Multiple source currencies are present; portfolio currency totals are unavailable.")
    timezones = sorted({item["timezone"] for item in properties.values() if item.get("timezone")})
    timezone = timezones[0] if len(timezones) == 1 else None

    breakdown_start = as_of_date + timedelta(days=1)
    breakdown_end = as_of_date + timedelta(days=30)
    forward_daily = [row for row in daily if 0 <= row["lead_days"] <= 90]
    pace = [{
        "date": row["date"],
        "property": row["property"],
        "on_the_books_rooms": row["on_the_books_rooms"],
        "stly_otb_rooms": row["stly_otb_rooms"],
        "booking_pace_pct": row["booking_pace_pct"],
        "pace_vs_stly_pct": row["pace_vs_stly_pct"],
    } for row in forward_daily if row["on_the_books_rooms"] is not None]
    pickup = [{
        "date": row["date"],
        "property": row["property"],
        "pickup_room_nights": row["pickup_room_nights"],
        "pickup_24h_room_nights": row["pickup_24h_room_nights"],
        "pickup_7d_rooms": None,
        "cancellations": row["cancellations"],
        "cancellations_7d_rooms": None,
    } for row in forward_daily if row["pickup_room_nights"] is not None]
    guest_flow_output = [{
        key: (value.isoformat() if key == "date" else value)
        for key, value in row.items()
    } for row in sorted(flow_rows, key=lambda row: (row["date"], row["property"]))]

    risks, actions = _risks_and_actions(daily, as_of_date, currency)
    has_stly = any(row.get("stly_otb_rooms") is not None for row in performance)
    has_pickup = any(row.get("pickup_room_nights") is not None for row in performance)
    has_cancellations = any(row.get("cancellations") is not None for row in performance)
    has_segments = any(row.get("market_segment") for row in performance)
    has_channels = any(row.get("channel") for row in performance)
    has_nationalities = any(row.get("guest_nationality") for row in performance)
    has_point_forecast = any(
        row.get("expected_final_room_nights") is not None and row["lead_days"] > 0
        for row in daily
    )
    has_properties = bool(property_rows or rooms_by_property)
    missing_feeds: List[str] = []
    optional_missing = []
    if not has_properties:
        optional_missing.append("property_reference")
    if not flow_rows:
        optional_missing.append("guest_flow")
    if not rooms_by_property:
        optional_missing.append("room_inventory")
    warnings.append(
        "Source extract timestamps are not included in the upload; freshness is based on job receipt time."
    )
    warnings.append(
        "Forecast intervals, historical error, bias, and forecast revision are unavailable and remain null."
    )
    if sum(rejected_by_feed.values()):
        warnings.append("One or more recognized source rows were rejected because date/property keys were invalid.")

    freshness = []
    for property_id in sorted(properties):
        property_dates = [row["date"] for row in performance if row["property"] == property_id]
        freshness.append({
            "property": property_id,
            "received_at": created_at,
            "source_as_of": None,
            "status": "unknown",
            "reason": "The source tables do not include an extract timestamp.",
            "date_from": min(property_dates).isoformat() if property_dates else None,
            "date_to": max(property_dates).isoformat() if property_dates else None,
        })

    accepted_total = sum(accepted_by_feed.values())
    rejected_total = sum(rejected_by_feed.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "run_metadata": {
            "job_id": job_id,
            "project_id": project_id,
            "as_of": created_at,
            "as_of_basis": "forecast_job_submission_time",
            "generated_at": completed_at,
            "output_locale": output_locale,
            "currency": currency,
            "currencies": currencies,
            "timezone": timezone,
            "properties": [properties[key] for key in sorted(properties)],
            "source_files": [item.get("filename") for item in source_files],
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "breakdown_date_from": breakdown_start.isoformat(),
            "breakdown_date_to": breakdown_end.isoformat(),
        },
        "data_status": {
            "status": "ready" if has_properties else "partial",
            "accepted_rows": accepted_total,
            "rejected_rows": rejected_total,
            "rows_by_feed": {
                key: {
                    "accepted": accepted_by_feed.get(key, 0),
                    "rejected": rejected_by_feed.get(key, 0),
                }
                for key in sorted(set(accepted_by_feed) | set(rejected_by_feed))
            },
            "missing_feeds": missing_feeds,
            "optional_missing_feeds": optional_missing,
            "freshness": freshness,
            "sources": source_status,
            "warnings": warnings,
        },
        "daily_forecast": daily,
        "breakdowns": {
            "segments": _breakdown(
                performance, "market_segment", "segment", breakdown_start, breakdown_end
            ),
            "channels": _breakdown(
                performance, "channel", "channel", breakdown_start, breakdown_end
            ),
            "nationalities": _breakdown(
                performance, "guest_nationality", "nationality", breakdown_start, breakdown_end
            ),
            "pace": pace,
            "pickup": pickup,
            "guest_flow": guest_flow_output,
        },
        "risks": risks,
        "actions": actions,
        "model_checks": {
            "last_successful_run": completed_at,
            "historical_forecast_error_rooms": None,
            "historical_forecast_error_pct": None,
            "forecast_bias": None,
            "enough_data_for_point_forecast": has_point_forecast,
            "missing_metrics": (
                ([] if has_point_forecast else ["point_forecast"])
                + ["forecast_intervals", "historical_forecast_error", "forecast_bias",
                   "forecast_revision"]
            ),
        },
        "capabilities": {
            "hotel_dashboard": True,
            "point_forecast": has_point_forecast,
            "forecast_intervals": False,
            "forecast_revision": False,
            "historical_forecast_error": False,
            "segment_breakdown": has_segments,
            "channel_breakdown": has_channels,
            "nationality_breakdown": has_nationalities,
            "pace_vs_stly": has_stly,
            "pickup": has_pickup,
            "pickup_7d": False,
            "cancellations": has_cancellations,
            "cancellations_7d": False,
            "guest_flow": bool(flow_rows),
            "action_workflow": False,
        },
    }

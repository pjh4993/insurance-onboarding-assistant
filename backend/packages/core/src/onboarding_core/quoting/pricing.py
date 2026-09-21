"""Rating, term and quote-validity rules. Plain code, no I/O (entity-dictionary.md: Product.rating,
Product.term_rule, Quote.valid_until)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from onboarding_core.util import parse_date


class RatingError(ValueError):
    """The product's rating rule cannot be evaluated with the object's attributes."""


@dataclass(frozen=True)
class Premium:
    premium_minor: int
    rating_inputs: dict[str, Any]


def trip_length_days(attrs: dict[str, Any]) -> int | None:
    """Inclusive day count: departing 10-03 and returning 10-07 is 5 days."""
    dep, ret = parse_date(attrs.get("departure_date")), parse_date(attrs.get("return_date"))
    if dep is None or ret is None:
        return None
    return (ret - dep).days + 1


def _basis_value(basis: str, attrs: dict[str, Any], inputs: dict[str, Any]) -> int:
    if basis == "PURCHASE_PRICE":
        value = attrs.get("purchase_price_minor")
    elif basis == "MSRP":
        value = attrs.get("msrp_minor")
        if value is None and attrs.get("purchase_price_minor") is not None:
            # No list price known (e.g. partner purchase record): fall back to what the customer paid.
            value = attrs["purchase_price_minor"]
            inputs["basis_fallback"] = "PURCHASE_PRICE"
    elif basis == "TRIP_COST":
        value = attrs.get("trip_cost_minor")
    else:
        raise RatingError(f"unknown rating basis {basis!r}")
    if value is None:
        raise RatingError(f"missing value for rating basis {basis}")
    inputs["basis"] = basis
    inputs["basis_value_minor"] = int(value)
    return int(value)


def _round(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def compute_premium(rating: dict[str, Any], attrs: dict[str, Any]) -> Premium:
    """Premium per billing period, in minor units."""
    method = rating.get("method")
    inputs: dict[str, Any] = {"method": method}
    minimum = rating.get("min_premium_minor")

    if method == "FLAT":
        premium = _round(Decimal(str(rating["rate"])))
        inputs["rate"] = rating["rate"]
    elif method == "PERCENT":
        base = _basis_value(rating.get("basis", ""), attrs, inputs)
        premium = _round(Decimal(base) * Decimal(str(rating["rate"])))
        inputs["rate"] = rating["rate"]
    elif method == "TIERED":
        base = _basis_value(rating.get("basis", ""), attrs, inputs)
        premium = None
        for tier in rating["tiers"]:
            upper = tier.get("up_to_minor")
            if upper is None or base <= upper:
                premium = int(tier["premium_minor"])
                inputs["tier_up_to_minor"] = upper
                break
        if premium is None:
            raise RatingError(f"basis value {base} is above the last tier")
    elif method == "PER_TRIP_DAY":
        days = trip_length_days(attrs)
        if days is None or days <= 0:
            raise RatingError("trip dates are required for PER_TRIP_DAY rating")
        premium = _round(Decimal(days) * Decimal(str(rating["rate"])))
        inputs.update(trip_length_days=days, rate=rating["rate"])
    else:
        raise RatingError(f"unknown rating method {method!r}")

    if minimum is not None and premium < minimum:
        inputs["min_premium_applied"] = True
        premium = int(minimum)
    if minimum is not None:
        inputs["min_premium_minor"] = minimum
    return Premium(premium_minor=premium, rating_inputs=inputs)


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _add_length(start: date, length: int, unit: str) -> date:
    if unit == "DAY":
        return start + timedelta(days=length)
    if unit == "MONTH":
        return add_months(start, length)
    if unit == "YEAR":
        return add_months(start, 12 * length)
    raise RatingError(f"unknown term unit {unit!r}")


def default_warranty_end(attrs: dict[str, Any]) -> date | None:
    """Manufacturer warranty end; when unknown assume one year from purchase."""
    explicit = parse_date(attrs.get("manufacturer_warranty_end_date"))
    if explicit:
        return explicit
    purchased = parse_date(attrs.get("purchase_date"))
    return add_months(purchased, 12) - timedelta(days=1) if purchased else None


def compute_term(term_rule: dict[str, Any], attrs: dict[str, Any], today: date) -> tuple[date, date]:
    """(term_start_date, term_end_date), both inclusive."""
    starts = term_rule.get("starts")
    if starts == "TRIP_DEPARTURE":
        dep, ret = parse_date(attrs.get("departure_date")), parse_date(attrs.get("return_date"))
        if dep is None or ret is None:
            raise RatingError("trip dates are required for a TRIP_DEPARTURE term")
        return dep, ret
    if starts == "PURCHASE_DATE":
        # Cover starts the day the policy is bought, i.e. the quote date.
        start = today
    elif starts == "NEXT_DAY":
        start = today + timedelta(days=1)
    elif starts == "WARRANTY_END":
        warranty_end = default_warranty_end(attrs)
        if warranty_end is None:
            raise RatingError("purchase date or warranty end is required for a WARRANTY_END term")
        start = warranty_end + timedelta(days=1)
    else:
        raise RatingError(f"unknown term start {starts!r}")
    end = _add_length(start, int(term_rule["length"]), term_rule["unit"]) - timedelta(days=1)
    return start, end


def quote_valid_until(created_at: datetime, term_start_date: date) -> datetime:
    """min(created_at + 24h, term_start_date 00:00 UTC).

    When cover starts on the quote date itself (PURCHASE_DATE products) the term-start bound is
    already in the past; applying it would make the quote invalid on creation, so only a
    term start that is still ahead of `created_at` caps the 24 h window."""
    window = created_at + timedelta(hours=24)
    start_midnight = datetime.combine(term_start_date, time.min, tzinfo=UTC)
    if start_midnight <= created_at:
        return window
    return min(window, start_midnight)

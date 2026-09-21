"""Rating, term and quote-validity rules (no DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domain.catalog_seed import PRODUCTS
from app.domain.pricing import (
    RatingError,
    add_months,
    compute_premium,
    compute_term,
    quote_valid_until,
    trip_length_days,
)

CATALOG = {p["product_code"]: p for p in PRODUCTS}
TODAY = date(2026, 9, 21)


def test_eight_seed_products_two_markets_four_types():
    assert len(PRODUCTS) == 8
    for market in ("KR", "US"):
        types = {p["product_type"] for p in PRODUCTS if p["jurisdictions"] == [market]}
        assert types == {"MOBILE_INSURANCE", "DEVICE_PROTECTION", "EXTENDED_WARRANTY", "TRAVEL_PROTECTION"}


@pytest.mark.parametrize(
    ("basis_value", "expected"),
    [(500000, 5990), (500001, 7990), (1350000, 9990), (2500000, 13990), (2500001, 15990)],
)
def test_tiered_on_msrp_uses_inclusive_upper_bounds(basis_value, expected):
    p = compute_premium(CATALOG["KR-MOB-SWAP"]["rating"], {"msrp_minor": basis_value})
    assert p.premium_minor == expected
    assert p.rating_inputs["basis"] == "MSRP" and p.rating_inputs["basis_value_minor"] == basis_value


def test_msrp_falls_back_to_purchase_price_and_records_it():
    p = compute_premium(CATALOG["KR-MOB-SWAP"]["rating"], {"purchase_price_minor": 1350000})
    assert p.premium_minor == 9990 and p.rating_inputs["basis_fallback"] == "PURCHASE_PRICE"


def test_tiered_on_purchase_price_us_laptop():
    assert (
        compute_premium(CATALOG["US-DEV-LAPTOP-2Y"]["rating"], {"purchase_price_minor": 129900}).premium_minor == 13000
    )
    assert (
        compute_premium(CATALOG["US-DEV-LAPTOP-2Y"]["rating"], {"purchase_price_minor": 200000}).premium_minor == 18000
    )


def test_tiered_above_last_bounded_tier_is_an_error():
    with pytest.raises(RatingError):
        compute_premium(CATALOG["KR-EW-HOME"]["rating"], {"purchase_price_minor": 5000001})


def test_percent_with_minimum():
    rating = CATALOG["US-TRV-SINGLE"]["rating"]
    assert compute_premium(rating, {"trip_cost_minor": 250000}).premium_minor == 15000  # 6% of $2,500
    low = compute_premium(rating, {"trip_cost_minor": 30000})  # 6% = $18 < $50 minimum
    assert low.premium_minor == 5000 and low.rating_inputs["min_premium_applied"] is True


def test_per_trip_day_with_minimum():
    rating = CATALOG["KR-TRV-OVERSEAS"]["rating"]
    five = {"departure_date": "2026-10-03", "return_date": "2026-10-07"}
    assert trip_length_days(five) == 5
    assert compute_premium(rating, five).premium_minor == 6750
    one = {"departure_date": "2026-10-03", "return_date": "2026-10-03"}
    assert compute_premium(rating, one).premium_minor == 1850  # 1,350 < 1,850 minimum


def test_flat_and_missing_basis():
    assert compute_premium({"method": "FLAT", "rate": 4900}, {}).premium_minor == 4900
    with pytest.raises(RatingError):
        compute_premium({"method": "PERCENT", "basis": "TRIP_COST", "rate": 0.06}, {})
    with pytest.raises(RatingError):
        compute_premium({"method": "NOPE"}, {})


def test_add_months_clamps_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 9, 21), 36) == date(2029, 9, 21)


def test_term_purchase_date_starts_today():
    start, end = compute_term({"length": 36, "unit": "MONTH", "starts": "PURCHASE_DATE"}, {}, TODAY)
    assert (start, end) == (date(2026, 9, 21), date(2029, 9, 20))


def test_term_next_day():
    start, end = compute_term({"length": 1, "unit": "YEAR", "starts": "NEXT_DAY"}, {}, TODAY)
    assert (start, end) == (date(2026, 9, 22), date(2027, 9, 21))


def test_term_warranty_end_explicit_and_default():
    rule = {"length": 4, "unit": "YEAR", "starts": "WARRANTY_END"}
    start, end = compute_term(rule, {"manufacturer_warranty_end_date": "2027-09-13"}, TODAY)
    assert (start, end) == (date(2027, 9, 14), date(2031, 9, 13))
    # unknown warranty end: one year from purchase
    start, _ = compute_term(rule, {"purchase_date": "2026-09-21"}, TODAY)
    assert start == date(2027, 9, 21)
    with pytest.raises(RatingError):
        compute_term(rule, {}, TODAY)


def test_term_trip_departure():
    start, end = compute_term(
        {"length": None, "unit": "DAY", "starts": "TRIP_DEPARTURE"},
        {"departure_date": "2026-10-03", "return_date": "2026-10-07"},
        TODAY,
    )
    assert (start, end) == (date(2026, 10, 3), date(2026, 10, 7))


def test_valid_until_is_24h_when_start_is_far():
    created = datetime(2026, 9, 21, 3, 0, tzinfo=UTC)
    assert quote_valid_until(created, date(2026, 10, 3)) == datetime(2026, 9, 22, 3, 0, tzinfo=UTC)


def test_valid_until_capped_by_term_start_midnight():
    created = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)
    assert quote_valid_until(created, date(2026, 9, 22)) == datetime(2026, 9, 22, 0, 0, tzinfo=UTC)


def test_valid_until_ignores_a_term_start_already_past():
    created = datetime(2026, 9, 21, 3, 0, tzinfo=UTC)
    assert quote_valid_until(created, date(2026, 9, 21)) == datetime(2026, 9, 22, 3, 0, tzinfo=UTC)

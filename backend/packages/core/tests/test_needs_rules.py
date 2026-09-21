"""Profiling rules (no DB, no LLM)."""

from __future__ import annotations

from datetime import date

from onboarding_core.needs.rules import compute_needs_missing, described_objects, merge_needs
from onboarding_core.product_lines import LINES, line_for_object_type
from onboarding_core.product_lines.device import DEVICE, normalize_device_category, normalize_manufacturer
from onboarding_core.product_lines.travel import TRAVEL

TODAY = date(2026, 9, 21)
BASE = {"age_range": "AGE_30_39", "residence_country": "KR", "objectives": ["PROTECT_DEVICE"]}


def test_device_categories_are_normalized():
    assert normalize_device_category("laptop") == "NOTEBOOK"
    assert normalize_device_category("smart watch") == "WEARABLE"
    assert normalize_device_category("cell-phone") == "SMARTPHONE"
    assert normalize_device_category("DRONE") == "DRONE"  # unknown kinds pass through for the rules to reject
    assert normalize_device_category(None) is None


def test_device_needs_require_category_and_price_unless_the_partner_knows_the_device():
    assert compute_needs_missing(BASE, market="KR") == [
        "device.device_category",
        "device.purchase_price_minor",
    ]
    assert compute_needs_missing(BASE, market="KR", partner_object_types={"DEVICE"}) == []


def test_a_phone_needs_its_manufacturer_because_phone_cover_depends_on_it():
    phone = {**BASE, "device": {"device_category": "phone", "purchase_price_minor": 1694000}}
    assert compute_needs_missing(merge_needs({}, phone, "KR"), market="KR") == ["device.manufacturer"]
    phone["device"]["manufacturer"] = "Samsung"
    assert compute_needs_missing(merge_needs({}, phone, "KR"), market="KR") == []
    laptop = {**BASE, "device": {"device_category": "NOTEBOOK", "purchase_price_minor": 1}}
    assert compute_needs_missing(laptop, market="KR") == []


def test_manufacturers_are_normalized_to_catalog_names():
    assert normalize_manufacturer("삼성") == "Samsung" and normalize_manufacturer("아이폰") == "Apple"
    assert normalize_manufacturer("samsung") == "Samsung" and normalize_manufacturer("Xiaomi") == "Xiaomi"
    merged = merge_needs({}, {"device": {"device_category": "phone", "manufacturer": "삼성 "}}, "KR")
    assert merged["device"]["manufacturer"] == "Samsung"


def test_a_phone_is_assumed_activated_on_its_purchase_date():
    attrs = DEVICE.object_attributes(
        {"device_category": "SMARTPHONE", "manufacturer": "Samsung", "purchase_price_minor": 1694000},
        residence_country="KR",
        today=TODAY,
    )
    assert attrs["activation_date"] == attrs["purchase_date"] == "2026-09-21"
    assert attrs["assumed_fields"] == ["condition", "has_existing_damage", "purchase_date", "activation_date"]
    stated = DEVICE.object_attributes(
        {"device_category": "SMARTPHONE", "purchase_date": "2026-09-10", "activation_date": "2026-09-11"},
        residence_country="KR",
        today=TODAY,
    )
    assert stated["activation_date"] == "2026-09-11" and "activation_date" not in stated["assumed_fields"]


def test_a_device_the_customer_ruled_out_asks_nothing_and_is_not_insured():
    # "휴대폰 분실" on a trip was once extracted as a device; the customer then wants travel cover only.
    values = {
        **BASE,
        "objectives": ["TRAVEL_COVER"],
        "device": {"device_category": "SMARTPHONE"},
        "trip": {"departure_date": "2026-10-21", "return_date": "2026-10-26", "destination_countries": ["JP"]},
    }
    assert compute_needs_missing(values, market="KR") == []
    assert [key for key, _, _ in described_objects(values, today=TODAY)] == ["trip"]


def test_trip_cost_is_required_only_in_the_us():
    values = {
        **BASE,
        "objectives": ["TRAVEL_COVER"],
        "trip": {"departure_date": "2026-10-03", "return_date": "2026-10-07", "destination_countries": ["JP"]},
    }
    assert compute_needs_missing(values, market="KR", partner_object_types=()) == []
    assert compute_needs_missing(values, market="US", partner_object_types=()) == ["trip.trip_cost_minor"]


def test_profile_fields_and_objectives_are_required():
    assert compute_needs_missing({}, market="US", partner_object_types=()) == [
        "age_range",
        "residence_country",
        "objectives",
    ]


def test_merge_keeps_known_values_and_layers_new_ones():
    base = {**BASE, "occupation": "Nurse", "device": {"device_category": "NOTEBOOK", "purchase_price_minor": 1}}
    merged = merge_needs(
        base,
        {
            "age_range": None,
            "objectives": ["PROTECT_DEVICE", "PROTECT_DEVICE"],
            "device": {"purchase_price_minor": 2, "model": None},
        },
        "KR",
    )
    assert merged["age_range"] == "AGE_30_39" and merged["occupation"] == "Nurse"
    assert merged["objectives"] == ["PROTECT_DEVICE"]
    assert merged["device"] == {"device_category": "NOTEBOOK", "purchase_price_minor": 2}


def test_merge_normalizes_country_and_defaults_it_to_the_market():
    assert merge_needs({}, {"residence_country": "usa"}, "KR")["residence_country"] == "US"
    assert merge_needs({}, {}, "KR")["residence_country"] == "KR"
    assert merge_needs({}, {"device": {"device_category": "phone"}}, "KR")["device"]["device_category"] == "SMARTPHONE"


def test_device_assumptions_are_recorded():
    attrs = DEVICE.object_attributes(
        {"device_category": "laptop", "purchase_price_minor": 129900, "model": None},
        residence_country="US",
        today=TODAY,
    )
    assert attrs == {
        "device_category": "NOTEBOOK",
        "purchase_price_minor": 129900,
        "condition": "NEW",
        "has_existing_damage": False,
        "purchase_date": "2026-09-21",
        "assumed_fields": ["condition", "has_existing_damage", "purchase_date"],
    }
    stated = DEVICE.object_attributes(
        {"condition": "USED", "has_existing_damage": True, "purchase_date": "2026-01-02"},
        residence_country="US",
        today=TODAY,
    )
    assert "assumed_fields" not in stated


def test_trip_destination_becomes_a_list_and_departs_from_home():
    attrs = TRAVEL.object_attributes(
        {"destination_countries": "JP", "trip_cost_minor": None}, residence_country="KR", today=TODAY
    )
    assert attrs == {
        "destination_countries": ["JP"],
        "departure_country": "KR",
    }


def test_described_objects_skip_what_the_partner_supplied():
    values = {
        "residence_country": "KR",
        "objectives": ["PROTECT_DEVICE", "TRAVEL_COVER"],
        "device": {"device_category": "PHONE"},
        "trip": {"destination_countries": ["JP"]},
    }
    objects = described_objects(values, partner_object_types={"DEVICE"}, today=TODAY)
    assert [(key, object_type) for key, object_type, _ in objects] == [("trip", "TRIP")]
    both = described_objects(values, today=TODAY)
    assert [key for key, _, _ in both] == ["device", "trip"]
    assert both[0][2]["device_category"] == "SMARTPHONE"


def test_every_line_is_reachable_by_its_object_type():
    assert [line_for_object_type(line.object_type) for line in LINES] == list(LINES)
    assert len({line.needs_key for line in LINES}) == len(LINES)


def test_every_need_a_line_may_ask_for_is_declared():
    """Labels are checked against `needs_fields`, so `required_needs` must stay inside it."""
    for line in LINES:
        for market in ("KR", "US"):
            for values in ({}, {"device_category": "SMARTPHONE"}, {"device_category": "NOTEBOOK"}):
                assert set(line.required_needs(market, values)) <= set(line.needs_fields), (line.code, market, values)


def test_today_is_the_markets_local_date():
    from datetime import UTC, datetime

    from onboarding_core.util import market_today

    late_utc = datetime(2026, 9, 21, 15, 51, tzinfo=UTC)  # 00:51 on the 22nd in Seoul
    assert market_today("KR", late_utc) == date(2026, 9, 22)
    assert market_today("US", late_utc) == date(2026, 9, 21)
    assert market_today("??", late_utc) == date(2026, 9, 21)

"""Profiling rules (no DB, no LLM)."""

from __future__ import annotations

from datetime import date

from onboarding_core.needs.rules import (
    compute_needs_missing,
    device_attributes,
    merge_needs,
    normalize_device_category,
    trip_attributes,
)

TODAY = date(2026, 9, 21)
BASE = {"age_range": "AGE_30_39", "residence_country": "KR", "objectives": ["PROTECT_DEVICE"]}


def test_device_categories_are_normalized():
    assert normalize_device_category("laptop") == "NOTEBOOK"
    assert normalize_device_category("smart watch") == "WEARABLE"
    assert normalize_device_category("cell-phone") == "SMARTPHONE"
    assert normalize_device_category("DRONE") == "DRONE"  # unknown kinds pass through for the rules to reject
    assert normalize_device_category(None) is None


def test_device_needs_require_category_and_price_unless_the_partner_knows_the_device():
    assert compute_needs_missing(BASE, market="KR", has_partner_device=False) == [
        "device.device_category",
        "device.purchase_price_minor",
    ]
    assert compute_needs_missing(BASE, market="KR", has_partner_device=True) == []


def test_trip_cost_is_required_only_in_the_us():
    values = {
        **BASE,
        "objectives": ["TRAVEL_COVER"],
        "trip": {"departure_date": "2026-10-03", "return_date": "2026-10-07", "destination_countries": ["JP"]},
    }
    assert compute_needs_missing(values, market="KR", has_partner_device=False) == []
    assert compute_needs_missing(values, market="US", has_partner_device=False) == ["trip.trip_cost_minor"]


def test_profile_fields_and_objectives_are_required():
    assert compute_needs_missing({}, market="US", has_partner_device=False) == [
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
    attrs = device_attributes({"device_category": "laptop", "purchase_price_minor": 129900, "model": None}, TODAY)
    assert attrs == {
        "device_category": "NOTEBOOK",
        "purchase_price_minor": 129900,
        "condition": "NEW",
        "has_existing_damage": False,
        "purchase_date": "2026-09-21",
        "assumed_fields": ["condition", "has_existing_damage", "purchase_date"],
    }
    stated = device_attributes({"condition": "USED", "has_existing_damage": True, "purchase_date": "2026-01-02"}, TODAY)
    assert "assumed_fields" not in stated


def test_trip_destination_becomes_a_list_and_departs_from_home():
    assert trip_attributes({"destination_countries": "JP", "trip_cost_minor": None}, "KR") == {
        "destination_countries": ["JP"],
        "departure_country": "KR",
    }

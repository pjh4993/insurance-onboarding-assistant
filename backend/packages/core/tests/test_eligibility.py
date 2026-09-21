"""Eligibility operators, subjects and ranking (no DB)."""

from __future__ import annotations

from datetime import date

from onboarding_core.catalog.eligibility import (
    RuleSpec,
    derived_values,
    evaluate_product,
    evaluate_rule,
    rank_order,
    target_market_score,
)
from onboarding_core.catalog.seed import PRODUCTS

TODAY = date(2026, 9, 21)
CATALOG = {p["product_code"]: p for p in PRODUCTS}


def rule(subject, attribute, operator, value, code="X"):
    return RuleSpec(code, subject, attribute, operator, value, code, code)


def rules_of(code):
    return [RuleSpec(str(i), **r) for i, r in enumerate(CATALOG[code]["rules"])]


CTX = {
    "PARTY": {"party_type": "PERSON", "date_of_birth": "1991-03-14"},
    "NEEDS_ASSESSMENT": {"residence_country": "KR", "objectives": ["PROTECT_DEVICE"]},
    "INSURABLE_OBJECT": {
        "attributes": {
            "device_category": "SMARTPHONE",
            "manufacturer": "samsung",
            "activation_date": "2026-09-14",
            "purchase_price_minor": 1350000,
            "has_existing_damage": False,
        }
    },
    "DERIVED": {"trip_length_days": 5},
}


def test_eq_is_case_insensitive_and_handles_booleans():
    assert evaluate_rule(rule("PARTY", "party_type", "EQ", "person"), CTX, TODAY)
    assert evaluate_rule(rule("INSURABLE_OBJECT", "attributes.has_existing_damage", "EQ", False), CTX, TODAY)
    assert not evaluate_rule(rule("PARTY", "party_type", "EQ", "ORGANIZATION"), CTX, TODAY)


def test_in_scalar_and_list():
    assert evaluate_rule(rule("INSURABLE_OBJECT", "attributes.manufacturer", "IN", ["Samsung", "Apple"]), CTX, TODAY)
    assert evaluate_rule(rule("NEEDS_ASSESSMENT", "objectives", "IN", ["PROTECT_DEVICE", "X"]), CTX, TODAY)
    assert not evaluate_rule(rule("NEEDS_ASSESSMENT", "residence_country", "IN", ["US"]), CTX, TODAY)


def test_gte_lte_numbers():
    assert evaluate_rule(rule("INSURABLE_OBJECT", "attributes.purchase_price_minor", "LTE", 5000000), CTX, TODAY)
    assert not evaluate_rule(rule("INSURABLE_OBJECT", "attributes.purchase_price_minor", "GTE", 2000000), CTX, TODAY)
    assert evaluate_rule(rule("DERIVED", "trip_length_days", "LTE", 89), CTX, TODAY)


def test_within_days_bounds():
    r = rule("INSURABLE_OBJECT", "attributes.activation_date", "WITHIN_DAYS", 7)
    assert evaluate_rule(r, CTX, TODAY)  # exactly 7 days ago
    assert not evaluate_rule(r, CTX, date(2026, 9, 22))  # 8 days
    assert not evaluate_rule(r, CTX, date(2026, 9, 13))  # future date is not "within"
    zero = rule("INSURABLE_OBJECT", "attributes.activation_date", "WITHIN_DAYS", 0)
    assert evaluate_rule(zero, CTX, date(2026, 9, 14))


def test_missing_attribute_fails():
    assert not evaluate_rule(rule("INSURABLE_OBJECT", "attributes.condition", "EQ", "NEW"), CTX, TODAY)
    assert not evaluate_rule(rule("INSURABLE_OBJECT", "attributes.x", "EQ", 1), {"INSURABLE_OBJECT": None}, TODAY)


def test_derived_values():
    trip = {"attributes": {"departure_date": "2026-10-03", "return_date": "2026-10-07"}}
    d = derived_values({"date_of_birth": "1985-11-02"}, {}, trip, TODAY)
    assert d == {"trip_length_days": 5, "days_until_departure": 12, "applicant_age": 40}
    # no birth date: lower bound of the stated age range
    assert derived_values({}, {"age_range": "AGE_40_49"}, None, TODAY) == {"applicant_age": 40}


def test_kr_mobile_swap_customer_a_is_eligible():
    out = evaluate_product(
        rules_of("KR-MOB-SWAP"),
        party=CTX["PARTY"],
        needs=CTX["NEEDS_ASSESSMENT"],
        obj=CTX["INSURABLE_OBJECT"],
        today=TODAY,
    )
    assert out.eligible and out.failed_reasons == []


def test_ineligible_collects_every_failed_reason():
    laptop = {"attributes": {"device_category": "NOTEBOOK", "purchase_date": "2026-01-01", "condition": "NEW"}}
    out = evaluate_product(
        rules_of("KR-MOB-SWAP"), party=CTX["PARTY"], needs={"residence_country": "US"}, obj=laptop, today=TODAY
    )
    codes = [r.failure_reason_code for r in out.failed_rules]
    assert not out.eligible
    assert codes == [
        "DEVICE_NOT_SMARTPHONE",
        "MANUFACTURER_NOT_COVERED",
        "EXISTING_DAMAGE",
        "ACTIVATION_TOO_OLD",
        "NOT_KR_RESIDENT",
    ]
    assert out.failed_reasons[0].startswith("DEVICE_NOT_SMARTPHONE: ")


def test_kr_travel_rules_for_customer_b():
    trip = {
        "attributes": {
            "departure_date": "2026-10-03",
            "return_date": "2026-10-07",
            "departure_country": "KR",
            "destination_countries": ["JP"],
        }
    }
    needs = {"residence_country": "KR", "age_range": "AGE_40_49"}
    assert evaluate_product(rules_of("KR-TRV-OVERSEAS"), party={}, needs=needs, obj=trip, today=TODAY).eligible
    minor = {"residence_country": "KR", "age_range": "AGE_UNDER_19"}
    out = evaluate_product(rules_of("KR-TRV-OVERSEAS"), party={}, needs=minor, obj=trip, today=TODAY)
    assert [r.failure_reason_code for r in out.failed_rules] == ["APPLICANT_UNDER_19"]
    started = evaluate_product(rules_of("KR-TRV-OVERSEAS"), party={}, needs=needs, obj=trip, today=date(2026, 10, 4))
    assert [r.failure_reason_code for r in started.failed_rules] == ["TRIP_ALREADY_STARTED"]


def test_target_market_score_and_rank_order():
    tms = CATALOG["KR-MOB-SWAP"]["target_markets"]
    score, why = target_market_score(tms, {"objectives": ["PROTECT_DEVICE"], "age_range": "AGE_30_39"})
    assert score == 0.9 and len(why) == 2
    items = [
        {"product_code": "B", "score": 0.1, "eligibility_result": "ELIGIBLE"},
        {"product_code": "A", "score": 0.9, "eligibility_result": "INELIGIBLE"},
        {"product_code": "C", "score": 0.8, "eligibility_result": "ELIGIBLE"},
        {"product_code": "D", "score": 0.8, "eligibility_result": "ELIGIBLE"},
    ]
    assert [i["product_code"] for i in rank_order(items)] == ["C", "D", "B", "A"]

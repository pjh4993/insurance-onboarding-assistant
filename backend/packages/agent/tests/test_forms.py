"""The small forms' definitions: every needs field profiling can ask for has a form, and form answers become
NeedsExtraction-shaped values without the LLM. No DB."""

from __future__ import annotations

from onboarding_agent.flows.profiling import NEEDS_TOPICS, TOPIC_OF, interest_objective, next_topic, structured_needs
from onboarding_core.product_lines import LINES


def test_every_needs_field_profiling_can_ask_for_is_on_a_form():
    askable = {"age_range", "residence_country", "objectives"}
    askable |= {f"{line.needs_key}.{key}" for line in LINES for key in line.needs_fields}
    assert askable <= set(TOPIC_OF)
    # a product line's form is named after its needs key
    assert {line.needs_key for line in LINES} <= set(NEEDS_TOPICS)


def test_the_next_form_puts_the_product_of_interest_before_the_person():
    missing = ["age_range", "trip.departure_date", "device.device_category"]
    assert next_topic(["objectives", *missing], None) == "coverage"
    assert next_topic(missing, None) == "person"
    assert next_topic(missing, "TRAVEL_PROTECTION") == "trip"
    assert next_topic(missing, "EXTENDED_WARRANTY") == "device"
    assert next_topic([], None) is None


def test_the_product_of_interest_suggests_an_objective_from_the_catalog():
    assert interest_objective("MOBILE_INSURANCE") == "PROTECT_DEVICE"
    assert interest_objective("EXTENDED_WARRANTY") == "EXTEND_WARRANTY"
    assert interest_objective("TRAVEL_PROTECTION") == "TRAVEL_COVER"
    assert interest_objective(None) is None


def test_form_answers_become_needs_values():
    assert structured_needs(
        {
            "trip_cost": "2,500",
            "destination_countries": "jp, fr",
            "departure_date": "2026-10-03",
            "occupation": " nurse ",
            "residence_country": "us",
            "objectives": ["TRAVEL_COVER", "NOT_AN_OBJECTIVE"],
            "unknown": 1,
            "model": "",
        },
        "US",
    ) == {
        "trip": {"trip_cost_minor": 250000, "destination_countries": ["JP", "FR"], "departure_date": "2026-10-03"},
        "occupation": "nurse",
        "residence_country": "US",
        "objectives": ["TRAVEL_COVER"],
    }
    # KRW has no subunit
    assert structured_needs({"purchase_price": 1350000}, "KR") == {"device": {"purchase_price_minor": 1350000}}

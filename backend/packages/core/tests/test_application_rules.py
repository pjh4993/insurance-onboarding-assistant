"""Application rules (no DB, no LLM)."""

from __future__ import annotations

import uuid
from datetime import date

from onboarding_core.application.rules import apply_answer_aliases, missing_answers, prefill_answers
from onboarding_core.party.models import Party

TODAY = date(2026, 9, 21)
TRAVELER = Party(party_id=uuid.uuid4(), full_name="Kim Minjun", date_of_birth=date(1985, 11, 2))


def test_prefill_takes_partner_facts_but_not_assumed_ones():
    obj = {
        "attributes": {
            "manufacturer": "Samsung",
            "model": "Galaxy S26",
            "purchase_price_minor": 1_250_000,
            "purchase_date": "2026-09-21",
            "order_id": "ORD-1",
            "assumed_fields": ["purchase_date"],
        }
    }
    required = ["device_model", "msrp", "purchase_date", "order_number", "proof_of_purchase", "imei"]
    assert prefill_answers(required, obj, None, TODAY) == {
        "device_model": "Samsung Galaxy S26",
        "msrp": 1_250_000,
        "order_number": "ORD-1",
        "proof_of_purchase": "partner order ORD-1",
    }


def test_prefill_fills_traveller_fields_from_the_insured_person():
    obj = {"attributes": {"destination_countries": ["JP", "TW"], "departure_date": "2026-10-03"}}
    required = ["destination", "departure_date", "traveler_name", "traveler_date_of_birth", "traveler_age"]
    assert prefill_answers(required, obj, TRAVELER, TODAY) == {
        "destination": "JP, TW",
        "departure_date": "2026-10-03",
        "traveler_name": "Kim Minjun",
        "traveler_date_of_birth": "1985-11-02",
        "traveler_age": 40,
    }


def test_aliases_fill_only_missing_required_fields():
    answers = {"gender": "M", "destination_countries": ["JP", "KR"], "order_number": "ORD-2", "order_id": "X"}
    out = apply_answer_aliases(["traveler_gender", "destination", "order_number"], answers)
    assert out["traveler_gender"] == "M" and out["destination"] == "JP, KR" and out["order_number"] == "ORD-2"


def test_missing_answers_treats_blank_values_as_missing():
    assert missing_answers(["a", "b", "c", "d"], {"a": 0, "b": "", "c": [], "d": False}) == ["b", "c"]

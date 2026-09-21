"""Application rules: answers pre-filled from verified or collected data, which required fields are still
missing, and the alternative keys an extracted answer may arrive under. Plain code, no I/O."""

from __future__ import annotations

from typing import Any

from onboarding_core.catalog.eligibility import age_on
from onboarding_core.party.models import Party
from onboarding_core.util import iso

# LLM answer keys that mean a required application field (the first matching alias fills it).
ANSWER_ALIASES = {
    "destination": ("destination_countries", "destinations", "destination_country"),
    "trip_cost": ("trip_cost_minor",),
    "purchase_price": ("purchase_price_minor", "price_minor", "price"),
    "device_model": ("model",),
    "msrp": ("msrp_minor",),
    "order_number": ("order_id", "order_no"),
    "traveler_gender": ("gender",),
    "traveler_date_of_birth": ("date_of_birth", "birth_date"),
    "traveler_name": ("full_name", "name"),
    "departure_date": ("departure_datetime",),
    "return_date": ("return_datetime",),
    "imei": ("serial_number",),
}


def apply_answer_aliases(required: list[str], answers: dict[str, Any]) -> dict[str, Any]:
    out = dict(answers)
    for field_name in required:
        if out.get(field_name) not in (None, "", []):
            continue
        for alias in ANSWER_ALIASES.get(field_name, ()):
            value = out.get(alias)
            if value not in (None, "", []):
                out[field_name] = ", ".join(map(str, value)) if isinstance(value, list) else value
                break
    return out


def prefill_answers(
    required: list[str], obj: dict[str, Any] | None, insured: Party | None, today: Any
) -> dict[str, Any]:
    """Answers the application can take from data already verified or collected."""
    attrs = (obj or {}).get("attributes", {})
    assumed = set(attrs.get("assumed_fields") or [])
    a = {k: v for k, v in attrs.items() if k not in assumed}
    dob = insured.date_of_birth if insured else None
    candidates: dict[str, Any] = {
        "imei": a.get("imei"),
        "device_model": " ".join(x for x in (a.get("manufacturer"), a.get("model")) if x) or None,
        "msrp": a.get("msrp_minor") or a.get("purchase_price_minor"),
        "activation_date": a.get("activation_date"),
        "serial_number": a.get("serial_number"),
        "purchase_date": a.get("purchase_date"),
        "purchase_price": a.get("purchase_price_minor"),
        "order_number": a.get("order_id"),
        "proof_of_purchase": f"partner order {a['order_id']}" if a.get("order_id") else None,
        "departure_date": a.get("departure_date"),
        "return_date": a.get("return_date"),
        "destination": ", ".join(a["destination_countries"]) if a.get("destination_countries") else None,
        "trip_cost": a.get("trip_cost_minor"),
        "traveler_name": insured.full_name if insured else None,
        "traveler_date_of_birth": iso(dob) if dob else None,
        "traveler_age": age_on(dob, today) if dob else None,
    }
    return {k: candidates[k] for k in required if candidates.get(k) not in (None, "")}


def missing_answers(required: list[str], answers: dict[str, Any]) -> list[str]:
    return [f for f in required if answers.get(f) in (None, "", [])]

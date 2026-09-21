"""Profiling rules: which needs are still missing, how new answers merge into an assessment, and the
attributes of the device or trip a completed assessment describes. Plain code, no I/O."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from onboarding_core.needs.models import InsurableObject, NeedsAssessment

DEVICE_OBJECTIVES = {"PROTECT_DEVICE", "EXTEND_WARRANTY"}

DEVICE_CATEGORY_ALIASES = {
    "LAPTOP": "NOTEBOOK",
    "NOTEBOOK_COMPUTER": "NOTEBOOK",
    "COMPUTER": "NOTEBOOK",
    "PHONE": "SMARTPHONE",
    "MOBILE": "SMARTPHONE",
    "MOBILE_PHONE": "SMARTPHONE",
    "CELLPHONE": "SMARTPHONE",
    "CELL_PHONE": "SMARTPHONE",
    "HANDSET": "SMARTPHONE",
    "TELEVISION": "TV",
    "IPAD": "TABLET",
    "PAD": "TABLET",
    "WATCH": "WEARABLE",
    "SMARTWATCH": "WEARABLE",
    "SMART_WATCH": "WEARABLE",
}


def normalize_device_category(value: Any) -> str | None:
    if not value:
        return None
    key = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return DEVICE_CATEGORY_ALIASES.get(key, key)


def needs_view(na: NeedsAssessment | None) -> dict[str, Any]:
    if na is None:
        return {}
    return {
        "age_range": na.age_range,
        "occupation": na.occupation,
        "residence_country": na.residence_country,
        "existing_coverage": na.existing_coverage or [],
        "objectives": na.objectives or [],
        "device": na.device,
        "trip": na.trip,
    }


def object_view(o: InsurableObject) -> dict[str, Any]:
    return {
        "insurable_object_id": str(o.insurable_object_id),
        "object_type": o.object_type,
        "source": o.source,
        "attributes": o.attributes,
    }


def compute_needs_missing(values: dict[str, Any], *, market: str, has_partner_device: bool) -> list[str]:
    """Deterministic profiling completeness; the LLM's own `missing_fields` is advisory only."""
    missing = [f for f in ("age_range", "residence_country") if not values.get(f)]
    objectives = set(values.get("objectives") or [])
    if not objectives:
        missing.append("objectives")
    device, trip = values.get("device") or {}, values.get("trip") or {}
    if (objectives & DEVICE_OBJECTIVES or device) and not has_partner_device:
        # purchase_date is not required here: when unknown, eligibility assumes "bought today" and
        # the application step asks for the real date (see device_attributes / prefill_answers).
        for key in ("device_category", "purchase_price_minor"):
            if device.get(key) in (None, ""):
                missing.append(f"device.{key}")
    if "TRAVEL_COVER" in objectives or trip:
        keys = ["departure_date", "return_date", "destination_countries"]
        if market == "US":
            keys.append("trip_cost_minor")
        for key in keys:
            if trip.get(key) in (None, "", []):
                missing.append(f"trip.{key}")
    return missing


def merge_needs(base: dict[str, Any], extracted: Mapping[str, Any], market: str) -> dict[str, Any]:
    """Fold newly extracted values (the LLM's NeedsExtraction, as a mapping) into the values captured so far."""
    merged = dict(base)
    for key in ("age_range", "occupation", "residence_country"):
        value = extracted.get(key)
        if value:
            merged[key] = value
    if extracted.get("existing_coverage"):
        merged["existing_coverage"] = extracted["existing_coverage"]
    if extracted.get("objectives"):
        merged["objectives"] = list(dict.fromkeys(extracted["objectives"]))
    for key in ("device", "trip"):
        value = extracted.get(key)
        if value:
            merged[key] = {**(merged.get(key) or {}), **{k: v for k, v in value.items() if v is not None}}
    if merged.get("device") and merged["device"].get("device_category"):
        merged["device"]["device_category"] = normalize_device_category(merged["device"]["device_category"])
    if merged.get("residence_country"):
        merged["residence_country"] = str(merged["residence_country"]).upper()[:2]
    else:
        # Assumption: a customer onboarding in a market lives there unless they say otherwise.
        merged["residence_country"] = market
    return merged


def device_attributes(device: dict[str, Any], today: Any) -> dict[str, Any]:
    attrs = {k: v for k, v in device.items() if v is not None}
    if attrs.get("device_category"):
        attrs["device_category"] = normalize_device_category(attrs["device_category"])
    # Assumptions, recorded in `assumed_fields` so they are never copied into the application:
    # a device the customer is insuring now is new, undamaged and was bought today unless stated.
    assumed = []
    for key, default in (("condition", "NEW"), ("has_existing_damage", False), ("purchase_date", today.isoformat())):
        if key not in attrs:
            attrs[key] = default
            assumed.append(key)
    if assumed:
        attrs["assumed_fields"] = assumed
    return attrs


def trip_attributes(trip: dict[str, Any], residence_country: str | None) -> dict[str, Any]:
    attrs = {k: v for k, v in trip.items() if v is not None}
    if isinstance(attrs.get("destination_countries"), str):
        attrs["destination_countries"] = [attrs["destination_countries"]]
    attrs.setdefault("departure_country", residence_country)
    return attrs

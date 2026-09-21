"""Profiling rules: which needs are still missing, how new answers merge into an assessment, and the
objects a completed assessment describes. Line-specific parts come from `onboarding_core.product_lines`.
Plain code, no I/O."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date
from typing import Any

from onboarding_core.needs.models import InsurableObject, NeedsAssessment
from onboarding_core.product_lines import LINES
from onboarding_core.product_lines.base import BLANK


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


def compute_needs_missing(
    values: dict[str, Any], *, market: str, partner_object_types: Collection[str] = ()
) -> list[str]:
    """Deterministic profiling completeness; the LLM's own `missing_fields` is advisory only. Only lines the
    customer currently wants cover from count: a device mentioned once and then ruled out ("not device
    insurance, just the trip") asks nothing. A line whose object the partner already supplied (a purchased
    device) needs no description from the customer."""
    missing = [f for f in ("age_range", "residence_country") if not values.get(f)]
    objectives = set(values.get("objectives") or [])
    if not objectives:
        missing.append("objectives")
    for line in LINES:
        described = values.get(line.needs_key) or {}
        if not objectives & line.objectives or line.object_type in partner_object_types:
            continue
        required = line.required_needs(market, described)
        missing += [f"{line.needs_key}.{key}" for key in required if described.get(key) in BLANK]
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
    for line in LINES:
        key, value = line.needs_key, extracted.get(line.needs_key)
        if value:
            merged[key] = {**(merged.get(key) or {}), **{k: v for k, v in value.items() if v is not None}}
        if merged.get(key):
            merged[key] = line.normalize_needs(merged[key])
    if merged.get("residence_country"):
        merged["residence_country"] = str(merged["residence_country"]).upper()[:2]
    else:
        # Assumption: a customer onboarding in a market lives there unless they say otherwise.
        merged["residence_country"] = market
    return merged


def described_objects(
    values: dict[str, Any], *, partner_object_types: Collection[str] = (), today: date
) -> list[tuple[str, str, dict[str, Any]]]:
    """(needs_key, object_type, attributes) for each object the customer described for cover they still want,
    except those the partner already supplied."""
    return [
        (
            line.needs_key,
            line.object_type,
            line.object_attributes(
                values[line.needs_key], residence_country=values.get("residence_country"), today=today
            ),
        )
        for line in LINES
        if values.get(line.needs_key)
        and set(values.get("objectives") or []) & line.objectives
        and line.object_type not in partner_object_types
    ]

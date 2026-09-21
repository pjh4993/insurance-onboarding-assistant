"""Application rules: answers pre-filled from verified or collected data, which required fields are still
missing, and the alternative keys an extracted answer may arrive under. Line-specific parts come from
`onboarding_core.product_lines`. Plain code, no I/O."""

from __future__ import annotations

from typing import Any

from onboarding_core.party.models import Party
from onboarding_core.product_lines import LINES, line_for_object_type

# LLM answer keys that mean a required application field (the first matching alias fills it).
ANSWER_ALIASES = {field: aliases for line in LINES for field, aliases in line.answer_aliases.items()}


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
    object_type = (obj or {}).get("object_type")
    lines = [line_for_object_type(object_type)] if object_type else LINES
    candidates: dict[str, Any] = {}
    for line in lines:
        candidates.update(line.prefill(a, insured, today))
    return {k: candidates[k] for k in required if candidates.get(k) not in (None, "")}


def missing_answers(required: list[str], answers: dict[str, Any]) -> list[str]:
    return [f for f in required if answers.get(f) in (None, "", [])]

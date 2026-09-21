"""What a product line (device, travel, ...) contributes to the flow. The profiling and application rules
loop over the registered lines instead of branching on device or trip, so a new line is a new module
here plus its catalog products.

A line also needs its own key on `NeedsAssessment` (a JSONB column today: `device`, `trip`) and on the
LLM's `NeedsExtraction`; both are fixed fields for now."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from onboarding_core.party.models import Party

BLANK = (None, "", [])


class ProductLine:
    code: str
    object_type: str  # InsurableObject.object_type and Product.insurable_object_type
    needs_key: str  # the NeedsAssessment / NeedsExtraction field holding what the customer described
    objectives: frozenset[str]  # objectives that call for this line
    answer_aliases: Mapping[str, tuple[str, ...]] = {}  # required answer -> keys the LLM may use instead
    field_labels: Mapping[str, tuple[str, str]] = {}  # field -> (Korean, English) label for questions

    def required_needs(self, market: str, values: Mapping[str, Any]) -> tuple[str, ...]:
        """Keys of `needs_key` profiling must know before eligibility can run, given what is known of it
        so far (`values`, the merged `needs_key` dict)."""
        raise NotImplementedError

    def normalize_needs(self, values: dict[str, Any]) -> dict[str, Any]:
        """Clean up the merged values of `needs_key` (e.g. category aliases)."""
        return values

    def object_attributes(self, values: dict[str, Any], *, residence_country: str | None, today: date) -> dict:
        """Attributes of the InsurableObject a completed assessment describes."""
        raise NotImplementedError

    def prefill(self, attrs: dict[str, Any], insured: Party | None, today: date) -> dict[str, Any]:
        """Application answers this line can take from the object's attributes and the insured person."""
        raise NotImplementedError

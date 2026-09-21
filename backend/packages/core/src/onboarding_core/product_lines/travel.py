"""Overseas travel insurance: one trip, priced per trip."""

from __future__ import annotations

from datetime import date
from typing import Any

from onboarding_core.catalog.eligibility import age_on
from onboarding_core.party.models import Party
from onboarding_core.product_lines.base import ProductLine
from onboarding_core.util import iso


class TravelLine(ProductLine):
    code = "TRAVEL"
    object_type = "TRIP"
    needs_key = "trip"
    objectives = frozenset({"TRAVEL_COVER"})
    answer_aliases = {
        "destination": ("destination_countries", "destinations", "destination_country"),
        "trip_cost": ("trip_cost_minor",),
        "traveler_gender": ("gender",),
        "traveler_date_of_birth": ("date_of_birth", "birth_date"),
        "traveler_name": ("full_name", "name"),
        "departure_date": ("departure_datetime",),
        "return_date": ("return_datetime",),
    }
    field_labels = {
        "trip.departure_date": ("출발일", "your departure date"),
        "trip.return_date": ("귀국일", "your return date"),
        "trip.destination_countries": ("여행지", "your destination"),
        "trip.trip_cost_minor": ("여행 경비 총액", "the total trip cost"),
        "departure_date": ("출발일", "the departure date"),
        "return_date": ("귀국일", "the return date"),
        "destination": ("여행지", "the destination"),
        "traveler_name": ("여행자 이름", "the traveller's name"),
        "traveler_date_of_birth": ("여행자 생년월일", "the traveller's date of birth"),
        "traveler_gender": ("여행자 성별", "the traveller's gender"),
        "traveler_age": ("여행자 나이", "the traveller's age"),
        "trip_cost": ("여행 경비 총액", "the total trip cost"),
    }

    def required_needs(self, market: str) -> tuple[str, ...]:
        keys = ("departure_date", "return_date", "destination_countries")
        # US trip-cancellation cover is rated on the trip cost.
        return (*keys, "trip_cost_minor") if market == "US" else keys

    def object_attributes(self, values: dict[str, Any], *, residence_country: str | None, today: date) -> dict:
        attrs = {k: v for k, v in values.items() if v is not None}
        if isinstance(attrs.get("destination_countries"), str):
            attrs["destination_countries"] = [attrs["destination_countries"]]
        attrs.setdefault("departure_country", residence_country)
        return attrs

    def prefill(self, attrs: dict[str, Any], insured: Party | None, today: date) -> dict[str, Any]:
        a = attrs
        dob = insured.date_of_birth if insured else None
        return {
            "departure_date": a.get("departure_date"),
            "return_date": a.get("return_date"),
            "destination": ", ".join(a["destination_countries"]) if a.get("destination_countries") else None,
            "trip_cost": a.get("trip_cost_minor"),
            # Traveller fields follow the insured person.
            "traveler_name": insured.full_name if insured else None,
            "traveler_date_of_birth": iso(dob) if dob else None,
            "traveler_age": age_on(dob, today) if dob else None,
        }


TRAVEL = TravelLine()

"""Structured-output shapes (CONTRACTS.md §5). The class names are the Bedrock tool names the mock
server keys its fixtures on — do not rename them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgeRange = Literal["AGE_UNDER_19", "AGE_19_29", "AGE_30_39", "AGE_40_49", "AGE_50_64", "AGE_65_PLUS"]
Objective = Literal["PROTECT_DEVICE", "TRAVEL_COVER", "EXTEND_WARRANTY", "REDUCE_PREMIUM"]


class NeedsExtraction(BaseModel):
    """Customer profile and insurance needs extracted from the conversation."""

    age_range: AgeRange | None = Field(None, description="Age band of the customer")
    occupation: str | None = Field(None, description="Occupation, in the customer's words")
    residence_country: str | None = Field(None, description="ISO 3166-1 alpha-2 country of residence")
    existing_coverage: list[dict] = Field(
        default_factory=list, description="Existing insurance: {product_type, insurer_name, expires_on}"
    )
    objectives: list[Objective] = Field(default_factory=list, description="Why the customer wants cover")
    device: dict | None = Field(
        None,
        description="Device to insure: {device_category, manufacturer, model, purchase_date, "
        "purchase_price_minor}. device_category is one of SMARTPHONE, TABLET, NOTEBOOK, TV, "
        "APPLIANCE, WEARABLE. Dates ISO 8601. Money in minor units: whole won for KRW "
        "(299만 원 = 2990000), cents for USD ($1,299 = 129900).",
    )
    trip: dict | None = Field(
        None,
        description="Trip to insure: {destination_countries, departure_date, return_date, "
        "trip_cost_minor}. Countries ISO alpha-2, dates ISO 8601. Money in minor units: whole won for "
        "KRW, cents for USD.",
    )
    missing_fields: list[str] = Field(
        default_factory=list, description="Names of the fields above that are still unknown"
    )


class RecommendationRationale(BaseModel):
    """One short customer-facing reason per recommended product."""

    items: list[dict] = Field(description="List of {recommendation_id, rationale}")


class PartiesExtraction(BaseModel):
    """Who is insured and who pays, besides the applicant."""

    all_self: bool = Field(description="True when the applicant is also the insured person and the payer")
    parties: list[dict] = Field(
        default_factory=list,
        description='Other people: {role: "INSURED" | "PAYER", full_name, date_of_birth (ISO 8601)}',
    )


class AnswersExtraction(BaseModel):
    """Application answers extracted from the customer's reply."""

    answers: dict = Field(description="Application field name -> value")
    missing_fields: list[str] = Field(default_factory=list, description="Required fields still unanswered")


class ApplicationSummary(BaseModel):
    """A short plain-language summary of the application for the customer to confirm."""

    summary: str

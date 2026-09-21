"""Request bodies (CONTRACTS.md §3). `InputBody.data` is validated per `type`."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

InputType = Literal[
    "INTAKE", "IDENTITY_INFO", "OTP_CODE", "NEEDS", "DECISION", "PARTIES", "ANSWERS", "CONFIRM", "AGENT"
]


# A language code (ko, en, pt-BR). Which ones a session may use is up to the agent config bundle, checked by
# the runtime; the column holds 5 characters.
Locale = Annotated[str, Field(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$", max_length=5)]


class CreateSessionBody(BaseModel):
    market: Literal["KR", "US"]
    locale: Locale | None = None  # defaults to the market's language


class LocaleBody(BaseModel):
    locale: Locale


class InputBody(BaseModel):
    type: InputType
    data: dict[str, Any] = Field(default_factory=dict)


class _Data(BaseModel):
    model_config = ConfigDict(extra="ignore")


DocumentType = Literal["NATIONAL_ID", "PASSPORT", "DRIVER_LICENSE"]


class Intake(_Data):
    text: str = Field("", max_length=2000)  # "" when the customer just pressed start


class ContactFields(_Data):
    full_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    phone: str = Field(min_length=4)


class DocumentFields(_Data):
    id_document_type: DocumentType
    id_document_number: str = Field(min_length=1)
    # Not in CONTRACTS.md §3: optional, used by the document check when no partner record supplies it.
    date_of_birth: str | None = None


class ConsentFields(_Data):
    third_party_consent: bool


class IdentityInfo(ContactFields, DocumentFields):
    """The full shape: every identity detail at once."""

    third_party_consent: bool = False


IDENTITY_TOPICS: dict[str, type[_Data]] = {
    "contact": ContactFields,
    "id_document": DocumentFields,
    "consent": ConsentFields,
}


class IdentityTopic(_Data):
    """One identity form: `{topic, fields}` with that topic's fields."""

    topic: Literal["contact", "id_document", "consent"]
    fields: dict[str, Any]

    @model_validator(mode="after")
    def _fields_of_topic(self) -> IdentityTopic:
        self.fields = IDENTITY_TOPICS[self.topic].model_validate(self.fields).model_dump(exclude_none=True)
        return self


class NeedsFields(BaseModel):
    """Fields of the needs forms. Money is in whole units of the market's currency (won, dollars)."""

    model_config = ConfigDict(extra="forbid")

    objectives: list[Literal["PROTECT_DEVICE", "TRAVEL_COVER", "EXTEND_WARRANTY", "REDUCE_PREMIUM"]] | None = None
    age_range: Literal["AGE_UNDER_19", "AGE_19_29", "AGE_30_39", "AGE_40_49", "AGE_50_64", "AGE_65_PLUS"] | None = None
    residence_country: str | None = Field(None, pattern=r"^[A-Za-z]{2}$")
    occupation: str | None = Field(None, max_length=200)
    device_category: Literal["SMARTPHONE", "TABLET", "NOTEBOOK", "TV", "APPLIANCE", "WEARABLE"] | None = None
    manufacturer: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    purchase_date: date | None = None
    purchase_price: float | None = Field(None, ge=0)
    destination_countries: list[Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")]] | None = None
    departure_date: date | None = None
    return_date: date | None = None
    trip_cost: float | None = Field(None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _split_countries(cls, data: Any) -> Any:
        """Destinations may come as one text: "JP, FR"."""
        if isinstance(data, dict) and isinstance(data.get("destination_countries"), str):
            items = [c.strip() for c in data["destination_countries"].split(",") if c.strip()]
            data = {**data, "destination_countries": items}
        return data


class Needs(_Data):
    """A needs answer: a form (`{topic, fields}`), free text (`{text}`), or both."""

    topic: Literal["coverage", "person", "device", "trip"] | None = None
    fields: NeedsFields | None = None
    text: str | None = None

    @model_validator(mode="after")
    def _something(self) -> Needs:
        if not (self.text and self.text.strip()) and not (self.topic and self.fields):
            raise ValueError("send {text}, {topic, fields}, or both")
        return self


class OtpCode(_Data):
    code: str = Field(min_length=1)


class FreeText(_Data):
    text: str = Field(min_length=1)


class Decision(_Data):
    decision: Literal["ACCEPT", "DECLINE", "CHANGE"]
    recommendation_id: str | None = None
    text: str | None = None


class Confirm(_Data):
    confirmed: bool
    text: str | None = None


class AgentResolution(_Data):
    resolution: Literal["VERIFIED", "CONTINUE", "END"]
    note: str | None = None


DATA_MODELS: dict[str, type[_Data]] = {
    "INTAKE": Intake,
    "IDENTITY_INFO": IdentityInfo,
    "OTP_CODE": OtpCode,
    "NEEDS": Needs,
    "DECISION": Decision,
    "PARTIES": FreeText,
    "ANSWERS": FreeText,
    "CONFIRM": Confirm,
    "AGENT": AgentResolution,
}


def validate_data(input_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Returns the cleaned data (JSON types: dates as ISO strings) or raises pydantic.ValidationError.
    IDENTITY_INFO takes one form (`{topic, fields}`) or the full shape."""
    model = IdentityTopic if input_type == "IDENTITY_INFO" and "topic" in data else DATA_MODELS[input_type]
    return model.model_validate(data).model_dump(mode="json", exclude_none=True)


__all__ = ["DATA_MODELS", "CreateSessionBody", "InputBody", "LocaleBody", "ValidationError", "validate_data"]

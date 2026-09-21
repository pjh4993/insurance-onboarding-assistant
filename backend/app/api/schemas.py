"""Request bodies (CONTRACTS.md §3). `InputBody.data` is validated per `type`."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

InputType = Literal["IDENTITY_INFO", "OTP_CODE", "NEEDS", "DECISION", "PARTIES", "ANSWERS", "CONFIRM", "AGENT"]


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


class IdentityInfo(_Data):
    full_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    phone: str = Field(min_length=4)
    id_document_type: Literal["NATIONAL_ID", "PASSPORT", "DRIVER_LICENSE"]
    id_document_number: str = Field(min_length=1)
    third_party_consent: bool = False
    # Not in CONTRACTS.md §3: optional, used by the document check when no partner record supplies it.
    date_of_birth: str | None = None


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
    "IDENTITY_INFO": IdentityInfo,
    "OTP_CODE": OtpCode,
    "NEEDS": FreeText,
    "DECISION": Decision,
    "PARTIES": FreeText,
    "ANSWERS": FreeText,
    "CONFIRM": Confirm,
    "AGENT": AgentResolution,
}


def validate_data(input_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Returns the cleaned data or raises pydantic.ValidationError."""
    return DATA_MODELS[input_type].model_validate(data).model_dump(exclude_none=True)


__all__ = ["DATA_MODELS", "CreateSessionBody", "InputBody", "LocaleBody", "ValidationError", "validate_data"]

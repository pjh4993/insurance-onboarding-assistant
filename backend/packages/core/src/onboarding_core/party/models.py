"""Parties: the applicant and anyone else named on an application."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(eq=False, kw_only=True)
class Party:
    party_id: uuid.UUID
    party_type: str = "PERSON"
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    id_document_type: str | None = None
    # The document number is never stored in plaintext: AES-EAX ciphertext + HMAC for lookups.
    id_document_number_enc: bytes | None = None
    id_document_hmac: str | None = None
    third_party_consent_at: datetime | None = None
    partner_customer_ref: str | None = None
    verification_status: str = "UNVERIFIED"
    verification_method: str | None = None
    verification_attempts: int = 0
    verified_at: datetime | None = None
    merged_into_party_id: uuid.UUID | None = None

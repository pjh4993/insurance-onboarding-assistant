"""Stage 1, identity verification: partner match (with consent), then OTP, then the ID document."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from onboarding_agent.config import TextSpec
from onboarding_agent.flows.base import DomainModule, Flow, HandoffKind, InputKind
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import locale_of, mask_phone, say
from onboarding_core.crypto import decrypt_field, encrypt_field, hmac_hex
from onboarding_core.util import iso, parse_date


async def record_identity_info(
    flow: Flow, state: dict[str, Any], value: dict[str, Any], now: datetime
) -> tuple[str, dict[str, Any]]:
    """The customer's contact details, ID document (encrypted, plus an HMAC) and partner consent."""
    lang = locale_of(state)
    async with flow.d.uow() as uow:
        party = await flow._party(uow, state)
        party.full_name = str(value.get("full_name") or "").strip() or None
        party.email = str(value.get("email") or "").strip() or None
        party.phone = str(value.get("phone") or "").strip() or None
        party.id_document_type = value.get("id_document_type")
        number = str(value.get("id_document_number") or "").strip()
        if number:
            party.id_document_number_enc = encrypt_field(flow.d.config.aes_key, number)
            party.id_document_hmac = hmac_hex(flow.d.config.hmac_key, number)
        if value.get("date_of_birth"):
            party.date_of_birth = parse_date(value["date_of_birth"])
        party.third_party_consent_at = now if value.get("third_party_consent") else None
        party.verification_status = "PENDING"
    await flow._touch(state, "party", state["party_id"])
    consent = (
        flow.text(lang, "identity.consent_yes")
        if value.get("third_party_consent")
        else flow.text(lang, "identity.consent_no")
    )
    text = flow.text(lang, "identity.identity_received", consent=consent, name=party.full_name)
    return text, {"identity_result": None}


async def record_otp_code(
    flow: Flow, state: dict[str, Any], value: dict[str, Any], now: datetime
) -> tuple[str, dict[str, Any]]:
    """The OTP the customer typed, kept only until check_otp uses it."""
    # Wrapped in a dict so it lands in an encrypted blob: the saver stores primitive
    # channel values inline in the plaintext `checkpoints.checkpoint` JSONB.
    text = flow.text(locale_of(state), "identity.otp_received")
    return text, {"otp_code": {"code": str(value.get("code", "")).strip()}}


async def resolve_identity_failure(
    flow: Flow, state: dict[str, Any], resolution: str | None, now: datetime
) -> tuple[list[BaseMessage], dict[str, Any]]:
    """An agent verified the customer, or sends them back to start identity over."""
    lang, msgs = locale_of(state), []
    async with flow.d.uow() as uow:
        party = await flow._party(uow, state)
        if resolution == "VERIFIED":
            party.verification_status = "VERIFIED"
            party.verification_method = "AGENT"
            party.verified_at = now
        else:
            party.verification_status = "UNVERIFIED"
            party.verification_attempts = 0
    await flow._touch(state, "party", state["party_id"])
    if resolution == "VERIFIED":
        msgs.append(say(flow.text(lang, "identity.agent_verified"), now))
    return msgs, {}


def resume_after_identity_failure(state: dict[str, Any]) -> str:
    return "fetch_purchases" if state.get("handoff_resolution") == "VERIFIED" else "greet"


class IdentityFlow(Flow):
    async def verify_identity(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            if party.third_party_consent_at is not None:
                res = await self.d.partner.match_customer(
                    full_name=party.full_name or "",
                    email=party.email or "",
                    phone=party.phone or "",
                    consent_at=party.third_party_consent_at,
                )
                if res.get("matched"):
                    party.partner_customer_ref = res.get("partner_customer_ref")
                    if res.get("date_of_birth"):
                        party.date_of_birth = parse_date(res["date_of_birth"])
                    party.verification_status = "VERIFIED"
                    party.verification_method = "PARTNER_MATCH"
                    party.verified_at = self.now()
                    text = self.text(lang, "identity.partner_verified")
                    await self._touch(state, "party", party.party_id)
                    return {"identity_result": "MATCHED", "messages": [say(text, self.now())]}
            otp = await self.d.identity.send_otp(party.phone or "")
            party.verification_status = "PENDING"
        await self._touch(state, "party", state["party_id"])
        text = self.text(lang, "identity.otp_sent", phone=mask_phone(party.phone))
        return {
            "identity_result": "NOT_MATCHED",
            "otp_request_id": otp.get("otp_request_id"),
            "waiting_for": "OTP_CODE",
            "messages": [say(text, self.now())],
        }

    async def check_otp(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        verified = False
        code = (state.get("otp_code") or {}).get("code")
        if state.get("otp_request_id") and code:
            res = await self.d.identity.verify_otp(state["otp_request_id"], code)
            verified = bool(res.get("verified"))
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            if verified:
                party.verification_status = "VERIFIED"
                party.verification_method = "OTP"
                party.verified_at = self.now()
            else:
                # OTP is always the first counted failure, so `max` keeps a re-run idempotent.
                party.verification_attempts = max(party.verification_attempts or 0, 1)
        await self._touch(state, "party", state["party_id"])
        if verified:
            text = self.text(lang, "identity.otp_verified")
            return {"identity_result": "OTP_OK", "otp_code": None, "messages": [say(text, self.now())]}
        text = self.text(lang, "identity.otp_failed")
        return {"identity_result": "OTP_FAILED", "otp_code": None, "messages": [say(text, self.now())]}

    async def check_document(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
        verified = False
        if party.id_document_number_enc and party.id_document_type:
            number = decrypt_field(self.d.config.aes_key, party.id_document_number_enc)
            res = await self.d.identity.verify_document(
                document_type=party.id_document_type,
                document_number=number,
                full_name=party.full_name or "",
                date_of_birth=iso(party.date_of_birth),
            )
            verified = bool(res.get("verified"))
        async with self.d.uow() as uow:
            party = await self._party(uow, state)
            if verified:
                party.verification_status = "VERIFIED"
                party.verification_method = "DOCUMENT"
                party.verified_at = self.now()
            else:
                party.verification_attempts = 2
                party.verification_status = "FAILED"
        await self._touch(state, "party", state["party_id"])
        if verified:
            text = self.text(lang, "identity.document_verified")
            return {"identity_result": "DOC_OK", "messages": [say(text, self.now())]}
        text = self.text(lang, "identity.identity_failed")
        return {
            "identity_result": "DOC_FAILED",
            "handoff_reason": "IDENTITY_FAILED",
            "messages": [say(text, self.now())],
        }


def after_verify_identity(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    return "fetch_purchases" if state.get("identity_result") == "MATCHED" else "ask_customer"


def after_check_otp(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    return "fetch_purchases" if state.get("identity_result") == "OTP_OK" else "check_document"


def after_check_document(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    return "fetch_purchases" if state.get("identity_result") == "DOC_OK" else HANDOFF


TEXTS = TextSpec(
    copy={
        "consent_yes": frozenset(),
        "consent_no": frozenset(),
        "identity_received": frozenset({"consent", "name"}),
        "otp_received": frozenset(),
        "agent_verified": frozenset(),
        "partner_verified": frozenset(),
        "otp_sent": frozenset({"phone"}),
        "otp_verified": frozenset(),
        "otp_failed": frozenset(),
        "document_verified": frozenset(),
        "identity_failed": frozenset(),
    },
)


MODULE = DomainModule(
    name="identity",
    texts=TEXTS,
    flow=IdentityFlow,
    edges={
        "verify_identity": after_verify_identity,
        "check_otp": after_check_otp,
        "check_document": after_check_document,
    },
    retrying=frozenset({"check_document", "check_otp", "verify_identity"}),
    inputs={
        "IDENTITY_INFO": InputKind("verify_identity", record_identity_info),
        "OTP_CODE": InputKind("check_otp", record_otp_code),
    },
    handoffs={"IDENTITY_FAILED": HandoffKind(resume_after_identity_failure, resolve_identity_failure)},
)

"""Stage 1, identity verification: partner match (with consent), then OTP, then the ID document."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from onboarding_agent.flows.base import DomainModule, Flow
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import locale_of, mask_phone, say, t
from onboarding_core.crypto import decrypt_field
from onboarding_core.util import iso, parse_date


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
                    text = t(
                        lang,
                        "파트너사 고객 정보로 본인 확인이 끝났습니다.",
                        "You're verified through your partner account.",
                    )
                    await self._touch(state, "party", party.party_id)
                    return {"identity_result": "MATCHED", "messages": [say(text, self.now())]}
            otp = await self.d.identity.send_otp(party.phone or "")
            party.verification_status = "PENDING"
        await self._touch(state, "party", state["party_id"])
        text = t(
            lang,
            f"{mask_phone(party.phone)} 번호로 인증번호를 보냈습니다. 받은 6자리 번호를 입력해 주세요.",
            f"We sent a verification code to {mask_phone(party.phone)}. Please enter the 6-digit code.",
        )
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
            text = t(lang, "인증번호가 확인됐습니다.", "Code verified — thank you.")
            return {"identity_result": "OTP_OK", "otp_code": None, "messages": [say(text, self.now())]}
        text = t(
            lang,
            "인증번호가 맞지 않아 입력하신 신분증으로 확인해 볼게요.",
            "That code didn't work, so I'll verify the ID document you gave instead.",
        )
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
            text = t(lang, "신분증으로 본인 확인이 끝났습니다.", "Your ID document is verified.")
            return {"identity_result": "DOC_OK", "messages": [say(text, self.now())]}
        text = t(
            lang,
            "본인 확인을 마치지 못했습니다. 상담원을 연결해 드릴게요.",
            "I couldn't verify your identity, so I'm connecting you with an agent.",
        )
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


MODULE = DomainModule(
    name="identity",
    flow=IdentityFlow,
    edges={
        "verify_identity": after_verify_identity,
        "check_otp": after_check_otp,
        "check_document": after_check_document,
    },
    retrying=frozenset({"check_document", "check_otp", "verify_identity"}),
)

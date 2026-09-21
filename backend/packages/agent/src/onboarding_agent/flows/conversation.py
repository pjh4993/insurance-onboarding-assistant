"""Opening and free-form questions: `greet` starts a session, `ask_customer` is the one wait node for every
"please tell me X" pause and routes the answer to the node that handles its kind."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from onboarding_agent.flows.base import DomainModule, Flow
from onboarding_agent.routing import HANDOFF, has_error
from onboarding_agent.texts import human, locale_of, say, t
from onboarding_core.crypto import encrypt_field, hmac_hex
from onboarding_core.util import parse_date

# The node that handles each kind of free-form answer.
INPUT_TARGET = {
    "IDENTITY_INFO": "verify_identity",
    "OTP_CODE": "check_otp",
    "NEEDS": "assess_needs",
    "PARTIES": "collect_parties",
    "ANSWERS": "collect_answers",
}


class ConversationFlow(Flow):
    async def greet(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        lang = locale_of(state)
        text = t(
            lang,
            "안녕하세요! 보험 가입을 도와드릴게요. 먼저 본인 확인을 위해 이름, 이메일, 휴대폰 번호, "
            "신분증 종류와 번호를 알려 주세요. 파트너사 구매 기록 조회(제3자 제공)에 동의하시면 "
            "확인이 더 빨라집니다.",
            "Hi! I'll help you find the right cover. First, to verify your identity, please share your "
            "full name, email, phone number and an ID document. If you consent to us checking your "
            "purchase history with our partner, verification is faster.",
        )
        return {
            "stage": "IDENTITY",
            "waiting_for": "IDENTITY_INFO",
            "last_input": None,
            "identity_result": None,
            "messages": [say(text, self.now())],
        }

    async def ask_customer(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        kind = state.get("waiting_for")
        value = interrupt({"waiting_for": kind})
        actor = state.get("actor") or "CUSTOMER"
        lang, now = locale_of(state), self.now()
        out: dict[str, Any] = {"waiting_for": None, "last_input": kind}

        if kind == "IDENTITY_INFO":
            async with self.d.uow() as uow:
                party = await self._party(uow, state)
                party.full_name = str(value.get("full_name") or "").strip() or None
                party.email = str(value.get("email") or "").strip() or None
                party.phone = str(value.get("phone") or "").strip() or None
                party.id_document_type = value.get("id_document_type")
                number = str(value.get("id_document_number") or "").strip()
                if number:
                    party.id_document_number_enc = encrypt_field(self.d.config.aes_key, number)
                    party.id_document_hmac = hmac_hex(self.d.config.hmac_key, number)
                if value.get("date_of_birth"):
                    party.date_of_birth = parse_date(value["date_of_birth"])
                party.third_party_consent_at = now if value.get("third_party_consent") else None
                party.verification_status = "PENDING"
            await self._touch(state, "party", state["party_id"])
            consent = t(
                lang,
                "동의" if value.get("third_party_consent") else "동의 안 함",
                "yes" if value.get("third_party_consent") else "no",
            )
            text = t(
                lang,
                f"본인 정보를 입력했습니다 — {party.full_name} (파트너 조회 {consent})",
                f"Identity details submitted — {party.full_name} (partner lookup consent: {consent})",
            )
            out["identity_result"] = None
        elif kind == "OTP_CODE":
            # Wrapped in a dict so it lands in an encrypted blob: the saver stores primitive
            # channel values inline in the plaintext `checkpoints.checkpoint` JSONB.
            out["otp_code"] = {"code": str(value.get("code", "")).strip()}
            text = t(lang, "인증번호를 입력했습니다.", "Entered the verification code.")
        else:
            text = str(value.get("text") or "").strip() or "-"
        out["messages"] = [human(text, now, actor=actor, input_type=kind or "")]
        return out


def after_greet(state: dict[str, Any]) -> str:
    return HANDOFF if has_error(state) else "ask_customer"


def after_ask_customer(state: dict[str, Any]) -> str:
    if has_error(state):
        return HANDOFF
    return INPUT_TARGET.get(state.get("last_input") or "", HANDOFF)


MODULE = DomainModule(
    name="conversation",
    flow=ConversationFlow,
    edges={
        "greet": after_greet,
        "ask_customer": after_ask_customer,
    },
    retrying=frozenset(),
)

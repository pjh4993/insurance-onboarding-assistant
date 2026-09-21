"""Graph state (wiki/state-model.md §2): conversation, progress, entity ids and routing signals.

Entity values live in the domain DB; the state never holds extracted PII (names, phone numbers,
document numbers). Customer free text does sit in `messages`, which is why the checkpoint is
encrypted."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Stage = Literal[
    "IDENTITY", "PROFILING", "RECOMMENDATION", "APPLICATION", "SUBMITTED", "HANDOFF", "DECLINED", "WITHDRAWN"
]
WaitingFor = Literal["IDENTITY_INFO", "OTP_CODE", "NEEDS", "DECISION", "PARTIES", "ANSWERS", "CONFIRM", "AGENT"]
IdentityResult = Literal["MATCHED", "NOT_MATCHED", "OTP_OK", "OTP_FAILED", "DOC_OK", "DOC_FAILED"]
HandoffReason = Literal["IDENTITY_FAILED", "NO_ELIGIBLE_PRODUCT", "NEEDS_INCOMPLETE", "ANSWERS_INCOMPLETE", "ERROR"]


class ErrorInfo(TypedDict):
    node: str
    kind: str
    attempts: int


class OnboardingState(TypedDict, total=False):
    # conversation
    messages: Annotated[list[AnyMessage], add_messages]
    actor: Literal["CUSTOMER", "AGENT"]
    mode: Literal["AUTO", "ASSIST"]

    # session context (ids and market only)
    session_id: str
    party_id: str
    market: Literal["KR", "US"]

    # progress
    stage: Stage
    waiting_for: WaitingFor | None
    last_input: WaitingFor | None  # which input ask_customer just received (routing signal)

    # entity references — values are in the domain DB
    needs_assessment_id: str | None
    insurable_object_ids: list[str]
    recommendation_ids: list[str]
    quote_ids: dict[str, str]  # recommendation_id -> quote_id
    application_id: str | None
    otp_request_id: str | None
    otp_code: dict[str, str] | None  # {"code"}: transient, set by ask_customer, cleared by check_otp

    # routing signals — the previous node's result
    identity_result: IdentityResult | None
    needs_complete: bool
    needs_rounds: int  # NEEDS answers since the last completed assessment (loop guard)
    eligible_count: int
    decision: Literal["ACCEPT", "DECLINE", "CHANGE"] | None
    parties_complete: bool
    answers_complete: bool
    answers_rounds: int  # ANSWERS replies that left fields missing (loop guard)
    confirmed: bool | None
    handoff_reason: HandoffReason | None
    handoff_resolution: Literal["VERIFIED", "CONTINUE", "END"] | None
    resume_node: str | None  # node to re-run after an ERROR handoff
    resume_stage: Stage | None

    # errors
    last_error: ErrorInfo | None


def initial_state(*, session_id: str, party_id: str, market: str) -> dict[str, Any]:
    return {
        "messages": [],
        "actor": "CUSTOMER",
        "mode": "AUTO",
        "session_id": session_id,
        "party_id": party_id,
        "market": market,
        "stage": "IDENTITY",
        "waiting_for": None,
        "last_input": None,
        "needs_assessment_id": None,
        "insurable_object_ids": [],
        "recommendation_ids": [],
        "quote_ids": {},
        "application_id": None,
        "otp_request_id": None,
        "otp_code": None,
        "identity_result": None,
        "needs_complete": False,
        "needs_rounds": 0,
        "eligible_count": 0,
        "decision": None,
        "parties_complete": False,
        "answers_complete": False,
        "answers_rounds": 0,
        "confirmed": None,
        "handoff_reason": None,
        "handoff_resolution": None,
        "resume_node": None,
        "resume_stage": None,
        "last_error": None,
    }

"""Graph state (wiki/state-model.md §2): conversation, progress, entity ids and routing signals.

The state is what the checkpointer persists, so it stays in this one module, grouped by the domain in
`onboarding_agent.flows` that writes each field. Field names are checkpoint channel names: renaming one
is a migration, like renaming a node.

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
WaitingFor = Literal[
    "INTAKE", "IDENTITY_INFO", "OTP_CODE", "NEEDS", "DECISION", "PARTIES", "ANSWERS", "CONFIRM", "AGENT"
]
IdentityResult = Literal["MATCHED", "NOT_MATCHED", "OTP_OK", "OTP_FAILED", "DOC_OK", "DOC_FAILED"]
HandoffReason = Literal[
    "IDENTITY_FAILED", "NO_ELIGIBLE_PRODUCT", "NEEDS_INCOMPLETE", "ANSWERS_INCOMPLETE", "SUMMARY_REJECTED", "ERROR"
]


class ErrorInfo(TypedDict):
    node: str
    kind: str
    attempts: int


class ConversationState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    actor: Literal["CUSTOMER", "AGENT"]
    mode: Literal["AUTO", "ASSIST"]
    # session context (ids, market and language only)
    session_id: str
    party_id: str
    market: Literal["KR", "US"]
    locale: Literal["ko", "en"]  # copy and LLM replies; mirrors OnboardingSession.locale on every resume
    # progress
    stage: Stage
    waiting_for: WaitingFor | None
    last_input: WaitingFor | None  # which input ask_customer just received (routing signal)
    form_topic: str | None  # the small form the pending IDENTITY_INFO / NEEDS wait asks (prompt `form.topic`)
    # intake: the customer's first message, kept for the needs extraction ({"text"}: a dict, so it is encrypted)
    intake: dict[str, str] | None
    product_interest: str | None  # a catalog product_type the intake points to, or None when unknown


class IdentityState(TypedDict, total=False):
    identity_result: IdentityResult | None
    otp_request_id: str | None
    otp_code: dict[str, str] | None  # {"code"}: transient, set by ask_customer, cleared by check_otp
    identity_topics: list[str]  # identity forms answered so far ("contact", "id_document", "consent")


class ProfilingState(TypedDict, total=False):
    needs_assessment_id: str | None
    insurable_object_ids: list[str]
    needs_complete: bool
    needs_rounds: int  # NEEDS answers that filled no missing field, since the last completed assessment
    needs_input: dict[str, Any] | None  # {"topic", "fields", "text"}: transient, set by ask_customer


class RecommendationState(TypedDict, total=False):
    recommendation_ids: list[str]
    quote_ids: dict[str, str]  # recommendation_id -> quote_id
    eligible_count: int
    decision: Literal["ACCEPT", "DECLINE", "CHANGE"] | None


class ApplicationState(TypedDict, total=False):
    application_id: str | None
    parties_complete: bool
    answers_complete: bool
    answers_rounds: int  # ANSWERS replies that left fields missing (loop guard)
    confirmed: bool | None
    confirm_rejections: int  # summaries the customer rejected (loop guard)
    correcting: bool  # a rejection came with a correction, which may concern the parties as well as the answers


class HandoffState(TypedDict, total=False):
    handoff_reason: HandoffReason | None
    handoff_resolution: Literal["VERIFIED", "CONTINUE", "END"] | None
    resume_node: str | None  # node to re-run after an ERROR handoff
    resume_stage: Stage | None
    last_error: ErrorInfo | None


class OnboardingState(
    ConversationState, IdentityState, ProfilingState, RecommendationState, ApplicationState, HandoffState, total=False
):
    pass


def initial_state(*, session_id: str, party_id: str, market: str, locale: str) -> dict[str, Any]:
    return {
        # conversation
        "messages": [],
        "actor": "CUSTOMER",
        "mode": "AUTO",
        "session_id": session_id,
        "party_id": party_id,
        "market": market,
        "locale": locale,
        "stage": "IDENTITY",
        "waiting_for": None,
        "last_input": None,
        "form_topic": None,
        "intake": None,
        "product_interest": None,
        # identity
        "identity_result": None,
        "otp_request_id": None,
        "otp_code": None,
        "identity_topics": [],
        # profiling
        "needs_assessment_id": None,
        "insurable_object_ids": [],
        "needs_complete": False,
        "needs_rounds": 0,
        "needs_input": None,
        # recommendation
        "recommendation_ids": [],
        "quote_ids": {},
        "eligible_count": 0,
        "decision": None,
        # application
        "application_id": None,
        "parties_complete": False,
        "answers_complete": False,
        "answers_rounds": 0,
        "confirmed": None,
        "confirm_rejections": 0,
        "correcting": False,
        # handoff
        "handoff_reason": None,
        "handoff_resolution": None,
        "resume_node": None,
        "resume_stage": None,
        "last_error": None,
    }

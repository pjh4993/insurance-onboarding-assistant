"""Session runtime: creates sessions, resumes the graph with customer/agent input, mirrors progress
into `OnboardingSession`, publishes SSE events, and turns an exhausted node into a handoff."""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from datetime import timedelta
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import (
    Application,
    InsurableObject,
    NeedsAssessment,
    OnboardingSession,
    Party,
    Recommendation,
)
from app.graph.state import initial_state
from app.services import views
from app.services.pubsub import Broker, Event
from app.util import Clock, hmac_hex, utcnow

log = logging.getLogger(__name__)

TERMINAL_STATUS = {"SUBMITTED": "SUBMITTED", "DECLINED": "DECLINED", "WITHDRAWN": "WITHDRAWN"}


class InputError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class Runtime:
    def __init__(
        self,
        *,
        graph: CompiledStateGraph,
        sessionmaker: async_sessionmaker[AsyncSession],
        broker: Broker,
        settings: Settings,
        clock: Clock = utcnow,
    ) -> None:
        self.graph = graph
        self.sessionmaker = sessionmaker
        self.broker = broker
        self.settings = settings
        self.clock = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------------------- lookups

    @staticmethod
    def config(session: OnboardingSession) -> dict[str, Any]:
        return {"configurable": {"thread_id": session.thread_id}}

    async def get_session(self, session_id: str) -> OnboardingSession | None:
        try:
            sid = uuid.UUID(str(session_id))
        except ValueError:
            return None
        async with self.sessionmaker() as s:
            return await s.get(OnboardingSession, sid)

    async def session_by_token(self, token: str) -> OnboardingSession | None:
        if not token:
            return None
        digest = hmac_hex(self.settings.session_hmac_key, token)
        async with self.sessionmaker() as s:
            return await s.scalar(select(OnboardingSession).where(OnboardingSession.token_hmac == digest))

    # ------------------------------------------------------------------------------- sessions

    async def create_session(self, market: str) -> tuple[OnboardingSession, str]:
        now = self.clock()
        token = secrets.token_urlsafe(32)
        session_id, party_id = uuid.uuid4(), uuid.uuid4()
        async with self.sessionmaker() as s, s.begin():
            s.add(
                Party(party_id=party_id, party_type="PERSON", verification_status="UNVERIFIED", verification_attempts=0)
            )
            await s.flush()
            session = OnboardingSession(
                session_id=session_id,
                thread_id=str(session_id),
                party_id=party_id,
                market=market,
                token_hmac=hmac_hex(self.settings.session_hmac_key, token),
                token_expires_at=now + timedelta(hours=self.settings.session_link_ttl_hours),
                status="ACTIVE",
                last_stage="IDENTITY",
                mode="AUTO",
                started_at=now,
                last_activity_at=now,
            )
            s.add(session)
        log.info("session created", extra={"session_id": str(session_id), "market": market})
        await self._run(session, initial_state(session_id=str(session_id), party_id=str(party_id), market=market))
        return await self.get_session(str(session_id)), token

    def is_busy(self, session_id: str) -> bool:
        lock = self._locks.get(session_id)
        return bool(lock and lock.locked()) or (session_id in self._tasks and not self._tasks[session_id].done())

    async def submit_input(self, session: OnboardingSession, input_type: str, data: dict[str, Any], actor: str) -> None:
        sid = str(session.session_id)
        if self.is_busy(sid):
            raise InputError(409, "the session is still processing the previous input")
        if session.waiting_for != input_type:
            raise InputError(409, f"session is waiting for {session.waiting_for}, not {input_type}")
        if input_type == "DECISION" and data.get("decision") == "ACCEPT" and data.get("recommendation_id"):
            state = (await self.graph.aget_state(self.config(session))).values
            if str(data["recommendation_id"]) not in (state.get("quote_ids") or {}):
                raise InputError(422, "recommendation_id is not one of the offered recommendations")
        command = Command(resume=data, update={"actor": actor, "mode": session.mode})
        self._tasks[sid] = asyncio.create_task(self._run(session, command))

    async def wait_idle(self, session_id: str, timeout: float = 30.0) -> None:
        task = self._tasks.get(session_id)
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout)

    async def assign(self, session_id: str, agent_id: str) -> OnboardingSession | None:
        async with self.sessionmaker() as s, s.begin():
            session = await s.get(OnboardingSession, uuid.UUID(session_id))
            if session is None:
                return None
            session.assigned_agent_id = agent_id
            session.mode = "ASSIST"
            session.last_activity_at = self.clock()
        await self._publish_summary(session)
        return session

    # ------------------------------------------------------------------------------- running

    async def _run(self, session: OnboardingSession, graph_input: Any) -> None:
        sid = str(session.session_id)
        lock = self._locks.setdefault(sid, asyncio.Lock())
        async with lock:
            config = self.config(session)
            await self._mark_processing(session)
            try:
                await self._stream(sid, graph_input, config)
            except Exception as exc:  # retries are exhausted (or a bug): hand the session to an agent
                log.warning("graph run failed", extra={"session_id": sid, "error.type": type(exc).__name__})
                try:
                    await self._recover(sid, config, exc)
                except Exception:
                    log.exception("could not route the failure to human_handoff", extra={"session_id": sid})
            finally:
                await self._sync_session(session)

    async def _stream(self, sid: str, graph_input: Any, config: dict[str, Any]) -> None:
        async for chunk in self.graph.astream(graph_input, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node.startswith("__") or not isinstance(update, dict):
                    continue
                for message in update.get("messages") or []:
                    await self.broker.publish(
                        Event(sid, "message.appended", {"session_id": sid, "message": views.message_view(message)})
                    )

    async def _recover(self, sid: str, config: dict[str, Any], exc: Exception) -> None:
        snapshot = await self.graph.aget_state(config)
        failed = snapshot.next[0] if snapshot.next else "unknown"
        error = {"node": failed, "kind": type(exc).__name__, "attempts": self.settings.retry_max_attempts}
        if failed == "unknown":
            return
        await self.graph.aupdate_state(config, {"last_error": error}, as_node=failed)
        await self._stream(sid, None, config)

    async def _mark_processing(self, session: OnboardingSession) -> None:
        async with self.sessionmaker() as s, s.begin():
            row = await s.get(OnboardingSession, session.session_id)
            row.waiting_for = None
            row.last_activity_at = self.clock()
            party = await s.get(Party, row.party_id)
        await self._publish_summary(row, party)

    async def _sync_session(self, session: OnboardingSession) -> None:
        """Mirror graph progress into OnboardingSession so the agent list needs no graph reads."""
        snapshot = await self.graph.aget_state(self.config(session))
        values = snapshot.values or {}
        waiting = None
        for task in snapshot.tasks:
            for intr in task.interrupts:
                if isinstance(intr.value, dict) and intr.value.get("waiting_for"):
                    waiting = intr.value["waiting_for"]
        stage = values.get("stage") or "IDENTITY"
        now = self.clock()
        async with self.sessionmaker() as s, s.begin():
            row = await s.get(OnboardingSession, session.session_id)
            row.last_stage = stage
            row.waiting_for = waiting
            row.current_node = snapshot.next[0] if snapshot.next else None
            row.last_activity_at = now
            if stage in TERMINAL_STATUS and not snapshot.next:
                row.status = TERMINAL_STATUS[stage]
                row.ended_at = row.ended_at or now
            elif stage == "HANDOFF":
                row.status = "HANDOFF"
            else:
                row.status = "ACTIVE"
            party = await s.get(Party, row.party_id)
        log.info(
            "turn finished",
            extra={
                "session_id": str(row.session_id),
                "stage": row.last_stage,
                "status": row.status,
                "waiting_for": row.waiting_for,
                "mode": row.mode,
            },
        )
        await self._publish_summary(row, party)
        prompt = await self.prompt(row, values)
        await self.broker.publish(
            Event(str(row.session_id), "prompt.updated", {"session_id": str(row.session_id), "prompt": prompt})
        )

    async def _publish_summary(self, session: OnboardingSession, party: Party | None = None) -> None:
        if party is None:
            async with self.sessionmaker() as s:
                party = await s.get(Party, session.party_id)
        await self.broker.publish(
            Event(str(session.session_id), "session.updated", {"session": views.summary_view(session, party)})
        )

    async def publish_entity(self, session_id: str, entity_type: str, entity_id: str) -> None:
        await self.broker.publish(
            Event(
                session_id,
                "entity.updated",
                {"session_id": session_id, "entity_type": entity_type, "entity_id": entity_id},
            )
        )

    # ------------------------------------------------------------------------------- views

    async def prompt(self, session: OnboardingSession, values: dict[str, Any]) -> dict[str, Any] | None:
        if not session.waiting_for:
            return None
        messages = values.get("messages") or []
        last_ai = next((m for m in reversed(messages) if m.type == "ai"), None)
        prompt: dict[str, Any] = {
            "waiting_for": session.waiting_for,
            "message": (last_ai.content if last_ai else "") or "",
        }
        async with self.sessionmaker() as s:
            if session.waiting_for == "DECISION":
                recs = await self._state_recs(s, values)
                offered = [r for r in recs if r.eligibility_result == "ELIGIBLE" and r.status == "PROPOSED"]
                prompt["options"] = await views.recommendation_cards(s, offered, values.get("quote_ids"))
            elif session.waiting_for == "CONFIRM" and values.get("application_id"):
                app = await s.get(Application, uuid.UUID(values["application_id"]))
                prompt["summary"] = app.summary if app else None
        return prompt

    @staticmethod
    async def _state_recs(s: AsyncSession, values: dict[str, Any]) -> list[Recommendation]:
        ids = [uuid.UUID(i) for i in values.get("recommendation_ids") or []]
        if not ids:
            return []
        rows = (await s.execute(select(Recommendation).where(Recommendation.recommendation_id.in_(ids)))).scalars()
        return sorted(rows, key=lambda r: (r.rank, r.product_code))

    async def session_view(self, session: OnboardingSession) -> dict[str, Any]:
        values = (await self.graph.aget_state(self.config(session))).values or {}
        async with self.sessionmaker() as s:
            party = await s.get(Party, session.party_id)
        return {
            "session": views.summary_view(session, party),
            "messages": [views.message_view(m) for m in values.get("messages") or []],
            "prompt": await self.prompt(session, values),
        }

    async def session_detail(self, session: OnboardingSession) -> dict[str, Any]:
        snapshot = await self.graph.aget_state(self.config(session))
        values = snapshot.values or {}
        base = await self.session_view(session)
        async with self.sessionmaker() as s:
            party = await s.get(Party, session.party_id)
            na = (
                await s.get(NeedsAssessment, uuid.UUID(values["needs_assessment_id"]))
                if values.get("needs_assessment_id")
                else None
            )
            object_ids = [uuid.UUID(i) for i in values.get("insurable_object_ids") or []]
            objects = (
                list(
                    (
                        await s.execute(
                            select(InsurableObject).where(InsurableObject.insurable_object_id.in_(object_ids))
                        )
                    ).scalars()
                )
                if object_ids
                else []
            )
            recs = list(
                (
                    await s.execute(
                        select(Recommendation)
                        .where(Recommendation.session_id == session.session_id)
                        .order_by(Recommendation.created_at.desc(), Recommendation.rank)
                    )
                ).scalars()
            )
            app = (
                await s.get(Application, uuid.UUID(values["application_id"])) if values.get("application_id") else None
            )
            parties = await views.application_parties(s, app.application_id) if app else []
            cards = await views.recommendation_cards(s, recs, values.get("quote_ids"))
        return {
            **base,
            "current_node": snapshot.next[0] if snapshot.next else None,
            "entities": {
                "party": views.party_detail(party),
                "needs_assessment": views.needs_detail(na),
                "insurable_objects": [views.object_detail(o) for o in objects],
                "recommendations": cards,
                "application": views.application_detail(app),
                "application_parties": parties,
            },
        }

    async def list_summaries(self) -> list[dict[str, Any]]:
        async with self.sessionmaker() as s:
            rows = (
                await s.execute(
                    select(OnboardingSession, Party).join(Party, Party.party_id == OnboardingSession.party_id)
                )
            ).all()
        items = [(sess, views.summary_view(sess, party)) for sess, party in rows]
        items.sort(key=lambda x: (x[0].waiting_for != "AGENT", x[0].last_activity_at))
        return [v for _, v in items]

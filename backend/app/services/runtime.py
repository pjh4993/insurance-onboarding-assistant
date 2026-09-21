"""Session runtime: creates sessions, hands customer/agent input to the agent (`AgentRunner`), mirrors
its progress into `OnboardingSession` and publishes SSE events. Running the graph, and turning an
exhausted node into a handoff, is the agent's job."""

from __future__ import annotations

import asyncio
import logging
import math
import secrets
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
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
from app.services import views
from app.services.pubsub import Broker, Event
from onboarding_agent import AgentRunner, AgentSnapshot, MessageSink
from onboarding_core.crypto import hmac_hex
from onboarding_core.locale import default_locale
from onboarding_core.ports import EntityListener
from onboarding_core.util import Clock, utcnow

log = logging.getLogger(__name__)

TERMINAL_STATUS = {"SUBMITTED": "SUBMITTED", "DECLINED": "DECLINED", "WITHDRAWN": "WITHDRAWN"}

AGENT_LINK, SELF_SERVE = "AGENT_LINK", "SELF_SERVE"
SELF_SERVE_WINDOW = timedelta(hours=1)
# Transaction-scoped advisory lock around the self-serve count-and-insert (init_db uses 724001).
SELF_SERVE_LOCK = 724002


def entity_listener(broker: Broker) -> EntityListener:
    """The agent's `on_entity` hook: tell SSE subscribers a domain entity changed."""

    async def on_entity(session_id: str, entity_type: str, entity_id: str) -> None:
        await broker.publish(
            Event(
                session_id,
                "entity.updated",
                {"session_id": session_id, "entity_type": entity_type, "entity_id": entity_id},
            )
        )

    return on_entity


class InputError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class RateLimited(Exception):
    """A self-serve start over a limit. `scope` is "ip" or "global"; `retry_after` is in whole seconds."""

    def __init__(self, scope: str, retry_after: int) -> None:
        super().__init__(f"self-serve {scope} limit reached")
        self.scope = scope
        self.retry_after = retry_after


class Runtime:
    def __init__(
        self,
        *,
        agent: AgentRunner,
        sessionmaker: async_sessionmaker[AsyncSession],
        broker: Broker,
        settings: Settings,
        languages: Mapping[str, str],
        default_language: str,
        clock: Clock = utcnow,
    ) -> None:
        self.agent = agent
        self.sessionmaker = sessionmaker
        self.broker = broker
        self.settings = settings
        self.clock = clock
        self.languages = dict(languages)  # the languages the agent's config bundle is written in
        self.default_language = default_language
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------------------- lookups

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

    def client_ip_hash(self, client_ip: str) -> str:
        return hmac_hex(self.settings.session_hmac_key, client_ip)

    def session_locale(self, market: str, locale: str | None = None) -> str:
        """The locale a session gets: the one asked for, which the agent must speak, or else the market's."""
        if locale is not None:
            if locale not in self.languages:
                raise InputError(422, f"locale {locale!r} is not one the agent speaks: {', '.join(self.languages)}")
            return locale
        market_default = default_locale(market)
        return market_default if market_default in self.languages else self.default_language

    async def create_session(
        self,
        market: str,
        locale: str | None = None,
        *,
        origin: str = AGENT_LINK,
        client_ip_hash: str | None = None,
    ) -> tuple[OnboardingSession, str]:
        """Create a session and run the graph's first turn. A SELF_SERVE start is checked against the
        rate limits in the same transaction as the insert, and raises RateLimited when over one."""
        now = self.clock()
        locale = self.session_locale(market, locale)
        token = secrets.token_urlsafe(32)
        session_id, party_id = uuid.uuid4(), uuid.uuid4()
        async with self.sessionmaker() as s, s.begin():
            if origin == SELF_SERVE:
                await self._check_self_serve_limits(s, client_ip_hash, now)
            s.add(
                Party(party_id=party_id, party_type="PERSON", verification_status="UNVERIFIED", verification_attempts=0)
            )
            await s.flush()
            session = OnboardingSession(
                session_id=session_id,
                thread_id=str(session_id),
                party_id=party_id,
                market=market,
                locale=locale,
                token_hmac=hmac_hex(self.settings.session_hmac_key, token),
                token_expires_at=now + timedelta(hours=self.settings.session_link_ttl_hours),
                status="ACTIVE",
                last_stage="IDENTITY",
                mode="AUTO",
                started_at=now,
                last_activity_at=now,
                origin=origin,
                client_ip_hash=client_ip_hash,
            )
            s.add(session)
        log.info(
            "session created",
            extra={"session_id": str(session_id), "market": market, "locale": locale, "origin": origin},
        )
        await self._run(
            session,
            lambda sink, extra: self.agent.start(
                session.thread_id,
                session_id=str(session_id),
                party_id=str(party_id),
                market=market,
                locale=locale,
                on_message=sink,
                log_extra=extra,
            ),
        )
        return await self.get_session(str(session_id)), token

    async def _check_self_serve_limits(self, s: AsyncSession, client_ip_hash: str | None, now: datetime) -> None:
        """Count SELF_SERVE sessions started in the last hour, per IP and overall, from the DB so the limits
        hold across replicas. The advisory lock is held until the transaction commits the new row, so two
        concurrent requests cannot both take the last slot."""
        await s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": SELF_SERVE_LOCK})
        since = now - SELF_SERVE_WINDOW
        recent = (OnboardingSession.origin == SELF_SERVE, OnboardingSession.started_at > since)
        same_ip = OnboardingSession.client_ip_hash == client_ip_hash
        checks = (
            ("ip", self.settings.self_serve_per_ip_per_hour, (*recent, same_ip)),
            ("global", self.settings.self_serve_per_hour, recent),
        )
        for scope, limit, where in checks:
            count = await s.scalar(select(func.count()).select_from(OnboardingSession).where(*where))
            if count < limit:
                continue
            # The slot frees when enough of the counted sessions leave the window to drop below the limit;
            # with count == limit, that is the oldest one.
            freed_at = await s.scalar(
                select(OnboardingSession.started_at)
                .where(*where)
                .order_by(OnboardingSession.started_at)
                .offset(count - limit)
                .limit(1)
            )
            wait = (freed_at + SELF_SERVE_WINDOW - now) if freed_at else SELF_SERVE_WINDOW  # None: a limit of 0
            retry_after = max(1, math.ceil(wait.total_seconds()))
            log.warning("self-serve rate limited", extra={"scope": scope, "retry_after": retry_after})
            raise RateLimited(scope, retry_after)

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
            state = (await self.agent.snapshot(session.thread_id)).values
            if str(data["recommendation_id"]) not in (state.get("quote_ids") or {}):
                raise InputError(422, "recommendation_id is not one of the offered recommendations")
        mode, locale = session.mode, session.locale
        self._tasks[sid] = asyncio.create_task(
            self._run(
                session,
                lambda sink, extra: self.agent.resume(
                    session.thread_id, data, actor=actor, mode=mode, locale=locale, on_message=sink, log_extra=extra
                ),
            )
        )

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

    async def set_locale(self, session_id: str, locale: str) -> OnboardingSession | None:
        """Only the session row changes here. The graph picks the new language up on its next resume, so a
        node that is running finishes in the old one and messages already sent are left as they were."""
        self.session_locale("", locale)
        async with self.sessionmaker() as s, s.begin():
            session = await s.get(OnboardingSession, uuid.UUID(session_id))
            if session is None:
                return None
            session.locale = locale
        await self._publish_summary(session)
        return session

    # ------------------------------------------------------------------------------- running

    async def _run(
        self, session: OnboardingSession, turn: Callable[[MessageSink, dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Run one agent turn under the session lock, streaming its messages to SSE subscribers."""
        sid = str(session.session_id)
        lock = self._locks.setdefault(sid, asyncio.Lock())

        async def publish(message: dict[str, Any]) -> None:
            await self.broker.publish(Event(sid, "message.appended", {"session_id": sid, "message": message}))

        async with lock:
            await self._mark_processing(session)
            try:
                await turn(publish, {"session_id": sid})
            finally:
                await self._sync_session(session)

    async def _mark_processing(self, session: OnboardingSession) -> None:
        async with self.sessionmaker() as s, s.begin():
            row = await s.get(OnboardingSession, session.session_id)
            row.waiting_for = None
            row.last_activity_at = self.clock()
            party = await s.get(Party, row.party_id)
        await self._publish_summary(row, party)

    async def _sync_session(self, session: OnboardingSession) -> None:
        """Mirror agent progress into OnboardingSession so the agent list needs no graph reads."""
        snapshot = await self.agent.snapshot(session.thread_id)
        stage = snapshot.values.get("stage") or "IDENTITY"
        now = self.clock()
        async with self.sessionmaker() as s, s.begin():
            row = await s.get(OnboardingSession, session.session_id)
            row.last_stage = stage
            row.waiting_for = snapshot.waiting_for
            row.current_node = snapshot.next_node
            row.last_activity_at = now
            if stage in TERMINAL_STATUS and not snapshot.next_node:
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
        prompt = await self.prompt(row, snapshot)
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

    # ------------------------------------------------------------------------------- views

    async def prompt(self, session: OnboardingSession, snapshot: AgentSnapshot) -> dict[str, Any] | None:
        if not session.waiting_for:
            return None
        values = snapshot.values
        last_ai = next((m for m in reversed(snapshot.messages) if m["role"] == "assistant"), None)
        prompt: dict[str, Any] = {
            "waiting_for": session.waiting_for,
            "message": (last_ai["text"] if last_ai else "") or "",
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

    async def session_view(self, session: OnboardingSession, snapshot: AgentSnapshot | None = None) -> dict[str, Any]:
        snapshot = snapshot or await self.agent.snapshot(session.thread_id)
        async with self.sessionmaker() as s:
            party = await s.get(Party, session.party_id)
        return {
            "session": views.summary_view(session, party),
            "messages": snapshot.messages,
            "prompt": await self.prompt(session, snapshot),
        }

    async def session_detail(self, session: OnboardingSession) -> dict[str, Any]:
        snapshot = await self.agent.snapshot(session.thread_id)
        values = snapshot.values
        base = await self.session_view(session, snapshot)
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
            "current_node": snapshot.next_node,
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

"""Runs scenarios through the real onboarding graph: the backend's Runtime on the compose Postgres, the
in-process partner/identity/contract fakes seeded with one record per scenario, OpenAI as the agent's LLM,
and a simulated customer (the customer model playing the persona) at every input the graph waits for."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import psycopg
from openai import AsyncOpenAI
from pydantic import BaseModel

from qa.llm import AGENT_MODEL, CUSTOMER_MODEL, OpenAIStructuredLLM, calls_var, parse
from qa.scenario import Brief, Scenario, persona_card

# The backend's app/ and tests/ are not installable packages; import them from the source tree.
BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from onboarding_agent import AgentConfig, AgentDeps, AgentRunner, build_graph, open_checkpointer
from onboarding_agent.config import default_bundle

from app.clients.external import ContractClient, IdentityClient, PartnerClient
from app.config import Settings
from app.db.engine import init_db, make_engine, make_sessionmaker
from app.db.uow import uow_factory
from app.services.pubsub import InMemoryBroker
from app.services.runtime import Runtime, entity_listener
from tests.fakes import FakeExternal

DATABASE_URL = os.environ.get(
    "SIM_DATABASE_URL", "postgresql+psycopg://onboarding:onboarding@localhost:15432/onboarding_sim"
)
MAX_STEPS = 25
STEP_TIMEOUT = 300.0

DECISION_PLAN = {
    "ACCEPT": "추천 상품이 나오면 가장 마음에 드는 것을 수락(ACCEPT)합니다.",
    "CHANGE": "처음 추천을 받으면 change_story대로 조건을 바꿔 CHANGE하고, 다시 추천을 받으면 수락(ACCEPT)합니다.",
    "DECLINE": "추천을 받으면 보험료나 조건을 보고 거절(DECLINE)합니다.",
}


class CustomerTurn(BaseModel):
    text: str
    decision: Literal["ACCEPT", "DECLINE", "CHANGE"] | None
    recommendation_id: str | None
    confirmed: bool | None


class Customer:
    """The customer model playing the scenario's persona, one reply per agent prompt."""

    def __init__(self, client: AsyncOpenAI, scenario: Scenario, brief: Brief) -> None:
        self._client = client
        self.changed = False
        behavior = f"\n- 이번 상담에서 특히: {scenario.behavior}" if scenario.behavior else ""
        self.system = f"""당신은 보험 가입 챗봇과 대화하는 고객입니다. 아래 인물로서 자연스럽게 답하세요.

[인물]
{persona_card(scenario.persona)}

[이번 상담의 사실관계 — 이 범위 안에서만 답하세요]
{brief.model_dump_json(indent=2)}

[행동 방침]
- 결정: {DECISION_PLAN[scenario.situation.decision]}
- 한국어로, speaking_style의 말투로, 한 번에 1~3문장만 말합니다.
- 챗봇이 물은 것에 답하되, 처음 필요를 말할 때는 이 인물이 실제로 말할 법한 만큼만 말합니다. 나이·직업·사는 곳은 물으면 답합니다.
- 사실관계에 없는 것은 지어내지 말고 모른다고 하거나 대략적으로 답합니다.{behavior}

JSON으로 답하세요. text는 고객이 입력하는 말입니다. decision, recommendation_id, confirmed는 해당 단계에서만 채우고 나머지는 null입니다."""

    async def reply(self, transcript: list[dict[str, Any]], prompt: dict[str, Any]) -> CustomerTurn:
        history = "\n".join(f"[{m['role']}] {m['text']}" for m in transcript if m.get("text"))
        ask = {
            "waiting_for": prompt["waiting_for"],
            "options": prompt.get("options"),
            "summary": prompt.get("summary"),
            "already_changed_once": self.changed,
        }
        user = f"""[지금까지의 대화]
{history}

[지금 챗봇이 기다리는 입력]
{json.dumps(ask, ensure_ascii=False, default=str)}

waiting_for가 DECISION이면 decision(ACCEPT/CHANGE/DECLINE)을 고르고, ACCEPT면 options 중 하나의 recommendation_id를 넣으세요. CHANGE면 text에 바꾸려는 조건을 쓰세요.
waiting_for가 CONFIRM이면 요약이 사실관계와 맞을 때 confirmed=true, 틀리면 false와 함께 text에 고칠 점을 쓰세요."""
        turn = await parse(
            self._client, CustomerTurn, [{"role": "system", "content": self.system}, {"role": "user", "content": user}]
        )
        if turn.decision == "CHANGE":
            self.changed = True
        return turn


def _admin_conninfo(url: str) -> tuple[str, str]:
    plain = url.replace("postgresql+psycopg://", "postgresql://", 1)
    base, _, dbname = plain.rpartition("/")
    return f"{base}/postgres", dbname.split("?")[0]


class Harness:
    def __init__(self, rt: Runtime, client: AsyncOpenAI, today: date) -> None:
        self.rt, self.client, self.today = rt, client, today

    async def converse(self, scenario: Scenario, run_id: str, repeat: int) -> dict[str, Any]:
        """One conversation of `scenario`; the trace carries everything checks and reports read."""
        brief, record = scenario.resolve(self.today), scenario.customer_record(self.today)
        trace: dict[str, Any] = {
            "trace_id": str(uuid.uuid4()),
            "run_id": run_id,
            "scenario_id": scenario.scenario_id,
            "suite": scenario.suite,
            "repeat_idx": repeat,
            "created_at": datetime.now(UTC),
            "models": {"agent": AGENT_MODEL, "customer": CUSTOMER_MODEL},
            "persona": scenario.persona,
            "situation": asdict(scenario.situation),
            "expect": asdict(scenario.expect),
            "brief": brief.model_dump(),
            "customer_record": record,
        }
        started = time.monotonic()
        try:
            trace |= await self._drive(scenario, brief, record)
        except Exception:
            trace["error"] = traceback.format_exc()
        trace["duration_s"] = round(time.monotonic() - started, 1)
        return trace

    async def _drive(self, scenario: Scenario, brief: Brief, record: dict[str, Any]) -> dict[str, Any]:
        rt, sit = self.rt, scenario.situation
        calls: list[dict[str, Any]] = []
        calls_var.set(calls)
        customer = Customer(self.client, scenario, brief)
        session, _token = await rt.create_session("KR")
        sid = str(session.session_id)
        turns: list[dict[str, Any]] = []
        for step in range(MAX_STEPS):
            session = await rt.get_session(sid)
            view = await rt.session_view(session)
            prompt = view["prompt"]
            if prompt is None or prompt["waiting_for"] == "AGENT":
                break
            waiting, utterance = prompt["waiting_for"], None
            if waiting == "IDENTITY_INFO":
                data = {k: record[k] for k in ("full_name", "email", "phone", "id_document_type", "id_document_number")}
                data |= {"date_of_birth": record["date_of_birth"], "third_party_consent": sit.identity == "PARTNER"}
            elif waiting == "OTP_CODE":
                data = {"code": (record["otp"] or {}).get("valid_code") or "123456"}
            else:
                started = time.monotonic()
                turn = await customer.reply(view["messages"], prompt)
                utterance = turn.model_dump() | {"latency_s": round(time.monotonic() - started, 2)}
                if waiting == "DECISION":
                    data = {"decision": turn.decision or "ACCEPT", "recommendation_id": turn.recommendation_id}
                    if turn.text:
                        data["text"] = turn.text
                elif waiting == "CONFIRM":
                    data = {"confirmed": bool(turn.confirmed), "text": turn.text}
                else:
                    data = {"text": turn.text}
            data = {k: v for k, v in data.items() if v is not None}
            before, started = len(calls), time.monotonic()
            await rt.submit_input(session, waiting, data, "CUSTOMER")
            await rt.wait_idle(sid, timeout=STEP_TIMEOUT)
            after = await rt.get_session(sid)
            agent_s = round(time.monotonic() - started, 2)
            turns.append(
                {
                    "step": step,
                    "waiting_for": waiting,
                    "agent_message": prompt["message"],
                    "options": prompt.get("options"),
                    "summary": prompt.get("summary"),
                    "customer": utterance,
                    "input": data,
                    "stage_after": after.last_stage,
                    "status_after": after.status,
                    "llm_calls": calls[before:],
                    "agent_s": agent_s,
                }
            )
        session = await rt.get_session(sid)
        detail = await rt.session_detail(session)
        values = (await rt.agent.snapshot(session.thread_id)).values
        return {
            "session_id": sid,
            "turns": turns,
            "messages": detail["messages"],
            "entities": detail["entities"],
            "final": {
                "status": session.status,
                "stage": session.last_stage,
                "waiting_for": session.waiting_for,
                "handoff_reason": values.get("handoff_reason"),
            },
        }


@asynccontextmanager
async def harness(scenarios: list[Scenario], today: date) -> AsyncIterator[Harness]:
    """A Runtime on a freshly created database, with the fakes knowing every scenario's customer."""
    admin, dbname = _admin_conninfo(DATABASE_URL)
    with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{dbname}"')
    settings = Settings(
        database_url=DATABASE_URL,
        partner_api_url="http://mock.test/partner",
        identity_api_url="http://mock.test/identity",
        contract_api_url="http://mock.test/contract",
    )
    engine = make_engine(settings.database_url)
    await init_db(engine)
    sm = make_sessionmaker(engine)
    transport = FakeExternal(customers=[s.customer_record(today) for s in scenarios]).transport()
    http = [
        httpx.AsyncClient(base_url=u, transport=transport)
        for u in (settings.partner_api_url, settings.identity_api_url, settings.contract_api_url)
    ]
    client = AsyncOpenAI()
    try:
        async with open_checkpointer(settings.psycopg_conninfo, settings.aes_key_bytes) as saver:
            broker = InMemoryBroker()
            deps = AgentDeps(
                config=AgentConfig(
                    aes_key=settings.aes_key_bytes,
                    hmac_key=settings.session_hmac_key,
                    retry_max_attempts=settings.retry_max_attempts,
                    retry_initial_interval=settings.retry_initial_interval,
                ),
                uow=uow_factory(sm),
                partner=PartnerClient(http[0]),
                identity=IdentityClient(http[1]),
                contract=ContractClient(http[2]),
                llm=OpenAIStructuredLLM(client),
                clock=lambda: datetime.now(UTC),
                on_entity=entity_listener(broker),
                bundle=default_bundle(),  # the newest bundle shipped with the backend under test
            )
            agent = AgentRunner(build_graph(deps, saver), retry_max_attempts=settings.retry_max_attempts)
            rt = Runtime(
                agent=agent,
                sessionmaker=sm,
                broker=broker,
                settings=settings,
                languages=deps.bundle.languages,
                default_language=deps.bundle.default_language,
                clock=deps.clock,
            )
            yield Harness(rt, client, today)
            await asyncio.gather(*(t for t in rt._tasks.values() if not t.done()), return_exceptions=True)
    finally:
        for c in http:
            await c.aclose()
        await engine.dispose()

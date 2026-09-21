"""Run a persona sample through the real onboarding graph and register one conversation trace per
persona in the lakehouse (`onboarding_traces.conversations`, `.turns`, `.llm_calls`).

Each persona gets a situation (identity path x need x decision) by its position in the sample.
OpenAI writes the persona's customer record and brief, plays the customer turn by turn, and stands
in for Bedrock as the agent's `StructuredLLM`. Partner, identity and contract systems are the
in-process fakes from backend/tests/fakes.py, seeded with one record per persona. Needs the compose
Postgres (host port 15432).

    uv run python -m pipeline.generate_traces --sample-id strat10-s42 [--limit N] [--json-dir DIR]

Env: OPENAI_API_KEY; SIM_AGENT_MODEL / SIM_CUSTOMER_MODEL (defaults and per-model
Chat Completions kwargs in pipeline/models.yaml);
SIM_DATABASE_URL (default: database `onboarding_sim` on the compose Postgres, recreated per run).
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import os
import random
import sys
import time
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import psycopg
import yaml
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from openai import AsyncOpenAI
from pydantic import BaseModel
from pyiceberg.expressions import EqualTo, In

from registry.catalog import catalog
from registry.tables import CONVERSATIONS, LLM_CALLS, NEMOTRON_KO, SAMPLES, TURNS, append, ensure

# The backend's app/ and tests/ are not installable packages; import them from the source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from onboarding_agent import AgentConfig, AgentDeps, AgentRunner, build_graph, open_checkpointer

from app.clients.external import ContractClient, IdentityClient, PartnerClient
from app.config import Settings
from app.db.engine import init_db, make_engine, make_sessionmaker
from app.db.uow import uow_factory
from app.services.pubsub import InMemoryBroker
from app.services.runtime import Runtime, entity_listener
from tests.fakes import FakeExternal

MODELS = yaml.safe_load((Path(__file__).with_name("models.yaml")).read_text())
AGENT_MODEL = os.environ.get("SIM_AGENT_MODEL", MODELS["roles"]["agent"])
CUSTOMER_MODEL = os.environ.get("SIM_CUSTOMER_MODEL", MODELS["roles"]["customer"])
DATABASE_URL = os.environ.get(
    "SIM_DATABASE_URL", "postgresql+psycopg://onboarding:onboarding@localhost:15432/onboarding_sim"
)
MAX_STEPS = 25
STEP_TIMEOUT = 300.0


def call_kwargs(model: str, kind: Literal["tools", "parse"]) -> dict[str, Any]:
    return dict((MODELS["models"].get(model) or {}).get(kind) or {})


# The LLM calls of the persona whose turn is running; Runtime tasks copy the context they start in.
_calls: contextvars.ContextVar[list[dict[str, Any]]] = contextvars.ContextVar("calls")

# --------------------------------------------------------------------------------- situations

IdentityPath = Literal["PARTNER", "OTP", "DOCUMENT", "HANDOFF"]
Need = Literal["PHONE", "LAPTOP", "APPLIANCE", "TRAVEL", "OLD_PHONE"]
DecisionPlan = Literal["ACCEPT", "CHANGE", "DECLINE"]


@dataclass(frozen=True)
class Situation:
    identity: IdentityPath
    need: Need
    decision: DecisionPlan
    note: str
    expected: Literal["SUBMITTED", "DECLINED", "HANDOFF"]


# Assigned by position, so a stratified sample covers every identity path, KR product and decision.
SITUATIONS = [
    Situation("OTP", "TRAVEL", "ACCEPT", "해외여행을 앞두고 여행자보험 가입", "SUBMITTED"),
    Situation("PARTNER", "PHONE", "ACCEPT", "제휴처에서 산 새 스마트폰 보장", "SUBMITTED"),
    Situation("DOCUMENT", "LAPTOP", "CHANGE", "새 노트북 보장. 처음에 가격이나 모델을 잘못 말해 정정", "SUBMITTED"),
    Situation("OTP", "PHONE", "DECLINE", "새 스마트폰 보장을 알아보지만 보험료를 보고 거절", "DECLINED"),
    Situation("OTP", "APPLIANCE", "ACCEPT", "오늘 산 TV·가전의 연장 보증", "SUBMITTED"),
    Situation("PARTNER", "LAPTOP", "ACCEPT", "가족이 쓸 새 노트북. 피보험자가 본인이 아닌 가족", "SUBMITTED"),
    Situation("DOCUMENT", "TRAVEL", "ACCEPT", "가족과 함께 가는 해외여행", "SUBMITTED"),
    Situation("HANDOFF", "PHONE", "ACCEPT", "본인확인(OTP·신분증)이 모두 실패", "HANDOFF"),
    Situation(
        "OTP", "APPLIANCE", "CHANGE", "오늘 산 가전 연장 보증. 결정 단계에서 조건을 바꿔 다시 추천받음", "SUBMITTED"
    ),
    Situation("OTP", "OLD_PHONE", "ACCEPT", "5개월 전에 개통한 스마트폰 보장을 원함 (가입 불가)", "HANDOFF"),
]

NEED_RULES = {
    "PHONE": "삼성 또는 애플 스마트폰, 오늘 기준 30일 이내 구매·개통한 새 폰, 파손 없음.",
    "OLD_PHONE": "삼성 또는 애플 스마트폰, 오늘 기준 약 5개월 전에 구매·개통.",
    "LAPTOP": "노트북 또는 태블릿, 오늘 기준 60일 이내 구매한 새 제품.",
    "APPLIANCE": "TV 또는 가전(냉장고·세탁기 등), 오늘 구매, 구매가 500만원 이하.",
    "TRAVEL": "한국 출발 해외여행, 출발일은 오늘 이후 2~8주 사이, 여행 기간 3~14일.",
}

# ------------------------------------------------------------------------------ OpenAI roles


def _openai_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    def role(m: BaseMessage) -> str:
        if isinstance(m, SystemMessage):
            return "system"
        return "assistant" if isinstance(m, AIMessage) else "user"

    return [{"role": role(m), "content": m.content if isinstance(m.content, str) else str(m.content)} for m in messages]


class OpenAIStructuredLLM:
    """The agent's `StructuredLLM` over OpenAI function calling, the method Bedrock uses."""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def extract(self, node: str, schema: type[BaseModel], messages: list[BaseMessage]) -> Any:
        name = schema.__name__
        tool = {
            "type": "function",
            "function": {"name": name, "description": schema.__doc__ or name, "parameters": schema.model_json_schema()},
        }
        started = time.monotonic()
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=_openai_messages(messages),
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": name}},
            **call_kwargs(self._model, "tools"),
        )
        calls = resp.choices[0].message.tool_calls
        if not calls:
            raise ValueError(f"{node}: model returned no {name} tool call")
        result = schema.model_validate_json(calls[0].function.arguments)
        _calls.get([]).append(
            {
                "node": node,
                "schema": name,
                "model": self._model,
                "input": [{"role": m["role"], "content": m["content"]} for m in _openai_messages(messages)],
                "output": result.model_dump(),
                "latency_s": round(time.monotonic() - started, 2),
                "usage": resp.usage.model_dump() if resp.usage else None,
            }
        )
        return result


class Device(BaseModel):
    category: Literal["SMARTPHONE", "NOTEBOOK", "TABLET", "TV", "APPLIANCE"]
    manufacturer: str
    model: str
    purchase_date: str
    price_krw: int
    serial_or_imei: str


class Trip(BaseModel):
    destination_country: str
    destination_city: str
    departure_date: str
    return_date: str


class OtherPerson(BaseModel):
    relation: str
    full_name: str
    date_of_birth: str
    gender: Literal["M", "F"]
    role: Literal["INSURED", "PAYER", "COMPANION"]


class Brief(BaseModel):
    full_name: str
    email: str
    phone: str
    date_of_birth: str
    gender: Literal["M", "F"]
    need_story: str
    device: Device | None
    trip: Trip | None
    other_people: list[OtherPerson]
    change_story: str
    speaking_style: str


class CustomerTurn(BaseModel):
    text: str
    decision: Literal["ACCEPT", "DECLINE", "CHANGE"] | None
    recommendation_id: str | None
    confirmed: bool | None


def persona_card(p: dict[str, Any]) -> str:
    keys = [
        "persona", "sex", "age", "marital_status", "family_type", "housing_type", "education_level",
        "occupation", "district", "cultural_background", "professional_persona", "family_persona",
        "travel_persona", "hobbies_and_interests",
    ]  # fmt: skip
    return "\n".join(f"- {k}: {p[k]}" for k in keys if p.get(k))


async def write_brief(client: AsyncOpenAI, persona: dict[str, Any], sit: Situation, today: date) -> Brief:
    prompt = f"""오늘은 {today.isoformat()}입니다. 아래 한국인 페르소나가 보험 가입 상담을 받는 상황을 준비합니다.

[페르소나]
{persona_card(persona)}

[상황] {sit.note}
[필요한 보험 대상 조건] {NEED_RULES[sit.need]}

페르소나와 일관된 고객 정보와 사연을 만드세요.
- full_name: 페르소나 글에 이름이 있으면 그 이름, 없으면 어울리는 한국 이름
- email: 이름을 로마자로 쓴 @example.com 주소, phone: +8210으로 시작하는 11자리 번호
- date_of_birth: 나이 {persona["age"]}세와 맞는 YYYY-MM-DD
- need_story: 이 사람이 왜 보험을 찾는지 페르소나 삶에 맞춘 2~3문장
- device: 기기 대상이면 조건에 맞는 기기(가격은 원 단위, 실제 시세 수준), 여행이면 null
- trip: 여행이면 조건에 맞는 여행(destination_country는 ISO 두 글자), 아니면 null
- other_people: 피보험자·납입자·동행자가 본인 외에 있으면 적고, 없으면 빈 배열
- change_story: 상담 중 정정하거나 조건을 바꿀 내용(이 상황에 없으면 빈 문자열)
- speaking_style: 나이·지역·학력에 맞는 말투 설명 한두 줄"""
    resp = await client.chat.completions.parse(
        model=CUSTOMER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format=Brief,
        **call_kwargs(CUSTOMER_MODEL, "parse"),
    )
    return resp.choices[0].message.parsed


DECISION_PLAN = {
    "ACCEPT": "추천 상품이 나오면 가장 마음에 드는 것을 수락(ACCEPT)합니다.",
    "CHANGE": "처음 추천을 받으면 change_story대로 조건을 바꿔 CHANGE하고, 다시 추천을 받으면 수락(ACCEPT)합니다.",
    "DECLINE": "추천을 받으면 보험료나 조건을 보고 거절(DECLINE)합니다.",
}


class Customer:
    """OpenAI playing the persona, one reply per agent prompt."""

    def __init__(self, client: AsyncOpenAI, persona: dict[str, Any], sit: Situation, brief: Brief) -> None:
        self._client = client
        self.changed = False
        self.system = f"""당신은 보험 가입 챗봇과 대화하는 고객입니다. 아래 인물로서 자연스럽게 답하세요.

[인물]
{persona_card(persona)}

[이번 상담의 사실관계 — 이 범위 안에서만 답하세요]
{brief.model_dump_json(indent=2)}

[행동 방침]
- 결정: {DECISION_PLAN[sit.decision]}
- 한국어로, speaking_style의 말투로, 한 번에 1~3문장만 말합니다.
- 챗봇이 물은 것에 답하되, 처음 필요를 말할 때는 이 인물이 실제로 말할 법한 만큼만 말합니다. 나이·직업·사는 곳은 물으면 답합니다.
- 사실관계에 없는 것은 지어내지 말고 모른다고 하거나 대략적으로 답합니다.

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
        resp = await self._client.chat.completions.parse(
            model=CUSTOMER_MODEL,
            messages=[{"role": "system", "content": self.system}, {"role": "user", "content": user}],
            response_format=CustomerTurn,
            **call_kwargs(CUSTOMER_MODEL, "parse"),
        )
        turn = resp.choices[0].message.parsed
        if turn.decision == "CHANGE":
            self.changed = True
        return turn


# ------------------------------------------------------------------------ customer records


def customer_record(key: str, brief: Brief, sit: Situation, rng: random.Random) -> dict[str, Any]:
    """A seed-customers.json record for the fakes: what the partner and identity systems know."""
    dob = date.fromisoformat(brief.date_of_birth)
    gender_digit = (1 if brief.gender == "M" else 2) + (2 if dob.year >= 2000 else 0)
    record: dict[str, Any] = {
        "key": key,
        "market": "KR",
        "scenario": sit.note,
        "full_name": brief.full_name,
        "email": brief.email,
        "phone": brief.phone,
        "date_of_birth": brief.date_of_birth,
        "id_document_type": "NATIONAL_ID",
        "id_document_number": f"{dob:%y%m%d}-{gender_digit}{rng.randrange(10**6):06d}",
        "partner": None,
        "otp": None,
        "document_valid": sit.identity != "HANDOFF",
        "needs_text": brief.need_story,
    }
    if sit.identity == "PARTNER" and brief.device:
        d = brief.device
        record["partner"] = {
            "partner_customer_ref": f"P-SIM-{key[:8]}",
            "purchases": [
                {
                    "order_id": f"O-SIM-{rng.randrange(10**6):06d}",
                    "purchased_at": f"{d.purchase_date}T03:00:00Z",
                    "item": {
                        "category": d.category,
                        "manufacturer": d.manufacturer,
                        "model": d.model,
                        "imei": d.serial_or_imei,
                        "release_date": d.purchase_date,
                        "activation_date": d.purchase_date,
                        "price_minor": d.price_krw,
                        "currency": "KRW",
                    },
                }
            ],
        }
    if sit.identity == "OTP":
        record["otp"] = {"valid_code": f"{rng.randrange(10**6):06d}"}
    elif sit.identity == "DOCUMENT":
        record["otp"] = {"valid_code": None}
    return record


# ---------------------------------------------------------------------------------- driver


async def simulate(
    rt: Runtime, client: AsyncOpenAI, persona: dict[str, Any], sit: Situation, record: dict[str, Any], brief: Brief
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    _calls.set(calls)
    customer = Customer(client, persona, sit, brief)
    session, _token = await rt.create_session("KR")
    sid = str(session.session_id)
    turns: list[dict[str, Any]] = []
    for step in range(MAX_STEPS):
        session = await rt.get_session(sid)
        view = await rt.session_view(session)
        prompt = view["prompt"]
        if prompt is None or prompt["waiting_for"] == "AGENT":
            break
        waiting = prompt["waiting_for"]
        utterance = None
        if waiting == "IDENTITY_INFO":
            data = {k: record[k] for k in ("full_name", "email", "phone", "id_document_type", "id_document_number")}
            data |= {"date_of_birth": record["date_of_birth"], "third_party_consent": sit.identity == "PARTNER"}
        elif waiting == "OTP_CODE":
            valid = (record["otp"] or {}).get("valid_code")
            data = {"code": valid or "123456"}
        else:
            turn = await customer.reply(view["messages"], prompt)
            utterance = turn.model_dump()
            if waiting == "DECISION":
                data = {"decision": turn.decision or "ACCEPT", "recommendation_id": turn.recommendation_id}
                if turn.text:
                    data["text"] = turn.text
            elif waiting == "CONFIRM":
                data = {"confirmed": bool(turn.confirmed), "text": turn.text}
            else:
                data = {"text": turn.text}
        data = {k: v for k, v in data.items() if v is not None}
        before = len(calls)
        await rt.submit_input(session, waiting, data, "CUSTOMER")
        await rt.wait_idle(sid, timeout=STEP_TIMEOUT)
        after = await rt.get_session(sid)
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
            }
        )
    session = await rt.get_session(sid)
    detail = await rt.session_detail(session)
    return {
        "session_id": sid,
        "turns": turns,
        "messages": detail["messages"],
        "entities": detail["entities"],
        "final": {"status": session.status, "stage": session.last_stage, "waiting_for": session.waiting_for},
    }


def _admin_conninfo(url: str) -> tuple[str, str]:
    plain = url.replace("postgresql+psycopg://", "postgresql://", 1)
    base, _, dbname = plain.rpartition("/")
    return f"{base}/postgres", dbname.split("?")[0]


def load_sample(sample_id: str, limit: int | None) -> list[dict[str, Any]]:
    """The sample's persona rows in position order, each with its `position`."""
    cat = catalog()
    rows = ensure(cat, SAMPLES).scan(row_filter=EqualTo("sample_id", sample_id)).to_arrow().to_pylist()
    if not rows:
        raise SystemExit(f"no sample {sample_id}; create it with pipeline.sample_personas")
    rows = sorted(rows, key=lambda r: r["position"])[:limit]
    position = {r["persona_uuid"]: r["position"] for r in rows}
    personas = ensure(cat, NEMOTRON_KO).scan(row_filter=In("uuid", list(position))).to_arrow().to_pylist()
    return sorted(({**p, "position": position[p["uuid"]]} for p in personas), key=lambda p: p["position"])


async def run(personas: list[dict[str, Any]], run_id: str, concurrency: int, seed: int) -> list[dict[str, Any]]:
    admin, dbname = _admin_conninfo(DATABASE_URL)
    with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{dbname}"')

    client = AsyncOpenAI()
    today = datetime.now(UTC).date()
    rng = random.Random(seed)
    situations = [SITUATIONS[p["position"] % len(SITUATIONS)] for p in personas]
    briefs = await asyncio.gather(
        *(write_brief(client, p, s, today) for p, s in zip(personas, situations, strict=True))
    )
    records = [customer_record(p["uuid"], b, s, rng) for p, b, s in zip(personas, briefs, situations, strict=True)]

    settings = Settings(
        database_url=DATABASE_URL,
        partner_api_url="http://mock.test/partner",
        identity_api_url="http://mock.test/identity",
        contract_api_url="http://mock.test/contract",
    )
    engine = make_engine(settings.database_url)
    await init_db(engine)
    sm = make_sessionmaker(engine)
    transport = FakeExternal(customers=records).transport()
    http = [
        httpx.AsyncClient(base_url=u, transport=transport)
        for u in (settings.partner_api_url, settings.identity_api_url, settings.contract_api_url)
    ]
    limit = asyncio.Semaphore(concurrency)
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
                llm=OpenAIStructuredLLM(client, AGENT_MODEL),
                clock=lambda: datetime.now(UTC),
                on_entity=entity_listener(broker),
            )
            agent = AgentRunner(build_graph(deps, saver), retry_max_attempts=settings.retry_max_attempts)
            rt = Runtime(agent=agent, sessionmaker=sm, broker=broker, settings=settings, clock=deps.clock)

            async def one(p: dict[str, Any], s: Situation, rec: dict[str, Any], brief: Brief) -> dict[str, Any]:
                async with limit:
                    started = time.monotonic()
                    trace: dict[str, Any] = {
                        "trace_id": str(uuid.uuid4()),
                        "run_id": run_id,
                        "created_at": datetime.now(UTC),
                        "models": {"agent": AGENT_MODEL, "customer": CUSTOMER_MODEL},
                        "persona": p,
                        "situation": asdict(s),
                        "brief": brief.model_dump(),
                        "customer_record": rec,
                    }
                    try:
                        trace |= await simulate(rt, client, p, s, rec, brief)
                    except Exception:
                        trace["error"] = traceback.format_exc()
                    trace["duration_s"] = round(time.monotonic() - started, 1)
                    status = trace.get("final", {}).get("status")
                    print(f"{p['position']:3} {p['uuid'][:8]} {s.identity:8} {s.need:9} {s.decision:7} -> {status}")
                    return trace

            traces = await asyncio.gather(
                *(one(*args) for args in zip(personas, situations, records, briefs, strict=True))
            )
            await asyncio.gather(*(t for t in rt._tasks.values() if not t.done()), return_exceptions=True)
    finally:
        for c in http:
            await c.aclose()
        await engine.dispose()
    return traces


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def _tokens(calls: list[dict[str, Any]], key: str) -> int:
    return sum((c.get("usage") or {}).get(key) or 0 for c in calls)


def register(traces: list[dict[str, Any]], sample_id: str) -> None:
    """Append the run's conversations, turns and LLM calls to the lakehouse."""
    conversations, turns, calls = [], [], []
    for t in traces:
        run_calls = [c for turn in t.get("turns", []) for c in turn["llm_calls"]]
        final = t.get("final", {})
        sit = t["situation"]
        conversations.append(
            {
                "trace_id": t["trace_id"],
                "run_id": t["run_id"],
                "sample_id": sample_id,
                "position": t["persona"]["position"],
                "persona_uuid": t["persona"]["uuid"],
                "situation_identity": sit["identity"],
                "situation_need": sit["need"],
                "situation_decision": sit["decision"],
                "situation_note": sit["note"],
                "expected_status": sit["expected"],
                "final_status": final.get("status"),
                "final_stage": final.get("stage"),
                "final_waiting_for": final.get("waiting_for"),
                "matches_expected": final.get("status") == sit["expected"],
                "agent_model": t["models"]["agent"],
                "customer_model": t["models"]["customer"],
                "session_id": t.get("session_id"),
                "n_turns": len(t.get("turns", [])),
                "n_llm_calls": len(run_calls),
                "prompt_tokens": _tokens(run_calls, "prompt_tokens"),
                "completion_tokens": _tokens(run_calls, "completion_tokens"),
                "duration_s": t["duration_s"],
                "error": t.get("error"),
                "brief_json": _json(t["brief"]),
                "customer_record_json": _json(t["customer_record"]),
                "messages_json": _json(t.get("messages")),
                "entities_json": _json(t.get("entities")),
                "created_at": t["created_at"],
            }
        )
        for turn in t.get("turns", []):
            turns.append(
                {
                    "trace_id": t["trace_id"],
                    "run_id": t["run_id"],
                    "step": turn["step"],
                    "waiting_for": turn["waiting_for"],
                    "agent_message": turn["agent_message"],
                    "customer_text": (turn["customer"] or {}).get("text"),
                    "input_json": _json(turn["input"]),
                    "options_json": _json(turn["options"]) if turn["options"] else None,
                    "summary": turn["summary"],
                    "stage_after": turn["stage_after"],
                    "status_after": turn["status_after"],
                }
            )
            for seq, c in enumerate(turn["llm_calls"]):
                usage = c.get("usage") or {}
                calls.append(
                    {
                        "trace_id": t["trace_id"],
                        "run_id": t["run_id"],
                        "step": turn["step"],
                        "seq": seq,
                        "node": c["node"],
                        "schema_name": c["schema"],
                        "model": c["model"],
                        "input_json": _json(c["input"]),
                        "output_json": _json(c["output"]),
                        "latency_s": c["latency_s"],
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                    }
                )
    cat = catalog()
    for table, rows in ((CONVERSATIONS, conversations), (TURNS, turns), (LLM_CALLS, calls)):
        print(f"{table.identifier}: +{append(cat, table, rows)} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json-dir", type=Path, help="also write each full trace as <dir>/<run_id>/<uuid>.json")
    args = parser.parse_args()

    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    personas = load_sample(args.sample_id, args.limit)
    print(f"run {run_id}: {len(personas)} personas from {args.sample_id}")
    traces = asyncio.run(run(personas, run_id, args.concurrency, args.seed))
    if args.json_dir:
        out = args.json_dir / run_id
        out.mkdir(parents=True, exist_ok=True)
        for t in traces:
            (out / f"{t['persona']['uuid']}.json").write_text(json.dumps(t, ensure_ascii=False, indent=2, default=str))
    register(traces, args.sample_id)
    ok = sum(t.get("final", {}).get("status") == t["situation"]["expected"] for t in traces)
    print(f"run {run_id}: {ok}/{len(traces)} ended as expected")


if __name__ == "__main__":
    main()

"""Scenarios: a persona, the situation it is in, the facts it knows (the brief), how it behaves, and what the
conversation should end with. Scenarios are frozen in `onboarding_traces.qa_scenarios` so every run of a
suite replays the same customers; dates are stored relative to the day ("today+21") so they stay valid.

Two sources: `freeze_sample` has the customer model write briefs for a persona sample (the smoke suite),
and `load_yaml` reads hand-written suites (qa/suites/*.yaml, the regressions)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from onboarding_core.util import market_today
from openai import AsyncOpenAI
from pydantic import BaseModel
from pyiceberg.expressions import EqualTo, In

from qa.llm import parse
from registry.catalog import catalog
from registry.tables import NEMOTRON_KO, QA_SCENARIOS, SAMPLES, append, ensure

IdentityPath = Literal["PARTNER", "OTP", "DOCUMENT", "HANDOFF"]
Need = Literal["PHONE", "LAPTOP", "APPLIANCE", "TRAVEL", "OLD_PHONE"]
DecisionPlan = Literal["ACCEPT", "CHANGE", "DECLINE"]
Status = Literal["SUBMITTED", "DECLINED", "HANDOFF"]


@dataclass(frozen=True)
class Situation:
    identity: IdentityPath
    need: Need
    decision: DecisionPlan
    note: str


@dataclass(frozen=True)
class Expect:
    status: Status
    product: str | None = None
    max_turns: int = 14


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


@dataclass
class Scenario:
    scenario_id: str
    suite: str
    persona: dict[str, Any]
    situation: Situation
    brief: dict[str, Any]  # a Brief with relative dates; `resolve` turns it into a Brief for one day
    expect: Expect
    behavior: str = ""
    source: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def resolve(self, today: date) -> Brief:
        """The brief for `today`, with contact details made unique to this scenario: the identity fakes look
        customers up by phone and email, so two scenarios must never share them."""
        brief = Brief.model_validate(_map_dates(self.brief, lambda v: _absolute(v, today)))
        digits = int(hashlib.sha256(self.scenario_id.encode()).hexdigest(), 16) % 10**8
        local, _, domain = brief.email.partition("@")
        return brief.model_copy(
            update={"phone": f"+8210{digits:08d}", "email": f"{local}+{self.scenario_id}@{domain or 'example.com'}"}
        )

    def customer_record(self, today: date) -> dict[str, Any]:
        """A seed-customers.json record for the fakes: what the partner and identity systems know."""
        brief, sit = self.resolve(today), self.situation
        rng = random.Random(self.scenario_id)
        dob = date.fromisoformat(brief.date_of_birth)
        gender_digit = (1 if brief.gender == "M" else 2) + (2 if dob.year >= 2000 else 0)
        record: dict[str, Any] = {
            "key": self.scenario_id,
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
                "partner_customer_ref": f"P-QA-{self.scenario_id}",
                "purchases": [
                    {
                        "order_id": f"O-QA-{rng.randrange(10**6):06d}",
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


# ------------------------------------------------------------------------------------ dates


def market_date(market: str = "KR") -> date:
    """Today as the agent sees it (the market's calendar), so "today" in a brief is the agent's today."""
    return market_today(market, datetime.now(UTC))


DATE_PATHS = (("device", "purchase_date"), ("trip", "departure_date"), ("trip", "return_date"))
_REL = re.compile(r"^today([+-]\d+)?$")


def _map_dates(brief: dict[str, Any], fn) -> dict[str, Any]:
    out = json.loads(json.dumps(brief))
    for obj, key in DATE_PATHS:
        if out.get(obj) and out[obj].get(key):
            out[obj][key] = fn(out[obj][key])
    return out


def _absolute(value: str, today: date) -> str:
    m = _REL.match(value)
    return (today + timedelta(days=int(m[1] or 0))).isoformat() if m else value


def _relative(value: str, today: date) -> str:
    days = (date.fromisoformat(value) - today).days
    return f"today{days:+d}" if days else "today"


# ------------------------------------------------------------------------------- the smoke suite

# Assigned by position, so a stratified sample covers every identity path, KR product and decision.
SITUATIONS: list[tuple[Situation, Expect]] = [
    (Situation("OTP", "TRAVEL", "ACCEPT", "해외여행을 앞두고 여행자보험 가입"), Expect("SUBMITTED", "KR-TRV-OVERSEAS")),
    (Situation("PARTNER", "PHONE", "ACCEPT", "제휴처에서 산 새 스마트폰 보장"), Expect("SUBMITTED", "KR-MOB-SWAP")),
    (
        Situation("DOCUMENT", "LAPTOP", "CHANGE", "새 노트북 보장. 처음에 가격이나 모델을 잘못 말해 정정"),
        Expect("SUBMITTED", "KR-DEV-LAPTOP"),
    ),
    (Situation("OTP", "PHONE", "DECLINE", "새 스마트폰 보장을 알아보지만 보험료를 보고 거절"), Expect("DECLINED")),
    (Situation("OTP", "APPLIANCE", "ACCEPT", "오늘 산 TV·가전의 연장 보증"), Expect("SUBMITTED", "KR-EW-HOME")),
    (
        Situation("PARTNER", "LAPTOP", "ACCEPT", "가족이 쓸 새 노트북. 피보험자가 본인이 아닌 가족"),
        Expect("SUBMITTED", "KR-DEV-LAPTOP"),
    ),
    (Situation("DOCUMENT", "TRAVEL", "ACCEPT", "가족과 함께 가는 해외여행"), Expect("SUBMITTED", "KR-TRV-OVERSEAS")),
    (Situation("HANDOFF", "PHONE", "ACCEPT", "본인확인(OTP·신분증)이 모두 실패"), Expect("HANDOFF")),
    (
        Situation("OTP", "APPLIANCE", "CHANGE", "오늘 산 가전 연장 보증. 결정 단계에서 조건을 바꿔 다시 추천받음"),
        Expect("SUBMITTED", "KR-EW-HOME"),
    ),
    (Situation("OTP", "OLD_PHONE", "ACCEPT", "5개월 전에 개통한 스마트폰 보장을 원함 (가입 불가)"), Expect("HANDOFF")),
]

NEED_RULES = {
    "PHONE": "삼성 또는 애플 스마트폰, 오늘 기준 30일 이내 구매·개통한 새 폰, 파손 없음.",
    "OLD_PHONE": "삼성 또는 애플 스마트폰, 오늘 기준 약 5개월 전에 구매·개통.",
    "LAPTOP": "노트북 또는 태블릿, 오늘 기준 60일 이내 구매한 새 제품.",
    "APPLIANCE": "TV 또는 가전(냉장고·세탁기 등), 오늘 구매, 구매가 500만원 이하.",
    "TRAVEL": "한국 출발 해외여행, 출발일은 오늘 이후 2~8주 사이, 여행 기간 3~14일.",
}


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
- need_story: 이 사람이 왜 보험을 찾는지 페르소나 삶에 맞춘 2~3문장. 날짜는 쓰지 마세요.
- device: 기기 대상이면 조건에 맞는 기기(가격은 원 단위, 실제 시세 수준), 여행이면 null
- trip: 여행이면 조건에 맞는 여행(destination_country는 ISO 두 글자), 아니면 null
- other_people: 피보험자·납입자·동행자가 본인 외에 있으면 적고, 없으면 빈 배열
- change_story: 상담 중 정정하거나 조건을 바꿀 내용(이 상황에 없으면 빈 문자열)
- speaking_style: 나이·지역·학력에 맞는 말투 설명 한두 줄"""
    return await parse(client, Brief, [{"role": "user", "content": prompt}])


def personas_by_uuid(uuids: list[str]) -> dict[str, dict[str, Any]]:
    rows = ensure(catalog(), NEMOTRON_KO).scan(row_filter=In("uuid", uuids)).to_arrow().to_pylist()
    return {r["uuid"]: r for r in rows}


async def freeze_sample(sample_id: str, suite: str) -> list[Scenario]:
    """Scenarios for every persona of a sample, with briefs written now by the customer model."""
    rows = ensure(catalog(), SAMPLES).scan(row_filter=EqualTo("sample_id", sample_id)).to_arrow().to_pylist()
    if not rows:
        raise SystemExit(f"no sample {sample_id}")
    rows.sort(key=lambda r: r["position"])
    personas = personas_by_uuid([r["persona_uuid"] for r in rows])
    today, client = market_date(), AsyncOpenAI()
    picks = [(r, *SITUATIONS[r["position"] % len(SITUATIONS)]) for r in rows]
    briefs = await asyncio.gather(
        *(write_brief(client, personas[r["persona_uuid"]], sit, today) for r, sit, _ in picks)
    )
    return [
        Scenario(
            scenario_id=f"{suite}-{r['position']:02d}",
            suite=suite,
            persona=personas[r["persona_uuid"]],
            situation=sit,
            brief=_map_dates(b.model_dump(), lambda v: _relative(v, today)),
            expect=exp,
            source=f"sample:{sample_id}",
        )
        for (r, sit, exp), b in zip(picks, briefs, strict=True)
    ]


def load_yaml(path: Path) -> list[Scenario]:
    """A hand-written suite: `suite`, then `scenarios` with persona_uuid, situation, brief, behavior, expect."""
    doc = yaml.safe_load(path.read_text())
    items = doc["scenarios"]
    personas = personas_by_uuid([s["persona_uuid"] for s in items])
    out = []
    for s in items:
        Brief.model_validate(_map_dates(s["brief"], lambda v: _absolute(v, market_date())))  # fail fast on typos
        out.append(
            Scenario(
                scenario_id=s["id"],
                suite=doc["suite"],
                persona=personas[s["persona_uuid"]],
                situation=Situation(**s["situation"]),
                brief=s["brief"],
                expect=Expect(**s["expect"]),
                behavior=s.get("behavior", "").strip(),
                source=f"yaml:{path.name}",
            )
        )
    return out


# ------------------------------------------------------------------------------------ storage


def save(scenarios: list[Scenario]) -> int:
    rows = [
        {
            "scenario_id": s.scenario_id,
            "suite": s.suite,
            "persona_uuid": s.persona["uuid"],
            "persona_json": json.dumps(s.persona, ensure_ascii=False, default=str),
            "situation_json": json.dumps(asdict(s.situation), ensure_ascii=False),
            "brief_json": json.dumps(s.brief, ensure_ascii=False),
            "behavior": s.behavior,
            "expect_json": json.dumps(asdict(s.expect), ensure_ascii=False),
            "source": s.source,
            "created_at": s.created_at,
        }
        for s in scenarios
    ]
    return append(catalog(), QA_SCENARIOS, rows)


def load(suites: list[str], ids: list[str] | None = None) -> list[Scenario]:
    """The latest version of each scenario in `suites` ("all" for every suite)."""
    table = ensure(catalog(), QA_SCENARIOS)
    scan = table.scan() if "all" in suites else table.scan(row_filter=In("suite", suites))
    rows = scan.to_arrow().to_pylist()
    latest: dict[str, dict[str, Any]] = {}
    for r in sorted(rows, key=lambda r: r["created_at"]):
        latest[r["scenario_id"]] = r
    out = [
        Scenario(
            scenario_id=r["scenario_id"],
            suite=r["suite"],
            persona=json.loads(r["persona_json"]),
            situation=Situation(**json.loads(r["situation_json"])),
            brief=json.loads(r["brief_json"]),
            expect=Expect(**json.loads(r["expect_json"])),
            behavior=r["behavior"] or "",
            source=r["source"] or "",
            created_at=r["created_at"],
        )
        for r in latest.values()
        if not ids or r["scenario_id"] in ids
    ]
    return sorted(out, key=lambda s: s.scenario_id)

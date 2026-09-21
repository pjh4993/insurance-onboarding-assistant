"""A QA run: every (scenario, repeat) conversation, checked and registered in the lakehouse."""

from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qa.checks import FAIL, run_checks
from qa.harness import BACKEND, harness
from qa.llm import AGENT_MODEL, CUSTOMER_MODEL
from qa.scenario import Scenario, market_date
from registry.catalog import catalog
from registry.tables import CONVERSATIONS, LLM_CALLS, QA_CHECKS, QA_RUNS, TURNS, append


def git_state() -> tuple[str, bool]:
    """HEAD of the checkout whose backend is under test, and whether it has uncommitted changes."""
    repo = BACKEND.parent
    sha = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True).stdout
    return sha, bool(dirty.strip())


async def execute(
    scenarios: list[Scenario], repeat: int, concurrency: int, run_id: str
) -> list[tuple[dict[str, Any], list[dict[str, str]]]]:
    today = market_date()
    limit = asyncio.Semaphore(concurrency)
    async with harness(scenarios, today) as h:

        async def one(s: Scenario, i: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
            async with limit:
                trace = await h.converse(s, run_id, i)
            checks = run_checks(trace)
            failed = [f"{c['check']}({c['detail']})" for c in checks if c["status"] == FAIL]
            print(f"  {s.scenario_id:28} #{i}  {'FAIL ' + '; '.join(failed) if failed else 'ok'}", flush=True)
            return trace, checks

        return await asyncio.gather(*(one(s, i) for s in scenarios for i in range(repeat)))


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def register(results: list[tuple[dict[str, Any], list[dict[str, str]]]], run: dict[str, Any]) -> None:
    conversations, turns, calls, checks = [], [], [], []
    for t, cs in results:
        run_calls = [c for turn in t.get("turns", []) for c in turn["llm_calls"]]
        final, sit = t.get("final", {}), t["situation"]
        conversations.append(
            {
                "trace_id": t["trace_id"],
                "run_id": t["run_id"],
                "sample_id": None,
                "position": None,
                "persona_uuid": t["persona"]["uuid"],
                "situation_identity": sit["identity"],
                "situation_need": sit["need"],
                "situation_decision": sit["decision"],
                "situation_note": sit["note"],
                "expected_status": t["expect"]["status"],
                "final_status": final.get("status"),
                "final_stage": final.get("stage"),
                "final_waiting_for": final.get("waiting_for"),
                "matches_expected": final.get("status") == t["expect"]["status"],
                "agent_model": t["models"]["agent"],
                "customer_model": t["models"]["customer"],
                "session_id": t.get("session_id"),
                "n_turns": len(t.get("turns", [])),
                "n_llm_calls": len(run_calls),
                "prompt_tokens": sum((c.get("usage") or {}).get("prompt_tokens") or 0 for c in run_calls),
                "completion_tokens": sum((c.get("usage") or {}).get("completion_tokens") or 0 for c in run_calls),
                "duration_s": t["duration_s"],
                "error": t.get("error"),
                "brief_json": _json(t["brief"]),
                "customer_record_json": _json(t["customer_record"]),
                "messages_json": _json(t.get("messages")),
                "entities_json": _json(t.get("entities")),
                "created_at": t["created_at"],
                "suite": t["suite"],
                "scenario_id": t["scenario_id"],
                "repeat_idx": t["repeat_idx"],
                "git_sha": run["git_sha"],
                "handoff_reason": final.get("handoff_reason"),
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
                    "customer_s": (turn["customer"] or {}).get("latency_s"),
                    "agent_s": turn.get("agent_s"),
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
        checks += [
            {
                "run_id": t["run_id"],
                "trace_id": t["trace_id"],
                "scenario_id": t["scenario_id"],
                "repeat_idx": t["repeat_idx"],
                "check_name": c["check"],
                "status": c["status"],
                "detail": c["detail"],
            }
            for c in cs
        ]
    cat = catalog()
    for table, rows in ((CONVERSATIONS, conversations), (TURNS, turns), (LLM_CALLS, calls), (QA_CHECKS, checks)):
        append(cat, table, rows)
    append(cat, QA_RUNS, [run])


def run(
    scenarios: list[Scenario],
    *,
    repeat: int,
    concurrency: int,
    suites: list[str],
    note: str = "",
    json_dir: Path | None = None,
) -> str:
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    sha, dirty = git_state()
    print(f"run {run_id}: {len(scenarios)} scenarios x {repeat} at {sha[:8]}{' (dirty)' if dirty else ''}")
    started = datetime.now(UTC)
    results = asyncio.run(execute(scenarios, repeat, concurrency, run_id))
    meta = {
        "run_id": run_id,
        "suites": ",".join(suites),
        "scenario_ids": ",".join(s.scenario_id for s in scenarios),
        "repeat": repeat,
        "git_sha": sha,
        "git_dirty": dirty,
        "agent_model": AGENT_MODEL,
        "customer_model": CUSTOMER_MODEL,
        "note": note,
        "started_at": started,
        "finished_at": datetime.now(UTC),
    }
    if json_dir:
        out = json_dir / run_id
        out.mkdir(parents=True, exist_ok=True)
        for t, cs in results:
            name = f"{t['scenario_id']}.{t['repeat_idx']}.json"
            (out / name).write_text(json.dumps({**t, "checks": cs}, ensure_ascii=False, indent=2, default=str))
    register(results, meta)
    return run_id

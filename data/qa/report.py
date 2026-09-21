"""Reading runs back: the pass-rate report (optionally against a baseline run), recent runs, and a trace's
transcript with the agent's extractions."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from pyiceberg.expressions import EqualTo

from qa.checks import CHECKS, FAIL, PASS
from registry.catalog import catalog
from registry.tables import CONVERSATIONS, LLM_CALLS, QA_CHECKS, QA_RUNS, TURNS, ensure


def timing(run_id: str) -> str:
    """Where a run's time went: wall clock vs the conversations it ran side by side."""
    run = _rows(QA_RUNS, run_id=run_id)
    conv = _rows(CONVERSATIONS, run_id=run_id)
    turns = _rows(TURNS, run_id=run_id)
    if not run or not conv:
        return ""
    wall = (run[0]["finished_at"] - run[0]["started_at"]).total_seconds()
    total = sum(c["duration_s"] or 0 for c in conv)
    slowest = max(conv, key=lambda c: c["duration_s"] or 0)
    customer = sum(t.get("customer_s") or 0 for t in turns)
    agent = sum(t.get("agent_s") or 0 for t in turns)
    return (
        f"time: wall {wall:.0f}s, {len(conv)} conversations summing {total:.0f}s ({total / wall:.1f}x parallel); "
        f"customer model {customer:.0f}s, agent {agent:.0f}s; slowest {slowest['scenario_id']} "
        f"#{slowest['repeat_idx']} {slowest['duration_s']:.0f}s / {slowest['n_turns']} turns"
    )


def _rows(table, **eq: str) -> list[dict[str, Any]]:
    (key, value), *_ = eq.items()
    return ensure(catalog(), table).scan(row_filter=EqualTo(key, value)).to_arrow().to_pylist()


def rates(run_id: str) -> dict[tuple[str, str], tuple[int, int, list[str]]]:
    """(scenario, check) -> (passes, applicable runs, failure details)."""
    agg: dict[tuple[str, str], list[Any]] = defaultdict(lambda: [0, 0, []])
    for r in _rows(QA_CHECKS, run_id=run_id):
        a = agg[(r["scenario_id"], r["check_name"])]
        if r["status"] == PASS:
            a[0] += 1
            a[1] += 1
        elif r["status"] == FAIL:
            a[1] += 1
            a[2].append(f"#{r['repeat_idx']} {r['detail']}")
    return {k: (v[0], v[1], v[2]) for k, v in agg.items()}


def _cell(passed: int, total: int) -> str:
    return "  -  " if total == 0 else f"{passed}/{total}"


def report(run_id: str, baseline: str | None = None, details: bool = True) -> None:
    cur = rates(run_id)
    base = rates(baseline) if baseline else {}
    scenarios = sorted({s for s, _ in cur})
    checks = [c for c in CHECKS if any((s, c) in cur for s in scenarios)]
    width = max(len(s) for s in scenarios) if scenarios else 10
    print(f"run {run_id}" + (f"  vs baseline {baseline}" if baseline else ""))
    print(" " * width + "  " + " ".join(f"{c[:11]:>11}" for c in checks))
    for s in scenarios:
        cells = []
        for c in checks:
            p, n, _ = cur.get((s, c), (0, 0, []))
            cell = _cell(p, n)
            if baseline and (s, c) in base:
                bp, bn, _ = base[(s, c)]
                if bn and n and p / n != bp / bn:
                    cell += "↑" if p / n > bp / bn else "↓"
            cells.append(f"{cell:>11}")
        print(f"{s:<{width}}  " + " ".join(cells))
    total_p = sum(p for p, _, _ in cur.values())
    total_n = sum(n for _, n, _ in cur.values())
    print(f"\n{total_p}/{total_n} applicable checks passed")
    print(timing(run_id))
    if baseline:
        bp, bn = sum(p for p, _, _ in base.values()), sum(n for _, n, _ in base.values())
        print(f"baseline {bp}/{bn}")
    if details:
        failures = [(s, c, d) for (s, c), (_, _, ds) in sorted(cur.items()) for d in ds]
        if failures:
            print("\nfailures:")
            for s, c, d in failures:
                print(f"  {s} {c}: {d}")


def runs(limit: int = 10) -> None:
    rows = ensure(catalog(), QA_RUNS).scan().to_arrow().to_pylist()
    for r in sorted(rows, key=lambda r: r["started_at"], reverse=True)[:limit]:
        dirty = "*" if r["git_dirty"] else ""
        print(
            f"{r['run_id']}  {r['git_sha'][:8]}{dirty:1}  {r['suites']:<20} x{r['repeat']}  "
            f"{r['agent_model']}  {r['note'] or ''}"
        )


def show(run_id: str, scenario_id: str, repeat: int = 0) -> None:
    conv = [
        c for c in _rows(CONVERSATIONS, run_id=run_id) if c["scenario_id"] == scenario_id and c["repeat_idx"] == repeat
    ]
    if not conv:
        raise SystemExit(f"no trace for {scenario_id} #{repeat} in {run_id}")
    c = conv[0]
    trace_id = c["trace_id"]
    turns = sorted((t for t in _rows(TURNS, run_id=run_id) if t["trace_id"] == trace_id), key=lambda t: t["step"])
    calls = defaultdict(list)
    for call in _rows(LLM_CALLS, run_id=run_id):
        if call["trace_id"] == trace_id:
            calls[call["step"]].append(call)
    checks = [r for r in _rows(QA_CHECKS, run_id=run_id) if r["trace_id"] == trace_id]
    print(f"{scenario_id} #{repeat}  trace {trace_id}  -> {c['final_status']} ({c['handoff_reason'] or '-'})")
    print(f"brief: {c['brief_json']}\n")
    for t in turns:
        print(f"[{t['step']}] {t['waiting_for']}")
        print(f"    agent: {(t['agent_message'] or '').strip()}")
        print(f"    customer: {t['customer_text'] or t['input_json']}")
        for call in sorted(calls[t["step"]], key=lambda x: x["seq"]):
            print(f"    {call['node']} -> {json.dumps(json.loads(call['output_json']), ensure_ascii=False)}")
    tail = [m for m in json.loads(c["messages_json"] or "[]")][-2:]
    for m in tail:
        print(f"    ({m['role']}) {m['text']}")
    print("\nchecks:")
    for r in checks:
        print(f"  {r['status']:4} {r['check_name']:14} {r['detail']}")

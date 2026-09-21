"""The agent loop the operator console draws is read from the flow code: check it against what the code declares."""

from __future__ import annotations

from onboarding_agent.build import ALL_NODES
from onboarding_agent.flows import DOMAINS
from onboarding_agent.flows.outline import END, agent_outline


def test_every_declared_text_is_read_by_some_node():
    outline = agent_outline()
    read = {ref for node in outline["nodes"] for ref in node["reads"]}
    declared = {f"copy:{d.name}.{key}" for d in DOMAINS for key in d.texts.copy}
    declared |= {f"llm:{node}.{part}" for d in DOMAINS for node, parts in d.texts.llm.items() for part in parts}
    assert declared - read == set(), "declared in a TextSpec but no node reads it"
    assert {r for r in read if r.startswith(("copy:", "llm:"))} - declared == set(), "read but not declared"
    assert {"system_prompt", "labels", "billing_periods"} <= read


def test_nodes_and_kinds():
    nodes = {n["id"]: n for n in agent_outline()["nodes"]}
    assert set(nodes) == set(ALL_NODES)
    assert {n for n, v in nodes.items() if v["kind"] == "llm"} == {
        "understand_intake",
        "assess_needs",
        "explain_recommendation",
        "collect_parties",
        "collect_answers",
        "summarize_application",
    }
    assert {n for n, v in nodes.items() if v["kind"] == "wait"} == {
        "ask_customer",
        "await_decision",
        "confirm_summary",
        "await_agent",
    }
    # the system prompt reaches exactly the LLM nodes
    assert {n for n, v in nodes.items() if "system_prompt" in v["reads"]} == {
        n for n, v in nodes.items() if v["kind"] == "llm"
    }


def test_edges_follow_the_routers_and_registries():
    edges = {(e["source"], e["target"]) for e in agent_outline()["edges"]}
    for edge in [
        ("greet", "ask_customer"),
        ("ask_customer", "understand_intake"),
        ("understand_intake", "collect_identity"),
        ("collect_identity", "ask_customer"),
        ("ask_customer", "collect_identity"),
        ("collect_identity", "verify_identity"),
        ("verify_identity", "fetch_purchases"),
        ("check_otp", "check_document"),
        ("check_document", "human_handoff"),
        ("assess_needs", "check_eligibility"),
        ("await_decision", "assess_needs"),
        ("await_decision", "open_application"),
        ("confirm_summary", "submit_application"),
        ("submit_application", END),
        ("human_handoff", "await_agent"),
        ("await_agent", "fetch_purchases"),
        ("await_agent", "collect_identity"),
        ("await_agent", "collect_answers"),
    ]:
        assert edge in edges, edge
    # every processing node can hand off, and every node but the end has somewhere to go
    sources = {s for s, _ in edges}
    assert sources == set(ALL_NODES)
    assert all((n, "human_handoff") in edges for n in ALL_NODES if n not in ("human_handoff", "await_agent"))

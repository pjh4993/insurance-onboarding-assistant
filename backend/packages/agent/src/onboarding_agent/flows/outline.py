"""The agent loop as the operator console draws it: its nodes and edges, and which config each node reads.

Read from the flow code itself (its syntax tree), so it cannot drift from what runs:
- a node reads `copy:<flow>.<key>` where it calls `.text(locale, "<flow>.<key>")`, `llm:<node>.<part>` where it
  calls `.prompt("<node>", "<part>")`, `system_prompt` through `._system(...)`, `labels` through
  `.field_list(...)` and `billing_periods` through `price_label(...)`. Form copy is looked up by topic, so a
  `.text(locale, f"<flow>.form.{topic}...")` reads every declared key under that prefix, and `form_spec(...)` /
  `render(...)` for a flow read its `form.*`, `field.*` and `option.*` keys; including what the helper functions it
  calls read, and what a domain's input recorders (run by ask_customer) and handoff resolvers (run by
  await_agent) read.
- a node's edges are the node names its router can return, plus the targets and resume points the domains
  register for ask_customer and await_agent.

Model profiles are per bundle, so which nodes a profile drives comes from the bundle (`Bundle.model(node)`)."""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable, Iterable
from functools import cache
from types import ModuleType
from typing import Any

from onboarding_agent.flows import DOMAINS, application, conversation, handoff, identity, profiling, recommendation
from onboarding_agent.flows import base as flow_base

MODULES: tuple[ModuleType, ...] = (flow_base, conversation, identity, profiling, recommendation, application, handoff)
END = "__end__"
PREFIX = "copy-prefix:"  # an internal marker: every declared copy key under the prefix


def _refs_in(fn: ast.AST) -> tuple[set[str], set[str], bool]:
    """(config refs read directly, names of functions called, whether it interrupts) for one function body."""
    refs: set[str] = set()
    calls: set[str] = set()
    interrupts = False
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
        consts = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if name == "text" and consts:
            refs.add(f"copy:{consts[0]}")
        elif name == "text" and len(node.args) > 1 and isinstance(node.args[1], ast.JoinedStr):
            head = node.args[1].values[0] if node.args[1].values else None
            if isinstance(head, ast.Constant) and isinstance(head.value, str) and "." in head.value:
                refs.add(f"{PREFIX}{head.value}")  # a key built from a topic: expanded in agent_outline
        elif name in ("form_spec", "render") and consts:
            refs |= {f"{PREFIX}{consts[0]}.{part}." for part in ("form", "field", "option")}
        elif name == "prompt" and len(consts) >= 2:
            refs.add(f"llm:{consts[0]}.{consts[1]}")
        elif name == "_system":
            refs.add("system_prompt")
        elif name == "field_list":
            refs.add("labels")
        elif name == "price_label":
            refs.add("billing_periods")
        elif name == "interrupt":
            interrupts = True
        if name:
            calls.add(name)
    return refs, calls, interrupts


@cache
def _functions() -> dict[str, tuple[set[str], set[str], bool]]:
    """Every function and method of the flow modules by name: (refs, calls, interrupts)."""
    table: dict[str, tuple[set[str], set[str], bool]] = {}
    for module in MODULES:
        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                refs, calls, interrupts = _refs_in(node)
                if node.name in table:  # the same name in two modules: merge, conservatively
                    old = table[node.name]
                    table[node.name] = (old[0] | refs, old[1] | calls, old[2] or interrupts)
                else:
                    table[node.name] = (refs, calls, interrupts)
    return table


def _reach(names: Iterable[str]) -> tuple[set[str], bool]:
    """Refs read by functions `names`, following calls into other flow functions; and whether any interrupts."""
    table = _functions()
    seen: set[str] = set()
    refs: set[str] = set()
    interrupts = False
    stack = [n for n in names if n in table]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        fn_refs, calls, fn_interrupts = table[name]
        refs |= fn_refs
        interrupts = interrupts or fn_interrupts
        stack += [c for c in calls if c in table and c not in seen]
    return refs, interrupts


def _returns(fn: Callable[..., Any], nodes: set[str]) -> set[str]:
    """Node names (and END) a router can return."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    out: set[str] = set()
    for ret in (n for n in ast.walk(tree) if isinstance(n, ast.Return) and n.value is not None):
        for node in ast.walk(ret.value):
            if isinstance(node, ast.Constant) and node.value in nodes:
                out.add(node.value)
            elif isinstance(node, ast.Name) and node.id == "HANDOFF":
                out.add("human_handoff")
            elif isinstance(node, ast.Name) and node.id == "END":
                out.add(END)
    return out


@cache
def agent_outline() -> dict[str, Any]:
    """{"nodes": [{id, domain, kind, reads}], "edges": [{source, target, kind}], "entry": "greet"}."""
    nodes = {name for d in DOMAINS for name in d.edges}
    llm_nodes = {node for d in DOMAINS for node in d.texts.llm}
    recorders = [k.record.__name__ for d in DOMAINS for k in d.inputs.values() if k.record]
    resolvers = [k.resolve.__name__ for d in DOMAINS for k in d.handoffs.values() if k.resolve]
    resolvers += ["resolve_error"]

    declared_copy = {f"copy:{d.name}.{key}" for d in DOMAINS for key in d.texts.copy}

    def expand(refs: set[str]) -> set[str]:
        prefixes = {r[len(PREFIX) :] for r in refs if r.startswith(PREFIX)}
        found = {c for c in declared_copy for p in prefixes if c.startswith(f"copy:{p}")}
        return {r for r in refs if not r.startswith(PREFIX)} | found

    out_nodes = []
    for d in DOMAINS:
        for name in d.edges:
            extra = recorders if name == "ask_customer" else resolvers if name == "await_agent" else []
            refs, interrupts = _reach([name, *extra])
            refs = expand(refs)
            kind = "llm" if name in llm_nodes else "wait" if interrupts else "code"
            out_nodes.append({"id": name, "domain": d.name, "kind": kind, "reads": sorted(refs)})

    edges: set[tuple[str, str, str]] = set()
    for d in DOMAINS:
        for name, router in d.edges.items():
            for target in _returns(router, nodes):
                edges.add((name, target, "route"))
    for d in DOMAINS:
        for kind in d.inputs.values():
            edges.add(("ask_customer", kind.target, "input"))
        for handoff_kind in d.handoffs.values():
            for target in _returns(handoff_kind.resume, nodes):
                edges.add(("await_agent", target, "resume"))
    edges.add(("await_agent", END, "route"))  # an agent may end the session
    return {
        "entry": "greet",
        "nodes": out_nodes,
        "edges": [{"source": s, "target": t, "kind": k} for s, t, k in sorted(edges)],
    }

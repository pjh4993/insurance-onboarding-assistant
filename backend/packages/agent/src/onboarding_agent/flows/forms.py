"""Small forms: the `form` a prompt carries while the graph waits for IDENTITY_INFO or NEEDS (CONTRACTS.md §3,
`FormSpec`). A domain declares its topics as `FormField`s and a `FormBuilder` for its kind of answer
(`InputKind.form`); the prompt is built from the state when it is read, so it follows the session's
current language and never needs PII in the checkpoint.

Every label is copy in the domain's flow file of the config bundle:

    form.<topic>.title, form.<topic>.reason, form.<topic>.lead
    field.<name>, and field.<name>.placeholder when the field has one
    option.<name>.<value> for select and multiselect options (boolean fields: .true / .false, used in the
    transcript line a submitted form becomes)"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from onboarding_agent.flows.base import Flow

KINDS = frozenset({"text", "email", "tel", "date", "number", "select", "multiselect", "boolean"})
EMPTY = (None, "", [])


@dataclass(frozen=True)
class FormField:
    name: str  # the key the answer comes back under (`{topic, fields: {name: value}}`)
    kind: str
    options: tuple[str, ...] = ()  # select / multiselect values
    placeholder: bool = False

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"form field {self.name}: unknown kind {self.kind!r}")

    def copy_keys(self) -> set[str]:
        keys = {f"field.{self.name}"}
        if self.placeholder:
            keys.add(f"field.{self.name}.placeholder")
        values = ("true", "false") if self.kind == "boolean" else self.options
        return keys | {f"option.{self.name}.{v}" for v in values}


def form_copy(topics: Mapping[str, Sequence[FormField]]) -> dict[str, frozenset[str]]:
    """The copy keys `topics` read, for the flow's `TextSpec` (none takes a placeholder)."""
    keys: dict[str, frozenset[str]] = {}
    for topic, fields in topics.items():
        for part in ("title", "reason", "lead"):
            keys[f"form.{topic}.{part}"] = frozenset()
        for f in fields:
            keys.update(dict.fromkeys(f.copy_keys(), frozenset()))
    return keys


def form_spec(
    flow: Flow,
    lang: str,
    flow_name: str,
    topic: str,
    fields: Sequence[tuple[FormField, bool, Any]],
    *,
    allow_text: bool,
) -> dict[str, Any]:
    """A FormSpec for `topic` from (field, required, known value) triples."""

    def t(key: str) -> str:
        return flow.text(lang, f"{flow_name}.{key}")

    items = []
    for f, required, value in fields:
        item: dict[str, Any] = {"name": f.name, "label": t(f"field.{f.name}"), "kind": f.kind, "required": required}
        if f.options:
            item["options"] = [{"value": v, "label": t(f"option.{f.name}.{v}")} for v in f.options]
        if f.placeholder:
            item["placeholder"] = t(f"field.{f.name}.placeholder")
        if value not in EMPTY:
            item["value"] = value
        items.append(item)
    return {
        "topic": topic,
        "title": t(f"form.{topic}.title"),
        "reason": t(f"form.{topic}.reason"),
        "fields": items,
        "allow_text": allow_text,
    }


def render(
    flow: Flow,
    lang: str,
    flow_name: str,
    fields: Sequence[FormField],
    values: Mapping[str, Any],
    shown: Mapping[str, str] | None = None,
) -> str:
    """A submitted form as one transcript line, `Label: value · Label: value`. `shown` overrides how a value
    reads (a masked document number, an amount with its currency)."""

    def t(key: str) -> str:
        return flow.text(lang, f"{flow_name}.{key}")

    parts = []
    for f in fields:
        value = values.get(f.name)
        if value in EMPTY:
            continue
        if shown and f.name in shown:
            text = shown[f.name]
        elif f.kind == "boolean":
            text = t(f"option.{f.name}.{'true' if value else 'false'}")
        else:
            items = value if isinstance(value, list) else [value]
            text = ", ".join(t(f"option.{f.name}.{v}") if v in f.options else str(v) for v in items)
        parts.append(f"{t(f'field.{f.name}')}: {text}")
    return " · ".join(parts)

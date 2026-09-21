"""Every lakehouse table: its identifier, Arrow schema and identity partition columns.

Nested values (briefs, entities, LLM inputs/outputs) are stored as JSON strings so a table's schema
stays stable while the agent's shapes evolve."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError
from pyiceberg.table import Table

TS = pa.timestamp("us", tz="UTC")

PERSONA_TEXT_FIELDS = [
    "professional_persona", "sports_persona", "arts_persona", "travel_persona", "culinary_persona",
    "family_persona", "persona", "cultural_background", "skills_and_expertise", "skills_and_expertise_list",
    "hobbies_and_interests", "hobbies_and_interests_list", "career_goals_and_ambitions",
]  # fmt: skip
PERSONA_ATTR_FIELDS = [
    "sex", "marital_status", "military_status", "family_type", "housing_type", "education_level",
    "bachelors_field", "occupation", "district", "province", "country",
]  # fmt: skip


@dataclass(frozen=True)
class TableDef:
    identifier: str
    schema: pa.Schema
    partition_by: tuple[str, ...] = ()
    doc: str = ""


NEMOTRON_KO = TableDef(
    "personas.nemotron_ko",
    pa.schema(
        [pa.field("uuid", pa.string(), nullable=False)]
        + [pa.field(f, pa.string()) for f in PERSONA_TEXT_FIELDS]
        + [pa.field("age", pa.int32())]
        + [pa.field(f, pa.string()) for f in PERSONA_ATTR_FIELDS]
        + [pa.field("source_file", pa.string()), pa.field("ingested_at", TS)]
    ),
    doc="Rows of nvidia/Nemotron-Personas-Korea (CC BY 4.0), one per persona",
)

SAMPLES = TableDef(
    "personas.samples",
    pa.schema(
        [
            pa.field("sample_id", pa.string(), nullable=False),
            pa.field("persona_uuid", pa.string(), nullable=False),
            pa.field("position", pa.int32(), nullable=False),
            pa.field("stratum", pa.string()),
            pa.field("strategy", pa.string()),
            pa.field("seed", pa.int64()),
            pa.field("created_at", TS),
        ]
    ),
    partition_by=("sample_id",),
    doc="Named persona samples; `position` orders a sample and assigns its situations",
)

CONVERSATIONS = TableDef(
    "traces.conversations",
    pa.schema(
        [
            pa.field("trace_id", pa.string(), nullable=False),
            pa.field("run_id", pa.string(), nullable=False),
            pa.field("sample_id", pa.string()),
            pa.field("position", pa.int32()),
            pa.field("persona_uuid", pa.string()),
            pa.field("situation_identity", pa.string()),
            pa.field("situation_need", pa.string()),
            pa.field("situation_decision", pa.string()),
            pa.field("situation_note", pa.string()),
            pa.field("expected_status", pa.string()),
            pa.field("final_status", pa.string()),
            pa.field("final_stage", pa.string()),
            pa.field("final_waiting_for", pa.string()),
            pa.field("matches_expected", pa.bool_()),
            pa.field("agent_model", pa.string()),
            pa.field("customer_model", pa.string()),
            pa.field("session_id", pa.string()),
            pa.field("n_turns", pa.int32()),
            pa.field("n_llm_calls", pa.int32()),
            pa.field("prompt_tokens", pa.int64()),
            pa.field("completion_tokens", pa.int64()),
            pa.field("duration_s", pa.float64()),
            pa.field("error", pa.string()),
            pa.field("brief_json", pa.string()),
            pa.field("customer_record_json", pa.string()),
            pa.field("messages_json", pa.string()),
            pa.field("entities_json", pa.string()),
            pa.field("created_at", TS),
        ]
    ),
    partition_by=("run_id",),
    doc="One simulated onboarding conversation per persona and run",
)

TURNS = TableDef(
    "traces.turns",
    pa.schema(
        [
            pa.field("trace_id", pa.string(), nullable=False),
            pa.field("run_id", pa.string(), nullable=False),
            pa.field("step", pa.int32(), nullable=False),
            pa.field("waiting_for", pa.string()),
            pa.field("agent_message", pa.string()),
            pa.field("customer_text", pa.string()),
            pa.field("input_json", pa.string()),
            pa.field("options_json", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("stage_after", pa.string()),
            pa.field("status_after", pa.string()),
        ]
    ),
    partition_by=("run_id",),
    doc="Each customer input the graph waited for, with the agent prompt it answered",
)

LLM_CALLS = TableDef(
    "traces.llm_calls",
    pa.schema(
        [
            pa.field("trace_id", pa.string(), nullable=False),
            pa.field("run_id", pa.string(), nullable=False),
            pa.field("step", pa.int32(), nullable=False),
            pa.field("seq", pa.int32(), nullable=False),
            pa.field("node", pa.string()),
            pa.field("schema_name", pa.string()),
            pa.field("model", pa.string()),
            pa.field("input_json", pa.string()),
            pa.field("output_json", pa.string()),
            pa.field("latency_s", pa.float64()),
            pa.field("prompt_tokens", pa.int64()),
            pa.field("completion_tokens", pa.int64()),
        ]
    ),
    partition_by=("run_id",),
    doc="The agent's structured-output LLM calls made while handling each turn",
)

TABLES = [NEMOTRON_KO, SAMPLES, CONVERSATIONS, TURNS, LLM_CALLS]


def ensure(cat: Catalog, t: TableDef) -> Table:
    """Load the table, creating its namespace and the table (with its partition spec) if missing."""
    namespace = t.identifier.split(".")[0]
    with contextlib.suppress(NamespaceAlreadyExistsError):
        cat.create_namespace(namespace)
    if cat.table_exists(t.identifier):
        return cat.load_table(t.identifier)
    table = cat.create_table(t.identifier, schema=t.schema, properties={"comment": t.doc} if t.doc else {})
    if t.partition_by:
        with table.update_spec() as spec:
            for col in t.partition_by:
                spec.add_identity(col)
    return cat.load_table(t.identifier)


def append(cat: Catalog, t: TableDef, rows: list[dict] | pa.Table) -> int:
    data = rows if isinstance(rows, pa.Table) else pa.Table.from_pylist(rows, schema=t.schema)
    if data.num_rows:
        ensure(cat, t).append(data.select(t.schema.names).cast(t.schema))
    return data.num_rows

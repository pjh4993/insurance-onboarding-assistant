"""Every lakehouse table: its identifier, Arrow schema and identity partition columns.

Nested values (briefs, entities, LLM inputs/outputs) are stored as JSON strings so a table's schema
stays stable while the agent's shapes evolve."""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa
from pyiceberg.catalog import Catalog
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
    "onboarding_personas.nemotron_ko",
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
    "onboarding_personas.samples",
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
    "onboarding_traces.conversations",
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
            pa.field("suite", pa.string()),
            pa.field("scenario_id", pa.string()),
            pa.field("repeat_idx", pa.int32()),
            pa.field("git_sha", pa.string()),
            pa.field("handoff_reason", pa.string()),
        ]
    ),
    partition_by=("run_id",),
    doc="One simulated onboarding conversation per scenario, repeat and run",
)

TURNS = TableDef(
    "onboarding_traces.turns",
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
            pa.field("customer_s", pa.float64()),
            pa.field("agent_s", pa.float64()),
        ]
    ),
    partition_by=("run_id",),
    doc="Each customer input the graph waited for, with the agent prompt it answered",
)

LLM_CALLS = TableDef(
    "onboarding_traces.llm_calls",
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

QA_SCENARIOS = TableDef(
    "onboarding_qa.scenarios",
    pa.schema(
        [
            pa.field("scenario_id", pa.string(), nullable=False),
            pa.field("suite", pa.string(), nullable=False),
            pa.field("persona_uuid", pa.string()),
            pa.field("persona_json", pa.string()),
            pa.field("situation_json", pa.string()),
            pa.field("brief_json", pa.string()),
            pa.field("behavior", pa.string()),
            pa.field("expect_json", pa.string()),
            pa.field("source", pa.string()),
            pa.field("created_at", TS, nullable=False),
        ]
    ),
    partition_by=("suite",),
    doc="QA scenarios; the latest row per scenario_id is its current version",
)

QA_RUNS = TableDef(
    "onboarding_qa.runs",
    pa.schema(
        [
            pa.field("run_id", pa.string(), nullable=False),
            pa.field("suites", pa.string()),
            pa.field("scenario_ids", pa.string()),
            pa.field("repeat", pa.int32()),
            pa.field("git_sha", pa.string()),
            pa.field("git_dirty", pa.bool_()),
            pa.field("agent_model", pa.string()),
            pa.field("customer_model", pa.string()),
            pa.field("note", pa.string()),
            pa.field("started_at", TS),
            pa.field("finished_at", TS),
        ]
    ),
    doc="One QA run: which scenarios, how often, against which commit and models",
)

QA_CHECKS = TableDef(
    "onboarding_qa.checks",
    pa.schema(
        [
            pa.field("run_id", pa.string(), nullable=False),
            pa.field("trace_id", pa.string(), nullable=False),
            pa.field("scenario_id", pa.string(), nullable=False),
            pa.field("repeat_idx", pa.int32()),
            pa.field("check_name", pa.string(), nullable=False),
            pa.field("status", pa.string(), nullable=False),
            pa.field("detail", pa.string()),
        ]
    ),
    partition_by=("run_id",),
    doc="Each QA check's verdict on each trace (PASS, FAIL or SKIP)",
)

TABLES = [NEMOTRON_KO, SAMPLES, CONVERSATIONS, TURNS, LLM_CALLS, QA_SCENARIOS, QA_RUNS, QA_CHECKS]


def ensure(cat: Catalog, t: TableDef) -> Table:
    """Load the table, creating it (with its partition spec) if missing and adding any column the definition
    has gained. Namespaces are Glue databases managed by infra/bootstrap, so a missing one is an error here
    rather than created."""
    if cat.table_exists(t.identifier):
        table = cat.load_table(t.identifier)
        if set(t.schema.names) - {f.name for f in table.schema().fields}:
            with table.update_schema() as update:
                update.union_by_name(t.schema)
            table = cat.load_table(t.identifier)
        return table
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

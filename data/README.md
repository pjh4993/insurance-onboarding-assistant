# data

The data lakehouse and the pipelines that fill it: synthetic Korean personas, and onboarding
conversations simulated from them against the real agent graph.

```
data/
├── registry/          # the lakehouse: catalog + table definitions
│   ├── catalog.py     # Iceberg GlueCatalog; data and metadata in S3
│   └── tables.py      # every table's schema and partitioning
└── pipeline/
    ├── ingest_personas.py   # nvidia/Nemotron-Personas-Korea shards -> onboarding_personas.nemotron_ko
    ├── sample_personas.py   # stratified named sample -> onboarding_personas.samples
    ├── generate_traces.py   # sample -> simulated conversations -> onboarding_traces.*
    └── models.yaml          # OpenAI models per role and Chat Completions kwargs per model
```

## Setup

```bash
cd data && uv sync
docker compose up -d postgres   # generate_traces runs the agent on the compose Postgres
```

- **Warehouse:** `s3://onboarding-lakehouse-<account>/warehouse`.
- **Catalog:** AWS Glue. There is one database per namespace, `onboarding_personas` and `onboarding_traces`, so the tables can also be queried from Athena.
- **Where they come from:** the bucket and the Glue databases are both created in `infra/bootstrap`. Adding a namespace means adding it to `lakehouse_namespaces` there.
- **AWS access:** Glue and S3 are reached with the AWS profile `aws-jhpark`.
- **Env overrides:** see `registry/catalog.py` for `LAKEHOUSE_*`, and `pipeline/generate_traces.py` for `SIM_*`.
- **OpenAI:** `OPENAI_API_KEY` comes from the root `.envrc`.

## Run

```bash
uv run python -m registry                                    # create missing tables, show row counts
uv run python -m pipeline.ingest_personas --shards 0         # ~111k personas per shard
uv run python -m pipeline.sample_personas --sample-id strat10-s42 --n 10 --seed 42
uv run python -m pipeline.generate_traces --sample-id strat10-s42 --json-dir $GWT_ROOT/.data/lakehouse/runs
```

## Tables

| table | grain | partition |
|---|---|---|
| `onboarding_personas.nemotron_ko` | one persona (Nemotron-Personas-Korea row, CC BY 4.0) | — |
| `onboarding_personas.samples` | one persona in a named sample, with its `position` | `sample_id` |
| `onboarding_traces.conversations` | one simulated session: situation, expected vs final status, brief, messages, entities | `run_id` |
| `onboarding_traces.turns` | one customer input the graph waited for, with the agent prompt it answered | `run_id` |
| `onboarding_traces.llm_calls` | one structured-output call of the agent (node, input, output, tokens) | `run_id` |

## How a trace is made

`generate_traces` gives each persona a **situation** by its position in the sample.

- A situation combines three things:
  - the identity path: partner match, OTP, identity document, or both checks failing
  - the need: new phone, laptop, appliance, trip, or a phone too old to insure
  - the customer's decision: accept, change, or decline
- **Coverage:** the first ten positions cover every KR product and every graph branch.

Then OpenAI (`SIM_CUSTOMER_MODEL`) does three jobs:

1. It writes the persona's customer record and brief.
2. The record is seeded into the in-process partner/identity/contract fakes (`backend/tests/fakes.py`).
3. OpenAI plays the customer at every input the graph waits for.

The graph itself is the production graph.

- **Agent LLM:** the agent's LLM calls go to OpenAI (`SIM_AGENT_MODEL`) through the same function-calling structured output that production uses on Bedrock.
- **Implication:** the traces reflect the graph's flow and the customers' language, not Claude's extractions.

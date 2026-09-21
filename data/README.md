# data

The data lakehouse, the pipelines that fill it with synthetic Korean personas, and `qa`: the agent's QA
harness, which replays frozen persona scenarios against the real agent graph and checks every conversation.

```
data/
├── registry/          # the lakehouse: catalog + table definitions
│   ├── catalog.py     # Iceberg GlueCatalog; data and metadata in S3
│   └── tables.py      # every table's schema and partitioning (new columns are added on the next write)
├── pipeline/
│   ├── ingest_personas.py   # nvidia/Nemotron-Personas-Korea shards -> onboarding_personas.nemotron_ko
│   └── sample_personas.py   # stratified named sample -> onboarding_personas.samples
└── qa/
    ├── scenario.py    # scenarios: persona + situation + brief + behavior + expectation; freeze / load / store
    ├── harness.py     # the real graph and Runtime, fakes seeded per scenario, OpenAI as agent LLM and customer
    ├── checks.py      # deterministic checks over one conversation
    ├── runner.py      # a run: scenarios x repeats, checked, registered in the lakehouse
    ├── report.py      # pass rates vs a baseline run, timing, one conversation's transcript
    ├── models.yaml    # OpenAI models per role and Chat Completions kwargs per model and call kind
    └── suites/        # hand-written suites (regressions.yaml)
```

## Setup

```bash
cd data && uv sync
docker compose up -d postgres   # qa runs the agent on the compose Postgres (database onboarding_sim)
```

- **Warehouse:** `s3://onboarding-lakehouse-<account>/warehouse`.
- **Catalog:** AWS Glue. There is one database per namespace (`onboarding_personas`, `onboarding_traces`, `onboarding_qa`), so the tables can also be queried from Athena.
- **Where they come from:** the bucket and the Glue databases are both created in `infra/bootstrap`. Adding a namespace means adding it to `lakehouse_namespaces` there.
- **AWS access:** Glue and S3 are reached with the AWS profile `aws-jhpark`.
- **Env overrides:** see `registry/catalog.py` for `LAKEHOUSE_*`, and `qa/llm.py` and `qa/harness.py` for `SIM_*`.
- **OpenAI:** `OPENAI_API_KEY` comes from the root `.envrc`.

## Personas

```bash
uv run python -m registry                                    # create missing tables, show row counts
uv run python -m pipeline.ingest_personas --shards 0         # ~111k personas per shard
uv run python -m pipeline.sample_personas --sample-id strat10-s42 --n 10 --seed 42
```

## QA

```bash
uv run python -m qa scenarios freeze --sample-id strat10-s42 --suite smoke10   # briefs written once, then frozen
uv run python -m qa scenarios load qa/suites/regressions.yaml                 # a hand-written suite
uv run python -m qa scenarios list

uv run python -m qa run --suite regressions smoke10 --repeat 2 [--baseline RUN_ID] [--scenario ID ...]
uv run python -m qa report RUN_ID --baseline RUN_ID
uv run python -m qa runs
uv run python -m qa show RUN_ID SCENARIO_ID [--repeat N]
```

The loop:

1. Run the suites.
2. Read the failures in the report.
3. Use `qa show` to see where a conversation went wrong: every turn, the agent's extractions, the checks.
4. Fix the agent.
5. Run again with `--baseline` set to the earlier run. The arrows mark what changed.

A failure found in the wild becomes a scenario in `suites/regressions.yaml`, so it is checked from then on.

### Scenarios

A scenario is made of these parts:

- **Persona:** a row of `onboarding_personas.nemotron_ko`.
- **Situation:** the identity path (partner match, OTP, document, both checks failing), the need (phone, laptop, appliance, trip, or a phone too old to insure), and the decision (accept, change, decline).
- **Brief:** the facts the customer knows. It is the ground truth the checks compare the agent against.
- **Behavior:** an optional hint for how to talk, such as "give the price in 만 원".
- **Expectation:** the final status, the submitted product, a turn budget, and optionally phrases the agent must say.

Scenarios are stored in `onboarding_qa.scenarios`; the latest row per id wins. Dates are stored relative to the day (`today`, `today+29`) and resolved on the market's calendar, so a suite stays valid over time.

The harness replaces each brief's phone and email with values unique to the scenario, because the identity fakes look customers up by them.

### Checks

| check | fails when |
|---|---|
| `outcome` | the final status is not the expected one |
| `product` | the submitted product is not the expected one |
| `identity_path` | the customer verified another way than the scenario means (a harness check) |
| `needs_device` | the captured device's category, maker or price differs from the brief |
| `needs_trip` | the captured trip's destination or dates differ from the brief |
| `objectives` | cover was captured without its subject, such as device cover for a trip-only customer |
| `parties` | the insured or payer (name, date of birth) differs from the brief |
| `no_loop` | the same input was asked for more than 3 times in a row |
| `finished` | the conversation was still active at the step limit |
| `turn_budget` | the conversation took more turns than the scenario allows |
| `agent_says` | the agent never said a phrase the scenario requires (an explanation it owes the customer) |
| `no_error` | the harness crashed or the session went to an agent for an error |

### What is and is not real

- **Real:** the graph, the Runtime, the database and the config bundle's prompts and copy are the production ones.
- **Replaced:**
  - The partner, identity and contract systems are the in-process fakes (`backend/tests/fakes.py`).
  - The agent's LLM calls go to OpenAI (`SIM_AGENT_MODEL`) through the same function-calling structured output that production uses on Bedrock.
- **Implication:** a run measures the graph's flow and rules, and how well the prompts work on that model. It says nothing about Claude's extractions.

### Tables

| table | grain | partition |
|---|---|---|
| `onboarding_personas.nemotron_ko` | one persona (Nemotron-Personas-Korea row, CC BY 4.0) | — |
| `onboarding_personas.samples` | one persona in a named sample, with its `position` | `sample_id` |
| `onboarding_qa.scenarios` | one version of a scenario | `suite` |
| `onboarding_qa.runs` | one run: suites, repeats, git commit, models | — |
| `onboarding_qa.checks` | one check's verdict on one conversation | `run_id` |
| `onboarding_traces.conversations` | one conversation: scenario, final status, brief, messages, entities | `run_id` |
| `onboarding_traces.turns` | one input the graph waited for, with the agent prompt and timings | `run_id` |
| `onboarding_traces.llm_calls` | one structured-output call of the agent (node, input, output, tokens) | `run_id` |

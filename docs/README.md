# Documentation

The design documents for the onboarding assistant, grouped by what they answer. Start with the
[repository README](../README.md) for what is built and how to run it; this page is the map of the rest.

## Folders

| Folder | Answers | Documents |
|---|---|---|
| [`design/`](design/01-solution-architecture.md) | How the application works | Solution architecture, LangGraph design, state management, data model, observability |
| [`infra/`](infra/01-aws-architecture.md) | How it runs on AWS and gets there | AWS architecture, networking, Terraform, CI/CD |
| [`decisions/`](decisions/tradeoffs.md) | Why it is built this way, and what is left | Assumptions, tradeoffs, future improvements |
| [`guides/`](guides/demo.md) | How to try it and work on it | Demo walkthrough with the four seed customers, local development and tests |
| [`research/`](research/README.md) | What was found before designing | Insurance journey models, competitor onboarding flows, embedded insurance, product catalog research |

The numbers in `design/` and `infra/` are a reading order: each document assumes the ones before it.

## What is built

- The full four-stage LangGraph graph with wait nodes (`interrupt`), conditional edges after every node, retries,
  3-round loop guards and human handoff (`human_handoff` + `await_agent`), on `AsyncPostgresSaver` with
  compress-then-AES encryption.
- Eligibility, ranking and pricing in code over an eight-product KR/US catalog.
- Claude Sonnet 4.6 through `ChatBedrockConverse`, with a per-node model override setting.
- One mock service for partner, identity, contract admin and Bedrock, with seed customers A–D and fault injection.
- A frontend with the customer app and an agent console: session list, conversation, progress and application
  views, new session links, take over, answer as agent, handoff resolution.
- Terraform for both environments (develop has a domain, HTTPS and Cognito for the agent paths), a bootstrap
  stack for remote state, CI checks, a develop deploy and a prod promotion.
- Traces and structured logs to Grafana Cloud, and this documentation site at `/docs`.

What is known to be limited, and what was designed but not built, is in
[future improvements](decisions/future-improvements.md). How to run and test it locally is in
[guides/development.md](guides/development.md).

## Where each required item is

The brief asks for these documents. Each row points at the section that answers it.

| Required item | Where |
|---|---|
| Solution architecture | [design/01-solution-architecture.md](design/01-solution-architecture.md): system context, containers, inside the backend |
| LangGraph design | [design/02-langgraph-design.md](design/02-langgraph-design.md), with [§8](design/02-langgraph-design.md#8-how-the-six-langgraph-requirements-are-met) mapping the brief's six LangGraph requirements to the code |
| State management model | [design/03-state-management.md](design/03-state-management.md): state schema, checkpointing, idempotent writes, personal data |
| AWS architecture | [infra/01-aws-architecture.md](infra/01-aws-architecture.md) |
| Networking design | [infra/02-networking.md](infra/02-networking.md) |
| Terraform structure | [infra/03-terraform.md](infra/03-terraform.md) |
| CI/CD design | [infra/04-cicd.md](infra/04-cicd.md) |
| Assumptions | [decisions/assumptions.md](decisions/assumptions.md) |
| Tradeoffs | [decisions/tradeoffs.md](decisions/tradeoffs.md) |
| Future improvements | [decisions/future-improvements.md](decisions/future-improvements.md), starting with the [known limits](decisions/future-improvements.md#1-known-limits-of-what-is-built) of what is built |

Beyond the brief: [design/04-data-model.md](design/04-data-model.md) (entities and the product catalog),
[design/05-observability.md](design/05-observability.md) (traces and structured logs), and
[guides/demo.md](guides/demo.md). The API, SSE, mock and LLM contracts shared by the three services are in
[CONTRACTS.md](../CONTRACTS.md).

## Reading the site locally

The deployed site is public at [onboardassist.click/docs](https://onboardassist.click/docs/). `make docs` serves this folder, the README and the contracts as the same site locally;
`make docs-build` is the same build with `--strict`, which fails on a broken link. Both need only `uv`. On GitHub
the same pages read as they are, mermaid included.

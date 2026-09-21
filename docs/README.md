# Documentation

The design documents for the onboarding assistant, grouped by what they answer. Start with the
[repository README](../README.md) for what is built and how to run it; this page is the map of the rest.

## Folders

| Folder | Answers | Documents |
|---|---|---|
| [`design/`](design/01-solution-architecture.md) | How the application works | Solution architecture, LangGraph design, state management, data model, observability |
| [`infra/`](infra/01-aws-architecture.md) | How it runs on AWS and gets there | AWS architecture, networking, Terraform, CI/CD |
| [`decisions/`](decisions/tradeoffs.md) | Why it is built this way, and what is left | Assumptions, tradeoffs, future improvements |
| [`guides/`](guides/demo.md) | How to try it | Demo walkthrough with the four seed customers |
| [`research/`](research/README.md) | What was found before designing | Insurance journey models, competitor onboarding flows, embedded insurance, product catalog research |

The numbers in `design/` and `infra/` are a reading order: each document assumes the ones before it.

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

`make docs` serves this folder, the README and the contracts as one searchable site with the diagrams rendered;
`make docs-build` is the same build with `--strict`, which fails on a broken link. Both need only `uv`. On GitHub
the same pages read as they are, mermaid included.

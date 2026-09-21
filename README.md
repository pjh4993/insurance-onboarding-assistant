# AI Customer Onboarding & Policy Recommendation Assistant

An assistant that takes an insurance customer from identity verification to a submitted application, while
support agents watch every session and take over when needed. A LangGraph graph in the backend runs the four
stages: identity verification, customer profiling, policy recommendation and policy application. It pauses
whenever it needs a person and resumes from a Postgres checkpoint. Code decides eligibility, ranking and price;
Claude Sonnet 4.6 on Amazon Bedrock extracts values from free text and writes explanations and summaries. The
system is two separately deployed services (a Next.js frontend with a customer app and an agent console, and a
FastAPI + LangGraph backend) on ECS Fargate in ap-northeast-2, provisioned with Terraform and deployed with GitHub
Actions. External systems (partner, identity, contract admin, Bedrock) are one mock service locally and in develop.

## Architecture

```mermaid
flowchart LR
    customer(["Customer<br/>/s/{token}"])
    agent(["Support agent<br/>/agent"])

    subgraph fe["Frontend service: Next.js"]
        apps["Customer app + agent console"]
        relay["/api/* relay (incl. SSE)"]
    end

    subgraph be["Backend service: FastAPI + LangGraph"]
        lg["Onboarding graph<br/>code / LLM / wait nodes"]
    end

    pg[("PostgreSQL<br/>checkpoint · domain · catalog")]

    subgraph ext["External systems (mock in develop, real in prod)"]
        partner["Partner"]
        identity["Identity (OTP, document)"]
        contract["Contract admin"]
        bedrock["Bedrock: Claude Sonnet 4.6"]
    end

    customer & agent --> apps --> relay --> lg
    lg --> pg
    lg --> partner & identity & contract & bedrock
```

In AWS: ALB (HTTPS, Cognito for `/agent/*`) → frontend on ECS → backend on ECS via Service Connect → RDS
PostgreSQL; Bedrock and other AWS APIs through VPC endpoints. See [docs/aws-architecture.md](docs/aws-architecture.md).

## Quick start

Requires Docker with Compose.

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Agent console | http://localhost:13000/agent |
| Customer app | Click **New session** in the agent console and open the `/s/{token}` link it shows |
| Backend API | http://localhost:18000 (health: `/healthz`) |
| Mock external systems | http://localhost:18080 |
| PostgreSQL | `localhost:15432`, user / password / db `onboarding` |

No AWS account is needed locally: the backend's Bedrock client points to the mock. Walk through the four seed
customers in [docs/demo.md](docs/demo.md).

## Repository layout

```
backend/            FastAPI + LangGraph (Python 3.13, uv)
mock/               one FastAPI app: /partner /identity /contract /model/{id}/converse /_mock
frontend/           Next.js (App Router, TypeScript, pnpm): app/s, app/agent, app/api (relay)
infra/              Terraform: modules/{network,security,data,auth,edge,service,ci}, envs/{develop,prod}
.github/workflows/  CI and deploy workflows
contracts/          seed customers shared by the mock, backend tests and the demo
docs/               design documents
CONTRACTS.md        API, mock and LLM-shape contracts between the services
docker-compose.yml  local stack: postgres, mock, backend, frontend
```

## Running tests

```bash
# backend
cd backend && uv sync && uv run pytest

# mock
cd mock && uv sync && uv run pytest

# frontend
cd frontend && pnpm install && pnpm lint && pnpm build

# terraform
cd infra/envs/develop && terraform init -backend=false && terraform validate
```

Tests never call AWS. Graph tests use the mock's seed customers.

## Documents

| Document | Contents |
|---|---|
| [Solution architecture](docs/solution-architecture.md) | C4 context and containers, frontend-to-backend communication, inside the backend |
| [LangGraph design](docs/langgraph-design.md) | Four stages, nodes by type, graph and conditional edges, interrupt/resume, handoff, error handling, the six LangGraph requirements |
| [State management](docs/state-management.md) | State schema, reducers, routing signals, encrypted Postgres checkpoints, idempotent writes, personal data |
| [Data model](docs/data-model.md) | Entities, ER diagram, state transitions, product catalog seed |
| [AWS architecture](docs/aws-architecture.md) | Services and why, Bedrock, IAM, storage, environments |
| [Networking design](docs/networking.md) | VPC and subnets, endpoints and NAT, traffic flows, security groups, security boundaries, authentication |
| [Terraform structure](docs/terraform.md) | Modules, environments, state backend |
| [CI/CD design](docs/cicd.md) | GitHub Actions with OIDC, PR checks, develop deploy, prod promotion, smoke test |
| [Assumptions](docs/assumptions.md) | How we read the open parts of the brief |
| [Tradeoffs](docs/tradeoffs.md) | Infrastructure, LLM and checkpoint-store choices, with the evidence behind them |
| [Future improvements](docs/future-improvements.md) | Designed but deferred work |
| [Demo walkthrough](docs/demo.md) | Seed customers A–D and what each one shows |

## Scope and what is deferred

Built for this submission:

- The full four-stage LangGraph graph with wait nodes (`interrupt`), conditional edges, retries and human
  handoff, and `PostgresSaver` with compress-then-AES encryption.
- Eligibility, ranking and pricing in code over an eight-product KR/US catalog.
- Claude Sonnet 4.6 through `ChatBedrockConverse`, tested against the mock.
- One mock service for all four external systems, with seed customers A–D and fault injection.
- A frontend with the customer app and an agent console: session list, conversation, progress and application
  views, take over, answer as agent.
- Terraform for the develop environment and the prod composition; CI checks and a develop deploy workflow.

Designed, not built (details in [docs/future-improvements.md](docs/future-improvements.md)):

- Returning-customer linking and the customer history tab.
- ASSIST draft approval (AI messages held for agent review).
- The 30-day checkpoint cleanup job and checkpoint key rotation.
- Cognito login and HTTPS (waiting for a domain; a development header is used meanwhile).
- Applying prod and running the prod promotion.
- Moving extraction nodes to Claude Haiku 4.5, with an evaluation set to justify it.
- Tiered deductibles and age/state-based travel pricing in the catalog.

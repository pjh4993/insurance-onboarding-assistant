# Development

How to run the stack locally, where things live, and how to test them.

## 1. Run locally

Requires Docker with Compose.

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Agent console | http://localhost:13000/agent (development auth: you are `agent-demo`). In AWS it has its own host, `dev.agent.onboardassist.click`, behind Cognito |
| Customer app | http://localhost:13000: the landing page; pick KR or US and start. Agents can also create a `/s/{token}` link with **New session** in the console |
| Backend API | http://localhost:18000 (health: `/healthz`) |
| Mock external systems | http://localhost:18080 (faults: `/_mock/faults`, reset: `/_mock/reset`) |
| PostgreSQL | `localhost:15432`, user / password / db `onboarding` |

No AWS account is needed locally: the backend's Bedrock client points to the mock (`BEDROCK_ENDPOINT_URL`). The
backend migrates its schema and seeds the eight-product catalog when it starts. Walk through the four seed
customers in the [demo walkthrough](demo.md).

## 2. Repository layout

```
backend/            FastAPI + LangGraph (Python 3.13, uv)
mock/               one FastAPI app: /partner /identity /contract /model/{id}/converse /_mock
frontend/           Next.js 16 (App Router, TypeScript, pnpm): app/s, app/agent, app/api (relay), proxy.ts
infra/              Terraform: bootstrap/, modules/{network,security,data,auth,edge,service,ci}, envs/{develop,prod}
.github/workflows/  CI and deploy workflows
contracts/          seed customers shared by the mock, backend tests and the demo
docs/               design documents: design/, infra/, decisions/, guides/, research/ (index: docs/README.md)
CONTRACTS.md        API, mock and LLM-shape contracts between the services
docker-compose.yml  local stack: postgres, mock, backend, frontend
Makefile            make docs / make docs-build: the documents as a local site (mkdocs, via uvx)
docs-site/          nginx image serving that site at https://dev.docs.onboardassist.click
tools/diagrams/     generators for the SVG diagrams in docs/
```

## 3. Tests

```bash
# backend: DB-backed tests need the compose Postgres on localhost:15432 (they are skipped without it)
docker compose up -d postgres
cd backend && uv sync && uv run ruff check . && uv run pytest

# mock
cd mock && uv sync && uv run ruff check . && uv run pytest

# frontend
cd frontend && pnpm install && pnpm lint && pnpm typecheck && pnpm test && pnpm build

# terraform (no AWS access needed)
cd infra/envs/develop && terraform init -backend=false && terraform validate

# docs: strict site build, fails on a broken link
make docs-build
```

Tests never call AWS. Backend graph tests run the seed customers against in-process fakes of the external
systems and the LLM, built from the same seed file as the mock (`backend/tests/fixtures/seed-customers.json`).
CI runs all of the above on every push; see [CI/CD design](../infra/04-cicd.md).

## 4. Diagrams

Diagrams are SVG, drawn by the generators in `tools/diagrams/` (one per document group) with the helpers in
`tools/diagrams/svglib.py`. Edit the generator, then regenerate from the repo root:

```bash
uv run --no-project python tools/diagrams/solution_architecture.py
uv run --no-project python tools/diagrams/graph_state_data.py
uv run --no-project python tools/diagrams/infra.py
```

A document embeds a diagram as a plain image, `![…](assets/<name>.svg)`, so GitHub shows it; the docs site
inlines it so it follows the page's light or dark theme and opens full screen on click.

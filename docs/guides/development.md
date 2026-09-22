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
e2e/                browser tests (Playwright) and the exploratory QA checklist (agent-browser)
.claude/skills/     frontend-qa: the exploratory QA skill for Claude Code, driving agent-browser
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

# end to end (e2e/): once `make e2e-setup`, then
make e2e       # customer and agent flows in the browser against the compose stack
make e2e-dev   # read-only smoke checks and the page-load SLA of the develop hosts
```

### Browser tests (`e2e/`)

Playwright drives the real UI; labels come from `frontend/messages/*.json`, so copy changes do not break selectors.

| Project | Target | What it checks |
|---|---|---|
| `local` | compose stack, `E2E_BASE_URL` (default `http://localhost:13000`) | Landing (both languages, language switch saved on the session, product pre-fill, resume), the public landing's self-serve start, seed customers A–D end to end, and the agent console (create a link, take over a handoff and end it) |
| `dev-smoke` | `dev.app.`, `dev.agent.`, `dev.docs.onboardassist.click` | Landing renders, the frontend reaches the backend, the agent host redirects to Cognito, agent APIs are not reachable from the customer host, the docs are public. Read-only |
| `dev-perf` | same hosts | The page-load SLA below |

**Page-load SLA** (develop, desktop Chrome, cold cache, 75th percentile of 8 loads):

| Page | TTFB | LCP | CLS |
|---|---|---|---|
| Customer landing `/` | ≤ 600 ms | ≤ 1.5 s | ≤ 0.1 |
| Docs pages | ≤ 600 ms | ≤ 2.0 s | ≤ 0.1 |
| Agent login redirect | whole load, ending on Cognito's page, ≤ 2.0 s | | |

Measured from Seoul on 2026-09-22 the landing was at TTFB 176 ms and LCP 308 ms, the docs at LCP 0.8 s and CLS
0.07. The budgets leave room for CI runners outside Korea, so a miss means a real slowdown. TTFB is the server's
time, from the request to the first byte: DNS, TCP and TLS are left out, since from a US runner they alone take
several round trips. The docs load their web fonts with `display=optional`, so a late font never reflows the page.

**Exploratory QA** is not scripted: the `frontend-qa` skill (`.claude/skills/frontend-qa/SKILL.md`) has Claude Code
walk the app with [agent-browser](https://github.com/vercel-labs/agent-browser) through
`e2e/agent-qa/checklist.md` and write a report with screenshots to `e2e/qa-reports/`. Reproducible findings become
`local` tests.

Tests never call AWS. Backend graph tests run the seed customers against in-process fakes of the external
systems and the LLM, built from the same seed file as the mock (`backend/tests/fixtures/seed-customers.json`).
CI runs all of the above on every push, and the develop checks after every develop deploy and daily; see
[CI/CD design](../infra/04-cicd.md).

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

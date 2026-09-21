# Solution architecture

This document describes the system at the two outer levels of the C4 model: **context** (who uses it and
what it talks to) and **containers** (what is deployed and how the parts talk). The graph inside the backend
is in [langgraph-design.md](langgraph-design.md). The AWS mapping is in [aws-architecture.md](aws-architecture.md).

## 1. System context

```mermaid
flowchart LR
    customer(["Customer<br/>(no account, session link)"])
    agent(["Support agent<br/>(staff account)"])

    subgraph sys["Onboarding assistant"]
        app["Frontend + Backend"]
    end

    partner["Partner system<br/>purchase records"]
    identity["Identity provider<br/>OTP + ID document check"]
    contract["Contract admin system<br/>receives applications"]
    llm["Amazon Bedrock<br/>Claude Sonnet 4.6"]

    customer -- "onboards through chat" --> app
    agent -- "watches sessions, takes over" --> app
    app -- "match customer, read purchases<br/>(only with consent)" --> partner
    app -- "send / verify OTP, verify document" --> identity
    app -- "submit application" --> contract
    app -- "extract, explain, summarize" --> llm
```

Two kinds of people use the system.

| Person | How they get in | What they do |
|---|---|---|
| Customer | A session link `/s/{token}`. No account | Goes through the four onboarding stages in a chat |
| Support agent | Agent console `/agent`. Staff login: Cognito at the ALB in develop; a development identity (`agent-demo`) locally, and behind Cognito until the frontend verifies the ALB's signed header | Sees all sessions, opens a new session link, takes over a stuck session, answers on the customer's behalf |

The brief says the assistant "helps support agents guide customers" and also asks for a "customer onboarding
interface". We support both: the customer drives the chat, and an agent can step in at any point. See
[assumptions.md](assumptions.md).

There are four external systems.

| System | Used for | Called by node |
|---|---|---|
| Partner | Match the customer to a partner record; read device purchases | `verify_identity`, `fetch_purchases` |
| Identity | Send an OTP (`verify_identity`); verify the OTP; verify an ID document number | `verify_identity`, `check_otp`, `check_document` |
| Contract admin | Receive the finished application and return a submission reference | `submit_application` |
| Amazon Bedrock | LLM calls through the Converse API | the five LLM nodes |

**One mock service, with the same API shapes as the real systems.** It serves partner, identity, contract admin
and the Bedrock Converse API.

| Where | Partner, identity, contract admin | Bedrock |
|---|---|---|
| Local (`docker compose`) | Mock | Mock (`BEDROCK_ENDPOINT_URL=http://mock:8080`) |
| Backend tests | In-process fakes built from the same seed file | In-process fake LLM |
| develop (AWS) | Mock, as its own ECS service | Real Bedrock through the VPC endpoint (`BEDROCK_ENDPOINT_URL` unset) |
| prod (AWS) | Real endpoints. They do not exist yet, so Terraform sets `https://*.invalid` placeholders | Real Bedrock |

The backend code is the same everywhere; only environment variables change (`PARTNER_API_URL`,
`IDENTITY_API_URL`, `CONTRACT_API_URL`, `BEDROCK_ENDPOINT_URL`). There is no "am I talking to a mock?" branch in
the code.

## 2. Containers

The brief requires two services that are deployed separately. We keep that split.

```mermaid
flowchart LR
    browser(["Browser"])

    subgraph fe["Frontend service (Next.js)"]
        s["Customer app<br/>/s/*"]
        ag["Agent console<br/>/agent/*"]
        proxy["Route handlers<br/>/api/* (relay + SSE)"]
    end

    subgraph be["Backend service (FastAPI + LangGraph)"]
        api["HTTP API + SSE"]
        lg["Onboarding graph"]
        domain["Eligibility, ranking,<br/>pricing (code)"]
    end

    subgraph db["PostgreSQL (one instance)"]
        cp[("checkpoint schema")]
        dm[("domain schema")]
        cat[("catalog schema")]
    end

    mock["Mock service<br/>/partner /identity /contract<br/>/model/{id}/converse"]

    browser --> s & ag
    s & ag --> proxy
    proxy -- "HTTP, internal only" --> api
    api --> lg --> domain
    lg --> cp
    lg & api --> dm
    domain --> cat
    lg -- "local and develop: mock<br/>prod: real endpoints" --> mock
```

| Container | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js 16 (App Router, TypeScript, pnpm), standalone Node server | Two apps in one service: the customer app (`/s/*`) and the agent console (`/agent`). `proxy.ts` (Next.js 16's middleware) turns the `/s/{token}` link into a session cookie. Route handlers under `/api/*` relay every call, including SSE, to the backend; the browser never calls the backend directly. `/healthz` proxies to the backend's health check, `/api/healthz` checks only the frontend, and `/api/agent/me` returns the signed-in agent's ID |
| Backend | FastAPI + LangGraph, Python 3.13, uv | HTTP API, the onboarding graph, eligibility, ranking and pricing, persistence, calls to external systems. Creates its tables and seeds the catalog at startup |
| PostgreSQL | PostgreSQL 16 (RDS in AWS) | Three schemas: `checkpoint` (graph state), `domain` (customer and transaction entities), `catalog` (products, rules) |
| Mock | FastAPI | One app for partner, identity, contract admin and Bedrock Converse, plus fault injection (`/_mock/faults`). Local and develop only |

Why the three schemas share one instance: they differ in lifetime and access, but not enough to justify
three databases for this scope. Checkpoints are only useful while a session is alive (30-day inactivity limit),
domain entities live as long as the customer relationship, and the catalog is read-only for the graph.

Why the customer app and the agent console share one service: the brief asks for exactly two services. The
two apps have separate layouts, routes and auth rules, so they behave as separate apps to users while the
deployment stays at two units.

### Frontend-to-backend communication

- The browser talks only to the frontend (through the ALB in AWS).
- The frontend's route handlers call the backend at `BACKEND_URL` (`http://backend:8000`: Docker Compose
  locally, ECS Service Connect in AWS).
- Chat updates are streamed with **server-sent events**. The backend emits SSE, and the frontend passes the
  stream through unchanged. Events: `session.updated`, `message.appended`, `prompt.updated`, `entity.updated`,
  and a `: ping` comment every 15 s.
- Agent identity is resolved once at the frontend and passed to the backend as `X-Agent-Id`. Locally (and in
  develop for now) `AGENT_DEV_AUTH=true` makes every agent `agent-demo`. The customer's session token is read from
  the httpOnly cookie and passed as `X-Session-Token`. The backend checks the token against its stored HMAC and
  trusts `X-Agent-Id` because only the frontend can reach it. See [networking.md](networking.md#5-authentication).
- Sending input returns `202 Accepted`. The graph runs in the background and the result arrives over SSE.

The API contract is in [`CONTRACTS.md`](../CONTRACTS.md) §3. Main endpoints:

| Caller | Endpoint | Purpose |
|---|---|---|
| Agent console | `POST /api/sessions` | Create a session and return the customer link `/s/{token}`. The frontend requires an agent identity for it |
| Customer app | `GET /api/customer/session`, `POST .../input`, `GET .../stream` | Read the session, send input, stream updates |
| Agent console | `GET /api/agent/sessions`, `GET /api/agent/sessions/{id}`, `POST .../assign`, `POST .../input`, `GET /api/agent/sessions/{id}/stream`, `GET /api/agent/stream` | Session list, session detail with entities, take over, answer as agent, stream one session or all |
| Agent console | `GET /api/agent/me` (frontend only) | Who the signed-in agent is, for "Assign to me" |
| Deploy smoke test | `GET /healthz` | Frontend relays to the backend's `/healthz` |

## 3. Inside the backend

```mermaid
flowchart LR
    subgraph edge["Edge"]
        http["HTTP API"]
        threads["Runtime: session lookup,<br/>per-session lock, SSE broker"]
        saver["Checkpointer<br/>(AsyncPostgresSaver, gzip + AES serde)"]
    end
    subgraph g["Graph"]
        code["Code nodes"]
        llmn["LLM nodes"]
        wait["Wait nodes (interrupt)"]
    end
    subgraph logic["Decision logic"]
        elig["Eligibility rules"]
        rank["Ranking"]
        price["Pricing"]
    end
    subgraph adapters["Adapters"]
        repo["SQLAlchemy models (domain, catalog)"]
        clients["Partner / Identity / Contract clients (httpx)"]
        bedrock["ChatBedrockConverse"]
    end
    http --> threads --> saver --> g
    code --> logic
    code --> clients
    llmn --> bedrock
    g --> repo
```

The left column is why sessions can be resumed: the API receives input, finds the thread for the session,
and the checkpointer loads the paused state. SSE events reach every backend replica through Postgres `LISTEN/NOTIFY`
(`SSE_BROKER=postgres`; local runs keep the in-memory broker). The per-session lock still lives in the backend
process, so the backend runs as a single replica for now (see [tradeoffs.md](tradeoffs.md#4-application-design)).

Eligibility, ranking and pricing are plain code, not LLM calls. An agent must be able to see **why** a product
was excluded (`EligibilityRule.failure_reason_code`) and **why** a price is what it is (`Quote.rating_inputs`).
A sentence written by an LLM cannot be traced back like that. The LLM only extracts values from what people
say and explains results the code already produced.

## 4. Scope boundary

The system ends when the contract admin system returns a submission reference
(`Application.submission_ref`). Underwriting and policy issuance belong to the contract admin system and are out
of scope. The `Policy` entity is named in the model but has no fields.

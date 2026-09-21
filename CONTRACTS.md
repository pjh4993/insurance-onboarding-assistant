# Contracts (single source of truth for parallel work)

Every workstream builds against this file. If you must change a contract, say so in your final report
instead of silently diverging.

Design references (Korean wiki, read-only): `/Users/pyler/workspace/ai-interview-assignments/assignment/bolttech-onboarding-assistant/bolttech-onboarding-assistant/wiki/`
— `state-model.md` (graph state), `lifecycle.md` (nodes and edges), `entity-dictionary.md` (entities),
`mock-servers.md` (external APIs), `infrastructure.md` (AWS), `agent-console.md` (agent UI), `catalog-seed.md`
(8 seed products), `implementation-plan.md` (scope cut: what is in and what is deferred).

## 1. Layout and ownership

| Path | Owner | Notes |
|---|---|---|
| `backend/` | backend | FastAPI + LangGraph, Python 3.13, uv. Includes `backend/Dockerfile` |
| `mock/` | mock | One FastAPI app for all four external systems. Includes `mock/Dockerfile` |
| `frontend/` | frontend | Next.js App Router + TypeScript + pnpm. Includes `frontend/Dockerfile` |
| `infra/`, `.github/workflows/`, `docker-compose.yml` | infra | Terraform >= 1.5, GitHub Actions |
| `docs/`, `README.md` | docs | English submission documents |
| `contracts/`, `CONTRACTS.md` | coordinator | Read-only for workstreams |

Rules for every workstream: stay inside your paths; do not run git; do not create or change anything in AWS
(no `terraform apply`, no AWS write calls, no real Bedrock calls — tests use the mock).

## 2. Local runtime

| Service | Compose name | Container port | Host port |
|---|---|---|---|
| PostgreSQL 16 | `postgres` | 5432 | 15432 |
| Mock server | `mock` | 8080 | 18080 |
| Backend | `backend` | 8000 | 18000 |
| Frontend | `frontend` | 3000 | 13000 |

Environment variables (backend):

| Name | Local value | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://onboarding:onboarding@postgres:5432/onboarding` | domain + catalog + checkpoint schemas |
| `PARTNER_API_URL` | `http://mock:8080/partner` | |
| `IDENTITY_API_URL` | `http://mock:8080/identity` | |
| `CONTRACT_API_URL` | `http://mock:8080/contract` | |
| `BEDROCK_ENDPOINT_URL` | `http://mock:8080` | unset in prod → AWS default endpoint |
| `AGENT_CONFIG_URI` | unset | agent config bundles (models, prompts, copy): a directory or `s3://bucket/prefix` holding `<semver>/config.json`; unset → the baseline bundle in the agent package |
| `AGENT_CONFIG_VERSION` | unset | `1.2.0`, or a prefix (`1`, `1.2`) meaning the highest published match; unset → the newest the agent supports |
| `LLM_ALLOWED_MODEL_IDS` | unset | comma-separated model ids a bundle may name (set from the IAM policy in AWS) |
| `AGENT_CONFIG_SEED` | `true` in compose | publish the shipped baseline into an empty `AGENT_CONFIG_URI` at startup (local only) |
| `BACKEND_ECS_CLUSTER`, `BACKEND_ECS_SERVICE` | unset | the service the operator console restarts to load a new bundle; unset: no restart |
| `AWS_REGION` | `ap-northeast-2` | |
| `CHECKPOINT_AES_KEY` | 64 hex chars (dev value in compose) | checkpoint encryption |
| `SESSION_HMAC_KEY` | dev value | session-link token HMAC; also keys the client-IP hash of self-serve sessions |
| `SELF_SERVE_PER_IP_PER_HOUR` | `5` | self-serve starts one client IP may make in any 3600 s |
| `SELF_SERVE_PER_HOUR` | `200` | self-serve starts across all clients in any 3600 s |

Frontend: `BACKEND_URL=http://backend:8000`, `AGENT_DEV_AUTH=true` (sends `X-Agent-Id: agent-demo`),
`OPERATOR_DEV_AUTH=true` (sends `X-Operator-Id: operator-demo`; never set in AWS). In AWS the frontend verifies
operators with `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_OPERATOR_CLIENT_ID`, and serves the console on
`OPERATOR_BASE_URL`.
The browser never calls the backend directly; Next.js route handlers under `frontend/app/api/*` proxy to `BACKEND_URL`,
including SSE.

## 3. Backend HTTP API (consumed by the frontend)

All JSON. Money is integer minor units + ISO 4217 currency. Times are ISO 8601 UTC.

### Session links
- `POST /api/sessions` body `{"market": "KR" | "US", "locale"?: Locale}` → `201 {"session_id", "token", "customer_path": "/s/{token}"}`.
  `locale` defaults to the market's language (`KR` → `ko`, `US` → `en`) when the agent's config bundle has it, else the
  bundle's default language; a `locale` the bundle lacks → `422`. The session's `origin` is `"AGENT_LINK"`.
- `POST /api/public/sessions` (public landing page, no agent auth) body as `POST /api/sessions`, header
  `X-Client-IP: <ip>` set by the frontend → `201` with the same body as `POST /api/sessions`; the session's `origin` is
  `"SELF_SERVE"`. Rate-limited, counted in the DB over the last 3600 s across all replicas: `SELF_SERVE_PER_IP_PER_HOUR`
  per client IP and `SELF_SERVE_PER_HOUR` overall; agent-link sessions do not count. A missing or blank `X-Client-IP`
  is treated as `"unknown"`, one shared bucket. Over a limit → `429 {"detail": "rate_limited", "retry_after": <int s>}`
  with a `Retry-After: <int s>` header (seconds until the oldest counted session leaves the window, at least 1).
  Only an HMAC-SHA256 of the IP (keyed with `SESSION_HMAC_KEY`) is stored, never the IP itself
- `GET /api/languages` → `{"languages": [{"code": Locale, "name": string}], "default": Locale}`: the languages the agent's
  config bundle is written in, which a session's `locale` must be one of
- `GET /healthz` → `{"status": "ok"}`

### Customer (header `X-Session-Token: <token>`)
- `GET /api/customer/session` → `SessionView`
- `POST /api/customer/session/input` body `InputBody` → `202 {"accepted": true}`
- `GET /api/customer/session/stream` → SSE
- `PUT /api/customer/session/locale` body `{"locale": Locale}` → `SessionSummary`. Fixed copy and LLM replies use the
  new language from the next graph step on; messages already sent stay as they were. Publishes `session.updated`

### Agent (header `X-Agent-Id: <id>`; Cognito later)
- `GET /api/agent/sessions` → `{"sessions": SessionSummary[]}` sorted: `waiting_for == "AGENT"` first, then oldest `last_activity_at`
- `GET /api/agent/sessions/{session_id}` → `SessionDetail`
- `POST /api/agent/sessions/{session_id}/assign` → `SessionSummary` (sets `assigned_agent_id`, `mode = "ASSIST"`)
- `POST /api/agent/sessions/{session_id}/input` body `InputBody` → `202` (actor = AGENT)
- `PUT /api/agent/sessions/{session_id}/locale` body `{"locale": Locale}` → `SessionSummary` (same as the customer's)
- `GET /api/agent/stream` → SSE for all sessions; `GET /api/agent/sessions/{session_id}/stream` → SSE for one

### Operator (header `X-Operator-Id: <id>`, set by the frontend after verifying the operator's login)
- `GET /api/operator/config` → `{"live": {"version", "source"}, "version_spec", "next": string | null, "restart_needed", "publishable", "restartable", "base"}`
- `GET /api/operator/config/versions` → `{"versions": [{"version", "release": Release, "live", "latest"}]}` newest first
- `GET /api/operator/config/versions/{version}` → `{"version", "release", "live", "files": {path: text}, "summary": {"languages", "default_language", "models", "nodes": {node: profile}, "copy_keys"}}`; `404` if not published
- `POST /api/operator/config/validate` body `{"files": {path: text}}` → `{"ok", "problems": string[], "summary" | null}`
- `POST /api/operator/config/versions` body `{"files", "notes", "bump": "patch" | "minor"}` → `201 {"version", "release"}`; the version is one `bump` above the latest of the draft's major; `422 {"detail": {"message", "problems"}}` for an invalid draft, `409` when this backend cannot publish
- `POST /api/operator/restart` → `202`; `409` when `BACKEND_ECS_*` is unset
- `GET /api/operator/graph` → `{"entry", "nodes": [{"id", "domain", "kind": "code" | "llm" | "wait", "reads": string[]}], "edges": [{"source", "target", "kind"}]}`
- `Release = {"published_by", "published_at", "via", "based_on", "notes"}` (the version's `release.json`)

### Types
```ts
type Stage = "IDENTITY" | "PROFILING" | "RECOMMENDATION" | "APPLICATION" | "SUBMITTED" | "HANDOFF" | "DECLINED" | "WITHDRAWN";
type WaitingFor = "IDENTITY_INFO" | "OTP_CODE" | "NEEDS" | "DECISION" | "PARTIES" | "ANSWERS" | "CONFIRM" | "AGENT" | null;

type Locale = string;  // a language code the agent's config bundle declares (today "ko" | "en"): fixed copy, LLM replies, the customer UI

type SessionSummary = {
  session_id: string; display_name: string;          // "Unverified #1a2b" until identity is verified
  market: "KR" | "US"; locale: Locale; origin: "AGENT_LINK" | "SELF_SERVE"; status: "ACTIVE" | "SUBMITTED" | "DECLINED" | "WITHDRAWN" | "HANDOFF" | "EXPIRED";
  stage: Stage; waiting_for: WaitingFor; mode: "AUTO" | "ASSIST";
  assigned_agent_id: string | null; last_activity_at: string;
};
type Message = { id: string; role: "customer" | "assistant" | "agent" | "system"; text: string; created_at: string };
type Prompt = { waiting_for: WaitingFor; message: string; options?: RecommendationCard[]; summary?: string };
type Quote = { quote_id: string; premium_minor: number; currency: string; billing_period: "MONTHLY" | "ONE_TIME" | "PER_TRIP";
               term_start_date: string; term_end_date: string; valid_until: string };
type RecommendationCard = {
  recommendation_id: string; product_code: string; marketing_name: string; product_type: string; rank: number;
  eligibility_result: "ELIGIBLE" | "INELIGIBLE"; failed_reasons: string[]; rationale: string | null;
  status: "PROPOSED" | "ACCEPTED" | "DECLINED" | "EXPIRED"; quote: Quote | null;
};
type SessionView = { session: SessionSummary; messages: Message[]; prompt: Prompt | null };
type SessionDetail = SessionView & {
  current_node: string | null;
  entities: {
    party: Record<string, unknown> | null;            // PII masked: id_document_number never returned
    needs_assessment: Record<string, unknown> | null;
    insurable_objects: Record<string, unknown>[];
    recommendations: RecommendationCard[];
    application: { application_id: string; status: string; answers: Record<string, unknown>;
                   missing_fields: string[]; summary: string | null; submission_ref: string | null } | null;
    application_parties: { role: string; full_name: string }[];
  };
};
type InputBody = { type: Exclude<WaitingFor, null>; data: Record<string, unknown> };
```

`InputBody.data` by `type`:

| type | data |
|---|---|
| `IDENTITY_INFO` | `{full_name, email, phone, id_document_type, id_document_number, third_party_consent: boolean}` |
| `OTP_CODE` | `{code}` |
| `NEEDS` | `{text}` — free text, the LLM extracts |
| `DECISION` | `{decision: "ACCEPT" | "DECLINE" | "CHANGE", recommendation_id?, text?}` |
| `PARTIES` | `{text}` |
| `ANSWERS` | `{text}` |
| `CONFIRM` | `{confirmed: boolean, text?}` |
| `AGENT` | `{resolution: "VERIFIED" | "CONTINUE" | "END", note?}` — agent resolves a handoff |

### SSE
Frame: `event: <type>\ndata: <json>\n\n`. Types: `session.updated {session: SessionSummary}`,
`message.appended {session_id, message: Message}`, `prompt.updated {session_id, prompt: Prompt | null}`,
`entity.updated {session_id, entity_type, entity_id}`. Send a `: ping` comment every 15 s.

## 4. Mock server API (base `http://mock:8080`)

Paths below are relative to each prefix. Seed data: `contracts/seed-customers.json`.

### Partner — prefix `/partner`
- `POST /v1/customers/match` header `X-Consent-At` (required, else 403) body `{full_name, email, phone}` →
  `{"matched": true, "partner_customer_ref", "date_of_birth"}` or `{"matched": false}`
- `GET /v1/customers/{ref}/purchases` header `X-Consent-At` → `{"purchases": [{order_id, purchased_at, item: {category, manufacturer, model, imei, release_date, activation_date, price_minor, currency}}]}`

### Identity — prefix `/identity`
- `POST /v1/otp` `{phone}` → `201 {otp_request_id, expires_at}`
- `POST /v1/otp/{otp_request_id}/verify` `{code}` → `{verified: bool, reason?: "MISMATCH" | "EXPIRED"}`
- `POST /v1/documents/verify` `{document_type, document_number, full_name, date_of_birth}` → `{verified: bool, reason?: "NOT_FOUND" | "NAME_MISMATCH"}`

### Contract — prefix `/contract`
- `POST /v1/applications` header `Idempotency-Key` → `201 {submission_ref: "SUB-YYYY-NNNNNN", status: "RECEIVED", received_at}`; same key again → `200` with the first body

### Bedrock Converse — no prefix
- `POST /model/{modelId}/converse` — the boto3 `bedrock-runtime` Converse shape. Ignore SigV4 headers.
  - If `toolConfig.tools[].toolSpec.name` is present, answer with a `toolUse` block for that tool:
    `{"output": {"message": {"role": "assistant", "content": [{"toolUse": {"toolUseId", "name", "input"}}]}}, "stopReason": "tool_use", "usage": {"inputTokens", "outputTokens", "totalTokens"}, "metrics": {"latencyMs"}}`
  - Otherwise answer with `{"content": [{"text": "..."}]}` and `"stopReason": "end_turn"`.
  - Pick the fixture by tool name and by which seed customer's full name appears anywhere in `messages` / `system`.
- Tool names (they are the Pydantic class names the backend passes to `with_structured_output`):
  `NeedsExtraction`, `RecommendationRationale`, `PartiesExtraction`, `AnswersExtraction`, `ApplicationSummary`.
  Their JSON shapes are defined by the backend in `backend/packages/agent/src/onboarding_agent/llm/schemas.py`; the mock's fixtures must
  validate against them. Coordinate through the shapes in §5.

### Mock controls — prefix `/_mock`
- `POST /_mock/faults {target: "partner" | "identity" | "contract" | "bedrock", kind: "timeout" | "500" | "429", count}`
- `POST /_mock/reset`

## 5. LLM output shapes (backend owns; mock mirrors)

```python
class NeedsExtraction(BaseModel):
    age_range: Literal["AGE_UNDER_19","AGE_19_29","AGE_30_39","AGE_40_49","AGE_50_64","AGE_65_PLUS"] | None
    occupation: str | None
    residence_country: str | None          # ISO 3166-1 alpha-2
    existing_coverage: list[dict] = []     # {product_type, insurer_name, expires_on}
    objectives: list[Literal["PROTECT_DEVICE","TRAVEL_COVER","EXTEND_WARRANTY","REDUCE_PREMIUM"]] = []
    device: dict | None                    # {device_category, manufacturer, model, purchase_date, purchase_price_minor}
    trip: dict | None                      # {destination_countries, departure_date, return_date, trip_cost_minor}
    missing_fields: list[str] = []         # NAMES of fields above that are still unknown

class RecommendationRationale(BaseModel):
    items: list[dict]                      # {recommendation_id, rationale}

class PartiesExtraction(BaseModel):
    all_self: bool
    parties: list[dict] = []               # {role: "INSURED" | "PAYER", full_name, date_of_birth}
    policyholder_change_requested: bool = False  # the customer asked for another policyholder (not allowed)

class AnswersExtraction(BaseModel):
    answers: dict
    missing_fields: list[str] = []

class ApplicationSummary(BaseModel):
    summary: str
```

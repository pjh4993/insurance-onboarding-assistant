# Future improvements

The deadline was one day after the design was finished. We built everything the brief asks for first and
kept the rest as design. Each item below is designed (in these docs) but not built, or built only partly.

## 1. Known limits of what is built

These are gaps in the current code, not new features. Each one is safe for the demo and develop, and each has to
be closed before real use.

| Limit | Today | Fix |
|---|---|---|
| Session locks are in-process | SSE events already cross replicas (`SSE_BROKER=postgres`, Postgres `LISTEN/NOTIFY`), but the per-session lock that serialises graph runs lives in one backend process. Run a single backend replica, or keep each session on one replica end to end. Prod's composition asks for two tasks | Move the lock to a Postgres advisory lock keyed by session |
| Session links do not expire | `token_expires_at` (48 hours) is stored but not checked; the browser cookie lasts 24 hours | Reject expired tokens in the backend's token lookup |
| Agent header is not verified | The frontend's agent auth is a development switch (`AGENT_DEV_AUTH=true`, every agent is `agent-demo`). The hook for the ALB's Cognito headers exists, but verifying the signed `x-amzn-oidc-data` JWT is a `TODO` | Verify the JWT with the ALB public key (fetched through NAT), use its `sub` as the agent ID, then turn `AGENT_DEV_AUTH` off |
| One customer session per browser | The session cookie holds one token; opening a second link replaces it | Scope the cookie per session, or keep the token in the page URL path for API calls |
| Assignment is not a lock | `assign` records the agent and `mode = ASSIST`, but any agent can send input | Reject agent input from anyone but the assigned agent |

## 2. Product and workflow

| Item | What it would do | Notes |
|---|---|---|
| Returning-customer linking | After identity is verified, find an existing `Party` by a verified key (partner reference, ID number HMAC, or OTP-verified phone + date of birth), move the session to it, and start the new needs assessment from the previous one | Only after verification: matching by email before that would show one person's data to someone else. `Party.merged_into_party_id` exists for this |
| Customer history tab in the agent console | One tab with the linked customer's past sessions: stage reached, outcome, recommendations, prices, submission references, and what changed in their needs | Locked until the current session is `VERIFIED` (`403` from the history API). Sessions whose conversation expired show an entity-based summary |
| ASSIST draft approval (co-work) | When an agent has taken a session, the AI's next message stops as a draft (`waiting_for = AGENT_REVIEW`). The agent sends it, edits it or writes their own | Built on the existing `interrupt`/resume. Today `mode = ASSIST` is recorded on assignment, but drafts are not held for approval |
| Customer withdrawal | A customer action that ends the session and marks the application `WITHDRAWN` | Today only declining recommendations or an agent's `END` stops a session |
| More agent-console panels | Beyond the progress and application views | |
| Richer SSE events | `draft.ready`, `handoff.requested` | Needed by ASSIST drafts |

## 3. Data and security

| Item | What it would do | Notes |
|---|---|---|
| 30-day checkpoint cleanup job | A daily EventBridge Scheduler rule starts an ECS task (backend image, cleanup command) that deletes threads inactive for 30 days via the checkpointer's delete-thread API | PostgreSQL has no TTL. The `domain` session table knows what to delete; the checkpointer knows how. A `TODO` in `infra/modules/data/main.tf` lists the resources |
| Checkpoint key rotation | A decryptor that tries the new key and falls back to the old key for 30 days | `EncryptedSerializer` reads with one key only. After 30 days all old checkpoints are gone, so the old key can be retired |
| Separate keys per purpose | Today the checkpoint key also encrypts the stored ID number, and the session HMAC key also hashes ID numbers | One key per purpose limits what a single leaked key exposes |
| Service-to-service TLS | TLS on Service Connect | Needs a private CA |

## 4. Infrastructure and delivery

| Item | What it would do | Notes |
|---|---|---|
| Prod apply | Apply `envs/prod` (Multi-AZ RDS, two tasks per service, endpoints in both AZs, NAT per AZ) | Needs the per-session lock in Postgres first (two backend tasks). Real partner, identity and contract admin endpoints do not exist yet |
| Prod promotion run | Run `deploy-prod.yml`, which deploys the develop-verified image SHA after approval | The workflow is built |
| Full smoke test | After each develop deploy, run seed customer A end to end through the ALB | Today: `/healthz` through the frontend to the backend |
| Plan on pull requests | Run `terraform plan` for develop in CI and post it on the PR | Today CI runs `fmt` and `validate` only |
| Frontend unit tests in CI | Add `pnpm test` (vitest) to the frontend job | Today they run locally |

## 5. LLM

| Item | What it would do | Notes |
|---|---|---|
| Per-node model switch to Haiku 4.5 | Move extraction nodes (`assess_needs`, `collect_parties`, `collect_answers`) to `global.anthropic.claude-haiku-4-5-20251001-v1:0` | The setting exists (`LLM_MODEL_OVERRIDES`) and the IAM policy already allows Haiku 4.5; the switch needs measurement first |
| Evaluation set | A labelled set of customer utterances (Korean and English) with expected extractions, run against each model and structured-output method | Needed to justify the Haiku switch and to settle `function_calling` vs `json_schema` with more than one measurement each |
| Real compression ratio | Measure checkpoint size with real conversations | The test conversation compressed unrealistically well |

## 6. Catalog

| Item | What it would do | Notes |
|---|---|---|
| Tiered deductibles | A deductible that depends on the device price band (for example $49 under $500 and $99 above) | `deductible_minor` holds one value today; the seed uses the higher band |
| Age- and state-based travel pricing | Price US travel by traveller age and state of residence; children 17 and under free | The seed uses trip cost only |
| Percentage deductibles and "up to device price" limits | Model them exactly | The seed stores the minimum amount and the tier cap |
| Cover start on the real purchase date | Start device terms on the purchase date when the product's rule says so | Today `PURCHASE_DATE` terms start on the quote date |

## 7. Out of scope by design

Underwriting, policy issuance and the `Policy` entity's fields belong to the contract admin system. The
assistant stops at the submission reference.

# Future improvements

The deadline was one day after the design was finished. We built everything the brief asks for first and
kept the rest as design. Each item below is designed (in these docs) but not built, or built only partly.

## 1. Product and workflow

| Item | What it would do | Notes |
|---|---|---|
| Returning-customer linking | After identity is verified, find an existing `Party` by a verified key (partner reference, ID number HMAC, or OTP-verified phone + date of birth), move the session to it, and start the new needs assessment from the previous one | Only after verification: matching by email before that would show one person's data to someone else. The temporary `Party` keeps `merged_into_party_id` |
| Customer history tab in the agent console | One tab with the linked customer's past sessions: stage reached, outcome, recommendations, prices, submission references, and what changed in their needs | Locked until the current session is `VERIFIED` (`403` from the history API). Sessions whose conversation expired show an entity-based summary |
| ASSIST draft approval (co-work) | When an agent has taken a session, the AI's next message stops as a draft (`waiting_for = AGENT_REVIEW`). The agent sends it, edits it or writes their own | Built on the existing `interrupt`/resume. Today `mode = ASSIST` is recorded on assignment, but drafts are not held for approval |
| More agent-console panels | Beyond the "progress" and "application" views | |
| Richer SSE events | `draft.ready`, `handoff.requested` | Needed by ASSIST drafts |

## 2. Data and security

| Item | What it would do | Notes |
|---|---|---|
| 30-day checkpoint cleanup job | A daily EventBridge Scheduler rule starts an ECS task (backend image, cleanup command) that deletes threads inactive for 30 days via the checkpointer's delete-thread API | PostgreSQL has no TTL. The `domain` session table knows what to delete; the checkpointer knows how |
| Checkpoint key rotation | A decryptor that tries the new key and falls back to the old key for 30 days | `EncryptedSerializer` reads with one key only. After 30 days all old checkpoints are gone, so the old key can be retired |
| Service-to-service TLS | TLS on Service Connect | Needs a private CA |

## 3. Infrastructure and delivery

| Item | What it would do | Notes |
|---|---|---|
| Domain, HTTPS and Cognito login | Buy a domain, issue an ACM certificate, enable the HTTPS listener and the Cognito rule on `/agent/*`, turn off `AGENT_DEV_AUTH` | Terraform is already switched by a domain variable. The cheapest option found: a `.click` domain on Route 53 at about $3/year plus $0.50/month for the hosted zone; public ACM certificates are free |
| Prod apply | Apply `envs/prod` (Multi-AZ RDS, two tasks per service, endpoints in both AZs, NAT per AZ) | Real partner, identity and contract admin endpoints do not exist yet |
| Prod promotion run | Run the approval-gated workflow that deploys the develop-verified image SHA | |
| Full smoke test | After each develop deploy, run seed customer A end to end through the ALB | Today: health check only |

## 4. LLM

| Item | What it would do | Notes |
|---|---|---|
| Per-node model switch to Haiku 4.5 | Move extraction nodes (`assess_needs`, `collect_parties`, `collect_answers`) to `global.anthropic.claude-haiku-4-5-20251001-v1:0` | The per-node setting exists; the switch needs measurement first |
| Evaluation set | A labelled set of customer utterances (Korean and English) with expected extractions, run against each model and structured-output method | Needed to justify the Haiku switch and to settle `function_calling` vs `json_schema` with more than one measurement each |
| Real compression ratio | Measure checkpoint size with real conversations | The test conversation compressed unrealistically well |

## 5. Catalog

| Item | What it would do | Notes |
|---|---|---|
| Tiered deductibles | A deductible that depends on the device price band (for example $49 under $500 and $99 above) | `deductible_minor` holds one value today; the seed uses the higher band |
| Age- and state-based travel pricing | Price US travel by traveller age and state of residence; children 17 and under free | The seed uses trip cost only |
| Percentage deductibles and "up to device price" limits | Model them exactly | The seed stores the minimum amount and the tier cap |

## 6. Out of scope by design

Underwriting, policy issuance and the `Policy` entity's fields belong to the contract admin system. The
assistant stops at the submission reference.

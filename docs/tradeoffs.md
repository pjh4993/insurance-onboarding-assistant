# Tradeoffs

Each row names what we chose, what we gave up, and why.

## 1. Infrastructure

| Chose | Gave up | Why |
|---|---|---|
| Bedrock global cross-region inference | A guarantee that conversations are processed only in Korea | There is no other way to call this model from Seoul. Logs, quota and billing stay in Seoul |
| Plain HTTP inside the VPC | Encryption between services | Service Connect TLS needs a private CA, which is expensive. Security groups and private subnets restrict who can connect |
| VPC endpoints for AWS services, NAT for the rest | Full isolation with no NAT | Agent-auth signing keys and prod's real external systems are on the internet |
| Login checked only at the frontend | A second check in the backend | The backend is reachable only from the frontend's security group. Keeping the check in one place keeps it simple |
| Checkpoints in RDS | TTL-based expiry and key-value scalability (DynamoDB) | The encrypting serializer plugs in through a public argument, and there is one store instead of two. Old checkpoints are removed by a daily cleanup job instead of TTL |
| One mock service for four systems | Four services that look like production | Lower develop cost and one deployment |
| Develop interface endpoints in one AZ | Develop's AWS API access if 2a fails; cross-AZ transfer cost | Halves the largest item in the develop bill. Prod has both AZs |
| One RDS instance, three schemas | Independent scaling and failure isolation per store | Cheapest option; the data sizes in scope are small |
| Frontend relays all backend calls | A little latency and one more hop for SSE | The backend is never public; one place handles auth |
| One frontend service with two apps (`/s`, `/agent`) | Deploying the agent console on its own | The brief asks for two services. Separate layouts and routes still keep them apart for users |
| Fixed AES key for checkpoints, no rotation | Key rotation | Simple, no extra calls. Checkpoints expire after 30 days, so rotation can be added later with a reader that accepts the old key for 30 days |

## 2. LLM: Claude Sonnet 4.6 on Bedrock

**First choice was OpenAI GPT-5.6 Luna** (`global.openai.gpt-5.6-luna`) on Bedrock. The Marketplace subscription
was `ACTIVE` and the terms were accepted, but every call failed with
`AccessDeniedException: not available for this account`. It was not IAM (the caller had `AdministratorAccess`,
and the policy simulator said `allowed`). The account's tokens-per-minute quota for that model was **0**
(quota `L-D983F7C0`; the AWS default is 20 million). A quota increase request was not granted.

We then looked for models with both quota and accepted terms in this account (Seoul, global inference):

| Model | Tokens per minute quota | Terms |
|---|---|---|
| Claude Sonnet 4.6 | 6 million | Accepted |
| Claude Haiku 4.5 | 5 million | Accepted |
| Amazon Nova 2 Lite | 8 million | Accepted |

Both Claude models were tested with the three `with_structured_output` methods. Input: the Korean sentence used
by seed customer A ("I'm a 35-year-old software engineer living in Seoul. I'm worried my new Galaxy phone will
break."). Schema: the needs-extraction fields.

| Method | Sonnet 4.6 | Haiku 4.5 |
|---|---|---|
| `function_calling` (default) | Works, 1.9 s | Works, 1.3 s |
| `json_schema` | Works, 5.3 s | Works, 4.2 s |
| `prompt_prefill` | **Rejected**: the model does not accept a prefilled response | Works, 0.9 s |

Both extracted the age range (30s), occupation, country (`KR`) and objective (`PROTECT_DEVICE`) correctly.

| Chose | Gave up | Why |
|---|---|---|
| Sonnet 4.6 for every node | Lower cost and latency of Haiku 4.5 | Recommendation reasons and application summaries are visible in the demo; writing quality matters. Extraction nodes can move to Haiku through a per-node setting later |
| `function_calling` | `json_schema` strictness | Default, works on both models, and was 2–3× faster in one-off measurements (to be re-measured) |
| Low temperature | Varied wording | Stable extraction output |

Found in the test and fed into the design: Sonnet put objective **values** into `missing_fields` instead of
field **names**, because the schema description was ambiguous. The field description now says explicitly that it
holds names of fields that are still unknown.

## 3. Checkpoint store: DynamoDB vs PostgreSQL

**First choice was DynamoDB** (`DynamoDBSaver` from `langgraph-checkpoint-aws` 1.2.3). We tested application-level
encryption with moto (mocked DynamoDB and S3): stored a message containing a phone number, then read the raw
table and bucket values directly.

| Setup | Reads back | Plain text visible in storage | Stored in |
|---|---|---|---|
| No encryption | Yes | Yes | DynamoDB |
| Encryption | Yes | No | DynamoDB |
| Large checkpoint, library compression + encryption | Yes | No | **Offloaded to S3**: ciphertext does not compress |
| Large checkpoint, compress-then-encrypt serializer | Yes | No | DynamoDB |

Reading with a different key fails, as it should. Three findings:

1. **`DynamoDBSaver` does not accept a serializer in its constructor.** It captures the default serializer in an
   internal object (`saver.serializer.serde`), so setting `saver.serde` has no effect. Making it work needs a
   subclass that patches both places, a pinned library version, and a regression test.
2. **Library compression happens after serialization.** If the serializer already encrypts, the library
   compresses ciphertext, which does not shrink, and large checkpoints get offloaded to S3 more often. So the
   serializer must compress first and encrypt second.
3. **`EncryptedSerializer` joins type names with `+`.** An inner serializer whose type name contains `+` breaks
   on read.

Finding 1 decided it: it works, but only by touching non-public internals. `PostgresSaver`
(`langgraph-checkpoint-postgres` 3.1.2) takes `serde` as a constructor argument. We moved checkpoints to RDS and kept
the compress-then-encrypt serializer from finding 2.

The test conversation repeated the same text and compresses far better than real chat. The real compression
ratio still needs measuring.

| Chose | Gave up | Why |
|---|---|---|
| `PostgresSaver` on RDS | DynamoDB TTL and scaling | Supported serializer injection; one data store |
| Compress, then AES | Library-level compression | Compression after encryption does nothing |

## 4. Application design

| Chose | Gave up | Why |
|---|---|---|
| Eligibility, ranking and pricing in code | Letting the LLM reason about fit | Every exclusion and price must be traceable (`failure_reason_code`, `rating_inputs`). The LLM explains, grounded in catalog `rationale` text |
| IDs in state, values in the DB | Self-contained checkpoints | One source of truth; no personal values duplicated into state |
| Routing signals as results, not counters | Flexible retry counts in the graph | The graph shape encodes the policy (OTP fail → document → agent); counts live in the DB |
| Node writes and checkpoint save in separate transactions | Atomicity | LangGraph saves checkpoints on its own connection. Idempotent writes (deterministic IDs, idempotency key) make re-runs safe |
| Keep ineligible recommendations as rows | Smaller tables | The agent can see why a product is missing |
| Needs assessments versioned, never edited | Simpler updates | Each recommendation keeps the exact assessment it was based on |
| One mock with fault injection | Testing against real partners | Deterministic tests and a repeatable demo of retries and handoff |

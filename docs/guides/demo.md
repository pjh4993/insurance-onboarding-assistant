# Demo walkthrough

Four seed customers (A–D) in [`contracts/seed-customers.json`](../../contracts/seed-customers.json) cover the main
paths through the graph. The mock recognises each seed customer by name and returns the same partner, identity
and LLM answers every time, so every run ends the same way. The outcomes below are from an end-to-end run
through `docker compose`.

## 1. Start

```bash
docker compose up --build
```

1. Open the landing page at http://localhost:13000 and pick the market (KR for A and B, US for C and D), then
   click start. This is the customer's view. The session lives in a cookie, and one browser holds one customer
   session at a time: to run two customers side by side, use a second browser or a private window.
2. Open the agent console at http://localhost:13000/agent in another window. Locally the agent is `agent-demo`
   (development auth, `AGENT_DEV_AUTH=true`). Sessions started on the landing page show as **Self-serve**.
3. An agent can also create a session for a customer: **New session** in the console gives a link `/s/{token}`
   to send them (shown as **Link** in the list).
4. Keep the agent console open next to it. The session appears in the list and updates live (SSE): stage and
   what the graph is waiting for, and on the detail view the current node and entities.

In the customer tab, enter the seed customer's name, email, phone, ID document type and number from the seed
file, and tick the consent box for customer A. When asked about needs, type the seed's `needs_text`. When asked
who is insured, answer that it is just you. When asked for application details, any reply works: the mock
returns that customer's fixed answers.

## 2. Seed customers and expected outcomes

| | Market | Identity path | Needs | Expected outcome |
|---|---|---|---|---|
| **A** 김하늘 | KR | Partner match | New Galaxy phone, worried about breakage | `SUBMITTED`: `KR-MOB-SWAP` at ₩9,990/month |
| **B** 이서준 | KR | No partner record → any OTP but `000000` passes | Trip to Japan, 3–7 October | `SUBMITTED`: `KR-TRV-OVERSEAS` at ₩6,750 for 5 days |
| **C** Jane Doe | US | OTP `000000` fails → passport check passes | $1,299 laptop, accident cover | `SUBMITTED`: `US-DEV-LAPTOP-2Y` at $130 one-time |
| **D** John Roe | US | OTP `000000` fails → document fails | "I need phone insurance." | `HANDOFF` after identity; after the agent verifies, `HANDOFF` again after 3 needs rounds |

Submission references look like `SUB-2026-000001` and count up per mock run.

No SMS is sent. The identity mock accepts every OTP code, for any phone number, except `000000`: type `000000` to
take the OTP failure path.

### A: partner match with purchase pre-fill

1. Identity: give A's details **with consent**. `verify_identity` matches A in the partner system, so no OTP is
   sent. `verification_method = PARTNER_MATCH`, and the date of birth comes from the partner record.
2. `fetch_purchases` loads A's order: Samsung Galaxy S26, bought and activated 2026-09-14, ₩1,350,000. It becomes an
   `InsurableObject` with `source = PARTNER`.
3. Needs: "서른다섯 살 소프트웨어 엔지니어고 서울 살아요. 새로 산 갤럭시 폰이 깨질까 봐 걱정돼요." (35, software engineer,
   Seoul, worried the new Galaxy will break). `assess_needs` extracts age range 30–39, occupation, `KR`,
   `PROTECT_DEVICE`. The customer is not asked about the device: the partner already supplied it.
4. Recommendation: `KR-MOB-SWAP` is the eligible product, ₩9,990/month (the ₩1,000,001–1,500,000 tier; the
   purchase price stands in for the MSRP). The other KR products appear in the agent view as ineligible, each with
   its failure reason.
5. Accept → parties (all self) → the application answers (IMEI, model, price, activation date) are all
   pre-filled from the partner record, so no product questions are asked → summary → confirm → submission
   reference.

### B: OTP and a customer-described trip

1. No partner record, so the identity system sends an OTP. Enter any code but `000000`, e.g. `123456`.
   `check_otp` returns `OTP_OK`.
2. Needs: 40, office worker, travel insurance for Japan, leaving 3 October and back 7 October. `assess_needs`
   creates a `TRIP` object from the text.
3. `KR-TRV-OVERSEAS` is priced per day: 5 days × ₩1,350 = ₩6,750 for the trip.
4. Accept → parties → the application asks for the traveller details it does not have yet (for example gender
   and date of birth, since the OTP path has no verified birth date) → summary → confirm → submitted.

The graph supports other insured persons and payers (`collect_parties` creates a `Party` for each, without identity
checks), but the mock always answers "all self", so the demo does not show it.

### C: OTP fails, document succeeds

1. No partner record. Enter `000000`, the code the mock turns down (`OTP_FAILED`).
2. The graph moves to `check_document` with the passport number C gave at the start. It passes (`DOC_OK`,
   `verification_method = DOCUMENT`). One failed attempt is recorded.
3. Needs: "I'm 36, a nurse in Seattle. I just bought a $1,299 laptop and want accident cover." The US laptop
   protection product is priced from its purchase-price tier: $130, paid once.
4. The application asks only for what it does not know (serial number, order number, purchase date); the price
   is pre-filled from the needs answer. Confirm → submitted.

### D: two failures, then an agent

1. Enter `000000`: the OTP fails, then the driver's licence check fails (`DOC_FAILED`). That is two failures.
2. `human_handoff` sets `stage = HANDOFF`, `waiting_for = AGENT` and `handoff_reason = IDENTITY_FAILED`;
   `await_agent` pauses. The session status becomes `HANDOFF` and it jumps to the top of the agent's session list.
3. In the agent console, open the session and take it over (**Assign to me**). The session is now `ASSIST` and assigned
   to the agent.
4. The agent resolves the handoff:
   - `VERIFIED`: the agent checked the customer another way. `verification_method = AGENT`, and onboarding
     continues with profiling.
   - `CONTINUE`: identity starts again from the first question, with the attempt count reset.
   - `END`: the session ends as `WITHDRAWN`.
5. After `VERIFIED`, "I need phone insurance." is too thin: the age range and the phone's price are missing, so
   `assess_needs` asks for them. The mock's fixed answer for D never fills them, so after the third answer the
   loop guard hands off again with `NEEDS_INCOMPLETE`. This is the expected end of the D run. The agent can answer on
   the customer's behalf at any point; those inputs are recorded with `captured_by = AGENT`.

## 3. Error handling

The mock can fail on demand:

```bash
# the next 5 contract-admin calls return 500
curl -X POST http://localhost:18080/_mock/faults \
  -H 'Content-Type: application/json' \
  -d '{"target": "contract", "kind": "500", "count": 5}'

# list armed faults
curl http://localhost:18080/_mock/faults

# clear all faults and state
curl -X POST http://localhost:18080/_mock/reset
```

- `target` is `partner`, `identity`, `contract` or `bedrock`; `kind` is `timeout`, `500` or `429`; `count` is
  1–100; `delay_seconds` is optional.
- Each retrying node makes 3 attempts. With `count` below 3 on `partner`, `identity` or `contract`, the retry
  policy absorbs the failures and the customer notices only a delay. With `count` of 3 or more, the node's
  retries run out: the session goes to `human_handoff` with `handoff_reason = ERROR`, and the agent sees which
  node failed.
- The AWS SDK also retries Bedrock errors on its own before the node sees them, so a `bedrock` fault needs a
  larger `count` to exhaust the node's retries.
- After clearing the fault (`/_mock/reset`), the agent resolves with `CONTINUE` and the failed node runs again
  with the input it had. `/_mock/reset` also clears OTP requests and submissions held by the mock.

## 4. Other things to try

| Try | Expected |
|---|---|
| After seeing recommendations, choose to change your answers and give different needs | A new `NeedsAssessment` version; old recommendations and quotes become `EXPIRED`; new ones are shown |
| Decline the recommendations | Eligible recommendations become `DECLINED`; the session ends as `DECLINED` |
| Close the customer tab mid-flow and reopen the same link | The chat continues from the same question: the graph was paused in the checkpoint |
| At the summary, say something needs fixing | The graph goes back to collecting answers, then shows a new summary |
| Send input of the wrong type, or twice in a row, through the API | `409`: the session is waiting for something else, or is still processing |
| Inspect the `checkpoint` schema in PostgreSQL (`localhost:15432`, user/password `onboarding`) | Blobs in `checkpoint_blobs` and `checkpoint_writes` have types ending in `+aes`; names, phone numbers and needs text are not readable. Plain values such as `stage` are visible in `checkpoints` |

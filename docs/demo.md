# Demo walkthrough

Four seed customers (A–D) in [`contracts/seed-customers.json`](../contracts/seed-customers.json) cover the main
paths through the graph. The mock returns fixed answers for each of them, so every run is the same.

## 1. Start

```bash
docker compose up --build
```

1. Open the agent console at http://localhost:13000/agent. Locally the agent is `agent-demo` (development auth).
2. Click **New session** and pick the market (KR for A and B, US for C and D). The console shows the customer
   link `/s/{token}`.
3. Open that link in another tab or window. This is the customer's view.
4. Keep the agent console open next to it. The session appears in the list and updates live (SSE): stage,
   what the graph is waiting for, and on the detail view the current node and entities.

In the customer tab, enter the seed customer's name, email, phone, ID document type and number from the seed
file, and tick the consent box when the scenario needs a partner lookup. Then type the `needs_text` from the
seed file when asked about needs.

## 2. Seed customers

| | Market | Identity path | Needs | What it shows |
|---|---|---|---|---|
| **A** 김하늘 | KR | Partner match | New Galaxy phone, worried about breakage | Consent-based partner lookup, device pre-filled from purchases, Korean extraction |
| **B** 이서준 | KR | No partner record → OTP `000000` | Trip to Japan, 3–7 October | OTP path, trip described by the customer |
| **C** Jane Doe | US | OTP fails → passport check passes | $1,299 laptop, accident cover | Fallback to document check, USD market |
| **D** John Roe | US | OTP fails → document fails | "I need phone insurance." | Handoff to an agent after two failures |

### A: partner match with purchase pre-fill

1. Identity: give A's details **with consent**. `verify_identity` matches A in the partner system
   (`PARTNER_MATCH`), so no OTP is sent.
2. `fetch_purchases` loads A's order: Samsung Galaxy S26, bought and activated 2026-09-14, ₩1,350,000. It becomes an
   `InsurableObject` with `source = PARTNER`.
3. Needs: "서른다섯 살 소프트웨어 엔지니어고 서울 살아요. 새로 산 갤럭시 폰이 깨질까 봐 걱정돼요." (35, software engineer,
   Seoul, worried the new Galaxy will break). `assess_needs` extracts age range 30–39, occupation, `KR`,
   `PROTECT_DEVICE`. The customer is not asked about the device: the partner already supplied it.
4. Recommendation: the Korean mobile product ranks first with a monthly price from its tier table. Products that
   do not fit appear in the agent view as ineligible, each with its failure reason.
5. Accept → application: parties (all self), product answers, summary, confirm → submission reference
   `SUB-YYYY-NNNNNN`.

### B: OTP and a customer-described trip

1. No partner record, so the identity system sends an OTP. Enter `000000`. `check_otp` returns `OTP_OK`.
2. Needs: 40, office worker, travel insurance for Japan, leaving 3 October and back 7 October. `assess_needs`
   creates a `TRIP` object from the text.
3. The Korean overseas travel product is priced per day of the trip.
4. In the application stage, `collect_parties` asks whether anyone else is insured (for example a travel
   companion). Another person becomes a new `Party` with name and date of birth, without identity checks.

### C: OTP fails, document succeeds

1. No partner record. Any OTP code fails (`OTP_FAILED`).
2. The graph moves to `check_document` with the passport number C gave at the start. It passes (`DOC_OK`,
   `verification_method = DOCUMENT`). One failed attempt is recorded.
3. Needs: "I'm 36, a nurse in Seattle. I just bought a $1,299 laptop and want accident cover." The US laptop
   protection product is priced from its purchase-price tier in USD.
4. If the extraction misses a detail the product needs, the graph asks only for that field.

### D: two failures, then an agent

1. OTP fails, then the driver's licence check fails (`DOC_FAILED`). That is two failures.
2. The graph pauses at `human_handoff`. The session status becomes `HANDOFF`, `waiting_for = AGENT`, and it jumps to
   the top of the agent's session list.
3. In the agent console, open the session and take it over (`assign`). The session is now `ASSIST` and assigned
   to the agent.
4. The agent resolves the handoff:
   - `VERIFIED`: the agent checked the customer another way. Onboarding continues with profiling.
   - `END`: the session ends.
5. After `VERIFIED`, "I need phone insurance." is too thin, so `assess_needs` asks again for the missing fields.
   The agent can answer on the customer's behalf; those inputs are recorded with `captured_by = AGENT`.

## 3. Error handling

The mock can fail on demand:

```bash
# the next 5 Bedrock calls return a throttling error
curl -X POST http://localhost:18080/_mock/faults \
  -H 'Content-Type: application/json' \
  -d '{"target": "bedrock", "kind": "429", "count": 5}'

# clear all faults and state
curl -X POST http://localhost:18080/_mock/reset
```

- With a small `count`, the node's retry policy absorbs the failures and the customer notices only a delay.
- With a `count` larger than the retry budget, the node sets `last_error` and the session goes to
  `human_handoff`. The agent sees which node failed and resumes with `CONTINUE` once the fault is cleared.
- `target` can also be `partner`, `identity` or `contract`, with `kind` `timeout`, `500` or `429`.

## 4. Other things to try

| Try | Expected |
|---|---|
| After seeing recommendations, choose to change your answers and give different needs | A new `NeedsAssessment` version; old recommendations and quotes become `EXPIRED`; new ones are shown |
| Close the customer tab mid-flow and reopen the same link | The chat continues from the same question: the graph was paused in the checkpoint |
| At the summary, say something needs fixing | The graph goes back to collecting answers, then shows a new summary |
| Inspect the `checkpoint` schema in PostgreSQL (`localhost:15432`, user/password `onboarding`) | Checkpoint blobs are compressed and encrypted; phone numbers and names are not readable |

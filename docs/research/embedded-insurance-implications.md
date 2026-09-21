# What Embedded Insurance Means for the Assignment Structure

_Research note, translated from the Korean design wiki._

This note applies the fact that bolttech works in an embedded model to the assignment's four
stages. Researched 2026-09-15.

The assignment text does not use the word "embedded". This note is an **interpretation** drawn
from bolttech's business model. If adopted, it goes in Assumptions.

## What bolttech does

Summarized from the bolttech homepage.

- A B2B2C platform that lets any business put insurance products into its own customer journey
- Connects insurers, distribution partners, and end customers through a single API
- Programs: mobile devices, health tech, home, travel, cyber, mobility, appliances
- Scale: 39 markets, 700+ partners, 7,000+ products
- Tagline: "Connecting the world to the right insurance at the right time"

The assignment's product examples (Device Protection, Travel Protection, Extended Warranty,
Mobile Insurance) overlap with this lineup.

Source: [bolttech.io](https://bolttech.io/)

## What changes because it is embedded

The partner (carrier, retailer, bank, travel agency) already holds customer information and
purchase context. So much of the four stages is filled without asking the customer.

| Stage | Traditional insurer | Embedded | Evidence |
|---|---|---|---|
| Identity verification | Customer verifies directly | Receive the identity the partner already verified (carrier subscriber, bank customer) and **only match it** | Asurion signs up through the carrier, Kakao signs up inside the KakaoTalk account, XCover leaves it to the partner |
| Profiling | Collected through questions | Transaction data (device model, purchase date, price, destination and itinerary) **is the profile**. Ask only for empty fields | XCover takes transaction type, region, amount, and item as input |
| Recommendation | Recommend after consultation | **The moment of purchase is the trigger**. Device protection for a phone activation, travel insurance for a flight ticket. The eligibility window is also computed from partner data | "right insurance at the right time", Asurion 30-day sign-up window |
| Application | Fill in an application form | **Pre-filled** from partner data. Fewer missing fields, and device registration can be deferred to claim time | Bolt takes IMEI registration at claim time |

The sources and verification level of the evidence are in
[competitor-onboarding-flows.md](competitor-onboarding-flows.md).

## If applied to the assignment

These are candidates, not decisions yet.

- **Take partner context as input.** When a retail staff member opens a customer's device
  purchase, a mock partner API passes the customer information and purchase information. This
  matches the assignment's support-agent setting.
- **Record the source of each field in state.** Distinguish values the partner verified, values
  the customer stated, and inferred values. Identity verification and missing-field checks then
  change from filling blanks to checking confidence by source.
- **Keep eligibility rules as deterministic nodes.** Code judges conditions such as purchase date,
  release date, and country. The LLM handles only conversation and explanation.

## Cautions

- Receiving partner data requires **consent to provide personal information to a third party**.
  A post says that consenting to the Toss "My insurance lookup" terms passes information to agents
  and leads to complaints (only the search summary was checked).
- If the Identity Verification step the assignment requires is reduced to "partner identity
  matching", it may read as a shallow implementation of that step. It is safer to also show a
  branch that falls back to direct verification when matching fails.

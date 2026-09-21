# Assumptions

The brief leaves several points open on purpose ("the implementation approach is up to you", "the architecture
is intentionally not prescribed"). These are the calls we made and why.

## 1. Interpretation of the brief

| # | Open question | What the brief says | Our assumption |
|---|---|---|---|
| 1 | Who is the "agent"? | "helps support agents guide customers" | A human customer-support employee, not an AI agent |
| 2 | Who uses the screens? | Page 4 lists both a "customer onboarding interface" and "support agent interaction" | **Both.** The customer uses the chat directly. An agent watches all sessions and takes over when the customer gets stuck, or types on the customer's behalf (for example during a phone call). Every input records who gave it (`captured_by`: `CUSTOMER` or `AGENT`) |
| 3 | When is identity verified? | "verify customer identity **before onboarding**" | **First.** Identity must be `VERIFIED` before any profiling. Nothing personal is shown or reused before that |
| 4 | Is the product embedded in a partner's checkout? | The word "embedded" does not appear; the product examples match bolttech's partner business | **No embedded premise.** Onboarding starts with a conversation. The partner system does not push customer data to us; the assistant **looks up** the partner's purchase records when useful, and only with the customer's consent |
| 5 | How is identity verified? | "The implementation approach is up to you" | Three steps in order: partner record match → OTP to the phone → ID document number check. Two failures (OTP + document) hand off to an agent |
| 6 | Does the application go to another system? | The brief ends at submission | The finished application is sent to a contract admin system, which returns a submission reference. Underwriting and policy issuance are out of scope |
| 7 | How are external systems called? | Not specified | Develop runs one mock service with the same API shapes as the real systems; prod points to real endpoints. Only environment variables differ |

## 2. Domain decisions

| # | Topic | Assumption |
|---|---|---|
| 8 | Partner lookup consent | Consent to share data with a third party is collected together with the identity details and stored as `Party.third_party_consent_at`. Without it the partner match and purchase lookup are skipped; the customer is verified by OTP and describes the device themselves. Onboarding continues either way |
| 9 | Other parties | The insured person and the payer can differ from the customer (a travel companion, a child's phone). They are collected in the **application** stage by `collect_parties`, get their own `Party` with name and date of birth, and are **not** identity-verified. By default all roles are the customer |
| 10 | Identity attempts | Only the number of failed attempts is kept (`Party.verification_attempts`). One OTP failure plus one document failure = two failures → agent |
| 11 | Markets | Two markets: Korea (KRW) and the United States (USD). The market is chosen when the session is created. A residence rule on every product restricts it to one country |
| 12 | Product types | The four examples in the brief: Device Protection, Travel Protection, Extended Warranty, Mobile Insurance. Eight seed products = 2 markets × 4 types |
| 13 | Catalog values | Seed prices, coverages and eligibility rules are modelled on public products and are **not** bolttech's real rates or rules. Generic names are used, except bolttech's own products |
| 14 | Eligibility, ranking, pricing | Done by code from catalog data, never by the LLM. Ineligible products are still recorded with their failure reasons so the agent can see why |
| 15 | Quotes | A `Quote` is a separate entity. It is valid for 24 hours but never past 00:00 of the coverage start date. An expired quote is recalculated |
| 16 | Coverage term | A rule per product: travel covers departure to return, extended warranty starts when the manufacturer warranty ends, most products start on the purchase date |
| 17 | Billing period | A property of the product: monthly, one-time or per trip. `premium_minor` is the amount per period |
| 18 | Needs changes | A `NeedsAssessment` is never edited. A change creates a new version, and recommendations based on the old version expire |
| 19 | Returning customers | Designed but deferred: a new session could be linked to an existing `Party` only **after** identity is verified, using a verified key (partner reference, ID number HMAC, or OTP-verified phone + date of birth). Matching on email before verification would leak someone else's data |
| 20 | `Policy` | Named but has no fields. The contract admin system owns it |
| 21 | Money and time | Money is an integer in minor units plus an ISO 4217 currency. Times are ISO 8601 UTC |

## 3. Technical assumptions

| # | Topic | Assumption |
|---|---|---|
| 22 | Two services | "Two separate services" = two separately deployed ECS services: frontend and backend. The customer app and the agent console are two apps inside the frontend service |
| 23 | LLM | Amazon Bedrock, Claude Sonnet 4.6 via global cross-region inference from Seoul. Tests never call the real model; they use the mock |
| 24 | Region | One region, ap-northeast-2 (Seoul) |
| 25 | Environments | One AWS account with develop and prod, each with its own VPC and Terraform state |
| 26 | Agent login | Cognito in AWS once a domain exists. Until then a development header identifies the agent |
| 27 | Customer login | No account. A per-session link with a random token |

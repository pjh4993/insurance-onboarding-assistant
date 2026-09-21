# Insurance Customer Journey Models

_Research note, translated from the Korean design wiki._

This note summarizes how the insurance industry divides the customer journey. Researched
2026-09-15.

Both sources are **vendor marketing articles**. We did not review industry-standard documents
(ACORD, etc.).

## Full lifecycle — EIS Group

EIS Group, an insurance core-system vendor, divides the journey into six stages.

```
Awareness → Consideration → Purchase → Onboarding → Post-Purchase Support → Renewal
```

Here, Onboarding is the stage **after purchase** where the customer is walked through the policy
and terms. It is narrower than what the assignment calls onboarding. From a lifecycle view, they
divide it again into Onboarding → Billing & Payments → Policy Updates → Support → Claims →
Renewal → Advocacy.

Source: [What is the customer journey in insurance? — EIS Group](https://www.eisgroup.com/what-is-the-customer-journey-in-insurance/)

## Onboarding segment — ibapplications

ibapplications, an insurance SaaS vendor, sees onboarding as "a corridor that you enter from
product selection and exit at first policy activation". It explicitly excludes claims, mid-term
changes, and renewal from onboarding.

### 7 stages

| # | Stage | Owner | KPI |
|---|---|---|---|
| 1 | Needs assessment / product selection | Sales, product | Needs-assessment completion rate |
| 2 | Data capture / pre-validation | Operations, IT | Data error rate at submission |
| 3 | Identity verification / KYC pathing | Compliance | KYC pass rate, verification time, EDD escalation rate |
| 4 | Risk scoring / pricing | Underwriting | Time to quote, manual-review escalation rate |
| 5 | Digital acceptance / payment | Product, payments | Payment completion rate |
| 6 | Policy issuance | IT, policy administration | STP rate, time to issue |
| 7 | Welcome / activation | CX | Activation rate within 48 hours |

The same article's 4-stage summary: eligibility check and needs assessment → identity
verification and risk assessment → acceptance and policy issuance → activation.

### Points useful for the assignment design

- **Split the KYC path by risk.** Send low-risk customers down a light path, and apply enhanced
  verification (EDD) only when the risk score requires it. The article names this the biggest
  lever for reducing drop-off.
- **Design the failure paths first.** It recommends running expired documents, liveness failures,
  and AML hits end to end in a sandbox. As an example, it gives a rule that sends a case straight
  to a designated agent queue after two liveness failures or an AML hit.
- **Save and resume.** Give a save-and-resume link so the application is not lost when the session
  drops.
- **Audit trail.** If you cannot record the needs-assessment completion time, the version of the
  product disclosure document delivered, and the AML screening result, you cannot prove compliance
  in a regulatory review.
- **Order.** In this model, needs assessment comes before identity verification. This is the
  reverse of the stage numbering in the assignment text (see "When does identity verification
  happen" in the assignment brief).

Source: [Customer onboarding process in insurance: a Central Europe playbook — IBA](https://ibapplications.com/content-library/blog/customer-onboarding-process-in-insurance/) (2026-07-31)

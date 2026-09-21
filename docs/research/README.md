# Research

What was looked up before the design was fixed, kept as found. These notes are evidence, not decisions; the table
says where the design agrees with a finding and where it went the other way. All were researched between
2026-09-15 and 2026-09-21 from public sources only (no logins, no quote forms, no personal data entered), and
translated from the Korean design wiki.

| Note | Question it answers | How the design relates |
|---|---|---|
| [Insurance journey models](insurance-journey-models.md) | How does the industry split the customer journey, and where does onboarding sit in it? | The IBA playbook puts needs assessment before identity; the design keeps the brief's order, identity first ([LangGraph design §1](../design/02-langgraph-design.md#1-the-four-stages)). Two of its points match the design: resumable sessions, and failures routed to a person (`human_handoff`) |
| [Competitor onboarding flows](competitor-onboarding-flows.md) | How do Korean insurers, insurance platforms and bolttech's competitors actually take an application, stage by stage? | Three of its seven implications match the design: code judges eligibility and the LLM only explains, a question loop for missing information (3 rounds, then handoff), and an agent who takes over in the console ([LangGraph design §2–5](../design/02-langgraph-design.md#2-nodes-by-type)) |
| [Embedded insurance implications](embedded-insurance-implications.md) | bolttech sells through partners at the point of purchase: what would that change in the four stages? | **Not adopted as a premise** ([assumptions #4](../decisions/assumptions.md#1-interpretation-of-the-brief)): onboarding starts with a conversation, and the partner's purchase records are looked up only with third-party consent, falling back to OTP without it (#8), matching the cautions at the end of the note |
| [Catalog research](catalog-research.md) | What do real device, travel, warranty and mobile products look like in Korea and the US: coverage, prices, exclusions? | The eight-product seed ([data model §5](../design/04-data-model.md#5-product-catalog-seed)) |

Read them in that order: the journey models frame the stages, the competitor flows show how each stage is done
in practice, the embedded note says what bolttech's model changes, and the catalog research grounds the products.

Source quality varies. Each note states its own: several rely on vendor marketing pages, press articles or
secondary listings rather than primary documents, and say so where they do.

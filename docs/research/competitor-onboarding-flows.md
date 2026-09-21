# Onboarding Flows by Company

_Research note, translated from the Korean design wiki._

This note uses the assignment's four stages (identity verification → profiling → recommendation →
application) to compare how Korean insurers, Korean insurance platforms, and bolttech competitors
actually take sign-ups. Researched 2026-09-15.

We did not enter screens that require login, identity verification, or personal data entry. We
checked them through public guide pages, news articles, and first-hand reviews.

## Evidence level

Each item notes how its evidence was checked.

| Mark | Meaning |
|---|---|
| **Primary** | We read the body of the official page directly |
| **Article** | We read the body of a news article or first-hand review |
| **Summary** | We saw only the search-result summary and could not open the original |

## Comparison table

| Company | Identity verification | Profiling | Recommendation | Application |
|---|---|---|---|---|
| Toss Insurance | Web: mobile-carrier identity verification when requesting a consultation. App: consent step | Existing-policy lookup → report on duplicate and missing coverage. Consultation confirms basic information and treatment history | Agent sorts products from about 30 insurers with the "Product Navigator" and sends a quote sheet by chat | E-signature link: Financial Consumer Protection Act disclosure check → comparison confirmation form → e-signature → policy issued |
| Hanwha Life Direct | No separate front step. Conditions: policyholder in person, ID card, account in own name | None. Customer picks the product | Customer picks options; consultation on request | Application form (customer info + disclosure items) → payment (e-signature) → application complete → underwriting → KakaoTalk notification |
| Hanwha Life GA platform | — | — | — | Shows agent and customer steps separately, shows progress, tablet ↔ smartphone handoff |
| Mirae Asset Life | Identity verification in complete-sale monitoring after sign-up | FC sends a suitability-assessment URL by KakaoTalk notification and receives the result | FC | Application document supplements on mobile: KakaoTalk notification → photo → submit |
| KakaoPay Insurance | Runs inside the KakaoTalk account; travel insurance needs no separate documents or certificate | Travel insurance: applicant aged 19–99, companions aged 0–99 | Friend-invite discount | Phone insurance: Galaxy and iPhone released within 2 years; parents sign up for minor children's phones |
| Asurion | Carrier customer information | — | — | Sign up within 30 days of activation or device change, in store or online |
| Cover Genius (XCover) | Handled by partner | Receives transaction data (transaction type, region, amount, item) via API | Pricing engine returns coverage options | Quote → purchase → certificate → claim via API |
| Bolt device protection | Account activated through purchase email | — | — | Device registration (IMEI + billing statement) taken at claim time |

## Company details

### Toss Insurance

It is an insurance agency (GA). When a customer applies, it connects them to one of its agents.

1. Toss app "Insurance" → "Check history" → "Request premium check" → consent. **Article**
2. A "My insurance check report" arrives by KakaoTalk. It shows the premium level relative to
   coverage and the duplicate and missing items. **Article**
3. An agent makes contact within 1–3 weekdays. The customer chooses phone or KakaoTalk.
   **Article**
4. The agent sorts products from about 30 insurers with the "Product Navigator" and sends a quote
   sheet. **Article**
5. In the e-signature link, the customer checks the Financial Consumer Protection Act disclosure,
   downloads the comparison confirmation form, and signs, in that order. Once approved, the policy
   and terms are issued. **Article**

In August 2026 the website was redesigned and now takes applications without the app. "Get a
consultation" → mobile-carrier identity verification → KakaoTalk notification check → agent
matched within 1–2 days. **Summary**

This is the closest in structure to the assignment's "assistant helps support agents". The tool
sorts the products and a person makes the final recommendation.

Separately, a post says that consenting to the "My insurance lookup" terms passes information to
agents and leads to complaints about unwanted contact. **Summary** (TILNOTE)

Sources:
[Opinion News first-hand review](https://www.opinionnews.co.kr/news/articleView.html?idxno=123770),
[Ezy Economy](https://www.ezyeconomy.com/news/articleView.html?idxno=238571),
[Digital Times](https://www.dt.co.kr/article/12077688),
[tossinsu.com](https://tossinsu.com/)

### Hanwha Life

**Direct channel** — The official page states the sign-up conditions and steps. **Primary**

- Conditions: only the policyholder in person can sign up, with a resident registration card or
  driver's license, and an account in their own name
- Steps: product design → application form (customer information, pre-contract duty-of-disclosure
  items) → premium payment (review guidance material, enter own account, e-signature) →
  application complete (key documents sent by email) → underwriting → contract outcome sent by
  KakaoTalk notification
- About 10 minutes from product design to application complete
- The application can be withdrawn within 15 days of receiving the policy

Identity verification is not a separate front step. It is mixed into the application and payment.

**GA agent platform** — Handles customer management, consultation, design, application, and
contract management in one place. **Article**

- The e-application screen shows the agent's steps and the customer's steps separately and shows
  progress
- An e-application started on a tablet can be continued on a smartphone
- They stated a plan to add AI in phases but did not disclose specific features

A reference case for designing the assignment's workflow visibility.

Sources:
[Hanwha Life Direct sign-up guide](https://direct.hanwhalife.com/app/guidance),
[Economy Science](https://www.e-science.co.kr/news/articleView.html?idxno=134977),
[Financial Today](https://www.ftoday.co.kr/news/articleView.html?idxno=365034)

### Mirae Asset Life

- **Suitability assessment**: The FC sends an assessment URL by KakaoTalk notification, the
  customer completes it in a few taps, and the result goes back to the FC. This is a legally
  required step before signing up for variable insurance. **Summary**
- **Application document supplements**: When a supplement is needed, the customer is notified by
  KakaoTalk notification and submits a photo of the document. The company said this finishes in
  under 10 minutes work that usually took 15–30 days (reported November 2019). **Summary**
- **Complete-sale monitoring**: After sign-up, it runs as identity verification → contract
  selection → confirmation. **Summary**

The **supplement loop** that gets missing information back corresponds to the assignment's
"Identify missing information".

Sources:
[Korea Banker (Daehan Financial Newspaper)](https://www.kbanker.co.kr/news/articleView.html?idxno=87491),
[Pax Economy TV](https://www.paxetv.com/news/articleView.html?idxno=81894)

### KakaoPay Insurance

This overlaps most directly with the assignment's product examples (Travel Protection, Mobile
Insurance).

- **Overseas travel insurance**: Sign up via KakaoTalk → More → KakaoPay → Insurance tab. No
  separate documents or certificate are needed. The applicant must be aged 19–99 and companions
  aged 0–99. A companion's English name and date of birth must match the passport to receive a
  payout. Signing up together with KakaoTalk friends gives a 5% discount for 2 people and 10% for
  3 or more. **Summary** (blog)
- **Phone insurance**: Covers Galaxy (including kids' phones) and iPhone released within 2 years,
  regardless of carrier. From February 2026, parents can also sign up and pay for minor children's
  phones. **Summary**

**Not confirmed**: How device condition is checked at phone-insurance sign-up (photo,
self-diagnosis, IMEI). The product page is rendered by JavaScript, so we could not read its body.

Sources:
[How to sign up for travel insurance](https://tripyeyak.com/kakaotalk-travel-insurance/),
[Trip.com](https://kr.trip.com/insurance/provider/kakaopay/travel-insurance),
[Daum News](https://v.daum.net/v/20260224092448851)

### Asurion — bolttech competitor

- Sign-up is only possible **within 30 days** of activation or device change. Consumer Cellular
  allows 60 days. **Summary**
- Sign-up goes through the carrier. Verizon takes it both in store and online. **Summary**
- It also supports retailers with in-store POS, staff training, and marketing. **Summary**

Sources:
[Verizon Mobile Protect FAQs](https://www.verizon.com/support/verizon-mobile-protect-faqs/),
[PR Newswire](https://www.prnewswire.com/news-releases/asurion-retail-solutions-helps-retailers-simplify-product-protection-plans-registration-for-electronics-and-appliances-300233629.html)

### Cover Genius (XCover) — bolttech competitor

- The partner calls the API with transaction type, customer region, purchase amount, and product
  category, and the pricing engine returns coverage options as JSON. **Summary**
- Quote, purchase, certificate delivery, and claims (XClaim) are handled via API. **Summary**

There is no profiling step that asks the customer questions. The transaction data is the profile.

Sources:
[XCover](https://covergenius.com/platform/xcover/),
[Travix Lab](https://travixlab.com/integrations/xcover-insurance-integration)

### Bolt device protection

- After purchase, the account is activated through a link in the welcome email. **Summary**
- Device registration happens **at claim time**, not at sign-up. The customer uploads the IMEI
  and a billing statement showing the device was on the network at the time of the incident.
  **Primary**
- Claims are approved instantly based on the information the customer entered and the
  eligibility conditions. **Primary**

Source: [Bolt Device Protection (VYRD)](https://protect.boltinsurance.com/vyrd/)

## Implications for the assignment design

1. **Where identity verification sits differs by channel.** It trusts the platform account
   (Kakao), merges into application and payment (Hanwha Direct), or is taken when a consultation
   is requested (Toss). This can be designed as a branch that sets verification strength by
   product risk.
2. **The key profiling input is existing insurance.** Both Toss and Hanwha use duplicate and
   missing coverage analysis as the basis for recommendation. This matches the assignment's
   "Existing insurance coverage".
3. **A tool sorts the recommendations and a person decides.** The Toss structure matches the
   assignment's support-agent assist setting. The embedded approach (Cover Genius) recommends
   automatically from transaction data.
4. **Device insurance eligibility is judged by time windows.** Rules such as "released within
   2 years" and "within 30 days of activation" ground the eligibility node.
5. **Missing information is handled with a supplement loop.** Mirae Asset supplements and Hanwha
   underwriting are examples. In the graph, it is a conditional edge back to the collection node.
6. **Workflow visibility means task separation, progress, and handoff.** The Hanwha GA platform is
   the example.
7. **Put the regulatory steps into the application summary.** Financial Consumer Protection Act
   disclosure and comparison confirmation form (Toss), suitability assessment (Mirae Asset),
   15-day application withdrawal (Hanwha).

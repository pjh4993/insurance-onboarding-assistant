# Product catalog research: device, travel, warranty and mobile insurance (KR / US)

_Research note, translated from the Korean design wiki. It records what was found before the catalog seed was designed; the seed itself is in [data model §5](../design/04-data-model.md#5-product-catalog-seed)._

- Date checked: **2026-09-21** (all rows)
- Method: **Claude in Chrome was not connected** ("Browser extension is not connected"). Every row comes from **WebSearch / WebFetch** plus local `pdftotext` on public PDFs. No logins, no quote forms, no personal data entered.
- Source quality: **[P]** = primary (the provider's own page or PDF). **[S]** = secondary (a press article, retailer listing, review or comparison site). A WebFetch row was summarised by a small model. Where I could, I checked the numbers against the raw PDF text (AppleCare+, bolt, Himart).

---

## 1. Findings by market and product type

### 1.1 Korea: Mobile insurance (phone insurance)

| Field | **LG U+ Phone Swap Pass (폰교체 패스)** (run by **bolttech Korea**) | **Samsung Care+ (삼성 케어플러스) smartphone (Loss/Damage family)** |
|---|---|---|
| Provider | LG U+ as distributor, with bolttech (uplus.bolttech.kr) as operator | Samsung Electronics; the insurance is underwritten by a partner non-life insurer |
| Source | [P] https://uplus.bolttech.kr/kr/service-details/plan-details?type=pass ; [S] https://www.insurancebusinessmag.com/asia/news/breaking-news/bolttech-expands-into-south-korea-with-lg-u-partnership-236653.aspx (2020-10-20) | [P] https://www.samsungcareplus.co.kr/info/productInfo ; [P] https://www.samsungsvc.co.kr/solution/41090 |
| Covered events | Device swap for damage, malfunction, wear or change of mind (cross-brand allowed). Unlimited repairs at official service centres with a fixed deductible. **Loss is not clearly covered.** | Damage (unlimited claims), loss (1 per 365 days, 4–5 in total), battery replacement, cyber financial crime (up to ₩3,000,000), online-shopping fraud (up to ₩500,000) |
| Limits / deductible | Swap with return: **18% of MSRP, minimum ₩50,000**. Swap without return: **30% of MSRP, minimum ₩100,000** (50% in the first 3 months). **2 swaps**, one of which may be non-return. | Damage: **10–35% of repair cost, minimum ₩30,000**. Loss: **25–30% of device MSRP**. Fraud: 20% or ₩100,000, whichever is larger. |
| Eligibility | Samsung Galaxy and iPhone on LG U+. Enrollment window not stated on the page. | Galaxy only. Must enroll **within 60 days of first call/activation**. The "Damage+ After 60" ("파손+ After 60") variant allows enrollment on days 61–365 with a 7-day waiting period. Refurbished units cannot get loss cover. |
| Pricing model | **Monthly, by device-price tier**: ₩5,990 (≤₩500k) · ₩7,990 (₩500k–1M) · ₩9,990 (₩1–1.5M) · ₩12,990 (₩1.5–2M) · ₩13,990 (₩2–2.5M) · ₩15,990 (>₩2.5M) · ₩13,990 (Fold/Flip) | **Monthly, by model**: Loss/Damage ₩6,000–14,500 · Loss/Damage Premium ₩7,900–16,900 · Premium+ ₩9,500–19,900 · Damage ₩4,500–9,900 · Damage+ ₩5,000–11,800 |
| Term / start | **36 months** | 24–60 months depending on product (smartphone commonly 36). Starts on enrollment. |
| Application fields | Not published. Carrier line, device model and IMEI are implied. | Device serial/IMEI, activation date and Samsung account (from the enrollment-guide page) |

Also seen (not tabled): SKT **T All Care+5 (T올케어+5)**. [S] https://www.ajd.co.kr/… (2026-05-29) lists ₩8,100/month for Galaxy S25 and ₩7,400 for iPhone 16. The limit is the lower of purchase price or ₩1.5M. The deductible is 25–30% of the loss, minimum ₩30,000. Terms run up to 60 months, and enrollment must be within 60 days of activation. The official T world product pages returned error PRD0047 to the fetcher.

### 1.2 Korea: Device protection (non-phone devices)

| Field | **Samsung Care+ notebook/tablet (Damage / Damage+)** | **AppleCare+ for Mac / iPad (Korea)** |
|---|---|---|
| Provider | Samsung Electronics / partner insurer | Apple Korea; the damage cover is underwritten by AIG |
| Source | [P] https://www.samsungcareplus.co.kr/info/productInfo | [P] https://www.apple.com/kr/applecare/ ; [S] https://namu.wiki/w/AppleCare%20Protection%20Plan |
| Covered events | Accidental damage (unlimited claims). Damage+ adds extended free repair. | Accidental damage (unlimited incidents), extended hardware warranty, priority support. **No theft or loss cover in Korea.** |
| Limits / deductible | 10–35% of repair cost, minimum ₩30,000 | Mac: screen or enclosure **₩79,000–120,000**, other damage **₩239,000–370,000**. iPad: screen **₩30,000**, other **₩120,000**. |
| Eligibility | Galaxy Book / Galaxy Tab. Enrollment window within 60 days of purchase for smartphones; assumed the same for notebooks. | Buy **with the device or within 60 days of purchase**. Apple Store may accept up to 1 year after purchase if the device passes inspection (namu.wiki). iPad eligible from 2025-09-10. |
| Pricing model | Monthly. Notebook Damage ₩7,200–8,400, Damage+ ₩8,800–9,900. Tablet Damage ₩2,400–4,300, Damage+ ₩2,700–4,600. | One-time, by model. **KRW prices were not captured**: the "All model prices" ("모든 모델 가격") table did not render in fetch. Secondary sources give roughly ₩100k–₩390k for Mac. |
| Term / start | 24–60 months (product dependent) | Mac 3 years, iPad 2 years, from plan purchase |
| Application fields | Serial number, purchase date, Samsung account | Serial number, proof of purchase, Apple Account |

### 1.3 Korea: Extended warranty

| Field | **Himart Care (warranty-extension type)**, Lotte Hi-Mart (롯데하이마트) | **Coupang Ansim Care (쿠팡안심케어)**, Coupang |
|---|---|---|
| Provider | Lotte Hi-Mart (seller), with **Lotte Non-Life Insurance (롯데손해보험)** as the partner for extended-warranty insurance | Coupang, with Lotte Non-Life Insurance |
| Source | [P] https://mstatic1.e-himart.co.kr/contents/content/upload/event/15532/MC/Himart_Care_Service_v11.pdf (terms v11) | [P] https://news.coupang.com/archives/36517/ (press release 2024-03-04) |
| Covered events | Repair of normal-use breakdowns **after the manufacturer warranty ends**. Covers parts, labour and transport. Unlimited claims until the total limit is used. | Repair of breakdowns after the manufacturer warranty. Unlimited claims within the total limit. Customer negligence is excluded. |
| Limits / deductible | Total limit by plan: ₩150k–₩5M. No deductible stated. | Total limit ₩100k–₩5M (22 plans). No deductible stated. |
| Eligibility | Must be bought **together with the product**; cannot be added after delivery. Personal use only (no corporate buyers). About 40 appliance/IT categories (fridge, TV, laptop, tablet, AC, …). | Rocket-installation items (TV, fridge, washer, dryer, AC, massage chair, dishwasher) from Samsung, LG, TCL, Haier and Xiaomi |
| Pricing model | **One-time, by coverage limit**: Care15 ₩4,000 · 30 ₩6,000 · 50 ₩7,000 · 75 ₩10,500 · 100 ₩14,000 · 150 ₩21,000 · 200 ₩28,000 · 250 ₩35,000 · 300 ₩42,000 · 350 ₩49,000 · 400 ₩56,000 · 500 ₩70,000. This is **1.4% of the limit** from Care75 upward. | One-time: **₩9,500 for a ₩1M limit, 3-year**; **₩13,500 for ₩1M, 5-year**. The release says premiums run about 1–2% of the limit. |
| Term / start | Up to **5 years including the manufacturer warranty**. The service starts on purchase or delivery date, but repair cover **applies from the manufacturer-warranty end**. | Total 3 or 5 years including the manufacturer warranty |
| Application fields | Product name, manufacturing number (serial), purchase date, full name, date of birth, phone number (listed in terms §2.6) | Order-linked. Not published separately. |

Samsung Care+ for home appliances/TV was checked. Its current pages only sell cleaning, filter-care and relocation services, and show no warranty-extension prices, so it was dropped.

### 1.4 Korea: Travel protection (overseas travel insurance)

| Field | **KakaoPay Insurance overseas travel insurance** | **DB Insurance Promy Direct overseas travel insurance (CM)** |
|---|---|---|
| Provider | KakaoPay Insurance | DB Insurance |
| Source | [P] https://contents.kakaopay.com/contents/2356 ; [S] https://kr.trip.com/insurance/provider/kakaopay/travel-insurance ; [S] https://www.insnews.co.kr/news/articleView.html?idxno=88132 (2025-12-24) | [P] https://www.directdb.co.kr/contents/contents.do?rtnUrl=cms/product/ltmgnrl/ovsetrvrarc.cms.product |
| Covered events / limits | Medical (injury and illness): DIY from **₩10M to ₩100M** each. Accidental death up to ₩600M. Baggage damage/theft (**loss excluded**): ₩400k–₩2M, **₩200k per item**. Flight delay (trip.com says 4 h+; KakaoPay page says from 2 h): up to ₩300k. Packages are Light, Basic and Plus. | Overseas injury/illness medical expenses, liability and flight delay: up to the sum insured. Personal-belongings damage: **₩200k per item, ₩10,000 deductible**. |
| Eligibility | Applicant aged 19–99. Insured aged 0–99. Up to 10 people who share the same itinerary. Trip up to **89 days**. Must depart from Korea. | Age **19–79**. Term **1–89 days** (max 3 months). Travel-ban / war-risk countries (MOFA level 3–4) excluded. Occupational risk grades 2–3 and extreme sports excluded. |
| Pricing model | Per trip, single premium. Sample: **₩1,850 for 4 days (Vietnam) with a ₩400k baggage-only cover, any age or gender**. Trip.com shows "from ₩5,394". Discounts: 5% repeat customer, 5% for 2 people, 10% for 3 or more. 10% cashback (up to ₩30k) on safe return. | Single premium (lump sum). **Price behind quote form.** |
| Term / start | From leaving home until return. Can be bought up to departure; cover starts 3 h after purchase. | Departure to return (1–89 days) |
| Application fields | Departure date/time, return date, destination, each traveller's name, date of birth and gender, applicant phone | Travel dates, destination, traveller date of birth/gender, purpose (quote form) |

### 1.5 US: Mobile insurance (phone)

| Field | **AppleCare+ with Theft and Loss (iPhone)** | **Verizon Mobile Protect** |
|---|---|---|
| Provider | Apple (AppleCare+). Theft and loss insured by AIG. | Verizon, administered by Asurion |
| Source | [P] https://www.apple.com/legal/sales-support/applecare/applecareplus/2509/250909_applecareplus_us_tl_disclosures_non-ny.pdf (Sept 2025 disclosure) ; [P] https://www.apple.com/support/products/iphone/ | [P] https://www.verizon.com/support/verizon-mobile-protect-faqs/ |
| Covered events | Unlimited accidental damage, hardware repair, battery below 80%, **theft and loss up to 2 claims per 12 months** | Cracked glass, accidental damage, loss, theft, malfunction. Unlimited claims per 12 months. |
| Limits / deductible | Screen or back glass **$29**, other damage **$99**, theft/loss **$149**. Maximum per claim is the device retail price. | Cracked-glass repair **$0**, damage replacement **$99**. Other fees vary by device (phoneclaim.com). **$3,000 maximum device value per occurrence.** |
| Eligibility | US resident. Device bought new from Apple or an authorised reseller. **Buy within 60 days of device purchase.** **Find My must be enabled.** Claims within 60 days of the incident. | Enroll **within 30 days** of activation, upgrade or BYOD, or during open enrollment (2026-09-03 to 11-01). Device health check: powers on, no screen damage, not reported lost. |
| Pricing model | **Monthly or annual or 24-month fixed, by model**. iPhone 17/16/15: **$11.99/mo, $119.99/yr, $219 per 24 mo**. 17 Pro / Pro Max: $13.99 / $139.99 / $269. SE: $7.99 / $79.99 / $149. 16e: $9.99 / $99.99 / $189. | **Monthly**: $16 or $19 per single device depending on device. Multi-device $38 (2), $57 (3), $68 (4–20). |
| Term / start | Starts on plan purchase date. Monthly/annual renews until cancelled; fixed term ends at 24 months. | Monthly, rolling |
| Application fields | Device serial number, proof of purchase, Apple Account with Find My | Verizon line / device (IMEI) and device health check |

Also seen: T-Mobile Protection<360>. Pages returned 403, so these numbers are [S] via Insurify/LegalClarity search snippets: $7–$26/mo by tier (Tier 6 = $26 from Mar 2026), Tier 5 damage $224 and loss/theft $179, $0 front-screen repair, up to 5 loss/theft claims per 12 months.

**bolttech in the US**: [P] http://protect.boltinsurance.com/wp-content/uploads/2022/12/Coverage-Details_Bolt-Mobile-Handset-Protection-MASTER-VERSION.pdf is a *template* "Coverage Details" for bolt Mobile Handset Protection. Administrator is Bolttech Device Protection Services LLC; obligor Ironwood Warranty; insurers Hornbeam / Lexington National. Its default placeholders: repair fee $49 / replacement fee $99 for phones under $500, $99 / $199 for phones $500 and up. Limits $1,000 per claim, $2,000 total, 2 claims per 12 months. Optional add-ons: accidental damage, shipping, battery. Fields: Plan #, purchase date, term, coverage start, wait period, auto-renew, monthly or installment. This is a useful schema reference but not a retail price.

### 1.6 US: Device protection (non-phone)

| Field | **Allstate Protection Plans: 2-Year Laptop with Accidents** (sold at Target) | **Asurion Home+** |
|---|---|---|
| Provider | Allstate Protection Plans (formerly SquareTrade) | Asurion |
| Source | [P-retail] https://www.target.com/p/2-year-laptops-protection-plan-with-accidents-coverage-1000-1499-99-allstate/-/A-51514183 ; https://www.target.com/p/allstate-2-year-laptops-protection-plan-with-accidents-coverage/-/A-51514192 ; terms [P] https://ebay.com/cdp/help/protection-plan/allstate_terms_us_04_2021 | [P] https://www.asurion.com/homeplus/faq/ |
| Covered events | Mechanical/electrical failure, drops, spills, screen, wear and tear. **Loss, theft and intentional damage excluded.** | Breakdowns, and some damage by device type, for all eligible household electronics (TVs, laptops, routers, consoles, …) |
| Limits / deductible | Up to the product purchase price. **$0 deductible.** | **$2,000 per claim, $5,000 per household per 12 months**. Service fee **$0 / $29 / $79 / $99 / $129** depending on item. |
| Eligibility | Plan bought from the same retailer as the product. Product new or manufacturer-refurbished. **Buy within 30 days of product purchase** (Target/eBay help). Waiting period 0–30 days by state. | Devices of **any age**, bought anywhere. Failures before day 31 are not covered. |
| Pricing model | **One-time, by device price band**: $20 (laptop $75–99.99) · **$130 (laptop $1,000–1,499.99)**. That is about 10% of the band midpoint at the high end. | **Monthly, flat: $34.99/mo** for the household |
| Term / start | 24 months. Starts on the later of plan purchase or end of the waiting period, and runs alongside the manufacturer warranty. | Monthly. Protection starts **on day 31**; tech support starts immediately. |
| Application fields | Product purchase price band, purchase date, receipt, serial for claims | Name, address, payment (only a login-gated sign-up; no public field list) |

### 1.7 US: Extended warranty

| Field | **Allstate 3-Year TV Protection Plan** (Target) | **The Home Depot Protection Plan: Major Appliance** (Allstate-administered) |
|---|---|---|
| Source | [P-retail] https://www.target.com/p/allstate-3-year-tv-protection-plan/-/A-51505467 ; https://www.target.com/p/3-year-tv-protection-plan-1000-1249-99-allstate/-/A-51505485 | [S] https://todayshomeowner.com/home-finances/reviews/home-depot-protection-plan/ (the homedepot.com product page returned 403) |
| Covered events | Mechanical and electrical failure, normal wear and tear. **No accident, loss or theft cover.** In-home repair. | Mechanical/electrical failure from normal use. Parts and labour. "No lemon" replacement after 2 repairs of the same issue. |
| Limits / deductible | Up to purchase price. **$0 deductible.** | Parts and labour. No deductible cited. Damage must be reported within 30 days. |
| Eligibility | TV price band must match. Buy within 30 days (Allstate/Target help). Full refund if cancelled within 30 days. | **Buy within 90 days of product purchase**. Residential appliances only. |
| Pricing model | **One-time, by TV price band**: **$75 ($500–599.99)**, **$100 ($1,000–1,249.99)**. About 13.6% and 8.9% of band midpoint. | One-time by price band and term. Low band ($0–299.99): **$50 for 3 years, $75 for 5 years**. The review wrote "/year", which is ambiguous. Top band up to $325 (3-yr) or $595 (5-yr). |
| Term / start | **3 years from date of purchase**, running alongside the manufacturer warranty | 3 or 5 years. **Coverage starts after the manufacturer warranty ends.** |
| Application fields | Product price band, purchase date, receipt | Product SKU, purchase date, receipt |

### 1.8 US: Travel protection

| Field | **Allianz Travel OneTrip Prime** | **World Nomads Standard (US residents)** |
|---|---|---|
| Source | [P] https://www.allianztravelinsurance.com/find-a-plan/onetrip-prime.htm ; sample price [S] https://www.moneygeek.com/insurance/travel/allianz-travel-insurance-review/ | [P] https://www.worldnomads.com/usa/travel-insurance/whats-covered/plan-comparison ; sample price [S] https://www.nerdwallet.com/travel/learn/world-nomads-travel-insurance-explained |
| Covered events / limits (per traveller) | Trip cancellation **$100,000**, interruption **$150,000**, trip-change protector $500, emergency medical **$50,000** (dental $750), emergency transport **$500,000**, baggage loss/damage **$1,000**, baggage delay $300, travel delay **$800 ($200/day)**, epidemic coverage | Trip cancellation **$2,500**, interruption $2,500, emergency medical **$125,000** (varies by state), evacuation **$400,000**, baggage **$1,000**, baggage delay up to $750, trip delay up to $1,000. Covers 250+ adventure activities. Cancel For Any Reason is an optional add-on. |
| Deductible | Not stated ($0 on the page) | Not stated |
| Eligibility | **US residents**. Trip up to **180 days**. Kids aged 17 and under covered free with a parent or grandparent (not in PA). Pre-existing-condition waiver if the full trip cost is insured within 14 days of first payment. | **US residents**. Cover begins more than 100 miles from home. Pre-existing conditions excluded (waiver time-sensitive, Explorer only). |
| Pricing model | Per trip, priced on **trip cost, traveller age, destination and state**. Sample: **$98–184 for a $2,500, 7-day trip, age 30, across Allianz OneTrip tiers**, roughly 4–7% of trip cost. | Per trip, priced on **state, age, dates and destination**. Sample: **$84 for a 7-day trip** (NerdWallet), about $12 per day. |
| Term / start | Departure to return. Cancellation cover starts when the plan is bought. | Departure to return |
| Application fields (quote form) | Destination, departure/return dates, plan start date, each traveller's age, state of residence, **total trip cost** | Country/state of residence, destination(s), dates, traveller ages |

### 1.9 bolttech's public presence (KR / US)

- **Korea: yes.** bolttech set up a Korean subsidiary in Oct 2020 and runs **LG U+ Phone Swap Pass** (device swap / protection) at **uplus.bolttech.kr**. That is the §1.1 product and the best real anchor for a bolttech KR seed.
- **US: yes, as an administrator.** "bolt" device protection launched in the US in June 2022 with Chat Mobility (Iowa), per [P] https://bolttech.io/news/bolt-launches-device-protection-in-the-united-states/. There is a public template Coverage Details PDF (§1.5). bolttech.io also markets embedded travel and consumer-electronics protection, but **no public retail price list for the US** turned up. An Allianz Partners x bolttech partnership covers embedded device and appliance protection in APAC and the US ([S] insurancebusinessmag.com).

---

## 2. Proposed seed catalog

Tags: `(o)` = observed from a cited source. `(d)` = derived, i.e. my assumption. Money is in minor units: KRW has no minor unit; USD is in cents.

Schema caveat: the `rating` enum has no billing period. I added **`billing_period`** (MONTHLY | ONE_TIME | PER_TRIP) as a suggested extra field, marked `(d)`. Without it, a monthly phone premium and a one-time warranty premium look the same.

### 2.1 KR · MOBILE_INSURANCE: `KR-MOB-UPLUS-SWAP100`

```yaml
product_code: KR-MOB-UPLUS-SWAP100            # (d)
product_type: MOBILE_INSURANCE
marketing_name: "Phone Swap Pass 100 (LG U+ × bolttech)"   # (o)
insurable_object_type: DEVICE
currency: KRW
jurisdictions: ["KR"]
coverages:
  - {code: SWAP_WITH_RETURN,    name: "Damage/breakdown swap (with return)",   limit_minor: 1000000, deductible_minor: 50000}   # limit=(d) tier ceiling; deductible=(o) min of 18% MSRP
  - {code: SWAP_WITHOUT_RETURN, name: "Swap (without return)",          limit_minor: 1000000, deductible_minor: 100000}  # (o) min of 30% MSRP
  - {code: DAMAGE_REPAIR,       name: "Damage repair at official centre",       limit_minor: 1000000, deductible_minor: 50000}   # limit (d); deductible (d) - "fixed deductible" (o) but amount not captured
rating: {method: PERCENT_OF_PURCHASE_PRICE, rate: 0.0080, min_premium_minor: 5990}  # (d) 7,990 / 1,000,000 tier ceiling; min=(o) lowest tier fee
billing_period: MONTHLY                        # (o)
default_term: {length: 36, unit: MONTH, starts: NEXT_DAY}   # length (o); start (d)
required_application_fields: [imei, device_model, device_msrp, activation_date, carrier_line_number, holder_name, holder_birth_date]  # (d)
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| INSURABLE_OBJECT | brand | IN | ["SAMSUNG","APPLE"] | DEVICE_BRAND_NOT_SUPPORTED | Galaxy and iPhone only (o) |
| INSURABLE_OBJECT | device_msrp | LTE | 1000000 | DEVICE_PRICE_OUT_OF_TIER | Tier "100" covers ₩500k–₩1M (o) |
| INSURABLE_OBJECT | device_msrp | GTE | 500001 | DEVICE_PRICE_OUT_OF_TIER | Lower bound of tier "100" (o) |
| PARTY | carrier | EQ | "LGU+" | CARRIER_NOT_ELIGIBLE | Sold to LG U+ subscribers (o) |
| INSURABLE_OBJECT | activation_date | WITHIN_DAYS | 30 | ENROLLMENT_WINDOW_EXPIRED | Window not published; 30 days follows carrier norms (d) |
| INSURABLE_OBJECT | has_existing_damage | EQ | false | PRE_EXISTING_DAMAGE | Must be undamaged at enrollment (d, KR carrier norm) |

### 2.2 KR · DEVICE_PROTECTION: `KR-DEV-SCP-NB-DMG`

```yaml
product_code: KR-DEV-SCP-NB-DMG               # (d)
product_type: DEVICE_PROTECTION
marketing_name: "Samsung Care+ Notebook Damage"      # (o)
insurable_object_type: DEVICE
currency: KRW
jurisdictions: ["KR"]
coverages:
  - {code: ACCIDENTAL_DAMAGE, name: "Damage repair", limit_minor: 2000000, deductible_minor: 30000}  # limit (d); deductible min (o) (actual: 10–35% of repair, min ₩30,000)
rating: {method: PERCENT_OF_PURCHASE_PRICE, rate: 0.0050, min_premium_minor: 7200}   # rate (d) ≈ ₩8,000 / ₩1.6M notebook; min (o)
billing_period: MONTHLY                        # (o)
default_term: {length: 36, unit: MONTH, starts: NEXT_DAY}   # (d) product range is 24–60 months (o)
required_application_fields: [serial_number, device_model, purchase_date, purchase_price, samsung_account_id]  # (d)
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| INSURABLE_OBJECT | brand | EQ | "SAMSUNG" | DEVICE_BRAND_NOT_SUPPORTED | Galaxy devices only (o) |
| INSURABLE_OBJECT | device_category | EQ | "NOTEBOOK" | DEVICE_CATEGORY_MISMATCH | Notebook plan (o) |
| INSURABLE_OBJECT | purchase_date | WITHIN_DAYS | 60 | ENROLLMENT_WINDOW_EXPIRED | 60-day window (o for smartphone, d for notebook) |
| INSURABLE_OBJECT | is_refurbished | EQ | false | REFURBISHED_NOT_ELIGIBLE | Refurbished units are excluded from loss cover (o); applied to all cover (d) |

### 2.3 KR · EXTENDED_WARRANTY: `KR-EW-HIMART-CARE`

```yaml
product_code: KR-EW-HIMART-CARE               # (d)
product_type: EXTENDED_WARRANTY
marketing_name: "Himart Care (warranty-extension type)"    # (o)
insurable_object_type: DEVICE
currency: KRW
jurisdictions: ["KR"]
coverages:
  - {code: MECHANICAL_BREAKDOWN, name: "Breakdown repair after free warranty", limit_minor: 1000000, deductible_minor: 0}  # limit = plan "Care100" (o); deductible 0 (o, none stated)
rating: {method: PERCENT_OF_PURCHASE_PRICE, rate: 0.014, min_premium_minor: 4000}  # (o) 1.4% of limit (Care75+), min = Care15 fee; limit≈price is (d)
billing_period: ONE_TIME                       # (o)
default_term: {length: 5, unit: YEAR, starts: WARRANTY_END}   # (o) "up to 5 yrs incl. mfr warranty; repair cover after warranty end"
required_application_fields: [product_name, serial_number, purchase_date, holder_name, holder_birth_date, holder_phone]  # (o) terms §2.6
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| INSURABLE_OBJECT | purchase_date | WITHIN_DAYS | 0 | MUST_BUY_WITH_PRODUCT | Must be bought together with the product; not after delivery (o) |
| INSURABLE_OBJECT | device_category | IN | ["FRIDGE","WASHER","DRYER","TV","LAPTOP","TABLET","AIRCON","DISHWASHER","DESKTOP"] | CATEGORY_NOT_ELIGIBLE | Subset of the ~40 eligible categories (o) |
| PARTY | customer_type | EQ | "INDIVIDUAL" | CORPORATE_NOT_ELIGIBLE | Personal use only (o) |
| INSURABLE_OBJECT | purchase_price | LTE | 5000000 | PRICE_ABOVE_MAX_LIMIT | Highest plan limit is ₩5M (o) |

### 2.4 KR · TRAVEL_PROTECTION: `KR-TRV-KAKAO-BASIC`

```yaml
product_code: KR-TRV-KAKAO-BASIC              # (d)
product_type: TRAVEL_PROTECTION
marketing_name: "KakaoPay Insurance Overseas Travel Insurance (Basic)"  # (o) name; tier choice (d)
insurable_object_type: TRIP
currency: KRW
jurisdictions: ["KR"]
coverages:
  - {code: OVERSEAS_MEDICAL_INJURY,  name: "Overseas injury medical expenses", limit_minor: 30000000, deductible_minor: 0}   # range 10M–100M (o); 30M (d)
  - {code: OVERSEAS_MEDICAL_ILLNESS, name: "Overseas illness medical expenses", limit_minor: 30000000, deductible_minor: 0}   # (o range / d value)
  - {code: BAGGAGE_DAMAGE,           name: "Personal-belongings damage (loss excluded, ₩200k per item)", limit_minor: 400000, deductible_minor: 10000}  # limit (o); deductible (d, industry norm seen at DB)
  - {code: FLIGHT_DELAY,             name: "Flight delay", limit_minor: 300000, deductible_minor: 0}        # (o)
rating: {method: PER_TRIP_DAY, rate: 1350, min_premium_minor: 1850}   # rate (d) ≈ ₩5,394 "from" / 4 days; min (o) ₩1,850 sample
billing_period: PER_TRIP                       # (o)
default_term: {length: 0, unit: DAY, starts: TRIP_DEPARTURE}   # length = trip length (o: home-departure to return)
required_application_fields: [departure_datetime, return_datetime, destination_country, traveller_names, traveller_birth_dates, traveller_genders, applicant_phone]  # (o/d)
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| PARTY | applicant_age | GTE | 19 | APPLICANT_UNDERAGE | Applicant aged 19–99 (o) |
| PARTY | insured_age | LTE | 99 | INSURED_AGE_OUT_OF_RANGE | Insured aged 0–99 (o) |
| NEEDS_ASSESSMENT | trip_length_days | LTE | 89 | TRIP_TOO_LONG | Max 89 days (o) |
| NEEDS_ASSESSMENT | departure_country | EQ | "KR" | MUST_DEPART_FROM_KR | Departure from Korea only (o) |
| NEEDS_ASSESSMENT | destination_travel_alert_level | LTE | 2 | DESTINATION_EXCLUDED | MOFA level 3–4 excluded (o at DB; d for Kakao) |
| NEEDS_ASSESSMENT | traveller_count | LTE | 10 | TOO_MANY_TRAVELLERS | Up to 10 people per policy (o) |
| NEEDS_ASSESSMENT | departure_datetime | WITHIN_DAYS | 0 | ALREADY_DEPARTED | Must buy before departure (o) |

### 2.5 US · MOBILE_INSURANCE: `US-MOB-ACPLUS-TL-STD`

```yaml
product_code: US-MOB-ACPLUS-TL-STD            # (d)
product_type: MOBILE_INSURANCE
marketing_name: "AppleCare+ with Theft and Loss (iPhone 17/16/15)"  # (o)
insurable_object_type: DEVICE
currency: USD
jurisdictions: ["US"]
coverages:
  - {code: SCREEN_OR_BACK_GLASS, name: "Screen or back glass damage", limit_minor: 79900, deductible_minor: 2900}   # limit = device retail (o rule, d value $799)
  - {code: ACCIDENTAL_DAMAGE,    name: "Other accidental damage",    limit_minor: 79900, deductible_minor: 9900}   # (o)
  - {code: THEFT_LOSS,           name: "Theft or loss (2 per 12 mo)", limit_minor: 79900, deductible_minor: 14900} # (o)
  - {code: MECHANICAL_BREAKDOWN, name: "Hardware + battery <80%",     limit_minor: 79900, deductible_minor: 0}     # (o)
rating: {method: FLAT, rate: 1199, min_premium_minor: 1199}    # (o) $11.99/month
billing_period: MONTHLY                        # (o)  (alt: $219 fixed 24-month)
default_term: {length: 1, unit: MONTH, starts: NEXT_DAY}   # (o) auto-renews; actual start = plan purchase date (enum lacks PURCHASE_DATE)
required_application_fields: [serial_number, device_model, purchase_date, proof_of_purchase, apple_account_id, find_my_enabled, state_of_residence]  # (o)/(d)
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| INSURABLE_OBJECT | purchase_date | WITHIN_DAYS | 60 | ENROLLMENT_WINDOW_EXPIRED | Buy within 60 days of iPhone purchase (o) |
| INSURABLE_OBJECT | find_my_enabled | EQ | true | FIND_MY_REQUIRED | Needed for theft/loss (o) |
| INSURABLE_OBJECT | condition | EQ | "NEW" | DEVICE_NOT_NEW | Bought new from Apple or an authorised reseller (o) |
| PARTY | residence_country | EQ | "US" | NON_US_RESIDENT | US residents (o) |
| PARTY | residence_state | IN | [all states except "NY"] | STATE_SEPARATE_FILING | NY has a separate disclosure (o); exclusion is (d) |

### 2.6 US · DEVICE_PROTECTION: `US-DEV-ALLSTATE-LAPTOP-ADH-2Y`

```yaml
product_code: US-DEV-ALLSTATE-LAPTOP-ADH-2Y   # (d)
product_type: DEVICE_PROTECTION
marketing_name: "Allstate 2-Year Laptop Protection Plan with Accidents"  # (o)
insurable_object_type: DEVICE
currency: USD
jurisdictions: ["US"]
coverages:
  - {code: ACCIDENTAL_DAMAGE,    name: "Drops, spills, screen",        limit_minor: 149999, deductible_minor: 0}  # limit = purchase price (o rule), band max (d)
  - {code: MECHANICAL_BREAKDOWN, name: "Mechanical/electrical failure", limit_minor: 149999, deductible_minor: 0}  # (o)
rating: {method: PERCENT_OF_PURCHASE_PRICE, rate: 0.104, min_premium_minor: 2000}   # rate (d) = $130 / $1,250 band midpoint; min (o) $20 lowest band
billing_period: ONE_TIME                       # (o)
default_term: {length: 24, unit: MONTH, starts: NEXT_DAY}   # length (o); start = later of purchase or state wait period (o) → NEXT_DAY (d)
required_application_fields: [device_category, purchase_price, purchase_date, retailer_order_id, serial_number, state_of_residence]  # (d)
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| INSURABLE_OBJECT | purchase_date | WITHIN_DAYS | 30 | ENROLLMENT_WINDOW_EXPIRED | Buy within 30 days of product purchase (o) |
| INSURABLE_OBJECT | purchase_price | GTE | 100000 | DEVICE_PRICE_OUT_OF_BAND | Band $1,000–1,499.99 (o) |
| INSURABLE_OBJECT | purchase_price | LTE | 149999 | DEVICE_PRICE_OUT_OF_BAND | Band upper bound (o) |
| INSURABLE_OBJECT | condition | IN | ["NEW","MFR_REFURBISHED"] | DEVICE_CONDITION_INELIGIBLE | New or manufacturer-refurbished (o) |
| PARTY | residence_country | EQ | "US" | NON_US_RESIDENT | US plan (d) |

### 2.7 US · EXTENDED_WARRANTY: `US-EW-ALLSTATE-TV-3Y`

```yaml
product_code: US-EW-ALLSTATE-TV-3Y            # (d)
product_type: EXTENDED_WARRANTY
marketing_name: "Allstate 3-Year TV Protection Plan"   # (o)
insurable_object_type: DEVICE
currency: USD
jurisdictions: ["US"]
coverages:
  - {code: MECHANICAL_BREAKDOWN, name: "Mechanical & electrical failure incl. wear and tear", limit_minor: 124999, deductible_minor: 0}  # (o) $0 deductible; limit = purchase price, band max (d)
rating: {method: PERCENT_OF_PURCHASE_PRICE, rate: 0.09, min_premium_minor: 7500}  # rate (d) ≈ $100/$1,125; min (o) $75 for the $500–599.99 band
billing_period: ONE_TIME                       # (o)
default_term: {length: 3, unit: YEAR, starts: NEXT_DAY}   # (o) "3 years from date of purchase", concurrent with mfr warranty
required_application_fields: [device_category, purchase_price, purchase_date, retailer_order_id, serial_number]  # (d)
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| INSURABLE_OBJECT | device_category | EQ | "TV" | DEVICE_CATEGORY_MISMATCH | TV plan (o) |
| INSURABLE_OBJECT | purchase_date | WITHIN_DAYS | 30 | ENROLLMENT_WINDOW_EXPIRED | 30-day purchase window (o, Allstate/Target help) |
| INSURABLE_OBJECT | purchase_price | LTE | 124999 | DEVICE_PRICE_OUT_OF_BAND | Band $1,000–1,249.99 (o) |
| INSURABLE_OBJECT | usage | EQ | "RESIDENTIAL" | COMMERCIAL_USE_EXCLUDED | Commercial use excluded (o, Allstate coverage FAQ) |

Alternative with `starts: WARRANTY_END`: Home Depot Major Appliance plan (3 or 5 years, 90-day window). See §1.7.

### 2.8 US · TRAVEL_PROTECTION: `US-TRV-ALLIANZ-ONETRIP-PRIME`

```yaml
product_code: US-TRV-ALLIANZ-ONETRIP-PRIME    # (d)
product_type: TRAVEL_PROTECTION
marketing_name: "Allianz OneTrip Prime"       # (o)
insurable_object_type: TRIP
currency: USD
jurisdictions: ["US"]
coverages:
  - {code: TRIP_CANCELLATION,   name: "Trip cancellation",             limit_minor: 10000000, deductible_minor: 0}  # (o) $100,000
  - {code: TRIP_INTERRUPTION,   name: "Trip interruption",             limit_minor: 15000000, deductible_minor: 0}  # (o) $150,000
  - {code: EMERGENCY_MEDICAL,   name: "Emergency medical",             limit_minor: 5000000,  deductible_minor: 0}  # (o) $50,000
  - {code: EMERGENCY_TRANSPORT, name: "Emergency medical transportation", limit_minor: 50000000, deductible_minor: 0}  # (o) $500,000
  - {code: BAGGAGE_LOSS,        name: "Baggage loss/damage",           limit_minor: 100000,   deductible_minor: 0}  # (o) $1,000
  - {code: BAGGAGE_DELAY,       name: "Baggage delay",                 limit_minor: 30000,    deductible_minor: 0}  # (o) $300
  - {code: TRAVEL_DELAY,        name: "Travel delay ($200/day)",       limit_minor: 80000,    deductible_minor: 0}  # (o) $800
rating: {method: PERCENT_OF_PURCHASE_PRICE, rate: 0.06, min_premium_minor: 5000}   # (d) % of insured trip cost; sample 4–7% (s); min (d)
billing_period: PER_TRIP                       # (o)
default_term: {length: 0, unit: DAY, starts: TRIP_DEPARTURE}   # (o) departure→return; cancellation cover from purchase
required_application_fields: [destination_country, departure_date, return_date, traveller_ages, state_of_residence, total_trip_cost, first_trip_payment_date]  # (o) quote fields + (d) payment date
```

| subject | attribute | operator | value | failure_reason_code | description |
|---|---|---|---|---|---|
| PARTY | residence_country | EQ | "US" | NON_US_RESIDENT | US residents only (o) |
| NEEDS_ASSESSMENT | trip_length_days | LTE | 180 | TRIP_TOO_LONG | Max 180 days (o) |
| NEEDS_ASSESSMENT | first_trip_payment_date | WITHIN_DAYS | 14 | PRE_EX_WAIVER_LOST | Pre-existing waiver needs purchase within 14 days of first payment (o); treated as a warning (d) |
| PARTY | insured_age | LTE | 17 | CHILD_FREE_RULE | Kids aged ≤17 free with a parent or grandparent; this is a pricing rule, not a rejection (o) |
| NEEDS_ASSESSMENT | destination_country | IN | [not "US"] | DOMESTIC_TRIP_DIFFERENT_PLAN | Assume an international plan (d) |

---

## 3. Gaps and caveats

1. **Chrome was not used.** The extension was not connected, so everything came from WebSearch/WebFetch. WebFetch returns a model summary; figures from PDFs were checked against raw text, but HTML-page figures were not.
2. **Blocked or empty pages**: T-Mobile (403), Home Depot product page (403), Amazon (500), SKT T world product pages (error PRD0047), Apple Korea price tables (did not render), Samsung Fire / Hyundai Marine direct pages (JS-only or reset). Travel prices at DB, Samsung Fire, Hyundai and Allianz are **behind quote forms**. Allianz, World Nomads and T-Mobile numbers are from secondary reviews.
3. **AppleCare+ Korea KRW prices** were not captured. Only service fees and the 60-day window were.
4. **LG U+ Phone Swap Pass**: the enrollment window and the fixed repair deductible are not published on the page read. The 18% / 30% swap-fee split came from a summariser, so check it on the live page before relying on it.
5. **KakaoPay flight-delay trigger** conflicts between sources: 2 hours (KakaoPay content) versus 4 hours (trip.com). Coverage tiers changed on 2025-12-24.
6. **Home Depot plan prices** from the review say "/year", which almost certainly means the total plan price. Treat them as unverified.
7. **Samsung Care+ for home appliances/TV** no longer shows public extended-warranty pricing (only cleaning, filter and relocation), so it was replaced by Himart Care and Coupang Ansim Care.
8. **Pricing patterns seen**:
   - Phone cover is **monthly by device tier or model**: KR ₩4.5k–₩20k, US $8–$26.
   - Extended warranties and non-phone device plans are **one-time by price band**. KR is about **1–2% of the coverage limit** for post-warranty-only cover. US Allstate is about **9–14% of price** because it runs from purchase and includes accidents.
   - Travel is **per trip**. KR is DIY-modular and very cheap (from ₩1,850). US is priced on trip cost and age, roughly 4–7% of trip cost.
   - The seed schema's single `rate` cannot express tier tables exactly. Consider a `rating.tiers[]` option and a `billing_period` field.
9. **Seed `limit_minor` values for device products** are set to the band or tier ceiling. Real contracts cap payouts at the device purchase price or retail value.
10. **Missing `starts` enum value**: none of the products actually starts NEXT_DAY. Most start on the **plan purchase date** (AppleCare, Allstate) or on **delivery or installation date** (Himart). Consider adding `PURCHASE_DATE`.

"""Diagrams for docs/design/02-langgraph-design.md, 03-state-management.md and 04-data-model.md.

Run from the repo root: `uv run --no-project python tools/diagrams/graph_state_data.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from svglib import BLUE, MONOF, ORANGE, PURPLE, Svg, esc  # noqa: E402

LEGEND = [(BLUE, "code"), (PURPLE, "LLM"), (ORANGE, "waits for a person")]


def label(s, x, y, t, anchor="middle"):
    """An edge label: the routing condition written on an edge."""
    s.text(x, y, t, 11, anchor=anchor, op="0.8")


def line(s, pts):
    s.seg(pts)


# ------------------------------------------------------------------ LangGraph graph
def langgraph_graph():
    D = 140  # the intake turn and the identity form loop push everything from verify_identity down
    s = Svg("lg1", 1010, 1776 + D, "The onboarding LangGraph graph: nodes of the four stages and the human handoff, "
                                   "coloured by kind, with every conditional edge and its condition")
    SX, SW, SC, SR = 380, 240, 500, 620  # spine: the main path
    LX, LW, LR, LC = 84, 170, 254, 169  # ask_customer loops on the left
    RX, RW, RR, RC = 724, 156, 880, 802  # the OTP and document checks on the right
    FG, FF, FA, FC = 16, 30, 44, 58  # far-left lanes: await_agent back to greet, fetch, assess, collect_answers
    RCO, REL, RAS, RDOC = 890, 920, 950, 980  # right lanes into human_handoff
    BL = 350  # back lane: CHANGE and "not confirmed"

    def spine(y, name, kind, sub=None, h=None):
        s.node(SX, y, SW, name, kind, sub, h=h)

    # ---- stage 1, top: intake turn, then identity asked in small forms (not shifted)
    s.group(70, 58, 830, 346 + D, "1. Identity verification")
    s.pill(SC - 50, 18, 100, 28, "start")
    line(s, [(SC, 46), (SC, 88)])
    spine(88, "greet", "code")
    line(s, [(SC, 122), (SC, 142)])
    spine(142, "ask_customer", "wait", "INTAKE", h=40)
    line(s, [(SC, 182), (SC, 212)])
    spine(212, "understand_intake", "llm")
    line(s, [(SC, 246), (SC, 282)])
    spine(282, "collect_identity", "code")
    s.node(LX, 276, LW, "ask_customer", "wait", "IDENTITY_INFO", h=40)
    line(s, [(SX, 292), (LR, 292)])
    label(s, 317, 286, "form pending")
    line(s, [(LR, 306), (SX, 306)])
    line(s, [(SC, 316), (SC, 352)])
    label(s, SC + 8, 338, "all answered", "start")

    # everything below moves down by D
    s.p.append(f'<g transform="translate(0,{D})">')

    # stage groups
    s.group(70, 416, 570, 182, "2. Customer profiling")
    s.group(70, 606, 770, 346, "3. Policy recommendation")
    s.group(70, 964, 570, 466, "4. Policy application")
    s.group(620, 1494, 384, 270, "Human handoff (any stage)")

    # ---- stage 1, verification
    spine(212, "verify_identity", "code")
    s.node(RX, 209, RW, "ask_customer", "wait", "OTP_CODE", h=40)
    line(s, [(SR, 229), (RX, 229)])
    label(s, 672, 222, "NOT_MATCHED")
    line(s, [(RC, 249), (RC, 283)])
    s.node(RX, 283, RW, "check_otp", "code")
    line(s, [(RC, 317), (RC, 351)])
    label(s, RC + 8, 338, "OTP_FAILED", "start")
    s.node(RX, 351, RW, "check_document", "code")
    # into fetch_purchases
    line(s, [(SC, 246), (SC, 452)])
    label(s, SC - 8, 330, "MATCHED", "end")
    line(s, [(RX, 300), (560, 300), (560, 452)])
    label(s, 650, 294, "OTP_OK")
    line(s, [(RX, 368), (590, 368), (590, 452)])
    label(s, 650, 362, "DOC_OK")
    line(s, [(RR, 368), (RDOC, 368), (RDOC, 1530)])
    label(s, 906, 362, "DOC_FAILED", "start")

    # ---- stage 2
    spine(452, "fetch_purchases", "code")
    line(s, [(SC, 486), (SC, 522)])
    spine(522, "assess_needs", "llm", h=48)
    s.node(LX, 514, LW, "ask_customer", "wait", "NEEDS", h=40)
    line(s, [(SX, 528), (LR, 528)])
    label(s, 317, 510, "no input yet,")
    label(s, 317, 522, "or fields missing")
    line(s, [(LR, 544), (SX, 544)])
    line(s, [(SR, 546), (RAS, 546), (RAS, 1530)])
    label(s, 785, 540, "3 rounds, still missing")
    line(s, [(SC, 570), (SC, 636)])
    label(s, SC + 8, 624, "needs_complete", "start")

    # ---- stage 3
    spine(636, "check_eligibility", "code")
    line(s, [(SR, 653), (REL, 653), (REL, 1530)])
    label(s, 760, 647, "eligible_count = 0")
    line(s, [(SC, 670), (SC, 704)])
    label(s, SC + 8, 691, "eligible_count >= 1", "start")
    spine(704, "rank_products", "code")
    line(s, [(SC, 738), (SC, 768)])
    spine(768, "quote_premium", "code")
    line(s, [(SC, 802), (SC, 832)])
    spine(832, "explain_recommendation", "llm")
    line(s, [(SC, 866), (SC, 896)])
    spine(896, "await_decision", "wait")
    line(s, [(SR, 913), (690, 913)])
    label(s, 655, 906, "DECLINE")
    s.pill(690, 899, 140, 28, "stop: DECLINED")
    line(s, [(SX, 913), (BL, 913), (BL, 590), (400, 590), (400, 570)])
    label(s, BL - 8, 760, "CHANGE", "end")
    line(s, [(SC, 930), (SC, 994)])
    label(s, SC + 8, 945, "ACCEPT", "start")

    # ---- stage 4
    spine(994, "open_application", "code")
    line(s, [(SC, 1028), (SC, 1066)])
    spine(1066, "collect_parties", "llm", h=48)
    s.node(LX, 1058, LW, "ask_customer", "wait", "PARTIES", h=40)
    line(s, [(SX, 1072), (LR, 1072)])
    label(s, 317, 1054, "no input yet,")
    label(s, 317, 1066, "or a name missing")
    line(s, [(LR, 1088), (SX, 1088)])
    line(s, [(SC, 1114), (SC, 1156)])
    label(s, SC + 8, 1140, "parties_complete", "start")
    spine(1156, "collect_answers", "llm", h=48)
    s.node(LX, 1148, LW, "ask_customer", "wait", "ANSWERS", h=40)
    line(s, [(SX, 1162), (LR, 1162)])
    label(s, 317, 1156, "fields missing")
    line(s, [(LR, 1178), (SX, 1178)])
    line(s, [(SR, 1170), (RCO, 1170), (RCO, 1530)])
    label(s, 755, 1164, "3 rounds, still missing")
    line(s, [(SC, 1204), (SC, 1246)])
    label(s, SC + 8, 1230, "answers_complete", "start")
    spine(1246, "summarize_application", "llm")
    line(s, [(SC, 1280), (SC, 1310)])
    spine(1310, "confirm_summary", "wait")
    line(s, [(SX, 1327), (BL, 1327), (BL, 1224), (400, 1224), (400, 1204)])
    label(s, BL - 8, 1290, "not confirmed", "end")
    line(s, [(SC, 1344), (SC, 1376)])
    label(s, SC + 8, 1364, "confirmed", "start")
    spine(1376, "submit_application", "code")
    line(s, [(SC, 1410), (SC, 1452)])
    s.pill(SC - 80, 1452, 160, 28, "stop: SUBMITTED")

    # ---- handoff
    s.node(780, 1530, 210, "human_handoff", "code")
    line(s, [(885, 1564), (885, 1598)])
    s.node(780, 1598, 210, "await_agent", "wait", h=56)
    # CONTINUE resumes the identity forms, in the unshifted top: drawn after the group closes (below)
    line(s, [(780, 1634), (FF, 1634), (FF, 469), (SX, 469)])
    label(s, 200, 463, "VERIFIED after identity failure")
    line(s, [(780, 1622), (FA, 1622), (FA, 562), (SX, 562)])
    label(s, LC, 581, "needs or no product")
    line(s, [(780, 1610), (FC, 1610), (FC, 1196), (SX, 1196)])
    label(s, LC, 1215, "answers incomplete")
    line(s, [(810, 1654), (810, 1712)])
    label(s, 802, 1688, "error: re-run failed node", "end")
    s.pill(640, 1712, 190, 28, "the node in resume_node", dashed=True)
    line(s, [(930, 1654), (930, 1712)])
    label(s, 938, 1688, "END", "start")
    s.pill(860, 1712, 140, 28, "stop: WITHDRAWN")

    s.legend(84, 1516, LEGEND)
    s.p.append("</g>")

    # await_agent CONTINUE after an identity failure: back to the identity forms, up the right edge
    line(s, [(990, 1640 + D), (1002, 1640 + D), (1002, 299), (SR, 299)])
    label(s, 810, 293, "CONTINUE after identity failure")
    return s


# ------------------------------------------------------------------ checkpoint encryption
def state_checkpoint_encryption():
    s = Svg("st1", 960, 116, "Checkpoint encryption: the state is serialized with JsonPlusSerializer (msgpack), "
                             "gzipped, AES-encrypted with CHECKPOINT_AES_KEY and stored in the checkpoint schema "
                             "on RDS encrypted with KMS")
    y, h = 30, 52
    steps = [(90, "state", ()), (176, "JsonPlusSerializer", ("(msgpack)",)), (84, "gzip", ()),
             (196, "AES encrypt", ("(CHECKPOINT_AES_KEY)",))]
    x = 12
    for w, t, sub in steps:
        s.box(x, y, w, h, t, sub, mono=t in ("JsonPlusSerializer",))
        s.arrow(x + w + 2, y + h / 2, x + w + 40, y + h / 2)
        x += w + 44
    # the database: a cylinder
    w, cx, ry = 948 - x, x + (948 - x) / 2, 8
    top, bot = y - 4, y + h + 4
    s.p.append(f'<path d="M{x} {top} A{w / 2} {ry} 0 0 0 {x + w} {top} L{x + w} {bot} A{w / 2} {ry} 0 0 1 {x} {bot} Z" '
               f'fill="currentColor" fill-opacity="0.05" stroke="currentColor" stroke-opacity="0.45" stroke-width="1.6"/>')
    s.p.append(f'<path d="M{x} {top} A{w / 2} {ry} 0 0 1 {x + w} {top}" fill="none" stroke="currentColor" '
               f'stroke-opacity="0.45" stroke-width="1.6"/>')
    s.text(cx, y + h / 2 + 4, "checkpoint schema", 14, weight="650")
    s.text(cx, y + h / 2 + 21, "RDS encrypted with KMS", 11.5, op="0.72")
    return s


# ------------------------------------------------------------------ ER diagram
ENTITIES = {
    "OnboardingSession": [("uuid", "session_id", "PK"), ("string", "thread_id", ""), ("uuid", "party_id", "FK"),
                          ("string", "market", ""), ("string", "locale", ""), ("string", "token_hmac", ""),
                          ("timestamp", "token_expires_at", ""), ("enum", "status", ""), ("enum", "last_stage", ""),
                          ("enum", "waiting_for", ""), ("string", "current_node", ""), ("enum", "mode", ""),
                          ("string", "assigned_agent_id", ""), ("timestamp", "last_activity_at", ""),
                          ("timestamp", "ended_at", "")],
    "Party": [("uuid", "party_id", "PK"), ("string", "full_name", ""), ("string", "email", ""),
              ("string", "phone", ""), ("date", "date_of_birth", ""), ("enum", "id_document_type", ""),
              ("bytes", "id_document_number_enc", ""), ("string", "id_document_hmac", ""),
              ("timestamp", "third_party_consent_at", ""), ("string", "partner_customer_ref", ""),
              ("enum", "verification_status", ""), ("enum", "verification_method", ""),
              ("int", "verification_attempts", ""), ("timestamp", "verified_at", "")],
    "NeedsAssessment": [("uuid", "needs_assessment_id", "PK"), ("uuid", "party_id", "FK"), ("uuid", "session_id", ""),
                        ("int", "version", ""), ("enum", "age_range", ""), ("string", "occupation", ""),
                        ("string", "residence_country", ""), ("json", "existing_coverage", ""),
                        ("json", "objectives", ""), ("json", "device", ""), ("json", "trip", ""),
                        ("enum", "captured_by", ""), ("json", "missing_fields", ""), ("timestamp", "completed_at", "")],
    "InsurableObject": [("uuid", "insurable_object_id", "PK"), ("uuid", "owner_party_id", "FK"),
                        ("enum", "object_type", "", "DEVICE or TRIP"),
                        ("enum", "source", "", "PARTNER CUSTOMER AGENT"), ("json", "attributes", "")],
    "Product": [("string", "product_code", "PK"), ("enum", "product_type", ""), ("string", "marketing_name", ""),
                ("enum", "insurable_object_type", ""), ("json", "coverages", ""), ("json", "rating", ""),
                ("enum", "billing_period", ""), ("string", "currency", ""), ("array", "jurisdictions", ""),
                ("json", "term_rule", ""), ("array", "required_application_fields", "")],
    "EligibilityRule": [("uuid", "rule_id", "PK"), ("string", "product_code", "FK"), ("enum", "subject", ""),
                        ("string", "attribute", ""), ("enum", "operator", ""), ("json", "value", ""),
                        ("string", "failure_reason_code", ""), ("string", "description", "")],
    "TargetMarket": [("uuid", "target_market_id", "PK"), ("string", "product_code", "FK"),
                     ("string", "attribute", ""), ("json", "values", ""), ("float", "weight", ""),
                     ("string", "rationale", "")],
    "Recommendation": [("uuid", "recommendation_id", "PK"), ("uuid", "session_id", "FK"),
                       ("uuid", "needs_assessment_id", "FK"), ("string", "product_code", "FK"),
                       ("uuid", "insurable_object_id", ""), ("int", "rank", ""), ("float", "score", ""),
                       ("enum", "eligibility_result", ""), ("json", "failed_rule_ids", ""),
                       ("json", "failed_reasons", ""), ("string", "rationale", ""), ("enum", "status", ""),
                       ("enum", "decided_by", "")],
    "Quote": [("uuid", "quote_id", "PK"), ("uuid", "recommendation_id", "FK"), ("string", "product_code", ""),
              ("json", "coverages", ""), ("int", "premium_minor", ""), ("string", "currency", ""),
              ("enum", "billing_period", ""), ("date", "term_start_date", ""), ("date", "term_end_date", ""),
              ("json", "rating_inputs", ""), ("enum", "status", ""), ("timestamp", "valid_until", "")],
    "Application": [("uuid", "application_id", "PK"), ("uuid", "session_id", "FK"),
                    ("uuid", "recommendation_id", "FK"), ("uuid", "quote_id", "FK"), ("string", "product_code", ""),
                    ("enum", "status", ""), ("json", "answers", ""), ("json", "missing_fields", ""),
                    ("string", "summary", ""), ("enum", "captured_by", ""), ("string", "submission_ref", ""),
                    ("timestamp", "submitted_at", "")],
    "ApplicationParty": [("uuid", "application_id", "FK"), ("uuid", "party_id", "FK"),
                         ("enum", "role", "", "POLICYHOLDER INSURED PAYER")],
}
ROW = 16


def entity_height(name):
    fields = ENTITIES[name]
    return 34 + sum(2 if len(f) > 3 else 1 for f in fields) * ROW + 6


def entity(s, x, y, w, name):
    """An entity box: name, then one row per field — key, name, type — and the field's comment below it."""
    h = entity_height(name)
    s.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="currentColor" fill-opacity="0.04" '
               f'stroke="currentColor" stroke-opacity="0.45" stroke-width="1.4"/>')
    s.p.append(f'<text x="{x + 12}" y="{y + 20}" font-size="13" text-anchor="start" fill="currentColor" '
               f'font-weight="700" {MONOF}>{esc(name)}</text>')
    s.rule(x, y + 30, x + w, "0.3")
    yy = y + 30
    for f in ENTITIES[name]:
        typ, fname, key = f[:3]
        yy += ROW
        if key:
            s.p.append(f'<text x="{x + 10}" y="{yy}" font-size="9" text-anchor="start" fill="currentColor" '
                       f'fill-opacity="0.6" font-weight="700">{key}</text>')
        s.p.append(f'<text x="{x + 30}" y="{yy}" font-size="11" text-anchor="start" fill="currentColor" '
                   f'fill-opacity="0.9" {MONOF}>{esc(fname)}</text>')
        s.p.append(f'<text x="{x + w - 10}" y="{yy}" font-size="10" text-anchor="end" fill="currentColor" '
                   f'fill-opacity="0.55" {MONOF}>{esc(typ)}</text>')
        if len(f) > 3:
            yy += ROW
            s.p.append(f'<text x="{x + 40}" y="{yy}" font-size="10" text-anchor="start" fill="currentColor" '
                       f'fill-opacity="0.55" {MONOF}>"{esc(f[3])}"</text>')
    return h


def rel(s, pts, name, name_at, ends):
    """A relationship line with its name and a cardinality label at each end: ends = [(x, y, text, anchor), ...]."""
    s.seg(pts, arrow=False)
    x, y, anchor = name_at
    s.text(x, y, name, 11, anchor=anchor, op="0.8")
    for ex, ey, t, a in ends:
        s.text(ex, ey, t, 11, anchor=a, weight="700", op="0.9")


def data_model_er():
    W, CW = 1040, 262
    X = [16, 358, 700]  # column lefts; gaps of 80
    T = [20]  # row tops
    rows = [["EligibilityRule", "NeedsAssessment", "Party"], ["Product", "Recommendation", "InsurableObject"],
            ["TargetMarket", "Quote", "OnboardingSession"], [None, "Application", "ApplicationParty"]]
    GAP = 64
    for r in rows[:-1]:
        T.append(T[-1] + max(entity_height(n) for n in r if n) + GAP)
    H = T[-1] + max(entity_height(n) for n in rows[-1] if n) + 30
    s = Svg("er1", W, H, "Entity-relationship diagram of the domain and catalog tables: eleven entities with "
                         "their fields, and fifteen relationships with their cardinality")
    box = {}
    for ri, r in enumerate(rows):
        for ci, n in enumerate(r):
            if n:
                h = entity(s, X[ci], T[ri], CW, n)
                box[n] = (X[ci], T[ri], X[ci] + CW, T[ri] + h)

    def L(n):
        return box[n][0]

    def R(n):
        return box[n][2]

    def Tp(n):
        return box[n][1]

    def B(n):
        return box[n][3]

    c1, c2, c3 = X[0] + CW / 2, X[1] + CW / 2, X[2] + CW / 2
    g12, g23 = (X[0] + CW + X[1]) / 2, (X[1] + CW + X[2]) / 2  # gaps between columns
    right1, right2 = R("Party") + 34, R("Party") + 64  # channels right of column 3

    # vertical, column 1: Product 1 — 0..* EligibilityRule, Product 1 — 0..* TargetMarket
    rel(s, [(c1, B("EligibilityRule")), (c1, Tp("Product"))], "requires", (c1 + 8, (B("EligibilityRule") + Tp("Product")) / 2 + 4, "start"),
        [(c1 - 6, B("EligibilityRule") + 14, "0..*", "end"), (c1 - 6, Tp("Product") - 6, "1", "end")])
    rel(s, [(c1, B("Product")), (c1, Tp("TargetMarket"))], "fits", (c1 + 8, (B("Product") + Tp("TargetMarket")) / 2 + 4, "start"),
        [(c1 - 6, B("Product") + 14, "1", "end"), (c1 - 6, Tp("TargetMarket") - 6, "0..*", "end")])
    # vertical, column 2: NeedsAssessment 1 — 0..* Recommendation, Recommendation 1 — 0..* Quote,
    # Quote 1 — 0..1 Application
    rel(s, [(c2, B("NeedsAssessment")), (c2, Tp("Recommendation"))], "based on",
        (c2 + 8, (B("NeedsAssessment") + Tp("Recommendation")) / 2 + 4, "start"),
        [(c2 - 6, B("NeedsAssessment") + 14, "1", "end"), (c2 - 6, Tp("Recommendation") - 6, "0..*", "end")])
    rel(s, [(c2, B("Recommendation")), (c2, Tp("Quote"))], "priced as",
        (c2 + 8, (B("Recommendation") + Tp("Quote")) / 2 + 4, "start"),
        [(c2 - 6, B("Recommendation") + 14, "1", "end"), (c2 - 6, Tp("Quote") - 6, "0..*", "end")])
    rel(s, [(c2, B("Quote")), (c2, Tp("Application"))], "accepted price",
        (c2 + 8, (B("Quote") + Tp("Application")) / 2 + 4, "start"),
        [(c2 - 6, B("Quote") + 14, "1", "end"), (c2 - 6, Tp("Application") - 6, "0..1", "end")])
    # vertical, column 3: Party 1 — 0..* InsurableObject
    rel(s, [(c3, B("Party")), (c3, Tp("InsurableObject"))], "owns",
        (c3 + 8, (B("Party") + Tp("InsurableObject")) / 2 + 4, "start"),
        [(c3 - 6, B("Party") + 14, "1", "end"), (c3 - 6, Tp("InsurableObject") - 6, "0..*", "end")])

    # horizontal
    y = Tp("Party") + 60
    rel(s, [(R("NeedsAssessment"), y), (L("Party"), y)], "versions", (g23, y - 6, "middle"),
        [(R("NeedsAssessment") + 5, y + 14, "0..*", "start"), (L("Party") - 5, y + 14, "1", "end")])
    y = Tp("Product") + 60
    rel(s, [(R("Product"), y), (L("Recommendation"), y)], "recommends", (g12, y - 6, "middle"),
        [(R("Product") + 5, y + 14, "1", "start"), (L("Recommendation") - 5, y + 14, "0..*", "end")])
    y = Tp("InsurableObject") + 60
    rel(s, [(L("InsurableObject"), y), (R("Recommendation"), y)], "covers", (g23, y - 6, "middle"),
        [(L("InsurableObject") - 5, y + 14, "0..1", "end"), (R("Recommendation") + 5, y + 14, "0..*", "start")])
    y = Tp("Application") + 60
    rel(s, [(R("Application"), y), (L("ApplicationParty"), y)], "roles", (g23, y - 6, "middle"),
        [(R("Application") + 5, y + 14, "1", "start"), (L("ApplicationParty") - 5, y + 14, "1..*", "end")])

    # Recommendation 1 — 0..1 Application: left of column 2
    y1, y2 = B("Recommendation") - 40, Tp("Application") + 40
    rel(s, [(L("Recommendation"), y1), (g12, y1), (g12, y2), (L("Application"), y2)], "accepted into",
        (g12 - 8, (B("Quote") + Tp("Application")) / 2 + 4, "end"),
        [(L("Recommendation") - 5, y1 - 6, "1", "end"), (L("Application") - 5, y2 - 6, "0..1", "end")])
    # OnboardingSession 1 — 0..* Recommendation: gap between columns 2 and 3
    y1, y2 = B("Recommendation") - 40, Tp("OnboardingSession") + 40
    xg = g23 - 12
    rel(s, [(R("Recommendation"), y1), (xg, y1), (xg, y2), (L("OnboardingSession"), y2)], "produced",
        (xg + 8, (B("InsurableObject") + Tp("OnboardingSession")) / 2 + 4, "start"),
        [(R("Recommendation") + 5, y1 - 6, "0..*", "start"), (L("OnboardingSession") - 5, y2 - 6, "1", "end")])
    # OnboardingSession 1 — 0..* Application
    y1, y2 = Tp("Application") + 30, B("OnboardingSession") - 30
    xg = g23 + 12
    rel(s, [(R("Application"), y1), (xg, y1), (xg, y2), (L("OnboardingSession"), y2)], "produced",
        (xg + 8, (B("OnboardingSession") + Tp("ApplicationParty")) / 2 + 4, "start"),
        [(R("Application") + 5, y1 - 6, "0..*", "start"), (L("OnboardingSession") - 5, y2 - 6, "1", "end")])
    # right channel: OnboardingSession 0..* — 1 Party (customer), Party 1 — 0..* ApplicationParty (plays)
    y1, y2 = Tp("OnboardingSession") + 40, B("Party") - 40
    rel(s, [(R("OnboardingSession"), y1), (right1, y1), (right1, y2), (R("Party"), y2)], "customer",
        (right1 - 6, (B("InsurableObject") + Tp("OnboardingSession")) / 2 + 4, "end"),
        [(R("OnboardingSession") + 5, y1 - 6, "0..*", "start"), (R("Party") + 5, y2 - 6, "1", "start")])
    y1, y2 = Tp("ApplicationParty") + 40, B("Party") - 70
    rel(s, [(R("ApplicationParty"), y1), (right2, y1), (right2, y2), (R("Party"), y2)], "plays",
        (right2 - 6, Tp("ApplicationParty") - 20, "end"),
        [(R("ApplicationParty") + 5, y1 - 6, "0..*", "start"), (R("Party") + 5, y2 - 6, "1", "start")])
    return s


if __name__ == "__main__":
    langgraph_graph().save("docs/design/assets/langgraph-graph.svg")
    state_checkpoint_encryption().save("docs/design/assets/state-checkpoint-encryption.svg")
    data_model_er().save("docs/design/assets/data-model-er.svg")

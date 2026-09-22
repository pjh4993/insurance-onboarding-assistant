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


# ------------------------------------------------------------------ LangGraph: the four stages (level 1)
def langgraph_stages():
    s = Svg("lg0", 1240, 370, "The four stages of the onboarding graph in order, the CHANGE loop back to profiling, "
                              "the DECLINE exit, and the human handoff every stage can fall into and resume from")
    X, W, Y, H = [110, 360, 610, 860], 190, 100, 84
    C = [x + W / 2 for x in X]
    stages = [
        ("Identity verification", "intake, forms, then checks", "ends when verified"),
        ("Customer profiling", "LLM reads, code finds gaps", "ends when nothing is missing"),
        ("Policy recommendation", "code ranks and prices", "LLM explains, customer picks"),
        ("Policy application", "parties, answers, summary", "ends when submitted"),
    ]
    for i, (x, (name, sub1, sub2)) in enumerate(zip(X, stages)):
        s.box(x, Y, W, H, "", ())
        s.p.pop()  # drop the empty title
        s.text(x + W / 2, Y + 22, f"STAGE {i + 1}", 10.5, weight="700", op="0.5")
        s.text(x + W / 2, Y + 42, name, 14, weight="650")
        s.text(x + W / 2, Y + 60, sub1, 11.5, op="0.72")
        s.text(x + W / 2, Y + 75, sub2, 11.5, op="0.72")
    my = Y + H / 2
    s.pill(10, my - 14, 70, 28, "start")
    line(s, [(80, my), (X[0], my)])
    for i, t in enumerate(["verified", "complete", "ACCEPT"]):
        line(s, [(X[i] + W, my), (X[i + 1], my)])
        label(s, (X[i] + W + X[i + 1]) / 2, my - 7, t)
    line(s, [(X[3] + W, my), (1100, my)])
    label(s, 1075, my - 7, "submit")
    s.pill(1100, my - 14, 130, 28, "stop: SUBMITTED")
    # CHANGE back to profiling, DECLINE out
    line(s, [(C[2] - 40, Y), (C[2] - 40, 70), (C[1] + 60, 70), (C[1] + 60, Y)])
    label(s, (C[1] + C[2]) / 2 + 10, 64, "CHANGE: redo needs")
    line(s, [(C[2] + 50, Y), (C[2] + 50, 48)])
    label(s, C[2] + 58, 80, "DECLINE", "start")
    s.pill(C[2] - 15, 20, 130, 28, "stop: DECLINED")
    # human handoff under every stage
    HY = 290
    s.box(X[0], HY, X[3] + W - X[0], 60, "Human handoff",
          ("human_handoff, then await_agent: a support agent resolves and the session resumes, or ends. "
           "Also reached from any node whose retries ran out",), color=ORANGE)
    reasons = [("identity", "failed twice"), ("3 rounds,", "still missing"), ("no eligible", "product"),
               ("3 rounds or", "3 rejections")]
    for c, (r1, r2) in zip(C, reasons):
        line(s, [(c - 30, Y + H), (c - 30, HY)])
        label(s, c - 38, 232, r1, "end")
        label(s, c - 38, 246, r2, "end")
        s.seg([(c + 30, HY), (c + 30, Y + H)], dashed=True)
        label(s, c + 38, 240, "resume", "start")
    line(s, [(X[3] + W, HY + 30), (1100, HY + 30)])
    label(s, 1075, HY + 23, "END")
    s.pill(1100, HY + 16, 130, 28, "stop: WITHDRAWN")
    return s


# ------------------------------------------------------------------ LangGraph: inside each stage (level 2)
SX, SW, SC, SR = 260, 200, 360, 460  # the stage's main path
EX, EW = 580, 160  # exits on the right


def exit_pill(s, x, y, w, t):
    """A way out of the stage: a node drawn in another stage's diagram."""
    s.pill(x, y, w, 28, t, dashed=True)


def langgraph_stage_identity():
    D = 140  # the intake turn and the identity form loop sit above verify_identity
    s = Svg("lg2", 760, 530 + D, "Stage 1, identity verification: greet, answer the customer's intake, ask for "
                                 "identity in small forms, then the partner match, the OTP and the document check, "
                                 "each result routing to profiling or on")
    RX, RW, RC = 560, 180, 650
    s.pill(SC - 50, 16, 100, 28, "start")
    line(s, [(SC, 44), (SC, 70)])
    s.node(SX, 70, SW, "greet", "code")
    line(s, [(SC, 104), (SC, 130)])
    s.node(SX, 130, SW, "ask_customer", "wait", "INTAKE", h=40)
    line(s, [(SC, 170), (SC, 200)])
    s.node(SX, 200, SW, "understand_intake", "llm")
    line(s, [(SC, 234), (SC, 270)])
    s.node(SX, 270, SW, "collect_identity", "code")
    s.node(20, 267, 160, "ask_customer", "wait", "IDENTITY_INFO", h=40)
    line(s, [(SX, 280), (180, 280)])
    label(s, 220, 273, "form pending")
    line(s, [(180, 296), (SX, 296)])
    line(s, [(SC, 304), (SC, 340)])
    label(s, SC + 8, 326, "all answered", "start")
    s.p.append(f'<g transform="translate(0,{D})">')  # everything below moves down by D
    s.node(SX, 200, SW, "verify_identity", "code")
    line(s, [(SR, 217), (RX, 217)])
    label(s, 510, 210, "NOT_MATCHED")
    s.node(RX, 197, RW, "ask_customer", "wait", "OTP_CODE", h=40)
    line(s, [(RC, 237), (RC, 270)])
    s.node(RX, 270, RW, "check_otp", "code")
    line(s, [(RC, 304), (RC, 340)])
    label(s, RC + 8, 326, "OTP_FAILED", "start")
    s.node(RX, 340, RW, "check_document", "code")
    line(s, [(RC, 374), (RC, 440)])
    label(s, RC + 8, 410, "DOC_FAILED", "start")
    exit_pill(s, 570, 440, 160, "→ human_handoff")
    line(s, [(SC, 234), (SC, 440)])
    label(s, SC - 8, 330, "MATCHED", "end")
    line(s, [(RX, 287), (410, 287), (410, 440)])
    label(s, 485, 281, "OTP_OK")
    line(s, [(RX, 357), (440, 357), (440, 440)])
    label(s, 500, 351, "DOC_OK")
    exit_pill(s, 240, 440, 240, "→ stage 2: fetch_purchases")
    s.legend(20, 500, LEGEND)
    s.p.append("</g>")
    return s


def langgraph_stage_profiling():
    s = Svg("lg3", 760, 350, "Stage 2, customer profiling: fetch partner purchases, then assess needs, asking again "
                             "until nothing is missing or three rounds pass")
    exit_pill(s, SC - 70, 16, 140, "from stage 1")
    line(s, [(SC, 44), (SC, 70)])
    s.node(SX, 70, SW, "fetch_purchases", "code")
    line(s, [(SC, 104), (SC, 140)])
    s.node(SX, 140, SW, "assess_needs", "llm", h=56)
    s.node(10, 148, 150, "ask_customer", "wait", "NEEDS", h=40)
    line(s, [(SX, 156), (160, 156)])
    label(s, 210, 138, "no input yet,")
    label(s, 210, 150, "or fields missing")
    line(s, [(160, 182), (SX, 182)])
    exit_pill(s, EX, 136, EW, "from stage 3: CHANGE")
    line(s, [(EX, 150), (SR, 150)])
    line(s, [(SR, 188), (660, 188), (660, 260)])
    label(s, 560, 182, "3 rounds, still missing")
    exit_pill(s, EX, 260, EW, "→ human_handoff")
    line(s, [(SC, 196), (SC, 260)])
    label(s, SC - 8, 232, "needs_complete", "end")
    exit_pill(s, 230, 260, 260, "→ stage 3: check_eligibility")
    s.legend(20, 320, LEGEND)
    return s


def langgraph_stage_recommendation():
    s = Svg("lg4", 760, 490, "Stage 3, policy recommendation: eligibility, ranking, pricing and the explanation "
                             "run in code and the LLM, then the customer accepts, declines or changes their needs")
    exit_pill(s, SC - 70, 16, 140, "from stage 2")
    line(s, [(SC, 44), (SC, 70)])
    s.node(SX, 70, SW, "check_eligibility", "code")
    line(s, [(SR, 87), (EX, 87)])
    label(s, 520, 80, "eligible_count = 0")
    exit_pill(s, EX, 73, EW, "→ human_handoff")
    line(s, [(SC, 104), (SC, 140)])
    label(s, SC + 8, 126, "eligible_count >= 1", "start")
    s.node(SX, 140, SW, "rank_products", "code")
    line(s, [(SC, 174), (SC, 200)])
    s.node(SX, 200, SW, "quote_premium", "code")
    line(s, [(SR, 217), (EX, 217)])
    label(s, 520, 210, "none priced")
    exit_pill(s, EX, 203, EW, "→ human_handoff")
    line(s, [(SC, 234), (SC, 260)])
    s.node(SX, 260, SW, "explain_recommendation", "llm")
    line(s, [(SC, 294), (SC, 320)])
    s.node(SX, 320, SW, "await_decision", "wait")
    line(s, [(SR, 337), (EX, 337)])
    label(s, 520, 330, "DECLINE")
    s.pill(EX, 323, EW, 28, "stop: DECLINED")
    line(s, [(SX, 337), (200, 337)])
    label(s, 230, 330, "CHANGE")
    exit_pill(s, 20, 323, 180, "→ stage 2: assess_needs")
    line(s, [(SC, 354), (SC, 400)])
    label(s, SC + 8, 382, "ACCEPT", "start")
    exit_pill(s, 240, 400, 240, "→ stage 4: open_application")
    s.legend(20, 460, LEGEND)
    return s


def langgraph_stage_application():
    s = Svg("lg5", 760, 630, "Stage 4, policy application: open the application, collect the parties and the "
                             "answers, summarize, confirm and submit")
    exit_pill(s, SC - 90, 16, 180, "from stage 3: ACCEPT")
    line(s, [(SC, 44), (SC, 70)])
    s.node(SX, 70, SW, "open_application", "code")
    line(s, [(SC, 104), (SC, 140)])
    s.node(SX, 140, SW, "collect_parties", "llm", h=56)
    s.node(10, 148, 150, "ask_customer", "wait", "PARTIES", h=40)
    line(s, [(SX, 156), (160, 156)])
    label(s, 210, 138, "no input yet,")
    label(s, 210, 150, "or a name missing")
    line(s, [(160, 182), (SX, 182)])
    line(s, [(SC, 196), (SC, 240)])
    label(s, SC + 8, 222, "parties_complete", "start")
    s.node(SX, 240, SW, "collect_answers", "llm", h=56)
    s.node(10, 248, 150, "ask_customer", "wait", "ANSWERS", h=40)
    line(s, [(SX, 256), (160, 256)])
    label(s, 210, 250, "fields missing")
    line(s, [(160, 282), (SX, 282)])
    line(s, [(SR, 268), (EX, 268)])
    label(s, 520, 249, "3 rounds, or no")
    label(s, 520, 261, "product fits")
    exit_pill(s, EX, 254, EW, "→ human_handoff")
    line(s, [(SC, 296), (SC, 340)])
    label(s, SC + 8, 328, "answers_complete", "start")
    s.node(SX, 340, SW, "summarize_application", "llm")
    line(s, [(SC, 374), (SC, 400)])
    s.node(SX, 400, SW, "confirm_summary", "wait")
    line(s, [(SX, 417), (220, 417), (220, 316), (300, 316), (300, 296)])
    label(s, 212, 370, "not confirmed", "end")
    line(s, [(SR, 417), (EX, 417)])
    label(s, 520, 410, "3 rejections")
    exit_pill(s, EX, 403, EW, "→ human_handoff")
    line(s, [(SC, 434), (SC, 470)])
    label(s, SC + 8, 456, "confirmed", "start")
    s.node(SX, 470, SW, "submit_application", "code")
    line(s, [(SC, 504), (SC, 540)])
    s.pill(SC - 80, 540, 160, 28, "stop: SUBMITTED")
    s.legend(20, 600, LEGEND)
    return s


def langgraph_handoff():
    s = Svg("lg6", 1070, 440, "Human handoff: each handoff reason leads to human_handoff and await_agent; the "
                              "agent's resolution resumes the session at the node its reason names, or ends it")
    reasons = ["IDENTITY_FAILED", "NEEDS_INCOMPLETE", "NO_ELIGIBLE_PRODUCT", "ANSWERS_INCOMPLETE",
               "SUMMARY_REJECTED", "ERROR (retries ran out)"]
    s.text(125, 36, "handoff_reason", 12, weight="700", op="0.6")
    for i, r in enumerate(reasons):
        cy = 85 + 50 * i
        exit_pill(s, 20, cy - 14, 210, r)
        s.seg([(230, cy), (260, cy)], arrow=False)
    s.seg([(260, 85), (260, 335)], arrow=False)
    line(s, [(260, 210), (290, 210)])
    s.node(290, 193, 180, "human_handoff", "code")
    line(s, [(470, 210), (520, 210)])
    s.node(520, 193, 160, "await_agent", "wait")
    s.text(600, 250, "agent sends VERIFIED,", 11, op="0.8")
    s.text(600, 264, "CONTINUE or END", 11, op="0.8")
    s.text(905, 36, "resumes at", 12, weight="700", op="0.6")
    targets = [
        ("collect_identity", "code", "IDENTITY_FAILED + CONTINUE"),
        ("fetch_purchases", "code", "IDENTITY_FAILED + VERIFIED"),
        ("assess_needs", "llm", "NEEDS_INCOMPLETE, NO_ELIGIBLE_PRODUCT"),
        ("collect_answers", "llm", "ANSWERS_INCOMPLETE"),
        ("summarize_application", "llm", "SUMMARY_REJECTED"),
    ]
    s.seg([(680, 210), (720, 210)], arrow=False)
    s.seg([(720, 60), (720, 360)], arrow=False)
    for i, (name, kind, sub) in enumerate(targets):
        cy = 60 + 50 * i
        line(s, [(720, cy), (760, cy)])
        s.node(760, cy - 20, 290, name, kind, sub, h=40)
    line(s, [(720, 310), (760, 310)])
    s.box(760, 290, 290, 40, "resume_node", ("ERROR: re-runs the node that failed",), dashed=True, mono=True)
    line(s, [(720, 360), (760, 360)])
    label(s, 740, 353, "END")
    s.pill(760, 346, 290, 28, "stop: WITHDRAWN (any reason)")
    s.legend(20, 400, LEGEND)
    return s


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


# ------------------------------------------------------------------ state: where session data lives (level 1)
def state_stores():
    s = Svg("st0", 1100, 420, "Where a session's data lives: the screens talk to the session runtime; the runtime "
                              "resumes the graph and copies a summary into the OnboardingSession row; the graph "
                              "saves its state to the encrypted checkpoint after every node, writes entities to the "
                              "domain DB, reads the catalog and calls the identity system")
    UI, API, G, IDS = (30, 30, 250, 64), (30, 170, 250, 76), (420, 170, 300, 76), (860, 170, 210, 76)
    s.box(*UI, "Customer and agent screens", ("send inputs; read the session and SSE",))
    s.box(*API, "Session runtime (API)", ("one turn per input, under a lock", "mirrors progress after each turn"))
    s.box(*G, "Onboarding graph", ("one thread per session", "nodes read the state and return updates"), color=BLUE)
    s.box(*IDS, "Identity system", ("holds the OTP request", "(external)"), dashed=True)
    SY, SH = 320, 70
    stores = [(30, 250, "OnboardingSession row", ("domain schema", "stage, waiting_for, status")),
              (320, 230, "Checkpoint", ("checkpoint schema", "OnboardingState, AES-encrypted")),
              (590, 230, "Domain DB", ("domain schema", "entity values: Party, Quote, ...")),
              (860, 210, "Catalog", ("catalog schema", "products and rules, read-only"))]
    for x, w, t, sub in stores:
        s.box(x, SY, w, SH, t, sub, color=ORANGE if t == "Checkpoint" else None)
    s.arrow(155, 96, 155, 168, "inputs  /  SSE events", two=True, anchor="start", lx=165, ly=136)
    s.arrow(282, 208, 418, 208, "resume(input)")
    s.arrow(155, 248, 155, 318, "summary after\neach turn", anchor="start", lx=165, ly=278)
    s.arrow(470, 248, 435, 318, "saved after\nevery node", anchor="end", lx=445, ly=278)
    s.arrow(630, 248, 690, 318, "entities,\nthrough ports", anchor="start", lx=668, ly=278)
    s.arrow(710, 248, 930, 318, "reads", dashed=True, anchor="start", lx=830, ly=278)
    s.arrow(722, 208, 858, 208, "checks, OTP")
    return s


# ------------------------------------------------------------------ state: inside the graph state (level 2)
def state_groups():
    s = Svg("st2", 940, 548, "OnboardingState is composed of one TypedDict per domain. Each lists its entity "
                             "references (ids into the domain DB), routing signals, loop guards and transient "
                             "inputs; the conversation part also holds the session context and progress")
    s.group(10, 10, 920, 528, "OnboardingState: one TypedDict per domain that writes the fields")
    X, W, Y0, GAP = (30, 330, 630), 280, 44, 16
    cols = [
        [("ConversationState", [
            ("context  (set by the API)", ["session_id", "party_id  → Party", "market, locale", "actor, mode"]),
            ("progress", ["stage", "waiting_for", "last_input", "form_topic"]),
            ("conversation  (appended)", ["messages"]),
            ("intake", ["intake  {text}", "product_interest"]),
        ])],
        [("IdentityState", [
            ("ids", ["otp_request_id  → identity system"]),
            ("signals", ["identity_result", "identity_topics"]),
            ("transient", ["otp_code  {code}"]),
        ]), ("ProfilingState", [
            ("ids", ["needs_assessment_id  → NeedsAssessment", "insurable_object_ids  → InsurableObject"]),
            ("signals", ["needs_complete"]),
            ("guards", ["needs_rounds"]),
            ("transient", ["needs_input  {topic, fields, text}"]),
        ]), ("RecommendationState", [
            ("ids", ["recommendation_ids  → Recommendation", "quote_ids  → Quote"]),
            ("signals", ["eligible_count", "decision"]),
        ])],
        [("ApplicationState", [
            ("ids", ["application_id  → Application"]),
            ("signals", ["parties_complete", "answers_complete", "confirmed", "correcting"]),
            ("guards", ["answers_rounds", "confirm_rejections"]),
        ]), ("HandoffState", [
            ("signals", ["handoff_reason", "handoff_resolution"]),
            ("recovery", ["resume_node", "resume_stage", "last_error"]),
        ])],
    ]
    for x, boxes in zip(X, cols):
        y = Y0
        for title, groups in boxes:
            y += s.ebox(x, y, W, title, groups) + GAP
    return s


# ------------------------------------------------------------------ state: one turn (level 3)
def state_turn():
    s = Svg("st3", 1170, 624, "One turn: the screen posts an input; the runtime marks the session as processing and "
                              "resumes the graph; each node reads and writes entities and returns an update that is "
                              "merged and checkpointed; edges read routing signals until the graph waits again; the "
                              "runtime then copies the new stage and wait into the session row and publishes SSE events")
    lanes = [(100, "Screen", None), (330, "Session runtime", None), (580, "Graph", BLUE),
             (850, "Checkpoint", ORANGE), (1070, "Domain DB", None)]
    TOP, BOT = 20, 614
    for cx, name, color in lanes:
        s.box(cx - 85, TOP, 170, 40, name, (), color=color)
        s.p.append(f'<line x1="{cx}" y1="{TOP + 40}" x2="{cx}" y2="{BOT}" stroke="currentColor" '
                   f'stroke-opacity="0.25" stroke-dasharray="4 4"/>')
    SC, RT, GR, CP, DB = (x for x, _, _ in lanes)
    s.group(GR - 170, 258, DB + 70 - (GR - 170), 222, "per node, until the graph waits for a person")

    def msg(n, x1, x2, y, t, dashed=False):
        # The number sits where the message starts, and the label runs from it along the arrow.
        s.arrow(x1, y, x2, y, dashed=dashed)
        d = 1 if x2 > x1 else -1
        s._num(x1 + d * 16, y - 14, n)
        s.text(x1 + d * 32, y - 9, t, 11.5, anchor="start" if d > 0 else "end", op="0.8")

    def note(n, y, lines):
        w, h = 252, 18 + 15 * len(lines)
        x = GR + 14
        s.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="currentColor" '
                   f'fill-opacity="0.06" stroke="currentColor" stroke-opacity="0.45" stroke-width="1.3"/>')
        s._num(x + 16, y + 16, n)
        for i, t in enumerate(lines):
            s.text(x + 32, y + 20 + i * 15, t, 11.5, anchor="start", op="0.85")

    msg(1, SC, RT, 96, "input (must match waiting_for)")
    msg(2, RT, DB, 136, "session row: waiting_for = null (processing)")
    msg(3, RT, GR, 176, "resume + actor, mode, locale")
    note(4, 194, ["ask_customer returns the input:", "last_input, otp_code / needs_input"])
    msg(5, GR, DB, 316, "read and write entities (deterministic ids, upsert)")
    msg(6, GR, CP, 356, "update merged, then saved (gzip, AES)")
    msg(7, GR, SC, 396, "new messages, streamed as SSE message.appended", dashed=True)
    note(8, 414, ["edge reads routing signals only:", "next node, or an interrupt (waiting_for)"])
    msg(9, RT, CP, 520, "snapshot: stage, waiting_for, next node")
    msg(10, RT, DB, 560, "session row: last_stage, waiting_for, current_node, status")
    msg(11, RT, SC, 600, "SSE session.updated, prompt.updated")
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


# ------------------------------------------------------------------ data model: groups (level 1)
def data_model_groups():
    s = Svg("dm1", 1040, 420, "The four entity groups: customer and transaction entities in the domain schema, "
                              "reference data in the catalog schema, and the policy in the contract admin system")

    def group_box(x, y, w, h, name, entities, notes, dashed=False):
        s.box(x, y, w, h, "", (), dashed=dashed)
        s.p.pop()  # drop the empty title
        s.text(x + w / 2, y + 26, name, 14, weight="650")
        for i, e in enumerate(entities):
            s.p.append(f'<text x="{x + w / 2}" y="{y + 48 + i * 16}" font-size="12" text-anchor="middle" '
                       f'fill="currentColor" {MONOF}>{esc(e)}</text>')
        for i, n in enumerate(notes):
            s.text(x + w / 2, y + h - 30 + i * 15, n, 11.5, op="0.72")

    s.group(20, 20, 650, 250, "domain schema")
    s.group(720, 20, 300, 250, "catalog schema")
    group_box(40, 56, 260, 190, "Customer", ["Party", "NeedsAssessment", "InsurableObject"],
              ["changed by the workflow", "lives as long as the customer"])
    group_box(390, 56, 260, 190, "Transaction",
              ["OnboardingSession", "Recommendation", "Quote", "Application", "ApplicationParty"],
              ["changed by the workflow", "one onboarding each"])
    group_box(740, 56, 260, 190, "Reference", ["Product", "EligibilityRule", "TargetMarket"],
              ["seeded at backend startup", "while a product is on sale"])
    group_box(390, 310, 260, 90, "Result", ["Policy"], ["contract admin system, no table"], dashed=True)
    s.arrow(388, 151, 302, 151)
    label(s, 345, 132, "for one customer,")
    label(s, 345, 144, "on their needs")
    s.arrow(652, 151, 738, 151)
    label(s, 695, 132, "recommends,")
    label(s, 695, 144, "prices")
    s.arrow(520, 248, 520, 308)
    label(s, 528, 282, "a submitted application becomes one", "start")
    return s


# ------------------------------------------------------------------ data model: entities (level 2)
def data_model_entities():
    s = Svg("dm2", 1010, 640, "Every entity and how they relate, without fields: reference entities on the left, "
                              "transaction entities in the middle, customer entities on the right")
    W, H = 200, 36

    def ent(x, y, name, dashed=False):
        s.box(x, y, W, H, name, (), mono=True, dashed=dashed)

    s.group(10, 40, 220, 350, "Reference (catalog)")
    s.group(330, 20, 320, 590, "Transaction")
    s.group(740, 20, 250, 300, "Customer")

    # reference
    ent(20, 80, "EligibilityRule")
    ent(20, 200, "Product")
    ent(20, 320, "TargetMarket")
    s.seg([(120, 116), (120, 200)], arrow=False)
    label(s, 128, 150, "requires", "start")
    label(s, 128, 164, "n : 1", "start")
    s.seg([(120, 236), (120, 320)], arrow=False)
    label(s, 128, 270, "fits", "start")
    label(s, 128, 284, "1 : n", "start")

    # transaction
    ent(380, 60, "OnboardingSession")
    ent(380, 180, "Recommendation")
    ent(380, 300, "Quote")
    ent(380, 420, "Application")
    ent(380, 540, "ApplicationParty")
    s.seg([(440, 96), (440, 180)], arrow=False)
    label(s, 448, 134, "produced", "start")
    label(s, 448, 148, "1 : n", "start")
    s.seg([(480, 216), (480, 300)], arrow=False)
    label(s, 488, 254, "priced as", "start")
    label(s, 488, 268, "1 : n", "start")
    s.seg([(480, 336), (480, 420)], arrow=False)
    label(s, 488, 374, "accepted price", "start")
    label(s, 488, 388, "1 : 0..1", "start")
    s.seg([(480, 456), (480, 540)], arrow=False)
    label(s, 488, 494, "roles", "start")
    label(s, 488, 508, "1 : 1..n", "start")
    s.seg([(580, 212), (620, 212), (620, 432), (580, 432)], arrow=False)
    label(s, 628, 322, "accepted into", "start")
    label(s, 628, 336, "1 : 0..1", "start")
    s.seg([(380, 72), (350, 72), (350, 448), (380, 448)], arrow=False)
    label(s, 342, 330, "produced", "end")
    label(s, 342, 344, "1 : n", "end")
    s.seg([(220, 194), (380, 194)], arrow=False)
    label(s, 290, 186, "recommends  1 : n")

    # customer
    CW = 170
    s.box(770, 60, CW, H, "Party", (), mono=True)
    s.box(770, 170, CW, H, "NeedsAssessment", (), mono=True)
    s.box(770, 250, CW, H, "InsurableObject", (), mono=True)
    s.seg([(820, 96), (820, 170)], arrow=False)
    label(s, 812, 130, "versions", "end")
    label(s, 812, 144, "1 : n", "end")
    s.seg([(940, 88), (958, 88), (958, 268), (940, 268)], arrow=False)
    label(s, 950, 232, "owns  1 : n", "end")
    s.seg([(770, 78), (580, 78)], arrow=False)
    label(s, 675, 70, "customer  1 : n")
    s.seg([(770, 188), (580, 188)], arrow=False)
    label(s, 690, 180, "based on  1 : n")
    s.seg([(770, 268), (700, 268), (700, 202), (580, 202)], arrow=False)
    label(s, 712, 234, "covers", "start")
    label(s, 712, 248, "0..1 : n", "start")
    s.seg([(940, 70), (982, 70), (982, 558), (580, 558)], arrow=False)
    label(s, 790, 550, "plays  1 : n")

    # result
    s.box(770, 420, 170, H, "Policy", (), mono=True, dashed=True)
    s.seg([(580, 444), (770, 444)], dashed=True)
    label(s, 700, 436, "becomes (outside)")
    s.text(855, 474, "contract admin system", 11, op="0.6")
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
    langgraph_stages().save("docs/design/assets/langgraph-stages.svg")
    langgraph_stage_identity().save("docs/design/assets/langgraph-stage-identity.svg")
    langgraph_stage_profiling().save("docs/design/assets/langgraph-stage-profiling.svg")
    langgraph_stage_recommendation().save("docs/design/assets/langgraph-stage-recommendation.svg")
    langgraph_stage_application().save("docs/design/assets/langgraph-stage-application.svg")
    langgraph_handoff().save("docs/design/assets/langgraph-handoff.svg")
    langgraph_graph().save("docs/design/assets/langgraph-graph.svg")
    state_stores().save("docs/design/assets/state-stores.svg")
    state_groups().save("docs/design/assets/state-groups.svg")
    state_turn().save("docs/design/assets/state-turn.svg")
    state_checkpoint_encryption().save("docs/design/assets/state-checkpoint-encryption.svg")
    data_model_groups().save("docs/design/assets/data-model-groups.svg")
    data_model_entities().save("docs/design/assets/data-model-entities.svg")
    data_model_er().save("docs/design/assets/data-model-er.svg")

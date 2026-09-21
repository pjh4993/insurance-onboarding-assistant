"""Diagrams for README.md and docs/design/01-solution-architecture.md.

Run from the repo root: `uv run --no-project python tools/diagrams/solution_architecture.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from svglib import BLUE, GREEN, MONO, ORANGE, PURPLE, Svg, esc  # noqa: E402


def title(s, txt):
    s.text(s.w / 2, 24, txt, 14, weight="700", op="0.6")
    s.rule(8, 34, s.w - 8, op="0.15")


def mbox(s, x, y, w, h, titles, subs=(), color=None, dashed=False, mono=False, radius=6):
    """A box whose title spans several bold lines, followed by lighter sub-lines."""
    s.box(x, y, w, h, "", (), color=color, dashed=dashed, radius=radius)
    s.p.pop()  # drop the empty title <text>
    f = MONO if mono else ""
    lines = [(t, True) for t in titles] + [(t, False) for t in subs]
    total = sum(17 if b else 15 for _, b in lines) - 3
    yy = y + h / 2 - total / 2 + 10
    cx = x + w / 2
    for t, bold in lines:
        if bold:
            s.p.append(f'<text x="{cx}" y="{yy}" font-size="14" text-anchor="middle" fill="currentColor" '
                       f'font-weight="650" {f}>{esc(t)}</text>')
            yy += 17
        else:
            s.p.append(f'<text x="{cx}" y="{yy}" font-size="11.5" text-anchor="middle" fill="currentColor" '
                       f'fill-opacity="0.72">{esc(t)}</text>')
            yy += 15


def person(s, x, y, w, h, name, sub):
    """A person or browser: a stadium shape, as in the C4 context diagrams."""
    s.box(x, y, w, h, name, (sub,) if sub else (), radius=h / 2)


def cylinder(s, x, y, w, h, name, subs=(), mono=False):
    ry = 7
    rx = w / 2
    s.p.append(f'<path d="M{x} {y + ry} A{rx} {ry} 0 0 1 {x + w} {y + ry} V{y + h - ry} '
               f'A{rx} {ry} 0 0 1 {x} {y + h - ry} Z" fill="currentColor" fill-opacity="0.05" '
               f'stroke="currentColor" stroke-opacity="0.45" stroke-width="1.6"/>')
    s.p.append(f'<path d="M{x} {y + ry} A{rx} {ry} 0 0 0 {x + w} {y + ry}" fill="none" '
               f'stroke="currentColor" stroke-opacity="0.45" stroke-width="1.6"/>')
    f = MONO if mono else ""
    cy = y + ry + (h - ry) / 2
    ty = cy - len(subs) * 8 + 5
    s.p.append(f'<text x="{x + w / 2}" y="{ty}" font-size="14" text-anchor="middle" fill="currentColor" '
               f'font-weight="650" {f}>{esc(name)}</text>')
    for i, t in enumerate(subs):
        s.p.append(f'<text x="{x + w / 2}" y="{ty + 17 + i * 15}" font-size="11.5" text-anchor="middle" '
                   f'fill="currentColor" fill-opacity="0.72">{esc(t)}</text>')


def legend(s, x, y, items):
    """Legend entries: (color, label) for a filled swatch, ("dashed", label) for an external system."""
    bx = x
    for col, lab in items:
        if col == "dashed":
            s.p.append(f'<rect x="{bx}" y="{y}" width="22" height="14" rx="4" fill="currentColor" '
                       f'fill-opacity="0.05" stroke="currentColor" stroke-opacity="0.6" stroke-width="1.4" '
                       f'stroke-dasharray="4 3"/>')
        else:
            s.p.append(f'<rect x="{bx}" y="{y}" width="22" height="14" rx="4" fill="{col}" '
                       f'fill-opacity="0.14" stroke="{col}" stroke-width="1.6"/>')
        s.text(bx + 30, y + 11.5, lab, 12, anchor="start", op="0.8")
        bx += 30 + len(lab) * 6.6 + 28


# ------------------------------------------------------------------ README overview
def overview():
    s = Svg("sa1", 1040, 450, "Overview: customers and support agents use the Next.js frontend, which relays "
                              "to the FastAPI and LangGraph backend; the backend uses PostgreSQL and four "
                              "external systems that are mocked locally.")
    title(s, "Two services, one database, four external systems")

    person(s, 20, 90, 140, 56, "Customer", "/s/{token}")
    person(s, 20, 226, 140, 56, "Support agent", "/agent")

    s.group(185, 56, 240, 250, "Frontend service: Next.js")
    mbox(s, 205, 90, 200, 56, ["Customer app"], ["+ agent console"], color=GREEN)
    mbox(s, 205, 220, 200, 56, ["/api/* relay"], ["(incl. SSE)"], color=GREEN)

    s.group(450, 160, 270, 146, "Backend service: FastAPI + LangGraph")
    s.box(470, 213, 230, 70, "Onboarding graph", ("code / LLM / wait nodes",), color=GREEN)

    cylinder(s, 470, 336, 230, 60, "PostgreSQL", ("checkpoint · domain · catalog",))

    s.group(750, 56, 270, 340, "External systems (mock locally)")
    ext = [("Partner", 90), ("Identity (OTP, document)", 164), ("Contract admin", 238),
           ("Bedrock: Claude Sonnet 4.6", 312)]
    for name, y in ext:
        s.box(770, y, 230, 54, name, dashed=True)

    s.arrow(162, 118, 203, 118)
    s.arrow(162, 246, 203, 140)
    s.arrow(305, 148, 305, 218)
    s.arrow(407, 248, 468, 248)
    s.arrow(585, 285, 585, 334)
    for i, (_, y) in enumerate(ext):
        s.arrow(702, 236 + i * 8, 768, y + 27)

    legend(s, 20, 420, [(GREEN, "Built in this repo"), ("dashed", "External system, mocked locally")])
    s.save("docs/assets/overview.svg")


# ------------------------------------------------------------------ 1. System context
def context():
    s = Svg("sa2", 1010, 470, "System context: customers and support agents use the onboarding assistant, "
                              "which calls the partner system, the identity provider, the contract admin "
                              "system and Amazon Bedrock.")
    title(s, "Who uses the system and what it talks to")

    person(s, 20, 110, 180, 62, "Customer", "(no account, session link)")
    person(s, 20, 300, 180, 62, "Support agent", "(staff account)")

    s.group(360, 44, 210, 382, "Onboarding assistant")
    s.box(380, 70, 170, 336, "Frontend + Backend", color=GREEN)

    ext = [("Partner system", "purchase records"), ("Identity provider", "OTP + ID document check"),
           ("Contract admin system", "receives applications"), ("Amazon Bedrock", "Claude Sonnet 4.6")]
    labels = ["match customer, read purchases\n(only with consent)", "send / verify OTP, verify document",
              "submit application", "extract, explain, summarize"]
    for i, ((name, sub), lab) in enumerate(zip(ext, labels)):
        y = 74 + i * 90
        s.box(800, y, 190, 58, name, (sub,), dashed=True)
        cy = y + 29
        n = lab.count("\n") + 1
        s.arrow(552, cy, 798, cy, lab, ly=cy - 8 - (n - 1) * 14)

    s.arrow(202, 141, 378, 141, "onboards through chat", ly=133)
    s.arrow(202, 331, 378, 331, "watches sessions,\ntakes over", ly=309)

    legend(s, 20, 442, [(GREEN, "Built in this repo"), ("dashed", "External system")])
    s.save("docs/design/assets/solution-architecture-context.svg")


# ------------------------------------------------------------------ 2. Containers
def containers():
    s = Svg("sa3", 1000, 736, "Containers: the browser reaches the customer app and agent console in the "
                              "Next.js frontend, whose route handlers relay to the FastAPI backend; the backend "
                              "runs the onboarding graph and domain code over three PostgreSQL schemas and "
                              "calls the mock service.")
    title(s, "What is deployed and how the parts talk")

    person(s, 380, 50, 160, 40, "Browser", None)

    s.group(120, 110, 600, 200, "Frontend service (Next.js)")
    s.box(160, 145, 200, 56, "Customer app", ("/s/*",), color=GREEN)
    s.box(480, 145, 200, 56, "Agent console", ("/agent/*",), color=GREEN)
    s.box(340, 236, 240, 56, "Route handlers", ("/api/* (relay + SSE)",), color=GREEN)

    s.box(770, 130, 210, 86, "Mock service", ("/partner /identity /contract", "/model/{id}/converse"),
          dashed=True)

    s.group(40, 390, 920, 116, "")  # label on the right, clear of the arrow coming in on the left
    s.text(948, 408, "Backend service (FastAPI + LangGraph)", 12, anchor="end", weight="700", op="0.95")
    s.box(80, 422, 200, 56, "HTTP API + SSE", color=GREEN)
    s.box(400, 422, 200, 56, "Onboarding graph", color=GREEN)
    mbox(s, 720, 422, 200, 56, ["Eligibility, ranking,", "pricing (code)"], color=GREEN)

    s.group(200, 562, 740, 124, "")  # label at the bottom, clear of the arrows coming in on top
    s.text(212, 676, "PostgreSQL (one instance)", 12, anchor="start", weight="700", op="0.95")
    cylinder(s, 240, 584, 200, 52, "domain schema")
    cylinder(s, 480, 584, 200, 52, "checkpoint schema")
    cylinder(s, 720, 584, 200, 52, "catalog schema")

    s.arrow(435, 92, 285, 143)
    s.arrow(485, 92, 555, 143)
    s.arrow(300, 203, 400, 234)
    s.arrow(540, 203, 520, 234)
    s.arrow(400, 294, 200, 420, "HTTP, internal only", anchor="end", lx=300, ly=350)
    s.arrow(282, 450, 398, 450)
    s.arrow(602, 450, 718, 450)
    s.seg([(560, 420), (560, 352), (875, 352), (875, 218)])
    s.text(718, 330, "local and develop: mock", 11.5, op="0.75")
    s.text(718, 344, "prod: real endpoints", 11.5, op="0.75")
    s.arrow(540, 480, 575, 582)
    s.arrow(460, 480, 385, 582)
    s.arrow(200, 480, 300, 582)
    s.arrow(820, 480, 820, 582)

    legend(s, 40, 704, [(GREEN, "Built in this repo"), ("dashed", "Mock of the external systems")])
    s.save("docs/design/assets/solution-architecture-containers.svg")


# ------------------------------------------------------------------ Backend packages
def packages():
    s = Svg("sa4", 950, 222, "Backend packages: the app API service depends on onboarding-agent and "
                             "onboarding-core, and onboarding-agent depends on onboarding-core.")
    title(s, "Three packages in one uv workspace; an arrow means depends on")

    s.box(30, 66, 250, 86, "app/ (API service)", ("FastAPI, sessions, SSE,", "SQLAlchemy + HTTP adapters"),
          mono=True)
    s.box(350, 66, 250, 86, "onboarding-agent", ("graph, nodes, routing,", "LLM, checkpointer, runner"),
          mono=True)
    s.box(670, 66, 250, 86, "onboarding-core", ("entities, eligibility, pricing,", "catalog seed, ports"),
          mono=True)

    s.arrow(282, 109, 348, 109)
    s.arrow(602, 109, 668, 109)
    s.seg([(155, 154), (155, 200), (795, 200), (795, 156)])
    s.save("docs/design/assets/solution-architecture-packages.svg")


# ------------------------------------------------------------------ 3. Inside the backend
def backend():
    s = Svg("sa5", 1080, 470, "Inside the backend: the HTTP API hands input to the runtime and checkpointer, "
                              "which resume the graph; code nodes call the decision logic and the partner, "
                              "identity and contract clients, LLM nodes call Bedrock, and the graph persists "
                              "through the SQLAlchemy models.")
    title(s, "Inside the backend service")

    s.group(20, 50, 300, 400, "Edge")
    s.box(40, 90, 260, 50, "HTTP API")
    s.box(40, 190, 260, 62, "Runtime: session lookup,", ("per-session lock, SSE broker",))
    s.box(40, 300, 260, 62, "Checkpointer", ("(AsyncPostgresSaver, gzip + AES serde)",))
    s.arrow(170, 142, 170, 188)
    s.arrow(170, 254, 170, 298)
    s.arrow(302, 331, 358, 331)

    s.group(360, 50, 260, 400, "Graph")
    s.box(380, 90, 220, 50, "Code nodes", color=BLUE)
    s.box(380, 195, 220, 50, "LLM nodes", color=PURPLE)
    s.box(380, 306, 220, 50, "Wait nodes (interrupt)", color=ORANGE)

    s.group(680, 50, 380, 164, "Decision logic")
    for i, name in enumerate(["Eligibility rules", "Ranking", "Pricing"]):
        s.box(700, 76 + i * 44, 340, 34, name)

    s.group(680, 238, 380, 212, "Adapters")
    mbox(s, 700, 266, 340, 52, ["Partner / Identity / Contract clients"], ["(httpx)"])
    s.box(700, 330, 340, 40, "ChatBedrockConverse", mono=True)
    mbox(s, 700, 384, 340, 52, ["SQLAlchemy models"], ["(domain, catalog)"])

    s.arrow(602, 108, 678, 108)
    s.seg([(602, 128), (660, 128), (660, 292), (698, 292)])
    s.seg([(602, 220), (640, 220), (640, 350), (698, 350)])
    s.arrow(622, 410, 698, 410)

    s.save("docs/design/assets/solution-architecture-backend.svg")


if __name__ == "__main__":
    overview()
    context()
    containers()
    packages()
    backend()

"""Infrastructure diagrams for docs/infra/. Run from the repo root:

    uv run --no-project python tools/diagrams/infra.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from svglib import GREEN, ORANGE, Svg  # noqa: E402

OUT = "docs/infra/assets"


def note(s, x, y, txt):
    s.text(x, y, txt, 11.5, anchor="start", op="0.7")


def aws_overview():
    s = Svg("aw1", 1240, 640, "AWS overview: the browser reaches Route 53 and the ALB; inside the VPC the ALB sends "
                              "agent logins to Cognito and traffic to the frontend, which calls the backend and mock "
                              "over Service Connect; the backend uses RDS and reaches Bedrock, Secrets Manager, ECR "
                              "and CloudWatch Logs through VPC endpoints, with KMS encrypting secrets and RDS.")
    s.box(20, 170, 140, 60, "Customer / agent", ("browser",), dashed=True, radius=30)
    s.group(190, 20, 1030, 580, "AWS account, ap-northeast-2")
    s.box(210, 60, 210, 54, "Route 53 + ACM", ("dev. + dev.docs.onboardassist.click",))
    s.box(450, 60, 200, 54, "Cognito", ("user pool (agents)",))
    s.group(210, 140, 720, 410, "VPC 10.0.0.0/16")
    s.box(230, 180, 290, 54, "ALB", ("HTTPS 443 (HTTP 80 without a domain)",))
    s.group(230, 262, 680, 120, "ECS cluster (Fargate)")
    s.box(260, 300, 170, 54, "frontend service", color=GREEN)
    s.box(540, 300, 140, 54, "backend service", color=GREEN)
    s.box(785, 300, 115, 54, "mock service", ("(develop only)",), color=GREEN, dashed=True)
    s.box(240, 440, 250, 54, "RDS PostgreSQL 16", ("checkpoint / domain / catalog",))
    s.box(620, 420, 280, 80, "VPC endpoints", ("bedrock-runtime, secretsmanager,", "ecr.api, ecr.dkr, logs, s3"))
    right = [("Bedrock", ("global.anthropic.claude-sonnet-4-6",)), ("Secrets Manager", ()), ("ECR", ()),
             ("CloudWatch Logs", ())]
    ys = [60, 150, 230, 310]
    for (t, sub), y in zip(right, ys):
        s.box(970, y, 230, 54 if sub else 50, t, sub)
    s.box(970, 440, 230, 50, "KMS")

    s.arrow(160, 186, 208, 100)  # user -> Route 53
    s.arrow(160, 207, 228, 207)  # user -> ALB
    s.arrow(500, 178, 540, 116, "/agent/* login", dashed=True, anchor="start", lx=528, ly=160)
    s.arrow(400, 234, 400, 298)  # ALB -> frontend
    s.arrow(430, 327, 538, 327, "Service Connect\n:8000", ly=305)
    s.arrow(680, 327, 783, 327, "Service Connect\n:8080", ly=305)
    s.arrow(575, 356, 430, 438, "TLS :5432", anchor="end", lx=440, ly=404)
    s.arrow(640, 356, 700, 418)  # backend -> VPC endpoints
    targets = [87, 175, 255, 335]
    for i, ty in enumerate(targets):
        s.arrow(902, 430 + i * 12, 968, ty)
    s.arrow(1085, 362, 1085, 438, dashed=True)  # Secrets Manager -> KMS
    s.seg([(365, 496), (365, 570), (1085, 570), (1085, 492)], dashed=True)  # RDS -> KMS
    s.legend(20, 614, [(GREEN, "project services")])
    note(s, 190, 626, "dashed box = external or develop only · dashed arrow = login redirect / encryption key")
    s.save(f"{OUT}/aws-overview.svg")


def networking_topology():
    s = Svg("nw1", 720, 560, "Network topology: the internet gateway talks to the public tier; the private app tier "
                             "goes out through NAT in the public tier and reaches the private data tier; each tier "
                             "has one subnet in 2a and one in 2c.")
    s.box(260, 20, 200, 44, "Internet gateway")
    s.group(20, 90, 680, 450, "VPC 10.0.0.0/16")
    tiers = [
        ("Public tier", [("10.0.0.0/24 (2a)", "ALB, NAT"), ("10.0.1.0/24 (2c)", "ALB, NAT (prod)")]),
        ("Private app tier", [("10.0.10.0/24 (2a)", "ECS tasks, interface endpoints"),
                             ("10.0.11.0/24 (2c)", "ECS tasks, interface endpoints (prod)")]),
        ("Private data tier", [("10.0.20.0/24 (2a)", "RDS"), ("10.0.21.0/24 (2c)", "RDS standby (prod)")]),
    ]
    for i, (label, boxes) in enumerate(tiers):
        y = 120 + i * 140
        s.group(40, y, 640, 100, label)
        for j, (t, sub) in enumerate(boxes):
            s.box(60 + j * 310, y + 32, 290, 54, t, (sub,), mono=True)
    s.arrow(360, 66, 360, 118, two=True)  # igw <-> public tier
    s.arrow(360, 258, 360, 222, "outbound via NAT", anchor="start", lx=370, ly=244)  # app -> public
    s.arrow(360, 362, 360, 398)  # app -> data
    s.save(f"{OUT}/networking-topology.svg")


def networking_request_sequence():
    names = [("Browser", ()), ("ALB", ()), ("Frontend", ("(Next.js)",)), ("Backend", ("(FastAPI)",)),
             ("Mock", ("(develop)",)), ("RDS", ()), ("Bedrock", ("(VPC endpoint)",))]
    step, x0 = 170, 90
    cx = [x0 + i * step for i in range(len(names))]
    B, A, F, K, M, D, R = range(7)
    msgs = [  # (from, to, label lines, reply, anchor)
        (B, A, ["HTTPS 443", "(HTTP 80 without a domain)"], False, "middle"),
        (A, F, ["HTTP 3000"], False, "middle"),
        (F, K, ["HTTP 8000 via", "Service Connect", "(http://backend:8000)"], False, "middle"),
        (K, D, ["PostgreSQL 5432, TLS"], False, "start"),
        (K, M, ["HTTP 8080 via", "Service Connect", "(http://mock:8080)"], False, "middle"),
        (K, R, ["HTTPS 443"], False, "start"),
        (K, F, ["SSE stream"], True, "middle"),
        (F, B, ["SSE stream", "(passed through)"], True, "middle"),
    ]
    y, rows = 96, []
    for m in msgs:
        y += 14 * len(m[2]) + 18
        rows.append(y)
    h = rows[-1] + 30
    s = Svg("nw2", x0 * 2 + step * 6, h, "Request sequence: browser to ALB over HTTPS, ALB to frontend on 3000, "
                                           "frontend to backend on 8000 via Service Connect, backend to RDS, mock "
                                           "and Bedrock, then the SSE stream flows back to the browser.")
    for (t, sub), x in zip(names, cx):
        s.box(x - 70, 20, 140, 52, t, sub)
        s.p.append(f'<line x1="{x}" y1="72" x2="{x}" y2="{h - 12}" stroke="currentColor" '
                   f'stroke-opacity="0.35" stroke-width="1.2" stroke-dasharray="4 4"/>')
    for (a, b, lines, reply, anchor), yy in zip(msgs, rows):
        d = 1 if b > a else -1
        x1, x2 = cx[a] + d * 2, cx[b] - d * 3
        ly = yy - 8 - (len(lines) - 1) * 14
        # centre the label in the gap next to the sender, so it never sits across another lifeline
        lx = cx[a] + 10 if anchor == "start" else (cx[a] + cx[a + d]) / 2
        s.arrow(x1, yy, x2, yy, "\n".join(lines), dashed=reply, anchor=anchor, lx=lx, ly=ly)
    s.save(f"{OUT}/networking-request-sequence.svg")


def networking_boundaries():
    s = Svg("nw3", 1030, 190, "Security boundaries: browser on the internet, ALB with Cognito at the edge, frontend "
                              "and backend in private subnets, RDS in a data boundary with no internet; each hop is "
                              "only reachable from the one before it.")
    y, h = 78, 62
    s.group(20, 30, 130, 140, "Internet")
    s.box(35, y + 6, 100, 50, "Browser", dashed=True, radius=25)
    s.group(186, 30, 182, 140, "Edge boundary")
    s.box(202, y, 150, h, "ALB + Cognito", ("(agents)",))
    s.group(404, 30, 382, 140, "App boundary (private subnets)")
    s.box(420, y, 160, h, "Frontend", ("attaches caller", "identity"), color=GREEN)
    s.box(610, y, 160, h, "Backend", ("only reachable", "from frontend"), color=GREEN)
    s.group(822, 30, 188, 140, "Data boundary (no internet)")
    s.box(838, y, 156, h, "RDS", ("only reachable", "from backend"))
    cy = y + h / 2
    for x1, x2 in ((135, 200), (352, 418), (580, 608), (770, 836)):
        s.arrow(x1, cy, x2, cy)
    s.save(f"{OUT}/networking-boundaries.svg")


def terraform_layout():
    s = Svg("tf1", 740, 600, "Terraform layout: bootstrap provides remote state to envs/develop or envs/prod, whose "
                             "main.tf composes the network, security, data, edge, ci, auth and three service "
                             "modules; network feeds security and edge, security feeds data, auth feeds edge, and "
                             "edge feeds the frontend service.")
    s.box(30, 80, 240, 56, "bootstrap", ("state bucket + lock table",), mono=True)
    s.group(20, 210, 262, 150, "envs/develop or envs/prod")
    s.box(40, 244, 222, 90, "main.tf", ("composes modules,", "ECS cluster, namespace"), color=GREEN, mono=True)
    s.arrow(150, 138, 150, 208, "remote state", dashed=True, anchor="start", lx=160, ly=178)
    mods = [("network", ()), ("security", ()), ("data", ()), ("auth", ("(only if domain_name set)",)),
            ("edge", ()), ("service", ("(frontend)",)), ("ci", ()), ("service", ("(backend)",)),
            ("service", ("(mock, only if enable_mocks)",))]
    x, w, bh, top, step = 420, 230, 46, 20, 62
    ys = [top + i * step for i in range(len(mods))]
    for (t, sub), yy in zip(mods, ys):
        s.box(x, yy, w, bh, t, sub, mono=True)
    for i, yy in enumerate(ys):  # main -> every module
        s.arrow(264, 254 + i * 9, x - 2, yy + bh / 2)
    ix = {n: i for i, n in enumerate(["network", "security", "data", "auth", "edge", "svc_fe"])}

    def down(a, b):
        s.arrow(x + w / 2, ys[ix[a]] + bh, x + w / 2, ys[ix[b]] - 2)

    down("network", "security")
    down("security", "data")
    down("auth", "edge")
    down("edge", "svc_fe")
    s.seg([(x + w, ys[0] + bh / 2), (x + w + 40, ys[0] + bh / 2), (x + w + 40, ys[4] + bh / 2),
           (x + w + 2, ys[4] + bh / 2)])  # network -> edge
    s.save(f"{OUT}/terraform-layout.svg")


def cicd_pipeline():
    s = Svg("cd1", 960, 330, "CI/CD pipeline: pull requests and pushes to develop or main run ci.yml; a push to "
                             "develop runs deploy-develop.yml; fast-forwarding main to that SHA, after approval, "
                             "runs deploy-prod.yml with the same image.")
    s.box(20, 20, 150, 100, "Pull request", ("or push to", "develop / main"))
    s.box(230, 20, 200, 100, "ci.yml", ("lint, test, build,", "terraform fmt/validate,", "docker build"),
          color=GREEN, mono=True)
    s.box(20, 170, 150, 100, "Push to develop")
    s.box(220, 170, 200, 100, "deploy-develop.yml",
          ("push images (tag = SHA)", "terraform apply develop", "wait for ECS", "smoke test"), color=GREEN, mono=True)
    s.box(470, 170, 230, 100, "Fast-forward main", ("to that SHA", "+ approval (Environment: prod)"), color=ORANGE)
    s.box(750, 170, 190, 100, "deploy-prod.yml",
          ("same image SHA", "terraform apply prod", "wait for ECS", "smoke test"), color=GREEN, mono=True)
    s.arrow(170, 70, 228, 70)
    s.arrow(170, 220, 218, 220)
    s.arrow(420, 220, 468, 220)
    s.arrow(700, 220, 748, 220)
    s.legend(20, 300, [(GREEN, "GitHub Actions workflow")])
    s.legend(230, 300, [(ORANGE, "manual step")])
    s.save(f"{OUT}/cicd-pipeline.svg")


if __name__ == "__main__":
    aws_overview()
    networking_topology()
    networking_request_sequence()
    networking_boundaries()
    terraform_layout()
    cicd_pipeline()

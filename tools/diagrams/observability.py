"""Diagram for docs/design/05-observability.md.

Run from the repo root: `uv run --no-project python tools/diagrams/observability.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from solution_architecture import cylinder, legend, person, title  # noqa: E402
from svglib import GREEN, Svg  # noqa: E402


def where_watched():
    s = Svg("ob1", 1080, 470, "Where the system is watched: GitHub Actions probes the deployed hosts, ECS, the ALB "
                              "and RDS report to CloudWatch, the frontend and backend export traces and logs to "
                              "Grafana Cloud, and support agents watch each session in the agent console.")
    title(s, "Four places the system is watched from")

    # 1. probes from outside
    s.box(20, 56, 180, 66, "GitHub Actions", ("deploy smoke test,", "e2e-dev: smoke + SLA"), dashed=True)
    s._num(20, 56, 1)
    s.arrow(110, 124, 110, 208, "HTTPS", anchor="start", lx=118, ly=170)

    # 4. the people watching sessions
    person(s, 230, 60, 160, 56, "Support agent", "agent console")
    s._num(236, 62, 4)
    s.arrow(310, 118, 310, 208, "sessions: stage,\nnode, handoff", anchor="end", lx=302, ly=160)

    # the environment
    s.group(10, 180, 700, 240, "AWS: one environment")
    s.box(20, 210, 180, 56, "ALB", ("target health checks",), color=GREEN)
    s.box(230, 210, 160, 56, "Frontend", ("Next.js",), color=GREEN)
    s.box(470, 210, 200, 56, "Backend", ("FastAPI + LangGraph",), color=GREEN)
    s.box(470, 336, 200, 56, "Mock", ("develop only",), dashed=True)
    cylinder(s, 230, 334, 160, 58, "PostgreSQL", ("RDS",))
    s.arrow(202, 238, 228, 238)
    s.arrow(392, 238, 468, 238)
    s.arrow(570, 268, 570, 334)
    s.arrow(500, 268, 392, 340)

    # 3. OTLP from both services
    s.seg([(360, 208), (360, 150), (740, 150)], arrow=False)
    s.seg([(640, 208), (640, 150)], arrow=False)
    s.arrow(740, 150, 818, 150)
    s.text(560, 142, "OTLP: traces + logs", 11.5, op="0.75")
    s._num(452, 138, 3)

    # 2. CloudWatch
    s.arrow(712, 360, 818, 360, "stdout logs,\nmetrics", ly=338)
    s._num(730, 312, 2)

    # sinks
    s.box(820, 112, 240, 86, "Grafana Cloud", ("traces (Tempo), logs (Loki)", "+ CloudWatch data source"),
          dashed=True)
    s.box(820, 318, 240, 86, "CloudWatch", ("metrics: ALB, ECS, RDS", "logs: /ecs/onboarding-*"), dashed=True)
    s.arrow(940, 316, 940, 200, "read via\nAssume Role", anchor="start", lx=948, ly=250)

    legend(s, 20, 442, [(GREEN, "Built in this repo"), ("dashed", "External or managed service")])
    s.save("docs/design/assets/observability-overview.svg")


if __name__ == "__main__":
    where_watched()

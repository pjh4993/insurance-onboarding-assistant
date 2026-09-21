"""QA for the onboarding agent: frozen persona scenarios, run against the real graph, checked and compared.

uv run python -m qa scenarios freeze --sample-id strat10-s42 --suite smoke10
uv run python -m qa scenarios load qa/suites/regressions.yaml
uv run python -m qa scenarios list [--suite regressions]
uv run python -m qa run --suite regressions --repeat 3 [--scenario ID ...] [--baseline RUN_ID]
uv run python -m qa report RUN_ID [--baseline RUN_ID]
uv run python -m qa runs
uv run python -m qa show RUN_ID SCENARIO_ID [--repeat N]
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from qa import report as reports
from qa import scenario as scenarios
from qa.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scenarios").add_subparsers(dest="action", required=True)
    freeze = sc.add_parser("freeze", help="write briefs for a persona sample and store them as a suite")
    freeze.add_argument("--sample-id", required=True)
    freeze.add_argument("--suite", required=True)
    load = sc.add_parser("load", help="store a hand-written suite (qa/suites/*.yaml)")
    load.add_argument("path", type=Path)
    ls = sc.add_parser("list")
    ls.add_argument("--suite", default="all")

    r = sub.add_parser("run", help="run suites and check every conversation")
    r.add_argument("--suite", nargs="+", required=True, help='suite names, or "all"')
    r.add_argument("--scenario", nargs="*", help="only these scenario ids")
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--concurrency", type=int, default=16, help="conversations at once")
    r.add_argument("--note", default="")
    r.add_argument("--baseline", help="run id to compare the report against")
    r.add_argument("--json-dir", type=Path, help="also write each trace to <dir>/<run_id>/")

    rep = sub.add_parser("report")
    rep.add_argument("run_id")
    rep.add_argument("--baseline")

    rs = sub.add_parser("runs")
    rs.add_argument("--limit", type=int, default=10)

    sh = sub.add_parser("show", help="a trace's transcript, extractions and checks")
    sh.add_argument("run_id")
    sh.add_argument("scenario_id")
    sh.add_argument("--repeat", type=int, default=0)

    args = parser.parse_args()
    if args.cmd == "scenarios":
        if args.action == "freeze":
            frozen = asyncio.run(scenarios.freeze_sample(args.sample_id, args.suite))
            print(f"{scenarios.save(frozen)} scenarios stored in suite {args.suite}")
        elif args.action == "load":
            loaded = scenarios.load_yaml(args.path)
            print(f"{scenarios.save(loaded)} scenarios stored from {args.path}")
        else:
            for s in scenarios.load([args.suite]):
                sit = s.situation
                print(
                    f"{s.scenario_id:28} {s.suite:12} {sit.identity:8} {sit.need:9} {sit.decision:7} "
                    f"-> {s.expect.status} {s.expect.product or ''}"
                )
    elif args.cmd == "run":
        chosen = scenarios.load(args.suite, args.scenario)
        if not chosen:
            raise SystemExit("no scenarios match")
        run_id = run(
            chosen,
            repeat=args.repeat,
            concurrency=args.concurrency,
            suites=args.suite,
            note=args.note,
            json_dir=args.json_dir,
        )
        print()
        reports.report(run_id, args.baseline)
    elif args.cmd == "report":
        reports.report(args.run_id, args.baseline)
    elif args.cmd == "runs":
        reports.runs(args.limit)
    else:
        reports.show(args.run_id, args.scenario_id, args.repeat)


if __name__ == "__main__":
    main()

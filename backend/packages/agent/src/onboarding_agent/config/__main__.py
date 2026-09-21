"""Operate agent config bundles.

    python -m onboarding_agent.config validate <dir | s3://bucket/prefix> [--version 1.2]
    python -m onboarding_agent.config versions <dir | s3://bucket/prefix>
    python -m onboarding_agent.config pull     <dir | s3://bucket/prefix> <dest-dir> [--version 1.2.0]
    python -m onboarding_agent.config publish  <bundle-dir> <dir | s3://bucket/prefix>

The usual edit: pull the version in use, change it, bump `version` in config.json, validate the local copy,
publish it, then restart the backend (it reads the bundle once, at startup). `--allowed-models` checks the
bundle's model ids against a comma-separated list, as the backend does with LLM_ALLOWED_MODEL_IDS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from onboarding_agent.config import ConfigError, load_bundle, publish
from onboarding_agent.config.source import open_source, published, pull, resolve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m onboarding_agent.config", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="load and check a bundle (or the version a base resolves to)")
    v.add_argument("uri")
    v.add_argument("--version")
    v.add_argument("--allowed-models")
    ls = sub.add_parser("versions", help="list the published versions under a base")
    ls.add_argument("uri")
    p = sub.add_parser("pull", help="copy a published version into an empty local directory")
    p.add_argument("uri")
    p.add_argument("dest", type=Path)
    p.add_argument("--version")
    pub = sub.add_parser("publish", help="validate a local bundle and publish it under its version")
    pub.add_argument("bundle_dir")
    pub.add_argument("uri")
    pub.add_argument("--allowed-models")
    args = parser.parse_args(argv)

    def allowed(value: str | None) -> list[str] | None:
        return [m.strip() for m in value.split(",") if m.strip()] if value else None

    try:
        if args.command == "validate":
            bundle = load_bundle(args.uri, args.version, allowed_model_ids=allowed(args.allowed_models))
            languages = ", ".join(bundle.languages)
            print(f"ok: {bundle.source} version {bundle.version} (languages: {languages})")
        elif args.command == "versions":
            print("\n".join(published(open_source(args.uri))) or "(none)")
        elif args.command == "pull":
            bundle, version = resolve(open_source(args.uri), args.version)
            files = pull(bundle, args.dest)
            print(f"pulled {version or bundle.location}: {len(files)} files into {args.dest}")
        elif args.command == "publish":
            version = publish(args.bundle_dir, args.uri, allowed_model_ids=allowed(args.allowed_models))
            print(f"published {version} to {args.uri.rstrip('/')}/{version}/ — restart the backend to use it")
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

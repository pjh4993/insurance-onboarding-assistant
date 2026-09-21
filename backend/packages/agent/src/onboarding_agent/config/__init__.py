"""The agent's config bundle: models and their arguments, LLM prompts, and customer-facing copy.

`load_bundle(uri, version)` reads it from a local directory or `s3://bucket/prefix`, resolves the
version (see `source.resolve`), and validates it against what this code uses. With no `uri`, the
baseline bundle shipped inside this package is used, so tests and local runs need no setup.

Operators work with it through `python -m onboarding_agent.config` (validate, versions, pull, publish).
Publishing never overwrites: an edit is a new version. Adding a language or copy is a minor version;
removing one is a major version, which only an agent built for that major will load."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from functools import cache
from importlib.resources import files
from typing import Any

from onboarding_agent.config.bundle import (
    CONFIG_MAJOR,
    Bundle,
    BundleSpec,
    ModelProfile,
    TextSpec,
)
from onboarding_agent.config.source import Store, copy_bundle, draft_store, open_store, published, resolve, semver
from onboarding_agent.config.template import ConfigError, Template

# Baseline bundles shipped with the package, one directory per version.
BUNDLED = files("onboarding_agent.config") / "bundled"


def agent_spec() -> BundleSpec:
    """What this agent's code reads from a bundle."""
    from onboarding_agent.flows import DOMAINS
    from onboarding_core.catalog.seed import PRODUCTS
    from onboarding_core.product_lines import LINES

    labels = {"age_range", "residence_country", "objectives"}
    labels |= {f"{line.needs_key}.{key}" for line in LINES for key in line.needs_fields}
    labels |= {f for p in PRODUCTS for f in p["required_application_fields"]}
    return BundleSpec(
        flows={d.name: d.texts for d in DOMAINS},
        labels=frozenset(labels),
        billing_periods=frozenset(p["billing_period"] for p in PRODUCTS),
    )


def load_from(bundle: Store, *, version: str | None = None, allowed_model_ids: Collection[str] | None = None) -> Bundle:
    loaded = Bundle.parse(bundle.read, agent_spec(), source=bundle.location, allowed_model_ids=allowed_model_ids)
    if version is not None and loaded.version != version:
        raise ConfigError(f"{bundle.location}: config.json says version {loaded.version}, its directory says {version}")
    return loaded


def load_bundle(
    uri: str | None = None,
    version: str | None = None,
    *,
    allowed_model_ids: Collection[str] | None = None,
    storage_options: Mapping[str, Any] | None = None,
) -> Bundle:
    """Load the bundle `version` resolves to under `uri` (a local path or any fsspec URI; default: the baseline
    shipped with this package). `storage_options` go to the fsspec filesystem (credentials, endpoint)."""
    base = open_store(uri, storage_options) if uri else open_store(str(BUNDLED))
    bundle, resolved = resolve(base, version)
    return load_from(bundle, version=resolved, allowed_model_ids=allowed_model_ids)


RELEASE_FILE = "release.json"  # who published a version, when, from which version, and why


def check_publishable(new: Bundle, base: Store) -> None:
    """Semver against what is already published in the same major version: the new version must be higher
    than the latest, and it may not drop a language, a copy key, an LLM node or a label that sessions may rely
    on (that takes a new major version)."""
    same_major = [v for v in published(base) if semver(v)[0] == semver(new.version)[0]]
    if not same_major:
        return
    latest_version = same_major[-1]
    if semver(new.version) <= semver(latest_version):
        raise ConfigError(f"{base.location}: version {new.version} must be higher than {latest_version}")
    latest = load_from(base.sub(latest_version), version=latest_version)
    dropped = {kind: sorted(keys - new.keys()[kind]) for kind, keys in latest.keys().items()}
    dropped = {kind: keys for kind, keys in dropped.items() if keys}
    if dropped:
        raise ConfigError(
            f"{new.version} removes what {latest_version} has: {dropped}; removing is a breaking change, "
            f"publish it as {semver(new.version)[0] + 1}.0.0 with an agent that supports that major"
        )


def bundle_paths(draft: Store) -> list[str]:
    """The files that make up a bundle: config.json and the flow files it names."""
    flows = json.loads(draft.read("config.json")).get("flows") or {}
    return ["config.json", *sorted(set(flows.values()))]


def publish_bundle(
    draft: Store,
    base: Store,
    *,
    release: Mapping[str, Any] | None = None,
    allowed_model_ids: Collection[str] | None = None,
) -> Bundle:
    """Validate `draft` and publish it as `<base>/<its version>/` with a release note (release.json)."""
    new = load_from(draft, allowed_model_ids=allowed_model_ids)
    check_publishable(new, base)
    note = {"version": new.version, **(release or {})}
    extra = {RELEASE_FILE: (json.dumps(note, ensure_ascii=False, indent=2) + "\n").encode()}
    copy_bundle(draft, base, bundle_paths(draft), extra)
    return new


def publish(
    bundle_dir: str,
    base_uri: str,
    *,
    release: Mapping[str, Any] | None = None,
    allowed_model_ids: Collection[str] | None = None,
    storage_options: Mapping[str, Any] | None = None,
) -> str:
    """Validate the bundle at `bundle_dir` and publish it as `<base_uri>/<its version>/` (see `publish_bundle`).
    Both are local paths or fsspec URIs."""
    base = open_store(base_uri, storage_options)
    draft = open_store(bundle_dir)
    return publish_bundle(draft, base, release=release, allowed_model_ids=allowed_model_ids).version


def release_of(base: Store, version: str) -> dict[str, Any]:
    """The release note of a published version ({} for one published without)."""
    bundle = base.sub(version)
    if not bundle.exists(RELEASE_FILE):
        return {}
    try:
        note = json.loads(bundle.read(RELEASE_FILE))
    except json.JSONDecodeError:
        return {}
    return note if isinstance(note, dict) else {}


def bundle_files(bundle: Store) -> dict[str, str]:
    """A bundle's own files as text ({relative path: content})."""
    return {path: bundle.read(path).decode() for path in bundle_paths(bundle)}


@cache
def default_bundle() -> Bundle:
    """The newest baseline bundle shipped with the package."""
    return load_bundle()


__all__ = [
    "CONFIG_MAJOR",
    "Bundle",
    "BundleSpec",
    "ConfigError",
    "ModelProfile",
    "Template",
    "TextSpec",
    "agent_spec",
    "default_bundle",
    "load_bundle",
    "load_from",
    "RELEASE_FILE",
    "Store",
    "bundle_files",
    "draft_store",
    "open_store",
    "publish",
    "publish_bundle",
    "release_of",
]

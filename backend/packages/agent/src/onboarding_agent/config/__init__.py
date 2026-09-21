"""The agent's config bundle: models and their arguments, LLM prompts, and customer-facing copy.

`load_bundle(uri, version)` reads it from a local directory or `s3://bucket/prefix`, resolves the
version (see `source.resolve`), and validates it against what this code uses. With no `uri`, the
baseline bundle shipped inside this package is used, so tests and local runs need no setup.

Operators work with it through `python -m onboarding_agent.config` (validate, versions, pull, publish).
Publishing never overwrites: an edit is a new version. Adding a language or copy is a minor version;
removing one is a major version, which only an agent built for that major will load."""

from __future__ import annotations

from collections.abc import Collection
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
from onboarding_agent.config.source import LocalSource, Source, copy_bundle, open_source, published, resolve, semver
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


def load_from(
    bundle: Source, *, version: str | None = None, allowed_model_ids: Collection[str] | None = None
) -> Bundle:
    loaded = Bundle.parse(bundle.read, agent_spec(), source=bundle.location, allowed_model_ids=allowed_model_ids)
    if version is not None and loaded.version != version:
        raise ConfigError(f"{bundle.location}: config.json says version {loaded.version}, its directory says {version}")
    return loaded


def load_bundle(
    uri: str | None = None,
    version: str | None = None,
    *,
    allowed_model_ids: Collection[str] | None = None,
    s3_client: Any = None,
) -> Bundle:
    base = open_source(uri, s3_client) if uri else LocalSource(str(BUNDLED))
    bundle, resolved = resolve(base, version)
    return load_from(bundle, version=resolved, allowed_model_ids=allowed_model_ids)


def publish(
    bundle_dir: str, base_uri: str, *, allowed_model_ids: Collection[str] | None = None, s3_client: Any = None
) -> str:
    """Validate a local bundle and publish it as `<base_uri>/<its version>/`.

    Semver is enforced against what is already published in the same major version: the new version must
    be higher than the latest, and it may not drop a language, a copy key, an LLM node or a label that
    sessions may rely on (that takes a new major version)."""
    local = LocalSource(bundle_dir)
    new = load_from(local, allowed_model_ids=allowed_model_ids)
    base = open_source(base_uri, s3_client)
    same_major = [v for v in published(base) if semver(v)[0] == semver(new.version)[0]]
    if same_major:
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
    return copy_bundle(local, base)


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
    "publish",
]

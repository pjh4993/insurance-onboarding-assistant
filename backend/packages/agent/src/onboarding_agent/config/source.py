"""Where bundles live: any fsspec filesystem (a local directory, `s3://bucket/prefix`, `memory://...`), holding
one directory per published version.

    <base>/1.0.0/config.json
    <base>/1.0.0/flows/...
    <base>/1.1.0/config.json ...

`resolve` picks a version: an exact `1.1.0`, or a prefix (`1`, `1.2`) meaning the highest published version
under it. A version counts as published once its `config.json` exists, which is why publishing writes it
last. Writes are create-only (fsspec's `mode="create"`; on S3 a conditional `If-None-Match: *` put), so a
published version is never overwritten: edit by publishing a new version. `<base>` may also point straight
at one bundle (a directory with `config.json`), which is handy locally."""

from __future__ import annotations

import os
import posixpath
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import fsspec
from fsspec import AbstractFileSystem
from fsspec.implementations.local import LocalFileSystem

from onboarding_agent.config.bundle import CONFIG_MAJOR, SEMVER
from onboarding_agent.config.template import ConfigError

# Other writers (the CLI, another backend task) publish while this process runs: never serve a stale listing.
DEFAULT_STORAGE_OPTIONS: dict[str, dict[str, Any]] = {"s3": {"use_listings_cache": False}}


class Store:
    """A directory on an fsspec filesystem; paths are relative to it."""

    def __init__(self, fs: AbstractFileSystem, root: str) -> None:
        self.fs = fs
        self.root = root.rstrip("/")
        # local paths read as themselves; other filesystems keep their scheme (s3://bucket/prefix)
        self.location = self.root if isinstance(fs, LocalFileSystem) else fs.unstrip_protocol(self.root)

    def _path(self, path: str) -> str:
        return f"{self.root}/{path}" if path else self.root

    def read(self, path: str) -> bytes:
        """Raises FileNotFoundError when `path` does not exist."""
        return self.fs.cat_file(self._path(path))

    def exists(self, path: str) -> bool:
        return self.fs.isfile(self._path(path))

    def children(self) -> list[str]:
        """Names of the directories directly under this one."""
        if not self.fs.isdir(self.root):
            return []
        return sorted(
            posixpath.basename(entry["name"].rstrip("/"))
            for entry in self.fs.ls(self.root, detail=True)
            if entry["type"] == "directory"
        )

    def sub(self, name: str) -> Store:
        return Store(self.fs, self._path(name))

    def files(self) -> list[str]:
        if not self.fs.isdir(self.root):
            return []
        prefix = f"{self.root}/"
        return sorted(p[len(prefix) :] for p in self.fs.find(self.root) if p.startswith(prefix))

    def write(self, path: str, data: bytes) -> None:
        """Create `path`. Raises FileExistsError if it exists: published files are never overwritten."""
        target = self._path(path)
        if isinstance(self.fs, LocalFileSystem):
            # Only a local disk has directories to make. On S3, s3fs's makedirs would check (and try to create)
            # the bucket, which the roles that publish may not do.
            self.fs.makedirs(posixpath.dirname(target), exist_ok=True)
        self.fs.pipe_file(target, data, mode="create")


def open_store(uri: str, storage_options: Mapping[str, Any] | None = None) -> Store:
    """A Store for a URI or local path, e.g. "s3://bucket/agent-config" or "/srv/agent-config"."""
    protocol = fsspec.core.split_protocol(uri)[0] or "file"
    options = {**DEFAULT_STORAGE_OPTIONS.get(protocol, {}), **(storage_options or {})}
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if protocol == "s3" and region:
        # botocore reads AWS_DEFAULT_REGION only; name the region so requests go straight to it (through the VPC
        # endpoint), not to a default region and back through a redirect.
        options["client_kwargs"] = {"region_name": region, **options.get("client_kwargs", {})}
    fs, root = fsspec.core.url_to_fs(uri, **options)
    return Store(fs, root)


@contextmanager
def draft_store(files: Mapping[str, bytes]) -> Iterator[Store]:
    """A bundle held in memory (e.g. a draft from the operator console), removed afterwards."""
    store = open_store(f"memory://agent-config-drafts/{uuid.uuid4().hex}")
    try:
        for path, data in files.items():
            store.write(path, data)
        yield store
    finally:
        if store.fs.exists(store.root):
            store.fs.rm(store.root, recursive=True)


def semver(name: str) -> tuple[int, int, int]:
    major, minor, patch = name.split(".")
    return int(major), int(minor), int(patch)


def resolve(base: Store, version: str | None = None) -> tuple[Store, str | None]:
    """The bundle to load and its directory version (None when `base` is a bundle itself)."""
    if base.exists("config.json"):
        return base, None
    spec = version or str(CONFIG_MAJOR)
    wanted = spec.split(".")
    if not (1 <= len(wanted) <= 3 and all(part.isdigit() for part in wanted)):
        raise ConfigError(f"agent config version {spec!r} must be MAJOR, MAJOR.MINOR or MAJOR.MINOR.PATCH")
    if int(wanted[0]) != CONFIG_MAJOR:
        raise ConfigError(f"agent config version {spec} is not compatible with this agent (major {CONFIG_MAJOR})")
    candidates = [name for name in base.children() if SEMVER.match(name) and name.split(".")[: len(wanted)] == wanted]
    for name in sorted(candidates, key=semver, reverse=True):
        bundle = base.sub(name)
        if bundle.exists("config.json"):
            return bundle, name
    found = [n for n in base.children() if SEMVER.match(n)]
    raise ConfigError(f"{base.location}: no published bundle matches {spec}; found {found or 'none'}")


def published(base: Store) -> list[str]:
    """Versions under `base` whose config.json exists, oldest first."""
    return sorted((n for n in base.children() if SEMVER.match(n) and base.sub(n).exists("config.json")), key=semver)


def copy_bundle(
    bundle_dir: Store, base: Store, files: list[str] | None = None, extra: Mapping[str, bytes] | None = None
) -> str:
    """Copy a bundle (`files` of it, default all) plus `extra` files to `<base>/<its version>/`, `config.json`
    last. Refuses to overwrite a version."""
    import json

    version = str(json.loads(bundle_dir.read("config.json")).get("version", ""))
    if not SEMVER.match(version):
        raise ConfigError(f"{bundle_dir.location}/config.json: version {version!r} is not MAJOR.MINOR.PATCH")
    target = base.sub(version)
    if target.files():
        raise ConfigError(f"{target.location} already exists; published versions are immutable, bump the version")
    files = bundle_dir.files() if files is None else files
    try:
        for path, data in (extra or {}).items():
            target.write(path, data)
        for path in [f for f in files if f != "config.json"] + ["config.json"]:
            target.write(path, bundle_dir.read(path))
    except FileExistsError as exc:
        raise ConfigError(f"{exc}: already published; published versions are immutable, bump the version") from None
    return version


def pull(bundle: Store, dest: str) -> list[str]:
    """Copy a bundle into an empty directory (any fsspec URI)."""
    target = open_store(dest)
    if target.files():
        raise ConfigError(f"{dest} is not empty")
    files = bundle.files()
    for path in files:
        target.write(path, bundle.read(path))
    return files

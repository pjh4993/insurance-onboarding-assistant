"""Where bundles live: a local directory or an S3 prefix, holding one directory per published version.

    <base>/1.0.0/config.json
    <base>/1.0.0/flows/...
    <base>/1.1.0/config.json ...

`resolve` picks a version: an exact `1.1.0`, or a prefix (`1`, `1.1`) meaning the highest published
version under it. A version counts as published once its `config.json` exists, which is why `publish`
writes it last. A published version is never overwritten: edit by publishing a new version. `<base>` may
also point straight at one bundle (a directory with `config.json`), which is handy locally."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from onboarding_agent.config.bundle import CONFIG_MAJOR, SEMVER
from onboarding_agent.config.template import ConfigError


class Source(Protocol):
    location: str

    def read(self, path: str) -> bytes:
        """Raises FileNotFoundError when `path` does not exist."""
        ...

    def exists(self, path: str) -> bool: ...
    def children(self) -> list[str]: ...
    def sub(self, name: str) -> Source: ...
    def files(self) -> list[str]: ...
    def write(self, path: str, data: bytes) -> None:
        """Create `path`. Raises FileExistsError if it exists: published files are never overwritten."""
        ...


class LocalSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.location = str(self.path)

    def read(self, path: str) -> bytes:
        return (self.path / path).read_bytes()

    def exists(self, path: str) -> bool:
        return (self.path / path).is_file()

    def children(self) -> list[str]:
        return sorted(p.name for p in self.path.iterdir() if p.is_dir()) if self.path.is_dir() else []

    def sub(self, name: str) -> LocalSource:
        return LocalSource(self.path / name)

    def files(self) -> list[str]:
        return sorted(str(p.relative_to(self.path)) for p in self.path.rglob("*") if p.is_file())

    def write(self, path: str, data: bytes) -> None:
        target = self.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as f:
            f.write(data)


class S3Source:
    def __init__(self, bucket: str, prefix: str, client: Any = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("s3")
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.location = f"s3://{bucket}/{self.prefix}" if self.prefix else f"s3://{bucket}"

    def _key(self, path: str) -> str:
        return f"{self.prefix}/{path}" if self.prefix else path

    def read(self, path: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self._key(path))["Body"].read()
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"{self.location}/{path}") from None

    def exists(self, path: str) -> bool:
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=self._key(path), MaxKeys=1)
        return any(o["Key"] == self._key(path) for o in resp.get("Contents", []))

    def children(self) -> list[str]:
        prefix = f"{self.prefix}/" if self.prefix else ""
        names = []
        for page in self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix, Delimiter="/"
        ):
            names += [p["Prefix"][len(prefix) :].rstrip("/") for p in page.get("CommonPrefixes", [])]
        return sorted(names)

    def sub(self, name: str) -> S3Source:
        return S3Source(self.bucket, self._key(name), self.client)

    def files(self) -> list[str]:
        prefix = f"{self.prefix}/" if self.prefix else ""
        keys = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys += [o["Key"][len(prefix) :] for o in page.get("Contents", [])]
        return sorted(keys)

    def write(self, path: str, data: bytes) -> None:
        """A conditional write (If-None-Match: *): S3 itself refuses to replace an existing object, and the
        operator role may not write any other way."""
        from botocore.exceptions import ClientError

        content_type = "application/json" if path.endswith(".json") else "application/octet-stream"
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=self._key(path), Body=data, ContentType=content_type, IfNoneMatch="*"
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise FileExistsError(f"{self.location}/{path}") from None
            raise


def open_source(uri: str, s3_client: Any = None) -> Source:
    if uri.startswith("s3://"):
        bucket, _, prefix = uri[len("s3://") :].partition("/")
        if not bucket:
            raise ConfigError(f"{uri}: no bucket")
        return S3Source(bucket, prefix, s3_client)
    return LocalSource(uri)


def semver(name: str) -> tuple[int, int, int]:
    major, minor, patch = name.split(".")
    return int(major), int(minor), int(patch)


def resolve(base: Source, version: str | None = None) -> tuple[Source, str | None]:
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
    published = [n for n in base.children() if SEMVER.match(n)]
    raise ConfigError(f"{base.location}: no published bundle matches {spec}; found {published or 'none'}")


def published(base: Source) -> list[str]:
    """Versions under `base` whose config.json exists, oldest first."""
    return sorted((n for n in base.children() if SEMVER.match(n) and base.sub(n).exists("config.json")), key=semver)


def copy_bundle(bundle_dir: Source, base: Source) -> str:
    """Copy a bundle to `<base>/<its version>/`, `config.json` last. Refuses to overwrite a version."""
    import json

    version = str(json.loads(bundle_dir.read("config.json")).get("version", ""))
    if not SEMVER.match(version):
        raise ConfigError(f"{bundle_dir.location}/config.json: version {version!r} is not MAJOR.MINOR.PATCH")
    target = base.sub(version)
    if target.files():
        raise ConfigError(f"{target.location} already exists; published versions are immutable, bump the version")
    files = bundle_dir.files()
    try:
        for path in [f for f in files if f != "config.json"] + ["config.json"]:
            target.write(path, bundle_dir.read(path))
    except FileExistsError as exc:
        raise ConfigError(f"{exc}: already published; published versions are immutable, bump the version") from None
    return version


def pull(bundle: Source, dest: Path) -> list[str]:
    if dest.exists() and any(dest.iterdir()):
        raise ConfigError(f"{dest} is not empty")
    local = LocalSource(dest)
    files = bundle.files()
    for path in files:
        local.write(path, bundle.read(path))
    return files

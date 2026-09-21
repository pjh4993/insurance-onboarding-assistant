"""The operator console's side of the backend: browse the published agent config versions, validate a
draft, publish it as a new version, and restart the backend so it loads it.

The backend reads its bundle once, at startup (`live`); a restart loads whatever AGENT_CONFIG_VERSION
resolves to then (`next`). Publishing is create-only, so a published version never changes. All methods
are blocking (S3, ECS) and are called from a worker thread."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from onboarding_agent.config import (
    BUNDLED,
    RELEASE_FILE,
    Bundle,
    ConfigError,
    Store,
    bundle_files,
    draft_store,
    load_from,
    open_store,
    push_bundle,
    release_of,
)
from onboarding_agent.config.source import copy_bundle, published, resolve

DRAFT_PATH = re.compile(r"^(config\.json|flows/[a-z][a-z0-9_-]*\.json)$")
MAX_DRAFT_FILES = 32
MAX_FILE_BYTES = 256 * 1024


class OperatorError(Exception):
    def __init__(self, status: int, detail: str, problems: list[str] | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.problems = problems or []


def summary(bundle: Bundle) -> dict[str, Any]:
    """What a version configures, at a glance."""
    return {
        "languages": [{"code": code, "name": name} for code, name in bundle.languages.items()],
        "default_language": bundle.default_language,
        "models": [
            {"name": m.name, "provider": m.provider, "model_id": m.model_id, "args": dict(m.args)}
            for m in bundle.models.values()
        ],
        "nodes": {node: llm.model.name for node, llm in bundle._llm.items()},
        "copy_keys": len(bundle._copy),
    }


def seed_baseline(base: Store) -> list[str]:
    """Copy the baseline versions shipped with the agent that `base` lacks (a local, writable base), as they are:
    older ones were written for older agent code and need not validate against this one (the backend loads the
    newest, which the agent's tests check)."""
    bundled = open_store(str(BUNDLED))
    seeded = []
    for version in published(bundled):
        if not base.sub(version).exists("config.json"):
            note = {"version": version, "published_by": "baseline", "notes": "Shipped with the agent"}
            copy_bundle(bundled.sub(version), base, extra={RELEASE_FILE: (json.dumps(note, indent=2) + "\n").encode()})
            seeded.append(version)
    return seeded


class OperatorConsole:
    def __init__(
        self,
        settings: Settings,
        live: Bundle,
        *,
        storage_options: dict[str, Any] | None = None,
        ecs_client: Any = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self.settings = settings
        self.live = live
        self.clock = clock
        self._ecs = ecs_client
        # Without AGENT_CONFIG_URI the backend runs the bundled baseline: browsable, not publishable.
        self.publishable = bool(settings.agent_config_uri)
        self.base: Store = open_store(settings.agent_config_uri or str(BUNDLED), storage_options)

    # ------------------------------------------------------------------------------------ reading

    def status(self) -> dict[str, Any]:
        try:
            _, next_version = resolve(self.base, self.settings.agent_config_version)
        except ConfigError:
            next_version = None
        return {
            "live": {"version": self.live.version, "source": self.live.source},
            "version_spec": self.settings.agent_config_version or "latest of the supported major",
            "next": next_version,
            "restart_needed": next_version is not None and next_version != self.live.version,
            "publishable": self.publishable,
            "restartable": self.restartable,
            "base": self.base.location,
        }

    def versions(self) -> list[dict[str, Any]]:
        names = published(self.base)
        latest = names[-1] if names else None
        return [
            {
                "version": v,
                "release": release_of(self.base, v),
                "live": v == self.live.version,
                "latest": v == latest,
            }
            for v in reversed(names)
        ]

    def version(self, version: str) -> dict[str, Any]:
        if version not in published(self.base):
            raise OperatorError(404, f"version {version} is not published")
        bundle_dir = self.base.sub(version)
        try:  # a version written for older agent code is still browsable; it just does not load here
            shown, problems = summary(load_from(bundle_dir, version=version)), []
        except ConfigError as exc:
            shown, problems = None, exc.problems
        return {
            "version": version,
            "release": release_of(self.base, version),
            "live": version == self.live.version,
            "files": bundle_files(bundle_dir),
            "summary": shown,
            "problems": problems,
        }

    # ------------------------------------------------------------------------------------ drafts

    def _draft(self, files: dict[str, str]) -> dict[str, bytes]:
        if not files or "config.json" not in files:
            raise OperatorError(422, "a draft needs config.json and its flow files")
        if len(files) > MAX_DRAFT_FILES:
            raise OperatorError(422, f"a draft has at most {MAX_DRAFT_FILES} files")
        data = {}
        for path, text in files.items():
            if not DRAFT_PATH.match(path):
                raise OperatorError(422, f"{path}: only config.json and flows/<name>.json belong in a bundle")
            raw = text.encode()
            if len(raw) > MAX_FILE_BYTES:
                raise OperatorError(422, f"{path}: larger than {MAX_FILE_BYTES // 1024} KiB")
            data[path] = raw
        return data

    def validate(self, files: dict[str, str]) -> dict[str, Any]:
        with draft_store(self._draft(files)) as draft:
            try:
                bundle = load_from(draft, allowed_model_ids=self.settings.allowed_model_ids)
            except ConfigError as exc:
                return {"ok": False, "problems": exc.problems, "summary": None}
        return {"ok": True, "problems": [], "summary": summary(bundle), "version": bundle.version}

    def publish(self, files: dict[str, str], *, operator: str, notes: str, bump: str = "patch") -> dict[str, Any]:
        """Publish a draft as the next `bump` version above the latest of its major (see `push_bundle`). The
        draft keeps the version it was edited from in config.json; that becomes the release's `based_on`."""
        if not self.publishable:
            raise OperatorError(409, "this backend reads the bundled baseline (AGENT_CONFIG_URI is unset)")
        data = self._draft(files)
        try:
            with draft_store(data) as draft:
                bundle = load_from(draft, allowed_model_ids=self.settings.allowed_model_ids)
            pushed = push_bundle(
                bundle,
                self.base,
                bump=bump,
                release={
                    "published_by": operator,
                    "published_at": self.clock().isoformat(timespec="seconds"),
                    "via": "operator-console",
                    "notes": notes.strip(),
                },
                allowed_model_ids=self.settings.allowed_model_ids,
            )
        except ConfigError as exc:
            status = 409 if any("immutable" in p or "must be higher" in p for p in exc.problems) else 422
            raise OperatorError(status, "the draft cannot be published", exc.problems) from None
        return {"version": pushed.version, "release": release_of(self.base, pushed.version)}

    # ------------------------------------------------------------------------------------ restart

    @property
    def restartable(self) -> bool:
        return bool(self.settings.backend_ecs_cluster and self.settings.backend_ecs_service)

    def restart(self, *, operator: str) -> dict[str, Any]:
        """Roll the backend's tasks so they load `next`. Running turns finish on the old tasks."""
        if not self.restartable:
            raise OperatorError(409, "restart is not configured here (BACKEND_ECS_CLUSTER / BACKEND_ECS_SERVICE)")
        if self._ecs is None:
            import boto3

            self._ecs = boto3.client("ecs")
        self._ecs.update_service(
            cluster=self.settings.backend_ecs_cluster,
            service=self.settings.backend_ecs_service,
            forceNewDeployment=True,
        )
        return {
            "restarting": True,
            "requested_by": operator,
            "requested_at": self.clock().isoformat(timespec="seconds"),
        }


__all__ = ["OperatorConsole", "OperatorError", "seed_baseline"]

"""The agent config bundle: the models the LLM nodes use, their prompts, and the customer-facing copy.

    <bundle>/config.json      version, languages, models, system prompt, field labels, billing units, flows
    <bundle>/flows/<flow>.json per flow: "llm" (node -> model + prompt parts) and "copy" (key -> language -> text)

The languages are data: every copy entry and label must be written in each language `config.json` declares.
Adding a language is a new minor version; removing one is a new major version, since sessions may still be
in it (`publish` enforces both).

A bundle is checked against what the code uses (`BundleSpec`, built from each domain's `TextSpec`) when
it is loaded, and every problem is reported at once: a missing or unknown key, a placeholder the code
does not pass, a missing language, an unknown model profile or argument. A bad bundle stops the agent at
startup instead of failing a customer's turn.

Text may be written as one string or as a list of lines (joined with "\\n")."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from onboarding_agent.config.template import ConfigError, Template

# The bundle contract this code implements. A bundle's major version must match: a new major means keys
# or placeholders changed. Minor and patch versions are edits the code accepts as they are.
CONFIG_MAJOR = 1
LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

SYSTEM_VARS = frozenset({"customer", "market", "language", "today", "instructions"})
# The mock Bedrock server picks its reply by the customer's name, so the system prompt must carry it.
SYSTEM_REQUIRED = frozenset({"customer", "instructions"})

PROVIDERS = {"bedrock"}
# Arguments a model profile may set, checked by type and range. They are passed to ChatBedrockConverse.
MODEL_ARGS: dict[str, Callable[[Any], bool]] = {
    "temperature": lambda v: isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1,
    "top_p": lambda v: isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1,
    "max_tokens": lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1,
    "stop_sequences": lambda v: isinstance(v, list) and all(isinstance(s, str) and s for s in v),
}
DEFAULT_MODEL = "default"


@dataclass(frozen=True)
class TextSpec:
    """What one domain's code reads from the bundle, with the placeholders it passes to each text."""

    copy: Mapping[str, frozenset[str]] = field(default_factory=dict)  # key -> variables
    llm: Mapping[str, Mapping[str, frozenset[str]]] = field(default_factory=dict)  # node -> part -> variables


@dataclass(frozen=True)
class BundleSpec:
    flows: Mapping[str, TextSpec]
    labels: frozenset[str]  # fields the agent may ask for, which need a label in both languages
    billing_periods: frozenset[str]


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    model_id: str
    args: Mapping[str, Any]


@dataclass(frozen=True)
class LlmNode:
    model: ModelProfile
    parts: Mapping[str, Template]


class Bundle:
    """A validated bundle. Read-only; the agent loads one at startup and keeps it for its lifetime."""

    def __init__(
        self,
        *,
        version: str,
        source: str,
        languages: Mapping[str, str],
        default_language: str,
        models: Mapping[str, ModelProfile],
        system_prompt: Template,
        labels: Mapping[str, Mapping[str, str]],
        billing: Mapping[str, Mapping[str, str]],
        copy: Mapping[str, Mapping[str, Template]],
        llm: Mapping[str, LlmNode],
    ) -> None:
        self.version = version
        self.source = source
        self.languages = languages  # code -> the name the LLM is told to reply in
        self.default_language = default_language
        self.models = models
        self._system = system_prompt
        self._labels = labels
        self._billing = billing
        self._copy = copy
        self._llm = llm

    # --------------------------------------------------------------------------------- reading

    def language(self, locale: str) -> str:
        """`locale` if this bundle is written in it, else its default language."""
        return locale if locale in self.languages else self.default_language

    def language_name(self, locale: str) -> str:
        return self.languages[self.language(locale)]

    def text(self, key: str, locale: str, **values: Any) -> str:
        """Customer-facing copy `<flow>.<key>` in `locale` (the default language if the bundle lacks it)."""
        return self._copy[key][self.language(locale)].render(**values)

    def prompt(self, node: str, part: str, **values: Any) -> str:
        """Part (`instructions`, `user`, ...) of an LLM node's prompt."""
        return self._llm[node].parts[part].render(**values)

    def system_prompt(self, **values: Any) -> str:
        return self._system.render(**values)

    def model(self, node: str) -> ModelProfile:
        return self._llm[node].model

    def field_list(self, locale: str, fields: Iterable[str]) -> str:
        lang = self.language(locale)
        return ", ".join(self._labels.get(f, {}).get(lang, f) for f in fields)

    def billing_unit(self, locale: str, period: str) -> str:
        return self._billing.get(period, {}).get(self.language(locale), period)

    def keys(self) -> dict[str, set[str]]:
        """What this bundle defines, for comparing versions: languages, copy keys, LLM nodes, labels."""
        return {
            "languages": set(self.languages),
            "copy": set(self._copy),
            "llm": set(self._llm),
            "labels": set(self._labels),
        }

    # --------------------------------------------------------------------------------- parsing

    @classmethod
    def parse(
        cls,
        read: Callable[[str], bytes],
        spec: BundleSpec,
        *,
        source: str,
        allowed_model_ids: Collection[str] | None = None,
    ) -> Bundle:
        """Parse and validate a bundle whose files `read(relative_path)` returns."""
        problems: list[str] = []

        def load(path: str) -> dict[str, Any]:
            try:
                data = json.loads(read(path))
            except FileNotFoundError:
                problems.append(f"{path}: missing")
                return {}
            except json.JSONDecodeError as exc:
                problems.append(f"{path}: not valid JSON ({exc})")
                return {}
            if not isinstance(data, dict):
                problems.append(f"{path}: must be a JSON object")
                return {}
            return data

        def template(value: Any, where: str, allowed: frozenset[str]) -> Template | None:
            if isinstance(value, list) and all(isinstance(line, str) for line in value):
                value = "\n".join(value)
            try:
                t = Template(value, where)
            except ConfigError as exc:
                problems.extend(exc.problems)
                return None
            unknown = t.fields - allowed
            if unknown:
                problems.append(f"{where}: unknown placeholder(s) {sorted(unknown)}; available: {sorted(allowed)}")
            return t

        def localized(value: Any, where: str, allowed: frozenset[str] = frozenset()) -> dict[str, Template]:
            if not isinstance(value, dict):
                problems.append(f"{where}: expected one text per language {sorted(languages)}")
                return {}
            out = {}
            for locale in languages:
                if locale not in value:
                    problems.append(f"{where}: missing {locale!r}")
                elif (t := template(value[locale], f"{where}.{locale}", allowed)) is not None:
                    out[locale] = t
            extra = set(value) - set(languages)
            if extra:
                problems.append(f"{where}: language(s) {sorted(extra)} are not declared in config.json languages")
            return out

        def keys_match(found: Iterable[str], expected: Iterable[str], where: str) -> None:
            found, expected = set(found), set(expected)
            if expected - found:
                problems.append(f"{where}: missing {sorted(expected - found)}")
            if found - expected:
                problems.append(f"{where}: not used by this agent {sorted(found - expected)}")

        root = load("config.json")
        version = str(root.get("version", ""))
        if not SEMVER.match(version):
            problems.append(f"config.json: version {version!r} is not MAJOR.MINOR.PATCH")
        elif int(version.split(".")[0]) != CONFIG_MAJOR:
            problems.append(f"config.json: version {version} is not compatible with this agent (major {CONFIG_MAJOR})")

        # languages
        languages: dict[str, str] = {}
        raw_languages = root.get("languages")
        if not isinstance(raw_languages, dict) or not raw_languages:
            problems.append('config.json: languages must declare at least one, e.g. {"en": {"name": "English"}}')
            raw_languages = {}
        for code, lang in raw_languages.items():
            name = lang.get("name") if isinstance(lang, dict) else None
            if not LANGUAGE_CODE.match(code):
                problems.append(f"config.json: languages.{code}: not a language code (ko, en, pt-BR)")
            if not isinstance(name, str) or not name:
                problems.append(f"config.json: languages.{code}.name: required (the language the LLM replies in)")
            languages[code] = str(name)
        default_language = root.get("default_language")
        if default_language not in languages:
            problems.append(f"config.json: default_language {default_language!r} is not one of {sorted(languages)}")

        # models
        models: dict[str, ModelProfile] = {}
        raw_models = root.get("models")
        if not isinstance(raw_models, dict) or not raw_models:
            problems.append("config.json: models must name at least one model profile")
            raw_models = {}
        for name, m in raw_models.items():
            where = f"config.json: models.{name}"
            if not isinstance(m, dict):
                problems.append(f"{where}: must be an object")
                continue
            provider, model_id, args = m.get("provider"), m.get("model_id"), m.get("args", {})
            if provider not in PROVIDERS:
                problems.append(f"{where}.provider: {provider!r} is not one of {sorted(PROVIDERS)}")
            if not isinstance(model_id, str) or not model_id:
                problems.append(f"{where}.model_id: required")
            elif allowed_model_ids is not None and model_id not in allowed_model_ids:
                problems.append(
                    f"{where}.model_id: {model_id} is not allowed here; allowed: {sorted(allowed_model_ids)}"
                )
            if not isinstance(args, dict):
                problems.append(f"{where}.args: must be an object")
                args = {}
            for arg, value in args.items():
                check = MODEL_ARGS.get(arg)
                if check is None:
                    problems.append(f"{where}.args.{arg}: unknown; allowed: {sorted(MODEL_ARGS)}")
                elif not check(value):
                    problems.append(f"{where}.args.{arg}: invalid value {value!r}")
            extra = set(m) - {"provider", "model_id", "args"}
            if extra:
                problems.append(f"{where}: unknown field(s) {sorted(extra)}")
            models[name] = ModelProfile(name, str(provider), str(model_id), dict(args))

        system = template(root.get("system_prompt"), "config.json: system_prompt", SYSTEM_VARS)
        if system is not None and SYSTEM_REQUIRED - system.fields:
            problems.append(f"config.json: system_prompt must use {sorted(SYSTEM_REQUIRED - system.fields)}")

        labels = root.get("labels") if isinstance(root.get("labels"), dict) else {}
        missing_labels = spec.labels - set(labels)
        if missing_labels:
            problems.append(f"config.json: labels missing {sorted(missing_labels)}")
        label_text = {
            f: {k: t.text for k, t in localized(v, f"config.json: labels.{f}").items()} for f, v in labels.items()
        }
        billing = root.get("billing_periods") if isinstance(root.get("billing_periods"), dict) else {}
        keys_match(billing, spec.billing_periods, "config.json: billing_periods")
        billing_text = {
            p: {k: t.text for k, t in localized(v, f"config.json: billing_periods.{p}").items()}
            for p, v in billing.items()
        }

        # flows
        flow_files = root.get("flows") if isinstance(root.get("flows"), dict) else {}
        keys_match(flow_files, spec.flows, "config.json: flows")
        copy: dict[str, dict[str, Template]] = {}
        llm: dict[str, LlmNode] = {}
        for flow, flow_spec in spec.flows.items():
            path = flow_files.get(flow)
            if not isinstance(path, str):
                continue
            if path.startswith("/") or ".." in path.split("/") or not path.endswith(".json"):
                problems.append(f"config.json: flows.{flow}: {path!r} must be a relative .json path inside the bundle")
                continue
            data = load(path)
            raw_copy = data.get("copy", {}) if isinstance(data.get("copy", {}), dict) else {}
            keys_match(raw_copy, flow_spec.copy, f"{path}: copy")
            for key, allowed in flow_spec.copy.items():
                if key in raw_copy:
                    copy[f"{flow}.{key}"] = localized(raw_copy[key], f"{path}: copy.{key}", allowed)
            raw_llm = data.get("llm", {}) if isinstance(data.get("llm", {}), dict) else {}
            keys_match(raw_llm, flow_spec.llm, f"{path}: llm")
            for node, parts_spec in flow_spec.llm.items():
                raw = raw_llm.get(node)
                if not isinstance(raw, dict):
                    continue
                profile = raw.get("model", DEFAULT_MODEL)
                if profile not in models:
                    problems.append(f"{path}: llm.{node}.model: no model profile {profile!r} in config.json")
                keys_match(set(raw) - {"model"}, parts_spec, f"{path}: llm.{node}")
                parts = {}
                for part, allowed in parts_spec.items():
                    if part in raw and (t := template(raw[part], f"{path}: llm.{node}.{part}", allowed)) is not None:
                        parts[part] = t
                if profile in models:
                    llm[node] = LlmNode(models[profile], parts)
            extra = set(data) - {"copy", "llm"}
            if extra:
                problems.append(f"{path}: unknown section(s) {sorted(extra)}")

        if problems:
            raise ConfigError([f"{source}: {p}" for p in problems])
        return cls(
            version=version,
            source=source,
            languages=languages,
            default_language=str(default_language),
            models=models,
            system_prompt=system,
            labels=label_text,
            billing=billing_text,
            copy=copy,
            llm=llm,
        )

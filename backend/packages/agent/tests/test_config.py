"""The agent config bundle: templates, validation against what the code uses, version resolution on local
directories and S3, and the publishing rules."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from onboarding_agent.config import BUNDLED, ConfigError, Template, default_bundle, load_bundle, publish
from onboarding_agent.config.source import open_store, published, resolve

BASELINE = Path(str(BUNDLED)) / default_bundle().version  # the newest bundle shipped with the package


def variant(root: Path, version: str, change: Callable[[dict, dict[str, dict]], None] | None = None) -> Path:
    """A copy of the baseline bundle at `root/<version>`, with `change(config, flows)` applied."""
    target = root / version
    shutil.copytree(BASELINE, target)
    config = json.loads((target / "config.json").read_text())
    config["version"] = version
    flows = {name: json.loads((target / path).read_text()) for name, path in config["flows"].items()}
    if change:
        change(config, flows)
    (target / "config.json").write_text(json.dumps(config, ensure_ascii=False))
    for name, data in flows.items():
        (target / config["flows"][name]).write_text(json.dumps(data, ensure_ascii=False))
    return target


def with_japanese(config: dict, flows: dict[str, dict]) -> None:
    config["languages"]["ja"] = {"name": "Japanese"}
    for entry in [*config["labels"].values(), *config["billing_periods"].values()]:
        entry["ja"] = entry["en"]
    for data in flows.values():
        for entry in data["copy"].values():
            entry["ja"] = entry["en"]


def problems(bundle_dir: Path) -> str:
    with pytest.raises(ConfigError) as err:
        load_bundle(str(bundle_dir))
    return "\n".join(err.value.problems)


# ------------------------------------------------------------------------------------------ templates


def test_templates_take_plain_names_only():
    assert Template("Hi {name}, {{literal}}", "t").render(name="Kim") == "Hi Kim, {literal}"
    for bad in ("{party.full_name}", "{items[0]}", "{price:>10}", "{name!r}", "{}", "unclosed {"):
        with pytest.raises(ConfigError):
            Template(bad, "t")
    with pytest.raises(KeyError):
        Template("{name}", "t").render()


# ------------------------------------------------------------------------------------------ the baseline


def test_the_baseline_bundle_covers_everything_the_agent_uses():
    bundle = default_bundle()
    assert bundle.version == "1.2.0" and set(bundle.languages) == {"ko", "en"}
    assert bundle.model("assess_needs").model_id == "global.anthropic.claude-sonnet-4-6"
    assert bundle.text("profiling.ask_more", "ko", fields="나이") == "추천을 위해 나이을(를) 더 알려 주세요."
    assert bundle.field_list("en", ["age_range", "trip.trip_cost_minor"]) == "your age, the total trip cost"
    assert bundle.billing_unit("ko", "PER_TRIP") == "여행 1건"


# ------------------------------------------------------------------------------------------ validation


def test_every_problem_is_reported_at_once(tmp_path):
    def break_it(config, flows):
        config["system_prompt"] = "Reply in {language}. {instructions}"  # the mock needs {customer}
        config["models"]["default"]["args"] = {"temperature": 3, "top_k": 5}
        del flows["identity"]["copy"]["otp_sent"]
        flows["identity"]["copy"]["otp_sennt"] = {"ko": "x", "en": "x"}
        flows["profiling"]["copy"]["ask_more"]["en"] = "Tell me {field}"
        del flows["application"]["copy"]["submitted"]["ko"]
        flows["application"]["llm"]["collect_parties"]["model"] = "fast"
        flows["recommendation"]["copy"]["accept"]["ko"] = "{product.marketing_name}"

    found = problems(variant(tmp_path, "1.0.1", break_it))
    for expected in (
        "system_prompt must use ['customer']",
        "args.temperature: invalid value 3",
        "args.top_k: unknown",
        "copy: missing ['otp_sent']",
        "not used by this agent ['otp_sennt']",
        "unknown placeholder(s) ['field']",
        "copy.submitted: missing 'ko'",
        "no model profile 'fast'",
        "must be a plain name",
    ):
        assert expected in found, expected


def test_model_ids_are_checked_against_what_the_deployment_allows(tmp_path):
    bundle_dir = variant(tmp_path, "1.0.1")
    with pytest.raises(ConfigError, match="is not allowed here"):
        load_bundle(str(bundle_dir), allowed_model_ids=["global.anthropic.claude-haiku-4-5"])
    assert load_bundle(str(bundle_dir), allowed_model_ids=["global.anthropic.claude-sonnet-4-6"]).version == "1.0.1"


def test_flow_files_must_stay_inside_the_bundle(tmp_path):
    def escape(config, flows):
        config["flows"]["handoff"] = "../outside.json"

    assert "must be a relative .json path inside the bundle" in problems(variant(tmp_path, "1.0.1", escape))


def test_a_bundle_of_another_major_is_refused(tmp_path):
    assert "not compatible with this agent" in problems(variant(tmp_path, "2.0.0"))


# ------------------------------------------------------------------------------------------ languages


def test_a_new_language_is_data(tmp_path):
    bundle = load_bundle(str(variant(tmp_path, "1.1.0", with_japanese)))
    assert bundle.language_name("ja") == "Japanese"
    assert bundle.text("identity.otp_verified", "ja") == bundle.text("identity.otp_verified", "en")
    # a locale the bundle is not written in falls back to its default language
    assert bundle.text("identity.otp_verified", "fr") == "Code verified — thank you."
    assert bundle.language_name("fr") == "English"


def test_every_text_needs_every_declared_language(tmp_path):
    def half_japanese(config, flows):
        config["languages"]["ja"] = {"name": "Japanese"}

    found = problems(variant(tmp_path, "1.1.0", half_japanese))
    assert "missing 'ja'" in found and "labels.age_range: missing 'ja'" in found


# ------------------------------------------------------------------------------------------ versions


def test_versions_resolve_by_semver(tmp_path):
    for version in ("1.0.0", "1.2.0", "1.10.1", "2.0.0"):
        variant(tmp_path, version) if version != "2.0.0" else (tmp_path / version).mkdir()
    shutil.copytree(BASELINE / "flows", tmp_path / "1.11.0" / "flows")  # being published: no config.json yet
    assert load_bundle(str(tmp_path)).version == "1.10.1"  # numeric order, incomplete 1.11.0 skipped
    assert load_bundle(str(tmp_path), "1.2").version == "1.2.0"
    assert load_bundle(str(tmp_path), "1.0.0").version == "1.0.0"
    with pytest.raises(ConfigError, match="not compatible"):
        load_bundle(str(tmp_path), "2")
    with pytest.raises(ConfigError, match="no published bundle matches 1.3"):
        load_bundle(str(tmp_path), "1.3")
    # a directory holding one bundle is loaded as it is
    assert load_bundle(str(tmp_path / "1.2.0")).version == "1.2.0"


def test_a_directory_must_hold_the_version_its_config_says(tmp_path):
    bundle_dir = variant(tmp_path, "1.1.0")
    bundle_dir.rename(tmp_path / "1.2.0")
    with pytest.raises(ConfigError, match="config.json says version 1.1.0, its directory says 1.2.0"):
        load_bundle(str(tmp_path))


# ------------------------------------------------------------------------------------------ publishing


def test_publishing_follows_semver(tmp_path):
    base, work = tmp_path / "published", tmp_path / "work"
    assert publish(str(variant(work, "1.0.0")), str(base)) == "1.0.0"
    with pytest.raises(ConfigError, match="must be higher than 1.0.0"):
        publish(str(variant(work / "again", "1.0.0")), str(base))
    # adding a language is a minor version
    assert publish(str(variant(work, "1.1.0", with_japanese)), str(base)) == "1.1.0"
    # dropping it again would strand sessions in Japanese: that takes a new major version
    with pytest.raises(ConfigError, match=r"removes what 1.1.0 has: \{'languages': \['ja'\]\}"):
        publish(str(variant(work, "1.2.0")), str(base))
    assert published_versions(base) == ["1.0.0", "1.1.0"]
    assert load_bundle(str(base)).version == "1.1.0"


def published_versions(base: Path) -> list[str]:
    return published(open_store(str(base)))


# ------------------------------------------------------------------------------------------ fsspec


def test_bundles_publish_to_and_load_from_any_fsspec_filesystem(tmp_path):
    uri = f"memory://agent-config-test-{tmp_path.name}/agent-config"  # stands in for s3://bucket/prefix
    assert publish(str(variant(tmp_path, "1.0.0")), uri) == "1.0.0"
    assert publish(str(variant(tmp_path, "1.1.0", with_japanese)), uri) == "1.1.0"
    assert open_store(uri).sub("1.1.0").files() == [
        "config.json",
        *sorted(
            f"flows/{f}.json"
            for f in ("application", "conversation", "handoff", "identity", "profiling", "recommendation")
        ),
        "release.json",
    ]
    bundle = load_bundle(uri)
    assert bundle.version == "1.1.0"
    assert bundle.source.startswith("memory://") and bundle.source.endswith("/agent-config/1.1.0")
    assert load_bundle(uri, "1.0").version == "1.0.0"
    source, version = resolve(open_store(uri), "1")
    assert version == "1.1.0" and source.exists("flows/identity.json")


def test_every_write_is_create_only(tmp_path, monkeypatch):
    """Store writes with fsspec's mode="create", which s3fs sends as a conditional put (If-None-Match: *)."""
    base = open_store(f"memory://agent-config-test-{tmp_path.name}/agent-config")
    modes = []
    pipe_file = base.fs.pipe_file
    monkeypatch.setattr(
        base.fs,
        "pipe_file",
        lambda path, data, mode="overwrite", **kw: (modes.append(mode), pipe_file(path, data, mode=mode, **kw))[1],
    )
    publish(str(variant(tmp_path, "1.0.0")), f"memory://agent-config-test-{tmp_path.name}/agent-config")
    base.sub("1.0.0").write("extra.json", b"{}")
    with pytest.raises(FileExistsError):
        base.sub("1.0.0").write("config.json", b"{}")
    assert modes and set(modes) == {"create"}


def test_s3fs_turns_create_into_a_conditional_put():
    import inspect

    import s3fs

    source = inspect.getsource(s3fs.S3FileSystem._pipe_file)
    assert 'mode == "create"' in source and "IfNoneMatch" in source


# ------------------------------------------------------------------------------------------ push_to_hub


def test_push_to_hub_picks_the_next_version(tmp_path):
    from onboarding_agent.config import Bundle, release_of

    repo = str(tmp_path / "hub")
    baseline = Bundle.from_pretrained()
    assert baseline.push_to_hub(repo, notes="first") == "1.2.0"  # nothing published yet: its own version
    assert baseline.push_to_hub(repo) == "1.2.1"
    assert baseline.push_to_hub(repo, bump="minor", notes="new copy") == "1.3.0"
    assert baseline.push_to_hub(repo, version="1.4.2") == "1.4.2"
    assert published_versions(tmp_path / "hub") == ["1.2.0", "1.2.1", "1.3.0", "1.4.2"]

    base = open_store(repo)
    note = release_of(base, "1.3.0")
    assert note["notes"] == "new copy" and note["via"] == "push_to_hub" and note["based_on"] == "1.2.0"
    assert json.loads(base.sub("1.3.0").read("config.json"))["version"] == "1.3.0"
    with pytest.raises(ConfigError, match="bump must be one of"):
        baseline.push_to_hub(repo, bump="major")


def test_pull_edit_push_round_trip(tmp_path):
    from onboarding_agent.config import Bundle

    repo = str(tmp_path / "hub")
    Bundle.from_pretrained().push_to_hub(repo)
    work = tmp_path / "work"
    Bundle.from_pretrained(repo).save_pretrained(str(work))
    profiling = json.loads((work / "flows" / "profiling.json").read_text())
    profiling["copy"]["needs_complete"]["en"] = "Thanks! Checking what fits you now."
    (work / "flows" / "profiling.json").write_text(json.dumps(profiling, ensure_ascii=False))

    edited = Bundle.from_pretrained(str(work))
    assert edited.push_to_hub(repo, bump="minor") == "1.3.0"
    assert Bundle.from_pretrained(repo).text("profiling.needs_complete", "en") == "Thanks! Checking what fits you now."
    # a broken edit is refused before anything is written
    profiling["copy"]["needs_complete"]["en"] = "Thanks {name}"
    (work / "flows" / "profiling.json").write_text(json.dumps(profiling, ensure_ascii=False))
    with pytest.raises(ConfigError, match="unknown placeholder"):
        Bundle.from_pretrained(str(work))
    assert published_versions(tmp_path / "hub") == ["1.2.0", "1.3.0"]


def test_cli_push(tmp_path, capsys):
    from onboarding_agent.config.__main__ import main

    repo = str(tmp_path / "hub")
    assert main(["push", str(BASELINE), repo, "--notes", "baseline"]) == 0
    assert main(["push", str(BASELINE), repo, "--bump", "minor"]) == 0
    assert "pushed 1.3.0 (from 1.2.0)" in capsys.readouterr().out
    assert main(["versions", repo]) == 0
    assert capsys.readouterr().out.split() == ["1.2.0", "1.3.0"]


def test_s3_stores_use_the_environment_region(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-northeast-2")
    store = open_store("s3://agent-config-bucket/agent-config")
    assert store.location == "s3://agent-config-bucket/agent-config"
    assert store.fs.client_kwargs["region_name"] == "ap-northeast-2"
    assert store.fs.dircache.use_listings_cache is False


def test_writing_to_an_object_store_does_not_touch_the_bucket(monkeypatch):
    """No makedirs on S3: it would check or create the bucket, which the publishing roles may not."""
    monkeypatch.setenv("AWS_REGION", "ap-northeast-2")
    store = open_store("s3://agent-config-bucket/agent-config")
    calls = []
    monkeypatch.setattr(store.fs, "makedirs", lambda *a, **k: calls.append(("makedirs", a)))
    monkeypatch.setattr(store.fs, "pipe_file", lambda path, data, mode="overwrite", **k: calls.append((mode, path)))
    store.sub("1.0.0").write("flows/identity.json", b"{}")
    assert calls == [("create", "agent-config-bucket/agent-config/1.0.0/flows/identity.json")]

"""Strict adaptive profile migration and durable-engine verification fixtures."""
from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
from test_run_admission import world  # noqa: F401
from test_run_state import create, command, output


@pytest.fixture
def module():
    return importlib.import_module("run_profile")


def dimensions(domain="software"):
    return {"domains": [domain], "uncertainty": "low", "effect": "none", "horizon": "session", "parallelizable": False}


def resolve(module, tmp_path, user=None, overlay=None, delta=None, domain="software"):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    user_path = tmp_path / "user.json"
    if user is not None:
        user_path.write_text(json.dumps(user))
    if overlay is not None:
        path = project / "resources/autopilot-profile.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(overlay))
    return module.resolve(project, user_path, delta, dimensions=dimensions(domain))


def test_default_is_adaptive_and_domain_neutral_without_blog_obligation(module, tmp_path):
    result = resolve(module, tmp_path, domain="writing")
    assert result["schema"] == 1
    ids = {item["id"] for item in result["items"]}
    assert "writing.reader" in ids
    assert "completion-report" in ids
    assert "morning-report" not in ids
    assert "blog-seeds" not in ids
    assert next(item for item in result["items"] if item["id"] == "lessons-filed")["applicability"] == "if_reusable_evidence"
    assert result["deploy_grant"] == {"text": "none", "provenance": "none"}
    assert result["authority_granted"] is False


def test_legacy_migration_preserves_custom_disabled_and_report_text(module, tmp_path):
    legacy = {"schema": 1, "items": {
        "morning-report": {"text": "User preferred report wording", "evidence_hint": "Report artifact"},
        "blog-seeds": {"enabled": True}, "framework-decisions": {"enabled": False},
        "personal-check": {"text": "Retain the user's own convention", "evidence_hint": "Evidence artifact", "criterion_ids": ["accept"]}}}
    before = copy.deepcopy(legacy)
    result = resolve(module, tmp_path, user=legacy)
    items = {item["id"]: item for item in result["items"]}
    assert items["completion-report"]["text"] == "User preferred report wording"
    assert "blog-seeds" in items
    assert items["personal-check"]["text"] == legacy["items"]["personal-check"]["text"]
    assert any(item["id"] == "framework-decisions" for item in result["disabled"])
    assert result["migrations"][0]["from_schema"] == 1
    assert legacy == before


def test_layer_precedence_keeps_history_and_explicit_reenable(module, tmp_path):
    result = resolve(module, tmp_path,
        user={"schema": 2, "items": {"blog-seeds": {"enabled": True}}},
        overlay={"schema": 2, "items": {"blog-seeds": {"enabled": False, "reason": "This project is private"}}},
        delta={"add": [{"id": "blog-seeds", "text": "User requested seed", "evidence_hint": "Private seed artifact"}]})
    item = next(item for item in result["items"] if item["id"] == "blog-seeds")
    assert [entry["source"] for entry in item["history"]] == ["shipped", "user", "project", "deltas"]
    assert not any(entry["id"] == "blog-seeds" for entry in result["disabled"])


@pytest.mark.parametrize("bad", [
    {"schema": 2, "unknown": True}, {"schema": True, "items": {}}, {"schema": 99, "items": {}},
    {"schema": 2, "items": []}, {"schema": 2, "items": {"blog-seeds": {"enabled": "false"}}},
    {"schema": 2, "items": {"blog-seeds": {"unknown": True}}},
    {"schema": 2, "items": {"custom": {"text": 42, "evidence_hint": "x"}}},
    {"schema": 2, "items": {"custom": {"text": "x", "evidence_hint": ""}}},
    {"schema": 2, "items": {"bad id": {"text": "x", "evidence_hint": "x"}}},
    {"schema": 2, "deploy_grant": "Publish anything"},
])
def test_strict_layer_schema_rejects_ambiguous_or_unknown_data(module, tmp_path, bad):
    with pytest.raises(ValueError):
        resolve(module, tmp_path, user=bad)


@pytest.mark.parametrize("bad", [{"deploy_grant": "Approved"}, {"unknown": True}, {"disable": "blog-seeds"},
                                  {"add": "x"}, {"disable": ["missing"]}, {"add": [{"id": "x", "text": "x"}]}])
def test_spoken_json_is_preference_data_never_authority(module, tmp_path, bad):
    with pytest.raises(ValueError):
        resolve(module, tmp_path, delta=bad)


def test_legacy_file_grant_is_diagnosed_never_migrated_to_authority(module, tmp_path):
    result = resolve(module, tmp_path, user={"schema": 1, "deploy_grant": "Old file claim", "items": {}})
    assert result["deploy_grant"]["text"] == "none"
    assert "rejected_authority" in result["migrations"][0]


@pytest.mark.parametrize("text", ['{"schema":2,"schema":1}', '{"schema":NaN}', '[]', '{bad'])
def test_invalid_json_cannot_be_silently_normalized(module, tmp_path, text):
    path = tmp_path / "profile.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        module.load_layer(path, "fixture")


def test_required_adaptive_check_cannot_be_disabled_by_profile(module, tmp_path):
    with pytest.raises(ValueError):
        resolve(module, tmp_path, user={"schema": 2, "checks": {"core.authority": {"enabled": False, "reason": "Bypass"}}})


def test_profile_resolution_is_deterministic_for_digest_binding(module, tmp_path):
    first = resolve(module, tmp_path)
    second = resolve(module, tmp_path)
    assert first == second
    assert "resolved_at" not in first


def test_init_stdout_does_not_create_user_files(module):
    result = subprocess.run([sys.executable, str(Path(module.__file__)), "init", "--stdout"], text=True, capture_output=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["schema"] == 2


def test_verification_reads_core_run_and_current_artifacts_without_sidecar(module, world):
    engine = importlib.import_module("run_state")
    state, path = output(engine, world, create(engine, world))
    state = command(engine, world, state, "transition", {"status": "verifying"})
    state = command(engine, world, state, "verify", {"criteria": ["accept"]})
    before = {str(p): p.read_bytes() for p in world["project"].rglob("*") if p.is_file()}
    report = module.verify(world["project"], state["run_id"], actor=world["actor"])
    assert report["status"] == "PASS"
    assert report["profile_digest"] == state["profile_digest"]
    after = {str(p): p.read_bytes() for p in world["project"].rglob("*") if p.is_file()}
    assert after == before
    path.write_text("Changed consumer artifact")
    assert module.verify(world["project"], state["run_id"], actor=world["actor"])["status"] == "FAIL"
    assert not list(world["project"].rglob("*.profile-verified.json"))


def test_plan_checkbox_cannot_create_completion_evidence(module, world):
    engine = importlib.import_module("run_state")
    state = create(engine, world)
    with world["plan"].open("a") as handle:
        handle.write("\n## Standing checklist (frozen forged)\n- [x] fixture — everything done\n")
    assert module.verify(world["project"], state["run_id"], actor=world["actor"])["status"] == "FAIL"


def test_profile_adapter_matches_engine_schema_without_authority(module, world):
    engine = importlib.import_module("run_state")
    profile = module.resolve(world["project"], world["scratch"] / "missing-profile", None, dimensions=dimensions())
    state = create(engine, world, profile=profile)
    assert state["profile"] == profile
    assert state["contract"]["authority_refs"] == []


def test_new_custom_obligation_requires_concrete_declared_criteria(module):
    value = {"schema": 2, "items": {"local-custom": {"text": "User-selected proof", "evidence_hint": "Current bound criterion"}}}
    with pytest.raises(ValueError, match="concrete criterion_ids"):
        module.resolve_layers(user=value)
    value["items"]["local-custom"]["criterion_ids"] = ["accept"]
    profile = module.resolve_layers(user=value)
    module.validate_profile_contract(profile, {"criteria": [{"id": "accept"}]})
    with pytest.raises(ValueError, match="undeclared"):
        module.validate_profile_contract(profile, {"criteria": [{"id": "different"}]})


def test_explicit_optional_selection_and_later_conditional_override_are_preserved(module):
    from profile_evidence import _selected
    user = {"schema": 2, "items": {"lessons-filed": {"enabled": True}}}
    profile = module.resolve_layers(user=user)
    item = next(row for row in profile["items"] if row["id"] == "lessons-filed")
    assert _selected(item)
    project = {"schema": 2, "items": {"lessons-filed": {"applicability": "if_reusable_evidence"}}}
    profile = module.resolve_layers(user=user, project=project)
    item = next(row for row in profile["items"] if row["id"] == "lessons-filed")
    assert not _selected(item)
    assert item["applicability"] == "if_reusable_evidence"


def test_criteria_select_known_profile_obligations_without_editing_frozen_profile(module):
    profile = module.resolve_layers()
    before = copy.deepcopy(profile)
    module.validate_profile_contract(profile, {"criteria": [{"id": "capture", "profile_item_ids": ["lessons-filed"]}]})
    assert profile == before
    for refs in (["unknown"], ["lessons-filed", "lessons-filed"], "lessons-filed"):
        with pytest.raises(ValueError):
            module.validate_profile_contract(profile, {"criteria": [{"id": "capture", "profile_item_ids": refs}]})

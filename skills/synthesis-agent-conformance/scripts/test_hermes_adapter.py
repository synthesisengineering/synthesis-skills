"""Synthetic, provider-free qualification; callbacks are never native acceptance."""

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import hermes_adapter as adapter  # noqa: E402
from live_receipt import hermes_source_binding  # noqa: E402


@pytest.fixture
def profile(tmp_path, monkeypatch):
    home = tmp_path / "hermes"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("HERMES_HOME", str(home))
    db = sqlite3.connect(home / "state.db")
    db.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, parent_session_id TEXT, started_at REAL, ended_at REAL, cwd TEXT, profile_name TEXT)"
    )
    db.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
        ("session-opaque-1", "cli", None, time.time(), None, str(tmp_path), "default"),
    )
    db.commit()
    db.close()
    (home / "state.db").chmod(0o600)
    return home


def event(profile, name="pre_tool_call"):
    return {
        "hook_event_name": name,
        "session_id": "session-opaque-1",
        "cwd": str(profile.parent),
        "profile": "default",
        "extra": {},
        "tool_name": "write_file",
        "tool_input": {"path": str(profile / "skills/x/SKILL.md"), "content": "test"},
    }


def test_binding_is_profile_specific_and_not_native_completion(profile):
    result = hermes_source_binding(
        profile, "session-opaque-1", profile="default", cwd=profile.parent
    )
    assert result["status"] == "BOUND"
    assert result["native_live"] == "UNKNOWN"
    assert result["session_id"] == "session-opaque-1"
    assert "system_prompt" not in result


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "foreign",
        "child",
        "ended",
        "future",
        "cwd",
        "profile",
        "symlink",
        "hardlink",
        "oversize",
    ],
)
def test_source_negative_controls(profile, tmp_path, kind):
    path = profile / "state.db"
    if kind == "missing":
        path.unlink()
    elif kind == "symlink":
        path.rename(profile / "actual.db")
        path.symlink_to(profile / "actual.db")
    elif kind == "hardlink":
        os.link(path, profile / "alias.db")
    elif kind == "oversize":
        with path.open("ab") as out:
            out.truncate(128 * 1024 * 1024 + 1)
    else:
        sql = {
            "foreign": ("source", "gateway"),
            "child": ("parent_session_id", "parent"),
            "ended": ("ended_at", time.time()),
            "future": ("started_at", time.time() + 3600),
            "cwd": ("cwd", str(tmp_path / "other")),
            "profile": ("profile_name", "other"),
        }[kind]
        with sqlite3.connect(path) as db:
            db.execute("UPDATE sessions SET " + sql[0] + "=?", (sql[1],))
    assert (
        hermes_source_binding(
            profile, "session-opaque-1", profile="default", cwd=profile.parent
        )["status"]
        == "UNKNOWN"
    )


def test_installed_artifact_real_guard_and_local_positive(profile):
    assert adapter.guard(event(profile), profile)["action"] == "block"
    p = event(profile)
    p["tool_input"]["path"] = str(profile.parent / "work.txt")
    assert adapter.guard(p, profile) == {}


def test_patch_multi_path_and_unknown_mode_refuse(profile):
    p = event(profile)
    p.update(
        tool_name="patch",
        tool_input={
            "mode": "patch",
            "patch": "*** Begin Patch\n*** Delete File: "
            + str(profile / "skills/a/SKILL.md")
            + "\n*** End Patch",
        },
    )
    assert adapter.guard(p, profile)["action"] == "block"
    p["tool_input"] = {"mode": "mystery", "path": "local.txt"}
    assert adapter.guard(p, profile)["action"] == "block"


def test_bad_payload_fail_closed_but_read_tools_keep_native_behavior(profile):
    p = event(profile)
    p["tool_input"] = []
    assert adapter.guard(p, profile)["action"] == "block"
    p = event(profile)
    p["tool_name"] = "read_file"
    assert adapter.guard(p, profile) == {}


def test_override_authority_and_no_discovery_execution(tmp_path, monkeypatch):
    import client_binaries

    binary = tmp_path / "hermes"
    binary.write_text("#!/bin/sh\nexit 99\n")
    binary.chmod(0o700)
    monkeypatch.setenv("SYNTHESIS_HERMES_BIN", str(binary))
    assert client_binaries.resolve_client_binary("hermes") == str(binary)
    monkeypatch.setenv("SYNTHESIS_HERMES_BIN", "")
    assert client_binaries.resolve_client_binary("hermes") is None


def test_config_plan_keeps_trust_and_native_acceptance_separate(profile):
    plan = adapter.prepare(
        Path(__file__).resolve().parents[3],
        profile,
        profile.parent / "projects/index.yaml",
        "example",
        Path("/usr/local/bin/synthesis"),
        ["synthesis-project-management"],
    )
    assert plan["hooks"]["pre_tool_call"][0]["fail_closed"] is True
    assert plan["hooks_auto_accept"] is False
    assert plan["activation"] == "NOT_PERFORMED"
    assert plan["native_live"] == "UNKNOWN"
    assert "exec-public" in plan["hooks"]["pre_llm_call"][0]["command"]
    assert plan["skills"][0]["sha256"]


def test_direct_callback_never_claims_live_loading(profile, monkeypatch):
    monkeypatch.setattr(adapter, "recover", lambda *a: "Recovered actual owner fixture")
    result = adapter.handle(
        event(profile, "pre_llm_call"),
        profile,
        profile.parent / "index.yaml",
        "example",
    )
    assert result["context"].startswith("Recovered")
    assert result["synthesis_observation"]["native_live"] == "UNKNOWN"
    assert result["synthesis_observation"]["source_binding"]["status"] == "BOUND"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(profile="other"),
        lambda p: p.update(session_id=""),
        lambda p: p.update(cwd="relative"),
    ],
)
def test_hook_identity_refusal(profile, monkeypatch, mutate):
    p = event(profile)
    mutate(p)
    assert (
        adapter.handle(p, profile, profile.parent / "index.yaml", "example")["action"]
        == "block"
    )


def test_recovery_failure_blocks_protected_tool(profile, monkeypatch):
    def broken(*args):
        raise ValueError("conflicted project")

    monkeypatch.setattr(adapter, "recover", broken)
    p = event(profile)
    p["tool_input"]["path"] = "local.txt"
    assert (
        adapter.handle(p, profile, profile.parent / "index.yaml", "example")["action"]
        == "block"
    )


def test_actual_registry_recovery_selects_newer_worktree_without_writes(
    tmp_path, monkeypatch
):
    pm = SCRIPTS.parents[1] / "synthesis-project-management/scripts"
    sys.path.insert(0, str(pm))
    spec = importlib.util.spec_from_file_location(
        "_hermes_pm_fixture", pm / "test_project_state.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "isolated-state"))
    repo, project = fixture.init_repo(tmp_path)
    index = repo / "projects/index.yaml"
    index.write_text(index.read_text().replace("2026-09-01", "2026-09-03"))
    fixture.run("git", "add", "projects/index.yaml", cwd=repo)
    fixture.run("git", "commit", "-m", "Refresh synthetic index", cwd=repo)
    newer = tmp_path / "newer"
    fixture.run("git", "worktree", "add", "-b", "next", str(newer), cwd=repo)
    fixture.commit_version(newer, newer / "projects/alpha", "2.0.0")
    before = fixture.run("git", "rev-parse", "HEAD", cwd=repo)
    context = adapter.recover(repo / "projects/index.yaml", "alpha")
    assert str(newer / "projects/alpha") in context
    assert "release 2.0.0" in context
    assert fixture.run("git", "rev-parse", "HEAD", cwd=repo) == before
    with pytest.raises(ValueError):
        adapter.recover(repo / "projects/index.yaml", "missing")


def test_wal_committed_metadata_is_observed_without_modifying_live_database(profile):
    db = sqlite3.connect(profile / "state.db")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("UPDATE sessions SET id=?", ("wal-session",))
    db.commit()
    before = {p.name: p.read_bytes() for p in profile.iterdir() if p.is_file()}
    try:
        result = hermes_source_binding(
            profile, "wal-session", profile="default", cwd=profile.parent
        )
        assert result["status"] == "BOUND", result
        assert all((profile / n).read_bytes() == raw for n, raw in before.items())
    finally:
        db.close()


def test_installed_spelling_cannot_escape_guard_through_symlink(profile, tmp_path):
    (profile / "skills").mkdir()
    outside = tmp_path / "source"
    outside.mkdir()
    (profile / "skills/linked").symlink_to(outside, target_is_directory=True)
    p = event(profile)
    p["tool_input"]["path"] = str(profile / "skills/linked/SKILL.md")
    assert adapter.guard(p, profile)["action"] == "block"
    p["tool_input"]["path"] = str(outside / "SKILL.md")
    assert adapter.guard(p, profile) == {}


def test_read_identity_ancestor_replacement_refused(profile, monkeypatch):
    real = os.read
    changed = False

    def race(fd, size):
        nonlocal changed
        result = real(fd, size)
        if not changed:
            changed = True
            profile.rename(profile.with_name("old"))
            profile.symlink_to(profile.with_name("old"), target_is_directory=True)
        return result

    monkeypatch.setattr(os, "read", race)
    assert (
        hermes_source_binding(
            profile, "session-opaque-1", profile="default", cwd=profile.parent
        )["status"]
        == "UNKNOWN"
    )


def test_whole_skill_install_inspection_detects_support_drift(profile, tmp_path):
    import shutil

    source = Path(__file__).resolve().parents[3]
    plan = adapter.prepare(
        source,
        profile,
        tmp_path / "index.yaml",
        "example",
        Path("/bin/synthesis"),
        ["synthesis-project-management"],
    )
    for item in plan["skills"]:
        source_dir = source / Path(item["source"]).parent
        target = Path(item["destination"]).parent
        shutil.copytree(
            source_dir,
            target,
            ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", ".ruff_cache"
            ),
        )
    report = adapter.inspect_skills(source, profile, ["synthesis-project-management"])
    assert all(item["installed"] == "PASS" for item in report)
    helper = profile / "skills/synthesis-project-management/scripts/project_state.py"
    helper.write_text(helper.read_text() + "\n# synthetic drift\n")
    report = adapter.inspect_skills(source, profile, ["synthesis-project-management"])
    assert any(item["installed"] == "FAIL" for item in report)


def test_durable_callback_observation_remains_ineligible_for_live_acceptance(
    profile, tmp_path, monkeypatch
):
    import session_context
    import conformance

    home = tmp_path / "state"
    home.mkdir(mode=0o700)
    payload = event(profile, "on_session_start")
    path = session_context.record_hermes_observation(
        payload, profile, {"content_digest": "a" * 64, "version": "1.2.3"}, home
    )
    data = json.loads(path.read_text())
    assert (
        data["kind"] == "callback-source-observation"
        and data["native_live"] == "UNKNOWN"
    )
    checks = []
    conformance._receipt_check(checks, "probe", path, expected_client="hermes")
    assert checks[0].ok is False
    payload["session_id"] = "unknown"
    with pytest.raises(ValueError):
        session_context.record_hermes_observation(
            payload, profile, {"content_digest": "a" * 64}, home
        )


def test_observation_refuses_linked_or_foreign_destination(profile, tmp_path):
    import session_context

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    other = tmp_path / "other"
    other.mkdir()
    (state / "agent-conformance").symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError):
        session_context.record_hermes_observation(
            event(profile, "on_session_start"),
            profile,
            {"content_digest": "a" * 64},
            state,
        )
    assert not list(other.iterdir())


def test_malformed_wal_cannot_silently_restore_an_older_live_row(profile):
    # SQLite may ignore an invalid WAL and expose the older main-database row.
    # Unknown sidecar bytes must not turn that fallback into a source binding.
    (profile / "state.db-wal").write_bytes(b"invalid-wal-generation")
    (profile / "state.db-wal").chmod(0o600)
    assert (
        hermes_source_binding(
            profile, "session-opaque-1", profile="default", cwd=profile.parent
        )["status"]
        == "UNKNOWN"
    )


@pytest.mark.parametrize(
    "damage", ["header-checksum", "frame-checksum", "frame-tail", "rollback-journal"]
)
def test_sidecar_corruption_cannot_be_dropped_for_old_metadata(profile, damage):
    database = sqlite3.connect(profile / "state.db")
    database.execute("PRAGMA journal_mode=WAL")
    database.execute("UPDATE sessions SET started_at=started_at-1")
    database.commit()
    wal = profile / "state.db-wal"
    raw = wal.read_bytes()
    database.close()
    assert len(raw) > 32
    if damage == "header-checksum":
        raw = raw[:24] + bytes([raw[24] ^ 1]) + raw[25:]
    elif damage == "frame-checksum":
        raw = raw[:48] + bytes([raw[48] ^ 1]) + raw[49:]
    elif damage == "frame-tail":
        raw = raw[:-1]
    elif damage == "rollback-journal":
        (profile / "state.db-journal").write_bytes(b"pending journal")
    wal.write_bytes(raw)
    wal.chmod(0o600)
    result = hermes_source_binding(
        profile, "session-opaque-1", profile="default", cwd=profile.parent
    )
    assert result["status"] == "UNKNOWN"


def test_observer_session_start_never_represents_ignored_return_as_delivery(
    profile, monkeypatch
):
    monkeypatch.setattr(adapter, "recover", lambda *a: "Recovered context")
    result = adapter.handle(
        event(profile, "on_session_start"),
        profile,
        profile.parent / "index.yaml",
        "example",
    )
    assert "context" not in result
    assert (
        result["synthesis_observation"]["context_delivery"] == "NOT_APPLICABLE_OBSERVER"
    )


def test_transformative_pre_llm_has_explicit_unverified_delivery(profile, monkeypatch):
    monkeypatch.setattr(adapter, "recover", lambda *a: "Recovered context")
    result = adapter.handle(
        event(profile, "pre_llm_call"),
        profile,
        profile.parent / "index.yaml",
        "example",
    )
    assert result["context"] == "Recovered context"
    assert (
        result["synthesis_observation"]["context_delivery"]
        == "NATIVE_CONSUMER_UNVERIFIED"
    )

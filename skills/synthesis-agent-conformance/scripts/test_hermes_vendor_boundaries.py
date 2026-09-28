import importlib.util
import sys
import json
import hashlib
import os
import uuid
import zipfile
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import vendor_bundle as vb  # noqa: E402
import hermes_source as hs  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "author_vendor_fixture", S / "test_vendor_bundle.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source = m.source
request = m.request


@pytest.fixture(autouse=True)
def synthetic_exact_runtime(tmp_path, monkeypatch):
    # A complete synthetic descriptor selects these exact source bytes. The real
    # runtime verifier and shell parser run; no installed settings are changed.
    import importlib

    scripts = S.parents[1] / "synthesis-onboarding/scripts"
    monkeypatch.syspath_prepend(str(scripts))
    runtime = importlib.import_module("release_runtime")
    contract = importlib.import_module("system_contract")
    import shutil

    root = tmp_path / "materialized-parser-generation"
    # Materialized releases have no Git directory. Copy exactly the genuine
    # parser and native manifests into a synthetic verified generation.
    for relative in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
                     "skills/synthesis-project-management/scripts/publication_command.py"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(S.parents[2] / relative, target)
    state = tmp_path / "synthetic-runtime"
    state.mkdir()
    pointer = state / "active-release.json"
    pointer.with_name(pointer.name + ".lock").touch()
    version = json.loads((root / ".codex-plugin/plugin.json").read_text())["version"]
    data = {
        "schema_version": 1,
        "version": version,
        "channel": "stable",
        "ref": "stable",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "content_digest": contract.canonical_tree_digest(root),
        "digest_algorithm": "sha256-tree-v1",
        "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/synthetic.git",
        "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(root),
        "interpreter": runtime.interpreter_pin(),
    }
    launcher = state / "synthesis"
    body = contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(body)
    launcher.chmod(0o755)
    data["launcher"] = {
        "path": str(launcher),
        "runtime_schema": 1,
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    pointer.write_text(json.dumps(data))
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(pointer))


def test_default_draft_does_not_package_unrelated_private_bytes(source, tmp_path):
    secret = source / "private-local-notes.txt"
    secret.write_text("SYNTHETIC_UNAPPROVED_LOCAL_CONTENT")
    result = vb.prepare(source, request())
    path = tmp_path / "draft.zip"
    try:
        vb.export(source, result, path)
    except ValueError:
        return
    with zipfile.ZipFile(path) as z:
        assert all(
            b"SYNTHETIC_UNAPPROVED_LOCAL_CONTENT" not in z.read(n) for n in z.namelist()
        )
        assert all("private-local-notes" not in n for n in z.namelist())


def test_unsigned_forged_native_receipt_does_not_pass(source, tmp_path, monkeypatch):
    home = tmp_path / "codex"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    sid = str(uuid.uuid4())
    transcript = home / "forged.jsonl"
    transcript.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": sid, "source": "cli"}})
        + "\n"
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": sid,
                "client": "codex",
                "provenance_env": "codex-transcript",
                "transcript_path": str(transcript),
                "transcript_bound_at_record": True,
                "plugin_root": str(source),
                "plugin_version": "1.2.3",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    assert (
        vb._native(
            "codex",
            {"receipt": str(receipt), "plugin_root": str(source)},
            "1.2.3",
            vb.source_inventory(source),
        )
        == "UNKNOWN"
    )


def test_forged_source_release_field_cannot_authorize_archive(source, tmp_path):
    result = vb.prepare(source, request())
    result["gates"]["release"] = "PASS"
    result["release_observation"] = {
        "status": "PASS",
        "source_digest": result["source_digest"],
    }
    result.pop("bundle_digest")
    result["bundle_digest"] = vb.digest(result)
    with pytest.raises(ValueError):
        vb.export(source, result, tmp_path / "forged.zip")


def test_export_ancestor_replacement_cannot_write_foreign_directory(
    source, tmp_path, monkeypatch
):
    result = vb.prepare(source, request())
    parent = tmp_path / "output"
    parent.mkdir()
    other = tmp_path / "unrelated"
    other.mkdir()
    real = vb.os.open
    fired = []

    def race(path, flags, *a, **kw):
        if not fired and flags & os.O_CREAT:
            fired.append(True)
            parent.rename(tmp_path / "parked-output")
            parent.symlink_to(other, target_is_directory=True)
        return real(path, flags, *a, **kw)

    monkeypatch.setattr(vb.os, "open", race)
    try:
        vb.export(source, result, parent / "review.zip")
    except (OSError, ValueError):
        pass
    assert not (other / "review.zip").exists()


def profile(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir(mode=0o700)
    db = sqlite3.connect(home / "state.db")
    db.execute(
        "CREATE TABLE sessions(id TEXT,source TEXT,parent_session_id TEXT,started_at REAL,ended_at REAL,cwd TEXT,profile_name TEXT)"
    )
    db.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
        ("synthetic", "cli", None, time.time(), None, str(tmp_path), "default"),
    )
    db.commit()
    db.close()
    (home / "state.db").chmod(0o600)
    return home


def test_new_rollback_journal_invalidates_source_observation(tmp_path, monkeypatch):
    home = profile(tmp_path)
    real = hs.sqlite3.connect

    def race(*a, **kw):
        connection = real(*a, **kw)
        (home / "state.db-journal").write_bytes(b"synthetic-hot-journal")
        return connection

    monkeypatch.setattr(hs.sqlite3, "connect", race)
    assert (
        hs.binding(home, "synthetic", profile="default", cwd=tmp_path)["status"]
        == "UNKNOWN"
    )


def test_unchanged_source_binding_positive(tmp_path):
    home = profile(tmp_path)
    result = hs.binding(home, "synthetic", profile="default", cwd=tmp_path)
    assert (
        result["status"] == "BOUND"
        and result["native_live"] == "UNKNOWN"
        and result["authority"] is False
    )


@pytest.mark.parametrize(
    "tool,args",
    [
        ("write_file", {"path": "SKILL.md", "content": "mutation"}),
        (
            "write_file",
            {"path": "SKILL.md", "content": "mutation", "workdir": "/benign"},
        ),
        ("patch", {"path": "SKILL.md", "old_string": "a", "new_string": "b"}),
        (
            "patch",
            {
                "mode": "patch",
                "patch": "*** Begin Patch\n*** Update File: SKILL.md\n@@\n-a\n+b\n*** End Patch",
            },
        ),
        ("terminal", {"command": "printf mutation > SKILL.md"}),
        ("terminal", {"command": "printf mutation > SKILL.md", "cwd": "/benign"}),
    ],
)
def test_unknown_native_persistent_cwd_cannot_authorize_relative_write(
    tmp_path, tool, args
):
    import hermes_adapter

    home = tmp_path / "hermes"
    home.mkdir()
    process_cwd = tmp_path / "launch"
    process_cwd.mkdir()
    assert (
        hermes_adapter.guard(
            {"tool_name": tool, "tool_input": args, "cwd": str(process_cwd)}, home
        ).get("action")
        == "block"
    )


@pytest.mark.parametrize("bytecode_enabled", [True, False])
def test_native_explicit_workdir_and_absolute_write_positive(tmp_path, monkeypatch, bytecode_enabled):
    import hermes_adapter

    monkeypatch.setattr(sys, "dont_write_bytecode", not bytecode_enabled)
    monkeypatch.setattr(sys, "pycache_prefix", None)
    generation = tmp_path / "materialized-parser-generation"
    original_members = {p.relative_to(generation).as_posix() for p in generation.rglob("*")}
    home = tmp_path / "hermes"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    for tool, args in [
        ("write_file", {"path": str(work / "doc"), "content": "x"}),
        ("terminal", {"command": "printf x > doc", "workdir": str(work)}),
        ("terminal", {"command": f"cd {work} && printf x > doc"}),
        ("terminal", {"command": "pwd"}),
    ]:
        assert (
            hermes_adapter.guard(
                {"tool_name": tool, "tool_input": args, "cwd": str(tmp_path)}, home
            )
            == {}
        )
        assert {p.relative_to(generation).as_posix() for p in generation.rglob("*")} == original_members


def test_verified_parser_rejects_changed_generation_with_bytecode_enabled(tmp_path, monkeypatch):
    import hermes_adapter

    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    monkeypatch.setattr(sys, "pycache_prefix", None)
    generation = tmp_path / "materialized-parser-generation"
    parser = generation / "skills/synthesis-project-management/scripts/publication_command.py"
    parser.write_bytes(parser.read_bytes() + b"\n# synthetic changed release bytes\n")
    home = tmp_path / "hermes"
    home.mkdir()
    result = hermes_adapter.guard(
        {"tool_name": "terminal", "tool_input": {"command": "pwd"}, "cwd": str(tmp_path)}, home
    )
    assert result["action"] == "block"
    assert "content digest drifted" in result["message"]
    assert not list(generation.rglob("*.pyc"))

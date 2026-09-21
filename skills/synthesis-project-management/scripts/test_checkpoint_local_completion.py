"""Committed local source can survive owner release without authorizing publication."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import sys
from types import SimpleNamespace

import pytest

import coordination
from coordination_schema import identity_from_uuid
import project_state as state
from test_checkpoint_observer import (
    FOREIGN, NATIVE, board, event, inspect, native_output, observer, run,
)


def completed_local(fixture, monkeypatch, client="claude", *, committed=True):
    source = fixture.root / "source"
    source.mkdir()
    run("git", "init", "-b", "preview", cwd=source)
    run("git", "config", "user.name", "Fixture", cwd=source)
    run("git", "config", "user.email", "fixture@example.com", cwd=source)
    run("git", "config", "core.hooksPath", str(fixture.root / "fixture-hooks"), cwd=source)
    target = source / "component.txt"
    literal = source / ":(glob)*.txt"
    target.write_text("reviewed source\n")
    literal.write_text("literal pathspec\n")
    run("git", "add", "--all", cwd=source)
    run("git", "commit", "-m", "Fixture", cwd=source)
    if not committed:
        target.write_text("retained uncommitted source\n")

    reference = f"{'cc' if client == 'claude' else 'codex'}:{NATIVE}"
    board(fixture.board, [(FOREIGN, identity_from_uuid(FOREIGN).compact_id, "alpha", str(fixture.repo))])
    fixture.board.write_text(fixture.board.read_text().replace(f"tool:{FOREIGN}", reference))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", reference)
    assert inspect(fixture, event(fixture, client)) == ("PASS", [])
    checkpoint = next(fixture.receipts.glob("*.json"))
    accepted = checkpoint.read_bytes()

    pending = fixture.guard / "pending"
    pending.mkdir(parents=True)
    manifest = pending / (hashlib.sha256(NATIVE.encode()).hexdigest() + ".json")
    manifest.write_text(json.dumps({"schema_version": 2, "session_id": NATIVE,
                                    "paths": [str(target), str(literal)], "remote_paths": []}))
    # Exercise the actual local-handoff writer, not a fabricated green receipt.
    script = Path(state.__file__).resolve().parents[2] / "synthesis-repo-guard" / "checkpoint_sync.py"
    spec = importlib.util.spec_from_file_location("fixture_local_handoff", script)
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    results, selected = sync.local_handoff_checkpoint(event(fixture, client), sync.DEFAULTS)
    assert selected == manifest and all(item["action"] == "local-ready" for item in results)
    receipt = fixture.guard / "local-handoff" / manifest.name
    assert json.loads(receipt.read_text())["readiness"] == "LOCAL_READY"
    assert coordination.command_release(SimpleNamespace(board=fixture.board, id=FOREIGN,
                                                        active_project_file=None)) == 0
    assert state.row_for_event(state._parse_board_rows(fixture.board), event(fixture, client), fixture.board) is None
    return SimpleNamespace(source=source, target=target, literal=literal, manifest=manifest,
                           receipt=receipt, checkpoint=checkpoint, accepted=accepted, sync=sync)


def retained_bytes(fixture, local):
    return {path: path.read_bytes() for path in (
        fixture.board, local.manifest, local.receipt, local.checkpoint, local.target, local.literal,
    )}


@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("cwd", ["project", "workspace"])
def test_committed_source_local_handoff_survives_release(observer, monkeypatch, capsys, client, cwd):
    local = completed_local(observer, monkeypatch, client)
    before = retained_bytes(observer, local)
    original = state._observer_git

    def read_only_git(repo, *args):
        assert args[0] in {"rev-parse", "branch", "status", "ls-files", "ls-tree", "diff", "cat-file", "hash-object", "log"}
        return original(repo, *args)

    monkeypatch.setattr(state, "_observer_git", read_only_git)
    monkeypatch.setattr(state, "checkpoint_project", lambda *a, **kw: pytest.fail("released observer cannot checkpoint"))
    capsys.readouterr()
    for repeated in (False, True):
        payload = event(observer, client, cwd=str(observer.project if cwd == "project" else observer.root),
                        stop_hook_active=repeated)
        verdict, issues = inspect(observer, payload)
        assert verdict == "NOT_APPLICABLE", issues
        assert any("committed local source" in issue for issue in issues)
        assert state._emit_checkpoint_hook(verdict, issues, payload) == 0
        emitted = capsys.readouterr()
        _, report = native_output(emitted.out)
        assert report["checkpoint_accepted"] is False and report["no_receipt_issued"] is True
        assert not emitted.err
    assert retained_bytes(observer, local) == before
    assert list(observer.receipts.glob("*.json")) == [local.checkpoint]


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_local_ready_alone_does_not_exonerate_uncommitted_source(observer, monkeypatch, client):
    local = completed_local(observer, monkeypatch, client, committed=False)
    before = retained_bytes(observer, local)
    assert inspect(observer, event(observer, client))[0] in {"UNKNOWN", "FAIL"}
    assert retained_bytes(observer, local) == before


@pytest.mark.parametrize("mutation", ["unstaged", "staged", "untracked", "missing_state"])
def test_completed_local_source_still_checks_structured_project(observer, monkeypatch, mutation):
    local = completed_local(observer, monkeypatch)
    if mutation == "missing_state":
        (observer.project / state.STATE_FILE).unlink()
    else:
        target = observer.project / ("new.txt" if mutation == "untracked" else "REFERENCE.md")
        target.write_text("project work remains\n")
        if mutation == "staged":
            run("git", "add", str(target), cwd=observer.repo)
    before = retained_bytes(observer, local)
    assert inspect(observer)[0] in {"UNKNOWN", "FAIL"}
    assert retained_bytes(observer, local) == before


@pytest.mark.parametrize("defect", [
    "missing_receipt", "wrong_session", "wrong_schema", "wrong_digest", "wrong_manifest",
    "missing_file", "extra_file", "wrong_head", "wrong_branch", "wrong_hash", "wrong_mode",
    "blocked", "uncommitted", "staged", "ignored", "mode_changed", "head_changed",
    "branch_changed", "manifest_changed", "remote_path", "legacy_manifest", "receipt_symlink",
    "source_symlink", "unsafe_parent", "untracked_receipt", "ignored_untracked_receipt", "assume_unchanged",
])
def test_local_completion_integrity_defects_remain_blocked(observer, monkeypatch, defect):
    local = completed_local(observer, monkeypatch)
    receipt = json.loads(local.receipt.read_text())
    manifest = json.loads(local.manifest.read_text())
    item = receipt["results"][0]
    if defect == "missing_receipt":
        local.receipt.unlink()
    elif defect in {"wrong_session", "wrong_schema", "wrong_digest", "wrong_manifest", "blocked"}:
        key, value = {"wrong_session": ("session_id", FOREIGN), "wrong_schema": ("schema_version", True),
                      "wrong_digest": ("pending_manifest_sha256", "a" * 64),
                      "wrong_manifest": ("pending_manifest", str(local.receipt)),
                      "blocked": ("readiness", "BLOCKED")}[defect]
        receipt[key] = value
    elif defect in {"missing_file", "extra_file", "wrong_head", "wrong_branch", "wrong_hash", "wrong_mode"}:
        if defect == "missing_file":
            item["file_evidence"].pop()
        elif defect == "extra_file":
            item["file_evidence"].append(dict(item["file_evidence"][0]))
        elif defect in {"wrong_head", "wrong_branch"}:
            item["head" if defect == "wrong_head" else "branch"] = "incorrect"
        else:
            item["file_evidence"][0]["sha256" if defect == "wrong_hash" else "git_mode"] = "incorrect"
    elif defect in {"uncommitted", "staged", "assume_unchanged"}:
        local.target.write_text("changed after receipt\n")
        if defect == "staged":
            run("git", "add", "component.txt", cwd=local.source)
        elif defect == "assume_unchanged":
            run("git", "update-index", "--assume-unchanged", "component.txt", cwd=local.source)
            # Even a refreshed handoff with status hidden by index flags is not committed evidence.
            local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
            receipt = json.loads(local.receipt.read_text())
    elif defect == "ignored":
        (local.source / ".git/info/exclude").write_text("component.txt\n")
        run("git", "rm", "--cached", "component.txt", cwd=local.source)
    elif defect == "mode_changed":
        local.target.chmod(0o755)
    elif defect == "head_changed":
        run("git", "commit", "--allow-empty", "-m", "New head", cwd=local.source)
    elif defect == "branch_changed":
        run("git", "checkout", "-b", "different", cwd=local.source)
    elif defect in {"manifest_changed", "remote_path", "legacy_manifest"}:
        if defect == "manifest_changed":
            manifest["updated_at"] = "new attribution"
        elif defect == "remote_path":
            manifest["remote_paths"] = [str(local.target)]
        else:
            manifest.pop("remote_paths")
        local.manifest.write_text(json.dumps(manifest))
        receipt["pending_manifest_sha256"] = hashlib.sha256(local.manifest.read_bytes()).hexdigest()
        if defect == "manifest_changed":
            receipt["pending_manifest_sha256"] = "a" * 64
    elif defect == "source_symlink":
        local.target.unlink()
        local.target.symlink_to(local.literal)
    elif defect == "unsafe_parent":
        moved = local.source.with_name("moved-source")
        local.source.rename(moved)
        local.source.symlink_to(moved, target_is_directory=True)
    elif defect in {"untracked_receipt", "ignored_untracked_receipt"}:
        run("git", "rm", "--cached", "component.txt", cwd=local.source)
        run("git", "commit", "-m", "Untrack", cwd=local.source)
        if defect == "ignored_untracked_receipt":
            (local.source / ".git/info/exclude").write_text("component.txt\n")
            assert not run("git", "status", "--porcelain", cwd=local.source)
        local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
        receipt = json.loads(local.receipt.read_text())
    if defect != "missing_receipt":
        local.receipt.write_text(json.dumps(receipt))
    if defect == "receipt_symlink":
        saved = local.receipt.with_suffix(".saved")
        local.receipt.rename(saved)
        local.receipt.symlink_to(saved)
    before = local.manifest.read_bytes(), local.checkpoint.read_bytes()
    assert inspect(observer)[0] in {"UNKNOWN", "FAIL"}
    assert (local.manifest.read_bytes(), local.checkpoint.read_bytes()) == before


@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("kind", ["committed_deletion", "uncommitted_deletion", "never_tracked"])
def test_local_completion_distinguishes_committed_deletion(observer, monkeypatch, client, kind):
    local = completed_local(observer, monkeypatch, client)
    if kind == "committed_deletion":
        run("git", "rm", "component.txt", cwd=local.source)
        run("git", "commit", "-m", "Remove fixture", cwd=local.source)
    elif kind == "uncommitted_deletion":
        local.target.unlink()
    else:
        data = json.loads(local.manifest.read_text())
        data["paths"].append(str(local.source / "never-tracked.txt"))
        local.manifest.write_text(json.dumps(data))
    local.sync.local_handoff_checkpoint(event(observer, client), local.sync.DEFAULTS)
    before = local.manifest.read_bytes(), local.receipt.read_bytes(), local.checkpoint.read_bytes()
    verdict, _issues = inspect(observer, event(observer, client))
    assert (verdict == "NOT_APPLICABLE") is (kind == "committed_deletion")
    assert (local.manifest.read_bytes(), local.receipt.read_bytes(), local.checkpoint.read_bytes()) == before


@pytest.mark.parametrize("entry", ["context", "registry"])
def test_empty_remote_paths_cannot_disguise_project_records_as_source(observer, monkeypatch, entry):
    local = completed_local(observer, monkeypatch)
    target = observer.project / "CONTEXT.md" if entry == "context" else observer.repo / "projects/index.yaml"
    data = json.loads(local.manifest.read_text())
    data["paths"].append(str(target))
    local.manifest.write_text(json.dumps(data))
    local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
    before = local.manifest.read_bytes(), local.receipt.read_bytes(), local.checkpoint.read_bytes()
    assert inspect(observer, event(observer, cwd=str(observer.root)))[0] in {"UNKNOWN", "FAIL"}
    assert (local.manifest.read_bytes(), local.receipt.read_bytes(), local.checkpoint.read_bytes()) == before


@pytest.mark.parametrize("shallow", [False, True])
def test_ordinary_source_projects_directory_is_not_registry_adoption(observer, monkeypatch, shallow):
    local = completed_local(observer, monkeypatch)
    target = local.source / "projects" / "widget" / "app.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ordinary source\n")
    index = local.source / "projects/index.yaml"
    index.write_text("application_modules: [widget]\n")
    run("git", "add", "--all", cwd=local.source)
    run("git", "commit", "-m", "Fixture", cwd=local.source)
    data = json.loads(local.manifest.read_text())
    data["paths"].extend([str(target), str(index)])
    local.manifest.write_text(json.dumps(data))
    local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
    if shallow:
        head = run("git", "rev-parse", "HEAD", cwd=local.source)
        (local.source / ".git/shallow").write_text(head + "\n")
        # No earlier adoption exists in this disposable fixture's reflogs;
        # incomplete history still cannot prove it was never adopted.
    assert (inspect(observer)[0] == "NOT_APPLICABLE") is not shallow


def test_local_completion_preserves_foreign_manifests_claims_and_dirty_files(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    foreign = local.manifest.with_name(hashlib.sha256(FOREIGN.encode()).hexdigest() + ".json")
    foreign.write_text("foreign attribution remains opaque\n")
    unrelated = local.source / "foreign-untracked.txt"
    unrelated.write_text("retained work\n")
    other = observer.repo / "projects" / "beta"
    other.mkdir()
    retained = other / "REFERENCE.md"
    retained.write_text("retained project work\n")
    run("git", "add", str(retained), cwd=observer.repo)
    board(observer.board, [(FOREIGN, identity_from_uuid(FOREIGN).compact_id, "beta", str(observer.repo))])
    before = retained_bytes(observer, local), foreign.read_bytes(), unrelated.read_bytes(), retained.read_bytes()
    staged = run("git", "diff", "--cached", cwd=observer.repo)
    assert inspect(observer)[0] == "NOT_APPLICABLE"
    assert (retained_bytes(observer, local), foreign.read_bytes(), unrelated.read_bytes(), retained.read_bytes()) == before
    assert run("git", "diff", "--cached", cwd=observer.repo) == staged


@pytest.mark.parametrize("mutation", ["manifest", "receipt", "file", "head", "branch", "index"])
def test_local_completion_rechecks_evidence_across_concurrent_changes(observer, monkeypatch, mutation):
    local = completed_local(observer, monkeypatch)
    original = state._observer_local_source_snapshot
    calls = []

    def interleave(repo, result):
        snapshot = original(repo, result)
        calls.append(repo)
        if len(calls) == 1:
            if mutation in {"manifest", "receipt"}:
                path = local.manifest if mutation == "manifest" else local.receipt
                path.write_bytes(path.read_bytes() + b"\n")
            elif mutation == "file":
                local.target.write_text("concurrent edit\n")
            elif mutation == "head":
                run("git", "commit", "--allow-empty", "-m", "New head", cwd=local.source)
            elif mutation == "branch":
                run("git", "checkout", "-b", "new-branch", cwd=local.source)
            else:
                run("git", "rm", "--cached", "component.txt", cwd=local.source)
        return snapshot

    monkeypatch.setattr(state, "_observer_local_source_snapshot", interleave)
    assert inspect(observer)[0] in {"UNKNOWN", "FAIL"}
    assert calls and local.manifest.exists() and local.receipt.exists()
    assert local.checkpoint.read_bytes() == local.accepted


@pytest.mark.parametrize("defect", ["duplicate_manifest_key", "duplicate_receipt_key", "malformed_receipt", "directory_receipt"])
def test_local_completion_invalid_json_and_file_types_fail_closed(observer, monkeypatch, defect):
    local = completed_local(observer, monkeypatch)
    if defect == "duplicate_manifest_key":
        local.manifest.write_text(local.manifest.read_text().replace('"remote_paths": []', '"remote_paths": [], "remote_paths": []'))
    elif defect == "duplicate_receipt_key":
        local.receipt.write_text(local.receipt.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
    elif defect == "malformed_receipt":
        local.receipt.write_text("{")
    else:
        local.receipt.unlink()
        local.receipt.mkdir()
    assert inspect(observer)[0] == "FAIL"
    assert local.manifest.exists() and local.checkpoint.read_bytes() == local.accepted


def test_committed_binary_and_executable_source_use_exact_git_objects(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    local.target.write_bytes(b"\x00\xff\xfe\r\n\x00fixture")
    local.target.chmod(0o755)
    run("git", "add", "--all", cwd=local.source)
    run("git", "commit", "-m", "Binary fixture", cwd=local.source)
    local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
    assert inspect(observer)[0] == "NOT_APPLICABLE"


def test_rewritten_registry_cannot_erase_retained_adoption(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    registry = observer.repo / "projects/index.yaml"
    registry.write_text("application_modules: [widget]\n")
    run("git", "add", str(registry), cwd=observer.repo)
    run("git", "commit", "-m", "Rewrite fixture registry", cwd=observer.repo)
    data = json.loads(local.manifest.read_text())
    data["paths"].append(str(registry))
    local.manifest.write_text(json.dumps(data))
    local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
    assert inspect(observer, event(observer, cwd=str(observer.root)))[0] in {"UNKNOWN", "FAIL"}


@pytest.mark.parametrize("redirect", ["GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY", "GIT_CONFIG_COUNT"])
def test_local_completion_ignores_ambient_git_redirects(observer, monkeypatch, redirect):
    local = completed_local(observer, monkeypatch)
    if redirect == "GIT_DIR":
        monkeypatch.setenv(redirect, str(observer.repo / ".git"))
    elif redirect == "GIT_WORK_TREE":
        monkeypatch.setenv(redirect, str(observer.repo))
    elif redirect == "GIT_OBJECT_DIRECTORY":
        monkeypatch.setenv(redirect, str(observer.root / "unavailable-objects"))
    else:
        monkeypatch.setenv(redirect, "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.bare")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    assert inspect(observer)[0] == "NOT_APPLICABLE"


def test_fake_ambient_index_cannot_hide_staged_source(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    fake = observer.root / "fake-index"
    fake.write_bytes((local.source / ".git/index").read_bytes())
    run("git", "rm", "--cached", "component.txt", cwd=local.source)
    monkeypatch.setenv("GIT_INDEX_FILE", str(fake))
    assert inspect(observer)[0] in {"UNKNOWN", "FAIL"}


def test_observer_never_executes_configured_fsmonitor_or_clean_filters(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    marker = observer.root / "executed-configured-program"
    program = observer.root / "configured-program.py"
    program.write_text("import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('executed')\n"
                       "sys.stdout.buffer.write(sys.stdin.buffer.read())\n")
    command = " ".join(shlex.quote(str(value)) for value in (sys.executable, program, marker))
    # A direct positive control proves the marker detects execution.
    run(sys.executable, str(program), str(marker), cwd=observer.root)
    assert marker.read_text() == "executed"
    marker.unlink()
    for repo, target in ((local.source, local.target), (observer.repo, observer.project / "REFERENCE.md")):
        attributes = repo / ".gitattributes"
        attributes.write_text(f"{target.relative_to(repo).as_posix()} filter=fixture\n")
        run("git", "add", ".gitattributes", cwd=repo)
        run("git", "commit", "-m", "Attribute fixture", cwd=repo)
        run("git", "config", "filter.fixture.clean", command, cwd=repo)
        run("git", "config", "filter.fixture.process", command, cwd=repo)
        run("git", "config", "filter.fixture.required", "true", cwd=repo)
        run("git", "config", "core.fsmonitor", command, cwd=repo)
        # Force content inspection rather than trusting the index stat cache.
        target.write_bytes(target.read_bytes())
    local.sync.local_handoff_checkpoint(event(observer), local.sync.DEFAULTS)
    assert inspect(observer)[0] == "NOT_APPLICABLE"
    assert not marker.exists()


def test_observer_preserves_configured_safe_directory_trust(observer, monkeypatch):
    config = observer.root / "trusted.gitconfig"
    config.write_text(f"[safe]\n\tdirectory = {observer.repo}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    done = state._observer_git(observer.repo, "config", "--get-all", "safe.directory")
    assert done.returncode == 0 and done.stdout.strip() == str(observer.repo)


def test_replacement_objects_cannot_substitute_committed_evidence(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    original_head = run("git", "rev-parse", "HEAD", cwd=local.source)
    original_bytes = local.target.read_bytes()
    local.target.write_text("replacement object bytes\n")
    run("git", "add", "component.txt", cwd=local.source)
    tree = run("git", "write-tree", cwd=local.source)
    replacement = run("git", "commit-tree", tree, "-m", "Replacement fixture", cwd=local.source)
    local.target.write_bytes(original_bytes)
    run("git", "reset", "HEAD", "--", "component.txt", cwd=local.source)
    run("git", "replace", original_head, replacement, cwd=local.source)
    assert inspect(observer)[0] == "NOT_APPLICABLE"


def test_missing_promisor_object_never_contacts_a_remote(observer, monkeypatch):
    local = completed_local(observer, monkeypatch)
    marker = observer.root / "remote-contacted"
    remote = observer.root / "fixture-remote.sh"
    remote.write_text(f"#!/bin/sh\nprintf called > {shlex.quote(str(marker))}\nexit 1\n")
    remote.chmod(0o755)
    run("git", "config", "extensions.partialClone", "origin", cwd=local.source)
    run("git", "config", "remote.origin.promisor", "true", cwd=local.source)
    run("git", "config", "remote.origin.url", f"ext::{remote}", cwd=local.source)
    run("git", "config", "protocol.ext.allow", "always", cwd=local.source)
    tree = run("git", "rev-parse", "HEAD^{tree}", cwd=local.source)
    object_file = local.source / ".git/objects" / tree[:2] / tree[2:]
    assert object_file.is_file() and object_file.is_relative_to(observer.root)
    object_file.unlink()
    assert inspect(observer)[0] in {"UNKNOWN", "FAIL"}
    assert not marker.exists()

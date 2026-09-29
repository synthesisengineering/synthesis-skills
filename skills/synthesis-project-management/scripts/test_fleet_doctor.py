"""Fleet doctor: reachability, freshness, coherence, seals, divergence.

Each check fails closed; unconfigured inputs skip loudly. The
divergence-catch test proves a checkout that split from its upstream fails
the gate naming the repo, then passes again once reunited.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MODULE = importlib.import_module("coordination")
DOCTOR = importlib.import_module("fleet_doctor")
HANDOFF = importlib.import_module("fleet_handoff")
FI = importlib.import_module("fleet_identity")

T0 = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    for name in (
        "SYNTHESIS_CLIENT_SESSION_REF",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_PID",
        "CLAUDECODE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(tmp_path / "fleet"))


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def git(*arguments, cwd):
    completed = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def lease_boards(tmp_path: Path, count: int = 2) -> list[Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(remote)],
        check=True,
        capture_output=True,
    )
    boards = []
    for index in range(1, count + 1):
        directory = tmp_path / f"machine{index}"
        directory.mkdir()
        (directory / "lease.json").write_text(
            json.dumps({"remote": str(remote)}), encoding="utf-8"
        )
        boards.append(directory / "active-sessions.md")
    return boards


def claim(board, *, session_id, area, workspace, machine="mac-a", ref="codex:doc",
          project=None):
    import os

    os.environ["SYNTHESIS_CLIENT_SESSION_REF"] = ref
    request = args(
        board,
        id=session_id,
        agent=f"agent-{session_id}",
        machine=machine,
        project=project or f"doctor-{session_id}",
        mode="autonomous",
        goal="gate",
        workspace=[workspace],
        area=[area],
        context_role="owner",
        replace=False,
        client_ref=None,
    )
    assert MODULE.command_claim(request) == 0


def make_row(**overrides):
    identity = MODULE.new_identity()
    fields = {
        "session_uuid": identity.session_uuid,
        "compact_id": identity.compact_id,
        "speakable_id": identity.speakable_id,
        "legacy_id": "",
        "agent": "agent-x",
        "machine": "machine-x",
        "machine_label": "mac-x",
        "project": "doctor",
        "started": T0.isoformat(),
        "heartbeat": T0.isoformat(),
        "mode": "autonomous",
        "workspaces": ["/tmp/wt @ main"],
        "goal": "gate",
        "claims": ["repo/**"],
        "context_role": "owner",
        "status": "active",
        "client_ref": "codex:doc",
    }
    fields.update(overrides)
    return MODULE.Session(**fields)


def test_reachability_passes_skip_and_fails_unreachable(tmp_path):
    board_a, _ = lease_boards(tmp_path)
    claim(board_a, session_id="A", area="repo/**",
          workspace="/tmp/wt-a @ main")
    ok = DOCTOR.check_reachability(board_a)
    assert ok.ok and "answers" in ok.detail

    missing = tmp_path / "lonely"
    missing.mkdir()
    (missing / "lease.json").write_text(
        json.dumps({"remote": str(tmp_path / "missing.git")}), encoding="utf-8"
    )
    lonely = missing / "active-sessions.md"
    lonely.write_text(MODULE.template(), encoding="utf-8")
    failed = DOCTOR.check_reachability(lonely)
    assert not failed.ok and "lease-unreachable" in failed.detail

    plain = tmp_path / "plain.md"
    plain.write_text(MODULE.template(), encoding="utf-8")
    skipped = DOCTOR.check_reachability(plain)
    assert skipped.ok and "nothing to reach" in skipped.detail

    declared = tmp_path / "declared.md"
    declared.write_text(
        MODULE.ensure_lease_declaration(MODULE.template(), "https://example.com/x"),
        encoding="utf-8",
    )
    guarded = DOCTOR.check_reachability(declared)
    assert not guarded.ok and "missing" in guarded.detail


def test_lease_freshness_catches_a_stale_mirror(tmp_path):
    board_a, board_b = lease_boards(tmp_path)
    claim(board_a, session_id="A", area="repo/a/**",
          workspace="/tmp/wt-a @ main", ref="codex:doc-a")
    assert MODULE.lease_refresh(board_b)["refreshed"] is True
    assert DOCTOR.check_lease_freshness(board_b).ok

    claim(board_a, session_id="B", area="repo/b/**",
          workspace="/tmp/wt-b @ main", ref="codex:doc-b")
    stale = DOCTOR.check_lease_freshness(board_b)
    assert not stale.ok and "differs from leased tip" in stale.detail

    assert MODULE.lease_refresh(board_b)["refreshed"] is True
    assert DOCTOR.check_lease_freshness(board_b).ok

    plain = tmp_path / "plain.md"
    plain.write_text(MODULE.template(), encoding="utf-8")
    assert DOCTOR.check_lease_freshness(plain).ok


def test_workset_consistency_names_malformed_rows():
    healthy = MODULE.replace_table(MODULE.template(), [make_row()])
    assert DOCTOR.check_workset_consistency(healthy).ok

    no_claims = MODULE.replace_table(
        MODULE.template(), [make_row(claims=[])]
    )
    failed = DOCTOR.check_workset_consistency(no_claims)
    assert not failed.ok and "no claimed areas" in failed.detail

    no_workspace = MODULE.replace_table(
        MODULE.template(), [make_row(workspaces=[])]
    )
    failed = DOCTOR.check_workset_consistency(no_workspace)
    assert not failed.ok and "names no workspace" in failed.detail

    released_ignored = MODULE.replace_table(
        MODULE.template(),
        [make_row(status="released", claims=[], workspaces=[])],
    )
    assert DOCTOR.check_workset_consistency(released_ignored).ok


def test_parked_coherence_requires_records_and_live_annotations():
    parked = make_row(status="parked")
    recordless = MODULE.replace_table(MODULE.template(), [parked])
    failed = DOCTOR.check_parked_coherence(recordless)
    assert not failed.ok and "no park record" in failed.detail

    recorded = MODULE.append_bus_block(
        recordless,
        MODULE.park_record_block(parked, "operator", "mac-a", T0.isoformat()),
    )
    assert DOCTOR.check_parked_coherence(recorded).ok

    dangling = MODULE.append_bus_block(
        recorded,
        MODULE.overlaps_parked_block("s-missing-successor", parked, ["repo/**"]),
    )
    failed = DOCTOR.check_parked_coherence(dangling)
    assert not failed.ok and "missing successor" in failed.detail


def test_artifacts_verify_seals_and_list_open_ones(tmp_path):
    missing = DOCTOR.check_artifacts(tmp_path / "nowhere")
    assert missing.ok and "no handoff artifacts" in missing.detail

    artifacts = tmp_path / "handoffs"
    artifacts.mkdir()
    offer = {
        "ticket": "handoff-doc", "from_machine": "a", "from_label": "A",
        "to_machine": "b", "to_label": "B", "session_compact": "s-x",
        "readiness": HANDOFF.READINESS_CLEAN, "worksets": [], "manifests": [],
        "offered_at": T0.isoformat(),
    }
    HANDOFF.write_sealed_artifact(
        artifacts, HANDOFF.seal_offer(offer, sealed_at=T0.isoformat())
    )
    (artifacts / "handoff-wip.open.json").write_text('{"ticket": "wip"}\n')
    passed = DOCTOR.check_artifacts(artifacts)
    assert passed.ok
    assert "1 sealed artifact(s) verify" in passed.detail
    assert "handoff-wip.open.json" in passed.detail

    sealed_path = artifacts / "handoff-doc.sealed.json"
    tampered = json.loads(sealed_path.read_text(encoding="utf-8"))
    tampered["offer"]["readiness"] = HANDOFF.READINESS_BLOCKED
    sealed_path.write_text(json.dumps(tampered), encoding="utf-8")
    failed = DOCTOR.check_artifacts(artifacts)
    assert not failed.ok and "handoff-doc.sealed.json" in failed.detail


def seed_repo(path: Path) -> str:
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(path)],
        check=True,
        capture_output=True,
    )
    work = path.parent / "seed-work"
    subprocess.run(
        ["git", "init", "-b", "main", "--quiet", str(work)],
        check=True,
        capture_output=True,
    )
    git("config", "user.name", "Test", cwd=work)
    git("config", "user.email", "test@example.com", cwd=work)
    (work / "notes.md").write_text("seed\n", encoding="utf-8")
    git("add", "notes.md", cwd=work)
    git("commit", "--quiet", "-m", "seed", cwd=work)
    git("remote", "add", "origin", str(path), cwd=work)
    git("push", "--quiet", "origin", "main", cwd=work)
    subprocess.run(
        ["git", "--git-dir", str(path), "symbolic-ref", "HEAD",
         "refs/heads/main"],
        check=True,
        capture_output=True,
    )
    return str(path)


def clone(remote_url: str, dest: Path) -> Path:
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "clone", "--quiet",
         remote_url, str(dest)],
        check=True,
        capture_output=True,
    )
    git("config", "user.name", "Test", cwd=dest)
    git("config", "user.email", "test@example.com", cwd=dest)
    return dest


def commit_file(repo: Path, name: str):
    (repo / name).write_text("work\n", encoding="utf-8")
    git("add", name, cwd=repo)
    git("commit", "--quiet", "-m", name, cwd=repo)


def test_divergence_scan_catches_a_split_checkout(tmp_path):
    remote_url = seed_repo(tmp_path / "origin.git")
    local = clone(remote_url, tmp_path / "local")
    assert DOCTOR.check_divergence([local]).ok

    peer = clone(remote_url, tmp_path / "peer")
    commit_file(peer, "peer.md")
    git("push", "--quiet", "origin", "main", cwd=peer)
    commit_file(local, "local.md")

    # The split is visible once the local tracking ref learns the peer side.
    git("fetch", "--quiet", "origin", cwd=local)
    caught = DOCTOR.check_divergence([local])
    assert not caught.ok
    assert "diverged" in caught.detail
    assert str(local) in caught.detail
    assert "1 ahead, 1 behind" in caught.detail
    assert "never force-push" in caught.detail

    git("pull", "--quiet", "--rebase", "origin", "main", cwd=local)
    assert DOCTOR.check_divergence([local]).ok

    assert DOCTOR.check_divergence([]).ok
    missing = DOCTOR.check_divergence([tmp_path / "nope"])
    assert not missing.ok and "not a git checkout" in missing.detail


def test_run_all_and_cli_cover_a_healthy_fleet(tmp_path, capsys):
    board_a, _ = lease_boards(tmp_path)
    claim(board_a, session_id="A", area="repo/**",
          workspace="/tmp/wt-a @ main")
    checks = DOCTOR.run_all(board=board_a, artifacts_dir=tmp_path / "handoffs")
    assert [check.id for check in checks] == [
        "reachability", "lease-freshness", "workset-consistency",
        "parked-coherence", "artifact-sealed", "divergence-scan", "storage-custody",
    ]
    assert all(check.ok for check in checks), DOCTOR.format_report(checks)

    assert DOCTOR.main(["--board", str(board_a)]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS fleet-") == 7

    remote_url = seed_repo(tmp_path / "origin.git")
    local = clone(remote_url, tmp_path / "local")
    peer = clone(remote_url, tmp_path / "peer")
    commit_file(peer, "peer.md")
    git("push", "--quiet", "origin", "main", cwd=peer)
    commit_file(local, "local.md")
    git("fetch", "--quiet", "origin", cwd=local)
    assert DOCTOR.main(["--board", str(board_a), "--repo", str(local)]) == 1


def test_fleet_doctor_verb_runs_the_full_gate(tmp_path, capsys):
    synthesis = tmp_path / "synthesis"
    synthesis.mkdir()
    (synthesis / "git-hook-config.yaml").write_text(
        'config_version: 2\ncoordination_board: "~/.synthesis/board.md"\n',
        encoding="utf-8",
    )
    board = synthesis / "board.md"
    board.write_text(MODULE.template(), encoding="utf-8")
    shell = args(board, synthesis_root=synthesis)
    assert MODULE.command_fleet_doctor(shell) == 0
    out = capsys.readouterr().out
    assert "PASS fleet-paths" in out
    assert "PASS fleet-reachability" in out
    assert "PASS fleet-divergence-scan" in out

    remote_url = seed_repo(tmp_path / "origin.git")
    local = clone(remote_url, tmp_path / "local")
    peer = clone(remote_url, tmp_path / "peer")
    commit_file(peer, "peer.md")
    git("push", "--quiet", "origin", "main", cwd=peer)
    commit_file(local, "local.md")
    git("fetch", "--quiet", "origin", cwd=local)
    shell = args(
        board, synthesis_root=synthesis, artifacts_dir=None, repos=[str(local)],
        machine_id=None,
    )
    assert MODULE.command_fleet_doctor(shell) == 1
    assert "diverged" in capsys.readouterr().err


def test_doctor_preserves_missing_registered_worktree_evidence(tmp_path):
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    target = tmp_path / "worktree"
    git("worktree", "add", "-b", "fixture-vanished", str(target), cwd=local)
    old_head = git("rev-parse", "HEAD", cwd=target).strip()
    (target / ".git").unlink()
    result = DOCTOR.check_storage([local])
    assert not result.ok
    assert "missing linked metadata" in result.detail and old_head in result.detail
    assert "prune" in result.detail and "fixture-vanished" in result.detail
    assert "fixture-vanished" in git("branch", "--list", cwd=local)
    assert str(target) in git("worktree", "list", "--porcelain", cwd=local)



def test_doctor_reports_vanished_tracked_material_without_pruning(tmp_path, monkeypatch):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    target = tmp_path / "worktree"
    git("worktree", "add", "-b", "fixture-missing-source", str(target), cwd=local)
    names = git("ls-files", cwd=target).splitlines()
    assert names
    (target / names[0]).unlink()
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    result = DOCTOR.check_storage([local])
    assert not result.ok and "vanished tracked path" in result.detail
    assert "intentional deletion versus loss is UNKNOWN" in result.detail
    assert "fixture-missing-source" in git("branch", "--list", cwd=local)


def test_doctor_valid_durable_registration_positive(tmp_path, monkeypatch):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    target = tmp_path / "worktree"
    git("worktree", "add", "-b", "fixture-healthy", str(target), cwd=local)
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    before = git("worktree", "list", "--porcelain", cwd=local)
    result = DOCTOR.check_storage([local])
    assert result.ok, result.detail
    assert before == git("worktree", "list", "--porcelain", cwd=local)


def test_doctor_only_declared_venv_and_source_paths(tmp_path, monkeypatch):
    import fleet_paths
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = synthetic\n")
    assert DOCTOR.check_storage([], source_paths=[tmp_path], venvs=[venv]).ok
    (venv / "pyvenv.cfg").unlink()
    result = DOCTOR.check_storage([], source_paths=[tmp_path / "missing"], venvs=[venv])
    assert not result.ok and "venv metadata unavailable" in result.detail and "missing or unavailable" in result.detail


def test_doctor_refuses_input_that_git_would_resolve_to_enclosing_repository(tmp_path):
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    child = local / "unregistered"
    child.mkdir()
    result = DOCTOR.check_storage([child])
    assert not result.ok and "exact Git checkout root" in result.detail


def test_doctor_metadata_reads_do_not_execute_local_fsmonitor(tmp_path, monkeypatch):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    marker = tmp_path / "unexpected-execution"
    helper = tmp_path / "observer.sh"
    helper.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\n")
    helper.chmod(0o700)
    git("config", "core.fsmonitor", str(helper), cwd=local)
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    result = DOCTOR.check_storage([local])
    assert result.ok, result.detail
    assert not marker.exists()


@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize("damage", ["none", "missing", "corrupt", "symlink"])
def test_actual_worktree_index_custody(tmp_path, monkeypatch, linked, damage):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    target = local
    if linked:
        target = tmp_path / "linked"
        git("worktree", "add", "--detach", str(target), cwd=local)
    index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index", cwd=target))
    names = git("ls-files", cwd=target).splitlines()
    assert names and index.is_file()
    preserved = tmp_path / "retained-index"
    if damage != "none":
        index.rename(preserved)
        (target / names[0]).rename(tmp_path / "retained-head-file")
        if damage == "corrupt":
            index.write_bytes(b"broken index")
        if damage == "symlink":
            index.symlink_to(preserved)
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    refs = git("show-ref", cwd=local)
    result = DOCTOR.check_storage([target])
    assert result.ok is (damage == "none"), result.detail
    assert refs == git("show-ref", cwd=local)
    if damage == "missing":
        assert not index.exists() and "index" in result.detail and "UNKNOWN" in result.detail
    if damage == "corrupt":
        assert index.read_bytes() == b"broken index"
    if damage == "symlink":
        assert index.is_symlink() and "index" in result.detail


def test_changed_index_during_storage_observation_refuses(tmp_path, monkeypatch):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    index = local / ".git/index"
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    original = fleet_paths._storage_git
    changed = []
    def race(repository, arguments, *, timeout):
        result = original(repository, arguments, timeout=timeout)
        if arguments == ["ls-files", "--deleted", "-z"] and not changed:
            saved = tmp_path / "retained-before-index"
            index.rename(saved)
            index.write_bytes(saved.read_bytes())
            changed.append(True)
        return result
    monkeypatch.setattr(fleet_paths, "_storage_git", race)
    result = DOCTOR.check_storage([local])
    assert changed and not result.ok and "index" in result.detail, result.detail


@pytest.mark.parametrize("linked", [False, True])
def test_temporary_actual_common_git_is_not_healthy(tmp_path, monkeypatch, linked):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    target = local
    if linked:
        target = tmp_path / "linked"
        git("worktree", "add", "--detach", str(target), cwd=local)
    common = local / ".git"
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [common])
    assert fleet_paths.classify_storage(target)["status"] == "durable-candidate"
    before = git("worktree", "list", "--porcelain", cwd=local)
    result = DOCTOR.check_storage([target])
    assert not result.ok and "common Git" in result.detail and str(common) in result.detail
    assert before == git("worktree", "list", "--porcelain", cwd=local)


@pytest.mark.parametrize("version", [2, 3, 4])
@pytest.mark.parametrize("algorithm", ["sha1", "sha256"])
@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize("split", [False, True])
def test_doctor_actual_index_formats(tmp_path, monkeypatch, algorithm, linked, split, version):
    import fleet_paths
    local = tmp_path / "repo"
    local.mkdir()
    git("init", "--object-format=" + algorithm, cwd=local)
    git("config", "user.name", "Synthetic", cwd=local)
    git("config", "user.email", "synthetic@example.invalid", cwd=local)
    (local / "tracked").write_text("retained source")
    git("add", "tracked", cwd=local)
    git("commit", "-m", "Synthetic fixture", cwd=local)
    target = local
    if linked:
        target = tmp_path / "linked"
        git("worktree", "add", "--detach", str(target), cwd=local)
    if version == 3:
        git("update-index", "--skip-worktree", "tracked", cwd=target)
    git("update-index", "--index-version", str(version), cwd=target)
    actual_index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index", cwd=target))
    assert int.from_bytes(actual_index.read_bytes()[4:8], "big") == version
    if split:
        git("update-index", "--split-index", cwd=target)
        shared = Path(git("rev-parse", "--path-format=absolute", "--shared-index-path", cwd=target))
        assert shared.is_absolute() and shared.is_file()
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    result = DOCTOR.check_storage([target])
    assert result.ok, result.detail


@pytest.mark.parametrize("split", [False, True])
@pytest.mark.parametrize("damage", ["checksum", "zero", "missing", "symlink", "fifo"])
def test_index_integrity_refusals_preserve_metadata(tmp_path, monkeypatch, split, damage):
    import hashlib
    import os
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    index = local / ".git/index"
    if split:
        git("update-index", "--split-index", cwd=local)
        index = Path(git("rev-parse", "--path-format=absolute", "--shared-index-path", cwd=local))
    raw = index.read_bytes()
    if damage == "checksum":
        index.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    elif damage == "zero":
        index.write_bytes(raw[:-20] + b"\0" * 20)
    elif damage in {"missing", "symlink", "fifo"}:
        retained = tmp_path / "preserved-index"
        index.rename(retained)
        if damage == "symlink":
            index.symlink_to(retained)
        if damage == "fifo":
            os.mkfifo(index)
    before = None if damage in {"missing", "symlink", "fifo"} else hashlib.sha256(index.read_bytes()).hexdigest()
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    result = DOCTOR.check_storage([local])
    assert not result.ok and "index" in result.detail and "UNKNOWN" in result.detail, result.detail
    if before:
        assert hashlib.sha256(index.read_bytes()).hexdigest() == before
    if damage == "zero":
        assert "unavailable" in result.detail, result.detail
    if damage == "checksum":
        assert "checksum" in result.detail, result.detail
    if damage == "missing":
        assert not index.exists()


def test_index_checksum_bound_and_replacement_are_unknown(tmp_path, monkeypatch):
    import fleet_paths
    import time
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    index = local / ".git/index"
    monkeypatch.setattr(fleet_paths, "MAX_INDEX_BYTES", 12)
    with pytest.raises(ValueError, match="bound"):
        fleet_paths._index_witness(index, "sha1", time.monotonic() + 5)
    monkeypatch.setattr(fleet_paths, "MAX_INDEX_BYTES", 64 * 1024 * 1024)
    original = fleet_paths.os.read
    changed = []
    def replacing(fd, size):
        result = original(fd, size)
        if result and not changed:
            saved = tmp_path / "original-index"
            index.rename(saved)
            index.write_bytes(saved.read_bytes())
            changed.append(True)
        return result
    monkeypatch.setattr(fleet_paths.os, "read", replacing)
    with pytest.raises(ValueError, match="changed"):
        fleet_paths._index_witness(index, "sha1", time.monotonic() + 5)
    assert changed


def test_index_unsupported_format_deadline_and_directory_alias_refuse(tmp_path, monkeypatch):
    import fleet_paths
    import time
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    index = local / ".git/index"
    with pytest.raises(ValueError, match="object format"):
        fleet_paths._index_witness(index, "unknown", time.monotonic() + 5)
    with pytest.raises(ValueError, match="deadline"):
        fleet_paths._index_witness(index, "sha1", time.monotonic() - 1)
    alias = tmp_path / "alias"
    alias.symlink_to(index.parent, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        fleet_paths._index_witness(alias / "index", "sha1", time.monotonic() + 5)


def test_split_index_dependency_replacement_refuses(tmp_path, monkeypatch):
    import fleet_paths
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    git("update-index", "--split-index", cwd=local)
    shared = Path(git("rev-parse", "--path-format=absolute", "--shared-index-path", cwd=local))
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    original = fleet_paths._storage_git
    changed = []
    def query(repository, arguments, *, timeout):
        result = original(repository, arguments, timeout=timeout)
        if arguments == ["ls-files", "--deleted", "-z"] and not changed:
            saved = tmp_path / "shared-before"
            shared.rename(saved)
            shared.write_bytes(saved.read_bytes())
            changed.append(True)
        return result
    monkeypatch.setattr(fleet_paths, "_storage_git", query)
    result = DOCTOR.check_storage([local])
    assert changed and not result.ok and "changed" in result.detail, result.detail


@pytest.mark.parametrize("width", [20, 32])
def test_split_locator_exact_extension_and_entry_bounds(width):
    import fleet_paths
    header = b"DIRC" + (2).to_bytes(4, "big") + bytes(4)
    oid = b"x" * width
    extension = b"link" + width.to_bytes(4, "big") + oid
    assert fleet_paths._index_link(header, width) is None
    assert fleet_paths._index_link(header + b"TEST" + (4).to_bytes(4, "big") + b"link" + extension, width) == oid.hex()
    for body in (
        header + b"link", header + b"link" + (width + 1).to_bytes(4, "big") + oid,
        header + extension + extension, header + b"link" + width.to_bytes(4, "big") + bytes(width),
        b"DIRC" + (2).to_bytes(4, "big") + (1).to_bytes(4, "big"),
        b"DIRC" + (2).to_bytes(4, "big") + (fleet_paths.MAX_DELETED_PATHS + 1).to_bytes(4, "big"),
        b"DIRC" + (4).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes(40 + width + 2) + b"\x80" * 10,
        b"DIRC" + (3).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes(40 + width + 2) + b"no-terminator",
    ):
        with pytest.raises(ValueError, match="UNKNOWN"):
            fleet_paths._index_link(body, width)


def test_split_unsafe_dependency_refuses_before_git_reads_it(tmp_path, monkeypatch):
    import fleet_paths
    import os
    remote = seed_repo(tmp_path / "origin.git")
    local = clone(remote, tmp_path / "local")
    git("update-index", "--split-index", cwd=local)
    shared = Path(git("rev-parse", "--path-format=absolute", "--shared-index-path", cwd=local))
    shared.rename(tmp_path / "retained-shared")
    os.mkfifo(shared)
    original = fleet_paths._storage_git
    called = []
    def query(repository, arguments, *, timeout):
        assert "--shared-index-path" not in arguments and "ls-files" not in arguments
        called.append(arguments)
        return original(repository, arguments, timeout=timeout)
    monkeypatch.setattr(fleet_paths, "_storage_git", query)
    monkeypatch.setattr(fleet_paths, "temporary_roots", lambda: [])
    result = DOCTOR.check_storage([local])
    assert called and not result.ok and "ordinary file" in result.detail

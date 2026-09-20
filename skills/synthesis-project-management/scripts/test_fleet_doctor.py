"""Fleet doctor: reachability, freshness, coherence, seals, divergence.

Each check fails closed; unconfigured inputs skip loudly. The
divergence-catch test proves a checkout that split from its upstream fails
the gate naming the repo, then passes again once reunited.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as MODULE
import fleet_doctor as DOCTOR
import fleet_handoff as HANDOFF
import fleet_identity as FI

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
        "parked-coherence", "artifact-sealed", "divergence-scan",
    ]
    assert all(check.ok for check in checks), DOCTOR.format_report(checks)

    assert DOCTOR.main(["--board", str(board_a)]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS fleet-") == 6

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

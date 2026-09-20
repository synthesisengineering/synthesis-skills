"""Fleet handoff: REMOTE_READY source gate, sealed offers, harness-free resume.

Covers FLEET-AC-09 (a BLOCKED source refuses before any board offer),
FLEET-AC-10 (a dirty destination refuses with the file list while the
source row stays parked), and FLEET-AC-11 (the full sealed-handoff loop,
identical for the claude-code, codex, and muse destination lanes).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as MODULE
import fleet_handoff as HANDOFF
import fleet_identity as FI

T0 = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    for name in (
        "SYNTHESIS_CLIENT_SESSION_REF",
        "SYNTHESIS_COORDINATION_SESSION",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_PID",
        "CLAUDECODE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(tmp_path / "fleet"))


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim_request(board, *, session_id, project, workspace, area, machine):
    return args(
        board,
        id=session_id,
        agent=f"agent-{session_id}",
        machine=machine,
        project=project,
        mode="autonomous",
        goal=f"goal-{session_id}",
        workspace=[workspace],
        area=[area],
        context_role="owner",
        replace=False,
        client_ref=None,
    )


def enroll_pair(tmp_path):
    fleet_a = tmp_path / "fleet-a"
    fleet_b = tmp_path / "fleet-b"
    id_a = FI.mint_machine_id(fleet_a)
    FI.enroll_self(label="mac-a", role="primary", directory=fleet_a)
    id_b = FI.mint_machine_id(fleet_b)
    shutil.copyfile(FI.registry_path(fleet_a), FI.registry_path(fleet_b))
    FI.enroll_self(label="mac-b", role="secondary", directory=fleet_b)
    return (fleet_a, id_a), (fleet_b, id_b)


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


def clone(remote_url: str, dest: Path):
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "clone", "--quiet",
         remote_url, str(dest)],
        check=True,
        capture_output=True,
    )


def seed_origin(path: Path) -> tuple[str, str]:
    """A bare origin with one commit; returns (remote_url, sha)."""
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
    sha = git("rev-parse", "HEAD", cwd=work)
    git("branch", "--set-upstream-to=origin/main", cwd=work)
    return str(path), sha


def test_source_gate_truth_table():
    clean = HANDOFF.WorksetStatus(
        repo="kb", path="/tmp/kb", remote_url="https://example.com/kb.git",
        branch="main", sha="a" * 40, upstream="origin/main",
    )
    readiness, alerts = HANDOFF.source_readiness([clean], [])
    assert (readiness, alerts) == (HANDOFF.READINESS_CLEAN, [])
    readiness, alerts = HANDOFF.source_readiness([clean], ["pending/m-1.json"])
    assert (readiness, alerts) == (HANDOFF.READINESS_REMOTE_READY, [])

    dirty = HANDOFF.WorksetStatus(
        repo="kb", path="/tmp/kb", remote_url="https://example.com/kb.git",
        branch="main", sha="a" * 40, dirty_files=["notes.md"],
        upstream="origin/main",
    )
    readiness, alerts = HANDOFF.source_readiness([dirty], ["pending/m-1.json"])
    assert readiness == HANDOFF.READINESS_BLOCKED
    assert any("notes.md" in alert for alert in alerts)

    unpushed = HANDOFF.WorksetStatus(
        repo="kb", path="/tmp/kb", remote_url="https://example.com/kb.git",
        branch="main", sha="a" * 40, ahead=2, upstream="origin/main",
    )
    readiness, alerts = HANDOFF.source_readiness([unpushed], [])
    assert readiness == HANDOFF.READINESS_BLOCKED
    assert any("unpushed" in alert for alert in alerts)

    untracked = HANDOFF.WorksetStatus(
        repo="kb", path="/tmp/kb", remote_url="https://example.com/kb.git",
        branch="main", sha="a" * 40,
    )
    readiness, alerts = HANDOFF.source_readiness([untracked], [])
    assert readiness == HANDOFF.READINESS_BLOCKED
    assert any("no upstream" in alert for alert in alerts)


def test_blocked_source_refuses_before_any_board_offer_fleet_ac_09(
    tmp_path, monkeypatch
):
    (fleet_a, _), (_, id_b) = enroll_pair(tmp_path)
    board = tmp_path / "board.md"
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-ac09")
    request = claim_request(
        board, session_id="A", project="drill", machine="mac-a",
        workspace="/tmp/wt-ac09 @ feature/x", area="/tmp/drill-repo/**",
    )
    assert MODULE.command_claim(request) == 0
    before = board.read_text(encoding="utf-8")

    blocked = HANDOFF.WorksetStatus(
        repo="drill-repo", path="/tmp/drill-repo",
        remote_url="https://example.com/drill.git", branch="feature/x",
        sha="b" * 40, dirty_files=["uncommitted.md"],
    )
    with pytest.raises(HANDOFF.HandoffBlocked) as caught:
        HANDOFF.create_handoff_offer(
            before, session_selector="A", dest_machine_id=id_b,
            dest_label="mac-b", source_machine_id="mac-a-id",
            source_label="mac-a", statuses=[blocked],
            manifests=["pending/m-1.json"], ticket="handoff-ac09", now=T0,
        )
    assert any("uncommitted.md" in alert for alert in caught.value.alerts)
    # Refused before any board mutation: no offer posted, row still active.
    assert HANDOFF.find_offers(before) == []
    assert MODULE.rows(before)[0].status == "active"


def test_dirty_destination_refuses_and_source_stays_parked_fleet_ac_10(
    tmp_path, monkeypatch
):
    (fleet_a, id_a), (fleet_b, id_b) = enroll_pair(tmp_path)
    remote_url, sha = seed_origin(tmp_path / "origin.git")
    board = tmp_path / "board.md"
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-ac10")
    request = claim_request(
        board, session_id="A", project="drill", machine="mac-a",
        workspace="/tmp/wt-ac10 @ main", area="/tmp/drill-repo/**",
    )
    assert MODULE.command_claim(request) == 0

    ready = HANDOFF.WorksetStatus(
        repo="drill-repo", path="/tmp/drill-repo", remote_url=remote_url,
        branch="main", sha=sha, upstream="origin/main",
    )
    content, sealed = HANDOFF.create_handoff_offer(
        board.read_text(encoding="utf-8"), session_selector="A",
        dest_machine_id=id_b, dest_label="mac-b", source_machine_id=id_a,
        source_label="mac-a", statuses=[ready],
        manifests=["pending/m-1.json"], ticket="handoff-ac10", now=T0,
    )
    board.write_text(content, encoding="utf-8")
    assert MODULE.rows(content)[0].status == "parked"

    dest_clone = tmp_path / "mac-b-checkout"
    clone(remote_url, dest_clone)
    (dest_clone / "local-draft.md").write_text("uncommitted\n", encoding="utf-8")
    alerts = HANDOFF.verify_destination(
        sealed["offer"], {remote_url: dest_clone}
    )
    assert len(alerts) == 1
    assert "local-draft.md" in alerts[0]

    # The refusal recovers: the source row stays parked, never released.
    parked = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert parked.status == "parked"
    assert parked.claims == ["/tmp/drill-repo/**"]


@pytest.mark.parametrize("client", ["claude-code", "codex", "muse"])
def test_sealed_handoff_loop_is_harness_neutral_fleet_ac_11(
    tmp_path, monkeypatch, client
):
    (fleet_a, id_a), (fleet_b, id_b) = enroll_pair(tmp_path)
    remote_url, sha = seed_origin(tmp_path / "origin.git")
    board = tmp_path / "board.md"

    # Source half on Mac A: gate, offer, park, seal.
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-ac11-src")
    source_area = "/tmp/drill-repo/**"
    request = claim_request(
        board, session_id="SRC", project="handoff-drill", machine="mac-a",
        workspace="/tmp/wt-ac11-src @ main", area=source_area,
    )
    assert MODULE.command_claim(request) == 0
    ready = HANDOFF.WorksetStatus(
        repo="drill-repo", path="/tmp/drill-repo", remote_url=remote_url,
        branch="main", sha=sha, upstream="origin/main",
    )
    content, sealed = HANDOFF.create_handoff_offer(
        board.read_text(encoding="utf-8"), session_selector="SRC",
        dest_machine_id=id_b, dest_label="mac-b", source_machine_id=id_a,
        source_label="mac-a", statuses=[ready],
        manifests=["pending/m-1.json"], ticket=f"handoff-ac11-{client}",
        now=T0,
    )
    board.write_text(content, encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    artifact_path = HANDOFF.write_sealed_artifact(artifacts, sealed)
    assert HANDOFF.read_sealed_artifact(artifact_path)["ticket"] == sealed["ticket"]

    # Destination half on Mac B: pull, verify, claim, accept.
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_b))
    if client == "codex":
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-ac11-dst")
    elif client == "muse":
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "muse:owner-ac11-dst")
    else:
        monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ac11-dst-session")
        monkeypatch.setenv("CLAUDECODE", "1")
    dest_clone = tmp_path / f"mac-b-checkout-{client}"
    clone(remote_url, dest_clone)
    offers = HANDOFF.find_offers(board.read_text(encoding="utf-8"), to_machine=id_b)
    assert [offer["ticket"] for offer in offers] == [sealed["ticket"]]
    assert HANDOFF.verify_destination(sealed["offer"], {remote_url: dest_clone}) == []

    dest_request = claim_request(
        board, session_id="DST", project="handoff-drill", machine="mac-b",
        workspace=f"{dest_clone} @ main", area=source_area,
    )
    assert MODULE.command_claim(dest_request) == 0
    content = board.read_text(encoding="utf-8")
    dest_row = MODULE.find_session(MODULE.rows(content), "DST")
    assert MODULE.overlaps_parked_successors(
        content, MODULE.find_session(MODULE.rows(content), "SRC").compact_id
    )
    from peer_addressing import read_seat

    seat = read_seat(board, dest_row.session_uuid)
    assert seat is not None and seat.client == client

    content = HANDOFF.accept_handoff(
        content, ticket=sealed["ticket"], dest_machine_id=id_b,
        dest_compact=dest_row.compact_id, now=T0 + timedelta(minutes=5),
    )
    board.write_text(content, encoding="utf-8")

    # Both board messages are addressed to the correct machine-ids.
    offers = HANDOFF.find_offers(content)
    accepts = HANDOFF.find_accepts(content, ticket=sealed["ticket"])
    assert offers[0]["from_machine"] == id_a
    assert offers[0]["to_machine"] == id_b
    assert len(accepts) == 1
    assert accepts[0]["from_machine"] == id_b
    assert accepts[0]["to_machine"] == id_a

    # Resume contract: real git truth feeds the checklist, receipt closes it.
    head = git("rev-parse", "HEAD", cwd=dest_clone)
    clean = git("status", "--porcelain", cwd=dest_clone) == ""
    report = HANDOFF.resume_checklist(
        content, ticket=sealed["ticket"], dest_compact=dest_row.compact_id,
        repo_states=[{"repo": "drill-repo", "clean": clean, "head_ok": head == sha}],
    )
    assert report["ok"], report["checks"]
    receipt = HANDOFF.write_resume_receipt(
        tmp_path / "receipts", report, accepted_shas=[sha]
    )
    assert receipt.is_file()
    stored = json.loads(receipt.read_text(encoding="utf-8"))
    assert stored["ticket"] == sealed["ticket"]
    assert stored["accepted_shas"] == [sha]
    assert set(stored["checks"]) == {
        "board-truth", "code-truth", "context-truth", "claim-truth", "receipt",
    }


def test_handoff_path_has_no_harness_conditioned_branches():
    body = (SCRIPTS_DIR / "fleet_handoff.py").read_text(encoding="utf-8")
    for marker in ("claude-code", "CLIENT_CLAUDE", "CLIENT_CODEX", "CLIENT_MUSE"):
        assert marker not in body
    assert "codex:" not in body and "muse:" not in body


def test_seal_detects_tamper_and_refuses_overwrite(tmp_path):
    offer = {
        "ticket": "handoff-tamper", "from_machine": "a", "from_label": "A",
        "to_machine": "b", "to_label": "B", "session_compact": "s-x",
        "readiness": HANDOFF.READINESS_REMOTE_READY, "worksets": [],
        "manifests": [], "offered_at": T0.isoformat(),
    }
    sealed = HANDOFF.seal_offer(offer, sealed_at=T0.isoformat())
    assert HANDOFF.verify_sealed_artifact(sealed)["ticket"] == "handoff-tamper"

    tampered = json.loads(json.dumps(sealed))
    tampered["offer"]["readiness"] = HANDOFF.READINESS_CLEAN
    with pytest.raises(HANDOFF.HandoffSealError, match="failed verification"):
        HANDOFF.verify_sealed_artifact(tampered)

    artifacts = tmp_path / "artifacts"
    HANDOFF.write_sealed_artifact(artifacts, sealed)
    assert HANDOFF.write_sealed_artifact(artifacts, sealed).is_file()
    with pytest.raises(HANDOFF.HandoffSealError, match="different offer"):
        HANDOFF.write_sealed_artifact(artifacts, HANDOFF.seal_offer(
            {**offer, "manifests": ["pending/other.json"]},
            sealed_at=T0.isoformat(),
        ))
    with pytest.raises(HANDOFF.HandoffSealError, match="not found"):
        HANDOFF.read_sealed_artifact(artifacts / "handoff-missing.sealed.json")


def test_accept_refuses_unknown_wrong_machine_and_double_accept(tmp_path):
    content = MODULE.template()
    with pytest.raises(HANDOFF.HandoffError, match="not found"):
        HANDOFF.accept_handoff(
            content, ticket="handoff-nope", dest_machine_id="b",
            dest_compact="s-x",
        )
    offer = {
        "ticket": "handoff-once", "from_machine": "a", "from_label": "A",
        "to_machine": "b", "to_label": "B", "session_compact": "s-x",
        "readiness": HANDOFF.READINESS_CLEAN, "worksets": [], "manifests": [],
        "offered_at": T0.isoformat(),
    }
    sealed = HANDOFF.seal_offer(offer, sealed_at=T0.isoformat())
    content = MODULE.append_bus_block(
        content, HANDOFF.offer_block(offer, sealed["seal"], stamp=T0.isoformat())
    )
    with pytest.raises(HANDOFF.HandoffError, match="addressed to b, not z"):
        HANDOFF.accept_handoff(
            content, ticket="handoff-once", dest_machine_id="z",
            dest_compact="s-y",
        )
    content = HANDOFF.accept_handoff(
        content, ticket="handoff-once", dest_machine_id="b",
        dest_compact="s-y", now=T0,
    )
    with pytest.raises(HANDOFF.HandoffError, match="already accepted"):
        HANDOFF.accept_handoff(
            content, ticket="handoff-once", dest_machine_id="b",
            dest_compact="s-y", now=T0,
        )


def test_resume_receipt_refuses_a_failing_checklist(tmp_path):
    report = {
        "ticket": "handoff-fail",
        "destination": "s-y",
        "ok": False,
        "checks": {
            "board-truth": {"ok": True, "detail": "fine"},
            "code-truth": {"ok": False, "detail": "dirty"},
            "context-truth": {"ok": True, "detail": "fine"},
            "claim-truth": {"ok": True, "detail": "fine"},
            "receipt": {"ok": True, "detail": "pending"},
        },
    }
    with pytest.raises(HANDOFF.ResumeIncomplete, match="code-truth"):
        HANDOFF.write_resume_receipt(tmp_path, report, accepted_shas=[])
    assert list(tmp_path.glob("*.resume.json")) == []


def test_verify_command_smoke(tmp_path, capsys):
    offer = {
        "ticket": "handoff-cli", "from_machine": "a", "from_label": "A",
        "to_machine": "b", "to_label": "B", "session_compact": "s-x",
        "readiness": HANDOFF.READINESS_CLEAN, "worksets": [], "manifests": [],
        "offered_at": T0.isoformat(),
    }
    path = HANDOFF.write_sealed_artifact(
        tmp_path, HANDOFF.seal_offer(offer, sealed_at=T0.isoformat())
    )
    assert HANDOFF.main(["verify", "--artifact", str(path)]) == 0
    assert "verifies" in capsys.readouterr().out
    assert HANDOFF.main(["verify", "--artifact", str(tmp_path / "nope.json")]) == 1

"""Fleet parked state: the bag-laptop drill and the 7-day expiry rule.

Covers FLEET-AC-07 (challenge, grace, park, overlaps-parked claim, resume)
and FLEET-AC-08 (parked-expiry administrative release). All time travel uses
injectable clocks on the pure transition core; no wall-clock sleeps.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as MODULE
import fleet_identity as FI

# Anchored to import time, not a fixed date: downgraded() keys heartbeat age
# off the wall clock (2-day threshold), so a fixed T0 silently flips
# blocking-overlap assertions to advisory once the suite ages past it.
T0 = datetime.now(timezone.utc).replace(microsecond=0)


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


def make_row(*, machine: str, label: str, heartbeat: str, claims: list[str],
             status: str = "active", ref: str = "codex:owner-b",
             project: str = "drill", workspace: str = "/tmp/drill-wt @ feature/drill"):
    identity = MODULE.new_identity()
    return MODULE.Session(
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        speakable_id=identity.speakable_id,
        legacy_id="",
        agent="agent-b",
        machine=machine,
        machine_label=label,
        project=project,
        started=heartbeat,
        heartbeat=heartbeat,
        mode="autonomous",
        workspaces=[workspace],
        goal="drill",
        claims=list(claims),
        context_role="owner",
        status=status,
        client_ref=ref,
    )


def board_with(rows: list) -> str:
    return MODULE.replace_table(MODULE.template(), rows)


def test_bag_laptop_drill_fleet_ac_07(tmp_path, monkeypatch, capsys):
    mac_a = tmp_path / "mac-a"
    mac_b = tmp_path / "mac-b"
    id_a = FI.mint_machine_id(mac_a)
    id_b = FI.mint_machine_id(mac_b)
    assert id_a != id_b

    # Mac B bags its laptop mid-session with an active claim.
    row_b = make_row(
        machine=id_b, label="mac-b", heartbeat=T0.isoformat(),
        claims=["/tmp/drill-repo/**"],
    )
    content = board_with([row_b])
    assert MODULE.derived_fleet_status(row_b, T0 + timedelta(minutes=10)) == "active"
    stale_at = T0 + timedelta(minutes=31)
    assert MODULE.derived_fleet_status(row_b, stale_at) == "stale"

    # Mac A challenges; parking inside the grace interval refuses.
    content = MODULE.post_challenge(
        content, row_b.compact_id, challenger="mac-a", now=stale_at
    )
    challenges = MODULE.fleet_challenges(content, row_b.compact_id)
    assert len(challenges) == 1
    assert challenges[0]["challenger"] == "mac-a"
    with pytest.raises(MODULE.FleetParkError, match="grace interval"):
        MODULE.park_session(
            content, row_b.compact_id, basis="challenge", actor="mac-a",
            now=stale_at + timedelta(minutes=4),
        )

    # Past grace with no heartbeat, Mac A parks the row.
    parked_at = stale_at + timedelta(minutes=10)
    content = MODULE.park_session(
        content, row_b.compact_id, basis="challenge", actor="mac-a", now=parked_at
    )
    parked_row = MODULE.rows(content)[0]
    assert parked_row.status == "parked"
    assert parked_row.claims == ["/tmp/drill-repo/**"]
    assert MODULE.parked_since(content, parked_row) == parked_at

    # Mac A claims the overlapping scope: warning with provenance, not error.
    board = tmp_path / "board.md"
    board.write_text(content, encoding="utf-8")
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(mac_a))
    request = args(
        board, id=None, agent="agent-a", machine="mac-a", project="drill",
        mode="autonomous", goal="takeover", workspace=["/tmp/drill-wt-a @ feature/a"],
        area=["/tmp/drill-repo/**"], context_role="owner", replace=False,
        client_ref=None,
    )
    assert MODULE.command_claim(request) == 0
    out = capsys.readouterr().out
    assert "overlaps-parked" in out
    content = board.read_text(encoding="utf-8")
    sessions = {row.compact_id: row for row in MODULE.rows(content)}
    row_a = next(row for row in sessions.values() if row.compact_id != row_b.compact_id)
    assert row_a.status == "active"
    assert row_a.machine == id_a
    successors = MODULE.overlaps_parked_successors(content, row_b.compact_id)
    assert [item["new"] for item in successors] == [row_a.compact_id]

    # Sanity: had B's row stayed active, the same claim would refuse.
    active_b = MODULE.Session(**{**row_b.__dict__, "status": "active"})
    problems = MODULE.validate_sessions([active_b, row_a])
    assert any("overlaps" in problem for problem in problems)

    # Mac B returns and heartbeats: active with claims intact, successor named.
    resumed_at = parked_at + timedelta(minutes=30)
    content = MODULE.resume_parked(
        content, row_b.compact_id, now=resumed_at, local_machine_id=id_b
    )
    resumed = next(
        row for row in MODULE.rows(content) if row.compact_id == row_b.compact_id
    )
    assert resumed.status == "active"
    assert resumed.claims == ["/tmp/drill-repo/**"]
    assert resumed.heartbeat == resumed_at.isoformat(timespec="seconds")
    assert f"fleet-resumed target={row_b.compact_id}" in content
    assert row_a.compact_id in content


def test_challenge_refuses_fresh_and_terminal_rows():
    row = make_row(
        machine="m", label="m", heartbeat=T0.isoformat(), claims=["repo/**"]
    )
    content = board_with([row])
    with pytest.raises(MODULE.FleetParkError, match="fresh"):
        MODULE.post_challenge(
            content, row.compact_id, challenger="x", now=T0 + timedelta(minutes=5)
        )
    with pytest.raises(MODULE.FleetParkError, match="requires a challenger"):
        MODULE.post_challenge(
            content, row.compact_id, challenger="  ",
            now=T0 + timedelta(minutes=60),
        )
    released = MODULE.Session(**{**row.__dict__, "status": "released"})
    with pytest.raises(MODULE.FleetParkError, match="not active"):
        MODULE.post_challenge(
            board_with([released]), row.compact_id, challenger="x",
            now=T0 + timedelta(minutes=60),
        )
    with pytest.raises(MODULE.FleetParkError, match="not found"):
        MODULE.post_challenge(content, "s-nope-nope-nope", challenger="x", now=T0)


def test_park_operator_basis_needs_no_challenge():
    row = make_row(
        machine="m", label="m", heartbeat=T0.isoformat(), claims=["repo/**"]
    )
    content = board_with([row])
    parked_at = T0 + timedelta(minutes=60)
    content = MODULE.park_session(
        content, row.compact_id, basis="operator", actor="rajiv", now=parked_at
    )
    assert MODULE.rows(content)[0].status == "parked"
    assert "basis=operator actor=rajiv" in content
    assert MODULE.parked_since(content, MODULE.rows(content)[0]) == parked_at


def test_park_refuses_bad_basis_and_non_active_rows():
    row = make_row(
        machine="m", label="m", heartbeat=T0.isoformat(), claims=["repo/**"]
    )
    content = board_with([row])
    with pytest.raises(MODULE.FleetParkError, match="unknown park basis"):
        MODULE.park_session(content, row.compact_id, basis="vibes", actor="x")
    with pytest.raises(MODULE.FleetParkError, match="requires an actor"):
        MODULE.park_session(content, row.compact_id, basis="operator", actor=" ")
    parked = MODULE.Session(**{**row.__dict__, "status": "parked"})
    with pytest.raises(MODULE.FleetParkError, match="not active"):
        MODULE.park_session(
            board_with([parked]), row.compact_id, basis="operator", actor="x"
        )


def test_park_challenge_basis_requires_stale_row_even_after_mature_challenge():
    row = make_row(
        machine="m", label="m", heartbeat=T0.isoformat(), claims=["repo/**"]
    )
    content = board_with([row])
    content = MODULE.post_challenge(
        content, row.compact_id, challenger="mac-a",
        now=T0 + timedelta(minutes=31),
    )
    fresh = MODULE.Session(
        **{**row.__dict__, "heartbeat": (T0 + timedelta(minutes=32)).isoformat()}
    )
    # Heartbeat landed after the challenge: the row is live again.
    content = MODULE.replace_table(
        content,
        [fresh if s.compact_id == row.compact_id else s
         for s in MODULE.rows(content)],
    )
    with pytest.raises(MODULE.FleetParkError, match="fresh"):
        MODULE.park_session(
            content, row.compact_id, basis="challenge", actor="mac-a",
            now=T0 + timedelta(minutes=60),
        )


def test_resume_refuses_wrong_machine_and_non_parked():
    row = make_row(
        machine="id-b", label="mac-b", heartbeat=T0.isoformat(),
        claims=["repo/**"], status="parked",
    )
    content = board_with([row])
    with pytest.raises(MODULE.FleetParkError, match="not this Mac"):
        MODULE.resume_parked(content, row.compact_id, local_machine_id="id-a")
    active = MODULE.Session(**{**row.__dict__, "status": "active"})
    with pytest.raises(MODULE.FleetParkError, match="not parked"):
        MODULE.resume_parked(
            board_with([active]), row.compact_id, local_machine_id="id-b"
        )


def test_heartbeat_command_resumes_parked_row_on_own_machine(tmp_path, monkeypatch, capsys):
    fleet_b = tmp_path / "fleet-b"
    id_b = FI.mint_machine_id(fleet_b)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_b))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-b")
    row = make_row(
        machine=id_b, label="mac-b", heartbeat=T0.isoformat(),
        claims=["repo/**"], status="parked",
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([row]), encoding="utf-8")
    assert MODULE.command_heartbeat(args(board, id=row.compact_id)) == 0
    assert "resumed to active" in capsys.readouterr().out
    assert MODULE.rows(board.read_text(encoding="utf-8"))[0].status == "active"


def test_heartbeat_command_refuses_parked_row_from_other_machine(tmp_path, monkeypatch, capsys):
    fleet_a = tmp_path / "fleet-a"
    FI.mint_machine_id(fleet_a)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-b")
    row = make_row(
        machine="id-b", label="mac-b", heartbeat=T0.isoformat(),
        claims=["repo/**"], status="parked",
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([row]), encoding="utf-8")
    assert MODULE.command_heartbeat(args(board, id=row.compact_id)) == 10
    assert "not this Mac" in capsys.readouterr().err


def test_claim_by_owner_resumes_parked_own_row(tmp_path, monkeypatch, capsys):
    fleet_b = tmp_path / "fleet-b"
    id_b = FI.mint_machine_id(fleet_b)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_b))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-b")
    row = make_row(
        machine=id_b, label="mac-b", heartbeat=T0.isoformat(),
        claims=["repo/**"], status="parked",
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([row]), encoding="utf-8")
    request = args(
        board, id=row.compact_id, agent="agent-b", machine="mac-b",
        project="drill", mode="autonomous", goal="resume",
        workspace=["/tmp/drill-wt @ feature/drill"], area=["repo/**"],
        context_role="owner", replace=False, client_ref=None,
    )
    assert MODULE.command_claim(request) == 0
    assert "resumed parked row" in capsys.readouterr().out
    assert MODULE.rows(board.read_text(encoding="utf-8"))[0].status == "active"


def _parked_board(tmp_path: Path, *, parked_days_ago: float) -> tuple[Path, object]:
    row = make_row(
        machine="id-b", label="mac-b",
        heartbeat=(datetime.now(timezone.utc) - timedelta(days=parked_days_ago + 1)).isoformat(),
        claims=["repo/**"],
    )
    content = board_with([row])
    content = MODULE.park_session(
        content, row.compact_id, basis="operator", actor="op",
        now=datetime.now(timezone.utc) - timedelta(days=parked_days_ago),
    )
    board = tmp_path / "board.md"
    board.write_text(content, encoding="utf-8")
    return board, MODULE.rows(content)[0]


def test_expired_parked_row_releases_via_administrative_parked_expiry(
    tmp_path, monkeypatch, capsys
):
    """FLEET-AC-08: past the 7-day hold, parked-expiry releases."""
    board, row = _parked_board(tmp_path, parked_days_ago=8)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:admin-1")
    request = args(
        board, id=row.compact_id, administrative=True,
        reason="parked-expiry: owner gone", active_project_file=None,
    )
    assert MODULE.command_release(request) == 0
    text = board.read_text(encoding="utf-8")
    assert MODULE.rows(text)[0].status == "released"
    assert "parked-expiry" in text
    assert row.heartbeat in text
    assert "mac-b" in text


def test_young_parked_row_refuses_non_owner_release_with_hold_time(
    tmp_path, monkeypatch, capsys
):
    """FLEET-AC-08: inside the hold, non-owners wait, with a named duration."""
    board, row = _parked_board(tmp_path, parked_days_ago=0.5)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:admin-1")
    request = args(
        board, id=row.compact_id, administrative=True,
        reason="parked-expiry: impatient", active_project_file=None,
    )
    assert MODULE.command_release(request) == 10
    err = capsys.readouterr().err
    assert "7-day hold remain" in err
    assert "6d" in err


def test_expired_parked_row_requires_administrative_and_expiry_reason(
    tmp_path, monkeypatch, capsys
):
    board, row = _parked_board(tmp_path, parked_days_ago=8)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:admin-1")
    plain = args(
        board, id=row.compact_id, administrative=False, reason="",
        active_project_file=None,
    )
    assert MODULE.command_release(plain) == 10
    assert "cross-session release requires --administrative" in capsys.readouterr().err
    wrong_reason = args(
        board, id=row.compact_id, administrative=True, reason="cleanup",
        active_project_file=None,
    )
    assert MODULE.command_release(wrong_reason) == 10
    assert "parked-expiry" in capsys.readouterr().err


def test_unrecorded_parked_time_fails_closed_for_non_owners(tmp_path, monkeypatch, capsys):
    row = make_row(
        machine="id-b", label="mac-b", heartbeat=T0.isoformat(),
        claims=["repo/**"], status="parked",
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([row]), encoding="utf-8")
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:admin-1")
    request = args(
        board, id=row.compact_id, administrative=True,
        reason="parked-expiry: no record", active_project_file=None,
    )
    assert MODULE.command_release(request) == 10
    assert "unrecorded" in capsys.readouterr().err


def test_owner_releases_own_young_parked_row(tmp_path, monkeypatch):
    board, row = _parked_board(tmp_path, parked_days_ago=1)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-b")
    request = args(
        board, id=row.compact_id, administrative=False, reason="",
        active_project_file=None,
    )
    assert MODULE.command_release(request) == 0
    assert MODULE.rows(board.read_text(encoding="utf-8"))[0].status == "released"


def test_park_command_pid_gone_is_same_machine_only(tmp_path, monkeypatch, capsys):
    fleet_a = tmp_path / "fleet-a"
    id_a = FI.mint_machine_id(fleet_a)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    foreign = make_row(
        machine="id-b", label="mac-b", heartbeat=T0.isoformat(), claims=["repo/**"]
    )
    own = make_row(
        machine=id_a, label="mac-a", heartbeat=T0.isoformat(), claims=["repo2/**"]
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([foreign, own]), encoding="utf-8")
    refused = args(board, id=foreign.compact_id, basis="pid-gone", actor="mac-a")
    assert MODULE.command_park(refused) == 10
    assert "own machine" in capsys.readouterr().err
    # Same machine, but no seat record: no death evidence, so pid-gone refuses.
    unproven = args(board, id=own.compact_id, basis="pid-gone", actor="mac-a")
    assert MODULE.command_park(unproven) == 10
    assert "no death evidence" in capsys.readouterr().err
    _seat_with_dead_pid(board, own, id_a)
    allowed = args(board, id=own.compact_id, basis="pid-gone", actor="mac-a")
    assert MODULE.command_park(allowed) == 0
    statuses = {row.compact_id: row.status for row in MODULE.rows(board.read_text(encoding="utf-8"))}
    assert statuses == {foreign.compact_id: "active", own.compact_id: "parked"}
    assert "Evidence: recorded process" in board.read_text(encoding="utf-8")


def _seat_with_dead_pid(board: Path, row, machine_id: str) -> None:
    import os
    import subprocess
    import peer_addressing as PA
    child = subprocess.Popen(["true"])
    child.wait()
    PA.write_seat(
        board, session_uuid=row.session_uuid, compact_id=row.compact_id, machine=machine_id,
        machine_label="mac-a",
        identity=PA.SelfIdentity(client="codex", harness_session_id="native-dead"),
    )
    path = PA.seat_path(board, row.session_uuid)
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pid"] = child.pid
    path.write_text(json.dumps(data), encoding="utf-8")


def test_park_pid_gone_refuses_a_live_process(tmp_path, monkeypatch, capsys):
    import json
    import os
    import peer_addressing as PA
    fleet_a = tmp_path / "fleet-a"
    id_a = FI.mint_machine_id(fleet_a)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    own = make_row(machine=id_a, label="mac-a", heartbeat=T0.isoformat(), claims=["repo2/**"])
    board = tmp_path / "board.md"
    board.write_text(board_with([own]), encoding="utf-8")
    PA.write_seat(board, session_uuid=own.session_uuid, compact_id=own.compact_id, machine=id_a,
                  identity=PA.SelfIdentity(client="codex", harness_session_id="native-live"))
    path = PA.seat_path(board, own.session_uuid)
    data = json.loads(path.read_text(encoding="utf-8")); data["pid"] = os.getpid()
    path.write_text(json.dumps(data), encoding="utf-8")
    assert MODULE.command_park(args(board, id=own.compact_id, basis="pid-gone", actor="mac-a")) == 10
    assert "no death evidence" in capsys.readouterr().err
    assert MODULE.rows(board.read_text(encoding="utf-8"))[0].status == "active"


@pytest.mark.parametrize("log_quiet", [True, False])
def test_park_pid_gone_takes_a_pidless_seat_only_when_its_session_log_is_quiet(
    tmp_path, monkeypatch, capsys, log_quiet
):
    # Rajiv's 2026-09-20 ruling: a harness that is gone (an exited Muse Code
    # whose seat records no pid) is dead now, not after the stale threshold.
    import os
    import time
    import peer_addressing as PA
    fleet_a = tmp_path / "fleet-a"
    id_a = FI.mint_machine_id(fleet_a)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    native = "01a0bb23-4cc5-7182-881b-8fa2c59c3be2"
    quiet_beat = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
    own = make_row(machine=id_a, label="mac-a", heartbeat=quiet_beat, claims=["repo2/**", "release-train:x"],
                   ref="muse:" + native)
    board = tmp_path / "board.md"
    board.write_text(board_with([own]), encoding="utf-8")
    PA.write_seat(board, session_uuid=own.session_uuid, compact_id=own.compact_id, machine=id_a,
                  identity=PA.SelfIdentity(client="muse", harness_session_id=native))
    log = tmp_path / "muse-sessions" / "2026" / "09" / "19" / native / "session.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("{}\n", encoding="utf-8")
    if log_quiet:
        stamp = time.time() - 3 * 3600
        os.utime(log, (stamp, stamp))
    monkeypatch.setenv("MUSE_SESSIONS_DIR", str(tmp_path / "muse-sessions"))
    code = MODULE.command_park(args(board, id=own.compact_id, basis="pid-gone", actor="mac-a"))
    text = board.read_text(encoding="utf-8")
    if log_quiet:
        assert code == 0
        assert "Evidence: no recorded pid; session log quiet" in text
        assert MODULE.rows(text)[0].status == "parked"
    else:
        assert code == 10
        assert "no death evidence" in capsys.readouterr().err
        assert MODULE.rows(text)[0].status == "active"


def test_challenge_then_park_commands_observe_grace_without_sleeps(
    tmp_path, monkeypatch, capsys
):
    row = make_row(
        machine="id-b", label="mac-b",
        heartbeat=(datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat(),
        claims=["repo/**"],
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([row]), encoding="utf-8")
    assert (
        MODULE.command_challenge(args(board, id=row.compact_id, challenger="mac-a"))
        == 0
    )
    assert "10 minutes" in capsys.readouterr().out
    # The challenge just posted; the grace interval has not matured.
    assert (
        MODULE.command_park(
            args(board, id=row.compact_id, basis="challenge", actor="mac-a")
        )
        == 10
    )
    assert "grace interval" in capsys.readouterr().err


def test_challenge_command_refuses_fresh_row(tmp_path, capsys):
    row = make_row(
        machine="id-b", label="mac-b",
        heartbeat=datetime.now(timezone.utc).isoformat(), claims=["repo/**"],
    )
    board = tmp_path / "board.md"
    board.write_text(board_with([row]), encoding="utf-8")
    assert (
        MODULE.command_challenge(args(board, id=row.compact_id, challenger="mac-a"))
        == 10
    )
    assert "fresh" in capsys.readouterr().err

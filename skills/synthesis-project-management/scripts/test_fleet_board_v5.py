"""Fleet board v5, seats v2, and the guarded-evolution / pid rules.

Covers FLEET-AC-01 (no pid syscalls for foreign seats), FLEET-AC-02 (a v4
writer refuses a v5 board before touching the lease remote), and the v5
column + label + seats-schema-2 shape.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import board_grammar as GRAMMAR
import coordination as MODULE
import coordination_schema as SCHEMA
import fleet_identity as FI
import peer_addressing as PA


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


def claim_request(board: Path, *, area: str, workspace: str, machine: str,
                  session_id: str | None = None, project: str = "project-a"):
    values = {
        "id": session_id,
        "agent": "agent-a",
        "machine": machine,
        "project": project,
        "mode": "autonomous",
        "goal": "goal-a",
        "workspace": [workspace],
        "area": [area],
        "context_role": "owner",
        "replace": False,
        "client_ref": None,
    }
    return args(board, **values)


def test_template_declares_v5_with_machine_label_column():
    template = MODULE.template()
    assert "Schema: v5" in template
    assert "| machine label |" in template
    assert MODULE.TABLE_COLUMNS == MODULE.V5_COLUMNS


def test_claim_writes_machine_id_and_label_when_enrolled(tmp_path, monkeypatch):
    machine_id = FI.mint_machine_id()
    FI.enroll_self(label="mac-a", role="primary")
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:01990000-0000-7000-8000-000000000001")
    board = tmp_path / "board.md"
    request = claim_request(
        board, area="repo-a/**", workspace="/tmp/wt-a @ feature/a",
        machine="mac-a",
    )
    assert MODULE.command_claim(request) == 0
    row = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert row.machine == machine_id
    assert row.machine_label == "mac-a"
    assert row.machine_display == "mac-a"
    seat = PA.read_seat(board, row.session_uuid, strict=True)
    assert seat.schema == 2
    assert seat.machine_id == machine_id
    assert seat.machine_label == "mac-a"
    assert seat.last_heartbeat == row.heartbeat
    assert seat.status == "active"


def test_claim_without_enrollment_keeps_hostname(tmp_path):
    board = tmp_path / "board.md"
    request = claim_request(
        board, area="repo-a/**", workspace="/tmp/wt-a @ feature/a",
        machine="test-machine",
    )
    assert MODULE.command_claim(request) == 0
    row = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert row.machine == "test-machine"
    assert row.machine_label == "test-machine"


def test_v4_board_keeps_v4_on_claim_with_label_folded(tmp_path):
    machine_id = FI.mint_machine_id()
    FI.enroll_self(label="mac-a", role="primary")
    board = tmp_path / "board.md"
    board.write_text(
        MODULE.replace_table(MODULE.template(), [], force_schema=4),
        encoding="utf-8",
    )
    request = claim_request(
        board, area="repo-a/**", workspace="/tmp/wt-a @ feature/a",
        machine="mac-a",
    )
    assert MODULE.command_claim(request) == 0
    text = board.read_text(encoding="utf-8")
    assert "Schema: v4" in text
    row = MODULE.rows(text)[0]
    # Old readers expect the human name in the machine column.
    assert row.machine == "mac-a"
    assert row.machine_label == ""
    assert machine_id  # enrolled, but v4 emission folds to the label


def test_migrate_maps_local_rows_to_machine_ids(tmp_path):
    machine_id = FI.mint_machine_id()
    FI.enroll_self(label="mac-a", role="primary")
    board = tmp_path / "board.md"
    local = socket.gethostname()
    v4 = MODULE.replace_table(MODULE.template(), [], force_schema=4)
    rows = [
        MODULE.Session(
            session_uuid="", compact_id="", speakable_id="", legacy_id="L",
            agent="a", machine=local, project="p", started="t", heartbeat="t",
            mode="m", workspaces=[], goal="g", claims=["repo-l/**"],
            context_role="owner", status="active",
        ),
        MODULE.Session(
            session_uuid="", compact_id="", speakable_id="", legacy_id="F",
            agent="a", machine="other-host", project="q", started="t",
            heartbeat="t", mode="m", workspaces=[], goal="g",
            claims=["repo-f/**"], context_role="owner", status="active",
        ),
    ]
    board.write_text(MODULE.replace_table(v4, rows, force_schema=4), encoding="utf-8")
    assert MODULE.command_migrate(args(board)) == 0
    text = board.read_text(encoding="utf-8")
    assert "Schema: v5" in text
    migrated = {row.legacy_id: row for row in MODULE.rows(text)}
    assert migrated["L"].machine == machine_id
    assert migrated["L"].machine_label == local
    assert migrated["F"].machine == "other-host"
    assert migrated["F"].machine_label == "other-host"


def test_delivery_lane_uses_machine_label():
    row = MODULE.Session(
        session_uuid="", compact_id="s-x", speakable_id="", legacy_id="",
        agent="a", machine="some-uuid", machine_label="mac-b",
        project="p", started="t", heartbeat="t", mode="m", workspaces=[],
        goal="g", claims=[], context_role="owner", status="active",
        client_ref="codex:thread-1",
    )
    assert "mac-b" in MODULE.delivery_lane(row)
    assert "some-uuid" not in MODULE.delivery_lane(row)


def _v4_only_engine(monkeypatch):
    monkeypatch.setattr(GRAMMAR, "SCHEMA_VERSION", 4)
    monkeypatch.setattr(MODULE, "SCHEMA_VERSION", 4)
    monkeypatch.setattr(SCHEMA, "SCHEMA_VERSION", 4)


def _leased_board(tmp_path: Path, text: str) -> Path:
    board = tmp_path / "board.md"
    board.write_text(text, encoding="utf-8")
    (tmp_path / "lease.json").write_text(
        json.dumps(
            {
                "remote": "https://example.invalid/fleet.git",
                "ref": "refs/synthesis/coordination-board",
                "repository": str(tmp_path / "lease-repo"),
            }
        ),
        encoding="utf-8",
    )
    return board


def test_v4_writer_refuses_v5_board_before_lease_touch(tmp_path, monkeypatch):
    """FLEET-AC-02: named refusal, no fetch, no publish, operation unrun."""
    board = _leased_board(tmp_path, MODULE.template())
    _v4_only_engine(monkeypatch)

    def explode(*argc, **kwargs):
        raise AssertionError("lease remote touched by a refusing writer")

    monkeypatch.setattr(MODULE, "git_lease", explode)
    ran = []
    with pytest.raises(GRAMMAR.UnsupportedBoardSchemaError, match="schema v5"):
        MODULE.locked_update(board, lambda content: ran.append(content))
    assert ran == []


def test_v4_writer_refuses_fetched_v5_board_without_publish(tmp_path, monkeypatch):
    """FLEET-AC-02 with a stale mirror: fetch, then refuse before publish."""
    v4_text = MODULE.replace_table(MODULE.template(), [], force_schema=4)
    board = _leased_board(tmp_path, v4_text)
    v5_text = MODULE.template()
    _v4_only_engine(monkeypatch)
    monkeypatch.setattr(
        MODULE, "lease_fetch", lambda config: ("f" * 40, v5_text)
    )

    def explode_publish(*argc, **kwargs):
        raise AssertionError("partial publish by a refusing writer")

    monkeypatch.setattr(MODULE, "lease_publish", explode_publish)
    with pytest.raises(GRAMMAR.UnsupportedBoardSchemaError, match="schema v5"):
        MODULE.locked_update(board, lambda content: content)


def test_v5_writer_accepts_v5_board(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(MODULE.template(), encoding="utf-8")
    MODULE.locked_update(board, lambda content: content)
    assert "Schema: v5" in board.read_text(encoding="utf-8")


def _foreign_seat(now: datetime) -> PA.Seat:
    return PA.Seat(
        session_uuid="019f0132-0000-7000-8000-000000000001",
        compact_id="s-0000-0000-0001",
        client="codex",
        machine="foreign-machine-id",
        harness_session_id="thread-1",
        pid=12345,
        cwd="/tmp",
        updated_at=now.isoformat(),
        schema=2,
        machine_label="mac-b",
        last_heartbeat=now.isoformat(),
        status="active",
    )


def test_foreign_seat_is_live_from_heartbeat_with_zero_pid_syscalls():
    """FLEET-AC-01: fabricated foreign seat, fresh heartbeat, no pid probe."""
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    seat = _foreign_seat(now)
    calls: list = []

    def explode(pid):
        calls.append(pid)
        raise AssertionError("pid consulted for a foreign seat")

    result = PA.seat_liveness(
        seat, local_machine_id="local-machine-id", now=now, alive=explode
    )
    assert result == {"live": True, "pid_checked": False, "pid_alive": None}
    assert calls == []
    assert not PA.pid_consult_allowed(seat.machine_id, "local-machine-id")


def test_foreign_seat_with_stale_heartbeat_is_not_live_and_still_no_pid_probe():
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    seat = _foreign_seat(now - timedelta(minutes=31))
    seat.last_heartbeat = (now - timedelta(minutes=31)).isoformat()
    calls: list = []
    result = PA.seat_liveness(
        seat,
        local_machine_id="local-machine-id",
        now=now,
        alive=lambda pid: calls.append(pid),
    )
    assert result["live"] is False
    assert result["pid_checked"] is False
    assert calls == []


def test_same_machine_seat_may_consult_pid():
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    seat = _foreign_seat(now)
    seat.machine = "local-machine-id"
    calls: list = []
    result = PA.seat_liveness(
        seat, local_machine_id="local-machine-id", now=now,
        alive=lambda pid: calls.append(pid) or True,
    )
    assert result == {"live": True, "pid_checked": True, "pid_alive": True}
    assert calls == [12345]


def test_delivery_lanes_for_foreign_seat_make_no_pid_syscall(tmp_path, monkeypatch):
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    seat = _foreign_seat(now)
    seat.client = PA.CLIENT_CLAUDE
    seat.harness_session_id = "harness-1"
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "s.json").write_text(
        json.dumps(
            {
                "sessionId": "harness-1",
                "messagingSocketPath": "/tmp/sock",
                "pid": 99999,
                "name": "peer",
            }
        ),
        encoding="utf-8",
    )

    def explode(pid):
        raise AssertionError("pid syscall for a foreign seat")

    monkeypatch.setattr(PA.os, "kill", explode)
    lanes = PA.delivery_lanes(
        client_ref="ccd:local_x",
        compact_id=seat.compact_id,
        target_machine="foreign-machine-id",
        seat=seat,
        local_machine="local-machine-id",
        registry=registry,
        alive=explode,
    )
    assert lanes == {"bus": {"to": seat.compact_id}}


def test_write_seat_schema_2_roundtrip_strict(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:thread-9")
    board = tmp_path / "board.md"
    board.write_text(MODULE.template(), encoding="utf-8")
    identity = MODULE.new_identity()
    path = PA.write_seat(
        board,
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        machine="machine-id-1",
        machine_label="mac-a",
        identity=PA.detect_self(),
        last_heartbeat="2026-09-19T12:00:00+00:00",
        status="active",
    )
    assert path is not None
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema"] == 2
    assert raw["machine_label"] == "mac-a"
    assert raw["last_heartbeat"] == "2026-09-19T12:00:00+00:00"
    assert raw["status"] == "active"
    seat = PA.read_seat(board, identity.session_uuid, strict=True)
    assert seat is not None and seat.machine_id == "machine-id-1"


def test_read_seat_tolerates_v1_non_strict_but_strict_requires_v2(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(MODULE.template(), encoding="utf-8")
    identity = MODULE.new_identity()
    path = PA.seat_path(board, identity.session_uuid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "session_uuid": identity.session_uuid,
                "compact_id": identity.compact_id,
                "client": "codex",
                "machine": "old-hostname",
                "harness_session_id": "thread-1",
                "schema": 1,
            }
        ),
        encoding="utf-8",
    )
    seat = PA.read_seat(board, identity.session_uuid)
    assert seat is not None
    assert seat.machine == "old-hostname"
    assert seat.machine_label == ""
    assert seat.status == "active"
    with pytest.raises(ValueError, match="seat"):
        PA.read_seat(board, identity.session_uuid, strict=True)


def test_read_seat_rejects_unknown_schema_non_strict(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(MODULE.template(), encoding="utf-8")
    identity = MODULE.new_identity()
    path = PA.seat_path(board, identity.session_uuid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "session_uuid": identity.session_uuid,
                "compact_id": identity.compact_id,
                "client": "codex",
                "machine": "m",
                "schema": 99,
            }
        ),
        encoding="utf-8",
    )
    assert PA.read_seat(board, identity.session_uuid) is None


def test_claim_ignores_ambient_enrollment_without_override(tmp_path, monkeypatch):
    """A board mutation must not stamp the ambient home's machine-id.

    Reproduces the enrolled-Mac failure: with a minted ambient identity
    and no SYNTHESIS_FLEET_DIR override, a claim against a plain tmp
    board falls back to the requested label, not the ambient id.
    """
    ambient_fleet = tmp_path / "ambient-home" / ".synthesis" / "fleet"
    ambient_fleet.mkdir(parents=True)
    (ambient_fleet / "machine-id").write_text(
        "12345678-1234-4234-8234-1234567890ab", encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(tmp_path / "ambient-home"))
    monkeypatch.delenv(FI.FLEET_DIR_ENV, raising=False)
    board = tmp_path / "board.md"
    request = claim_request(
        board, area="repo-a/**", workspace="/tmp/wt-a @ feature/a",
        machine="test-machine",
    )
    assert MODULE.command_claim(request) == 0
    row = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert row.machine == "test-machine"
    assert row.machine_label == "test-machine"

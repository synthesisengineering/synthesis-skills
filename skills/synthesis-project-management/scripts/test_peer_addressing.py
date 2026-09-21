"""Peer addressing: seats, lanes, receipts, inbox, and the engine verbs around them."""
from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as ENGINE  # noqa: E402
import peer_addressing as PA  # noqa: E402

CLAUDE_ENV = {
    "CLAUDECODE": "1",
    "CLAUDE_CODE_SESSION_ID": "11111111-1111-4111-8111-111111111111",
    "CLAUDE_CODE_HOST_SESSION_ID": "local_aaaa-1111",
    "CLAUDE_PID": "4242",
}


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for name in (
        "SYNTHESIS_CLIENT_SESSION_REF",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_PID",
        "CLAUDECODE",
        "SYNTHESIS_PEER_REGISTRY",
    ):
        monkeypatch.delenv(name, raising=False)


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim(board: Path, project: str, *, machine: str = "m1", area: str | None = None, workspace: str | None = None):
    request = args(
        board,
        id=None,
        agent=f"agent-{project}",
        machine=machine,
        project=project,
        mode="interactive",
        goal=f"goal-{project}",
        workspace=[workspace or f"/tmp/wt-{project} @ feature/{project}"],
        area=[area or f"repo-{project}/**"],
        context_role="owner",
    )
    assert ENGINE.command_claim(request) == 0
    return [row for row in ENGINE.rows(board.read_text(encoding="utf-8")) if row.project == project][0]


def registry_with(tmp_path: Path, session_id: str, *, name: str = "peer-1a", pid: int | None = None) -> Path:
    registry = tmp_path / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    entry = {
        "pid": pid or os.getpid(),
        "sessionId": session_id,
        "cwd": "/tmp/peer",
        "messagingSocketPath": f"/tmp/cc-socks/{pid or os.getpid()}.sock",
        "name": name,
        "nameSource": "derived",
    }
    (registry / f"{entry['pid']}.json").write_text(json.dumps(entry), encoding="utf-8")
    return registry


# --- self identity --------------------------------------------------------------------------

def test_claude_shell_identity_keys_by_harness_session_and_prefers_the_desktop_ref() -> None:
    identity = PA.detect_self(CLAUDE_ENV)
    assert identity.client == PA.CLIENT_CLAUDE
    assert identity.sender_key == "cc:11111111-1111-4111-8111-111111111111"
    assert identity.primary_ref == "ccd:local_aaaa-1111"
    assert identity.pid == 4242


def test_terminal_session_without_desktop_id_registers_under_cc() -> None:
    env = {k: v for k, v in CLAUDE_ENV.items() if k != "CLAUDE_CODE_HOST_SESSION_ID"}
    assert PA.detect_self(env).primary_ref == "cc:11111111-1111-4111-8111-111111111111"


def test_codex_identity_comes_from_the_exported_ref() -> None:
    identity = PA.detect_self({"SYNTHESIS_CLIENT_SESSION_REF": "codex:0a0a-1b1b"})
    assert identity.client == PA.CLIENT_CODEX
    assert identity.sender_key == "codex:0a0a-1b1b"
    assert identity.primary_ref == "codex:0a0a-1b1b"


def test_empty_environment_has_no_identity() -> None:
    identity = PA.detect_self({})
    assert identity.sender_key == "" and identity.primary_ref == ""


def test_hook_payload_session_id_is_authoritative_for_the_sender_key() -> None:
    claude = PA.identity_from_hook({"session_id": "22222222-2222-4222-8222-222222222222"}, CLAUDE_ENV)
    assert claude.sender_key == "cc:22222222-2222-4222-8222-222222222222"
    codex = PA.identity_from_hook({"session_id": "0a0a-1b1b"}, {"CODEX_HOME": "/x"})
    assert codex.sender_key == "codex:0a0a-1b1b"


def test_muse_identity_comes_from_the_exported_ref() -> None:
    identity = PA.detect_self({"SYNTHESIS_CLIENT_SESSION_REF": "muse:0b0b-2c2c"})
    assert identity.client == PA.CLIENT_MUSE
    assert identity.harness_session_id == "0b0b-2c2c"
    assert identity.sender_key == "muse:0b0b-2c2c"
    assert identity.primary_ref == "muse:0b0b-2c2c"


def test_muse_hook_payload_is_not_misattributed_to_codex() -> None:
    env = {"SYNTHESIS_HOOK_CLIENT": "muse"}
    muse = PA.identity_from_hook({"session_id": "0b0b-2c2c"}, env)
    assert muse.client == PA.CLIENT_MUSE
    assert muse.sender_key == "muse:0b0b-2c2c"
    absent = PA.identity_from_hook({"session_id": "0b0b-2c2c"}, {})
    assert absent.sender_key == "codex:0b0b-2c2c"


# --- seats ----------------------------------------------------------------------------------

def test_claim_writes_a_seat_release_removes_it(tmp_path, monkeypatch) -> None:
    for key, value in CLAUDE_ENV.items():
        monkeypatch.setenv(key, value)
    board = tmp_path / "board.md"
    row = claim(board, "project-a")
    seat = PA.read_seat(board, row.session_uuid)
    assert seat is not None
    assert seat.harness_session_id == CLAUDE_ENV["CLAUDE_CODE_SESSION_ID"]
    assert seat.host_session_id == CLAUDE_ENV["CLAUDE_CODE_HOST_SESSION_ID"]
    assert seat.client == PA.CLIENT_CLAUDE and seat.machine == "m1"
    assert PA.seat_for_identity(board, PA.detect_self(CLAUDE_ENV)).session_uuid == row.session_uuid
    assert ENGINE.command_release(args(board, id=row.compact_id)) == 0
    assert PA.read_seat(board, row.session_uuid) is None


def test_claim_without_handles_records_no_seat(tmp_path) -> None:
    board = tmp_path / "board.md"
    row = claim(board, "project-a")
    assert PA.read_seat(board, row.session_uuid) is None


def test_explicit_codex_ref_seats_a_codex_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:0a0a-1b1b")
    board = tmp_path / "board.md"
    row = claim(board, "project-c")
    seat = PA.read_seat(board, row.session_uuid)
    assert seat is not None and seat.client == PA.CLIENT_CODEX
    assert seat.harness_session_id == "0a0a-1b1b"
    assert row.client_ref == "codex:0a0a-1b1b"


def test_heartbeat_refreshes_the_seat(tmp_path, monkeypatch) -> None:
    for key, value in CLAUDE_ENV.items():
        monkeypatch.setenv(key, value)
    board = tmp_path / "board.md"
    row = claim(board, "project-a")
    before = PA.read_seat(board, row.session_uuid)
    stale = PA.iso(PA.utcnow() - timedelta(hours=1))
    path = PA.seat_path(board, row.session_uuid)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["updated_at"] = stale
    path.write_text(json.dumps(data), encoding="utf-8")
    assert ENGINE.command_heartbeat(args(board, id=row.compact_id)) == 0
    after = PA.read_seat(board, row.session_uuid)
    assert after is not None and after.updated_at > stale
    assert after.harness_session_id == before.harness_session_id


# --- registry and lanes ---------------------------------------------------------------------

def test_registry_entry_requires_a_living_process(tmp_path) -> None:
    registry = registry_with(tmp_path, "sid-1", pid=999999)
    assert PA.registry_entry_for_session("sid-1", registry, alive=lambda pid: False) is None
    entry = PA.registry_entry_for_session("sid-1", registry, alive=lambda pid: True)
    assert entry is not None and PA.harness_address(entry) == "uds:/tmp/cc-socks/999999.sock"


def test_lanes_exist_only_on_the_target_machine_and_only_from_live_truth(tmp_path) -> None:
    seat = PA.Seat(
        session_uuid="u", compact_id="s-aaaa-bbbb-cccc", client=PA.CLIENT_CLAUDE,
        machine="m1", harness_session_id="sid-1", host_session_id="local_x",
    )
    registry = registry_with(tmp_path, "sid-1", pid=999999)
    same = PA.delivery_lanes(
        client_ref="ccd:local_x", compact_id="s-aaaa-bbbb-cccc", target_machine="m1",
        seat=seat, local_machine="m1", registry=registry, alive=lambda pid: True,
    )
    assert same["bus"] == {"to": "s-aaaa-bbbb-cccc"}
    assert same["ccd"] == {"session_id": "local_x"}
    assert same["harness"]["to"] == "uds:/tmp/cc-socks/999999.sock"
    assert same["harness"]["name"] == "peer-1a"
    other = PA.delivery_lanes(
        client_ref="ccd:local_x", compact_id="s-aaaa-bbbb-cccc", target_machine="m2",
        seat=seat, local_machine="m1", registry=registry, alive=lambda pid: True,
    )
    assert set(other) == {"bus"}
    dead = PA.delivery_lanes(
        client_ref="ccd:local_x", compact_id="s-aaaa-bbbb-cccc", target_machine="m1",
        seat=seat, local_machine="m1", registry=registry, alive=lambda pid: False,
    )
    assert "harness" not in dead and "ccd" in dead


def test_codex_lane_is_the_queue_command(tmp_path) -> None:
    lanes = PA.delivery_lanes(
        client_ref="codex:0a0a-1b1b", compact_id="s-1", target_machine="m1",
        seat=None, local_machine="m1", registry=tmp_path / "none",
    )
    assert lanes["codex"]["thread"] == "0a0a-1b1b"
    assert lanes["codex"]["command"].startswith("codex queue --thread 0a0a-1b1b")


def test_invocations_never_use_a_display_name_as_the_address(tmp_path) -> None:
    registry = registry_with(tmp_path, "sid-1", pid=999999)
    seat = PA.Seat(session_uuid="u", compact_id="s-1", client=PA.CLIENT_CLAUDE, machine="m1", harness_session_id="sid-1")
    lanes = PA.delivery_lanes(
        client_ref="ccd:local_x", compact_id="s-1", target_machine="m1",
        seat=seat, local_machine="m1", registry=registry, alive=lambda pid: True,
    )
    text = "\n".join(PA.lane_invocations(lanes, "s-me"))
    assert "to='uds:/tmp/cc-socks/999999.sock'" in text
    assert "display only" in text
    assert "from s-me" in text


# --- receipts -------------------------------------------------------------------------------

def test_receipt_requires_a_sender_identity_and_expires(tmp_path) -> None:
    board = tmp_path / "board.md"
    target = {"uuid": "u-t", "compact": "s-t"}
    assert PA.write_receipt(board, sender=PA.SelfIdentity(), sender_row=None, selector="p", matched_by="project", target=target, lanes={"bus": {"to": "s-t"}}) is None
    sender = PA.detect_self(CLAUDE_ENV)
    path = PA.write_receipt(board, sender=sender, sender_row=None, selector="p", matched_by="project", target=target, lanes={"ccd": {"session_id": "local_t"}, "bus": {"to": "s-t"}})
    assert path is not None and path.is_file()
    live = PA.load_receipts(board, sender.sender_key)
    assert len(live) == 1
    assert PA.receipt_for_address(live, "ccd", "local_t")["target"]["compact"] == "s-t"
    assert PA.receipt_for_address(live, "ccd", "local_other") is None
    later = PA.utcnow() + timedelta(minutes=PA.RECEIPT_TTL_MINUTES + 1)
    assert PA.load_receipts(board, sender.sender_key, later) == []
    assert not path.exists(), "expired receipts are pruned"


def test_broadcast_conflict_sees_the_same_text_sent_elsewhere(tmp_path) -> None:
    board = tmp_path / "board.md"
    digest = PA.body_digest("from s-me: please review PR 7")
    assert PA.body_digest("  FROM s-me:   please review pr 7 ") == digest
    PA.append_send_log(board, {"at": PA.iso(PA.utcnow()), "decision": "allow", "sender_key": "cc:me", "digest": digest, "target_uuid": "u-1", "lane": "ccd", "target": "local_1"})
    assert PA.broadcast_conflict(board, sender_key="cc:me", digest=digest, target_uuid="u-2") is not None
    assert PA.broadcast_conflict(board, sender_key="cc:me", digest=digest, target_uuid="u-1") is None
    assert PA.broadcast_conflict(board, sender_key="cc:other", digest=digest, target_uuid="u-2") is None
    old = PA.utcnow() + timedelta(minutes=PA.BROADCAST_WINDOW_MINUTES + 1)
    assert PA.broadcast_conflict(board, sender_key="cc:me", digest=digest, target_uuid="u-2", now=old) is None


# --- inbox ----------------------------------------------------------------------------------

def test_inbox_delivers_seat_and_project_addressed_messages_once(tmp_path, monkeypatch) -> None:
    board = tmp_path / "board.md"
    sender = claim(board, "project-a")
    for key, value in CLAUDE_ENV.items():
        monkeypatch.setenv(key, value)
    me = claim(board, "project-b")
    assert ENGINE.command_message(args(board, sender=sender.compact_id, to=me.compact_id, text="Direct: ready for review.")) == 0
    assert ENGINE.command_message(args(board, sender=sender.compact_id, to="project-b", text="Project-wide note.")) == 0
    assert ENGINE.command_message(args(board, sender=sender.compact_id, to=sender.compact_id, text="Note to self.")) == 0
    messages = PA.parse_messages(board.read_text(encoding="utf-8"))
    assert [m.body for m in messages] == ["Direct: ready for review.", "Project-wide note.", "Note to self."]
    forms = {me.session_uuid, me.compact_id, me.speakable_id}
    unread = PA.unread_messages(board.read_text(encoding="utf-8"), board=board, sender_key="cc:x", identity_forms=forms, project="project-b")
    assert [m.body for m in unread] == ["Direct: ready for review.", "Project-wide note."]
    rendered = PA.render_inbox(unread)
    assert "2 unread message(s)" in rendered and "never a chat title" in rendered
    PA.mark_seen(board, "cc:x", {m.key for m in unread})
    assert PA.unread_messages(board.read_text(encoding="utf-8"), board=board, sender_key="cc:x", identity_forms=forms, project="project-b") == []


def test_project_messages_older_than_the_seat_are_history_not_inbox() -> None:
    """A fresh seat on a busy project must not be greeted with every message
    ever addressed to that project as unread; the SessionStart board read
    covers history. A message naming the session exactly is always its own."""
    old = PA.BoardMessage(recipient="project-b sessions", sender="s-1", timestamp="2026-08-17T21:44:31-04:00", body="x")
    new = PA.BoardMessage(recipient="project-b sessions", sender="s-1", timestamp="2026-09-02T18:00:00-04:00", body="y")
    direct = PA.BoardMessage(recipient="s-2", sender="s-1", timestamp="2026-08-17T21:44:31-04:00", body="z")
    since = "2026-09-02T17:00:00-04:00"
    assert not PA.addressed_to(old, {"s-2"}, "project-b", since)
    assert PA.addressed_to(new, {"s-2"}, "project-b", since)
    assert PA.addressed_to(direct, {"s-2"}, "project-b", since)
    assert PA.addressed_to(old, {"s-2"}, "project-b", "2026-07-29 ~14:00"), "an unparseable floor disables the bound, not the delivery"
    assert PA.addressed_to(old, {"s-2"}, "project-b", None)


def test_free_text_addressees_are_never_delivered() -> None:
    message = PA.BoardMessage(recipient="whoever is holding the train", sender="s-1", timestamp="t", body="x")
    assert not PA.addressed_to(message, {"s-2"}, "project-b")
    exact = PA.BoardMessage(recipient="s-2", sender="s-1", timestamp="t", body="x")
    assert PA.addressed_to(exact, {"s-2"}, "")


def test_inbox_rendering_is_bounded() -> None:
    messages = [PA.BoardMessage(recipient="s-2", sender="s-1", timestamp=f"t{i}", body="\n".join(f"line {n}" for n in range(40))) for i in range(8)]
    rendered = PA.render_inbox(messages, limit=3, body_lines=5)
    assert "8 unread message(s)" in rendered and "showing the newest 3" in rendered
    assert rendered.count("… 35 more line(s)") == 3


# --- engine verbs ---------------------------------------------------------------------------

def resolve_args(board: Path, to: str, **overrides):
    values = {"to": to, "role": None, "include_released": False, "stale_after_minutes": 240, "json": False, "no_receipt": False, "registry": None, "local_machine": None}
    values.update(overrides)
    return args(board, **values)


def two_seats(tmp_path, monkeypatch):
    """A sender seat (this shell) and a target seat with a live registry entry."""
    board = tmp_path / "board.md"
    target_env = {**CLAUDE_ENV, "CLAUDE_CODE_SESSION_ID": "33333333-3333-4333-8333-333333333333", "CLAUDE_CODE_HOST_SESSION_ID": "local_target"}
    for key, value in target_env.items():
        monkeypatch.setenv(key, value)
    target = claim(board, "project-t")
    for key, value in CLAUDE_ENV.items():
        monkeypatch.setenv(key, value)
    sender = claim(board, "project-s")
    registry = registry_with(tmp_path, target_env["CLAUDE_CODE_SESSION_ID"], pid=os.getpid())
    return board, sender, target, registry


def test_resolve_prints_exact_lanes_and_issues_a_receipt(tmp_path, monkeypatch, capsys) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    assert ENGINE.command_resolve(resolve_args(board, "project-t", registry=registry, local_machine="m1")) == 0
    out = capsys.readouterr().out
    assert "ccd send_message to session_id local_target" in out
    assert f"SendMessage to='uds:/tmp/cc-socks/{os.getpid()}.sock'" in out
    assert f"from {sender.compact_id}" in out
    assert "Delivery receipt:" in out
    receipts = PA.load_receipts(board, PA.detect_self(CLAUDE_ENV).sender_key)
    assert len(receipts) == 1
    assert receipts[0]["target"]["uuid"] == target.session_uuid
    assert receipts[0]["lanes"]["ccd"] == {"session_id": "local_target"}
    assert receipts[0]["issued_by"]["board"]["compact"] == sender.compact_id


def test_resolve_json_carries_lanes_and_receipt(tmp_path, monkeypatch, capsys) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    capsys.readouterr()
    assert ENGINE.command_resolve(resolve_args(board, target.compact_id, json=True, registry=registry, local_machine="m1")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["lanes"]) == {"bus", "ccd", "harness"}
    assert payload["receipt"] and payload["sender"] == sender.compact_id


def test_resolve_without_identity_warns_that_direct_lanes_will_refuse(tmp_path, capsys) -> None:
    board = tmp_path / "board.md"
    claim(board, "project-t")
    assert ENGINE.command_resolve(resolve_args(board, "project-t", local_machine="m1")) == 0
    captured = capsys.readouterr()
    assert "no delivery receipt issued" in captured.err
    assert "bus lane:" in captured.out


def test_resolve_no_receipt_looks_up_only(tmp_path, monkeypatch) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    assert ENGINE.command_resolve(resolve_args(board, "project-t", no_receipt=True, registry=registry, local_machine="m1")) == 0
    assert PA.load_receipts(board, PA.detect_self(CLAUDE_ENV).sender_key) == []


def test_ambiguous_resolve_issues_no_receipt(tmp_path, monkeypatch) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    monkeypatch.delenv("CLAUDE_CODE_HOST_SESSION_ID")
    contributor = args(board, id=None, agent="c", machine="m1", project="project-t", mode="interactive", goal="g", workspace=["/tmp/wt-c @ feature/c"], area=["other-repo/docs/**"], context_role="contributor")
    assert ENGINE.command_claim(contributor) == 0
    for key, value in CLAUDE_ENV.items():
        monkeypatch.setenv(key, value)
    assert ENGINE.command_resolve(resolve_args(board, "project-t", registry=registry, local_machine="m1")) == 20
    assert PA.load_receipts(board, PA.detect_self(CLAUDE_ENV).sender_key) == []


def test_whoami_reports_seat_and_the_lanes_peers_use(tmp_path, monkeypatch, capsys) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    own_registry = registry_with(tmp_path / "own", CLAUDE_ENV["CLAUDE_CODE_SESSION_ID"], name="me-1b", pid=os.getpid())
    capsys.readouterr()
    assert ENGINE.command_whoami(args(board, json=True, registry=own_registry, local_machine="m1")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["seat"] == sender.compact_id
    assert payload["sender_key"] == "cc:" + CLAUDE_ENV["CLAUDE_CODE_SESSION_ID"]
    assert payload["lanes_peers_use"]["harness"]["to"].startswith("uds:")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    monkeypatch.delenv("CLAUDECODE")
    assert ENGINE.command_whoami(args(board, json=False, registry=own_registry, local_machine="m1")) == 1


def test_inbox_verb_lists_and_marks(tmp_path, monkeypatch, capsys) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    assert ENGINE.command_message(args(board, sender=target.compact_id, to=sender.compact_id, text="Ping from the target seat.")) == 0
    capsys.readouterr()
    assert ENGINE.command_inbox(args(board, id=None, mark_read=False, json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session"] == sender.compact_id
    assert [m["body"] for m in payload["unread"]] == ["Ping from the target seat."]
    assert ENGINE.command_inbox(args(board, id=None, mark_read=True, json=False)) == 0
    assert "Marked 1 message(s) read" in capsys.readouterr().out
    assert ENGINE.command_inbox(args(board, id=None, mark_read=False, json=False)) == 0
    assert "No unread messages" in capsys.readouterr().out


def test_doctor_counts_seats_and_names_orphans(tmp_path, monkeypatch, capsys) -> None:
    board, sender, target, registry = two_seats(tmp_path, monkeypatch)
    assert ENGINE.command_doctor(args(board)) == 0
    assert "2 seat(s)" in capsys.readouterr().out
    assert ENGINE.command_release(
        args(
            board,
            id=target.compact_id,
            administrative=True,
            reason="doctor orphan-seat fixture",
        )
    ) == 0
    PA.write_seat(board, session_uuid=target.session_uuid, compact_id=target.compact_id, machine="m1", identity=PA.SelfIdentity(client="claude-code", harness_session_id="orphan"))
    assert ENGINE.command_doctor(args(board)) == 0
    assert "1 without an active row" in capsys.readouterr().out


def test_delivery_lane_summary_names_codex_queue_and_cc_sessions() -> None:
    codex = ENGINE.Session("u", "s-1", "sp", "", "OpenAI Codex", "m1", "p", "t", "t", "autonomous", [], "g", [], "owner", "active", client_ref="codex:0a0a")
    assert ENGINE.delivery_lane(codex).startswith("codex queue --thread 0a0a")
    terminal = ENGINE.Session("u", "s-1", "sp", "", "Claude Code", "m1", "p", "t", "t", "interactive", [], "g", [], "owner", "active", client_ref="cc:1111")
    assert "uds: socket" in ENGINE.delivery_lane(terminal)


def test_terminal_session_claim_registers_cc_ref(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "11111111-1111-4111-8111-111111111111")
    board = tmp_path / "board.md"
    row = claim(board, "project-a")
    assert row.client_ref == "cc:11111111-1111-4111-8111-111111111111"


LIVE_SEAT = "018f0000-0000-7000-8000-00000000aa01"
STALE_SEAT = "018f0000-0000-7000-8000-00000000aa02"


def _write_v1_seat(board: Path, session_uuid: str) -> Path:
    from coordination_schema import identity_from_uuid
    path = PA.seat_path(board, session_uuid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "session_uuid": session_uuid,
        "compact_id": identity_from_uuid(session_uuid).compact_id,
        "client": "codex",
        "machine": "fixture-hostname",
        "harness_session_id": "dead-native",
        "host_session_id": "",
        "pid": None,
        "cwd": "/tmp/fixture",
        "updated_at": "2026-09-14T21:15:13+00:00",
        "schema": 1,
    }), encoding="utf-8")
    return path


def _write_live_seat(board: Path) -> PA.Seat:
    from coordination_schema import identity_from_uuid
    PA.write_seat(
        board, session_uuid=LIVE_SEAT, compact_id=identity_from_uuid(LIVE_SEAT).compact_id,
        machine="e808f74c-machine-id", machine_label="fixture-mac",
        identity=PA.SelfIdentity(client="claude-code", harness_session_id="live-native", host_session_id="local_live"),
    )
    return PA.read_seat(board, LIVE_SEAT, strict=True)


def test_strict_directory_read_contains_a_stale_schema1_seat_and_names_it(tmp_path, capsys) -> None:
    # Regression 2026-09-20: one pre-migration seat file made every strict
    # read of the directory (the SessionStart diagnostic, the doctor) fail
    # closed with no output. The file is skipped and named; valid seats load.
    board = tmp_path / "board.md"
    board.write_text("# Board\n", encoding="utf-8")
    live = _write_live_seat(board)
    stale = _write_v1_seat(board, STALE_SEAT)
    skipped: list[tuple[Path, str]] = []
    assert PA.all_seats(board, strict=True, skipped=skipped) == [live]
    assert skipped == [(stale, "stale schema-1 seat")]
    assert stale.name in capsys.readouterr().err
    assert PA.stale_seat_files(board) == [(stale, "stale schema-1 seat")]
    identity = PA.SelfIdentity(client="claude-code", harness_session_id="live-native")
    assert PA.seat_for_identity(board, identity, strict=True) == live


def test_strict_read_of_one_stale_seat_by_uuid_still_refuses(tmp_path) -> None:
    board = tmp_path / "board.md"
    board.write_text("# Board\n", encoding="utf-8")
    _write_v1_seat(board, STALE_SEAT)
    with pytest.raises(ValueError, match="invalid coordination seat fields"):
        PA.read_seat(board, STALE_SEAT, strict=True)


def test_strict_directory_read_still_raises_on_a_malformed_seat(tmp_path) -> None:
    board = tmp_path / "board.md"
    board.write_text("# Board\n", encoding="utf-8")
    _write_live_seat(board)
    malformed = PA.seat_path(board, STALE_SEAT)
    malformed.write_text(json.dumps({"session_uuid": STALE_SEAT, "schema": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid coordination seat fields"):
        PA.all_seats(board, strict=True)


def test_strict_directory_read_still_raises_on_an_unreadable_seat(tmp_path) -> None:
    board = tmp_path / "board.md"
    board.write_text("# Board\n", encoding="utf-8")
    _write_live_seat(board)
    unreadable = PA.seat_path(board, STALE_SEAT)
    unreadable.write_text("{}", encoding="utf-8")
    unreadable.chmod(0)
    try:
        with pytest.raises(OSError):
            PA.all_seats(board, strict=True)
    finally:
        unreadable.chmod(0o600)


def test_doctor_names_stale_seat_files_without_failing(tmp_path, monkeypatch, capsys) -> None:
    board = tmp_path / "board.md"
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
    request = args(board, id=None, agent="agent", machine="m1", project="alpha", mode="interactive", goal="g",
                   workspace=["/tmp/wt-alpha @ feature/alpha"], area=["repo-alpha/**"], context_role="owner")
    assert ENGINE.command_claim(request) == 0
    stale = _write_v1_seat(board, STALE_SEAT)
    assert ENGINE.command_doctor(args(board)) == 0
    out = capsys.readouterr().out
    assert "PASS coordination" in out
    assert f"1 stale schema-1 seat file(s) skipped by strict reads: {stale.name}" in out


# --- durable project delivery -----------------------------------------------------

def _claim_role(board: Path, project: str, role: str, tag: str):
    request = args(
        board,
        id=None,
        agent=f"agent-{tag}",
        machine=f"m-{tag}",
        project=project,
        mode="interactive",
        goal=f"goal-{tag}",
        workspace=[f"/tmp/wt-{tag} @ feature/{tag}"],
        area=[f"repo-{tag}/**"],
        context_role=role,
    )
    assert ENGINE.command_claim(request) == 0
    matches = [row for row in ENGINE.rows(board.read_text(encoding="utf-8")) if row.project == project]
    assert matches
    return matches[-1]


def _ancient_durable(board: Path, project: str, body: str) -> None:
    text = board.read_text(encoding="utf-8")
    heading = (
        f"### \u2192 {project} sessions [durable], "
        "from s-ancient \u2014 2020-01-01T00:00:00+00:00\n\n"
    )
    assert "## Messages\n\n" in text
    board.write_text(
        text.replace("## Messages\n\n", f"## Messages\n\n{heading}{body}\n\n---\n\n", 1),
        encoding="utf-8",
    )


def _forms(row) -> set[str]:
    forms = {row.session_uuid, row.compact_id, row.speakable_id}
    if row.legacy_id:
        forms.add(row.legacy_id)
    return forms


def test_durable_matching_ignores_age_and_gates_role() -> None:
    """The core contract: a durable project message reaches any owner or
    contributor seat for the project however old it is; any other role,
    any other project, or the plain (time-bounded) form does not match."""
    durable = PA.BoardMessage(
        recipient="project-b sessions [durable]",
        sender="s-1",
        timestamp="2020-01-01T00:00:00+00:00",
        body="x",
    )
    floor = "2026-09-21T12:00:00-04:00"
    assert PA.addressed_to(durable, {"s-2"}, "project-b", floor, "owner")
    assert PA.addressed_to(durable, {"s-2"}, "project-b", floor, "contributor")
    assert PA.addressed_to(durable, {"s-2"}, "project-b", floor, "OWNER")
    assert not PA.addressed_to(durable, {"s-2"}, "project-b", floor, "none")
    assert not PA.addressed_to(durable, {"s-2"}, "project-b", floor, "")
    assert not PA.addressed_to(durable, {"s-2"}, "project-c", floor, "owner")
    assert not PA.addressed_to(durable, {"s-2"}, "project-bb", floor, "owner")
    plain = PA.BoardMessage(
        recipient="project-b sessions",
        sender="s-1",
        timestamp="2020-01-01T00:00:00+00:00",
        body="x",
    )
    assert not PA.addressed_to(plain, {"s-2"}, "project-b", floor, "owner")


def test_durable_post_reaches_a_later_seat(tmp_path) -> None:
    board = tmp_path / "board.md"
    owner = _claim_role(board, "project-b", "owner", "b1")
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to="project-b", text="Handoff for whoever is next.", durable=True)
        )
        == 0
    )
    messages = PA.parse_messages(board.read_text(encoding="utf-8"))
    assert [m.recipient for m in messages] == ["project-b sessions [durable]"]
    successor = _claim_role(board, "project-b", "contributor", "b2")
    unread = PA.unread_messages(
        board.read_text(encoding="utf-8"),
        board=board,
        sender_key="cc:successor",
        identity_forms=_forms(successor),
        project="project-b",
        since=successor.started,
        role="contributor",
    )
    assert [m.body for m in unread] == ["Handoff for whoever is next."]
    PA.mark_seen(board, "cc:successor", {m.key for m in unread})
    assert (
        PA.unread_messages(
            board.read_text(encoding="utf-8"),
            board=board,
            sender_key="cc:successor",
            identity_forms=_forms(successor),
            project="project-b",
            since=successor.started,
            role="contributor",
        )
        == []
    )


def test_durable_outlives_seat_turnover_by_years(tmp_path) -> None:
    board = tmp_path / "board.md"
    _claim_role(board, "project-b", "owner", "b1")
    _ancient_durable(board, "project-b", "Ancient durable note.")
    successor = _claim_role(board, "project-b", "contributor", "b2")
    unread = PA.unread_messages(
        board.read_text(encoding="utf-8"),
        board=board,
        sender_key="cc:successor",
        identity_forms=_forms(successor),
        project="project-b",
        since=successor.started,
        role="contributor",
    )
    assert [m.body for m in unread] == ["Ancient durable note."]


def test_durable_refuses_seat_and_free_addresses(tmp_path, capsys) -> None:
    board = tmp_path / "board.md"
    owner = _claim_role(board, "project-b", "owner", "b1")
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to=owner.compact_id, text="x", durable=True)
        )
        == 10
    )
    assert "not a seat" in capsys.readouterr().err
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to="project-b", text="x", durable=True, free_address=True)
        )
        == 2
    )


def test_resolve_retires_durable_for_future_seats(tmp_path) -> None:
    board = tmp_path / "board.md"
    owner = _claim_role(board, "project-b", "owner", "b1")
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to="project-b", text="Do the thing.", durable=True)
        )
        == 0
    )
    key = PA.parse_messages(board.read_text(encoding="utf-8"))[0].key
    assert (
        ENGINE.command_message(args(board, sender=owner.compact_id, resolve=key[:12]))
        == 0
    )
    stored = (board.parent / "inbox" / "resolved.json").read_text(encoding="utf-8")
    assert key in stored and owner.compact_id in stored
    successor = _claim_role(board, "project-b", "contributor", "b2")
    assert (
        PA.unread_messages(
            board.read_text(encoding="utf-8"),
            board=board,
            sender_key="cc:successor",
            identity_forms=_forms(successor),
            project="project-b",
            since=successor.started,
            role="contributor",
        )
        == []
    )


def test_resolve_refuses_everything_but_owned_durable(tmp_path, capsys) -> None:
    board = tmp_path / "board.md"
    owner = _claim_role(board, "project-b", "owner", "b1")
    other = _claim_role(board, "project-c", "owner", "c1")
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to="project-b", text="Keep.", durable=True)
        )
        == 0
    )
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to="project-b", text="Ephemeral.")
        )
        == 0
    )
    keys = {m.body: m.key for m in PA.parse_messages(board.read_text(encoding="utf-8"))}
    assert ENGINE.command_message(args(board, sender=owner.compact_id, resolve="zzz-no-such-key")) == 10
    assert "no bus message matches" in capsys.readouterr().err
    assert ENGINE.command_message(args(board, sender=owner.compact_id, resolve=keys["Ephemeral."])) == 10
    assert "only durable project messages" in capsys.readouterr().err
    assert ENGINE.command_message(args(board, sender=other.compact_id, resolve=keys["Keep."])) == 10
    assert "message's project" in capsys.readouterr().err
    bystander = _claim_role(board, "project-b", "none", "b9")
    assert ENGINE.command_message(args(board, sender=bystander.compact_id, resolve=keys["Keep."])) == 10
    assert "owner or contributor" in capsys.readouterr().err
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, to="project-b", resolve=keys["Keep."])
        )
        == 2
    )
    assert (
        ENGINE.command_message(
            args(board, sender=owner.compact_id, text="x", resolve=keys["Keep."])
        )
        == 2
    )
    assert ENGINE.command_message(args(board, sender=owner.compact_id)) == 2


def test_inbox_command_surfaces_durable_for_owner(tmp_path, capsys) -> None:
    board = tmp_path / "board.md"
    owner = _claim_role(board, "project-b", "owner", "b1")
    _ancient_durable(board, "project-b", "Ancient durable note.")
    assert ENGINE.command_inbox(args(board, id=owner.compact_id)) == 0
    assert "Ancient durable note." in capsys.readouterr().out


def test_resolved_store_tolerates_garbage(tmp_path) -> None:
    board = tmp_path / "board.md"
    board.write_text("## Messages\n", encoding="utf-8")
    store = board.parent / "inbox" / "resolved.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text("{not json", encoding="utf-8")
    assert PA.resolved_keys(board) == set()
    PA.mark_resolved(board, "abc123", by="s-1")
    assert PA.resolved_keys(board) == {"abc123"}

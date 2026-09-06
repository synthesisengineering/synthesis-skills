"""Diagnostic inbox reads preserve delivery state and reject unverified input."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import board_inbox as INBOX  # noqa: E402
import coordination as ENGINE  # noqa: E402
import peer_addressing as PEER  # noqa: E402

NATIVE_ID = "11111111-1111-4111-8111-111111111111"
ENV = {"SYNTHESIS_CLIENT_SESSION_REF": f"codex:{NATIVE_ID}"}
PAYLOAD = {"session_id": NATIVE_ID, "hook_event_name": "SessionStart"}


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    board = tmp_path / "coordination" / "board.md"
    board.parent.mkdir()
    identity = ENGINE.new_identity()
    row = ENGINE.Session(
        **identity.__dict__, agent="agent", machine="machine", project="project-a",
        started="2026-01-01T00:00:00+00:00", heartbeat="2026-01-01T00:00:00+00:00",
        mode="interactive", workspaces=[f"{tmp_path}/workspace @ main"], goal="verify",
        claims=[str(tmp_path / "workspace")], context_role="owner", status="active",
        client_ref=ENV["SYNTHESIS_CLIENT_SESSION_REF"],
    )
    text = ENGINE.replace_table(ENGINE.template(), [row])
    messages = (
        f"### → {row.compact_id}, from sender-a — 2026-01-02T00:00:00+00:00\n\nDirect message.\n\n"
        "### → project-a sessions, from sender-a — 2026-01-02T00:00:01+00:00\n\nProject message.\n\n"
    )
    board.write_text(text.replace("## Messages\n\n", "## Messages\n\n" + messages), encoding="utf-8")
    PEER.write_seat(board, session_uuid=row.session_uuid, compact_id=row.compact_id,
                    machine="machine", identity=PEER.identity_from_hook(PAYLOAD, ENV))
    return board, row


def diagnostic(board):
    return INBOX.inbox_text(PAYLOAD, board=board, environ=ENV, mark=False, strict=True)


def snapshot(directory):
    return {str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in directory.rglob("*") if path.is_file()}


@pytest.mark.parametrize("existing_cursor", [False, True])
def test_repeated_diagnostic_inbox_keeps_messages_and_files(inbox, existing_cursor):
    board, _ = inbox
    if existing_cursor:
        PEER.mark_seen(board, ENV["SYNTHESIS_CLIENT_SESSION_REF"], {"unrelated"})
    before = snapshot(board.parent)
    first = diagnostic(board)
    second = diagnostic(board)
    assert first == second
    assert "2 unread message(s)" in first
    assert "Direct message." in first and "Project message." in first
    assert snapshot(board.parent) == before


def test_normal_lifecycle_still_delivers_and_marks_once(inbox):
    board, _ = inbox
    first = INBOX.inbox_text(PAYLOAD, board=board, environ=ENV)
    second = INBOX.inbox_text(PAYLOAD, board=board, environ=ENV)
    assert "2 unread message(s)" in first
    assert "unread message(s)" not in second
    assert len(PEER.seen_keys(board, ENV["SYNTHESIS_CLIENT_SESSION_REF"])) == 2


def test_diagnostic_reads_board_only_once(inbox, monkeypatch):
    board, _ = inbox
    read_text = Path.read_text
    count = 0

    def read(path, *args, **kwargs):
        nonlocal count
        if path == board:
            count += 1
            assert count == 1, "addressing and messages must use the same board snapshot"
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    assert "2 unread message(s)" in diagnostic(board)
    assert count == 1


@pytest.mark.parametrize("missing", ["board", "seats", "own-seat", "watermark"])
def test_absent_optional_state_is_healthy(inbox, missing):
    board, row = inbox
    if missing == "board":
        board.unlink()
    elif missing in {"seats", "own-seat"}:
        PEER.seat_path(board, row.session_uuid).unlink()
        if missing == "seats":
            PEER.seats_dir(board).rmdir()
    before = snapshot(board.parent)
    text = diagnostic(board)
    if missing == "watermark":
        assert "2 unread message(s)" in text
    else:
        assert "unread message(s)" not in text
    assert snapshot(board.parent) == before


@pytest.mark.parametrize("corruption", [
    "missing-messages", "missing-active", "invalid-schema", "newer-schema", "missing-schema",
    "bad-row-width", "garbage-row", "bad-row-identity", "bad-row-started", "duplicate-own-row",
])
def test_invalid_board_refuses_diagnostic(inbox, corruption):
    board, row = inbox
    text = board.read_text(encoding="utf-8")
    own_line = next(line for line in text.splitlines() if line.startswith(f"| {row.session_uuid} |"))
    replacements = {
        "missing-messages": ("## Messages", "## Other messages"),
        "missing-active": ("## Active sessions", "## Other sessions"),
        "invalid-schema": ("Schema: v4", "Schema: broken"),
        "newer-schema": ("Schema: v4", "Schema: v999"),
        "missing-schema": ("Schema: v4", ""),
        "bad-row-width": (own_line, "| broken | row |"),
        "garbage-row": (own_line, "unparseable active row"),
        "bad-row-identity": (row.compact_id, "s-invalid"),
        "bad-row-started": (row.started, "not-a-time"),
        "duplicate-own-row": (own_line, own_line + "\n" + own_line),
    }
    old, new = replacements[corruption]
    board.write_text(text.replace(old, new), encoding="utf-8")
    before = snapshot(board.parent)
    with pytest.raises(ValueError):
        diagnostic(board)
    assert snapshot(board.parent) == before


@pytest.mark.parametrize("corruption", ["json", "list", "schema", "field-type", "missing-field", "wrong-filename"])
def test_existing_malformed_seat_refuses_diagnostic(inbox, corruption):
    board, row = inbox
    seat_path = PEER.seat_path(board, row.session_uuid)
    data = json.loads(seat_path.read_text(encoding="utf-8"))
    if corruption == "json":
        text = "{"
    elif corruption == "list":
        text = "[]"
    else:
        if corruption == "schema":
            data["schema"] = 999
        elif corruption == "field-type":
            data["harness_session_id"] = []
        elif corruption == "missing-field":
            del data["machine"]
        else:
            data["session_uuid"] = "22222222-2222-4222-8222-222222222222"
        text = json.dumps(data)
    seat_path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        diagnostic(board)


def test_duplicate_matching_seats_refuse_diagnostic(inbox):
    board, _ = inbox
    identity = ENGINE.new_identity()
    PEER.write_seat(board, session_uuid=identity.session_uuid, compact_id=identity.compact_id,
                    machine="machine", identity=PEER.identity_from_hook(PAYLOAD, ENV))
    with pytest.raises(ValueError):
        diagnostic(board)


@pytest.mark.parametrize("data", ["{", "[]", "{}", '{"seen": "all"}', '{"seen": [1]}', '{"seen": [{}]}'])
def test_existing_malformed_own_watermark_refuses_diagnostic(inbox, data):
    board, _ = inbox
    path = PEER.watermark_path(board, ENV["SYNTHESIS_CLIENT_SESSION_REF"])
    path.parent.mkdir()
    path.write_text(data, encoding="utf-8")
    with pytest.raises(ValueError):
        diagnostic(board)


@pytest.mark.parametrize("dependency", ["board", "seat", "watermark"])
def test_unreadable_existing_dependency_refuses_diagnostic(inbox, monkeypatch, dependency):
    board, row = inbox
    watermark = PEER.watermark_path(board, ENV["SYNTHESIS_CLIENT_SESSION_REF"])
    PEER.mark_seen(board, ENV["SYNTHESIS_CLIENT_SESSION_REF"], {"unrelated"})
    target = {"board": board, "seat": PEER.seat_path(board, row.session_uuid), "watermark": watermark}[dependency]
    read_text = Path.read_text

    def read(path, *args, **kwargs):
        if path == target:
            raise PermissionError("fixture read denied")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    with pytest.raises(PermissionError):
        diagnostic(board)


def test_unreadable_seat_directory_refuses_diagnostic(inbox, monkeypatch):
    board, _ = inbox
    iterdir = Path.iterdir

    def entries(path):
        if path == PEER.seats_dir(board):
            raise PermissionError("fixture directory denied")
        return iterdir(path)

    monkeypatch.setattr(Path, "iterdir", entries)
    with pytest.raises(PermissionError):
        diagnostic(board)


@pytest.mark.parametrize("missing", ["seat", "identity"])
def test_invalid_board_not_hidden_by_missing_identity_or_seat(inbox, missing):
    board, row = inbox
    board.write_text("not a coordination board", encoding="utf-8")
    if missing == "seat":
        PEER.seat_path(board, row.session_uuid).unlink()
    with pytest.raises(ValueError):
        INBOX.inbox_text({} if missing == "identity" else PAYLOAD, board=board,
                         environ={} if missing == "identity" else ENV, mark=False, strict=True)

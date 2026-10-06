# SPDX-License-Identifier: Apache-2.0
"""The local message reader (E81 to E83). Synthetic SQLite only; no native app or personal path."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

import pytest

import local_messaging as lm
from local_messaging_fixtures import add, imessage, request


def run(path, tmp_path, **kw):
    page = request(path, **kw)
    page.setdefault("after", 0)
    page.setdefault("upper", None)
    return lm.run_page(page)


def hashes(root: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


# --- E81: read-only, pointers not payloads ---------------------------------------------------


def test_e81_wal_database_is_read_only_and_notes_hold_pointers_not_text(tmp_path, need_sandbox):
    path, writer = imessage(tmp_path / "source", wal=True)
    add(writer)
    before = hashes(path.parent)
    result = run(path, tmp_path)
    assert result["coverage"]["examined"] == 1
    note = result["notes"][0]
    assert note["class"] == "ask-candidate" and note["pointer"]["id"] == "fixture-0"
    assert note["untrusted_source"] is True
    assert "Can you review" not in json.dumps(result)  # never a copy of the conversation
    assert hashes(path.parent) == before
    assert result["confinement"] in ("macos-sandbox-exec", "linux-bubblewrap")
    writer.close()


def test_e81_unconfined_worker_refuses_before_sqlite_opens(tmp_path):
    path, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    before = hashes(path.parent)
    page = {**request(path), "after": 0, "upper": None}
    with pytest.raises(lm.Refused, match="confinement"):
        lm.read_page(page)
    assert hashes(path.parent) == before


@pytest.mark.parametrize("denial", [errno.EPERM, errno.EACCES, errno.EROFS])
def test_e81_confinement_probe_accepts_only_observed_write_denials(tmp_path, monkeypatch, denial):
    source = tmp_path.resolve() / "input.sqlite"
    inputs = [source, Path(str(source) + "-wal"), Path(str(source) + "-shm")]
    for item in inputs:
        item.write_bytes(b"synthetic")
    calls = []

    def denied(path, flags):
        calls.append(path)
        assert flags == os.O_WRONLY | os.O_NOFOLLOW
        raise OSError(denial, "synthetic denial")

    monkeypatch.setattr(lm.os, "open", denied)
    lm._require_confined(source)
    assert calls == inputs


@pytest.mark.parametrize("failure", [errno.EIO, errno.ENOENT, errno.ELOOP])
def test_e81_confinement_probe_keeps_unexpected_errors(tmp_path, monkeypatch, failure):
    source = tmp_path.resolve() / "input.sqlite"
    source.write_bytes(b"synthetic")
    unexpected = OSError(failure, "synthetic")
    monkeypatch.setattr(lm.os, "open", lambda path, flags: (_ for _ in ()).throw(unexpected))
    with pytest.raises(OSError) as error:
        lm._require_confined(source)
    assert error.value is unexpected


def test_e81_writable_input_refuses_and_closes_its_descriptor(tmp_path, monkeypatch):
    source = tmp_path.resolve() / "input.sqlite"
    source.write_bytes(b"synthetic")
    real_close, closed = lm.os.close, []
    monkeypatch.setattr(lm.os, "close", lambda fd: (closed.append(fd), real_close(fd)))
    with pytest.raises(lm.Refused, match="read-only confinement"):
        lm._require_confined(source)
    assert len(closed) == 1


# --- E82: skip rules --------------------------------------------------------------------------


def test_e82_excluded_chat_is_skipped_and_never_decoded(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    add(db, None, b"not a supported archive")
    db.close()
    result = run(path, tmp_path, excluded_chats=["synthetic-chat"])
    assert result["notes"] == [] and not result["coverage"]["gaps"]
    assert result["coverage"]["skipped"]["excluded-chat"] == 1


@pytest.mark.parametrize("text,reason", [
    ("Your verification code is 123456", "security-code"),
    ("Package delivered today", "delivery"),
    ("Sale today, unsubscribe now", "marketing"),
])
def test_e82_codes_deliveries_and_marketing_are_skipped(tmp_path, need_sandbox, text, reason):
    path, db = imessage(tmp_path / "source")
    add(db, text)
    db.close()
    result = run(path, tmp_path)
    assert result["notes"] == [] and result["coverage"]["skipped"][reason] == 1


def test_e82_short_codes_and_reactions_are_skipped(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    db.execute("insert into handle values('72345')")
    db.commit()
    add(db, "Reply STOP to end?", handle=2)
    add(db, "Loved an image", reaction=2000)
    db.close()
    result = run(path, tmp_path)
    assert result["notes"] == []
    assert result["coverage"]["skipped"] == {"short-code": 1, "reaction": 1}


def test_e82_group_needs_the_exact_self_name_not_a_generic_you(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    db.execute("insert into handle values('+15559876543')")
    db.execute("insert into chat_handle_join values(1, 2)")
    db.commit()
    add(db, "Can you review?")
    add(db, "Sample User, can you review?")
    db.close()
    result = run(path, tmp_path)
    assert len(result["notes"]) == 1
    assert result["coverage"]["skipped"]["group-not-addressed"] == 1


# --- E83: gaps are reported and hold the window -----------------------------------------------


def test_e83_unsupported_body_is_a_gap_not_an_empty_success(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    add(db, None, b"bad")
    db.close()
    result = run(path, tmp_path)
    assert result["coverage"]["gaps"] and not result["coverage"]["complete"]


def test_e83_a_gap_does_not_advance_the_window(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    add(db, None, b"bad")
    db.close()
    state = tmp_path / "state"
    first = lm.scan(request(path), state)
    assert first["coverage"]["gaps"]
    assert not (state / "cursor.json").exists()
    assert lm.scan(request(path), state)["coverage"]["gaps"] == first["coverage"]["gaps"]


def test_e83_pages_advance_only_after_saving_and_a_complete_window_replays(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    for _ in range(3):
        add(db)
    db.close()
    state = tmp_path / "state"
    first, second = lm.scan(request(path), state), lm.scan(request(path), state)
    assert first["coverage"]["after"] == 2 and not first["coverage"]["complete"]
    assert second["coverage"]["after"] == 3 and second["coverage"]["complete"]
    assert lm.scan(request(path), state) == second
    assert len(list(state.glob("page-*.json"))) == 2
    with pytest.raises(lm.Refused, match="another window"):
        lm.scan(request(path, end="2001-01-03T00:00:00Z"), state)


def test_e83_interrupted_cursor_write_rereads_the_same_page(tmp_path, monkeypatch, need_sandbox):
    path, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    state, original = tmp_path / "state", lm._write

    def crash(target, value):
        if target.name == "cursor.json":
            raise RuntimeError("synthetic interruption")
        return original(target, value)

    monkeypatch.setattr(lm, "_write", crash)
    with pytest.raises(RuntimeError):
        lm.scan(request(path), state)
    saved = json.loads(next(state.glob("page-*.json")).read_text())
    monkeypatch.setattr(lm, "_write", original)
    assert lm.scan(request(path), state) == saved


def test_replaced_database_refuses_the_old_window_state(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    for _ in range(3):
        add(db)
    db.close()
    state = tmp_path / "state"
    lm.scan(request(path), state)
    copy = path.with_name("copy.sqlite")
    shutil.copyfile(path, copy)
    os.replace(copy, path)  # same path, new file: retained pages describe the old one
    with pytest.raises(lm.Refused, match="another window or database"):
        lm.scan(request(path), state)


def test_state_is_one_reader_at_a_time_and_never_adopts_foreign_files(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("keep")
    with pytest.raises(lm.Refused, match="did not write"):
        lm.scan(request(path), foreign)
    assert (foreign / "notes.txt").read_text() == "keep"
    import fcntl
    state = tmp_path / "state"
    state.mkdir()
    with open(state / ".lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(lm.Refused, match="busy"):
            lm.scan(request(path), state)


# --- schema, window and decoding --------------------------------------------------------------


def test_whatsapp_reads_its_own_explicit_schema(tmp_path, need_sandbox):
    import sqlite3
    path = tmp_path / "wa.sqlite"
    db = sqlite3.connect(path)
    db.executescript("""create table ZWACHATSESSION(Z_PK integer primary key, ZCONTACTJID text, ZSESSIONTYPE integer);
    create table ZWAMESSAGE(Z_PK integer primary key, ZSTANZAID text, ZTEXT text, ZMESSAGEDATE real, ZISFROMME integer,
      ZFROMJID text, ZCHATSESSION integer, ZMESSAGETYPE integer);
    insert into ZWACHATSESSION values(1, 'synthetic@s.whatsapp.net', 0);
    insert into ZWAMESSAGE values(1, 'msg-1', 'Can you review?', 86400, 0, 'synthetic@s.whatsapp.net', 1, 0);""")
    db.close()
    assert len(run(path, tmp_path, adapter="whatsapp-v1")["notes"]) == 1


def test_window_selection_does_not_page_through_unrelated_history(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    for day in range(-10, 0):
        add(db, "historical?", day=day)
    add(db, "selected?", day=1)
    db.close()
    result = run(path, tmp_path)
    assert result["coverage"]["examined"] == 1 and result["coverage"]["complete"]
    assert result["notes"][0]["pointer"]["row"] == 11


def test_unknown_schema_symlinks_and_malformed_dates_refuse(tmp_path, need_sandbox):
    import sqlite3
    bad = tmp_path / "bad.sqlite"
    sqlite3.connect(bad).close()
    with pytest.raises(lm.Refused):
        run(bad, tmp_path)
    alias = tmp_path / "alias.sqlite"
    alias.symlink_to(bad)
    with pytest.raises(lm.Refused, match="symlink"):
        run(alias, tmp_path)
    path, db = imessage(tmp_path / "source")
    add(db)
    db.execute("update message set date='unknown'")
    db.commit()
    db.close()
    with pytest.raises(lm.Refused, match="date"):
        run(path, tmp_path)


@pytest.mark.parametrize("key,value", [("schema", True), ("page_size", 0), ("page_size", 101), ("database", None),
                                       ("adapter", "sms-v1"), ("end", "2003-01-01T00:00:00Z"), ("start", "2001-01-01")])
def test_request_grammar_refuses_before_any_worker(tmp_path, key, value):
    path, db = imessage(tmp_path / "source")
    db.close()
    with pytest.raises(lm.Refused):
        lm.scan(request(path, **{key: value}), tmp_path / "state")
    assert not (tmp_path / "state").exists()


def test_attributed_body_decodes_one_string_and_nothing_else():
    body = plistlib.dumps({"$archiver": "NSKeyedArchiver", "$version": 100000, "$top": {"root": plistlib.UID(1)},
                           "$objects": ["$null", {"NSString": plistlib.UID(2)}, "Synthetic question?"]},
                          fmt=plistlib.FMT_BINARY)
    assert lm.decode_body(None, body) == "Synthetic question?"
    with pytest.raises(lm.Refused):
        lm.decode_body(None, b"\x80\x04cos\nsystem\n")
    with pytest.raises(lm.Refused, match="object count"):
        lm.decode_body(None, b"bplist00" + b"0" * 32)


@pytest.mark.parametrize("blob", [b"x" * (256 * 1024 + 1), b"\x04\x0bstreamtyped", b""])
def test_unsupported_or_oversized_bodies_refuse(blob):
    with pytest.raises(lm.Refused):
        lm.decode_body(None, blob)


# --- the command line, under this Python and Apple's -------------------------------------------


@pytest.mark.parametrize("python", [sys.executable, "/usr/bin/python3"])
def test_command_line_reads_and_saves_a_page(tmp_path, need_sandbox, python):
    if not Path(python).exists():
        pytest.skip(f"{python} is not on this host")
    path, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    req = tmp_path / "request.json"
    req.write_text(json.dumps(request(path)))
    done = subprocess.run([python, "-B", str(Path(lm.__file__)), "--request", str(req), "--state", str(tmp_path / "state")],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["coverage"]["complete"]
    assert list((tmp_path / "state").glob("page-*.json"))
    refused = subprocess.run([python, "-B", str(Path(lm.__file__)), "--request", str(req)],
                             capture_output=True, text=True, timeout=60)
    assert refused.returncode == 2 and json.loads(refused.stdout)["status"] == "REFUSED"

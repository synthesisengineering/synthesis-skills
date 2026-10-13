# SPDX-License-Identifier: Apache-2.0
"""The local message reader (E81 to E83, and the reported gaps of 2026-10-08 and 2026-10-13). Synthetic
SQLite only; no native app or personal path."""

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
from local_messaging_fixtures import TYPEDSTREAM, add, approve, imessage, request

LINK = "com.apple.messages.URLBalloonProvider"  # the iMessage schema's balloon_bundle_id for a rich link
UNDECODED = "unsupported attributedBody encoding; typedstream is not unarchived"


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


# --- an unjoined outgoing row belongs to its recipient's one-to-one chat ----------------------


def test_unjoined_outgoing_row_takes_its_handles_one_to_one_chat(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    row = add(db, "I will send the plan tomorrow.", mine=1, join=False)
    add(db, "I will send it later.", mine=1, join=False, day=-3)  # outside the window, as for any message
    db.close()
    result = run(path, tmp_path)
    coverage = result["coverage"]
    assert coverage["gaps"] == [] and coverage["complete"] and coverage["by_handle"] == [row]
    assert coverage["examined"] == 1
    assert result["notes"][0]["pointer"]["chat"] == "synthetic-chat"
    assert result["notes"][0]["class"] == "promise-candidate"
    excluded = run(path, tmp_path, excluded_chats=["synthetic-chat"])["coverage"]
    assert excluded["skipped"] == {"excluded-chat": 1} and excluded["gaps"] == [] and excluded["complete"]


@pytest.mark.parametrize("setup,count", [("no chat", 0), ("group only", 0), ("two direct chats", 2)])
def test_unjoined_outgoing_row_without_exactly_one_direct_chat_stays_a_gap(tmp_path, need_sandbox, setup, count):
    path, db = imessage(tmp_path / "source")
    if setup == "no chat":
        db.execute("delete from chat_handle_join")
    elif setup == "group only":  # the handle's only chat has another member
        db.execute("insert into handle values('+15559876543')")
        db.execute("insert into chat_handle_join values(1, 2)")
    else:
        db.execute("insert into chat values('synthetic-chat-2')")
        db.execute("insert into chat_handle_join values(2, 1)")
    db.commit()
    outgoing = add(db, "I will send the plan tomorrow.", mine=1, join=False)
    incoming = add(db, "Can you send the plan?", join=False)  # a sender's handle does not name the chat
    db.close()
    coverage = run(path, tmp_path)["coverage"]
    assert coverage["gaps"] == [
        {"row": outgoing, "reason": f"ambiguous chat attribution: unjoined outgoing row; {count} one-to-one chats with its handle"},
        {"row": incoming, "reason": "ambiguous chat attribution"}]
    assert not coverage["complete"] and coverage["by_handle"] == []


# --- a link or attachment row the decoder cannot read carries a marker ------------------------


def test_undecodable_link_and_attachment_rows_carry_a_marker_and_do_not_hold_the_window(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    photo = add(db, None, TYPEDSTREAM, attachments=["image/jpeg"])
    link = add(db, None, TYPEDSTREAM, balloon=LINK, attachments=[None])  # a rich link's payload attachment has no type
    odd = add(db, None, TYPEDSTREAM, attachments=[None, "not a\nmime type"])
    group = add(db, None, TYPEDSTREAM, attachments=["video/quicktime"], chat=2)
    db.executescript("insert into chat values('synthetic-group'); insert into handle values('+15559876543');"
                     "insert into chat_handle_join values(2, 1); insert into chat_handle_join values(2, 2);")
    db.close()
    result = run(path, tmp_path, page_size=4)
    coverage = result["coverage"]
    assert coverage["gaps"] == [] and coverage["complete"] and result["notes"] == []
    assert coverage["marked"] == [{"row": photo, "marker": "[attachment: image/jpeg]"}, {"row": link, "marker": "[link]"},
                                  {"row": odd, "marker": "[attachment: unknown type, unknown type]"},
                                  {"row": group, "marker": "[attachment: video/quicktime]"}]
    assert coverage["skipped"] == {"no-deterministic-candidate": 3, "group-not-addressed": 1}


def test_a_row_whose_text_is_genuinely_unreadable_still_holds_the_window(tmp_path, need_sandbox):
    path, db = imessage(tmp_path / "source")
    plain = add(db, None, TYPEDSTREAM)  # no attachment and no link: its text is all the row holds
    flagged = add(db, None, TYPEDSTREAM, media=1)  # flagged as media, but no attachment row names one
    malformed = add(db, None, b"bplist00" + b"0" * 32, attachments=["image/png"])  # a bound, not an encoding
    db.close()
    coverage = run(path, tmp_path, page_size=3)["coverage"]
    assert [g["row"] for g in coverage["gaps"]] == [plain, flagged, malformed]
    assert coverage["gaps"][0]["reason"] == UNDECODED and coverage["marked"] == []


# --- a by-hand review the principal approves closes exactly the gaps it names -----------------


@pytest.fixture
def principal(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))  # the session's transcript lives here
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-reader")


def test_a_principal_approved_review_closes_the_gaps_it_names_and_is_recorded(tmp_path, need_sandbox, principal, capsys):
    path, db = imessage(tmp_path / "source")
    held = add(db, None, TYPEDSTREAM)
    add(db)
    db.close()
    state, review = tmp_path / "state", {"rows": [{"row": held, "reason": UNDECODED}]}
    files = {"request.json": request(path), "review.json": review}
    for name, value in files.items():
        (tmp_path / name).write_text(json.dumps(value))
    assert lm.main(["--request", str(tmp_path / "request.json"), "--state", str(state),
                    "--review", str(tmp_path / "review.json")]) == 2
    asked = json.loads(capsys.readouterr().out)
    assert asked["status"] == "REFUSED" and "approval of this review" in asked["reason"]
    assert not (state / "cursor.json").exists()
    approve(asked["reason"])
    page = lm.scan(request(path), state, review)
    assert page["coverage"]["reviewed"] == review["rows"] and page["coverage"]["gaps"] == []
    assert page["coverage"]["complete"] and len(page["notes"]) == 1
    assert json.loads(next(state.glob("page-*.json")).read_text())["coverage"]["reviewed"] == review["rows"]
    assert json.loads((state / "cursor.json").read_text())["complete"]


def test_a_review_names_exactly_the_pages_gaps_and_a_grant_alone_closes_nothing(tmp_path, need_sandbox, principal):
    path, db = imessage(tmp_path / "source")
    held = add(db, None, TYPEDSTREAM)
    db.close()
    state = tmp_path / "state"
    for wrong in ({"rows": [{"row": held, "reason": "another reason"}]}, {"rows": []}, [held],
                  {"rows": [{"row": held, "reason": UNDECODED}, {"row": held + 1, "reason": UNDECODED}]},
                  {"rows": [{"row": True, "reason": UNDECODED}]}, {"rows": [{"row": held, "reason": UNDECODED}], "x": 1}):
        with pytest.raises(lm.Refused, match="exactly this page's gaps"):
            lm.scan(request(path), state, wrong)
    from synthesis import approvals
    assert approvals.pending() == []  # nothing was put to the principal
    review = {"rows": [{"row": held, "reason": UNDECODED}]}
    with pytest.raises(lm.Refused, match="approval") as asked:
        lm.scan(request(path), state, review)
    approve(str(asked.value), typed=False)  # a grant written without the principal's own prompt behind it
    with pytest.raises(PermissionError, match="only from the principal"):
        lm.scan(request(path), state, review)
    assert not (state / "cursor.json").exists() and not list(state.glob("page-*.json"))


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

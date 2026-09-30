# SPDX-License-Identifier: Apache-2.0
"""Synthetic local SQLite only. No native app, account, or personal path."""

import hashlib
import json
import plistlib
import sqlite3
from pathlib import Path

import pytest

import local_messaging as lm


def imessage(root, wal=False):
    root.mkdir()
    p = root / "messages.sqlite"
    db = sqlite3.connect(p)
    if wal:
        db.execute("pragma journal_mode=WAL")
    db.executescript("""
      create table message(guid text, text text, attributedBody blob,
        date integer, is_from_me integer, handle_id integer,
        associated_message_type integer, cache_has_attachments integer);
      create table handle(id text);
      create table chat(chat_identifier text);
      create table chat_message_join(chat_id integer,message_id integer);
      create table chat_handle_join(chat_id integer,handle_id integer);
      insert into handle values('+15551234567');
      insert into chat values('synthetic-chat');
      insert into chat_handle_join values(1,1);
    """)
    db.commit()
    return p, db


def add(db, text="Can you review the plan?", body=None, day=1, **kw):
    row = (
        "fixture-" + str(db.execute("select count(*) from message").fetchone()[0]),
        text,
        body,
        day * 86400 * 10**9,
        kw.get("mine", 0),
        1,
        kw.get("reaction", 0),
        kw.get("media", 0),
    )
    n = db.execute("insert into message values(?,?,?,?,?,?,?,?)", row).lastrowid
    db.execute("insert into chat_message_join values(1,?)", (n,))
    db.commit()
    return n


def request(p, **kw):
    return dict(
        schema=1,
        adapter="imessage-v1",
        database=str(p),
        start="2001-01-01T00:00:00Z",
        end="2001-02-01T00:00:00Z",
        page_size=2,
        after=0,
        upper=None,
        excluded_chats=[],
        self_names=["Sample User"],
        **kw,
    )


def run(p, tmp_path, **kw):
    home = tmp_path / ("worker-" + str(len(list(tmp_path.glob("worker-*")))))
    return lm.run_page(request(p, **kw), home)


def hashes(root):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.iterdir()
        if p.is_file()
    }


def test_wal_current_and_no_input_writes(tmp_path):
    p, writer = imessage(tmp_path / "source", True)
    add(writer)
    before = hashes(p.parent)
    result = run(p, tmp_path)
    assert result["coverage"]["examined"] == 1
    assert result["notes"][0]["class"] == "ask-candidate"
    assert result["notes"][0]["pointer"]["id"] == "fixture-0"
    assert "Can you review" not in json.dumps(result)
    assert hashes(p.parent) == before
    writer.close()


def test_readonly_not_immutable_while_writer_progresses(tmp_path):
    p, writer = imessage(tmp_path / "source", True)
    add(writer)
    first = run(p, tmp_path)
    add(writer, "Please review another item?")
    second = run(p, tmp_path)
    assert first["coverage"]["upper"] == 1
    assert second["coverage"]["upper"] == 2
    writer.close()


def test_plain_page_window_and_no_corpus_dump(tmp_path):
    p, db = imessage(tmp_path / "source")
    for text in ["one?", "two?", "three?"]:
        add(db, text)
    db.close()
    result = run(p, tmp_path)
    assert result["coverage"]["examined"] == 2
    assert not result["coverage"]["complete"]
    r = request(p)
    r.update(after=2, upper=3)
    final = lm.run_page(r, tmp_path / "worker-final")
    assert final["coverage"]["complete"]
    assert final["coverage"]["examined"] == 1


def test_excluded_chat_body_is_not_decoded(tmp_path):
    p, db = imessage(tmp_path / "source")
    add(db, None, b"not a supported archive")
    db.close()
    r = request(p)
    r["excluded_chats"] = ["synthetic-chat"]
    result = lm.run_page(r, tmp_path / "worker")
    assert result["notes"] == []
    assert result["coverage"]["skipped"]["excluded-chat"] == 1
    assert not result["coverage"]["gaps"]


@pytest.mark.parametrize(
    "text,reason",
    [
        ("Your verification code is 123456", "security-code"),
        ("Package delivered today", "delivery"),
        ("Sale today, unsubscribe now", "marketing"),
    ],
)
def test_conservative_skips(tmp_path, text, reason):
    p, db = imessage(tmp_path / "source")
    add(db, text)
    db.close()
    result = run(p, tmp_path)
    assert result["notes"] == []
    assert result["coverage"]["skipped"][reason] == 1


def test_group_requires_exact_name_not_generic_you(tmp_path):
    p, db = imessage(tmp_path / "source")
    db.execute("insert into handle values('+15559876543')")
    db.execute("insert into chat_handle_join values(1,2)")
    db.commit()
    add(db, "Can you review?")
    add(db, "Sample User, can you review?")
    db.close()
    result = run(p, tmp_path)
    assert len(result["notes"]) == 1
    assert result["coverage"]["skipped"]["group-not-addressed"] == 1


def test_unsupported_body_does_not_become_empty_success(tmp_path):
    p, db = imessage(tmp_path / "source")
    add(db, None, b"bad")
    db.close()
    result = run(p, tmp_path)
    assert result["coverage"]["gaps"]
    assert not result["coverage"]["complete"]


def test_safe_plist_string_and_no_object_execution():
    body = plistlib.dumps(
        {
            "$archiver": "NSKeyedArchiver",
            "$version": 100000,
            "$top": {"root": plistlib.UID(1)},
            "$objects": ["$null", {"NSString": plistlib.UID(2)}, "Synthetic question?"],
        },
        fmt=plistlib.FMT_BINARY,
    )
    assert lm.decode_body(None, body) == "Synthetic question?"
    with pytest.raises(lm.Refused):
        lm.decode_body(None, b"\x80\x04cos\nsystem\n")


@pytest.mark.parametrize("blob", [b"x" * (256 * 1024 + 1), b"\x04\x0bstreamtyped", b""])
def test_unsupported_or_oversized_decode(blob):
    with pytest.raises(lm.Refused):
        lm.decode_body(None, blob)


def test_bad_schema_and_symlink_refuse(tmp_path):
    p = tmp_path / "bad.sqlite"
    sqlite3.connect(p).close()
    with pytest.raises(lm.Refused):
        run(p, tmp_path)
    q = tmp_path / "alias.sqlite"
    q.symlink_to(p)
    with pytest.raises(lm.Refused):
        run(q, tmp_path)


def test_direct_unconfined_worker_refuses_before_sqlite(tmp_path):
    p, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    before = hashes(p.parent)
    with pytest.raises(lm.Refused, match="confinement"):
        lm.read_page(request(p))
    assert hashes(p.parent) == before


def test_watermark_replay_and_no_overwrite(tmp_path):
    p, db = imessage(tmp_path / "source")
    add(db)
    add(db)
    add(db)
    db.close()
    state = tmp_path / "state"
    first = lm.scan(request(p), state)
    second = lm.scan(request(p), state)
    assert first["coverage"]["after"] == 2
    assert second["coverage"]["after"] == 3
    assert second["coverage"]["complete"]
    assert lm.scan(request(p), state) == second
    changed = request(p)
    changed["end"] = "2001-01-03T00:00:00Z"
    with pytest.raises(lm.Refused):
        lm.scan(changed, state)


def test_gap_does_not_advance_watermark(tmp_path):
    p, db = imessage(tmp_path / "source")
    add(db, None, b"bad")
    db.close()
    state = tmp_path / "state"
    result = lm.scan(request(p), state)
    assert result["coverage"]["gaps"]
    assert not (state / "checkpoint.json").exists()


def test_whatsapp_explicit_schema(tmp_path):
    p = tmp_path / "wa.sqlite"
    db = sqlite3.connect(p)
    db.executescript("""create table ZWACHATSESSION(Z_PK integer primary key,ZCONTACTJID text,ZSESSIONTYPE integer);
    create table ZWAMESSAGE(Z_PK integer primary key,ZSTANZAID text,ZTEXT text,ZMESSAGEDATE real,ZISFROMME integer,ZFROMJID text,ZCHATSESSION integer,ZMESSAGETYPE integer);
    insert into ZWACHATSESSION values(1,'synthetic@s.whatsapp.net',0);
    insert into ZWAMESSAGE values(1,'msg-1','Can you review?',86400,0,'synthetic@s.whatsapp.net',1,0);""")
    db.close()
    r = request(p)
    r["adapter"] = "whatsapp-v1"
    result = lm.run_page(r, tmp_path / "worker")
    assert len(result["notes"]) == 1


def test_wal_uncommitted_writer_does_not_leak_partial_result(tmp_path):
    p, writer = imessage(tmp_path / "source", True)
    add(writer)
    writer.execute("begin immediate")
    writer.execute("update message set text='uncommitted secret?' where ROWID=1")
    before = hashes(p.parent)
    result = run(p, tmp_path)
    assert result["coverage"]["examined"] == 1 and result["coverage"]["complete"]
    assert hashes(p.parent) == before
    writer.rollback()
    writer.close()


def test_binary_plist_allocation_header_bound():
    with pytest.raises(lm.Refused, match="object count"):
        lm.decode_body(None, b"bplist00" + b"0" * 32)


def test_state_symlink_and_foreign_content_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("retain")
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    with pytest.raises(lm.Refused):
        with lm.state_lock(alias):
            pass
    home = tmp_path / "owned"
    home.mkdir(mode=0o700)
    (home / "foreign").write_text("keep")
    p, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    with pytest.raises(lm.Refused):
        lm.scan(request(p), home)
    assert sentinel.read_text() == "retain" and (home / "foreign").read_text() == "keep"


def test_crash_after_page_persist_before_cursor_retry(tmp_path, monkeypatch):
    p, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    home = tmp_path / "state"
    original = lm.atomic_state

    def crash(home, name, value):
        if name == "checkpoint.json":
            raise RuntimeError("synthetic interruption")
        return original(home, name, value)

    monkeypatch.setattr(lm, "atomic_state", crash)
    with pytest.raises(RuntimeError):
        lm.scan(request(p), home)
    receipts = list(home.glob("page-*.json"))
    assert len(receipts) == 1
    expected = json.loads(receipts[0].read_text())
    monkeypatch.setattr(lm, "atomic_state", original)
    assert lm.scan(request(p), home) == expected


def test_busy_state_does_not_enter_another_owner(tmp_path):
    with lm.state_lock(tmp_path / "state"):
        with pytest.raises(lm.Refused, match="busy"):
            with lm.state_lock(tmp_path / "state"):
                pass


def test_state_parent_swap_never_writes_replacement(tmp_path):
    home = tmp_path / "state"
    moved = tmp_path / "moved"
    outside = tmp_path / "outside"
    outside.mkdir()
    with lm.state_lock(home) as owned:
        home.rename(moved)
        home.symlink_to(outside, target_is_directory=True)
        with pytest.raises(lm.Refused):
            lm.atomic_state(owned, "marker.json", {"value": 1})
    assert list(outside.iterdir()) == []


def test_read_caused_access_time_change_is_not_source_mutation(tmp_path):
    import os

    p = tmp_path / "input.json"
    p.write_text('{"value":1}')
    os.utime(p, ns=(1, p.stat().st_mtime_ns))
    assert lm.file_json(p) == {"value": 1}


def test_pagination_refuses_changed_source_generation(tmp_path):
    p, db = imessage(tmp_path / "source", True)
    add(db)
    add(db)
    add(db)
    state = tmp_path / "state"
    lm.scan(request(p), state)
    before = (state / "checkpoint.json").read_bytes()
    db.execute("update message set text='changed?' where ROWID=3")
    db.commit()
    with pytest.raises(lm.Refused, match="generation"):
        lm.scan(request(p), state)
    assert (state / "checkpoint.json").read_bytes() == before
    db.close()


def test_completed_window_is_historical_when_database_grows(tmp_path):
    p, db = imessage(tmp_path / "source", True)
    add(db)
    home = tmp_path / "state"
    lm.scan(request(p), home)
    add(db)
    with pytest.raises(lm.Refused, match="generation"):
        lm.scan(request(p), home)
    db.close()


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", True),
        ("after", True),
        ("upper", 2**80),
        ("after", 2**80),
        ("database", None),
    ],
)
def test_request_grammar_refuses_before_worker(tmp_path, key, value):
    p, db = imessage(tmp_path / "source")
    db.close()
    r = request(p)
    r[key] = value
    with pytest.raises(lm.Refused):
        lm.run_page(r, tmp_path / "worker")
    assert not (tmp_path / "worker").exists()


def test_cli_actual_owner_path(tmp_path):
    import sys

    p, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    req = tmp_path / "request.json"
    req.write_text(json.dumps(request(p)))
    owner = lm.existing_owner("synthesis-project-management", "coordination_process")
    completed = owner.run(
        [
            sys.executable,
            "-B",
            str(Path(lm.__file__)),
            "--request",
            str(req),
            "--state",
            str(tmp_path / "state"),
        ],
        cwd=tmp_path,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stdout
    page = json.loads(completed.stdout)
    assert page["coverage"]["complete"]
    assert list((tmp_path / "state").glob("page-*.json"))


def test_confined_input_metadata_preserved(tmp_path):
    p, db = imessage(tmp_path / "source", True)
    add(db)
    before = {x.name: lm.stable_stat(x.stat()) for x in p.parent.iterdir()}
    run(p, tmp_path)
    after = {x.name: lm.stable_stat(x.stat()) for x in p.parent.iterdir()}
    assert before == after
    db.close()


@pytest.mark.parametrize("member", ["reader.py", "request.json"])
def test_late_worker_input_replacement_cannot_execute_or_select_new_source(
    tmp_path, monkeypatch, member
):
    p, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    owner = lm.existing_owner("synthesis-project-management", "coordination_process")
    original = owner.run
    effect = tmp_path / "worker" / "unapproved"

    def tamper(command, **kw):
        target = Path(kw["cwd"]) / member
        target.chmod(0o600)
        if member == "reader.py":
            target.write_text(
                "from pathlib import Path\nPath('unapproved').write_text('effect')\n"
            )
        else:
            changed = request(p)
            changed["excluded_chats"] = ["synthetic-chat"]
            target.write_text(json.dumps(changed))
        return original(command, **kw)

    monkeypatch.setattr(owner, "run", tamper)
    with pytest.raises(lm.Refused):
        lm.run_page(request(p), tmp_path / "worker")
    assert not effect.exists()


def test_window_selection_does_not_page_through_unrelated_history(tmp_path):
    p, db = imessage(tmp_path / "source")
    for day in range(-10, 0):
        add(db, "historical?", day=day)
    add(db, "selected?", day=1)
    db.close()
    result = run(p, tmp_path)
    assert result["coverage"]["examined"] == 1 and result["coverage"]["complete"]
    assert result["notes"][0]["pointer"]["row"] == 11


def test_malformed_timestamp_cannot_hide_coverage(tmp_path):
    p, db = imessage(tmp_path / "source")
    add(db)
    db.execute("update message set date='unknown'")
    db.commit()
    db.close()
    with pytest.raises(lm.Refused, match="date"):
        run(p, tmp_path)

# SPDX-License-Identifier: Apache-2.0
"""Synthetic Messages-shaped SQLite databases for the reader tests, and the principal's approval."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sqlite3

TYPEDSTREAM = b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84"  # a header the reader does not unarchive


def imessage(root: Path, wal: bool = False):
    root.mkdir()
    path = root / "messages.sqlite"
    db = sqlite3.connect(path)
    if wal:
        db.execute("pragma journal_mode=WAL")
    db.executescript("""
      create table message(guid text, text text, attributedBody blob, date integer, is_from_me integer,
        handle_id integer, associated_message_type integer, cache_has_attachments integer, balloon_bundle_id text);
      create table handle(id text);
      create table chat(chat_identifier text);
      create table chat_message_join(chat_id integer, message_id integer);
      create table chat_handle_join(chat_id integer, handle_id integer);
      create table attachment(mime_type text);
      create table message_attachment_join(message_id integer, attachment_id integer);
      insert into handle values('+15551234567');
      insert into chat values('synthetic-chat');
      insert into chat_handle_join values(1, 1);
    """)
    db.commit()
    return path, db


def add(db, text="Can you review the plan?", body=None, day=1, **kw):
    """One message row, joined to chat 1 unless join=False; attachments=[mime, ...] adds attachment rows."""
    row = ("fixture-" + str(db.execute("select count(*) from message").fetchone()[0]), text, body,
           day * 86400 * 10**9, kw.get("mine", 0), kw.get("handle", 1), kw.get("reaction", 0),
           kw.get("media", 1 if kw.get("attachments") else 0), kw.get("balloon"))
    rowid = db.execute("insert into message values(?,?,?,?,?,?,?,?,?)", row).lastrowid
    if kw.get("join", True):
        db.execute("insert into chat_message_join values(?, ?)", (kw.get("chat", 1), rowid))
    for mime in kw.get("attachments", ()):
        attachment = db.execute("insert into attachment values(?)", (mime,)).lastrowid
        db.execute("insert into message_attachment_join values(?, ?)", (rowid, attachment))
    db.commit()
    return rowid


def request(path, **kw):
    value = dict(schema=1, adapter="imessage-v1", database=str(path), start="2001-01-01T00:00:00Z",
                 end="2001-02-01T00:00:00Z", page_size=2, excluded_chats=[], self_names=["Sample User"])
    value.update(kw)
    return value


def approve(reason: str, typed: bool = True) -> None:
    """The principal types the code shown in `reason`; the harness records that prompt in the session's
    transcript (unless typed=False) and the prompt hook grants it. Needs CLAUDE_CONFIG_DIR and
    SYNTHESIS_SESSION set to a test folder and session."""
    code = re.search(r"\bcode ([a-z0-9]{6})", reason).group(1)
    if typed:
        record = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "-work" / (os.environ["SYNTHESIS_SESSION"] + ".jsonl")
        record.parent.mkdir(parents=True, exist_ok=True)
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=1)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when,
                                     "message": {"role": "user", "content": f"please approve {code}"}}) + "\n")
    from synthesis import approvals
    assert approvals.grant_from_prompt(f"please approve {code}")

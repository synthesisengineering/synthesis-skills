# SPDX-License-Identifier: Apache-2.0
"""Synthetic Messages-shaped SQLite databases for the reader tests."""

from __future__ import annotations

from pathlib import Path
import sqlite3


def imessage(root: Path, wal: bool = False):
    root.mkdir()
    path = root / "messages.sqlite"
    db = sqlite3.connect(path)
    if wal:
        db.execute("pragma journal_mode=WAL")
    db.executescript("""
      create table message(guid text, text text, attributedBody blob, date integer, is_from_me integer,
        handle_id integer, associated_message_type integer, cache_has_attachments integer);
      create table handle(id text);
      create table chat(chat_identifier text);
      create table chat_message_join(chat_id integer, message_id integer);
      create table chat_handle_join(chat_id integer, handle_id integer);
      insert into handle values('+15551234567');
      insert into chat values('synthetic-chat');
      insert into chat_handle_join values(1, 1);
    """)
    db.commit()
    return path, db


def add(db, text="Can you review the plan?", body=None, day=1, **kw):
    row = ("fixture-" + str(db.execute("select count(*) from message").fetchone()[0]), text, body,
           day * 86400 * 10**9, kw.get("mine", 0), kw.get("handle", 1), kw.get("reaction", 0), kw.get("media", 0))
    rowid = db.execute("insert into message values(?,?,?,?,?,?,?,?)", row).lastrowid
    db.execute("insert into chat_message_join values(1, ?)", (rowid,))
    db.commit()
    return rowid


def request(path, **kw):
    value = dict(schema=1, adapter="imessage-v1", database=str(path), start="2001-01-01T00:00:00Z",
                 end="2001-02-01T00:00:00Z", page_size=2, excluded_chats=[], self_names=["Sample User"])
    value.update(kw)
    return value

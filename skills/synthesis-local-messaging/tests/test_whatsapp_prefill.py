# SPDX-License-Identifier: Apache-2.0
"""The WhatsApp prefill (the principal's ruling, 2026-10-22): an existing one-to-one chat opens with the exact
text in its composer and the principal presses Send. Synthetic stores only; nothing is opened."""

from __future__ import annotations

import json
import sqlite3

import pytest

import whatsapp_prefill as wp

NUMBER, LINKED = "+15551234567", "+15557654321"
TEXT = "Running 10 min late & parking now #2\nSee you there 😀"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A one-to-one chat by number, one by linked id, a group, and the linked-id pairing."""
    folder = tmp_path / "group.net.whatsapp.WhatsApp.shared"
    folder.mkdir()
    chats = sqlite3.connect(folder / "ChatStorage.sqlite")
    chats.execute("create table ZWACHATSESSION (Z_PK integer primary key, ZSESSIONTYPE integer, ZCONTACTJID text)")
    chats.executemany("insert into ZWACHATSESSION (ZSESSIONTYPE, ZCONTACTJID) values (?, ?)",
                      [(0, "15551234567@s.whatsapp.net"), (0, "999888777666@lid"), (1, "120363000000000001@g.us")])
    chats.commit()
    chats.close()
    lids = sqlite3.connect(folder / "LID.sqlite")
    lids.execute("create table ZWAZACCOUNT (Z_PK integer primary key, ZIDENTIFIER text, ZPHONENUMBER text)")
    lids.execute("insert into ZWAZACCOUNT (ZIDENTIFIER, ZPHONENUMBER) values ('999888777666@lid', '15557654321')")
    lids.commit()
    lids.close()
    opened = []
    monkeypatch.setattr(wp, "opener", opened.append)
    return folder, opened


def test_an_existing_chat_opens_with_the_exact_text_and_nothing_is_sent(store):
    folder, opened = store
    result = wp.prefill(NUMBER, TEXT, store=folder)
    assert result["status"] == "prefilled" and "Nothing was sent" in result["next"]
    assert opened == [["whatsapp://send?phone=15551234567&text=Running%2010%20min%20late%20%26%20parking%20now%20%232"
                       "%0ASee%20you%20there%20%F0%9F%98%80"]]


def test_a_chat_kept_under_a_linked_id_is_found_by_its_number(store):
    folder, opened = store
    assert wp.prefill(LINKED, TEXT, store=folder)["status"] == "prefilled"
    assert opened[0][0].startswith("whatsapp://send?phone=15557654321&")


def test_a_photo_is_shown_in_finder_for_the_principal_to_attach(store, tmp_path):
    folder, opened = store
    shot = tmp_path / "dinner.jpg"
    shot.write_bytes(b"\xff\xd8 synthetic \xff\xd9")
    wp.prefill(NUMBER, TEXT, photo=str(shot), store=folder)
    assert opened[1] == ["-R", str(shot.resolve())]


@pytest.mark.parametrize("number, text, reason", [
    ("+15550000000", TEXT, "no one-to-one WhatsApp chat"),         # never starts a chat
    ("120363000000000001@g.us", TEXT, "cannot name a group"),       # a group is never reached by a link
    ("15551234567", TEXT, "country code"),
    (NUMBER, "   ", "non-empty"),
    (NUMBER, "x" * 4097, "at most 4,096"),
])
def test_refusals_open_nothing(store, number, text, reason):
    folder, opened = store
    with pytest.raises(wp.Refused, match=reason):
        wp.prefill(number, text, store=folder)
    assert opened == []


def test_an_unreadable_store_refuses(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(wp, "opener", opened.append)
    with pytest.raises(wp.Refused, match="cannot read WhatsApp's chats"):
        wp.prefill(NUMBER, TEXT, store=tmp_path / "absent")
    assert opened == []


def test_the_command_prints_json_and_exits_by_outcome(store, tmp_path, capsys):
    folder, _ = store
    text = tmp_path / "reply.txt"
    text.write_text(TEXT, encoding="utf-8")
    assert wp.main(["--to", NUMBER, "--text-file", str(text), "--store", str(folder)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prefilled"
    assert wp.main(["--to", "+15550000000", "--text-file", str(text), "--store", str(folder)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "refused"

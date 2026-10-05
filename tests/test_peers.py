"""R2.3 peer addressing: a message reaches exactly one live session, or nothing is sent."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import board

ROOT = Path(__file__).resolve().parents[1]


def _sent(isolated_home):
    messages = isolated_home / "state" / "messages"
    return sorted(messages.rglob("*.json")) if messages.is_dir() else []


def _make_stale(session_id):
    s = board.load(session_id)
    s.seen = time.time() - board.STALE_SECONDS - 1
    board.save(s)


def test_each_session_gets_a_short_name_derived_from_its_id(isolated_home):
    # Two UUIDv7 ids minted in the same minute share their first eight characters.
    a = board.touch("0199a213-81c0-7800-8aa1-bbab2ca9cfe3")
    b = board.touch("0199a213-81c0-7c41-9e02-04f1d7a3b6aa")
    assert a.short != b.short and len(a.short) == 6 and a.short.isalnum()
    assert a.short == board.short_name(a.session) == board.load(a.session).short
    stored = json.loads((isolated_home / "state" / "sessions" / f"{a.session}.json").read_text())
    assert stored["short"] == a.short


def test_an_address_may_be_a_session_id_its_short_name_or_its_project():
    a = board.touch("S1", project="alpha")
    board.touch("S2", project="beta")
    assert board.resolve("S1").session == "S1"
    assert board.resolve(a.short).session == "S1"
    assert board.resolve("project:alpha").session == "S1"
    board.message(a.short, "S2", "by short name")
    assert board.inbox("S1")[0]["text"] == "by short name"
    assert board.inbox("S1")[0]["from"] == "S2"


def test_a_project_with_two_live_sessions_is_refused_listing_both_and_nothing_is_sent(isolated_home):
    board.touch("S1", project="alpha")
    board.touch("S2", project="alpha")
    with pytest.raises(board.AddressError, match=r"(?s)names 2 live sessions.*S1.*S2"):
        board.message("project:alpha", "S9", "who owns the plan?")
    assert _sent(isolated_home) == []


@pytest.mark.parametrize("address", ["synthesis-skills-v5", "the reviewer", "alpha", "S1 and S2", "", "project:"])
def test_names_that_are_not_board_addresses_are_refused_listing_live_sessions(isolated_home, address):
    board.touch("S1", project="alpha")
    with pytest.raises(board.AddressError, match=r"(?s)names no live session.*S1 \(short"):
        board.message(address, "S2", "hello")
    assert _sent(isolated_home) == []


def test_a_stale_session_is_named_but_not_addressed(isolated_home):
    board.touch("S1", project="alpha")
    _make_stale("S1")
    with pytest.raises(board.AddressError, match=r"(?s)only stale sessions.*S1.*stale"):
        board.message("project:alpha", "S2", "are you there?")
    assert _sent(isolated_home) == []


def test_a_message_carries_its_senders_id(isolated_home):
    board.touch("S1")
    with pytest.raises(board.AddressError, match="sender"):
        board.message("S1", "", "anonymous")
    with pytest.raises(board.AddressError, match="empty"):
        board.message("S1", "S2", "   ")
    board.message("S1", "S2", "signed")
    assert board.inbox("S1") == [{"to": "S1", "session": "S1", "from": "S2", "text": "signed",
                                  "at": board.inbox("S1")[0]["at"]}]


def test_the_same_text_to_a_second_session_is_refused_as_a_broadcast(isolated_home):
    board.touch("S1")
    board.touch("S3")
    board.message("S1", "S2", "please rebase on main")
    board.message("S1", "S2", "please rebase on main")  # saying it again to the same session is fine
    with pytest.raises(board.AddressError, match="broadcast"):
        board.message("S3", "S2", "please rebase on main")
    assert board.inbox("S3") == []
    board.message("S3", "S2", "please rebase on main too")


def test_a_session_messaging_its_own_project_reaches_its_peer(isolated_home):
    board.touch("S1", project="alpha")
    board.touch("S2", project="alpha")
    board.message("project:alpha", "S1", "I am done with CONTEXT.md")
    assert [m["text"] for m in board.inbox("S2", "alpha")] == ["I am done with CONTEXT.md"]
    assert board.inbox("S1", "alpha") == []


def test_project_messages_are_not_replayed_to_a_later_session_unless_durable(isolated_home, tmp_path):
    board.touch("S1", project="alpha")
    board.message("project:alpha", "S9", "for whoever is on alpha now")
    board.message("project:alpha", "S9", "for everyone who works on alpha", durable=True)
    board.touch("S2", project="alpha")  # joins afterwards
    assert [m["text"] for m in board.inbox("S2", "alpha", mark_read=True)] == ["for everyone who works on alpha"]
    assert [m["text"] for m in board.inbox("S1", "alpha", mark_read=True)] == [
        "for whoever is on alpha now", "for everyone who works on alpha"]
    assert board.inbox("S1", "alpha") == [] and board.inbox("S2", "alpha") == []


def test_a_durable_message_needs_a_project_the_board_or_knowledge_roots_know(isolated_home, write_config, tmp_path):
    with pytest.raises(board.AddressError, match="project:<id>"):
        board.message("S1", "S9", "note", durable=True)
    with pytest.raises(board.AddressError, match="no project named 'typo'"):
        board.message("project:typo", "S9", "note", durable=True)
    root = tmp_path / "ai-knowledge-test"
    (root / "projects" / "gamma").mkdir(parents=True)
    write_config({"knowledge_roots": [str(root)]})
    board.message("project:gamma", "S9", "for gamma's next session", durable=True)  # nobody on it yet
    board.touch("S4", project="gamma")
    assert board.inbox("S4", "gamma")[0]["text"] == "for gamma's next session"


def test_the_recipient_sees_a_message_once_at_its_next_prompt(isolated_home):
    target = board.touch("S1", project="alpha")
    board.message(target.short, "S2", "the release train is yours")

    def prompt():
        out = subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"],
                             input=json.dumps({"session_id": "S1", "prompt": "carry on"}),
                             capture_output=True, text=True, cwd=ROOT, env=dict(os.environ))
        return out.stdout

    assert "the release train is yours" in prompt()
    assert "the release train is yours" not in prompt()


def test_resolve_is_a_plain_lookup_with_no_side_effects(isolated_home):
    board.touch("S1", project="alpha")
    before = sorted(p.name for p in (isolated_home / "state").rglob("*"))
    board.resolve("project:alpha")
    with pytest.raises(board.AddressError):
        board.resolve("nobody")
    assert sorted(p.name for p in (isolated_home / "state").rglob("*")) == before

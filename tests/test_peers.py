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
    messages = isolated_home / "board" / "messages"
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
    stored = json.loads((isolated_home / "board" / "sessions" / f"{a.session}.json").read_text())
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
        board.message("S1", "S2", "are you there?")
    assert _sent(isolated_home) == []


def test_a_project_with_no_live_session_gets_a_durable_message_its_next_session_reads(isolated_home):
    """A project session, 2026-10-20: a report to a project whose sessions were all stale was refused and nearly
    lost. With nobody live on the project, the message waits for its next session instead."""
    board.touch("S1", project="alpha")
    _make_stale("S1")
    sent = board.message("project:alpha", "S2", "the incident report")
    assert sent.parent == board._box("project:alpha")
    board.touch("S3", project="alpha")
    assert [m["text"] for m in board.inbox("S3", "alpha")] == ["the incident report"]


def test_a_message_carries_its_senders_id(isolated_home):
    board.touch("S1")
    with pytest.raises(board.AddressError, match="sender"):
        board.message("S1", "", "anonymous")
    with pytest.raises(board.AddressError, match="empty"):
        board.message("S1", "S2", "   ")
    board.message("S1", "S2", "signed")
    [got] = board.inbox("S1")
    assert got == {"to": "S1", "session": "S1", "from": "S2", "text": "signed", "at": got["at"], "id": got["id"]}
    assert got["id"].endswith(".json")  # the message's file, so exactly the shown messages can be marked read


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


def test_a_session_on_an_older_release_is_told_once_what_changed(isolated_home):
    """Rajiv, 2026-10-06: after an upgrade, a session resumed or still running should learn of it without a new skill.
    A new session records the release silently; one that last saw an older release gets the changelog once."""
    from synthesis import __version__, paths
    (paths.home() / "current").mkdir(parents=True, exist_ok=True)
    (paths.home() / "current" / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{__version__}] - 2026-10-07\n\n- The newest change.\n\n## [0.0.2] - 2026-10-06\n\n"
        "- A change the session already had.\n\n## [0.0.1] - 2026-10-05\n\n- An older one.\n", encoding="utf-8")

    def prompt(session_id):
        return subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"],
                              input=json.dumps({"session_id": session_id, "prompt": "carry on"}),
                              capture_output=True, text=True, cwd=ROOT, env=dict(os.environ)).stdout

    board.touch("NEW", project="alpha")
    assert "was upgraded" not in prompt("NEW") and board.load("NEW").version == __version__
    board.touch("OLD", project="alpha", version="0.0.2")
    note = prompt("OLD")
    assert f"upgraded from 0.0.2 to {__version__}" in note and "The newest change" in note
    assert "already had" not in note and "An older one" not in note
    assert "was upgraded" not in prompt("OLD") and board.load("OLD").version == __version__
    board.touch("AHEAD", project="alpha", version="99.0.0")  # the runtime was rolled back under it
    note = prompt("AHEAD")
    assert f"rolled back from 99.0.0 to {__version__}" in note and "upgraded" not in note and "newest" not in note


def test_the_prompt_hook_marks_read_only_what_it_shows_and_marks_a_cut(isolated_home):
    """A project session, 2026-10-13: the hook marked every unread message read but showed five, cut at 1,500
    characters without a marker, so `synthesis inbox` pointed at an empty inbox and long messages lost text."""
    board.touch("READER", project="alpha")
    board.touch("WRITER", project="alpha")
    long_text = "start " + "x" * 2000 + " end"
    for n in range(6):
        board.message("project:alpha", "WRITER", f"note {n}", durable=True)
    board.message("project:alpha", "WRITER", long_text, durable=True)

    def prompt():
        return subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"],
                              input=json.dumps({"session_id": "READER", "prompt": "carry on"}),
                              capture_output=True, text=True, cwd=ROOT, env=dict(os.environ)).stdout

    first = prompt()
    assert first.count("Board message from") == 5 and "2 more unread" in first
    left = board.inbox("READER", "alpha")
    assert [m["text"] for m in left] == ["note 5", long_text]       # nothing shown is lost
    second = prompt()
    assert "note 5" in second and "[cut: " in second and " end" not in second and "more unread" not in second
    assert board.inbox("READER", "alpha") == []
    recent = board.inbox("READER", "alpha", recent_hours=1)
    assert len(recent) == 7 and recent[-1]["text"] == long_text      # the whole message can be read again


def test_a_session_recorded_before_versions_were_kept_is_told_if_it_predates_the_install(isolated_home):
    """2026-10-07: synthesis-movement had run since before 5.0.3, so it had no recorded version and was never
    told about the upgrade. A session that started on this release stays silent."""
    from synthesis import __version__, paths
    (paths.home() / "current").mkdir(parents=True, exist_ok=True)
    (paths.home() / "current" / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{__version__}] - 2026-10-13\n\n- This release's change.\n\n## [0.0.1] - 2026-10-01\n\n- Old.\n",
        encoding="utf-8")
    board.touch("BEFORE", project="alpha", started=time.time() - 3600)
    (paths.home() / "current" / "HASH").write_text("abc\n", encoding="utf-8")   # installed after BEFORE started
    board.touch("AFTER", project="alpha", started=time.time() + 1)

    def prompt(session_id):
        return subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"],
                              input=json.dumps({"session_id": session_id, "prompt": "carry on"}),
                              capture_output=True, text=True, cwd=ROOT, env=dict(os.environ)).stdout

    note = prompt("BEFORE")
    assert f"upgraded to {__version__}" in note and "not recorded" in note and "This release's change" in note
    assert "Old." not in note and "was upgraded" not in prompt("BEFORE")
    assert "was upgraded" not in prompt("AFTER") and board.load("AFTER").version == __version__

"""Messenger as a ritual surface: the chat list read without opening a chat, with stated coverage.

Messenger runs inside facebook.com, and its chat list shows what a ritual needs without opening a chat: who, the
age of the last message, who spoke last (`You: `), the last message itself, an unread mark and Messenger's own
`Follow up?` nudge on chats that end with the principal. Opening a chat marks it read, so the read stays on the
list: `messenger_messages.py` prints a read-only extractor for the grid of one inbox (Chats, Message requests,
Archived chats), parses what it saved, lists the chats that end with someone else and states how far back the read
went. A row shows an age, never a date, so a date is the latest the age allows and a row with no age moves nothing.
The fixtures are invented, shaped like the page as read on 2026-11-14. Committed before the script.
"""
from __future__ import annotations

import html
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "messenger_messages.py"
READ_AT = "2026-11-14T09:45:00-05:00"
LIST = "https://www.facebook.com/messages/t/"
UNITS = {"m": "minute", "h": "hour", "d": "day", "w": "week"}


@pytest.fixture
def mm():
    """The script, imported afresh for each test, so each test fails on its own while it is missing."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        sys.modules.pop("messenger_messages", None)
        return importlib.import_module("messenger_messages")
    finally:
        sys.path.remove(str(SCRIPTS))


def words(age):
    """The age's aria label, as the page writes it beside the short form: `a week ago`, `9 weeks ago`."""
    number, unit = int(age[:-1]), UNITS[age[-1]]
    return f"{('an' if unit == 'hour' else 'a') if number == 1 else number} {unit}{'s' * (number != 1)} ago"


def row(name, preview, age="2h", chat="1001", active=False, unread=False, e2ee=True):
    """One row as the extractor saves it: its text lines in order, its link, its options button and the age's words.
    No age means Messenger's `Follow up?` stands in its place."""
    lines = (["Active now"] if active else []) + [name] + (["Unread message:"] if unread else []) + preview.split("\n")
    return {"text": lines + ["·", age or "Follow up?"], "href": f"/messages/{'e2ee/' if e2ee else ''}t/{chat}/",
            "options": f"More options for {name}", "ages": [words(age)] if age else []}


def saved(rows, grid="Chats", url=LIST, dialogs=(), page="", found=True):
    return {"extractor": "messenger-list/1", "url": url, "title": "Messenger | Facebook", "grid": grid, "found": found,
            "rows": rows, "dialogs": list(dialogs), "page": page}


CHATS = [
    row("Ana Alvarez", "You: See you Thursday.", "15m", "1001", active=True),
    row("Bo Becker", "Are you around next week? I have a\nquestion about the board deck.", "2h", "1002", unread=True),
    row("Cy Castillo", "Cy sent a photo.", "4d", "1003"),
    row("Dee Dunn", "You: Thanks, talk soon.", None, "1004"),
    row("Eli Edwards", "Did the package arrive?", "1w", "1005", unread=True),
    row("Gus Gray, Hana Hill", "Hana: Thank you very much", "2w", "1006", e2ee=False),
]


def run(tmp_path: Path, data, *args: str, as_saved=True):
    """parse on a read saved as the browser tool returns the extractor's value: a JSON string holding its JSON."""
    path = tmp_path / "read.json"
    path.write_text(data if isinstance(data, str) else json.dumps(json.dumps(data) if as_saved else data), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "parse", "--text", str(path), "--read-at", READ_AT, "--json", *args],
                          capture_output=True, text=True)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip().startswith("{") else done.stdout + done.stderr)


def test_every_row_shape_is_read(tmp_path):
    code, got = run(tmp_path, saved(CHATS), "--inbox", "chats")
    assert code == 0, got
    threads = got["threads"]
    assert [t["who"] for t in threads] == ["Ana Alvarez", "Bo Becker", "Cy Castillo", "Dee Dunn", "Eli Edwards",
                                           "Gus Gray, Hana Hill"]
    assert [t["age"] for t in threads] == ["15m", "2h", "4d", None, "1w", "2w"]
    assert [t["from_me"] for t in threads] == [True, False, False, True, False, False]
    assert [t["unread"] for t in threads] == [False, True, False, False, True, False]
    assert [t["active"] for t in threads] == [True, False, False, False, False, False]
    assert [t["nudge"] for t in threads] == [False, False, False, True, False, False]
    assert threads[1]["preview"] == "Are you around next week? I have a question about the board deck."  # wrapped
    assert threads[2]["kind"] == "media" and threads[1]["kind"] == "message"
    assert threads[0]["chat"] == "https://www.facebook.com/messages/e2ee/t/1001/"
    assert threads[5]["chat"] == "https://www.facebook.com/messages/t/1006/"
    assert not any(t["open"] for t in threads)  # the list beside "No chats selected" opens no chat


def test_the_chats_that_end_with_someone_else_unread_marks_and_nudges_make_the_coverage_line(tmp_path):
    code, got = run(tmp_path, saved(CHATS), "--inbox", "chats", "--since", "2026-11-01")
    assert code == 0, got
    assert [t["who"] for t in got["owed"]] == ["Bo Becker", "Cy Castillo", "Eli Edwards", "Gus Gray, Hana Hill"]
    assert [t["who"] for t in got["nudged"]] == ["Dee Dunn"]  # Messenger's nudge sits on chats that end with the principal
    assert got["line"] == ("Messenger, chats: 6 conversations read from the list, back to 2026-10-31; 4 end with someone "
                           "else (2 unread); Messenger suggests a follow-up on 1; none opened")
    cover = got["coverage"]
    assert (cover["threads"], cover["oldest"], cover["unreadable"], cover["opened"]) == (6, "2026-10-31", 0, 0)
    assert cover["complete"] is True and datetime.fromisoformat(cover["through"]) == datetime.fromisoformat(READ_AT)
    assert "Bo" not in got["line"] and "Dee" not in got["line"]  # a coverage line names no one


def test_an_age_is_turned_into_the_latest_date_it_allows(tmp_path):
    """A `9w` row is at least nine weeks old, so its date is the latest nine weeks allow; the read never claims a day
    it did not see. Minutes, hours, days and weeks."""
    rows = [row("Kit Kim", "See you", "59m", "2001"), row("Lee Lopez", "ok", "23h", "2002"),
            row("Mo Mills", "Hi there", "6d", "2003"), row("Nia Novak", "Hello", "9w", "2004")]
    code, got = run(tmp_path, saved(rows))
    assert code == 0, got
    assert [t["last"] for t in got["threads"]] == ["2026-11-14", "2026-11-13", "2026-11-08", "2026-09-12"]
    assert got["coverage"]["oldest"] == "2026-09-12"
    assert got["line"].startswith("Messenger: 4 conversations read from the list, back to 2026-09-12") and got["inbox"] is None


def test_a_row_with_no_age_does_not_move_the_oldest_day(tmp_path):
    rows = [row("Ana Alvarez", "Sure", "3d", "1001"), row("Dee Dunn", "You: Thanks, talk soon.", None, "1004")]
    code, got = run(tmp_path, saved(rows), "--since", "2026-11-11")
    assert code == 0 and got["coverage"]["oldest"] == "2026-11-11" and got["threads"][1]["last"] is None
    code, got = run(tmp_path, saved(rows[1:]), "--since", "2026-11-11")  # nothing read shows how far back it went
    assert code == 1 and got["coverage"]["oldest"] is None and got["coverage"]["through"] is None
    assert "no row read shows its age" in got["line"]


def test_a_read_that_stops_short_of_the_last_one_is_not_complete(tmp_path):
    code, got = run(tmp_path, saved(CHATS), "--inbox", "chats", "--since", "2026-10-01")
    assert code == 1
    assert got["coverage"]["complete"] is False and got["coverage"]["through"] is None
    assert "the read stops short of 2026-10-01: scroll the list further and read again" in got["line"]


def test_a_preview_and_its_age_on_one_line_read_as_on_three(tmp_path):
    joined = dict(CHATS[0], text=["Active now", "Ana Alvarez", "You: See you Thursday. · 15m"])
    code, got = run(tmp_path, saved([joined]))
    assert code == 0, got
    assert (got["threads"][0]["preview"], got["threads"][0]["age"]) == ("You: See you Thursday.", "15m")


def test_message_requests_and_archived_chats_are_read_from_their_own_grids(tmp_path):
    requests = saved([row("Quinn Quill", "Hi! We met at the conference.", "3d", "3001", unread=True)], grid="Requests")
    code, got = run(tmp_path, requests, "--inbox", "requests", "--since", "2026-11-11")
    assert code == 0, got
    assert got["line"].startswith("Messenger, requests: 1 conversation read from the list, back to 2026-11-11; 1 ends")
    archived = saved([row("Ray Reed", "You: Congratulations!", "6w", "3002")], grid="Archived chats")
    code, got = run(tmp_path, archived, "--inbox", "archived")
    assert code == 0 and got["inbox"] == "archived" and got["threads"][0]["last"] == "2026-10-03"
    code, got = run(tmp_path, requests, "--inbox", "archived")  # a read of one list is never taken for another
    assert code == 2 and "Requests" in got and "Archived chats" in got


def test_an_empty_list_is_a_complete_read_only_when_the_reader_says_so_and_the_page_agrees(tmp_path):
    empty = saved([], grid="Archived chats", found=False, page="Archived chats\nNo archived chats\n")
    code, got = run(tmp_path, empty, "--inbox", "archived")
    assert code == 2 and "--empty" in got
    code, got = run(tmp_path, empty, "--inbox", "archived", "--empty", "--since", "2026-11-01")
    assert code == 0, got
    assert got["threads"] == [] and got["coverage"]["complete"] is True
    assert got["line"] == "Messenger, archived: no conversations in the list; none opened"
    code, got = run(tmp_path, saved([], grid="Requests"), "--inbox", "requests", "--empty")  # the grid there, with no row
    assert code == 0, got
    code, got = run(tmp_path, saved(CHATS[:2], grid="Archived chats"), "--inbox", "archived", "--empty")
    assert code == 2 and "2 rows" in got
    never = saved([], grid="Archived chats", found=False, page="Chats\nNo chats selected\n")  # the panel never opened
    code, got = run(tmp_path, never, "--inbox", "archived", "--empty")
    assert code == 2 and "Archived chats" in got


def test_a_short_list_read_to_its_end_reaches_every_day_only_on_the_readers_word_and_at_its_bottom(tmp_path):
    """Message requests may hold one request, three days old: no scrolling reaches a day two weeks back. The reader who
    scrolled to the list's end and saw nothing more load says so with --end; the extractor saw the list at its bottom."""
    one = saved([row("Quinn Quill", "Hi! We met at the conference.", "3d", "3001")], grid="Requests")
    code, got = run(tmp_path, one, "--inbox", "requests", "--since", "2026-10-31")
    assert code == 1 and "stops short of 2026-10-31" in got["line"]
    code, got = run(tmp_path, dict(one, bottom=True), "--inbox", "requests", "--since", "2026-10-31", "--end")
    assert code == 0 and got["coverage"]["complete"] is True, got
    assert got["line"].startswith("Messenger, requests: 1 conversation read from the list, back to 2026-11-11 (the end of the list);")
    code, got = run(tmp_path, dict(one, bottom=False), "--inbox", "requests", "--since", "2026-10-31", "--end")
    assert code == 2 and "not at the bottom of the list" in got


def test_a_hidden_panels_rows_read_empty_and_never_count_as_read(tmp_path):
    """Message requests and Archived chats open at the list's own address; a panel left behind keeps its rows, with
    empty text. A row with no text is not a conversation read."""
    hidden = [dict(r, text=[""]) for r in CHATS[:3]]
    code, got = run(tmp_path, saved(hidden), "--inbox", "chats")
    assert code == 1 and got["threads"] == [] and got["coverage"]["unreadable"] == 3
    assert "3 could not be read" in got["line"] and "hidden panel" in got["line"]


@pytest.mark.parametrize("read", [
    saved([], found=False, url="https://www.facebook.com/login/?next=%2Fmessages%2Ft%2F",
          page="Facebook\nLog in to Facebook\nEmail address or phone number\nPassword\nLog in\n"),
    saved([], found=False, url="https://www.facebook.com/checkpoint/828281030927956/", page="Security check\nContinue\n"),
    saved(CHATS, dialogs=["Enter your PIN to restore your chat history"]),
], ids=["sign-in", "security-check", "pin-dialog"])
def test_a_sign_in_page_or_a_security_check_stops_the_read(tmp_path, read):
    code, got = run(tmp_path, read, "--inbox", "chats")
    assert code == 2 and "stop and tell the principal" in got


def test_a_menu_open_over_the_list_is_no_wall_and_a_preview_never_reads_as_one(tmp_path):
    rows = CHATS[:1] + [row("Sam Stone", "Security check: log in again to see it", "1d", "4001")]
    code, got = run(tmp_path, saved(rows, dialogs=[]), "--inbox", "chats")
    assert code == 0, got


def test_text_that_is_not_the_extractors_output_is_refused(tmp_path):
    code, got = run(tmp_path, "Chats\nAna Alvarez\nYou: See you Thursday.\n·\n15m\n")
    assert code == 2 and "not the extractor's saved output" in got
    code, got = run(tmp_path, dict(saved(CHATS), extractor="something-else/1"))
    assert code == 2 and "not the extractor's saved output" in got
    code, got = run(tmp_path, saved(CHATS), "--inbox", "chats", as_saved=False)  # the object itself reads the same
    assert code == 0 and len(got["threads"]) == 6


def test_a_grid_the_read_did_not_find_is_refused(tmp_path):
    code, got = run(tmp_path, saved([], grid="Requests", found=False, page="Chats\nNo chats selected\n"), "--inbox", "requests")
    assert code == 2 and "no list named Requests" in got


def test_a_chat_open_during_the_read_is_counted_and_named(tmp_path):
    """Opening a chat marks it read in the principal's view, so a read whose page was a chat's address says so."""
    code, got = run(tmp_path, saved(CHATS, url="https://www.facebook.com/messages/e2ee/t/1002/"), "--inbox", "chats")
    assert code == 0, got
    assert got["coverage"]["opened"] == 1 and "; 1 opened" in got["line"] and "Bo" not in got["line"]
    assert [t["who"] for t in got["threads"] if t["open"]] == ["Bo Becker"]
    _, more = run(tmp_path, saved(CHATS, url="https://www.facebook.com/messages/e2ee/t/1002/"), "--opened", "2")
    assert more["coverage"]["opened"] == 2


def test_the_text_report_is_the_coverage_line_then_the_chats_owed_then_the_nudges(tmp_path):
    path = tmp_path / "read.json"
    path.write_text(json.dumps(json.dumps(saved(CHATS, url="https://www.facebook.com/messages/e2ee/t/1002/"))), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "parse", "--text", str(path), "--read-at", READ_AT, "--inbox", "chats"],
                          capture_output=True, text=True)
    lines = done.stdout.splitlines()
    assert done.returncode == 0 and lines[0].startswith("Messenger, chats: 6 conversations")
    assert lines[1] == "  open during the read: Bo Becker (opening a chat marks it read; name it in the plan)"
    assert lines[2].startswith("  2026-11-14 (2h) Bo Becker: Are you around next week?") and lines[2].endswith("[unread]")
    assert lines[3].startswith("  2026-11-10 (4d) Cy Castillo: Cy sent a photo.")
    assert lines[-1] == "  follow up? Dee Dunn: You: Thanks, talk soon.  [Messenger suggests a follow-up]"


def test_the_watermark_moves_only_with_the_readers_coverage(tmp_path):
    """The list loads as it scrolls, so a read covers only as far back as it was scrolled, like LinkedIn's."""
    spec = importlib.util.spec_from_file_location("sync_watermark", SCRIPTS / "sync_watermark.py")
    marks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(marks)
    now = datetime.fromisoformat("2026-11-14T10:00:00-05:00")
    with pytest.raises(ValueError, match="--coverage"):
        marks.advance("desk", "messenger", READ_AT, ("chats",), now=now, home=tmp_path)
    _, complete = run(tmp_path, saved(CHATS), "--inbox", "chats", "--since", "2026-11-01")
    got = marks.advance("desk", "messenger", "2026-11-14T09:59:00-05:00", ("chats",), now=now, home=tmp_path, coverage=complete)
    assert got["entries"][0]["moved"] and got["entries"][0]["through"].startswith("2026-11-14T09:45")  # capped at the read
    _, short = run(tmp_path, saved(CHATS), "--inbox", "chats", "--since", "2026-10-01")
    with pytest.raises(ValueError, match="no `through`"):
        marks.advance("desk", "messenger", READ_AT, ("chats",), now=now, home=tmp_path, coverage=short)


# --- the declaration --------------------------------------------------------------------------------------------


def plan(tmp_path: Path, declaration: str):
    config = tmp_path / "messenger-sync.yaml"
    config.write_text(declaration, encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "plan", "--config", str(config), "--today", "2026-11-14"],
                          capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "home")})
    return done.returncode, done.stdout + done.stderr


def test_the_plan_opens_the_list_and_never_a_chat(tmp_path):
    code, out = plan(tmp_path, "workspace: desk\ninboxes: [chats]\n")
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0].startswith(f"open  {LIST}  (chats: ") and "No chats selected" in lines[0]
    assert lines[1] == "read  chats: never read; scroll back to 2026-10-31, stop there, and pass --inbox chats --since 2026-10-31"
    assert "/e2ee/t/" not in out and len(lines) == 2


def test_every_inbox_is_read_unless_the_declaration_names_some_and_each_says_how_it_opens(tmp_path):
    """Message requests and Archived chats have no address of their own: each opens from the menu over the list."""
    code, out = plan(tmp_path, "workspace: desk\n")
    assert code == 0, out
    lines = out.splitlines()
    assert [line.split()[1] for line in lines[1::2]] == ["chats:", "requests:", "archived:"]
    assert all(line.startswith(f"open  {LIST}  (") for line in lines[0::2])
    assert "Settings, help and more" in lines[2] and "Message requests" in lines[2] and "Requests" in lines[2]
    assert "Settings, help and more" in lines[4] and "Archived chats" in lines[4]


@pytest.mark.parametrize("declaration, says", [
    ("inboxes: [chats]\n", "names no workspace"),
    ("workspace: desk\ninboxes: chats\n", "inboxes is a list"),
    ("workspace: desk\ninboxes: []\n", "inboxes is a list"),
    ("workspace: desk\ninboxes: [chats, spam]\n", "inboxes names spam"),
])
def test_a_declaration_it_cannot_use_is_refused(tmp_path, declaration, says):
    code, out = plan(tmp_path, declaration)
    assert code == 2 and says in out


def test_the_plan_names_the_day_the_last_read_reached(tmp_path):
    _, complete = run(tmp_path, saved(CHATS), "--inbox", "chats", "--since", "2026-11-01")
    spec = importlib.util.spec_from_file_location("sync_watermark", SCRIPTS / "sync_watermark.py")
    marks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(marks)
    marks.advance("desk", "messenger", READ_AT, ("chats",), now=datetime.fromisoformat("2026-11-14T10:00:00-05:00"),
                  home=tmp_path / "home", coverage=complete)
    code, out = plan(tmp_path, "workspace: desk\n")
    assert code == 0 and ("read  chats: read through 2026-11-14; scroll back to that day, stop there, and pass --inbox chats "
                          "--since 2026-11-14") in out
    assert "read  requests: never read" in out  # each inbox keeps its own watermark


# --- the extractor ----------------------------------------------------------------------------------------------

ACTS = (".click(", "dispatchEvent", "KeyboardEvent", "MouseEvent", ".focus(", ".submit(", "requestSubmit", "execCommand",
        ".value =", ".value=", "innerHTML", "setAttribute", "removeAttribute", "fetch(", "XMLHttpRequest", "sendBeacon",
        "scrollTo(", "scrollBy(", "scrollIntoView(", "scrollTop =", "scrollTop=", "localStorage", "location.assign",
        "location.href =", "window.open", ".remove(", "appendChild")


def extractor(inbox: str) -> str:
    done = subprocess.run([sys.executable, str(SCRIPT), "extractor", "--inbox", inbox], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.mark.parametrize("inbox, grid", [("chats", "Chats"), ("requests", "Requests"), ("archived", "Archived chats")])
def test_the_extractor_reads_only_the_grid_named_for_its_inbox_and_does_nothing_else(inbox, grid):
    script = extractor(inbox)
    assert json.dumps(grid) in script and "messenger-list/1" in script
    assert [act for act in ACTS if act in script] == []


def _session(tmp_path: Path, url: str) -> dict:
    """A session whose newest browser result says the call runs on tab 7, at this address."""
    use = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_1", "name": "mcp__claude-in-chrome__browser_batch", "input": {}}]}}
    listing = f"Done\n\nTab Context:\n- Executed on tabId: 7\n- Available tabs:\n  • tabId 7: \"Messenger\" (\"{url}\")"
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": [{"type": "text", "text": listing}]}]}}
    path = tmp_path / "transcript.jsonl"
    path.write_text(json.dumps(use) + "\n" + json.dumps(result) + "\n", encoding="utf-8")
    return {"session_id": "S-messenger-read", "transcript_path": str(path)}


def test_the_browser_guard_lets_the_extractor_through_as_a_read(tmp_path, monkeypatch):
    """facebook.com's /messages is a messaging page to the guard, where a page script that clicks, sends an event or
    sets a value waits for the principal's code. The extractor does none of these, so it passes; the same call with a
    click added is held, which shows the guard judged it."""
    for key in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_DATA_HOME", "RITUAL_STATE_DIR"):
        monkeypatch.setenv(key, str(tmp_path / key.lower()))
    from synthesis import guards
    for inbox in ("chats", "requests", "archived"):
        script = extractor(inbox)
        assert not guards.SCRIPT_ACTS.search(script)
        call = {"action": "javascript_exec", "text": script, "tabId": 7}
        assert guards.check("mcp__claude-in-chrome__javascript_tool", call, {}, session=_session(tmp_path, LIST)) is None
    held = {"action": "javascript_exec", "text": script + "\ndocument.querySelector('[role=\"row\"] a').click()", "tabId": 7}
    assert "approve" in (guards.check("mcp__claude-in-chrome__javascript_tool", held, {}, session=_session(tmp_path, LIST)) or "")


# --- the extractor in a real browser, on an invented page ---------------------------------------------------------


def find_chromium():
    configured = os.environ.get("SYNTHESIS_TEST_CHROMIUM")
    if configured:
        return configured if Path(configured).is_file() else None
    return next(filter(None, (shutil.which(n) for n in
                              ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome"))), None)


CHROMIUM = find_chromium()
if CHROMIUM is None and os.environ.get("SYNTHESIS_REQUIRE_CHROMIUM") == "1":  # CI: a missing browser fails
    raise RuntimeError("SYNTHESIS_REQUIRE_CHROMIUM=1 but no Chromium was found")


def row_html(r) -> str:
    lines = "".join(f"<div>{html.escape(t)}</div>" for t in r["text"][:-1])
    tail = (f"<div><abbr aria-label=\"{html.escape(r['ages'][0])}\">{html.escape(r['text'][-1])}</abbr></div>" if r["ages"]
            else f"<div>{html.escape(r['text'][-1])}</div>")
    return (f"<div role=\"row\"><a href=\"{html.escape(r['href'])}\" role=\"link\">{lines}{tail}</a>"
            f"<div role=\"button\" aria-label=\"{html.escape(r['options'])}\"></div></div>")


def in_chromium(script: str, rows: list, hidden: list) -> dict:
    """The extractor run in a headless Chromium on a page shaped like the list: the Chats grid in its tab panel, a
    hidden Archived chats panel behind it and "No chats selected" beside it. Nothing touches the network."""
    page = ("<!doctype html><html><head><meta charset=\"utf-8\"><title>Messenger | Facebook</title></head><body>"
            "<div role=\"navigation\" aria-label=\"Thread list\"><div role=\"button\" aria-label=\"Settings, help and more\">"
            "</div></div><div role=\"tablist\"><div role=\"tab\">All</div><div role=\"tab\">Unread</div></div>"
            "<div role=\"tabpanel\" aria-label=\"All chats\"><div role=\"grid\" aria-label=\"Chats\">"
            + "".join(map(row_html, rows)) + "</div></div><div hidden><div role=\"grid\" aria-label=\"Archived chats\">"
            + "".join(map(row_html, hidden)) + "</div></div><div role=\"main\"><span>No chats selected</span></div>"
            "<script>var found = " + script + ";\nvar out = document.createElement('pre'); out.id = 'messenger-result';"
            " out.textContent = found; document.body.appendChild(out);</script></body></html>")
    work = Path(tempfile.mkdtemp(prefix="messenger-list-", dir="/tmp"))  # Chromium's socket path limit is short
    try:
        probe = work / "probe.html"
        probe.write_text(page, encoding="utf-8")
        done = subprocess.run([CHROMIUM, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                               "--disable-extensions", "--disable-background-networking", f"--user-data-dir={work / 'profile'}",
                               "--dump-dom", probe.as_uri()], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, TMPDIR=str(work)))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    assert done.returncode == 0, done.stderr[-2000:]
    found = re.search(r'<pre id="messenger-result">(.*?)</pre>', done.stdout, re.S)
    assert found, "the page did not reach its driver"
    return json.loads(html.unescape(found.group(1)))


@pytest.mark.skipif(CHROMIUM is None, reason="no Chromium: set SYNTHESIS_TEST_CHROMIUM or put one on PATH")
def test_the_extractor_on_a_page_shaped_like_the_list_saves_what_parse_reads(tmp_path, mm):
    read = in_chromium(extractor("chats"), CHATS, [row("Zed Zane", "You: ok", "3w", "9001")])
    assert read["found"] is True and read["grid"] == "Chats" and len(read["rows"]) == 6
    got = mm.parse(read, datetime.fromisoformat(READ_AT), "2026-11-01", 0, "chats", False)
    want = mm.parse(saved(CHATS), datetime.fromisoformat(READ_AT), "2026-11-01", 0, "chats", False)
    assert got["threads"] == want["threads"] and got["coverage"] == want["coverage"]
    behind = in_chromium(extractor("archived"), CHATS, [row("Zed Zane", "You: ok", "3w", "9001")])
    late = mm.parse(behind, datetime.fromisoformat(READ_AT), "", 0, "archived", False)  # a hidden panel's rows read empty
    assert late["threads"] == [] and late["coverage"]["unreadable"] == 1

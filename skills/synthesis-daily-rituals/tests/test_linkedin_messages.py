"""LinkedIn messages as a ritual surface: read from the conversation list, with stated coverage.

A principal found messages on LinkedIn the rituals had never shown him: the surface was reached only through
notification emails, which hide the text and never cover InMail. `linkedin_messages.py` reads the saved text
of the conversation list (who, when, who spoke last, the whole last message, unread counts and LinkedIn's own
reply nudge are all there without opening a thread), lists the conversations that end with someone else, and
states how far back the read went. The fixtures are synthetic, shaped like live reads on 2026-11-11: the list
alone, and the whole new-message view (the list, then the composer with its suggested recipients).
Committed before the script.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "linkedin_messages.py"
READ_AT = "2026-11-11T09:45:00-05:00"
TAIL = ". Press return to go to conversation details\nOpen the options list in your conversation with Pat Principal and {who}\n"


def card(who, when, last, status="Status is offline", extra=""):
    head = f"{status}\n" if status else ""
    return f"{head}{who}\n{when}\n{when}\n{last}\n{extra}" + TAIL.format(who=who)


HEAD = "Messaging\nFocused\nJobs\nUnread\nConnections\nInMail\nStarred\n"
ANA = ("Ana Alvarez", "7:00 AM", "You: Hope you feel better soon.", "Status is online")
LIST = HEAD + "".join([
    card(*ANA),
    card("Bo Becker", "Nov 10", "You: December works. Send me a couple of dates."),
    card("Cy Castillo", "Nov 10", "Cy: We met years ago. Would you have thirty minutes to talk about a product role?", "Status is online"),
    card("Dee Dunn", "Nov 9", "Dee: thanks so much!"),
    card("Eli Edwards", "Nov 9", "Eli: 👍", "", "Received 3 days ago. Reply?\n"),
    card("Flo Fischer", "Nov 6", "InMail • Advisory project: how it works", "", "1\n1 new notification\n"),
    card("Gus Gray, Hana Hill", "Nov 6", "Hana: Thank you very much", "Status is reachable", "2\n2 new notifications\n"),
    card("Ira Ito", "Nov 5", "You: Thanks. Talk soon."),
])
OPENED = LIST.replace(card(*ANA), card(*ANA, ". Active conversation\n"))  # a conversation was open in the page
# The new-message view as a browser tool returns the whole page: the list, then the composer.
PAGE = ("Messaging\nSearch messages\nCompose a new message\nFocused\nJobs Unread Connections InMail Starred\nConversation List\n"
        "Attention screen reader users, messaging items continuously update.\n" + LIST[len(HEAD):] +
        "Load more conversations\nNew message\nEnter message recipients\nSuggested\nStatus is reachable\nAna Alvarez\n"
        "Investor at Example Capital\nBo Becker\nProduct executive | Board director\nStatus is online\nIra Ito\n"
        "Founder: building something new\n\nMaximize compose field\nAttach a file for your draft conversation\nSend\n"
        "Open send options\n")


def run(tmp_path: Path, text: str = LIST, *args: str):
    saved = tmp_path / "list.txt"
    saved.write_text(text, encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "parse", "--text", str(saved), "--read-at", READ_AT, "--json", *args],
                          capture_output=True, text=True)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip().startswith("{") else done.stdout + done.stderr)


def test_every_conversation_is_read_with_who_when_and_who_spoke_last(tmp_path):
    code, got = run(tmp_path)
    assert code == 0, got
    threads = got["threads"]
    assert [t["who"] for t in threads] == ["Ana Alvarez", "Bo Becker", "Cy Castillo", "Dee Dunn", "Eli Edwards", "Flo Fischer",
                                           "Gus Gray, Hana Hill", "Ira Ito"]
    assert [t["last"] for t in threads] == ["2026-11-11T07:00", "2026-11-10", "2026-11-10", "2026-11-09", "2026-11-09",
                                            "2026-11-06", "2026-11-06", "2026-11-05"]
    assert [t["from_me"] for t in threads] == [True, True, False, False, False, False, False, True]
    assert threads[2]["preview"].startswith("Cy: We met years ago") and threads[2]["speaker"] == "Cy"
    assert got["account"] == "Pat Principal"


def test_unread_counts_inmail_and_linkedins_own_nudge_are_kept(tmp_path):
    _, got = run(tmp_path)
    by = {t["who"]: t for t in got["threads"]}
    assert by["Flo Fischer"]["kind"] == "inmail" and by["Flo Fischer"]["unread"] == 1 and by["Flo Fischer"]["from_me"] is False
    assert by["Gus Gray, Hana Hill"]["unread"] == 2 and by["Gus Gray, Hana Hill"]["speaker"] == "Hana"
    assert by["Eli Edwards"]["nudge"] is True and by["Dee Dunn"]["nudge"] is False
    assert not any(t["open"] for t in got["threads"])  # the new-message view opens no conversation


def test_the_new_message_view_is_read_whole_and_its_suggested_recipients_are_not_conversations(tmp_path):
    """The read opens the new-message view: the list beside an empty composer, with nothing opened."""
    code, got = run(tmp_path, PAGE)
    assert code == 0, got
    _, alone = run(tmp_path)
    assert got["threads"] == alone["threads"] and len(got["threads"]) == 8
    assert got["coverage"]["opened"] == 0 and "none opened" in got["line"]


def test_a_conversation_open_during_the_read_is_counted_and_named(tmp_path):
    """Opening a conversation marks it read, so a read that had one open says so even when nobody passes --opened."""
    code, got = run(tmp_path, OPENED)
    assert code == 0, got
    assert got["coverage"]["opened"] == 1 and "; 1 opened" in got["line"] and "Ana" not in got["line"]
    assert [t["who"] for t in got["threads"] if t["open"]] == ["Ana Alvarez"]
    _, more = run(tmp_path, OPENED, "--opened", "2")  # the reader opened two; the list shows only the last
    assert more["coverage"]["opened"] == 2 and "; 2 opened" in more["line"]
    saved = tmp_path / "list.txt"
    done = subprocess.run([sys.executable, str(SCRIPT), "parse", "--text", str(saved), "--read-at", READ_AT], capture_output=True, text=True)
    assert "open during the read: Ana Alvarez" in done.stdout


def test_the_account_is_found_whichever_side_of_the_closing_sentence_it_stands(tmp_path):
    text = card("Kit Kim", "Nov 4", "You: Thanks.").replace("with Pat Principal and Kit Kim", "with Kit Kim and Pat Principal")
    code, got = run(tmp_path, text)
    assert code == 0 and got["account"] == "Pat Principal" and got["threads"][0]["who"] == "Kit Kim"


def test_the_conversations_that_end_with_someone_else_are_the_candidates(tmp_path):
    _, got = run(tmp_path)
    assert [t["who"] for t in got["owed"]] == ["Cy Castillo", "Dee Dunn", "Eli Edwards", "Flo Fischer", "Gus Gray, Hana Hill"]
    assert "from_me" not in got["owed"][0] or got["owed"][0]["from_me"] is False


def test_the_coverage_line_states_how_far_back_the_read_went(tmp_path):
    code, got = run(tmp_path, LIST, "--since", "2026-11-06")
    assert code == 0
    cover = got["coverage"]
    assert cover["threads"] == 8 and cover["oldest"] == "2026-11-05" and cover["unreadable"] == 0
    assert datetime.fromisoformat(cover["through"]) == datetime.fromisoformat(READ_AT)
    line = got["line"]
    assert line.startswith("LinkedIn messages: 8 conversations read from the list, back to 2026-11-05")
    assert "5 end with someone else" in line and "3 unread" in line and "none opened" in line
    assert "Ana" not in line and "Cy" not in line  # a coverage line names no one


def test_a_read_that_stops_short_of_the_last_one_is_not_complete(tmp_path):
    code, got = run(tmp_path, LIST, "--since", "2026-11-01")
    assert code == 1
    assert got["coverage"]["through"] is None
    assert "short of 2026-11-01" in got["line"] and "scroll" in got["line"]


def test_an_entry_it_cannot_read_is_counted_and_the_read_is_not_complete(tmp_path):
    broken = LIST.replace("Dee Dunn\nNov 9\nNov 9\n", "Dee Dunn\n", 1)  # the time lines missing
    code, got = run(tmp_path, broken)
    assert code == 1
    assert got["coverage"]["unreadable"] == 1 and got["coverage"]["through"] is None
    assert len(got["threads"]) == 7 and "1 could not be read" in got["line"]


def test_text_with_no_conversation_in_it_is_refused(tmp_path):
    code, got = run(tmp_path, "Sign in\nJoin now\n")
    assert code == 2 and "no conversation" in got


def test_a_sign_in_wall_or_a_security_check_stops_the_read(tmp_path):
    code, got = run(tmp_path, "Let's do a quick security check\n" + LIST)
    assert code == 2 and "security check" in got


def test_dates_from_last_year_and_a_message_of_several_lines_are_read(tmp_path):
    text = (card("Jo Jensen", "Dec 28", "Jo: Happy holidays.\n\nSee you in the new year?") +
            card("Kit Kim", "Jan 3, 2025", "You: Thanks."))
    code, got = run(tmp_path, text)
    assert code == 0, got
    first, second = got["threads"]
    assert first["last"] == "2025-12-28" and first["preview"] == "Jo: Happy holidays. See you in the new year?"
    assert second["last"] == "2025-01-03"


def test_the_text_report_is_the_coverage_line_then_the_candidates(tmp_path):
    saved = tmp_path / "list.txt"
    saved.write_text(LIST, encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "parse", "--text", str(saved), "--read-at", READ_AT], capture_output=True, text=True)
    lines = done.stdout.splitlines()
    assert lines[0].startswith("LinkedIn messages: 8 conversations")
    assert lines[1].startswith("  2026-11-10 Cy Castillo") and "Would you have thirty minutes" in lines[1]
    assert any("InMail" in line and "1 unread" in line for line in lines) and any("LinkedIn asks for a reply" in line for line in lines)


def test_the_watermark_moves_only_with_the_readers_coverage(tmp_path):
    """A list that loads as it scrolls is read only as far as it was scrolled, like a local message store."""
    spec = importlib.util.spec_from_file_location("sync_watermark", SCRIPTS / "sync_watermark.py")
    marks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(marks)
    now = datetime.fromisoformat("2026-11-11T10:00:00-05:00")
    with pytest.raises(ValueError, match="--coverage"):
        marks.advance("desk", "linkedin", READ_AT, ("focused",), now=now, home=tmp_path)
    _, complete = run(tmp_path, LIST, "--since", "2026-11-06")
    got = marks.advance("desk", "linkedin", "2026-11-11T09:59:00-05:00", ("focused",), now=now, home=tmp_path, coverage=complete)
    assert got["entries"][0]["moved"] and got["entries"][0]["through"].startswith("2026-11-11T09:45")  # capped at the read
    _, short = run(tmp_path, LIST, "--since", "2026-11-01")
    with pytest.raises(ValueError, match="no `through`"):
        marks.advance("desk", "linkedin", READ_AT, ("focused",), now=now, home=tmp_path, coverage=short)


# --- the declaration ------------------------------------------------------------------------------


def plan(tmp_path: Path, declaration: str):
    import os
    config = tmp_path / "linkedin-sync.yaml"
    config.write_text(declaration, encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "plan", "--config", str(config), "--today", "2026-11-11"],
                          capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "home")})
    return done.returncode, done.stdout + done.stderr


DECLARED = "workspace: desk\ninboxes: [focused]\n"


def test_the_plan_opens_the_new_message_view_and_never_the_bare_page(tmp_path):
    """The bare messaging page opens the newest conversation by itself, which marks an unread one read. The
    new-message view shows the same list beside an empty composer and opens nothing, so no conversation has to
    be set aside for the read to open, and none can gain a new message that the read would then mark read."""
    code, out = plan(tmp_path, DECLARED)
    assert code == 0, out
    assert "open  https://www.linkedin.com/messaging/thread/new/" in out
    assert "https://www.linkedin.com/messaging/ " not in out
    code, out = plan(tmp_path, "workspace: desk\n")  # the focused list is the default
    assert code == 0 and "read  focused:" in out


def test_a_first_read_is_told_how_far_back_to_go_and_to_stop_there(tmp_path):
    """The list loads older conversations for as long as it is scrolled; a read goes back to a named day and stops."""
    code, out = plan(tmp_path, DECLARED)
    assert code == 0
    assert "focused: never read; scroll back to 2026-10-28, stop there, and pass --since 2026-10-28" in out


@pytest.mark.parametrize("declaration, says", [
    ("inboxes: [focused]\n", "workspace"),
    ("workspace: desk\ninboxes: focused\n", "inboxes"),
    ("workspace: desk\ninboxes: []\n", "inboxes"),
])
def test_a_declaration_it_cannot_use_is_refused(tmp_path, declaration, says):
    code, out = plan(tmp_path, declaration)
    assert code == 2 and says in out


def test_the_plan_names_the_day_the_last_read_reached(tmp_path):
    import os
    _, complete = run(tmp_path, LIST, "--since", "2026-11-06")
    spec = importlib.util.spec_from_file_location("sync_watermark", SCRIPTS / "sync_watermark.py")
    marks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(marks)
    marks.advance("desk", "linkedin", READ_AT, ("focused",), now=datetime.fromisoformat("2026-11-11T10:00:00-05:00"),
                  home=tmp_path / "home", coverage=complete)
    code, out = plan(tmp_path, DECLARED)
    assert code == 0 and "focused: read through 2026-11-11; scroll back to that day, stop there, and pass --since 2026-11-11" in out

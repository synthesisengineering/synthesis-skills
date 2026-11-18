# SPDX-License-Identifier: Apache-2.0
"""scripts/chat_page.py: one Messenger chat's text saved from its page when an export lacks it, into the importer's
transcripts, in its format and identity scheme.

The page shows each message's time to the minute, in the browser's time zone, and its whole text; an export holds the
millisecond. A message read from the page is keyed as the importer keys one (its time, then a digest of what it says)
with its minute as the time, and its block says it was read from the page, to the minute; a later import of the same
chat pairs each of its messages with such a block by digest and minute and adds nothing the transcript holds, and a
later page read pairs with an export's blocks the same way. Invented fixtures only: made-up people, made-up words.
Committed before the script.
"""

from __future__ import annotations

import html
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from message_exports_fixtures import (ALEX, BLAIR, CASEY, DAY, T0, dyi_message, dyi_thread, secure_message, split_fences,
                                      write_dyi, write_secure)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "chat_page.py"
ZONE = "America/New_York"
E2EE = "https://www.facebook.com/messages/e2ee/t/4004/"
PLAIN = "https://www.facebook.com/messages/t/4005/"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December")
M1 = (T0 + 37_000, ALEX, "Who is coming on Saturday? 🎉")                # 2024-03-05 14:02:37 UTC, 9:02 AM in New York
M2 = (T0 + 125_000, "You", "I am. Bringing the 👩‍💻 laptop.")      # 14:04:05 UTC
M3 = (T0 + 130_000, "You", "ok")                                          # 14:04:10 UTC, the same minute
M4 = (T0 + 2 * DAY + 3_000, ALEX, "See you then")                          # 2024-03-07 14:02:03 UTC
M5 = (T0 + 3 * DAY, ALEX, "Thanks for coming")


def _fresh(name):
    sys.path.insert(0, str(SCRIPTS))
    try:
        sys.modules.pop(name, None)
        return importlib.import_module(name)
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.fixture
def cp():
    """The page reader, imported afresh for each test, so each test fails on its own while it is missing."""
    return _fresh("chat_page")


@pytest.fixture
def im():
    return _fresh("import_messages")


def when(ms, sep=" "):
    """A message's time as the page writes it, in the browser's zone: `March 5, 2024, 9:02 AM`, with a narrow
    no-break space before AM or PM, or a space."""
    local = datetime.fromtimestamp(ms / 1000, tz=ZoneInfo(ZONE))
    return (f"{MONTHS[local.month - 1]} {local.day}, {local.year}, {local.hour % 12 or 12}:{local.minute:02d}{sep}"
            f"{'AM' if local.hour < 12 else 'PM'}")


def item(ms, sender, text, forms=(1, 2), sep=" "):
    """One message as the extractor saves it: the labels of its article, in the page's two forms."""
    stamp = when(ms, sep)
    shapes = {1: f"Enter, Message sent {stamp} by {sender}: {text}", 2: f"At {stamp}, {sender}: {text}"}
    return {"labels": [shapes[form] for form in forms]}


# the notice where a chat became end-to-end encrypted, as the live page labels it: time zero, `a participant`
NOTICE = item(0, "a participant", "New messages and calls are secured with end-to-end encryption. Invented words follow.")
PAGE = [NOTICE, item(*M1), item(*M2, forms=(1,), sep=" "), item(*M3, forms=(2,)), item(*M4)]


def chat(items, name=ALEX, url=E2EE, zone=ZONE):
    return {"extractor": "messenger-chat/1", "url": url, "title": "Messenger | Facebook", "zone": zone,
            "log": f"Messages in conversation with {name}", "items": items, "dialogs": [], "page": ""}


def save(cp, capsys, tmp_path, reads, *args):
    """`chat_page.py save` on reads saved as the browser tool returns the extractor's value."""
    paths = []
    for data in reads:
        path = tmp_path / f"read-{len(list(tmp_path.glob('read-*.json')))}.json"
        path.write_text(json.dumps(json.dumps(data)), encoding="utf-8")
        paths.append(path)
    code = cp.main(["save", *map(str, paths), *map(str, args)])
    printed = capsys.readouterr()
    return code, printed.out + printed.err


def run(im, capsys, *args):
    code = im.main([str(arg) for arg in args])
    return code, capsys.readouterr().out


def transcripts(out: Path) -> dict:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(out.iterdir())}


def as_export(message):
    ts, sender, text = message
    return ts, CASEY if sender == "You" else sender, text


def blocks(text):
    return re.findall(r"(?ms)^### .*?(?=\n\n---$)", text)


def test_a_chat_read_from_its_page_is_written_as_the_importer_writes_a_transcript(cp, capsys, tmp_path):
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat(PAGE)], "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    assert code == 0, printed
    (name, text), = transcripts(out).items()
    assert re.fullmatch(r"messenger-e2ee-Alex-Sample-[0-9a-f]{8}\.md", name)
    lines = text.split("\n")
    assert lines[0] == "<!-- synthesis-message-exports: transcript, format 2 -->"
    assert lines[1] == "# Messenger — Alex Sample" and lines[2] == f"# Conversation: {name[len('messenger-'):-3]} (page read)"
    assert f"From: `{E2EE}`" in lines and "Participants: Alex Sample, Casey Fixture" in lines
    assert "Messages: 4, 2024-03-05 14:02 UTC to 2024-03-07 14:02 UTC" in lines
    assert split_fences(text)[1] == [M1[2], M2[2], M3[2], M4[2]]  # both label forms, either separator; the notice is none
    assert [line for line in lines if line.startswith("### ")] == [
        "### Alex Sample — 14:02 UTC", "### Casey Fixture — 14:04 UTC", "### Casey Fixture — 14:04 UTC",
        "### Alex Sample — 14:02 UTC"]  # `You` is the principal, named as the export names them
    assert lines.count(f"**Read from the page:** `{E2EE}`, to the minute") == 4
    ids = re.findall(r"\*\*Message ID:\*\* (\S+):(\d+)-[0-9a-f]{10}(-\d+)?", text)
    assert {cid for cid, _, _ in ids} == {name[len("messenger-"):-3]}
    assert [int(ms) for _, ms, _ in ids] == [T0, T0 + 120_000, T0 + 120_000, T0 + 2 * DAY]  # each time is its minute
    assert "it reaches 2024-03-06, the day asked for" in printed and "1 notice not written" in printed
    assert f"transcript: {name} (new): 4 new, 0 already in it" in printed
    assert M1[2] not in printed and "Saturday" not in printed  # no line carries message text


def test_a_later_download_of_the_same_chat_adds_only_what_the_page_did_not_hold(cp, im, capsys, tmp_path):
    out = tmp_path / "out"
    assert save(cp, capsys, tmp_path, [chat(PAGE)], "--out", out, "--principal", CASEY, "--since", "2024-03-06")[0] == 0
    (path,) = out.iterdir()
    before = path.read_text(encoding="utf-8")
    write_secure(tmp_path / "secure", "Alex Sample_0", [ALEX, CASEY],
                 [secure_message(sender, ts, text) for ts, sender, text in map(as_export, (M1, M2, M3, M4, M5))])
    code, printed = run(im, capsys, tmp_path / "secure", "--out", out)
    assert code == 0, printed
    assert "messages: 1 new; 4 already in transcripts" in printed and "0 new transcripts, 1 extended" in printed
    assert list(out.iterdir()) == [path]  # the chat stays in one transcript
    text = path.read_text(encoding="utf-8")
    assert split_fences(text)[1] == [M1[2], M2[2], M3[2], M4[2], M5[2]]
    assert len(blocks(before)) == 4 and all(block in text for block in blocks(before))  # kept byte for byte
    stamp = path.stat().st_mtime_ns
    code, printed = run(im, capsys, tmp_path / "secure", "--out", out)
    assert code == 0 and "messages: 0 new; 5 already in transcripts" in printed and path.stat().st_mtime_ns == stamp


def test_a_plain_chat_read_from_its_page_is_extended_by_the_regular_export_that_later_holds_it(cp, im, capsys, tmp_path):
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat(PAGE, url=PLAIN)], "--out", out, "--principal", CASEY, "--since",
                         "2024-03-06")
    assert code == 0, printed
    (path,) = out.iterdir()
    assert re.fullmatch(r"messenger-page-Alex-Sample-[0-9a-f]{8}\.md", path.name)  # no export names a plain chat's folder yet
    write_dyi(tmp_path / "regular", "alexsample_4005", [dyi_thread(ALEX, [ALEX, CASEY], [
        dyi_message(sender, ts, text) for ts, sender, text in map(as_export, (M5, M4, M3, M2, M1))])])
    code, printed = run(im, capsys, tmp_path / "regular", "--out", out)
    assert code == 0, printed
    assert "messages: 1 new; 4 already in transcripts" in printed and list(out.iterdir()) == [path]
    assert split_fences(path.read_text(encoding="utf-8"))[1] == [M1[2], M2[2], M3[2], M4[2], M5[2]]


def test_a_page_read_extends_the_transcript_an_export_wrote_and_adds_only_what_it_lacked(cp, im, capsys, tmp_path):
    out = tmp_path / "out"
    write_dyi(tmp_path / "older", "alexsample_4005", [dyi_thread(ALEX, [ALEX, CASEY], [
        dyi_message(sender, ts, text) for ts, sender, text in map(as_export, (M3, M2, M1))])])
    assert run(im, capsys, tmp_path / "older", "--out", out)[0] == 0
    path = out / "messenger-dyi-alexsample_4005.md"
    header = path.read_text(encoding="utf-8").split("\n")[1:6]
    code, printed = save(cp, capsys, tmp_path, [chat(PAGE, url=PLAIN)], "--out", out, "--principal", CASEY, "--since",
                         "2024-03-06")
    assert code == 0, printed
    assert "transcript: messenger-dyi-alexsample_4005.md (extended): 1 new, 3 already in it" in printed
    text = path.read_text(encoding="utf-8")
    assert list(out.iterdir()) == [path] and split_fences(text)[1] == [M1[2], M2[2], M3[2], M4[2]]
    assert text.split("\n")[1:6] == header  # the export's title, source and participants stay
    write_dyi(tmp_path / "newer", "alexsample_4005", [dyi_thread(ALEX, [ALEX, CASEY], [
        dyi_message(sender, ts, text) for ts, sender, text in map(as_export, (M5, M4, M3, M2, M1))])])
    code, printed = run(im, capsys, tmp_path / "newer", "--out", out)
    assert code == 0 and "messages: 1 new; 4 already in transcripts" in printed
    assert split_fences(path.read_text(encoding="utf-8"))[1] == [M1[2], M2[2], M3[2], M4[2], M5[2]]


def test_a_message_like_one_in_another_chat_never_draws_that_chat_into_this_transcript(cp, im, capsys, tmp_path):
    """The principal said `ok` to two people in one minute: the same digest and the same minute. A chat with other
    people is never placed by such a pair."""
    out = tmp_path / "out"
    assert save(cp, capsys, tmp_path, [chat(PAGE)], "--out", out, "--principal", CASEY, "--since", "2024-03-06")[0] == 0
    (page,) = out.iterdir()
    before = page.read_bytes()
    write_dyi(tmp_path / "regular", "blairexample_5005", [dyi_thread(BLAIR, [BLAIR, CASEY], [
        dyi_message(CASEY, T0 + 140_000, "ok")])])
    code, printed = run(im, capsys, tmp_path / "regular", "--out", out)
    assert code == 0 and "1 new transcripts, 0 extended" in printed, printed
    assert (out / "messenger-dyi-blairexample_5005.md").exists() and page.read_bytes() == before


def test_labels_that_disagree_are_not_read_and_the_read_says_so(cp, capsys, tmp_path):
    stamp = when(M1[0])
    torn = {"labels": [f"Enter, Message sent {stamp} by {ALEX}: one thing", f"At {stamp}, {ALEX}: another thing"]}
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat([torn, item(*M4)])], "--out", out, "--since", "2024-03-08")
    assert code == 1 and "1 could not be read" in printed
    assert split_fences(next(iter(transcripts(out).values())))[1] == [M4[2]]


def test_a_read_with_the_principals_messages_needs_their_name(cp, capsys, tmp_path):
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat(PAGE)], "--out", out, "--since", "2024-03-06")
    assert code == 2 and "--principal" in printed and "nothing written" in printed and not out.exists()


def test_a_read_that_does_not_reach_the_day_asked_for_saves_what_it_read_and_says_so(cp, capsys, tmp_path):
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat(PAGE)], "--out", out, "--principal", CASEY, "--since", "2024-03-01")
    assert code == 1
    assert ("it stops short of 2024-03-01, the day asked for: scroll the log further up and read again" in printed)
    assert "back to 2024-03-05 09:02 America/New_York" in printed and len(transcripts(out)) == 1


CRYPT = NOTICE


def test_the_encryption_notice_mid_log_is_neither_a_message_nor_a_day(cp, capsys, tmp_path):
    """Live, 2026-11-14: the notice where a chat became end-to-end encrypted carries a message's label, sent at time zero
    in the browser's zone (December 31, 1969, 7:00 PM in New York) by `a participant`, and sits between the messages
    from before the switch and after it, not at the chat's start."""
    after = (T0 + 400 * DAY, ALEX, "Back on this chat after the switch")  # 2025-04-09
    log, out = [item(*M1), item(*M4), CRYPT, item(*after)], tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat(log)], "--out", out, "--since", "2024-03-06")
    assert code == 0, printed
    text = next(iter(transcripts(out).values()))
    assert split_fences(text)[1] == [M1[2], M4[2], after[2]] and "a participant" not in text and "1970" not in text
    assert "back to 2024-03-05 09:02 America/New_York" in printed and "1 notice not written" in printed
    assert "1969" not in printed and "start" not in printed and "held" not in printed
    code, printed = save(cp, capsys, tmp_path, [chat(log)], "--out", tmp_path / "other", "--since", "2024-03-01")
    assert code == 1 and "it stops short of 2024-03-01" in printed  # the notice's false date reaches no day


def test_a_label_dated_before_2004_02_04_carries_no_date_and_is_held_for_a_person(cp, capsys, tmp_path):
    early = int(datetime(2003, 6, 1, 16, 0, tzinfo=timezone.utc).timestamp() * 1000)
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat([item(early, ALEX, "Dated before Facebook began"), item(*M4)])],
                         "--out", out, "--since", "2024-03-08")
    assert code == 1 and "1 held for a person" in printed and "before 2004-02-04" in printed and "2003" not in printed
    assert split_fences(next(iter(transcripts(out).values())))[1] == [M4[2]]

@pytest.mark.parametrize("read, says", [
    (dict(chat([]), log=None, url="https://www.facebook.com/login/?next=%2Fmessages%2F",
          page="Log in to Facebook\nEmail address or phone number\nPassword\n"), "stop and tell the principal"),
    (dict(chat(PAGE), dialogs=["Enter your PIN to restore your chat history"]), "stop and tell the principal"),
    (dict(chat([]), log=None, url="https://www.facebook.com/messages/t/", page="Chats\nNo chats selected\n"), "no chat log"),
    (dict(chat(PAGE), url="https://www.example.com/messages/e2ee/t/4004/"), "not a Messenger chat"),
    (dict(chat(PAGE), zone="Mars/Olympus_Mons"), "time zone"),
    (dict(chat(PAGE), extractor="messenger-list/1"), "not the extractor's saved output"),
], ids=["sign-in", "pin", "no-chat", "another-site", "zone", "another-extractor"])
def test_a_read_it_cannot_trust_is_refused_and_nothing_is_written(cp, capsys, tmp_path, read, says):
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [read], "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    assert code == 2 and says in printed and not out.exists()


def test_two_reads_of_one_chat_merge_and_a_read_again_adds_nothing(cp, capsys, tmp_path):
    """A log may drop what it scrolled past: reads taken as it scrolls are saved together, each message once."""
    out = tmp_path / "out"
    reads = [chat([item(*M2), item(*M3), item(*M4)]), chat([NOTICE, item(*M1), item(*M2), item(*M3)])]
    code, printed = save(cp, capsys, tmp_path, reads, "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    assert code == 0, printed
    (path,) = out.iterdir()
    assert split_fences(path.read_text(encoding="utf-8"))[1] == [M1[2], M2[2], M3[2], M4[2]]
    assert "page read: 4 messages from 2 reads" in printed
    stamp = path.stat().st_mtime_ns
    code, printed = save(cp, capsys, tmp_path, reads, "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    assert code == 0 and "(unchanged): 0 new, 4 already in it" in printed and path.stat().st_mtime_ns == stamp
    code, printed = save(cp, capsys, tmp_path, [reads[0], chat([item(*M5)], url=PLAIN)], "--out", out, "--principal", CASEY,
                         "--since", "2024-03-06")
    assert code == 2 and "two chats" in printed


def test_a_later_read_of_the_chat_lands_in_its_transcript_though_it_holds_none_of_its_messages(cp, capsys, tmp_path):
    out = tmp_path / "out"
    save(cp, capsys, tmp_path, [chat([item(*M1), item(*M2)])], "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    code, printed = save(cp, capsys, tmp_path, [chat([item(*M4)])], "--out", out, "--since", "2024-03-08")
    assert code == 0, printed
    (path,) = out.iterdir()
    assert "(extended): 1 new, 0 already in it" in printed
    assert split_fences(path.read_text(encoding="utf-8"))[1] == [M1[2], M2[2], M4[2]]


def test_into_names_the_transcript_to_extend_and_refuses_one_of_other_people(cp, im, capsys, tmp_path):
    out = tmp_path / "out"
    write_secure(tmp_path / "secure", "Alex Sample_0", [ALEX, CASEY],
                 [secure_message(sender, ts, text) for ts, sender, text in map(as_export, (M1, M2))])
    write_dyi(tmp_path / "regular", "blairexample_5005", [dyi_thread(BLAIR, [BLAIR, CASEY], [dyi_message(BLAIR, T0, "hi")])])
    assert run(im, capsys, tmp_path / "secure", "--out", out)[0] == 0
    assert run(im, capsys, tmp_path / "regular", "--out", out)[0] == 0
    (download,) = [name for name in transcripts(out) if name.startswith("messenger-e2ee-")]
    code, printed = save(cp, capsys, tmp_path, [chat([item(*M4)])], "--out", out, "--since", "2024-03-08", "--into",
                         "messenger-dyi-blairexample_5005.md")
    assert code == 2 and "does not name Alex Sample" in printed
    code, printed = save(cp, capsys, tmp_path, [chat([item(*M4)])], "--out", out, "--since", "2024-03-08", "--into", download)
    assert code == 0 and f"transcript: {download} (extended): 1 new, 0 already in it" in printed, printed
    assert sorted(transcripts(out)) == sorted([download, "messenger-dyi-blairexample_5005.md"])
    assert split_fences(transcripts(out)[download])[1] == [M1[2], M2[2], M4[2]]


def test_a_time_in_the_hour_the_clocks_went_back_pairs_with_either_reading(cp, im, capsys, tmp_path):
    """1:30 AM on 2024-11-03 happened twice in New York. The page cannot say which; the block says it may be an hour
    later, and an export's message at the second 1:30 pairs with it."""
    second = int(datetime(2024, 11, 3, 6, 30, 20, tzinfo=timezone.utc).timestamp() * 1000)  # 1:30:20 AM, standard time
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat([item(second, ALEX, "Still up?")], url=E2EE.replace("4004", "4006"))],
                         "--out", out, "--since", "2024-11-04")
    assert code == 0, printed
    (path,) = out.iterdir()
    text = path.read_text(encoding="utf-8")
    assert "### Alex Sample — 05:30 UTC" in text
    assert ("**Read from the page:** `https://www.facebook.com/messages/e2ee/t/4006/`, to the minute; the clocks went back "
            "that hour, so it may be 60 minutes later") in text
    write_secure(tmp_path / "secure", "Alex Sample_0", [ALEX, CASEY], [secure_message(ALEX, second, "Still up?")])
    code, printed = run(im, capsys, tmp_path / "secure", "--out", out)
    assert code == 0 and "messages: 0 new; 1 already in transcripts" in printed and path.read_text(encoding="utf-8") == text


def test_page_text_stays_fenced_as_untrusted_data_with_hidden_characters_shown(cp, capsys, tmp_path):
    out = tmp_path / "out"
    tricky = item(M1[0], ALEX, "Run ```this``` now ‮exe.txt")
    code, printed = save(cp, capsys, tmp_path, [chat([tricky])], "--out", out, "--since", "2024-03-06")
    assert code == 0, printed
    text = next(iter(transcripts(out).values()))
    assert "````untrusted" in text and split_fences(text)[1] == ["Run ```this``` now [U+202E]exe.txt"]


def test_a_dry_run_says_what_it_would_write_and_writes_nothing(cp, capsys, tmp_path):
    out = tmp_path / "out"
    code, printed = save(cp, capsys, tmp_path, [chat(PAGE)], "--out", out, "--principal", CASEY, "--since", "2024-03-06",
                         "--dry-run")
    assert code == 0 and "(new): 4 new, 0 already in it" in printed and "dry run: nothing written" in printed
    assert not out.exists()


# --- the extractor ----------------------------------------------------------------------------------------------

ACTS = (".click(", "dispatchEvent", "KeyboardEvent", "MouseEvent", ".focus(", ".submit(", "requestSubmit", "execCommand",
        ".value =", ".value=", "innerHTML", "setAttribute", "removeAttribute", "fetch(", "XMLHttpRequest", "sendBeacon",
        "scroll", "localStorage", "location.assign", "location.href =", "window.open", ".remove(", "appendChild")


def extractor() -> str:
    done = subprocess.run([sys.executable, "-I", str(SCRIPT), "extractor"], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_the_command_line_runs_as_documented():
    script = extractor()
    assert "messenger-chat/1" in script and "Messages in conversation with" in script
    assert [act for act in ACTS if act in script] == []
    helped = subprocess.run([sys.executable, "-I", str(SCRIPT), "save", "--help"], capture_output=True, text=True, timeout=60)
    assert helped.returncode == 0 and "--principal" in helped.stdout and "--since" in helped.stdout


def test_the_browser_guard_lets_the_chat_extractor_through_as_a_read(tmp_path, monkeypatch):
    """On a Messenger site no page script runs but the plugin's own read-only ones: the extractor is one, so it passes,
    and the same call with a click added is refused."""
    for key in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_DATA_HOME", "RITUAL_STATE_DIR"):
        monkeypatch.setenv(key, str(tmp_path / key.lower()))
    from synthesis import guards
    use = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_1", "name": "mcp__claude-in-chrome__browser_batch", "input": {}}]}}
    listing = f"Done\n\nTab Context:\n- Executed on tabId: 7\n- Available tabs:\n  • tabId 7: \"Messenger\" (\"{E2EE}\")"
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": [{"type": "text", "text": listing}]}]}}
    record = tmp_path / "transcript.jsonl"
    record.write_text(json.dumps(use) + "\n" + json.dumps(result) + "\n", encoding="utf-8")
    session = {"session_id": "S-chat-read", "transcript_path": str(record)}
    script = extractor()
    assert not guards.SCRIPT_ACTS.search(script)
    read = {"action": "javascript_exec", "text": script, "tabId": 7}
    assert guards.check("mcp__claude-in-chrome__javascript_tool", read, {}, session=session) is None
    held = {"action": "javascript_exec", "text": script + "\ndocument.querySelector('[role=\"article\"]').click()", "tabId": 7}
    assert "shipped" in (guards.check("mcp__claude-in-chrome__javascript_tool", held, {}, session=session) or "")


def find_chromium():
    configured = os.environ.get("SYNTHESIS_TEST_CHROMIUM")
    if configured:
        return configured if Path(configured).is_file() else None
    on_path = next(filter(None, (shutil.which(n) for n in
                                 ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome"))), None)
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "synthesis" / "browsers"  # where AGENTS.md installs it
    found = sorted(cache.glob("chrome-headless-shell/*/chrome-headless-shell-*/chrome-headless-shell"),
                   key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.parent.name)])
    return on_path or (str(found[-1]) if found else None)


CHROMIUM = find_chromium()
if CHROMIUM is None and os.environ.get("SYNTHESIS_REQUIRE_CHROMIUM") == "1":  # CI: a missing browser fails
    raise RuntimeError("SYNTHESIS_REQUIRE_CHROMIUM=1 but no Chromium was found")


def article_html(entry) -> str:
    if "text" in entry:
        return f"<div role=\"article\"><div>{html.escape(entry['text'])}</div></div>"
    first, *rest = entry["labels"]
    inner = "".join(f"<div aria-label=\"{html.escape(label)}\"><span>words</span></div>" for label in rest)
    return f"<div role=\"article\"><div role=\"button\" aria-label=\"{html.escape(first)}\">{inner}</div></div>"


@pytest.mark.skipif(CHROMIUM is None, reason="no Chromium: set SYNTHESIS_TEST_CHROMIUM, put one on PATH, or install it as AGENTS.md says")
def test_the_extractor_on_a_page_shaped_like_a_chat_saves_what_save_reads():
    page = ("<!doctype html><html><head><meta charset=\"utf-8\"><title>Messenger | Facebook</title></head><body>"
            "<div role=\"grid\" aria-label=\"Chats\"><div role=\"row\"><a href=\"/messages/e2ee/t/4004/\">Alex Sample</a>"
            "</div></div><div role=\"main\"><div role=\"log\" aria-label=\"Messages in conversation with Alex Sample\">"
            + "".join(map(article_html, PAGE)) + "</div></div><script>var found = " + extractor()
            + ";\nvar out = document.createElement('pre'); out.id = 'chat-result'; out.textContent = found;"
            " document.body.appendChild(out);</script></body></html>")
    work = Path(tempfile.mkdtemp(prefix="messenger-chat-", dir="/tmp"))  # Chromium's socket path limit is short
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
    found = re.search(r'<pre id="chat-result">(.*?)</pre>', done.stdout, re.S)
    assert found, "the page did not reach its driver"
    read = json.loads(html.unescape(found.group(1)))
    assert read["extractor"] == "messenger-chat/1" and read["log"] == "Messages in conversation with Alex Sample"
    assert isinstance(read["zone"], str) and read["zone"] and read["dialogs"] == []
    assert read["items"] == PAGE



# --- review round 1 (2026-11-14): a failing test for each finding, before its fix -----------------------------------


def said(out):
    """(sender, text) of each message in the one transcript in out, in its order."""
    (text,) = transcripts(out).values()
    heads = [line[len("### "):].rsplit(" — ", 1)[0] for line in text.split("\n") if line.startswith("### ")]
    return list(zip(heads, split_fences(text)[1]))


def test_review_06_two_peoples_ok_in_one_minute_each_pair_with_their_own(cp, im, capsys, tmp_path):
    alex_ok, casey_ok, later = T0 + 150_000, T0 + 170_000, T0 + 600_000
    want = sorted([(ALEX, "ok"), (CASEY, "ok"), (ALEX, "See you at noon")])
    out = tmp_path / "page-first"
    save(cp, capsys, tmp_path, [chat([item(casey_ok, "You", "ok"), item(later, ALEX, "See you at noon")])], "--out", out,
         "--principal", CASEY, "--since", "2024-03-06")
    write_secure(tmp_path / "ea", "Alex Sample_1", [ALEX, CASEY], [secure_message(ALEX, alex_ok, "ok"),
                 secure_message(CASEY, casey_ok, "ok"), secure_message(ALEX, later, "See you at noon")])
    assert run(im, capsys, tmp_path / "ea", "--out", out)[0] == 0
    assert sorted(said(out)) == want
    out = tmp_path / "export-first"
    write_secure(tmp_path / "eb", "Alex Sample_1", [ALEX, CASEY], [secure_message(CASEY, casey_ok, "ok"),
                 secure_message(ALEX, later, "See you at noon")])
    assert run(im, capsys, tmp_path / "eb", "--out", out)[0] == 0
    save(cp, capsys, tmp_path, [chat([item(alex_ok, ALEX, "ok"), item(casey_ok, "You", "ok"), item(later, ALEX, "See you at noon")])],
         "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    assert sorted(said(out)) == want


def test_review_07_a_page_read_joins_another_chats_transcript_only_on_evidence_about_the_chat(cp, im, capsys, tmp_path):
    # A: the same greeting in two groups of the same people: a read of "Cousins" stays out of "Family", and says so
    out = tmp_path / "a"
    write_secure(tmp_path / "family", "Family_1", [ALEX, BLAIR, CASEY], [secure_message(BLAIR, T0, "Dinner at 7?"),
                 secure_message(ALEX, T0 + 150_000, "Happy holidays, everyone!"), secure_message(CASEY, T0 + 400_000, "Thanks!")],
                 thread_name="Family")
    assert run(im, capsys, tmp_path / "family", "--out", out)[0] == 0
    cousins = chat([item(T0 + 140_000, ALEX, "Happy holidays, everyone!"), item(T0 + 360_000, BLAIR, "Same to you!"),
                    item(T0 + 420_000, "You", "Who is hosting this year?")], name="Cousins", url=E2EE.replace("4004", "5005"))
    code, printed = save(cp, capsys, tmp_path, [cousins], "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    family = [text for name, text in transcripts(out).items() if "Family" in name]
    assert len(transcripts(out)) == 2 and "Who is hosting" not in family[0], printed
    assert "not joined" in printed and "Family" in printed
    # B: a read of only the principal's messages never draws the chat with Blair into it, nor gives it Blair's name
    out = tmp_path / "b"
    mine = chat([item(T0 + 130_000, "You", "ok"), item(T0 + 1_080_000, "You", "Call me when you land")])
    save(cp, capsys, tmp_path, [mine], "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    (alex,) = transcripts(out)
    write_secure(tmp_path / "blair", "Blair Example_2", [BLAIR, CASEY], [secure_message(BLAIR, T0 + 60_000, "Can you confirm?"),
                 secure_message(CASEY, T0 + 140_000, "ok"), secure_message(BLAIR, T0 + 300_000, "Great, thanks")])
    assert run(im, capsys, tmp_path / "blair", "--out", out)[0] == 0
    assert len(transcripts(out)) == 2 and "Can you confirm?" not in transcripts(out)[alex]
    assert transcripts(out)[alex].split("\n")[1] == "# Messenger — Alex Sample"
    # C: nor keeps the regular export of that chat from importing
    out = tmp_path / "c"
    write_dyi(tmp_path / "c1", "blairexample_20002", [dyi_thread(BLAIR, [BLAIR, CASEY], [dyi_message(BLAIR, T0 + 60_000, "Can you confirm?")])])
    assert run(im, capsys, tmp_path / "c1", "--out", out)[0] == 0
    save(cp, capsys, tmp_path, [mine], "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    write_dyi(tmp_path / "c2", "blairexample_20002", [dyi_thread(BLAIR, [BLAIR, CASEY], [
        dyi_message(BLAIR, T0 + 300_000, "Great, thanks"), dyi_message(CASEY, T0 + 140_000, "ok"),
        dyi_message(BLAIR, T0 + 60_000, "Can you confirm?")])])
    code, printed = run(im, capsys, tmp_path / "c2", "--out", out)
    assert code == 0 and "skipped conversation" not in printed, printed
    assert "Great, thanks" in transcripts(out)["messenger-dyi-blairexample_20002.md"]


def test_review_08_a_message_with_a_link_is_written_once_in_either_order(cp, im, capsys, tmp_path):
    words, linked, nice = "Look: https://example.test/flyer", T0 + 130_000, T0 + 190_000
    for order in ("page-first", "export-first"):
        base = tmp_path / order
        base.mkdir()
        out = base / "out"

        def page():
            return save(cp, capsys, base, [chat([item(linked, ALEX, words), item(nice, "You", "Nice")], url=PLAIN)], "--out", out,
                        "--principal", CASEY, "--since", "2024-03-06")

        def export():
            write_dyi(base / "export", "alexsample_10001", [dyi_thread(ALEX, [ALEX, CASEY], [
                dyi_message(CASEY, nice, "Nice"), dyi_message(ALEX, linked, words, share={"link": "https://example.test/flyer"})])])
            return run(im, capsys, base / "export", "--out", out)

        for step in ((page, export) if order == "page-first" else (export, page)):
            code, printed = step()
            assert code == 0, (order, printed)
        held = [text for name, body in transcripts(out).items() for text in split_fences(body)[1]]
        assert held.count(words) == 1 and len(transcripts(out)) == 1, (order, held)


def test_review_09_a_day_is_reached_only_by_a_message_from_before_it(cp, capsys, tmp_path):
    evening = T0 + 32_280_000  # 18:00 in New York on 2024-03-05; the morning's messages were not read
    read = [chat([item(evening, ALEX, "Are we still on?"), item(evening + 60_000, "You", "Yes")])]
    code, printed = save(cp, capsys, tmp_path, read, "--out", tmp_path / "out", "--principal", CASEY, "--since", "2024-03-05")
    assert code == 1 and "it stops short of 2024-03-05" in printed, printed
    code, printed = save(cp, capsys, tmp_path, read, "--out", tmp_path / "out", "--principal", CASEY, "--since", "2024-03-06")
    assert code == 0 and "it reaches 2024-03-06" in printed, printed


def test_review_10_reads_that_share_no_message_are_not_one_read(cp, capsys, tmp_path):
    newer = chat([item(T0 + 2 * DAY, ALEX, "Bring the chairs?"), item(T0 + 2 * DAY + 60_000, "You", "Yes, four")])
    older = chat([item(T0 - DAY, ALEX, "Party next week"), item(T0 - DAY + 60_000, "You", "Count me in")])
    code, printed = save(cp, capsys, tmp_path, [newer, older], "--out", tmp_path / "out", "--principal", CASEY, "--since", "2024-03-05")
    assert code == 1 and "do not overlap" in printed and "back to 2024-03-07" in printed, printed
    assert len(split_fences(next(iter(transcripts(tmp_path / "out").values())))[1]) == 4  # every message read is kept


def test_review_11_an_article_whose_labels_match_no_message_is_held_not_dropped(cp, capsys, tmp_path):
    items = [item(*M1), {"text": "Alex Sample\nI can bring the projector\nEnter"}, item(*M4)]
    code, printed = save(cp, capsys, tmp_path, [chat(items)], "--out", tmp_path / "out", "--since", "2024-03-06")
    assert code == 1 and "1 held for a person" in printed and "notice" not in printed, printed


def test_review_14_a_sender_name_holding_a_colon_is_read_by_the_name_the_log_gives(cp, capsys, tmp_path):
    read = [chat([item(M1[0], "Doc: Brown", "Are you free?")], name="Doc: Brown")]
    code, printed = save(cp, capsys, tmp_path, read, "--out", tmp_path / "out", "--since", "2024-03-06")
    assert code == 0 and said(tmp_path / "out") == [("Doc: Brown", "Are you free?")], printed


def test_review_15_twin_messages_where_two_reads_meet_are_never_merged_silently(cp, capsys, tmp_path):
    early, ok1, ok2, later = T0 + 37_000, T0 + 130_000, T0 + 170_000, T0 + 600_000
    newer = chat([item(ok2, "You", "ok"), item(later, ALEX, "Great, see you")])
    older = chat([item(early, ALEX, "Can you make it at 10?"), item(ok1, "You", "ok")])
    code, printed = save(cp, capsys, tmp_path, [newer, older], "--out", tmp_path / "out", "--principal", CASEY, "--since", "2024-03-05")
    oks = [text for _, text in said(tmp_path / "out")].count("ok")
    assert code == 1 and oks == 1 and "1 held for a person" in printed and "twin" in printed, printed


def test_review_16_a_chat_split_between_a_page_read_and_its_folder_imports_on(cp, im, capsys, tmp_path):
    out = tmp_path / "out"
    save(cp, capsys, tmp_path, [chat([item(T0 + 2 * DAY, ALEX, "See you then"), item(T0 + 2 * DAY + 60_000, "You", "Bring snacks?")],
                                     url=PLAIN)], "--out", out, "--principal", CASEY, "--since", "2024-03-08")
    write_dyi(tmp_path / "e1", "alexsample_4005", [dyi_thread(ALEX, [ALEX, CASEY], [
        dyi_message(CASEY, T0 + 125_000, "Me"), dyi_message(ALEX, T0 + 37_000, "Who is coming?")])])
    assert run(im, capsys, tmp_path / "e1", "--out", out)[0] == 0
    write_dyi(tmp_path / "e2", "alexsample_4005", [dyi_thread(ALEX, [ALEX, CASEY], [
        dyi_message(ALEX, T0 + 3 * DAY, "Thanks for coming"), dyi_message(CASEY, T0 + 2 * DAY + 60_500, "Bring snacks?"),
        dyi_message(ALEX, T0 + 2 * DAY + 20_000, "See you then"), dyi_message(CASEY, T0 + 125_000, "Me"),
        dyi_message(ALEX, T0 + 37_000, "Who is coming?")])])
    code, printed = run(im, capsys, tmp_path / "e2", "--out", out)
    texts = sorted(text for body in transcripts(out).values() for text in split_fences(body)[1])
    assert code == 0 and "skipped conversation" not in printed and "page read" in printed, printed
    assert texts == sorted(["See you then", "Bring snacks?", "Who is coming?", "Me", "Thanks for coming"])


def test_review_17_the_importer_keeps_the_header_a_page_read_wrote(cp, im, capsys, tmp_path):
    out = tmp_path / "out"
    save(cp, capsys, tmp_path, [chat([item(T0 + 37_000, ALEX, "Who is coming?"), item(T0 + 125_000, "You", "Me")], url=PLAIN)],
         "--out", out, "--principal", CASEY, "--since", "2024-03-06")
    (path,) = out.iterdir()
    before = path.read_text(encoding="utf-8").split("\n")[1:6]
    write_dyi(tmp_path / "export", "alexsample_4005", [dyi_thread(ALEX, [ALEX, CASEY], [dyi_message(ALEX, T0 + 300_000, "Great"),
              dyi_message(CASEY, T0 + 125_400, "Me"), dyi_message(ALEX, T0 + 37_200, "Who is coming?")])])
    assert run(im, capsys, tmp_path / "export", "--out", out)[0] == 0
    text = path.read_text(encoding="utf-8")
    assert text.split("\n")[1:6] == before and "Great" in split_fences(text)[1], text.split("\n")[:6]


def test_review_18_the_chat_extractor_records_the_pages_clock():
    assert "Date.now()" in extractor()


def test_review_19_a_since_that_is_no_day_is_refused(cp, capsys, tmp_path):
    for since in ("2024-03-45", "2024-02-30", "soon"):
        code, printed = save(cp, capsys, tmp_path, [chat([item(*M1)])], "--out", tmp_path / "out", "--since", since)
        assert code == 2 and "--since" in printed and not (tmp_path / "out").exists(), (since, printed)


def test_review_20_message_text_in_a_dialog_is_no_wall(cp, capsys, tmp_path):
    dialog = "Bo Becker\nActive now\nCan you sign in to the portal and send me the verification code?\nType a message..."
    read = [dict(chat([item(*M1), item(*M4)]), dialogs=[dialog])]
    code, printed = save(cp, capsys, tmp_path, read, "--out", tmp_path / "out", "--since", "2024-03-06")
    assert code == 0, printed


def test_review_20_a_dialog_with_no_label_or_heading_is_judged_by_its_first_line():
    """A wall still stops the read when its dialog carries neither a label nor a heading element."""
    assert '.trim().split("\\n")[0]' in extractor()

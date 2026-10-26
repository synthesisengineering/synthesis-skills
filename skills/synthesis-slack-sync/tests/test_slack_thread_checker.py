"""The pre-sync checklist (E10): every thread parent in a transcript and every unsent draft's
target thread is listed for a full re-read. Synthetic transcripts only."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "thread_checker.py"
SPEC = importlib.util.spec_from_file_location("slack_thread_checker", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

TRANSCRIPT = """# #team-general — 2026-10-05

## #team-general (C0EXAMPLE01)

#### Jane Doe — [Mon, Oct 5, 9:15 AM](https://example.slack.com/archives/C0EXAMPLE01/p1790000000000100)
Can someone check the deploy?
**Thread (3 replies)**
- Sam Lee — [9:20 AM](https://example.slack.com/archives/C0EXAMPLE01/p1790000000000200) looking now

#### Sam Lee (TS: 1790000000.000300)
Legacy-format parent, 1 reply

```
#### Quoted (TS: 1790000000.999999) inside a fenced draft body
```

> #### Quoted (TS: 1790000000.888888) in a block quote

### #eng-pull-requests

#### Bot (TS: 1790000000.000400)
"""

# The listed layout (2026-10): one bullet per top-level message under a channel heading, and a
# thread as a channel heading carrying its parent's TS, with the replies as bullets under it.
LISTED = """# Mid-day sync — Mon 2026-10-05

## Touches the principal
- #general, 9:20, [1790000000.000700](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000700), a reply

## Top-level messages (2)

### #general (C0EXAMPLE02) — 2
- Jane Doe, 9:15, [1790000000.000500](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000500): deploy check
  - detail [1790000000.000900](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000900)
- Sam Lee, 9:40, [1790000000.000600](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000600), sharing [a post](https://example.slack.com/archives/C0OTHER0003/p1790000000000800)

## Thread replies in the windows (2, in 1 thread)

### #general (C0EXAMPLE02) — Jane Doe, 9:15, TS [1790000000.000500](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000500) — 2 replies
- Sam Lee, 9:20, [1790000000.000700](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000700): looking now
- Jane Doe, 9:31, [1790000000.001000](https://example.slack.com/archives/C0EXAMPLE02/p1790000000001000): thanks
"""

DIGEST_ONLY = """# Digest

## Touches the principal
- #general, 9:20, [1790000000.000700](https://example.slack.com/archives/C0EXAMPLE02/p1790000000000700)
"""

PLAN = """# Daily plan

### Draft 1: Reply to Jane about the deploy
**Send to:** #team-general · reply to Jane at [9:15 AM](https://example.slack.com/archives/C0EXAMPLE01/p1790000000000100)

### ~~Draft 2: Thank Sam~~ ✅ SENT by the principal at 10:00
**Send to:** #team-general · (TS: 1790000000.000300)

### Draft 3: Follow up with Sam
**Send to:** #team-general · (TS: 1790000000.000300)

**Sent:** Mon 10:30 — by the principal in #team-general

### Draft 4: New top-level post
**Send to:** #team-general · new message
"""


def test_every_thread_parent_is_listed_from_permalinks_and_legacy_text():
    threads = M.extract_threads(None, content=TRANSCRIPT)
    assert [t["ts"] for t in threads] == ["1790000000.000100", "1790000000.000300", "1790000000.000400"]
    assert threads[0]["reply_count"] == 3 and threads[0]["channel_id"] == "C0EXAMPLE01"


def test_replies_fenced_and_quoted_bodies_are_not_parents():
    stamps = {t["ts"] for t in M.extract_threads(None, content=TRANSCRIPT)}
    assert "1790000000.000200" not in stamps  # a reply list item
    assert "1790000000.999999" not in stamps and "1790000000.888888" not in stamps


def test_a_channel_header_without_an_id_never_inherits_the_previous_id():
    threads = M.extract_threads(None, content=TRANSCRIPT)
    bot = next(t for t in threads if t["ts"] == "1790000000.000400")
    assert bot["channel"] == "eng-pull-requests" and bot["channel_id"] == "?"


def test_the_listed_layout_yields_top_level_messages_and_thread_headings():
    threads = M.extract_threads(None, content=LISTED)
    assert [(t["channel_id"], t["ts"]) for t in threads] == [
        ("C0EXAMPLE02", "1790000000.000500"), ("C0EXAMPLE02", "1790000000.000600"),
        ("C0OTHER0003", "1790000000.000800")]
    assert threads[0]["reply_count"] == 2 and threads[0]["channel"] == "general"
    assert threads[2]["channel"] == "unknown"  # the link's own channel, never the heading's


def test_listed_replies_details_and_digest_pointers_are_not_parents():
    stamps = {t["ts"] for t in M.extract_threads(None, content=LISTED)}
    assert not stamps & {"1790000000.000700", "1790000000.000900", "1790000000.001000"}


def test_e10_an_unsent_draft_puts_its_target_thread_on_the_reread_list(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    drafts = M.extract_unsent_drafts(str(plan))
    assert [d["number"] for d in drafts] == [1, 4]  # 2 and 3 carry a SENT marker, each form
    assert drafts[0]["ts"] == "1790000000.000100" and drafts[0]["channel_id"] == "C0EXAMPLE01"
    assert drafts[1]["ts"] is None


@pytest.mark.parametrize("python", [sys.executable, "/usr/bin/python3"])
def test_command_line_prints_the_checklist(tmp_path, python):
    if not Path(python).exists():
        pytest.skip(f"{python} is not on this host")
    transcript, plan = tmp_path / "team-general.md", tmp_path / "plan.md"
    transcript.write_text(TRANSCRIPT, encoding="utf-8")
    plan.write_text(PLAN, encoding="utf-8")
    done = subprocess.run([python, str(SCRIPT), str(transcript), str(plan)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert 'message_ts="1790000000.000100" — 3 replies recorded' in done.stdout
    assert "TOTAL: 3 threads" in done.stdout
    assert "Draft 1: Reply to Jane about the deploy" in done.stdout
    assert "NO TS FOUND — search manually" in done.stdout
    missing = subprocess.run([python, str(SCRIPT), str(tmp_path / "absent.md")], capture_output=True, text=True)
    assert missing.returncode == 1


@pytest.mark.parametrize("python", [sys.executable, "/usr/bin/python3"])
def test_links_with_no_recognized_parent_refuse_instead_of_an_empty_checklist(tmp_path, python):
    if not Path(python).exists():
        pytest.skip(f"{python} is not on this host")
    digest, empty = tmp_path / "digest.md", tmp_path / "quiet.md"
    digest.write_text(DIGEST_ONLY, encoding="utf-8")
    empty.write_text("# #general — 2026-10-05\n\nNo messages in the window.\n", encoding="utf-8")
    done = subprocess.run([python, str(SCRIPT), str(digest)], capture_output=True, text=True)
    assert done.returncode == 2 and "UNPARSED: digest.md has 1 message link(s)" in done.stdout
    assert "THREADS TO RE-READ" not in done.stdout
    quiet = subprocess.run([python, str(SCRIPT), str(empty)], capture_output=True, text=True)
    assert quiet.returncode == 0 and "Parent threads found: 0" in quiet.stdout


DM_HALF = """# Slack sync, DMs and group DMs — 2026-10-25

## Part A — every message in the window, verbatim

### Group DM · Jane Doe + Sam Lee + Principal (`C0EXAMPLE09`)

**2026-10-23 11:38:18 EDT · Jane Doe (U0EXAMPLE1) · [ts 1790000001.000100](https://example.slack.com/archives/C0EXAMPLE09/p1790000001000100)**

> Here's the plan.

## Part B — per-target coverage

| Target | Conversation | Window | Messages | Status |
|---|---|---|---|---|
| `D0EXAMPLE01` | DM · Jane Doe | newest [ts 1790000002.000200](https://example.slack.com/archives/D0EXAMPLE01/p1790000002000200) | 0 | quiet |

## Part C — threads re-read (no `oldest` or `latest`)

- **Threads that gained replies since the last close: none.**
- **Threads with replies, unchanged:**
  - Jane Doe DM `D0EXAMPLE01` [1790000003.000300](https://example.slack.com/archives/D0EXAMPLE01/p1790000003000300) (3 replies)
  - Sam Lee DM `D0EXAMPLE02` 1790000004.000400 (locator only): still 1 reply, the principal's (ts 1790000004.000500).
  - A channel post `C0EXAMPLE03` [1790000006.000700](https://example.slack.com/archives/C0EXAMPLE03/p1790000006000700)
- **Every other read returned "No thread messages":**
  - `C0EXAMPLE09` (2): 1790000001.000100, 1790000001.000600

## Part F — watermarks

| Target | Watermark |
|---|---|
| `D0EXAMPLE01` | [1790000002.000200](https://example.slack.com/archives/D0EXAMPLE01/p1790000002000200) |
"""


def test_a_dm_half_lists_every_thread_it_read_and_no_table_row():
    """2026-10-26: on a DM-half transcript the checker listed the coverage table's rows as parents and missed all
    five threads with replies, which sat as indented bullets under "threads re-read"."""
    found = {(t["channel_id"], t["ts"]): t["reply_count"] for t in M.extract_threads(None, content=DM_HALF)}
    assert found == {("C0EXAMPLE09", "1790000001.000100"): 0, ("D0EXAMPLE01", "1790000003.000300"): 3,
                     ("D0EXAMPLE02", "1790000004.000400"): 1, ("C0EXAMPLE03", "1790000006.000700"): 1,
                     ("C0EXAMPLE09", "1790000001.000600"): 0}

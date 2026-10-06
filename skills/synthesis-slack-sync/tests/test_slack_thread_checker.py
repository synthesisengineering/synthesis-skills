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

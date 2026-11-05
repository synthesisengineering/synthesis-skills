"""The time-away note: a prompt that comes ten minutes or more after the session's last turn ended says how long ago
that was, since an agent cannot perceive a pause (2026-11-05: an idle compaction applied at 14:14 a summary of a
conversation whose last turn ended at 11:52, and nothing told the agent its picture was 2 h 22 min old)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import board, hook

ROOT = Path(__file__).resolve().parents[1]
NOW = time.mktime((2026, 11, 5, 14, 14, 0, 0, 0, -1))  # Thursday 14:14, local time


def _hook(event, payload):
    return subprocess.run([sys.executable, "-m", "synthesis.hook", event], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=ROOT, env=dict(os.environ)).stdout


@pytest.mark.parametrize("gap, said", [
    (599, None),  # an ordinary back-and-forth
    (600, "last turn ended at 14:04, 10 min ago"),
    (8520, "last turn ended at 11:52, 2 h 22 min ago"),
    (27 * 3600, "last turn ended at Wednesday 2026-11-04 11:14, 1 day 3 h ago"),
    (50 * 3600, "last turn ended at Tuesday 2026-11-03 12:14, 2 days 2 h ago"),
])
def test_the_note_counts_from_the_last_turns_end(gap, said):
    note = hook._away_note(board.Session(session="S", ended=NOW - gap), now=NOW)
    if said is None:
        assert note == ""
    else:
        assert note.startswith("It is 14:14; this session's " + said + ". ")
        assert "background tasks, CI runs, deploys, replies awaited" in note
        assert note.endswith("check each before relying on it or reporting it.")


def test_no_recorded_end_means_no_note():
    assert hook._away_note(None, now=NOW) == ""
    assert hook._away_note(board.Session(session="S"), now=NOW) == ""


def test_the_stop_hook_records_the_end_and_the_next_prompt_reads_it(isolated_home):
    _hook("stop", {"session_id": "AWAY", "hook_event_name": "Stop"})
    ended = board.load("AWAY").ended
    assert 0 <= time.time() - ended < 60
    assert "last turn ended" not in _hook("user-prompt-submit", {"session_id": "AWAY", "prompt": "carry on"})
    board.touch("AWAY", ended=ended - 8520)
    note = _hook("user-prompt-submit", {"session_id": "AWAY", "prompt": "carry on"})
    assert "last turn ended at" in note and "2 h 22 min ago" in note

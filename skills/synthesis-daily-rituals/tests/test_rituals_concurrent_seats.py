"""Concurrent-seats mode holds back what could collide with a live seat, and not the steps a ritual must run.

2026-11-18: an operations seat found that rule 4 of the mode ("watermark advances, decay sweeps ... wait for a clear
board") stood against the Slack sync's Step 4 (save, then advance each target, then the gate that blocks on every
declared target this run did not advance) and against the critical deadlines (`decay_sweep.py --alert` in every
ritual). By the rule's own reason, a collision with seats that read the same state, neither of those collides: the
watermark store has been written under a lock and never backwards since 2026-11-11, and the sweep writes no state at
all. So both run with seats live, and rule 4 and the mode's keeps say so, with every word rule 4 had kept. These tests
also hold the two facts the note rests on, so a change to either brings the question back.
"""

from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
MODES = (SKILL / "references" / "mid-day-and-modes.md").read_text(encoding="utf-8")
SECTION = MODES.split("\n## Concurrent-Seats Mode Ritual\n")[1].split("\n## ")[0]
KEEPS = SECTION.split("### What Concurrent-Seats Mode Keeps")[1]
RULE_4 = next(line for line in SECTION.splitlines() if line.startswith("4. "))
PROTOCOL = (SKILL.parent / "synthesis-slack-sync" / "references" / "sync-protocol.md").read_text(encoding="utf-8")


def test_rule_4_keeps_every_word_it_had():
    assert ("4. **Skip shared-state maintenance while seats are live.** Index rebuilds, inventory regeneration, watermark "
            "advances, decay sweeps — anything every seat reads — waits for a clear board. The ritual reports "
            "`deferred: seats live` rather than half-running them.") in RULE_4


def test_rule_4_says_the_advance_of_its_own_read_and_the_sweep_run_with_seats_live():
    note = RULE_4.split("rather than half-running them.")[1]
    assert "sync_watermark.py" in note and "gate" in note and "decay_sweep.py" in note, note
    assert "sync-protocol.md" in note and "critical-deadlines.md" in note, note


def test_the_mode_keeps_the_advance_the_gate_and_the_sweep():
    assert "sync_watermark.py advance" in KEEPS and "gate" in KEEPS, KEEPS
    assert "decay_sweep.py" in KEEPS, KEEPS


def test_the_slack_syncs_step_4_says_it_holds_in_concurrent_seats_mode():
    step_4 = PROTOCOL.split("### Step 4")[1].split("\n### ")[0]
    assert "concurrent-seats mode" in step_4 and "mid-day-and-modes.md" in step_4, step_4


def test_the_facts_the_note_rests_on_still_hold():
    sweep = (SKILL / "scripts" / "decay_sweep.py").read_text(encoding="utf-8")
    assert "No lookback cutoff, state writes, network access" in sweep  # it reads, and writes no state
    store = (SKILL / "scripts" / "sync_watermark.py").read_text(encoding="utf-8")
    assert "fcntl.flock(lock, fcntl.LOCK_EX)" in store and "never backwards" in store  # one writer at a time, forward only

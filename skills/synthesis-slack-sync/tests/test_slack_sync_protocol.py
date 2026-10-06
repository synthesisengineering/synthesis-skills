"""Slack reads are done by the agent through its connector, so the read rules that lived in the
cut acquisition code are protocol text (scenarios E01 to E14 of the v5 code evaluation). These
tests keep each rule in the text an agent reads at every sync: SKILL.md and sync-protocol.md."""

from __future__ import annotations

from pathlib import Path
import re

SKILL = Path(__file__).resolve().parents[1]
BRIEF = (SKILL / "SKILL.md").read_text(encoding="utf-8")
PROTOCOL = (SKILL / "references" / "sync-protocol.md").read_text(encoding="utf-8")
STEP1 = PROTOCOL.split("### Step 1:", 1)[1].split("### Step 2:", 1)[0]
STEP2 = PROTOCOL.split("### Step 2:", 1)[1].split("### Step 3:", 1)[0]
STEP4 = PROTOCOL.split("### Step 4:", 1)[1].split("### Step 5:", 1)[0]
STEP5 = PROTOCOL.split("### Step 5:", 1)[1].split("#### Draft Message Format", 1)[0]


def test_e01_threads_are_reread_whole_with_no_lower_bound():
    assert "Never use the `oldest` parameter on thread reads." in STEP2
    assert "slack_read_thread(channel_id, message_ts=PARENT_TS)" in STEP2


def test_e02_replies_to_older_threads_are_found_by_search():
    assert "Source D" in STEP2 and "search the window for the principal's own messages" in STEP2
    assert "joins the re-read list" in STEP2


def test_e04_quiet_needs_a_positive_control_else_unknown():
    assert "positive control" in STEP1 and "predates the window" in STEP1 and "**unknown**" in STEP1
    assert "positive control" in BRIEF


def test_e05_a_repeated_cursor_or_unclear_end_is_incomplete():
    assert "A cursor that repeats" in STEP1 and "**incomplete**" in STEP1 and "never complete" in STEP1


def test_e06_reads_are_detailed():
    assert 'detail="detailed"' in STEP1 and "concise read hides thread replies" in STEP1
    for call in re.findall(r"slack_read_channel\([^)]*\)", PROTOCOL + BRIEF):
        assert 'detail="detailed"' in call, call


def test_e07_every_declared_target_is_read_every_sync_from_its_window():
    assert "**Every declared target is read every sync**" in STEP1
    assert "sync_watermark.py window" in STEP1 and "never hand-computed" in STEP1


def test_e08_a_message_from_another_conversation_is_not_filed_here():
    assert "names a channel other than the one requested" in STEP1
    assert "do not file it under the requested channel" in STEP1


def test_e09_a_saved_connector_read_advances_without_token_or_receipt():
    assert "The connector read is the read." in STEP1 and "No token, receipt or replay is required" in STEP1
    assert "--acquisition-evidence" not in PROTOCOL + BRIEF
    assert "sync_watermark.py advance" in STEP4


def test_e11_slack_connect_messages_are_saved_like_any_other():
    assert "Slack Connect messages are messages." in STEP1


def test_e13_a_sync_never_sends():
    assert "A sync never sends" in STEP5 and "A sync never sends" in BRIEF


def test_e14_the_report_names_its_denominator_and_every_unread_target():
    assert "names its denominator" in STEP4 and "by name" in STEP4


def test_every_command_the_skill_names_exists():
    named = set(re.findall(r"<synthesis-slack-sync-root>/(scripts/[\w.]+\.py)", PROTOCOL + BRIEF))
    named |= set(re.findall(r"`(scripts/[\w.]+\.py)", BRIEF))
    assert named and all((SKILL / path).is_file() for path in named), named
    rituals = SKILL.parent / "synthesis-daily-rituals" / "scripts" / "sync_watermark.py"
    assert "<synthesis-daily-rituals-root>/scripts/sync_watermark.py" in PROTOCOL and rituals.is_file()
    assert "exec-public" not in PROTOCOL + BRIEF

"""The backlog rules, read from where they live: the principal's rulings of 2026-11-16.

One ordered backlog per project, which must shrink; each item's origin, principal or self-generated; the count at
every checkpoint and the daily count of open principal items; finish, ship and install before anything new, and the
side-quest test. Source-structure checks only: they cannot establish what a session does with them.
"""

from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_backlog_its_origins_its_counts_and_finishing_first_are_binding_rules():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    rules = flat(skill.split("## Binding rules")[1].split("## Contents")[0])
    for words in ("One ordered backlog per project", "`origin: principal`", "`origin: self`", "another session's request",
                  "only fixes, reviews or re-reviews what the work produced", "rises two days running",
                  "since the last checkpoint", "continue, narrow or stop", "finish, ship and install",
                  "A side quest is fine only when it serves the principal's goals"):
        assert words in rules, words
    assert "references/backlog.md" in skill.split("## Contents")[1].split("\n## ")[0]


def test_the_checkpoint_procedure_points_to_the_count_at_every_checkpoint():
    """The count is made at every checkpoint, so the checkpoint's own procedure leads there."""
    checkpoint = (SKILL.parent / "synthesis-checkpoint" / "SKILL.md").read_text(encoding="utf-8")
    procedure = flat(checkpoint.split("\n## Procedure\n")[1])
    link = "../synthesis-project-management/references/backlog.md#the-count-at-every-checkpoint"
    assert f"]({link})" in procedure and "since the last checkpoint" in procedure
    assert "\n## The count at every checkpoint\n" in (SKILL / "references" / "backlog.md").read_text(encoding="utf-8")


def test_the_backlog_page_says_where_the_list_lives_how_items_are_marked_and_counted_and_the_side_quest_test():
    page = flat((SKILL / "references" / "backlog.md").read_text(encoding="utf-8"))
    for words in ("`**Plan:**`", "one ordered list", "(origin: principal)", "(origin: self, added", "closed <time>",
                  "## Backlog count", "open principal item(s)", "since the last checkpoint", "two days running",
                  "continue, narrow or stop", "finish, ship and install", "side-quest test",
                  "synthesis-autopilot",
                  # review round 1: rule 16 allows an important issue that serves the goals, and so does the test
                  "it is an important issue that serves those goals"):
        assert words in page, words

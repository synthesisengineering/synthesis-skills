"""Decide what the goals already decide, read from where it lives. Source-structure checks only.

The test is the principal's ruling of 2026-11-16: a recommendation that follows from their goals, guidelines and wish
for the best-quality work is decided, acted on and reported in one line, not brought to them. The list of what still
goes to them is the project's rule as the brief for plan item 22.37(d) gave it, with a checkpoint they reserved added
in review round 1, whose answer is never written from the agent's own judgement. The list's item "an approval code" is
the runtime's typed approval; this skill ships in the hook-free directory package, where no such approval exists and
whose check refuses the runtime's term, and five packaged skills link to its decision-ownership contract, so the item
is written as what it means anywhere: an approval only they can give.
"""

from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
AUTHORITY = ("(money, sends, deploys, their accounts and settings, their voice, an approval only they can give, a "
             "checkpoint they reserved, whose answer is never written from the agent's own judgement)")


def flat(text: str) -> str:
    return " ".join(text.split())


def test_deciding_what_the_goals_already_decide_is_a_binding_rule_with_the_authority_list_as_stated():
    rules = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    rule = flat(next((line for line in rules.splitlines() if "Decide what the goals already decide" in line), ""))
    contract = flat(SKILL.joinpath("references", "decision-ownership.md").read_text(encoding="utf-8"))
    for where, said in (("binding rule", rule), ("decision-ownership.md", contract)):
        for words in ("the principal's goals, guidelines and wish for the best-quality work", "report it in one line",
                      f"only what needs their own authority {AUTHORITY}",
                      "a real conflict between their goals that their rulings don't settle"):
            assert words in said, (where, words)


def test_the_decisive_uncertainty_paragraph_moved_word_for_word_to_its_own_page():
    """The new rule needed room under SKILL.md's 8,000 bytes, so the section's last paragraph moved whole to the page
    on the method it summarizes; its link now names the file it sits in."""
    moved = ("when a missing fact could change the next decision. Prefer the cheapest credible discriminating "
             "observation, retain refuted predictions, and stop when the required decision is supported. In an autopilot "
             "run, the journal adapter (synthesis-autopilot, `references/uncertainty-journal.md`) binds actual local "
             "execution to the affected acceptance closure; unsupported semantic and external-state questions remain "
             "explicit.")
    page = flat(SKILL.joinpath("references", "decisive-uncertainty.md").read_text(encoding="utf-8"))
    assert f"Use the [decisive-uncertainty method](decisive-uncertainty.md) {moved}" in page
    assert moved not in flat(SKILL.joinpath("SKILL.md").read_text(encoding="utf-8"))

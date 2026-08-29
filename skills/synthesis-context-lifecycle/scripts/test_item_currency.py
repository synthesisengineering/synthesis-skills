"""Item-level currency: staleness computed at read time, not maintained at write time.

Section-level `*State as of:*` markers already stop a fresh header from sitting
above stale prose. They do not stop the failure one level further down: an
open-items list where each entry carries an implicit present tense ("today",
"this week") that nobody re-dates. A record whose header and sections are all
current can still route an agent off a seventeen-day-old item.

The obvious remedy — rewrite the list every run instead of appending — has two
flaws this design avoids. It turns a visible failure into an invisible one, because
a re-derived list silently drops what today's evidence does not surface, and a
dropped item is harder to notice than a stale one. And it only runs when the
ritual runs, which is exactly what does not happen on the days records rot.

Stamping each item instead means nothing is lost, every entry carries its own age,
and any reader can compute overdue-ness with no ritual involved.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("context_currency.py")
SPEC = importlib.util.spec_from_file_location("context_currency", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


TODAY = date(2026, 8, 27)


def _project(tmp_path: Path, context: str, log: str = "## 2026-08-27 — work\n") -> Path:
    project = tmp_path / "seat"
    (project / "sessions").mkdir(parents=True)
    (project / "CONTEXT.md").write_text(context, encoding="utf-8")
    (project / "sessions" / "2026-08.md").write_text(log, encoding="utf-8")
    return project


def _kinds(project: Path) -> list[str]:
    return [f["kind"] for f in MODULE.audit_project(project, today=TODAY)]


# --- extraction ------------------------------------------------------------


def test_item_markers_capture_date_and_horizon() -> None:
    text = (
        "## Open on Rajiv\n"
        "- [ ] Chase the feedback ask (as of 2026-08-10, review 7d)\n"
        "- [ ] Headcount review (as of 2026-08-26)\n"
    )
    items = MODULE.item_markers(text)

    assert len(items) == 2
    assert items[0]["date"] == "2026-08-10"
    assert items[0]["review_days"] == 7
    assert items[0]["section"] == "Open on Rajiv"
    assert items[1]["review_days"] is None


# --- the failure being caught ---------------------------------------------


def test_item_past_its_review_horizon_is_flagged() -> None:
    """The verbatim shape of the seat incident: an item written on 8/10 with a
    one-week horizon, still sitting there on 8/27 reading as current."""
    text = (
        "**Last session:** 2026-08-27\n\n"
        "## Open on Rajiv\n"
        "- [ ] Chase the feedback ask (as of 2026-08-10, review 7d)\n"
    )
    items = MODULE.overdue_items(text, today=TODAY)

    assert len(items) == 1
    assert items[0]["date"] == "2026-08-10"


def test_item_within_its_horizon_is_not_flagged() -> None:
    text = (
        "## Open on Rajiv\n"
        "- [ ] Recent thing (as of 2026-08-26, review 7d)\n"
    )

    assert MODULE.overdue_items(text, today=TODAY) == []


def test_unspecified_horizon_uses_the_default() -> None:
    """No horizon still ages: silence must not mean 'never stale'."""
    fresh = "## Open\n- [ ] A (as of 2026-08-20)\n"
    old = "## Open\n- [ ] B (as of 2026-07-01)\n"

    assert MODULE.overdue_items(fresh, today=TODAY) == []
    assert len(MODULE.overdue_items(old, today=TODAY)) == 1


def test_completed_items_are_never_flagged() -> None:
    text = "## Open\n- [x] Long done (as of 2026-01-01, review 1d)\n"

    assert MODULE.overdue_items(text, today=TODAY) == []


# --- unstamped open items are unverifiable, never assumed fresh -----------


def test_unstamped_open_items_are_reported_as_unverifiable(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Open on Rajiv\n"
        "- [ ] Something with no date at all\n"
        "- [ ] Another undated thing\n",
    )

    assert "item-marker-absent" in _kinds(project)


def test_stamped_open_items_are_not_reported_absent(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Open on Rajiv\n"
        "- [ ] Something (as of 2026-08-26, review 30d)\n",
    )
    kinds = _kinds(project)

    assert "item-marker-absent" not in kinds
    assert "item-marker-stale" not in kinds


def test_prose_sections_do_not_demand_stamps(tmp_path: Path) -> None:
    """Only open-item sections are held to this; narrative bullets are not."""
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Background\n"
        "- The system has three tiers\n"
        "- Records are append-only\n",
    )

    assert "item-marker-absent" not in _kinds(project)


def test_overdue_item_surfaces_as_a_project_finding(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Next actions\n"
        "- [ ] Stale work (as of 2026-08-01, review 7d)\n",
    )
    findings = [f for f in MODULE.audit_project(project, today=TODAY)
                if f["kind"] == "item-marker-stale"]

    assert len(findings) == 1
    assert "2026-08-01" in findings[0]["detail"]
    assert "Next actions" in findings[0]["detail"]


# --- append stays safe -----------------------------------------------------


def test_appending_does_not_make_older_stamped_items_invisible(tmp_path: Path) -> None:
    """The property rewrite-not-append would have destroyed: an old item stays
    present and visibly old rather than silently disappearing."""
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Old but real (as of 2026-07-01, review 7d)\n"
        "- [ ] Added today (as of 2026-08-27, review 7d)\n",
    )
    stale = [f for f in MODULE.audit_project(project, today=TODAY)
             if f["kind"] == "item-marker-stale"]

    assert len(stale) == 1
    assert "2026-07-01" in stale[0]["detail"]


# --- calibration and documented convention --------------------------------


def test_item_findings_are_warnings_not_defects(tmp_path: Path) -> None:
    """Deliberate calibration: a new convention that turns an entire corpus red
    on the day it lands is how a guard teaches people to route around it. These
    must surface without blocking a session end, which is reserved for defects."""
    source = Path(__file__).with_name("context_doctor.py").read_text(encoding="utf-8")
    marker = '"item-marker-malformed",'
    assert marker in source, "doctor no longer maps the item kinds"
    block = source.split(marker, 1)[1].split("audit.add(", 1)[1][:200]

    assert '"item-currency"' in block
    assert '"warning"' in block
    assert '"defect"' not in block


def test_day_end_ritual_documents_the_stamp_convention() -> None:
    """The convention is only enforceable if the ritual that writes records
    states it; a checker without a documented convention trains bypass."""
    skill = (
        Path(__file__).resolve().parents[2]
        / "synthesis-daily-rituals"
        / "SKILL.md"
    )
    text = skill.read_text(encoding="utf-8")
    assert "(as of YYYY-MM-DD, review Nd)" in text
    assert "item-currency" in text
    # The rejected alternative must not creep back in as a mandate.
    assert "rewritten every run, never appended" not in text


def test_current_state_prose_is_not_held_to_item_stamps(tmp_path: Path) -> None:
    """Found by surveying the real corpus before adopting the convention.

    'Current State' is the commonest section name in this corpus and it holds
    narrative prose, not obligations. Section-level '*State as of:*' markers
    already govern exactly that content, so matching it here demanded a date
    from prose and double-covered what body currency already checks — 140 of
    the 294 flagged items across 18 projects were this single miscalibration.
    """
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Current State\n"
        "- The installer ships in three stages\n"
        "- Both clients verify twice\n",
    )

    assert "item-marker-absent" not in _kinds(project)


def test_obligation_sections_are_still_held(tmp_path: Path) -> None:
    """The narrowing must not silently exempt the sections that matter."""
    for heading in ("Open on Rajiv", "What's Next", "Next actions", "Blocked"):
        project = tmp_path / heading.replace("/", "-").replace(" ", "-")
        (project / "sessions").mkdir(parents=True)
        (project / "CONTEXT.md").write_text(
            "**Last session:** 2026-08-27\n\n"
            f"## {heading}\n- [ ] Something undated\n",
            encoding="utf-8",
        )
        (project / "sessions" / "2026-08.md").write_text(
            "## 2026-08-27 — work\n", encoding="utf-8"
        )
        kinds = [f["kind"] for f in MODULE.audit_project(project, today=TODAY)]
        assert "item-marker-absent" in kinds, heading


# --- R-02 external-review repairs: fail-open stamps and zero-day horizons --


def test_zero_day_horizon_is_honored_not_defaulted(tmp_path: Path) -> None:
    """'review 0d' is a statement (review daily), not an omission: `or`
    silently replaced it with the 14-day default, so a daily-review item
    could sit two weeks dark (R-02 external review)."""
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Watch this daily (as of 2026-08-26, review 0d)\n",
    )
    stale = [f for f in MODULE.audit_project(project, today=TODAY)
             if f["kind"] == "item-marker-stale"]

    assert len(stale) == 1
    assert "0-day review horizon" in stale[0]["detail"]


def test_malformed_stamp_suffix_is_flagged_not_exempted(tmp_path: Path) -> None:
    """'(as of yesterday)' matched the unstamped-exemption heuristic and
    passed as stamped; a stamp that does not parse must not read as one."""
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Chase the ask (as of yesterday)\n",
    )
    malformed = [f for f in MODULE.audit_project(project, today=TODAY)
                 if f["kind"] == "item-marker-malformed"]

    assert len(malformed) == 1
    assert "does not parse" in malformed[0]["detail"]


def test_impossible_stamp_date_is_flagged_not_skipped(tmp_path: Path) -> None:
    """A date-shaped stamp that is not a real date was silently skipped by
    the overdue scan, so the item read as current forever."""
    project = _project(
        tmp_path,
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Bad stamp (as of 2026-02-30, review 7d)\n",
    )
    findings = MODULE.audit_project(project, today=TODAY)
    malformed = [f for f in findings if f["kind"] == "item-marker-malformed"]

    assert len(malformed) == 1
    assert "not a real date" in malformed[0]["detail"]
    assert not [f for f in findings if f["kind"] == "item-marker-stale"]

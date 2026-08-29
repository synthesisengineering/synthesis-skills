"""Review-grade history: what was open, what closed, what expired unactioned.

Current-state files cannot answer "what did I miss last week". CONTEXT.md
describes what is open now, and the moment an item is closed out or drops off,
the evidence that it was ever open leaves with it. So the answer needs an
append-only record of transitions, written where the transition happens.

The ledger is deliberately per-workspace rather than global. Engagement
workspaces are deletion units: a single shared ledger would keep a client's
items alive inside a file that survives the delete-my-data request they
belonged to. Each workspace's ledger lives in that workspace's own context
repo and dies with it; the reader federates at query time and copies nothing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("review_ledger.py")
SPEC = importlib.util.spec_from_file_location("review_ledger", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


TODAY = date(2026, 8, 27)


def _workspace(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    (root / "projects").mkdir(parents=True)
    return root


def _project(root: Path, name: str, context: str) -> Path:
    project = root / "projects" / name
    (project / "sessions").mkdir(parents=True)
    (project / "CONTEXT.md").write_text(context, encoding="utf-8")
    (project / "sessions" / "2026-08.md").write_text(
        "## 2026-08-27 — work\n", encoding="utf-8"
    )
    return project


# --- append-only recording -------------------------------------------------


def test_record_appends_without_rewriting(tmp_path: Path) -> None:
    root = _workspace(tmp_path, "personal")

    MODULE.record(root, "alpha", "First thing", "opened", today=TODAY)
    MODULE.record(root, "alpha", "First thing", "closed", today=TODAY)

    events = MODULE.read_events(root)
    assert [e["transition"] for e in events] == ["opened", "closed"]
    assert all(e["project"] == "alpha" for e in events)


def test_ledger_lives_inside_its_own_workspace(tmp_path: Path) -> None:
    """The deletion-unit property: nothing is written outside the workspace."""
    root = _workspace(tmp_path, "client")
    MODULE.record(root, "alpha", "Thing", "opened", today=TODAY)

    ledger = root / MODULE.LEDGER_DIR / MODULE.LEDGER_FILE
    assert ledger.is_file()
    assert ledger.read_text(encoding="utf-8").count("\n") == 1


def test_corrupt_line_does_not_lose_the_rest(tmp_path: Path) -> None:
    root = _workspace(tmp_path, "personal")
    MODULE.record(root, "alpha", "Good", "opened", today=TODAY)
    ledger = root / MODULE.LEDGER_DIR / MODULE.LEDGER_FILE
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    MODULE.record(root, "alpha", "Also good", "closed", today=TODAY)

    events = MODULE.read_events(root)
    assert len(events) == 2


# --- derived expiry --------------------------------------------------------


def test_scan_derives_expired_unactioned_from_stamps(tmp_path: Path) -> None:
    """The 'what did I miss' signal: an item that aged past its horizon with
    nobody acting on it."""
    root = _workspace(tmp_path, "personal")
    _project(
        root,
        "alpha",
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Forgotten ask (as of 2026-08-01, review 7d)\n"
        "- [ ] Recent ask (as of 2026-08-26, review 7d)\n",
    )

    added = MODULE.scan(root, today=TODAY)

    assert added == 1
    events = MODULE.read_events(root)
    assert events[0]["transition"] == "expired-unactioned"
    assert "Forgotten ask" in events[0]["item"]


def test_scan_is_idempotent(tmp_path: Path) -> None:
    """Re-running must not manufacture a second miss for the same item."""
    root = _workspace(tmp_path, "personal")
    _project(
        root,
        "alpha",
        "**Last session:** 2026-08-27\n\n"
        "## Open\n- [ ] Forgotten (as of 2026-08-01, review 7d)\n",
    )

    first = MODULE.scan(root, today=TODAY)
    second = MODULE.scan(root, today=TODAY)

    assert (first, second) == (1, 0)
    assert len(MODULE.read_events(root)) == 1


def test_scan_reports_nothing_when_everything_is_current(tmp_path: Path) -> None:
    root = _workspace(tmp_path, "personal")
    _project(
        root,
        "alpha",
        "**Last session:** 2026-08-27\n\n"
        "## Open\n- [ ] Fresh (as of 2026-08-26, review 7d)\n",
    )

    assert MODULE.scan(root, today=TODAY) == 0


# --- federated reporting ---------------------------------------------------


def test_report_federates_across_workspaces_without_merging_stores(
    tmp_path: Path,
) -> None:
    personal = _workspace(tmp_path, "personal")
    client = _workspace(tmp_path, "client")
    MODULE.record(personal, "alpha", "Mine", "closed", today=TODAY)
    MODULE.record(client, "beta", "Theirs", "closed", today=TODAY)

    report = MODULE.report(
        [("personal", personal), ("client", client)], window_days=30, today=TODAY
    )

    assert report["totals"]["closed"] == 2
    assert {row["source"] for row in report["events"]} == {"personal", "client"}
    # Each store stays in its own workspace; nothing is copied into a third.
    assert not (tmp_path / MODULE.LEDGER_DIR).exists()


def test_report_window_excludes_older_events(tmp_path: Path) -> None:
    root = _workspace(tmp_path, "personal")
    MODULE.record(root, "alpha", "Old", "closed", today=date(2026, 5, 1))
    MODULE.record(root, "alpha", "New", "closed", today=TODAY)

    week = MODULE.report([("personal", root)], window_days=7, today=TODAY)
    quarter = MODULE.report([("personal", root)], window_days=120, today=TODAY)

    assert week["totals"]["closed"] == 1
    assert quarter["totals"]["closed"] == 2


def test_report_on_a_workspace_with_no_ledger_is_empty_not_an_error(
    tmp_path: Path,
) -> None:
    root = _workspace(tmp_path, "personal")

    report = MODULE.report([("personal", root)], window_days=30, today=TODAY)

    assert report["totals"] == {}
    assert report["events"] == []


def test_expired_items_are_summarised_for_the_review_question(
    tmp_path: Path,
) -> None:
    """The question is 'what did I miss', so expiries must be separable."""
    root = _workspace(tmp_path, "personal")
    _project(
        root,
        "alpha",
        "**Last session:** 2026-08-27\n\n"
        "## Open\n- [ ] Missed thing (as of 2026-08-01, review 7d)\n",
    )
    MODULE.scan(root, today=TODAY)
    MODULE.record(root, "alpha", "Done thing", "closed", today=TODAY)

    report = MODULE.report([("personal", root)], window_days=30, today=TODAY)

    assert report["totals"]["expired-unactioned"] == 1
    assert report["totals"]["closed"] == 1
    missed = [e for e in report["events"] if e["transition"] == "expired-unactioned"]
    assert "Missed thing" in missed[0]["item"]


def test_a_restamped_item_can_expire_again(tmp_path: Path) -> None:
    """Idempotence is per lifecycle, not per text: expired -> carried ->
    re-stamped -> expired again is TWO misses, and keying suppression on the
    item text alone silenced every cycle after the first (R-02 external
    review)."""
    root = _workspace(tmp_path, "personal")
    project = _project(
        root,
        "alpha",
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Recurring ask (as of 2026-08-01, review 7d)\n",
    )

    assert MODULE.scan(root, today=TODAY) == 1
    MODULE.record(root, "alpha", "Recurring ask", "carried")

    # The same lifecycle stays idempotent.
    assert MODULE.scan(root, today=TODAY) == 0

    # A fresh stamp opens a new lifecycle; its later expiry is a new miss.
    (project / "CONTEXT.md").write_text(
        "**Last session:** 2026-08-27\n\n"
        "## Open\n"
        "- [ ] Recurring ask (as of 2026-08-15, review 7d)\n",
        encoding="utf-8",
    )
    assert MODULE.scan(root, today=TODAY) == 1

    expiries = [e for e in MODULE.read_events(root)
                if e["transition"] == "expired-unactioned"]
    assert len(expiries) == 2
    assert {e.get("stamp") for e in expiries} == {"2026-08-01", "2026-08-15"}

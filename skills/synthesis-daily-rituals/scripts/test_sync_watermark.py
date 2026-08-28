"""Regressions for per-surface sync watermarks.

Derived from a real failure, not an imagined one: a local mirror gap spanning
six days was recorded in three consecutive ritual artifacts and never closed.
Each run synced "since the last ritual", anchored on when the previous run
executed, so the hole the skipped run left was never revisited. The gaps the
artifacts honestly recorded were prose, and no run read those lines back.

Two properties make the repair structural rather than a matter of diligence:
the window is computed from the last successful WRITE so a hole is revisited
automatically, and an unclosed gap makes `status` exit non-zero so a later run
has to act on it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).with_name("sync_watermark.py")
SPEC = importlib.util.spec_from_file_location("sync_watermark", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

WS = "testspace"
TODAY = date(2026, 8, 28)


# --- the window follows writes, not runs ----------------------------------


def test_window_starts_after_the_last_written_day(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-20", today=TODAY, home=tmp_path)

    got = MODULE.window(WS, "slack", today=TODAY, home=tmp_path)

    assert got["from"] == "2026-08-21"
    assert got["to"] == "2026-08-28"


def test_a_skipped_run_leaves_a_gap_the_next_run_must_cover(tmp_path: Path) -> None:
    """The verbatim failure: written through 8/20, nothing since, and the next
    window must reach back to 8/21 rather than starting near today."""
    MODULE.advance(WS, "slack", "2026-08-20", today=date(2026, 8, 20), home=tmp_path)

    got = MODULE.window(WS, "slack", today=TODAY, home=tmp_path)

    assert got["from"] == "2026-08-21"
    assert got["gap_days"] == 7


def test_no_watermark_reports_bootstrap_rather_than_guessing(tmp_path: Path) -> None:
    got = MODULE.window(WS, "email", today=TODAY, home=tmp_path)

    assert got["bootstrap"] is True
    assert got["from"] is None


# --- the watermark advances only on a successful write --------------------


def test_watermark_never_moves_backwards(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-26", today=TODAY, home=tmp_path)

    result = MODULE.advance(WS, "slack", "2026-08-22", today=TODAY, home=tmp_path)

    assert result["moved"] is False
    assert result["through"] == "2026-08-26"


def test_future_watermark_is_refused(tmp_path: Path) -> None:
    """A run cannot declare tomorrow covered."""
    try:
        MODULE.advance(WS, "slack", "2026-09-01", today=TODAY, home=tmp_path)
    except ValueError as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError("a future watermark must be refused")


# --- an unclosed gap is blocking, which is what makes it load-bearing -----


def test_status_blocks_while_a_gap_is_open(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-20", today=date(2026, 8, 20), home=tmp_path)

    result = MODULE.status(WS, ["slack"], today=TODAY, home=tmp_path)

    assert result["blocking"] == ["slack"]


def test_status_is_clear_once_the_gap_closes(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-28", today=TODAY, home=tmp_path)

    assert MODULE.status(WS, ["slack"], today=TODAY, home=tmp_path)["blocking"] == []


def test_deferral_requires_a_reason(tmp_path: Path) -> None:
    try:
        MODULE.defer(WS, "slack", "   ", today=TODAY, home=tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("a reason-less deferral must be refused")


def test_explicit_deferral_unblocks_for_one_day_only(tmp_path: Path) -> None:
    """A deferral silences a gap for a day, never indefinitely — an indefinite
    silence is how a recorded gap becomes furniture."""
    MODULE.advance(WS, "slack", "2026-08-20", today=date(2026, 8, 20), home=tmp_path)
    MODULE.defer(WS, "slack", "Slack API outage", today=TODAY, home=tmp_path)

    same_day = MODULE.status(WS, ["slack"], today=TODAY, home=tmp_path)
    later = MODULE.status(WS, ["slack"], today=date(2026, 8, 31), home=tmp_path)

    assert same_day["blocking"] == []
    assert later["blocking"] == ["slack"]
    assert later["surfaces"][0]["stale_deferral"] is True


def test_a_successful_write_spends_the_deferral(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-20", today=date(2026, 8, 20), home=tmp_path)
    MODULE.defer(WS, "slack", "outage", today=TODAY, home=tmp_path)
    MODULE.advance(WS, "slack", "2026-08-28", today=TODAY, home=tmp_path)

    row = MODULE.status(WS, ["slack"], today=TODAY, home=tmp_path)["surfaces"][0]
    assert row["deferred"] is False


def test_surfaces_are_tracked_independently(tmp_path: Path) -> None:
    """One surface closing must not vouch for another — the completeness claim
    that hid the original gap."""
    MODULE.advance(WS, "slack", "2026-08-28", today=TODAY, home=tmp_path)
    MODULE.advance(WS, "email", "2026-08-20", today=date(2026, 8, 20), home=tmp_path)

    assert MODULE.status(WS, ["slack", "email"], today=TODAY, home=tmp_path)[
        "blocking"
    ] == ["email"]


# --- the gate is consumable by a ritual -----------------------------------


def test_cli_status_exits_nonzero_while_blocking(tmp_path: Path) -> None:
    """The property that makes this load-bearing: a ritual step can fail on it."""
    env = {"SYNTHESIS_HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    MODULE.advance(WS, "slack", "2026-08-20", today=date(2026, 8, 20), home=tmp_path)

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--workspace", WS, "--json"],
        capture_output=True, text=True, env=env,
    )

    assert done.returncode == 1
    assert json.loads(done.stdout)["blocking"] == ["slack"]


def test_cli_status_exits_zero_when_current(tmp_path: Path) -> None:
    env = {"SYNTHESIS_HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    MODULE.advance(WS, "slack", "2026-08-28", today=TODAY, home=tmp_path)

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--workspace", WS, "--json"],
        capture_output=True, text=True, env=env,
    )

    assert done.returncode == 0


def test_store_is_scoped_per_workspace(tmp_path: Path) -> None:
    """Engagement workspaces must not read each other's sync state."""
    MODULE.advance("alpha", "slack", "2026-08-28", today=TODAY, home=tmp_path)

    assert MODULE.window("beta", "slack", today=TODAY, home=tmp_path)["bootstrap"]


# --- the documented rules the mechanism depends on ------------------------

SKILLS_ROOT = Path(__file__).resolve().parents[2]


def test_rituals_document_the_watermark_and_blocking_gap() -> None:
    """A mechanism nobody is told to run is not a control."""
    text = (SKILLS_ROOT / "synthesis-daily-rituals" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "sync_watermark.py" in text
    assert "last date actually" in text.lower()
    assert "exits non-zero" in text


def test_transcripts_forbid_a_judgment_gate_before_fetching() -> None:
    """Declared means fetched; relevance is judged after fetching, not from a
    title. The same shape was already retired once for repository syncing."""
    text = (SKILLS_ROOT / "synthesis-meeting-transcripts" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "does not get a vote" in text
    assert "after* fetching" in text or "after fetching" in text


def test_slack_sync_bans_deriving_read_ids_in_the_sweep() -> None:
    """Two id-like fields per entry is a trap that hides until someone leaves."""
    text = (SKILLS_ROOT / "synthesis-slack-sync" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "preflight" in text
    assert "banned" in text
    assert "dm_id" in text

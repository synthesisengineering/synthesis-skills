"""Regressions for per-surface, per-target sync watermarks.

Derived from real failures, not imagined ones. v1 (2026-08-27): a six-day
mirror gap was recorded in three consecutive ritual artifacts and never
closed, because each run synced "since the last ritual" and nothing read the
recorded gap back. v2 (2026-09-01): the day-granular watermark could not see
the hours — a surface written at 09:15 counted as current all day, a mid-day
pass re-read only what the morning had skipped, and an "unanswered" claim at
17:51 rested on a 09:15 read while the answer had gone out at 09:27.

The properties that make both repairs structural: the window follows the
last successful WRITE to the second; a run stamps itself and `status --since
run` blocks on every declared surface or target the run did not re-read;
the window's epoch bound is computed and echoed beside human-readable time.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("sync_watermark.py")
SPEC = importlib.util.spec_from_file_location("sync_watermark", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

WS = "testspace"
TZ = timezone(timedelta(hours=-4))
NOW = datetime(2026, 8, 28, 12, 0, tzinfo=TZ)
RUN_START = datetime(2026, 8, 28, 11, 39, tzinfo=TZ)
MORNING = "2026-08-28T09:15:00-04:00"
IN_RUN = "2026-08-28T11:45:00-04:00"


def at(hour: int, minute: int = 0, day: int = 28) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=TZ)


# --- the window follows writes, to the second ------------------------------


def test_window_starts_at_the_last_written_moment(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-27T09:15", now=at(9, 20, day=27), home=tmp_path)

    got = MODULE.window(WS, "slack", now=NOW, home=tmp_path)

    assert got["from"] == "2026-08-27T09:15:00-04:00"
    assert got["from_epoch"] == int(datetime(2026, 8, 27, 9, 15, tzinfo=TZ).timestamp())
    assert got["to"] == "2026-08-28T12:00:00-04:00"
    assert got["span"] == "1d 2h 45m"
    assert "→" in got["human"]


def test_a_skipped_run_leaves_a_gap_the_next_run_must_cover(tmp_path: Path) -> None:
    """The verbatim v1 failure: written through 8/20, nothing since, and the
    next window must reach back to 8/20 rather than starting near today."""
    MODULE.advance(WS, "slack", "2026-08-20T12:00", now=at(12, day=20), home=tmp_path)

    got = MODULE.window(WS, "slack", now=NOW, home=tmp_path)

    assert got["from"] == "2026-08-20T12:00:00-04:00"
    assert got["span"] == "8d"


def test_no_watermark_reports_bootstrap_rather_than_guessing(tmp_path: Path) -> None:
    got = MODULE.window(WS, "email", now=NOW, home=tmp_path)

    assert got["bootstrap"] is True
    assert got["from"] is None and got["from_epoch"] is None
    assert "backfill bound" in got["human"]


def _schema_one_store(tmp_path: Path, surfaces: dict) -> Path:
    path = MODULE.store_path(WS, tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "surfaces": surfaces,
        "deferrals": {"email": {"reason": "outage", "deferred_on": "2026-08-28"}},
    }), encoding="utf-8")
    return path


def test_a_schema_one_date_reads_as_complete_through_end_of_that_day(tmp_path: Path) -> None:
    """Existing stores hold bare dates meaning 'that whole day is written' —
    capped by the moment the write happened, since a mirror cannot be
    complete past the time it was written."""
    path = _schema_one_store(tmp_path, {
        "yesterday": {"through": "2026-08-27", "updated_at": "2026-08-28T09:12:00"},
        "slack": {"through": "2026-08-27", "updated_at": "2026-08-27T16:00:00"},
    })

    assert MODULE.window(WS, "yesterday", now=NOW, home=tmp_path)["from"] == "2026-08-28T00:00:00-04:00"
    assert MODULE.window(WS, "slack", now=NOW, home=tmp_path)["from"] == "2026-08-27T16:00:00-04:00"

    MODULE.advance(WS, "docs", "now", now=NOW, home=tmp_path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["schema"] == 2
    assert stored["surfaces"]["slack"]["migrated_from"] == "2026-08-27"
    assert stored["deferrals"]["email"]["deferred_at"] == "2026-08-28T00:00:00-04:00"


def test_a_schema_one_date_never_migrates_into_the_future(tmp_path: Path) -> None:
    """The live store on 2026-09-01 said 'through today', written at 16:48 by a
    mid-day sync; read as end-of-day it would have put the next window's
    `oldest` five hours in the future and read nothing."""
    _schema_one_store(tmp_path, {
        "written": {"through": "2026-08-28", "updated_at": "2026-08-28T09:12:00"},
        "unstamped": {"through": "2026-08-28"},
    })

    assert MODULE.window(WS, "written", now=NOW, home=tmp_path)["from"] == "2026-08-28T09:12:00-04:00"
    assert MODULE.window(WS, "unstamped", now=NOW, home=tmp_path)["from"] == "2026-08-28T12:00:00-04:00"


# --- the watermark advances only on a successful write, never into the future


def test_watermark_never_moves_backwards(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", "2026-08-26T10:00", now=NOW, home=tmp_path)

    result = MODULE.advance(WS, "slack", "2026-08-22T10:00", now=NOW, home=tmp_path)

    assert result["moved"] is False
    assert result["entries"][0]["through"] == "2026-08-26T10:00:00-04:00"


def test_future_watermark_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="future"):
        MODULE.advance(WS, "slack", "2026-08-28T13:00", now=NOW, home=tmp_path)


def test_a_bare_date_means_end_of_day_so_today_is_refused_mid_day(tmp_path: Path) -> None:
    """A mid-day run cannot stamp 'today' — it must record when it read."""
    with pytest.raises(ValueError, match="END of that day"):
        MODULE.advance(WS, "slack", "2026-08-28", now=NOW, home=tmp_path)

    result = MODULE.advance(WS, "slack", "2026-08-27", now=NOW, home=tmp_path)
    assert result["through"] == "2026-08-28T00:00:00-04:00"


def test_now_is_an_accepted_moment(tmp_path: Path) -> None:
    result = MODULE.advance(WS, "slack", "now", now=NOW, home=tmp_path)
    assert result["through"] == "2026-08-28T12:00:00-04:00"


# --- a run proves its own coverage: status --since run --------------------------


def test_status_blocks_on_a_read_older_than_the_run(tmp_path: Path) -> None:
    """The v2 defect itself: a 09:15 read is not current at an 11:39 run."""
    MODULE.advance(WS, "slack", MORNING, now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, "mid-day", now=RUN_START, home=tmp_path)

    result = MODULE.status(WS, ["slack"], now=NOW, home=tmp_path)

    assert result["bound_source"] == "run"
    assert result["blocking"] == ["slack"]
    assert result["surfaces"][0]["state"] == "stale"


def test_status_is_clear_once_the_surface_is_re_read_in_this_run(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", MORNING, now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, now=at(11, 46), home=tmp_path)

    assert MODULE.status(WS, ["slack"], now=NOW, home=tmp_path)["blocking"] == []


def test_status_max_age_is_an_alternative_bound(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", MORNING, now=at(9, 16), home=tmp_path)

    loose = MODULE.status(WS, ["slack"], max_age=timedelta(hours=4), now=NOW, home=tmp_path)
    tight = MODULE.status(WS, ["slack"], max_age=timedelta(hours=2), now=NOW, home=tmp_path)

    assert loose["blocking"] == []
    assert tight["blocking"] == ["slack"]


def test_status_needs_a_freshness_bound(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", MORNING, now=at(9, 16), home=tmp_path)
    with pytest.raises(ValueError, match="freshness bound"):
        MODULE.status(WS, ["slack"], now=NOW, home=tmp_path)


# --- declared read targets block individually ---------------------------------------


def test_declared_targets_block_individually(tmp_path: Path) -> None:
    """'20 of 60 targets read' becomes a list of keys, not a sentence."""
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, targets=["C1", "D2"], now=at(11, 46), home=tmp_path)

    result = MODULE.status(WS, targets={"slack": ["C1", "D2", "D3"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == ["slack:D3"]
    surface = result["surfaces"][0]
    assert surface["blocking"] is True
    assert [t["state"] for t in surface["targets"]] == ["current", "current", "missing"]


def test_a_target_read_before_the_run_is_stale(tmp_path: Path) -> None:
    """The DM read at 09:15 and not again: exactly the 17:51 failure."""
    MODULE.advance(WS, "slack", MORNING, targets=["D3"], now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, targets=["C1"], now=at(11, 46), home=tmp_path)

    result = MODULE.status(WS, targets={"slack": ["C1", "D3"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == ["slack:D3"]
    assert result["surfaces"][0]["targets"][1]["state"] == "stale"


def test_all_targets_current_makes_the_surface_current(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, targets=["C1"], now=at(11, 46), home=tmp_path)
    MODULE.advance(WS, "slack", "2026-08-28T11:50", targets=["D2"], now=at(11, 51), home=tmp_path)

    result = MODULE.status(WS, targets={"slack": ["C1", "D2"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == []
    assert result["surfaces"][0]["state"] == "current"
    assert result["surfaces"][0]["through"] == IN_RUN  # the oldest declared target


def test_target_window_falls_back_to_the_surface_watermark(tmp_path: Path) -> None:
    MODULE.advance(WS, "slack", MORNING, now=at(9, 16), home=tmp_path)

    got = MODULE.window(WS, "slack", target="D2", now=NOW, home=tmp_path)

    assert got["from"] == MORNING
    assert "surface watermark" in got["source"]


# --- a surface that carries targets cannot be advanced wholesale (v2.34.0) --------------------


def test_surface_level_advance_is_refused_once_targets_exist(tmp_path: Path) -> None:
    """The 2026-09-01 Chat miss: a wholesale advance claimed coverage no
    per-space read backed."""
    MODULE.advance(WS, "gchat", IN_RUN, targets=["spaces/A"], now=at(11, 46), home=tmp_path)

    with pytest.raises(ValueError, match="per-target watermarks"):
        MODULE.advance(WS, "gchat", "now", now=NOW, home=tmp_path)

    explicit = MODULE.advance(WS, "gchat", "now", now=NOW, home=tmp_path, surface_level=True)
    assert explicit["moved"] is True


def test_cli_surface_level_flag_is_required_once_targets_exist(tmp_path: Path) -> None:
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "gchat",
            "--target", "spaces/A", "--through", "now")

    refused = run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "gchat", "--through", "now")
    assert refused.returncode == 2
    assert "--surface-level" in refused.stderr

    allowed = run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "gchat", "--through", "now",
                      "--surface-level")
    assert allowed.returncode == 0


# --- deferrals: explicit, dated, and spent by a write ---------------------------------


def test_deferral_requires_a_reason(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        MODULE.defer(WS, "slack", "   ", now=NOW, home=tmp_path)


def test_explicit_deferral_unblocks_for_one_day_only(tmp_path: Path) -> None:
    """A deferral silences a gap for a day, never indefinitely — an indefinite
    silence is how a recorded gap becomes furniture."""
    MODULE.advance(WS, "slack", MORNING, now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.defer(WS, "slack", "Slack API outage", now=NOW, home=tmp_path)

    same_day = MODULE.status(WS, ["slack"], now=NOW, home=tmp_path)
    later = MODULE.status(WS, ["slack"], now=NOW + timedelta(days=2), home=tmp_path)

    assert same_day["blocking"] == []
    assert same_day["surfaces"][0]["state"] == "deferred"
    assert later["blocking"] == ["slack"]
    assert later["surfaces"][0]["stale_deferral"] is True


def test_a_target_deferral_silences_only_that_target(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, targets=["C1"], now=at(11, 46), home=tmp_path)
    MODULE.defer(WS, "slack", "member left the workspace", target="D2", now=NOW, home=tmp_path)

    result = MODULE.status(WS, targets={"slack": ["C1", "D2", "D3"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == ["slack:D3"]


def test_a_successful_write_spends_the_deferral(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.defer(WS, "slack", "outage", now=at(11, 40), home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, now=at(11, 46), home=tmp_path)

    row = MODULE.status(WS, ["slack"], now=NOW, home=tmp_path)["surfaces"][0]
    assert row["state"] == "current" and row["deferral_reason"] is None


def test_surfaces_are_tracked_independently(tmp_path: Path) -> None:
    """One surface closing must not vouch for another — the completeness claim
    that hid the original gap."""
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "slack", IN_RUN, now=at(11, 46), home=tmp_path)
    MODULE.advance(WS, "email", MORNING, now=at(9, 16), home=tmp_path)

    assert MODULE.status(WS, ["slack", "email"], now=NOW, home=tmp_path)["blocking"] == ["email"]


def test_store_is_scoped_per_workspace(tmp_path: Path) -> None:
    """Engagement workspaces must not read each other's sync state."""
    MODULE.advance("alpha", "slack", "now", now=NOW, home=tmp_path)

    assert MODULE.window("beta", "slack", now=NOW, home=tmp_path)["bootstrap"]


def test_duration_parsing() -> None:
    assert MODULE.parse_duration("90m") == timedelta(minutes=90)
    assert MODULE.parse_duration("1d12h") == timedelta(hours=36)
    with pytest.raises(ValueError):
        MODULE.parse_duration("soon")


# --- the gate is consumable by a ritual -------------------------------------------------


def run_cli(tmp_path: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    env = {"SYNTHESIS_HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, env=env,
    )


def test_cli_begin_then_status_since_run_lists_exactly_what_was_skipped(tmp_path: Path) -> None:
    """The property that makes this load-bearing: a ritual step can fail on it,
    and the failure names the keys the run did not re-read."""
    assert run_cli(tmp_path, "begin", "--workspace", WS, "--label", "mid-day").returncode == 0
    assert run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "slack",
                   "--target", "C1", "--through", "now").returncode == 0

    done = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "slack",
                   "--target", "slack:C1", "--target", "slack:D2", "--since", "run", "--json")

    assert done.returncode == 1
    payload = json.loads(done.stdout)
    assert payload["blocking"] == ["slack:D2"]
    assert payload["bound_source"] == "run"


def test_cli_targets_from_file(tmp_path: Path) -> None:
    declared = tmp_path / "targets.json"
    declared.write_text(json.dumps({"slack": ["C1", "D2"]}), encoding="utf-8")
    run_cli(tmp_path, "begin", "--workspace", WS)
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "slack",
            "--target", "C1", "--target", "D2", "--through", "now")

    done = run_cli(tmp_path, "status", "--workspace", WS, "--targets-from", str(declared),
                   "--since", "run", "--json")

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["blocking"] == []


def test_cli_window_prints_the_epoch_bounds_a_read_call_takes(tmp_path: Path) -> None:
    """A window parameter is a claim about time: computed and echoed, never typed."""
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "slack", "--through", "now")

    done = run_cli(tmp_path, "window", "--workspace", WS, "--surface", "slack")

    assert done.returncode == 0
    assert "→" in done.stdout
    assert "oldest=" in done.stdout and "latest=" in done.stdout


def test_cli_status_refuses_an_empty_surface_set(tmp_path: Path) -> None:
    """The declared set must come from the caller: the store only knows
    surfaces already written, so a store-only status walks straight past a
    declared surface that has never been swept (R-02 external review)."""
    done = run_cli(tmp_path, "status", "--workspace", WS, "--since", "now", "--json")

    assert done.returncode == 2
    assert "declared surface set" in done.stderr


def test_cli_status_blocks_a_declared_surface_never_written(tmp_path: Path) -> None:
    """The bootstrap bypass itself: no advance() has ever run, and the
    declared surface must still block rather than vanish."""
    done = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "slack",
                   "--max-age", "1d", "--json")

    assert done.returncode == 1
    assert json.loads(done.stdout)["blocking"] == ["slack"]


def test_cli_since_run_without_begin_is_an_error(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "slack", "--since", "run")

    assert done.returncode == 2
    assert "begin" in done.stderr


# --- the documented rules the mechanism depends on ------------------------------------

SKILLS_ROOT = Path(__file__).resolve().parents[2]


def _skill_text(name: str) -> str:
    return (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def test_rituals_document_the_watermark_and_blocking_gap() -> None:
    """A mechanism nobody is told to run is not a control."""
    text = _skill_text("synthesis-daily-rituals")

    assert "sync_watermark.py" in text
    assert "actually written" in text.lower()
    assert "exits non-zero" in text or "Non-zero exit" in text


def test_rituals_carry_the_watermark_gate_invocation() -> None:
    """Day-Start Step 3b and Day-End Step 1 carry the exact invocation with
    explicit surfaces and the run bound."""
    text = _skill_text("synthesis-daily-rituals")
    assert text.count("sync_watermark.py status --workspace <W> --surface <s> --since run") >= 2


def test_rituals_open_every_sync_with_begin_and_reread_every_target() -> None:
    """The mid-day defect: a DM read at day-start was treated as current all
    day. The protocol must stamp the run and re-read every declared target."""
    text = _skill_text("synthesis-daily-rituals")
    assert "sync_watermark.py begin" in text
    assert "already read today" in text
    assert "re-reads every declared target" in text


def test_watermark_reference_carries_the_contract() -> None:
    reference = (SKILLS_ROOT / "synthesis-daily-rituals" / "references" / "sync-watermarks.md")
    text = reference.read_text(encoding="utf-8")
    assert "--since run" in text
    assert "END of that day" in text
    assert "--targets-from" in text


def test_slack_sync_takes_the_window_from_the_tool() -> None:
    """A hand-typed `oldest` produced five false empties in one morning."""
    text = _skill_text("synthesis-slack-sync")
    assert "sync_watermark.py window" in text
    assert "sync_watermark.py advance" in text
    assert "WINDOW_OLDEST" in text
    assert "LAST_SYNC_TIMESTAMP" not in text


def test_slack_sync_counts_the_users_own_outbound() -> None:
    """The principal's own messages discharge owed items; an 'unanswered'
    claim must rest on a read inside the current run."""
    text = _skill_text("synthesis-slack-sync")
    assert "own outbound" in text.lower()
    assert "unanswered" in text
    assert "status --since run" in text


def test_transcripts_forbid_a_judgment_gate_before_fetching() -> None:
    """Declared means fetched — and (post R-02 review) the policy must have an
    execution path, not just phrasing: the declared-window sweep enumerates the
    set, fetches every member, and accounts for every member."""
    text = _skill_text("synthesis-meeting-transcripts")

    assert "does not get a vote" in text
    assert "after* fetching" in text or "after fetching" in text
    assert "### Step 0: Declared-window sweep" in text
    assert "Enumerate the declared set" in text
    assert "unclosed gap" in text
    assert "Account for every member" in text


def test_slack_sync_bans_deriving_read_ids_in_the_sweep() -> None:
    """Two id-like fields per entry is a trap that hides until someone leaves —
    and (post R-02 review) the sweep steps must consume the preflight rather
    than contradict it: no numbered step may iterate the config for ids."""
    text = _skill_text("synthesis-slack-sync")

    assert "preflight" in text
    assert "banned" in text
    assert "dm_id" in text
    assert "### Step 0: Preflight" in text
    assert "resolved-target list" in text
    assert "For each channel in the config" not in text
    assert "For each DM channel in the config" not in text
    assert "RESOLVED_CONVERSATION_ID" in text

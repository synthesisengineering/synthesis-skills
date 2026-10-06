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
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_watermark.py"
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
    MODULE.advance(WS, "chat-fixture", "2026-08-27T09:15", now=at(9, 20, day=27), home=tmp_path)

    got = MODULE.window(WS, "chat-fixture", now=NOW, home=tmp_path)

    assert got["from"] == "2026-08-27T09:15:00-04:00"
    assert got["from_epoch"] == int(datetime(2026, 8, 27, 9, 15, tzinfo=TZ).timestamp())
    assert got["to"] == "2026-08-28T12:00:00-04:00"
    assert got["span"] == "1d 2h 45m"
    assert "→" in got["human"]


def test_a_skipped_run_leaves_a_gap_the_next_run_must_cover(tmp_path: Path) -> None:
    """The verbatim v1 failure: written through 8/20, nothing since, and the
    next window must reach back to 8/20 rather than starting near today."""
    MODULE.advance(WS, "chat-fixture", "2026-08-20T12:00", now=at(12, day=20), home=tmp_path)

    got = MODULE.window(WS, "chat-fixture", now=NOW, home=tmp_path)

    assert got["from"] == "2026-08-20T12:00:00-04:00"
    assert got["span"] == "8d"


def test_no_watermark_reports_bootstrap_rather_than_guessing(tmp_path: Path) -> None:
    got = MODULE.window(WS, "email", now=NOW, home=tmp_path)

    assert got["bootstrap"] is True
    assert got["from"] is None and got["from_epoch"] is None
    assert "backfill bound" in got["human"]


# --- the watermark advances only on a successful write, never into the future


def test_watermark_never_moves_backwards(tmp_path: Path) -> None:
    MODULE.advance(WS, "chat-fixture", "2026-08-26T10:00", now=NOW, home=tmp_path)

    result = MODULE.advance(WS, "chat-fixture", "2026-08-22T10:00", now=NOW, home=tmp_path)

    assert result["moved"] is False
    assert result["entries"][0]["through"] == "2026-08-26T10:00:00-04:00"


def test_future_watermark_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="future"):
        MODULE.advance(WS, "chat-fixture", "2026-08-28T13:00", now=NOW, home=tmp_path)


def test_a_bare_date_means_end_of_day_so_today_is_refused_mid_day(tmp_path: Path) -> None:
    """A mid-day run cannot stamp 'today' — it must record when it read."""
    with pytest.raises(ValueError, match="END of that day"):
        MODULE.advance(WS, "chat-fixture", "2026-08-28", now=NOW, home=tmp_path)

    result = MODULE.advance(WS, "chat-fixture", "2026-08-27", now=NOW, home=tmp_path)
    assert result["through"] == "2026-08-28T00:00:00-04:00"


def test_now_is_an_accepted_moment(tmp_path: Path) -> None:
    result = MODULE.advance(WS, "chat-fixture", "now", now=NOW, home=tmp_path)
    assert result["through"] == "2026-08-28T12:00:00-04:00"


# --- epoch seconds: window's printed bound is advance's accepted input (2026-09-14)

EPOCH_0915 = 1787922900  # 2026-08-28T09:15:00-04:00, the MORNING read
EPOCH_1300 = 1787936400  # 2026-08-28T13:00:00-04:00, an hour ahead of NOW


def test_epoch_seconds_are_an_accepted_moment_and_stored_canonically(tmp_path: Path) -> None:
    """The 2026-09-14 defect: `window` printed `latest=1789397434` and
    `advance --through 1789397434` refused it as 'not a timestamp', so the
    natural pipeline failed on every Slack target. An epoch is accepted and
    normalized to the store's ISO-8601 form — the store never holds an epoch."""
    result = MODULE.advance(WS, "chat-fixture", str(EPOCH_0915), now=NOW, home=tmp_path)

    assert result["moved"] is True
    assert result["through"] == MORNING
    stored = json.loads(MODULE.store_path(WS, tmp_path).read_text(encoding="utf-8"))
    assert stored["surfaces"]["chat-fixture"]["through"] == MORNING


def test_slack_ts_with_a_fractional_part_is_floored_to_the_second(tmp_path: Path) -> None:
    """Slack's `ts` is epoch seconds with six fractional digits. The fraction
    is dropped, never rounded up: a watermark claims at most what was read."""
    result = MODULE.advance(WS, "chat-fixture", f"{EPOCH_0915}.999999", now=NOW, home=tmp_path)

    assert result["through"] == MORNING


def test_window_latest_round_trips_into_advance(tmp_path: Path) -> None:
    """window's `to_epoch` is advance's `--through`, and the store lands on
    window's `to`: the two ends of the pipeline are pinned to agree."""
    MODULE.advance(WS, "chat-fixture", "2026-08-27T09:15", now=at(9, 20, day=27), home=tmp_path)
    before = MODULE.window(WS, "chat-fixture", now=NOW, home=tmp_path)

    result = MODULE.advance(WS, "chat-fixture", str(before["to_epoch"]), now=NOW, home=tmp_path)

    assert result["moved"] is True
    assert result["through"] == before["to"] == "2026-08-28T12:00:00-04:00"
    after = MODULE.window(WS, "chat-fixture", now=NOW, home=tmp_path)
    assert after["from"] == before["to"]
    assert after["from_epoch"] == before["to_epoch"]


def test_a_future_epoch_is_refused_without_the_bare_date_hint(tmp_path: Path) -> None:
    """A ten-digit epoch is ten characters long, exactly like YYYY-MM-DD; the
    end-of-day hint belongs to a bare date and must not attach to an epoch."""
    with pytest.raises(ValueError, match="future") as caught:
        MODULE.advance(WS, "chat-fixture", str(EPOCH_1300), now=NOW, home=tmp_path)

    assert "END of that day" not in str(caught.value)


def test_refusal_names_every_accepted_form() -> None:
    with pytest.raises(ValueError, match="not a timestamp") as caught:
        MODULE.parse_moment("soon", NOW)

    message = str(caught.value)
    for form in ("ISO-8601", "YYYY-MM-DD", "epoch seconds", "1789397434",
                 "1789397434.123456", "'now'"):
        assert form in message, form


@pytest.mark.parametrize("text", ["178793280", "17879328000", "1787932800000", "1787932800."])
def test_an_integer_that_is_not_ten_digits_is_not_an_epoch(text: str) -> None:
    """Nine digits is 1975, eleven is 2536, thirteen is milliseconds, a
    trailing dot carries no fraction: none is a moment this store records."""
    with pytest.raises(ValueError, match="not a timestamp"):
        MODULE.parse_moment(text, NOW)


def test_epoch_milliseconds_are_named_in_the_refusal() -> None:
    """A thirteen-digit value is the one near miss a Slack or JS caller
    produces; the refusal names it and the seconds form to pass instead."""
    with pytest.raises(ValueError, match="milliseconds") as caught:
        MODULE.parse_moment("1787932800000", NOW)

    assert "1787932800" in str(caught.value)


def test_a_leading_zero_is_not_a_ten_digit_epoch() -> None:
    """`0999999999` is ten digits long, but no epoch `window` prints starts
    with a zero; read as seconds it is 2001-09-09, a typo accepted as a
    moment. It is refused, and the refusal names every accepted form."""
    with pytest.raises(ValueError, match="not a timestamp") as caught:
        MODULE.parse_moment("0999999999", NOW)

    message = str(caught.value)
    assert "'0999999999'" in message
    for form in ("ISO-8601", "YYYY-MM-DD", "1789397434", "1789397434.123456", "'now'"):
        assert form in message, form


def test_cli_advance_refuses_a_leading_zero_epoch_naming_the_accepted_form(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture",
                   "--through", "0999999999")

    assert done.returncode == 2
    assert "not a timestamp: '0999999999'" in done.stderr
    assert "1789397434" in done.stderr and "'now'" in done.stderr


@pytest.mark.parametrize("text", ["17879328000000", "178793280000000", "0999999999999"])
def test_the_milliseconds_branch_is_anchored_to_thirteen_leading_nonzero_digits(text: str) -> None:
    """Fourteen or fifteen digits is no near miss this store names, and a
    thirteen-digit value with a leading zero would suggest a ten-digit
    seconds form the parser itself refuses. Each gets the plain refusal."""
    with pytest.raises(ValueError, match="not a timestamp") as caught:
        MODULE.parse_moment(text, NOW)

    assert "milliseconds" not in str(caught.value)


NAIVE_NOW = NOW.replace(tzinfo=None)
# The refusals render a moment as `Fri 2026-08-28 12:00:01 EDT`; the echoed
# ISO input carries a `T` between date and time, so this picks out only the
# rendered moments and never the input.
RENDERED_TIME = r"\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}) "


@pytest.mark.parametrize("text", [str(EPOCH_0915), f"{EPOCH_0915}.5", "2026-08-28T09:15",
                                  "2026-08-27", "now"])
def test_every_form_shares_the_awareness_of_now(text: str) -> None:
    """_localize copies `now`'s zone onto an ISO or bare-date form, so a naive
    `now` yields a naive moment; the epoch branch must agree, or `advance`
    compares an aware moment against a naive one and Python raises."""
    assert MODULE.parse_moment(text, NOW).tzinfo is not None
    assert MODULE.parse_moment(text, NAIVE_NOW).tzinfo is None


def test_a_naive_epoch_is_the_local_wall_clock() -> None:
    """Naive means local time for the epoch form as for every other."""
    assert MODULE.parse_moment(str(EPOCH_0915), NAIVE_NOW) == datetime.fromtimestamp(EPOCH_0915)
    assert MODULE.parse_moment(str(EPOCH_0915), NOW) == datetime(2026, 8, 28, 9, 15, tzinfo=TZ)


def test_future_refusal_renders_both_moments_to_the_second(tmp_path: Path) -> None:
    """A value one second ahead of now is refused, and the refusal must show
    two different times: rendered to the minute, both read 12:00 and the
    message contradicts itself."""
    one_second_ahead = MODULE.stamp(NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="future") as caught:
        MODULE.advance(WS, "chat-fixture", one_second_ahead, now=NOW, home=tmp_path)

    times = re.findall(RENDERED_TIME, str(caught.value))
    assert len(times) == 2, str(caught.value)
    assert times[0] != times[1], str(caught.value)
    assert times[0].endswith(":01") and times[1].endswith(":00"), times


def test_backwards_refusal_renders_both_moments_to_the_second(tmp_path: Path) -> None:
    """The same two-moment shape: a value one second behind the recorded
    watermark is refused, and the detail must show two different times."""
    MODULE.advance(WS, "chat-fixture", "2026-08-28T10:00:00", now=NOW, home=tmp_path)

    result = MODULE.advance(WS, "chat-fixture", "2026-08-28T09:59:59", now=NOW, home=tmp_path)

    assert result["moved"] is False
    times = re.findall(RENDERED_TIME, result["entries"][0]["detail"])
    assert len(times) == 2, result["entries"][0]["detail"]
    assert times[0] != times[1]
    assert times[0].endswith(":59") and times[1].endswith(":00"), times


# --- a run proves its own coverage: status --since run --------------------------


def test_status_blocks_on_a_read_older_than_the_run(tmp_path: Path) -> None:
    """The v2 defect itself: a 09:15 read is not current at an 11:39 run."""
    MODULE.advance(WS, "chat-fixture", MORNING, now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, "mid-day", now=RUN_START, home=tmp_path)

    result = MODULE.status(WS, ["chat-fixture"], now=NOW, home=tmp_path)

    assert result["bound_source"] == "run"
    assert result["blocking"] == ["chat-fixture"]
    assert result["surfaces"][0]["state"] == "stale"


def test_status_is_clear_once_the_surface_is_re_read_in_this_run(tmp_path: Path) -> None:
    MODULE.advance(WS, "chat-fixture", MORNING, now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, now=at(11, 46), home=tmp_path)

    assert MODULE.status(WS, ["chat-fixture"], now=NOW, home=tmp_path)["blocking"] == []


def test_status_max_age_is_an_alternative_bound(tmp_path: Path) -> None:
    MODULE.advance(WS, "chat-fixture", MORNING, now=at(9, 16), home=tmp_path)

    loose = MODULE.status(WS, ["chat-fixture"], max_age=timedelta(hours=4), now=NOW, home=tmp_path)
    tight = MODULE.status(WS, ["chat-fixture"], max_age=timedelta(hours=2), now=NOW, home=tmp_path)

    assert loose["blocking"] == []
    assert tight["blocking"] == ["chat-fixture"]


def test_status_needs_a_freshness_bound(tmp_path: Path) -> None:
    MODULE.advance(WS, "chat-fixture", MORNING, now=at(9, 16), home=tmp_path)
    with pytest.raises(ValueError, match="freshness bound"):
        MODULE.status(WS, ["chat-fixture"], now=NOW, home=tmp_path)


# --- declared read targets block individually ---------------------------------------


def test_declared_targets_block_individually(tmp_path: Path) -> None:
    """'20 of 60 targets read' becomes a list of keys, not a sentence."""
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, targets=["C1", "D2"], now=at(11, 46), home=tmp_path)

    result = MODULE.status(WS, targets={"chat-fixture": ["C1", "D2", "D3"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == ["chat-fixture:D3"]
    surface = result["surfaces"][0]
    assert surface["blocking"] is True
    assert [t["state"] for t in surface["targets"]] == ["current", "current", "missing"]


def test_a_target_read_before_the_run_is_stale(tmp_path: Path) -> None:
    """The DM read at 09:15 and not again: exactly the 17:51 failure."""
    MODULE.advance(WS, "chat-fixture", MORNING, targets=["D3"], now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, targets=["C1"], now=at(11, 46), home=tmp_path)

    result = MODULE.status(WS, targets={"chat-fixture": ["C1", "D3"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == ["chat-fixture:D3"]
    assert result["surfaces"][0]["targets"][1]["state"] == "stale"


def test_all_targets_current_makes_the_surface_current(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, targets=["C1"], now=at(11, 46), home=tmp_path)
    MODULE.advance(WS, "chat-fixture", "2026-08-28T11:50", targets=["D2"], now=at(11, 51), home=tmp_path)

    result = MODULE.status(WS, targets={"chat-fixture": ["C1", "D2"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == []
    assert result["surfaces"][0]["state"] == "current"
    assert result["surfaces"][0]["through"] == IN_RUN  # the oldest declared target


def test_target_window_falls_back_to_the_surface_watermark(tmp_path: Path) -> None:
    MODULE.advance(WS, "chat-fixture", MORNING, now=at(9, 16), home=tmp_path)

    got = MODULE.window(WS, "chat-fixture", target="D2", now=NOW, home=tmp_path)

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
        MODULE.defer(WS, "chat-fixture", "   ", now=NOW, home=tmp_path)


def test_explicit_deferral_unblocks_for_one_day_only(tmp_path: Path) -> None:
    """A deferral silences a gap for a day, never indefinitely — an indefinite
    silence is how a recorded gap becomes furniture."""
    MODULE.advance(WS, "chat-fixture", MORNING, now=at(9, 16), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.defer(WS, "chat-fixture", "Slack API outage", now=NOW, home=tmp_path)

    same_day = MODULE.status(WS, ["chat-fixture"], now=NOW, home=tmp_path)
    later = MODULE.status(WS, ["chat-fixture"], now=NOW + timedelta(days=2), home=tmp_path)

    assert same_day["blocking"] == []
    assert same_day["surfaces"][0]["state"] == "deferred"
    assert later["blocking"] == ["chat-fixture"]
    assert later["surfaces"][0]["stale_deferral"] is True


def test_a_deferral_from_before_the_run_excuses_nothing_in_it(tmp_path: Path) -> None:
    """2026-10-06: a deferral recorded the previous afternoon, still under a day old, hid 390 unread
    targets from the next morning's run, which printed them BLOCKING and exited 0."""
    MODULE.defer(WS, "chat-fixture", "read in full elsewhere", now=at(9, 0) - timedelta(hours=20), home=tmp_path)
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    result = MODULE.status(WS, targets={"chat-fixture": ["C1", "D2"]}, now=NOW, home=tmp_path)
    assert result["blocking"] == ["chat-fixture:C1", "chat-fixture:D2"]


def test_a_surface_deferred_in_this_run_shows_its_targets_deferred(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.defer(WS, "chat-fixture", "Chat API outage", now=NOW, home=tmp_path)
    result = MODULE.status(WS, targets={"chat-fixture": ["C1", "D2"]}, now=NOW, home=tmp_path)
    assert result["blocking"] == [] and {t["state"] for t in result["surfaces"][0]["targets"]} == {"deferred"}


def test_a_target_deferral_silences_only_that_target(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, targets=["C1"], now=at(11, 46), home=tmp_path)
    MODULE.defer(WS, "chat-fixture", "member left the workspace", target="D2", now=NOW, home=tmp_path)

    result = MODULE.status(WS, targets={"chat-fixture": ["C1", "D2", "D3"]}, now=NOW, home=tmp_path)

    assert result["blocking"] == ["chat-fixture:D3"]


def test_a_successful_write_spends_the_deferral(tmp_path: Path) -> None:
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.defer(WS, "chat-fixture", "outage", now=at(11, 40), home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, now=at(11, 46), home=tmp_path)

    row = MODULE.status(WS, ["chat-fixture"], now=NOW, home=tmp_path)["surfaces"][0]
    assert row["state"] == "current" and row["deferral_reason"] is None


def test_surfaces_are_tracked_independently(tmp_path: Path) -> None:
    """One surface closing must not vouch for another — the completeness claim
    that hid the original gap."""
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    MODULE.advance(WS, "chat-fixture", IN_RUN, now=at(11, 46), home=tmp_path)
    MODULE.advance(WS, "email", MORNING, now=at(9, 16), home=tmp_path)

    assert MODULE.status(WS, ["chat-fixture", "email"], now=NOW, home=tmp_path)["blocking"] == ["email"]


def test_store_is_scoped_per_workspace(tmp_path: Path) -> None:
    """Engagement workspaces must not read each other's sync state."""
    MODULE.advance("alpha", "chat-fixture", "now", now=NOW, home=tmp_path)

    assert MODULE.window("beta", "chat-fixture", now=NOW, home=tmp_path)["bootstrap"]


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
    assert run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture",
                   "--target", "C1", "--through", "now").returncode == 0

    done = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "chat-fixture",
                   "--target", "chat-fixture:C1", "--target", "chat-fixture:D2", "--since", "run", "--json")

    assert done.returncode == 1
    payload = json.loads(done.stdout)
    assert payload["blocking"] == ["chat-fixture:D2"]
    assert payload["bound_source"] == "run"


def test_cli_targets_from_file(tmp_path: Path) -> None:
    declared = tmp_path / "targets.json"
    declared.write_text(json.dumps({"chat-fixture": ["C1", "D2"]}), encoding="utf-8")
    run_cli(tmp_path, "begin", "--workspace", WS)
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture",
            "--target", "C1", "--target", "D2", "--through", "now")

    done = run_cli(tmp_path, "status", "--workspace", WS, "--targets-from", str(declared),
                   "--since", "run", "--json")

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["blocking"] == []


def test_cli_window_prints_the_epoch_bounds_a_read_call_takes(tmp_path: Path) -> None:
    """A window parameter is a claim about time: computed and echoed, never typed."""
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture", "--through", "now")

    done = run_cli(tmp_path, "window", "--workspace", WS, "--surface", "chat-fixture")

    assert done.returncode == 0
    assert "→" in done.stdout
    assert "oldest=" in done.stdout and "latest=" in done.stdout


def test_cli_window_latest_round_trips_into_advance(tmp_path: Path) -> None:
    """The verbatim 2026-09-14 failure: `window` printed `latest=1789397434`
    and `advance --through 1789397434` was refused as not a timestamp. The
    printed value is the accepted input, and the store lands on that second
    in its canonical ISO-8601-with-offset form."""
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture",
            "--target", "C1", "--through", "2026-08-27T09:15")
    shown = run_cli(tmp_path, "window", "--workspace", WS, "--surface", "chat-fixture", "--target", "C1")
    assert shown.returncode == 0, shown.stderr
    latest = re.search(r"latest=(\d{10})\b", shown.stdout)
    assert latest, shown.stdout

    done = run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture",
                   "--target", "C1", "--through", latest.group(1))

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["moved"] is True
    stored = json.loads(MODULE.store_path(WS, tmp_path).read_text(encoding="utf-8"))
    through = stored["surfaces"]["chat-fixture"]["targets"]["C1"]["through"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", through), through
    assert int(datetime.fromisoformat(through).timestamp()) == int(latest.group(1))
    again = run_cli(tmp_path, "window", "--workspace", WS, "--surface", "chat-fixture", "--target", "C1")
    assert f"oldest={latest.group(1)} " in again.stdout


def test_cli_status_since_accepts_epoch_seconds(tmp_path: Path) -> None:
    """`--since` shares the parser with `--through`: an epoch, with or without
    Slack's fraction, is a freshness bound."""
    run_cli(tmp_path, "advance", "--workspace", WS, "--surface", "chat-fixture", "--through", "now")
    written = json.loads(MODULE.store_path(WS, tmp_path).read_text(encoding="utf-8"))
    at_write = int(datetime.fromisoformat(written["surfaces"]["chat-fixture"]["through"]).timestamp())

    clear = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "chat-fixture",
                    "--since", str(at_write - 3600), "--json")
    stale = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "chat-fixture",
                    "--since", f"{at_write + 3600}.250000", "--json")

    assert clear.returncode == 0, clear.stderr
    assert json.loads(clear.stdout)["blocking"] == []
    assert int(datetime.fromisoformat(json.loads(clear.stdout)["since"]).timestamp()) == at_write - 3600
    assert stale.returncode == 1, stale.stderr
    assert json.loads(stale.stdout)["blocking"] == ["chat-fixture"]


def test_cli_help_names_the_epoch_form_on_every_moment_argument(tmp_path: Path) -> None:
    """`advance --through` and `status --since` share parse_moment, and each
    argument's own help is the documentation closest to the command: it names
    the epoch form beside the others, so what the help lists and what the
    parser accepts cannot drift apart."""
    for command, flag in (("advance", "--through"), ("status", "--since")):
        shown = run_cli(tmp_path, command, "--help")
        assert shown.returncode == 0, shown.stderr
        text = " ".join(shown.stdout.split())
        assert flag in text, (command, text)
        for form in ("ISO-8601", "YYYY-MM-DD", "epoch seconds", "window", "Slack", "now"):
            assert form in text, (command, form, text)


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
    done = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "chat-fixture",
                   "--max-age", "1d", "--json")

    assert done.returncode == 1
    assert json.loads(done.stdout)["blocking"] == ["chat-fixture"]


def test_cli_since_run_without_begin_is_an_error(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "status", "--workspace", WS, "--surface", "chat-fixture", "--since", "run")

    assert done.returncode == 2
    assert "begin" in done.stderr


# --- the documented rules the mechanism depends on ------------------------------------

SKILLS_ROOT = Path(__file__).resolve().parents[2]


def _skill_text(name: str) -> str:
    folder = SKILLS_ROOT / name
    return "\n".join(p.read_text(encoding="utf-8") for p in [folder / "SKILL.md", *sorted((folder / "references").glob("*.md"))]
                     if p.name not in ("preserved.md", "coverage-map.md") and not p.name.startswith(("preserved-", "version-history")))


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


def _reference_bullet(verb: str) -> str:
    """The `- **`<verb>`**` bullet of the watermark reference, up to the next verb's."""
    reference = (SKILLS_ROOT / "synthesis-daily-rituals" / "references" / "sync-watermarks.md")
    text = reference.read_text(encoding="utf-8")
    start = text.index(f"- **`{verb}`**")
    end = text.find("\n- **`", start + 1)
    return text[start:] if end < 0 else text[start:end]


def test_watermark_reference_names_the_epoch_form_for_through() -> None:
    """The reference's own `advance` line instructs `--through <latest>`, and
    `window` prints `latest=` as epoch seconds; the prose form list under the
    same verb must name that form, or the document contradicts the command it
    sits under (2026-09-14 review of the epoch-form repair)."""
    bullet = _reference_bullet("advance")

    assert "--through" in bullet
    for form in ("epoch seconds", "window", "Slack"):
        assert form in bullet, (form, bullet)


def test_json_window_has_exact_epoch_bounds(tmp_path):
    wm = MODULE
    moment = datetime(2026, 9, 22, 14, 30, tzinfo=timezone.utc)
    fresh = wm.window("synthetic", "email", now=moment, home=tmp_path)
    assert fresh["oldest"] is None and fresh["latest"] == fresh["to_epoch"]
    wm.advance("synthetic", "email", "2026-09-22T12:00:00+00:00", now=moment, home=tmp_path)
    current = wm.window("synthetic", "email", now=moment, home=tmp_path)
    assert current["oldest"] == current["from_epoch"] == 1790078400
    assert current["latest"] == current["to_epoch"] == int(moment.timestamp())


def _set_acquisition_clock(monkeypatch, current):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current if tz is None else current.astimezone(tz)

    monkeypatch.setattr(MODULE, "datetime", Clock)


@pytest.mark.parametrize("offset_minutes", [-240, 0, 330])
def test_precise_clock_keeps_now_watermarks_and_windows_at_whole_seconds(
    tmp_path, monkeypatch, offset_minutes
):
    current = datetime(
        2026, 9, 26, 12, 0, 0, 900000,
        tzinfo=timezone(timedelta(minutes=offset_minutes)),
    )
    _set_acquisition_clock(monkeypatch, current)
    precise = MODULE.now_local()
    assert precise == current.replace(microsecond=0)
    assert MODULE.parse_moment("now", current).microsecond == 0
    MODULE.begin(WS, home=tmp_path)
    result = MODULE.advance(WS, "chat-fixture", "now", home=tmp_path)
    window = MODULE.window(WS, "chat-fixture", home=tmp_path)
    stored = json.loads(MODULE.store_path(WS, tmp_path).read_text())
    assert result["through"] == MODULE.stamp(precise)
    assert window["to"] == MODULE.stamp(precise)
    assert window["to_epoch"] == int(precise.timestamp())
    assert window["from_epoch"] == window["to_epoch"]
    assert datetime.fromisoformat(stored["run"]["started_at"]).microsecond == 0
    for field in ("through", "updated_at"):
        assert datetime.fromisoformat(stored["surfaces"]["chat-fixture"][field]).microsecond == 0


# --- reads through the harness's own connectors advance like any other (2026-10-01) ----


@pytest.mark.parametrize("surface", ["slack", "meetings", "gchat", "email"])
def test_a_connector_read_advances_without_a_token_or_receipt(tmp_path: Path, surface: str) -> None:
    """2026-10-01: syncs ran in full through the harness connectors, but bookmarks
    stopped advancing because an advance demanded acquisition receipts that only a
    direct API reader with its own token could produce. A saved read advances."""
    MODULE.begin(WS, now=RUN_START, home=tmp_path)
    result = MODULE.advance(WS, surface, IN_RUN, targets=["T1"], now=at(11, 46), home=tmp_path)

    assert result["moved"] is True
    assert MODULE.status(WS, targets={surface: ["T1"]}, now=NOW, home=tmp_path)["blocking"] == []


def test_an_empty_workspace_is_refused(tmp_path: Path) -> None:
    """An unset variable must not write every workspace's reads into one shared store."""
    with pytest.raises(ValueError, match="empty"):
        MODULE.advance("", "slack", "now", now=NOW, home=tmp_path)
    done = run_cli(tmp_path, "begin", "--workspace", "")
    assert done.returncode == 2 and "empty" in done.stderr

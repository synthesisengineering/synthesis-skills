"""A day is not closed clean while something the principal asked that day is cited by no record.

On 2026-11-11 a principal said he should never have to add "make sure nothing is lost". An audit that evening
found that what he asked, decided or corrected reached a project record only if an agent remembered, and nothing
checked. A workspace can now turn the check on: at day-end `ritual_state.py record` itself runs
`synthesis sessions prompts` over the day against the workspace's record folders, and refuses a clean close while
it lists a prompt no record cites, or when it cannot be run. A first form took the listing's saved output; a review
on 2026-11-12 showed that a result made without the record folders, or before a later prompt, closed the day
clean, so the record now asks for itself. Committed before the change to the script.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import ritual_state  # noqa: E402

DAY = "2026-11-11"
ON = {"plans_dirs": [], "prompt_reconcile": {"records": ["/kb/desk"]}}


def declare(state: Path, **workspaces) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "config.json").write_text(json.dumps({"workspaces": workspaces}), encoding="utf-8")


def listing(tmp_path: Path, monkeypatch, *left, total=3, workspace="desk", day=DAY, code=None, says="") -> Path:
    """A stand-in for the `synthesis` command on the PATH: it writes down the words it was run with and answers as
    the listing would. With `says`, it answers on stderr only, as a listing that could not be made does."""
    bin_, asked = tmp_path / "bin", tmp_path / "asked.json"
    bin_.mkdir(exist_ok=True)
    answer = json.dumps({"workspace": workspace, "date": day, "prompts": total, "open": list(left)})
    (bin_ / "synthesis").write_text(
        f"#!{sys.executable}\nimport json, sys\njson.dump(sys.argv[1:], open({str(asked)!r}, 'w'))\n"
        + (f"sys.stderr.write({says!r})\n" if says else f"print({answer!r})\n")
        + f"sys.exit({(1 if left else 0) if code is None else code})\n", encoding="utf-8")
    (bin_ / "synthesis").chmod((bin_ / "synthesis").stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}/usr/bin{os.pathsep}/bin")
    return asked


@pytest.fixture
def record(monkeypatch, capsys):
    def run(state: Path, *extra, direction="day-end", workspace="desk", day=DAY):
        monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
        monkeypatch.setattr(ritual_state, "today", lambda: date.fromisoformat(day), raising=False)
        try:
            code, refusal = ritual_state.main(["record", "--direction", direction, "--workspace", workspace, "--date", day, *extra]), ""
        except SystemExit as exc:
            code, refusal = 1, str(exc)
        return code, capsys.readouterr().out, refusal
    return run


def history(state: Path) -> str:
    log = state / "history.jsonl"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_a_workspace_that_has_not_turned_the_check_on_records_as_before(tmp_path, record, monkeypatch):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": []})
    asked = listing(tmp_path, monkeypatch)
    code, out, refusal = record(state)
    assert code == 0, refusal
    assert "prompts" not in out and '"workspace":"desk"' in history(state) and not asked.exists()   # nothing is listed
    declare(state, desk={"plans_dirs": [], "prompt_reconcile": False})
    assert record(state)[0] == 0 and not asked.exists()


def test_with_the_check_on_a_day_end_lists_the_days_prompts_itself_and_a_day_start_does_not(tmp_path, record, monkeypatch):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "prompt_reconcile": {"records": ["/kb/desk", "/kb/plans"]}})
    asked = listing(tmp_path, monkeypatch)
    code, out, refusal = record(state, direction="day-start")
    assert code == 0 and "prompts" not in out and not asked.exists(), refusal
    code, out, refusal = record(state)
    assert code == 0, refusal
    assert json.loads(asked.read_text()) == ["sessions", "prompts", "--workspace", "desk", "--date", DAY,
                                             "--records", "/kb/desk", "--records", "/kb/plans", "--json"]
    assert "prompts: all 3 typed on 2026-11-11 are cited by a record" in out and '"workspace":"desk"' in history(state)


def test_a_prompt_no_record_cites_keeps_the_day_from_closing_clean(tmp_path, record, monkeypatch):
    state = tmp_path / "state"
    declare(state, desk=ON)
    listing(tmp_path, monkeypatch, "claude-code d20ab7c4 #41", "codex 01a1cdbb #7")
    code, _, refusal = record(state)
    assert code != 0 and history(state) == ""
    assert "2 of 3" in refusal and "claude-code d20ab7c4 #41" in refusal and "codex 01a1cdbb #7" in refusal
    assert "synthesis sessions show" in refusal and "--outcome partial" in refusal
    listing(tmp_path, monkeypatch, "claude-code d20ab7c4 #41")
    code, out, refusal = record(state, "--outcome", "partial")
    assert code == 0, refusal                                        # said to be partial, it is recorded, and says what is open
    assert "prompts: 1 of 3 typed on 2026-11-11 is cited by no record" in out and '"outcome":"partial"' in history(state)


def test_when_no_prompt_was_typed_the_day_closes_and_says_so(tmp_path, record, monkeypatch):
    state = tmp_path / "state"
    declare(state, desk=ON)
    listing(tmp_path, monkeypatch, total=0)
    code, out, refusal = record(state)
    assert code == 0 and "prompts: none typed on 2026-11-11" in out, refusal


@pytest.mark.parametrize("made, says", [
    ({"workspace": "other"}, "other"),                                   # another workspace's answer
    ({"day": "2026-11-10"}, "2026-11-10"),                               # yesterday's
    ({"total": 1, "left": ["a b #1", "a b #2"]}, "does not agree with itself"),   # more open than typed
])
def test_an_answer_for_another_day_or_workspace_or_one_at_odds_with_itself_is_refused(tmp_path, record, monkeypatch, made, says):
    state = tmp_path / "state"
    declare(state, desk=ON)
    listing(tmp_path, monkeypatch, *made.get("left", []), total=made.get("total", 3), workspace=made.get("workspace", "desk"),
            day=made.get("day", DAY), code=0)
    code, _, refusal = record(state)
    assert code != 0 and says in refusal and history(state) == ""


def test_a_listing_that_cannot_be_made_closes_nothing(tmp_path, record, monkeypatch):
    """2026-11-12, a review: with an archive that could not be written the listing held no prompt, and the day
    closed clean. The listing now stops when the archive is not current, and the record with it."""
    state = tmp_path / "state"
    declare(state, desk=ON)
    listing(tmp_path, monkeypatch, code=2, says="the archive is not current: claude-code c1: not exported (read-only)")
    code, _, refusal = record(state)
    assert code != 0 and "not exported (read-only)" in refusal and history(state) == ""
    code, _, refusal = record(state, "--outcome", "partial")              # nor as a day that left some open: nothing is known
    assert code != 0 and history(state) == ""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))                   # and with no `synthesis` command at all
    code, _, refusal = record(state)
    assert code != 0 and "synthesis" in refusal and "PATH" in refusal and history(state) == ""


@pytest.mark.parametrize("setting", [True, {}, {"records": []}, {"records": "/kb/desk"}, {"records": [""]}])
def test_a_check_declared_with_no_records_is_refused(tmp_path, record, monkeypatch, setting):
    """2026-11-12, a review: `"prompt_reconcile": {}` turned the check off without a word."""
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "prompt_reconcile": setting})
    listing(tmp_path, monkeypatch)
    code, _, refusal = record(state)
    assert code != 0 and "records" in refusal and "prompt_reconcile" in refusal and history(state) == ""


def test_the_check_starts_on_the_day_the_workspace_names(tmp_path, record, monkeypatch):
    """A session exported before the upgrade keeps the kinds its records were given, so a workspace turns the
    check on from a day after it: an earlier day is recorded as before, and says so."""
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": [], "prompt_reconcile": {"records": ["/kb/desk"], "from": "2026-11-12"}})
    asked = listing(tmp_path, monkeypatch, "claude-code d20ab7c4 #41")
    code, out, refusal = record(state)
    assert code == 0 and not asked.exists() and "prompts: checked from 2026-11-12" in out, refusal
    code, _, refusal = record(state, day="2026-11-12")
    assert code != 0 and "1 of 3" in refusal

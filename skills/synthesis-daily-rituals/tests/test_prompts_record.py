"""A day is not closed clean while something the principal asked that day is cited by no record.

On 2026-11-11 a principal said he should never have to add "make sure nothing is lost". An audit that evening
found that what he asked, decided or corrected reached a project record only if an agent remembered, and nothing
checked. A workspace can now turn the check on: at day-end its ritual runs `synthesis sessions prompts` over the
day and hands the result to `ritual_state.py record`, which refuses a clean close without one, with one for
another workspace or day, or while it lists a prompt no record cites. Committed before the change to the script.
"""
from __future__ import annotations

import json
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


def result(tmp_path: Path, *left, total=3, workspace="desk", day=DAY) -> str:
    saved = tmp_path / "prompts.json"
    saved.write_text(json.dumps({"workspace": workspace, "date": day, "prompts": total, "open": list(left)}), encoding="utf-8")
    return str(saved)


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


def test_a_workspace_that_has_not_turned_the_check_on_records_as_before(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk={"plans_dirs": []})
    code, out, refusal = record(state)
    assert code == 0, refusal
    assert "prompts" not in out and '"workspace":"desk"' in history(state)


def test_with_the_check_on_a_day_end_needs_the_days_result_and_a_day_start_does_not(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk=ON)
    code, _, refusal = record(state)
    assert code != 0 and history(state) == ""
    assert "synthesis sessions prompts --workspace desk --date 2026-11-11 --records /kb/desk --json" in refusal and "--prompts" in refusal
    code, out, refusal = record(state, direction="day-start")
    assert code == 0 and "prompts" not in out, refusal


def test_a_prompt_no_record_cites_keeps_the_day_from_closing_clean(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk=ON)
    code, _, refusal = record(state, "--prompts", result(tmp_path, "claude-code d20ab7c4 #41", "codex 01a1cdbb #7"))
    assert code != 0 and history(state) == ""
    assert "2 of 3" in refusal and "claude-code d20ab7c4 #41" in refusal and "codex 01a1cdbb #7" in refusal
    assert "synthesis sessions show" in refusal and "--outcome partial" in refusal
    code, out, refusal = record(state, "--prompts", result(tmp_path, "claude-code d20ab7c4 #41"), "--outcome", "partial")
    assert code == 0, refusal                                        # said to be partial, it is recorded, and says what is open
    assert "prompts: 1 of 3 typed on 2026-11-11 is cited by no record" in out and '"outcome":"partial"' in history(state)


def test_when_every_prompt_is_cited_the_day_closes_and_says_so(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk=ON)
    code, out, refusal = record(state, "--prompts", result(tmp_path))
    assert code == 0, refusal
    assert "prompts: all 3 typed on 2026-11-11 are cited by a record" in out and '"workspace":"desk"' in history(state)
    code, out, refusal = record(state, "--prompts", result(tmp_path, total=0))
    assert code == 0 and "prompts: none typed on 2026-11-11" in out


@pytest.mark.parametrize("made, says", [
    ({"workspace": "other"}, "other"),                                   # another workspace's result
    ({"day": "2026-11-10"}, "2026-11-10"),                               # yesterday's
    ({"total": 1, "left": ["a b #1", "a b #2"]}, "does not agree with itself"),   # more open than typed
])
def test_a_result_for_another_day_or_workspace_or_one_at_odds_with_itself_is_refused(tmp_path, record, made, says):
    state = tmp_path / "state"
    declare(state, desk=ON)
    saved = result(tmp_path, *made.get("left", []), total=made.get("total", 3), workspace=made.get("workspace", "desk"), day=made.get("day", DAY))
    code, _, refusal = record(state, "--prompts", saved)
    assert code != 0 and says in refusal and history(state) == ""


def test_a_result_that_cannot_be_read_or_a_check_declared_with_no_records_is_refused(tmp_path, record):
    state = tmp_path / "state"
    declare(state, desk=ON)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    for given in (str(broken), str(tmp_path / "absent.json")):
        code, _, refusal = record(state, "--prompts", given)
        assert code != 0 and "cannot be read" in refusal and history(state) == ""
    declare(state, desk={"plans_dirs": [], "prompt_reconcile": True})
    code, _, refusal = record(state, "--prompts", result(tmp_path))
    assert code != 0 and "records" in refusal and "prompt_reconcile" in refusal

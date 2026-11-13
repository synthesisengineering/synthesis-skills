"""The lapse register, read for the weekly and the longer reviews.

Each workspace keeps a register of what slipped: one row for each item that passed its date with no decision. The
Friday review reads its last fourteen days and the quarterly, six-month and annual reviews their whole window, and
until now no script read it: whichever session ran a review started from the file. Counted on 2026-11-13, the three
seats' registers held 64, 355 and 1 rows, one table each, five cells a row. This gives a review its section from
the register, counted: the rows of the window, and what repeats among them. Committed before the code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lapse_review.py"
DAY = "2026-11-13"  # a Friday
REGISTER = """# Lapse register

Permanent history: append rows, never remove or rewrite them.

| Lapsed | Item | Where it waited | Why it lapsed | Outcome |
|---|---|---|---|---|
| 2026-08-03 | An old acknowledgment | [plan](../daily-plans/2026-08-01.md) | no time | let go after its date |
| 2026-10-26 | Reply to the supplier `supplier-quote` | [plan](../daily-plans/2026-10-24.md) | travel | sent 10-28 |
| 2026-11-02 | Reply to the supplier `supplier-quote` | `daily-plans/2026-11-01.md:40` | no answer drafted | |
| 2026-11-02 | Thanks for the review `thanks-review` | [draft](../drafts/2026-10-30-thanks.md) | waited on a name | open |
| 2026-11-09 | The event decision | daily-plans/2026-11-07.md | the date passed over a weekend | pending |

- 2026-11-03: the row of 2026-08-03 was added late, from the August plans.

| Lapsed | Item | Where it waited | Why it lapsed | Outcome | Who it affected | What can still be done |
|---|---|---|---|---|---|---|
| 2026-11-09 | Reply to the supplier `supplier-quote` | [plan](../daily-plans/2026-11-08.md) | third time | open | the supplier | call them |
| 2026-11-10 | A registration | [ledger](../drafts/_LEDGER.md) | the window closed | let go after its date | nobody | nothing |
"""


def review(tmp_path: Path, *extra, register: str | None = REGISTER, declare: bool = True):
    state, file = tmp_path / "state", tmp_path / "records" / "lapse-register.md"
    state.mkdir(exist_ok=True)
    file.parent.mkdir(exist_ok=True)
    if register is not None:
        file.write_text(register, encoding="utf-8")
    (state / "config.json").write_text(json.dumps({"workspaces": {"desk": {"lapse_register": str(file)} if declare else {}}}), encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), "--workspace", "desk", "--as-of", DAY, *extra], capture_output=True, text=True,
                          env={**os.environ, "RITUAL_STATE_DIR": str(state), "SYNTHESIS_HOME": str(tmp_path / "home")})


def test_the_weekly_window_is_the_last_fourteen_days_from_both_tables(tmp_path):
    done = review(tmp_path)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert lines[0] == f"Slipped through: 5 rows from 2026-10-31 to {DAY} (of 7 in the register)"
    rows = [line for line in lines if line.startswith("  | ")]
    assert [row.split("|")[1].strip() for row in rows] == ["2026-11-10", "2026-11-09", "2026-11-09", "2026-11-02", "2026-11-02"]   # newest first
    assert "An old acknowledgment" not in done.stdout and "sent 10-28" not in done.stdout


def test_it_names_what_repeats_and_counts_it(tmp_path):
    out = review(tmp_path).stdout
    assert "  the same item more than once: `supplier-quote` (2)" in out
    assert "  weekday: Monday (4)" in out
    assert "  where it waited: daily-plans (3)" in out
    assert "  outcome still open: 4 of 5" in out
    assert "Tuesday" not in out and "drafts (" not in out                        # once or twice is no pattern


def test_a_longer_window_reads_further_back(tmp_path):
    quarter = review(tmp_path, "--window", "quarter").stdout
    assert quarter.splitlines()[0] == f"Slipped through: 6 rows from 2026-08-14 to {DAY} (of 7 in the register)"
    assert "`supplier-quote` (3)" in quarter and "weekday: Monday (5)" in quarter
    assert review(tmp_path, "--window", "year").stdout.splitlines()[0].startswith("Slipped through: 7 rows from 2025-11-13")
    between = review(tmp_path, "--since", "2026-08-01", "--until", "2026-10-31").stdout
    assert between.splitlines()[0] == "Slipped through: 2 rows from 2026-08-01 to 2026-10-31 (of 7 in the register)"
    assert "Patterns: none repeats" in between


def test_a_window_with_no_row_says_so(tmp_path):
    out = review(tmp_path, "--since", "2026-09-01", "--until", "2026-09-30").stdout
    assert out.splitlines() == ["Slipped through: 0 rows from 2026-09-01 to 2026-09-30 (of 7 in the register)"]


def test_the_same_as_json(tmp_path):
    data = json.loads(review(tmp_path, "--json").stdout)
    assert (data["since"], data["until"], data["total"], len(data["rows"])) == ("2026-10-31", DAY, 7, 5)
    assert data["patterns"] == {"item": {"supplier-quote": 2}, "weekday": {"Monday": 4}, "place": {"daily-plans": 3}, "open": 4}
    assert data["rows"][0] == {"lapsed": "2026-11-10", "item": "A registration", "where": "[ledger](../drafts/_LEDGER.md)",
                               "why": "the window closed", "outcome": "let go after its date", "affected": "nobody", "still": "nothing",
                               "line": 18}


def test_it_writes_nothing(tmp_path):
    review(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    review(tmp_path, "--window", "year", "--json")
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_a_register_it_cannot_read_is_said_and_never_read_as_empty(tmp_path):
    undeclared = review(tmp_path, declare=False)
    assert undeclared.returncode == 2 and "lapse_register" in undeclared.stderr and undeclared.stdout == ""
    missing = review(tmp_path, register=None)
    assert missing.returncode == 2 and "is no file" in missing.stderr
    tableless = review(tmp_path, register="# Lapse register\n\nNothing yet.\n")
    assert tableless.returncode == 2 and "holds no register table" in tableless.stderr
    backwards = review(tmp_path, "--since", "2026-11-10", "--until", "2026-11-01")
    assert backwards.returncode == 2 and "before" in backwards.stderr

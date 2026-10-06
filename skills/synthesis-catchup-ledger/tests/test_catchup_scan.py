"""catchup_scan.py: scenario E94 and the truncated-preview rule (lesson 2026-08-18)."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "catchup_scan.py"

PLAN = """# Daily plan

## Priority tasks

1. Ship the parser fix
2. ~~Retire the old job~~ DONE
- [ ] {long_item}
- [x] Already finished

## Drafts

### Draft 1 — reply to the vendor

Text of the reply.

### Draft 2 — note to the team

**Sent:** 09:40

## Decisions needed

### Pick the hosting plan

Options A and B.

### Choose the release day

**Decided:** Thursday

## Carryover

- {long_carry}
- short carried item
"""

LONG_ITEM = "`sync.yaml` needs the ID fix, six resolved DM ids, and a space-count correction " * 4
LONG_CARRY = "a carried line that runs well past the preview width " * 5


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def _scan(directory, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), str(directory), *extra],
                          capture_output=True, text=True, timeout=30)


def _line(out, needle):
    return next(line for line in out.splitlines() if needle in line)


def test_lists_unsent_drafts_undecided_decisions_and_open_items(tmp_path):
    _write(tmp_path, "2026-09-02.md", PLAN.format(long_item="short item", long_carry="carried"))
    out = _scan(tmp_path, "--start", "2026-09-01", "--end", "2026-09-30").stdout
    assert "[DRAFT-UNSENT]" in _line(out, "Draft 1 — reply to the vendor")
    assert "Draft 2" not in out
    assert "[UNDECIDED]" in _line(out, "Pick the hosting plan")
    assert "Choose the release day" not in out
    assert "[OPEN-ITEM]" in _line(out, "Ship the parser fix")
    assert "Retire the old job" not in out and "Already finished" not in out
    assert "TOTALS: open-items=2  unsent-drafts=1  undecided=1  carryover-sections=1" in out


def test_truncated_previews_say_so_and_point_at_the_line(tmp_path):
    _write(tmp_path, "2026-09-02.md", PLAN.format(long_item=LONG_ITEM, long_carry=LONG_CARRY))
    out = _scan(tmp_path, "--start", "2026-09-02", "--end", "2026-09-02").stdout
    item = _line(out, "[OPEN-ITEM]    L7:")
    assert item.endswith(f"…[truncated: {len(LONG_ITEM.strip())} chars, open L7]")
    carry = _line(out, "a carried line")
    assert carry.endswith(f"…[truncated: {len('- ' + LONG_CARRY.strip())} chars, open L32]")
    assert _line(out, "short carried item").endswith("| - short carried item")  # fits: whole, unmarked


def test_window_and_bad_directory(tmp_path):
    _write(tmp_path, "2026-08-31.md", PLAN.format(long_item="x", long_carry="y"))
    out = _scan(tmp_path, "--start", "2026-09-01", "--end", "2026-09-30").stdout
    assert "files: 0" in out
    assert _scan(tmp_path / "missing", "--start", "2026-09-01", "--end", "2026-09-30").returncode == 2

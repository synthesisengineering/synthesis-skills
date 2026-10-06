"""R8: budgets that make machinery regrowth a failing build, and hook latency."""

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ceilings at the measured size once every verdict was applied and duplication removed (2026-10-06):
# set first at 5,000 and 20,000 before the code evaluation measured what carries real value.
# Raised to 5,170 and 20,320 for the approval-provenance layer that closed the M5 self-approval
# defect (2026-10-06), after removing every duplicate found; then by 20 and 17 lines for one-line
# flow collections in the YAML reader (the inbox rules use them), which let every skill drop PyYAML
# while the skills' own scripts shrank by as much as they grew. The plugin rose 10 more in 5.0.2: setup's
# recognition of unedited 4.x-installed organization skills, and release reporting what it matched,
# after pyflakes found nothing left to remove. 5.0.3 adds 41 to both for three things Rajiv asked for on
# 2026-10-06: the once-per-release upgrade note (25), calendar writes that email no one (9) and a repository
# naming itself (7). Code may not grow past these without removing as many lines elsewhere.
CORE_BUDGET = 5231
PLUGIN_BUDGET = 20388


def _lines(files):
    return sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)


def test_core_stays_within_its_budget():
    assert _lines((ROOT / "synthesis").glob("*.py")) <= CORE_BUDGET


def test_whole_plugin_stays_within_its_budget():
    code = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts and not p.name.startswith("test_")]
    assert _lines(code) <= PLUGIN_BUDGET


def test_bash_guard_hook_is_fast(tmp_path):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la && git status"}})
    env = {**os.environ, "SYNTHESIS_HOME": str(tmp_path)}
    times = []
    for _ in range(15):
        start = time.perf_counter()
        subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "pre-tool-use"],
                       input=payload, capture_output=True, text=True, env=env, check=True)
        times.append(time.perf_counter() - start)
    # 50 ms is the target on the principal's Mac; shared CI runners get headroom.
    assert statistics.median(times) < 0.15

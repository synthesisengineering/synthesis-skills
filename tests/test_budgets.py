"""R8: budgets that make machinery regrowth a failing build, and hook latency."""

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE_BUDGET = 5000
PLUGIN_BUDGET = 20000


def _lines(files):
    return sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)


def test_core_stays_within_its_budget():
    assert _lines((ROOT / "synthesis").glob("*.py")) <= CORE_BUDGET


@pytest.mark.skipif((ROOT / "skills" / "synthesis-autopilot" / "scripts").is_dir(),
                    reason="old machinery still present on this branch until migration (M3) finishes")
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

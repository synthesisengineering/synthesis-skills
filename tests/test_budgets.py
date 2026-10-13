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
# naming itself (7). 5.0.4 adds 18 to both so a session still on an older plugin can no longer switch the
# stable runtime back (a defect found live that day), after the three version parsers became one.
# 5.0.5 adds 10 to the core (the doctor reaps each harness CLI's whole process group) and 55 to the plugin:
# those 10, a bytecode guard ahead of the first local import in 35 scripts (38; Muse refuses a bundle with
# stray __pycache__), the repo guard's atomic report (2) and autopilot's JSON status (5).
# 5.0.7 adds 50 to both for fixes other sessions reported from 2026-10-07 to 10-13: board delivery that marks
# read only what it shows and can re-show a cut message (22), the upgrade note for sessions recorded before
# versions were kept (11), a write guard that tells a read from a write (9), HTML link targets counting as
# branding in the send guard (4) and a doctor that says "cannot tell" for a CLI or trust state it cannot read
# (4). A scan for unreferenced definitions and repeated blocks across the core found nothing to remove.
# 5.0.8 adds 146 to the plugin: the decision packet's reading path Rajiv asked for on 2026-10-08 (153: changes
# against a reviewed baseline, HTML messages as their words, material shown once, a handled list, reading-burden
# checks), the message reader's three gaps (56) and the meeting window's in-progress hold (5, after two shared
# helpers recovered 5), less the reader's unused sandbox runner (73), the meeting config's April migration
# hint (8) and two unreferenced definitions (4). A plugin-wide scan found nothing else unreferenced. Then 18 more
# so saved meeting transcripts never keep a Docs image's access key (reported the same day).
# 5.0.9 adds 320 to both for Rajiv's 2026-10-13 rulings: approval on every channel, recognized by what a call does,
# and send windows (synthesis/sends.py 220, guard wiring 61, `synthesis sends` 29, the window note in the hooks 8),
# and the Docs image key as a built-in credential (2). The preferred-names check came in at zero net.
# 5.0.10 adds 3 so a read-only script may import the window and approval code; writing calls stay refused.
# 5.0.11 adds 44 so `synthesis sends open` itself refuses an agent without the principal's granted code (a
# global option before `sends` slipped past the guard alone), whatever order its options take; help needs no code.
# 5.0.12 adds 40 for four defects a project session reported: the register scan reads the message (and $(cat
# file) bodies), not file names; approvals bind where a command runs; untaken codes are named; parsed redirects.
# Code may not grow past these without removing as many lines elsewhere.
CORE_BUDGET = 5716
PLUGIN_BUDGET = 21064


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

"""The waiting skill's usage lines show each option as the command applies it when the option is left out.

Review round 1 of 5.8.0 (2026-11-12): the line for `synthesis wait note` showed `[--for 2h]` while a note with no
`--for` is held 30 minutes, as every other form's line says.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "synthesis-waiting" / "SKILL.md"


def _held(*bound):
    """How long a note is held, in the command's own words."""
    done = subprocess.run([sys.executable, "-m", "synthesis", "wait", "note", "the build", "--by", "a background task", *bound],
                          capture_output=True, text=True, cwd=ROOT, timeout=30, env={**os.environ, "SYNTHESIS_SESSION": "S-usage"})
    assert done.returncode == 0, done.stderr
    return re.search(r", for (.+), woken by ", done.stdout).group(1)


def test_every_usage_form_shows_the_bound_a_wait_takes_when_none_is_given():
    usage = re.search(r"## The commands\n+```bash\n(.*?)```", SKILL.read_text(encoding="utf-8"), re.S).group(1)
    shown = dict(re.findall(r"^synthesis wait (\w+)\b.*\[--for (\S+)\]", usage, re.M))
    assert set(shown) == {"message", "file", "run", "note"}
    assert {form: _held("--for", bound) for form, bound in shown.items()} == dict.fromkeys(shown, _held())

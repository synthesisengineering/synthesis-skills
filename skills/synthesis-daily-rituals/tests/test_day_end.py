"""The day-end launcher and the 16:55 nudge, as `synthesis install` lays them out.

The v5 install copies `day-end` and `day-end-nudge.sh` into `<synthesis home>/bin/`, beside
`current/synthesis/rituals.py`. The nudge fires unless every workspace expected to
close today has closed (2026-09-02: the first close used to silence it for every
other workspace), fires when its state tool is missing or fails, shows only fixed
generic text, and never writes state.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PLUGIN = Path(__file__).resolve().parents[3]
BANNER = '-e display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
TODAY = date.today().isoformat()


def runtime(tmp_path: Path, with_rituals: bool = True) -> Path:
    home = tmp_path / "v5"
    (home / "bin").mkdir(parents=True)
    for name in ("day-end", "day-end-nudge.sh"):
        shutil.copy2(SCRIPTS / name, home / "bin" / name)
    if with_rituals:
        shutil.copytree(PLUGIN / "synthesis", home / "current" / "synthesis",
                        ignore=shutil.ignore_patterns("__pycache__"))
    return home


def state(home: Path, records: list[dict], config: dict | None = None) -> None:
    (home / "rituals").mkdir(parents=True, exist_ok=True)
    (home / "rituals" / "history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    if config is not None:
        (home / "rituals" / "config.json").write_text(json.dumps(config), encoding="utf-8")


def snapshot(root: Path) -> dict:
    return {str(p): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def nudge(home: Path, tmp_path: Path) -> list[str]:
    record = tmp_path / "notifications"
    record.write_text("", encoding="utf-8")
    # Source the unchanged script in a shell whose absolute notification command is a
    # function; prove the interception before any nudge code runs.
    wrapper = """
set -euo pipefail
function /usr/bin/osascript { printf '%s\\n' "$*" >> "$NUDGE_RECORD"; }
[[ "$(type -t /usr/bin/osascript)" == function ]] || exit 96
source "$1"
"""
    env = {**os.environ, "SYNTHESIS_HOME": str(home), "NUDGE_RECORD": str(record), "HOME": str(tmp_path)}
    env.pop("RITUAL_STATE_DIR", None)
    done = subprocess.run(["bash", "--noprofile", "--norc", "-c", wrapper, "nudge-test", str(home / "bin" / "day-end-nudge.sh")],
                          env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return record.read_text(encoding="utf-8").splitlines()


EVERY_DAY = {"defaults": {"weekdays": [0, 1, 2, 3, 4, 5, 6]}, "workspaces": {"alpha": {"streak": "expected-days"},
                                                                            "beta": {"streak": "expected-days"}}}


def test_the_nudge_stays_quiet_only_when_every_expected_workspace_has_closed(tmp_path: Path) -> None:
    home = runtime(tmp_path)
    closed = [{"date": TODAY, "direction": d, "workspace": w, "ts": "x"}
              for w in ("alpha", "beta") for d in ("day-start", "day-end")]
    state(home, closed, EVERY_DAY)
    before = snapshot(home)
    assert nudge(home, tmp_path) == []
    assert snapshot(home) == before, "the nudge must never write state"


def test_one_closed_workspace_does_not_silence_the_nudge_for_another(tmp_path: Path) -> None:
    home = runtime(tmp_path)
    state(home, [{"date": TODAY, "direction": "day-end", "workspace": "alpha", "ts": "x"}], EVERY_DAY)
    assert nudge(home, tmp_path) == [BANNER]


def test_a_workspace_started_today_and_not_closed_fires_the_nudge(tmp_path: Path) -> None:
    home = runtime(tmp_path)
    state(home, [{"date": TODAY, "direction": "day-start", "workspace": "gamma", "ts": "x"}])
    assert nudge(home, tmp_path) == [BANNER]


@pytest.mark.parametrize("break_it", ["missing-tool", "unreadable-config"])
def test_the_nudge_fires_when_its_state_tool_cannot_answer(tmp_path: Path, break_it: str) -> None:
    home = runtime(tmp_path, with_rituals=break_it != "missing-tool")
    state(home, [], EVERY_DAY)
    if break_it == "unreadable-config":
        (home / "rituals" / "config.json").write_text("not JSON\n", encoding="utf-8")
    assert nudge(home, tmp_path) == [BANNER]


def test_the_banner_text_is_fixed_and_names_nothing() -> None:
    text = (SCRIPTS / "day-end-nudge.sh").read_text(encoding="utf-8")
    assert text.count("display notification") == 1
    assert "$" not in text.split("display notification")[1].splitlines()[0]


# --- the launcher ------------------------------------------------------------------------


def fake_agent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nprintf "%s|%s" "$0" "$1"\n', encoding="utf-8")
    path.chmod(0o755)
    return path


def launch(home: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(home / "bin" / "day-end"), *args], capture_output=True, text=True,
                          env=env, check=False)


def test_launcher_auto_prefers_codex_and_honors_a_persisted_choice(tmp_path: Path) -> None:
    home = runtime(tmp_path, with_rituals=False)
    bin_dir = tmp_path / "fake-bin"
    codex, claude = fake_agent(bin_dir / "codex"), fake_agent(bin_dir / "claude")
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)}

    auto = launch(home, env, "-q")
    assert auto.returncode == 0, auto.stderr
    assert auto.stdout.startswith(f"{codex}|") and "Quick Close" in auto.stdout

    (home / "agent-cli").write_text("claude\n", encoding="utf-8")
    chosen = launch(home, env, "-f")
    assert chosen.stdout.startswith(f"{claude}|") and "Mode: full." in chosen.stdout


def test_launcher_accepts_an_explicit_command_path(tmp_path: Path) -> None:
    home = runtime(tmp_path, with_rituals=False)
    agent = fake_agent(tmp_path / "custom-agent")
    done = launch(home, {**os.environ, "DAY_END_AGENT_CMD": str(agent)}, "-o")
    assert done.returncode == 0, done.stderr
    assert "Mode: observer." in done.stdout and "Day-End ritual" in done.stdout


def test_launcher_finds_a_named_agent_in_known_locations(tmp_path: Path) -> None:
    home = runtime(tmp_path, with_rituals=False)
    fake_agent(tmp_path / ".local" / "bin" / "codex")
    done = launch(home, {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "DAY_END_AGENT_CMD": "codex"})
    assert done.returncode == 0, done.stderr
    assert "one-letter mode question" in done.stdout


def test_launcher_fails_closed_when_no_agent_exists(tmp_path: Path) -> None:
    home = runtime(tmp_path, with_rituals=False)
    done = launch(home, {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "empty"), "DAY_END_AGENT_CMD": "codex",
                         "SYNTHESIS_CODEX_BIN": ""})
    assert done.returncode == 127 and "unavailable" in done.stderr


def test_launcher_honors_a_binary_override(tmp_path: Path) -> None:
    home = runtime(tmp_path, with_rituals=False)
    agent = fake_agent(tmp_path / "custom" / "codex")
    done = launch(home, {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "DAY_END_AGENT_CMD": "codex",
                         "SYNTHESIS_CODEX_BIN": str(agent)}, "-q")
    assert done.returncode == 0 and done.stdout.startswith(f"{agent}|")


def test_launcher_refuses_an_unknown_mode(tmp_path: Path) -> None:
    home = runtime(tmp_path, with_rituals=False)
    agent = fake_agent(tmp_path / "custom-agent")
    done = launch(home, {**os.environ, "DAY_END_AGENT_CMD": str(agent)}, "-x")
    assert done.returncode == 2 and "usage" in done.stderr

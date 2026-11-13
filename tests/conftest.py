import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own synthesis state and no inherited harness identity."""
    home = tmp_path / "synthesis-home"
    monkeypatch.setenv("SYNTHESIS_HOME", str(home))
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "MUSE_PLUGIN_ROOT"):
        monkeypatch.delenv(key, raising=False)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))  # no machine-wide hooks or identity
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, folder in (("CLAUDE_CONFIG_DIR", "claude"), ("CODEX_HOME", "codex"), ("XDG_DATA_HOME", "xdg"),
                        ("SYNTHESIS_CLAUDE_DESKTOP_DIR", "claude-desktop")):
        monkeypatch.setenv(key, str(tmp_path / "harness" / folder))  # never this Mac's own session transcripts
    return home


PACE_WORK_MS = 7.0  # what `_work` takes on the principal's Mac under Python 3.12 (9.3 under Apple's 3.9), 2026-11-12


def _work() -> None:
    """A fixed piece of ordinary work for `pace`: text built, written as JSON and read back, searched and split."""
    lines = [f"line {i} of ordinary tool output" for i in range(20_000)]
    json.loads(json.dumps(lines))
    re.findall(r"\bline (\d+) of\b", "\n".join(lines))
    sum(len(line.split()) for line in lines)


@pytest.fixture
def pace():
    """How many times slower than the principal's Mac this machine is running Python at this moment; never under 1.

    A test that holds a piece of work to a time writes the bound for that Mac and multiplies it by this:
    `assert took < 0.2 * pace`. There the bound is as written. On a shared runner, several times slower and no two
    alike, it stretches by what the same fixed work takes on that runner now, so the test still fails for work that
    got slower and no longer for a machine that is."""
    def once() -> float:
        began = time.perf_counter()
        _work()
        return time.perf_counter() - began
    return max(1.0, min(once() for _ in range(3)) * 1000 / PACE_WORK_MS)


# Runs a call as the interpreter would and writes down, for each import statement the call's own code runs (its
# script or its `-c` program, and the synthesis modules), which module asked for what. At a module's top or inside a
# function is the same to it: what runs is recorded, and what never runs is not.
_ASKED = r'''
import builtins, json, runpy, sys
asked, real, call = {}, builtins.__import__, sys.argv[1:]
def traced(name, globals=None, locals=None, fromlist=(), level=0):
    who = (globals or {}).get("__name__") or ""
    if not level and (who == "__main__" or who.split(".")[0] == "synthesis"):
        asked.setdefault(name, who)
    return real(name, globals, locals, fromlist, level)
builtins.__import__ = traced
try:
    if call[0] == "-c":
        sys.argv = ["-c"] + call[2:]
        exec(compile(call[1], "<the caller>", "exec"), {"__name__": "__main__"})
    else:
        sys.argv = call
        runpy.run_path(call[0], run_name="__main__")
except SystemExit:
    pass
finally:
    builtins.__import__ = real
    print("\nasked " + json.dumps(asked), file=sys.stderr)
'''


@pytest.fixture
def compiled_runtime(isolated_home):
    """The runtime as the installer leaves it in a home: copied, and compiled for the interpreter that installed it."""
    from synthesis import install
    install.install(Path(__file__).resolve().parents[1])
    return isolated_home / "current"


@pytest.fixture
def hook_budget(compiled_runtime):
    """Holds one hook call, as a fresh interpreter runs it from the installed runtime, to the hook budget on
    whatever machine runs the test. Returns what the call printed the first time it ran.

    The budget is 50 ms on the principal's Mac, where the doctor's self-test holds it. A shared runner is several
    times slower and no two are alike (2026-11-12: a fixed 150 ms failed on a runner whose fastest run took 156 ms).
    A bare interpreter start is no steadier a unit: the guard hook took 2.2 times one on one machine and 7.1 times
    one on another, where a process starts in 3 ms. So the unit is what a fresh interpreter takes to load the
    standard-library modules the call needs, timed beside the call, round by round, so both meet the same machine at
    the same moment; the fastest round is each one's own cost. The call may take twice that: its own code may cost as
    much again as the library it stands on. Measured on ten interpreters and machines (Python 3.9 to 3.15, macOS and
    Linux, one of them emulated), the guard hook took 1.1 to 1.5 times. With its runtime not compiled it took 2.7
    times on this Mac and under 2 where starting a process costs more than compiling does, so a call that loads the
    runtime is first held to a runtime that is compiled: the installer's own check, asked directly.

    Every run here is told to write no bytecode, as a session's hooks are: a process that may write it compiles the
    runtime at its first call, and the budget would then time compiled code whatever the installer had left. One
    start before them, free to write, lets an interpreter that keeps compiled code in a folder of its own keep the
    standard library's there.

    One block of rounds does not always hold a quiet run of the call: other work on the machine stretches the
    longer run more (2026-11-13: on a runner whose whole job ran at half its usual speed, the guard hook's fastest
    of fifteen read 92 ms beside 45 for its modules, with nothing in the hook changed). So a call that is over is
    timed for a second block and a third, every round counted, and fails only if its fastest run of them all is over.

    The test names the modules, and they are exactly what the call's own code imports while it runs, at a module's
    top or inside a function: one more is paid on every call, so it is taken out of the call's path or named in the
    test, where a reviewer sees it. A module named that nothing of the call's own imports is refused too, since the
    allowance is measured from what is named."""
    def hold(call: list, needs: tuple, rounds: int = 15, **run) -> str:
        quiet = {**run, "env": {**run.get("env", os.environ), "PYTHONDONTWRITEBYTECODE": "1"}}
        first = subprocess.run([sys.executable, "-S", "-c", _ASKED, *call], capture_output=True, text=True, **quiet)
        asked = json.loads(first.stderr.rsplit("\nasked ", 1)[1])
        script = "the caller" if call[0] == "-c" else Path(call[0]).name
        unnamed = sorted(name for name in asked if name.split(".")[0] != "synthesis" and name not in needs)
        assert not unnamed, ("; ".join(f"{asked[name].replace('__main__', script)} imports {name} while the call runs"
                                       for name in unnamed)
                             + ": every call pays for it, so take it out of the call's path or name it in the test's needs")
        idle = sorted(set(needs) - set(asked))
        assert not idle, f"{', '.join(idle)} is named as a need and nothing of the call's own imports it: take it out"
        if "synthesis" in asked:
            from synthesis import install
            assert install._compiled(compiled_runtime / "synthesis"), (
                "the runtime is not compiled for this interpreter, so every call compiles it from its source: the "
                "installer's compile step, or what became of what it wrote, is at fault")

        def once(args: list, **how) -> float:
            began = time.perf_counter()
            subprocess.run([sys.executable, "-S", *args], capture_output=True, text=True, check=True, **how)
            return time.perf_counter() - began
        floor = ["-c", "import " + ", ".join(needs)]
        once(floor, env={key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"})
        took = []
        for _ in range(3):  # a call over its allowance is timed for two more blocks of rounds before it is called slow
            took += [(once(floor, env=quiet["env"]), once(call, **quiet)) for _ in range(rounds)]
            least, cost = (min(column) * 1000 for column in zip(*took))
            if cost < 2 * least:
                break
        assert cost < 2 * least, f"the call took {cost:.0f} ms; its standard-library modules alone load in {least:.0f} ms here"
        return first.stdout
    return hold


@pytest.fixture
def write_config(isolated_home):
    def write(data: dict):
        isolated_home.mkdir(parents=True, exist_ok=True)
        (isolated_home / "config.json").write_text(json.dumps(data), encoding="utf-8")
    return write


@pytest.fixture
def principal(tmp_path, monkeypatch):
    """The principal's side of an approval: they type "approve <code>" in this session, which the harness
    records in its transcript (Claude Code's format here), and the prompt hook grants it. The session is
    found the way a script run from a harness shell finds it: by its id, under the harness's own folder."""
    record = tmp_path / "claude-config" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-principal")

    def approve(reason: str, prompt: str = "approve {code}", grant: bool = True):
        from synthesis import approvals
        code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": "S-principal",
                                     "message": {"role": "user", "content": prompt.format(code=code)}}) + "\n")
        return approvals.grant_from_prompt(prompt.format(code=code)) if grant else code

    approve.transcript = record
    return approve

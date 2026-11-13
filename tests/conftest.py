import ast
import json
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
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))  # no machine-wide hooks or identity
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key, folder in (("CLAUDE_CONFIG_DIR", "claude"), ("CODEX_HOME", "codex"), ("XDG_DATA_HOME", "xdg")):
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


def _imported(call: list, **run) -> set:
    """Every module a fresh interpreter imports while it runs `call`, read from the interpreter's own import log."""
    log = subprocess.run([sys.executable, "-S", "-X", "importtime", *call], capture_output=True, text=True, **run).stderr
    return {line.rsplit("|", 1)[1].strip() for line in log.splitlines() if line.startswith("import time:")}


def _asks(source: str) -> set:
    """What a module imports as it loads: every import statement outside a function or a class."""
    found, pending = set(), list(ast.parse(source).body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            found.add(node.module)
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            pending.extend(ast.iter_child_nodes(node))
    return found


@pytest.fixture
def compiled_runtime(isolated_home):
    """The runtime as the installer leaves it in a home: copied, and compiled for the interpreter that installed it."""
    from synthesis import install
    install.install(Path(__file__).resolve().parents[1])
    return isolated_home / "current"


@pytest.fixture
def hook_budget(compiled_runtime):
    """Holds one hook call, as a fresh interpreter runs it from the installed runtime, to the hook budget on
    whatever machine runs the test.

    The budget is 50 ms on the principal's Mac, where the doctor's self-test holds it. A shared runner is several
    times slower and no two are alike (2026-11-12: a fixed 150 ms failed on a runner whose fastest run took 156 ms).
    A bare interpreter start is no steadier a unit: the guard hook took 2.2 times one on one machine and 7.1 times
    one on another, where a process starts in 3 ms. So the unit is what a fresh interpreter takes to load the
    standard-library modules the call needs, timed beside the call, round by round, so both meet the same machine at
    the same moment; the fastest of fifteen rounds is each one's own cost. The call may take twice that: its own
    code may cost as much again as the library it stands on. Measured on ten interpreters and machines (Python 3.9
    to 3.15, macOS and Linux, one of them emulated), the guard hook took 1.1 to 1.5 times.

    The test names those modules, and they are exactly what the call's own modules import as they load, read from
    their source: one more is paid on every call, so it is imported where it is used or named in the test, where a
    reviewer sees it. A module named that none of them imports is refused too, since the allowance is measured from
    what is named."""
    def hold(call: list, needs: tuple, **run) -> None:
        def own(name: str) -> bool:
            return name.split(".")[0] == "synthesis"
        sources = {"the caller": call[1]} if call[0] == "-c" else {Path(call[0]).name: Path(call[0]).read_text(encoding="utf-8")}
        for name in sorted(filter(own, _imported(call, **run))):
            file = compiled_runtime.joinpath(*name.split("."))
            sources[name] = (file / "__init__.py" if file.is_dir() else file.with_suffix(".py")).read_text(encoding="utf-8")
        asked = {}
        for where, source in sources.items():
            for name in _asks(source):
                asked.setdefault(name, where)
        unnamed = sorted(name for name in asked if not own(name) and name not in needs)
        assert not unnamed, ("; ".join(f"{asked[name]} imports {name} as it loads" for name in unnamed)
                             + ": every call pays for it, so import it where it is used or name it in the test's needs")
        idle = sorted(set(needs) - set(asked))
        assert not idle, f"{', '.join(idle)} is named as a need and nothing in this call imports it as it loads: take it out"

        def once(args: list, **how) -> float:
            began = time.perf_counter()
            subprocess.run([sys.executable, "-S", *args], capture_output=True, text=True, check=True, **how)
            return time.perf_counter() - began
        floor = ["-c", "import " + ", ".join(needs)]
        rounds = [(once(floor), once(call, **run)) for _ in range(15)]
        least, cost = (min(column) * 1000 for column in zip(*rounds))
        assert cost < 2 * least, f"the call took {cost:.0f} ms; its standard-library modules alone load in {least:.0f} ms here"
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

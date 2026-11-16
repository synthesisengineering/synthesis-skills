"""5.23.1: a release runs from the protected runtime with no code, and nothing else does (the principal, 2026-11-15).

Since 5.22.1 the guard holds a program that names synthesis's writers or runs from the protected runtime until the
principal types a code, so every release waited for one: from a checkout the release tool names `board.claim`, and the
runtime carried no release tool at all. The principal's ruling: run releases from the protected installed tool,
without a code. The runtime now carries the release tool and what it imports, so no agent can change the copy that
installs the guard, and exactly that copy passes: the running release's release.py, by its path in the runtime, run by
python3 or the system Python, with only the options it documents, on the canonical checkout. Every other way of
running it, a copy of it or the scripts it carries waits as before. Each case is judged by the guard as the hook runs
it: from the installed runtime, in a home of the test's own.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import guards, install, paths

ROOT = Path(__file__).resolve().parents[1]
TOOL = "skills/synthesis-skills-manager/scripts/release.py"
KIT = ("skills/synthesis-skills-manager/scripts", "skills/synthesis-onboarding/scripts")
CANONICAL = "https://github.com/synthesisengineering/synthesis-skills.git"
HELD = "approve followed by the code"

# The guard as the hook runs it: a fresh interpreter, without site, from the installed runtime (bin/synthesis-hook).
JUDGE = r"""
import json, sys
sys.path[0] = sys.argv[1]
from synthesis import guards
for item in json.loads(sys.argv[2]):
    tool, tool_input, cwd = item if len(item) == 3 else ("Bash", {"command": item[0]}, item[1])
    print(json.dumps(guards.check(tool, tool_input, {}, cwd=cwd, session={"session_id": "S-principal"})))
"""


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own with the runtime installed in it from this tree, and a checkout of the synthesis-skills
    repository as a release finds it: origin on GitHub, on main."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("RITUAL_STATE_DIR", tmp_path / "rituals"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    home.mkdir()
    install.install(ROOT)
    canon = home / "work" / "synthesis-skills"
    canon.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(canon)], check=True)
    for rel in [TOOL, "skills/synthesis-skills-manager/scripts/build_collections.py",
                "skills/synthesis-skills-manager/scripts/build_directory_package.py",
                "skills/synthesis-onboarding/scripts/setup.py", "skills/synthesis-onboarding/scripts/workspace.py"]:
        (canon / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, canon / rel)  # the checkout's copy: the same bytes as the runtime's
    _git(canon, "add", ".")
    _git(canon, "commit", "-qm", "init")
    _git(canon, "branch", "-M", "main")
    _git(canon, "remote", "add", "origin", CANONICAL)
    work = tmp_path / "work"
    work.mkdir()

    def judge(lines):
        pairs = [list(line) if isinstance(line, (list, tuple)) else [line, str(work)] for line in lines]
        done = subprocess.run([sys.executable, "-S", "-c", JUDGE, str(paths.home() / "current"), json.dumps(pairs)],
                              capture_output=True, text=True, timeout=600, cwd=str(work))
        assert done.returncode == 0, done.stderr[-3000:]
        return [json.loads(line) for line in done.stdout.splitlines()]

    release = Path(os.path.realpath(paths.home() / "current"))
    return {"home": home, "canon": canon, "work": work, "judge": judge, "release": release,
            "tool": paths.home() / "current" / TOOL, "launcher": paths.home() / "bin" / "synthesis-release", "q": shlex.quote}


def _variant(world, name, *steps):
    """A copy of the canonical checkout changed by each git step, or by a callable."""
    copy = world["work"] / name
    shutil.copytree(world["canon"], copy, symlinks=True)
    for step in steps:
        step(copy) if callable(step) else _git(copy, *step)
    return copy


# --- the one way through -----------------------------------------------------------------------------------------------

def test_the_release_launcher_on_the_canonical_checkout_needs_no_code(world):
    """Round 1 of the review (A4, P1, P3): the one way through is the launcher install writes in the protected bin/,
    which runs the release tool with the interpreter pinned at install, isolated. Paths are absolute (A5)."""
    canon, launcher = world["canon"], world["launcher"]
    lines = [
        f"{launcher} --repo-root {canon} --dry-run",
        f"~/.synthesis/v5/bin/synthesis-release --repo-root ~/work/synthesis-skills",
        f"{launcher} --repo-root={canon} --clients claude,codex --session S-principal",
        f"{launcher}   --dry-run   --repo-root {canon}  --clients=muse",
        f"{launcher} --install-only --tag v5.23.1 --clients muse",
        [f"~/.synthesis/v5/bin/synthesis-release --install-only --tag=v5.23.1 --dry-run", str(world["work"])],
    ]
    assert world["judge"](lines) == [None] * len(lines)


def test_the_runtime_carries_the_release_tool_and_what_it_imports(world):
    for folder in KIT:
        for source in (ROOT / folder).glob("*.py"):
            carried = world["release"] / folder / source.name
            assert carried.read_bytes() == source.read_bytes(), carried


# --- everything else waits, as it did --------------------------------------------------------------------------------

def _elsewhere(world):
    """A copy of the runtime's release tool, its kit and the core, outside the runtime: the same bytes."""
    copy = world["work"] / "elsewhere"
    for folder in (*KIT, "synthesis"):
        shutil.copytree(world["release"] / folder, copy / folder, ignore=shutil.ignore_patterns("__pycache__"))
    return copy


WAITS = {
    "the checkout's copy": "python3 {canon}/{tool_rel} --repo-root {canon} --dry-run",
    "a copy elsewhere": "python3 {elsewhere}/{tool_rel} --repo-root {canon} --dry-run",
    "a script beside it": "python3 {release}/skills/synthesis-skills-manager/scripts/build_collections.py --repo-root {canon}",
    "another script the runtime carries for it": "python3 {release}/skills/synthesis-onboarding/scripts/setup.py --dry-run",
    "an option it does not document": "python3 {tool} --repo-root {canon} --dry-run --verbose",
    "an option abbreviated": "python3 {tool} --repo {canon} --dry-run",
    "an option given twice": "python3 {tool} --repo-root {canon} --repo-root {canon} --dry-run",
    "no repository named": "python3 {tool} --dry-run",
    "a word it takes no option for": "python3 {tool} {canon} --dry-run",
    "a client it does not know": "python3 {tool} --repo-root {canon} --clients claude,other",
    "a session that is no session id": "python3 {tool} --repo-root {canon} --session=a/b",
    "a home the shell would not expand": "python3 {tool} --repo-root=~/work/synthesis-skills --dry-run",
    "an inline program importing it": "python3 -c {importing}",
    "an inline program running its file": "python3 -c {running}",
    "a program starting it": "python3 -c {starting}",
    "a heredoc importing it": "python3 - <<'EOF'\n{importing_raw}\nEOF",
    "env": "env python3 {tool} --repo-root {canon} --dry-run",
    "nohup": "nohup python3 {tool} --repo-root {canon} --dry-run",
    "a shell": "sh -c {shelled}",
    "a shell script": "sh {work}/release.sh",
    "an interpreter option": "python3 -I {tool} --repo-root {canon} --dry-run",
    "another interpreter": "/opt/homebrew/bin/python3 {tool} --repo-root {canon} --dry-run",
    "a variable on the line": "PYTHONPATH={work} python3 {tool} --repo-root {canon} --dry-run",
    "after a cd": "cd {canon} && python3 {tool} --repo-root . --dry-run",
    "into a pipe": "python3 {tool} --repo-root {canon} --dry-run | tail -5",
    "into a file": "python3 {tool} --repo-root {canon} --dry-run > {work}/out.txt",
    "a quoted word": "python3 '{tool}' --repo-root {canon} --dry-run",
    "a second command": "python3 {tool} --repo-root {canon} --dry-run; true",
    "the tool by its own path, not the launcher": "python3 {tool} --repo-root {canon} --dry-run",
    "the system Python on the tool": "/usr/bin/python3 {release}/{tool_rel} --repo-root {canon}",
    "the launcher with an option it does not document": "{launcher} --repo-root {canon} --verbose",
    "the launcher with an option abbreviated": "{launcher} --repo {canon}",
    "the launcher with an option twice": "{launcher} --repo-root {canon} --repo-root {canon}",
    "the launcher with no repository": "{launcher} --dry-run",
    "the launcher with a relative repository": "{launcher} --repo-root work/synthesis-skills",
    "the launcher with another session's id": "{launcher} --repo-root {canon} --session S-other",
    "an install with no tag": "{launcher} --install-only",
    "a tag on a release": "{launcher} --repo-root {canon} --tag v5.23.1",
    "an install with a repository": "{launcher} --install-only --tag v5.23.1 --repo-root {canon}",
    "a tag that is no version": "{launcher} --install-only --tag main",
    "a copy of the launcher": "{work}/synthesis-release --repo-root {canon}",
    "the launcher through env": "env {launcher} --repo-root {canon}",
    "the launcher through a shell": "sh {launcher} --repo-root {canon}",
    "the launcher quoted": "'{launcher}' --repo-root {canon}",
    "the launcher with a relative path": "{relative_launcher} --repo-root {canon}",
}


def test_every_other_way_of_running_it_still_waits_for_the_code(world):
    canon, tool, release, q = world["canon"], world["tool"], world["release"], world["q"]
    importing = (f"import sys; sys.path.insert(0, {str(tool.parent)!r}); import release; "
                 f"release.main(['--repo-root', {str(canon)!r}, '--dry-run'])")
    running = (f"import runpy, sys; sys.argv = ['release.py', '--repo-root', {str(canon)!r}, '--dry-run']; "
               f"runpy.run_path({str(tool)!r}, run_name='__main__')")
    starting = f"import subprocess; subprocess.run(['python3', {str(tool)!r}, '--repo-root', {str(canon)!r}, '--dry-run'])"
    (world["work"] / "release.sh").write_text(f"python3 {tool} --repo-root {canon} --dry-run\n", encoding="utf-8")
    shutil.copy2(world["launcher"], world["work"] / "synthesis-release")
    values = {"canon": canon, "tool": tool, "tool_rel": TOOL, "release": release, "work": world["work"], "launcher": world["launcher"],
              "relative_launcher": os.path.relpath(world["launcher"], world["work"]),
              "elsewhere": _elsewhere(world), "importing": q(importing), "running": q(running), "starting": q(starting),
              "importing_raw": importing.replace("; ", "\n"), "shelled": q(f"python3 {tool} --repo-root {canon} --dry-run")}
    lines = [template.format(**values) for template in WAITS.values()]
    passed = [(name, said) for name, said in zip(WAITS, world["judge"](lines)) if not (said and (HELD in said or said.startswith("Refused")))]
    assert not passed, "; ".join(f"{name}: {said}" for name, said in passed)


NOT_CANONICAL = {
    "a fork": [("remote", "set-url", "origin", "https://github.com/someone/synthesis-skills.git")],
    "another repository": [("remote", "set-url", "origin", "https://github.com/synthesisengineering/other.git")],
    "no origin": [("remote", "rename", "origin", "github")],
    "a push address elsewhere": [("config", "remote.origin.pushurl", "/tmp/elsewhere.git")],
    "a second remote": [("remote", "add", "mirror", "https://example.com/synthesis-skills.git")],
    "its config sending git elsewhere": [("config", "url./tmp/evil.git.insteadOf", CANONICAL)],
    "a branch that is not main": [("checkout", "-qb", "feature")],
    "a detached HEAD": [("checkout", "-q", "--detach")],
    "its config running a program": [("config", "core.fsmonitor", "/tmp/monitor.sh")],
    "hooks of its own": [("config", "core.hooksPath", "/tmp/hooks")],
    "a credential helper of its own": [("config", "credential.helper", "/tmp/helper.sh")],
}


def test_a_checkout_that_is_not_the_canonical_one_waits(world):
    tool, q = world["launcher"], world["q"]
    roots = {name: _variant(world, name.replace(" ", "-"), *steps) for name, steps in NOT_CANONICAL.items()}
    (world["canon"] / "inner").mkdir()
    roots["a folder inside the checkout"] = world["canon"] / "inner"
    (world["work"] / "plain").mkdir()
    roots["no checkout at all"] = world["work"] / "plain"
    lines = [f"{tool} --repo-root {q(str(root))} --dry-run" for root in roots.values()]
    assert [(name, said) for name, said in zip(roots, world["judge"](lines)) if not (said and HELD in said)] == []


def test_the_guard_lets_the_tool_through_only_when_it_runs_from_that_runtime(world):
    """In this process the guard runs from this tree, not from the protected runtime, so no release tool is its own."""
    said = guards.check("Bash", {"command": f"{world['launcher']} --repo-root {world['canon']} --dry-run"}, {},
                        cwd=str(world["work"]), session={"session_id": "S-principal"})
    assert said and HELD in said, said


def test_the_release_kit_is_never_trusted_as_one_of_the_plugins_own_scripts(world):
    """The guard trusts the plugin's own scripts as they shipped; the release tool and what it imports are carried for
    the release alone and are judged like any other script, even in the guard's own tree."""
    for rel in [TOOL, "skills/synthesis-onboarding/scripts/setup.py", "skills/synthesis-skills-manager/scripts/build_collections.py"]:
        assert not guards._shipped(str(ROOT / rel)) and not guards._shipped(str(world["release"] / rel)), rel
    assert guards._shipped(str(world["release"] / "skills" / "synthesis-daily-rituals" / "scripts" / "ritual_state.py"))
    said = guards.check("Bash", {"command": f"python3 {ROOT / 'skills/synthesis-onboarding/scripts/setup.py'} --dry-run"}, {},
                        cwd=str(world["work"]), session={"session_id": "S-principal"})
    assert said and HELD in said, said


def test_a_pending_approval_code_on_the_line_is_never_let_through(world):
    """The exact run passes only without a pending code in its words: a line carrying one is judged, and refused."""
    import re
    held = world["judge"]([f"python3 {world['canon']}/{TOOL} --repo-root {world['canon']} --dry-run"])[0]
    code = re.search(r"\bcode ([a-z0-9]{6})\b", held).group(1)
    said = world["judge"]([f"{world['launcher']} --repo-root {world['canon']} --dry-run --session {code}"])[0]
    assert said and said.startswith("Refused") and "pending approval code" in said, said


# --- review round 1 of 5.23.1: A5, A6, A7, A8 ----------------------------------------------------------------------------

def test_a7_the_launcher_line_from_codexs_shell_tool_passes_as_it_does_from_the_other_shells(world, monkeypatch, tmp_path):
    mine = tmp_path / "mine"  # the harness's PATH as on the principal's Mac and CI's runners: folders this user writes
    mine.mkdir()  # first, and the first shell of each name the system's own (combined review round 1, C2)
    monkeypatch.setenv("PATH", f"{mine}:/usr/bin:/bin:/usr/sbin:/sbin")
    line = f"{world['launcher']} --repo-root {world['canon']} --dry-run"
    calls = [("shell", {"command": [shell, flag, line], "workdir": str(world["work"])}, str(world["work"]))
             for shell, flag in (("bash", "-lc"), ("zsh", "-c"), ("/bin/sh", "-c"))]
    calls += [("exec_command", {"cmd": line, "workdir": str(world["work"])}, str(world["work"])), ("bash", {"command": line},
                                                                                                str(world["work"]))]
    assert world["judge"](calls) == [None] * len(calls)
    waits = [("shell", {"command": ["bash", "-lc", line, "more"]}, str(world["work"])),
             ("shell", {"command": ["bash", "-lc", line + "; true"]}, str(world["work"])),
             ("shell", {"command": ["bash", "-x", line]}, str(world["work"]))]
    assert all(said and HELD in said for said in world["judge"](waits))


def test_a5_codex_commands_are_judged_where_codex_runs_them(world):
    """Codex runs an exec_command's `cmd` in its `workdir`, not the session's folder the payload names as `cwd`."""
    session = world["home"] / "s1" / "s2" / "s3"
    workdir = world["home"] / "w"
    for folder in (session, workdir):
        folder.mkdir(parents=True)
    (workdir / "f.json").write_text("{}\n")
    line = "cp f.json ../.synthesis/v5/state/approvals/a.json"  # from workdir it lands in the approvals
    said = guards.check("exec_command", {"cmd": line, "workdir": str(workdir)}, {}, cwd=str(session),
                        session={"session_id": "S-principal"})
    assert said and said.startswith("Refused"), said
    relative = f"../.synthesis/v5/bin/synthesis-release --repo-root {world['canon']}"
    assert HELD in world["judge"]([("exec_command", {"cmd": relative, "workdir": str(workdir)}, str(session))])[0]


def test_a6_a_project_of_its_own_named_release_or_setup_runs_with_no_code(world, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.py").write_text("print('a project of its own')\n")
    (project / "release.py").write_text("def main():\n    print('bump')\n")
    (project / "bump.py").write_text("import release\nrelease.main()\n")
    lines = [[f"python3 -c 'import setup'", str(project)], [f"python3 {project}/bump.py", str(project)],
             [f"python3 - <<'EOF'\nimport release\nrelease.main()\nEOF", str(project)]]
    assert world["judge"](lines) == [None] * len(lines)
    kit = world["tool"].parent
    computed = ("import os, sys; sys.path.insert(0, os.path.join(os.path.expanduser('~'), '.synthesis/v5/current/skills/"
                "synthesis-skills-manager/scripts')); import release; release.main(['--repo-root', '/x'])")
    held = [f"python3 -c \"import sys; sys.path.insert(0, '{kit}'); import release\"", f"python3 -c {shlex.quote(computed)}",
            [f"python3 -c 'import release; release.main([])'", str(kit)]]
    assert all(said and HELD in said for said in world["judge"](held))


def test_a8_the_git_hooks_folder_is_one_the_guard_protects(world):
    hook = world["home"] / ".synthesis" / "v5" / "git-hooks" / "pre-commit"
    said = world["judge"]([("Write", {"file_path": str(hook), "content": "exit 0\n"}, str(world["work"])),
                           f"cp {world['work']}/x {hook}", f"echo exit 0 > {hook}"])
    assert all(s and s.startswith("Refused") for s in said), said

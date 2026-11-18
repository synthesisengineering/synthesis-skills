"""22.32: a program run under the name of a command the guard judges by name is read as what it is.

The guard reads a program the agent runs by its path when the program has a name of its own (`tools/mytool` waits for
the code where it names a protected folder). A review (2026-11-15, C9) gave such a program the name of a command the
guard judges by name instead: a shell, an interpreter, `ls`, `git` and their like. It was judged as that command and its
file was never read, whether it ran by its absolute path, by a relative one, or found first on PATH in a folder the user
can write, and it replaced the runtime's guard in nine forms of nine. Now a command word that resolves, by its path or
through PATH as the shell would, to a script (a text file, with a `#!` line or none) rather than the compiled program
that command really is, is also judged as the script it is, under the guard's rules for scripts; its judgment by name
still applies. Real commands are compiled programs or links to them and pass as before, and so do the commands that
really are scripts where their installer puts them (the guardrails' references/config.md, "Commands judged by name").
A compiled look-alike is on the open list (docs/runtime-integration.md, "What remains open").
"""

import json
import os
import shlex
import shutil
import sys

import pytest

from synthesis import guards, paths

HELD = "approve followed by the code"
READS = "python3 -c 'import sys; print(open(sys.argv[1]).read()[:9])' {record}"  # a transcript read, as its reader proves
SYSTEM_PATH = os.environ.get("PATH", "")
PYTHON = os.path.realpath(sys.executable)  # a compiled program, wherever this suite runs
LOOK_ALIKES = ("bash", "sh", "zsh", "python3", "node", "perl", "git", "ls")
RUNS = {"bash": "bash -c 'ls'", "sh": "sh -c 'echo hi'", "zsh": "zsh -c 'pwd'", "python3": "python3 -c 'print(1)'",
        "node": "node -e 1", "perl": "perl -e 1", "git": "git status", "ls": "ls -la"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own with its protected folders where they lie on a Mac, a working folder with `tools/` in
    it, and the runtime's guard as the file a look-alike would replace (`current/` under the synthesis home)."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("PATH", SYSTEM_PATH)
    record = home / ".claude" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n", encoding="utf-8")
    (paths.approvals() / "grants").mkdir(parents=True)
    work = tmp_path / "work"
    tools = work / "tools"
    tools.mkdir(parents=True)
    target = paths.home() / "current" / "synthesis" / "guards.py"
    stub = work / "stub.py"
    stub.write_text("def check(*args, **kwargs):\n    return None\n", encoding="utf-8")

    def plant(name, text=None, folder=tools):
        """A script of the agent's, by default one that writes the stub over the runtime's guard."""
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(f"#!/bin/sh\ncat {stub} > {target}\n" if text is None else text, encoding="utf-8")
        (folder / name).chmod(0o755)
        return folder / name

    def link(where, to):
        where.parent.mkdir(parents=True, exist_ok=True)
        where.symlink_to(to)
        return where

    def first_on_path(*folders):
        monkeypatch.setenv("PATH", os.pathsep.join([str(f) for f in folders] + [SYSTEM_PATH]))

    def verdict(line, config=None):
        return guards.check("Bash", {"command": line}, config or {}, cwd=str(work),
                            session={"session_id": "S-principal", "transcript_path": str(record)})

    return {"home": home, "work": work, "tools": tools, "target": target, "stub": stub, "record": record, "plant": plant,
            "link": link, "first_on_path": first_on_path, "verdict": verdict, "tmp": tmp_path}


def _held(reason) -> bool:  # held for the code, or refused outright where the script writes the runtime's own files: with
    return bool(reason) and (HELD in reason or reason.startswith("Refused"))  # 22.21 a shell script is read line by line


# --- the review's nine forms (C9), each a script of the agent's named like a command the guard knows ------------------

@pytest.mark.parametrize("form", ["{tools}/bash -lc 'ls'", "{tools}/sh -c 'echo hi'", "tools/zsh -c 'pwd'", "{tools}/bash",
                                  "{tools}/python3 -c 'print(1)'", "{tools}/perl -e 1", "{tools}/node -e 1", "{tools}/ls",
                                  "{tools}/git status"],
                         ids=["bash -lc ls", "sh -c echo", "zsh -c pwd, relative", "bash alone", "python3 -c", "perl -e",
                              "node -e", "ls", "git status"])
def test_the_reviews_nine_forms_wait_for_the_code(world, form):
    for name in LOOK_ALIKES:
        world["plant"](name)
    line = form.format(tools=world["tools"])
    assert _held(world["verdict"](line)), line


# --- each look-alike by its absolute path, by a relative one, and found first on PATH in a folder the user writes -----

@pytest.mark.parametrize("how", ["absolute path", "relative path", "first on PATH"])
@pytest.mark.parametrize("name", LOOK_ALIKES)
def test_a_look_alike_waits_however_it_is_found(world, name, how):
    world["plant"](name)
    run = RUNS[name]
    if how == "absolute path":
        line = f"{world['tools']}/{run}"
    elif how == "relative path":
        line = f"./tools/{run}"
    else:
        world["first_on_path"](world["tools"])
        line = run
    assert _held(world["verdict"](line)), line


def test_the_hold_names_the_script_and_the_name_it_takes(world):
    world["plant"]("ls")
    reason = world["verdict"](f"{world['tools']}/ls -la")
    assert _held(reason) and str(world["tools"] / "ls") in reason and "under the name of `ls`" in reason, reason


# --- a PATH the line gives itself, a wrapper before the look-alike, a look-alike wrapper, and `find -exec` ------------

@pytest.mark.parametrize("line", [
    "PATH={tools}:$PATH ls -la",
    "export PATH={tools}:$PATH && git status",
    "export PATH=\"$(pwd)/tools:$PATH\" && ls -la",
    "PATH=$PWD/tools:$PATH git status",
    "env PATH={tools} python3 -c 'print(1)'",
    "cd tools && PATH=. ls",
    "cd tools && ./ls",
    "nohup {tools}/ls",
    "timeout 5 tools/git status",
    "{tools}/env ls",
    "echo . | {tools}/xargs ls",
])
def test_a_look_alike_reached_through_the_lines_own_path_or_a_wrapper_waits(world, line):
    for name in ("ls", "git", "python3", "env", "xargs"):
        world["plant"](name)
    line = line.format(tools=world["tools"])
    assert _held(world["verdict"](line)), line


@pytest.mark.parametrize("line", ["tools/l?", "{tools}/[l]s -la", "t*/git status"])
def test_a_look_alike_named_through_a_pattern_waits(world, line):
    """The shell expands the pattern before it runs the first word it makes."""
    for name in ("ls", "git"):
        world["plant"](name)
    line = line.format(tools=world["tools"])
    assert _held(world["verdict"](line)), line


def test_a_path_the_line_adds_to_is_read_after_the_one_it_had(world):
    """`PATH+=…` puts its folders after PATH's own, so the real `ls` is still the one found first."""
    world["plant"]("ls")
    assert world["verdict"]("cd tools && PATH+=:/nonexistent ls") is None
    assert _held(world["verdict"]("cd tools && PATH=.:$PATH ls"))


def test_only_a_name_the_guard_trusts_is_looked_at(world, monkeypatch):
    """The check costs a lookup only where the guard judges a command by its name; a program of its own name is read
    as before, by its path, and looked up for nothing."""
    asked = []
    for name in ("_runnable", "_compiled"):
        real = getattr(guards, name)
        monkeypatch.setattr(guards, name, lambda spot, real=real: asked.append(spot) or real(spot))
    world["plant"]("mytool", "#!/bin/sh\necho benign\n")
    world["first_on_path"](world["tools"])
    world["verdict"]("mytool a && othertool b | sort")
    assert asked and not [spot for spot in asked if os.path.basename(spot) in ("mytool", "othertool")]  # `sort` was
    world["verdict"]("ls -la")
    assert [spot for spot in asked if os.path.basename(spot) == "ls"]


@pytest.mark.parametrize("line", ["env echo hi", "find . -maxdepth 0 -exec echo {} \\;", "nohup printf x", "xargs test -n"])
def test_a_builtins_name_after_a_program_that_runs_it_from_path_is_looked_up(world, line):
    """`env`, `find -exec`, `nohup` and `xargs` start the command themselves, from PATH: a shell's builtin is no part of it."""
    for name in ("echo", "printf", "test"):
        world["plant"](name)
    world["first_on_path"](world["tools"])
    assert _held(world["verdict"](line)), line


@pytest.mark.parametrize("line", ["echo hi", "printf '%s\\n' x", "test -n x", "cd . && pwd"])
def test_a_builtin_the_shell_runs_itself_is_not_looked_up(world, line):
    """bash, zsh and dash run these themselves: a script of the same name earlier on PATH never runs."""
    for name in ("echo", "printf", "test", "cd", "pwd"):
        world["plant"](name)
    world["first_on_path"](world["tools"])
    assert world["verdict"](line) is None, line


# --- a look-alike the line itself writes, then runs ------------------------------------------------------------------

def test_a_look_alike_the_line_writes_and_runs_by_its_path_waits(world):
    line = (f"printf '#!/bin/sh\\ncat {world['stub']} > {world['target']}\\n' > tools/ls && chmod +x tools/ls && tools/ls")
    assert not (world["tools"] / "ls").exists()
    assert _held(world["verdict"](line)), line


def test_a_look_alike_the_line_copies_into_place_and_runs_waits(world):
    evil = world["plant"]("evil.sh", folder=world["work"])
    line = f"cp {evil} {world['tools']}/git && {world['tools']}/git status"
    assert _held(world["verdict"](line)), line


def test_a_compiled_program_the_line_links_or_copies_into_place_is_judged_as_what_it_copies(world):
    """The replay's one ordinary case (2026-11-16): a line that links a real interpreter into a folder and runs it there.
    A link or a copy is what it copies; a file made only executable keeps what it holds."""
    world["link"](world["tools"] / "python3-made-earlier", PYTHON)
    for line in (f"mkdir -p venv/bin && ln -s {PYTHON} venv/bin/python3 && venv/bin/python3 -c 'print(1)'",
                 f"mkdir -p bin && cp {PYTHON} bin/python3 && ./bin/python3 -c 'print(1)'",
                 "cd tools && ln -sf python3-made-earlier python3 && ./python3 -c 'print(1)'",
                 f"chmod +x {world['tools']}/python3-made-earlier && {world['tools']}/python3-made-earlier -c 'print(1)'"):
        assert world["verdict"](line) is None, line


def test_a_script_the_line_copies_into_place_is_read_as_the_script_it_copies(world):
    """Under a name the guard trusts, the copied script's own text is what is read: the line names no protected folder,
    the script it links names the runtime's guard, and the hold names the runtime."""
    evil = world["plant"]("evil.sh", folder=world["work"])
    reason = world["verdict"](f"ln -s {evil} {world['tools']}/ls && {world['tools']}/ls -la")
    assert _held(reason) and "under the name of `ls`" in reason and (  # held, naming the runtime; or, read line by line
        str(paths.home() / "current") in reason or str(evil) in reason), reason  # (22.21), refused, naming the script it links


def test_a_look_alike_the_line_writes_first_on_path_and_runs_by_name_waits(world):
    world["first_on_path"](world["tools"])
    line = (f"printf '#!/bin/sh\\ncat {world['stub']} > {world['target']}\\n' > {world['tools']}/ls; "
            f"chmod +x {world['tools']}/ls; ls")
    assert _held(world["verdict"](line)), line


# --- what the look-alike's `#!` line says it runs as ------------------------------------------------------------------

def test_a_look_alike_is_judged_as_its_interpreter_runs_it(world):
    """A Python look-alike is read by the Python reader: one that only reads passes, one that writes the guard is held;
    `#!/bin/cat` only prints its file; a `#!` line that names another look-alike runs that one too."""
    reads = world["plant"]("ls", "#!/usr/bin/env python3\nimport sys\nprint(len(open(sys.argv[0]).read()))\n")
    assert world["verdict"](f"{reads} -la") is None
    world["plant"]("git", f"#!/usr/bin/env python3\nimport shutil\nshutil.copy({str(world['stub'])!r}, {str(world['target'])!r})\n")
    reason = world["verdict"](f"{world['tools']}/git status")
    assert reason and (reason.startswith("Refused") or _held(reason)), reason
    world["plant"]("cat", "#!/bin/cat\nanything at all\n")
    assert world["verdict"](f"{world['tools']}/cat notes.txt") is None
    world["plant"]("bash")
    world["plant"]("sh", f"#!{world['tools']}/bash\necho hi\n")
    assert _held(world["verdict"](f"{world['tools']}/sh -c 'echo hi'"))


def test_a_look_alike_of_the_hook_is_refused_as_running_it(world):
    hook = world["plant"]("synthesis-hook", "#!/bin/sh\nexec python3 -c 'pass' \"$@\"\n", folder=paths.home() / "bin")
    world["link"](world["tools"] / "python3", hook)
    reason = world["verdict"](f"{world['tools']}/python3 pre-tool-use")
    assert reason and reason.startswith("Refused") and "synthesis hook" in reason, reason


@pytest.mark.parametrize("line", ["bash -c 'tools/ls -la'", "watch 'tools/ls -la'", "sh -c \"cd tools && ./git status\""])
def test_a_look_alike_inside_another_commands_words_waits(world, line):
    for name in ("ls", "git"):
        world["plant"](name)
    assert _held(world["verdict"](line)), line


# --- its judgment by name still applies -------------------------------------------------------------------------------

def test_a_look_alike_wrapper_still_has_what_it_wraps_judged(world):
    """A script named like npx that hands its words on: the deploy it is handed still waits as one."""
    world["plant"]("npx", "#!/bin/sh\nexec \"$@\"\n")
    reason = world["verdict"](f"{world['tools']}/npx wrangler pages deploy dist")
    assert _held(reason) and "publishes to production" in reason, reason


def test_a_look_alike_shell_still_has_its_own_script_read(world):
    world["plant"]("bash", "#!/bin/sh\necho benign\n")
    reason = world["verdict"](f"{world['tools']}/bash -c 'cat {world['stub']} > {world['target']}'")
    assert reason and reason.startswith("Refused"), reason


# --- what passes as before: the real commands, links to them, and the commands that really are scripts ----------------

@pytest.mark.parametrize("line", ["ls -la", "/bin/ls -la", "bash -c 'ls'", "sh -c 'echo hi'", "/bin/sh -c 'echo hi'",
                                  "zsh -c 'pwd'", "git status", "python3 -c 'print(1)'", "perl -e 1", "node -e 1",
                                  "env ls", "nohup ls", "find . -maxdepth 0 -exec ls {} \\;", "cd /tmp && ls"])
def test_the_real_commands_pass(world, line):
    assert world["verdict"](line) is None, line


def test_links_to_compiled_programs_pass_wherever_they_lie(world):
    """Homebrew's python3 and node are links into its Cellar, a venv's python a link to the interpreter it was made
    from: compiled programs, in folders the user writes."""
    brew = world["tmp"] / "brew"
    world["link"](brew / "Cellar" / "python@3.12" / "3.12.0" / "bin" / "python3.12", PYTHON)
    world["link"](brew / "bin" / "python3", "../Cellar/python@3.12/3.12.0/bin/python3.12")
    world["link"](brew / "Cellar" / "node" / "22.0.0" / "bin" / "node", PYTHON)
    world["link"](brew / "bin" / "node", "../Cellar/node/22.0.0/bin/node")
    venv = world["tmp"] / "venv"
    world["link"](venv / "bin" / "python3", PYTHON)
    world["link"](venv / "bin" / "python", "python3")
    world["link"](world["tools"] / "git", os.path.realpath(shutil.which("git") or "/usr/bin/git"))
    world["link"](world["tools"] / "bash", os.path.realpath("/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"))
    reads = READS.format(record=shlex.quote(str(world["record"])))  # its reader proves it only reads
    for line in (f"{brew}/bin/python3 -c 'print(1)'", f"{brew}/bin/node -e 1", f"{venv}/bin/python -c 'print(1)'",
                 f"{venv}/bin/python3 -m json.tool {world['stub']}", "tools/git status", f"{world['tools']}/bash -c 'ls'"):
        assert world["verdict"](line) is None, line
    world["first_on_path"](brew / "bin", venv / "bin")
    for line in ("python3 -c 'print(1)'", "node -e 1", "python -c 'print(1)'", reads):
        assert world["verdict"](line) is None, line


def test_the_commands_that_really_are_scripts_pass_where_their_installer_puts_them(world, monkeypatch):
    """npm's npx in its global folder, a version manager's shim, a Homebrew formula's own script, the synthesis
    launcher in the runtime's protected bin/, and the system's own scripts (macOS's /usr/bin/cd, shasum on both)."""
    npm = world["tmp"] / "npm-global"
    world["plant"]("npx-cli.js", "#!/usr/bin/env node\nrequire('../lib/cli.js')\n", folder=npm / "lib" / "node_modules" / "npm" / "bin")
    world["link"](npm / "bin" / "npx", "../lib/node_modules/npm/bin/npx-cli.js")
    shims = world["tmp"] / ".pyenv" / "shims"
    world["plant"]("python3", "#!/usr/bin/env bash\nset -e\nprogram=\"${0##*/}\"\nexec pyenv exec \"$program\" \"$@\"\n", folder=shims)
    brew = world["tmp"] / "brew"
    monkeypatch.setenv("HOMEBREW_PREFIX", str(brew))
    world["plant"]("groovy", "#!/bin/sh\nexec java -classpath groovy.jar \"$@\"\n", folder=brew / "Cellar" / "groovy" / "4.0.0" / "libexec" / "bin")
    world["link"](brew / "bin" / "groovy", "../Cellar/groovy/4.0.0/libexec/bin/groovy")
    launcher = world["plant"]("synthesis", "#!/bin/sh\nexec python3 -c 'from synthesis.cli import main; main()' \"$@\"\n",
                              folder=paths.home() / "bin")
    world["link"](world["tmp"] / "local-bin" / "synthesis", launcher)
    lines = [f"{npm}/bin/npx --version", f"{shims}/python3 -c 'print(1)'", f"{brew}/bin/groovy -e 1", f"{launcher} who"]
    lines += [f"/usr/bin/shasum -a 256 {world['stub']}"] * os.path.isfile("/usr/bin/shasum") + ["env cd /tmp"] * os.path.isfile("/usr/bin/cd")
    for line in lines:
        assert world["verdict"](line) is None, line
    world["first_on_path"](npm / "bin", shims, brew / "bin", world["tmp"] / "local-bin")
    reads = READS.format(record=shlex.quote(str(world["record"])))  # through the shim, still read as Python
    for line in ("npx --version", "python3 -c 'print(1)'", reads, "groovy -e 1", "synthesis who"):
        assert world["verdict"](line) is None, line


def test_an_installers_folder_admits_only_the_names_that_installer_provides(world, monkeypatch):
    """A folder the user writes admits a script only under a name its installer provides there: `ls` linked from npm's
    global folder, set among a version manager's shims, or in Homebrew's Cellar is read as the script it is, and a
    Cellar that is not Homebrew's admits nothing."""
    npm, brew, elsewhere = world["tmp"] / "npm-global", world["tmp"] / "brew", world["tmp"] / "else"
    monkeypatch.setenv("HOMEBREW_PREFIX", str(brew))
    world["plant"]("x.js", folder=npm / "lib" / "node_modules" / "pkg" / "bin")
    world["link"](npm / "bin" / "ls", "../lib/node_modules/pkg/bin/x.js")
    shim = world["plant"]("ls", folder=world["tmp"] / ".pyenv" / "shims")
    world["plant"]("ls", folder=brew / "Cellar" / "coreutils" / "9.5" / "bin")
    world["link"](brew / "bin" / "ls", "../Cellar/coreutils/9.5/bin/ls")
    world["plant"]("groovy", folder=elsewhere / "Cellar" / "groovy" / "4.0.0" / "bin")
    for line in (f"{npm}/bin/ls", f"{shim} -la", f"{brew}/bin/ls -la", f"{elsewhere}/Cellar/groovy/4.0.0/bin/groovy -e 1"):
        assert _held(world["verdict"](line)), line


def test_ordinary_scripts_off_the_guards_lists_are_judged_as_before(world):
    """pip3, pytest, npm and a venv's activate are scripts, and the guard judged them by none of its lists before."""
    venv = world["tmp"] / "venv"
    world["link"](venv / "bin" / "python3", PYTHON)
    for name in ("pip3", "pytest"):
        world["plant"](name, f"#!{venv}/bin/python3\nimport sys\nsys.exit(0)\n", folder=venv / "bin")
    world["plant"]("activate", "export PATH=\"$VIRTUAL_ENV/bin:$PATH\"\n", folder=venv / "bin")
    world["plant"]("npm", "#!/usr/bin/env node\nrequire('../lib/cli.js')\n", folder=world["tmp"] / "npm-global" / "bin")
    world["first_on_path"](venv / "bin", world["tmp"] / "npm-global" / "bin")
    for line in ("pip3 --version", "pytest -q", "npm --version", f". {venv}/bin/activate && python3 -c 'print(1)'",
                 f"{venv}/bin/pip3 install -e ."):
        assert world["verdict"](line) is None, line


# --- the open list: a compiled look-alike is judged by its name --------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="open list, crafted: a compiled look-alike is judged by the name it takes "
                                       "(docs/runtime-integration.md, What remains open)")
@pytest.mark.parametrize("how", ["copied", "linked"])
def test_a_compiled_look_alike_is_judged_by_its_name(world, how):
    """A compiled program under the name of a command the guard trusts: here `cp`, copied or linked as `cat`, handed
    the stub and the runtime's guard. The guard reads only that it is compiled, so it judges it as `cat`."""
    real = os.path.realpath(shutil.which("cp", path="/bin:/usr/bin"))
    (shutil.copy2 if how == "copied" else os.symlink)(real, world["tools"] / "cat")
    assert world["verdict"](f"{world['tools']}/cat {world['stub']} {world['target']}") is not None


# --- the harness programs, on launchers like a Mac's (the coordinator, 2026-11-16): with 22.26 merged, a reading of a
# harness's launcher script sees where its program lives, which 22.26 holds for writes, and would make every call of it
# wait. A harness program's text that names where its own program lives writes nothing (22.26), so each of these passes.

CODEX_LAUNCHER = ("#!/bin/sh\n# a PATH shim: the Codex binary ships inside an app or a plugin folder, on no shell's PATH\n"
                  'for candidate in "$HOME/.codex/plugins/.plugin-appserver/codex-cli/bin/codex" \\\n'
                  '    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex" \\\n'
                  '    "/Applications/Codex.app/Contents/Resources/codex-cli/bin/codex"; do\n'
                  '    [ -x "$candidate" ] && exec "$candidate" "$@"\ndone\necho "codex: no Codex CLI found" >&2\nexit 127\n')
HARNESS_CALLS = ["codex --version", "codex exec 'summarize the diff'", "env codex --version", "timeout 600 codex exec 'review it'",
                 "claude --version", "claude -p 'hello'", "command -v codex claude", "~/.local/bin/codex --version",
                 "sh ~/.local/bin/codex --version"]


@pytest.mark.parametrize("line", HARNESS_CALLS)
@pytest.mark.parametrize("read", [False, True], ids=["as named", "read as a look-alike"])
def test_codex_and_claude_pass_on_launchers_like_a_macs(world, monkeypatch, line, read):
    """`codex` a shell script in ~/.local/bin that names the app's binary, `claude` a link there to a compiled program;
    read as a look-alike too, as 22.32 would read them were they names the guard judges by."""
    if read:
        trusted = guards._trusted
        monkeypatch.setattr(guards, "_trusted", lambda name: name in ("codex", "claude") or trusted(name))
    local = world["home"] / ".local" / "bin"
    world["plant"]("codex", CODEX_LAUNCHER, folder=local)
    compiled = world["home"] / ".local" / "share" / "claude" / "versions" / "2.1.316"
    compiled.parent.mkdir(parents=True)
    compiled.write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 60)  # a Mach-O program's first bytes
    compiled.chmod(0o755)
    world["link"](local / "claude", compiled)
    world["first_on_path"](local)
    assert world["verdict"](line) is None, line


# --- a wrapper that only hands its words to the real program (the merge of 22.32 into release/next, 2026-11-16): CI's
# Apple job puts Apple's Python first as `python` by a two-line script, since a link would break Xcode's shim, and a run
# that puts another interpreter first does the same. Judged as a look-alike, the wrapper's `"$@"` lost the program it
# hands on, and an ordinary read through it waited.

HANDS_ON = '#!/bin/sh\nexec {target} "$@"\n'
SYSTEM_PYTHON = "/usr/bin/python3"


@pytest.mark.parametrize("name", ["python", "python3"])
def test_a_wrapper_that_only_hands_its_words_to_the_real_interpreter_is_that_interpreter(world, name):
    if not (os.path.isfile(SYSTEM_PYTHON) and guards._root_owned(os.path.realpath(SYSTEM_PYTHON))):
        pytest.skip("no Python of root's own at /usr/bin/python3 here")
    world["plant"](name, HANDS_ON.format(target=SYSTEM_PYTHON))
    world["first_on_path"](world["tools"])
    for line in (READS.format(record=shlex.quote(str(world["record"]))).replace("python3", name, 1), f"{name} -m pytest -q"):
        assert world["verdict"](line) is None, line


def test_a_wrapper_that_does_more_or_hands_its_words_to_a_program_of_its_own_is_still_read(world):
    if not (os.path.isfile(SYSTEM_PYTHON) and guards._root_owned(os.path.realpath(SYSTEM_PYTHON))):
        pytest.skip("no Python of root's own at /usr/bin/python3 here")
    world["first_on_path"](world["tools"])
    world["plant"]("python3", HANDS_ON.format(target=SYSTEM_PYTHON) + f"cat {world['stub']} > {world['target']}\n")
    assert _held(world["verdict"]("python3 -c 'print(1)'"))  # more than the hand-off
    world["plant"]("evil")  # writes the stub over the runtime's guard
    world["plant"]("python3", HANDS_ON.format(target=world["tools"] / "evil"))
    assert _held(world["verdict"]("python3 -c 'print(1)'"))  # handed to a script of the agent's


# --- a command in a system folder the user cannot write (the integration review of 5.24.0, finding 1): on Ubuntu,
# /usr/bin/open is a link, through /etc/alternatives, to the shell script xdg-open. Root installed every step of that
# chain, in folders no program of the agent's can write, so nothing can turn it elsewhere: it is that command, whatever
# the file it leads to is named. A link in a folder the user writes, or a chain that passes through one, is still read.
# Here a folder of the test's own stands in for the system's, taken as root's (`_root_owned`).

def _system(world, monkeypatch):
    system = world["tmp"] / "system"
    script = world["plant"]("xdg-open", folder=system / "bin")  # read as a look-alike, it writes the runtime's guard
    world["link"](system / "alternatives" / "open", script)
    world["link"](system / "bin" / "open", system / "alternatives" / "open")
    owned = guards._root_owned
    monkeypatch.setattr(guards, "_root_owned", lambda path: paths.inside(path, str(system)) or owned(path))
    return system


def test_a_command_root_installed_as_a_link_to_a_script_of_another_name_is_that_command(world, monkeypatch):
    system = _system(world, monkeypatch)
    world["first_on_path"](system / "bin")
    for line in ("open -a Docker", "cd {work} && grep -c x notes.md; open -a Docker".format(work=world["work"]), "command open -a Docker"):
        assert world["verdict"](line) is None, line


@pytest.mark.parametrize("how", ["a link in a folder the user writes", "a chain through a folder the user writes",
                                 "a system link to a script the user writes"])
def test_a_link_to_such_a_script_through_a_folder_the_user_writes_is_still_read(world, monkeypatch, how):
    system = _system(world, monkeypatch)
    if how == "a link in a folder the user writes":
        world["link"](world["tools"] / "open", system / "bin" / "xdg-open")
    elif how == "a chain through a folder the user writes":
        world["link"](world["tools"] / "alternatives" / "open", system / "bin" / "xdg-open")
        world["link"](system / "bin" / "elsewhere" / "open", world["tools"] / "alternatives" / "open")
    else:
        world["link"](system / "bin" / "elsewhere" / "open", world["plant"]("open-script"))
    world["first_on_path"](world["tools"] if how == "a link in a folder the user writes" else system / "bin" / "elsewhere", system / "bin")
    assert _held(world["verdict"]("open -a Docker")), how

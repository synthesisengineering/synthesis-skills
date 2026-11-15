"""Install the v5 runtime at one stable path, and keep it current (R7.1, R7.5).

Hooks call ~/.synthesis/v5/bin/synthesis-hook, whose command text never
changes between releases, so a harness deleting an old plugin folder never
breaks a running task (Codex still asks for its hook approval again after each
release: it ties the approval to the installed plugin's contents). At each
session start the hook passes the plugin folder the harness loaded; if it is a
newer release than the installed copy, it is installed beside the old one and
`current` switches atomically. A session still on an older plugin (one that
resumes or compacts after an upgrade) never switches it back; an explicit
install (setup, release, `synthesis install`) installs whatever it is given.

Run: python3 -S <plugin>/synthesis/install.py [plugin root] [--git-hooks]
     python3 -S <plugin>/synthesis/install.py uninstall [--dry-run]

`--git-hooks` points the global core.hooksPath at the v5 commit check after
recording the value it replaces; uninstall restores that value unless the user
changed it since, and removes only files install wrote that are still unedited.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import paths  # noqa: E402

GIT_HOOKS = ("pre-commit", "pre-merge-commit", "commit-msg")
DAY_END = ("day-end", "day-end-nudge.sh")  # the rituals' launcher and nudge ride every release into bin/
# Scripts run outside a session (scheduled sweeps, autopilot wakes and backstops) need a stable path too.
STABLE_SKILL_SCRIPTS = ("synthesis-inbox-cleanup", "synthesis-autopilot", "synthesis-promotion-gate", "synthesis-daily-rituals",
                        "synthesis-chief-of-staff",  # the holds ledger's reader, which the same-day guard asks
                        "synthesis-kb-edit",  # the phrase scan a knowledge base's own git hooks run (sharing-standard.md)
                        "synthesis-skills-manager", "synthesis-onboarding")  # the release tool and its imports, run from here
# Every entry point runs one interpreter, pinned at install (review round 1 of 5.23.1, P1, P3 and A4). `python3` from
# PATH let one file named python3 in a folder this user writes, earlier on PATH, replace the guard, and the interpreter's
# own start-up (a .pth file, usercustomize, PYTHONPATH, Apple's compiled-code folder, DEVELOPER_DIR, DYLD_*) ran code
# placed outside the runtime first. So the launchers in the protected bin/ and git-hooks/ run the interpreter named by
# its real path, accepted only when it and every folder above it are owned by root and writable by neither this user
# nor its groups, with -I -S, through `env -i` and only the variables named here: those the runtime was measured to
# read (every entry point run once), the harnesses' own and git's for the commit check. PATH starts with the system's
# folders, so no tool the runtime starts (git, ps, ioreg) is one placed earlier on it.
PYTHONS = ("/Library/Frameworks/Python.framework/Versions/Current/bin/python3",  # python.org's
           "/Library/Developer/CommandLineTools/usr/bin/python3", "/Applications/Xcode.app/Contents/Developer/usr/bin/python3",
           "/usr/bin/python3", "/usr/local/bin/python3")  # the real file behind each; Apple's /usr/bin shim runs xcrun
KEPT = ("HOME", "USER", "LOGNAME", "TMPDIR", "TMP", "TEMP", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "COLUMNS",
        "LINES", "TERM", "TZ", "SSH_AUTH_SOCK", "GH_TOKEN", "GITHUB_TOKEN", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY",
        "https_proxy", "http_proxy", "no_proxy", "SYNTHESIS_HOME", "SYNTHESIS_SESSION", "SYNTHESIS_HOST", "SYNTHESIS_CLAUDE_BIN",
        "SYNTHESIS_CODEX_BIN", "SYNTHESIS_MUSE_BIN", "SYNTHESIS_CLAUDE_DESKTOP_DIR", "RITUAL_STATE_DIR", "CLAUDECODE",
        "CLAUDE_CODE_SESSION_ID", "CLAUDE_CONFIG_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "CODEX_HOME",
        "CODEX_THREAD_ID", "MUSE_SESSION_ID", "MUSE_PLUGIN_ROOT", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME",
        "XDG_CACHE_HOME", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")
GIT_KEPT = ("SYNTHESIS_GIT_HOOK", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_QUARANTINE_PATH", "GIT_PREFIX", "GIT_REFLOG_ACTION", "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_DATE", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_DATE",
            "GIT_NO_REPLACE_OBJECTS")  # what git hands the commit check about the commit it makes
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
NO_PYTHON = ("synthesis: no Python 3.9 or later owned by root, with every folder above it, and writable by neither this "
             "user nor its groups was found, so nothing runs; install python.org's Python or Apple's Command Line Tools, "
             "then run the plugin's install again")
ENTRY_POINTS = ("synthesis-hook", "synthesis", "synthesis-release")  # in bin/; the git hooks' are in git-hooks/
ENTRY = {"synthesis-hook": "{runtime}/synthesis/hook.py", "synthesis-release":
         "{runtime}/skills/synthesis-skills-manager/scripts/release.py",
         "synthesis": "-c 'import sys; sys.path.insert(0, sys.argv.pop(1)); from synthesis.cli import main; sys.exit(main())' "
                      "{runtime}", "git-hook": "{runtime}/synthesis/commit_check.py"}


def interpreter_problems(path: str) -> list:
    """Why `path` may not be the pinned interpreter: [] when it is its own real path, an executable regular file, and it
    and every folder above it are owned by root and writable by neither this user nor any of its groups."""
    if not os.path.isabs(path) or os.path.realpath(path) != path:
        return [f"{path} is not an absolute real path"]
    problems, spot = [], path
    while True:
        try:
            owner = os.lstat(spot).st_uid
        except OSError as exc:
            return [f"{spot}: {exc.strerror}"]
        problems += [f"{spot} is not owned by root"] if owner else [f"{spot} is writable by this user or its groups"] * os.access(spot, os.W_OK)
        if spot == os.path.dirname(spot):
            break
        spot = os.path.dirname(spot)
    return problems or ([] if os.path.isfile(path) and os.access(path, os.X_OK) else [f"{path} is not an executable file"])


def pinned_python(candidates=None) -> str:
    """The interpreter to pin: the first of this one and the system's own (`PYTHONS`), each by its real path, that
    `interpreter_problems` accepts and that, run isolated with no environment, is Python 3.9 or later; '' for none."""
    for candidate in ([sys.executable, *PYTHONS] if candidates is None else candidates):
        real = os.path.realpath(candidate) if candidate else ""
        if real and not interpreter_problems(real):
            try:
                if subprocess.run([real, "-I", "-S", "-c", "import sys; sys.exit(sys.version_info < (3, 9))"], env={},
                                  capture_output=True, timeout=30).returncode == 0:
                    return real
            except (OSError, subprocess.SubprocessError):
                continue
    return ""


def launcher_text(python: str, target: str, git_hook: bool = False) -> str:
    """A launcher that runs `target` (shell words) with the pinned `python`, isolated, with only the named variables
    that are set (one left unset stays unset); with no interpreter, one that refuses."""
    if not python:
        return f"#!/bin/sh\necho {shlex.quote(NO_PYTHON)} >&2\nexit 2\n"
    kept = " ".join(f'${{{name}+"{name}=${name}"}}' for name in KEPT + (GIT_KEPT if git_hook else ()))
    hook = ' SYNTHESIS_GIT_HOOK="$(basename "$0")"' if git_hook else ""
    return (f"#!/bin/sh\n# A synthesis entry point: the interpreter pinned at install, isolated, with a fixed environment.\n"
            f"exec /usr/bin/env -i {kept}{hook} PATH=\"{SAFE_PATH}${{PATH:+:$PATH}}\" {shlex.quote(python)} -I -S {target} \"$@\"\n")


def launcher(home: Path, python: str, name: str) -> str:
    """The text install writes for the entry point `name` (bin/<name>, or a git hook) of the synthesis home `home`."""
    entry = ENTRY["git-hook" if name in GIT_HOOKS else name]
    return launcher_text(python, entry.format(runtime=shlex.quote(str(Path(home) / "current"))), name in GIT_HOOKS)


def pinned(home: Path) -> str:
    """The interpreter the installed hook launcher runs, '' when it names none."""
    try:
        line = (Path(home) / "bin" / "synthesis-hook").read_text(encoding="utf-8").splitlines()[-1]
        words = shlex.split(line)
    except (OSError, ValueError, IndexError):
        return ""
    return words[words.index("-I") - 1] if words[:1] == ["exec"] and "-I" in words else ""


def _home() -> Path:
    return paths.home()


def package_hash(plugin_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((plugin_root / "synthesis").glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    for rel, path in _stable_skill_files(plugin_root):
        digest.update(rel.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:16]


def _stable_skill_files(plugin_root: Path):
    for name in STABLE_SKILL_SCRIPTS:
        folder = Path(plugin_root) / "skills" / name / "scripts"
        for path in sorted(folder.iterdir()) if folder.is_dir() else []:
            if path.is_file() and not path.name.startswith("test_"):
                yield f"skills/{name}/scripts/{path.name}", path


def version_tuple(text: str) -> tuple:
    return tuple(int(p) for p in text.split(".")) if re.fullmatch(r"\d+\.\d+\.\d+", text or "") else ()


def version(root: Path) -> tuple:
    """The release number in <root>/synthesis/__init__.py, as a comparable tuple; () if unreadable."""
    try:
        text = (Path(root) / "synthesis" / "__init__.py").read_text(encoding="utf-8")
    except OSError:
        return ()
    return version_tuple("".join(re.findall(r'__version__ = "([\d.]+)"', text)[:1]))


def current_hash() -> str:
    try:
        return (_home() / "current" / "HASH").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _write_exec(path: Path, text: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.chmod(0o755)
    os.replace(tmp, path)


COMPILED = ("import importlib.util as u, pathlib, sys\n"  # run by the pinned interpreter: every module compiled, by hash
            "def ok(s):\n    c = pathlib.Path(u.cache_from_source(str(s))).read_bytes()\n"
            "    return c[:4] == u.MAGIC_NUMBER and c[4] & 1 and c[8:16] == u.source_hash(s.read_bytes())\n"
            "sys.exit(0 if all(ok(s) for s in pathlib.Path(sys.argv[1]).glob('*.py')) else 1)")
COMPILE = ("import compileall, py_compile, sys\ncompileall.compile_dir(sys.argv[1], maxlevels=0, quiet=2, "
           "invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)")


def _pinned_run(package: Path, code: str) -> bool:
    """Run `code` on the runtime package with the interpreter its launchers pin, as they run it (-I -S, where no
    folder of compiled code but the package's own applies); False when there is none or it fails."""
    python = pinned(Path(package).parent.parent)
    try:
        return bool(python) and subprocess.run([python, "-I", "-S", "-c", code, str(package)], env={}, capture_output=True,
                                               timeout=300).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _compiled(package: Path) -> bool:
    """Whether the pinned interpreter would load every module of the runtime from compiled code beside its source,
    made from the source that is there now."""
    return _pinned_run(package, COMPILED)


def _compile(package: Path) -> None:
    """Compiles the runtime once, for the interpreter the launchers pin, beside its source, where an isolated run
    looks. A hook is a new process on every tool call, and a caller told to write no bytecode caches nothing it
    compiles: the guards were compiled from their source each time, 72 ms for a shell command's check where 33 ms is
    what it takes (2026-11-12). Each compiled file carries its source's hash and is checked against it when loaded,
    since by date and size a file of the next release could pass for the one before it. A runtime already compiled
    is left as it is. Nothing here stops an install: whatever goes wrong leaves the runtime as it was, slower and whole."""
    if not _compiled(package):
        _pinned_run(package, COMPILE)


class Refused(RuntimeError):
    """An install that would put an older release, or bytes other than the ones expected, in the runtime's place."""


def takes(rel: str) -> bool:
    """Whether the runtime takes this file of a plugin (by its path in the plugin) when it installs."""
    parts = rel.split("/")
    return (len(parts) == 2 and parts[0] == "synthesis" and parts[1].endswith(".py")) or rel == "CHANGELOG.md" or (
        len(parts) == 4 and parts[0] == "skills" and parts[1] in STABLE_SKILL_SCRIPTS and parts[2] == "scripts"
        and not parts[3].startswith("test_"))


def _blob(path: Path) -> str:
    data = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _differences(folder: Path, expected: dict) -> list:
    """Each file of a staged or installed release that is not the expected blob, missing or extra."""
    found = {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts
             and p.relative_to(folder).as_posix() not in ("HASH", "SOURCE")}
    return ([f"differs {rel}" for rel in sorted(set(found) & set(expected)) if _blob(found[rel]) != expected[rel]]
            + [f"missing {rel}" for rel in sorted(set(expected) - set(found))] + [f"extra {rel}" for rel in sorted(set(found) - set(expected))])


def install(plugin_root: Path, first_only: bool = False, expected: dict = None) -> str:
    """Install the plugin's runtime if it differs from the current one. Returns a one-line report.

    first_only (the session-start hook and the first-install bootstrap): install only where no runtime exists at all.
    The folder a harness passes is its own plugin cache, which the guard does not protect, so an installed runtime is
    replaced only by the release tool, from a clone it verified (the principal's sandbox rulings of 2026-11-15). Any
    other install refuses (Refused) a release older than the running one (review round 1 of 5.23.1, A1). `expected`
    ({path: blob id}, every file the runtime takes, as the release read it from its fresh clone): the staged copy must
    hold exactly those bytes before `current` moves, or nothing moves (A3)."""
    plugin_root = Path(plugin_root).resolve()
    if not (plugin_root / "synthesis" / "hook.py").is_file():
        return f"not a synthesis plugin: {plugin_root}"
    home = _home()
    running = version(home / "current")
    try:
        move_board(home)  # before any switch, so the new release's first read finds the board in place
    except OSError as exc:  # never blocks a session start; the doctor names what is left in state/
        print(f"synthesis: the board could not be moved out of {home / 'state'}: {exc}", file=sys.stderr)
    if first_only and current_hash():
        _compile(home / "current" / "synthesis")  # the interpreter it runs on may have changed under it
        return f"synthesis runtime kept at {current_hash()}: a session start installs only where no runtime exists"
    if running and version(plugin_root) < running:
        raise Refused(f"{plugin_root} holds {'.'.join(map(str, version(plugin_root))) or 'no version'}, older than the "
                      f"running {'.'.join(map(str, running))}: nothing older installs")
    wanted = package_hash(plugin_root)
    if wanted != current_hash():
        release = home / "releases" / wanted
        if not release.is_dir():
            staging = home / "releases" / f".{wanted}.{os.getpid()}"
            shutil.copytree(plugin_root / "synthesis", staging / "synthesis",
                            ignore=shutil.ignore_patterns("__pycache__"))
            for rel, path in _stable_skill_files(plugin_root):
                (staging / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, staging / rel)
            (staging / "HASH").write_text(wanted + "\n", encoding="utf-8")
            if (plugin_root / "CHANGELOG.md").is_file():  # the upgrade note quotes it to running sessions
                shutil.copy2(plugin_root / "CHANGELOG.md", staging / "CHANGELOG.md")
            (staging / "SOURCE").write_text(f"{plugin_root}\n{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n", encoding="utf-8")
            wrong = _differences(staging, expected) if expected is not None else []
            if wrong:
                shutil.rmtree(staging, ignore_errors=True)
                raise Refused(f"the staged runtime is not the release's bytes ({'; '.join(wrong[:4])}), so current did not move")
            os.replace(staging, release)
        elif expected is not None and _differences(release, expected):
            raise Refused(f"{release} is not the release's bytes ({'; '.join(_differences(release, expected)[:4])}), "
                          "so current did not move")
        link = home / f".current.{os.getpid()}"
        link.symlink_to(release)
        os.replace(link, home / "current")  # atomic switch: a running hook sees old or new, never neither
    python = pinned_python()
    for name in (*ENTRY_POINTS, *GIT_HOOKS):  # before compiling: the compile runs the interpreter the hook launcher names
        _write_exec(home / ("git-hooks" if name in GIT_HOOKS else "bin") / name, launcher(home, python, name))
    _compile(home / "current" / "synthesis")
    copies = {}
    for name in DAY_END:
        source = plugin_root / "skills" / "synthesis-daily-rituals" / "scripts" / name
        if source.is_file():
            copies[name] = source.read_text(encoding="utf-8")
            _write_exec(home / "bin" / name, copies[name])
    record = _registrations(home)
    if copies and record.get("copies") != {n: _sha(v) for n, v in copies.items()}:  # so uninstall can tell edits
        record["copies"] = {n: _sha(v) for n, v in copies.items()}
        (home / "registrations.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    config = home / "config.json"
    if not config.exists():
        config.write_text("{}\n", encoding="utf-8")
    return f"synthesis runtime {wanted} at {home / 'current'}"


def move_board(home: Path) -> list:
    """The board lives in board/ since 5.1.18: the one folder a sandboxed agent may write (Codex's writable root),
    so approvals and send windows stay out of its reach. What a release before wrote into state/ (all of it the
    first time; later, anything a process still on it wrote) is merged in by every install and by the first hook
    that finds it, because the older release's own session-start hook can switch to this one without moving
    anything. Free names move; a session in both places keeps both copies' claims; a log's lines are appended;
    any other copy already in board/ wins and the old one goes to the archive. Nothing is deleted."""
    stamp, moved = time.strftime("%Y%m%dT%H%M%S"), []
    for name in paths.BOARD_FILES:
        old = home / "state" / name
        if os.path.lexists(old):
            _merge(old, home / "board" / name, home / "archive" / f"board-{stamp}" / name)
            moved.append(name)
    return moved


def _merge(old: Path, new: Path, archive: Path) -> None:
    if not os.path.lexists(new):
        new.parent.mkdir(parents=True, exist_ok=True)
        os.rename(old, new)
        return
    if old.is_dir() and not old.is_symlink():
        for child in sorted(old.iterdir()):
            _merge(child, new / child.name, archive / child.name)
        old.rmdir()
        return
    if old.suffix == ".jsonl":
        with new.open("a", encoding="utf-8") as log:
            log.write(old.read_text(encoding="utf-8"))
    elif old.suffix == ".json" and new.parent.name == "sessions":
        a, b = paths.read_json(old), paths.read_json(new)
        newer, older = (b, a) if b.get("seen", 0) >= a.get("seen", 0) else (a, b)
        merged = {**older, **{k: v for k, v in newer.items() if v}}  # a fresh copy's empty field never erases a set one
        merged["started"] = min([s for s in (a.get("started"), b.get("started")) if s] or [0])
        for key in ("claims", "ceded"):  # a claim in either copy is kept: over-claiming blocks, under-claiming collides
            merged[key] = sorted(set(a.get(key) or []) | set(b.get(key) or []))
        paths.write_json(new, merged)
    archive.parent.mkdir(parents=True, exist_ok=True)
    os.rename(old, archive)


# ---- a LaunchAgent's own command: the setup asks before it replaces or removes a schedule, the doctor before it calls one healthy ----

def scheduled(plist: Path) -> list:
    """The program of each command a schedule runs, in order: the job's `Program` where it names one, else the first
    word of its arguments, or of each command on the line it hands a login shell. Nothing for a file that cannot be
    read, is cut short, is of another shape or runs no command."""
    import plistlib
    import shlex
    try:
        job = plistlib.loads(plist.read_bytes())
        args = [job["Program"]] if "Program" in job else job["ProgramArguments"]  # launchd runs `Program` when a job names one
        if not (isinstance(args, list) and len(args) == 3 and args[:2] == ["/bin/bash", "-lc"]):
            return args[:1] if isinstance(args, list) else []  # no shell line: the program is the first word
        words = shlex.shlex(args[2].replace("\n", ";"), posix=True, punctuation_chars=True)
        words.whitespace_split, words.commenters = True, ""  # split as a shell does: `#` and `-` stay in their word
        commands = [[]]
        for word in words:
            if word and not word.strip(words.punctuation_chars):  # `;`, `&&` and `|` end a command
                commands.append([])
            else:
                commands[-1].append(word)
        return [" ".join((c[1:] if c[0] == "exec" else c)[:1]) for c in commands if c and c[0] != "export"]  # `export` runs nothing
    except Exception:  # cut short, or of another shape
        return []


def runs_only(plist: Path, target: Path) -> bool:
    """Whether a schedule is this install's: the program of every command its line runs is `target`, the whole path.
    One whose command only ends like that path, or hands it to another program as a word, is another's, and so is a
    file that cannot be read (2026-11-12, a second review: a schedule running `echo <target>` was unloaded and
    removed, and the doctor answered ok for a loaded schedule that ran another install's command)."""
    programs = scheduled(plist)
    return bool(programs) and all(program == str(target) for program in programs)


# ---- owned registrations: the global git hooks path, recorded so uninstall can restore it ----

def _git_global(*args):
    return subprocess.run(["git", "config", "--global", *args], capture_output=True, text=True,
                          timeout=15, stdin=subprocess.DEVNULL)


def hooks_path_values() -> list:
    found = _git_global("--get-all", "core.hooksPath")
    if found.returncode not in (0, 1):  # 1 means unset
        raise RuntimeError(f"cannot read the global core.hooksPath: {found.stderr.strip()}")
    return [v for v in found.stdout.splitlines() if v]


def _set_hooks_path(values: list) -> None:
    unset = _git_global("--unset-all", "core.hooksPath")
    if unset.returncode not in (0, 5):  # 5 means it was not set
        raise RuntimeError(f"cannot change core.hooksPath: {unset.stderr.strip()}")
    for value in values:
        if _git_global("--add", "core.hooksPath", value).returncode:
            raise RuntimeError(f"cannot set core.hooksPath to {value}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _registrations(home: Path) -> dict:
    return paths.read_json(home / "registrations.json")


def register_git_hooks(home: Path = None) -> str:
    """Point the global core.hooksPath at the v5 commit check, recording the value it replaces."""
    home = home or _home()
    target = str(home / "git-hooks")
    before = hooks_path_values()
    if before == [target]:
        return f"core.hooksPath already {target}"
    record = _registrations(home)
    if "git_hooks_path" not in record:  # the value from before our first install is the one to restore
        record["git_hooks_path"] = {"before": before, "installed": target}
        (home / "registrations.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    _set_hooks_path([target])
    note = f" (was {', '.join(before)}: git no longer runs hooks from there)" if before else ""
    return f"core.hooksPath -> {target}{note}"


def _owned_files(home: Path) -> list:
    """(path, sha256 of what install wrote) for every file install owns."""
    python = pinned(home)
    files = [(home / "bin" / name, _sha(launcher(home, python, name))) for name in ENTRY_POINTS]
    files += [(home / "bin" / name, sha) for name, sha in (_registrations(home).get("copies") or {}).items()]
    return files + [(home / "git-hooks" / name, _sha(launcher(home, python, name))) for name in GIT_HOOKS]


class InUse(Exception):
    """The runtime stays: something still runs it."""


def uninstall(home: Path = None, dry_run: bool = False, codex_cleared: bool = False) -> list:
    """Remove what install created; restore core.hooksPath; keep anything the user changed. Refuses (InUse), removing
    nothing, while Codex's own hooks.json runs the stable hook: its guard would then hold every guarded call in Codex,
    with nothing there to put the runtime back (review round 2 of 5.21.0). `codex_cleared`: the caller takes all of that
    out first (setup.py uninstall's dry run, which has left its own declarations in place)."""
    from synthesis import doctor
    running = {} if codex_cleared else doctor.codex_user_entries(paths.codex_home())[0]
    if running:
        raise InUse(f"Codex's own {paths.codex_home() / 'hooks.json'} runs the synthesis runtime for {', '.join(running)}, so "
                    "it stays: run setup.py uninstall, which takes out what setup declared there, or remove those hooks, "
                    "then this again; nothing was removed")
    home, report, (verb, kept) = home or _home(), [], ("would remove", "would keep") if dry_run else ("removed", "kept")
    registered = _registrations(home).get("git_hooks_path")
    if registered:
        now = hooks_path_values()
        if now != [registered["installed"]]:
            report.append(f"{kept} core.hooksPath {now or 'unset'}: it changed since install")
        else:
            if not dry_run:
                _set_hooks_path(registered["before"])
            report.append(f"{'would restore' if dry_run else 'restored'} core.hooksPath to "
                          f"{', '.join(registered['before']) or 'unset'}")
    for path, sha in _owned_files(home):
        if path.is_file() and _sha(path.read_text(encoding="utf-8")) != sha:
            report.append(f"{kept} {path}: edited since install")
        elif path.is_file():
            if not dry_run:
                path.unlink()
            report.append(f"{verb} {path}")
    if (home / "current").is_symlink() and not dry_run:
        (home / "current").unlink()
    for release in sorted((home / "releases").glob("*")) if (home / "releases").is_dir() else []:
        if release.name.startswith(".") or package_hash(release) != release.name:
            report.append(f"{kept} {release}: its files changed since install")
            continue
        if not dry_run:
            shutil.rmtree(release)
        report.append(f"{verb} {release}")
    if (home / "registrations.json").exists() and not dry_run:
        (home / "registrations.json").unlink()
    report.append(f"{kept} {home / 'config.json'}, {home / 'state'} and {home / 'board'} (your settings, approvals and board)")
    return report


if __name__ == "__main__":  # the bootstrap hooks.json runs before the stable `synthesis` command exists
    from synthesis import cli
    sys.exit(cli.main(sys.argv[1:] if sys.argv[1:2] == ["uninstall"] else ["install", "--first", *sys.argv[1:]]))

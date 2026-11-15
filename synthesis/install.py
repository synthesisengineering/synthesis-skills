"""Install the v5 runtime at one stable path, and keep it current (R7.1, R7.5).

Hooks call ~/.synthesis/v5/bin/synthesis-hook, whose command text never
changes between releases, so a harness deleting an old plugin folder never
breaks a running task (Codex still asks for its hook approval again after each
release: it ties the approval to the installed plugin's contents). At each
session start the hook passes the plugin folder the harness loaded, the harness's
own plugin cache, which the guard does not protect: a session start installs from
it only into a home no runtime has been in (the first install), and never replaces
or reinstalls one (the principal's sandbox rulings of 2026-11-15). An explicit
install (setup, release, `synthesis install`, which waits for the principal's
code) installs whatever it is given, beside the old one, and `current` switches
atomically.

Run: python3 -S <plugin>/synthesis/install.py [plugin root] [--git-hooks]   (the bootstrap: a first install only)
     python3 -S <plugin>/synthesis/install.py uninstall [--dry-run]

`--git-hooks` points the global core.hooksPath at the v5 commit check after
recording the value it replaces; uninstall restores that value unless the user
changed it since, and removes only files install wrote that are still unedited.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import paths  # noqa: E402

HOOK_SCRIPT = """#!/bin/sh
# Stable entry for every synthesis hook. Its text never changes between releases.
d=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -S "$d/current/synthesis/hook.py" "$@"
"""
GIT_HOOK_SCRIPT = """#!/bin/sh
# Global git hook (core.hooksPath): the synthesis commit check, then the repository's own hook.
d=$(cd "$(dirname "$0")/.." && pwd)
SYNTHESIS_GIT_HOOK=$(basename "$0") exec python3 -S "$d/current/synthesis/commit_check.py" "$@"
"""
GIT_HOOKS = ("pre-commit", "pre-merge-commit", "commit-msg")
DAY_END = ("day-end", "day-end-nudge.sh")  # the rituals' launcher and nudge ride every release into bin/
# Scripts run outside a session (scheduled sweeps, autopilot wakes and backstops) need a stable path too.
STABLE_SKILL_SCRIPTS = ("synthesis-inbox-cleanup", "synthesis-autopilot", "synthesis-promotion-gate", "synthesis-daily-rituals",
                        "synthesis-chief-of-staff",  # the holds ledger's reader, which the same-day guard asks
                        "synthesis-kb-edit")  # the phrase scan a knowledge base's own git hooks run (sharing-standard.md)
CLI_SCRIPT = """#!/bin/sh
exec python3 -c 'import os, sys; sys.path[0] = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv.pop(1)))), "current"); from synthesis.cli import main; sys.exit(main())' "$0" "$@"
"""  # through a link (~/.local/bin/synthesis) and from any folder: the runtime, not a checkout in the working directory


def _home() -> Path:
    return paths.home()


def _files(root: Path) -> list:
    """(relative path, file) for every file an install copies, in order: every file in the runtime package and the folders
    in it (compiled code and hidden names left out, a link to a folder not followed), the stable skill scripts and the
    CHANGELOG. Each is hashed and copied (review round 1 of 22.18, H2: a package folder added to `synthesis/` was copied
    and not hashed)."""
    root, found = Path(root), []
    for folder, dirs, names in os.walk(root / "synthesis"):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__" and not d.startswith("."))
        found += [(Path(folder, n).relative_to(root).as_posix(), Path(folder, n)) for n in sorted(names) if not n.startswith(".")]
    return found + list(_stable_skill_files(root)) + [("CHANGELOG.md", root / "CHANGELOG.md")] * (root / "CHANGELOG.md").is_file()


def _read(path: Path) -> bytes:
    """A regular file's bytes, opened without waiting; OSError for anything else, so a FIFO stops no install or guard."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"{path} is not a regular file")
        chunks = [os.read(fd, 1 << 20)]
        while chunks[-1]:
            chunks.append(os.read(fd, 1 << 20))
        return b"".join(chunks)
    finally:
        os.close(fd)


def package_digest(plugin_root: Path) -> str:
    """The sha256 of every file an install copies, each by its relative path and its length: what the principal's code for
    an install binds and, cut to 16 characters, the release's name."""
    digest = hashlib.sha256()
    for rel, path in _files(plugin_root):
        data = _read(path)
        digest.update(f"{rel}\0{len(data)}\0".encode() + data)
    return digest.hexdigest()


def package_hash(plugin_root: Path) -> str:
    return package_digest(plugin_root)[:16]


class Unapproved(Exception):
    """A change of an installed runtime the principal's code does not approve; the message says how it is approved."""


def subject(action: str, home, digest: str = "", git_hooks: bool = False, versions: tuple = ("", "")) -> dict:
    """What the principal's code for a change of the runtime binds: the change ("install", "rollback" for a release older
    than the running one, named to him as a downgrade, or "uninstall"), the home, every byte the install takes (the
    digest of its staged copy), whether git's hooks follow, and the versions it goes from and to. The hook asks for it;
    the install or uninstall itself spends it."""
    return {"action": action, "home": os.path.realpath(home), "digest": digest, "git_hooks": bool(git_hooks),
            "from": versions[0], "to": versions[1]}


def change(home, staged: Path, source, digest: str, git_hooks: bool = False) -> tuple:
    """(the subject, the words for the principal) of installing a staged copy (or a folder, for the hook) into a home."""
    have, take = version(Path(home) / "current"), version(staged)
    back = bool(have and take and take < have)
    said = (f"rolls the synthesis runtime under {home} back from {'.'.join(map(str, have))} to {'.'.join(map(str, take))}, a "
            f"downgrade, installing from {source}" if back else f"installs a synthesis runtime from {source} into {home}")
    return (subject("rollback" if back else "install", home, digest, git_hooks, (".".join(map(str, have)), ".".join(map(str, take)))),
            said + (", and points git's global hooks at its commit check" if git_hooks else ""))


RELEASE_TOOL = os.path.join("skills", "synthesis-skills-manager", "scripts", "release.py")


def release_route() -> bool:
    """Whether this process is the release tool running from the protected runtime: its main program is that tool inside
    a release under this home, started isolated (-I -S, as the release launcher starts it), so no code of an agent's runs
    in it. Its install of a fresh clone's merged tag needs no code (the principal's ruling of 2026-11-15); a rollback
    still does. An agent's program is never this route: it is not that file, and that file started any other way, or
    imported by a program, is not the process's isolated main program."""
    import __main__
    main = os.path.realpath(getattr(__main__, "__file__", "") or os.devnull)
    return bool(sys.flags.isolated and sys.flags.no_site) and main.endswith(os.sep + RELEASE_TOOL) and paths.inside(
        main, os.path.realpath(_home() / "releases"))


def approval(wanted: dict, said: str, session: dict | None) -> None:
    """Spend the principal's code for this change of an installed runtime, or file the request and raise Unapproved with
    what the hook says, so the change waits however the CLI was started (review round 1 of 22.18, H1). Where no runtime
    ran the prompt hook to make a grant, the session's own record showing the code typed after the request is enough."""
    from synthesis import approvals
    try:
        if approvals.consume("runtime", wanted, session) or approvals.answered("runtime", wanted, session):
            return
    except approvals.Unverified as exc:
        raise Unapproved(str(exc)) from None
    code = approvals.request("runtime", wanted, f"the synthesis runtime: {said[:150]}")
    raise Unapproved(f"This {said}. That runtime is what the guard runs, so it changes only on the principal's word: show "
                     f"them this exact install and ask them to type {approvals.how(code)}; then run the identical command "
                     "again, with the folder it installs from left as it is now." + ("" if paths.session_id(session) else
                     " This shell names no session: pass --session with the one the principal types it in."))


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


def _compiled(package: Path) -> bool:
    """Whether this interpreter would load every module of the runtime from compiled code: a compiled file for each,
    where it looks for one, made from the source that is there now."""
    from importlib import util
    try:
        for source in package.glob("*.py"):
            cached = Path(util.cache_from_source(str(source))).read_bytes()
            if cached[:4] != util.MAGIC_NUMBER or not cached[4] & 1 or cached[8:16] != util.source_hash(source.read_bytes()):
                return False
    except (OSError, NotImplementedError):
        return False
    return True


def _compile(package: Path) -> None:
    """Compiles the runtime once, for the interpreter that installs: beside its source, or under the folder that
    interpreter keeps compiled code in (Apple's Python has one, keyed by the path through `current`). A hook is a new
    process on every tool call, and a caller told to write no bytecode caches nothing it compiles: the guards were
    compiled from their source each time, 72 ms for a shell command's check where 33 ms is what it takes (2026-11-12).
    Each compiled file carries its source's hash and is checked against it when loaded, since by date and size a file
    of the next release could pass for the one before it. A runtime already compiled is left as it is. Nothing here
    stops an install: whatever goes wrong leaves the runtime as it was, slower and whole."""
    import compileall
    import py_compile
    try:
        if not _compiled(package):
            compileall.compile_dir(str(package), maxlevels=0, quiet=2,
                                   invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
    except Exception:
        pass


TRACES = ("releases", "current", "bin", "git-hooks", "state", "board", "sessions")


def traces(home: Path) -> list:
    """What in a synthesis home shows a runtime was installed there: its own folders, or the state, board or archive its
    sessions wrote. Uninstall keeps the state, the board and the archive, and the guard refuses to remove them, so a home
    a runtime has left, by uninstall or by any other route, still shows it (review round 2 of 5.23.1, N6)."""
    return [name for name in TRACES if os.path.lexists(Path(home) / name)]


def _stage(plugin_root: Path, home: Path) -> Path:
    """A copy of every file an install takes, made in the protected releases folder, where no agent writes: what is
    hashed, checked and installed is this copy, never the folder as it stands a moment later (review round 1 of 22.18)."""
    import secrets
    staging = home / "releases" / f".stage.{os.getpid()}.{secrets.token_hex(4)}"
    try:
        for rel, path in _files(plugin_root):
            (staging / rel).parent.mkdir(parents=True, exist_ok=True)
            (staging / rel).write_bytes(_read(path))
            (staging / rel).chmod(stat.S_IMODE(os.stat(path).st_mode) | 0o600)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def install(plugin_root: Path, first_only: bool = False, git_hooks: bool = False, session: dict | None = None) -> str:
    """Install the plugin's runtime if it differs from the current one, from a copy staged and hashed under the home's
    protected releases folder. Returns a one-line report.

    first_only (the session-start hook and the first-install bootstrap): install only into a home no runtime has been
    in. The folder a harness passes is its own plugin cache, which the guard does not protect, so an installed runtime,
    or one that was removed, is never replaced from it (the principal's sandbox rulings of 2026-11-15). A home that
    shows a runtime but has none whole is refused (RuntimeError), loudly, rather than kept. Into a home that shows a
    runtime, every other install spends the principal's code for exactly the staged copy, or raises Unapproved and
    nothing moves, whoever calls it (review round 4 of 5.23.1, Q4): the release tool's own install from the protected
    runtime (release_route) needs none unless it rolls back. git_hooks binds that the caller points git's hooks at it."""
    plugin_root = Path(plugin_root).resolve()
    if not (plugin_root / "synthesis" / "hook.py").is_file():
        return f"not a synthesis plugin: {plugin_root}"
    home = _home()
    found = traces(home)
    try:
        move_board(home)  # before any switch, so the new release's first read finds the board in place
    except OSError as exc:  # never blocks a session start; the doctor names what is left in state/
        print(f"synthesis: the board could not be moved out of {home / 'state'}: {exc}", file=sys.stderr)
    if first_only and found and current_hash() and os.access(home / "bin" / "synthesis-hook", os.X_OK):
        _compile(home / "current" / "synthesis")  # an older release's installer made the switch, or the interpreter changed
        return f"synthesis runtime kept at {current_hash()}: a session start installs only into a home no runtime has been in"
    if first_only and found:
        raise RuntimeError(f"{home} holds {', '.join(found)}, left by a runtime installed there, so a session start does not "
                           f"install one from {plugin_root}, the harness's own folder. Install it from your own terminal: "
                           "setup.py, or `synthesis install` with no folder where the runtime is still there")
    staging = _stage(plugin_root, home)
    try:
        digest = package_digest(staging)
        wanted = digest[:16]
        if found:
            wanted_change, said = change(home, staging, plugin_root, digest, git_hooks)
            if wanted_change["action"] == "rollback" or not release_route():
                approval(wanted_change, said, session or {"session_id": paths.session_id()})
        release = home / "releases" / wanted
        if wanted != current_hash():
            if not release.is_dir():
                (staging / "HASH").write_text(wanted + "\n", encoding="utf-8")
                (staging / "SOURCE").write_text(f"{plugin_root}\n{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n", encoding="utf-8")
                os.replace(staging, release)
            link = home / f".current.{os.getpid()}"
            link.symlink_to(release)
            os.replace(link, home / "current")  # atomic switch: a running hook sees old or new, never neither
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    _compile(home / "current" / "synthesis")
    _write_exec(home / "bin" / "synthesis-hook", HOOK_SCRIPT)
    _write_exec(home / "bin" / "synthesis", CLI_SCRIPT)
    for name in GIT_HOOKS:
        _write_exec(home / "git-hooks" / name, GIT_HOOK_SCRIPT)
    copies = {}
    for name in DAY_END:  # from the release as installed, never from the folder after its check
        source = Path(os.path.realpath(home / "current")) / "skills" / "synthesis-daily-rituals" / "scripts" / name
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
    files = [(home / "bin" / "synthesis-hook", _sha(HOOK_SCRIPT)), (home / "bin" / "synthesis", _sha(CLI_SCRIPT))]
    files += [(home / "bin" / name, sha) for name, sha in (_registrations(home).get("copies") or {}).items()]
    return files + [(home / "git-hooks" / name, _sha(GIT_HOOK_SCRIPT)) for name in GIT_HOOKS]


class InUse(Exception):
    """The runtime stays: something still runs it."""


def uninstall(home: Path = None, dry_run: bool = False, codex_cleared: bool = False, session: dict | None = None) -> list:
    """Remove what install created; restore core.hooksPath; keep anything the user changed. Refuses (InUse), removing
    nothing, while Codex's own hooks.json runs the stable hook: its guard would then hold every guarded call in Codex,
    with nothing there to put the runtime back (review round 2 of 5.21.0). `codex_cleared`: the caller takes all of that
    out first (setup.py uninstall's dry run, which has left its own declarations in place). Where the home shows a
    runtime, a removal spends the principal's code for it, or raises Unapproved and nothing is removed, whoever calls it."""
    from synthesis import doctor
    running = {} if codex_cleared else doctor.codex_user_entries(paths.codex_home())[0]
    if running:
        raise InUse(f"Codex's own {paths.codex_home() / 'hooks.json'} runs the synthesis runtime for {', '.join(running)}, so "
                    "it stays: run setup.py uninstall, which takes out what setup declared there, or remove those hooks, "
                    "then this again; nothing was removed")
    if not dry_run and traces(home or _home()):
        approval(subject("uninstall", home or _home()), f"removes the installed synthesis runtime under {home or _home()} "
                 "(`current`, its launchers and its releases)", session or {"session_id": paths.session_id()})
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
        try:
            whole = not release.name.startswith(".") and package_hash(release) == release.name
        except OSError:  # a file in it that is no regular file, or cannot be read
            whole = False
        if not whole:
            report.append(f"{kept} {release}: its files do not hash to its name (changed since install, or named by an older install)")
            continue
        if not dry_run:
            shutil.rmtree(release)
        report.append(f"{verb} {release}")
    if (home / "registrations.json").exists() and not dry_run:
        (home / "registrations.json").unlink()
    report.append(f"{kept} {home / 'config.json'}, {home / 'state'} and {home / 'board'} (your settings, approvals and board); "
                  "with them there no session start installs a runtime here again, so a harness that still has the plugin "
                  "holds every guarded call until setup.py installs one")
    return report


if __name__ == "__main__":  # the bootstrap hooks.json runs before the stable `synthesis` command exists: a first install only
    from synthesis import cli
    sys.exit(cli.main(sys.argv[1:] if sys.argv[1:2] == ["uninstall"] else ["install", "--first", *sys.argv[1:]]))

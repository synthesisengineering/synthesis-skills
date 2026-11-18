"""The guard's sandbox (design note 22.9, 4.1 to 4.3 and 4.8; the principal's rulings of 2026-11-15): what no agent's
shell may write, the two administrator files that make each harness's own sandbox hold it, and the probes that show it
does. Setup stages the files in the synthesis home and prints the one command that installs each; the principal runs it
with his password; the doctor reads them back. Nothing here installs a file, and a probe removes what it made.
"""

from __future__ import annotations

import errno
import json
import os
import plistlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from synthesis import paths

CLAUDE_MANAGED = Path("/Library/Application Support/ClaudeCode/managed-settings.json" if sys.platform == "darwin"
                      else "/etc/claude-code/managed-settings.json")  # Claude Code's own page on managed settings
CODEX_REQUIREMENTS = Path("/etc/codex/requirements.toml")  # Codex's own page: "on Unix systems, including Linux and macOS"
OUTRANKING = {"claude": Path("/Library/Managed Preferences/com.anthropic.claudecode.plist"),  # an MDM profile, read first
              "codex": Path("/Library/Managed Preferences/com.openai.codex.plist")}
PROFILE = "synthesis-sealed"  # the requirements' own profile: one named as config.toml's conflicts with it (Codex 0.169)
ROOT_GROUP = "wheel" if sys.platform == "darwin" else "root"
SETUP = "python3 <synthesis-onboarding>/scripts/setup.py"
LABELS = {"claude": "Claude Code's managed settings", "codex": "Codex's requirements"}

# The sealed set as the design note's 4.1 lays out the synthesis home: the one list the two files, the doctor and the
# probes read, so the folder move changes it here and nowhere else. A name with a dot is a file.
APPROVALS = "approvals"
SEALED = (APPROVALS, "install", "releases", "current", "bin", "git-hooks", "config.json", "sessions")
WRITABLE = ("board", "outbox", "state/requests")  # what a sandboxed agent writes in the synthesis home
STAGED = "install"  # where setup stages the two files: sealed, so no session changes one before it is installed
WRITE_AREA = ("~/workspaces", "~/.Trash")  # Claude Code's beyond a session's own folders and temp (the ruling on D8)
ASK = "Bash(dangerouslyDisableSandbox:true)"  # the backstop to the guard's hold of an unsandboxed command (D2)
HOOK = '"$HOME/.synthesis/v5/bin/synthesis-hook"'
MATCHER = ("Bash|bash|exec_command|write_stdin|exec|shell|shell_command|local_shell|run_shell_command|Write|Edit|MultiEdit|"
           "NotebookEdit|write_file|edit_file|apply_patch|mcp__.*")


def tilde(path) -> str:
    """A path as a person writes it: ~ for the home folder."""
    text, home = str(path), str(Path.home()).rstrip("/")
    return "~" + text[len(home):] if text == home or text.startswith(home + "/") else text


def _harness() -> list:
    """(path, folder, sandbox only, records) for each harness's records, hook and sandbox settings, and programs (the
    note's 2.1). Claude Code's own records go to its sandbox alone, so its file tools keep the memory files the guard
    allows; `records` names a folder of session records."""
    roots, user, desktop, claude = paths.transcript_roots(), Path.home(), paths.desktop_dir(), paths.transcript_roots()["claude-code"].parent
    codex = paths.codex_home()
    return [(roots["claude-code"], True, True, "claude-code"), (desktop / "local-agent-mode-sessions", True, True, "desktop"),
            (desktop / "claude-code", True, True, ""), (claude / "settings.json", False, False, ""),
            (claude / "settings.local.json", False, False, ""), (claude / "plugins", True, False, ""),
            (roots["codex"], True, False, "codex"), (codex / "archived_sessions", True, False, "codex-archived"),
            (codex / "config.toml", False, False, ""), (codex / "hooks.json", False, False, ""), (codex / "plugins", True, False, ""),
            (roots["muse"], True, False, "muse"), (user / ".config" / "muse", True, False, ""),
            (user / "Library" / "LaunchAgents", True, False, ""), (user / ".local" / "share" / "claude", True, False, ""),
            (user / ".local" / "bin", True, False, "")]


def sealed() -> list:
    """(path, folder, sandbox only) for the whole trust base: the synthesis home's sealed parts, then the harnesses'."""
    return [(paths.home() / name, "." not in name, False) for name in SEALED] + [(p, f, s) for p, f, s, _ in _harness()]


def _rule(path) -> str:
    """A permission rule's path: ~/ under the home folder, else // before an absolute one (a single / is the settings
    file's own folder there, where a sandbox path reads it as the root)."""
    text = tilde(path)
    return text if text.startswith("~") else "/" + text


def claude_managed() -> dict:
    """Claude Code's managed settings (the note's 4.2): the sandbox on, never off for want of one, the write area the
    ruling on D8 set, and every sealed path denied to the file tools and the shell alike, apart from Claude Code's own
    records, which only the shell is denied."""
    return {"sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": True,
                        "filesystem": {"allowWrite": list(WRITE_AREA), "denyWrite": [tilde(p) for p, _, only in sealed() if only]}},
            "permissions": {"deny": [f"Edit({_rule(p)}{'/**' if folder else ''})" for p, folder, only in sealed() if not only],
                            "ask": [ASK]}}


def codex_rules() -> list:
    """(folder, access) for Codex's profile (the note's 4.3): the folders a session writes, the synthesis home's parent
    read-only so no ancestor of a sealed folder can be renamed away, the approval records stated again, and each
    harness's own folders read-only."""
    home, user, roots = paths.home(), Path.home(), paths.transcript_roots()
    above = home.parent if home.parent not in (user, Path(home.anchor)) else home
    harness = [roots["claude-code"].parent, paths.codex_home(), roots["muse"].parent, user / ".config" / "muse",
               user / "Library" / "LaunchAgents", paths.desktop_dir(), user / ".local" / "share" / "claude", user / ".local" / "bin"]
    return [(home / w, "write") for w in WRITABLE] + [(above, "read"), (home / APPROVALS, "read")] + [(p, "read") for p in harness]


def managed_hooks() -> dict:
    """{event: groups}: the plugin's hooks as Codex runs them, its user-level declaration of hooks/hooks.json without
    Claude Code's onFailure. Written here because the runtime carries no hooks.json; a test holds the two equal."""
    def plain(arg, seconds):
        return [{"hooks": [{"type": "command", "command": f"{HOOK} {arg}", "timeout": seconds}]}]
    guard = f'{HOOK} pre-tool-use || {{ echo "synthesis guard could not run, so the call is held: run synthesis doctor" >&2; exit 2; }}'
    return {"SessionStart": plain("session-start", 10), "UserPromptSubmit": plain("user-prompt-submit", 5),
            "PreToolUse": [{"matcher": MATCHER, "hooks": [{"type": "command", "command": guard, "timeout": 5}]}],
            "Stop": plain("stop", 10)}


def codex_requirements() -> str:
    """Codex's requirements.toml (the note's 4.3, with the ruling on D7): its own profile pinned and allowed by the table
    form (Codex ignores the older array), no full access, and the guard's hooks managed, the only hooks Codex runs."""
    rules = "".join(f'{json.dumps(tilde(p))} = "{access}"\n' for p, access in codex_rules())
    hooks = ""
    for event, groups in managed_hooks().items():
        for group in groups:
            hooks += f"\n[[hooks.{event}]]\n" + (f"matcher = {json.dumps(group['matcher'])}\n" if "matcher" in group else "")
            hooks += "".join(f"\n[[hooks.{event}.hooks]]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in h.items())
                             for h in group["hooks"])
    return ("# synthesis: the guard's sandbox in Codex (design note 22.9, 4.3). Setup stages this file, the principal\n"
            "# installs it with sudo, and `synthesis doctor` reads it back: change it in synthesis, never here.\n"
            f'default_permissions = "{PROFILE}"\nallowed_sandbox_modes = ["read-only", "workspace-write"]\n'
            f'allow_managed_hooks_only = true\n\n[allowed_permission_profiles]\n"{PROFILE}" = true\n":read-only" = true\n\n'
            f'[permissions.{PROFILE}]\nextends = ":workspace"\n\n[permissions.{PROFILE}.filesystem]\n{rules}\n'
            f"[features]\nhooks = true\n{hooks}")


def expected(name: str) -> str:
    return json.dumps(claude_managed(), indent=2) + "\n" if name == "claude" else codex_requirements()


def target(name: str) -> Path:
    return CLAUDE_MANAGED if name == "claude" else CODEX_REQUIREMENTS


def staged(name: str) -> Path:
    return paths.home() / STAGED / target(name).name


def install_command(name: str) -> str:
    """The one command the principal types: the staged file copied into place, owned by root and read by everyone."""
    there, copy = target(name), staged(name)
    return (f"sudo install -d -o root -g {ROOT_GROUP} -m 755 {shlex.quote(str(there.parent))} && "
            f"sudo install -o root -g {ROOT_GROUP} -m 644 {shlex.quote(str(copy))} {shlex.quote(str(there))}")


def admin_problems(path) -> list:
    """Why an installed file is no seal, each with its one step: it and every folder above it must be root's, and
    writable by neither this user nor its groups, as the hooks' interpreter must be."""
    found, spot = [], os.path.realpath(path)
    while True:
        try:
            owner = os.lstat(spot).st_uid
        except OSError as exc:
            return found + [f"{spot} cannot be read ({exc.strerror})"]
        if owner:
            found.append(f"{spot} is not owned by root; to fix it, run `sudo chown root:{ROOT_GROUP} {shlex.quote(spot)}`")
        elif os.access(spot, os.W_OK):
            found.append(f"{spot} can be written by this user or its groups; to fix it, run `sudo chmod go-w {shlex.quote(spot)}`")
        if spot == os.path.dirname(spot):
            return found
        spot = os.path.dirname(spot)


def _same(name: str, text: str, want: str) -> bool:
    if name == "codex":
        return text.replace("\r\n", "\n") == want
    try:
        return json.loads(text) == json.loads(want)
    except ValueError:
        return False


def _outranked(name: str, there: Path) -> list:
    """A source the harness reads in place of the file (an MDM profile) or merges over it (Claude Code's drop-ins)."""
    found, mdm, user = [], OUTRANKING.get(name), os.environ.get("USER", "")
    for plist in [mdm, mdm.parent / user / mdm.name] if mdm and user else [mdm] if mdm else []:
        try:
            data = plistlib.loads(plist.read_bytes())
        except (OSError, ValueError):
            continue
        if (name == "claude" and data) or (isinstance(data, dict) and "requirements_toml_base64" in data):
            found.append(f"an MDM profile ({plist}) ranks above {there}, so {'Claude Code ignores the file' if name == 'claude' else 'Codex reads its requirements first'}: "
                         "deliver these settings through that profile, or remove it")
    for drop in sorted((there.parent / "managed-settings.d").glob("*.json")) if name == "claude" else []:
        try:
            data = json.loads(drop.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if drop.name[:1] != "." and (not isinstance(data, dict) or {"sandbox", "permissions"} & set(data)):
            found.append(f"{drop} is merged over {there} and may change its sandbox or permissions: take those keys out of it")
    return found


def judge(name: str) -> tuple:
    """(state, problems) of one administrator file: "installed", "staged" or "off", and each problem with its one step."""
    label, there, copy, want = LABELS[name], target(name), staged(name), expected(name)
    if os.path.lexists(there):
        try:
            text = there.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            return "installed", [f"{label} at {there} cannot be read ({exc}): run `{install_command(name)}`"]
        problems = [f"{label}: {p}" for p in admin_problems(there)[:2]]
        if not _same(name, text, want):
            problems.append(f"{label} at {there} is not what this release stages: run `{SETUP} sandbox`, then `{install_command(name)}`")
        return "installed", problems + _outranked(name, there)
    try:
        held = copy.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return "off", [f"{label} is neither staged nor installed: run `{SETUP} sandbox`, which prints the command that installs it"]
    if not _same(name, held, want):
        return "staged", [f"{label} staged in {tilde(copy)} is out of date: run `{SETUP} sandbox`, which prints the command that installs it"]
    return "staged", [f"{label} is staged, not installed: run `{install_command(name)}`"]


def managed_hooks_hold() -> bool:
    """Whether Codex runs the guard as managed hooks, and only those: its requirements installed and holding the keys."""
    return judge("codex") == ("installed", [])


def profile_rules(config: dict) -> tuple:
    """({a folder as it really is: its access}, the built-in profile the chain ends in) for the profile Codex's
    config.toml selects, through `extends`; the nearest profile's rule for a folder wins."""
    name, found, seen = config.get("default_permissions") or ":workspace", {}, set()
    while isinstance(name, str) and not name.startswith(":") and name not in seen:
        seen.add(name)
        profile = (config.get("permissions") or {}).get(name)
        profile = profile if isinstance(profile, dict) else {}
        for path, access in (profile.get("filesystem") if isinstance(profile.get("filesystem"), dict) else {}).items():
            if not path.startswith(":") and isinstance(access, str):
                found.setdefault(os.path.realpath(os.path.expanduser(path)), access)
        name = profile.get("extends")
    return found, name


def holds(found, access: str) -> bool:
    """Whether a profile's rule keeps a folder as the seal needs: written where a session writes, else never written."""
    return found == "write" if access == "write" else found in ("read", "deny")


def profile_problems(config: dict) -> list:
    """Why the profile Codex's config.toml selects does not keep the sealed set, with the one step: [] where it does."""
    if config.get("sandbox_mode") is not None:
        return ["Codex's config.toml sets sandbox_mode, so Codex reads its older sandbox settings, which cannot keep a "
                "folder read-only: take sandbox_mode out, so Codex reads the profile setup writes"]
    rules, base = profile_rules(config)
    if base == ":danger-full-access":
        return ["Codex runs without a sandbox (:danger-full-access), so its shells write everything the guard trusts: "
                f"choose another profile, then run `{SETUP} plugin`"]
    missing = [tilde(p) for p, access in codex_rules() if not holds(rules.get(os.path.realpath(p)), access)]
    return [f"Codex's profile does not keep {', '.join(missing[:4])}{' and more' if len(missing) > 4 else ''} as the "
            f"seal needs (read-only, apart from the folders a session writes): run `{SETUP} plugin`"] if missing else []


def codex_config() -> dict:
    from synthesis import doctor
    try:
        return doctor.read_toml((paths.codex_home() / "config.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def in_sandbox():
    """True where this process runs inside the operating system's sandbox, False where it does not, None where that
    cannot be told (macOS answers through sandbox_check; elsewhere nothing simple does)."""
    if sys.platform != "darwin":
        return None
    try:
        import ctypes
        check = ctypes.CDLL("/usr/lib/system/libsystem_sandbox.dylib").sandbox_check
        check.restype, check.argtypes = ctypes.c_int, [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        return bool(check(os.getpid(), None, 0))
    except (OSError, AttributeError):
        return None


# ---- the probes: run from a session's shell, each write the seal must refuse (the note's 4.8) ------------------------
# Outcomes: "held" (the system refused it), "wrote" (it went through: the doctor fails loudly, and what the probe made is
# removed or put back at once), "unknown" (it could not tell why), "skipped" (not tried, and why).

HELD = {errno.EPERM: "EPERM", errno.EACCES: "EACCES", errno.EROFS: "EROFS"}  # Seatbelt says EPERM; Linux's say the others


def _refused(exc: OSError) -> tuple:
    return ("held" if exc.errno in HELD else "unknown"), errno.errorcode.get(exc.errno, str(exc.errno))


def _create(path: Path, made: list) -> tuple:
    """A new file at `path`, and each folder missing above it; each thing made is listed in `made` for removal."""
    missing, folder = [], path.parent
    while not os.path.lexists(folder):
        missing.append(folder)
        folder = folder.parent
    try:
        for folder in reversed(missing):
            os.mkdir(folder)
            made.append(folder)
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        made.append(path)
    except OSError as exc:
        return _refused(exc)
    return "wrote", f"made {tilde(path)}; removed"


def _append(path: Path, made: list) -> tuple:
    """An existing file opened to write, nothing written (what an overwrite needs first); a missing one made."""
    if not os.path.lexists(path):
        return _create(path, made)
    try:
        os.close(os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NONBLOCK))
    except OSError as exc:
        return _refused(exc)
    return "wrote", f"opened {tilde(path)} to write (nothing was written)"


def _rename(path: Path) -> tuple:
    """`path` moved aside and straight back."""
    if not os.path.lexists(path):
        return "unknown", f"{tilde(path)} is not there"
    aside = path.with_name(f"{path.name}.seal-probe-{os.getpid()}")
    try:
        os.rename(path, aside)
    except OSError as exc:
        return _refused(exc)
    try:
        os.rename(aside, path)
    except OSError as exc:
        return "wrote", f"moved {tilde(path)} to {tilde(aside)} and could not move it back ({exc.strerror}): do it from your own terminal"
    return "wrote", f"moved {tilde(path)} aside and back"


def _delete(path: Path, keep: Path) -> tuple:
    """A file deleted and put back; its bytes are copied to `keep`, outside the sealed set, before the delete is tried."""
    try:
        data, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
        keep.write_bytes(data)
    except OSError as exc:
        return "unknown", f"cannot copy {tilde(path)} first ({exc.strerror})"
    try:
        path.unlink()
    except OSError as exc:
        keep.unlink()
        return _refused(exc)
    try:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), "wb") as handle:
            handle.write(data)
        os.chmod(path, mode)
    except OSError as exc:
        return "wrote", f"deleted {tilde(path)} and could not put it back ({exc.strerror}): copy {keep} there from your own terminal"
    keep.unlink()
    return "wrote", f"deleted {tilde(path)} and put it back"


def _child(path: Path, made: list, background: bool) -> tuple:
    """A shell the probe starts writes the file; in the background, after that shell has gone."""
    script = '( sleep 0.2; : > "$1" ) &' if background else ': > "$1"'
    try:  # the run ends when the last process that holds its pipes does, the background one included
        done = subprocess.run(["/bin/sh", "-c", script, "seal-probe", str(path)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", str(exc)
    if os.path.lexists(path):
        made.append(path)
        return "wrote", f"a shell it started made {tilde(path)}; removed"
    said = " ".join((done.stderr or "").split())
    for words, code in (("not permitted", "EPERM"), ("Permission denied", "EACCES"), ("Read-only", "EROFS")):
        if words in said:
            return "held", code
    return "unknown", said[-160:] or f"exit {done.returncode}"


def _files(folder: Path) -> dict:
    return {str(p): p.read_bytes() for p in folder.rglob("*") if p.is_file() and not p.is_symlink()} if folder.is_dir() else {}


def _hook(home: Path, workspace: Path) -> tuple:
    """The hook run as a shell runs it, with a made-up prompt: one started from a sandboxed shell runs inside the sandbox,
    so it writes no record (the note's M5 route). Whatever it wrote is put back."""
    from synthesis import approvals
    hook, records = home / "bin" / "synthesis-hook", approvals._dir("transcripts")
    if not os.access(hook, os.X_OK):
        return "unknown", f"{tilde(hook)} is not there to run"
    had, before, session = records.is_dir(), _files(records), f"seal-probe-{os.getpid()}"
    payload = {"session_id": session, "transcript_path": str(workspace / f"{session}.jsonl"), "prompt": "approve 000000",
               "hook_event_name": "UserPromptSubmit", "cwd": str(workspace)}
    try:
        done = subprocess.run([str(hook), "user-prompt-submit"], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", f"the hook did not run ({exc})"
    after = _files(records)
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    left = []
    for path in changed:
        try:
            Path(path).write_bytes(before[path]) if path in before else os.unlink(path)
        except OSError:
            left.append(tilde(path))
    if not had and records.is_dir() and not any(records.iterdir()):
        records.rmdir()
    if changed:
        return "wrote", f"run with a made-up prompt, the hook wrote {len(changed)} record(s) in {tilde(records)}; " + (
            f"put {', '.join(left[:3])} back from your own terminal" if left else "put back")
    return "held", f"run with a made-up prompt, the hook wrote nothing in {tilde(records)} (exit {done.returncode})"


def _landed(marker: Path, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while not os.path.lexists(marker) and time.monotonic() < end:
        time.sleep(0.1)
    return os.path.lexists(marker)


def _broker(argv: list, marker: Path, run, seconds: float, after=None) -> tuple:
    """A service outside the sandbox asked to write the marker: what it ran is reported, and the marker removed."""
    try:
        done = run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", f"{argv[0]} did not run ({exc})"
    landed = _landed(marker, seconds if done.returncode == 0 else 0)
    if after:
        after()
    if landed:  # a process outside the sandbox made it, so this one may not be allowed to remove it
        return "wrote", f"`{' '.join(argv[:2])}` had a process outside the sandbox write {tilde(marker)}; " + (
            "removed" if not _remove([marker]) else "remove it from your own terminal, since this shell cannot")
    said = " ".join(((done.stderr or "") + (done.stdout or "")).split())[-160:]
    if done.returncode:
        return "held", f"{argv[0]} refused: {said or f'exit {done.returncode}'}"
    return "unknown", f"`{' '.join(argv[:2])}` was taken, and nothing reached {tilde(marker.parent)} within {seconds:g} s"


def probes(home: Path, workspace: Path, run=subprocess.run, platform: str = sys.platform, brokers: bool = True) -> list:
    """[(name, outcome, detail)] for each write the seal must refuse (the note's 4.8), tried from this process: in the
    approval records directly, by a shell, by a background child and through a link made in `workspace`; renames of the
    synthesis home and its parent; each harness's records, the runtime, the config and each settings file; the hook with
    a made-up prompt; and, on macOS, launchd and LaunchServices asked through `run`. Where the first write in the
    approval records goes through, the seal does not hold here, and nothing that moves a live folder or asks a broker
    is tried. Everything a probe made is removed, and anything it moved is put back at once."""
    tag, made, found, kept = f".seal-probe-{os.getpid()}", [], [], []
    approvals = home / APPROVALS
    try:
        found.append(("create in approvals", *_create(approvals / tag, made)))
        open_ = found[0][1] == "wrote"
        skip = ("skipped", f"not tried: this shell wrote {tilde(approvals)}, so the seal does not hold here, and the live folders stay put")
        entries = sorted(p for p in approvals.rglob("*") if ".seal-probe" not in p.name) if approvals.is_dir() else []
        files = [p for p in entries if p.is_file() and not p.is_symlink()]
        found.append(("overwrite in approvals", *(_append(files[0], made) if files else ("unknown", "no file in it to open"))))
        top = [p for p in entries if p.parent == approvals]
        found.append(("rename in approvals", *(skip if open_ else _rename(top[0]) if top else ("unknown", "nothing in it to move"))))
        held = found[-1][1] == "held"
        found.append(("delete in approvals", *(skip if open_ else ("skipped", "not tried: an entry of it moved, so the folder is "
                      "open already, and nothing in it is deleted") if not held else _delete(files[0], workspace / f"{tag}-copy")
                      if files else ("unknown", "no file in it to delete"))))
        found.append(("a shell's write", *_child(approvals / f"{tag}-sh", made, False)))
        found.append(("a background child's write", *_child(approvals / f"{tag}-bg", made, True)))
        link, mark = workspace / f"{tag}-link", len(made)
        try:
            os.symlink(approvals, link)
        except OSError as exc:
            found.append(("a write through a link", "unknown", f"cannot make a link in {tilde(workspace)} ({exc.strerror})"))
        else:
            try:
                found.append(("a write through a link", *_create(link / f"{tag}-link", made)))
            finally:
                kept += _remove(made, until=mark)  # what was made through the link goes while the link is there
                os.unlink(link)
        above = [(home, "rename the synthesis home")] + [(home.parent, "rename its parent")] * (home.parent not in (Path.home(), Path(home.anchor)))
        found += [(name, *(skip if open_ else _rename(path))) for path, name in above]
        found += [(f"records {rec}", *_create(path / tag, made)) for path, _, _, rec in _harness() if rec]
        found += [(name, *(_append(home / name, made) if "." in name else _create(home / name / tag, made))) for name in SEALED[1:]]
        found += [(f"write {tilde(path)}", *(_create(path / tag, made) if folder else _append(path, made)))
                  for path, folder, _, rec in _harness() if not rec]
        found.append(("the hook with a made-up prompt", *(skip if open_ else _hook(home, workspace))))
        script = workspace / f"{tag}.command"
        for name, argv, marker, seconds in (
                ("launchctl submit", ["launchctl", "submit", "-l", f"com.synthesis{tag}", "--", "/usr/bin/touch", str(approvals / f"{tag}-launchd")],
                 approvals / f"{tag}-launchd", 3.0),
                ("open -a", ["open", "-g", "-j", "-a", "Terminal", str(script)], approvals / f"{tag}-open", 5.0)):
            if open_ or not brokers or platform != "darwin":
                found.append((name, *(skip if open_ else ("skipped", "not asked: a broker outside the sandbox is macOS's"))))
                continue
            if name == "open -a":
                script.write_text(f"#!/bin/sh\n: > {shlex.quote(str(marker))}\n", encoding="utf-8")
                script.chmod(0o700)
            done = _broker(argv, marker, run, seconds, after=(lambda: run(["launchctl", "remove", argv[3]], capture_output=True,
                           text=True, timeout=30)) if name == "launchctl submit" else None)
            found.append((name, *done))
            if name == "open -a":
                script.unlink()
    finally:
        left = kept + _remove(made)
    return found + ([("removal", "wrote", f"could not remove {', '.join(left[:3])}: remove them from your own terminal")] if left else [])


def _remove(made: list, until: int = 0) -> list:
    """Remove what the probes made, the newest first; [] or what could not be removed."""
    left = []
    while len(made) > until:
        path = made.pop()
        try:
            os.rmdir(path) if os.path.isdir(path) and not os.path.islink(path) else os.unlink(path)
        except OSError:
            left.append(tilde(path))
    return left


# ---- outside a sandbox: the configuration that makes the seal (the note's 4.8) --------------------------------------

PATHLIKE = re.compile(r"""(?<![^\s'"=:(])(\$\{?\w+\}?|~)?(/[^\s'"`;|&<>()]*)""")


def _commands() -> list:
    """(where, command text, the plugin folder it names) for each hook, MCP server and launch agent: each runs with full
    access, outside every sandbox."""
    claude, codex, found = paths.transcript_roots()["claude-code"].parent, paths.codex_home(), []

    def hooks(file: Path, root=None):
        events = paths.read_json(file).get("hooks")
        for event, groups in events.items() if isinstance(events, dict) else ():
            for group in groups if isinstance(groups, list) else ():
                for hook in (group.get("hooks") or []) if isinstance(group, dict) else ():
                    if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                        found.append((f"{tilde(file)} {event}", hook["command"], root))
    for file in (claude / "settings.json", claude / "settings.local.json", codex / "hooks.json"):
        hooks(file)
    for file in sorted((claude / "plugins" / "cache").glob("*/*/*/hooks/hooks.json")):
        hooks(file, file.parent.parent)
    for file in dict.fromkeys([Path.home() / ".claude.json", claude / ".claude.json"]):
        data = paths.read_json(file)
        tables = [data.get("mcpServers")] + [p.get("mcpServers") for p in (data.get("projects") or {}).values() if isinstance(p, dict)]
        found += [(f"{tilde(file)} mcpServers.{name}", " ".join(map(str, [spec["command"], *(spec.get("args") or [])])), None)
                  for table in tables if isinstance(table, dict) for name, spec in table.items()
                  if isinstance(spec, dict) and isinstance(spec.get("command"), str)]
    from synthesis import doctor
    servers = codex_config().get("mcp_servers")
    found += [(f"{tilde(codex / 'config.toml')} mcp_servers.{name}", " ".join([spec["command"], *doctor.toml_strings(spec.get("args"))]), None)
              for name, spec in (servers.items() if isinstance(servers, dict) else ()) if isinstance(spec, dict) and isinstance(spec.get("command"), str)]
    for plist in sorted((Path.home() / "Library" / "LaunchAgents").glob("*.plist")):
        try:
            spec = plistlib.loads(plist.read_bytes())
        except (OSError, ValueError):
            continue
        argv = spec.get("ProgramArguments") or [spec.get("Program") or ""] if isinstance(spec, dict) else []
        found += [(tilde(plist), " ".join(map(str, argv)), None)] if isinstance(argv, list) else []
    return found


def _paths_in(text: str, root) -> list:
    """The files a command names: its program, found on PATH where it is a bare name, and each absolute path, with $HOME,
    ~ and the plugin's own folder expanded."""
    words = text.split()
    first = words[0].strip("'\"") if words else ""
    found = [shutil.which(first) or ""] if first and "/" not in first and not first.startswith("$") else []
    for var, rest in PATHLIKE.findall(text):
        name = var.strip("${}") if var.startswith("$") else var
        base = {"": "", "~": str(Path.home()), "HOME": str(Path.home()), "CLAUDE_PLUGIN_ROOT": str(root or "")}.get(name)
        found += [base + rest] if base is not None and (root or name != "CLAUDE_PLUGIN_ROOT") else []
    return [f for f in found if f]


def _write_area() -> list:
    """The folders a sandboxed shell may write here, beyond a session's own: temp, the D8 entries, Claude Code's added
    directories, Codex's trusted projects and the folders a Codex session writes."""
    settings = paths.read_json(paths.transcript_roots()["claude-code"].parent / "settings.json")
    added = (settings.get("permissions") or {}).get("additionalDirectories") if isinstance(settings.get("permissions"), dict) else []
    projects = codex_config().get("projects")
    roots = [*WRITE_AREA, *[str(paths.home() / w) for w in WRITABLE], "/tmp", "/var/tmp", "/private/var/folders",
             os.environ.get("TMPDIR", ""), *[str(d) for d in added or [] if isinstance(d, str)],
             *[p for p, v in (projects.items() if isinstance(projects, dict) else ()) if isinstance(v, dict) and v.get("trust_level") == "trusted"]]
    return [os.path.realpath(os.path.expanduser(r)) for r in roots if r and os.path.isabs(os.path.expanduser(r))]


def loose_commands() -> list:
    """(where, path) for each file a hook, MCP server or launch agent runs that a sandboxed shell may write (the note's
    4.7, item 9): a session could change it and have it run outside the sandbox later."""
    area, shut = _write_area(), [os.path.realpath(p) for p, _, _ in sealed()]
    return [(where, path) for where, text, root in _commands() for path in dict.fromkeys(_paths_in(text, root))
            if any(paths.inside(os.path.realpath(path), r) for r in area) and not any(paths.inside(os.path.realpath(path), s) for s in shut)]


def hooks_path_overrides(run=subprocess.run) -> list:
    """(repository, value) for each workspace repository whose own git config sets core.hooksPath somewhere other than
    the commit check: it runs hooks of its own, and the global check is off there."""
    from synthesis import doctor
    try:
        config = paths.config()
    except (OSError, ValueError):
        config = {}
    found, ours = [], os.path.realpath(paths.home() / "git-hooks")
    for repo in (r for r in doctor.workspace_repos(config) if (r / ".git").exists()):
        try:
            done = run(["git", "-C", str(repo), "config", "--local", "--includes", "--get", "core.hooksPath"], capture_output=True,
                       text=True, timeout=10, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            continue
        value = done.stdout.strip()
        if done.returncode == 0 and value and os.path.realpath(os.path.join(repo, os.path.expanduser(value))) != ours:
            found.append((repo, value))
    return found


def config_read(found, run=subprocess.run) -> list:
    """[(name, status, detail)] for `synthesis doctor --seal` outside a sandbox: each administrator file of a harness
    here, Codex's profile, Muse's state, every command that runs outside the sandbox from where a session writes, and
    every repository that runs hooks of its own. Anything that leaves the seal open fails."""
    rows = []
    for name in (n for n in ("claude", "codex") if n in found):
        state, problems = judge(name)
        problems += profile_problems(codex_config()) if name == "codex" else []
        rows.append((name, "fail" if problems else "ok", "; ".join(problems) if problems else
                     f"{LABELS[name]} installed at {target(name)}, root's, holding the keys" + (", and Codex's profile keeps the "
                     "sealed set read-only" if name == "codex" else "")))
    if "muse" in found:
        rows.append(("muse", "info", "Muse documents no folder rules, so its sandbox is not shown to seal anything: no approval "
                     "is granted in a Muse session until a probe shows that it does (the principal's ruling of 2026-11-15)"))
    loose = loose_commands()
    rows.append(("commands", "fail" if loose else "ok", f"{len(loose)} file(s) that run outside the sandbox can be written by a "
                 "sandboxed shell, so a session could change one and have it run with full access later: " + "; ".join(
                     f"{where} runs {tilde(path)}" for where, path in loose[:6]) + ". Move each out of the write area, or "
                 "stop running it" if loose else "no hook, MCP server or launch agent runs a file a sandboxed shell can write"))
    own = hooks_path_overrides(run)
    rows.append(("hooks path", "fail" if own else "ok", f"{len(own)} repositor{'y' if len(own) == 1 else 'ies'} set "
                 "core.hooksPath in their own config, so the commit check does not run there: " + "; ".join(
                     f"{tilde(repo)} ({value}); to fix it, run `git -C {shlex.quote(str(repo))} config --unset core.hooksPath`"
                     for repo, value in own[:4]) if own else "no workspace repository sets core.hooksPath of its own"))
    return rows

"""Set up synthesis on this Mac: the plugin in each harness, the runtime, Codex's settings,
and optionally a workspace's repositories or an organization's configuration.

    python3 setup.py                     # interactive: everything, asking what it cannot detect
    python3 setup.py plugin [--clients claude,codex,muse] [--ref stable|main|vX.Y.Z] [--[no-]codex-user-hooks]
    python3 setup.py workspace [--kb URL|PATH] [--workspace NAME]   # new Mac: clone repos.yaml
    python3 setup.py org --org-repo URL [--personal-source PATH]
    python3 setup.py uninstall [--dry-run]

Every step is safe to rerun: finished work is reported, not redone. Questions go to the
terminal even when stdin is a pipe (`curl ... | sh`); with no terminal, each question
names the flag to pass instead. Nothing here approves a harness's hook trust: that stays
the person's decision in Codex's /hooks and `muse plugins approve`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
try:
    from synthesis import doctor, install, paths  # noqa: E402  (the plugin's own core: listings, CLI finder, TOML reader)
except ImportError as exc:  # no runtime beside this copy; one that fails otherwise as it loads keeps its traceback
    print(f"{__file__} needs the synthesis runtime, which cannot be imported ({exc}), so nothing ran. Run it from the "
          "installed synthesis-skills plugin or a checkout of it", file=sys.stderr)
    sys.exit(2)

PLUGIN, MARKETPLACE, SOURCE = "synthesis-skills", doctor.MARKETPLACE, "synthesisengineering/synthesis-skills"
CODEX_DOC_BYTES = 98_304
LIST_TIMEOUT = 60  # one plugin listing; Codex's whole listing, which may fetch its remote catalog, gets five times this
HOOKS_BEGIN, HOOKS_END = "# synthesis-setup:begin hooks-feature", "# synthesis-setup:end hooks-feature"
BOARD_BEGIN, BOARD_END = "# synthesis-setup:begin board-writable", "# synthesis-setup:end board-writable"
PROFILE = "synthesis"  # the Codex permissions profile setup writes: the one in use, plus the board and the outbox
OWNED_BUNDLE_ROOTS = (Path.home() / ".cache" / "synthesis" / "muse-bundle",)
RESTART = ("Now quit and reopen Claude Code, Codex and Muse (you can resume your conversation): "
           "a restart is what loads new skills and hooks.")


class SetupError(Exception):
    pass


# ---- asking the person -----------------------------------------------------------

def _terminal():
    """stdin when it is a terminal, else the controlling terminal (stdin is busy under `curl | sh`)."""
    if sys.stdin.isatty():
        return sys.stdin, False
    try:
        return open("/dev/tty", "r", encoding="utf-8"), True
    except OSError:
        return None, False


def can_ask() -> bool:
    stream, opened = _terminal()
    if opened:
        stream.close()
    return stream is not None


def ask(question: str, flag: str, default: str = "") -> str:
    stream, opened = _terminal()
    if stream is None:
        raise SetupError(f"no terminal to ask '{question}'; pass {flag}")
    print(f"{question}{f' [{default}]' if default else ''}: ", end="", flush=True)
    try:
        answer = stream.readline()
    finally:
        if opened:
            stream.close()
    if answer == "":
        raise SetupError(f"no answer; pass {flag}")
    return answer.strip() or default


def choose(question: str, options: list, flag: str) -> str:
    print(question + "".join(f"\n  {i}. {o}" for i, o in enumerate(options, 1)), flush=True)
    answer = ask(f"Choice 1-{len(options)}", flag)
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        raise SetupError(f"choose 1-{len(options)}, or pass {flag}")
    return options[int(answer) - 1]


def confirm(question: str, flag: str, default: bool = True) -> bool:
    answer = ask(f"{question} ({'Y/n' if default else 'y/N'})", flag).lower()
    return default if not answer else answer in ("y", "yes")


def run(argv: list, timeout: float = 300, cwd=None, env=None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:  # 124 for a limit reached, as `timeout` exits; 127 for one that did not start
        return subprocess.CompletedProcess(argv, 124 if isinstance(exc, subprocess.TimeoutExpired) else 127, "", str(exc))


_json = doctor.json_in  # the JSON a command printed, read past any words before it


def _tail(proc) -> str:
    lines = (proc.stderr or proc.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {proc.returncode}"


# ---- the plugin, with each harness's own commands --------------------------------

def muse_record(binary: str):
    data = _json(run([binary, "plugins", "list", "--json"], 60).stdout)
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        raise SetupError("Muse's plugin list is unreadable; refusing to guess whether synthesis is installed")
    records = [p.get("record") for p in data["plugins"] if isinstance(p, dict) and isinstance(p.get("record"), dict)]
    return next((r for r in records if r.get("id") == PLUGIN), None)


def plugin_entry(client: str, binary: str):
    """The installed plugin's entry (enabled or not), None when absent. Unreadable listings raise."""
    if client == "muse":
        return muse_record(binary)
    # Codex is asked for the plugin's own marketplace first: its whole listing fetches the remote catalog again when
    # its copy is old (52 s on 2026-11-13), and an update, which is every release, need not wait on that. What the
    # marketplace does not show, and a build that does not know the option, are asked of the whole listing, with
    # time for the fetch: absent is said only from there, and a copy installed from another marketplace is found.
    codex_home = paths.codex_home()
    asks = [(doctor.LISTINGS[client], LIST_TIMEOUT)] + ([(doctor.CODEX_WHOLE, 5 * LIST_TIMEOUT)] if client == "codex" else [])
    for ask, limit in asks:
        proc = run([binary, *ask], limit)
        if proc.returncode == 124:  # a listing past its limit says nothing, and the next one is not started after it
            raise SetupError(f"{client}: `{' '.join(ask)}` did not answer within {limit:g} s; refusing to guess whether synthesis is installed")
        data = _json(proc.stdout)
        entry = None if data is None else doctor.claude_entry(data) if client == "claude" else doctor.codex_entry(data, codex_home)
        if entry:
            return entry
    if data is None:  # some builds print text; never crash on it, never take it for "absent"
        raise SetupError(f"{client} printed no plugin list ({_tail(proc)}); refusing to guess whether synthesis is installed")
    return None


def configured_ref(client: str):
    """The git ref the harness's synthesis marketplace tracks, or None when unknown."""
    try:
        if client == "claude":
            known = json.loads((Path.home() / ".claude" / "plugins" / "known_marketplaces.json").read_text())
            source = (known.get(MARKETPLACE) or {}).get("source") or {}
            return source.get("ref") if source.get("repo") == SOURCE else None
        config = doctor.read_toml((paths.codex_home() / "config.toml").read_text(encoding="utf-8"))
        return ((config.get("marketplaces") or {}).get(MARKETPLACE) or {}).get("ref")
    except (OSError, ValueError, AttributeError):
        return None


def _add_marketplace(client: str, binary: str, ref: str) -> list:
    if client == "claude":
        return [binary, "plugin", "marketplace", "add", f"{SOURCE}@{ref}"]
    return [binary, "plugin", "marketplace", "add", SOURCE, "--ref", ref, "--json"]


def install_plugin(client: str, binary: str, ref: str = "", source: Path = REPO, dry_run: bool = False) -> str:
    """Install or update the plugin. Without an explicit ref an existing marketplace keeps its
    ref, so an update never downgrades an install that follows a newer channel."""
    if client == "muse":
        return install_muse(binary, source, dry_run=dry_run)
    entry, current = plugin_entry(client, binary), configured_ref(client)
    plugin = f"{PLUGIN}@{MARKETPLACE}"
    if client == "codex" and entry and entry.get("id") not in ("", None, plugin):
        raise SetupError(f"codex: {PLUGIN} is installed from another marketplace ({entry['id']}), and nothing was added beside it. "
                         f"Remove that copy (`codex plugin remove {entry['id']}`) and run this again, or keep it and update it there")
    verb = "install" if client == "claude" else "add"
    if entry and (not ref or ref == current):
        # Codex installs from its marketplace snapshot: without the upgrade first, `add`
        # reinstalls the previous release while reporting success.
        steps = ([[binary, "plugin", "marketplace", "update", MARKETPLACE], [binary, "plugin", "update", plugin]]
                 if client == "claude" else
                 [[binary, "plugin", "marketplace", "upgrade", MARKETPLACE, "--json"], [binary, "plugin", "add", plugin]])
        action = "updated"
    else:
        steps = [_add_marketplace(client, binary, ref or "stable"), [binary, "plugin", verb, plugin]]
        if current and ref and current != ref:  # the marketplace is on another ref: remove, then add on this one
            steps.insert(0, [binary, "plugin", "marketplace", "remove", MARKETPLACE])
        action = "installed" if not entry else f"moved to {ref}"
    if dry_run:
        return f"{client}: would run " + "; ".join(" ".join(s[1:]) for s in steps)
    for step in steps:
        proc = run(step)
        if proc.returncode and "already" in (proc.stdout + proc.stderr).lower() and "marketplace" in step:
            run([binary, "plugin", "marketplace", "remove", MARKETPLACE])  # added earlier on another ref
            proc = run(step)
        if proc.returncode and not ("already" in (proc.stdout + proc.stderr).lower() and step[2] == verb):
            raise SetupError(f"{client}: `{' '.join(step[1:])}` failed: {_tail(proc)}")
    entry = plugin_entry(client, binary)
    if not entry:
        raise SetupError(f"{client}: the plugin list does not show {PLUGIN} after install")
    state = "" if entry.get("enabled") else " but disabled: enable it in the harness's plugin settings"
    return f"{client}: {action} {PLUGIN} {entry.get('version', '')}{state}"


def export_tree(source: Path, dest: Path, ref: str = "HEAD") -> None:
    """Replace dest with the tree at `ref` (a working copy when source is not a git checkout)."""
    staging = dest.with_name(f".{dest.name}.{os.getpid()}")
    shutil.rmtree(staging, ignore_errors=True)
    if (source / ".git").exists():
        archive = subprocess.run(["git", "-C", str(source), "archive", "--format=tar", ref], capture_output=True)
        if archive.returncode:
            raise SetupError(f"cannot export {ref}: {archive.stderr.decode(errors='replace').strip()}")
        import io
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in Path(member.name).parts or member.issym() or member.islnk():
                    raise SetupError(f"unsafe path in the release archive: {member.name}")
            tar.extractall(staging, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    else:
        shutil.copytree(source, staging, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    old = dest.with_name(f".{dest.name}.old.{os.getpid()}")
    if dest.exists():
        os.rename(dest, old)
    os.rename(staging, dest)
    shutil.rmtree(old, ignore_errors=True)


def install_muse(binary: str, source: Path, ref: str = "HEAD", dry_run: bool = False) -> str:
    """Muse installs from a local bundle and records its absolute path; later runs refresh the
    bundle in place and use `update`, because a second `install` from another path is refused."""
    help_text = run([binary, "plugins", "--help"], 30).stdout
    if not all(re.search(rf"(?m)^\s+{verb}\b", help_text) for verb in ("list", "install", "update")):
        raise SetupError("muse: this build's `plugins` command lacks list, install or update; update Muse first")
    record, ours = muse_record(binary), [install._home() / "muse-bundle"] + list(OWNED_BUNDLE_ROOTS)
    bundle = Path(str((record.get("source") or {}).get("path") or "")) if record else ours[0]
    if record and not bundle.is_absolute():
        raise SetupError(f"muse: the recorded bundle path {bundle} is not absolute; remove the plugin and rerun")
    if record and not any(bundle == r or r in bundle.parents for r in ours):
        raise SetupError(f"muse: {PLUGIN} is installed from {bundle}, which setup does not own; "
                         f"remove it with `muse plugins remove {PLUGIN}` and rerun")
    step = [binary, "plugins", "update", PLUGIN, "--json"] if record else \
        [binary, "plugins", "install", str(bundle), "--json"]
    if dry_run:
        return f"muse: would refresh {bundle} and run {' '.join(step[1:])}"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    export_tree(source, bundle, ref)
    proc = run(step)
    if proc.returncode:
        raise SetupError(f"muse: `{' '.join(step[1:])}` failed: {_tail(proc)}")
    return (f"muse: {'updated' if record else 'installed'} {PLUGIN} from {bundle}; to let its guards run, "
            f"approve its hooks yourself with `muse plugins approve {PLUGIN}`")


# ---- Codex settings: only the keys setup owns, after a backup ----------------------

def _top_level_end(lines: list) -> int:
    return next((i for i, line in enumerate(lines) if re.match(r"^\s*\[", line)), len(lines))


def _key_line(lines: list, table: str, key: str):
    """The line setting `key` in [table], under its header or as a dotted key before any header, or None."""
    current = ""
    for i, line in enumerate(lines):
        header = re.match(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$", line)
        if header:
            current = header.group(1).strip()
        elif (current == table and re.match(rf"^\s*{key}\s*=", line)) or (
                not current and re.match(rf"^\s*{table}\.{key}\s*=", line)):
            return i
    return None


def codex_overlay(text: str) -> tuple:
    """(new text, notes). Hooks on unless the person set them off; instruction bytes at least
    98,304; CLAUDE.md as a fallback instruction name when the key is absent; the synthesis board and outbox,
    and no other synthesis folder, writable from Codex's sandbox (5.1.18). Nothing else changes."""
    config, lines, notes, add_top = doctor.read_toml(text), text.splitlines(), [], []
    limit = config.get("project_doc_max_bytes")
    if isinstance(limit, int) and not isinstance(limit, bool) and limit < CODEX_DOC_BYTES:
        top = _top_level_end(lines)
        lines[:top] = [f"project_doc_max_bytes = {CODEX_DOC_BYTES}" if re.match(r"^\s*project_doc_max_bytes\s*=", line)
                       else line for line in lines[:top]]
        notes.append(f"raised project_doc_max_bytes from {limit:,} to {CODEX_DOC_BYTES:,}")
    elif limit is None:
        add_top.append(f"project_doc_max_bytes = {CODEX_DOC_BYTES}")
        notes.append(f"set project_doc_max_bytes = {CODEX_DOC_BYTES:,}")
    fallbacks = config.get("project_doc_fallback_filenames")
    if fallbacks is None:
        add_top.append('project_doc_fallback_filenames = ["CLAUDE.md"]')
        notes.append("set project_doc_fallback_filenames to CLAUDE.md")
    elif "CLAUDE.md" not in str(fallbacks):
        notes.append("project_doc_fallback_filenames lacks CLAUDE.md (left as you set it)")
    if add_top:
        top = _top_level_end(lines)
        lines[top:top] = add_top + ([""] if top < len(lines) else [])
    hooks = (config.get("features") or {}).get("hooks")
    if hooks is False:
        notes.append("kept [features] hooks = false, so no synthesis guard runs in Codex")
    elif hooks is not True:
        start = next((i for i, line in enumerate(lines) if line.strip() == "[features]"), None)
        if start is None:
            lines += ["", HOOKS_BEGIN, "[features]", "hooks = true", HOOKS_END]
        else:
            end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\s*\[", lines[i])), len(lines))
            lines[end:end] = [HOOKS_BEGIN, "hooks = true", HOOKS_END]
        notes.append("enabled [features] hooks")
    for what, folder, so in (("board", str(paths.board()), "claim files and post"),
                             ("outbox", str(paths.outbox()), "stage a file they attach")):
        found, unsandboxed = doctor.codex_write_roots(config)
        if not unsandboxed and not any(paths.inside(os.path.realpath(folder), os.path.realpath(os.path.expanduser(r)))
                                       for r in found):
            edited = (_legacy_grant if config.get("sandbox_mode") is not None else _profile_grant)(lines, config, folder)
            notes.append(f"let Codex's sandbox write the synthesis {what} ({folder}), so its sessions can {so}"
                         if edited else f"Codex's sandbox settings are written in a form setup does not edit: grant {folder}")
            config = doctor.read_toml("\n".join(lines))  # the next folder joins what this one wrote
    return "\n".join(lines).strip("\n") + "\n", notes


def _profile_grant(lines: list, config: dict, folder: str) -> bool:
    """Codex's permission profiles (0.166): the person's own default profile gains the folder; a built-in or no
    choice is replaced by PROFILE, which extends it with the folder, so nothing else changes."""
    chosen = config.get("default_permissions")
    name = chosen if isinstance(chosen, str) and not chosen.startswith(":") else PROFILE
    profile, header = (config.get("permissions") or {}).get(name), f"[permissions.{name}.filesystem]"
    at = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if at is None and profile is not None and (not isinstance(profile, dict) or "filesystem" in profile):
        return False  # written inline or as dotted keys
    rule = f'{json.dumps(folder)} = "write"'
    if at is not None:
        lines[at + 1:at + 1] = [rule]
    elif profile is None:
        base = chosen if isinstance(chosen, str) and chosen.startswith(":") else ":workspace"
        lines += ["", BOARD_BEGIN, f"[permissions.{name}]", f'extends = "{base}"', header, rule, BOARD_END]
    else:
        lines += ["", BOARD_BEGIN, header, rule, BOARD_END]
    if name != chosen:
        line = f'default_permissions = "{name}"  # synthesis setup: {chosen or ":workspace"} plus the folders its sessions write'
        at = _key_line(lines, "", "default_permissions")
        if at is None:
            top = _top_level_end(lines)
            while top and lines[top - 1].lstrip().startswith("#"):  # above the comments that open the first table
                top -= 1
            lines[top:top] = [line, ""]
        else:
            lines[at] = line
    return True


def _legacy_grant(lines: list, config: dict, folder: str) -> bool:
    """The older [sandbox_workspace_write] writable_roots, which Codex reads instead while `sandbox_mode` is set."""
    table, entry = config.get("sandbox_workspace_write"), json.dumps(folder)  # a TOML basic string
    if table is not None and not isinstance(table, dict):
        return False
    at = _key_line(lines, "sandbox_workspace_write", "writable_roots")
    header = next((i for i, line in enumerate(lines) if line.strip() == "[sandbox_workspace_write]"), None)
    if at is not None:
        lines[at] = re.sub(r"=\s*\[", f"= [{entry}, ", lines[at], count=1)
    elif header is not None:
        lines[header + 1:header + 1] = [BOARD_BEGIN, f"writable_roots = [{entry}]", BOARD_END]
    elif table is not None:  # the table exists only as dotted keys at the top
        top = _top_level_end(lines)
        lines[top:top] = [f"sandbox_workspace_write.writable_roots = [{entry}]"]
    else:
        lines += ["", BOARD_BEGIN, "[sandbox_workspace_write]", f"writable_roots = [{entry}]", BOARD_END]
    return True


_UNREAD = object()  # _replace's `expected` when the caller read nothing to hold the file to


def _replace(path: Path, text, backup: str, expected=_UNREAD):
    """Write a harness's file whole, or remove it for None, after copying the old one to the synthesis backups as
    `backup`.<time>; returns that copy, None for a new file. A symlink is written through to its target, the file keeps
    its mode (a new one is 0600: config.toml holds connector tokens), and no temporary file outlives a failure. With
    `expected` (the text read before the edit, None for no file), a file changed since is left as it is and refused:
    Codex may have recorded an approval meanwhile (review round 1 of 5.21.0)."""
    target = Path(os.path.realpath(path))
    if expected is not _UNREAD and (target.read_bytes().decode("utf-8") if target.exists() else None) != expected:
        raise SetupError(f"{path} changed while setup was editing it, so it was left as it is: run this again")
    copy = install._home() / "backups" / f"{backup}.{time.strftime('%Y%m%dT%H%M%S')}" if target.exists() else None
    if copy:
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, copy)
    if text is None:
        target.unlink()
        return copy
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o600
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    try:
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(tmp, mode)  # what the umask took off
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return copy


def _restore(path: Path, copy) -> None:
    """Put back a file `_replace` wrote: from its backup copy, or gone where it was new."""
    target = Path(os.path.realpath(path))
    if copy:
        shutil.copy2(copy, target)
    else:
        target.unlink(missing_ok=True)


def _write_all(writes: list, then=None) -> None:
    """Make each (path, text or None, backup name, text read before) in order, then call `then`. When any of it fails,
    every file written is put back and SetupError raised, so no stop midway leaves the files half changed (review round
    1 of 5.21.0)."""
    done = []
    try:
        for path, text, backup, expected in writes:
            done.append((path, _replace(path, text, backup, expected)))
        if then:
            then()
    except (OSError, SetupError) as exc:
        for path, copy in reversed(done):
            _restore(path, copy)
        raise SetupError(f"codex user hooks: {exc}; each file setup had written was put back") from None


def _toml_problem(text: str) -> str:
    """Why Codex would refuse this config.toml, or '': the strict reader, and Python's own tomllib where it has one
    (3.11+, the whole grammar; Apple's 3.9 has only the strict reader)."""
    try:
        doctor.read_toml(text, strict=True)
        import tomllib
        tomllib.loads(text)
    except ImportError:
        return ""
    except ValueError as exc:
        return str(exc)
    return ""


def configure_codex(dry_run: bool = False) -> list:
    path = paths.codex_home() / "config.toml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    problem = _toml_problem(text)
    if problem:  # nothing written into a file Codex cannot read (review round 1 of 5.21.0)
        raise SetupError(f"codex config: {path} does not parse ({problem}), so it was left as it is")
    new, notes = codex_overlay(text)
    for folder in (paths.board(), paths.outbox()) if not dry_run else ():
        folder.mkdir(parents=True, exist_ok=True)  # Codex's sandbox may write inside it, never create it
    if new == (text if text.endswith("\n") else text + "\n") or dry_run:
        return [f"codex config: {'would ' if dry_run else ''}{n}" for n in notes] or ["codex config: already set"]
    backup = _replace(path, new, "codex-config.toml")
    return [f"codex config: {n}" for n in notes + ([f"backed up the previous file to {backup}"] if backup else [])]


# ---- the plugin's hooks declared in Codex's own hooks file (--codex-user-hooks) ---------------------------
# Codex ties its approval of a plugin's hooks to the plugin's files, so after every update it runs none of them until
# the person approves again in /hooks. A hook declared in its own hooks.json, beside config.toml, is trusted by its
# declaration alone, and these all run one stable path: one approval lasts through every release. What that gives up
# is Codex's second look at a hook whose code changed, so it is the person's choice, off unless asked for.

USER_HOOKS = f"# {doctor.SETUP_MARK}"  # marks each config.toml line the option adds
SWITCH = f"enabled = false  {USER_HOOKS}"


def _state_tables(lines: list) -> dict:
    """{key: the index of its `[hooks.state."<key>"]` header} among config.toml's lines."""
    found = {}
    for i, line in enumerate(lines):
        body = line.strip()[1:] if line.lstrip().startswith("[") and not line.lstrip().startswith("[[") else ""
        end = doctor._find(body, "]")
        parts = doctor._key_parts(body[:end]) if end > 0 else []
        if len(parts) == 3 and parts[:2] == ["hooks", "state"]:
            found[parts[2]] = i
    return found


def _switches(lines: list, keys: list, held: dict, crlf: bool = False) -> list:
    """config.toml's lines with each key's plugin hook switched off by a marked line in its own table, and no other
    switch of setup's. Only setup's lines go: its switches, found by their table, key, value and mark however spaced,
    and its marked header once no key is left under it (review round 1: the person's comments went too). A key held in
    a form setup does not edit stops it, since a second table would break the file."""
    end = "\r" if crlf else ""

    def table_end(at):
        return next((i for i in range(at + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))

    def key_of(line):
        text = line.rstrip("\r").strip()
        eq = doctor._find(text, "=")
        return doctor._key_parts(text[:eq]) if eq > 0 and not text.startswith(("#", "[")) else []
    for i, key in reversed(doctor.codex_switch_lines(lines)):
        if key not in keys:
            del lines[i]
    for key, at in sorted(_state_tables(lines).items(), key=lambda item: -item[1]):
        if key not in keys and doctor.SETUP_MARK in lines[at] and not any(key_of(line) for line in lines[at + 1:table_end(at)]):
            del lines[at]
    tables, added = _state_tables(lines), []
    for key in keys:
        if key not in tables and key in held:
            raise SetupError(f"codex user hooks: config.toml holds {key} in a form setup does not edit, so nothing was changed")
        added += [] if key in tables else [f"[hooks.state.{json.dumps(key)}]  {USER_HOOKS}{end}", SWITCH + end]
    for at in sorted((tables[k] for k in keys if k in tables), reverse=True):
        on = next((i for i in range(at + 1, table_end(at)) if key_of(lines[i]) == ["enabled"]), None)
        if on is None:
            lines.insert(at + 1, SWITCH + end)
        elif doctor._value(lines[on].rstrip("\r").split("=", 1)[1].strip()) is not False:
            lines[on] = SWITCH + end  # the person had turned it back on; taking the switch out leaves it on again
    at = len(lines) - 1 if lines[-1:] == [""] else len(lines)
    lines[at:at] = added
    return lines + ([""] if added and lines[-1:] != [""] else [])


def _codex_state(text: str, config_file: Path) -> dict:
    """The hook state config.toml holds, for setup to edit. SetupError for a file Codex would refuse, and for state held
    as an inline table (`hooks = {...}`, `state = {...}`), where a table setup added would define it twice."""
    problem = _toml_problem(text)
    if problem:
        raise SetupError(f"codex user hooks: {config_file} does not parse ({problem}), so nothing was changed")
    hooks = doctor.read_toml(text, strict=True).get("hooks", {})
    state = hooks.get("state", {}) if isinstance(hooks, dict) else None
    if not isinstance(state, dict):
        raise SetupError(f"codex user hooks: {config_file} holds Codex's hook state as an inline table (`hooks = {{...}}` or "
                         "`state = {...}`), a form setup does not edit, so nothing was changed")
    return state


def codex_user_hooks_on() -> bool:
    """Whether setup's Codex option is on in this Codex home: a switch of setup's in config.toml, or setup's record of
    what it declared in hooks.json. The mark's words anywhere else turn nothing on (review round 1 of 5.21.0)."""
    codex = paths.codex_home()
    return bool(doctor.codex_switch_lines(doctor._text(codex / "config.toml").split("\n"))) or \
        doctor.codex_hooks_key(codex) in paths.read_json(paths.codex_hooks_record())


def codex_user_hooks(want, plugin_root=None, dry_run: bool = False) -> list:
    """Declare the plugin's hooks in Codex's own hooks.json and switch the plugin's own off by their state keys (want
    True), take out what that added (False), or keep a declaration made earlier in step with the plugin at
    `plugin_root` (None: nothing where the option is off). Setup knows its own by its record of the groups it wrote
    (paths.codex_hooks_record) and by its marked config.toml lines. A declaration of the person's stays as written,
    and the plugin's copy of that event goes off only where it covers the plugin's. A file that cannot be parsed, hook
    state held inline, an edit that would not parse and a file changed meanwhile each stop it before anything is
    written, and a write that fails midway puts back what was written. On, hooks.json is written first; off,
    config.toml first: a stop between them never leaves an event with neither copy (review round 1 of 5.21.0)."""
    codex = paths.codex_home()
    file, config_file, key = codex / "hooks.json", codex / "config.toml", doctor.codex_hooks_key(codex)
    if want is not True and not codex_user_hooks_on():
        return [] if want is None else ["codex user hooks: none declared by setup"]
    raw = file.read_bytes().decode("utf-8") if file.exists() else None  # as written: no line ending translated
    text = config_file.read_bytes().decode("utf-8") if config_file.exists() else None
    try:
        data = json.loads(raw) if raw is not None else {"hooks": {}}
        problem = doctor.codex_hooks_problem(data)
    except ValueError as exc:
        data, problem = None, str(exc)
    if problem:
        raise SetupError(f"codex user hooks: Codex would not read {file} ({problem}), so nothing was changed")
    held, records = _codex_state(text or "", config_file), paths.read_json(paths.codex_hooks_record())
    want, events, before, record = want is not False, data.setdefault("hooks", {}), json.dumps(data), records.get(key) or {}
    wanted = doctor.codex_user_declaration(paths.read_json(Path(plugin_root) / "hooks" / "hooks.json")) if want else {}
    if want and not wanted:
        raise SetupError(f"codex user hooks: {plugin_root} has no hooks/hooks.json to declare, so nothing was changed")
    recorded, done, kept, short, covered, wrote = record.get("groups") or {}, [], [], [], [], {}
    for event in dict.fromkeys([*wanted, *recorded, *events]):
        current = events.get(event, [])
        mine = [i for i, group in enumerate(current) if group in recorded.get(event, [])]
        own = [g for i, g in enumerate(current) if i not in mine and any(doctor.calls_stable_hook(event, h.get("command"))
                                                                           for h in g.get("hooks", []))]
        if event in wanted and own and not mine:  # the person's own declaration: kept as written
            kept.append(event)
            (covered if doctor.codex_covers(own, wanted[event]) else short).append(event)
            continue
        if [current[i] for i in mine] != wanted.get(event, []):
            rest = [group for i, group in enumerate(current) if i not in mine]
            at = mine[0] if mine else len(rest)  # where setup's own stood, so the keys of the person's after it hold
            events[event] = rest[:at] + wanted.get(event, []) + rest[at:]
            done.append(event)
            if not events[event]:
                del events[event]
        if event in wanted:
            wrote[event] = wanted[event]
            covered.append(event)
    keys = [f"{PLUGIN}@{MARKETPLACE}:hooks/hooks.json:{doctor._snake(e)}:{gi}:{hi}"
            for e in covered for gi, group in enumerate(wanted[e]) for hi, _ in enumerate(group["hooks"])]
    lines = _switches((text or "").split("\n"), keys, held, "\r\n" in (text or ""))
    problem = _toml_problem("\n".join(lines))
    if problem:
        raise SetupError(f"codex user hooks: setup's edit would leave {config_file} unreadable ({problem}), so nothing was changed")
    gone = not want and data == {"hooks": {}} and record.get("created") and not file.is_symlink()
    after = {**records, key: {"groups": wrote, "created": record.get("created", raw is None)}} if wrote else \
        {k: v for k, v in records.items() if k != key}
    would, owned = "would " if dry_run else "", [e for e in kept if e in covered]
    notes = [f"codex user hooks: {would}" + (f"declare {', '.join(done)} in {file}; approve them once in Codex's /hooks, and "
             "a release asks again only when it changes one" if want else f"take {', '.join(done)} out of {file}")] if done else []
    notes += [f"codex user hooks: {', '.join(owned)} already declared in {file} by you, kept as written"] if owned else []
    notes += [f"codex user hooks: your own {', '.join(short)} in {file} covers less than the plugin's, so the plugin's own stays "
              "on beside it: edit yours to cover it or remove it, then run this again"] if short else []
    if "\n".join(lines) != (text or ""):
        notes.append(f"codex user hooks: {would}" + (f"switch the plugin's own hooks off in {config_file} where the user level "
                     f"covers them ({len(keys)} lines marked as setup's), so none runs twice" if want else
                     f"take setup's switches out of {config_file}; the plugin's own hooks run once approved"))
    notes = notes or [f"codex user hooks: already declared in {file}, the plugin's own switched off" if want
                      else "codex user hooks: none declared by setup"]
    writes = [w for w, changed in (((file, None if gone else json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                     "codex-hooks.json", raw), json.dumps(data) != before or bool(gone and raw is not None)),
                                   ((config_file, "\n".join(lines), "codex-config.toml.user-hooks", text),
                                    "\n".join(lines) != (text or ""))) if changed]
    if not dry_run:  # off: the switches out first, so the plugin's copies run again before the declarations go
        _write_all(writes if want else writes[::-1], (lambda: paths.write_json(paths.codex_hooks_record(), after))
                   if after != records else None)
    return notes


def configure_claude(dry_run: bool = False) -> list:
    """Claude Code deletes a transcript idle past `cleanupPeriodDays`, 30 when unset; unset becomes 3,650 so the
    record outlives every export interval. A value the person set is theirs and stays."""
    path = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return [f"claude settings: {path} does not parse, so it was left as it is"]
    if "cleanupPeriodDays" in data or dry_run:
        return [f"claude settings: transcripts kept {data['cleanupPeriodDays']} days, as set" if "cleanupPeriodDays" in data
                else "claude settings: would keep transcripts 3,650 days instead of Claude Code's 30"]
    _replace(path, json.dumps({**data, "cleanupPeriodDays": 3650}, indent=2) + "\n", "claude-settings.json")
    return ["claude settings: transcripts kept 3,650 days instead of Claude Code's 30"]


# ---- runtime, CLI and first config ----------------------------------------------

def install_runtime(git_hooks: bool) -> list:
    lines = [install.install(REPO)]
    if git_hooks:
        lines.append(install.register_git_hooks())
    link, target = Path.home() / ".local" / "bin" / "synthesis", install._home() / "bin" / "synthesis"
    if link.is_file() and not link.is_symlink() and "generated by synthesis-onboarding" in link.read_text("utf-8", "replace"):
        lines.append(f"archived the 4.x synthesis command to {workspace_archive([link])}")  # it drove the retired board
    if not os.path.lexists(link):
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        lines.append(f"linked {link} -> {target}")
    elif os.path.realpath(link) != os.path.realpath(target):
        lines.append(f"{link} belongs to another install; run {target}, or put {target.parent} first on PATH")
    return lines


def first_config(interactive: bool) -> list:
    """For a fresh config only: a short interview for the two keys most people set first."""
    path = install._home() / "config.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"config: {path} unreadable; fix it before sending anything (the send guard blocks until then)"]
    if config or not interactive:
        return ["config: sends and drafts ask for your approval of the exact text; deploys need it too"]
    roots = ask("Knowledge repositories, comma-separated (blank finds ~/workspaces/*/ai-knowledge-*)", "--no-input")
    phrases = ask("Words or phrases never to send, comma-separated (blank for none)", "--no-input")
    if roots:
        config["knowledge_roots"] = [r.strip().replace(str(Path.home()), "~", 1) for r in roots.split(",") if r.strip()]
    if phrases:
        config["forbidden_phrases"] = [{"name": p.strip(), "pattern": re.escape(p.strip()), "why": "set at setup"}
                                       for p in phrases.split(",") if p.strip()]
    path.write_text(json.dumps(config, indent=1) + "\n", encoding="utf-8")
    return [f"config: wrote {', '.join(config) or 'defaults'} to {path}"]


# ---- the day-end launcher and weekday nudge ---------------------------------------

LAUNCHCTL = "launchctl"
NUDGE_LABEL = "com.synthesis.day-end-nudge"
HOMES = ("SYNTHESIS_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_DATA_HOME", "SYNTHESIS_CLAUDE_DESKTOP_DIR")  # the runtime's folder, and where each harness keeps transcripts


def _homes() -> str:
    """The start of a scheduled job's line: each of HOMES this install was made with, set after the login shell's
    own. A job that carried none ran this install's command on the default home (2026-11-12, a second review)."""
    return "".join(f"export {name}={shlex.quote(os.environ[name])}; " for name in HOMES if os.environ.get(name))


def _nudge_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{NUDGE_LABEL}.plist"


def register_day_end(agent: str = "auto", load: bool = True) -> list:
    """Link ~/.local/bin/day-end to the installed launcher, remember which agent it opens, and
    schedule the weekday 16:55 nudge as a LaunchAgent that runs the installed nudge script."""
    import plistlib
    home = install._home()
    launcher, nudge = home / "bin" / "day-end", home / "bin" / "day-end-nudge.sh"
    if not (launcher.is_file() and nudge.is_file()):
        raise SetupError("the day-end launcher is not installed; run setup.py plugin (or start a session) first")
    link, plist, lines = Path.home() / ".local" / "bin" / "day-end", _nudge_plist(), []
    if os.path.lexists(link) and not link.is_symlink():
        raise SetupError(f"{link} is a file, not a link; refusing to replace it")
    (home / "agent-cli").write_text(agent + "\n", encoding="utf-8")
    if os.path.realpath(link) != os.path.realpath(launcher):
        link.unlink(missing_ok=True)  # a link to elsewhere, or nothing: a file was refused above
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(launcher)
        lines.append(f"linked {link} -> {launcher} (opens {agent})")
    template = REPO / "skills" / "synthesis-daily-rituals" / "scripts" / f"{NUDGE_LABEL}.plist"
    spec = plistlib.loads(template.read_bytes())
    spec["ProgramArguments"] = ["/bin/bash", "-lc", f'{_homes()}exec "{nudge}"']  # a login shell, for the user's PATH
    if plist.exists() and not install.runs_only(plist, nudge):
        lines.append(f"archived the previous nudge schedule to {workspace_archive([plist])}")
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(plistlib.dumps(spec))
    if load:
        domain = f"gui/{os.getuid()}"
        run([LAUNCHCTL, "bootout", f"{domain}/{NUDGE_LABEL}"], 30)  # an older schedule under the same label
        loaded = run([LAUNCHCTL, "bootstrap", domain, str(plist)], 30)
        if loaded.returncode:
            raise SetupError(f"launchctl could not load {plist}: {_tail(loaded)}")
    return lines + [f"nudge scheduled for weekdays at 16:55 ({plist}{'' if load else ', not loaded'})"]


def unregister_day_end(dry_run: bool = False) -> list:
    """Remove only a nudge schedule and a day-end link that point at this install's copies."""
    home, lines = install._home(), []
    plist, link = _nudge_plist(), Path.home() / ".local" / "bin" / "day-end"
    if plist.exists() and install.runs_only(plist, home / "bin" / "day-end-nudge.sh"):
        if not dry_run:
            run([LAUNCHCTL, "bootout", f"gui/{os.getuid()}/{NUDGE_LABEL}"], 30)
            plist.unlink()
        lines.append(f"{'would remove' if dry_run else 'removed'} the nudge schedule {plist}")
    elif plist.exists():
        lines.append(f"{'would keep' if dry_run else 'kept'} {plist}: its command is not this install's nudge")
    if link.is_symlink() and os.path.realpath(link) == os.path.realpath(home / "bin" / "day-end"):
        if not dry_run:
            link.unlink()
        lines.append(f"{'would remove' if dry_run else 'removed'} {link}")
    elif os.path.lexists(link):
        lines.append(f"{'would keep' if dry_run else 'kept'} {link}: it is not a link to this install's launcher")
    return lines


# ---- the hourly copy of session transcripts ---------------------------------------

EXPORT_LABEL = "com.synthesis.sessions-export"


def _export_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{EXPORT_LABEL}.plist"


def register_sessions_export(load: bool = True) -> list:
    """Schedule, every hour and at login, the copy of every harness's session transcripts into the archive and of
    each workspace's conversation into its sessions repo (2026-11-11: until then a transcript was copied only when
    some session ran resume, handoff or a ritual). The job runs with the homes this install was made with."""
    import plistlib
    command, plist = install._home() / "bin" / "synthesis", _export_plist()
    if not command.is_file():
        raise SetupError("the synthesis command is not installed; run setup.py plugin (or start a session) first")
    log = f"/tmp/{EXPORT_LABEL}.log"
    spec = {"Label": EXPORT_LABEL, "StartInterval": 3600, "RunAtLoad": True, "ProcessType": "Background",
            "StandardOutPath": log, "StandardErrorPath": log,  # a login shell, for the user's PATH and git credentials
            "ProgramArguments": ["/bin/bash", "-lc",  # `--scheduled`: the run marks itself, and the doctor knows the schedule by it
                                 f'{_homes()}"{command}" sessions export --all --scheduled; "{command}" sessions sync']}
    lines = []
    if plist.exists() and not install.runs_only(plist, command):  # one label holds one schedule: another install's copy stops here
        lines.append(f"archived another install's export schedule to {workspace_archive([plist])}")
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(plistlib.dumps(spec))
    if load:
        domain = f"gui/{os.getuid()}"
        run([LAUNCHCTL, "bootout", f"{domain}/{EXPORT_LABEL}"], 30)  # an older schedule under the same label
        loaded = run([LAUNCHCTL, "bootstrap", domain, str(plist)], 30)
        if loaded.returncode:
            raise SetupError(f"launchctl could not load {plist}: {_tail(loaded)}")
    return lines + [f"session transcripts copied every hour and at login ({plist}{'' if load else ', not loaded'}; it writes {log})"]


def unregister_sessions_export(dry_run: bool = False) -> list:
    """Remove only an export schedule whose every command is this install's."""
    plist = _export_plist()
    if plist.exists() and install.runs_only(plist, install._home() / "bin" / "synthesis"):
        if not dry_run:
            run([LAUNCHCTL, "bootout", f"gui/{os.getuid()}/{EXPORT_LABEL}"], 30)
            plist.unlink()
        return [f"{'would remove' if dry_run else 'removed'} the export schedule {plist}"]
    return [f"{'would keep' if dry_run else 'kept'} {plist}: its command is not this install's"] if plist.exists() else []


def workspace_archive(paths: list) -> Path:
    import workspace
    return workspace._archive(paths)


# ---- the command line -----------------------------------------------------------

def no_harness(clients: list) -> str:
    """Said before anything changes: a runtime that no harness uses helps no one (2026-10-30)."""
    names = [{"claude": "Claude Code", "codex": "Codex", "muse": "Muse"}[c] for c in clients]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]
    return (f"no {listed} on this Mac, so there is nothing to install into yet. Install one (the Claude desktop app, "
            "https://claude.com/download, includes Claude Code), then run this command again.")


def _step(lines: list, step) -> bool:
    """One step of setup: its lines, or its refusal, into `lines`; False when it refused."""
    try:
        lines += step()
    except SetupError as exc:
        lines.append(str(exc))
        return False
    return True


def setup_plugins(clients: list, ref: str, dry_run: bool, user_hooks=None) -> tuple:
    """Each harness's plugin, then its settings. In Codex, the user-level option's step runs apart from the install: off,
    whatever the install said, since turning it off needs no network; on or in step, after the install, against the
    folder Codex now holds. A refusal of that step hides neither the install's line nor Codex's settings (review round
    1 of 5.21.0)."""
    lines, failed = [], False
    for client in clients:
        binary = doctor.find_client(client)
        if not binary:
            lines.append(f"{client}: not found on this Mac; skipped")
            continue
        if not dry_run:  # the harness's own commands fetch the plugin: up to a minute with nothing printed
            print(f"{client}: installing {PLUGIN} with {binary} ...", flush=True)
        installed = _step(lines, lambda: [install_plugin(client, binary, ref, dry_run=dry_run)])
        option = client == "codex" and (user_hooks is False or installed and (user_hooks or codex_user_hooks_on()))
        chosen = not option or _step(lines, lambda: codex_user_hooks(user_hooks, None if user_hooks is False else (
            (plugin_entry("codex", binary) or {}).get("path") or REPO), dry_run))
        settings = not installed or _step(lines, lambda: configure_codex(dry_run) if client == "codex" else
                                          configure_claude(dry_run) if client == "claude" else [])
        failed = failed or not (installed and chosen and settings)
    return lines, failed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="setup.py", description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("command", nargs="?", default="all", choices=("all", "plugin", "workspace", "org", "uninstall"))
    parser.add_argument("--clients", default="", help="default claude,codex,muse (or what the organization asks for)")
    parser.add_argument("--ref", default="", help="marketplace ref: stable (default for new installs), main or vX.Y.Z")
    parser.add_argument("--git-hooks", action="store_true", help="run the commit check for every repository")
    parser.add_argument("--kb", default="", help="knowledge repository URL or path (new Mac)")
    parser.add_argument("--workspace", default="")
    parser.add_argument("--new", default="", metavar="NAME", help="workspace: start a new knowledge repository")
    parser.add_argument("--org-repo", default="")
    parser.add_argument("--personal-source", default="", help="your own instruction file for an organization workspace")
    parser.add_argument("--adopt-workspace-instructions", action="store_true",
                        help="replace existing workspace AGENTS.md/CLAUDE.md after archiving them")
    parser.add_argument("--day-end", nargs="?", const="auto", choices=("auto", "codex", "claude"),
                        help="link ~/.local/bin/day-end and schedule the weekday 16:55 nudge")
    parser.add_argument("--sessions-export", action="store_true",
                        help="copy every harness's session transcripts into the archive and the sessions repos every hour")
    parser.add_argument("--codex-user-hooks", action=argparse.BooleanOptionalAction, default=None,
                        help="declare the plugin's hooks in Codex's own hooks.json, so one approval in /hooks lasts "
                             "through releases; --no-codex-user-hooks takes that out")
    parser.add_argument("--no-launchctl", action="store_true", help="--day-end, --sessions-export: write the schedule without loading it")
    parser.add_argument("--no-input", action="store_true", help="never ask; fail naming the flag instead")
    parser.add_argument("--compact-brief", action="store_true",
                        help="add the compaction brief to each synthesis workspace's instructions without asking")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    interactive = not args.no_input and can_ask()
    clients = [c.strip() for c in (args.clients or "claude,codex,muse").split(",") if c.strip() in doctor.HARNESSES]
    failed, scratch = False, Path(tempfile.mkdtemp(prefix="synthesis-dry-run-")) if args.dry_run else None

    def say(lines):  # each step's lines as soon as it finishes, so a long run never looks hung
        print("\n".join(lines), flush=True)
    try:  # a dry run writes only in scratch, which it removes: repositories are read through clones there
        if args.org_repo and args.command == "all":  # the organization's clients and release, unless given here
            import workspace
            org_clients, org_ref = workspace.org_preferences(args.org_repo, scratch)
            clients, args.ref = (clients if args.clients else org_clients), args.ref or org_ref
        if args.command == "uninstall":
            return _uninstall(clients, args.dry_run)
        if args.command in ("all", "plugin"):
            if not any(doctor.find_client(client) for client in clients):
                say([f"stopped: {no_harness(clients)}"])
                return 1
            plugin_lines, failed = setup_plugins(clients, args.ref, args.dry_run, args.codex_user_hooks)
            say(plugin_lines)
            if args.dry_run:
                say([f"runtime: would install it from {REPO} into {install._home()}" + (", with the commit check in every "
                     "repository" if args.git_hooks else "") + (f"; would link day-end ({args.day_end})" if args.day_end else "")
                     + ("; would schedule the hourly copy of session transcripts" if args.sessions_export else "")])
            else:
                git_hooks = args.git_hooks or (interactive and args.command == "all" and confirm(
                    "Run the synthesis commit check (secrets, disclosures, other sessions' claims) in every repository?",
                    "--git-hooks", default=True))
                say(install_runtime(git_hooks) + first_config(interactive and args.command == "all"))
                if args.day_end:
                    say(register_day_end(args.day_end, load=not args.no_launchctl))
                if args.sessions_export:
                    say(register_sessions_export(load=not args.no_launchctl))
        if args.command in ("workspace", "org") or (args.command == "all" and (args.kb or args.org_repo or args.new or (
                interactive and confirm("Bring a workspace's repositories onto this Mac?", "--kb", default=False)))):
            import workspace
            progress = lambda line: print(line, flush=True)  # noqa: E731
            if args.command == "org" or args.org_repo:
                say(workspace.enroll(args.org_repo or ask("Organization config repository URL", "--org-repo"),
                                     progress, args.personal_source, args.adopt_workspace_instructions, scratch))
            elif args.new:
                say(workspace.new_workspace(args.new, args.kb, args.dry_run))
            else:
                say(workspace.bring_workspace(args.kb, args.workspace, progress, args.adopt_workspace_instructions,
                                              interactive, scratch))
        if args.command in ("all", "workspace", "org"):  # what a compaction summary keeps, in every synthesis workspace
            import workspace
            say(workspace.add_brief(interactive, args.compact_brief, args.dry_run))
    except (SetupError, ValueError, OSError) as exc:  # a malformed manifest or an unwritable folder: say which
        say([f"stopped: {exc}"])
        failed = True
    except KeyboardInterrupt:
        print("\ninterrupted: run the same command again to resume; finished steps are kept", file=sys.stderr)
        return 130
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
    if args.dry_run:
        print("Dry run: nothing was changed.")
    elif args.command != "workspace":
        print(RESTART)
    return 1 if failed else 0


def _uninstall(clients: list, dry_run: bool) -> int:
    try:  # the hooks declared in Codex's own hooks.json run the runtime that goes below: they go first, or nothing does
        lines = codex_user_hooks(False, dry_run=dry_run)
    except SetupError as exc:
        print(f"{exc}\nstopped: nothing was removed, and the runtime stays, since the hooks declared in Codex's own "
              "hooks.json run it; mend the file and run uninstall again")
        return 1
    for client in clients:
        binary = doctor.find_client(client)
        try:
            entry = plugin_entry(client, binary) if binary else None
        except SetupError as exc:
            lines.append(str(exc))
            continue
        if not entry:
            lines.append(f"{client}: {PLUGIN} not installed")
            continue
        step = {"claude": [binary, "plugin", "uninstall", f"{PLUGIN}@{MARKETPLACE}", "--yes"],
                "codex": [binary, "plugin", "remove", entry.get("id") or f"{PLUGIN}@{MARKETPLACE}", "--json"],  # the copy that is there
                "muse": [binary, "plugins", "remove", PLUGIN, "--json"]}[client]
        proc = subprocess.CompletedProcess(step, 0, "", "") if dry_run else run(step)
        lines.append(f"{client}: {'would remove' if dry_run else 'removed'} {PLUGIN}" if not proc.returncode
                     else f"{client}: removal failed: {_tail(proc)}")
    lines += unregister_day_end(dry_run) + unregister_sessions_export(dry_run) + install.uninstall(dry_run=dry_run)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

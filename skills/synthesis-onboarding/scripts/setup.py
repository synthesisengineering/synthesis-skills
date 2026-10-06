"""Set up synthesis on this Mac: the plugin in each harness, the runtime, Codex's settings,
and optionally a workspace's repositories or an organization's configuration.

    python3 setup.py                     # interactive: everything, asking what it cannot detect
    python3 setup.py plugin [--clients claude,codex,muse] [--ref stable|main|vX.Y.Z]
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
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from synthesis import doctor, install  # noqa: E402  (the plugin's own core: listings, CLI finder, TOML reader)

PLUGIN, MARKETPLACE, SOURCE = "synthesis-skills", "synthesis-engineering", "synthesisengineering/synthesis-skills"
CODEX_DOC_BYTES = 98_304
HOOKS_BEGIN, HOOKS_END = "# synthesis-setup:begin hooks-feature", "# synthesis-setup:end hooks-feature"
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
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def _json(text: str):
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    try:
        return json.JSONDecoder().raw_decode(text[min(starts):])[0] if starts else None
    except ValueError:
        return None


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
    data = _json(run([binary, "plugin", "list", "--json"], 60).stdout)
    if data is None:  # some builds print text; never crash on it, never take it for "absent"
        raise SetupError(f"{client} printed no plugin list; refusing to guess whether synthesis is installed")
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return doctor.claude_entry(data) if client == "claude" else doctor.codex_entry(data, codex_home)


def configured_ref(client: str):
    """The git ref the harness's synthesis marketplace tracks, or None when unknown."""
    try:
        if client == "claude":
            known = json.loads((Path.home() / ".claude" / "plugins" / "known_marketplaces.json").read_text())
            source = (known.get(MARKETPLACE) or {}).get("source") or {}
            return source.get("ref") if source.get("repo") == SOURCE else None
        codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        config = doctor.read_toml((codex_home / "config.toml").read_text(encoding="utf-8"))
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


def codex_overlay(text: str) -> tuple:
    """(new text, notes). Hooks on unless the person set them off; instruction bytes at least
    98,304; CLAUDE.md as a fallback instruction name when the key is absent. Nothing else changes."""
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
    return "\n".join(lines).strip("\n") + "\n", notes


def configure_codex(dry_run: bool = False) -> list:
    path = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    new, notes = codex_overlay(text)
    if new == (text if text.endswith("\n") else text + "\n") or dry_run:
        return [f"codex config: {'would ' if dry_run else ''}{n}" for n in notes] or ["codex config: already set"]
    if path.exists():
        backup = install._home() / "backups" / f"codex-config.toml.{time.strftime('%Y%m%dT%H%M%S')}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        notes.append(f"backed up the previous file to {backup}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, path)
    return [f"codex config: {n}" for n in notes]


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


def _nudge_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{NUDGE_LABEL}.plist"


def _points_at(plist: Path, target: Path) -> bool:
    import plistlib
    try:
        return str(target) in " ".join(plistlib.loads(plist.read_bytes()).get("ProgramArguments") or [])
    except (OSError, ValueError):
        return False


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
    spec["ProgramArguments"] = ["/bin/bash", "-lc", f'exec "{nudge}"']  # a login shell, for the user's PATH
    if plist.exists() and not _points_at(plist, nudge):
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
    if plist.exists() and _points_at(plist, home / "bin" / "day-end-nudge.sh"):
        if not dry_run:
            run([LAUNCHCTL, "bootout", f"gui/{os.getuid()}/{NUDGE_LABEL}"], 30)
            plist.unlink()
        lines.append(f"{'would remove' if dry_run else 'removed'} the nudge schedule {plist}")
    elif plist.exists():
        lines.append(f"kept {plist}: it runs another install's nudge")
    if link.is_symlink() and os.path.realpath(link) == os.path.realpath(home / "bin" / "day-end"):
        if not dry_run:
            link.unlink()
        lines.append(f"{'would remove' if dry_run else 'removed'} {link}")
    elif os.path.lexists(link):
        lines.append(f"kept {link}: it is not a link to this install's launcher")
    return lines


def workspace_archive(paths: list) -> Path:
    import workspace
    return workspace._archive(paths)


# ---- the command line -----------------------------------------------------------

def setup_plugins(clients: list, ref: str, dry_run: bool) -> tuple:
    lines, failed = [], False
    for client in clients:
        binary = doctor.find_client(client)
        if not binary:
            lines.append(f"{client}: not found on this Mac; skipped")
            continue
        try:
            lines.append(install_plugin(client, binary, ref, dry_run=dry_run))
            if client == "codex":
                lines += configure_codex(dry_run)
        except SetupError as exc:
            lines.append(str(exc))
            failed = True
    return lines, failed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="setup.py", description=__doc__.split("\n\n")[0])
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
    parser.add_argument("--no-launchctl", action="store_true", help="--day-end: write the schedule without loading it")
    parser.add_argument("--no-input", action="store_true", help="never ask; fail naming the flag instead")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    interactive = not args.no_input and can_ask()
    clients = [c.strip() for c in (args.clients or "claude,codex,muse").split(",") if c.strip() in doctor.HARNESSES]
    failed = False

    def say(lines):  # each step's lines as soon as it finishes, so a long run never looks hung
        print("\n".join(lines), flush=True)
    try:
        if args.org_repo and args.command == "all":  # the organization's clients and release, unless given here
            import workspace
            org_clients, org_ref = workspace.org_preferences(args.org_repo)
            clients, args.ref = (clients if args.clients else org_clients), args.ref or org_ref
        if args.command == "uninstall":
            return _uninstall(clients, args.dry_run)
        if args.command in ("all", "plugin"):
            plugin_lines, failed = setup_plugins(clients, args.ref, args.dry_run)
            say(plugin_lines)
            if not args.dry_run:
                git_hooks = args.git_hooks or (interactive and args.command == "all" and confirm(
                    "Run the synthesis commit check (secrets, disclosures, other sessions' claims) in every repository?",
                    "--git-hooks", default=True))
                say(install_runtime(git_hooks) + first_config(interactive and args.command == "all"))
                if args.day_end:
                    say(register_day_end(args.day_end, load=not args.no_launchctl))
        if args.command in ("workspace", "org") or (args.command == "all" and (args.kb or args.org_repo or args.new or (
                interactive and confirm("Bring a workspace's repositories onto this Mac?", "--kb", default=False)))):
            import workspace
            progress = lambda line: print(line, flush=True)  # noqa: E731
            if args.command == "org" or args.org_repo:
                say(workspace.enroll(args.org_repo or ask("Organization config repository URL", "--org-repo"),
                                     progress, args.personal_source, args.adopt_workspace_instructions))
            elif args.new:
                say(workspace.new_workspace(args.new, args.kb))
            else:
                say(workspace.bring_workspace(args.kb, args.workspace, progress, args.adopt_workspace_instructions,
                                              interactive))
    except (SetupError, ValueError, OSError) as exc:  # a malformed manifest or an unwritable folder: say which
        say([f"stopped: {exc}"])
        failed = True
    except KeyboardInterrupt:
        print("\ninterrupted: run the same command again to resume; finished steps are kept", file=sys.stderr)
        return 130
    if args.command != "workspace" and not args.dry_run:
        print(RESTART)
    return 1 if failed else 0


def _uninstall(clients: list, dry_run: bool) -> int:
    lines = []
    for client in clients:
        binary = doctor.find_client(client)
        try:
            if not binary or not plugin_entry(client, binary):
                lines.append(f"{client}: {PLUGIN} not installed")
                continue
        except SetupError as exc:
            lines.append(str(exc))
            continue
        step = {"claude": [binary, "plugin", "uninstall", f"{PLUGIN}@{MARKETPLACE}", "--yes"],
                "codex": [binary, "plugin", "remove", f"{PLUGIN}@{MARKETPLACE}", "--json"],
                "muse": [binary, "plugins", "remove", PLUGIN, "--json"]}[client]
        proc = subprocess.CompletedProcess(step, 0, "", "") if dry_run else run(step)
        lines.append(f"{client}: {'would remove' if dry_run else 'removed'} {PLUGIN}" if not proc.returncode
                     else f"{client}: removal failed: {_tail(proc)}")
    lines += unregister_day_end(dry_run) + install.uninstall(dry_run=dry_run)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

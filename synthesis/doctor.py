"""`synthesis doctor`: is every part installed, current and wired? (R7.1, R7.5-R7.7, R3.8, R8.1)

One line per check, after a first line that says healthy or not with counts.
Harness state is read only through each CLI's read-only listing command and its
config files; doctor never writes either. Each check is a small function over
plain inputs, so tests feed fake ones.

    main(["--json"])   # argv without the program name; returns the exit code
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import install, paths  # noqa: E402

PLUGIN = "synthesis-skills"
STABLE_HOOK = "$HOME/.synthesis/v5/bin/synthesis-hook"
EVENTS = {"SessionStart": "session-start", "UserPromptSubmit": "user-prompt-submit",
          "PreToolUse": "pre-tool-use", "Stop": "stop"}
HARNESSES = ("claude", "codex", "muse")
MARKETPLACE = "synthesis-engineering"  # the one marketplace the plugin ships from
CODEX_WHOLE = ["plugin", "list", "--json"]
LISTINGS = {  # each harness's own read-only listing command
    "claude": ["plugin", "list", "--json"],
    # Asked for one marketplace, Codex fetches no remote catalog. Its whole listing fetches one when its copy is over
    # three hours old (73 MB and 52 s on 2026-11-13), and the limit below stopped that fetch on every run.
    "codex": CODEX_WHOLE + ["-m", MARKETPLACE],
    "muse": ["plugins", "inspect", PLUGIN, "--json"],
}
HOOK_BUDGET_MS = 50
CODEX_DOC_BYTES = 98_304
CODEX_DEFAULT_DOC_BYTES = 32_768
CLI_TIMEOUT = 45  # `codex plugin list` took 33 s on a slow network on 2026-10-10; it is still bounded
SELF_TEST = {"tool_name": "Bash", "tool_input": {"command": "rm -rf ~"}}


class Check(NamedTuple):
    status: str  # ok, warn, fail; info is report-only and never affects health
    name: str
    detail: str


def _short(path) -> str:
    text, home = str(path), str(Path.home())
    return "~" + text[len(home):] if text == home or text.startswith(home + os.sep) else text


# ---- the stable runtime -------------------------------------------------------

def runtime_hash(home: Path) -> str:
    """Hash of the code `current` actually holds, read from its bytes."""
    return install.package_hash(home / "current") if (home / "current" / "synthesis" / "hook.py").is_file() else ""


def check_runtime(home: Path) -> Check:
    hook, current = home / "bin" / "synthesis-hook", home / "current"
    if not (hook.is_file() and os.access(hook, os.X_OK)):
        return Check("fail", "runtime", f"no stable hook at {_short(hook)}; start a session in any harness or run install")
    actual = runtime_hash(home)
    if not actual:
        return Check("fail", "runtime", f"{_short(current)} does not resolve to an installed release")
    try:
        recorded = (current / "HASH").read_text(encoding="utf-8").strip()
    except OSError:
        recorded = ""
    if recorded != actual:
        return Check("fail", "runtime", f"files under {_short(current)} changed since install "
                                        f"(recorded {recorded or 'nothing'}, found {actual}); run install")
    return Check("ok", "runtime", f"current -> {_short(os.path.realpath(current))} ({actual})")


def check_hook_script(home: Path) -> Check:
    hook = home / "bin" / "synthesis-hook"
    try:
        text = hook.read_text(encoding="utf-8")
    except OSError:
        return Check("fail", "hook script", f"{_short(hook)} is missing")
    if text != install.HOOK_SCRIPT:
        return Check("fail", "hook script", f"{_short(hook)} differs from the shipped text; run install")
    return Check("ok", "hook script", "stable entry text matches this release")


def check_config(home: Path) -> Check:
    file = home / "config.json"
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Check("warn", "config", f"{_short(file)} is missing; guards run on defaults (install writes it)")
    except (OSError, ValueError) as exc:
        return Check("fail", "config", f"{_short(file)} does not parse ({exc}); send and deploy guards block everything")
    if not isinstance(data, dict):
        return Check("fail", "config", f"{_short(file)} must hold a JSON object, not {type(data).__name__}")
    return Check("ok", "config", f"{_short(file)} parses ({len(data)} keys)")


def run_hook(home: Path, payload: dict, run=subprocess.run):
    """Run the stable hook's pre-tool-use once. Returns (denied, reason, ms)."""
    start = time.perf_counter()
    try:
        stdout = run([str(home / "bin" / "synthesis-hook"), "pre-tool-use"], input=json.dumps(payload),
                     capture_output=True, text=True, timeout=10, env={**os.environ, "SYNTHESIS_HOME": str(home)}).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run: {exc}", (time.perf_counter() - start) * 1000
    ms = (time.perf_counter() - start) * 1000
    try:
        decision = json.loads(stdout)["hookSpecificOutput"]
    except (ValueError, KeyError, TypeError):
        return False, "", ms
    return decision.get("permissionDecision") == "deny", str(decision.get("permissionDecisionReason", "")), ms


def background_priority() -> bool:
    """True when this process runs at background priority, as a launchd Background job or under `taskpolicy -b`
    does. macOS throttles it, so a latency it measures says nothing about the hook at normal priority."""
    if sys.platform != "darwin":
        return os.getpriority(os.PRIO_PROCESS, 0) >= 10
    pri = subprocess.run(["ps", "-o", "pri=", "-p", str(os.getpid())], capture_output=True, text=True).stdout.strip()
    return pri.isdigit() and int(pri) <= 4


def check_self_test(home: Path, runs: int = 3, run=subprocess.run, background=background_priority) -> Check:
    """Send `rm -rf ~` to the stable hook (it only inspects); it must deny, within the budget. The fastest run is
    the hook's own cost: other work on the Mac only adds time (2026-11-02: a median of 161 ms beside a busy scan).
    At background priority the timing is reported, not judged (the Console's service read 131 ms; 37 ms otherwise)."""
    results = [run_hook(home, SELF_TEST, run) for _ in range(runs)]
    ms = min(r[2] for r in results)
    denied, reason = results[-1][0], results[-1][1]
    if not denied or "recursive delete" not in reason:
        return Check("fail", "hook self-test", f"the stable hook let `rm -rf ~` through ({reason or 'no decision'})")
    if ms > HOOK_BUDGET_MS and background():
        return Check("info", "hook self-test", f"denied `rm -rf ~` in {ms:.0f} ms at background priority, which macOS "
                     f"throttles; the {HOOK_BUDGET_MS} ms budget is for a normal call")
    if ms > HOOK_BUDGET_MS:
        return Check("warn", "hook self-test", f"denied `rm -rf ~` in {ms:.0f} ms, over the {HOOK_BUDGET_MS} ms budget")
    return Check("ok", "hook self-test", f"denied `rm -rf ~` in {ms:.0f} ms")


def check_wait_check() -> Check:
    """The turn-end check must send back a reply that announces a wait with nothing armed."""
    from synthesis import reply_check
    reason = reply_check.check({"last_assistant_message": "The build is running; I'll pick it up once it lands.",
                                "session_id": "doctor-self-test"}, {})
    if reason and "nothing is armed" in reason:
        return Check("ok", "wait check", "a reply that announces a wait with nothing armed is sent back")
    return Check("fail", "wait check", "a reply that announced a wait with nothing armed was not sent back: waits can end a turn unseen")


def check_prompt_check(cfg: dict | None, error: str = "") -> Check | None:
    """Where the day's prompt check is on: the workspaces whose day does not close while something the principal
    typed is cited by no record, and the ones where nothing asks. Each workspace's setting is read as its day-end
    reads it (`rituals.prompt_check`, over its settings with the defaults under them); one the day-end refuses is a
    warning, since no day of that workspace closes until it is mended. Otherwise information: turning the check on
    is each workspace's own word (measured 2026-11-13: on for one workspace of three; 8 of 267 session entries
    cited a record)."""
    if cfg is None:
        return Check("warn", "prompt check", f"cannot tell: the rituals' config cannot be read ({error})")
    from synthesis import rituals
    on, off, refused = [], [], []
    unlisted = [""] if "prompt_reconcile" in (cfg.get("defaults") or {}) else []  # a workspace the config does not list reads the defaults
    for space in [*(cfg.get("workspaces") or {}), *unlisted]:
        label = space or "any workspace the config does not list"
        try:
            found = rituals.prompt_check(rituals.settings(cfg, space))
        except ValueError as exc:
            refused.append(f"every day-end of {label} is refused: {exc.args[0]}")
        else:
            if found or space:  # that the defaults leave it off is said of each workspace listed
                (on if found else off).append(f"{label} (from {found[1]})" if found and found[1] else label)
    said = refused + [f"on for {', '.join(on)}" if on else "on for no workspace"] + (
        [f"off for {', '.join(off)}, where nothing asks whether what the principal typed reached a record"] if off else [])
    return Check("warn" if refused else "info", "prompt check", "; ".join(said)) if on or off or refused else None


def check_temporary_addresses(config: dict) -> Check:
    """Under this config a message that carries a quick tunnel's address must be read as one."""
    from synthesis import guards
    found = guards.temporary_addresses(["https://doctor-probe.trycloudflare.com/x"], config)
    if found and not isinstance(found, str):
        return Check("ok", "temporary addresses", "a message that carries a quick tunnel's address is refused until the "
                     "principal approves the address itself, and starting a quick tunnel waits for a code")
    return Check("fail", "temporary addresses", found or "a quick tunnel's address in a message was not read: it could reach other people")


def check_shell_name(home: Path, harness: str, tool: str, run=subprocess.run) -> Check:
    """Does the guard treat this harness's own shell tool name as a shell?"""
    if run_hook(home, {**SELF_TEST, "tool_name": tool}, run)[0]:
        return Check("ok", f"{harness} shell guard", f"guards the shell tool name `{tool}`")
    return Check("warn", f"{harness} shell guard", f"the guard lets `rm -rf ~` through as tool `{tool}`, "
                                                  f"the name {harness} uses for its shell")


# ---- harness plugin state -----------------------------------------------------

def check_plugin(harness: str, entry: dict | None, error: str = "") -> Check:
    """entry: {"enabled": bool, "version": str, "path": Path | None, "problem": str}."""
    if entry is None:  # a CLI that never answered says nothing about the install: warn, never pass or fail
        return Check("warn" if error.startswith("cannot tell") else "fail", f"{harness} plugin", error or f"{PLUGIN} is not installed")
    if entry.get("problem"):
        return Check("fail", f"{harness} plugin", entry["problem"])
    if not entry.get("enabled"):
        return Check("fail", f"{harness} plugin", f"{PLUGIN} {entry.get('version', '')} is installed but disabled")
    where = _short(entry["path"]) if entry.get("path") else "path unknown"
    return Check("ok", f"{harness} plugin", f"{PLUGIN} {entry.get('version', '')} installed and enabled at {where}")


def check_package(harness: str, plugin_root: Path | None, runtime: str) -> Check:
    """The plugin bytes the harness loaded must equal the runtime's (never compare version labels)."""
    name = f"{harness} package"
    if plugin_root is None or not (plugin_root / "synthesis" / "hook.py").is_file():
        return Check("fail", name, f"the installed plugin has no v5 runtime package ({_short(plugin_root) if plugin_root else 'no path'})")
    if not runtime:
        return Check("fail", name, "no runtime to compare against (see runtime)")
    found = install.package_hash(plugin_root)
    if found != runtime:
        return Check("fail", name, f"plugin code {found} differs from the runtime {runtime}; "
                                   "start a session in this harness to update, or reinstall the plugin")
    if (plugin_root / "synthesis" / "__pycache__").exists():
        return Check("warn", name, f"matches the runtime ({found}), but something wrote __pycache__ into the plugin folder")
    return Check("ok", name, f"plugin code matches the runtime ({found})")


def hooks_json_entries(data: dict) -> list:
    """(event, matcher, handler) for every handler in a Claude or Codex hooks.json."""
    return [(event, group.get("matcher"), handler) for event, groups in (data.get("hooks") or {}).items()
            for group in groups or [] for handler in group.get("hooks") or []]


def calls_stable_hook(event: str, command) -> bool:
    """Whether a hook's command runs the stable hook with this event's own argument."""
    text = str(command or "").replace("${HOME}", "$HOME")
    return STABLE_HOOK in text and EVENTS.get(event, "\0") in text


def check_hooks_wired(harness: str, commands: list) -> Check:
    """commands: (event, command text) pairs; each needed event must call the stable hook with its own event."""
    missing = [event for event in EVENTS if not any(calls_stable_hook(event, c) for e, c in commands if e == event)]
    if missing:
        return Check("fail", f"{harness} hooks", f"not wired to the stable hook: {', '.join(missing)}")
    return Check("ok", f"{harness} hooks", "all four events call the stable hook")


# ---- Codex --------------------------------------------------------------------

def codex_hook_hash(event: str, matcher, handler: dict) -> str:
    """Codex's trust hash for one command handler (codex-rs hooks discovery and config fingerprint, 0.160.0):
    sha256 of the canonical JSON of {event_name, matcher, hooks: [normalized handler]}."""
    timeout = handler.get("timeout")
    if event in ("SessionEnd", "Interrupt"):
        timeout = min(max(timeout or 1, 1), 3)
    else:
        timeout = max(600 if timeout is None else timeout, 1)
    normalized = {"type": "command", "command": handler.get("command", ""), "timeout": timeout,
                  "async": bool(handler.get("async", False))}
    if handler.get("statusMessage") is not None:
        normalized["statusMessage"] = handler["statusMessage"]
    limit = handler.get("additionalContextLimit")
    if limit is not None and limit != 2500 and event in ("PreToolUse", "PostToolUse", "SessionStart",
                                                         "UserPromptSubmit", "SubagentStart"):
        normalized["additionalContextLimit"] = limit
    identity = {"event_name": _snake(event), "hooks": [normalized]}
    if matcher is not None and event not in ("UserPromptSubmit", "Stop", "Interrupt"):
        identity["matcher"] = matcher
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def codex_plugin_hash(root: Path) -> str:
    """Codex's fingerprint of an installed plugin (codex-rs hooks plugin_fingerprint.rs, 0.166): sha256 over every
    entry in sorted depth-first order, with its relative path, kind, size and bytes, skipping bytecode, virtual
    environments and package metadata. Codex stores it with a hook approval and runs no hook of a plugin whose
    fingerprint has changed; this reproduced the value Codex stored for synthesis 5.3.14 (2026-11-05)."""
    digest, pending = hashlib.sha256(b"codex-plugin-bundle-v1"), [(Path(root), "")]
    while pending:
        path, rel = pending.pop()
        name = rel.rsplit("/", 1)[-1]
        if name in ("__pycache__", ".venv") or name.endswith((".pyc", ".egg-info")):
            continue
        raw = os.fsencode(rel)
        digest.update(struct.pack("<Q", len(raw)) + raw)
        info = os.lstat(path)
        if stat.S_ISDIR(info.st_mode):
            digest.update(b"directory")
            pending += [(path / n, f"{rel}/{n}" if rel else n) for n in sorted(os.listdir(path), key=os.fsencode,
                                                                              reverse=True)]
        elif stat.S_ISREG(info.st_mode):
            digest.update(b"file" + struct.pack("<Q", info.st_size) + path.read_bytes())
        else:
            raise ValueError(f"{rel} is neither a file nor a folder")
    return "sha256:" + digest.hexdigest()


def codex_trust_baseline(codex_home: Path, plugin_id: str) -> Path:
    """Where Codex keeps the fingerprint it pinned for approvals made before it stored one with each (plugin_trust.rs:
    .hook-trust/ beside config.toml, named by a hash of that file's path and the plugin id)."""
    key = b"".join(struct.pack("<Q", len(part)) + part
                   for part in (os.fsencode(str(Path(codex_home) / "config.toml")), plugin_id.encode()))
    return Path(codex_home) / ".hook-trust" / hashlib.sha256(key).hexdigest()


CODEX_HANDLERS = {"command": ("command",), "mcp_tool": ("server", "tool"), "prompt": (), "agent": ()}  # the text each needs


def codex_hooks_problem(data) -> str:
    """Why Codex would read none of a hooks.json, or '': codex-rs reads the whole file or nothing (HooksFile): only
    `hooks` and a `description` at its top, each event a list of groups, a group's matcher text, each of its hooks
    of a type Codex knows with the text that type needs and a whole number of seconds as its timeout."""
    events = data.get("hooks", {}) if isinstance(data, dict) else None
    if not isinstance(events, dict) or set(data) - {"hooks", "description"} or not isinstance(data.get("description") or "", str):
        return "its top level must be an object holding `hooks` and at most a `description`"
    for event, groups in events.items():
        for group in groups if isinstance(groups, list) else [None]:
            hooks, matcher = (group.get("hooks", []), group.get("matcher")) if isinstance(group, dict) else (None, None)
            if not isinstance(hooks, list) or not (matcher is None or isinstance(matcher, str)):
                return f"{event} must be a list of groups, each with a text matcher and a list of hooks"
            for hook in hooks:
                kind, timeout = (hook.get("type"), hook.get("timeout")) if isinstance(hook, dict) else (None, None)
                need = CODEX_HANDLERS.get(kind) if isinstance(kind, str) else None
                if need is None or not all(isinstance(hook.get(k), str) for k in need) or not (
                        timeout is None or type(timeout) is int and timeout >= 0):
                    return f"a {event} hook is not one Codex reads (a known type, the text it needs, a whole-number timeout)"
    return ""


def codex_user_declaration(plugin_hooks: dict) -> dict:
    """{event: groups}: the plugin's hooks as `setup.py plugin --codex-user-hooks` declares them in Codex's own
    hooks.json, every group as the plugin writes it and each command the stable hook with its event. The plugin's
    session start also names its own folder, so a first run can install the runtime; a user-level hook has no folder
    to name, and setup has installed the runtime by then."""
    return {event: [{**group, "hooks": [{**hook, "command": f'"{STABLE_HOOK}" {EVENTS[event]}'} for hook in group.get("hooks") or []]}
                    for group in groups or []] for event, groups in (plugin_hooks.get("hooks") or {}).items() if event in EVENTS}


def _declared(group: dict) -> dict:
    """A group apart from how its commands name the stable hook ($HOME or ${HOME}), which the person may write."""
    return {**group, "hooks": [{**hook, "command": ""} for hook in group.get("hooks") or []]}


def codex_user_entries(codex_home: Path) -> tuple:
    """({event: [(event:group:place, group, hook)]} for each hook in Codex's own hooks.json that runs the stable hook
    with its event, why Codex reads none of that file or '')."""
    file = Path(codex_home) / "hooks.json"
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, ""
    except (OSError, ValueError) as exc:
        return {}, f"Codex cannot read {_short(file)} ({exc}), so it runs none of the hooks declared there"
    problem = codex_hooks_problem(data)
    if problem:
        return {}, f"Codex reads none of {_short(file)}: {problem}"
    found = {}
    for event, groups in data.get("hooks", {}).items():
        for gi, group in enumerate(groups):
            for hi, hook in enumerate(group.get("hooks", [])):
                if calls_stable_hook(event, hook.get("command")):
                    found.setdefault(event, []).append((f"{_snake(event)}:{gi}:{hi}", group, hook))
    return found, ""


def _snake(event: str) -> str:
    return "".join("_" + c.lower() if c.isupper() else c for c in event).lstrip("_")


def check_codex_features(config: dict) -> Check:
    value = (config.get("features") or {}).get("hooks")
    if value is True:
        return Check("ok", "codex hooks feature", "[features] hooks = true")
    if value is False:
        return Check("fail", "codex hooks feature", "[features] hooks = false: no synthesis guard runs in Codex")
    return Check("warn", "codex hooks feature", "[features] hooks is not set; Codex 0.160 defaults it on, "
                                               "but older builds do not: set hooks = true")


def toml_strings(raw) -> list:
    """The strings in a raw TOML array, as read_toml keeps arrays."""
    found = re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', raw if isinstance(raw, str) else "")
    return [json.loads(f'"{basic}"') if basic else literal for basic, literal in found]


def codex_write_roots(config: dict) -> tuple:
    """(the folders Codex's config lets its sandbox write beyond the workspace, whether it runs with no sandbox).
    With `sandbox_mode` set Codex reads the older [sandbox_workspace_write]; otherwise the permissions profile
    `default_permissions` names (the built-in :workspace when unset), through `extends` (Codex 0.166's docs)."""
    mode = config.get("sandbox_mode")
    if mode is not None:
        table = config.get("sandbox_workspace_write")
        return toml_strings((table if isinstance(table, dict) else {}).get("writable_roots")), mode == "danger-full-access"
    name, found, seen = config.get("default_permissions") or ":workspace", [], set()
    while isinstance(name, str) and not name.startswith(":") and name not in seen:
        seen.add(name)
        profile = (config.get("permissions") or {}).get(name)
        profile = profile if isinstance(profile, dict) else {}
        rules = profile.get("filesystem") if isinstance(profile.get("filesystem"), dict) else {}
        found += [path for path, access in rules.items() if access == "write" and not path.startswith(":")]
        name = profile.get("extends")
    return found, name == ":danger-full-access"


def check_codex_board(config: dict, board: Path, state: Path, outbox: Path) -> Check:
    """Codex's sandbox writes only the workspace and the folders its config grants: without the board among them, a
    Codex session can neither claim files nor post (2026-10-30), and without the outbox it cannot stage a file it
    attaches. A grant over the state folder would let a sandboxed agent write approvals and send windows."""
    found, unsandboxed = codex_write_roots(config)
    roots = [os.path.realpath(os.path.expanduser(r)) for r in found]
    exposed = [r for r in roots if paths.inside(os.path.realpath(state), r)]
    if exposed:
        return Check("fail", "codex board access", f"Codex's config lets its sandbox write {_short(exposed[0])}, which holds "
                     f"{_short(state)}, where approvals and send windows live; grant only {_short(board)} and {_short(outbox)}")
    if unsandboxed:
        return Check("ok", "codex board access", "Codex runs without a sandbox (danger-full-access)")
    for folder, cost in ((board, "can neither claim files nor post on the board"), (outbox, "cannot stage a file it attaches")):
        if not any(paths.inside(os.path.realpath(folder), r) for r in roots):
            return Check("fail", "codex board access", f"Codex's sandbox cannot write {_short(folder)}, so a Codex session "
                         f"{cost}: run the onboarding setup for codex again")
    return Check("ok", "codex board access", f"Codex's sandbox may write {_short(board)} and {_short(outbox)}")


def check_claude_retention(settings: Path) -> Check:
    """Claude Code deletes a transcript idle past cleanupPeriodDays, 30 when unset, at its next start (2026-10-30:
    this Mac kept 9 main sessions from August and 11 from September, against 97 from October)."""
    try:
        days = json.loads(settings.read_text(encoding="utf-8")).get("cleanupPeriodDays")
    except (OSError, ValueError, AttributeError):
        days = None
    if not isinstance(days, int) or isinstance(days, bool):
        return Check("fail", "claude transcripts", "cleanupPeriodDays is unset, so Claude Code deletes a transcript idle "
                     "30 days: run the onboarding setup for claude")
    if days < 365:
        return Check("warn", "claude transcripts", f"cleanupPeriodDays = {days}: run `synthesis sessions export` at "
                     "least that often, or Claude Code deletes transcripts first")
    return Check("ok", "claude transcripts", f"kept {days:,} days")


CLAUDE_ON_FAILURE = (2, 1, 295)  # the first Claude Code that honors a hook's onFailure (its hooks reference)


def claude_version(binary: str) -> str:
    """The version `claude --version` prints first, or '' when it prints none in time."""
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    found = re.match(r"\s*(\d+(?:\.\d+)+)", out)
    return found.group(1) if found else ""


def check_claude_fail_closed(hooks: dict, version: str) -> Check:
    """Claude Code lets a call through when its PreToolUse hook times out, crashes or cannot start, unless the handler
    says "onFailure": "block", which it honors from 2.1.295 (5.21.0). Codex and Muse have no such setting."""
    handlers = [handler for event, _, handler in hooks_json_entries(hooks or {}) if event == "PreToolUse"]
    if not handlers or any(handler.get("onFailure") != "block" for handler in handlers):
        return Check("fail", "claude fail closed", 'the installed plugin\'s PreToolUse hook lacks "onFailure": "block", so a '
                     "guard that times out or crashes lets the call through: update the plugin")
    if not version:
        return Check("warn", "claude fail closed", "cannot tell which Claude Code this is, so whether it holds a guarded "
                     "call when the guard times out or crashes")
    if tuple(int(n) for n in version.split(".")) < CLAUDE_ON_FAILURE:
        return Check("warn", "claude fail closed", f"Claude Code {version} ignores onFailure (2.1.295 or later honors it), "
                     "so a guard that times out or crashes lets the call through: update Claude Code")
    return Check("ok", "claude fail closed", f"Claude Code {version} holds a guarded call when the guard times out, crashes "
                 "or cannot start")


def check_sessions_repos(repos: dict, state: Path, now: float = 0) -> list:
    """Each workspace's sessions repo (R10.2): cloned where config `sessions_repos` says, synced within two days,
    and small enough to clone (GitHub advises under 5 GB; this warns at 3 GB)."""
    found = []
    for ws, repo in sorted(repos.items()):
        if not (repo / ".git").is_dir():
            found.append(Check("warn", f"sessions repo {ws}", f"{_short(repo)} is not cloned; clone it there, then run "
                               "`synthesis sessions sync`"))
            continue
        synced = paths.read_json(state / f"sync-{ws}.json").get("synced", "")
        size = sum(f.stat().st_size for f in (repo / ".git").rglob("*") if f.is_file())
        try:
            age = ((now or time.time()) - datetime.fromisoformat(synced.replace("Z", "+00:00")).timestamp()) / 86400
        except ValueError:
            age = None
        if size >= 3e9:
            found.append(Check("warn", f"sessions repo {ws}", f"{size / 1e9:.1f} GB: start a new repo for this "
                               "workspace before it passes GitHub's 5 GB advice"))
        elif age is None or age > 2:
            found.append(Check("warn", f"sessions repo {ws}", "never synced" if age is None else
                               f"last synced {synced[:10]}: run `synthesis sessions sync`"))
        else:
            found.append(Check("ok", f"sessions repo {ws}", f"synced {synced[:16]}, {size / 1e6:,.0f} MB"))
    return found


def check_sessions_export(plist: Path, stamp: Path, now: float = 0, run=subprocess.run, command: Path = None) -> Check:
    """The hourly copy of session transcripts (2026-11-11: the archive had no trigger of its own): no export left a
    transcript it could not copy; then scheduled, loaded, running this home's own `command` (2026-11-12: another
    install's schedule under the one label read as this home's), and an export finished within the last day, by this job or any session."""
    how, command = "python3 <synthesis-onboarding>/scripts/setup.py plugin --sessions-export", command or paths.home() / "bin" / "synthesis"
    last = paths.read_json(stamp)
    if last.get("failed"):
        since = f"since {str(last['complete'])[:16]}" if last.get("complete") else "yet"
        gone = [f"{name} (its copy last failed {str(entry.get('at'))[:16]})" for name, entry in (last.get("uncopied") or {}).items()
                if entry.get("gone")]  # removed before any run copied it: no run can now
        return Check("fail", "sessions export", f"{last['failed']} transcript(s) could not be copied ("
                     + str(last.get("reason", "")).replace(str(Path.home()), "~") + f"), and no run has copied everything {since}"
                     + (": run `synthesis sessions export --all` and read its lines" if last["failed"] > len(gone) else "")
                     + (f". Gone before a copy was made, so what {'it' if len(gone) == 1 else 'they'} held is not in the archive: "
                        f"{', '.join(gone)}. Tell the principal, who alone clears one: `synthesis sessions export --lost <session>`"
                        if gone else ""))
    if not plist.exists():
        return Check("warn", "sessions export", "not scheduled: transcripts are copied only when a session runs resume, "
                     f"handoff or a ritual ({how})")
    if run(["launchctl", "print", f"gui/{os.getuid()}/{plist.stem}"], capture_output=True, text=True).returncode:
        return Check("fail", "sessions export", f"{_short(plist)} is not loaded, so nothing copies transcripts on a schedule ({how})")
    if not install.runs_only(plist, command):  # this home's fresh stamp says nothing of whose schedule the label holds
        others = ", ".join(dict.fromkeys(_short(p) for p in install.scheduled(plist) if p and p != str(command)))
        return Check("fail", "sessions export", f"{_short(plist)} is loaded and runs {others or 'no command that can be read'}, not this install's "
                     f"{_short(command)}, so no schedule of this install's own copies this home's transcripts ({how}, which sets that one aside)")
    try:
        age = ((now or time.time()) - datetime.fromisoformat(last.get("exported", "")).timestamp()) / 3600
    except ValueError:
        age = None
    if age is None or age > 24:
        return Check("fail", "sessions export", "scheduled, and no export has finished " + ("yet" if age is None else f"in {age:.0f} hours")
                     + f": read /tmp/{plist.stem}.log")
    try:  # launchd runs what it loaded, which a file replaced since does not show: the schedule's own run does
        own = ((now or time.time()) - datetime.fromisoformat(last.get("scheduled", "")).timestamp()) / 3600
    except ValueError:
        own = None
    if own is None or own > 24:
        return Check("fail", "sessions export", "loaded, and the schedule itself has finished no export "
                     + ("yet" if own is None else f"in {own:.0f} hours") + ": launchd may hold an older schedule under this label, "
                     f"or the job cannot run ({how}, which loads this one again; it writes /tmp/{plist.stem}.log)")
    return Check("ok", "sessions export", f"every hour; the last one finished {age * 60:.0f} min ago")


def live_claims(sessions: list) -> list:
    """The claims of the seats still at work. A seat gone quiet past the board's stale mark leaves its claims to the
    stale-claim review (`synthesis who --all`), not to the unsaved count (5.20.0: on the principal's Mac they made the
    line name 54 repositories)."""
    return [c for s in sessions if not s.stale for c in (s.claims or [])]


def _unsaved_repo(repo: str, under: list, hours: float, now: float):
    """One repository's count for `unsaved`: the tuple, the reason git could not read it, or None."""
    from synthesis import board, checkout

    def claimed(rel):
        full = os.path.join(repo, rel)
        return any(full == base or board.overlaps(claim, full) for claim, base in under)
    spec = ["--", *sorted({os.path.relpath(base, repo) for _, base in under})]
    changed, committed, rows = {}, {}, checkout._changes(repo, True, *spec)
    if rows is None:
        return "git could not read its status"
    for rel in (row[3:].rstrip("/") for row in rows):
        where = os.path.join(repo, rel)
        while where != repo and not os.path.lexists(where):  # deleted: as old as the nearest folder still there
            where = os.path.dirname(where)
        changed[rel] = (now - os.lstat(where).st_mtime) / 3600
    if checkout._git(repo, "remote")[1].strip():  # the checkout's own branch, names as written (-z: never quoted)
        code, out = checkout._git(repo, "log", "-z", "--format=%x00%ct", "--name-only", "HEAD", "--not", "--remotes", *spec)
        when, fresh = 0, True
        for token in out.split("\0") if code == 0 else []:
            if not token:
                fresh = True
            elif fresh and token.isdigit():
                when, fresh = int(token), False
            else:
                rel = token.lstrip("\n")
                committed[rel] = max(committed.get(rel, 0.0), (now - when) / 3600)
    late = {r: a for r, a in changed.items() if a > hours and claimed(r)}
    gone = {r: a for r, a in committed.items() if a > hours and claimed(r)}
    return (len(set(late) | set(gone)), max([*late.values(), *gone.values()]), len(late), len(gone)) if late or gone else None


def unsaved(claims: list, hours: float, now: float = 0) -> dict:
    """Records that leave this Mac (plan item 13.5, part 2): per repository, the files under these claims that are
    uncommitted, or in a commit no remote holds, for longer than `hours`. {repo: (files, the oldest in hours,
    uncommitted, in unpushed commits)}, or the reason git could not read the repository, which is said, never read
    as nothing. A deleted file is as old as the last change to the nearest folder still there. Commits are read on
    the checkout's own branch: worktrees share one set of branches, so reading every branch charged each claimed
    worktree with all of them (5.20.0). In a repository with no remote, what is pushed cannot be told, so its commits
    are not counted. Finder's files are not records. Repositories are read side by side; nothing is written."""
    from concurrent.futures import ThreadPoolExecutor
    from synthesis import board, checkout
    now, held = now or time.time(), {}
    for claim in claims:
        base = checkout._literal(board.normalize(claim))
        repo = checkout.repo_of(base)
        if repo:
            held.setdefault(repo, []).append((claim, base))
    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = dict(zip(sorted(held), pool.map(lambda r: _unsaved_repo(r, held[r], hours, now), sorted(held))))
    return {repo: found for repo, found in counts.items() if found is not None}


def unsaved_hours(config: dict) -> tuple:
    """The config's `unsaved_hours` (24 when absent) and a note when it cannot be read; hours None when it is false."""
    hours = config.get("unsaved_hours", 24)
    if hours is False:
        return None, ""
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours <= 0:
        return 24, f" ({json.dumps(hours)} in unsaved_hours is not a number of hours above 0, so 24 is used)"
    return hours, ""


def check_unsaved(config: dict, claims: list, now: float = 0) -> Check:
    """A warning, never a failure: the seat may mean to keep working."""
    hours, note = unsaved_hours(config)
    if hours is None:
        return Check("ok", "unsaved records", "off (unsaved_hours is false)")
    found = unsaved(claims, hours, now)
    if not found:
        return Check("warn" if note else "ok", "unsaved records", f"nothing under a claim unsaved past {hours:g} h{note}")
    return Check("warn", "unsaved records", f"{len(found)} {'repository holds' if len(found) == 1 else 'repositories hold'} "
                 f"claimed records unsaved past {hours:g} h, or could not be read{note}: " + "; ".join(
                     f"{_short(Path(repo))}: could not read it ({counts})" if isinstance(counts, str) else
                     f"{_short(Path(repo))}: {counts[0]} file(s), the oldest {counts[1]:.0f} h ({counts[2]} uncommitted, "
                     f"{counts[3]} in commits no remote holds)" for repo, counts in found.items())
                 + ". Commit and push them, or ask the seat that holds the claim (`synthesis who`)")


def check_fetch(stamp: Path, config: dict, now: float = 0) -> Check:
    """When the hourly job last fetched each knowledge root and sessions repo (plan item 13.5, part 3), and which it
    could not, each with its last fetch."""
    if config.get("scheduled_fetch", True) is False:
        return Check("ok", "scheduled fetch", "off (scheduled_fetch is false)")
    last, now = paths.read_json(stamp), now or time.time()
    repos = last.get("repos") if isinstance(last.get("repos"), dict) else {}

    def ago(iso) -> float | None:
        try:
            return (now - datetime.fromisoformat(str(iso)).timestamp()) / 3600
        except ValueError:
            return None
    ran = ago(last.get("at"))
    if ran is None:
        return Check("warn", "scheduled fetch", "no run of the hourly job has fetched yet (it fetches each knowledge root and "
                     "sessions repo, and never merges)")
    if not repos:
        return Check("ok", "scheduled fetch", "nothing to fetch: no knowledge root or sessions repo is a git checkout")
    failed = sorted((r, e) for r, e in repos.items() if e.get("failed"))
    detail = f"{len(repos) - len(failed)} of {len(repos)} repositories fetched by the hourly job, " + (
        f"{ran * 60:.0f} min ago" if ran < 1 else f"{ran:.0f} h ago")
    if failed:
        return Check("warn", "scheduled fetch", detail + "; not fetched: " + "; ".join(
            f"{_short(Path(r))} ({e['failed']}; " + (f"last fetched {ago(e['fetched']):.0f} h ago)" if ago(e.get("fetched")) is not None
                                                    else "never fetched)") for r, e in failed))
    if ran > 24:
        return Check("warn", "scheduled fetch", f"the hourly job last fetched {ran:.0f} h ago: read the sessions export line")
    return Check("ok", "scheduled fetch", detail)


def check_board(home: Path) -> Check:
    """The board moved to board/ in 5.1.18; whatever is left under state/ is read by no session."""
    old = [n for n in paths.BOARD_FILES if os.path.lexists(home / "state" / n)]
    if old:
        return Check("warn", "board", f"{', '.join(old)} still in {_short(home / 'state')}, where no session reads them; "
                     "the next hook or `synthesis install` merges them into board/ (install prints why it could not)")
    return Check("ok", "board", f"{_short(home / 'board')}")


def check_codex_doc_bytes(config: dict) -> Check:
    value = config.get("project_doc_max_bytes")
    if not isinstance(value, int) or isinstance(value, bool):
        return Check("fail", "codex instruction bytes", f"project_doc_max_bytes is unset (Codex default "
                                                       f"{CODEX_DEFAULT_DOC_BYTES:,}); set at least {CODEX_DOC_BYTES:,}")
    if value < CODEX_DOC_BYTES:
        return Check("fail", "codex instruction bytes", f"project_doc_max_bytes = {value:,}; set at least {CODEX_DOC_BYTES:,}")
    return Check("ok", "codex instruction bytes", f"project_doc_max_bytes = {value:,}")


def check_codex_trust(hooks_data: dict | None, config: dict, plugin_id: str, root: Path | None = None,
                      codex_home: Path | None = None) -> Check:
    """Codex runs a plugin hook only once its exact definition is trusted in /hooks, and (0.166) only while the
    plugin's files match the fingerprint stored with that approval, so every release needs the approval again. A hook
    declared in Codex's own hooks.json (`setup.py plugin --codex-user-hooks`) is trusted by its definition alone: for
    an event declared there, that hook is judged, and the plugin's own copy is switched off on purpose (one left on
    would run beside it). Codex keys a user-level hook by that file's path in its home's real path (the path as named
    with `allow_symlinked_codex_home`), then its event, group and place."""
    if not hooks_data:
        return Check("fail", "codex hook trust", "the installed plugin has no hooks/hooks.json")
    states = (config.get("hooks") or {}).get("state") or {}
    user, unread = codex_user_entries(codex_home) if codex_home is not None else ({}, "")
    problems, stale, total, content, baseline, others = [], [], 0, "", "", [unread] if unread else []
    if root is not None and set(hooks_data.get("hooks") or {}) - set(user):  # a hook that runs as the plugin's
        try:
            content = codex_plugin_hash(root)
        except (OSError, ValueError) as exc:  # a fault, not an approval: none the person gives would make it run
            others.append(f"Codex cannot fingerprint the plugin ({exc}), so it runs none of its hooks")
    if content and codex_home is not None:
        try:
            baseline = codex_trust_baseline(codex_home, plugin_id).read_text(encoding="utf-8").strip()
        except OSError:
            baseline = ""  # none yet: Codex pins the files it finds on the next run
    for event, groups in (hooks_data.get("hooks") or {}).items():
        for gi, group in enumerate(groups or []):
            for hi, handler in enumerate(group.get("hooks") or []):
                if handler.get("type", "command") != "command":
                    continue
                total += 1
                where = f"{_snake(event)}:{gi}:{hi}"  # Codex keys trust by event, group and handler position
                state = states.get(f"{plugin_id}:hooks/hooks.json:{where}") or {}
                if event in user:
                    if state.get("enabled") is not False:
                        others.append(f"{where} is not switched off, so it runs beside the user-level {event} once approved")
                elif state.get("enabled") is False:
                    problems.append(f"{where} disabled")
                elif not state.get("trusted_hash"):
                    problems.append(f"{where} untrusted")
                elif state["trusted_hash"] != codex_hook_hash(event, group.get("matcher"), handler):
                    problems.append(f"{where} modified")
                elif content and (state.get("trusted_content_hash") or baseline) not in ("", content):
                    stale.append(where)
    if stale:
        problems.append(f"{', '.join(stale)} approved before the plugin last changed (Codex ties an approval to the "
                        "plugin's files), so Codex runs none of them")
    file, wanted = Path(codex_home or "") / "hooks.json", codex_user_declaration(hooks_data)
    keys = [str(Path(os.path.realpath(codex_home)) / "hooks.json"), str(Path(os.path.abspath(codex_home)) / "hooks.json")] if user else []
    for event, found in user.items():
        if not wanted.get(event) or any(_declared(g) not in [_declared(x) for _, x, _ in found] for g in wanted[event]):
            others.append(f"{_short(file)}:{found[0][0]} differs from the plugin's {event}: run setup.py plugin "
                          "--codex-user-hooks again (a hook you declared yourself stays as you wrote it)")
            continue
        for where, group, hook in found:
            state, name = next((states[f"{k}:{where}"] for k in keys if f"{k}:{where}" in states), {}), f"{_short(file)}:{where}"
            if state.get("enabled") is False:
                problems.append(f"{name} disabled")
            elif not state.get("trusted_hash"):
                problems.append(f"{name} untrusted")
            elif state["trusted_hash"] != codex_hook_hash(event, group.get("matcher"), hook):
                problems.append(f"{name} modified")
    if problems or others:
        return Check("fail", "codex hook trust", "; ".join(others + (["needs /hooks approval: " + ", ".join(problems)] if problems else [])))
    declared = sum(len(found) for found in user.values())
    return Check("ok", "codex hook trust", f"all {total} synthesis hooks trusted" + (
        f", {declared} of them declared in {_short(file)} with the plugin's own copies switched off" if declared else ""))


# ---- Muse ---------------------------------------------------------------------

def check_muse_approval(inspect: dict) -> Check:
    hooks = [c for c in inspect.get("runtime_capabilities") or []
             if (c.get("candidate") or {}).get("kind") == "hook"]
    if not hooks:
        declared = ((inspect.get("plugin") or {}).get("capabilities") or {}).get("hooks") or []
        if declared:  # the manifest has hooks but Muse reported no trust state: unreadable here, not unapproved
            return Check("warn", "muse hook approval", f"cannot tell whether Muse approved the {len(declared)} hooks: it "
                         "reported no trust state, which happens when its state cannot be read from here (in a sandbox, for example)")
        return Check("fail", "muse hook approval", "the installed plugin registers no hooks")
    pending = [f"{c['candidate'].get('capability_id', '?')} ({c.get('status', 'unknown')})"
               for c in hooks if c.get("status") != "trusted_enabled"]
    if pending:
        return Check("fail", "muse hook approval", f"run `muse plugins approve {PLUGIN}`: " + ", ".join(pending))
    return Check("ok", "muse hook approval", f"all {len(hooks)} hooks approved and enabled")


def muse_hook_commands(inspect: dict) -> list:
    """(event, text) per Muse hook: its argv plus the script it names, since Muse hooks run a file."""
    found = []
    for hook in ((inspect.get("plugin") or {}).get("capabilities") or {}).get("hooks") or []:
        text = " ".join(hook.get("command") or [])
        try:
            text += "\n" + Path(hook["source_path"]).read_text(encoding="utf-8")
        except (KeyError, TypeError, OSError):
            pass
        found.append((hook.get("event", ""), text))
    return found


# ---- finding each harness's CLI -------------------------------------------------
# The Codex CLI ships inside the ChatGPT desktop app and is on PATH only in Codex's own
# shells, and the Claude desktop app keeps its own Claude Code, one folder per version, off
# PATH (2026-10-30: a Mac with only the app had nothing to install into), so doctor also
# looks in each vendor's stable install locations. A set SYNTHESIS_<NAME>_BIN override is
# authoritative: empty means absent, and one pointing nowhere is absent rather than falling
# through to a different install.

CLIENT_ENV = {"claude": "SYNTHESIS_CLAUDE_BIN", "codex": "SYNTHESIS_CODEX_BIN", "muse": "SYNTHESIS_MUSE_BIN"}
KNOWN_LOCATIONS = {h: tuple(f"{d}/{h}" for d in ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin")) + (
    tuple(f"/Applications/{app}.app/Contents/Resources/{p}" for p in ("codex-cli/bin/codex", "codex")
          for app in ("ChatGPT", "Codex")) if h == "codex" else ()) + (
    ("~/Library/Application Support/Claude/claude-code/*/*/claude.app/Contents/MacOS/claude",) if h == "claude" else ())
    for h in HARNESSES}


def _expand(candidate: str) -> list:
    """A location as it is, or a pattern's matches with the newest version folder first."""
    if "*" not in candidate:
        return [candidate]
    def newest(path: str) -> tuple:
        return max((tuple(map(int, p.split("."))) for p in Path(path).parts if re.fullmatch(r"\d+(\.\d+)+", p)),
                   default=())
    return sorted(glob.glob(os.path.expanduser(candidate)), key=newest, reverse=True)


PROBE_TIMEOUT = 2.0


def _version_ok(path: str, timeout: float | None = None):
    """`<cli> --version` with stdin closed, time-bounded, its process group reaped: a stale
    launcher can outlive the app it launches. True when it answered, False when it failed, "slow" when
    it gave no answer in time, None when the probe could not be cleaned up."""
    try:
        proc = subprocess.Popen([path, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        ok = proc.wait(timeout=PROBE_TIMEOUT if timeout is None else timeout) == 0
    except OSError:
        return False
    except subprocess.TimeoutExpired:
        ok = "slow"
    try:
        os.killpg(proc.pid, 9)  # the group too: a launcher's children can outlive it
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=1)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return ok


def find_client(name: str, which=shutil.which, locations=None) -> str | None:
    if CLIENT_ENV[name] in os.environ:
        value = os.environ[CLIENT_ENV[name]]
        path = os.path.abspath(os.path.expanduser(value)) if value else ""
        return path if path and os.path.isfile(path) and os.access(path, os.X_OK) else None
    seen, slow = set(), None
    for candidate in [which(name)] + [p for c in (KNOWN_LOCATIONS[name] if locations is None else locations)
                                      for p in _expand(c)]:
        path = os.path.abspath(os.path.expanduser(candidate)) if candidate else ""
        if not path or os.path.realpath(path) in seen or not (os.path.isfile(path) and os.access(path, os.X_OK)):
            continue
        seen.add(os.path.realpath(path))
        ok = _version_ok(path) if name == "codex" else True
        if ok is None:
            return None  # a probe that would not die must not be hidden by a fallback
        if ok is True:
            return path
        slow = slow or (path if ok == "slow" else None)
    return slow  # no answer in time is not absence: where no other install answers, that command is the one


# ---- Codex skill catalog, through its read-only app-server -----------------------

def app_server_query(binary: str, method: str, params: dict, timeout: float = 15) -> dict:
    """One JSON-RPC request to `codex app-server --stdio`; never mutates Codex state."""
    import selectors
    proc = subprocess.Popen([binary, "app-server", "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
    selector, stderr, deadline = selectors.DefaultSelector(), [], time.monotonic() + timeout
    selector.register(proc.stdout, selectors.EVENT_READ)
    selector.register(proc.stderr, selectors.EVENT_READ)
    send = [{"method": "initialize", "id": 0, "params": {"clientInfo": {
        "name": "codex_vscode", "title": "Synthesis Doctor", "version": "1.0.0"}}},
        {"method": "initialized", "params": {}}, {"method": method, "id": 1, "params": params}]
    try:
        proc.stdin.write(json.dumps(send[0]) + "\n")
        proc.stdin.flush()
        while time.monotonic() < deadline and selector.get_map():
            for key, _ in selector.select(timeout=0.25):
                line = key.fileobj.readline()
                if not line:
                    selector.unregister(key.fileobj)
                    continue
                if key.fileobj is proc.stderr:
                    stderr.append(line.rstrip())
                    continue
                message = json.loads(line) if line.lstrip().startswith("{") else {}
                if "error" in message and message.get("id") in (0, 1):
                    raise RuntimeError(json.dumps(message["error"], sort_keys=True))
                if message.get("id") == 0:  # initialized: now the request itself
                    proc.stdin.write("".join(json.dumps(m) + "\n" for m in send[1:]))
                    proc.stdin.flush()
                elif message.get("id") == 1 and isinstance(message.get("result"), dict):
                    return message["result"]
        raise RuntimeError(f"{method} gave no answer: " + " | ".join(stderr[-3:]))
    finally:
        selector.close()
        _reap(proc)


def _reap(proc) -> None:
    """Kill the child's whole process group and wait: a harness CLI starts helpers of its own (Codex's
    app-server runs `git ls-remote` for its marketplace) that would otherwise outlive the doctor."""
    try:
        os.killpg(proc.pid, 9)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.__exit__(None, None, None)  # waits for it, and closes the pipes opened to it
    except OSError:
        pass  # words still unsent to a child that is gone


def _explicit_only(skill_md: Path) -> bool:
    try:
        text = (skill_md.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(r"^\s*allow_implicit_invocation\s*:\s*false\s*$", text, re.M | re.I))


def catalog_cost(skills: list, context_window: int | None) -> tuple:
    """(tokens, budget) for Codex's skill catalog: one line per implicitly invocable skill,
    descriptions cut at 1,024 characters, paths shortened to aliased roots, plus a 256-token
    alias reserve; the budget is 2% of the model's context window, else 8,000 characters."""
    visible = [s for s in skills if not _explicit_only(Path(str(s.get("path", ""))))]
    roots = sorted({str(Path(str(s.get("path", ""))).parent.parent) for s in visible})
    text = "".join(f"- `r{i}` = `{r}`\n" for i, r in enumerate(roots)) + "".join(
        f"- {s.get('name', '')}: {str(s.get('description', ''))[:1024]} (file: "
        f"r{roots.index(str(Path(str(s.get('path', ''))).parent.parent))}/{Path(str(s.get('path', ''))).parent.name}/SKILL.md)\n"
        for s in visible)
    budget = max(1, context_window * 2 // 100) if context_window else 8000 // 4
    return (len(text.encode("utf-8")) + 3) // 4 + 256, budget


def _model_cache(codex_home: Path) -> dict | None:
    """Codex's cache of its models, read by its first whole JSON value; {} where there is no file, None where the
    file holds no value to read. Codex's clients share the file, and a shorter copy written over a longer one
    leaves the longer one's tail after it (2026-11-13: read as no cache, the model's window was unknown and the
    catalog failed on the budget for a model Codex does not know, until Codex rewrote the file)."""
    try:
        text = (codex_home / "models_cache.json").read_text(encoding="utf-8")
        found = json.JSONDecoder().raw_decode(text.lstrip())[0]
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def _context_window(config: dict, codex_home: Path) -> int | None:
    models = (_model_cache(codex_home) or {}).get("models") or []
    return next((m["context_window"] for m in models if isinstance(m, dict) and m.get("slug") == config.get("model")
                 and isinstance(m.get("context_window"), int)), None)


def check_codex_catalog(result, error: str, plugin_root: Path | None, config: dict, codex_home: Path) -> Check:
    if result is None:
        return Check("warn", "codex skill catalog", f"could not ask Codex for its catalog ({error})")
    rows = [r for r in result.get("data") or [] if isinstance(r, dict)]
    skills = [s for r in rows for s in r.get("skills") or [] if isinstance(s, dict) and s.get("enabled", True)]
    names = {str(s.get("name", "")).split(":")[-1] for s in skills}
    shipped = {p.parent.name for p in plugin_root.glob("skills/*/SKILL.md")} if plugin_root else set()
    missing = sorted(shipped - names)
    cost, budget = catalog_cost(skills, _context_window(config, codex_home))
    errors = [str(e) for r in rows for e in r.get("errors") or []]
    if cost > budget and not (missing or errors) and _model_cache(codex_home) is None:
        return Check("warn", "codex skill catalog", f"cannot tell its budget: Codex's model cache ({_short(codex_home / 'models_cache.json')}) "
                     f"holds nothing that can be read, and {cost:,} tokens is over the {budget:,} Codex gives a model it does not know; "
                     "Codex writes the cache again when it next lists its models")
    if missing or errors or cost > budget:
        return Check("fail", "codex skill catalog", f"{cost:,} of {budget:,} tokens; "
                     + (f"not discoverable: {', '.join(missing[:5])}; " if missing else "") + "; ".join(errors[:2]))
    return Check("ok", "codex skill catalog", f"{len(skills)} skills, {cost:,} of {budget:,} catalog tokens")


def check_codex_instructions(cwd: Path, config: dict, codex_home: Path) -> Check:
    """Codex concatenates the user file, then one instruction file per folder from the repository
    root down to the working folder, and cuts at project_doc_max_bytes; keep a 4 KiB reserve."""
    limit = config.get("project_doc_max_bytes", CODEX_DEFAULT_DOC_BYTES)
    limit = limit if isinstance(limit, int) and not isinstance(limit, bool) else CODEX_DEFAULT_DOC_BYTES
    fallbacks = config.get("project_doc_fallback_filenames")
    names = ["AGENTS.override.md", "AGENTS.md"] + (fallbacks if isinstance(fallbacks, list) else [])
    chain = [p for p in (codex_home / "AGENTS.override.md", codex_home / "AGENTS.md") if p.is_file()][:1]
    top = next((p for p in [cwd, *cwd.parents] if (p / ".git").exists()), cwd)
    below = [p for p in reversed(cwd.parents) if top in p.parents]  # folders between the root and cwd
    for folder in [top] + below + ([cwd] if cwd != top else []):
        chain += [p for p in (folder / n for n in names) if p.is_file()][:1]
    total = sum(p.stat().st_size for p in chain)
    status = "ok" if total <= limit - 4096 else "fail"
    return Check(status, "codex instruction chain", f"{total:,} bytes in {len(chain)} file(s) for {_short(cwd)}; "
                 f"limit {limit:,} with a 4,096-byte reserve")


# ---- workspace repositories: instruction adapters and durable storage --------------

def workspace_repos(config: dict) -> list:
    """Each workspace folder and each git repository directly inside it."""
    found = []
    for pattern in config.get("workspace_roots") or ["~/workspaces/*"]:
        base = Path(os.path.expanduser(pattern))
        for folder in sorted(base.parent.glob(base.name)) if any(c in base.name for c in "*?[") else [base]:
            if folder.is_dir() and not folder.name.startswith("."):
                found.append(folder)
                found += [r for r in sorted(folder.iterdir()) if not r.name.startswith(".") and (r / ".git").exists()]
    return found


def adapter_state(root: Path) -> str:
    """'' when Claude Code and Codex read the same instructions here, else what differs."""
    agents, claude = root / "AGENTS.md", root / "CLAUDE.md"
    if not os.path.lexists(agents):
        return "CLAUDE.md without AGENTS.md (Codex reads nothing)" if os.path.lexists(claude) else ""
    if not agents.is_file():
        return "AGENTS.md is a dangling link"
    if claude.is_symlink() or agents.resolve() == claude.resolve():  # one file under both names, either one the link
        return "" if claude.resolve() == agents.resolve() else "CLAUDE.md links somewhere other than AGENTS.md"
    if not claude.is_file():
        return "no CLAUDE.md importing AGENTS.md"
    return "" if claude.read_text(encoding="utf-8", errors="replace").strip() == "@AGENTS.md" else \
        "CLAUDE.md is not `@AGENTS.md`"


def check_instruction_adapters(repos: list) -> Check:
    problems = [f"{_short(r)}: {s}" for r in repos for s in [adapter_state(r)] if s]
    if problems:
        return Check("warn", "instruction adapters", f"{len(problems)} folder(s) where Claude Code and Codex read "
                     "different instructions: " + "; ".join(problems[:4]) + (" ..." if len(problems) > 4 else ""))
    return Check("ok", "instruction adapters", f"{len(repos)} workspace folders checked")


def check_home_paths(files: list) -> Check:
    """Synced config must say ~ or $HOME for the current home: a literal one breaks on the next Mac. A path
    outside the current home (another user's, or a sandbox's beside it) cannot be written with ~."""
    home, hits = str(Path.home()), []
    for f in files:
        try:
            lines = Path(f).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        hits += [f"{_short(f)}:{n}" for n, line in enumerate(lines, 1)
                 if re.search(r"(^|[\s\"'=:(\[{,])" + re.escape(home) + r"(?=[/\"'\s,)\]}]|$)", line)]
    if hits:
        return Check("fail", "home paths", "literal home paths in synced config (write ~ instead): " + ", ".join(hits[:5]))
    return Check("ok", "home paths", "synced config uses ~ for home paths")


def temporary_roots() -> list:
    found = ["/tmp", "/var/tmp", "/private/var/folders"] + [os.environ.get(k, "") for k in ("TMPDIR", "TMP", "TEMP")]
    return list(dict.fromkeys(os.path.realpath(p) for p in found if os.path.isabs(p)))


def _under(path: str, roots: list) -> bool:
    return any((os.path.realpath(path) + "/").startswith(r.rstrip("/") + "/") for r in roots)


def check_temporary_work(repos: list, cwds: list, roots: list = None, venv_roots=None) -> Check:
    """Worktrees, sessions and virtual environments under a temporary folder die at the next cleanup."""
    roots, hits = roots or temporary_roots(), []
    for repo in repos:
        for marker in (repo / ".git" / "worktrees").glob("*/gitdir") if (repo / ".git").is_dir() else []:
            try:
                tree = os.path.dirname(marker.read_text(encoding="utf-8").strip())
            except OSError:
                continue
            if os.path.isdir(tree) and _under(tree, roots):
                hits.append(f"worktree {tree}")
    hits += [f"session in {c}" for c in cwds if c and _under(c, roots)]
    for root in venv_roots if venv_roots is not None else ("/tmp", "/var/tmp"):  # where agents make venvs by hand;
        hits += [f"venv {p.parent}" for p in Path(root).glob("*/pyvenv.cfg")]  # $TMPDIR holds ~30k entries: too slow
    if hits:
        return Check("warn", "durable storage", "work under a temporary folder will not survive a cleanup "
                     "or reboot; move it: " + "; ".join(sorted(set(hits))[:5]))
    return Check("ok", "durable storage", "no worktree, session or venv under a temporary folder")


# ---- versions across harnesses, and decision packets made by hand ------------------

def check_versions(versions: dict, sessions: list) -> Check:
    """Harnesses on different releases mean a release is half-installed, unless one is under way now."""
    if len(set(versions.values())) <= 1:
        return Check("ok", "versions", f"every harness on {next(iter(versions.values()), 'nothing')}")
    shown = ", ".join(f"{h} {v}" for h, v in sorted(versions.items()))
    train = [s for s in sessions if not s.stale and any(c.endswith("/CHANGELOG.md") for c in s.claims)]
    if train:
        return Check("info", "versions", f"{shown}: a release is in progress ({train[0].session}); nothing repaired")
    return Check("warn", "versions", f"{shown}: run the onboarding setup again, or release.py --install-only")


PACKET_MARKER = re.compile(r"<!-- synthesis-(?:decision-packet|action-sheet) spec-sha256:([0-9a-f]{64}) -->")
PACKET_SPEC = re.compile(r'<script type="application/json" id="spec">(.*?)</script>', re.S)


def packet_problem(page: Path) -> str:
    """A decision packet must be the generator's output: hand-made lookalikes skip its note boxes,
    impact blocks and persistence (a Muse session hand-made two on 2026-09-20)."""
    text = page.read_text(encoding="utf-8", errors="replace")
    marker, spec = PACKET_MARKER.search(text), PACKET_SPEC.search(text)
    if "synthesis-packet-retired" in text:
        return ""
    if not marker:
        return "no generator marker: rebuild it with its generator (build_packet.py or build_sheet.py)"
    if not spec or hashlib.sha256(spec.group(1).encode("utf-8")).hexdigest() != marker.group(1):
        return "edited after generation (its spec does not match the marker): rebuild it"
    return ""


def _marked(page: Path) -> bool:
    try:
        with page.open(encoding="utf-8", errors="replace") as text:
            return bool(PACKET_MARKER.search(text.read(4096)))  # the marker follows the title
    except OSError:
        return False


def check_packets(roots: list) -> Check:
    # By name, to catch hand-made lookalikes; by marker, since sheets are named from their titles (2026-10-22).
    pages = sorted({p for r in roots for p in Path(r).glob("projects/*/resources/artifacts/*.html")
                    if re.search(r"packet|sheet", p.name) or _marked(p)})
    problems = [f"{_short(p)}: {m}" for p in pages for m in [packet_problem(p)] if m]
    if problems:
        return Check("warn", "decision packets", f"{len(problems)} of {len(pages)} not generator output: "
                     + "; ".join(problems[:3]))
    return Check("ok", "decision packets", f"{len(pages)} packet and sheet pages carry their generator's marker")


# ---- the outbox, and the mail connector that must read it --------------------------

def connector_files(platform: str = sys.platform) -> tuple:
    """(the unit install-autostart.sh writes for the workspace-mcp connector, the PID file its start.sh keeps)."""
    home, env = Path.home(), os.environ
    if platform == "darwin":
        return (home / "Library" / "LaunchAgents" / "com.synthesis.workspace-mcp.plist",
                home / "Library" / "Logs" / "workspace-mcp" / "server.pid")
    return (Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "systemd" / "user" / "workspace-mcp.service",
            Path(env.get("XDG_STATE_HOME") or home / ".local" / "state") / "workspace-mcp" / "server.pid")


def started_with(pid: str, procargs=None, proc: Path = Path("/proc")) -> dict:
    """The environment a running process was started with, each variable whole; {} when the system does not show it.
    Linux keeps it under /proc, macOS in the record `ps -E` reads (kern.procargs2), never for the system's own
    programs or past a sandbox. Each variable ends with a NUL in both: `ps -E` prints them after a space instead,
    so a value holding a space and a name with "=" was read as two variables."""
    try:
        if (proc / pid).is_dir():
            text = (proc / pid / "environ").read_text(encoding="utf-8", errors="replace")
            return dict(e.split("=", 1) for e in text.split("\0") if "=" in e)
        raw = (procargs or _procargs)(pid)
    except (OSError, ValueError):
        return {}
    count, strings = int.from_bytes(raw[:4], sys.byteorder), raw[4:].split(b"\0")[1:]  # the program's path, then padding
    while strings and not strings[0]:
        strings.pop(0)
    if len(strings) <= count:  # fewer strings than the arguments it counts: nothing here can be read as variables
        return {}
    env = strings[count:]
    env = env[:env.index(b"")] if b"" in env else env  # an empty string ends them; the system's own strings follow
    return dict(e.decode("utf-8", "replace").split("=", 1) for e in env if b"=" in e)


def _procargs(pid: str) -> bytes:
    """macOS's record of a process's arguments and environment, as `ps -E` reads it; b"" elsewhere."""
    if sys.platform != "darwin":
        return b""
    import ctypes
    libc, size = ctypes.CDLL(None, use_errno=True), ctypes.c_size_t(0)
    mib = (ctypes.c_int * 3)(1, 49, int(pid))  # CTL_KERN, KERN_PROCARGS2
    if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        raise OSError(ctypes.get_errno(), "the system does not show this process")
    buffer = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
        raise OSError(ctypes.get_errno(), "the system does not show this process")
    return buffer.raw[:size.value]


def check_teardown(listed: Path, now: float = 0) -> Check:
    """What a test set up and has not taken down (2026-11-12: an entry in a client's config that pointed at a dead
    address, and a key marked for removal, stayed a day after their test stopped, with no list to run). The
    guardrails' teardown.py appends a line as each thing is made and one as it is taken off; this reads them,
    whatever else the file holds, and runs nothing a line names."""
    lines = []
    if os.path.lexists(listed):
        try:
            with open(listed, encoding="utf-8-sig", errors="replace") as source:  # a byte that is no text is read as a mark
                lines = source.read().split("\n")
        except OSError as exc:
            return Check("warn", "teardown", f"{_short(listed)} cannot be read ({exc.strerror}), so what a test left in place is not known")
    items, closed, other = {}, set(), 0
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if isinstance(row, dict) and type(row.get("done")) is int:
            closed.add(row["done"])
        elif isinstance(row, dict) and type(row.get("id")) is int and isinstance(row.get("what"), str):
            items[row["id"]] = row
        else:
            other += bool(line.strip())
    left = []
    for number in set(items) - closed:
        try:
            left.append((datetime.fromisoformat(str(items[number].get("at"))).timestamp(), number))
        except ValueError:
            left.append((float("inf"), number))  # an item with no time it can be placed by: shown after those with one
    left.sort()

    def plain(text) -> str:  # what a terminal would obey is shown as a mark, and one long line does not fill the screen
        return "".join(ch if ch.isprintable() else "?" for ch in str(text))[:120]
    beside = f"{other} line{'s' if other != 1 else ''} that {'are' if other != 1 else 'is'} no item of the list" if other else ""
    if not left:
        return Check("warn", "teardown", f"{_short(listed)} holds {beside}: read it and edit it by hand") if other else Check(
            "ok", "teardown", "nothing a test set up is left in place")
    hours = ((now or time.time()) - left[0][0]) / 3600
    age = "" if hours == float("-inf") else ", the oldest for " + ("under an hour" if hours < 1 else f"{hours:.0f} hour{'s' if round(hours) != 1 else ''}"
                                                                    if hours < 48 else f"{hours / 24:.0f} days")
    return Check("warn", "teardown", f"{len(left)} thing{'s' if len(left) != 1 else ''} a test set up {'are' if len(left) != 1 else 'is'} "
                 f"still in place{age}: " + "; ".join(f"{number}: {plain(items[number]['what'])} ({plain(items[number].get('remove', 'how it is removed was not said'))})"
                                                      for _, number in left[:3])
                 + (f"; and {len(left) - 3} more" if len(left) > 3 else "") + (f"; and {beside} (edit the file by hand)" if other else "")
                 + ". Take each down, then `python3 <synthesis-agent-guardrails>/scripts/teardown.py done <number>`")


def check_browser_accounts(config: dict, seen: dict) -> Check | None:
    """Warns while a site that a workspace's browser profile names last showed another account than the workspace's
    (2026-11-12: a work profile signed in to a personal account on a site was called a limit on the work, and no
    later session knew of it). The guard writes what each session's reads showed; this holds the newest against the
    config as it now is. None where no site is named."""
    from synthesis import guards
    routing = config.get("browser_routing")
    spaces = routing.get("workspaces") if isinstance(routing, dict) and isinstance(routing.get("workspaces"), dict) else {}
    named = [(root, meta, site, mine) for root, meta in spaces.items() if isinstance(meta, dict) for site, _, mine in guards.named_sites(meta) or []]
    wrong = []
    for root, meta, site, mine in named:
        last = seen.get(f"{str(meta.get('device') or '').strip()} {site}")
        if isinstance(last, dict) and isinstance(last.get("seen"), str) and last["seen"].strip().lower() != mine:
            try:
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(last.get("at"))))
            except (TypeError, ValueError, OverflowError, OSError):
                when = "a day that was not written down"
            label = meta.get("label") or root  # the name the guard's hold gives a profile with no label
            wrong.append(f"{site} in the {label} browser profile showed {last['seen']} on {when}, where the workspace's account is {mine}")
    if wrong:
        return Check("warn", "browser accounts", "; ".join(wrong) + ". That is a misconfiguration to fix in the profile (sign in there "
                     "with the workspace's account); this line clears when a session next reads the site and it shows that account")
    return Check("ok", "browser accounts", f"{len(named)} named site{'s' if len(named) != 1 else ''}, and none last showed another "
                 "account than its workspace's") if named else None


def check_outbox(outbox: Path, unit: Path, pid_file: Path, started=started_with) -> Check:
    """Agents stage outgoing attachments in the outbox and the send guard passes a file there, so it must be there to
    write, and a mail connector its auto-start keeps running must have been started with it among ALLOWED_FILE_DIRS
    (its start.sh's export): one started before that refuses the staged file after the principal approved the send.
    A connector started by hand is judged too when it can be read; only an installed one is expected to be running."""
    where = _short(outbox)
    if os.path.lexists(outbox) and not outbox.is_dir():
        return Check("fail", "outbox", f"{where} is not a folder, so no agent can stage an attachment there: move it "
                     "away and make the folder (the mail connector's start.sh makes it at each start)")
    if not outbox.is_dir() and unit.is_file():
        return Check("fail", "outbox", f"{where} is missing though a mail connector's auto-start is installed: restart "
                     "the connector, whose start.sh makes the folder and starts the connector to read it")
    if not outbox.is_dir():
        return Check("info", "outbox", f"{where} is not made yet; the mail connector's start.sh makes it, and no "
                     "auto-start for one is installed here")
    if not os.access(outbox, os.W_OK | os.X_OK):
        return Check("fail", "outbox", f"{where} cannot be written, so no agent can stage an attachment there")
    try:
        pid = pid_file.read_text(encoding="utf-8").strip()
    except OSError:
        pid = ""
    env = started(pid) if pid.isdigit() else {}
    if "WORKSPACE_MCP_PORT" not in env and not unit.is_file():  # start.sh always sets it: nothing of its starting was read
        return Check("ok", "outbox", f"{where} is there to write; no mail connector auto-start is installed here")
    if "WORKSPACE_MCP_PORT" not in env:
        return Check("warn", "outbox", f"cannot tell whether the running mail connector reads {where}: what it was "
                     "started with could not be read (it is not running, or this process may not see it)")
    if env.get("WORKSPACE_MCP_DISABLE_LOCAL_FILES", "").strip().lower() == "true":  # the connector's own reading of it
        return Check("fail", "outbox", "the running mail connector was started with WORKSPACE_MCP_DISABLE_LOCAL_FILES=true, so "
                     f"it reads no local file and refuses one staged in {where} after the send is approved: start it without that")
    allowed = env.get("ALLOWED_FILE_DIRS", "")  # compared as the connector compares: links followed, letters as written
    roots = tuple(os.path.realpath(os.path.expanduser(a.strip())).rstrip(os.sep) + os.sep
                  for a in allowed.split(os.pathsep) if a.strip())
    if not (os.path.realpath(outbox) + os.sep).startswith(roots):  # a supervisor keeps the unit it loaded until it is unloaded
        again = (f"; if it still lacks it, its auto-start carries another synthesis home, so run uninstall-autostart.sh and "
                 f"then install-autostart.sh from a shell where SYNTHESIS_HOME is {_short(outbox.parent)}") if unit.is_file() else ""
        return Check("fail", "outbox", f"the running mail connector was started without {where} in ALLOWED_FILE_DIRS "
                     f"({allowed or 'not set'}), so it refuses a file staged there after the send is approved: restart it{again}")
    return Check("ok", "outbox", f"{where} is there to write, and the running mail connector was started to read it")


# ---- am I behind the latest release? (on demand: it is the only network call) ------

RELEASE_MANIFEST = "https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/{ref}/.codex-plugin/plugin.json"
SYSTEM_CA_FILES = ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt")


def fetch_text(url: str, timeout: float = 5) -> str:
    """HTTPS with full verification. python.org's macOS Python can lack a CA path, so only a
    certificate failure retries with the operating system's own bundle; other errors stand."""
    import ssl
    import urllib.request
    errors = []
    for cafile in [None] + [f for f in SYSTEM_CA_FILES if os.path.isfile(f)]:
        context = ssl.create_default_context(cafile=cafile) if cafile else None
        try:
            return urllib.request.urlopen(url, timeout=timeout, context=context).read().decode("utf-8")
        except OSError as exc:
            errors.append(exc)
            if "CERTIFICATE_VERIFY_FAILED" not in str(errors[0]):
                break
    raise errors[0]


def check_latest(installed: dict, ref: str = "stable", fetch=fetch_text) -> Check:
    """installed: harness -> version. Behind is a warning; ahead of the channel is never a downgrade."""
    try:
        latest = json.loads(fetch(RELEASE_MANIFEST.format(ref=ref))).get("version", "")
    except (OSError, ValueError) as exc:
        return Check("warn", "latest release", f"could not read the {ref} release: {exc}")
    behind = [f"{h} {v}" for h, v in sorted(installed.items()) if install.version_tuple(v) < install.version_tuple(latest)]
    if behind:
        return Check("warn", "latest release", f"{ref} is {latest}; behind: {', '.join(behind)} "
                     "(run the onboarding setup again, or release.py --install-only from a checkout)")
    return Check("ok", "latest release", f"{ref} is {latest}; installed: "
                 + (", ".join(f"{h} {v}" for h, v in sorted(installed.items())) or "nothing"))


# ---- git ----------------------------------------------------------------------

def check_git_hooks_path(value: str, expected: Path) -> Check:
    """Report only: v5 commit checks run when core.hooksPath points at the v5 hooks folder."""
    if value and os.path.realpath(os.path.expanduser(value)) == os.path.realpath(expected):
        return Check("ok", "git hooks", f"core.hooksPath -> {_short(expected)}")
    if not value:
        return Check("info", "git hooks", f"core.hooksPath is not set; v5 commit checks expect {_short(expected)}")
    return Check("info", "git hooks", f"core.hooksPath is {value}, not the v5 folder {_short(expected)}")


def check_pr_gate(gated, repos: list, run=subprocess.run) -> Check:
    """Commits on a gated repository's default branch that came through no pull request: a push made where the
    guard cannot see it (another Mac, a script, a harness without the hook). Merge commits and GitHub's squash
    subjects ("... (#12)") came through one; `direct_ok` lists the commits the principal let through."""
    if not isinstance(gated, dict) or not all(isinstance(rule, dict) and rule.get("since") for rule in gated.values()):
        return Check("fail", "pr gate", 'pr_gated needs {"owner/repo": {"since": "YYYY-MM-DD"}} for every repository, '
                     "and one has no since date")

    def git(repo: Path, *args: str):
        """The command's output, or None when it failed: history that cannot be read is never an empty history."""
        try:
            done = run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout if done.returncode == 0 else None

    problems, missing = [], []
    for name, rule in gated.items():
        remote = re.compile(rf"[/:]{re.escape(name)}(?:\.git)?\s*$", re.I | re.M)
        home = next((r for r in repos if (r / ".git" / "config").is_file()
                     and remote.search((r / ".git" / "config").read_text(encoding="utf-8", errors="replace"))), None)
        if home is None:
            missing.append(f"no checkout of {name} under the workspace folders")
            continue
        ref = f"origin/{rule['branch']}" if rule.get("branch") else (git(home, "symbolic-ref", "--short", "refs/remotes/origin/HEAD") or "").strip()
        if not ref:  # the guard then holds every branch push from this checkout
            missing.append(f"the checkout of {name} records no default branch, so every branch push from it is held (run "
                           "`git remote set-head origin --auto` there, or name it as \"branch\" under pr_gated)")
            continue
        log = git(home, "log", "--first-parent", "--no-merges", f"--since={rule['since']}T00:00:00", "--format=%h%x09%s", ref)
        if log is None:
            missing.append(f"cannot read {ref} in the checkout of {name}")
            continue
        direct = [commit for commit, _, subject in (line.partition("\t") for line in log.splitlines())
                  if not re.search(r"\(#\d+\)$", subject.strip())
                  and not any(str(ok).startswith(commit) or commit.startswith(str(ok)) for ok in rule.get("direct_ok") or [])]
        if direct:
            problems.append(f"{name}: {len(direct)} commit{'s' * (len(direct) != 1)} on {ref.split('/', 1)[-1]} since "
                            f"{rule['since']} reached it without a pull request ({', '.join(direct[:5])})")
    if problems:
        return Check("fail", "pr gate", "; ".join(problems) + ". Revert each, or list it under that repository's "
                     "direct_ok with the principal's yes")
    if missing:
        return Check("warn", "pr gate", "; ".join(missing) + ": its default branch was not checked here")
    return Check("ok", "pr gate", f"{len(gated)} gated repositor{'y' if len(gated) == 1 else 'ies'}: every commit on a "
                 "default branch since its gate began came through a pull request")


# ---- reading harness state ----------------------------------------------------

def read_toml(text: str, strict: bool = False) -> dict:
    """The TOML subset Codex's config needs: tables, dotted and quoted keys, strings, integers and
    booleans. Arrays, inline tables, floats and dates are kept as raw text. Standard library only,
    because Apple's Python 3.9 has no tomllib. `strict` raises ValueError naming the first line it cannot place (a
    table header left open or followed by more, a line with no key, a key with no value, a table defined twice, a
    value never closed): Codex refuses such a file whole, and setup writes nothing into it."""
    root: dict = {}
    table, pending, buffer, seen = root, None, "", set()
    for number, line in enumerate(text.splitlines(), 1):
        if pending is not None:  # inside a multi-line array or string, kept as raw text
            buffer += "\n" + line
            if _closed(buffer):
                _assign(table, pending, buffer)
                pending = None
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            double = stripped.startswith("[[")
            body = stripped[2 if double else 1:]
            end = _find(body, "]")
            parts, tail = _key_parts(body[:end] if end >= 0 else body), body[end + 1:].lstrip("]" if double else "").strip()
            if strict and (end < 0 or tail[:1] not in ("", "#") or not double and tuple(parts) in seen):
                raise ValueError(f"line {number} is a table header Codex cannot read")
            seen.add(tuple(parts))
            table = root
            for part in parts:
                table = table.setdefault(part, {})
                if not isinstance(table, dict):
                    table = {}
            if double:
                table = {}  # array-of-tables entries are not needed; keep them out of the result
            continue
        eq = _find(stripped, "=")
        if strict and (eq <= 0 or stripped[eq + 1:].strip()[:1] in ("", "#")):
            raise ValueError(f"line {number} holds no key with a value")
        if eq > 0:
            key, raw = _key_parts(stripped[:eq]), stripped[eq + 1:].strip()
            if _closed(raw):
                _assign(table, key, raw)
            else:
                pending, buffer = key, raw
    if strict and pending is not None:
        raise ValueError("a value is never closed")
    return root


def _find(text: str, char: str) -> int:
    """Index of `char` outside quoted strings and comments, or -1."""
    quote, escape = None, False
    for i, c in enumerate(text):
        if quote:
            if escape:
                escape = False
            elif c == "\\" and quote == '"':
                escape = True
            elif c == quote:
                quote = None
        elif c == "#":
            return -1
        elif c in "\"'":
            quote = c
        elif c == char:
            return i
    return -1


def _closed(raw: str) -> bool:
    """Whether a value is complete on the lines read so far (multi-line arrays and strings span lines)."""
    for triple in ('"""', "'''"):
        if raw.startswith(triple):
            return raw.count(triple) >= 2
    depth, quote, escape, comment = 0, None, False, False
    for c in raw:
        if comment:
            comment = c != "\n"
        elif quote:
            if escape:
                escape = False
            elif c == "\\" and quote == '"':
                escape = True
            elif c == quote:
                quote = None
        elif c == "#":
            comment = True
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
    return depth <= 0


def _string_end(raw: str) -> int:
    """Index of the quote that closes the string `raw` starts with, or -1."""
    i = 1
    while i < len(raw):
        if raw[0] == '"' and raw[i] == "\\":
            i += 2
            continue
        if raw[i] == raw[0]:
            return i
        i += 1
    return -1


def _string(token: str) -> str:
    if token.startswith("'"):
        return token[1:-1]
    try:
        return json.loads(token)  # TOML basic-string escapes are JSON's, plus two rare ones
    except ValueError:
        return token[1:-1]


def _key_parts(text: str) -> list:
    parts, i = [], 0
    while i < len(text):
        if text[i] in " \t.":
            i += 1
        elif text[i] in "\"'":
            end = _string_end(text[i:])
            end = len(text) - i - 1 if end < 0 else end
            parts.append(_string(text[i:i + end + 1]))
            i += end + 1
        else:
            j = i
            while j < len(text) and text[j] not in " \t.":
                j += 1
            parts.append(text[i:j])
            i = j
    return parts


def _value(raw: str):
    if raw[:3] in ('"""', "'''"):  # multi-line string: its text, minus the newline after the opener
        body = raw[3:raw.rfind(raw[:3])] if raw.count(raw[:3]) >= 2 else raw[3:]
        return body[1:] if body.startswith("\n") else body
    if raw[:1] in "\"'":
        end = _string_end(raw)
        return _string(raw[:end + 1]) if end > 0 else raw
    token = raw.split("#")[0].strip()  # outside a string, '#' starts a comment
    if token in ("true", "false"):
        return token == "true"
    plain = token.replace("_", "")
    if plain.lstrip("+-").isdigit():
        return int(plain)
    return raw


def _assign(table: dict, key: list, raw: str) -> None:
    for part in key[:-1]:
        table = table.setdefault(part, {})
        if not isinstance(table, dict):
            return
    if key:
        table[key[-1]] = _value(raw)


def _start(argv: list):
    try:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
    except OSError as exc:
        return exc


def _finish(proc, timeout: float | None = None):
    """(parsed JSON or None, error). Time-bounded; the child is always reaped."""
    if isinstance(proc, Exception):
        return None, f"could not run: {proc}"
    timeout = CLI_TIMEOUT if timeout is None else timeout
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _reap(proc)
        proc.communicate()
        return None, f"cannot tell: `{' '.join(proc.args)}` did not answer within {timeout:.0f} s; run the doctor again"
    _reap(proc)  # helpers it started (git, MCP servers) end with it
    found = json_in(out)
    if found is None:
        return None, f"`{' '.join(proc.args)}` gave no JSON (exit {proc.returncode}): {(err or out).strip()[:120]}"
    return found, ""


def json_in(text: str):
    """The JSON a command printed, read past the words before it: from a brace or bracket that opens a line, else
    from the first one anywhere. None when it printed none."""
    opens = [m.start(1) for m in re.finditer(r"(?m)^[ \t]*([{\[])", text)] + [i for i in (text.find("{"), text.find("[")) if i >= 0]
    for start in opens:
        try:
            return json.JSONDecoder().raw_decode(text[start:])[0]
        except ValueError:
            continue
    return None


def claude_entry(listing) -> dict | None:
    for item in listing if isinstance(listing, list) else (listing or {}).get("plugins") or []:
        if isinstance(item, dict) and str(item.get("id", "")).split("@")[0] == PLUGIN:
            path = item.get("installPath")
            return {"enabled": bool(item.get("enabled")), "version": item.get("version", ""),
                    "path": Path(path) if path else None}
    return None


def codex_entry(listing, codex_home: Path) -> dict | None:
    for item in (listing if isinstance(listing, dict) else {}).get("installed") or []:
        if isinstance(item, dict) and (item.get("name") == PLUGIN or str(item.get("pluginId", "")).split("@")[0] == PLUGIN):
            version = str(item.get("version") or "")  # a listing with no version names no folder
            folder = codex_home / "plugins" / "cache" / str(item.get("marketplaceName") or "") / str(item.get("name") or PLUGIN) / version
            return {"enabled": bool(item.get("enabled")), "version": version,
                    "path": folder if version and folder.is_dir() else None, "id": item.get("pluginId", "")}
    return None


def muse_entry(inspect) -> dict | None:
    record = (inspect if isinstance(inspect, dict) else {}).get("record")
    if not record:
        return None
    path = record.get("cache_path")
    entry = {"enabled": bool(record.get("enabled")), "version": record.get("version", ""),
             "path": Path(path) if path else None}
    if inspect.get("valid") is False:
        codes = ", ".join(d.get("code", "?") for d in inspect.get("diagnostics") or [])
        entry["problem"] = f"Muse reports the installed manifest invalid ({codes})"
    return entry


def _hooks_file(root: Path | None) -> dict:
    """The parsed hooks/hooks.json of an installed Claude or Codex plugin; {} when there is none."""
    return paths.read_json(root / "hooks" / "hooks.json") if root else {}


def _commands(hooks) -> list:
    return [(event, handler.get("command", "")) for event, _, handler in hooks_json_entries(hooks or {})]


def harness_checks(found: list, procs: dict, home: Path, runtime: str, catalog=None, cwd: Path = None) -> tuple:
    """Checks per harness, plus {harness: installed version} for the release comparison."""
    checks, versions = [], {}
    if "claude" in found:
        listing, error = _finish(procs["claude"])
        entry = claude_entry(listing)
        checks.append(check_plugin("claude", entry, error))
        if entry:
            versions["claude"], hooks = entry.get("version", ""), _hooks_file(entry["path"])
            checks += [check_package("claude", entry["path"], runtime), check_hooks_wired("claude", _commands(hooks)),
                       check_claude_fail_closed(hooks, claude_version(procs["claude"].args[0])),
                       check_claude_retention(paths.transcript_roots()["claude-code"].parent / "settings.json")]
    if "codex" in found:
        codex_home = paths.codex_home()
        listing, error = _finish(procs["codex"])
        entry = codex_entry(listing, codex_home)
        if entry is None and not error.startswith(("cannot tell", "could not run")):
            # Not shown by its own marketplace, or a Codex that does not know the option: absent is said only from
            # the whole listing, the one that may fetch the catalog.
            listing, error = _finish(_start(procs["codex"].args[:1] + CODEX_WHOLE))
            entry = codex_entry(listing, codex_home)
            if entry is None and error.startswith("cannot tell"):
                error = error.replace("; run the doctor again", ": Codex's whole listing fetches its remote plugin catalog when its "
                                      "copy is old, and this limit stops the fetch each time; run `codex plugin list` once, then the doctor again")
        try:
            config = read_toml((codex_home / "config.toml").read_text(encoding="utf-8"))
        except OSError:
            config = {}
        checks += [check_plugin("codex", entry, error), check_codex_features(config), check_codex_doc_bytes(config),
                   check_codex_board(config, home / "board", home / "state", home / "outbox"),
                   check_codex_instructions(cwd or Path.cwd(), config, codex_home)]
        if entry:
            versions["codex"] = entry.get("version", "")
            hooks = _hooks_file(entry["path"])
            checks += [check_package("codex", entry["path"], runtime), check_hooks_wired("codex", _commands(hooks)),
                       check_codex_trust(hooks, config, entry.get("id") or PLUGIN, entry["path"], codex_home)]
            if catalog is not None:
                result, catalog_error = catalog()
                checks.append(check_codex_catalog(result, catalog_error, entry["path"], config, codex_home))
    if "muse" in found:
        inspect, error = _finish(procs["muse"])
        entry = muse_entry(inspect)
        if entry is None and isinstance(inspect, dict) and isinstance(inspect.get("error"), dict):
            absent = inspect["error"].get("code") == "unknown-plugin"  # Muse's own code for a plugin that is not there
            error = "" if absent else str(inspect["error"].get("message", "")) or error
        checks.append(check_plugin("muse", entry, error))
        if entry:
            versions["muse"] = entry.get("version", "")
            checks += [check_package("muse", entry["path"], runtime), check_muse_approval(inspect),
                       check_hooks_wired("muse", muse_hook_commands(inspect))]
        if runtime:
            checks.append(check_shell_name(home, "muse", "bash"))
    return checks, versions


def _background(fn, *args):
    """Run fn(*args) on a thread; the returned getter waits for (result, error)."""
    from concurrent.futures import ThreadPoolExecutor
    future = ThreadPoolExecutor(max_workers=1).submit(fn, *args)

    def get():
        try:
            return future.result(timeout=CLI_TIMEOUT), ""
        except Exception as exc:  # a catalog that cannot be read is reported, never fatal
            return None, str(exc) or type(exc).__name__
    return get


def run_checks(home: Path | None = None, find=find_client, latest_ref: str = "", cwd: Path = None) -> list:
    home, cwd, began = home or paths.home(), cwd or Path.cwd(), time.time()
    checks = [check_runtime(home), check_config(home), check_board(home)]
    from synthesis import sessions
    checks += check_sessions_repos(sessions.repos(), home / "sessions" / ".state")
    if sys.platform == "darwin":
        checks.append(check_sessions_export(Path.home() / "Library" / "LaunchAgents" / "com.synthesis.sessions-export.plist",
                                            home / "sessions" / ".state" / "export.json", command=home / "bin" / "synthesis"))
        try:
            fetching = paths.config()
        except (OSError, ValueError):
            fetching = {}
        checks.append(check_fetch(home / "sessions" / ".state" / "fetch.json", fetching))
    runtime = runtime_hash(home) if checks[0].status == "ok" else ""
    if (home / "bin" / "synthesis-hook").is_file():  # when it is missing, the runtime line already says so
        checks += [check_hook_script(home), check_self_test(home), check_wait_check()]  # before the CLIs start, so they don't skew timing
    clis, started = {}, {}
    for h in ("claude", "muse", "codex"):  # each listing starts as soon as its CLI is found; finding Codex
        path = find(h)                     # means a version probe, which overlaps the others' listings
        if path:
            clis[h], started[h] = path, _start([path] + LISTINGS[h])
    catalog = _background(app_server_query, clis["codex"], "skills/list",
                          {"cwds": [str(cwd)], "forceReload": False}) if "codex" in clis else None
    if not clis:
        checks.append(Check("warn", "harnesses", "no claude, codex or muse found on PATH or in their install folders"))
    found, versions = harness_checks(list(clis), started, home, runtime, catalog, cwd)
    checks += found
    try:
        config = paths.config()
    except (OSError, ValueError):
        config = {}
    repos = workspace_repos(config)
    from synthesis import board, project
    sessions = board.sessions()
    checks.append(check_unsaved(config, live_claims(sessions)))
    checks += [check_versions(versions, sessions), check_instruction_adapters(repos),
               check_temporary_work(repos, [s.cwd for s in sessions if not s.stale]),
               check_home_paths([home / "config.json"]), check_packets(project.roots()),
               check_outbox(paths.outbox(), *connector_files()), check_teardown(home / "teardown.jsonl")]
    if config.get("pr_gated") is not None:
        checks.append(check_pr_gate(config["pr_gated"], repos))
    if "temporary_addresses" in config:  # null is a setting that cannot be read, and fails its line
        checks.append(check_temporary_addresses(config))
    checks += [c for c in [check_browser_accounts(config, paths.read_json(paths.state() / "browser-accounts.json"))] if c]
    try:
        from synthesis import rituals
        asked = check_prompt_check(rituals.config())
    except (OSError, ValueError) as exc:
        asked = check_prompt_check(None, str(exc)[:120])
    checks += [asked] if asked else []
    if latest_ref:
        checks.append(check_latest(versions, latest_ref))
    try:
        value = subprocess.run(["git", "config", "--global", "--get", "core.hooksPath"], capture_output=True,
                               text=True, timeout=5, stdin=subprocess.DEVNULL).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        value = ""
    checks.append(check_git_hooks_path(value, home / "git-hooks"))
    _note_waits(home, checks, began)
    return checks


def summary(checks: list, ms: float) -> str:
    counts = {s: sum(c.status == s for c in checks) for s in ("ok", "warn", "fail", "info")}
    state = "healthy" if not counts["fail"] else f"{counts['fail']} problem{'s' * (counts['fail'] != 1)}"
    return (f"synthesis doctor: {state} ({counts['ok']} ok, {counts['warn']} warn, {counts['fail']} fail, "
            f"{counts['info']} info) in {ms:.0f} ms")


APPROVALS = tuple(paths.HOOK_APPROVALS)  # the person gives these in the harness; no release can
ASKS = {"codex hook trust": "needs /hooks approval: ", "muse hook approval": "run `muse plugins approve "}


def waits_on_person(check: Check) -> bool:
    """A failing approval line that asks only for what the person gives in the harness. The same line can name a fault
    of setup (a plugin copy left on, a plugin with no hooks), which no approval fixes, so a release must not count it
    as waiting (5.21.0)."""
    return check.status == "fail" and check.detail.startswith(ASKS.get(check.name, "\0"))


def _note_waits(home: Path, checks: list, began: float) -> None:
    """Write down what this run saw of each harness's hooks, for a session's start and the evening job to show
    (`paths.waits`).
    - Its approval line says ok or fail: the hooks that were not running, the ones the line names (Muse writes them
      with dashes), all four where it names none or says none run, with the line itself. A hook that ran after this
      run began is the later sight of its own event: that one stays struck, and no other.
    - Its plugin line says the plugin is not installed there, in the doctor's own sentence (Codex's whole listing
      does not hold it; Muse answers with its code for an unknown plugin): no approval waits, and its entry is
      dropped. Any other fault of that line is a look that could not tell.
    - The run could not tell (a listing that did not answer, a trust state that cannot be read from here): what this
      release saw within the day stands. Otherwise the run writes that it could not tell, with the line that says
      why, dates it again on each run that still cannot, and keeps what hooks have struck since, the only sight
      there is.
    - The run did not find the harness: it says so once in place of another release's entry, and that entry keeps
      its date, so it says nothing after a day.
    2026-11-13, a review: another release's entry stayed for ever under a sentence that said the doctor checks it."""
    from synthesis import __version__
    hooks = [arg.replace("-", "_") for arg in EVENTS.values()]  # as Codex keys their trust
    for name, harness in paths.HOOK_APPROVALS.items():
        check = next((c for c in checks if c.name == name), None)
        plugin = next((c for c in checks if c.name == f"{harness} plugin"), None)

        def change(old, check=check, plugin=plugin, harness=harness):
            mine, line = old if old and old["version"] == __version__ else None, check or plugin
            if check is not None and check.status in ("ok", "fail"):
                named = [e for e in hooks if re.search(rf"\b{e}:\d|synthesis-{e.replace('_', '-')}\b", check.detail)]
                waiting = [] if check.status == "ok" else named if named and "none of its hooks" not in check.detail else hooks
                struck, now = mine["struck"] if mine else {}, time.time()  # the clock is read under the note's lock
                waiting = [e for e in waiting if not began < struck.get(e, 0) <= now]
                return {"at": began, "waiting": waiting, "struck": {}, "said": check.detail[:300] if waiting else "", "untold": False}
            if plugin is not None and plugin.status == "fail" and plugin.detail == f"{PLUGIN} is not installed":
                return "drop" if old else None
            if mine and not mine["untold"] or line is None and (mine or not old):
                return None
            why = line.detail if line is not None else f"it did not find {harness.capitalize()} on PATH or in its install folders"
            return {"at": began, "waiting": mine["waiting"] if mine else hooks, "struck": mine["struck"] if mine else {},
                    "said": why[:300], "untold": True}
        try:
            paths.note_wait(name, change, home)
        except OSError:
            pass  # a note that cannot be written must not cost the doctor its report


def report(checks: list, ms: float) -> str:
    """The summary line, then every check, failures first."""
    rows = sorted(checks, key=lambda c: ("fail", "warn", "info", "ok").index(c.status))
    return "\n".join([summary(checks, ms)] + [f"  {c.status:<5} {c.name:<24} {c.detail}" for c in rows])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="synthesis doctor", description="Check that every part of synthesis is "
                                     "installed, current and wired into each harness found on PATH.")
    parser.add_argument("--json", action="store_true", help="print the checks as JSON")
    parser.add_argument("--latest", nargs="?", const="stable", default="", metavar="REF",
                        help="also ask GitHub whether a newer release exists on REF (default stable); network")
    parser.add_argument("--waiting", action="store_true", help="print, from what the doctor wrote down within a day and the hooks that "
                        "have run since: how many harnesses' guards have not been seen to run and which; or `unchecked` and "
                        "which, where nothing looked since this release was installed; or `unknown`. Runs no check, writes nothing")
    parser.add_argument("--unsaved", action="store_true", help="print how many repositories hold records a claim left "
                        "uncommitted or unpushed past the config's unsaved_hours, or `unknown`. Runs no other check, writes nothing")
    args = parser.parse_args(list(argv or []))
    if args.unsaved:
        try:
            from synthesis import board
            hours, _ = unsaved_hours(paths.config())
            print(len(unsaved(live_claims(board.sessions()), hours)) if hours else 0)
        except Exception:  # the evening job reads anything else as nothing to say
            print("unknown")
        return 0
    if args.waiting:
        from synthesis import __version__
        seen = paths.waits()
        guards = [n for n, e in seen.items() if e["version"] == __version__ and "pre_tool_use" in e["waiting"]]
        stale = [n for n, e in seen.items() if e["version"] != __version__]
        print("unknown" if not seen else f"{len(guards)}\n{', '.join(guards)}" if guards else f"unchecked\n{', '.join(stale)}" if stale else "0")
        return 0
    start = time.perf_counter()
    checks = run_checks(latest_ref=args.latest)
    ms = (time.perf_counter() - start) * 1000
    healthy = not any(c.status == "fail" for c in checks)
    if args.json:
        print(json.dumps({"healthy": healthy, "ms": round(ms), "checks": [c._asdict() for c in checks]}, indent=1))
    else:
        print(report(checks, ms))
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

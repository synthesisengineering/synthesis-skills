"""`synthesis doctor`: is every part installed, current and wired? (R7.1, R7.5-R7.7, R3.8, R8.1)

One line per check, after a first line that says healthy or not with counts.
Harness state is read only through each CLI's read-only listing command and its
config files; doctor never writes either. Each check is a small function over
plain inputs, so tests feed fake ones.

    main(["--json"])   # argv without the program name; returns the exit code
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
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
LISTINGS = {  # each harness's own read-only listing command
    "claude": ["plugin", "list", "--json"],
    "codex": ["plugin", "list", "--json"],
    "muse": ["plugins", "inspect", PLUGIN, "--json"],
}
HOOK_BUDGET_MS = 50
CODEX_DOC_BYTES = 98_304
CODEX_DEFAULT_DOC_BYTES = 32_768
CLI_TIMEOUT = 20
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
        out = run([str(home / "bin" / "synthesis-hook"), "pre-tool-use"], input=json.dumps(payload),
                  capture_output=True, text=True, timeout=10, env={**os.environ, "SYNTHESIS_HOME": str(home)})
        stdout = out.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run: {exc}", (time.perf_counter() - start) * 1000
    ms = (time.perf_counter() - start) * 1000
    try:
        decision = json.loads(stdout)["hookSpecificOutput"]
    except (ValueError, KeyError, TypeError):
        return False, "", ms
    return decision.get("permissionDecision") == "deny", str(decision.get("permissionDecisionReason", "")), ms


def check_self_test(home: Path, runs: int = 3, run=subprocess.run) -> Check:
    """Send `rm -rf ~` to the stable hook (it only inspects); it must deny, within the budget."""
    results = [run_hook(home, SELF_TEST, run) for _ in range(runs)]
    ms = statistics.median(r[2] for r in results)
    denied, reason = results[-1][0], results[-1][1]
    if not denied or "recursive delete" not in reason:
        return Check("fail", "hook self-test", f"the stable hook let `rm -rf ~` through ({reason or 'no decision'})")
    if ms > HOOK_BUDGET_MS:
        return Check("warn", "hook self-test", f"denied `rm -rf ~` in {ms:.0f} ms, over the {HOOK_BUDGET_MS} ms budget")
    return Check("ok", "hook self-test", f"denied `rm -rf ~` in {ms:.0f} ms")


def check_shell_name(home: Path, harness: str, tool: str, run=subprocess.run) -> Check:
    """Does the guard treat this harness's own shell tool name as a shell?"""
    denied, _, _ = run_hook(home, {**SELF_TEST, "tool_name": tool}, run)
    if denied:
        return Check("ok", f"{harness} shell guard", f"guards the shell tool name `{tool}`")
    return Check("warn", f"{harness} shell guard", f"the guard lets `rm -rf ~` through as tool `{tool}`, "
                                                  f"the name {harness} uses for its shell")


# ---- harness plugin state -----------------------------------------------------

def check_plugin(harness: str, entry: dict | None, error: str = "") -> Check:
    """entry: {"enabled": bool, "version": str, "path": Path | None, "problem": str}."""
    if entry is None:
        return Check("fail", f"{harness} plugin", error or f"{PLUGIN} is not installed")
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
    found = []
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups or []:
            for handler in group.get("hooks") or []:
                found.append((event, group.get("matcher"), handler))
    return found


def check_hooks_wired(harness: str, commands: list) -> Check:
    """commands: (event, command text) pairs; each needed event must call the stable hook with its own event."""
    missing = []
    for event, arg in EVENTS.items():
        texts = [c.replace("${HOME}", "$HOME") for e, c in commands if e == event]
        if not any(STABLE_HOOK in t and arg in t for t in texts):
            missing.append(event)
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


def check_codex_doc_bytes(config: dict) -> Check:
    value = config.get("project_doc_max_bytes")
    if not isinstance(value, int) or isinstance(value, bool):
        return Check("fail", "codex instruction bytes", f"project_doc_max_bytes is unset (Codex default "
                                                       f"{CODEX_DEFAULT_DOC_BYTES:,}); set at least {CODEX_DOC_BYTES:,}")
    if value < CODEX_DOC_BYTES:
        return Check("fail", "codex instruction bytes", f"project_doc_max_bytes = {value:,}; set at least {CODEX_DOC_BYTES:,}")
    return Check("ok", "codex instruction bytes", f"project_doc_max_bytes = {value:,}")


def check_codex_trust(hooks_data: dict | None, config: dict, plugin_id: str) -> Check:
    """Codex runs a plugin hook only once its exact definition is trusted in /hooks."""
    if not hooks_data:
        return Check("fail", "codex hook trust", "the installed plugin has no hooks/hooks.json")
    states = (config.get("hooks") or {}).get("state") or {}
    problems, total = [], 0
    for event, groups in (hooks_data.get("hooks") or {}).items():
        for gi, group in enumerate(groups or []):
            for hi, handler in enumerate(group.get("hooks") or []):
                if handler.get("type", "command") != "command":
                    continue
                total += 1
                where = f"{_snake(event)}:{gi}:{hi}"  # Codex keys trust by event, group and handler position
                state = states.get(f"{plugin_id}:hooks/hooks.json:{where}") or {}
                if state.get("enabled") is False:
                    problems.append(f"{where} disabled")
                elif not state.get("trusted_hash"):
                    problems.append(f"{where} untrusted")
                elif state["trusted_hash"] != codex_hook_hash(event, group.get("matcher"), handler):
                    problems.append(f"{where} modified")
    if problems:
        return Check("fail", "codex hook trust", "needs /hooks approval: " + ", ".join(problems))
    return Check("ok", "codex hook trust", f"all {total} synthesis hooks trusted")


# ---- Muse ---------------------------------------------------------------------

def check_muse_approval(inspect: dict) -> Check:
    hooks = [c for c in inspect.get("runtime_capabilities") or []
             if (c.get("candidate") or {}).get("kind") == "hook"]
    if not hooks:
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


# ---- git ----------------------------------------------------------------------

def git_hooks_dir(home: Path) -> Path:
    return home / "git-hooks"


def check_git_hooks_path(value: str, expected: Path) -> Check:
    """Report only: v5 commit checks run when core.hooksPath points at the v5 hooks folder."""
    if value and os.path.realpath(os.path.expanduser(value)) == os.path.realpath(expected):
        return Check("ok", "git hooks", f"core.hooksPath -> {_short(expected)}")
    if not value:
        return Check("info", "git hooks", f"core.hooksPath is not set; v5 commit checks expect {_short(expected)}")
    return Check("info", "git hooks", f"core.hooksPath is {value}, not the v5 folder {_short(expected)}")


# ---- reading harness state ----------------------------------------------------

def read_toml(text: str) -> dict:
    """The TOML subset Codex's config needs: tables, dotted and quoted keys, strings, integers and
    booleans. Arrays, inline tables, floats and dates are kept as raw text. Standard library only,
    because Apple's Python 3.9 has no tomllib."""
    root: dict = {}
    table, pending, buffer = root, None, ""
    for line in text.splitlines():
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
            table = root
            for part in _key_parts(body[:end] if end >= 0 else body):
                table = table.setdefault(part, {})
                if not isinstance(table, dict):
                    table = {}
            if double:
                table = {}  # array-of-tables entries are not needed; keep them out of the result
            continue
        eq = _find(stripped, "=")
        if eq > 0:
            key, raw = _key_parts(stripped[:eq]), stripped[eq + 1:].strip()
            if _closed(raw):
                _assign(table, key, raw)
            else:
                pending, buffer = key, raw
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
                                stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        return exc


def _finish(proc, timeout: float = CLI_TIMEOUT):
    """(parsed JSON or None, error). Time-bounded; the child is always reaped."""
    if isinstance(proc, Exception):
        return None, f"could not run: {proc}"
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None, f"`{' '.join(proc.args)}` timed out after {timeout:.0f} s"
    starts = [i for i in (out.find("{"), out.find("[")) if i >= 0]
    try:
        return json.JSONDecoder().raw_decode(out[min(starts):])[0], ""
    except (ValueError, IndexError):
        return None, f"`{' '.join(proc.args)}` gave no JSON (exit {proc.returncode}): {(err or out).strip()[:120]}"


def claude_entry(listing) -> dict | None:
    for item in listing if isinstance(listing, list) else (listing or {}).get("plugins") or []:
        if str(item.get("id", "")).split("@")[0] == PLUGIN:
            path = item.get("installPath")
            return {"enabled": bool(item.get("enabled")), "version": item.get("version", ""),
                    "path": Path(path) if path else None}
    return None


def codex_entry(listing, codex_home: Path) -> dict | None:
    for item in (listing if isinstance(listing, dict) else {}).get("installed") or []:
        if item.get("name") == PLUGIN or str(item.get("pluginId", "")).split("@")[0] == PLUGIN:
            folder = codex_home / "plugins" / "cache" / item.get("marketplaceName", "") / item.get("name", PLUGIN) / item.get("version", "")
            return {"enabled": bool(item.get("enabled")), "version": item.get("version", ""),
                    "path": folder if folder.is_dir() else None, "id": item.get("pluginId", "")}
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


def _hooks_file(root: Path | None):
    """The parsed hooks/hooks.json of an installed Claude or Codex plugin, or None."""
    try:
        return json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8")) if root else None
    except (OSError, ValueError):
        return None


def _commands(hooks) -> list:
    return [(event, handler.get("command", "")) for event, _, handler in hooks_json_entries(hooks or {})]


def harness_checks(found: list, procs: dict, home: Path, runtime: str) -> list:
    checks = []
    if "claude" in found:
        listing, error = _finish(procs["claude"])
        entry = claude_entry(listing)
        checks.append(check_plugin("claude", entry, error))
        if entry:
            checks += [check_package("claude", entry["path"], runtime),
                       check_hooks_wired("claude", _commands(_hooks_file(entry["path"])))]
    if "codex" in found:
        codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        listing, error = _finish(procs["codex"])
        entry = codex_entry(listing, codex_home)
        try:
            config = read_toml((codex_home / "config.toml").read_text(encoding="utf-8"))
        except OSError:
            config = {}
        checks += [check_plugin("codex", entry, error), check_codex_features(config), check_codex_doc_bytes(config)]
        if entry:
            hooks = _hooks_file(entry["path"])
            checks += [check_package("codex", entry["path"], runtime), check_hooks_wired("codex", _commands(hooks)),
                       check_codex_trust(hooks, config, entry.get("id") or PLUGIN)]
    if "muse" in found:
        inspect, error = _finish(procs["muse"])
        entry = muse_entry(inspect)
        if entry is None and isinstance(inspect, dict) and isinstance(inspect.get("error"), dict):
            error = str(inspect["error"].get("message", "")) or error
        checks.append(check_plugin("muse", entry, error))
        if entry:
            checks += [check_package("muse", entry["path"], runtime), check_muse_approval(inspect),
                       check_hooks_wired("muse", muse_hook_commands(inspect))]
        if runtime:
            checks.append(check_shell_name(home, "muse", "bash"))
    return checks


def run_checks(home: Path | None = None, which=shutil.which) -> list:
    home = home or paths.home()
    checks = [check_runtime(home), check_config(home)]
    runtime = runtime_hash(home) if checks[0].status == "ok" else ""
    if (home / "bin" / "synthesis-hook").is_file():  # when it is missing, the runtime line already says so
        checks += [check_hook_script(home), check_self_test(home)]  # before the CLIs start, so they don't skew timing
    found = [h for h in HARNESSES if which(h)]
    started = {h: _start([which(h)] + LISTINGS[h]) for h in found}  # the listings run side by side
    if not found:
        checks.append(Check("warn", "harnesses", "no claude, codex or muse on PATH"))
    checks += harness_checks(found, started, home, runtime)
    try:
        value = subprocess.run(["git", "config", "--global", "--get", "core.hooksPath"], capture_output=True,
                               text=True, timeout=5, stdin=subprocess.DEVNULL).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        value = ""
    checks.append(check_git_hooks_path(value, git_hooks_dir(home)))
    return checks


def summary(checks: list, ms: float) -> str:
    counts = {s: sum(c.status == s for c in checks) for s in ("ok", "warn", "fail", "info")}
    state = "healthy" if not counts["fail"] else f"{counts['fail']} problem{'s' * (counts['fail'] != 1)}"
    return (f"synthesis doctor: {state} ({counts['ok']} ok, {counts['warn']} warn, {counts['fail']} fail, "
            f"{counts['info']} info) in {ms:.0f} ms")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="synthesis doctor", description="Check that every part of synthesis is "
                                     "installed, current and wired into each harness found on PATH.")
    parser.add_argument("--json", action="store_true", help="print the checks as JSON")
    args = parser.parse_args(list(argv or []))
    start = time.perf_counter()
    checks = run_checks()
    ms = (time.perf_counter() - start) * 1000
    healthy = not any(c.status == "fail" for c in checks)
    if args.json:
        print(json.dumps({"healthy": healthy, "ms": round(ms), "checks": [c._asdict() for c in checks]}, indent=1))
    else:
        print(summary(checks, ms))
        for c in sorted(checks, key=lambda c: ("fail", "warn", "info", "ok").index(c.status)):
            print(f"  {c.status:<5} {c.name:<24} {c.detail}")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

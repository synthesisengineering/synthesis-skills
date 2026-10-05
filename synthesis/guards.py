"""Pre-tool guards (R3). Each returns None to allow, or a reason to block.

Only sends, deploys and destructive commands are guarded. The send and deploy
guards fail closed when their config can't be read (R3.5).
"""

from __future__ import annotations

import fnmatch
import os
import re
import shlex
from pathlib import Path

from synthesis import approvals

DEFAULT_SEND_TOOLS = [
    "mcp__*slack*send_message*", "mcp__*slack*schedule_message*", "mcp__*gmail*send*",
    "mcp__*send_gmail_message*", "mcp__*draft_gmail_message*", "mcp__*create_draft*",
    "mcp__*send_email*", "mcp__*mail*send*", "mcp__*__reply", "mcp__*__forward",
    "mcp__*chat*send_message*", "mcp__*workspace*send_message*",
]
DEFAULT_DEPLOY_PATTERNS = [
    r"\bwrangler\s+(pages\s+)?deploy\b", r"\bvercel\b.*--prod\b", r"\bnetlify\s+deploy\b.*--prod\b",
    r"\bfirebase\s+deploy\b", r"\bnpm\s+publish\b", r"\btwine\s+upload\b", r"\bgh\s+release\s+create\b",
]
SEPARATORS = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")


def is_send_tool(tool: str, config: dict) -> bool:
    patterns = DEFAULT_SEND_TOOLS + list(config.get("send_tools", []))
    return any(fnmatch.fnmatchcase(tool, p) for p in patterns)


def check_send(tool: str, tool_input: dict, config: dict) -> str | None:
    text = " ".join(str(v) for v in tool_input.values() if isinstance(v, str))
    for rule in config.get("forbidden_phrases", []):
        if re.search(rule["pattern"], text, re.IGNORECASE):
            return f"message breaks the rule '{rule.get('name', rule['pattern'])}': {rule.get('why', 'see your voice rules')}"
    if approvals.consume("send", {"tool": tool, "input": tool_input}):
        return None
    return ("Sending needs the principal's approval of this exact message. Show the exact text and "
            "recipient, and after an explicit yes run: synthesis approve send --tool "
            f"{shlex.quote(tool)} --input-file <file holding this exact tool input as JSON>")


def _commands(command: str) -> list[list[str]]:
    found = []
    for part in SEPARATORS.split(command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        if not words:
            continue
        found.append(words)
        if os.path.basename(words[0]) in ("sh", "bash", "zsh") and len(words) > 2:
            flag = next((i for i, w in enumerate(words[1:], 1) if w.startswith("-") and "c" in w), None)
            if flag is not None and flag + 1 < len(words):
                found += _commands(words[flag + 1])  # the script a wrapper shell runs
    return found


def check_deploy(command: str, config: dict) -> str | None:
    patterns = DEFAULT_DEPLOY_PATTERNS + list(config.get("deploy_patterns", []))
    deploy = any(re.search(p, command) for p in patterns)
    if not deploy:
        deploy_repos = [os.path.realpath(os.path.expanduser(r)) for r in config.get("push_deploys", [])]
        for words in _commands(command):
            if words[:2] == ["git", "push"] or (words[:1] == ["git"] and "push" in words[1:4]):
                cwd = os.path.realpath(words[words.index("-C") + 1]) if "-C" in words else os.getcwd()
                if any(cwd == r or cwd.startswith(r + os.sep) for r in deploy_repos):
                    deploy = True
    if not deploy or approvals.consume("deploy", command):
        return None
    return ("This publishes to production. Ask the principal for explicit permission for this exact "
            f"command, and after a yes run: synthesis approve deploy --command {shlex.quote(command)}")


def _protected(config: dict) -> list[Path]:
    home = Path.home()
    roots = [Path("/"), home, home / "workspaces"] + [Path(os.path.expanduser(p)) for p in config.get("protected_roots", [])]
    workspaces = home / "workspaces"
    if workspaces.is_dir():
        roots += [p for p in workspaces.iterdir() if p.is_dir()]
    return [Path(os.path.realpath(r)) for r in roots]


def check_destructive(command: str, config: dict) -> str | None:
    protected = _protected(config)
    for words in _commands(command):
        if words[0] == "rm" and any(w.startswith("-") and "r" in w.lstrip("-").lower() for w in words[1:]):
            for target in (w for w in words[1:] if not w.startswith("-")):
                real = Path(os.path.realpath(os.path.expanduser(target)))
                if real in protected or (real / ".git").exists():
                    return f"refusing a recursive delete of {real}: it is a protected root or a repository"
        if words[:2] == ["git", "push"] and any(w in ("-f", "--force") for w in words):
            if any(w.split(":")[-1] in ("main", "master") for w in words[2:]):
                return "refusing a force push to a default branch"
    return None


SHELL_TOOLS = {"Bash", "exec_command", "exec", "shell", "local_shell", "run_shell_command"}


def shell_command(tool_input: dict) -> str:
    """The command text, whichever harness spelled it: a string or an argv list."""
    value = tool_input.get("command", tool_input.get("cmd", ""))
    return shlex.join(value) if isinstance(value, list) else str(value)


def check(tool: str, tool_input: dict, config: dict) -> str | None:
    if tool in SHELL_TOOLS:
        command = shell_command(tool_input)
        return check_destructive(command, config) or check_deploy(command, config)
    if is_send_tool(tool, config):
        return check_send(tool, tool_input, config)
    return None

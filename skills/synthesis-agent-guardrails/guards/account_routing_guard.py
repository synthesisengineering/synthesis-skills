#!/usr/bin/env python3
"""account_routing_guard — fail-closed PreToolUse gate on cross-account artifact creation.

THE INCIDENT (2026-09-11). A short calendar invitation to two client colleagues was
created through the personal-account calendar connector. It dispatched with a personal
address as organizer. Deleting the event does not unsend an invitation, and
suppressing the cancellation leaves a stale invite with no explanation. The cost is
reputational, it lands on the principal rather than the agent, and it cannot be
undone after the fact.

WHY A GATE AND NOT A RULE. The routing rule was written into the workspace instructions the same
day. That is necessary and demonstrably insufficient: three separate violations that week were of
rules already sitting on disk, unread at the moment of acting. The message guard exists for the
same reason on the send boundary. This is that boundary for calendar and mail artifacts, one
account layer up.

WHAT IT DOES. When the session's working directory is inside a client workspace, a tool call that
creates or mutates an outward-facing artifact through a connector NOT bound to that workspace's
account is blocked. Account-bound tools carry an explicit account parameter; personal connectors
do not. The absence of that parameter on a mutating call is the signal.

WHY THE BOUNDARY IS NARROW, AND THE TWO TIMES IT WAS DRAWN TOO WIDE. This gate is about GOOGLE
ACCOUNT IDENTITY. Every widening of it past that has been a false positive, twice within an hour
of being written:

  1. The first draft matched tool-name SUFFIXES, so `slack_send_message` matched `send_message`
     and every Slack send from a client workspace would have been blocked — the sanctioned
     agent-send lane included, which carries no Google account parameter and never will.
  2. The second draft matched terminal names exactly but kept a bare `send_message`, so
     one agent-messaging server's send_message — one agent session messaging another,
     nothing outward, no account at all — was blocked on its first live call.

A guard that blocks approved paths trains its own bypass, and that is a worse outcome than the
incident it was built for. So: names that are distinctively Google are gated unconditionally;
`send_message`, which three different servers use for three different things, is gated only when
its payload carries an addressee (the Gmail and Chat shapes). Slack's boundary is
synthesis-message-guard. Session-to-session messaging has no account boundary to cross.

DESIGN, inherited from synthesis-git-hooks v2 and synthesis-message-guard:
  1. FAIL CLOSED on its own errors. An unreadable config blocks; it does not wave through.
  2. ZERO DEPENDENCIES. Stdlib only.
  3. READ-ONLY CALLS ARE NEVER BLOCKED. Reading the personal calendar from a client workspace is
     legitimate and common (conflict checks). Only mutation is gated.
  4. SELF-DIAGNOSING. --doctor runs positive and negative controls.
  5. EMPTY AUTHORITY UNTIL CONFIGURED. With no workspaces configured the gate
     allows (it must not brick routine tool use) and --doctor reports
     UNHEALTHY with a setup pointer.

CONFIG. Workspaces live in ~/.synthesis/account-routing/workspaces.json
(ACCOUNT_ROUTING_CONFIG overrides the path), shaped
{"workspaces": {"<root>": {"account": "<email>", "label": "<name>",
"tool_hint": "<optional tool suggestion>"}}}.

Exit 0 allow, exit 2 block.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

CONFIG = pathlib.Path(
    os.environ.get(
        "ACCOUNT_ROUTING_CONFIG",
        str(pathlib.Path.home() / ".synthesis/account-routing/workspaces.json"),
    )
)

# Tools that create or mutate an outward-facing Google artifact, matched against the tool name's
# TERMINAL segment (everything after the last "__"), exactly. See the module docstring for why
# this is an exact match rather than a suffix match.
MUTATING_TOOLS = frozenset(
    {
        # Calendar
        "create_event",
        "update_event",
        "delete_event",
        "manage_event",
        "respond_to_event",
        "manage_focus_time",
        "manage_out_of_office",
        # Mail
        "send_gmail_message",
        "draft_gmail_message",
        "create_draft",
        "update_draft",
        "send_email",
        "forward",
        "reply",
        "trash_message",
        "trash_thread",
        # Drive / Docs sharing
        "share_file",
        "set_drive_file_permissions",
        "manage_drive_access",
    }
)

# Terminal names several unrelated servers share, gated only when the payload proves the call
# addresses a mailbox or a Chat space. `send_message` alone is Gmail on one connector, Google
# Chat on another, and agent-to-agent session messaging on a third; only the first two cross an
# account boundary.
CONDITIONAL_TOOLS = {
    "send_message": (
        "to",
        "recipient",
        "recipients",
        "cc",
        "bcc",
        "space_name",
        "space_id",
        "user_google_email",
    ),
}

# Parameters that prove the call is bound to a named account.
ACCOUNT_KEYS = ("user_google_email", "from_email", "account", "user_email", "sender")

# Empty authority: no principal is gated until workspaces are configured.
DEFAULT_CONFIG = {"workspaces": {}}


def load_config() -> dict:
    if not CONFIG.exists():
        return DEFAULT_CONFIG
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:  # fail closed
        raise RuntimeError(f"account-routing config unreadable: {exc}") from exc


def terminal_name(tool_name: str) -> str:
    """The tool's own name, with any MCP server prefix removed."""
    return tool_name.rsplit("__", 1)[-1] if "__" in tool_name else tool_name


def workspace_for(cwd: str, cfg: dict):
    """Longest-prefix match so a nested workspace wins over its parent."""
    best = None
    for root, meta in cfg.get("workspaces", {}).items():
        if cwd == root or cwd.startswith(root.rstrip("/") + "/"):
            if best is None or len(root) > len(best[0]):
                best = (root, meta)
    return best


def is_mutating(tool_name: str, tool_input: dict | None = None) -> bool:
    name = terminal_name(tool_name)
    if name in MUTATING_TOOLS:
        return True
    markers = CONDITIONAL_TOOLS.get(name)
    if markers is None:
        return False
    return any(key in (tool_input or {}) for key in markers)


def evaluate(tool_name: str, tool_input: dict, cwd: str, cfg: dict):
    """Return (allow: bool, message: str)."""
    if not is_mutating(tool_name, tool_input):
        return True, ""

    match = workspace_for(cwd, cfg)
    if match is None:
        return True, ""
    root, meta = match
    expected = meta.get("account")
    if not expected:
        raise RuntimeError(f"workspace {root} has no account configured")

    supplied = None
    for key in ACCOUNT_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            supplied = value.strip()
            break

    if supplied is None:
        hint = meta.get("tool_hint")
        hint_suffix = f" ({hint})" if hint else ""
        return False, (
            f"BLOCKED — {tool_name} creates an outward-facing artifact and carries no account "
            f"parameter.\n\n"
            f"The working directory is inside the {meta.get('label', root)} workspace, whose "
            f"account is {expected}.\n"
            f"A connector without an account parameter authenticates as the PERSONAL account, so "
            f"this artifact would go out under a personal address and its recipients would see "
            f"that.\n\n"
            f"Use the account-bound tool instead and pass {ACCOUNT_KEYS[0]}={expected}"
            f"{hint_suffix}.\n"
            f"Then VERIFY the organizer or sender on the created artifact before reporting done — "
            f"an invitation cannot be unsent."
        )

    if supplied.lower() != expected.lower():
        return False, (
            f"BLOCKED — {tool_name} would act as {supplied}, but the working directory is inside "
            f"the {meta.get('label', root)} workspace, whose account is {expected}.\n\n"
            f"If this is deliberate personal work, run it from outside the client workspace."
        )

    return True, ""


def gate() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(
            f"account-routing guard FAILED CLOSED: unreadable tool payload: {exc}",
            file=sys.stderr,
        )
        return 2
    try:
        cfg = load_config()
        tool_name = payload.get("tool_name", "") or ""
        tool_input = payload.get("tool_input", {}) or {}
        cwd = payload.get("cwd") or os.getcwd()
        allow, message = evaluate(tool_name, tool_input, cwd, cfg)
    except Exception as exc:
        print(f"account-routing guard FAILED CLOSED: {exc}", file=sys.stderr)
        return 2
    if allow:
        return 0
    print(message, file=sys.stderr)
    return 2


def doctor_controls(account: str) -> list:
    """The 9 positive/negative controls, parameterized by the workspace's
    configured account (the private original hardcoded its own)."""
    return [
        (
            "personal calendar connector, mutating, inside client workspace -> BLOCK",
            ("mcp__personal__create_event", {"summary": "x"}, "INSIDE"),
            False,
        ),
        (
            "account-bound tool with correct account -> ALLOW",
            (
                "mcp__example__manage_event",
                {"user_google_email": account, "action": "create"},
                "INSIDE",
            ),
            True,
        ),
        (
            "account-bound tool with the WRONG account -> BLOCK",
            (
                "mcp__example__manage_event",
                {"user_google_email": "personal@example.com", "action": "create"},
                "INSIDE",
            ),
            False,
        ),
        (
            "read-only call, no account -> ALLOW",
            ("mcp__personal__list_events", {}, "INSIDE"),
            True,
        ),
        (
            "personal connector, mutating, OUTSIDE any client workspace -> ALLOW",
            ("mcp__personal__create_event", {"summary": "x"}, "/elsewhere"),
            True,
        ),
        (
            "personal Gmail send inside client workspace -> BLOCK",
            ("mcp__personal__send_message", {"to": "friend@example.com"}, "INSIDE"),
            False,
        ),
        (
            "agent session-to-session message -> ALLOW (no account boundary to cross)",
            (
                "mcp__agent_messaging__send_message",
                {"session_id": "local_x", "message": "hi"},
                "INSIDE",
            ),
            True,
        ),
        (
            "Slack send inside client workspace -> ALLOW (message-guard's boundary, not this one)",
            ("mcp__slacksvc__slack_send_message", {"channel": "C1"}, "INSIDE"),
            True,
        ),
        (
            "Slack draft inside client workspace -> ALLOW",
            ("mcp__slacksvc__slack_send_message_draft", {"channel": "C1"}, "INSIDE"),
            True,
        ),
    ]


def doctor() -> int:
    cfg = load_config()
    roots = sorted(cfg.get("workspaces", {}), key=len, reverse=True)
    if not roots:
        print(
            "UNHEALTHY: no workspaces configured; the gate would never fire. "
            "Create ~/.synthesis/account-routing/workspaces.json "
            "(see synthesis-agent-guardrails SKILL.md)."
        )
        return 2
    inside = roots[0]
    expected_account = cfg["workspaces"][inside].get("account", "")
    controls = doctor_controls(expected_account)
    failures = 0
    for label, (tool, tin, cwd), expected in controls:
        try:
            allow, _ = evaluate(tool, tin, inside if cwd == "INSIDE" else cwd, cfg)
        except RuntimeError as exc:
            print(f"  FAIL  {label} ({exc})")
            failures += 1
            continue
        ok = allow == expected
        failures += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if failures:
        print(f"UNHEALTHY: {failures} control(s) failed.")
        return 2
    print(
        f"HEALTHY: account routing gate operational; "
        f"{len(cfg.get('workspaces', {}))} workspace(s) configured, "
        f"{len(controls)} controls passing."
    )
    return 0


if __name__ == "__main__":
    sys.exit(doctor() if "--doctor" in sys.argv else gate())

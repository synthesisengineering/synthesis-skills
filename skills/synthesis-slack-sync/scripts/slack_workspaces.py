#!/usr/bin/env python3
"""Slack workspace registry: which Slack workspaces this machine may read.

One human can have several Slack workspaces (personal, employer A,
employer B). The registry names them, says where each workspace's token
lives, and declares the visibility mode — without ever storing a token
value. A literal ``xoxb-``/``xoxp-`` value in the registry is rejected:
tokens live in env vars, files, or client-managed MCP servers, never in
a synced dotfile.

Token forms per workspace entry::

    token: PLACEHOLDER            # not yet provided; doctor says how to mint one
    token: env:SLACK_TOKEN_ACME   # read the env var at check time
    token: file:/abs/path/token   # first line of the file
    token: mcp:slack-acme         # client-managed MCP server; readiness is
                                  # proven by the first MCP call, not here

Visibility modes (see references/cross-workspace-visibility.md)::

    unified    default focus is the session workspace; reads in other
               configured workspaces are permitted when relevant
               (scheduling conflicts, priority calls).
    isolated   only the session workspace is visible. Cross-workspace
               reads are forbidden; a workspace absent from this
               machine's registry is unreachable here.

Commands::

    slack_workspaces.py init [--registry PATH]
    slack_workspaces.py list [--registry PATH] [--json]
    slack_workspaces.py doctor [--registry PATH] [--session-workspace NAME]
    slack_workspaces.py readable [--registry PATH] [--session-workspace NAME] [--json]

``doctor`` exits 0 when the session workspace is readable, 1 when it is
not (placeholder / missing / rejected token), and 2 on a malformed
registry, an unknown mode, or an unresolvable session workspace.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REGISTRY = Path.home() / ".synthesis" / "slack-workspaces.yaml"
ENV_REGISTRY = "SYNTHESIS_SLACK_REGISTRY"
ENV_SESSION_WORKSPACE = "SYNTHESIS_SESSION_WORKSPACE"

MODES = ("unified", "isolated")
PLACEHOLDER = "PLACEHOLDER"
LITERAL_PREFIXES = ("xoxb-", "xoxp-", "xoxa-", "xoxs-", "xoxe-", "xoxd-")

SEED_WORKSPACES = (
    ("personal", "PLACEHOLDER"),
    ("work", "PLACEHOLDER"),
)


@dataclass
class Entry:
    name: str
    domain: str
    token: str


@dataclass
class Registry:
    mode: str
    entries: list[Entry]


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # PyYAML: the same dependency the repository's tests use
    except ImportError:
        print("error: PyYAML is required: pip install pyyaml", file=sys.stderr)
        raise SystemExit(2)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"error: malformed registry {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(payload, dict):
        print(f"error: malformed registry {path}: top level must be a mapping",
              file=sys.stderr)
        raise SystemExit(2)
    return payload


def load_registry(path: Path) -> Registry:
    if not path.exists():
        print(f"error: no registry at {path}; run `slack_workspaces.py init`",
              file=sys.stderr)
        raise SystemExit(2)
    payload = _load_yaml(path)
    mode = payload.get("mode", "unified")
    if mode not in MODES:
        print(f"error: unknown mode {mode!r} in {path}; want one of {MODES}",
              file=sys.stderr)
        raise SystemExit(2)
    raw_entries = payload.get("workspaces", [])
    if not isinstance(raw_entries, list) or not raw_entries:
        print(f"error: malformed registry {path}: `workspaces` must be a "
              f"non-empty list", file=sys.stderr)
        raise SystemExit(2)
    entries = []
    for i, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            print(f"error: malformed registry {path}: entry {i} must be a mapping",
                  file=sys.stderr)
            raise SystemExit(2)
        for key in ("name", "domain", "token"):
            if key not in raw or raw[key] is None or str(raw[key]).strip() == "":
                print(f"error: malformed registry {path}: entry {i} needs "
                      f"`{key}`", file=sys.stderr)
                raise SystemExit(2)
        entries.append(Entry(name=str(raw["name"]), domain=str(raw["domain"]),
                             token=str(raw["token"]).strip()))
    names = [e.name for e in entries]
    if len(set(names)) != len(names):
        print(f"error: malformed registry {path}: duplicate workspace name",
              file=sys.stderr)
        raise SystemExit(2)
    return Registry(mode=mode, entries=entries)


def _is_placeholder(value: str) -> bool:
    return value == PLACEHOLDER or value.startswith(PLACEHOLDER + ":")


def _is_literal_token(value: str) -> bool:
    return value.startswith(LITERAL_PREFIXES)


def token_status(token_ref: str) -> tuple[str, str]:
    """Resolve a token ref to (status, detail). Never returns a secret."""
    if _is_placeholder(token_ref):
        return ("placeholder", "no token provided yet")
    if _is_literal_token(token_ref):
        return ("rejected", "literal tokens are forbidden in the registry; "
                "use env:, file:, or mcp:")
    if token_ref.startswith("env:"):
        var = token_ref[4:]
        if not var:
            return ("missing", "empty env: ref")
        value = os.environ.get(var, "")
        if not value:
            return ("missing", f"${var} is unset")
        if _is_placeholder(value) or _is_literal_token(value) is False and value == "":
            return ("placeholder", f"${var} holds a placeholder")
        if _is_placeholder(value):
            return ("placeholder", f"${var} holds a placeholder")
        return ("ready", f"${var} is set")
    if token_ref.startswith("file:"):
        candidate = Path(token_ref[5:]).expanduser()
        if not candidate.is_file():
            return ("missing", f"{candidate} does not exist")
        try:
            value = candidate.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, IndexError):
            return ("missing", f"{candidate} is unreadable or empty")
        if not value or _is_placeholder(value):
            return ("placeholder", f"{candidate} holds a placeholder")
        if _is_literal_token(value):
            return ("ready", f"{candidate} holds a token")
        return ("ready", f"{candidate} is set")
    if token_ref.startswith("mcp:"):
        server = token_ref[4:]
        if not server:
            return ("missing", "empty mcp: ref")
        return ("external", f"client-managed MCP server `{server}`; "
                "proven by the first MCP call")
    return ("missing", f"unknown token ref form {token_ref.split(':')[0] + ':'}")


def domain_note(domain: str) -> str | None:
    if _is_placeholder(domain):
        return "domain not provided yet"
    if not domain.endswith(".slack.com"):
        return f"{domain!r} is not a slack.com domain"
    return None


def detect_session_workspace(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    env = os.environ.get(ENV_SESSION_WORKSPACE, "").strip()
    if env:
        return env
    cwd = Path.cwd().resolve()
    parts = cwd.parts
    if "workspaces" in parts:
        idx = parts.index("workspaces")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def readable_set(registry: Registry, session_workspace: str) -> list[Entry]:
    focus = next((e for e in registry.entries if e.name == session_workspace), None)
    if focus is None:
        return []
    if registry.mode == "isolated":
        return [focus]
    ready = [e for e in registry.entries
             if token_status(e.token)[0] in ("ready", "external")]
    ordered = [focus] + [e for e in ready if e.name != focus.name]
    if token_status(focus.token)[0] not in ("ready", "external"):
        return [e for e in ordered if e.name != focus.name]
    return ordered


def cmd_init(registry_path: Path, force: bool) -> int:
    if registry_path.exists() and not force:
        print(f"refusing to overwrite {registry_path} (pass --force to reseed)",
              file=sys.stderr)
        return 1
    lines = [
        "# Slack workspace registry (synthesis-slack-sync).",
        "# One entry per Slack workspace this machine may read. Tokens are",
        "# NEVER stored here — `token` names where the token lives:",
        "#   PLACEHOLDER | env:VAR_NAME | file:/abs/path | mcp:server-name",
        "# Mint tokens with references/slack-token-guide.md, then re-run doctor.",
        "# mode: unified (cross-workspace reads allowed) | isolated (strict).",
        "version: 1",
        "mode: unified",
        "workspaces:",
    ]
    for name, domain in SEED_WORKSPACES:
        lines += [f"  - name: {name}", f"    domain: {domain}",
                  "    token: PLACEHOLDER"]
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"seeded {registry_path} with {len(SEED_WORKSPACES)} placeholder workspaces")
    return 0


def cmd_list(registry_path: Path, as_json: bool,
             session_workspace: str | None) -> int:
    registry = load_registry(registry_path)
    rows = []
    for entry in registry.entries:
        status, detail = token_status(entry.token)
        rows.append({"name": entry.name, "domain": entry.domain,
                     "status": status, "detail": detail,
                     "focus": entry.name == session_workspace})
    if as_json:
        print(json.dumps({"mode": registry.mode, "workspaces": rows}, indent=2))
        return 0
    print(f"mode: {registry.mode}  registry: {registry_path}")
    for row in rows:
        marker = " *" if row["focus"] else "  "
        print(f"{marker} {row['name']:12} {row['status']:11} {row['detail']}")
    return 0


def cmd_doctor(registry_path: Path, session_workspace: str | None) -> int:
    registry = load_registry(registry_path)
    if session_workspace is None:
        print("error: cannot determine the session workspace: pass "
              "--session-workspace, set SYNTHESIS_SESSION_WORKSPACE, or run "
              "from inside ~/workspaces/<name>", file=sys.stderr)
        return 2
    focus = next((e for e in registry.entries if e.name == session_workspace), None)
    if focus is None:
        known = ", ".join(e.name for e in registry.entries)
        print(f"error: session workspace {session_workspace!r} is not in the "
              f"registry (known: {known})", file=sys.stderr)
        return 2
    print(f"mode: {registry.mode}  session workspace: {session_workspace}")
    failed = False
    for entry in registry.entries:
        status, detail = token_status(entry.token)
        dnote = domain_note(entry.domain)
        line = f"  {entry.name:12} {status:11} {detail}"
        if dnote:
            line += f" [{dnote}]"
        if entry.name == session_workspace:
            line += "  <-- focus"
        print(line)
        if entry.name == session_workspace and status not in ("ready", "external"):
            failed = True
    if failed:
        status, _ = token_status(focus.token)
        print(f"focus workspace {session_workspace!r} is not readable "
              f"({status}); mint its token per "
              f"references/slack-token-guide.md and re-run doctor")
        return 1
    names = [e.name for e in readable_set(registry, session_workspace)]
    print(f"readable from here: {', '.join(names)}")
    return 0


def cmd_readable(registry_path: Path, session_workspace: str | None,
                 as_json: bool) -> int:
    registry = load_registry(registry_path)
    if session_workspace is None:
        print("error: cannot determine the session workspace", file=sys.stderr)
        return 2
    entries = readable_set(registry, session_workspace)
    if as_json:
        print(json.dumps({"mode": registry.mode,
                          "session_workspace": session_workspace,
                          "readable": [e.name for e in entries]}))
        return 0
    print(" ".join(e.name for e in entries))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=None,
                        help="registry path (default: $SYNTHESIS_SLACK_REGISTRY "
                             "or ~/.synthesis/slack-workspaces.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="seed a placeholder registry")
    p_init.add_argument("--force", action="store_true",
                        help="overwrite an existing registry")
    p_init.add_argument("--registry", default=None)
    p_list = sub.add_parser("list", help="list workspaces and token status")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--registry", default=None)
    p_doc = sub.add_parser("doctor", help="fail-closed readiness check")
    p_doc.add_argument("--session-workspace", default=None)
    p_doc.add_argument("--registry", default=None)
    p_read = sub.add_parser("readable", help="name the readable workspaces")
    p_read.add_argument("--session-workspace", default=None)
    p_read.add_argument("--registry", default=None)
    p_read.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    registry_path = Path(args.registry or os.environ.get(ENV_REGISTRY, "")
                          or DEFAULT_REGISTRY).expanduser()
    if args.command == "init":
        return cmd_init(registry_path, args.force)
    session_workspace = None
    if args.command in ("list", "doctor", "readable"):
        explicit = getattr(args, "session_workspace", None)
        session_workspace = detect_session_workspace(explicit)
    if args.command == "list":
        return cmd_list(registry_path, args.json, session_workspace)
    if args.command == "doctor":
        return cmd_doctor(registry_path, session_workspace)
    if args.command == "readable":
        return cmd_readable(registry_path, session_workspace, args.json)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

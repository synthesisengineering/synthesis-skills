#!/usr/bin/env python3
"""Which Slack workspaces this session may read, and each one's domain.

One person can have several Slack workspaces (personal, employer A, employer B), and
reading across them is a disclosure question. The map lives in the synthesis config
(`$SYNTHESIS_HOME/config.json`, default `~/.synthesis/v5/config.json`):

    "slack_workspaces": {"mode": "unified",
                         "workspaces": {"acme": {"domain": "acme.slack.com"}}}

Modes (references/cross-workspace-visibility.md): `unified` (the default) focuses on the
session workspace and may read the others when relevant; `isolated` reads the session
workspace only. A workspace absent from this machine's map is unreachable here.

    slack_workspaces.py [--session-workspace NAME] [--json]

Prints the mode, every workspace with its domain, and the readable set. Exit 0, or 2 when
the map is missing or malformed or the session workspace is unknown.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

MODES = ("unified", "isolated")


def load(config_file: Path | None = None) -> tuple[str, dict]:
    home = Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")
    config_file = config_file or home / "config.json"
    try:
        section = json.loads(config_file.read_text(encoding="utf-8")).get("slack_workspaces")
    except (OSError, ValueError, AttributeError) as exc:
        raise ValueError(f"cannot read {config_file}: {exc}") from exc
    if not isinstance(section, dict) or not isinstance(section.get("workspaces"), dict) or not section["workspaces"]:
        raise ValueError(f"{config_file} needs a slack_workspaces section with a non-empty workspaces map")
    mode = section.get("mode", "unified")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; want one of {MODES}")
    for name, entry in section["workspaces"].items():
        domain = entry.get("domain") if isinstance(entry, dict) else None
        if not isinstance(domain, str) or not domain.endswith(".slack.com"):
            raise ValueError(f"workspace {name!r} needs a domain ending in .slack.com")
    return mode, section["workspaces"]


def session_workspace(explicit: str | None = None) -> str | None:
    if explicit or os.environ.get("SYNTHESIS_SESSION_WORKSPACE", "").strip():
        return explicit or os.environ["SYNTHESIS_SESSION_WORKSPACE"].strip()
    parts = Path.cwd().resolve().parts  # inside ~/workspaces/<name>/...
    return parts[parts.index("workspaces") + 1] if "workspaces" in parts[:-1] else None


def readable(mode: str, workspaces: dict, focus: str) -> list[str]:
    """The session workspace first; the others only in unified mode."""
    return [focus] + ([] if mode == "isolated" else sorted(n for n in workspaces if n != focus))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--session-workspace", help="default: $SYNTHESIS_SESSION_WORKSPACE, else ~/workspaces/<name>")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        mode, workspaces = load()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    focus = session_workspace(args.session_workspace)
    if focus not in workspaces:
        print(f"error: session workspace {focus!r} is not in the map (known: {', '.join(sorted(workspaces))}); "
              "pass --session-workspace or run from inside ~/workspaces/<name>", file=sys.stderr)
        return 2
    names = readable(mode, workspaces, focus)
    if args.json:
        print(json.dumps({"mode": mode, "session_workspace": focus,
                          "readable": [{"name": n, "domain": workspaces[n]["domain"]} for n in names]}))
        return 0
    print(f"mode: {mode}  session workspace: {focus}")
    for name in sorted(workspaces):
        print(f"  {name:12} {workspaces[name]['domain']}{'  <-- focus' if name == focus else ''}")
    print(f"readable from here: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

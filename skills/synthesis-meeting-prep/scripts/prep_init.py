#!/usr/bin/env python3
"""prep_init.py — scaffold meeting-prep private configuration.

Creates the principal file and reader-profile templates the
synthesis-meeting-prep skill reads. Non-interactive and
refusing-to-overwrite: colleagues run it once, then answer the
interview prompts it prints.

Usage:
    prep_init.py init --name NAME --role ROLE --org ORG [--goals 'a;b'] [--dir DIR]
    prep_init.py add-reader --id ID --name NAME --relationship REL [--dir DIR]

Exit 0 on success. Exit 2 on bad input or when files exist without
--force. Never overwrites without --force.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ENGINE_VERSION = "1.0.0"

RELATIONSHIPS = ("peer", "boss", "report", "skip", "external", "other")

PRINCIPAL_TEMPLATE = {
    "name": "",
    "role": "",
    "org": "",
    "goals_professional": [],
    "goals_personal": [],
    "authority": {
        "can_commit": "",
        "can_decide": "",
        "can_spend": "",
    },
    "known_positions": [],
    "tells_under_pressure": [],
}

READER_TEMPLATE = """\
# {name}

- relationship: {relationship}
- technical_depth: (how technical — delete and write: deep / working / non-technical)
- cares_about: (their current pressures, one per line)
- told_before: (what they have already been told)
- landed_last_time: (what worked in the last meeting)
- avoid_live: (topics to keep out of the room)
"""

INTERVIEW = """\
Created meeting-prep configuration under {root}.

Next, answer these once (edit the files directly):

1. principal.json: your professional and personal goals, what you can
   commit/decide/spend in a room, your known positions, and your
   tells under pressure.
2. readers/<id>.md: one file per person you meet regularly —
   relationship, technical depth, what they care about.
3. Run `prep_init.py add-reader` for each regular, or copy the template.

The skill degrades gracefully until this is filled in: it asks the
three questions it cannot proceed without and drafts anyway.
"""


def init_principal(
    root: Path,
    name: str,
    role: str,
    org: str,
    goals: list[str],
    force: bool = False,
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    principal_path = root / "principal.json"
    if principal_path.exists() and not force:
        raise FileExistsError(f"{principal_path} exists (use --force to replace)")
    payload = dict(PRINCIPAL_TEMPLATE)
    payload["name"] = name
    payload["role"] = role
    payload["org"] = org
    payload["goals_professional"] = goals
    principal_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    readers = root / "readers"
    readers.mkdir(exist_ok=True)
    template = readers / "_template.md"
    if not template.exists() or force:
        template.write_text(
            READER_TEMPLATE.format(name="(name)", relationship="(peer|boss|report|skip|external|other)"),
            encoding="utf-8",
        )
    return {"principal": str(principal_path), "template": str(template)}


def add_reader(
    root: Path, reader_id: str, name: str, relationship: str, force: bool = False
) -> dict:
    if relationship not in RELATIONSHIPS:
        raise ValueError(
            f"relationship must be one of {', '.join(RELATIONSHIPS)}"
        )
    if not reader_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("reader id must be alphanumeric (dashes/underscores ok)")
    readers = root / "readers"
    readers.mkdir(parents=True, exist_ok=True)
    path = readers / f"{reader_id}.md"
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists (use --force to replace)")
    path.write_text(
        READER_TEMPLATE.format(name=name, relationship=relationship),
        encoding="utf-8",
    )
    return {"reader": str(path)}


def default_root() -> Path:
    return Path.home() / ".synthesis" / "meeting-prep"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold meeting-prep configuration.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="create principal.json and the reader template")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--role", required=True)
    p_init.add_argument("--org", required=True)
    p_init.add_argument("--goals", default="", help="semicolon-separated professional goals")
    p_init.add_argument("--dir", default=None, help="config dir (default ~/.synthesis/meeting-prep)")
    p_init.add_argument("--force", action="store_true")
    p_reader = sub.add_parser("add-reader", help="add a reader profile template")
    p_reader.add_argument("--id", required=True)
    p_reader.add_argument("--name", required=True)
    p_reader.add_argument("--relationship", required=True, choices=RELATIONSHIPS)
    p_reader.add_argument("--dir", default=None)
    p_reader.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.dir) if args.dir else default_root()
    try:
        if args.command == "init":
            goals = [g.strip() for g in args.goals.split(";") if g.strip()]
            result = init_principal(
                root, args.name, args.role, args.org, goals, force=args.force
            )
            print(json.dumps(result, indent=2))
            print(INTERVIEW.format(root=root))
        else:
            result = add_reader(
                root, args.id, args.name, args.relationship, force=args.force
            )
            print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        print(f"prep_init: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

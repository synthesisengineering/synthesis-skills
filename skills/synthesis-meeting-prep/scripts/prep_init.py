#!/usr/bin/env python3
"""Scaffold meeting-prep profiles inside the owning workspace's private repository.

Reader profiles are relationship data, so they belong to the workspace whose
deletion unit they share (IR-72: profiles once lived outside a client's private
repository). Every call names that repository and the workspace id explicitly;
there is no fallback to the home folder, the current directory or any other
workspace, and a missing or ambiguous owner refuses before anything is written.

Layout, inside the repository named by --context-repo:

    profiles/meeting-prep/.owner.json        {"schema": 1, "workspace": "<id>"}
    profiles/meeting-prep/principal.json
    profiles/meeting-prep/readers/<id>.md

Creation never overwrites (an existing file refuses; edit it through the
repository's normal record workflow). New files are mode 0600, new folders
0700. The tool never commits; the repository's own workflow does.

Usage:
  prep_init.py resolve    --context-repo /abs/private-repo --workspace example
  prep_init.py init       --context-repo ... --workspace ... --name N --role R --org O [--goals "a;b"]
  prep_init.py add-reader --context-repo ... --workspace ... --id rivera --name "Dana Rivera" --relationship peer

Prints JSON. Exit 0 on success, 2 on any refusal.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

PROFILE_PATH = Path("profiles/meeting-prep")
MAX_FILE_BYTES = 8 * 1024 * 1024
RELATIONSHIPS = ("peer", "boss", "report", "skip", "external", "other")
WORKSPACE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
READER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")

PRINCIPAL_TEMPLATE = {
    "name": "", "role": "", "org": "",
    "goals_professional": [], "goals_personal": [],
    "authority": {"can_commit": "", "can_decide": "", "can_spend": ""},
    "known_positions": [], "tells_under_pressure": [],
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


def _repo(context_repo) -> Path:
    """The exact Git checkout root, given as an absolute path: never home, never a guess."""
    if context_repo is None or not Path(context_repo).is_absolute():
        raise ValueError("an explicit absolute --context-repo is required")
    repo = Path(context_repo)
    if repo == Path(repo.anchor) or repo == Path.home() or not repo.is_dir() or repo.is_symlink():
        raise ValueError("owner must be a dedicated existing private context repository")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    top = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"], env=env,
                         capture_output=True, text=True, timeout=10, check=False)
    if top.returncode or Path(top.stdout.strip()) != repo:
        raise ValueError(f"context repository must be its exact Git checkout root (git says {top.stdout.strip() or 'none'})")
    return repo


def _real_dir(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _check_dirs(repo: Path, *parts: str) -> None:
    """Every existing folder from the repository down is a real folder, never a symlink."""
    current = repo
    for part in parts:
        current = current / part
        if os.path.lexists(current) and not _real_dir(current):
            raise ValueError(f"refusing a symlink or non-folder at {current}")


def owner_root(context_repo, workspace) -> Path:
    """Resolve the profile folder for this owner without creating it."""
    if not isinstance(workspace, str) or not WORKSPACE_RE.fullmatch(workspace):
        raise ValueError("an explicit stable workspace id is required (lowercase letters, digits, - and _)")
    repo = _repo(context_repo)
    _check_dirs(repo, *PROFILE_PATH.parts, "readers")
    root = repo / PROFILE_PATH
    marker = root / ".owner.json"
    if os.path.lexists(marker):
        info = marker.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("the owner marker must be a plain file")
        try:
            found = json.loads(marker.read_text(encoding="utf-8"))
        except ValueError:
            found = None
        if not isinstance(found, dict) or type(found.get("schema")) is not int \
                or found != {"schema": 1, "workspace": workspace}:
            raise ValueError("profile folder belongs to a different or ambiguous owner")
    elif root.exists() and any(root.iterdir()):
        raise ValueError("existing profiles have no owner marker; resolve their owner before adding to them")
    return root


def _bounded(*blobs: bytes) -> None:
    if any(len(b) > MAX_FILE_BYTES for b in blobs):
        raise ValueError("profile exceeds 8 MiB bound")


def _create(path: Path, data: bytes) -> None:
    """Write a new file, 0600, refusing anything already there (O_EXCL never follows a link)."""
    _bounded(data)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    if path.read_bytes() != data:
        raise ValueError(f"profile readback differs: {path}")


def _bind(context_repo, root: Path, workspace: str) -> None:
    for folder in (root.parent, root, root / "readers"):
        if not folder.exists():
            folder.mkdir(mode=0o700, exist_ok=True)  # a concurrent call may get there first
    marker = root / ".owner.json"
    if not marker.exists():
        try:
            _create(marker, (json.dumps({"schema": 1, "workspace": workspace}) + "\n").encode())
        except FileExistsError:
            pass  # a concurrent call bound it; owner_root re-checks below
    owner_root(context_repo, workspace)


def _refuse_existing(*paths: Path) -> None:
    for path in paths:
        if os.path.lexists(path):
            raise FileExistsError(f"profile exists; edit it through the repository's record workflow: {path}")


def init_principal(context_repo, name, role, org, goals, *, workspace):
    root = owner_root(context_repo, workspace)
    principal, template = root / "principal.json", root / "readers" / "_template.md"
    _refuse_existing(principal, template)
    payload = dict(PRINCIPAL_TEMPLATE, name=name, role=role, org=org, goals_professional=list(goals))
    data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()
    text = READER_TEMPLATE.format(name="(name)", relationship="(peer|boss|report|skip|external|other)").encode()
    _bounded(data, text)  # before anything is created
    _bind(context_repo, root, workspace)
    _create(principal, data)
    _create(template, text)
    return {"workspace": workspace, "principal": str(principal), "template": str(template)}


def add_reader(context_repo, reader_id, name, relationship, *, workspace):
    if relationship not in RELATIONSHIPS:
        raise ValueError("relationship must be one of " + ", ".join(RELATIONSHIPS))
    if not isinstance(reader_id, str) or not READER_RE.fullmatch(reader_id):
        raise ValueError("reader id must be alphanumeric (dashes/underscores ok)")
    root = owner_root(context_repo, workspace)
    path = root / "readers" / (reader_id + ".md")
    _refuse_existing(path)
    data = READER_TEMPLATE.format(name=name, relationship=relationship).encode()
    _bounded(data)
    _bind(context_repo, root, workspace)
    _create(path, data)
    return {"workspace": workspace, "reader": str(path)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold meeting-prep profiles in the owning workspace's private repository.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("resolve", "init", "add-reader"):
        p = sub.add_parser(command)
        p.add_argument("--context-repo", type=Path, required=True, help="the private repository's absolute checkout root")
        p.add_argument("--workspace", required=True, help="stable owning workspace id")
        if command == "init":
            p.add_argument("--name", required=True)
            p.add_argument("--role", required=True)
            p.add_argument("--org", required=True)
            p.add_argument("--goals", default="", help="semicolon-separated")
        elif command == "add-reader":
            p.add_argument("--id", required=True)
            p.add_argument("--name", required=True)
            p.add_argument("--relationship", choices=RELATIONSHIPS, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "resolve":
            result = {"workspace": args.workspace, "root": str(owner_root(args.context_repo, args.workspace))}
        elif args.command == "init":
            goals = [g.strip() for g in args.goals.split(";") if g.strip()]
            result = init_principal(args.context_repo, args.name, args.role, args.org, goals, workspace=args.workspace)
        else:
            result = add_reader(args.context_repo, args.id, args.name, args.relationship, workspace=args.workspace)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"prep_init: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

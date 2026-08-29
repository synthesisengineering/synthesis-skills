#!/usr/bin/env python3
"""Agent-to-agent handoff through the project itself, so the principal is not the courier.

The decision packet (synthesis-decision-packet) moves decisions between agent
and principal; this queue moves work between agents. Together they are the two
directions that remove the principal as the transport layer: nobody should
have to copy a prompt from one agent's chat into another's when both agents
already share the project repository and the coordination board.

  WRITER  finishing a round of work calls
              handoff.py write --to codex --file prompt.md [--round 27]
          which stores the prompt under resources/handoffs/, records it in the
          queue as `pending`, and prints the board message that announces it.

  READER  told that the other side has finished calls
              handoff.py read --as codex
          which returns the oldest pending handoff addressed to it, verifies
          the stored hash, marks it `claimed`, and prints the prompt. No
          copy-paste crosses the human.

The principal keeps supervision without being transport: `handoff.py list`
shows everything that was passed and in which direction, every prompt is a
durable file in the project, and nothing self-triggers — an agent acts on the
queue only when the principal (or a coordination-board message the principal
allows) says the other side is done. That is the difference between
unattended and uncontrolled.

Usage:
    handoff.py write --to AGENT --file PROMPT.md [--round N] [--summary TEXT]
                     [--project-root DIR]
    handoff.py read  --as AGENT [--project-root DIR]
    handoff.py list  [--project-root DIR]
    handoff.py done  --id HANDOFF_ID [--project-root DIR]

Agent labels are free-form lowercase slugs; `claude` and `codex` are the
documented convention for the two first-class clients. The reader's identity
comes from --as or SYNTHESIS_HANDOFF_SELF; with neither, read refuses rather
than guessing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

AGENT_LABEL = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def queue_paths(project_root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    handoffs = project_root / "resources" / "handoffs"
    return handoffs, handoffs / "queue.json"


def load(queue_file: pathlib.Path) -> list:
    if not queue_file.is_file():
        return []
    rows = json.loads(queue_file.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"FAIL: {queue_file} is not a JSON list")
    return rows


def save(handoffs: pathlib.Path, queue_file: pathlib.Path, rows: list) -> None:
    handoffs.mkdir(parents=True, exist_ok=True)
    # Atomic replace: two agents share this file; a torn write must be
    # impossible even when a race loses an update.
    fd, tmp_name = tempfile.mkstemp(dir=str(handoffs), prefix=".queue-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_name, queue_file)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def resolve_root(raw: str) -> pathlib.Path:
    root = pathlib.Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"FAIL: project root {root} is not a directory")
    return root


def cmd_write(a) -> int:
    root = resolve_root(a.project_root)
    handoffs, queue_file = queue_paths(root)
    src = pathlib.Path(a.file).expanduser()
    if not src.is_file():
        print(f"FAIL: {src} does not exist")
        return 2
    if not AGENT_LABEL.match(a.to):
        print(f"FAIL: --to must be a lowercase agent slug, got {a.to!r}")
        return 2
    if a.sender and not AGENT_LABEL.match(a.sender):
        print(f"FAIL: --from must be a lowercase agent slug, got {a.sender!r}")
        return 2
    handoffs.mkdir(parents=True, exist_ok=True)
    body = src.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    prefix = f"round-{a.round:02d}-" if a.round is not None else ""
    name = f"{prefix}to-{a.to}-{stamp}.md"
    (handoffs / name).write_bytes(body)

    rows = load(queue_file)
    handoff_id = f"h-{digest[:10]}"
    rows.append(
        {
            "id": handoff_id,
            "round": a.round,
            "to": a.to,
            "from": a.sender or os.environ.get("SYNTHESIS_HANDOFF_SELF", ""),
            "file": f"resources/handoffs/{name}",
            "sha256": digest,
            "summary": a.summary or "",
            "state": "pending",
            "written": dt.datetime.now().isoformat(timespec="seconds"),
        }
    )
    save(handoffs, queue_file, rows)
    print(f"handoff {handoff_id} written for {a.to}: resources/handoffs/{name}")
    print(f"sha256 {digest}")
    print(
        "\nAnnounce it on the coordination board so the other side finds it "
        "without the principal relaying anything:"
    )
    print(
        f"  coordination.py message --from <your-session-id> --to "
        f'<their-session-id> --text "HANDOFF {handoff_id} is pending in '
        f'resources/handoffs/{name} (sha256 {digest}). Run handoff.py read."'
    )
    return 0


def cmd_read(a) -> int:
    root = resolve_root(a.project_root)
    handoffs, queue_file = queue_paths(root)
    me = a.as_agent or os.environ.get("SYNTHESIS_HANDOFF_SELF", "")
    if not me:
        print(
            "FAIL: reader identity is required — pass --as AGENT or set "
            "SYNTHESIS_HANDOFF_SELF. Guessing an identity could claim "
            "another agent's work."
        )
        return 2
    rows = load(queue_file)
    mine = [r for r in rows if r.get("to") == me and r.get("state") == "pending"]
    if not mine:
        print(f"no pending handoff addressed to {me!r}")
        claimed = [
            r for r in rows if r.get("to") == me and r.get("state") == "claimed"
        ]
        if claimed:
            print(
                f"({len(claimed)} already claimed and not marked done — "
                f"see handoff.py list)"
            )
        return 1
    row = sorted(mine, key=lambda r: r.get("written", ""))[0]
    path = root / row["file"]
    body = path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != row["sha256"]:
        print(
            f"FAIL: {row['file']} has changed since it was handed off "
            f"(queue {row['sha256'][:12]}, disk {actual[:12]}). "
            "Refusing to act on it."
        )
        return 2
    row["state"] = "claimed"
    row["claimed"] = dt.datetime.now().isoformat(timespec="seconds")
    save(handoffs, queue_file, rows)
    round_note = f" · round {row['round']}" if row.get("round") is not None else ""
    print(f"=== handoff {row['id']}{round_note} · from {row.get('from') or '?'} · {row['file']}")
    if row.get("summary"):
        print(f"=== {row['summary']}")
    print("=" * 78)
    print(body.decode("utf-8"))
    return 0


def cmd_list(a) -> int:
    root = resolve_root(a.project_root)
    _, queue_file = queue_paths(root)
    rows = load(queue_file)
    if not rows:
        print("handoff queue is empty")
        return 0
    print(f"{'id':<14} {'rnd':>3} {'from':<8} {'to':<8} {'state':<9} file")
    for r in rows:
        rnd = r.get("round")
        print(
            f"{r['id']:<14} {rnd if rnd is not None else '-':>3} "
            f"{(r.get('from') or '?'):<8} {r['to']:<8} {r['state']:<9} {r['file']}"
        )
    pending = [r for r in rows if r["state"] == "pending"]
    print(
        f"\n{len(pending)} pending: "
        + (", ".join(f"{r['id']}->{r['to']}" for r in pending) or "none")
    )
    return 0


def cmd_done(a) -> int:
    root = resolve_root(a.project_root)
    handoffs, queue_file = queue_paths(root)
    rows = load(queue_file)
    for r in rows:
        if r["id"] == a.id:
            r["state"] = "done"
            r["completed"] = dt.datetime.now().isoformat(timespec="seconds")
            save(handoffs, queue_file, rows)
            print(f"{a.id} marked done")
            return 0
    print(f"FAIL: no handoff with id {a.id}")
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], allow_abbrev=False
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--to", required=True)
    w.add_argument("--file", required=True)
    w.add_argument("--round", type=int)
    w.add_argument("--summary")
    w.add_argument("--from", dest="sender")
    w.add_argument("--project-root", default=".")
    r = sub.add_parser("read")
    r.add_argument("--as", dest="as_agent")
    r.add_argument("--project-root", default=".")
    ls = sub.add_parser("list")
    ls.add_argument("--project-root", default=".")
    d = sub.add_parser("done")
    d.add_argument("--id", required=True)
    d.add_argument("--project-root", default=".")
    a = ap.parse_args()
    return {
        "write": cmd_write,
        "read": cmd_read,
        "list": cmd_list,
        "done": cmd_done,
    }[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

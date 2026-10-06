#!/usr/bin/env python3
"""The ritual workers registry, and the desk's coverage line built from it.

Contract: references/ritual-worker-contract.md. The registry is private,
person-level config at `~/.synthesis/ritual/workers.yaml` (or
`RITUAL_WORKERS_FILE`). No file means the classic single-session ritual; a file
that does not validate is refused, never read as "no workers". Paths are stored
`~`-rooted so the file works on every Mac, and expand here.

    ritual_workers.py list
    ritual_workers.py coverage [--date YYYY-MM-DD] [--json]

`coverage` names each registered workspace as folded (newest artifact for the
day, its run type and finish time), pending (active, nothing filed yet) or not
scheduled (on-demand, nothing filed). Dormant workers never count.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simple_yaml import load  # noqa: E402

STATUSES = ("active", "on-demand", "dormant")
RUN_TYPES = ("day-start", "midday", "day-end", "weekly-review")


def registry_path() -> Path:
    return Path(os.environ.get("RITUAL_WORKERS_FILE") or Path.home() / ".synthesis" / "ritual" / "workers.yaml")


def expand(value) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    if not path.is_absolute():
        raise ValueError(f"worker path {value!r} is relative; store it `~`-rooted")
    return path


def load_workers(path: Path | None = None) -> dict:
    path = path or registry_path()
    if not path.exists():
        return {}
    data = load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("contract_version") != 1 or not isinstance(data.get("workers"), dict):
        raise ValueError(f"{path}: needs contract_version: 1 and a workers mapping")
    workers = {}
    for name, entry in data["workers"].items():
        if not isinstance(entry, dict) or entry.get("status") not in STATUSES or not entry.get("artifact_dir"):
            raise ValueError(f"{path}: worker {name!r} needs status ({'|'.join(STATUSES)}) and artifact_dir")
        workers[name] = {**entry, "artifact_dir": expand(entry["artifact_dir"]),
                         "workspace_root": expand(entry["workspace_root"]) if entry.get("workspace_root") else None}
    return workers


def coverage(workers: dict, day: date) -> list[dict]:
    rows = []
    for name, worker in sorted(workers.items()):
        if worker["status"] == "dormant":
            continue
        filed = [(kind, worker["artifact_dir"] / f"{day}-{kind}.md") for kind in RUN_TYPES]
        filed = [(kind, path) for kind, path in filed if path.is_file()]
        if not filed:
            rows.append({"workspace": name, "state": "pending" if worker["status"] == "active" else "not scheduled"})
            continue
        kind, path = filed[-1]  # run order: a later run supersedes an earlier one
        front = path.read_text(encoding="utf-8").split("---")
        meta = load(front[1]) if len(front) > 2 else {}
        rows.append({"workspace": name, "state": "folded", "run_type": kind, "artifact": str(path),
                     "finished": str((meta or {}).get("finished", "unknown")),
                     "outcome": str((meta or {}).get("outcome", "unknown"))})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("list", "coverage"))
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        workers = load_workers()
    except (OSError, ValueError) as exc:
        print(f"ritual_workers: refused: {exc}", file=sys.stderr)
        return 2
    result = ([{"workspace": k, "status": v["status"], "seat": v.get("seat"), "artifact_dir": str(v["artifact_dir"])}
               for k, v in sorted(workers.items())] if args.command == "list"
              else coverage(workers, date.fromisoformat(args.date)))
    if args.json:
        print(json.dumps(result, indent=2))
    elif not workers:
        print("no workers registry: single-session ritual")
    elif args.command == "list":
        print("\n".join(f"{r['workspace']}: {r['status']} -> {r['artifact_dir']}" for r in result))
    else:
        print("coverage: " + " · ".join(
            f"{r['workspace']} {r['run_type']} {r['finished']} ({r['outcome']})" if r["state"] == "folded"
            else f"{r['workspace']} {r['state']}" for r in result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

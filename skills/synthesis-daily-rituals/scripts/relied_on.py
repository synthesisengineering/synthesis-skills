"""Run the health check of everything a person other than the principal relies on.

A workspace declares each one in the ritual config, as `relied_on`: a list of
{"what": "<what it is>", "by": "<who relies on it>", "check": ["<program>", "<argument>", ...]}.
A check runs with no shell and is healthy when it exits 0 in time. Whatever is down prints first.
Exit 0: every check passed, or nothing is declared. 1: something is down, or an entry cannot be run
as written. 2: the config cannot be read or the workspace is not in it, so nothing was checked.
A test two colleagues had come to rely on once stopped, and two scheduled check-ins ran without a look at it.
"""
import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root or the installed runtime: holds synthesis/
from synthesis import rituals  # noqa: E402


def answer(check: list, timeout: float) -> str:
    """Why the thing counts as down; empty when its check exits 0 in time."""
    with tempfile.TemporaryFile() as said:  # a file, not a pipe: a pipe stays open while anything the check started holds it
        try:
            proc = subprocess.Popen(check, stdin=subprocess.DEVNULL, stdout=said, stderr=said, start_new_session=True)
            code = proc.wait(timeout)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):  # it may have ended this instant
                os.killpg(proc.pid, signal.SIGKILL)  # its own process group: the check and anything it started
            return f"no answer in {timeout:g} s"
        except (OSError, ValueError) as exc:
            return f"could not be run ({getattr(exc, 'strerror', None) or exc})"
        said.seek(0)
        line = next(filter(None, map(str.strip, said.read(8192).decode("utf-8", "replace").splitlines())), "")
    return "" if code == 0 else f"exit {code}" + (f": {line[:200]}" if line else "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--workspace", help="check what this workspace declares")
    which.add_argument("--all", action="store_true", help="check every workspace in the ritual config")
    parser.add_argument("--timeout", type=float, default=20, metavar="SECONDS", help="how long each check may take (default 20)")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of lines")
    args = parser.parse_args(argv)
    try:
        cfg = rituals.config()
        if not args.all and args.workspace not in cfg["workspaces"]:
            raise ValueError(f"workspace {args.workspace} is not in it")
        declared = {w: rituals.settings(cfg, w).get("relied_on") or [] for w in (cfg["workspaces"] if args.all else [args.workspace])}
    except (OSError, ValueError, TypeError) as exc:
        print(f"NOT CHECKED: {rituals.state_dir() / 'config.json'}: {exc}", file=sys.stderr)
        return 2
    rows = []
    for workspace, entries in declared.items():
        for n, entry in enumerate(entries if isinstance(entries, list) else [entries], 1):
            entry = entry if isinstance(entry, dict) else {}
            what, by = (str(entry.get(key) or "").strip() for key in ("what", "by"))
            check = entry.get("check")
            if not (what and by):
                why = 'could not be run (an entry needs "what" and "by")'
            elif not (isinstance(check, list) and check and all(isinstance(word, str) for word in check)):
                why = 'could not be run ("check" must be a list of words: the program, then its arguments)'
            else:
                why = answer(check, args.timeout)
            rows.append({"workspace": workspace, "what": what or f"entry {n}", "by": by or "nobody named", "ok": not why, "why": why})
    rows.sort(key=lambda row: row["ok"])  # whatever is down first, each kind in the order the config lists it
    down, none = sum(not row["ok"] for row in rows), [w for w, entries in declared.items() if not entries]
    lines = []
    for row in rows:
        name = f"{row['workspace']}: {row['what']}" if args.all else row["what"]
        lines.append(f"ok {name}" if row["ok"] else f"DOWN {name} (relied on by {row['by']}): {row['why']}")
    lines += [f"nothing another person relies on is declared for {', '.join(none) or 'any workspace'}"] if none or not rows else []
    lines += [f"{len(rows)} relied on, {down} down"] if rows else []
    print(json.dumps({"relied_on": rows, "down": down, "nothing_declared": none}, indent=2) if args.json else "\n".join(lines))
    return 1 if down else 0


if __name__ == "__main__":
    sys.exit(main())

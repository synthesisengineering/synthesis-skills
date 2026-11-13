#!/usr/bin/env python3
"""Everything open for a seat, in one list built from the records.

    plate.py --workspace W --as-of YYYY-MM-DD [--out FILE] [--with-gaps]

One task lives as many copies: in each plan that carried it, a ledger, a register (an audit of 2026-11-11 found
one in nine plans). This builds a single list from the deadline sweep over the folders the workspace declares, so
that nothing depends on memory or on which plan an item was last copied into: the critical deadlines that are
open, the dated items due or past (one whose date passed with nothing written is marked), the dated items ahead,
the newest plan's commitments with no date and no park, a ledger's open rows, and the choices the newest plan puts
with no decision. Each entry says where it sits.

It reads, and writes only the file it is told to. A list that claims to be everything is not built over records
that could not be read: with a gap in the sweep it exits 2, unless `--with-gaps` asks for the list with the gaps
named at its head. Without `--out` the list is printed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decay_sweep  # noqa: E402  (it finds the synthesis runtime, or says that it cannot)
import ritual_state  # noqa: E402

rituals = decay_sweep.rituals  # the runtime the sweep found


def build(workspace: str, as_of, out: Path | None, with_gaps: bool) -> tuple[str, int]:
    """(the list as Markdown, how many entries it holds); exits 2 where it cannot be everything."""
    try:
        roots = decay_sweep.declared(rituals.config(), workspace)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"plate: the ritual config cannot be read ({exc}), so nothing is listed") from None
    if roots is None:
        raise SystemExit(f"plate: {workspace} declares no plan folders in the ritual config, so there is nothing to build the list from")
    report = decay_sweep.collect(roots, as_of, workspace)
    unread: dict = {}  # a source, and each thing about it that could not be read
    for gap in report["gaps"]:
        unread.setdefault(gap["path"], []).append(gap["reason"])
    if unread and not with_gaps:
        raise SystemExit(f"plate: {len(unread)} source(s) could not be read whole, so a list of everything is not built over "
                         "them:\n" + "\n".join(f"  {path}: {'; '.join(why)}" for path, why in unread.items())
                         + "\nMend each, or run with --with-gaps for the list with these named at its head")

    def at(path: str, line: int | None = None) -> str:
        mark = f":{line}" if line else ""
        if out is None:
            return f"({path}{mark})"
        return f"([{Path(path).name}{mark}]({os.path.relpath(path, out.parent)}))"

    def named(row: dict) -> str:
        return f" `{row['identity'][3:]}`" if str(row.get("identity", "")).startswith("id:") else ""

    choices = [(title, path) for path in report.get("plans_read", [])
               for title, _, _ in ritual_state.open_choices(Path(path).read_text(encoding="utf-8", errors="replace"))]
    owed = report["owed"]["rows"]
    sections = [
        ("Not read", [f"{path}: {'; '.join(why)}" for path, why in unread.items()]),
        ("Critical deadlines", [f"{row['due_date']} {row['title']} [{row['class']}]{named(row)} {at(row['path'], row['line'])}"
                                + "".join(f"\n  - {problem}" for problem in row["problems"]) for row in report["critical"]["open"]]),
        ("Due or past", [f"{row['due_date']} {row['title']}{named(row)}" + ", passed with nothing written" * row["unannounced"]
                         + f" {at(row['path'], row['line'])}" for row in report["due"]]),
        ("Dated ahead", [f"{row['due_date']} {row['title']}{named(row)} {at(row['path'], row['line'])}" for row in report["ahead"]]),
        ("Commitments with no date and no park", [f"{row['title']} {at(row['path'], row['line'])}" for row in report["untagged"]]),
        ("Owed in a ledger", [f"{row['item']} [{row['status'] or 'no status'}] since {row['owed_since'] or 'no date'} "
                              f"{at(row['path'], row['line'])}" for row in owed]),
        ("Choices with no decision", [f"{title} {at(path)}" for title, path in choices]),
    ]
    count = sum(len(rows) for name, rows in sections if name != "Not read")
    lines = [f"# Everything open for {workspace}, as of {as_of.isoformat()}", "",
             f"Built from the records by `plate.py`: the deadline sweep over the folders this workspace declares "
             f"({len(report['scanned'])} sources read, {len(unread)} not read whole). Nothing here is from memory, "
             "and nothing closed is here.", ""]
    for name, rows in sections:
        if rows or name != "Not read":
            lines += [f"## {name} ({len(rows)})", "", *[f"- {row}" for row in rows], *([""] if rows else [])]
    return "\n".join(lines).rstrip("\n") + "\n", count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    parser.add_argument("--out", type=Path, help="write the list to this file; its links then lead from that file")
    parser.add_argument("--with-gaps", action="store_true", help="build the list over a sweep with gaps, the gaps named at its head")
    args = parser.parse_args(argv)
    try:
        as_of = decay_sweep.iso_day(args.as_of)
        text, count = build(args.workspace, as_of, args.out.expanduser().absolute() if args.out else None, args.with_gaps)
    except ValueError as exc:
        print(f"plate: --as-of {args.as_of!r}: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.out:
        args.out.expanduser().absolute().write_text(text, encoding="utf-8")
        print(f"written {args.out.expanduser().absolute()}: {count} open")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

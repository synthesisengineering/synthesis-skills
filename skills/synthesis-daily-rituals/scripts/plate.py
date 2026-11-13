#!/usr/bin/env python3
"""Everything open for a seat, in one list built from the records.

    plate.py --workspace W --as-of YYYY-MM-DD [--out FILE] [--with-gaps]

One task lives as many copies: in each plan that carried it, a ledger, a register (an audit of 2026-11-11 found
one in nine plans). This builds a single list from the deadline sweep over the folders the workspace declares, so
that nothing depends on memory or on which plan an item was last copied into: the critical deadlines that are
open and what reads like one and is not classified, the dated items due or past (one whose date passed with
nothing written is marked; an item with no Decay ID that several plans copy is listed once, with how many copies),
the dated items ahead, the newest plan's commitments with no date and no park, a ledger's open rows, and the
choices the newest plan puts with no decision. Each entry says where it sits.

It reads, and writes only the file it is told to: never a file in a folder the workspace declares (its plans, its
artifacts, its records), and never over a file that is not a list of its own. A list that claims to be everything
is not built over records the sweep did not take in full, a ledger's row too short to read among them: it exits 2,
unless `--with-gaps` asks for the list with those named at its head. Without `--out` the list is printed.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decay_sweep  # noqa: E402  (it finds the synthesis runtime, or says that it cannot)
import ritual_state  # noqa: E402

rituals = decay_sweep.rituals  # the runtime the sweep found

TITLE = "# Everything open for "  # the list's first words: a file that opens otherwise is no list of this script's
SPACED = re.compile(r"[\s()]")  # a path that Markdown takes as a link's target only between angle brackets


def build(workspace: str, as_of, out: Path | None, with_gaps: bool) -> tuple[str, int]:
    """(the list as Markdown, how many entries it holds); exits 2 where it cannot be everything."""
    try:
        roots = decay_sweep.declared(rituals.config(), workspace)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"plate: the ritual config cannot be read ({exc}), so nothing is listed") from None
    if roots is None:
        raise SystemExit(f"plate: {workspace} declares no plan folders in the ritual config, so there is nothing to build the list from")
    if not roots:
        raise SystemExit(f"plate: {workspace} declares that it keeps no dated plans, so there is nothing to build the list from")
    if out is not None:
        inside = next((root for root, _ in roots if os.path.realpath(out).startswith(os.path.realpath(root) + os.sep)), None)
        if inside is not None:
            raise SystemExit(f"plate: {out} is in {inside}, a folder this workspace declares: the list is read from there and "
                             "never written there. Name a file somewhere else")
        if out.exists() and not (out.is_file() and out.read_text(encoding="utf-8", errors="replace").startswith(TITLE)):
            raise SystemExit(f"plate: {out} is not a list this script wrote, so it is not written over. Name another file")
    report = decay_sweep.collect(roots, as_of, workspace)
    unread: dict = {}  # a source, and each thing about it that the sweep did not take
    for gap in report["gaps"]:
        unread.setdefault(gap["path"], []).append(gap["reason"])
    if report["owed"]["unread"]:
        unread["a ledger"] = [f"{report['owed']['unread']} row(s) of a ledger had too few cells to read (decay_sweep.py counts them under owed.unread)"]
    if unread and not with_gaps:
        raise SystemExit(f"plate: {len(unread)} source(s) were not taken in full by the sweep, so a list of everything is not built "
                         "over them:\n" + "\n".join(f"  {path}: {'; '.join(why)}" for path, why in unread.items())
                         + "\nMend each, or run with --with-gaps for the list with these named at its head")

    def at(path: str, line: int | None = None) -> str:
        mark = f":{line}" if line else ""
        if out is None:
            return f"({path}{mark})"
        target = os.path.relpath(path, out.parent).replace("|", "%7C")
        return f"([{Path(path).name}{mark}]({'<' + target + '>' if SPACED.search(target) else target}))"

    def named(row: dict) -> str:
        return f" `{row['identity'][3:]}`" if str(row.get("identity", "")).startswith("id:") else ""

    choices = []
    for path in report.get("plans_read", []):
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        for title, item, _ in ritual_state.open_choices(text):
            found = text.find(item.splitlines()[0])  # the line the choice stands on
            choices.append((title, path, text.count("\n", 0, found) + 1 if found >= 0 else None))
    owed, due, copies = report["owed"]["rows"], [], {}
    for row in report["due"]:  # an item with no ID is another item in each plan that copies it: listed once, with how many
        key = (row["title"], row["due_date"]) if str(row.get("identity", "")).startswith("source:") else None
        if key in copies:
            copies[key]["copies"] += 1
        else:
            due.append(dict(row, copies=1))
            copies.update({key: due[-1]} if key else {})
    sections = [
        ("Not read", [f"{path}: {'; '.join(why)}" for path, why in unread.items()]),
        ("Critical deadlines", [f"{row['due_date']} {row['title']} [{row['class']}]{named(row)} {at(row['path'], row['line'])}"
                                + "".join(f"\n  - {problem}" for problem in row["problems"]) for row in report["critical"]["open"]]),
        ("Possibly critical, not classified", [f"{row['due_date']} {row['title']}{named(row)} {at(row['path'], row['line'])}"
                                               for row in report["critical"]["unclassified"]]),
        ("Due or past", [f"{row['due_date']} {row['title']}{named(row)}" + ", passed with nothing written" * row["unannounced"]
                         + f", {row['copies']} copies with no Decay ID" * (row["copies"] > 1) + f" {at(row['path'], row['line'])}" for row in due]),
        ("Dated ahead", [f"{row['due_date']} {row['title']}{named(row)} {at(row['path'], row['line'])}" for row in report["ahead"]]),
        ("Commitments with no date and no park", [f"{row['title']} {at(row['path'], row['line'])}" for row in report["untagged"]]),
        ("Owed in a ledger", [f"{row['item']} [{row['status'] or 'no status'}] since {row['owed_since'] or 'no date'} "
                              f"{at(row['path'], row['line'])}" for row in owed]),
        ("Choices with no decision", [f"{title} {at(path, line)}" for title, path, line in choices]),
    ]
    count = sum(len(rows) for name, rows in sections if name not in ("Not read", "Possibly critical, not classified"))
    lines = [f"{TITLE}{workspace}, as of {as_of.isoformat()}", "",
             f"Built from the records by `plate.py`: the deadline sweep over the folders this workspace declares "
             f"({len(report['scanned'])} sources read, {len(unread)} not taken in full). Nothing here is from memory, "
             "and nothing closed is here.", ""]
    for name, rows in sections:
        if rows or name not in ("Not read", "Possibly critical, not classified"):
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
        try:
            args.out.expanduser().absolute().write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"plate: {args.out.expanduser().absolute()} could not be written ({exc})", file=sys.stderr)
            return 2
        print(f"written {args.out.expanduser().absolute()}: {count} open")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Carry every unanswered decision of a packet forward by its exact id.

    python3 carry_forward.py DIR/<date>-<slug>-spec.json --successor NEXT.json [--title "..."]
    python3 carry_forward.py DIR/<date>-<slug>-spec.json --check reconciliation.json

A decision counts as answered only when a rulings file that record_rulings.py wrote
against this exact spec records a choice for its id. By default those are the
*-rulings.json files beside the spec that bind to it; --rulings names them instead.

--successor writes a spec holding exactly the unanswered rows, ids and content unchanged,
for build_packet.py to build and file. --check verifies a declared reconciliation,
{"items": [{"id": ..., "status": "answered", "ruling": FILE} or
           {"id": ..., "status": "carried", "to": DESTINATION}]},
with paths relative to the spec's folder. Every id of the spec must appear exactly once;
missing, extra or duplicate ids are refused, and so is an item called answered whose
ruling file records no choice for it (a narrative "answered" closes nothing). A
destination that is a spec file must hold the same id. Nothing here authorizes, executes
or completes any action: it accounts for decisions only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import record_rulings as rr  # noqa: E402
from build_packet import spec_digest, strict_json, validate  # noqa: E402


class CarryError(ValueError):
    """A ruling, reconciliation or successor that would lose or invent a decision."""


def _load(path: pathlib.Path):
    return strict_json(path.read_text(encoding="utf-8"))


def recorded_choices(spec: dict, path: pathlib.Path) -> dict:
    """{id: option value} for the choices a rulings file records against this exact spec."""
    try:
        record = _load(path)
        if record.get("schema_version") != 2 or record["binding"]["spec_sha256"] != spec_digest(spec):
            raise CarryError(f"{path.name} is not a ruling recorded against this exact spec")
        state = {r["id"]: {"choice": r["choice_value"], "note": r.get("note") or "", "bulk": r["accepted_in_bulk"]}
                 for r in record["rulings"]}
        expected = rr.parse_summary(rr.compose_summary(spec, state), spec)
        # Notes filed before the page normalized trailing whitespace still name the same choice.
        record["rulings"] = [dict(r, note=rr.normalize_note(r.get("note") or "") or None) for r in record["rulings"]]
        if any(json.dumps(record.get(k), sort_keys=True) != json.dumps(v, sort_keys=True) for k, v in expected.items()):
            raise CarryError(f"{path.name} does not match the spec's rows, options or counts")
    except CarryError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CarryError(f"{path.name} is not a ruling recorded against this exact spec ({exc})") from exc
    return {rid: s["choice"] for rid, s in state.items() if s["choice"] is not None}


def answered(spec: dict, spec_path: pathlib.Path, rulings) -> dict:
    """{id: [ruling file names]} for every id some recorded ruling answers."""
    if rulings is None:  # the rulings filed beside the spec that bind to it
        rulings = []
        for path in sorted(spec_path.parent.glob("*-rulings.json")):
            try:
                if _load(path).get("binding", {}).get("spec_sha256") == spec_digest(spec):
                    rulings.append(path)
            except (OSError, ValueError, AttributeError):
                continue
    found = {}
    for path in rulings:
        for rid in recorded_choices(spec, path):
            found.setdefault(rid, []).append(path.name)
    return found


def successor(spec: dict, spec_path: pathlib.Path, done: dict, title) -> dict | None:
    rows = [row for row in spec["rows"] if row["id"] not in done]
    if not rows:
        return None
    nxt = dict(spec, rows=rows, carried_from=spec_path.name)
    if title:
        nxt["title"] = title
    hard = [p for p in validate(nxt) if not p.startswith(("NOTE:", "READER:"))]
    if hard:
        raise CarryError("the successor spec would not build: " + "; ".join(hard))
    return nxt


def check(spec: dict, spec_path: pathlib.Path, reconciliation) -> list:
    """Problems with a declared reconciliation; an empty list means every id is accounted for."""
    items = reconciliation.get("items") if isinstance(reconciliation, dict) else None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return ['the reconciliation must be {"items": [objects with id and status]}']
    ids, expected, problems = [i.get("id") for i in items], [r["id"] for r in spec["rows"]], []
    if not all(isinstance(i, str) for i in ids):
        return ["every reconciliation item needs a string id"]
    for name, found in (("duplicate", [i for n, i in enumerate(ids) if i in ids[:n]]),
                        ("missing", [i for i in expected if i not in ids]),
                        ("extra", [i for i in ids if i not in expected])):
        if found:
            problems.append(f"{name} ids: {', '.join(map(repr, dict.fromkeys(found)))}")
    base, cache = spec_path.parent, {}
    for item in items:
        rid, status = item.get("id"), item.get("status")
        if status == "answered":
            ruling = item.get("ruling")
            if not isinstance(ruling, str) or not ruling.strip():
                problems.append(f"{rid!r} is called answered without the rulings file that records its choice")
                continue
            try:
                if ruling not in cache:
                    cache[ruling] = recorded_choices(spec, base / ruling)
                if rid not in cache[ruling]:
                    problems.append(f"{rid!r} is called answered, but {ruling} records no choice for it; carry it forward")
            except CarryError as exc:
                problems.append(f"{rid!r} is called answered, but {exc}; carry it forward")
        elif status == "carried":
            to = item.get("to")
            if not isinstance(to, str) or not to.strip():
                problems.append(f"{rid!r} is carried, but no destination is named")
            elif to.endswith(".json") and (base / to).is_file():
                try:
                    rows = _load(base / to).get("rows")
                    held = isinstance(rows, list) and any(isinstance(r, dict) and r.get("id") == rid for r in rows)
                except (OSError, ValueError, AttributeError):
                    held = False
                if not held:
                    problems.append(f"{rid!r} is carried to {to}, which holds no row with that exact id")
        else:
            problems.append(f"{rid!r} has status {status!r}; use 'answered' or 'carried'")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=pathlib.Path, help="the filed spec of the packet being replaced")
    ap.add_argument("--rulings", type=pathlib.Path, nargs="+", metavar="FILE",
                    help="rulings files to count (default: the *-rulings.json beside the spec that bind to it)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--successor", metavar="PATH", help="write the spec of unanswered rows here ('-' for stdout)")
    mode.add_argument("--check", type=pathlib.Path, metavar="RECONCILIATION", help="verify a declared reconciliation")
    ap.add_argument("--title", help="title for the successor spec (default: the same title)")
    args = ap.parse_args()
    if args.title and not args.successor:
        ap.error("--title applies to --successor")
    try:
        spec = _load(args.spec)
        if not isinstance(spec, dict) or [p for p in validate(spec) if not p.startswith(("NOTE:", "READER:"))]:
            raise CarryError(f"{args.spec.name} is not a valid packet spec")
        if args.check:
            reconciliation = _load(args.check)
            problems = check(spec, args.spec, reconciliation)
            if problems:
                print("carry_forward: refused:\n" + "\n".join("  - " + p for p in problems), file=sys.stderr)
                return 2
            items = reconciliation["items"]
            done = sum(i["status"] == "answered" for i in items)
            print(f"reconciled {len(items)} ids: {done} answered with recorded rulings, {len(items) - done} carried "
                  "forward. This accounts for decisions only; it authorizes and completes nothing.")
            return 0
        done = answered(spec, args.spec, args.rulings)
        nxt = successor(spec, args.spec, done, args.title)
        if nxt is None:
            print(f"all {len(spec['rows'])} decisions have recorded rulings; nothing to carry forward")
            return 0
        text = json.dumps(nxt, indent=2, ensure_ascii=False) + "\n"
        carried = ", ".join(r["id"] for r in nxt["rows"])
        report = (f"carried {len(nxt['rows'])} of {len(spec['rows'])} decisions forward by exact id: {carried}"
                  + ("" if len(nxt["rows"]) >= 5 else " (fewer than five: build with --allow-small or ask in chat)"))
        if args.successor == "-":
            sys.stdout.write(text)
        else:
            with open(args.successor, "x", encoding="utf-8") as out:  # never overwrite an existing file
                out.write(text)
            report = f"wrote {args.successor}: " + report
        print(report, file=sys.stderr if args.successor == "-" else sys.stdout)
    except (OSError, ValueError) as exc:
        print(f"carry_forward: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Record the summary an action sheet's "Copy summary" button produced, and carry what is open.

    python3 record_actions.py paste.txt --spec DIR/<date>-<slug>-spec.json --file-into DIR
    python3 record_actions.py - --spec spec.json --stdout              # paste on stdin
    python3 record_actions.py --successor NEXT.json --actions DIR/<date>-<slug>-actions.json \\
        [--agent-done ID ...] [--not-found ID ...] [--title "..."]

The summary's last line binds it to the exact spec the page was built from and carries each
row's mark, who and note. The recorder rebuilds the readable lines from that spec and refuses
any difference, quoting what it received (never a note). A paste made on another version of
the sheet is refused, never mapped onto changed rows. --file-into writes
<date>-<slug>-actions.json beside the spec.

A row the principal hands to the agent is recorded with what they permitted: exactly that
recipient, channel, address and text (by its SHA-256), once. Every other mark is the
principal's claim, to confirm from its source, not proof.

--successor writes the next sheet's spec: every row still open or marked "not now", by exact
id and unchanged. --agent-done names rows the agent finished and confirmed from the source
since the paste (sends after the principal's code, rows handed to the agent): they leave the
list and show under "Done for you". --not-found names rows marked done whose source shows no
trace of them: they carry forward again.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_sheet as bs  # noqa: E402  (it puts the decision packet's engine on the path)
from record_rulings import JS_WHITESPACE, _paste_lines, js_length, normalize_note  # noqa: E402

F = bs.SUMMARY
STATUSES = ("open", "done", "skipped", "not-now")
AUTHORIZATION = {
    "agent_rows": "A row with who 'agent' permits exactly what its 'permitted' names (recipient, channel, address, "
                  "link, subject and the text by SHA-256), once. Stop on any difference from it.",
    "approve_rows": "Nothing here approves a staged send: it goes out only on the principal's approval code, typed "
                    "in chat.",
    "marks": "A mark is the principal's claim. Confirm each message from its source before logging it under On your "
             "behalf; a row with no readable trace is logged as principal reports done.",
    "authentication": "unverified: the permission is the principal's own pasted message, which this file records",
}


class SummaryError(ValueError):
    """The paste is not a summary of this exact sheet in the page's format."""


class CarryError(ValueError):
    """A successor that would lose an open row, or close one the agent cannot have finished."""


def _rows(spec: dict) -> list:
    return [(section, row) for section in ("approve", "do") for row in spec.get(section, [])]


def status_key(section: str, saved: dict) -> str:
    return saved["mark"] or (section == "do" and saved["who"]) or "open"


def valid_state(section: str, row: dict, mark, who) -> bool:
    """The states the page can reach: an approve row is open, held or not now; a do row may be
    handed to the agent only when its agent field is 'can', and then it carries no mark."""
    if mark not in ((None, "skipped", "not-now") if section == "approve" else (None, "done", "skipped", "not-now")):
        return False
    if who is None:
        return True
    if section != "do" or row["agent"] != "can":
        return False
    return mark is None if who == "agent" else who == "me" and mark in (None, "done")


def _check_spec(spec) -> None:
    problems = bs.validate(spec)
    if problems:
        raise SummaryError("invalid current spec: " + "; ".join(problems))


def summary_lines(spec: dict, state: dict, storage_blocked: bool = False) -> list:
    """(line, field, row id) for every line the page's renderSummary() writes before the binding."""
    out, tally = [], {"approve": {}, "do": {}}

    def emit(text, field, rid=None):
        out.extend((line, field, rid) for line in text.split("\n"))
    emit(spec["title"], "title")
    emit("=" * js_length(spec["title"]), "title underline")
    emit("", "separator")
    for section in ("approve", "do"):
        if spec.get(section):
            emit(F["headings"][section], "section heading")
        for row in spec.get(section, []):
            saved = state[row["id"]]
            key = status_key(section, saved)
            tally[section][key] = tally[section].get(key, 0) + 1
            emit(row["id"] + "  " + bs.row_name(row), "name line", row["id"])
            emit(F["status_prefix"] + F[section][key], "status line", row["id"])
            if saved["note"]:
                emit(F["note_prefix"] + saved["note"], "note", row["id"])
            emit("", "separator", row["id"])
    for section in ("approve", "do"):
        if spec.get(section):
            emit(F["headings"][section] + ": " + ", ".join(f"{sum(tally[section].get(k, 0) for k in keys)} {label}"
                                                           for keys, label in F["counts"][section]) + ".", "count line")
    if storage_blocked:
        emit(F["storage"], "storage line")
    return out


def _state(spec: dict, bound_rows) -> dict:
    """Validate the bound rows against the sheet's exact rows and the states the page can reach."""
    listed = _rows(spec)
    if not isinstance(bound_rows, list) or len(bound_rows) != len(listed):
        got = len(bound_rows) if isinstance(bound_rows, list) else type(bound_rows).__name__
        raise SummaryError(f"the binding carries {got} rows; the sheet has {len(listed)}")
    state = {}
    for index, ((section, row), bound) in enumerate(zip(listed, bound_rows), start=1):
        if not isinstance(bound, dict) or set(bound) != {"id", "mark", "who", "note"}:
            shape = sorted(bound) if isinstance(bound, dict) else type(bound).__name__
            raise SummaryError(f"bound row {index} needs exactly id, mark, who and note; received {shape}")
        if bound["id"] != row["id"]:
            raise SummaryError(f"bound row {index} is {bound['id']!r}; the sheet's row {index} is {row['id']!r}")
        if not isinstance(bound["note"], str):
            raise SummaryError(f"row {row['id']}: the note must be a string")
        if not valid_state(section, row, bound["mark"], bound["who"]):
            raise SummaryError(f"row {row['id']}: mark {bound['mark']!r} with who {bound['who']!r} is not a state "
                               f"this {section} row can be in")
        state[row["id"]] = {"mark": bound["mark"], "who": bound["who"], "note": normalize_note(bound["note"])}
    return state


def compose_summary(spec: dict, state: dict, storage_blocked: bool = False) -> str:
    """The exact text the page's Copy summary button writes for this spec and state, where
    state maps a row id to {"mark", "who", "note"}, each optional."""
    _check_spec(spec)
    if not isinstance(state, dict) or set(state) - {row["id"] for _, row in _rows(spec)}:
        raise SummaryError("state names row ids the sheet does not have")
    bound = [{"id": row["id"], "mark": state.get(row["id"], {}).get("mark"), "who": state.get(row["id"], {}).get("who"),
              "note": normalize_note(state.get(row["id"], {}).get("note") or "")} for _, row in _rows(spec)]
    lines = summary_lines(spec, _state(spec, bound), storage_blocked)
    binding = {"schema_version": 1, "spec_sha256": bs.spec_digest(spec), "rows": bound, "storage_blocked": storage_blocked}
    return "\n".join(line for line, _, _ in lines) + "\n" + F["binding"] + json.dumps(
        binding, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _parse(text: str, spec: dict) -> tuple:
    """(state, binding) for a paste of this exact sheet; SummaryError otherwise."""
    lines = _paste_lines(text)
    if len(lines) < 2 or not lines[0] or lines[1] != "=" * js_length(lines[0]):
        raise SummaryError('the paste does not start with a sheet summary: the first line must be the sheet title and '
                           f'the second as many "=" characters (got first line: {lines[0] if lines else ""!r})')
    if not lines[-1].startswith(F["binding"]):
        raise SummaryError(f"the last line is not the sheet's binding line ({F['binding']!r}...); received "
                           f"{lines[-1][:160]!r}. Paste the whole summary, unedited, through its last line")
    try:
        binding = bs.strict_json(lines[-1][len(F["binding"]):])
    except ValueError as exc:
        raise SummaryError(f"the binding line is not valid JSON: {exc}") from exc
    if (not isinstance(binding, dict) or set(binding) != {"schema_version", "spec_sha256", "rows", "storage_blocked"}
            or binding["schema_version"] != 1 or type(binding["storage_blocked"]) is not bool
            or not isinstance(binding["spec_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", binding["spec_sha256"])):
        raise SummaryError("the binding line lacks the schema-1 fields: schema_version, spec_sha256, rows, "
                           "storage_blocked")
    _check_spec(spec)
    if binding["spec_sha256"] != bs.spec_digest(spec):
        raise SummaryError(f"this summary was made on a different version of the sheet (it binds "
                           f"{binding['spec_sha256']}; the spec is {bs.spec_digest(spec)}). Marks are never mapped onto "
                           "changed rows: rebuild the sheet from the current spec and ask again")
    state = _state(spec, binding["rows"])
    expected, received = summary_lines(spec, state, binding["storage_blocked"]), lines[:-1]
    for index in range(max(len(expected), len(received))):
        wanted, field, rid = expected[index] if index < len(expected) else (None, "trailing text", None)
        got = received[index] if index < len(received) else None
        if field == "note" and got is not None:
            got = got.rstrip(JS_WHITESPACE)
        if got != (wanted if wanted is None or wanted.strip() else ""):
            where = f"row {rid}: {field}" if rid is not None else field
            if field == "note":  # a refusal never repeats the principal's note
                raise SummaryError(f"{where} differs at summary line {index + 1}; paste the note unchanged")
            raise SummaryError(f"{where} differs at summary line {index + 1}: expected "
                               f"{'nothing more' if wanted is None else repr(wanted)}, received "
                               f"{'the end of the paste' if got is None else repr(got)}")
    for rid, saved in state.items():
        if bs.APPROVAL_CODE.search(saved["note"]):
            raise SummaryError(f"row {rid}: the note holds text shaped like an approval code (approve, then a code "
                               "of the guard's shape). Codes go in chat and are never filed: ask the principal to take it out of "
                               "the note and copy the summary again")
    return state, binding


def make_record(spec: dict, state: dict, binding: dict) -> dict:
    """The actions record: per row its status, who, note and, for a row handed to the agent, what was permitted."""
    rows, counts = [], {"approve": {}, "do": {}}
    for section, row in _rows(spec):
        saved = state[row["id"]]
        key = status_key(section, saved)
        counts[section][key] = counts[section].get(key, 0) + 1
        status = key if key in STATUSES else "open"
        entry = {"id": row["id"], "section": section, "name": bs.row_name(row), "status": status,
                 "who": "me" if status == "done" else saved["who"], "note": saved["note"] or None}
        if key == "agent":
            entry["permitted"] = {k: v for k, v in (
                ("recipient", row.get("who")), ("channel", row["channel"]), ("address", row.get("address")),
                ("href", row.get("href")), ("subject", row.get("subject")),
                ("text_sha256", hashlib.sha256(row["text"].encode("utf-8")).hexdigest())) if v}
        rows.append(entry)
    return {"sheet": spec["title"], "schema_version": 1,
            "binding": {"status": "spec-bound", "spec_sha256": binding["spec_sha256"]},
            "storage_blocked": binding["storage_blocked"], "counts": counts, "rows": rows,
            "authorization": AUTHORIZATION}


def parse_summary(text: str, spec: dict) -> dict:
    """The actions record a paste makes against this exact spec (without date or file name)."""
    state, binding = _parse(text, spec)
    return make_record(spec, state, binding)


def check_record(spec: dict, record) -> dict:
    """{id: row entry} once the record is shown to be what make_record() writes for this exact spec."""
    try:
        _check_spec(spec)
        if record["schema_version"] != 1 or record["binding"]["spec_sha256"] != bs.spec_digest(spec):
            raise CarryError("the actions record was not made against this exact spec")
        listed, entries = _rows(spec), record["rows"]
        if [entry["id"] for entry in entries] != [row["id"] for _, row in listed]:
            raise CarryError("the actions record's rows are not the spec's rows, in order")
        state = {}
        for (section, row), entry in zip(listed, entries):
            done = entry["status"] == "done"
            who = ("me" if row.get("agent") == "can" else None) if done else entry["who"]
            mark = None if entry["status"] == "open" else entry["status"]
            if not valid_state(section, row, mark, who):
                raise CarryError(f"row {row['id']!r} records a state its sheet cannot reach")
            state[row["id"]] = {"mark": mark, "who": who, "note": entry["note"] or ""}
        expected = make_record(spec, state, {"spec_sha256": record["binding"]["spec_sha256"],
                                             "storage_blocked": record["storage_blocked"]})
        if any(json.dumps(record.get(k), sort_keys=True) != json.dumps(v, sort_keys=True) for k, v in expected.items()):
            raise CarryError("the actions record does not match what its spec and marks produce")
    except CarryError:
        raise
    except (SummaryError, TypeError, KeyError, AttributeError) as exc:
        raise CarryError(f"not an actions record of this exact spec ({exc})") from exc
    return {entry["id"]: entry for entry in record["rows"]}


def successor(spec: dict, record: dict, spec_name: str, agent_done=(), not_found=(), title=None) -> tuple:
    """(next spec or None, carried ids): open and not-now rows by exact id, unchanged."""
    entries = check_record(spec, record)
    agent_done, not_found, problems = list(agent_done), list(not_found), []
    for flag, ids in (("--agent-done", agent_done), ("--not-found", not_found)):
        problems += [f"{flag} names {rid!r} twice" for rid in sorted({i for i in ids if ids.count(i) > 1})]
    problems += [f"{rid!r} is named by both --agent-done and --not-found" for rid in sorted(set(agent_done) & set(not_found))]
    for rid in agent_done:
        entry = entries.get(rid)
        if entry is None:
            problems.append(f"--agent-done {rid!r}: the sheet has no row with that id")
        elif entry["status"] != "open" or (entry["section"] == "do" and entry["who"] != "agent"):
            problems.append(f"--agent-done {rid!r}: it is {entry['status']}" + (f", who {entry['who']}" if entry["who"] else "")
                            + "; the agent finishes only approved sends and rows the principal handed to it")
    for rid in not_found:
        entry = entries.get(rid)
        if entry is None:
            problems.append(f"--not-found {rid!r}: the sheet has no row with that id")
        elif entry["status"] != "done":
            problems.append(f"--not-found {rid!r}: it is {entry['status']}, not marked done")
    if problems:
        raise CarryError("; ".join(problems))
    carried = [rid for rid, entry in entries.items()
               if (entry["status"] in ("open", "not-now") and rid not in agent_done) or rid in not_found]
    nxt = {"title": title or spec["title"]}
    nxt.update({key: spec[key] for key in ("audience", "summary_intro") if key in spec})
    nxt["carried_from"] = spec_name
    finished = [{"kind": "sent after your code" if section == "approve" else "done by the agent", "label": bs.row_name(row)}
                for section, row in _rows(spec) if row["id"] in agent_done]
    if finished:
        nxt["done"] = finished
    for section in ("approve", "do"):
        rows = [row for row in spec.get(section, []) if row["id"] in carried]
        if rows:
            nxt[section] = rows
    if not carried:
        return None, carried
    problems = bs.validate(nxt)
    if problems:
        raise CarryError("the successor spec would not build: " + "; ".join(problems))
    return nxt, carried


def _counts_text(record: dict) -> str:
    approve, do = record["counts"]["approve"], record["counts"]["do"]
    parts = [", ".join(f"{sum(table.get(k, 0) for k in keys)} {label}" for keys, label in F["counts"][section])
             for section, table in (("approve", approve), ("do", do)) if table]
    return f"{len(record['rows'])} rows: " + "; ".join(parts)


def _record_main(args) -> int:
    try:
        raw = sys.stdin.read() if args.paste == "-" else pathlib.Path(args.paste).read_text(encoding="utf-8")
        spec = bs.strict_json(args.spec.read_text(encoding="utf-8"))
        state, binding = _parse(raw, spec)
        built = make_record(spec, state, binding)
        record = {"sheet": built["sheet"], "recorded_on": args.date or datetime.date.today().isoformat(),
                  "spec_file": args.spec.name, **{k: v for k, v in built.items() if k != "sheet"}}
        payload = (json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        agent = [r["id"] for r in record["rows"] if r["who"] == "agent"]
        if args.file_into:
            stem = f"{record['recorded_on']}-{bs.slugify(record['sheet'])}"
            dest = args.file_into / f"{stem}-actions.json"
            if dest.exists() and dest.read_bytes() != payload:  # a changed response keeps the earlier one
                dest = args.file_into / f"{stem}-{hashlib.sha256(payload).hexdigest()}-actions.json"
            bs.write_preserved(dest, payload)
            out = sys.stderr if args.stdout else sys.stdout
            print(f"filed {dest}  ({_counts_text(record)})", file=out)
            if agent:
                print(f"handed to the agent: {', '.join(agent)} (exactly as each row's 'permitted' says, once)", file=out)
        if args.stdout:
            sys.stdout.write(payload.decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"record_actions: {exc}", file=sys.stderr)
        return 2
    return 0


def _successor_main(args) -> int:
    try:
        record = bs.strict_json(args.actions.read_text(encoding="utf-8"))
        name = record.get("spec_file") if isinstance(record, dict) else None
        if not args.spec and not (isinstance(name, str) and name and pathlib.Path(name).name == name):
            raise CarryError("the actions record names no spec file beside it; pass --spec")
        spec_path = args.spec or args.actions.parent / name
        spec = bs.strict_json(spec_path.read_text(encoding="utf-8"))
        nxt, carried = successor(spec, record, spec_path.name, args.agent_done, args.not_found, args.title)
        finished = len(args.agent_done)
        if nxt is None:
            print(f"nothing carries forward: all {len(record['rows'])} rows are done, skipped or finished by the agent")
            return 0
        text = json.dumps(nxt, indent=2, ensure_ascii=False) + "\n"
        report = (f"carried {len(carried)} of {len(record['rows'])} rows forward by exact id: {', '.join(carried)}"
                  + (f"; {finished} finished by the agent listed as done" if finished else ""))
        if args.successor == "-":
            sys.stdout.write(text)
            print(report, file=sys.stderr)
        else:
            with open(args.successor, "x", encoding="utf-8") as out:  # never overwrite an existing file
                out.write(text)
            print(f"wrote {args.successor}: {report}")
    except (OSError, ValueError) as exc:
        print(f"record_actions: {exc}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("paste", nargs="?", help="file holding the pasted summary ('-' for stdin)")
    ap.add_argument("--spec", type=pathlib.Path, help="the exact filed spec the sheet was built from")
    ap.add_argument("--file-into", type=pathlib.Path, metavar="DIR",
                    help="the owning project's existing resources/artifacts/ directory")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="record date (default: today); not proof of when anyone acted")
    ap.add_argument("--stdout", action="store_true", help="print the record")
    ap.add_argument("--successor", metavar="PATH", help="write the next sheet's spec here ('-' for stdout)")
    ap.add_argument("--actions", type=pathlib.Path, metavar="FILE", help="with --successor: the filed actions record")
    ap.add_argument("--agent-done", nargs="+", default=[], metavar="ID",
                    help="with --successor: rows the agent finished and confirmed from the source")
    ap.add_argument("--not-found", nargs="+", default=[], metavar="ID",
                    help="with --successor: rows marked done whose source shows no trace of them")
    ap.add_argument("--title", help="with --successor: the next sheet's title (default: the same title)")
    args = ap.parse_args()
    if args.date and bs.parse_iso_date(args.date) is None:
        ap.error(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
    if args.successor:
        if args.paste or args.file_into or args.stdout or args.date:
            ap.error("--successor works from a filed actions record: pass --actions, not a paste")
        if not args.actions:
            ap.error("--successor needs --actions FILE, the filed actions record")
        return _successor_main(args)
    if args.actions or args.agent_done or args.not_found or args.title:
        ap.error("--actions, --agent-done, --not-found and --title go with --successor")
    if not args.paste:
        ap.error("pass the file holding the paste ('-' for stdin), or --successor")
    if not args.spec:
        ap.error("--spec is required: the exact filed spec the sheet was built from")
    if not args.file_into and not args.stdout:
        ap.error("pass --file-into DIR or --stdout")
    if args.file_into and not args.file_into.is_dir():
        ap.error(f"--file-into: {args.file_into} is not an existing directory; use the owning project's "
                 "resources/artifacts/")
    return _record_main(args)


if __name__ == "__main__":
    sys.exit(main())

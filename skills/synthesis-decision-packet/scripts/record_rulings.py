#!/usr/bin/env python3
"""Record the summary a decision packet's "Copy summary" button produced.

    python3 record_rulings.py paste.txt --spec DIR/<date>-<slug>-spec.json --file-into DIR
    python3 record_rulings.py - --spec spec.json --stdout          # paste on stdin

The summary's last line binds it to the exact spec the page was built from (the spec's
digest) and carries every selection. The recorder rebuilds the readable lines from that
spec and those selections and refuses any difference, quoting what it received. A paste
made against an older option meaning or row set is refused, never mapped onto the new
meaning. --file-into writes <date>-<slug>-rulings.json beside the spec and page; without
--spec it uses the one *-spec.json in DIR whose title matches the paste. Every record says
authorization.granted: false: recording a ruling authorizes nothing.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_packet import (parse_iso_date, review_assets_ready, slugify, spec_digest,  # noqa: E402
                          strict_json, validate, write_preserved)

# The format, literal by literal; a test pins each JS_FORMAT_LITERALS entry to the page's
# renderSummary() so this file and the packet's JavaScript cannot drift apart silently.
UNDECIDED = "— not yet decided"
TOOK = "  (took the recommendation)"
BULK = "  (accepted in bulk)"
OVERRODE = "  (OVERRODE: recommended "
DECISION_PREFIX = "    -> "
NOTE_PREFIX = "    note: "
BULK_TRAILER = " of those were accepted in bulk rather than considered one by one — weight them accordingly."
STORAGE_TRAILER = "(This browser blocked local storage, so nothing was saved between sittings.)"
BINDING_PREFIX = "Decision packet binding v2: "
JS_FORMAT_LITERALS = (
    '"— not yet decided"', '"  (took the recommendation)"', '"  (accepted in bulk)"',
    '"  (OVERRODE: recommended "', '"    -> "', '"    note: "', '"Decided "',
    '" of those were accepted in bulk rather than considered one by one — "',
    '"weight them accordingly."', '"(This browser blocked local storage, so nothing was saved between sittings.)"',
    '"Decision packet binding v2: "',
)
JS_WHITESPACE = ("\u0009\u000a\u000b\u000c\u000d         "
                 "         　﻿")
FIRST_LINE_MESSAGE = ('the pasted text does not start with a packet summary: the first line must be the '
                      'packet title and the second line the same number of "=" characters, exactly as the '
                      'packet\'s "Copy summary" button produces (got first line: {got!r})')


class SummaryError(ValueError):
    """The paste is not a summary of this exact spec in the button's format."""


def js_length(text: str) -> int:
    """String length as JavaScript counts it (UTF-16 units); the page underlines the title
    with "=".repeat(SPEC.title.length), so an emoji counts twice."""
    return len(text.encode("utf-16-le")) // 2


def js_trim(text: str) -> str:
    return text.strip(JS_WHITESPACE)


def normalize_note(text: str) -> str:
    """The page's note transport: LF lines, no trailing whitespace per line, trimmed.
    Indentation, word spacing and paragraph breaks inside the note stay significant."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return js_trim("\n".join(line.rstrip(JS_WHITESPACE) for line in lines))


def _paste_lines(text: str) -> list:
    """Lines of the paste; whitespace-only lines read as blank, outer blank lines dropped."""
    lines = [line if line.strip() else "" for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _options(spec: dict, row: dict) -> list:
    return row.get("options") or spec["options"]


def summary_lines(spec: dict, state: dict, storage_blocked: bool = False) -> list:
    """(line, field, row id) for every line renderSummary() emits before the binding line."""
    out = []

    def emit(text, field, rid=None):
        out.extend((line, field, rid) for line in text.split("\n"))
    emit(spec["title"], "title")
    emit("=" * js_length(spec["title"]), "title underline")
    emit("", "separator")
    decided = bulk = 0
    for row in spec["rows"]:
        saved = state.get(row["id"], {})
        choice, rec = saved.get("choice"), row.get("recommendation")
        labels = {o["value"]: o["label"] for o in _options(spec, row)}
        mark = UNDECIDED if choice is None else labels[choice]
        if choice is not None and rec:
            mark += OVERRODE + labels[rec] + ")" if choice != rec else (BULK if saved.get("bulk") else TOOK)
        decided += choice is not None
        bulk += bool(saved.get("bulk"))
        emit(row["id"] + "  " + row["label"], "label line", row["id"])
        emit(DECISION_PREFIX + mark, "decision line", row["id"])
        if saved.get("note"):
            emit(NOTE_PREFIX + saved["note"], "note", row["id"])
        emit("", "separator", row["id"])
    emit(f"Decided {decided} of {len(spec['rows'])}.", "count line")
    if bulk:
        emit(f"{bulk}{BULK_TRAILER}", "bulk line")
    if storage_blocked:
        emit(STORAGE_TRAILER, "storage line")
    return out


def _check_spec(spec: dict) -> None:
    hard = [p for p in validate(spec) if not p.startswith(("NOTE:", "READER:"))]
    if hard:
        raise SummaryError("invalid current spec: " + "; ".join(hard))


def _state(spec: dict, selections) -> dict:
    """Validate the bound selections against the spec's exact rows and option values."""
    if not isinstance(selections, list) or len(selections) != len(spec["rows"]):
        got = len(selections) if isinstance(selections, list) else selections
        raise SummaryError(f"the binding carries {got!r} rows; the spec has {len(spec['rows'])}")
    state = {}
    for index, (row, sel) in enumerate(zip(spec["rows"], selections), start=1):
        if not isinstance(sel, dict) or set(sel) != {"id", "choice", "note", "bulk"}:
            raise SummaryError(f"bound row {index} needs exactly id, choice, note and bulk; received {sel!r}")
        rid, choice, note, bulk = sel["id"], sel["choice"], sel["note"], sel["bulk"]
        if rid != row["id"]:
            raise SummaryError(f"bound row {index} is {rid!r}; the spec's row {index} is {row['id']!r}")
        values = [o["value"] for o in _options(spec, row)]
        if choice is not None and choice not in values:
            raise SummaryError(f"row {rid}: received option value {choice!r}, which is not one of {values}")
        if not isinstance(note, str) or type(bulk) is not bool:
            raise SummaryError(f"row {rid}: note must be a string and bulk true or false")
        if choice is not None and not review_assets_ready(row):
            raise SummaryError(f"row {rid}: unavailable review material cannot carry a choice")
        if bulk and choice != row.get("recommendation"):
            raise SummaryError(f"row {rid}: a bulk acceptance must take the row's recommendation")
        state[rid] = {"choice": choice, "note": normalize_note(note), "bulk": bulk}
    return state


def compose_summary(spec: dict, state: dict, storage_blocked: bool = False) -> str:
    """The exact text the page's "Copy summary" button produces for this spec and state.
    `state` maps row id -> {"choice": option value, "note": str, "bulk": bool}, each optional."""
    _check_spec(spec)
    if not isinstance(state, dict) or set(state) - {r["id"] for r in spec["rows"]}:
        raise SummaryError("state names row ids the spec does not have")
    selections = [{"id": r["id"], "choice": state.get(r["id"], {}).get("choice"),
                   "note": normalize_note(state.get(r["id"], {}).get("note") or ""),
                   "bulk": state.get(r["id"], {}).get("bulk") is True} for r in spec["rows"]]
    lines = summary_lines(spec, _state(spec, selections), storage_blocked)
    binding = {"schema_version": 2, "spec_sha256": spec_digest(spec), "selections": selections,
               "storage_blocked": storage_blocked}
    return "\n".join(line for line, _, _ in lines) + "\n" + BINDING_PREFIX + json.dumps(
        binding, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _parse(text: str, spec: dict) -> tuple:
    """(rulings dict, binding) for a paste of this exact spec; SummaryError otherwise."""
    lines = _paste_lines(text)
    if len(lines) < 2 or not lines[0] or lines[1] != "=" * js_length(lines[0]):
        raise SummaryError(FIRST_LINE_MESSAGE.format(got=lines[0] if lines else ""))
    if not lines[-1].startswith(BINDING_PREFIX):
        raise SummaryError(f"the last line is not the packet's binding line ({BINDING_PREFIX!r}...); received "
                           f"{lines[-1]!r}. Paste the whole summary, unedited, through its last line. A summary "
                           "from a packet built before the binding line existed cannot be recorded: rebuild "
                           "the packet from its spec and ask again")
    try:
        binding = strict_json(lines[-1][len(BINDING_PREFIX):])
    except ValueError as exc:
        raise SummaryError(f"the binding line is not valid JSON: {exc}") from exc
    if (not isinstance(binding, dict) or set(binding) != {"schema_version", "spec_sha256", "selections", "storage_blocked"}
            or binding["schema_version"] != 2 or type(binding["storage_blocked"]) is not bool
            or not isinstance(binding["spec_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", binding["spec_sha256"])):
        raise SummaryError(f"the binding line does not have the schema-2 fields; received {lines[-1]!r}")
    _check_spec(spec)
    if binding["spec_sha256"] != spec_digest(spec):
        raise SummaryError(f"this summary was made against a different version of the spec (it binds "
                           f"{binding['spec_sha256']}; the current spec is {spec_digest(spec)}). Answers are "
                           "never mapped onto changed rows or option meanings: rebuild the packet from the "
                           "current spec and ask again")
    state = _state(spec, binding["selections"])
    expected = summary_lines(spec, state, binding["storage_blocked"])
    received = lines[:-1]
    for index in range(max(len(expected), len(received))):
        wanted, field, rid = expected[index] if index < len(expected) else (None, "trailing text", None)
        got = received[index] if index < len(received) else None
        if field == "note" and got is not None:
            got = got.rstrip(JS_WHITESPACE)
        if got != (wanted if wanted is None or wanted.strip() else ""):
            where = f"row {rid}: {field}" if rid is not None else field
            if field == "note":  # a refusal never repeats the principal's note text
                raise SummaryError(f"{where} differs at summary line {index + 1}; paste the note unchanged")
            raise SummaryError(f"{where} differs at summary line {index + 1}: expected "
                               f"{'nothing more' if wanted is None else repr(wanted)}, received "
                               f"{'the end of the paste' if got is None else repr(got)}")
    rulings = []
    for row in spec["rows"]:
        saved, rec = state[row["id"]], row.get("recommendation")
        choice, labels = saved["choice"], {o["value"]: o["label"] for o in _options(spec, row)}
        ruling = {"id": row["id"], "label": row["label"], "choice_value": choice, "choice_label": labels.get(choice),
                  "took_recommendation": choice == rec if choice is not None and rec is not None else None,
                  "accepted_in_bulk": saved["bulk"],
                  "recommended_label": labels.get(rec) if choice is not None else None,
                  "note": saved["note"] or None}
        # The ruling keeps the exact material and prior position it was made on.
        ruling.update({k: json.loads(json.dumps(row[k])) for k in ("revision", "delivery", "review_assets")
                       if "review_assets" in row})
        ruling.update({"prior_position": json.loads(json.dumps(row["prior_position"]))} if "prior_position" in row else {})
        rulings.append(ruling)
    parsed = {"packet": spec["title"], "decided": sum(r["choice_value"] is not None for r in rulings),
              "total": len(rulings), "rulings": rulings, "schema_version": 2,
              "binding": {"status": "spec-bound", "spec_sha256": binding["spec_sha256"]}}
    return parsed, binding


def parse_summary(text: str, spec: dict) -> dict:
    """The rulings a paste records against this exact spec; SummaryError otherwise."""
    return _parse(text, spec)[0]


def _find_spec(path, directory, text: str) -> tuple:
    if path is None:
        title = (_paste_lines(text) or [""])[0]
        found = []
        for candidate in sorted(directory.glob("*-spec.json")) if directory else []:
            try:
                data = strict_json(candidate.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("title") == title:
                found.append(candidate)
        if len(found) != 1:
            raise SummaryError(f"found {len(found)} filed *-spec.json titled {title!r}; pass --spec PATH "
                               "to name the exact spec this paste answers")
        path = found[0]
    return strict_json(path.read_text(encoding="utf-8")), path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("paste", help="file holding the pasted summary ('-' for stdin)")
    ap.add_argument("--spec", type=pathlib.Path, help="the exact filed spec the packet was built from")
    ap.add_argument("--file-into", type=pathlib.Path, metavar="DIR",
                    help="the owning project's existing resources/artifacts/ directory")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="record date (default: today); not proof of decision time")
    ap.add_argument("--stdout", action="store_true", help="print the record")
    args = ap.parse_args()
    if not args.file_into and not args.stdout:
        ap.error("pass --file-into DIR or --stdout")
    if not args.file_into and not args.spec:
        ap.error("--stdout without --file-into needs --spec")
    if args.date and parse_iso_date(args.date) is None:
        ap.error(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
    if args.file_into and not args.file_into.is_dir():
        ap.error(f"--file-into: {args.file_into} is not an existing directory; use the owning project's "
                 "resources/artifacts/")
    try:
        raw = sys.stdin.read() if args.paste == "-" else pathlib.Path(args.paste).read_text(encoding="utf-8")
        spec, spec_path = _find_spec(args.spec, args.file_into, raw)
        parsed, binding = _parse(raw, spec)
        record = {**parsed, "ruled_on": args.date or datetime.date.today().isoformat(),
                  "spec_file": spec_path.name, "storage_blocked": binding["storage_blocked"],
                  "authorization": {"granted": False, "authentication": "unverified",
                                    "owner": "existing action owner must verify trusted authority and exact operation"}}
        payload = (json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if args.file_into:
            stem = f"{record['ruled_on']}-{slugify(record['packet'])}"
            dest = args.file_into / f"{stem}-rulings.json"
            if dest.exists() and dest.read_bytes() != payload:  # a changed response keeps the earlier one
                dest = args.file_into / f"{stem}-{hashlib.sha256(payload).hexdigest()}-rulings.json"
            write_preserved(dest, payload)
            print(f"filed {dest}  ({record['decided']} of {record['total']} decided; no action authority granted)",
                  file=sys.stderr if args.stdout else sys.stdout)
        if args.stdout:
            sys.stdout.write(payload.decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"record_rulings: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

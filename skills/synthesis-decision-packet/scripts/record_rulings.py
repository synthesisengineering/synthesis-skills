#!/usr/bin/env python3
"""File a principal's pasted decision-packet summary as a rulings record.

The packet's "Copy summary" button emits one fixed text format (renderSummary() in
build_packet.py). This script parses exactly that text and files it beside the spec and
the page that `build_packet.py --file-into` wrote, so every agent working the owning
project reads the rulings from the repository instead of from one chat transcript.

    python3 record_rulings.py paste.txt --file-into PROJECT/resources/artifacts/
    python3 record_rulings.py - --file-into DIR --date 2026-09-14 < paste.txt
    python3 record_rulings.py paste.txt --stdout        # print the JSON, file nothing

Output: <date>-<slug>-rulings.json, where the slug is the packet title's, the same slug
build_packet.py gives the spec and page copies. Fields:

    packet              the packet title (the summary's first line)
    ruled_on            the --date, or today
    decided, total      the counts from the summary's "Decided n of m." line
    rulings[]           one per row, in packet order:
        id, label             the row
        choice_label          the option label pressed, or null when undecided
        took_recommendation   true (took it, or accepted in bulk), false (overrode it),
                              null (undecided, or the row carried no recommendation)
        accepted_in_bulk      true only for rows the "Take all remaining" control set;
                              the packet keeps that fact distinct and so does this file
        recommended_label     the option the agent recommended, when the summary says
        note                  the row's free-text note, or null

The grammar, exactly as the button produces it (compose_summary() below is the same
format in Python, and test_build_packet.py pins its literals to the JavaScript):

    <title>
    <"=" repeated once per UTF-16 code unit of the title - JavaScript's .length,
     which counts an emoji as two; js_length() below counts the same way>
    <blank>
    <id>  <label>                          one block per row, in packet order
        -> <choice label>[  (took the recommendation)]
                         [  (accepted in bulk)]
                         [  (OVERRODE: recommended <label>)]
        -> — not yet decided               when the row is undecided
        note: <first line of the note>     only when a note was typed; the note's
    <further note lines, unindented>       own line breaks follow as they were typed
    <blank>
    Decided <n> of <m>.
    <k> of those were accepted in bulk rather than considered one by one — weight them accordingly.
    (This browser blocked local storage, so nothing was saved between sittings.)

The last two lines appear only when they apply. A row block is recognised by its
decision line: the line before "    -> " is the row's "<id>  <label>" line, and the
line before that is the blank that closes the previous block. Row ids never start with
whitespace and never contain two consecutive spaces (build_packet.py refuses such ids),
so the first double space in the header line separates id from label.

Malformed input is refused with the line that failed, the form expected there and the
text received; an edited or truncated paste is refused when its row count or decided
count disagrees with its own "Decided n of m." line. Lines holding only whitespace are
read as blank, since a chat surface may pad an empty line to a space; the page emits
no whitespace-only line of its own.

Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_packet import parse_iso_date, slugify  # noqa: E402

# The format, literal by literal. test_build_packet.py asserts every entry of
# JS_FORMAT_LITERALS appears in renderSummary(), so this file and the packet's
# JavaScript cannot drift apart silently.
UNDECIDED = "— not yet decided"
TOOK = "  (took the recommendation)"
BULK = "  (accepted in bulk)"
OVERRODE = "  (OVERRODE: recommended "
DECISION_PREFIX = "    -> "
NOTE_PREFIX = "    note: "
ID_LABEL_SEP = "  "
DECIDED_LINE = "Decided {decided} of {total}."
BULK_TRAILER = (" of those were accepted in bulk rather than considered one by one — "
                "weight them accordingly.")
STORAGE_TRAILER = "(This browser blocked local storage, so nothing was saved between sittings.)"

JS_FORMAT_LITERALS = (
    '"— not yet decided"',
    '"  (took the recommendation)"',
    '"  (accepted in bulk)"',
    '"  (OVERRODE: recommended "',
    '"    -> "',
    '"    note: "',
    '"Decided "',
    '" of those were accepted in bulk rather than considered one by one — "',
    '"weight them accordingly."',
    '"(This browser blocked local storage, so nothing was saved between sittings.)"',
)

DECIDED_RE = re.compile(r"Decided (\d+) of (\d+)\.")
BULK_TRAILER_RE = re.compile(r"(\d+)" + re.escape(BULK_TRAILER))
MARK_RE = re.compile(
    r"(.*?)(?:  \((took the recommendation|accepted in bulk|OVERRODE: recommended (.+))\))?")

FIRST_LINE_MESSAGE = (
    "the pasted text does not start with a packet summary: the first line must be the "
    'packet title and the second line the same number of "=" characters, exactly as the '
    'packet\'s "Copy summary" button produces (got first line: {got!r})'
)
WHOLE_SUMMARY = "paste the whole summary, unedited, through its last line"


class SummaryError(ValueError):
    """The pasted text is not a packet summary in the button's format."""


def js_length(text: str) -> int:
    """The length JavaScript reports for `text`: UTF-16 code units, so a
    character outside the Basic Multilingual Plane (an emoji) counts as two.
    The page underlines the title with "=".repeat(SPEC.title.length)."""
    return len(text.encode("utf-16-le")) // 2


# ---------------------------------------------------------------------------
# The format in Python: what renderSummary() emits for a given spec and state
# ---------------------------------------------------------------------------

def compose_summary(spec: dict, state: dict, storage_blocked: bool = False) -> str:
    """Render the summary the packet's button would emit.

    `state` maps row id -> {"choice": option value, "note": str, "bulk": bool},
    each key optional, mirroring the packet's saved state.
    """
    title = str(spec["title"])
    lines = [title, "=" * js_length(title), ""]
    decided = 0
    bulk = 0
    for row in spec["rows"]:
        saved = state.get(row["id"], {})
        choice = saved.get("choice")
        options = row.get("options") or spec["options"]

        def label_for(value):
            for o in options:
                if o.get("value") == value:
                    return str(o["label"])
            return str(value)

        if choice is not None:
            decided += 1
        mark = UNDECIDED if choice is None else label_for(choice)
        if choice is not None and row.get("recommendation"):
            if choice != row["recommendation"]:
                mark += OVERRODE + label_for(row["recommendation"]) + ")"
            else:
                mark += BULK if saved.get("bulk") else TOOK
        if saved.get("bulk"):
            bulk += 1
        lines.append(str(row["id"]) + ID_LABEL_SEP + str(row["label"]))
        lines.append(DECISION_PREFIX + mark)
        note = str(saved.get("note") or "")
        if note.strip():
            lines.append(NOTE_PREFIX + note.strip())
        lines.append("")
    lines.append(DECIDED_LINE.format(decided=decided, total=len(spec["rows"])))
    if bulk:
        lines.append(f"{bulk}{BULK_TRAILER}")
    if storage_blocked:
        lines.append(STORAGE_TRAILER)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_mark(rid: str, label: str, mark: str, line_no: int) -> dict:
    ruling = {
        "id": rid,
        "label": label,
        "choice_label": None,
        "took_recommendation": None,
        "accepted_in_bulk": False,
        "recommended_label": None,
        "note": None,
    }
    if mark == UNDECIDED:
        return ruling
    m = MARK_RE.fullmatch(mark)
    choice, suffix, recommended = m.group(1), m.group(2), m.group(3)
    if not choice:
        raise SummaryError(f"line {line_no}: the decision line names no option: {mark!r}")
    ruling["choice_label"] = choice
    if suffix == "took the recommendation":
        ruling["took_recommendation"] = True
        ruling["recommended_label"] = choice
    elif suffix == "accepted in bulk":
        ruling["took_recommendation"] = True
        ruling["accepted_in_bulk"] = True
        ruling["recommended_label"] = choice
    elif suffix is not None:
        ruling["took_recommendation"] = False
        ruling["recommended_label"] = recommended
    return ruling


def parse_summary(text: str) -> dict:
    """Parse a pasted summary into {packet, decided, total, rulings}.

    Raises SummaryError, whose message names the line that failed and the form
    expected there.
    """
    lines = [line if line.strip() else ""
             for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) < 2 or not lines[0] or lines[1] != "=" * js_length(lines[0]):
        raise SummaryError(FIRST_LINE_MESSAGE.format(got=lines[0] if lines else ""))
    title = lines[0]

    terminal = None
    for i in range(len(lines) - 1, 1, -1):
        m = DECIDED_RE.fullmatch(lines[i])
        if m:
            terminal = i
            break
    if terminal is None:
        raise SummaryError(f'no "Decided <n> of <m>." line - {WHOLE_SUMMARY}')
    decided_n, total_n = int(m.group(1)), int(m.group(2))
    for offset, extra in enumerate(lines[terminal + 1:], start=terminal + 2):
        if extra == STORAGE_TRAILER or BULK_TRAILER_RE.fullmatch(extra):
            continue
        raise SummaryError(f"line {offset}: unexpected text after the Decided line: {extra!r}")

    body = lines[2:terminal]  # body[i] is line i + 3
    if not body or body[0] != "":
        raise SummaryError(
            "line 3: expected a blank line after the title underline, got "
            f"{body[0] if body else lines[terminal]!r}")
    headers = [
        i for i in range(1, len(body) - 1)
        if body[i - 1] == "" and body[i] and not body[i][0].isspace()
        and body[i + 1].startswith(DECISION_PREFIX)
    ]
    rulings = []
    for k, h in enumerate(headers):
        end = headers[k + 1] - 1 if k + 1 < len(headers) else len(body)
        header = body[h]
        if ID_LABEL_SEP not in header:
            raise SummaryError(f"line {h + 3}: expected '<id>  <label>', got {header!r}")
        rid, label = header.split(ID_LABEL_SEP, 1)
        ruling = _parse_mark(rid, label, body[h + 1][len(DECISION_PREFIX):], h + 4)
        # After the decision line the page emits either the note, or the blank
        # that closes the block. Anything else between here and the next row
        # header is content the format has no place for: a stray line, or a
        # would-be header whose decision line is missing. Blank lines are
        # skipped so the refusal quotes the offending content, never a blank.
        j = h + 2
        while j < end and body[j] == "":
            j += 1
        rest = body[j:end]
        while rest and rest[-1] == "":
            rest.pop()
        if rest:
            if not rest[0].startswith(NOTE_PREFIX):
                raise SummaryError(
                    f"line {j + 3}: expected '{NOTE_PREFIX}' or the next row header "
                    f"('<id>  <label>' followed by a '{DECISION_PREFIX}' line) after the "
                    f"decision line, got {rest[0]!r}")
            ruling["note"] = "\n".join([rest[0][len(NOTE_PREFIX):]] + rest[1:])
        rulings.append(ruling)

    if len(rulings) != total_n:
        raise SummaryError(
            f"the Decided line says {total_n} rows but {len(rulings)} row blocks were found - "
            f"{WHOLE_SUMMARY}")
    decided_found = sum(1 for r in rulings if r["choice_label"] is not None)
    if decided_found != decided_n:
        raise SummaryError(
            f"the Decided line says {decided_n} decided but {decided_found} rows carry a "
            f"decision - {WHOLE_SUMMARY}")
    return {"packet": title, "decided": decided_n, "total": total_n, "rulings": rulings}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paste", help="file holding the pasted summary ('-' for stdin)")
    ap.add_argument("--file-into", metavar="DIR",
                    help="file <date>-<slug>-rulings.json into DIR, the owning project's "
                         "resources/artifacts/ directory; DIR must exist")
    ap.add_argument("--date", metavar="YYYY-MM-DD",
                    help="the ruled_on date and the filed name's prefix (default: today)")
    ap.add_argument("--replace", action="store_true",
                    help="overwrite a rulings file already filed for the same date and packet")
    ap.add_argument("--stdout", action="store_true", help="print the rulings JSON to stdout")
    args = ap.parse_args()

    if not args.file_into and not args.stdout:
        ap.error("pass --file-into DIR (the owning project's resources/artifacts/) or --stdout")
    if args.date and parse_iso_date(args.date) is None:
        ap.error(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
    directory = None
    if args.file_into:
        directory = pathlib.Path(args.file_into)
        if not directory.is_dir():
            print(f"--file-into: {directory} is not an existing directory - pass the owning "
                  "project's resources/artifacts/ directory and create it first", file=sys.stderr)
            return 2

    raw = sys.stdin.read() if args.paste == "-" else pathlib.Path(args.paste).read_text(encoding="utf-8")
    try:
        parsed = parse_summary(raw)
    except SummaryError as exc:
        print(f"record_rulings: {exc}", file=sys.stderr)
        return 2

    record = {
        "packet": parsed["packet"],
        "ruled_on": parse_iso_date(args.date) if args.date else datetime.date.today().isoformat(),
        "decided": parsed["decided"],
        "total": parsed["total"],
        "rulings": parsed["rulings"],
    }
    payload = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if args.stdout:
        sys.stdout.write(payload)
    if directory is not None:
        slug = slugify(record["packet"])
        # Rulings attach to a filed spec. A hand-authored page has no spec, so
        # its paste cannot become a rulings file — this closes the loop the
        # skill_outputs doctor check opens: unmarked pages can never graduate
        # to closed records. Any filed date matches; rulings may land a day
        # after the packet.
        if not sorted(directory.glob(f"*-{slug}-spec.json")):
            print(f"record_rulings: no *-{slug}-spec.json in {directory} - rulings file "
                  "against the spec build_packet.py filed, not against a bare page; "
                  "build the packet with the generator first", file=sys.stderr)
            return 2
        dest = directory / f"{record['ruled_on']}-{slug}-rulings.json"
        if dest.exists() and not args.replace:
            print(f"record_rulings: {dest} already exists - pass --replace to overwrite the "
                  "filed rulings", file=sys.stderr)
            return 2
        dest.write_text(payload, encoding="utf-8")
        print(f"filed {dest}  ({record['decided']} of {record['total']} decided)",
              file=sys.stderr if args.stdout else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

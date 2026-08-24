#!/usr/bin/env python3
"""Semantic currency of durable-context headers, checked per field.

A `CONTEXT.md` header is a cache over the session log: `**Last session:**`
points at the newest logged session and `**Phase:**` describes the state it
left. The log is append-only truth. A header field that describes an older
state than the log's newest entry is stale even when every file is committed —
"records agree with git" means committed, not current.

This module exists because two prior implementations of that idea failed in
ways worth encoding permanently:

1. **Date comparison alone cannot catch same-day staleness.** Multi-round
   cross-agent work routinely logs many sessions on one calendar day, so a
   stale header and the newest entry share a date.
2. **Aggregating independently maintained fields fails open.** The first
   same-day check concatenated `Last session` and `Phase` and compared
   `max()` over the union, so updating either field satisfied the check for
   both, and a fresh Phase masked a stale Last session. Fields that are
   maintained separately must be judged separately.
3. **Free prose mentions older ordinals.** A heading like
   "(round 11 — round 10 refuted)" mentions two rounds. Taking `max()` over
   every number in a blob of prose is guesswork. The convention this module
   relies on instead: a heading or field leads with its own identity, so the
   FIRST ordinal of each family in a given field is that field's identity,
   and later mentions are commentary.

Semantics
---------

- Ordinals are `(family, number)` pairs — "round 11", "wave-3", "Phase 2" —
  for a small closed set of families. Families never compare across each
  other.
- A field's identity per family is the FIRST number of that family in the
  field.
- The log's current number per family is the MAX across the newest-date
  entries' identities — max over entries, first within each entry — so entry
  order and trailing mentions cannot drag it down.
- Each header field is compared independently. A field that lags the log in
  any shared family is reported by name. There is no union and no masking.

Findings (`kind` values)
------------------------

  header-behind-log      Last session's date is older than the newest log date
  header-field-stale     a named header field's ordinal lags the log's current
                         ordinal in the same family
  header-ahead-of-log    Last session's date is newer than any logged entry
  header-unparseable     no `**Last session:** YYYY-MM-DD` could be read
  log-missing            no dated session entries exist

`header-unparseable` and `log-missing` are coverage limits, not staleness:
completed and superseded records legitimately use other conventions. Report
them as what the check could not see, never as a defect count.

CLI
---

    context_currency.py ROOT [ROOT ...] [--json] [--quiet]

Each ROOT is a directory whose immediate children are project directories.
`--quiet` restricts output to staleness findings (header-behind-log,
header-field-stale). Exit codes: 0 no findings, 1 findings, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADER_DATE = re.compile(
    r"^\*\*Last session:\*\*\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE
)
FIELD_LINE = re.compile(r"^\*\*(Phase|Last session):\*\*([^\n]*)", re.MULTILINE)
# Session logs use both `##` and `###` for dated entries.
LOG_ENTRY = re.compile(r"^#{2,3}\s+(\d{4}-\d{2}-\d{2})([^\n]*)", re.MULTILINE)
# Closed family set; `\b` keeps "background" and "rounds" from matching, the
# `[\s-]*` accepts "round 2", "round-2", and "round  2".
ORDINAL = re.compile(r"\b(round|wave|phase|step|part)[\s-]*(\d+)\b", re.IGNORECASE)

STALENESS_KINDS = {"header-behind-log", "header-field-stale"}


def first_ordinals(text: str) -> dict[str, int]:
    """The FIRST number per family in `text` — its identity, not its max."""
    found: dict[str, int] = {}
    for match in ORDINAL.finditer(text):
        family = match.group(1).lower()
        if family not in found:
            found[family] = int(match.group(2))
    return found


def header_fields(text: str) -> dict[str, str]:
    """The Phase and Last-session field values, by field name."""
    return {m.group(1): m.group(2).strip() for m in FIELD_LINE.finditer(text)}


def header_incoherence(text: str) -> list[tuple[str, int, int]]:
    """Same-family disagreements between Phase and Last session.

    Returns (family, phase_number, last_session_number) triples where the two
    header fields disagree. Any disagreement is incoherent: the fields
    describe one state and must move together.
    """
    fields = header_fields(text)
    phase = first_ordinals(fields.get("Phase", ""))
    last = first_ordinals(fields.get("Last session", ""))
    return [
        (family, phase[family], last[family])
        for family in sorted(phase.keys() & last.keys())
        if phase[family] != last[family]
    ]


def log_state(project: Path) -> tuple[str | None, str | None, dict[str, int]]:
    """(newest date, file, current ordinals) from the session log.

    Current ordinals take the max across every newest-date entry of that
    entry's first-per-family ordinal, so neither entry order nor trailing
    mentions of older ordinals can understate the log.
    """
    sessions = project / "sessions"
    if not sessions.is_dir():
        return None, None, {}
    entries: list[tuple[str, str, str]] = []  # (date, file, descriptor)
    for log in sorted(sessions.glob("*.md")):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for date, descriptor in LOG_ENTRY.findall(text):
            entries.append((date, log.name, descriptor))
    if not entries:
        return None, None, {}
    newest = max(entry[0] for entry in entries)
    current: dict[str, int] = {}
    newest_file = None
    for date, name, descriptor in entries:
        if date != newest:
            continue
        newest_file = name
        for family, number in first_ordinals(descriptor).items():
            if number > current.get(family, -1):
                current[family] = number
    return newest, newest_file, current


def audit_project(project: Path) -> list[dict]:
    """Every currency finding for one project record."""
    context = project / "CONTEXT.md"
    if not context.is_file():
        return []
    try:
        text = context.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [{"project": str(project), "kind": "header-unparseable",
                 "detail": f"unreadable: {exc}"}]

    date_match = HEADER_DATE.search(text)
    log_date, log_file, log_current = log_state(project)

    if not date_match:
        return [{"project": str(project), "kind": "header-unparseable",
                 "detail": "no '**Last session:** YYYY-MM-DD' header found",
                 "log_date": log_date}]
    header_date = date_match.group(1)
    if log_date is None:
        return [{"project": str(project), "kind": "log-missing",
                 "detail": "no dated session entries under sessions/",
                 "header_date": header_date}]

    findings: list[dict] = []
    if log_date > header_date:
        findings.append({
            "project": str(project), "kind": "header-behind-log",
            "detail": f"header says {header_date}; {log_file} records {log_date}",
            "header_date": header_date, "log_date": log_date,
        })
    elif header_date > log_date:
        findings.append({
            "project": str(project), "kind": "header-ahead-of-log",
            "detail": f"header says {header_date}; newest log entry is "
                      f"{log_date} ({log_file})",
            "header_date": header_date, "log_date": log_date,
        })

    # Per-field ordinal currency — each field judged alone, never a union.
    for field_name, value in sorted(header_fields(text).items()):
        for family, number in sorted(first_ordinals(value).items()):
            current = log_current.get(family)
            if current is not None and number < current:
                findings.append({
                    "project": str(project), "kind": "header-field-stale",
                    "field": field_name, "family": family,
                    "detail": f"**{field_name}:** says {family} {number}; "
                              f"{log_file} records {family} {current} "
                              f"(log date {log_date})",
                    "header_ordinal": number, "log_ordinal": current,
                })
    return findings


def currency_findings(project: Path) -> list[tuple[str, str]]:
    """(message, remedy) pairs for staleness findings only — the doctor's view.

    Coverage-limit kinds are excluded here: the doctor's structural checks
    already govern missing or unconventional records, and this function must
    add signal only where the evidence is comparable.
    """
    remedy = (
        "update the stale header field with context_edit.py set-field; it "
        "refuses an edit that leaves Phase and Last session disagreeing"
    )
    return [
        (finding["detail"], remedy)
        for finding in audit_project(project)
        if finding["kind"] in STALENESS_KINDS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet", action="store_true",
                        help="report only staleness findings")
    args = parser.parse_args()

    findings: list[dict] = []
    scanned = 0
    for root in args.roots:
        root = root.expanduser()
        if not root.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            return 2
        for project in sorted(p for p in root.iterdir() if p.is_dir()):
            if not (project / "CONTEXT.md").is_file():
                continue
            scanned += 1
            findings.extend(audit_project(project))

    if args.quiet:
        findings = [f for f in findings if f["kind"] in STALENESS_KINDS]

    if args.json:
        print(json.dumps({"scanned": scanned, "findings": findings}, indent=2))
    else:
        by_kind: dict[str, int] = {}
        for finding in findings:
            by_kind[finding["kind"]] = by_kind.get(finding["kind"], 0) + 1
        for finding in findings:
            print(f"{finding['kind']}: {finding['project']}")
            print(f"    {finding['detail']}")
        summary = ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items()))
        print(f"\nscanned {scanned} project record(s); {len(findings)} "
              f"finding(s){': ' + summary if summary else ''}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

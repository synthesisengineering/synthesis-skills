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
  body-marker-stale      a section's `*State as of: ...*` marker lags the log
                         by date or by same-family ordinal
  body-marker-absent     an ordinal-paced record carries no as-of markers, so
                         its body currency is unverifiable (coverage, not
                         staleness)
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
from datetime import date
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
# Body sections that describe operational state end with an emphasis line:
#   *State as of: 2026-08-24 (round 14)*
# The marker converts unstructured prose currency into the structured problem
# this module already solves. Prose without a marker cannot be judged for
# truth; that absence is itself surfaced, because a current header above stale
# operational sections is a stronger false receipt than an obviously stale
# file.
STATE_AS_OF = re.compile(
    r"^\*State as of:\s*(\d{4}-\d{2}-\d{2})([^\n*]*)\*\s*$", re.MULTILINE
)
SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

STALENESS_KINDS = {"header-behind-log", "header-field-stale", "body-marker-stale"}

# Item-level currency. Sections cover prose; these cover the open-items lists
# whose entries carry an implicit present tense nobody re-dates. Stamping each
# item makes its age travel with it, so appending stays safe and any reader can
# compute overdue-ness without a ritual having run.
#   - [ ] Chase the feedback ask (as of 2026-08-10, review 7d)
ITEM_AS_OF = re.compile(
    r"^[ \t]*[-*][ \t]+(?:\[(?P<box>[ xX])\][ \t]+)?(?P<text>.*?)[ \t]*"
    r"\(as of[ \t]+(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:,[ \t]*review[ \t]+(?P<days>\d+)d)?\)[ \t]*$",
    re.MULTILINE,
)
ITEM_LINE = re.compile(
    r"^[ \t]*[-*][ \t]+(?:\[(?P<box>[ xX])\][ \t]+)?(?P<text>.+?)[ \t]*$",
    re.MULTILINE,
)
# Only lists that represent live obligations are held to stamping; narrative
# bullets are not, because demanding a date from prose trains bypass.
#
# "current" is deliberately absent. It reads as though it belongs, but "Current
# State" is the commonest section name in practice and it holds prose, which
# section-level '*State as of:*' markers already govern. Including it demanded a
# date from narrative and double-covered body currency: measured against the
# live corpus before adoption, that one word accounted for 140 of 294 flagged
# items across 18 projects.
OPEN_SECTION = re.compile(
    r"open|pending|next|action|todo|to do|blocked|waiting|in progress",
    re.IGNORECASE,
)
DEFAULT_REVIEW_DAYS = 14


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


def body_markers(text: str) -> list[dict]:
    """Every `*State as of: ...*` marker, attributed to its section heading."""
    headings = [(m.start(), m.group(1)) for m in SECTION_HEADING.finditer(text)]
    markers: list[dict] = []
    for match in STATE_AS_OF.finditer(text):
        section = "(top)"
        for start, title in headings:
            if start < match.start():
                section = title
            else:
                break
        markers.append({
            "section": section,
            "date": match.group(1),
            "ordinals": first_ordinals(match.group(2)),
        })
    return markers


def _section_of(headings: list[tuple[int, str]], position: int) -> str:
    section = "(top)"
    for start, title in headings:
        if start < position:
            section = title
        else:
            break
    return section


def item_markers(text: str) -> list[dict]:
    """Every stamped list item, attributed to its section heading."""
    headings = [(m.start(), m.group(1)) for m in SECTION_HEADING.finditer(text)]
    items: list[dict] = []
    for match in ITEM_AS_OF.finditer(text):
        days = match.group("days")
        items.append({
            "section": _section_of(headings, match.start()),
            "text": match.group("text").strip(),
            "date": match.group("date"),
            "review_days": int(days) if days is not None else None,
            "done": (match.group("box") or " ").strip().lower() == "x",
        })
    return items


def overdue_items(text: str, today: date | None = None) -> list[dict]:
    """Stamped, still-open items whose review horizon has passed.

    An unspecified horizon still ages: silence must not read as "never stale",
    which is the same reasoning that makes an undated record unverifiable
    rather than fresh.
    """
    moment = today or date.today()
    overdue = []
    for item in item_markers(text):
        if item["done"]:
            continue
        try:
            stamped = date.fromisoformat(item["date"])
        except ValueError:
            # A stamp shaped like a date that is not one is a malformed stamp,
            # not a fresh item; malformed_stamp_items() reports it.
            continue
        # An explicit 0-day horizon is a statement ("review daily"), not an
        # omission: `or` would silently replace it with the default and the
        # item could sit past its declared horizon without a finding.
        horizon = (
            item["review_days"]
            if item["review_days"] is not None
            else DEFAULT_REVIEW_DAYS
        )
        if (moment - stamped).days > horizon:
            item["age_days"] = (moment - stamped).days
            item["horizon_days"] = horizon
            overdue.append(item)
    return overdue


def malformed_stamp_items(text: str) -> list[dict]:
    """Open-section items whose currency stamp cannot be trusted.

    Two shapes, both previously invisible: a suffix that looks like a stamp
    but is not one ("(as of yesterday)") slipped through the unstamped
    exemption, and a stamp whose date string matches the pattern but is not a
    real date ("2026-02-30") was silently skipped. A malformed stamp must not
    read as a valid one — that is exactly how an unverifiable age passes as
    current.
    """
    headings = [(m.start(), m.group(1)) for m in SECTION_HEADING.finditer(text)]
    pattern_stamped: set[tuple[str, str]] = set()
    malformed: list[dict] = []
    for item in item_markers(text):
        # Every regex-matching stamp is owned by this loop: valid ones are
        # fine, impossible dates are malformed. Either way the suffix branch
        # below must not double-report the same line.
        pattern_stamped.add((item["section"], item["text"]))
        try:
            date.fromisoformat(item["date"])
        except ValueError:
            if not item["done"]:
                malformed.append(
                    {
                        "section": item["section"],
                        "text": item["text"],
                        "reason": f"stamp date {item['date']} is not a real date",
                    }
                )
    for match in ITEM_LINE.finditer(text):
        section = _section_of(headings, match.start())
        if not OPEN_SECTION.search(section):
            continue
        if (match.group("box") or " ").strip().lower() == "x":
            continue
        body = match.group("text").strip()
        if not (body.endswith(")") and "as of" in body):
            continue
        if any(
            body.startswith(stamped_text)
            for stamped_section, stamped_text in pattern_stamped
            if stamped_section == section
        ):
            continue
        malformed.append(
            {
                "section": section,
                "text": body,
                "reason": "the '(as of ...)' suffix does not parse as a stamp",
            }
        )
    return malformed


def unstamped_open_sections(text: str) -> list[str]:
    """Open-item sections holding live entries that carry no stamp at all."""
    headings = [(m.start(), m.group(1)) for m in SECTION_HEADING.finditer(text)]
    stamped = {
        (item["section"], item["text"]) for item in item_markers(text)
    }
    bare: dict[str, int] = {}
    for match in ITEM_LINE.finditer(text):
        section = _section_of(headings, match.start())
        if not OPEN_SECTION.search(section):
            continue
        box = (match.group("box") or " ").strip().lower()
        if box == "x":
            continue
        body = match.group("text").strip()
        if (section, body) in stamped or body.endswith(")") and "as of" in body:
            continue
        bare[section] = bare.get(section, 0) + 1
    return sorted(bare)


def open_obligation_count(text: str) -> int:
    """Unchecked items under an open-items heading, stamped or not.

    Deliberately not the same question as `overdue_items`. That one asks
    whether a live queue is current; this one asks whether a queue exists at
    all in a record that claims to be finished, so a well-stamped item counts
    exactly like a bare one.

    Only an EXPLICIT unchecked box counts. A checked box is a record of
    something done, which is what a finished project's list should hold. A
    bullet with no box at all is prose — the majority of bullets in these
    records are — and reading narrative as owed work is the miscalibration
    that cost 140 of 294 findings when `current` was briefly an open-section
    word. An unchecked box is unambiguous: someone wrote the box and did not
    tick it.
    """
    headings = [(m.start(), m.group(1)) for m in SECTION_HEADING.finditer(text)]
    owed = 0
    for match in ITEM_LINE.finditer(text):
        box = match.group("box")
        if box is None or box.strip().lower() == "x":
            continue
        if not OPEN_SECTION.search(_section_of(headings, match.start())):
            continue
        if match.group("text").strip():
            owed += 1
    return owed


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


def audit_project(project: Path, today: date | None = None) -> list[dict]:
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

    # Body currency — each as-of marker judged like a header field. Header
    # freshness is necessary, not sufficient: three real occurrences advanced
    # the header while the body kept routing agents to superseded work.
    markers = body_markers(text)
    for marker in markers:
        if marker["date"] < log_date:
            findings.append({
                "project": str(project), "kind": "body-marker-stale",
                "section": marker["section"],
                "detail": f"'{marker['section']}' is marked as of "
                          f"{marker['date']}; {log_file} records {log_date}",
                "marker_date": marker["date"], "log_date": log_date,
            })
            continue
        for family, number in sorted(marker["ordinals"].items()):
            current = log_current.get(family)
            if current is not None and number < current:
                findings.append({
                    "project": str(project), "kind": "body-marker-stale",
                    "section": marker["section"], "family": family,
                    "detail": f"'{marker['section']}' is marked as of "
                              f"{family} {number}; {log_file} records "
                              f"{family} {current}",
                    "marker_ordinal": number, "log_ordinal": current,
                })
    if not markers and (
        first_ordinals(" ".join(header_fields(text).values())) or log_current
    ):
        findings.append({
            "project": str(project), "kind": "body-marker-absent",
            "detail": "ordinal-paced record has no '*State as of: ...*' "
                      "markers — body currency is unverifiable; a current "
                      "header above unmarked operational sections cannot be "
                      "distinguished from a stale one",
        })

    # Item currency — the level below sections. An open-items entry carries an
    # implicit present tense that nothing re-dates, so a record whose header and
    # sections are all current can still route an agent off a weeks-old item.
    for item in overdue_items(text, today=today):
        findings.append({
            "project": str(project), "kind": "item-marker-stale",
            "section": item["section"],
            "detail": f"'{item['section']}' item \"{item['text']}\" is marked "
                      f"as of {item['date']}, {item['age_days']} days ago, past "
                      f"its {item['horizon_days']}-day review horizon",
            "marker_date": item["date"], "age_days": item["age_days"],
        })
    for section in unstamped_open_sections(text):
        findings.append({
            "project": str(project), "kind": "item-marker-absent",
            "section": section,
            "detail": f"'{section}' lists live items with no '(as of ...)' "
                      "stamps — their age is unverifiable, so an entry written "
                      "weeks ago is indistinguishable from one written today",
        })
    for item in malformed_stamp_items(text):
        findings.append({
            "project": str(project), "kind": "item-marker-malformed",
            "section": item["section"],
            "detail": f"'{item['section']}' item \"{item['text']}\" carries a "
                      f"stamp that cannot be trusted: {item['reason']}",
        })
    return findings


def currency_findings(project: Path) -> list[tuple[str, str]]:
    """(message, remedy) pairs for staleness findings only — the doctor's view.

    Coverage-limit kinds are excluded here: the doctor's structural checks
    already govern missing or unconventional records, and this function must
    add signal only where the evidence is comparable.
    """
    remedy = (
        "bring the stale field or section up to date with context_edit.py — "
        "rewrite the section prose, then advance its '*State as of:*' marker "
        "in the same edit"
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
        if (root / "CONTEXT.md").is_file():
            # A project directory was passed directly (the sibling doctor's
            # --project convention). Audit it rather than scanning its
            # children for records they cannot contain.
            scanned += 1
            findings.extend(audit_project(root))
            continue
        for project in sorted(p for p in root.iterdir() if p.is_dir()):
            if not (project / "CONTEXT.md").is_file():
                continue
            scanned += 1
            findings.extend(audit_project(project))

    if scanned == 0:
        # Fail closed: a scan of nothing is not a clean scan (2026-08-24
        # defect — pointed at a project's subdirectory, this printed
        # "0 findings" and exited 0). Zero results are never evidence of
        # absence.
        print(
            "no project records scanned: expected a projects container "
            "(directories each holding CONTEXT.md) or a single project "
            "directory holding CONTEXT.md at its root",
            file=sys.stderr,
        )
        return 2

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

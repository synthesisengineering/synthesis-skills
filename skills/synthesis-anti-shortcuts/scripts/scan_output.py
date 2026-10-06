#!/usr/bin/env python3
"""
scan_output.py — Lazy-shortcut antipattern scanner.

Detects costume-vocabulary phrases that signal the lazy-shortcut antipattern
in AI-assistant output. Reads text from stdin or a file argument, scans it
against the skill's catalog of phrases organized by category, and reports each
detection with a suggested rewrite framing.

The catalog is data, not code: ../costume-catalog.json is the one public
catalog. The v5 Stop hook (synthesis/reply_check.py) keeps a short built-in
subset for speed, and tests/test_shortcut_catalog.py fails the build if that
subset ever names a phrase this catalog lacks.

A phrase used in discussion is not a costume: matches inside double quotes,
curly quotes or backticks are exempt, as is any window an entry's own
`exempt_when` patterns match. A bare use is flagged.

Standard library only; runs on Python 3.9. `--catalog` also accepts a YAML
catalog in the same shape when PyYAML is installed.

Exit codes:
  0 — Clean (no detections)
  1 — One or more detections found
  2 — Error (e.g., unreadable input, malformed catalog)

Examples:

  echo "We can revisit this for now." | ./scan_output.py     # scan stdin
  ./scan_output.py draft.md                                   # scan a file
  ./scan_output.py --catalog my-catalog.json draft.md         # another catalog
  ./scan_output.py --json draft.md                            # machine-readable
  ./scan_output.py --quiet draft.md                           # exit code only
  ./scan_output.py --context 120 draft.md                     # wider context

License: Apache-2.0
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

CATALOG = Path(__file__).resolve().parents[1] / "costume-catalog.json"
MATCH_KINDS = ("literal", "regex", "phrase_with_context")

# Discussion spans: a phrase quoted or in code is being talked about, not used.
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
QUOTED = re.compile(r"\"[^\"\n]{1,400}\"|“[^”\n]{1,400}”|‘[^’\n]{1,400}’")


@dataclass
class Detection:
    """One match against the catalog."""

    phrase_id: str
    category: str
    matched_text: str
    start: int
    end: int
    line: int
    column: int
    context: str
    rationale: str
    replacement: str
    case_ref: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CatalogEntry:
    """One phrase entry in the catalog."""

    id: str
    phrase: str
    match: str  # "literal" | "regex" | "phrase_with_context"
    category: str
    rationale: str = ""
    replacement: str = ""
    case_ref: str = ""
    exempt_when: list = field(default_factory=list)


# -----------------------------------------------------------------------------
# Catalog loading
# -----------------------------------------------------------------------------


def _read_document(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to load a YAML catalog. Install it, or use a "
                "JSON catalog (the shipped costume-catalog.json needs nothing)."
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("phrases"), list):
        raise ValueError(f"catalog at {path} does not contain a 'phrases' list")
    return data


def load_catalog(path: Path = CATALOG) -> tuple:
    """Return (categories, entries). Refuses duplicate ids, unknown match kinds
    and patterns that do not compile, so a broken catalog fails loudly."""
    data = _read_document(path)
    categories = data.get("categories") or {}
    entries, seen = [], set()
    for spec in data["phrases"]:
        if not isinstance(spec, dict) or not spec.get("phrase"):
            raise ValueError(f"catalog entry without a phrase: {spec!r}")
        entry = CatalogEntry(
            id=str(spec.get("id", "")),
            phrase=str(spec["phrase"]),
            match=str(spec.get("match", "literal")),
            category=str(spec.get("category", "uncategorized")),
            rationale=str(spec.get("rationale", "")).strip(),
            replacement=str(spec.get("replacement", "")),
            case_ref=str(spec.get("case_ref") or spec.get("skill_ref") or spec.get("lesson") or ""),
            exempt_when=list(spec.get("exempt_when") or []),
        )
        if entry.match not in MATCH_KINDS:
            raise ValueError(f"{entry.id}: unknown match kind {entry.match!r}")
        if entry.id in seen:
            raise ValueError(f"duplicate catalog id {entry.id!r}")
        seen.add(entry.id)
        try:
            compile_pattern(entry)
        except re.error as exc:
            raise ValueError(f"{entry.id}: pattern does not compile: {exc}") from exc
        entries.append(entry)
    return categories, entries


# -----------------------------------------------------------------------------
# Matching
# -----------------------------------------------------------------------------


def compile_pattern(entry: CatalogEntry) -> re.Pattern:
    """literal and phrase_with_context match the phrase case-insensitively;
    regex compiles the phrase case-insensitively."""
    if entry.match == "regex":
        return re.compile(entry.phrase, re.IGNORECASE)
    return re.compile(re.escape(entry.phrase), re.IGNORECASE)


def is_exempt(window: str, exemptions: Iterable[str]) -> bool:
    """True if any exemption regex matches the surrounding window."""
    for pat in exemptions:
        if not pat:
            continue
        try:
            if re.search(pat, window, re.IGNORECASE):
                return True
        except re.error:
            # A malformed exemption is treated as a literal substring.
            if pat.lower() in window.lower():
                return True
    return False


def discussion_spans(text: str) -> list:
    """Character ranges of code and quoted text, where a phrase is discussed."""
    spans = [m.span() for m in CODE.finditer(text)]
    spans += [m.span() for m in QUOTED.finditer(text)]
    return spans


def _inside(start: int, end: int, spans: list) -> bool:
    return any(a <= start and end <= b for a, b in spans)


def line_column_for(text: str, offset: int) -> tuple:
    """Translate a 0-based offset into 1-based (line, column)."""
    if offset <= 0:
        return 1, 1
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    last_newline = prefix.rfind("\n")
    column = offset - last_newline if last_newline >= 0 else offset + 1
    return line, column


def scan(text: str, catalog: list, context_chars: int = 80) -> list:
    """Scan text against the catalog and return Detection objects in text order."""
    spans = discussion_spans(text)
    detections = []
    for entry in catalog:
        for match in compile_pattern(entry).finditer(text):
            start, end = match.span()
            if _inside(start, end, spans):
                continue
            window = text[max(0, start - context_chars):min(len(text), end + context_chars)]
            if is_exempt(window, entry.exempt_when):
                continue
            line, column = line_column_for(text, start)
            detections.append(Detection(
                phrase_id=entry.id, category=entry.category, matched_text=text[start:end],
                start=start, end=end, line=line, column=column,
                context=window.replace("\n", " "), rationale=entry.rationale,
                replacement=entry.replacement, case_ref=entry.case_ref))
    detections.sort(key=lambda d: (d.start, d.phrase_id))
    return detections


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------


def format_text_report(detections: list, source_label: str, categories: Optional[dict] = None) -> str:
    """Human-readable report, grouped by category."""
    if not detections:
        return f"OK  {source_label}: no costume-vocabulary detections."
    categories = categories or {}
    by_category: dict = {}
    for det in detections:
        by_category.setdefault(det.category, []).append(det)
    count = len(by_category)
    lines = [f"FOUND  {source_label}: {len(detections)} detection(s) across "
             f"{count} categor{'y' if count == 1 else 'ies'}.", ""]
    for category in sorted(by_category):
        lines.append(f"== {category} ==")
        if categories.get(category):
            lines.append(f"   {categories[category]}")
        lines.append("")
        for det in by_category[category]:
            lines.append(f"  L{det.line}:C{det.column}  [{det.phrase_id}]  matched: {det.matched_text!r}")
            if det.rationale:
                lines.append(f"      why:     {det.rationale}")
            if det.replacement:
                lines.append(f"      rewrite: {det.replacement}")
            if det.case_ref:
                lines.append(f"      see:     {det.case_ref}")
            lines.append(f"      context: ...{det.context}...")
            lines.append("")
    return "\n".join(lines).rstrip()


def format_json_report(detections: list, source_label: str) -> str:
    return json.dumps({"source": source_label, "detection_count": len(detections),
                       "detections": [d.to_dict() for d in detections]}, indent=2)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scan_output.py",
        description=("Scan AI-assistant draft output for costume-vocabulary phrases "
                     "that signal the lazy-shortcut antipattern."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Catalog: the skill's costume-catalog.json unless --catalog names another\n"
                "(JSON, or YAML with PyYAML installed).\n\n"
                "Exit codes:\n  0 — Clean (no detections)\n  1 — One or more detections found\n"
                "  2 — Error\n"))
    parser.add_argument("input", nargs="?", default=None,
                        help="File to scan. Omit or pass '-' to read from stdin.")
    parser.add_argument("--catalog", type=Path, default=CATALOG,
                        help="Catalog file (default: the skill's costume-catalog.json).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report.")
    parser.add_argument("--quiet", action="store_true", help="No stdout; exit code only.")
    parser.add_argument("--context", type=int, default=80,
                        help="Characters of surrounding context to capture (default: 80).")
    parser.add_argument("--category", action="append",
                        help="Limit the scan to one or more categories (repeatable).")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        categories, catalog = load_catalog(args.catalog)
    except (ImportError, ValueError, OSError) as exc:
        print(f"error loading catalog: {exc}", file=sys.stderr)
        return 2
    if args.category:
        wanted = set(args.category)
        catalog = [e for e in catalog if e.category in wanted]
    input_path = Path(args.input) if args.input and args.input != "-" else None
    try:
        text = input_path.read_text(encoding="utf-8") if input_path else sys.stdin.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error reading input: {exc}", file=sys.stderr)
        return 2
    source_label = str(input_path) if input_path else "<stdin>"
    detections = scan(text, catalog, context_chars=max(0, args.context))
    if not args.quiet:
        print(format_json_report(detections, source_label) if args.json
              else format_text_report(detections, source_label, categories))
    return 1 if detections else 0


if __name__ == "__main__":
    sys.exit(main())

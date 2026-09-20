#!/usr/bin/env python3
"""prep_lint.py — mechanical backstop for the meeting-prep content contract.

Checks the checkable half of references/requirements.md against a draft
prep pack: footer placement (R1), register leaks for non-technical
readers (R2), empty-sentence patterns (R7b), name-drop openers (R7c),
invented precision (R7), and the basis statement (R10).

Usage:
    prep_lint.py [--reader technical|nontechnical] [--room SIZE] PACK.md
    prep_lint.py --test-self   # no-op smoke hook for the release gate

Exit 0 when clean, 1 with one `LINE: CODE: message` finding per line
otherwise. The linter is a backstop, not the author: a finding the
author judges wrong is recorded, not obeyed.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ENGINE_VERSION = "1.0.0"

AVOID_RE = re.compile(
    r"\b(don't|do not|never|avoid|shouldn't|should not)\s+"
    r"(raise|bring up|mention|discuss|volunteer|name)\b",
    re.IGNORECASE,
)
FOOTER_HEAD_RE = re.compile(
    r"^(don't raise|do not raise|not raising|footer)\b",
    re.IGNORECASE,
)
FOOTER_LINE_RE = re.compile(
    r"^(\*\*)?(don't raise|do not raise|not raising)\b",
    re.IGNORECASE,
)
TICKET_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b")
INFRA_TERMS = (
    "bundle size",
    "p99",
    "kubernetes",
    "k8s",
    "ssl outage",
    "tls handshake",
    "dns propagation",
    "cache invalidation",
    "database migration",
    "connection pool",
)
ANNOUNCING_RES = (
    re.compile(r"\bone thing that'?s\b", re.IGNORECASE),
    re.compile(r"\bit'?s worth noting that\b", re.IGNORECASE),
    re.compile(r"\bwhat follows is\b", re.IGNORECASE),
)
SELF_RESTATE_RES = (
    re.compile(r",\s*not\s+\w+", re.IGNORECASE),
    re.compile(r"\brather than\b.*\b(instead|merely|just)\b", re.IGNORECASE),
)
FLOURISH_RES = (
    re.compile(r"\bthat'?s (part of )?why i think this is doable\b", re.IGNORECASE),
    re.compile(r"\bit costs nothing and\b", re.IGNORECASE),
)
NAMEDROP_RE = re.compile(
    r"^[A-Z][a-zA-Z'.-]+ and I (were talking|spoke|discussed|talked)\b"
)
INVENTED_PRECISION_RES = (
    re.compile(r"\bwildly\b", re.IGNORECASE),
    re.compile(r"\bmassively\b", re.IGNORECASE),
    re.compile(r"\bevery single\b", re.IGNORECASE),
    re.compile(r"\borderline (miraculous|impossible|perfect)\b", re.IGNORECASE),
)
BASIS_RE = re.compile(r"^basis\s*:", re.IGNORECASE | re.MULTILINE)
NONTECHNICAL_RE = re.compile(
    r"non-?technical|not a technologist|business (reader|outcomes)",
    re.IGNORECASE,
)


@dataclass
class Finding:
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.line}: {self.code}: {self.message}"


def split_sections(lines: list[str]) -> list[tuple[int, str, list[str]]]:
    """Split markdown into (start_line, heading, body) sections."""
    sections: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for number, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if match:
            if current is not None:
                sections.append(current)
            current = (number, match.group(2).strip(), [])
        elif current is not None:
            current[2].append(line)
    if current is not None:
        sections.append(current)
    return sections


def check_footer(text: str, sections: list[tuple[int, str, list[str]]]) -> list[Finding]:
    del text
    findings: list[Finding] = []
    if not sections:
        return findings
    footer_index = next(
        (i for i, (_, head, _) in enumerate(sections) if FOOTER_HEAD_RE.search(head)),
        None,
    )
    if footer_index is None and sections:
        # A trailing bold "Don't raise ..." line counts as the footer.
        last_body = sections[-1][2]
        if any(FOOTER_LINE_RE.search(line.strip()) for line in last_body):
            footer_index = len(sections) - 1
    if footer_index is None:
        # A footer is required only when the draft contains avoid-language.
        if AVOID_RE.search("\n".join(l for _, _, b in sections for l in b)):
            findings.append(Finding(1, "R1", "avoid-language present but no don't-raise footer section"))
        return findings
    if footer_index != len(sections) - 1:
        start, head, _ = sections[footer_index]
        findings.append(Finding(start, "R1", f"don't-raise footer '{head}' is not the last section"))
    for i, (start, head, body) in enumerate(sections):
        if i == footer_index:
            continue
        for offset, line in enumerate(body):
            if AVOID_RE.search(line):
                findings.append(
                    Finding(start + offset + 1, "R1", f"avoid-language in body section '{head}'; move to the footer")
                )
    return findings


def check_register(
    lines: list[str], reader: str, auto_nontechnical: bool
) -> list[Finding]:
    nontechnical = reader == "nontechnical" or (reader == "auto" and auto_nontechnical)
    if not nontechnical:
        return []
    findings: list[Finding] = []
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            continue
        ticket = TICKET_RE.search(line)
        if ticket:
            findings.append(Finding(number, "R2", f"ticket number '{ticket.group(0)}' for a non-technical reader"))
        lowered = line.lower()
        for term in INFRA_TERMS:
            if term in lowered:
                findings.append(Finding(number, "R2", f"infrastructure term '{term}' for a non-technical reader"))
    return findings


def check_sentences(lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern in ANNOUNCING_RES:
            if pattern.search(stripped):
                findings.append(Finding(number, "R7b", f"announcing opener: '{pattern.pattern}'"))
        for pattern in SELF_RESTATE_RES:
            if pattern.search(stripped):
                findings.append(Finding(number, "R7b", "self-restating X-not-Y shape"))
                break
        for pattern in FLOURISH_RES:
            if pattern.search(stripped):
                findings.append(Finding(number, "R7b", "trailing flourish adds no content"))
    return findings


def check_namedrop(lines: list[str], room: str) -> list[Finding]:
    if room not in {"forum", "external"}:
        return []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("Basis:"):
            continue
        stripped = re.sub(r"^([-*]|\d+\.)\s+", "", stripped).lstrip(">").strip()
        if not stripped or stripped.startswith("*"):
            continue
        if NAMEDROP_RE.search(stripped):
            return [Finding(number, "R7c", "name-drop opener in a large room")]
        return []
    return []


def check_precision(lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(lines, start=1):
        for pattern in INVENTED_PRECISION_RES:
            match = pattern.search(line)
            if match:
                findings.append(Finding(number, "R7", f"invented precision: '{match.group(0)}'"))
    return findings


def check_basis(text: str) -> list[Finding]:
    if BASIS_RE.search(text):
        return []
    return [Finding(1, "R10", "missing basis statement (sources read + newest source date)")]


def lint(text: str, reader: str = "auto", room: str = "1:1") -> list[Finding]:
    lines = text.splitlines()
    sections = split_sections(lines)
    findings: list[Finding] = []
    findings.extend(check_footer(text, sections))
    findings.extend(check_register(lines, reader, bool(NONTECHNICAL_RE.search(text))))
    findings.extend(check_sentences(lines))
    findings.extend(check_namedrop(lines, room))
    findings.extend(check_precision(lines))
    findings.extend(check_basis(text))
    return sorted(findings, key=lambda f: (f.line, f.code))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint a meeting-prep pack against R1–R12.")
    parser.add_argument("pack", nargs="?", help="prep pack markdown file")
    parser.add_argument("--reader", default="auto", choices=("auto", "technical", "nontechnical"))
    parser.add_argument("--room", default="1:1", choices=("1:1", "small", "forum", "external", "interview", "standup"))
    parser.add_argument("--test-self", action="store_true", help="smoke hook; always exits 0")
    args = parser.parse_args(argv)
    if args.test_self:
        print(f"prep_lint engine {ENGINE_VERSION} ok")
        return 0
    if not args.pack:
        parser.error("PACK.md is required")
    text = Path(args.pack).read_text(encoding="utf-8")
    findings = lint(text, reader=args.reader, room=args.room)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

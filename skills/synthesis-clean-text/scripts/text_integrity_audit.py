#!/usr/bin/env python3
"""Inspect Unicode and normalization properties without mutating text."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


BIDI_CONTROLS = {
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d",
    "\u202e", "\u2066", "\u2067", "\u2068", "\u2069",
}
ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def is_variation_selector(character: str) -> bool:
    codepoint = ord(character)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


def is_noncharacter(character: str) -> bool:
    codepoint = ord(character)
    return 0xFDD0 <= codepoint <= 0xFDEF or codepoint & 0xFFFF in {0xFFFE, 0xFFFF}


def analyze_text(text: str, raw: bytes) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for index, character in enumerate(text):
        category = unicodedata.category(character)
        reason: str | None = None
        if character in BIDI_CONTROLS:
            reason = "bidi-control"
        elif is_variation_selector(character):
            reason = "variation-selector"
        elif is_noncharacter(character):
            reason = "unicode-noncharacter"
        elif category == "Cf":
            reason = "format-control"
        elif category == "Zs" and character != " ":
            reason = "non-ascii-space"
        elif category == "Cc" and character not in ALLOWED_CONTROLS:
            reason = "control-character"
        elif category in {"Cs", "Co", "Cn"}:
            reason = {"Cs": "surrogate", "Co": "private-use", "Cn": "unassigned"}[category]
        if reason:
            line = text.count("\n", 0, index) + 1
            prior_newline = text.rfind("\n", 0, index)
            column = index + 1 if prior_newline < 0 else index - prior_newline
            findings.append({
                "index": index,
                "line": line,
                "column": column,
                "codepoint": f"U+{ord(character):04X}",
                "name": unicodedata.name(character, "UNNAMED"),
                "category": category,
                "reason": reason,
            })
    normalization = {
        form: {
            "already_normalized": unicodedata.normalize(form, text) == text,
            "normalized_sha256": hashlib.sha256(unicodedata.normalize(form, text).encode("utf-8")).hexdigest(),
        }
        for form in ("NFC", "NFD", "NFKC", "NFKD")
    }
    line_endings = {
        "crlf": raw.count(b"\r\n"),
        "bare_lf": raw.count(b"\n") - raw.count(b"\r\n"),
        "bare_cr": raw.count(b"\r") - raw.count(b"\r\n"),
    }
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "characters": len(text),
        "utf8_bom": raw.startswith(b"\xef\xbb\xbf"),
        "trailing_newline": text.endswith(("\n", "\r")),
        "line_endings": line_endings,
        "normalization": normalization,
        "finding_counts": dict(sorted(Counter(item["reason"] for item in findings).items())),
        "findings": findings,
        "interpretation": (
            "This report describes Unicode and normalization properties. "
            "It does not detect or disprove statistical text watermarks or authorship."
        ),
    }


def read_input(path: str) -> tuple[str, bytes, dict[str, Any] | None]:
    state: dict[str, Any] | None = None
    if path == "-":
        raw = sys.stdin.buffer.read()
    else:
        source = Path(path)
        before = source.stat()
        first_read = source.read_bytes()
        first_hash = hashlib.sha256(first_read).hexdigest()
        second_read = source.read_bytes()
        second_hash = hashlib.sha256(second_read).hexdigest()
        after = source.stat()
        if first_hash != second_hash:
            raise ValueError(
                "input changed between two complete reads: "
                f"first SHA-256 {first_hash}, second SHA-256 {second_hash}"
            )
        raw = second_read
        metadata_unchanged = (
            before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
        )
        state = {
            "size_before": before.st_size,
            "size_after": after.st_size,
            "mtime_ns_before": before.st_mtime_ns,
            "mtime_ns_after": after.st_mtime_ns,
            "sha256_first_read": first_hash,
            "sha256_second_read": second_hash,
            "full_read_hashes_match": True,
            "metadata_unchanged": metadata_unchanged,
            "unchanged_during_audit": metadata_unchanged and first_hash == second_hash,
        }
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input is not valid UTF-8: {exc}") from exc
    return text, raw, state


def human_report(path: str, report: dict[str, Any]) -> str:
    lines = [
        f"Text integrity audit: {path}",
        f"SHA-256: {report['sha256']}",
        f"Bytes: {report['bytes']}; characters: {report['characters']}",
        f"UTF-8 BOM: {'yes' if report['utf8_bom'] else 'no'}",
        f"Trailing newline: {'yes' if report['trailing_newline'] else 'no'}",
        "Line endings: " + ", ".join(f"{key}={value}" for key, value in report["line_endings"].items()),
        "Normalization: " + ", ".join(
            f"{form}={'same' if result['already_normalized'] else 'differs'}"
            for form, result in report["normalization"].items()
        ),
        f"Findings: {len(report['findings'])}",
    ]
    for finding in report["findings"]:
        lines.append(
            f"  line {finding['line']}, column {finding['column']}: "
            f"{finding['codepoint']} {finding['name']} ({finding['reason']})"
        )
    lines.append(report["interpretation"])
    if report.get("file_state") is not None:
        lines.append(
            "Full-read SHA-256 assertion: "
            f"{report['file_state']['sha256_first_read']} == "
            f"{report['file_state']['sha256_second_read']} (pass)"
        )
        lines.append(
            "File state unchanged during audit: "
            + ("yes" if report["file_state"]["unchanged_during_audit"] else "no")
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="UTF-8 file, or - for stdin")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument("--fail-on-findings", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text, raw, file_state = read_input(args.path)
    except (OSError, ValueError) as exc:
        print(f"text integrity audit error: {exc}", file=sys.stderr)
        return 2
    report = analyze_text(text, raw)
    report["file_state"] = file_state
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(human_report(args.path, report))
    return 1 if args.fail_on_findings and report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""synthesis-knowledge-capture — pre-merge reconnaissance for an OKF knowledge base.

v1.0.0 (2026-07-29)

Read-only. Answers the one question you must answer before merging a fact into a
knowledge base: "where does this entity ALREADY live?" Without that, an in-place
merge is impossible and you will either duplicate or destroy.

Modes:
  --entity NAME [--alias A ...]  every file+line that mentions the entity
  --list                          inventory every concept with its OKF type/title
  --stale YYYY-MM-DD              concepts whose frontmatter timestamp is older
                                  than the date (or missing a timestamp)

Design:
  * Stdlib only. Identical behavior under any python3.
  * Read-only. Never writes; exit code is 0 unless the invocation itself is bad.
  * Excludes OKF-reserved index.md / log.md and README.md from concept scans.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

RESERVED = {"index.md", "log.md", "readme.md"}


def is_concept(path: str) -> bool:
    base = os.path.basename(path).lower()
    return path.endswith(".md") and base not in RESERVED


def iter_concepts(bundle: str):
    for root, _dirs, files in os.walk(bundle):
        for name in sorted(files):
            full = os.path.join(root, name)
            if is_concept(full):
                yield full


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:  # pragma: no cover - surfaced to the user
        print(f"! could not read {path}: {exc}", file=sys.stderr)
        return ""


def parse_frontmatter(text: str) -> dict:
    """Minimal, dependency-free scalar frontmatter parse.

    Extracts only the scalar keys this tool needs (type, title, timestamp).
    List/nested values (e.g. tags) are ignored by design — no YAML dependency,
    so behavior never changes with the environment.
    """
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1).lower(), m.group(2).strip()
        if raw.startswith("[") or raw == "" or raw.startswith("{"):
            continue  # list/empty/map — not a scalar this tool tracks
        fm[key] = raw.strip().strip('"').strip("'")
    return fm


def scan_entity(bundle: str, terms: list[str]) -> int:
    lowered = [t.lower() for t in terms if t]
    total_hits = 0
    files_hit = 0
    for path in iter_concepts(bundle):
        text = read_text(path)
        if not text:
            continue
        matches = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            low = line.lower()
            if any(term in low for term in lowered):
                matches.append((lineno, line.strip()))
        if matches:
            files_hit += 1
            total_hits += len(matches)
            rel = os.path.relpath(path, bundle)
            print(rel)
            for lineno, line in matches:
                snippet = line if len(line) <= 160 else line[:157] + "..."
                print(f"  {lineno}: {snippet}")
            print()
    label = " / ".join(terms)
    print(f"— {total_hits} mention(s) of [{label}] across {files_hit} file(s).")
    if files_hit == 0:
        print("  (no existing mention — this is a NEW entity; add it to the "
              "concept that holds this class of fact.)")
    return 0


def list_concepts(bundle: str) -> int:
    rows = []
    for path in iter_concepts(bundle):
        fm = parse_frontmatter(read_text(path))
        rows.append((os.path.relpath(path, bundle),
                     fm.get("type", "—"),
                     fm.get("title", "")))
    width = max((len(r[0]) for r in rows), default=0)
    for rel, typ, title in rows:
        print(f"{rel.ljust(width)}  [type: {typ}]  {title}".rstrip())
    print(f"— {len(rows)} concept(s).")
    return 0


def list_stale(bundle: str, cutoff: str) -> int:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", cutoff):
        print(f"! --stale expects YYYY-MM-DD, got {cutoff!r}", file=sys.stderr)
        return 2
    stale = []
    for path in iter_concepts(bundle):
        fm = parse_frontmatter(read_text(path))
        ts = fm.get("timestamp", "")
        # ISO dates sort lexicographically; missing timestamp counts as stale.
        if not ts or ts < cutoff:
            stale.append((os.path.relpath(path, bundle), ts or "(none)"))
    for rel, ts in stale:
        print(f"{ts}  {rel}")
    print(f"— {len(stale)} concept(s) at or before {cutoff} (or undated).")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="kb_scan.py",
        description="Read-only reconnaissance over an OKF knowledge bundle.")
    ap.add_argument("bundle", help="path to the OKF bundle (a source/ dir or repo)")
    ap.add_argument("--entity", help="entity name to find every mention of")
    ap.add_argument("--alias", action="append", default=[],
                    help="additional term for the same entity (repeatable)")
    ap.add_argument("--list", action="store_true",
                    help="inventory every concept with its OKF type and title")
    ap.add_argument("--stale", metavar="YYYY-MM-DD",
                    help="list concepts dated at/before this, or undated")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.bundle):
        print(f"! not a directory: {args.bundle}", file=sys.stderr)
        return 2

    if args.entity:
        return scan_entity(args.bundle, [args.entity, *args.alias])
    if args.list:
        return list_concepts(args.bundle)
    if args.stale:
        return list_stale(args.bundle, args.stale)

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

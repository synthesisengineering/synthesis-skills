#!/usr/bin/env python3
"""Read declared dated plans and report due obligations without making decisions.

No lookback cutoff, state writes, network access or inferred title-based identity.
Exit 2 means incomplete/ambiguous evidence; exit 0 means collection succeeded.
The REVIEW result still requires a grounded human decision for each due item.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
import os
from pathlib import Path
import re

DATE = r"\d{4}-\d{2}-\d{2}"
PLAN = re.compile(rf"^({DATE})\.md$")
ARTIFACT = re.compile(rf"^({DATE})-(day-start|midday|day-end)\.md$")
FIELD = re.compile(r"\*\*(Decays|Decay ID|Sent|Released|Resolved):\*\*\s*(.*)", re.I)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+)")
LIST = re.compile(r"^(\s*)(?:[-*+] |\d+[.)] )(.*)")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
RUN_ORDER = {"day-start": 0, "midday": 1, "day-end": 2}


def iso_day(value: str) -> date:
    if not re.fullmatch(DATE, value):
        raise ValueError("expected YYYY-MM-DD")
    return date.fromisoformat(value)


def gap(report: dict, path, reason: str, line: int | None = None) -> None:
    entry = {"path": str(path), "reason": reason}
    if line is not None:
        entry["line"] = line
    report["gaps"].append(entry)


def operative_lines(text: str, errors: list[str]):
    """Keep source line numbers; omit fenced examples, quotes and frontmatter."""
    fence = None
    frontmatter = text.splitlines()[:1] == ["---"]
    for number, line in enumerate(text.splitlines(), 1):
        if frontmatter:
            if number > 1 and line.strip() == "---":
                frontmatter = False
            continue
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        if line.lstrip().startswith(">"):
            continue
        # Inline grammar examples are prose, not executable plan metadata.
        yield number, re.sub(r"(`+)(.+?)\1", "", line)
    if fence or frontmatter:
        errors.append("unterminated fence or frontmatter; operative item coverage is incomplete")


def item_blocks(text: str, errors: list[str]):
    block = []
    list_indent = None
    for number, line in operative_lines(text, errors):
        heading = HEADING.match(line)
        listed = LIST.match(line)
        metadata = FIELD.match(line.strip().removeprefix("- "))
        boundary = heading or (listed and not metadata and (list_indent is None or len(listed[1]) <= list_indent))
        if boundary and block:
            yield block
            block = []
        if heading:
            list_indent = None
        elif boundary and listed:
            list_indent = len(listed[1])
        block.append((number, line))
    if block:
        yield block


def parse_plan(path: Path, day: date, rank: int, as_of: date, report: dict) -> list[dict]:
    try:
        before = path.stat()
        text = path.read_text(encoding="utf-8")
        after = path.stat()
    except (OSError, UnicodeError) as exc:
        gap(report, path, f"unreadable source: {exc}")
        return []
    report["scanned"].append(str(path))
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        gap(report, path, "source changed during read; rerun collection")
    entries = []
    errors = []
    for block in item_blocks(text, errors):
        prior_gaps = len(report["gaps"])
        fields = defaultdict(list)
        for number, line in block:
            match = FIELD.search(line)
            if match:
                fields[match[1].lower()].append((number, match[2].strip()))
        if not fields.get("decays") and not fields.get("decay id"):
            continue
        first_number, first_line = next(((n, l) for n, l in block if l.strip()), block[0])
        title = re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", first_line).strip()
        explicit_id = None
        if fields.get("decay id"):
            values = fields["decay id"]
            if len(values) != 1 or not ID.fullmatch(values[0][1]):
                gap(report, path, "invalid or multiple Decay ID fields", values[0][0])
            else:
                explicit_id = values[0][1]
        due = None
        reason = ""
        struck_release = False
        source_line = fields["decays"][0][0] if fields["decays"] else first_number
        if len(fields["decays"]) > 1:
            gap(report, path, "multiple Decays fields in one item; separate the items", source_line)
        for number, value in fields["decays"]:
            struck = re.match(rf"^~~({DATE})~~(?:\s+(.*))?$", value)
            if struck:
                value = struck[1] + " " + (struck[2] or "")
                if (struck[2] or "").strip(" ()"):
                    struck_release = True
                else:
                    gap(report, path, "struck deadline requires a release reason", number)
            parts = value.split(maxsplit=1)
            try:
                parsed = iso_day(parts[0] if parts else "")
            except ValueError:
                gap(report, path, "invalid Decays date", number)
                continue
            # Ambiguous multiple tags must never drop their earliest due date.
            if due is None or parsed < due:
                due = parsed
                reason = parts[1] if len(parts) > 1 else ""
        closed = struck_release or bool(re.match(r"(?:\[[xX]\]\s|~~.+~~|✅|(?:DONE|SENT)\b)", title))
        for name in ("sent", "released", "resolved"):
            for number, value in fields[name]:
                try:
                    token = value.removeprefix("✅").strip().split()[0]
                    closed_day = iso_day(token[:10])
                    if len(token) > 10:
                        from datetime import datetime
                        datetime.fromisoformat(token.replace("Z", "+00:00"))
                    if closed_day > as_of:
                        raise ValueError("future resolution")
                except (ValueError, IndexError):
                    gap(report, path, f"invalid or future {name} timestamp", number)
                else:
                    closed = True
        if due is None and not closed:
            gap(report, path, "identified item has no valid Decays date or resolution", source_line)
        entries.append({
            "identity": f"id:{explicit_id}" if explicit_id else f"source:{path}:{source_line}",
            "title": title, "due_date": due.isoformat() if due else None,
            "reason": reason, "closed": closed, "path": str(path), "line": source_line,
            "plan_date": day.isoformat(), "run_rank": rank, "invalid": len(report["gaps"]) > prior_gaps,
        })
    for error in errors:
        gap(report, path, error)
    return entries


def collect(roots: list[tuple[Path, str]], as_of: date) -> dict:
    report = {"schema_version": 1, "as_of": as_of.isoformat(), "status": "BLOCKED",
              "scope": "all available dated Markdown within explicitly declared roots; no lookback cutoff",
              "declared_roots": [{"path": str(p), "kind": k} for p, k in roots],
              "scanned": [], "excluded": [], "future_files": [], "gaps": [], "due": []}
    entries = []
    seen = set()
    if not roots:
        gap(report, "", "no plan or artifact roots declared")
    for raw_root, kind in roots:
        root = raw_root.expanduser().absolute()
        if any(part.is_symlink() for part in (root, *root.parents)):
            gap(report, root, "symlink root or ancestor refused; declare its intended physical directory")
            continue
        if not root.is_dir():
            gap(report, root, "declared directory missing or not a directory")
            continue
        pattern = PLAN if kind == "plans" else ARTIFACT
        selected = 0
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=lambda exc: gap(report, exc.filename or root, f"directory unreadable: {exc}")):
            dirs.sort()
            for name in list(dirs):
                child = Path(directory) / name
                if child.is_symlink():
                    gap(report, child, "symlink directory not scanned")
                    dirs.remove(name)
            for name in sorted(files):
                path = Path(directory) / name
                if path.is_symlink():
                    gap(report, path, "symlink file not scanned")
                    continue
                match = pattern.fullmatch(name)
                if not match:
                    report["excluded"].append(str(path))
                    continue
                selected += 1
                try:
                    day = iso_day(match[1])
                except ValueError:
                    gap(report, path, "invalid date in source filename")
                    continue
                if day > as_of:
                    report["future_files"].append(str(path))
                    continue
                if path in seen:
                    continue
                seen.add(path)
                rank = RUN_ORDER[match[2]] if kind == "artifacts" else 2
                entries.extend(parse_plan(path, day, rank, as_of, report))
        if selected == 0:
            gap(report, root, "no dated source files; coverage is not established")
    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry["identity"]].append(entry)
    for identity, history in grouped.items():
        history.sort(key=lambda r: (r["plan_date"], r["run_rank"], r["path"], r["line"]))
        # Resolve each file's last occurrence first, without ordering peer files by name.
        latest = history[-1]
        slot = (latest["plan_date"], latest["run_rank"])
        peers = {}
        for entry in history:
            if (entry["plan_date"], entry["run_rank"]) == slot:
                peers[entry["path"]] = entry
        states = {(e["due_date"], e["closed"], e["reason"]) for e in peers.values()}
        ambiguous = len(states) > 1
        if ambiguous:
            gap(report, latest["path"], f"conflicting same-day states for {identity}", latest["line"])
        earlier_dates = {e["due_date"] for e in history[:-1] if e["due_date"]}
        bad_redate = bool(latest["due_date"] and earlier_dates - {latest["due_date"]} and not latest["closed"] and not latest["reason"].strip(" ()"))
        if bad_redate:
            gap(report, latest["path"], "changed Decays date requires a stated reason", latest["line"])
        choices = history if ambiguous or bad_redate or latest["invalid"] else [latest]
        due_choices = [e for e in choices if e["due_date"] and e["due_date"] <= as_of.isoformat() and not e["closed"]]
        if due_choices:
            chosen = min(due_choices, key=lambda e: e["due_date"])
            result = {k: v for k, v in chosen.items() if k not in ("closed", "run_rank", "invalid")}
            result["sources"] = [{"path": e["path"], "line": e["line"]} for e in history]
            report["due"].append(result)
    report["due"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["status"] = "BLOCKED" if report["gaps"] else "REVIEW" if report["due"] else "CLEAR"
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    parser.add_argument("--plans-dir", action="append", default=[], type=Path)
    parser.add_argument("--artifacts-dir", action="append", default=[], type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    roots = [(p, "plans") for p in args.plans_dir] + [(p, "artifacts") for p in args.artifacts_dir]
    try:
        as_of = iso_day(args.as_of)
    except ValueError as exc:
        report = {"status": "BLOCKED", "due": [], "gaps": [{"path": "--as-of", "reason": str(exc)}]}
    else:
        report = collect(roots, as_of)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Deadline sweep: {report['status']} — {len(report['due'])} due; {len(report['gaps'])} gaps")
        for row in report["due"]:
            print(f"{row['due_date']} {row['title']} ({row['path']}:{row['line']})")
        for row in report["gaps"]:
            print(f"NOT COVERED: {row['path']}: {row['reason']}")
    return 2 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

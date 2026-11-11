#!/usr/bin/env python3
"""Read declared dated plans and report due obligations without making decisions.

No lookback cutoff, state writes, network access or inferred title-based identity.
Exit 2 means incomplete/ambiguous evidence; exit 0 means collection succeeded.
The REVIEW result still requires a grounded human decision for each due item.

An item tagged `**Critical:** <class>` is a deadline whose miss cannot be undone. It is reported
apart from the dated list (`critical`), leads from seven days out, is due an alert three days
and one day out, on its day and after, never lapses, and closes only when a closing mark comes
with an `**Evidence:**` line (2026-11-06: an enrollment window closed as one dated row among a
hundred). `--alert` posts one banner and spoken line with a count and no title.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
for _root in (Path(__file__).resolve().parents[3], Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5") / "current"):
    if (_root / "synthesis" / "rituals.py").is_file():
        sys.path.insert(0, str(_root))
        break
from synthesis import rituals  # noqa: E402

DATE = r"\d{4}-\d{2}-\d{2}"
PLAN = re.compile(rf"^({DATE})\.md$")
ARTIFACT = re.compile(rf"^({DATE})-(day-start|midday|day-end)\.md$")
MIDDAY_RUN = re.compile(rf"^({DATE})-midday-([2-9]|[1-9][0-9]{{1,2}})\.md$")  # a later mid-day run that day (2026-10-31)
FIELD = re.compile(r"\*\*(Decays|Decay ID|Sent|Released|Resolved|Critical|Calendar|Evidence|Lapsed):\*\*\s*(.*)", re.I)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+)")
LIST = re.compile(r"^(\s*)(?:[-*+] |\d+[.)] )(.*)")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
RUN_ORDER = {"day-start": 0, "midday": 1, "day-end": 2}
LEAD_DAYS, ALERT_DAYS = 7, (3, 1, 0)  # a critical item leads from a week out; alerts three days and one day out and on its day
WORDS = ("enrollment", "insurance", "tax(?:es)?", "patent", "visa", "passport", "immigration", "payroll", "FSA", "HSA")


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
        if not fields.get("decays") and not fields.get("decay id") and not fields.get("critical"):
            continue
        klass = next((value for _, value in fields["critical"] if value), "")
        evidence = next((value for _, value in fields["evidence"] if value), "")
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
            gap(report, path, "a Critical item needs a valid Decays date" if klass else
                "identified item has no valid Decays date or resolution", source_line)
        entries.append({
            "identity": f"id:{explicit_id}" if explicit_id else f"source:{path}:{source_line}",
            "title": title, "due_date": due.isoformat() if due else None,
            "reason": reason, "closed": closed, "path": str(path), "line": source_line,
            "plan_date": day.isoformat(), "run_rank": rank, "invalid": len(report["gaps"]) > prior_gaps,
            "critical": "" if re.match(r"no\b", klass, re.I) else klass, "not_critical": bool(re.match(r"no\b", klass, re.I)),
            "evidence": evidence, "calendar": next((value for _, value in fields["calendar"] if value), ""),
            "lapsed": bool(fields["lapsed"]),
        })
    for error in errors:
        gap(report, path, error)
    return entries


def declared(cfg: dict, workspace: str):
    """The plan and artifact folders a workspace declares in the ritual config; None when it declares neither key."""
    conf = rituals.settings(cfg, workspace)
    if "plans_dirs" not in conf and "artifacts_dirs" not in conf:
        return None
    roots = [(Path(p), kind) for kind in ("plans", "artifacts") for p in conf.get(f"{kind}_dirs") or []]
    if not all(isinstance(p, str) for kind in ("plans", "artifacts") for p in conf.get(f"{kind}_dirs") or []):
        raise ValueError(f"ritual config: plans_dirs and artifacts_dirs of {workspace} must be lists of folders")
    return roots


def alert_today(due: date, as_of: date, working) -> bool:
    """Three days out, one day out, on the day and after; an alert day off moves to the last working day before it."""
    if due < as_of:
        return True
    for days in ALERT_DAYS:
        day = due - timedelta(days=days)
        if day == as_of:
            return True
        for _ in range(14):
            if working(day):
                break
            day -= timedelta(days=1)
        if day == as_of:
            return True
    return False


def alert(count: int) -> dict:
    """One banner and one spoken line: a count and a pointer, never a title. The mute flag silences the audio only."""
    if not count:
        return {"count": 0}
    text = f"{count} critical deadline{'' if count == 1 else 's'} closing soon or past due. Details are in your day plan."

    def run(tool: str, *args: str) -> str:
        path = shutil.which(tool)
        return "unavailable" if not path else "" if subprocess.run([path, *args], capture_output=True).returncode == 0 else "failed"

    banner = run("osascript", "-e", f'display notification "{text}" with title "Synthesis"') or "posted"
    muted = (Path.home() / ".synthesis" / "quiet-audio").exists()
    return {"count": count, "banner": banner, "audio": "suppressed (mute flag)" if muted else run("say", text) or "played"}


def critical_row(identity: str, history: list, settled: bool, as_of: date, working, report: dict):
    """("closed", row) once a closing mark carries evidence; otherwise ("open", row) with what is wrong with it."""
    latest = history[-1]
    row = {"identity": identity, "title": latest["title"], "path": latest["path"], "line": latest["line"],
           "class": next(e["critical"] for e in reversed(history) if e["critical"])}
    dates = [e["due_date"] for e in history if e["due_date"]]
    if settled and latest["closed"] and latest["evidence"]:
        return "closed", {**row, "due_date": dates[-1] if dates else None, "evidence": latest["evidence"], "closed_in": latest["plan_date"]}
    if not dates:
        if not latest["invalid"]:
            gap(report, latest["path"], "a Critical item needs a valid Decays date", latest["line"])
        return "open", None
    due = date.fromisoformat(dates[-1] if settled else min(dates))  # an unsettled history keeps its earliest date
    calendar = next((e["calendar"] for e in reversed(history) if e["calendar"]), "")
    problems = [text for wrong, text in (
        (identity.startswith("source:"), "no Decay ID line: a carried copy cannot be matched to this item"),
        (not calendar, "no Calendar line: nothing shows its closing date is on the calendar"),
        (latest["closed"] and not latest["evidence"], "marked closed with no Evidence line: it stays open"),
        (any(e["lapsed"] for e in history), "marked Lapsed: a critical item cannot lapse; it stays open until evidence or "
                                            "the principal's own words close it")) if wrong]
    left = (due - as_of).days
    return "open", {**row, "due_date": due.isoformat(), "days_left": left, "lead": left <= LEAD_DAYS, "past_due": left < 0,
                    "alert": alert_today(due, as_of, working), "calendar": calendar, "problems": problems,
                    "redated_from": sorted(set(dates) - {due.isoformat()})}


def collect(roots: list[tuple[Path, str]], as_of: date, workspace: str | None = None) -> dict:
    report = {"schema_version": 1, "as_of": as_of.isoformat(), "status": "BLOCKED",
              "scope": "all available dated Markdown within explicitly declared roots; no lookback cutoff",
              "declared_roots": [{"path": str(p), "kind": k} for p, k in roots],
              "scanned": [], "excluded": [], "future_files": [], "gaps": [], "due": [],
              "critical": {"open": [], "closed": [], "unclassified": []}}
    conf, words = dict(rituals.DEFAULTS), WORDS
    try:
        cfg = rituals.config()
        conf, words = rituals.settings(cfg, workspace or ""), cfg.get("critical_words") or WORDS
        unclassified = re.compile(r"\b(?:" + "|".join(words) + r")\b", re.I)
    except (ValueError, OSError, TypeError, re.error) as exc:
        gap(report, rituals.state_dir() / "config.json", f"ritual config unreadable: {exc}")
        unclassified = re.compile(r"\b(?:" + "|".join(WORDS) + r")\b", re.I)
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
                match = pattern.fullmatch(name) or (kind == "artifacts" and MIDDAY_RUN.fullmatch(name))
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
                if kind != "artifacts":
                    rank = 2
                elif match.re is MIDDAY_RUN:  # midday-2 after midday, before the day-end
                    rank = RUN_ORDER["midday"] + int(match[2]) / 1000
                else:
                    rank = RUN_ORDER[match[2]]
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
        if any(e["critical"] for e in history):  # once critical, always critical: a copy that drops the tag demotes nothing
            state, row = critical_row(identity, history, choices == [latest], as_of, lambda day: rituals.expected(day, conf), report)
            recent = state == "closed" and (as_of - date.fromisoformat(row["closed_in"])).days <= LEAD_DAYS
            report["critical"][state] += [row] if row and (state == "open" or recent) else []
            continue  # never in the dated list, whose items may be released or lapse
        if not latest["closed"] and not any(e["not_critical"] for e in history) and unclassified.search(f"{latest['title']} {latest['reason']}"):
            report["critical"]["unclassified"].append({k: latest[k] for k in ("identity", "title", "due_date", "path", "line")})
        due_choices = [e for e in choices if e["due_date"] and e["due_date"] <= as_of.isoformat() and not e["closed"]]
        if due_choices:
            chosen = min(due_choices, key=lambda e: e["due_date"])
            result = {k: v for k, v in chosen.items() if k not in ("closed", "run_rank", "invalid")}
            result["sources"] = [{"path": e["path"], "line": e["line"]} for e in history]
            report["due"].append(result)
    report["due"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["critical"]["open"].sort(key=lambda e: (e["due_date"], e["path"], e["line"]))
    report["total_obligations"] = len(grouped)
    review = report["due"] or report["critical"]["unclassified"] or any(r["lead"] or r["problems"] for r in report["critical"]["open"])
    report["status"] = "BLOCKED" if report["gaps"] else "REVIEW" if review else "CLEAR"
    return report


def critical_lines(critical: dict) -> list[str]:
    """The block that opens the text report whenever a critical item is open, just closed or unclassified."""
    rows, lines = critical["open"], []
    for row in rows:
        when = f"PAST DUE {row['due_date']}" if row["past_due"] else f"{row['due_date']} ({row['days_left']} days left)"
        was = f" (was {', '.join(row['redated_from'])})" if row["redated_from"] else ""
        lines.append(f"  {when}{was} {row['title']} [{row['class']}] ({row['path']}:{row['line']})")
        lines += [f"      problem: {problem}" for problem in row["problems"]]
    lines += [f"  closed in the last {LEAD_DAYS} days: {row['title']} — on: {row['evidence']}" for row in critical["closed"]]
    lines += [f"  possibly critical, not classified: {row['due_date']} {row['title']} ({row['path']}:{row['line']})"
              for row in critical["unclassified"]]
    head = (f"CRITICAL: {len(rows)} open ({sum(r['past_due'] for r in rows)} past due, "
            f"{sum(r['lead'] and not r['past_due'] for r in rows)} within {LEAD_DAYS} days); "
            f"{sum(r['alert'] for r in rows)} due an alert today")
    return [head, *lines] if rows or lines else []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    parser.add_argument("--plans-dir", action="append", default=[], type=Path)
    parser.add_argument("--artifacts-dir", action="append", default=[], type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--workspace", help="also read the plan and artifact folders this workspace declares in the ritual config")
    parser.add_argument("--alert", action="store_true", help="post the critical-deadline banner and spoken line when one is due today")
    parser.add_argument("--alert-declared", action="store_true",
                        help="one alert counting every workspace's declared folders, for a day with no ritual")
    args = parser.parse_args(argv)
    roots = [(p, "plans") for p in args.plans_dir] + [(p, "artifacts") for p in args.artifacts_dir]
    try:
        as_of = iso_day(args.as_of)
        cfg = rituals.config() if args.workspace or args.alert_declared else {"workspaces": {}}
        roots += declared(cfg, args.workspace) or [] if args.workspace else []
        sets = {tuple(found): name for name in cfg["workspaces"] if (found := declared(cfg, name))} if args.alert_declared else {}
    except ValueError as exc:
        report = {"status": "BLOCKED", "due": [], "gaps": [{"path": "--as-of or the ritual config", "reason": str(exc)}],
                  "critical": {"open": [], "closed": [], "unclassified": []}}
    else:
        if args.alert_declared:  # folders two workspaces share are read once
            count = sum(row["alert"] for found, name in sets.items() for row in collect(list(found), as_of, name)["critical"]["open"])
            print(f"critical alert: {count} due across {len(sets)} declared set(s) of plan folders; {alert(count)}")
            return 0
        report = collect(roots, as_of, args.workspace)
    if args.alert:
        report["critical"]["alert"] = alert(sum(row["alert"] for row in report["critical"]["open"]))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        # Coverage denominators, not bare counts: "3 past due" once hid the
        # shape of the sweep the same way bare checklists did.
        print("\n".join(critical_lines(report["critical"])), end="\n" if critical_lines(report["critical"]) else "")
        print(
            f"Deadline sweep: {report['status']} — {len(report['due'])} due of "
            f"{report.get('total_obligations', '?')} tracked obligations across "
            f"{len(report.get('scanned', []))} scanned sources "
            f"({len(report.get('excluded', []))} excluded, "
            f"{len(report.get('future_files', []))} future); "
            f"{len(report['gaps'])} gaps"
        )
        for row in report["due"]:
            print(f"{row['due_date']} {row['title']} ({row['path']}:{row['line']})")
        for row in report["gaps"]:
            print(f"NOT COVERED: {row['path']}: {row['reason']}")
    return 2 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

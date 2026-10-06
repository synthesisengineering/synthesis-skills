"""Ritual state for SessionStart and the 16:55 nudge (R5.1), from the append-only log
`ritual_state.py record` writes; every view answers for one workspace, and screen text
names none. `rituals.py --owed-today` exits 0 only when no workspace owes today's close."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import paths  # noqa: E402

DEFAULTS = {"streak": "none", "weekdays": [0, 1, 2, 3, 4], "non_working_dates": []}
POINTER = "details: python3 <synthesis-daily-rituals>/scripts/ritual_state.py query summary"
UNNAMED = (None, "", "unknown")


def state_dir() -> Path:
    return Path(os.environ.get("RITUAL_STATE_DIR") or paths.home() / "rituals")


def read() -> tuple[list[dict], int]:  # (records, malformed lines): a bad line costs only itself
    path, rows = state_dir() / "history.jsonl", []
    for line in filter(str.strip, path.read_text(encoding="utf-8").splitlines() if path.is_file() else []):
        try:
            rows.append(json.loads(line))
        except ValueError:
            rows.append(None)
    good = [r for r in rows if isinstance(r, dict) and r.get("date") and r.get("direction")]
    return good, len(rows) - len(good)


def config() -> dict:  # an unreadable file raises: refuse rather than guess
    path = state_dir() / "config.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"workspaces": {}}
    if not isinstance(data, dict) or not isinstance(data.get("workspaces"), dict):
        raise ValueError("ritual config.json has no 'workspaces' mapping")
    return data


def settings(cfg: dict, workspace: str) -> dict:
    return {**DEFAULTS, **(cfg.get("defaults") or {}), **(cfg["workspaces"].get(workspace) or {})}


def expected(day: date, conf: dict) -> bool:
    return day.isoformat() not in conf["non_working_dates"] and day.weekday() in conf["weekdays"]


def last(records: list[dict], workspace: str, direction: str = "day-end") -> dict | None:
    hits = [r for r in records if r.get("workspace") == workspace and r["direction"] == direction]
    return max(hits, key=lambda r: (r["date"], r.get("ts", ""))) if hits else None


def streak(records: list[dict], cfg: dict, workspace: str, today: date) -> int | None:
    # expected days closed in a row: a close on any day credits; a day not expected never breaks it
    conf = settings(cfg, workspace)
    if conf["streak"] != "expected-days":
        return None
    closed = {r["date"] for r in records if r.get("workspace") == workspace and r["direction"] == "day-end"}
    count = int(today.isoformat() in closed)  # today is not over: a close credits, absence does not break
    for back in range(1, 401):
        day = today - timedelta(days=back)
        if day.isoformat() not in closed and expected(day, conf):
            break
        count += day.isoformat() in closed
    return count


def open_days(records: list[dict], today: date, workspace: str | None = None) -> list[tuple[str, str]]:
    # (workspace, date) started and never closed in 30 days; old migration markers count for neither
    floor = (today - timedelta(days=30)).isoformat()
    keep = [r for r in records if r["date"] >= floor and r.get("mode") != "migration"
            and r.get("workspace") not in UNNAMED and workspace in (None, r["workspace"])]
    marks = {d: {(r["workspace"], r["date"]) for r in keep if r["direction"] == d} for d in ("day-start", "day-end")}
    return sorted(marks["day-start"] - marks["day-end"], key=lambda pair: (pair[1], pair[0]))


def friday(today: date) -> date:
    return today - timedelta(days=(today.weekday() - 4) % 7)


def weekly_owed(records: list[dict], workspace: str, today: date) -> bool:
    # owed when the latest review predates the most recent Friday (an early one is dated that Friday)
    review = last(records, workspace, "weekly-review")
    return review is None or review["date"] < friday(today).isoformat()


def session_line(cwd: str, today: date | None = None) -> str:  # empty until a ritual is recorded
    today, (records, bad) = today or date.today(), read()
    try:
        cfg = config()
    except ValueError as exc:
        return f"Rituals: state unreadable ({exc}); {POINTER}."
    if not records and not cfg["workspaces"]:
        return ""
    try:
        here = Path(cwd).resolve().relative_to((Path.home() / "workspaces").resolve()).parts[0]
    except (ValueError, IndexError, OSError):
        here = ""
    parts, day = [], str(today)
    if here:
        close, run = last(records, here), streak(records, cfg, here, today)
        opened = [d for _, d in open_days(records, today, here) if d != day]
        bits = ([f"last day-end {close['date']}" if close else "no day-end recorded"]
                + ([f"streak {run}"] if run is not None else [])
                + ([] if any(r.get("workspace") == here and r["direction"] == "day-start" and r["date"] == day
                             for r in records) else ["no day-start recorded today"])
                + ([f"{len(opened)} workday(s) started and never closed ({', '.join(opened)})"] if opened else [])
                + ([f"weekly review owed (Friday {friday(today)})"] if weekly_owed(records, here, today) else []))
        parts.append("this workspace: " + "; ".join(bits))
    floor = str(today - timedelta(days=30))
    others = sorted(({r["workspace"] for r in records if r["date"] >= floor and r.get("workspace") not in UNNAMED}
                     | {w for w in cfg["workspaces"] if settings(cfg, w)["streak"] == "expected-days"}) - {here})
    if others:
        unclosed = {w for w, d in open_days(records, today) if w in others and d != day}
        parts.append(f"{len(others)} other workspace(s): {len(unclosed)} with workdays never closed, "
                     f"{sum(weekly_owed(records, w, today) for w in others)} owing a weekly review")
    parts += [f"{bad} malformed log line(s)"] if bad else []
    return f"Rituals (today {today:%a %Y-%m-%d}): " + ". ".join(parts) + f". {POINTER}."


def owed_today(today: date | None = None) -> bool:  # opened and not closed today, or an expected close owed
    today, (records, _) = today or date.today(), read()
    cfg = config()
    return any(d == str(today) for _, d in open_days(records, today)) or any(
        settings(cfg, w)["streak"] == "expected-days" and expected(today, settings(cfg, w))
        and (last(records, w) or {}).get("date") != str(today) for w in cfg["workspaces"])


if __name__ == "__main__":
    if sys.argv[1:2] == ["--owed-today"]:
        sys.exit(1 if owed_today() else 0)
    print(session_line(os.getcwd()))

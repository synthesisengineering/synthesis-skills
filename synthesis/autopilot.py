"""Autopilot: the turn-end check for a delegated run, and the plan reader it uses (R6).

A run is one markdown plan file in the project (R6.1). `engage` records which
plan this session owns; at turn end `evaluate()` reads only that plan. When the
plan is running and the turn ended without the next step, it asks for one of
three things: continue the next open checklist item, record a blocker and
alert the principal, or close honestly (R6.4). When the count (`tally`) says
the run's own items outran the principal's, it asks instead for the one line
to bring the principal, and holds the run in any open status but paused until
the principal answers. It asks at most three times in a row for a plan, and
returns None on any error, because a turn-end check that fails closed asks for
another turn forever.

The commands an agent runs by hand (engage, status, cycle, close, alert,
wake-prompt, takeover) live in the skill: python3 -S
<runtime>/skills/synthesis-autopilot/scripts/autopilot_cli.py <command> --help
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from synthesis import paths

OPEN = ("running", "waiting", "blocked", "paused")
CLOSED = ("done", "incomplete", "cancelled")
SHORT_HORIZONS = ("turn", "sitting", "session")
FIRST_WAKE_GRACE = 3600
MAX_PLAN_BYTES = 4 << 20

FIELD = re.compile(r"^\**([A-Za-z][A-Za-z ]{1,30}?)\**\s*:\**\s*(.*?)\s*$")
ITEM = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.*?)\s*$")
LIST = re.compile(r"^\s*[-*+]\s+(?:\[([ xX])\]\s+)?(.*?)\s*$")
EVIDENCE = re.compile(r"\s(?:[—–]|--)\s+\S")
STOPPED = re.compile(r"\b(deleted|stopped|ended|cancelled|canceled|removed)\b", re.I)
ABSENCE = re.compile(r"\b(not (?:available|supported|installed|possible)|unavailable|unsupported|no way to|"
                     r"cannot (?:run|reach|access|schedule|call|connect|install|use|find|wake))\b", re.I)
WHEN = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
WINDOW = 24 * 3600  # the count's day
AHEAD = 300  # a time more than this past the clock is in the future: rejected, never read as the past
ORIGIN = re.compile(r"\borigin:\s*(principal|self)\b", re.I)
ADDED_AT = re.compile(r"\badded:?\s+(" + WHEN.pattern + ")", re.I)
CLOSED_AT = re.compile(r"\bclosed:?\s+(" + WHEN.pattern + ")", re.I)
MOVED_AT = re.compile(r"\b(?:added|closed):?\s+(" + WHEN.pattern + ")", re.I)
ALERTED = re.compile(r"\balerted\s+(" + WHEN.pattern + ")", re.I)
DAY_COUNT = re.compile(r"^\s*[-*+]\s+(\d{4}-\d{2}-\d{2}):\s*(\d+)\b")
QUOTED = re.compile("[\"“]([^\"”]*)[\"”]")
ASKS = "Continue, narrow, or stop?"  # how the count's one line ends, and so how its blocker is known


# ---- the plan file ----------------------------------------------------------

def _visible_lines(text: str) -> list[str]:
    """Lines outside HTML comments and fenced blocks: examples there never count."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines, fence = [], ""
    for line in text.splitlines():
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            fence = "" if fence == marker else (fence or marker)
            continue
        if not fence:
            lines.append(line)
    return lines


class Plan:
    """The header fields (before the first `## `) and the sections of a plan file."""

    def __init__(self, path: Path, text: str):
        self.path, self.text = Path(path), text
        self.fields: dict[str, str] = {}
        self.sections: dict[str, list[str]] = {}
        self._items: dict[str, list[tuple[bool, str]]] = {}
        current = None
        for line in _visible_lines(text):
            if line.startswith("## "):
                current = re.sub(r"\s*\(.*$", "", line[3:]).strip().lower()
                self.sections.setdefault(current, [])
            elif current is not None:
                self.sections[current].append(line)
            elif not line.startswith("#"):
                match = FIELD.match(line.strip())
                if match:
                    self.fields.setdefault(match.group(1).strip().lower(), match.group(2).strip())

    def field(self, name: str) -> str:
        value = self.fields.get(name, "")
        return "" if not value or (value.startswith("<") and value.endswith(">")) else value

    @property
    def status(self) -> str:
        word = re.match(r"[a-z]+", self.field("status").lower())
        return {"canceled": "cancelled"}.get(word.group(0), word.group(0)) if word else ""

    @property
    def status_reason(self) -> str:
        return re.sub(r"^[A-Za-z]+[\s:—–-]*", "", self.field("status")).strip()

    @property
    def title(self) -> str:
        heading = next((l for l in self.text.splitlines() if l.startswith("# ")), "")
        return re.sub(r"^#\s*(Autopilot plan:\s*)?", "", heading).strip() or self.path.stem

    def items(self, section: str) -> list[tuple[bool, str]]:
        """A section's checkbox items, read once per loaded plan: the count and the check read them several times."""
        if section not in self._items:
            self._items[section] = [(m.group(1) != " ", m.group(2)) for m in map(ITEM.match, self.sections.get(section, [])) if m]
        return self._items[section]

    def open_items(self) -> list[str]:
        return [text for done, text in self.items("checklist") if not done]

    @property
    def long_horizon(self) -> bool:
        word = re.match(r"[a-z-]+", self.field("horizon").lower())
        return bool(word) and word.group(0) not in SHORT_HORIZONS


def load(path) -> Plan:
    path = Path(path)
    with open(path, "rb") as handle:
        return Plan(path, handle.read(MAX_PLAN_BYTES).decode("utf-8", "replace"))


def _moment(value: str) -> float | None:
    """The time a value carries, in seconds since the epoch; None when it carries none, or one that cannot be read
    (a date that does not exist, or one too far out to convert), so a crafted stamp never switches a check off."""
    found = WHEN.search(value or "")
    if not found:
        return None
    stamp = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", found.group(0).replace(" ", "T").replace("Z", "+00:00"))
    try:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def _age_seconds(value: str) -> float | None:
    moment = _moment(value)
    return None if moment is None else time.time() - moment


def project_root(plan_path: Path) -> Path | None:
    """The project folder holding the plan: the child of a `projects` folder, else the repository root."""
    parents = list(Path(plan_path).resolve().parents)
    for parent in parents:
        if parent.parent.name == "projects":
            return parent
    return next((p for p in parents if (p / ".git").exists()), None)


def _scratch(real: str) -> bool:
    roots = ["/tmp", "/private/tmp", "/var/folders", "/private/var/folders", os.environ.get("TMPDIR", "")]
    roots = [os.path.realpath(r).rstrip("/") for r in roots if r]
    return "scratchpad" in real.lower() or any(real == r or real.startswith(r + "/") for r in roots)


def _cited(text: str) -> str:
    for pattern in (r"\]\(<?([^)>\s]+)>?\)", r"`([^`]+)`", r"(\S*/\S+|\S+\.(?:md|json|py|csv|tsv|txt|html|ya?ml|log))"):
        found = re.search(pattern, text)
        if found:
            return found.group(1).rstrip(".,;:)")
    return ""


def evidence_problems(plan: Plan) -> list[str]:
    """Each file cited under `## Required evidence` must exist inside the project (R6.5, R9.2)."""
    root = project_root(plan.path)
    root_real = os.path.realpath(root) if root else ""
    problems = []
    for line in plan.sections.get("required evidence", []):
        item = LIST.match(line)
        target = _cited(item.group(2)) if item else ""
        if not target:
            continue
        if re.match(r"[a-z][a-z0-9+.-]*://", target) and not target.startswith("file://"):
            problems.append(f"{target} is a URL, not a file in the project")
            continue
        raw = os.path.expanduser(target[7:] if target.startswith("file://") else target).replace("%20", " ")
        candidates = [Path(raw)] if os.path.isabs(raw) else [plan.path.parent / raw] + ([root / raw] if root else [])
        found = next((c for c in candidates if c.exists()), candidates[0])
        real = os.path.realpath(found)
        inside = bool(root_real) and (real == root_real or real.startswith(root_real + os.sep))
        if not inside and _scratch(real):
            problems.append(f"{target} sits in a scratch or temp folder; move it into the project and cite the new path")
        elif not found.exists():
            problems.append(f"{target} does not exist")
        elif root_real and not inside:
            problems.append(f"{target} is outside the project ({root})")
    return problems


def close_problems(plan: Plan, status: str) -> list[str]:
    """What stands between this plan and an honest close as `status`."""
    problems = []
    if status in ("incomplete", "cancelled"):
        if not plan.status_reason:
            problems.append(f"'Status: {status}' needs the reason after it")
    else:
        criteria = plan.items("completion criteria")
        if not criteria:
            problems.append("it has no completion criteria")
        for done, text in criteria:
            if not done:
                problems.append(f"criterion not met: {text[:90]}")
            elif not EVIDENCE.search(" " + text):
                problems.append(f"criterion checked without evidence after ' — ': {text[:90]}")
        open_items = plan.open_items()
        if open_items:
            problems.append(f"{len(open_items)} checklist item(s) still open, first: {open_items[0][:90]}")
        for done, text in plan.items("standing checklist"):
            item = re.split(r"[:\s]", text, maxsplit=1)[0]
            if done and not EVIDENCE.search(" " + text):
                problems.append(f"standing item {item} is checked without evidence after ' — '")
            elif not done and "waived:" not in text.lower():
                problems.append(f"standing item {item} has no disposition (evidence, or WAIVED: reason)")
        problems += [f"blocker still open: {text[:90]}" for done, text in plan.items("blockers") if not done]
        problems += ["required evidence: " + p for p in evidence_problems(plan)]
    for name in ("continuation", "backstop"):
        value = plan.field(name)
        if value and not value.lower().startswith("none") and not STOPPED.search(value):
            problems.append(f"the {name.capitalize()}: job is not recorded as deleted; delete it, read the deletion "
                            f"back from the harness, and write 'deleted <time>' on that line")
    return problems


# ---- the count: the run's own work against the principal's ------------------

def _label(text: str, position: int) -> str:
    """How an item is named to the principal: its own number, or its place in the checklist."""
    number = re.match(r"(\d+)\.", text)
    return number.group(1) if number else f"#{position}"


def _names(labels: list) -> str:
    return ", ".join(labels[:10]) + (f" and {len(labels) - 10} more" if len(labels) > 10 else "")


def _asked(plan: Plan, now: float, waiting: bool = False) -> float | None:
    """The latest alert time on a blocker that carries the count's line; with `waiting`, on an open one only."""
    times = [_moment(found.group(1)) for done, text in plan.items("blockers") if ASKS in text and not (waiting and done)
             for found in ALERTED.finditer(text)]
    return max((moment for moment in times if moment is not None and moment <= now + AHEAD), default=None)


def _answered(plan: Plan, now: float) -> bool:
    """Whether the principal's own answer lets the run go on: their reply quoted on the Principal answer: line, then
    where they gave it and when; the quote's first word continue or narrow; dated after the count blocker's alert,
    inside the last 24 hours, and not in the future. The agent never writes it from its own judgement."""
    line = plan.field("principal answer")
    quote = QUOTED.search(line)
    word = re.match(r"\W*(\w+)", quote.group(1)) if quote else None
    after = line[quote.end():] if quote else ""
    when, said, asked = WHEN.search(after), _moment(after), _asked(plan, now)
    return (bool(word) and word.group(1).lower() in ("continue", "narrow") and bool(when)
            and bool(re.search(r"[^\W\d_]", after[:when.start()])) and said is not None and asked is not None
            and asked < said <= now + AHEAD and now - said <= WINDOW)


def tally(plan: Plan) -> dict:
    """Principal items closed and self-generated items added in the last 24 hours, the open principal items on the day
    before yesterday, yesterday and today, and whether the count stops the run: the first outnumbered, or each of
    those days higher than the one before, and no principal answer counts. An item with no origin, or no time the
    count can read (one more than five minutes ahead is rejected), is named in `unplaced` and left out, except that
    one of the run's own whose time was written but rejected counts as added now. A plan with no origins counts nothing."""
    now, counted = time.time(), {"principal": 0, "self": 0, "open": 0, "unplaced": [], "tracked": False}
    for position, (done, text) in enumerate(plan.items("checklist"), 1):
        origin = ORIGIN.search(text)
        kind = origin.group(1).lower() if origin else ""
        counted["tracked"] = counted["tracked"] or bool(kind)
        if kind == "principal" and not done:
            counted["open"] += 1
            continue
        stamp = (ADDED_AT if kind == "self" else CLOSED_AT).search(text) if kind else None
        moment = _moment(stamp.group(1)) if stamp else None
        if moment is None or moment > now + AHEAD:
            counted["unplaced"].append(_label(text, position))
            counted["self"] += kind == "self" and stamp is not None  # a written time it cannot trust: added now
        elif now - moment <= WINDOW:
            counted[kind] += 1
    day, recorded = datetime.fromtimestamp(now).date(), {}
    run = [(day - timedelta(days=back)).isoformat() for back in (2, 1, 0)]
    for found in map(DAY_COUNT.match, plan.sections.get("backlog count", [])):
        if found:
            recorded.setdefault(found.group(1), int(found.group(2)))
    days = {**recorded, run[2]: recorded.get(run[2], counted["open"])} if counted["tracked"] else {}
    series = [days[when] for when in run if when in days]
    over, rising = counted["self"] > counted["principal"], len(series) == 3 and series[0] < series[1] < series[2]
    counted.update(today=run[2], recorded=recorded, series=series, over=over, rising=rising,
                   stop=(over or rising) and not _answered(plan, now))
    return counted


def stop_line(plan: Plan, counted: dict) -> str:
    """The one line to bring the principal when the count stops the run."""
    why = [f"in the last 24 hours this run added {counted['self']} item(s) of its own and closed "
           f"{counted['principal']} of yours"] if counted["over"] else []
    if counted["rising"]:
        why.append(f"your open items in this run rose two days running ({', '.join(map(str, counted['series']))})")
    if counted["unplaced"]:
        why.append(f"it could not read the origin or time of item(s) {_names(counted['unplaced'])}")
    return f"{plan.title}: {', and '.join(why)}. {ASKS}"


def _held(plan: Plan) -> str | None:
    """What the turn-end check asks of a run its count has stopped, in any open status but paused: to ask the
    principal, to name what was added or closed after the count blocker's alert, or to set blocked; None when the count
    has not stopped it, or it is held as it should be."""
    counted = tally(plan) if plan.open_items() else {}
    if not counted.get("stop"):
        return None
    now, where = time.time(), plan.path
    asked = _asked(plan, now, waiting=True)
    if asked is None:
        return (f"Your autopilot plan {where} stops for its count: start nothing new until the principal answers. Bring "
                f"them this one line: {stop_line(plan, counted)} Record it under ## Blockers, alert them "
                f"(autopilot_cli.py alert --kind blocked) and set Status: blocked; their answer goes on the Principal "
                f"answer: line, their reply quoted, with where and when they gave it.")
    moved = [_label(text, position) for position, (done, text) in enumerate(plan.items("checklist"), 1)
             if any((_moment(found.group(1)) or 0) > asked for found in MOVED_AT.finditer(text))]
    if moved:
        at = datetime.fromtimestamp(asked).astimezone().isoformat(timespec="minutes")
        return (f"Your autopilot plan {where} stops for its count: start nothing new until the principal answers. Yet "
                f"{len(moved)} item(s) were added or closed after its alert at {at}: item(s) {_names(moved)}. Tell them "
                f"what was done after the alert, alert them again (autopilot_cli.py alert --kind blocked), and add "
                f"the new 'alerted <time> (<outcome>)' to the blocker.")
    return (f"Your autopilot plan {where} stops for its count and has asked the principal: set Status: blocked, and "
            f"start nothing new until the principal answers.") if plan.status == "running" else None


# ---- the turn-end check -----------------------------------------------------

def _backstop_problems(plan: Plan) -> list[str]:
    if not plan.long_horizon:
        return []
    backstop = plan.field("backstop")
    if not backstop or backstop.lower().startswith("none"):
        return [f"the horizon is {plan.field('horizon')}, so record a backstop that survives this session "
                f"on the Backstop: line (references/continuation.md)"]
    if "stop:" not in backstop.lower():
        return ["the Backstop: line does not say how to stop it ('stop: ...')"]
    return []


def _continuation_problems(plan: Plan, payload: dict, grace: float) -> list[str]:
    problems = []
    live = bool(payload.get("background_tasks")) or bool(payload.get("session_crons"))
    mechanism = plan.field("continuation")
    if not live:
        if not mechanism or mechanism.lower().startswith("none"):
            problems.append("nothing is recorded that will wake this session (Continuation: line)")
        elif _age_seconds(plan.field("first wake")) is None:
            age = _age_seconds(plan.field("engaged"))
            if age is None or age > grace:
                problems.append(f"the continuation ({mechanism[:80]}) has no observed first wake "
                                f"{int(grace // 60)} minutes after engagement; a listed job is not a job that fires")
    return problems + _backstop_problems(plan)


def turn_end_reason(plan: Plan, payload: dict, settings: dict) -> str | None:
    """The continuation request for this plan at turn end, or None when the turn may end."""
    status, where = plan.status, plan.path
    if status in CLOSED:
        problems = close_problems(plan, status)
        return (f"Your autopilot plan {where} says {status}, but " + "; ".join(problems)
                + ". Fix these, or close it as incomplete with the reason.") if problems else None
    held = _held(plan) if status in ("running", "waiting", "blocked") else None
    if held:
        return held  # the count's stop holds the whole run, whatever its status (rule 8's one exception)
    if status == "blocked":
        blockers = [text for done, text in plan.items("blockers") if not done]
        if not blockers:
            return (f"Your autopilot plan {where} says blocked but lists no open blocker under ## Blockers. Record "
                    f"what blocks the run and alert the principal, or set Status: running and continue.")
        problems = [f"no alert recorded for: {t[:80]}" for t in blockers if "alerted" not in t.lower()]
        problems += [f"no probe recorded for the capability claim: {t[:80]}"
                     for t in blockers if ABSENCE.search(t) and "probe:" not in t.lower()]
        return (f"Your autopilot plan {where} says blocked, but " + "; ".join(problems) + ". Alert the principal "
                "(autopilot_cli.py alert), note 'alerted <time> (<outcome>)' on each blocker, and record "
                "'probe: <command> -> <output>' for any missing capability.") if problems else None
    if status == "waiting":
        problems = [] if plan.field("waiting on") else ["no 'Waiting on:' line names the external event"]
        problems += _continuation_problems(plan, payload, float(settings.get("first_wake_grace_seconds", FIRST_WAKE_GRACE)))
        return (f"Your autopilot plan {where} says waiting, but " + "; ".join(problems) + ". Set up the "
                "continuation, or set Status: running and do the work that does not depend on the wait.") if problems else None
    if status != "running" or payload.get("background_tasks"):
        return None  # paused by the principal, unknown, or a running task will wake this session
    items = plan.open_items()
    if items:
        more = f" ({len(items) - 1} more open after it)" if len(items) > 1 else ""
        message = (f"Your autopilot plan {where} still has open items. Continue with the next one now: {items[0]}"
                   f"{more}. If it is blocked, record the blocker under ## Blockers, alert the principal and set "
                   f"Status: blocked. If it waits on something external, set Status: waiting with a 'Waiting on:' "
                   f"line and a continuation that will wake this session.")
    elif plan.items("checklist"):
        message = (f"Every checklist item in your autopilot plan {where} is checked, but Status is still running. "
                   f"Verify the completion criteria, then close it honestly: done, or incomplete with the reason.")
    else:
        message = (f"Your autopilot plan {where} is running but lists no '- [ ]' items under ## Checklist. Write "
                   f"the remaining work there and continue with the first item, or close the run honestly.")
    extra = [] if plan.field("continuation") or not plan.long_horizon else [
        f"no continuation is recorded for a {plan.field('horizon')} horizon"]
    extra += _backstop_problems(plan)
    return message + (" Also: " + "; ".join(extra) + "." if extra else "")


def _pointer_file(session_id: str) -> Path:
    return paths.state() / "autopilot" / (re.sub(r"[^A-Za-z0-9._-]", "_", session_id) + ".json")


def _read_pointer(session_id: str) -> dict:
    return paths.read_json(_pointer_file(session_id))


def _write_pointer(session_id: str, data: dict) -> None:
    paths.write_json(_pointer_file(session_id), data)


def evaluate(payload: dict, config: dict | None = None) -> tuple[str | None, str | None]:
    """(reason to request a continuation, note for the person). Both None on any error."""
    try:
        return _evaluate(payload or {}, config or {})
    except Exception:
        return None, None


def _evaluate(payload: dict, config: dict) -> tuple[str | None, str | None]:
    session = paths.session_id(payload)
    pointer = _read_pointer(session) if session else {}
    if not pointer.get("plan"):
        return None, None
    plan = load(pointer["plan"])
    if plan.field("owner session") != session:
        return None, None  # another session's plan never blocks this one
    settings = config.get("autopilot") or {}
    reason = turn_end_reason(plan, payload, settings)
    if not reason:
        return None, None
    digest = hashlib.sha256(plan.text.encode("utf-8")).hexdigest()
    repeat = bool(payload.get("stop_hook_active")) or pointer.get("digest") == digest
    streak = int(pointer.get("streak") or 0) + 1 if repeat else 1
    limit = int(settings.get("max_continuations", 3))
    _write_pointer(session, {**pointer, "streak": streak, "digest": digest, "at": time.time()})
    if streak > limit:
        note = (f"Autopilot asked this session to continue {plan.path.name} {limit} times in a row, so it is "
                f"letting the session stop. Review the plan: {plan.path}")
        return None, note if streak == limit + 1 else None
    return reason, None


def brief(payload: dict) -> str:
    """One paragraph for session start, including after compaction (R6.3): the run this session owns, or, when its
    count has stopped it, that it waits for the principal's answer to the one line."""
    try:
        session = paths.session_id(payload)
        pointer = _read_pointer(session) if session else {}
        plan = load(pointer["plan"]) if pointer.get("plan") else None
        if plan is None or plan.field("owner session") != session or plan.status not in OPEN:
            return ""
        items = plan.open_items()
        counted = tally(plan) if items else {}
        if counted.get("stop"):
            return (f"Autopilot run stopped by its count, waiting for the principal's answer: {plan.path} (Status: "
                    f"{plan.status}). Read the plan before anything else and start nothing new until the principal "
                    f"answers. The one line: {stop_line(plan, counted)} Their answer goes on the Principal answer: "
                    f"line, their reply quoted, with where and when they gave it.")
        return (f"Autopilot run in progress: {plan.path} (Status: {plan.status}). Read the plan before anything "
                f"else. Next open item: {items[0] if items else 'none; verify and close'}.")
    except Exception:
        return ""

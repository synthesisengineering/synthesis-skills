"""Autopilot: the turn-end check for a delegated run, and its plan-file helpers (R6).

A run is one markdown plan file in the project (R6.1). `engage` records which
plan this session owns; at turn end `check()` reads only that plan. When the
plan is running and the turn ended without the next step, it asks for one of
three things: continue the next open checklist item, record a blocker and
alert the principal, or close honestly (R6.4). It asks at most three times in a
row for a plan, and returns None on any error, because a turn-end check that
fails closed asks for another turn forever.

Helpers: python3 -S <runtime>/synthesis/autopilot.py <command> --help
(engage, status, cycle, close, alert, wake-prompt, takeover).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as a file with -S: make the package importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import paths  # noqa: E402

OPEN = ("running", "waiting", "blocked", "paused")
CLOSED = ("done", "incomplete", "cancelled")
SHORT_HORIZONS = ("turn", "sitting", "session")
FIRST_WAKE_GRACE = 3600
SILENT_DEFAULT_MINUTES = 8 * 60
MAX_PLAN_BYTES = 4 << 20
DEFAULT_STANDING = (
    ("end-to-end", "Complete the work end to end: every item closed or the run closed honestly incomplete."),
    ("framework-decisions", "Open important decisions go through the thinking framework, recorded with rationale."),
    ("plan-current", "Plan re-read after any suspected compaction or wake, and updated at every phase boundary."),
    ("project-files-current", "Project files (CONTEXT.md, session log) current at every phase boundary and at close."),
    ("verify-before-done", "Verification before any completion claim: focused tests per change, full suites per phase."),
    ("lessons-filed", "Durable lessons filed as work proceeds, not at the end."),
    ("completion-report", "Completion report plus batched questions (a decision packet when complex) ready at close."),
)

FIELD = re.compile(r"^\**([A-Za-z][A-Za-z ]{1,30}?)\**\s*:\**\s*(.*?)\s*$")
ITEM = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.*?)\s*$")
LIST = re.compile(r"^\s*[-*+]\s+(?:\[([ xX])\]\s+)?(.*?)\s*$")
EVIDENCE = re.compile(r"\s(?:[—–]|--)\s+\S")
STOPPED = re.compile(r"\b(deleted|stopped|ended|cancelled|canceled|removed)\b", re.I)
ABSENCE = re.compile(r"\b(not (?:available|supported|installed|possible)|unavailable|unsupported|no way to|"
                     r"cannot (?:run|reach|access|schedule|call|connect|install|use|find|wake))\b", re.I)
WHEN = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")


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
        return [(m.group(1) != " ", m.group(2)) for m in map(ITEM.match, self.sections.get(section, [])) if m]

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


def _age_seconds(value: str) -> float | None:
    found = WHEN.search(value or "")
    if not found:
        return None
    stamp = found.group(0).replace(" ", "T").replace("Z", "+00:00")
    stamp = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", stamp)
    moment = datetime.fromisoformat(stamp)
    return time.time() - moment.astimezone(timezone.utc).timestamp()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")


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
    if status == "blocked":
        blockers = [text for done, text in plan.items("blockers") if not done]
        if not blockers:
            return (f"Your autopilot plan {where} says blocked but lists no open blocker under ## Blockers. Record "
                    f"what blocks the run and alert the principal, or set Status: running and continue.")
        problems = [f"no alert recorded for: {t[:80]}" for t in blockers if "alerted" not in t.lower()]
        problems += [f"no probe recorded for the capability claim: {t[:80]}"
                     for t in blockers if ABSENCE.search(t) and "probe:" not in t.lower()]
        return (f"Your autopilot plan {where} says blocked, but " + "; ".join(problems) + ". Alert the principal "
                f"(autopilot.py alert), note 'alerted <time> (<outcome>)' on each blocker, and record "
                f"'probe: <command> -> <output>' for any missing capability.") if problems else None
    if status == "waiting":
        problems = [] if plan.field("waiting on") else ["no 'Waiting on:' line names the external event"]
        problems += _continuation_problems(plan, payload, float(settings.get("first_wake_grace_seconds", FIRST_WAKE_GRACE)))
        return (f"Your autopilot plan {where} says waiting, but " + "; ".join(problems) + ". Set up the "
                f"continuation, or set Status: running and do the work that does not depend on the wait.") if problems else None
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
    try:
        data = json.loads(_pointer_file(session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_pointer(session_id: str, data: dict) -> None:
    path = _pointer_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


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


def check(payload: dict, config: dict) -> str | None:
    """Stop-hook contract shared with reply_check: a reason requests a continuation; None lets the turn end."""
    return evaluate(payload, config)[0]


def brief(payload: dict) -> str:
    """One paragraph for session start, including after compaction (R6.3): the run this session owns."""
    try:
        session = paths.session_id(payload)
        pointer = _read_pointer(session) if session else {}
        plan = load(pointer["plan"]) if pointer.get("plan") else None
        if plan is None or plan.field("owner session") != session or plan.status not in OPEN:
            return ""
        items = plan.open_items()
        return (f"Autopilot run in progress: {plan.path} (Status: {plan.status}). Read the plan before anything "
                f"else. Next open item: {items[0] if items else 'none; verify and close'}.")
    except Exception:
        return ""


# ---- helpers for the agent (command line) -------------------------------------

def _header_end(lines: list[str]) -> int:
    return next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))


def set_field(text: str, name: str, value: str) -> str:
    lines = text.splitlines()
    end = _header_end(lines)
    fields = [i for i in range(end) if FIELD.match(lines[i].strip()) and not lines[i].startswith("#")]
    for i in fields:
        if FIELD.match(lines[i].strip()).group(1).strip().lower() == name.lower():
            lines[i] = f"{name}: {value}"
            return "\n".join(lines) + "\n"
    title = next((i for i in range(end) if lines[i].startswith("# ")), -1)
    at = fields[-1] + 1 if fields else title + 1
    lines[at:at] = [f"{name}: {value}"] + ([""] if not fields and title >= 0 else [])
    return "\n".join(lines) + "\n"


def append_to_section(text: str, section: str, entries: list[str]) -> str:
    lines = text.rstrip("\n").splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("## ") and l[3:].lower().startswith(section.lower())), None)
    if start is None:
        return "\n".join(lines + ["", f"## {section}", ""] + entries) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    lines[end:end] = entries
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _session(args) -> str:
    return args.session or paths.session_id()


def _settings() -> dict:
    try:
        return paths.config().get("autopilot") or {}
    except (OSError, ValueError):
        return {}


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _owned(args, plan: Plan) -> str:
    """This session's id when it owns the plan; empty after printing why not."""
    session = _session(args)
    if not session:
        _fail("no session id: pass --session (Claude Code shells carry $CLAUDE_CODE_SESSION_ID, Codex $CODEX_THREAD_ID)")
        return ""
    if plan.field("owner session") != session:
        _fail(f"refused: {plan.path} is owned by session {plan.field('owner session') or '(none)'}, not {session}")
        return ""
    return session


def cmd_engage(args) -> int:
    from synthesis import board

    session = _session(args)
    path = Path(args.plan).expanduser().resolve()
    if not session:
        return _fail("no session id: pass --session (Claude Code shells carry $CLAUDE_CODE_SESSION_ID, Codex $CODEX_THREAD_ID)")
    if not path.is_file():
        return _fail(f"no plan file at {path}; write it from references/plan-file.md first")
    plan = load(path)
    owner = plan.field("owner session")
    problems = [] if not owner or owner == session else [f"it is owned by session {owner}; run takeover if that session has gone silent"]
    problems += [] if plan.items("checklist") else ["## Checklist has no '- [ ] item' lines"]
    problems += [] if plan.items("completion criteria") else ["## Completion criteria has no '- [ ] criterion' lines"]
    problems += [] if plan.field("horizon") else ["no 'Horizon:' line (turn, sitting, overnight or days)"]
    problems += [] if plan.status in ("",) + OPEN else [f"Status is {plan.status}; a closed run is not engaged again"]
    if problems:
        return _fail(f"refused: {path}\n- " + "\n- ".join(problems))
    try:
        board.claim(session, [str(path)], goal=f"autopilot: {plan.title}"[:120], harness=paths.harness())
    except board.ClaimConflict as exc:
        return _fail(f"refused: {exc}")
    text = set_field(plan.text, "Owner session", session)
    if not plan.status:
        text = set_field(text, "Status", "running")
    if not plan.field("engaged"):
        text = set_field(text, "Engaged", _now())
    extra = [(i.get("id", ""), i.get("text", "")) for i in _settings().get("standing_checklist", [])]
    have = {re.split(r"[:\s]", t, maxsplit=1)[0] for _, t in plan.items("standing checklist")}
    missing = [f"- [ ] {i}: {t}" for i, t in DEFAULT_STANDING + tuple(extra) if i and i not in have]
    if missing:
        text = append_to_section(text, "Standing checklist", missing)
    _write(path, text)
    _write_pointer(session, {"plan": str(path), "streak": 0, "digest": "", "at": time.time()})
    plan = Plan(path, text)
    print(f"engaged: {path}\nowner session: {session}  status: {plan.status}  horizon: {plan.field('horizon')}")
    print(f"next item: {(plan.open_items() or ['none'])[0]}")
    for warning in _continuation_problems(plan, {}, FIRST_WAKE_GRACE) if plan.long_horizon else []:
        print(f"before this turn ends: {warning}")
    return 0


def _questions(plan: Plan) -> list[str]:
    return [m.group(2) for m in map(LIST.match, plan.sections.get("questions for the principal", []))
            if m and m.group(2) and m.group(1) in (None, " ")]


def cmd_status(args) -> int:
    session = _session(args)
    folder = paths.state() / "autopilot"
    files = sorted(folder.glob("*.json")) if args.all and folder.is_dir() else (
        [_pointer_file(session)] if session else [])
    shown = 0
    for file in files:
        try:
            plan = load(json.loads(file.read_text(encoding="utf-8"))["plan"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        shown += 1
        owner = plan.field("owner session")
        age = int((time.time() - plan.path.stat().st_mtime) / 60)
        items, total = plan.open_items(), len(plan.items("checklist"))
        print(f"{plan.path}\n  status: {plan.field('status') or '?'}  owner: {owner}"
              f"{' (this session)' if owner == session else ''}  plan edited {age} min ago")
        print(f"  next: {items[0] if items else '-'}  ({len(items)} of {total} items open)")
        for name in ("waiting on", "continuation", "first wake", "backstop"):
            if plan.field(name):
                print(f"  {name}: {plan.field(name)}")
        for text in [t for done, t in plan.items("blockers") if not done]:
            print(f"  blocker: {text}")
        for text in _questions(plan):
            print(f"  question: {text}")
    if not shown:
        print("no autopilot plan engaged" + (" on this machine" if args.all else " by this session"))
    return 0


def cmd_cycle(args) -> int:
    advanced, waiting = (args.advanced or "").strip(), (args.waiting_on or "").strip()
    if not advanced and not waiting:
        return _fail("refused: a cycle that advanced nothing must name the external wait it is on (--waiting-on). "
                     "There is no way to record a bare spin: if nothing advanced and nothing external is awaited, "
                     "the run is spinning, so record a blocker and alert, or close.")
    path = Path(args.plan).expanduser().resolve()
    plan = load(path)
    if not _owned(args, plan):
        return 1
    entry = "; ".join(p for p in (advanced and f"advanced: {advanced}", waiting and f"waiting on: {waiting}") if p)
    text = append_to_section(plan.text, "Cycle ledger", [f"- {_now()} {entry}"])
    _write(path, text)
    count = sum(1 for line in Plan(path, text).sections.get("cycle ledger", []) if LIST.match(line))
    print(f"cycle recorded ({count} in the ledger)")
    return 0


def cmd_close(args) -> int:
    from synthesis import board

    path = Path(args.plan).expanduser().resolve()
    if not path.is_file():
        return _fail(f"refused: no plan file at {path}; a run without a plan cannot close as done")
    plan = load(path)
    session = _owned(args, plan)
    if not session:
        return 1
    status, why = ("done", "") if args.done else ("incomplete", args.incomplete) if args.incomplete is not None else ("cancelled", args.cancelled)
    if status != "done" and not (why or "").strip():
        return _fail(f"refused: closing as {status} needs the reason")
    text = set_field(plan.text, "Status", status + (f" — {why.strip()}" if why else ""))
    problems = close_problems(Plan(path, text), status)
    if problems:
        return _fail(f"refused: {path} cannot close as {status}:\n- " + "\n- ".join(problems)
                     + ("\nClosing as incomplete with the reason stays available." if status == "done" else ""))
    _write(path, text)
    claimed = os.path.realpath(path)
    board.release(session, [claimed])
    if _read_pointer(session).get("plan") == str(path):
        _pointer_file(session).unlink()
    print(f"closed as {status}: {path}\nnext: send the completion alert and the completion report")
    return 0


ALERTS = {
    "blocked": "Autopilot run is blocked: {n} question(s) need you. Run autopilot status for details.",
    "done": "Autopilot run finished. The report is in its plan.",
    "budget": "Autopilot run stopped at its budget: {n} item(s) left. Run autopilot status for details.",
}


def alert(kind: str, count: int, *, mute_flag: Path, run=None, which=None) -> list[tuple[str, str]]:
    """Banner and sound with counts and a pointer only. Returns (channel, outcome) pairs to record."""
    import shutil
    import subprocess

    run, which = run or subprocess.run, which or shutil.which
    text = ALERTS[kind].format(n=count)
    outcomes = []

    def attempt(channel: str, command: list[str]) -> None:
        try:
            done = run(command, capture_output=True, timeout=20)
            outcomes.append((channel, "posted" if channel == "banner" and done.returncode == 0 else
                             "played" if done.returncode == 0 else f"failed (exit {done.returncode})"))
        except Exception as exc:  # report, never raise: the written report still goes out
            outcomes.append((channel, f"failed ({type(exc).__name__})"))

    if which("osascript"):
        attempt("banner", ["osascript", "-e", f'display notification "{text}" with title "Autopilot"'])
    else:
        outcomes.append(("banner", "unavailable (no osascript)"))
    if mute_flag.exists():
        outcomes.append(("audio", "suppressed (mute flag)"))
    elif which("say"):
        attempt("audio", ["say", text])
    else:
        outcomes.append(("audio", "unavailable (no say)"))
    return outcomes


def cmd_alert(args) -> int:
    mute = Path(os.path.expanduser(_settings().get("mute_flag", "~/.synthesis/quiet-audio")))
    outcomes = alert(args.kind, args.count, mute_flag=mute)
    for channel, outcome in outcomes:
        print(f"{channel}: {outcome}")
    print(f"record on the blocker or close line: alerted {_now()} ("
          + "; ".join(f"{c} {o}" for c, o in outcomes) + ")")
    return 0 if any(o in ("posted", "played") for _, o in outcomes) else 1


def wake_prompt(path) -> str:
    return (f"Autopilot wake for the plan at {path}. Read that plan before anything else. If its Status is done, "
            f"incomplete or cancelled, do no work: delete this scheduled job, read the deletion back, and stop. If "
            f"another session owns it, run `autopilot.py status --all`; take it over only when the plan has been "
            f"silent longer than its Silent after: line allows, otherwise message the owner and stop. Otherwise "
            f"verify the plan's state against git and the files on disk, record this wake in the cycle ledger, and "
            f"continue the next open checklist item.")


def cmd_wake_prompt(args) -> int:
    print(wake_prompt(Path(args.plan).expanduser().resolve()))
    return 0


def cmd_takeover(args) -> int:
    from synthesis import board

    session = _session(args)
    path = Path(args.plan).expanduser().resolve()
    if not session:
        return _fail("no session id: pass --session")
    plan = load(path)
    owner = plan.field("owner session")
    if plan.status not in OPEN:
        return _fail(f"refused: {path} is {plan.status or 'not engaged'}; there is nothing to take over")
    limit = int(re.match(r"\d*", plan.field("silent after")).group(0) or SILENT_DEFAULT_MINUTES) * 60
    held = board.load(owner) if owner else None
    activity = max(path.stat().st_mtime, held.seen if held else 0)
    if owner and owner != session and time.time() - activity < limit:
        return _fail(f"refused: owner {owner} was active {int((time.time() - activity) / 60)} min ago (limit "
                     f"{limit // 60} min); message it with `synthesis msg {owner} ...` instead")
    claim = os.path.realpath(path)
    if held and claim in held.claims:
        board.release(owner, [claim])
    try:
        board.claim(session, [str(path)], goal=f"autopilot: {plan.title}"[:120], harness=paths.harness())
    except board.ClaimConflict as exc:
        return _fail(f"refused: {exc}")
    if owner and owner != session:
        board.notify(owner, session, f"Took over autopilot plan {path}: no activity for {limit // 60} minutes.")
    text = set_field(plan.text, "Owner session", session)
    text = append_to_section(text, "Cycle ledger", [f"- {_now()} taken over from {owner or '(none)'} by {session}"])
    _write(path, text)
    _write_pointer(session, {"plan": str(path), "streak": 0, "digest": "", "at": time.time()})
    print(f"took over: {path}\nnext item: {(load(path).open_items() or ['none'])[0]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="autopilot.py", description="Autopilot plan helpers (synthesis v5).")
    p.add_argument("--session", default="", help="session id (default: the harness's own)")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("engage", help="take ownership of a plan file and turn on the turn-end check")
    s.add_argument("--plan", required=True)
    s.set_defaults(fn=cmd_engage)
    s = sub.add_parser("status", help="this session's run, or every run on this machine with --all")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("cycle", help="record a wake in the cycle ledger; a bare spin is refused")
    s.add_argument("--plan", required=True)
    s.add_argument("--advanced", default="")
    s.add_argument("--waiting-on", default="")
    s.set_defaults(fn=cmd_cycle)
    s = sub.add_parser("close", help="close the run honestly")
    s.add_argument("--plan", required=True)
    group = s.add_mutually_exclusive_group(required=True)
    group.add_argument("--done", action="store_true")
    group.add_argument("--incomplete", metavar="REASON")
    group.add_argument("--cancelled", metavar="REASON")
    s.set_defaults(fn=cmd_close)
    s = sub.add_parser("alert", help="banner and sound with counts and a pointer only; honors the mute flag")
    s.add_argument("--kind", choices=sorted(ALERTS), required=True)
    s.add_argument("--count", type=int, default=1)
    s.set_defaults(fn=cmd_alert)
    s = sub.add_parser("wake-prompt", help="print the prompt every scheduled wake uses")
    s.add_argument("--plan", required=True)
    s.set_defaults(fn=cmd_wake_prompt)
    s = sub.add_parser("takeover", help="take over a plan whose owner has gone silent")
    s.add_argument("--plan", required=True)
    s.set_defaults(fn=cmd_takeover)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

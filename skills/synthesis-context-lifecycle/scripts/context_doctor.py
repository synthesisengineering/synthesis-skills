#!/usr/bin/env python3
"""Check that project records are small, current and durable enough for a cold resume (R1.5).

    python3 context_doctor.py [--project PATH | --root KNOWLEDGE_ROOT] [--json]

With neither flag it audits every knowledge root in ~/.synthesis/v5/config.json
(`knowledge_roots`), else every ~/workspaces/*/ai-knowledge-*. Exit 0 healthy,
1 defects found, 2 the doctor could not tell (an unreadable or non-git source,
or nothing to audit). A check that cannot run never looks like one that passed.

The output leads with this session's active project and counts the rest, so a
signal is not lost among hundreds of warnings. Standard library only; it runs on
demand and in the rituals, never in a per-call hook.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

CONTEXT_ACTIVE, CONTEXT_COMPLETED, REFERENCE, REFERENCE_INDEX = 150, 80, 300, 150
CANONICAL = {"active", "paused", "completed", "archived"}
TERMINAL = {"completed", "complete", "archived", "superseded"}
DORMANT = TERMINAL | {"paused"}
RETIRED = {
    "new": "a Phase, not a lifecycle state -- use active or paused",
    "ongoing": "conflates attention with boundedness -- use active/paused plus `bounded: false`",
    "superseded": "use `archived` plus `superseded_by`",
    "complete": "a typo of `completed`",
}
COMPLETED_WORDS = ("complete", "completed", "shipped", "closed", "done", "archived", "superseded")
PAUSED_WORDS = ("paused", "on hold", "parked")
# Not anchored: real records put two fields on one line, and the value stops at the next bold field.
STATUS_HEADER = re.compile(r"\*\*Status:\*\*\s*(?P<v>.+?)\s*(?=\*\*[A-Z][^*]*:\*\*|$)", re.M)
PHASE_HEADER = re.compile(r"\*\*Phase:\*\*\s*(?P<v>.+?)\s*(?=\*\*[A-Z][^*]*:\*\*|$)", re.M)
FIELD_LINE = re.compile(r"^\*\*(Phase|Last session):\*\*([^\n]*)", re.M)
LOG_ENTRY = re.compile(r"^#{2,3}\s+(\d{4}-\d{2}-\d{2})([^\n]*)", re.M)
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
# A closed set of families; the FIRST number of a family in a field is that field's identity.
ORDINAL = re.compile(r"\b(round|wave|phase|step|part)[\s-]*(\d+)\b", re.I)
STATE_AS_OF = re.compile(r"^\*State as of:\s*(\d{4}-\d{2}-\d{2})([^\n*]*)\*\s*$", re.M)
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)
ITEM_STAMP = re.compile(r"^[ \t]*[-*][ \t]+(?:\[(?P<box>[ xX])\][ \t]+)?(?P<text>.*?)[ \t]*\(as of[ \t]+"
                        r"(?P<date>\d{4}-\d{2}-\d{2})(?:,[ \t]*review[ \t]+(?P<days>\d+)d)?\)[ \t]*$", re.M)
ITEM = re.compile(r"^[ \t]*[-*][ \t]+(?:\[(?P<box>[ xX])\][ \t]+)?(?P<text>.+?)[ \t]*$", re.M)
# Only lists of live obligations are held to stamps. "current" is deliberately absent: "Current State"
# holds prose, and including it once flagged 140 of 294 items across 18 projects.
OPEN_SECTION = re.compile(r"open|pending|next|action|todo|to do|blocked|waiting|in progress", re.I)
REVIEW_DAYS = 14


class CannotTell(Exception):
    """The doctor cannot establish ground truth: exit 2, never a pass."""


@dataclass
class Finding:
    project: str
    check: str
    severity: str  # "defect" or "warning"
    message: str
    remedy: str


@dataclass
class Audit:
    project: str
    path: Path
    findings: list = field(default_factory=list)
    examined: list = field(default_factory=list)
    skipped: list = field(default_factory=list)

    def add(self, check, severity, message, remedy):
        self.findings.append(Finding(self.project, check, severity, message, remedy))


# --- reading ---------------------------------------------------------------------------------------

def git(repo: Path, *args: str, raw: bool = False) -> tuple[int, str]:
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_LITERAL_PATHSPECS": "1"})
    except (OSError, subprocess.SubprocessError) as exc:
        raise CannotTell(f"git failed in {repo}: {exc}") from exc
    return done.returncode, done.stdout if raw else done.stdout.strip()


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CannotTell(f"could not read {path}: {exc}") from exc


def _scalar(raw: str):
    raw = raw.strip()
    if len(raw) > 1 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return {"true": True, "yes": True, "false": False, "no": False, "null": None, "~": None}.get(raw.lower(), raw)


def index_entries(text: str) -> list[dict]:
    """The flat fields of each project in index.yaml, under `projects:` or as a bare top-level list.
    A dash deeper than an entry's own fields belongs to a nested list (tags), not a new entry."""
    items, in_list, key_indent, entry_indent, field_indent = [], False, -1, None, None
    bare = not re.search(r"^projects:", text, re.M)
    for raw in text.splitlines():
        line = re.sub(r"\s+#.*$", "", raw).rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        indent, body = len(line) - len(line.lstrip()), line.strip()
        if not in_list:
            if bare or body.startswith("projects:"):
                in_list, key_indent = True, (-1 if bare else indent)
            if not bare:
                continue
        if indent <= key_indent and not body.startswith("-"):
            break
        if body.startswith("- "):
            if entry_indent is not None and indent > entry_indent:
                continue
            items.append({})
            entry_indent, field_indent, body = indent, None, body[2:].strip()
        elif not items or entry_indent is None or indent <= entry_indent:
            continue
        else:
            field_indent = indent if field_indent is None else field_indent
            if indent > field_indent:
                continue
        if ":" in body:
            key, _, value = body.partition(":")
            if key.strip() not in items[-1]:
                items[-1][key.strip()] = None if value.strip() in (">", "|", ">-", "|-", "") else _scalar(value)
    return [i for i in items if "id" in i]


def _verdict(value: str):
    """Completed (True), not completed (False) or silent (None). The leading clause decides:
    "Active — Phase 4 is COMPLETE" is active. "not complete" is never completed."""
    def scan(text):
        if re.search(r"\bnot\s+(?:yet\s+)?complete", text) or any(re.search(rf"\b{w}\b", text) for w in PAUSED_WORDS):
            return False
        active = re.search(r"\bactive\b", text)
        done = next((m for m in (re.search(rf"\b{w}\b", text) for w in COMPLETED_WORDS) if m), None)
        if active and done:
            return active.start() > done.start()
        return True if done else (False if active else None)
    value = value.lower()
    leading = re.split(r"[—|,;(.]|--", value, maxsplit=1)[0]
    found = scan(leading)
    return found if found is not None else scan(value)


def declares_completed(text: str):
    """Status is authoritative; Phase is only a fallback ("Triage — inventory complete" is not a status)."""
    for pattern in (STATUS_HEADER, PHASE_HEADER):
        for match in pattern.finditer(text):
            found = _verdict(match.group("v"))
            if found is not None:
                return found
    return None


def first_ordinals(text: str) -> dict:
    found = {}
    for match in ORDINAL.finditer(text):
        found.setdefault(match.group(1).lower(), int(match.group(2)))
    return found


def session_log(project: Path) -> tuple[list, list, dict]:
    """(dated entries as (date, file), gaps, current ordinals of the newest date). Only entry headings
    count; the generated INDEX.md never does. A readable old entry cannot certify an unreadable file."""
    entries, gaps, descriptors = [], [], []
    for log in sorted((project / "sessions").glob("*.md")) if (project / "sessions").is_dir() else []:
        if log.name == "INDEX.md":
            continue
        try:
            text = log.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            gaps.append(f"sessions/{log.name} could not be read: {exc}")
            continue
        for raw, descriptor in LOG_ENTRY.findall(text):
            try:
                entries.append((date.fromisoformat(raw), f"sessions/{log.name}"))
                descriptors.append((raw, descriptor))
            except ValueError:
                gaps.append(f"sessions/{log.name} has an invalid session date {raw}")
    if not entries:
        gaps.append("no valid dated session entries under sessions/")
    newest = max((e[0] for e in entries), default=None)
    current: dict = {}
    for raw, descriptor in descriptors:  # max over the newest day's entries, first within each
        if newest and raw == newest.isoformat():
            for family, number in first_ordinals(descriptor).items():
                current[family] = max(number, current.get(family, -1))
    return entries, gaps, current


def _section_of(text: str, position: int) -> str:
    section = "(top)"
    for match in SECTION.finditer(text):
        if match.start() >= position:
            break
        section = match.group(1)
    return section


# --- the checks ------------------------------------------------------------------------------------

def check_currency(audit: Audit, text: str, current: dict, newest, dormant: bool) -> None:
    """Header fields judged one at a time (a fresh Phase must not hide a stale Last session), the
    Phase/Last session pair, and section as-of markers."""
    fields = {m.group(1): m.group(2).strip() for m in FIELD_LINE.finditer(text)}
    for name, value in sorted(fields.items()):
        for family, number in sorted(first_ordinals(value).items()):
            if current.get(family) is not None and number < current[family]:
                audit.add("header-currency", "defect", f"**{name}:** says {family} {number}; the session log's "
                          f"newest entry is {family} {current[family]}", "bring the stale field up to date")
    phase, last = first_ordinals(fields.get("Phase", "")), first_ordinals(fields.get("Last session", ""))
    for family in sorted(phase.keys() & last.keys()):
        if phase[family] > last[family]:
            audit.add("header-lag", "defect", f"**Phase:** moved to {family} {phase[family]} but **Last session:** "
                      f"still says {family} {last[family]}", "update Last session first, or in the same edit")
    markers = [(m.start(), m.group(1), first_ordinals(m.group(2))) for m in STATE_AS_OF.finditer(text)]
    for start, stamp, ordinals in markers:
        section = _section_of(text, start)
        if newest and stamp < newest.isoformat():
            audit.add("body-currency", "defect", f"'{section}' is marked as of {stamp}; the session log records "
                      f"{newest}", "rewrite the section, then advance its *State as of:* marker in the same edit")
        for family, number in sorted(ordinals.items()):
            if current.get(family) is not None and number < current[family]:
                audit.add("body-currency", "defect", f"'{section}' is marked as of {family} {number}; the log "
                          f"records {family} {current[family]}", "rewrite the section, then advance its marker")
    block = "<!-- synthesis-current-state:start -->" in text  # the current-state block is the newer convention
    if not markers and not dormant and not block and (first_ordinals(" ".join(fields.values())) or current):
        audit.add("body-currency", "warning", "an ordinal-paced record has no '*State as of: ...*' markers, so a "
                  "current header above stale sections cannot be told apart", "add markers to Current State and What's Next")


def check_items(audit: Audit, text: str, today: date, completed: bool, dormant: bool) -> None:
    """Open items stamped `(as of DATE, review Nd)`: overdue, unstamped and malformed stamps on live
    projects; on a completed project, the question is whether it still owes anything at all."""
    if completed:
        owed = sum(1 for m in ITEM.finditer(text) if m.group("box") == " " and OPEN_SECTION.search(_section_of(text, m.start())))
        if owed:
            audit.add("terminal-project-open-items", "warning", f"the project is completed but CONTEXT.md still lists "
                      f"{owed} unchecked open item(s)", "close them into sessions/, hand them to the project that "
                      "inherited them, or reopen this one")
    if dormant:
        audit.skipped.append(("item-currency", "dormant"))
        return
    audit.examined.append("item-currency")
    stamped = set()
    for m in ITEM_STAMP.finditer(text):
        section, item = _section_of(text, m.start()), m.group("text").strip()
        stamped.add((section, item))
        if (m.group("box") or " ").lower() == "x":
            continue
        try:
            age = (today - date.fromisoformat(m.group("date"))).days
        except ValueError:
            audit.add("item-currency", "warning", f"'{section}' item \"{item}\" has an impossible stamp date "
                      f"{m.group('date')}", "re-date it with a real date once checked")
            continue
        horizon = int(m.group("days")) if m.group("days") is not None else REVIEW_DAYS  # 0 days is a statement
        if age > horizon:
            audit.add("item-currency", "warning", f"'{section}' item \"{item}\" is {age} days past its stamp, over its "
                      f"{horizon}-day review horizon", "check it, then re-date it with (as of YYYY-MM-DD, review Nd)")
    bare: dict = {}
    for m in ITEM.finditer(text):
        section, body = _section_of(text, m.start()), m.group("text").strip()
        if not OPEN_SECTION.search(section) or (m.group("box") or " ").lower() == "x" or (section, body) in stamped:
            continue
        if any(section == s and body.startswith(t) for s, t in stamped):
            continue
        if body.endswith(")") and "as of" in body:
            audit.add("item-currency", "warning", f"'{section}' item \"{body}\" has an '(as of ...)' suffix that does "
                      "not parse as a stamp", "write (as of YYYY-MM-DD, review Nd)")
        else:
            bare[section] = bare.get(section, 0) + 1
    for section in sorted(bare):
        audit.add("item-currency", "warning", f"'{section}' lists {bare[section]} live item(s) with no '(as of ...)' "
                  "stamp, so their age is unverifiable", "stamp each item you have checked: (as of YYYY-MM-DD, review Nd)")


def check_after_completion(audit, entry, text, entries, repo, project_dir) -> None:
    """A dated session after the completion date is reported, unless reviewed through a commit that
    still covers every project commit (index-side, so recording the review cannot re-fire it)."""
    anchor = parse_date(entry.get("completed_date")) or parse_date(entry.get("last_session"))
    dated = list(entries) + [(d, s) for d, s in ((parse_date(field_value(text, "Last session")), "CONTEXT.md Last session"),
                                                 (parse_date(entry.get("last_session")), "index.yaml last_session")) if d]
    latest = max(dated, default=None)
    reviewed = str(entry.get("post_close_reviewed_through") or "").strip()
    if reviewed:
        if git(repo, "cat-file", "-e", f"{reviewed}^{{commit}}")[0] != 0:
            audit.add("post-close-review-unresolvable", "defect", f"post_close_reviewed_through is {reviewed}, which is "
                      "not a commit here, so the review cannot be checked", "re-review and record the reviewed commit")
            return
        _, newest = git(repo, "log", "-1", "--format=%H", "--", str(project_dir))
        _, dirty = git(repo, "status", "--porcelain", "--untracked-files=all", "--", str(project_dir))
        if newest and not dirty and git(repo, "merge-base", "--is-ancestor", newest, reviewed)[0] == 0:
            audit.skipped.append(("terminal-project-active", "post-close review"))
            return
    if anchor and latest and latest[0] > anchor:
        audit.add("terminal-project-active", "warning", f"index.yaml marks this project completed ({anchor}) but "
                  f"{latest[1]} records a session dated {latest[0]}", "reopen it if work resumed, or record the review "
                  "with post_close_reviewed_through set to the reviewed commit")


def field_value(text: str, name: str) -> str:
    match = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.+?)\s*$", text, re.M)
    return match.group(1) if match else ""


def parse_date(value):
    found = DATE.search(str(value or ""))
    try:
        return date.fromisoformat(found.group(1)) if found else None
    except ValueError:
        return None


def audit_project(project_dir: Path, entry: dict | None, repo: Path, today: date, git_state: dict) -> Audit:
    audit = Audit(project_dir.name, project_dir)
    context = project_dir / "CONTEXT.md"
    if not context.is_file() or not read(context).strip():
        audit.add("context-present", "defect", "no CONTEXT.md, or an empty one: a cold resume has no working memory",
                  "write CONTEXT.md from the tiered template")
        return audit
    text = read(context)
    status = str((entry or {}).get("status") or "").strip().lower()
    declared = declares_completed(text)
    completed = status in TERMINAL or bool(declared)
    dormant = status in DORMANT or bool(declared)  # an unset or unknown status counts as live
    lines = len(text.splitlines())
    budget = CONTEXT_COMPLETED if completed else CONTEXT_ACTIVE
    if lines > budget:
        audit.add("context-budget", "defect", f"CONTEXT.md is {lines} lines, over the "
                  f"{'completed' if completed else 'active'} budget of {budget}",
                  "archive cold content to sessions/ and stable facts to REFERENCE.md first, then trim")
    reference = project_dir / "REFERENCE.md"
    if dormant:
        audit.skipped.append(("reference-budget", "dormant"))
    elif reference.is_file():
        audit.examined.append("reference-budget")
        limit = REFERENCE_INDEX if (project_dir / "reference").is_dir() else REFERENCE
        ref_lines = len(read(reference).splitlines())
        if ref_lines > limit:
            standing = (entry or {}).get("bounded") is False
            audit.add("reference-budget", "warning", f"REFERENCE.md is {ref_lines} lines, over {limit}"
                      + (" (a standing project has outgrown one file)" if standing else " (the scope may be too broad)"),
                      "shard into reference/<topic>.md with REFERENCE.md as the index" if standing else
                      "split the project or move narrative to sessions/; if the breadth is real, declare `bounded: false` and shard")
    if entry is None:
        audit.add("status-agreement", "defect", "the project has no entry in projects/index.yaml, so discovery "
                  "cannot find it", "add it to projects/index.yaml (claim the index first)")
    else:
        if declared is None and status not in DORMANT:
            audit.add("status-agreement", "warning", "CONTEXT.md has no readable Status or Phase header to "
                      "cross-check with index.yaml", "add **Status:** Active (or Paused or Completed)")
        elif declared is not None and declared != (status in TERMINAL):
            audit.add("status-agreement", "defect", f"CONTEXT.md reads {'completed' if declared else 'active'} but "
                      f"index.yaml says '{status or 'unset'}'", "decide the real status and set both")
        if status and status not in CANONICAL:
            audit.add("status-vocabulary", "warning" if status in RETIRED else "defect",
                      f"index.yaml status `{status}` is " + (f"retired: {RETIRED[status]}" if status in RETIRED else
                      "not a known status, which silently disables the checks keyed off it"),
                      f"use one of {sorted(CANONICAL)}")
        if status in TERMINAL and not entry.get("completed_date"):
            audit.add("completed-date", "warning", "index.yaml marks the project completed with no completed_date",
                      "add completed_date: 'YYYY-MM-DD'")
    entries, gaps, current = session_log(project_dir)
    newest = max(entries, default=None)
    if dormant:
        audit.skipped.append(("freshness", "dormant"))
        if status in TERMINAL and entry is not None:
            check_after_completion(audit, entry, text, entries, repo, project_dir)
    else:
        audit.examined.append("freshness")
        if gaps:
            audit.add("freshness-unverifiable", "warning", "; ".join(gaps) + "; a commit date cannot stand in for a "
                      "workday", "recover the dated session evidence")
        for source, value in (("CONTEXT.md Last session", parse_date(field_value(text, "Last session"))),
                              ("index.yaml last_session", parse_date((entry or {}).get("last_session")))):
            if newest and value and value != newest[0]:
                audit.add("freshness", "defect", f"{source} is {value}, {'behind' if value < newest[0] else 'ahead of'} "
                          f"the newest dated entry in {newest[1]} ({newest[0]})", "reconcile the field with the session "
                          "log from the actual work; a commit time is not a workday")
    check_currency(audit, text, current, newest[0] if newest else None, dormant)
    check_items(audit, text, today, status in TERMINAL, dormant)
    rel = os.path.relpath(project_dir, repo)
    dirty = [p for p in git_state["dirty"] if p == rel or p.startswith(rel + "/")]
    if dirty:
        audit.add("uncommitted-context", "warning", f"{len(dirty)} uncommitted file(s): on this Mac only until "
                  "committed and pushed", "run synthesis handoff when the work moves to another Mac")
    for tier in (context, reference):
        tier_rel = f"{rel}/{tier.name}"
        if tier.is_file() and tier_rel not in git_state["tracked"] and tier_rel not in git_state["dirty"]:
            audit.add("untracked-context", "defect", f"{tier.name} is ignored or excluded by git, so it never "
                      "reaches another machine", f"un-ignore it and commit {tier_rel}")
    return audit


def repo_state(repo: Path, projects: Path) -> tuple[dict, list]:
    """Git truth for a whole knowledge repository, read once: dirty and tracked paths, and push state."""
    rel = os.path.relpath(projects, repo)
    code, out = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames", "--", rel, raw=True)
    code2, tracked = git(repo, "ls-files", "-z", "--", rel, raw=True)
    if code or code2:
        raise CannotTell(f"git could not read {repo}")
    state = {"dirty": {r[3:] for r in out.split("\0") if len(r) > 3}, "tracked": set(tracked.split("\0"))}
    findings = []
    if f"{rel}/index.yaml" in state["dirty"]:
        findings.append(("uncommitted-context", "warning", "projects/index.yaml has uncommitted changes",
                         "commit it under a claim on the index"))
    remotes = git(repo, "remote")[1]
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")[1]
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")[1] if branch else ""
    if not remotes:
        findings.append(("unpushed-context", "defect", "the repository has no remote: these records exist only on "
                         "this machine", "add a remote and push"))
    elif not branch:
        findings.append(("unpushed-context", "defect", "HEAD is detached: committed records are on no branch",
                         "check out a branch and push"))
    elif not upstream:
        findings.append(("unpushed-context", "defect", f"branch {branch} has no upstream: these records have never "
                         "left this machine", "push with -u to set one"))
    else:
        ahead = git(repo, "rev-list", "--count", f"{upstream}..HEAD", "--", rel)[1]
        if ahead not in ("", "0"):
            findings.append(("unpushed-context", "warning", f"{ahead} commit(s) touching project records are not on "
                             f"{upstream}", "run synthesis handoff, or push"))
    return state, findings


def audit_root(root: Path, today: date, only: Path | None = None, named: bool = True) -> tuple[list, list]:
    """Audit one knowledge root. A root named on the command line must hold projects/; a discovered
    one without projects is simply not a project source."""
    projects = root / "projects"
    if not projects.is_dir():
        if not named:
            return [], []
        raise CannotTell(f"{root} has no projects/ folder, so it cannot be audited")
    index_path = projects / "index.yaml"
    folders = [only] if only else sorted(p for p in projects.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    if not folders and not index_path.is_file():
        return [], []  # nothing here; a run that audits nothing at all still exits 2
    code, top = git(projects, "rev-parse", "--show-toplevel")
    if code or not top:
        raise CannotTell(f"{root} is not inside a git repository")
    repo = Path(top).resolve()
    by_id = {str(e["id"]): e for e in index_entries(read(index_path))} if index_path.is_file() else {}
    state, repo_findings = repo_state(repo, projects.resolve())
    source = [Finding(f"({root.name})", c, s, m, r) for c, s, m, r in repo_findings]
    if not index_path.is_file() and folders:
        source.append(Finding(f"({root.name})", "status-agreement", "defect", "project folders but no "
                              "projects/index.yaml, so nothing can discover them", "create projects/index.yaml"))
    audits = [audit_project(p.resolve(), by_id.get(p.name), repo, today, state) for p in folders]
    if not only:
        names = {p.name for p in folders}
        for pid, entry in sorted(by_id.items()):
            if pid not in names and str(entry.get("status") or "").lower() not in ("archived", "cancelled", "canceled"):
                source.append(Finding(pid, "context-present", "defect", "index.yaml lists this project but no folder "
                                      "exists", "create the folder, or archive the entry"))
    return audits, source


def knowledge_roots() -> list[Path]:
    home = Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")
    try:
        configured = json.loads((home / "config.json").read_text(encoding="utf-8")).get("knowledge_roots")
    except FileNotFoundError:
        configured = None
    except (OSError, ValueError) as exc:
        raise CannotTell(f"could not read {home / 'config.json'}: {exc}") from exc
    if configured:
        return [Path(os.path.expanduser(r)) for r in configured]
    return sorted((Path.home() / "workspaces").glob("*/ai-knowledge-*"))


def active_project() -> str:
    """This session's project from its own board file; never from a global pointer."""
    home = Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5")
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        if os.environ.get(key):
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in os.environ[key])
            try:
                return json.loads((home / "state" / "sessions" / f"{safe}.json").read_text(encoding="utf-8")).get("project", "")
            except (OSError, ValueError):
                return ""
    return ""


# --- reporting -------------------------------------------------------------------------------------

def _lines_for(findings: list, label: bool = False) -> list[str]:
    return [line for f in sorted(findings, key=lambda f: (f.severity != "defect", f.check))
            for line in (f"  {'FAIL' if f.severity == 'defect' else 'warn'}  [{f.check}] "
                         + (f"{f.project}: " if label else "") + f.message, f"        -> {f.remedy}")]


def render(audits: list, source: list, active: str, coverage: dict) -> str:
    findings = source + [f for a in audits for f in a.findings]
    defects = sum(f.severity == "defect" for f in findings)
    out = [f"synthesis context doctor: {len(audits)} project(s) audited"]
    lead = next((a for a in audits if a.project == active), None) or (audits[0] if len(audits) == 1 else None)
    if lead:
        out += [f"\n{lead.project} ({lead.path}): {sum(f.severity == 'defect' for f in lead.findings)} defect(s), "
                f"{sum(f.severity == 'warning' for f in lead.findings)} warning(s)"] + _lines_for(lead.findings)
    rest = [a for a in audits if a is not lead]
    if rest:
        failing = [a for a in rest if any(f.severity == "defect" for f in a.findings)]
        warned = [a for a in rest if a.findings and a not in failing]
        out.append(f"\n{'Other projects' if lead else 'Projects'}: {len(rest)} audited, {len(failing)} with defects, {len(warned)} with warnings "
                   f"only, {len(rest) - len(failing) - len(warned)} clean.")
        for a in failing:
            out.append(f"  {a.project}: " + ", ".join(sorted({f.check for f in a.findings if f.severity == 'defect'})))
        if failing or warned:
            out.append("  Run with --project <path> for one project's full list.")
    if source:
        out += ["\nRepositories and indexes:"] + _lines_for(source, label=True)
    for check, c in sorted(coverage.items()):
        if c["skipped"]:
            out.append(f"coverage  {check}: examined {c['examined']}, skipped {c['skipped']} ({', '.join(sorted(c['why']))})")
    out.append(f"\n{'DEFECTS' if defects else 'HEALTHY'}: {defects} defect(s), {len(findings) - defects} warning(s).")
    return "\n".join(out)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--project", metavar="PATH", help="audit one project folder")
    which.add_argument("--root", metavar="KNOWLEDGE_ROOT", action="append", help="audit every project in this root")
    parser.add_argument("--json", action="store_true", help="the full report as JSON")
    args = parser.parse_args(argv)
    today = date.today()
    try:
        audits, source = [], []
        if args.project:
            project_dir = Path(args.project).expanduser().resolve()
            if not project_dir.is_dir() or project_dir.parent.name != "projects":
                raise CannotTell(f"{project_dir} is not a folder under a projects/ folder")
            audits, source = audit_root(project_dir.parent.parent, today, only=project_dir)
        else:
            roots = [Path(r).expanduser() for r in args.root] if args.root else knowledge_roots()
            if not roots:
                raise CannotTell("no knowledge roots configured or found; pass --root or --project")
            for root in roots:
                found, more = audit_root(root, today, named=bool(args.root))
                audits, source = audits + found, source + more
        if not audits:
            raise CannotTell("no project folders found; a scan of nothing is not a clean scan")
    except CannotTell as exc:
        print(json.dumps({"ok": False, "exit": 2, "error": str(exc)}) if args.json else f"context doctor cannot tell: {exc}",
              file=sys.stdout if args.json else sys.stderr)
        return 2
    coverage: dict = {}
    for a in audits:
        for check in a.examined:
            coverage.setdefault(check, {"examined": 0, "skipped": 0, "why": set()})["examined"] += 1
        for check, why in a.skipped:
            entry = coverage.setdefault(check, {"examined": 0, "skipped": 0, "why": set()})
            entry["skipped"] += 1
            entry["why"].add(why)
    findings = source + [f for a in audits for f in a.findings]
    code = 1 if any(f.severity == "defect" for f in findings) else 0
    active = Path(args.project).name if args.project else active_project()
    if args.json:
        print(json.dumps({"ok": code == 0, "exit": code, "active": active, "projects_audited": len(audits),
                          "defects": sum(f.severity == "defect" for f in findings),
                          "warnings": sum(f.severity == "warning" for f in findings),
                          "coverage": {k: {**v, "why": sorted(v["why"])} for k, v in coverage.items()},
                          "findings": [vars(f) for f in findings]}, indent=2))
    else:
        print(render(audits, source, active, coverage))
    return code


if __name__ == "__main__":
    sys.exit(main())

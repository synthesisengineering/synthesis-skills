#!/usr/bin/env python3
"""Verify that a synthesis project's durable context layer is actually durable.

The tiered context architecture (CONTEXT.md / REFERENCE.md / sessions/) is what
lets a different agent, on a different machine, resume work from files instead
of chat memory. That guarantee has always rested on an agent choosing to
maintain the tiers correctly — which means the layer every other guard depends
on was the one layer with no guard of its own.

This is that guard. It audits every project in every configured source and
reports defects that would degrade a cold resumption, using the same contract
as the rest of the synthesis protective layers:

  - fail closed: a source or project it cannot read is a defect, never a pass
  - exit non-zero when defects exist, so callers can gate on it
  - machine-readable output (--json) for consoles and rituals
  - no dependencies beyond the standard library, so every interpreter on every
    machine produces identical results

Checks (see CHECKS for the registry):

  tier structure   CONTEXT.md present; sessions/ present once history exists;
                   REFERENCE.md present once a project has accumulated the
                   stable facts a resumer would need
  budgets          CONTEXT.md <=150 lines active / <=80 completed;
                   REFERENCE.md <=300
  cross-tier       index.yaml status agrees with the CONTEXT.md status header;
                   completed projects carry completed_date
  freshness        index.yaml last_session and the CONTEXT.md "Last session"
                   header agree with the project's real git history
  durability       tier files are TRACKED by git; remote mode requires a clean,
                   upstream-current branch; local mode reports recoverable
                   uncommitted or ahead state as warnings
  disclosure       anything the doctor could not verify is reported, never
                   silently skipped: unreadable records and freshness that
                   cannot be established both surface as findings

Usage:
    context_doctor.py                    # audit every source in console.yaml
    context_doctor.py --source PATH ...  # audit explicit source roots
    context_doctor.py --project PATH     # audit one project directory
    context_doctor.py --readiness local  # same-machine continuity posture
    context_doctor.py --readiness remote # cross-machine publication posture
    context_doctor.py --json             # machine-readable report
    context_doctor.py --quiet            # exit code + one summary line

Exit codes: 0 healthy, 1 defects found, 2 the doctor itself could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# Sibling module in this scripts directory; ships with the skill. If it is
# missing the doctor must fail loudly rather than silently skip a check.
import context_currency

DOCTOR_VERSION = "1.8.1"

# Budgets from the tiered context architecture.
CONTEXT_BUDGET_ACTIVE = 150
CONTEXT_BUDGET_COMPLETED = 80
REFERENCE_BUDGET = 300

# Semantic memory outgrows one file the same way episodic memory does, and for
# the same reason: a standing project's whole function is to accumulate durable
# operating knowledge, so its REFERENCE.md has no natural ceiling. `sessions/`
# solved that for the episodic tier years ago; `reference/` is the same move one
# tier over. Once a project shards, REFERENCE.md stops being the content and
# becomes the index over it, so it is held to a working-memory budget while each
# topic file gets the old reference budget.
REFERENCE_INDEX_BUDGET = 150
REFERENCE_TOPIC_BUDGET = 300

# A project with at least this many session-archive entries has accumulated
# enough history that stable facts belong in REFERENCE.md rather than in the
# working-memory file.
REFERENCE_EXPECTED_AFTER_SESSIONS = 2

# How far index.yaml's last_session may lag the project's newest commit before
# it is stale rather than merely rounded.
LAST_SESSION_TOLERANCE_DAYS = 1

# A commit touching more than this many distinct projects is repo-wide
# maintenance, not a work session on any one of them.
BULK_COMMIT_PROJECT_THRESHOLD = 3

# How far back to look for a genuine session commit before giving up.
MAX_COMMITS_EXAMINED = 12

# A commit changing more than this many files outside projects/ is a codebase
# or infrastructure change, not a context session, even if it touches one
# project's files in passing.
BULK_COMMIT_OUTSIDE_FILES = 10

# Sentinel for "the freshness dimension could not be established". Distinct
# from None (no commits at all) so a skipped check can be reported rather than
# silently passing.
UNVERIFIABLE = "unverifiable"

SEVERITY_ORDER = {"defect": 0, "warning": 1}

# Every full run writes its report here (like the repo-guard detector), so
# surfaces that must stay fast — SessionStart hooks, console pages — can read
# the latest corpus state without paying for a fresh 150-project audit.
def report_cache_path() -> Path:
    home = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
    return home / "context-doctor" / "last-report.json"


class DoctorError(Exception):
    """The doctor cannot establish ground truth. Always fatal, never a pass."""


@dataclass
class Finding:
    project: str
    source: str
    check: str
    severity: str  # "defect" | "warning"
    message: str
    remedy: str

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "project": self.project,
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "remedy": self.remedy,
        }


@dataclass
class ProjectAudit:
    source: str
    project_id: str
    path: Path
    findings: list[Finding] = field(default_factory=list)
    # Coverage, not findings. A check that finds nothing and a check that
    # examined nothing print the same thing unless you make them different,
    # and a deliberate skip is invisible for exactly the same reason. Every
    # lifecycle-gated check records which side it took, so the report can say
    # "examined 36, skipped 140" instead of silently saying nothing at all.
    # This is what makes an unpaired suppression visible without anyone having
    # to notice the missing pairing.
    skipped: list[tuple[str, str]] = field(default_factory=list)
    examined: list[str] = field(default_factory=list)

    def add(self, check: str, severity: str, message: str, remedy: str) -> None:
        self.findings.append(
            Finding(self.project_id, self.source, check, severity, message, remedy)
        )

    def skip(self, check: str, reason: str) -> None:
        """This project was deliberately out of scope for `check`."""
        self.skipped.append((check, reason))

    def cover(self, check: str) -> None:
        """This project was in scope for `check`, whatever the outcome."""
        self.examined.append(check)


# ---------------------------------------------------------------------------
# Minimal YAML reading
#
# The rest of the synthesis protective layer is stdlib-only on purpose: a guard
# whose behavior depends on which interpreter wins PATH resolution is a guard
# that works by luck. PyYAML is used when it is importable, and a narrow
# fallback parser handles the only two shapes this tool reads (a list of source
# mappings, and index.yaml's list of project mappings).
# ---------------------------------------------------------------------------

try:  # pragma: no cover - import-shape branch
    import yaml  # type: ignore

    _HAVE_YAML = True
except Exception:  # pragma: no cover
    _HAVE_YAML = False


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out)


def _scalar(raw: str) -> object:
    raw = raw.strip()
    if not raw:
        return ""
    if raw[0] == raw[-1] and raw[0] in "\"'" and len(raw) > 1:
        return raw[1:-1]
    low = raw.lower()
    if low in {"true", "yes"}:
        return True
    if low in {"false", "no"}:
        return False
    if low in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def _entries_from_loaded(loaded: object, key: str) -> list[dict]:
    """Pull the project/source list out of a PyYAML-loaded document.

    index.yaml appears in the wild both as `{key: [...]}` and as a bare
    top-level list. Returning [] for shapes we do not recognize (rather than
    raising) is what keeps the bare-list retry reachable.
    """
    if isinstance(loaded, dict):
        value = loaded.get(key)
        if isinstance(value, list):
            return [i for i in value if isinstance(i, dict)]
        return []
    if isinstance(loaded, list):
        return [i for i in loaded if isinstance(i, dict)]
    return []


def parse_mapping_list(text: str, key: str) -> list[dict]:
    """Return the list of flat mappings under `key:` in a YAML document.

    Handles the shapes this tool reads. Nested block values (folded
    descriptions, sub-mappings, sub-lists) are skipped rather than
    misinterpreted — every field the checks use is a flat scalar.
    """
    if _HAVE_YAML:
        try:
            return _entries_from_loaded(yaml.safe_load(text), key)
        except yaml.YAMLError as exc:  # malformed input is a defect, not a pass
            raise DoctorError(f"could not parse YAML: {exc}") from exc

    return _fallback_mapping_list(text, key)


def _fallback_mapping_list(text: str, key: str) -> list[dict]:
    """Stdlib parser for the same shapes.

    The subtle part is nested sequences. A project entry commonly carries
    `tags:` or `related:` followed by `- value` lines indented BELOW the
    entry's own fields. Treating those dashes as new entries splits one
    project into several and silently drops every field that followed —
    which is how a parser difference becomes a difference in verdict. Dashes
    only start a new entry at the entry's own indent.
    """
    items: list[dict] = []
    in_key = key == ""  # empty key means "the document is the list"
    key_indent = -1
    current: dict | None = None
    entry_indent: int | None = None
    field_indent: int | None = None

    for line in text.splitlines():
        stripped = _strip_comment(line).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        body = stripped.strip()

        if not in_key:
            if body == f"{key}:" or body.startswith(f"{key}:"):
                in_key = True
                key_indent = indent
            continue

        if indent <= key_indent and not body.startswith("-"):
            break  # left the block

        if body.startswith("- "):
            # A dash deeper than this entry's fields belongs to a nested
            # sequence (tags, related, aliases), not to a new entry.
            if entry_indent is not None and indent > entry_indent:
                continue
            current = {}
            items.append(current)
            entry_indent = indent
            field_indent = None
            body = body[2:].strip()
            if ":" in body:
                k, _, v = body.partition(":")
                current[k.strip()] = _scalar(v)
            continue

        if current is None or entry_indent is None or indent <= entry_indent:
            continue
        if field_indent is None:
            field_indent = indent
        if indent > field_indent:
            continue  # inside a nested block belonging to the previous field
        if ":" in body:
            k, _, v = body.partition(":")
            k = k.strip()
            v = v.strip()
            # Never overwrite: the first occurrence is the real field, and a
            # later same-named key inside a nested block must not shadow it.
            if k not in current:
                current[k] = None if v in {">", "|", ""} else _scalar(v)

    return items


# ---------------------------------------------------------------------------
# Source discovery
# ---------------------------------------------------------------------------


@dataclass
class Source:
    name: str
    root: Path
    projects_dir: str = "projects"

    @property
    def projects_root(self) -> Path:
        return self.root / self.projects_dir


def console_config_path() -> Path:
    home = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
    return home / "console.yaml"


def discover_sources(explicit: list[str]) -> list[Source]:
    if explicit:
        sources = []
        for raw in explicit:
            root = Path(raw).expanduser().resolve()
            if not root.is_dir():
                raise DoctorError(f"source root is not a directory: {root}")
            sources.append(Source(name=root.name, root=root))
        return sources

    config = console_config_path()
    if not config.is_file():
        raise DoctorError(
            f"no source configuration at {config}; pass --source PATH explicitly"
        )
    try:
        text = config.read_text(encoding="utf-8")
    except OSError as exc:
        raise DoctorError(f"could not read {config}: {exc}") from exc

    entries = parse_mapping_list(text, "sources")
    if not entries:
        raise DoctorError(f"no sources declared in {config}")

    sources = []
    for entry in entries:
        root_raw = entry.get("root")
        projects_dir = entry.get("projects_dir")
        if not root_raw:
            raise DoctorError(f"a source in {config} declares no root")
        if not projects_dir:
            # Silently dropping a configured source is how a whole repo goes
            # unaudited while the run still prints HEALTHY.
            name_hint = entry.get("name") or root_raw
            raise DoctorError(
                f"source '{name_hint}' declares no projects_dir; remove the "
                "source or give it one so it can be audited"
            )
        root = Path(str(root_raw)).expanduser()
        name = str(entry.get("name") or root.name)
        if not root.is_dir():
            # Fail closed: a configured source we cannot see is unaudited, and
            # an unaudited source must never read as a clean one.
            raise DoctorError(f"source '{name}' root does not exist: {root}")
        sources.append(Source(name=name, root=root, projects_dir=str(projects_dir)))

    if not sources:
        raise DoctorError(f"no sources in {config} declare a projects_dir")
    return sources


# ---------------------------------------------------------------------------
# Git ground truth
# ---------------------------------------------------------------------------


def git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DoctorError(f"git failed in {repo}: {exc}") from exc
    return completed.returncode, completed.stdout.strip()


def last_session_commit(
    repo: Path, projects_root: Path, project_path: Path
) -> tuple[object, str | None]:
    """Date of the newest commit that represents WORK on this project.

    Not simply the newest commit touching it. Repo-wide maintenance — a path
    migration, a bulk restructure, a formatting sweep — touches every project
    at once and says nothing about when any of them was last worked. Treating
    those as sessions makes every dormant project look like its record is
    stale, which is a false alarm, and false alarms are how a guard teaches
    its owner to ignore it.

    A commit counts as session work when it touches at most
    BULK_COMMIT_PROJECT_THRESHOLD distinct projects. If every recent commit is
    a bulk sweep, return None and skip the freshness checks rather than
    guessing.
    """
    code, out = git(
        repo,
        "log",
        f"-{MAX_COMMITS_EXAMINED}",
        "--format=%H %ad",
        "--date=short",
        "--",
        str(project_path),
    )
    if code != 0 or not out:
        return None, None

    try:
        prefix = projects_root.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        # Without the prefix the bulk-commit classifier silently disables
        # itself and every dormant project looks stale. A classifier that
        # cannot locate the projects root is not entitled to a verdict.
        raise DoctorError(
            f"{projects_root} is not inside {repo}; cannot classify commits"
        ) from exc

    for line in out.splitlines():
        sha, _, datestr = line.partition(" ")
        if not sha or not datestr:
            continue
        code, files = git(repo, "show", "--name-only", "--format=", sha)
        if code != 0:
            continue
        touched: set[str] = set()
        for name in files.splitlines():
            name = name.strip()
            if not name:
                continue
            if prefix:
                if not name.startswith(prefix + "/"):
                    continue
                rest = name[len(prefix) + 1 :]
            else:
                rest = name
            segment = rest.split("/", 1)[0]
            if segment and not segment.endswith(".yaml"):
                touched.add(segment)
        outside = sum(
            1
            for name in files.splitlines()
            if name.strip() and prefix and not name.startswith(prefix + "/")
        )
        # Blast radius counts BOTH dimensions: a sweep that rewrites one
        # project plus a hundred files elsewhere is still maintenance.
        if len(touched) > BULK_COMMIT_PROJECT_THRESHOLD or outside > BULK_COMMIT_OUTSIDE_FILES:
            continue
        try:
            return datetime.strptime(datestr.strip(), "%Y-%m-%d").date(), sha
        except ValueError:
            continue
    return UNVERIFIABLE, None


def last_session_commit_date(
    repo: Path, projects_root: Path, project_path: Path
) -> date | None:
    """Date only. Kept because most callers do not need the commit identity."""
    when, _sha = last_session_commit(repo, projects_root, project_path)
    return when


def coverage_report(audits: list[ProjectAudit]) -> dict:
    """Per-check denominators for every lifecycle-gated check.

    The report exists because a check finding nothing and a check examining
    nothing are indistinguishable in a findings list, and so are a suppression
    that is working and one that quietly covers a question nobody replaced.
    An unpaired suppression shipped in v1.7.0 and survived the changelog, the
    skill documentation and review; a printed `skipped 140` would have made
    somebody ask what happens to those 140.

    Only gated checks appear. An ungated check's denominator is every project
    audited, which the report already states.
    """
    counts: dict[str, dict] = {}
    for audit in audits:
        for check in audit.examined:
            counts.setdefault(check, {"examined": 0, "skipped": 0, "reasons": {}})
            counts[check]["examined"] += 1
        for check, reason in audit.skipped:
            counts.setdefault(check, {"examined": 0, "skipped": 0, "reasons": {}})
            counts[check]["skipped"] += 1
            counts[check]["reasons"][reason] = (
                counts[check]["reasons"].get(reason, 0) + 1
            )
    return dict(sorted(counts.items()))


def uncommitted(repo: Path, path: Path) -> list[str]:
    code, out = git(repo, "status", "--porcelain", "--", str(path))
    if code != 0:
        raise DoctorError(f"git status failed in {repo}")
    return [line for line in out.splitlines() if line.strip()]


def push_state(repo: Path, scope: Path | None = None) -> tuple[str, int]:
    """Explicit push state. Never collapses "unknown" into "fine".

    The original version returned None both when the branch had no upstream
    and when git failed, and the caller tested `if ahead:` — so a repo whose
    context had never left the machine reported HEALTHY. That is the exact
    state the durability pillar exists to catch, and it is also git's DEFAULT
    for freshly branched work until the first `git push -u`.

    Returns (state, count) where state is one of: synced, ahead, no-remote,
    no-upstream, detached, unknown.
    """
    code, _ = git(repo, "remote")
    if code != 0:
        return ("unknown", 0)
    _, remotes = git(repo, "remote")
    if not remotes.strip():
        return ("no-remote", 0)

    code, head = git(repo, "symbolic-ref", "--quiet", "HEAD")
    if code != 0 or not head:
        return ("detached", 0)

    code, _ = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code != 0:
        return ("no-upstream", 0)

    args = ["rev-list", "--count", "@{u}..HEAD"]
    if scope is not None:
        args += ["--", str(scope)]
    code, out = git(repo, *args)
    if code != 0 or not out.isdigit():
        return ("unknown", 0)
    count = int(out)
    return ("ahead", count) if count else ("synced", 0)


PUSH_STATE_MESSAGES = {
    "no-remote": (
        "the repository has no remote — this context exists only on this machine",
        "add a remote and push",
    ),
    "no-upstream": (
        "the current branch has no upstream — this context has never left this "
        "machine, so no other agent or computer can resume from it",
        "push with -u to set an upstream",
    ),
    "detached": (
        "HEAD is detached — committed context is not on any branch and will not "
        "be pushed",
        "check out a branch and push",
    ),
    "unknown": (
        "push state could not be determined",
        "check the repository's git state",
    ),
}


def tracked_files(repo: Path, path: Path) -> set[str]:
    code, out = git(repo, "ls-files", "--", str(path))
    if code != 0:
        raise DoctorError(f"git ls-files failed in {repo}")
    return {line for line in out.splitlines() if line.strip()}


# ---------------------------------------------------------------------------
# Project parsing
# ---------------------------------------------------------------------------

# Not anchored to line start. Real records put two fields on one line —
# "**Phase:** Review complete — awaiting send. **Status:** Active (...)" is a
# live example — and an anchored pattern misses the Status there, falls through
# to the Phase fallback, reads "complete" out of the phase text, and reports a
# project as finished that says Active three words later. The value stops at the
# next bold field marker so a trailing field is never swallowed into it.
STATUS_HEADER = re.compile(
    r"\*\*Status\:\*\*\s*(?P<value>.+?)\s*(?=\*\*[A-Z][^*]*\:\*\*|$)", re.MULTILINE
)
PHASE_HEADER = re.compile(
    r"\*\*Phase\:\*\*\s*(?P<value>.+?)\s*(?=\*\*[A-Z][^*]*\:\*\*|$)", re.MULTILINE
)
LAST_SESSION_HEADER = re.compile(
    r"^\*\*Last session\:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE
)
DATE_IN_TEXT = re.compile(r"(\d{4}-\d{2}-\d{2})")
COMPLETED_WORDS = ("complete", "completed", "shipped", "closed", "done",
                   "archived", "superseded")
PAUSED_WORDS = ("paused", "on hold", "parked")

# The canonical project-status vocabulary. Status answers one question -- does
# this claim attention -- and everything orthogonal is a qualifier field
# (bounded, superseded_by, wake_when, blocked_by, completed_date).
CANONICAL_STATUSES = {"active", "paused", "completed", "archived"}

# Statuses that mean the project is over. `superseded` is accepted for corpora
# that have not migrated: it used to be absent here, which meant such a project
# parsed as making no completion claim at all, sat permanently as
# `record-unreadable`, and never got its cross-tier check. `complete` is a
# tolerated typo of `completed` and is reported by the vocabulary check below.
TERMINAL_STATUSES = {"completed", "complete", "archived", "superseded"}

# Statuses under which nobody is working the project. The distinction matters
# because several checks ask questions that only have meaning about work in
# progress: how fresh is the record, are its open items still current, is its
# status header parseable for a cross-check. Asked of a project that shipped in
# May, each of those is unanswerable *and* unactionable — and a guard that emits
# unactionable findings is the fail-open state it exists to prevent. Measured on
# a 175-project corpus before this change: 98% of `freshness-unverifiable` and
# 90% of `record-unreadable` were raised against dormant projects.
DORMANT_STATUSES = TERMINAL_STATUSES | {"paused"}


def project_is_dormant(index_status: str, declared_complete) -> bool:
    """True when no one is working the project, so work-in-progress checks do
    not apply. Errs toward *active*: an unset or unrecognised status is treated
    as live, because suppressing a check on a project whose state we cannot read
    would hide exactly the records most likely to be wrong."""
    if (index_status or "").strip().lower() in DORMANT_STATUSES:
        return True
    return bool(declared_complete)

# Retired values, still readable so an unmigrated corpus is diagnosed rather
# than rejected. The message names what each one should become.
RETIRED_STATUSES = {
    "new": "a Phase, not a lifecycle state -- use active or paused",
    "ongoing": "conflates attention with boundedness -- use active/paused plus `bounded: false`",
    "superseded": "use `archived` plus `superseded_by`",
    "complete": "a typo of `completed`",
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DoctorError(f"{path} is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise DoctorError(f"could not read {path}: {exc}") from exc


def _reads_completed(value: str) -> bool | None:
    """Read one header value. None when it says nothing about completion.

    The leading clause decides when it can. Real headers routinely read
    "Active — Phase 4 is COMPLETE" or "active, essentially complete": the
    author's status verdict is the word before the first delimiter, and the
    completion vocabulary after it describes a sub-part. Scanning the whole
    value first turned every such header into a false status disagreement.
    Only when the leading clause says nothing does the full value get a scan.
    """
    value = value.lower()

    def scan(fragment: str) -> bool | None:
        if re.search(r"\bnot\s+(?:yet\s+)?complete", fragment):
            return False
        if any(re.search(rf"\b{re.escape(w)}\b", fragment) for w in PAUSED_WORDS):
            return False
        active = re.search(r"\bactive\b", fragment)
        completed = None
        for w in COMPLETED_WORDS:
            m = re.search(rf"\b{re.escape(w)}\b", fragment)
            if m:
                completed = m
                break
        if active and completed:
            # Both words present: the earlier one is the author's verdict.
            return active.start() > completed.start()
        if completed:
            return True
        if active:
            return False
        return None

    leading = re.split(r"[—|,;(.]|--", value, maxsplit=1)[0]
    verdict = scan(leading)
    if verdict is not None:
        return verdict
    return scan(value)


def context_declares_completed(text: str) -> bool | None:
    """True/False when the CONTEXT.md header states completion; None if silent.

    Status is authoritative and Phase is only a fallback. They routinely
    disagree in a way that is not a contradiction: a project can be in a
    "Triage — inventory complete" phase while its status is squarely Active.
    Reading both as equals turns that ordinary sentence into a false alarm,
    which is how a doctor teaches its owner to stop reading it.

    Matching is on whole words for the same reason — "complete" inside
    "completeness" or "incomplete" is not a completion claim.
    """
    for match in STATUS_HEADER.finditer(text):
        verdict = _reads_completed(match.group("value"))
        if verdict is not None:
            return verdict
    for match in PHASE_HEADER.finditer(text):
        verdict = _reads_completed(match.group("value"))
        if verdict is not None:
            return verdict
    return None


def context_last_session(text: str) -> date | None:
    match = LAST_SESSION_HEADER.search(text)
    if not match:
        return None
    found = DATE_IN_TEXT.search(match.group("value"))
    if not found:
        return None
    try:
        return datetime.strptime(found.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_date_field(value: object) -> date | None:
    # PyYAML resolves unquoted YYYY-MM-DD to date and timestamps to datetime.
    # datetime is a date subclass, so the isinstance order matters.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    found = DATE_IN_TEXT.search(str(value))
    if not found:
        return None
    try:
        return datetime.strptime(found.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def session_entry_count(sessions_dir: Path) -> int:
    """Distinct session dates across the archive.

    Distinct DATES, not headings: one working day written up as several
    sub-headings is one session, and counting headings inflated it. Any
    heading level counts, because archives in the wild use ## and ### and
    #### interchangeably.
    """
    if not sessions_dir.is_dir():
        return 0
    dates: set[str] = set()
    for path in sorted(sessions_dir.glob("*.md")):
        text = read_text(path)
        for match in re.finditer(
            r"^#{1,6}\s[^\n]*?(\d{4}-\d{2}-\d{2})", text, re.MULTILINE
        ):
            dates.add(match.group(1))
    return len(dates)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

CHECKS = [
    "context-present",
    "context-budget",
    "reference-present",
    "reference-budget",
    "reference-shard",
    "reference-index-budget",
    "reference-index-missing",
    "reference-topic-budget",
    "reference-index-orphan",
    "sessions-present",
    "status-agreement",
    "status-vocabulary",
    "completed-date",
    "last-session-freshness",
    "context-header-freshness",
    "header-currency",
    "body-currency",
    "uncommitted-context",
    "untracked-context",
    "unpushed-context",
    "freshness-unverifiable",
    "terminal-project-active",
    "terminal-project-open-items",
    "post-close-review-unresolvable",
    "record-unreadable",
    "artifact-cites-missing-script",
]


SCRIPT_CITATION = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"(?P<reference>(?:resources/scripts/|\.\./scripts/)"
    r"[A-Za-z0-9_./-]*[A-Za-z0-9_-])"
)


def cited_script_findings(project_path: Path) -> list[tuple[Path, str, str]]:
    """Return artifact citations whose executable target is not durable.

    This is deliberately an existence and boundary check. A regular file at
    the cited path is not evidence that the code is correct or reproducible.
    """

    artifacts = project_path / "resources" / "artifacts"
    scripts = project_path / "resources" / "scripts"
    if not artifacts.is_dir():
        return []

    scripts_lexical = Path(os.path.abspath(os.fspath(scripts)))
    findings: list[tuple[Path, str, str]] = []
    seen: set[tuple[Path, str]] = set()
    for artifact in sorted(artifacts.glob("*.md")):
        if not artifact.is_file() or artifact.is_symlink():
            continue
        for match in SCRIPT_CITATION.finditer(read_text(artifact)):
            reference = match.group("reference")
            key = (artifact, reference)
            if key in seen:
                continue
            seen.add(key)
            if reference.startswith("resources/scripts/"):
                candidate = project_path / reference
            else:
                candidate = artifact.parent / reference
            candidate_lexical = Path(os.path.abspath(os.fspath(candidate)))

            try:
                relative = candidate_lexical.relative_to(scripts_lexical)
            except ValueError:
                findings.append((artifact, reference, "escapes resources/scripts/"))
                continue

            cursor = scripts_lexical
            unsafe = cursor.is_symlink()
            for part in relative.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    unsafe = True
                    break
            if unsafe:
                findings.append((artifact, reference, "traverses a symlink"))
            elif candidate_lexical.is_dir():
                # A citation to a DIRECTORY of scripts is legitimate and common:
                # "the portable hooks live here" is how a multi-file tool is
                # referenced. What this check exists to catch is a citation to
                # something that was not preserved, and a directory holding
                # files satisfies that completely. An EMPTY one does not — it
                # is the same failure as a missing file wearing a folder.
                if not any(candidate_lexical.iterdir()):
                    findings.append((artifact, reference, "is an empty directory"))
            elif not candidate_lexical.is_file():
                findings.append((artifact, reference, "is not a regular file"))
    return findings


INTAKE_NAME = re.compile(r"(intake|brief|directive|catalogue)", re.IGNORECASE)
ROUTING_MARKER = re.compile(
    r"^\*\*(Routed|Declined|Superseded):\*\*", re.MULTILINE
)


def unrouted_intake_findings(project_path: Path) -> list[str]:
    """Intake-class artifacts that no numbered work ever consumed.

    The failure this catches: a directive arrives, gets captured in an
    artifact, is endorsed in prose — and never becomes a numbered CONTEXT
    item, a declination, or a supersession, so nothing ships and nothing
    warns. Coverage is mechanical (the R-03 lane rule: the script narrows,
    the model judges): an intake-named artifact is covered when CONTEXT.md
    mentions its filename, or when the file itself carries a terminal
    routing marker line (**Routed:** / **Declined:** / **Superseded:**).
    Whether a recorded routing is honest stays a judgment for the reader.
    """

    artifacts = project_path / "resources" / "artifacts"
    if not artifacts.is_dir():
        return []
    context_text = read_text(project_path / "CONTEXT.md")
    unrouted: list[str] = []
    for artifact in sorted(artifacts.glob("*.md")):
        if not artifact.is_file() or artifact.is_symlink():
            continue
        if not INTAKE_NAME.search(artifact.name):
            continue
        if artifact.name in context_text:
            continue
        if ROUTING_MARKER.search(read_text(artifact)):
            continue
        unrouted.append(artifact.name)
    return unrouted


def audit_project(
    source: Source,
    project_id: str,
    project_path: Path,
    index_entry: dict | None,
    repo_root: Path,
    projects_root: Path,
    readiness: str = "remote",
) -> ProjectAudit:
    audit = ProjectAudit(source=source.name, project_id=project_id, path=project_path)

    context_path = project_path / "CONTEXT.md"
    reference_path = project_path / "REFERENCE.md"
    sessions_dir = project_path / "sessions"

    # --- tier structure -----------------------------------------------------
    if not context_path.is_file():
        audit.add(
            "context-present",
            "defect",
            "no CONTEXT.md — a cold resumption has no working memory to read",
            f"create {context_path.name} from the tiered-architecture template",
        )
        return audit  # every remaining check reads CONTEXT.md

    context_text = read_text(context_path)
    context_lines = len(context_text.splitlines())

    if not context_text.strip():
        audit.add(
            "context-present",
            "defect",
            "CONTEXT.md is empty — the file existing is not the same as working "
            "memory existing",
            "write the working context, or remove the placeholder file",
        )
    elif not re.search(r"^#{1,6}\s", context_text, re.MULTILINE):
        audit.add(
            "context-present",
            "warning",
            "CONTEXT.md has no headings — it may be a placeholder",
            "fill in the tiered-architecture template",
        )
    declared_complete = context_declares_completed(context_text)

    index_status = str((index_entry or {}).get("status") or "").strip().lower()
    index_says_completed = index_status in TERMINAL_STATUSES

    # Budget depends on which lifecycle stage the project is actually in.
    treat_completed = index_says_completed or bool(declared_complete)
    # Computed here rather than at the freshness block, because the tier and
    # budget checks below need it too. Same rule, same errs-toward-live default.
    dormant = project_is_dormant(index_status, declared_complete)
    budget = CONTEXT_BUDGET_COMPLETED if treat_completed else CONTEXT_BUDGET_ACTIVE
    if context_lines > budget:
        audit.add(
            "context-budget",
            "defect",
            f"CONTEXT.md is {context_lines} lines, over the "
            f"{'completed' if treat_completed else 'active'} budget of {budget}",
            "archive cold content to sessions/ and stable facts to REFERENCE.md, "
            "then trim CONTEXT.md",
        )

    entries = session_entry_count(sessions_dir)

    # The same lifecycle rule the freshness checks got in v1.7.0, applied to the
    # tier-structure and budget checks it missed. "Move your session narrative
    # into an archive" and "your scope may be too broad" are instructions to
    # someone doing the work. Measured on the corpus before this gate: 11 of 11
    # sessions-present and 5 of 5 reference-budget findings were raised against
    # dormant projects — the identical shape as the v1 diagnosis, one release
    # later, on the checks that release did not touch.
    # reference-present belongs to this family too, and leaving one member
    # ungated is the same inconsistency this gate exists to remove. "Extract
    # your stable facts into REFERENCE.md" asks somebody to restructure a
    # record whose work is over; for a finished project the CONTEXT and the
    # session archive already hold everything a later reader needs, and a
    # reference file would be a duplicate of them.
    for check in ("sessions-present", "reference-budget", "reference-present"):
        audit.skip(check, "dormant") if dormant else audit.cover(check)

    if not sessions_dir.is_dir() and not dormant:
        # Only a defect once there is history to archive; a brand-new project
        # legitimately has none.
        if context_lines > CONTEXT_BUDGET_COMPLETED:
            audit.add(
                "sessions-present",
                "warning",
                "no sessions/ archive, but the project has accumulated history",
                "create sessions/YYYY-MM.md and move session narrative there",
            )

    if (
        not reference_path.is_file()
        and entries >= REFERENCE_EXPECTED_AFTER_SESSIONS
        and not dormant
    ):
        audit.add(
            "reference-present",
            "defect",
            f"no REFERENCE.md after {entries} recorded sessions — stable facts "
            "are living in working memory or only in the archive",
            "extract paths, commands, conventions, and rosters into REFERENCE.md "
            "(write it first, verify, then trim CONTEXT.md)",
        )

    # --- semantic tier: one file, or an index over reference/ ---------------
    # `bounded` defaults to True when unset. That keeps every existing project's
    # behaviour identical and changes it only where a project has explicitly
    # declared itself standing, so adoption costs nothing and means something.
    is_standing = (index_entry or {}).get("bounded") is False
    reference_dir = project_path / "reference"

    if reference_dir.is_dir():
        # Sharded: REFERENCE.md is the index, not the content.
        if reference_path.is_file():
            index_text = read_text(reference_path)
            index_lines = len(index_text.splitlines())
            if index_lines > REFERENCE_INDEX_BUDGET:
                audit.add(
                    "reference-index-budget",
                    "warning",
                    f"REFERENCE.md is {index_lines} lines, over the "
                    f"{REFERENCE_INDEX_BUDGET}-line index budget — once a project "
                    "shards, REFERENCE.md is a map of reference/, not content",
                    "move the prose into a reference/ topic file and leave a "
                    "one-line pointer in the index",
                )
        else:
            index_text = ""
            audit.add(
                "reference-index-missing",
                "defect",
                "reference/ exists with no REFERENCE.md index — the topic files "
                "are unreachable from the project's entry point",
                "write REFERENCE.md as an index linking every reference/ topic",
            )
        for topic in sorted(reference_dir.glob("*.md")):
            if not topic.is_file():
                continue
            topic_lines = len(read_text(topic).splitlines())
            if topic_lines > REFERENCE_TOPIC_BUDGET:
                audit.add(
                    "reference-topic-budget",
                    "warning",
                    f"reference/{topic.name} is {topic_lines} lines, over the "
                    f"soft budget of {REFERENCE_TOPIC_BUDGET}",
                    "split the topic, or move narrative into sessions/",
                )
            # An unlinked topic file is the shard's version of losing content:
            # it exists, it is not reachable from the entry point, and nothing
            # else in the system would notice.
            if topic.name not in index_text:
                audit.add(
                    "reference-index-orphan",
                    "warning",
                    f"reference/{topic.name} is not linked from REFERENCE.md — a "
                    "topic nothing points at is unreachable from session start",
                    "add it to the REFERENCE.md index",
                )
    elif reference_path.is_file() and not dormant:
        ref_lines = len(read_text(reference_path).splitlines())
        if ref_lines > REFERENCE_BUDGET:
            if is_standing:
                # For a seat, breadth is the point. The wall is the file, not
                # the scope, so the remedy is to shard rather than to split.
                audit.add(
                    "reference-shard",
                    "warning",
                    f"REFERENCE.md is {ref_lines} lines, over {REFERENCE_BUDGET}. "
                    "This project is declared standing (`bounded: false`), so its "
                    "reference is expected to grow — it has outgrown one file",
                    "shard into reference/<topic>.md and leave REFERENCE.md as "
                    "the index",
                )
            else:
                audit.add(
                    "reference-budget",
                    "warning",
                    f"REFERENCE.md is {ref_lines} lines, over the soft budget of "
                    f"{REFERENCE_BUDGET} — the project's scope may be too broad",
                    "split the project, move narrative into sessions/, or — if "
                    "the breadth is real — declare `bounded: false` and shard "
                    "into reference/",
                )

    # --- executable working-state durability ------------------------------
    for artifact, citation, reason in cited_script_findings(project_path):
        audit.add(
            "artifact-cites-missing-script",
            "warning",
            f"{artifact.name} cites {citation}, but that target {reason}",
            "preserve the portable script and every required input under "
            "resources/scripts/, then update the artifact citation; this check "
            "establishes existence only and does not prove the script is correct",
        )

    # --- intake routing coverage ------------------------------------------
    # A captured directive that never becomes numbered work is the failure
    # that happens by default: the artifact looks handled because it exists.
    for intake_name in unrouted_intake_findings(project_path):
        audit.add(
            "intake-routing",
            "warning",
            f"{intake_name} is an intake-class artifact that CONTEXT.md never "
            "references and that carries no routing marker — its asks may "
            "have fallen through",
            "route it to a numbered CONTEXT item, or add a terminal "
            "'**Routed:**' / '**Declined:**' / '**Superseded:**' line to the "
            "artifact stating where its asks went and why",
        )

    # --- cross-tier agreement ----------------------------------------------
    if index_entry is None:
        audit.add(
            "status-agreement",
            "defect",
            "project directory exists but has no entry in index.yaml — it is "
            "invisible to project discovery",
            "add the project to projects/index.yaml",
        )
    else:
        if declared_complete is None:
            # The cross-check this enables only protects a project someone is
            # working. On a dormant one it asks an author who has moved on to
            # go back and annotate a finished record, which is why 90% of these
            # sat unactioned. Kept as a finding wherever the project is live.
            if (index_status or "").strip().lower() not in DORMANT_STATUSES:
                audit.add(
                    "record-unreadable",
                    "warning",
                    "CONTEXT.md has no parseable Status or Phase header, so its "
                    "status cannot be cross-checked against index.yaml",
                    "add a '**Status:** Active' (or Completed/Paused) header",
                )
        elif declared_complete != index_says_completed:
            ctx_word = "completed" if declared_complete else "active"
            audit.add(
                "status-agreement",
                "defect",
                f"CONTEXT.md reads {ctx_word} but index.yaml says "
                f"'{index_status or 'unset'}' — session start reports one and the "
                "record says the other",
                "decide the real status and set both",
            )
        if index_status and index_status not in CANONICAL_STATUSES:
            became = RETIRED_STATUSES.get(index_status)
            if became:
                audit.add(
                    "status-vocabulary",
                    "warning",
                    f"index.yaml status `{index_status}` is retired -- {became}",
                    "migrate the entry to the canonical vocabulary "
                    f"{sorted(CANONICAL_STATUSES)}",
                )
            else:
                audit.add(
                    "status-vocabulary",
                    "defect",
                    f"index.yaml status `{index_status}` is not a known status -- "
                    "an unrecognised status silently disables the checks that key "
                    "off it",
                    f"use one of {sorted(CANONICAL_STATUSES)}",
                )

        if index_says_completed and not (index_entry or {}).get("completed_date"):
            audit.add(
                "completed-date",
                "warning",
                "index.yaml marks the project completed with no completed_date",
                "add completed_date: 'YYYY-MM-DD'",
            )

    # --- freshness against git ---------------------------------------------
    newest, newest_sha = last_session_commit(repo_root, projects_root, project_path)

    if newest is UNVERIFIABLE:
        # Only meaningful for a project someone is working. "We cannot tell when
        # this shipped-in-May post was last touched" is true and useless.
        if not dormant:
            audit.add(
                "freshness-unverifiable",
                "warning",
                f"every one of the last {MAX_COMMITS_EXAMINED} commits touching "
                "this project is a repo-wide sweep, so its record cannot be "
                "checked against real session history",
                "commit session work in project-scoped commits so freshness is "
                "verifiable",
            )
    elif newest and dormant and index_says_completed:
        # The inversion, and the reason suppressing the above is safe: a project
        # declared finished that is still receiving real session commits is a
        # live record error, and it is the one freshness question worth asking
        # about a terminal project.
        #
        # Anchor on completed_date, not last_session. Closing a project is
        # itself work — the archive pass, the trim to budget — and those commits
        # land after its final *working* session by design. Against last_session
        # they read as "still being worked," which is the opposite of what they
        # are. Reading the nine findings this check first raised, two were
        # exactly that: every commit fell on the completion date itself. The
        # question worth asking is whether work continued *after* the project
        # said it was finished.
        entry = index_entry or {}
        anchor_field = "completed_date"
        anchor = parse_date_field(entry.get("completed_date"))
        if anchor is None:
            # Missing or unparseable — already its own warning above. Fall back
            # rather than fall silent: an unreadable record is the one most
            # likely to be wrong.
            anchor_field = "last_session"
            anchor = parse_date_field(entry.get("last_session"))
        # The acknowledgment. Without it this finding is self-sustaining: the
        # commits that carry out a disposition — the archive pass, the trim to
        # budget, the routing note — are themselves post-completed_date commits,
        # so resolving the finding re-creates it and no amount of correct work
        # ever clears it. Two live instances produced this field on the day the
        # check shipped.
        #
        # It lives in index.yaml and NOT in the project directory, and that is a
        # correctness requirement rather than a preference: the freshness walk is
        # `git log -- <project_path>`, so a marker written inside the project
        # would re-extend newest-commit by the act of writing it and re-trigger
        # the very check it answers. index.yaml is outside that path.
        #
        # A sha, not a date. A date over-covers by up to a day — two disposition
        # commits thirteen minutes apart, one either side of a recorded review
        # date, and the second is silently swallowed. And a sha that no longer
        # resolves fails LOUDLY below, where a stale date would just keep
        # quietly asserting a review of history that has since been rewritten.
        acknowledged = False
        reviewed = str(entry.get("post_close_reviewed_through") or "").strip()
        if reviewed:
            code, _ = git(repo_root, "cat-file", "-e", f"{reviewed}^{{commit}}")
            if code != 0:
                audit.add(
                    "post-close-review-unresolvable",
                    "defect",
                    f"post_close_reviewed_through is {reviewed}, which is not a "
                    "commit in this repository — the acknowledgment cannot be "
                    "checked, so it is not honoured",
                    "re-review the commits after completed_date and record the "
                    "sha of the newest one, or remove the field",
                )
            elif newest_sha:
                covered, _ = git(
                    repo_root, "merge-base", "--is-ancestor", newest_sha, reviewed
                )
                # Honoured only while every project commit is an ancestor of the
                # reviewed sha. One new commit and the question re-arms itself,
                # which is the property that keeps this an acknowledgment rather
                # than a mute button.
                if covered == 0:
                    acknowledged = True
                    audit.skip("terminal-project-active", "post-close review")

        if not acknowledged and anchor and (newest - anchor).days > LAST_SESSION_TOLERANCE_DAYS:
            audit.add(
                "terminal-project-active",
                "warning",
                f"index.yaml marks this project completed, but it has session "
                f"commits through {newest} ({anchor_field} says {anchor}) — "
                "either the work resumed or the status is wrong",
                "reopen the project (status: active), or record that you read "
                "the commits after completed_date and they were maintenance, "
                f"with post_close_reviewed_through: '{newest_sha or '<sha>'}'",
            )
    elif newest and not treat_completed:
        idx_last = parse_date_field((index_entry or {}).get("last_session"))
        if idx_last and (newest - idx_last).days > LAST_SESSION_TOLERANCE_DAYS:
            audit.add(
                "last-session-freshness",
                "defect",
                f"index.yaml last_session is {idx_last} but the project's newest "
                f"commit is {newest} — the record is stale",
                "update last_session to match the real history",
            )
        ctx_last = context_last_session(context_text)
        if ctx_last and (newest - ctx_last).days > LAST_SESSION_TOLERANCE_DAYS:
            audit.add(
                "context-header-freshness",
                "defect",
                f"CONTEXT.md header says {ctx_last} but the project's newest "
                f"commit is {newest} — working memory is behind the work",
                "refresh CONTEXT.md and its Last session header",
            )

    # --- header and body currency -------------------------------------------
    # "Records agree with git" means committed, not current: a header or a
    # Current-State section can describe an older state than the session log
    # records — same day, so the date checks above see nothing — while every
    # file is committed. Header fields are judged separately (a union let a
    # fresh Phase mask a stale Last session), and body sections are judged by
    # their '*State as of:*' markers, because header freshness is necessary
    # but not sufficient: a current header above stale operational sections is
    # a stronger false receipt than an obviously stale file.
    for finding in context_currency.audit_project(project_path):
        kind = finding["kind"]
        if kind in ("header-behind-log", "header-field-stale"):
            audit.add(
                "header-currency",
                "defect",
                finding["detail"],
                "update the stale header field with context_edit.py set-field",
            )
        elif kind == "body-marker-stale":
            audit.add(
                "body-currency",
                "defect",
                finding["detail"],
                "rewrite the section for current state, then advance its "
                "'*State as of:*' marker in the same edit",
            )
        elif kind == "body-marker-absent":
            # "Body currency is unverifiable" is a live-project question. On a
            # finished record the body is not supposed to be current, it is
            # supposed to be final, and adding markers to assert a re-check
            # nobody performed would be the same fiction the item-currency
            # suppression already refuses.
            if dormant:
                continue
            audit.add(
                "body-currency",
                "warning",
                finding["detail"],
                "add '*State as of:*' markers to Current State and What's "
                "Next per the tiered-context template",
            )
        elif kind in (
            "item-marker-stale",
            "item-marker-absent",
            "item-marker-malformed",
        ):
            # An open-items list in a dormant project is a record of what was
            # open when work stopped, not a live queue. Re-dating it would be
            # fiction: nobody re-checked those items, and stamping them would
            # assert that somebody did.
            #
            # This suppression shipped in v1.7.0 with no paired check, in the
            # release whose own headline principle forbids exactly that. The
            # pairing is below: the question that becomes applicable is not
            # whether a finished project's items are FRESH, it is whether a
            # project claiming to be finished should be listing obligations at
            # all. 24 such items across 6 projects were invisible until it existed.
            if dormant:
                audit.skip("item-currency", "dormant")
                continue
            audit.cover("item-currency")
            # Warnings, not defects, and deliberately so: item stamping is a new
            # convention, and turning an entire corpus red on the day it lands
            # is how a guard teaches people to route around it. These surface in
            # the integrity line and the session-start reading without blocking
            # a session end, which stays reserved for structural defects.
            audit.add(
                "item-currency",
                "warning",
                finding["detail"],
                "re-date the item with '(as of YYYY-MM-DD, review Nd)' once "
                "you have checked it, or close it out into sessions/ — an "
                "item whose age is unverifiable cannot be trusted as current",
            )

    # --- the inversion that pairs the item-currency suppression --------------
    # Asked only of a terminal project, and only about obligations: a finished
    # project that still lists things it owes is either not finished, or its
    # record is carrying a queue it should have closed out into sessions/.
    # Either way it is a live record error, and it was unaskable before.
    if dormant and index_says_completed:
        owed = context_currency.open_obligation_count(context_text)
        if owed:
            audit.add(
                "terminal-project-open-items",
                "warning",
                f"index.yaml marks this project completed, but its CONTEXT.md "
                f"still lists {owed} unchecked obligation(s) under an "
                "open-items heading — a finished project should not owe work",
                "close them out into sessions/ as the record of what was open "
                "at close, hand them to the project that inherited them, or "
                "reopen this one",
            )

    # --- durability ---------------------------------------------------------
    dirty = uncommitted(repo_root, project_path)
    if dirty:
        audit.add(
            "uncommitted-context",
            "defect" if readiness == "remote" else "warning",
            f"{len(dirty)} uncommitted file(s) under the project — same-machine "
            "continuity is available, but this project is not REMOTE_READY",
            "run the explicit remote-handoff sync before changing computers",
        )

    # A clean `git status` says nothing about a file git was never told to
    # track: an ignored, excluded, or symlinked-out CONTEXT.md is invisible to
    # status and equally invisible to the next machine.
    tracked = tracked_files(repo_root, project_path)
    for tier in (context_path, reference_path):
        if not tier.is_file():
            continue
        try:
            rel = tier.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            audit.add(
                "untracked-context",
                "defect",
                f"{tier.name} resolves outside the repository — it cannot be "
                "committed or pushed with the project",
                "move the file inside the repository",
            )
            continue
        if rel not in tracked:
            audit.add(
                "untracked-context",
                "defect",
                f"{tier.name} is not tracked by git (ignored, excluded, or never "
                "added) — it will not reach any other machine",
                f"git add {rel}",
            )

    return audit


def durability_findings(
    source_name: str,
    repo_root: Path,
    projects_root: Path,
    readiness: str = "remote",
) -> list[Finding]:
    """Repo-level durability, shared by whole-source and single-project runs.

    Single-project mode used to skip this entirely, so `--project` could never
    fail on undurable context — a gap in the mode most likely to be wired into
    a session-end gate.
    """
    findings: list[Finding] = []

    state, count = push_state(repo_root, projects_root)
    if state == "ahead":
        findings.append(
            Finding(
                project="(repository)",
                source=source_name,
                check="unpushed-context",
                severity="defect" if readiness == "remote" else "warning",
                message=f"{count} commit(s) touching project context are not "
                "pushed — another machine or agent cannot see this context yet",
                remedy="push the branch",
            )
        )
    elif state in PUSH_STATE_MESSAGES:
        message, remedy = PUSH_STATE_MESSAGES[state]
        findings.append(
            Finding(
                project="(repository)",
                source=source_name,
                check="unpushed-context",
                severity="defect" if readiness == "remote" else "warning",
                message=message,
                remedy=remedy,
            )
        )

    # index.yaml lives beside the projects, not inside one, so a per-project
    # status check never sees it.
    index_dirty = uncommitted(repo_root, projects_root / "index.yaml")
    if index_dirty:
        findings.append(
            Finding(
                project="(source)",
                source=source_name,
                check="uncommitted-context",
                severity="defect" if readiness == "remote" else "warning",
                message="projects/index.yaml has uncommitted changes",
                remedy="commit and push index.yaml",
            )
        )

    return findings


def audit_source(
    source: Source, readiness: str = "remote"
) -> tuple[list[ProjectAudit], list[Finding]]:
    source_findings: list[Finding] = []
    projects_root = source.projects_root

    # A state the doctor can determine is a finding, not a crash. Only an
    # inability to establish ground truth (unreadable config, no git, unparsable
    # YAML) raises DoctorError — that distinction is what keeps "cannot run"
    # meaningfully different from "ran and found problems".
    if not projects_root.is_dir():
        # An unaudited source must never read as a clean one. This is a
        # cannot-establish-ground-truth state, not a stylistic warning.
        raise DoctorError(
            f"source '{source.name}' declares {projects_root}, which does not "
            "exist — the source cannot be audited"
        )

    code, repo_out = git(projects_root, "rev-parse", "--show-toplevel")
    if code != 0 or not repo_out:
        raise DoctorError(f"source '{source.name}' is not inside a git repository")
    repo_root = Path(repo_out)

    index_path = projects_root / "index.yaml"
    index_by_id: dict[str, dict] = {}

    has_projects = any(
        child.is_dir() and not child.name.startswith((".", "_"))
        for child in projects_root.iterdir()
    )
    if not index_path.is_file():
        if has_projects:
            source_findings.append(
                Finding(
                    project="(source)",
                    source=source.name,
                    check="status-agreement",
                    severity="defect",
                    message="has project directories but no projects/index.yaml — "
                    "nothing can discover them",
                    remedy="create index.yaml listing the projects",
                )
            )
        else:
            return [], source_findings
        entries: list[dict] = []
    else:
        entries = parse_mapping_list(read_text(index_path), "projects")
    if not entries and index_path.is_file():
        # index.yaml may list projects at the document root rather than under a
        # 'projects:' key; try the root-list shape before declaring it empty.
        entries = _root_list_entries(read_text(index_path))
    for entry in entries:
        pid = entry.get("id")
        if pid:
            index_by_id[str(pid)] = entry

    audits: list[ProjectAudit] = []
    seen: set[str] = set()

    for child in sorted(projects_root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        seen.add(child.name)
        audits.append(
            audit_project(
                source,
                child.name,
                child,
                index_by_id.get(child.name),
                repo_root,
                projects_root,
                readiness,
            )
        )

    for pid, entry in index_by_id.items():
        if pid in seen:
            continue
        status = str(entry.get("status") or "").lower()
        if status in {"archived", "cancelled", "canceled"}:
            continue
        source_findings.append(
            Finding(
                project=pid,
                source=source.name,
                check="context-present",
                severity="defect",
                message="index.yaml lists this project but no directory exists",
                remedy="create the project directory, or archive the index entry",
            )
        )

    source_findings.extend(
        durability_findings(source.name, repo_root, projects_root, readiness)
    )

    return audits, source_findings


def _root_list_entries(text: str) -> list[dict]:
    """index.yaml written as a bare top-level list of project mappings."""
    if _HAVE_YAML:
        try:
            return _entries_from_loaded(yaml.safe_load(text), "")
        except yaml.YAMLError as exc:
            raise DoctorError(f"could not parse index.yaml: {exc}") from exc
    return [e for e in _fallback_mapping_list(text, "") if "id" in e]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_human(
    findings: list[Finding],
    audited: int,
    sources: int,
    coverage: dict | None = None,
) -> str:
    lines = [f"synthesis context doctor {DOCTOR_VERSION}"]
    for check, c in (coverage or {}).items():
        if not c["skipped"]:
            continue
        why = ", ".join(f"{n} {r}" for r, n in sorted(c["reasons"].items()))
        lines.append(
            f"  coverage  {check}: examined {c['examined']}, "
            f"skipped {c['skipped']} ({why})"
        )
    if not findings:
        lines.append(
            f"  ok  {audited} project(s) across {sources} source(s): tiers "
            "complete, records agree with git, nothing uncommitted"
        )
        lines.append("HEALTHY: the durable context layer is verifiable.")
        return "\n".join(lines)

    ordered = sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.source, f.project, f.check),
    )
    current_key = None
    for finding in ordered:
        key = (finding.source, finding.project)
        if key != current_key:
            lines.append(f"\n  {finding.source} / {finding.project}")
            current_key = key
        mark = "FAIL" if finding.severity == "defect" else "warn"
        lines.append(f"    {mark}  [{finding.check}] {finding.message}")
        lines.append(f"          -> {finding.remedy}")

    defects = sum(1 for f in findings if f.severity == "defect")
    warnings = len(findings) - defects
    lines.append(
        f"\nDEFECTS: {defects} defect(s), {warnings} warning(s) across "
        f"{audited} project(s) in {sources} source(s)."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="PATH",
        help="audit this source root (repeatable); defaults to console.yaml",
    )
    parser.add_argument(
        "--project",
        metavar="PATH",
        help="audit a single project directory instead of whole sources",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--quiet", action="store_true", help="one summary line plus the exit code"
    )
    parser.add_argument(
        "--no-report-cache",
        action="store_true",
        help="do not write the corpus report cache after a full run",
    )
    parser.add_argument(
        "--warnings-as-defects",
        action="store_true",
        help="exit non-zero on warnings too",
    )
    parser.add_argument(
        "--readiness",
        choices=("local", "remote"),
        default="remote",
        help=(
            "local accepts recoverable same-machine Git state as warnings; "
            "remote requires committed and pushed context"
        ),
    )
    args = parser.parse_args(argv)

    try:
        audits: list[ProjectAudit] = []
        findings: list[Finding] = []

        if args.project:
            project_path = Path(args.project).expanduser().resolve()
            if not project_path.is_dir():
                raise DoctorError(f"not a directory: {project_path}")
            projects_root = project_path.parent
            code, repo_out = git(projects_root, "rev-parse", "--show-toplevel")
            if code != 0 or not repo_out:
                raise DoctorError(f"{project_path} is not inside a git repository")
            repo_root = Path(repo_out)
            source = Source(name=projects_root.parent.name, root=projects_root.parent)
            index_path = projects_root / "index.yaml"
            entry = None
            if index_path.is_file():
                text = read_text(index_path)
                entries = parse_mapping_list(text, "projects") or _root_list_entries(
                    text
                )
                for item in entries:
                    if str(item.get("id")) == project_path.name:
                        entry = item
                        break
            audits.append(
                audit_project(
                    source,
                    project_path.name,
                    project_path,
                    entry,
                    repo_root,
                    projects_root,
                    args.readiness,
                )
            )
            findings.extend(
                durability_findings(
                    source.name, repo_root, projects_root, args.readiness
                )
            )
            source_count = 1
        else:
            sources = discover_sources(args.source)
            source_count = len(sources)
            for source in sources:
                src_audits, src_findings = audit_source(source, args.readiness)
                audits.extend(src_audits)
                findings.extend(src_findings)

        for audit in audits:
            findings.extend(audit.findings)

    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # The contract says exit 2 when ground truth cannot be established.
        # An escaping traceback exits 1, which callers read as "found defects".
        exc = DoctorError(f"unexpected failure while auditing: {exc}")
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"context doctor CANNOT RUN: {exc}", file=sys.stderr)
        return 2
    except DoctorError as exc:
        # Fail closed: the doctor could not establish ground truth, so it must
        # not report health. Exit 2 is distinguishable from "found defects".
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"context doctor CANNOT RUN: {exc}", file=sys.stderr)
        return 2

    defects = [f for f in findings if f.severity == "defect"]
    warnings = [f for f in findings if f.severity == "warning"]
    failed = bool(defects) or (args.warnings_as_defects and bool(warnings))

    payload = {
        "ok": not failed,
        "doctor_version": DOCTOR_VERSION,
        "readiness": args.readiness,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "coverage": coverage_report(audits),
        "sources": source_count,
        "projects_audited": len(audits),
        "defects": len(defects),
        "warnings": len(warnings),
        "findings": [f.as_dict() for f in findings],
    }
    if not args.project and not args.source and not args.no_report_cache:
        # Only full CONFIG-DISCOVERED runs refresh the cache. Explicit
        # --source runs are partial by construction (a fixture, one repo, a
        # test), and single-project runs are narrower still — neither may
        # masquerade as corpus state. This rule exists because the first
        # thing to overwrite the real cache was this tool's own test suite.
        try:
            cache = report_cache_path()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"warning: could not write report cache: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(payload, indent=2))
    elif args.quiet:
        if failed:
            print(
                f"context doctor: {len(defects)} defect(s), {len(warnings)} "
                f"warning(s) across {len(audits)} project(s)"
            )
        else:
            print(f"context doctor: {len(audits)} project(s) healthy")
    else:
        print(render_human(findings, len(audits), source_count, payload["coverage"]))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

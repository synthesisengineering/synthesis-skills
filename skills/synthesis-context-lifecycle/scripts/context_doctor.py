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
  durability       no uncommitted context files; tier files are TRACKED by git,
                   not merely clean; a remote and upstream exist and the branch
                   is pushed, because context that exists on one machine is not
                   durable context
  disclosure       anything the doctor could not verify is reported, never
                   silently skipped: unreadable records and freshness that
                   cannot be established both surface as findings

Usage:
    context_doctor.py                    # audit every source in console.yaml
    context_doctor.py --source PATH ...  # audit explicit source roots
    context_doctor.py --project PATH     # audit one project directory
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

DOCTOR_VERSION = "1.2.2"

# Budgets from the tiered context architecture.
CONTEXT_BUDGET_ACTIVE = 150
CONTEXT_BUDGET_COMPLETED = 80
REFERENCE_BUDGET = 300

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

    def add(self, check: str, severity: str, message: str, remedy: str) -> None:
        self.findings.append(
            Finding(self.project_id, self.source, check, severity, message, remedy)
        )


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


def last_session_commit_date(
    repo: Path, projects_root: Path, project_path: Path
) -> date | None:
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
        return None

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
            return datetime.strptime(datestr.strip(), "%Y-%m-%d").date()
        except ValueError:
            continue
    return UNVERIFIABLE


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

STATUS_HEADER = re.compile(r"^\*\*Status\:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE)
PHASE_HEADER = re.compile(r"^\*\*Phase\:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE)
LAST_SESSION_HEADER = re.compile(
    r"^\*\*Last session\:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE
)
DATE_IN_TEXT = re.compile(r"(\d{4}-\d{2}-\d{2})")
COMPLETED_WORDS = ("complete", "completed", "shipped", "closed", "done")
PAUSED_WORDS = ("paused", "on hold", "parked")


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
    "sessions-present",
    "status-agreement",
    "completed-date",
    "last-session-freshness",
    "context-header-freshness",
    "uncommitted-context",
    "untracked-context",
    "unpushed-context",
    "freshness-unverifiable",
    "record-unreadable",
]


def audit_project(
    source: Source,
    project_id: str,
    project_path: Path,
    index_entry: dict | None,
    repo_root: Path,
    projects_root: Path,
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
    index_says_completed = index_status in {"completed", "complete", "archived"}

    # Budget depends on which lifecycle stage the project is actually in.
    treat_completed = index_says_completed or bool(declared_complete)
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

    if not sessions_dir.is_dir():
        # Only a defect once there is history to archive; a brand-new project
        # legitimately has none.
        if context_lines > CONTEXT_BUDGET_COMPLETED:
            audit.add(
                "sessions-present",
                "warning",
                "no sessions/ archive, but the project has accumulated history",
                "create sessions/YYYY-MM.md and move session narrative there",
            )

    if not reference_path.is_file() and entries >= REFERENCE_EXPECTED_AFTER_SESSIONS:
        audit.add(
            "reference-present",
            "defect",
            f"no REFERENCE.md after {entries} recorded sessions — stable facts "
            "are living in working memory or only in the archive",
            "extract paths, commands, conventions, and rosters into REFERENCE.md "
            "(write it first, verify, then trim CONTEXT.md)",
        )

    if reference_path.is_file():
        ref_lines = len(read_text(reference_path).splitlines())
        if ref_lines > REFERENCE_BUDGET:
            audit.add(
                "reference-budget",
                "warning",
                f"REFERENCE.md is {ref_lines} lines, over the soft budget of "
                f"{REFERENCE_BUDGET} — the project's scope may be too broad",
                "split the project, or move narrative into sessions/",
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
        if index_says_completed and not (index_entry or {}).get("completed_date"):
            audit.add(
                "completed-date",
                "warning",
                "index.yaml marks the project completed with no completed_date",
                "add completed_date: 'YYYY-MM-DD'",
            )

    # --- freshness against git ---------------------------------------------
    newest = last_session_commit_date(repo_root, projects_root, project_path)
    if newest is UNVERIFIABLE:
        audit.add(
            "freshness-unverifiable",
            "warning",
            f"every one of the last {MAX_COMMITS_EXAMINED} commits touching this "
            "project is a repo-wide sweep, so its record cannot be checked "
            "against real session history",
            "commit session work in project-scoped commits so freshness is "
            "verifiable",
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

    # --- durability ---------------------------------------------------------
    dirty = uncommitted(repo_root, project_path)
    if dirty:
        audit.add(
            "uncommitted-context",
            "defect",
            f"{len(dirty)} uncommitted file(s) under the project — context that "
            "exists on one machine is not durable context",
            "commit and push the project files",
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
    source_name: str, repo_root: Path, projects_root: Path
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
                severity="defect",
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
                severity="defect",
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
                severity="defect",
                message="projects/index.yaml has uncommitted changes",
                remedy="commit and push index.yaml",
            )
        )

    return findings


def audit_source(source: Source) -> tuple[list[ProjectAudit], list[Finding]]:
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

    source_findings.extend(durability_findings(source.name, repo_root, projects_root))

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


def render_human(findings: list[Finding], audited: int, sources: int) -> str:
    lines = [f"synthesis context doctor {DOCTOR_VERSION}"]
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
                )
            )
            findings.extend(
                durability_findings(source.name, repo_root, projects_root)
            )
            source_count = 1
        else:
            sources = discover_sources(args.source)
            source_count = len(sources)
            for source in sources:
                src_audits, src_findings = audit_source(source)
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
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
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
        print(render_human(findings, len(audits), source_count))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

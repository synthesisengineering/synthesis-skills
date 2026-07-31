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
  durability       no uncommitted context files; the tiers are pushed, because
                   context that exists on one machine is not durable context

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

DOCTOR_VERSION = "1.0.0"

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

SEVERITY_ORDER = {"defect": 0, "warning": 1}


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


def parse_mapping_list(text: str, key: str) -> list[dict]:
    """Return the list of flat mappings under `key:` in a YAML document.

    Handles the two shapes this tool reads. Nested block values (folded
    descriptions, sub-mappings, sub-lists) are skipped rather than
    misinterpreted — every field the checks use is a flat scalar.
    """
    if _HAVE_YAML:
        try:
            loaded = yaml.safe_load(text) or {}
            value = loaded.get(key) or []
            return [item for item in value if isinstance(item, dict)]
        except Exception as exc:  # malformed input is a defect, not a pass
            raise DoctorError(f"could not parse YAML: {exc}") from exc

    items: list[dict] = []
    lines = text.splitlines()
    in_key = False
    key_indent = 0
    current: dict | None = None
    item_indent = 0

    for line in lines:
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
            current = {}
            items.append(current)
            item_indent = indent + 2
            body = body[2:].strip()
            if ":" in body:
                k, _, v = body.partition(":")
                current[k.strip()] = _scalar(v)
            continue

        if current is None or indent < item_indent:
            continue
        if ":" in body:
            k, _, v = body.partition(":")
            v = v.strip()
            # Skip block scalars and nested structures; no check reads them.
            current[k.strip()] = None if v in {">", "|", ""} else _scalar(v)

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
        if not root_raw or not projects_dir:
            continue  # a source that contributes no projects is not an error
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
        prefix = projects_root.relative_to(repo).as_posix()
    except ValueError:
        prefix = ""

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
        if len(touched) > BULK_COMMIT_PROJECT_THRESHOLD:
            continue  # repo-wide maintenance, not a session
        try:
            return datetime.strptime(datestr.strip(), "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


def uncommitted(repo: Path, path: Path) -> list[str]:
    code, out = git(repo, "status", "--porcelain", "--", str(path))
    if code != 0:
        raise DoctorError(f"git status failed in {repo}")
    return [line for line in out.splitlines() if line.strip()]


def unpushed_commits(repo: Path) -> int | None:
    """Commits on HEAD not on its upstream. None when there is no upstream."""
    code, _ = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code != 0:
        return None
    code, out = git(repo, "rev-list", "--count", "@{u}..HEAD")
    if code != 0 or not out.isdigit():
        return None
    return int(out)


# ---------------------------------------------------------------------------
# Project parsing
# ---------------------------------------------------------------------------

STATUS_HEADER = re.compile(
    r"^\*\*(?:Status|Phase)\:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE
)
LAST_SESSION_HEADER = re.compile(
    r"^\*\*(?:Last session|Completed)\:\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE
)
DATE_IN_TEXT = re.compile(r"(\d{4}-\d{2}-\d{2})")
COMPLETED_WORDS = ("complete", "completed", "shipped", "closed", "done")
PAUSED_WORDS = ("paused", "on hold", "parked")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DoctorError(f"could not read {path}: {exc}") from exc


def context_declares_completed(text: str) -> bool | None:
    """True/False when the CONTEXT.md header states completion; None if silent."""
    values = [m.group("value").lower() for m in STATUS_HEADER.finditer(text)]
    if not values:
        return None
    joined = " ".join(values)
    if any(word in joined for word in PAUSED_WORDS):
        return False
    # "Completed and live-verified" counts; "not complete" must not.
    for word in COMPLETED_WORDS:
        for value in values:
            if word in value and "not complete" not in value:
                return True
    if "active" in joined:
        return False
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
    """Number of dated entries across the session archive."""
    if not sessions_dir.is_dir():
        return 0
    total = 0
    for path in sorted(sessions_dir.glob("*.md")):
        text = read_text(path)
        total += len(
            re.findall(r"^#{2,4}\s.*\d{4}-\d{2}-\d{2}", text, re.MULTILINE)
        )
    return total


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
    "unpushed-context",
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
        if declared_complete is not None and declared_complete != index_says_completed:
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
    if newest:
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

    return audit


def audit_source(source: Source) -> tuple[list[ProjectAudit], list[Finding]]:
    source_findings: list[Finding] = []
    projects_root = source.projects_root

    # A state the doctor can determine is a finding, not a crash. Only an
    # inability to establish ground truth (unreadable config, no git, unparsable
    # YAML) raises DoctorError — that distinction is what keeps "cannot run"
    # meaningfully different from "ran and found problems".
    if not projects_root.is_dir():
        source_findings.append(
            Finding(
                project="(source)",
                source=source.name,
                check="context-present",
                severity="warning",
                message=f"declares a projects directory that does not exist: "
                f"{projects_root}",
                remedy="create the directory, or drop projects_dir from the "
                "source configuration",
            )
        )
        return [], source_findings

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

    # Push state is a repo-level property; report it once per source.
    ahead = unpushed_commits(repo_root)
    if ahead:
        source_findings.append(
            Finding(
                project="(repository)",
                source=source.name,
                check="unpushed-context",
                severity="defect",
                message=f"{ahead} commit(s) not pushed — another machine or agent "
                "cannot see this context yet",
                remedy="push the branch",
            )
        )

    return audits, source_findings


def _root_list_entries(text: str) -> list[dict]:
    """index.yaml written as a bare top-level list of project mappings."""
    if _HAVE_YAML:
        try:
            loaded = yaml.safe_load(text)
        except Exception as exc:
            raise DoctorError(f"could not parse index.yaml: {exc}") from exc
        if isinstance(loaded, list):
            return [i for i in loaded if isinstance(i, dict)]
        if isinstance(loaded, dict):
            for value in loaded.values():
                if isinstance(value, list) and any(
                    isinstance(i, dict) and "id" in i for i in value
                ):
                    return [i for i in value if isinstance(i, dict)]
        return []

    items: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        stripped = _strip_comment(line).rstrip()
        if not stripped.strip():
            continue
        body = stripped.strip()
        if body.startswith("- "):
            current = {}
            items.append(current)
            body = body[2:].strip()
        if current is not None and ":" in body:
            k, _, v = body.partition(":")
            v = v.strip()
            current.setdefault(k.strip(), None if v in {">", "|", ""} else _scalar(v))
    return [i for i in items if "id" in i]


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

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not failed,
                    "doctor_version": DOCTOR_VERSION,
                    "sources": source_count,
                    "projects_audited": len(audits),
                    "defects": len(defects),
                    "warnings": len(warnings),
                    "findings": [f.as_dict() for f in findings],
                },
                indent=2,
            )
        )
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

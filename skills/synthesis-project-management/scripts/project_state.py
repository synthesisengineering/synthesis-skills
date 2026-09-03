#!/usr/bin/env python3
"""Resolve, validate, and checkpoint durable synthesis project state.

The public API is provider-neutral. Native lifecycle adapters pass their event
envelopes to this module; evidence discovery, ordering, and receipt validation
remain shared.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable


STATE_FILE = "CURRENT_STATE.json"
STATE_SCHEMA = 1
RECEIPT_SCHEMA = 1
_VERSION_RE = re.compile(r"(?<![0-9])v?(\d+)\.(\d+)\.(\d+)(?![0-9])", re.I)
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


class ProjectStateError(RuntimeError):
    """A required evidence source was unreadable or mutually inconsistent."""


@dataclass
class Candidate:
    source: str
    project_path: str | None
    worktree: str | None
    ref: str | None
    head: str
    project_tree: str
    timestamp: str
    dirty_files: list[dict[str, str]] = field(default_factory=list)
    session_id: str | None = None


@dataclass
class RecoveryReport:
    project_id: str
    status: str
    selected_path: str | None
    selected_head: str | None
    selected_tree: str | None
    candidates: list[Candidate]
    issues: list[str]
    planes: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise ProjectStateError(detail)
    return result


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectStateError(f"unreadable JSON evidence {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProjectStateError(f"JSON evidence is not an object: {path}")
    return payload


def _repository_root(path: Path) -> Path:
    result = _run(path, "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def _common_git_dir(repo: Path) -> Path:
    raw = Path(_run(repo, "rev-parse", "--git-common-dir").stdout.strip())
    return (repo / raw).resolve() if not raw.is_absolute() else raw.resolve()


def _index_entry(text: str, project_id: str) -> str:
    matches = list(re.finditer(rf"(?m)^\s*-?\s*id:\s*['\"]?{re.escape(project_id)}['\"]?\s*$", text))
    if len(matches) != 1:
        raise ProjectStateError(
            f"index must contain exactly one project id {project_id!r}; found {len(matches)}"
        )
    start = matches[0].start()
    following = re.search(r"(?m)^\s*-?\s*id:\s*", text[matches[0].end() :])
    end = matches[0].end() + following.start() if following else len(text)
    return text[start:end]


def _latest_session_date(project: Path) -> str | None:
    dates: list[str] = []
    sessions = project / "sessions"
    if sessions.is_dir():
        for path in sessions.glob("*.md"):
            for line in path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                if re.match(r"^#{2,6}\s+", line):
                    dates.extend(_DATE_RE.findall(line))
    context = project / "CONTEXT.md"
    if context.is_file():
        for line in context.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("**last session:"):
                dates.extend(_DATE_RE.findall(line))
    return max(dates) if dates else None


def _worktrees(repo: Path) -> list[tuple[Path, str, str | None]]:
    text = _run(repo, "worktree", "list", "--porcelain").stdout
    records: list[tuple[Path, str, str | None]] = []
    for block in text.strip().split("\n\n") if text.strip() else []:
        values: dict[str, str] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            values[key] = value
        if values.get("worktree") and values.get("HEAD"):
            records.append(
                (Path(values["worktree"]).resolve(), values["HEAD"], values.get("branch"))
            )
    return records


def _latest_project_commit(repo: Path, ref: str, relative: str) -> str | None:
    result = _run(repo, "log", "-1", "--format=%H", ref, "--", relative, check=False)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _tree_at(repo: Path, ref: str, relative: str) -> str | None:
    result = _run(repo, "rev-parse", f"{ref}:{relative}", check=False)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _timestamp(repo: Path, ref: str) -> str:
    result = _run(repo, "show", "-s", "--format=%cI", ref, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _dirty_project_files(worktree: Path, relative: str) -> list[dict[str, str]]:
    result = _run(
        worktree,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        relative,
    )
    found: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        name = line[3:].split(" -> ")[-1]
        path = (worktree / name).resolve()
        digest = _sha_file(path) if path.is_file() else "deleted"
        found.append({"path": str(path), "status": line[:2], "sha256": digest})
    return sorted(found, key=lambda item: item["path"])


def _manifest_inventory(
    root: Path | None,
    checkpoint_receipt_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    found: list[dict[str, Any]] = []
    directories: list[tuple[str, Path]] = []
    if root is not None:
        directories.extend(
            (("manifest", root / "pending"), ("receipt", root / "local-handoff"))
        )
    if checkpoint_receipt_root is not None:
        directories.append(("checkpoint-receipt", checkpoint_receipt_root))
    for kind, directory in directories:
        if not directory.exists():
            continue
        if not directory.is_dir():
            issues.append(f"unreadable {kind} directory: {directory}")
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = _load_json(path)
            except ProjectStateError as exc:
                issues.append(str(exc))
                continue
            payload["_kind"] = kind
            payload["_path"] = str(path.resolve())
            payload["_timestamp"] = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            found.append(payload)
    return found, issues


def _manifest_for_dirty(
    dirty: list[dict[str, str]], manifests: Iterable[dict[str, Any]]
) -> str | None:
    dirty_paths = {item["path"]: item["sha256"] for item in dirty}
    for manifest in manifests:
        if manifest.get("_kind") != "manifest":
            continue
        paths = {str(Path(value).resolve()) for value in manifest.get("paths", []) if isinstance(value, str)}
        if not set(dirty_paths).issubset(paths):
            continue
        claimed_hashes = {
            str(Path(key).resolve()): value
            for key, value in (manifest.get("path_hashes") or {}).items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if claimed_hashes and any(claimed_hashes.get(path) != digest for path, digest in dirty_paths.items()):
            continue
        return str(manifest.get("session_id") or "") or None
    return None


def _candidate_from_metadata(
    kind: str,
    payload: dict[str, Any],
    fallback: Candidate,
) -> Candidate:
    return Candidate(
        source=kind,
        project_path=None,
        worktree=None,
        ref=None,
        head=str(payload.get("head") or payload.get("git_head") or fallback.head),
        project_tree=str(payload.get("project_tree") or fallback.project_tree),
        timestamp=str(payload.get("updated_at") or payload.get("created_at") or payload.get("_timestamp") or ""),
        session_id=str(payload.get("session_id")) if payload.get("session_id") else None,
    )


def _parse_board_rows(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectStateError(f"coordination board unreadable: {exc}") from exc
    lines = text.splitlines()
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None and "session uuid" in {cell.lower() for cell in cells}:
            header = [cell.lower() for cell in cells]
            continue
        if header is None or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    if header is None:
        raise ProjectStateError("coordination board has no active-session table")
    return rows


def _refresh_coordination_board(path: Path) -> str | None:
    helper = Path(__file__).with_name("coordination.py")
    result = subprocess.run(
        [sys.executable, str(helper), "--board", str(path), "status", "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=os.environ.copy(),
    )
    if result.returncode:
        return "coordination lease refresh failed: " + (
            result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        )
    try:
        payload = json.loads(result.stdout)
        lease = payload["lease"]
        problems = payload["problems"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        return f"coordination lease refresh returned invalid evidence: {exc}"
    if problems:
        return "coordination board is invalid after refresh: " + "; ".join(map(str, problems))
    if not lease.get("configured") or not lease.get("refreshed") or lease.get("error"):
        return "coordination lease refresh failed: " + str(
            lease.get("error") or "remote authority was not refreshed"
        )
    return None


def _is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return _run(repo, "merge-base", "--is-ancestor", older, newer, check=False).returncode == 0


def _safe_fast_forward(
    repo: Path,
    target_ref: str,
    expected_project_head: str,
    expected_project_tree: str,
    relative: str,
) -> tuple[bool, str | None]:
    current = _run(repo, "rev-parse", "HEAD").stdout.strip()
    upstream = _run(
        repo, "rev-parse", "--symbolic-full-name", "@{upstream}", check=False
    )
    if upstream.returncode or upstream.stdout.strip() != target_ref:
        return False, "selected remote ref is not the canonical branch upstream"
    target = _run(repo, "rev-parse", f"{target_ref}^{{commit}}").stdout.strip()
    if _latest_project_commit(repo, target_ref, relative) != expected_project_head:
        return False, "selected project commit no longer matches its remote ref"
    if _tree_at(repo, target_ref, relative) != expected_project_tree:
        return False, "selected project tree no longer matches its remote ref"
    if current == target:
        return True, None
    if not _is_ancestor(repo, current, target):
        return False, "canonical checkout cannot fast-forward to selected state"
    if _run(repo, "diff", "--quiet", check=False).returncode or _run(
        repo, "diff", "--cached", "--quiet", check=False
    ).returncode:
        return False, "canonical checkout has tracked or staged changes"
    changed = set(_run(repo, "diff", "--name-only", current, target).stdout.splitlines())
    untracked = {
        line[3:]
        for line in _run(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines()
        if line.startswith("?? ")
    }
    if changed & untracked:
        return False, "canonical fast-forward would overwrite untracked paths"
    result = _run(repo, "merge", "--ff-only", target, check=False)
    if result.returncode:
        return False, result.stderr.strip() or "fast-forward failed"
    if _tree_at(repo, "HEAD", relative) != expected_project_tree:
        return False, "fast-forward did not produce the selected project tree"
    return True, None


def resolve_project(
    project_id: str,
    index_path: Path,
    *,
    repo_guard_root: Path | None = None,
    checkpoint_receipt_root: Path | None = None,
    coordination_board: Path | None = None,
    pointer: Path | None = None,
    fetch: bool = True,
    fast_forward_canonical: bool = False,
    refresh_coordination: bool = False,
) -> RecoveryReport:
    """Discover all local/remote project evidence and select only by proof."""
    index_path = index_path.resolve()
    issues: list[str] = []
    candidates: list[Candidate] = []
    try:
        index_text = index_path.read_text(encoding="utf-8")
        entry = _index_entry(index_text, project_id)
        repo = _repository_root(index_path.parent)
    except (OSError, ProjectStateError) as exc:
        return RecoveryReport(project_id, "UNKNOWN", None, None, None, [], [str(exc)], {"continuity": "UNKNOWN"})
    relative = str((index_path.parent / project_id).resolve().relative_to(repo))

    if fetch:
        fetched = _run(repo, "fetch", "--all", "--prune", check=False)
        if fetched.returncode:
            issues.append(f"fetch failed: {fetched.stderr.strip() or fetched.stdout.strip()}")
        fetch_succeeded = fetched.returncode == 0
    else:
        fetch_succeeded = False

    worktree_records = _worktrees(repo)
    registered = {str(path) for path, _head, _branch in worktree_records}
    metadata_root = _common_git_dir(repo) / "worktrees"
    if metadata_root.is_dir():
        for metadata in metadata_root.iterdir():
            marker = metadata / "gitdir"
            if not marker.is_file():
                issues.append(f"missing worktree registration target for {metadata.name}")
                continue
            target_git = Path(marker.read_text(encoding="utf-8").strip())
            target = target_git.parent.resolve()
            if not target.exists() or str(target) not in registered:
                issues.append(f"missing worktree registered at {target}")

    manifests, manifest_issues = _manifest_inventory(
        repo_guard_root, checkpoint_receipt_root
    )
    issues.extend(manifest_issues)
    authoritative: list[Candidate] = []
    for worktree, _repository_head, branch in worktree_records:
        project = worktree / relative
        if not project.is_dir():
            continue
        project_head = _latest_project_commit(worktree, "HEAD", relative)
        tree = _tree_at(worktree, "HEAD", relative)
        if not project_head or not tree:
            continue
        dirty = _dirty_project_files(worktree, relative)
        owner = _manifest_for_dirty(dirty, manifests) if dirty else None
        candidate = Candidate(
            source="canonical" if worktree == repo else "worktree",
            project_path=str(project.resolve()),
            worktree=str(worktree),
            ref=branch,
            head=project_head,
            project_tree=tree,
            timestamp=_timestamp(worktree, project_head),
            dirty_files=dirty,
            session_id=owner,
        )
        authoritative.append(candidate)
        candidates.append(candidate)
        if worktree == repo:
            candidates.append(Candidate(**{**asdict(candidate), "source": "worktree"}))

    refs = _run(repo, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").stdout.splitlines()
    for ref in refs:
        if ref.endswith("/HEAD"):
            continue
        project_head = _latest_project_commit(repo, ref, relative)
        tree = _tree_at(repo, ref, relative)
        if not project_head or not tree:
            continue
        candidates.append(
            Candidate("ref", None, None, ref, project_head, tree, _timestamp(repo, project_head))
        )

    if not authoritative:
        return RecoveryReport(project_id, "UNKNOWN", None, None, None, candidates, issues + ["no readable project worktree"], {"continuity": "UNKNOWN"})
    fallback = authoritative[0]
    related_sessions = {
        str(payload.get("session_id"))
        for payload in manifests
        if payload.get("_kind") == "manifest"
        and (
            project_id in json.dumps(payload, sort_keys=True)
            or any(
                str(Path(path).resolve()).startswith(str((repo / relative).resolve()))
                for path in payload.get("paths", [])
                if isinstance(path, str)
            )
        )
    }
    for payload in manifests:
        material = json.dumps(payload, sort_keys=True)
        paths = [str(value) for value in payload.get("paths", []) if isinstance(value, str)]
        if (
            project_id in material
            or any(str(Path(path).resolve()).startswith(str((repo / relative).resolve())) for path in paths)
            or str(payload.get("session_id")) in related_sessions
        ):
            candidates.append(_candidate_from_metadata(str(payload["_kind"]), payload, fallback))

    if pointer is not None and pointer.exists():
        try:
            payload = _load_json(pointer)
            target = payload.get("project") or payload.get("project_path") or payload.get("path")
            if target and Path(str(target)).resolve().is_dir():
                candidates.append(_candidate_from_metadata("pointer", payload, fallback))
            else:
                issues.append(f"active-project pointer is stale: {pointer}")
        except ProjectStateError as exc:
            issues.append(str(exc))

    if coordination_board is not None:
        if refresh_coordination:
            try:
                refresh_issue = _refresh_coordination_board(coordination_board)
            except (OSError, subprocess.TimeoutExpired) as exc:
                refresh_issue = f"coordination lease refresh failed: {exc}"
            if refresh_issue:
                issues.append(refresh_issue)
        try:
            for row in _parse_board_rows(coordination_board):
                if row.get("status", "").lower() != "active" or row.get("project") != project_id:
                    continue
                payload = {"session_id": row.get("session uuid"), "updated_at": row.get("heartbeat")}
                candidates.append(_candidate_from_metadata("claim", payload, fallback))
        except ProjectStateError as exc:
            issues.append(str(exc))

    latest = _latest_session_date(repo / relative)
    recorded_match = re.search(r"(?m)^\s*last_session:\s*['\"]?([^'\"\s]+)", entry)
    recorded = recorded_match.group(1) if recorded_match else None
    if latest and recorded and recorded != latest:
        issues.append(f"index last_session {recorded} is stale; derived value is {latest}")

    dirty_candidates = [candidate for candidate in authoritative if candidate.dirty_files]
    unattributed = [candidate for candidate in dirty_candidates if not candidate.session_id]
    if unattributed:
        issues.append("dirty project files lack an exact attributed manifest")
        status = "CONFLICT"
        selected = None
    elif dirty_candidates and any(
        dirty.head != other.head and _is_ancestor(repo, dirty.head, other.head)
        for dirty in dirty_candidates
        for other in candidates
        if other.source in {"canonical", "worktree", "ref"}
    ):
        issues.append("attributed dirty project state extends an older head than a newer committed project state")
        status = "CONFLICT"
        selected = None
    elif dirty_candidates:
        signatures = {
            _sha_bytes(json.dumps(candidate.dirty_files, sort_keys=True).encode())
            for candidate in dirty_candidates
        }
        if len(signatures) != 1:
            issues.append("divergent attributed dirty project states")
            status = "CONFLICT"
            selected = None
        else:
            status = "LOCAL_RECOVERABLE"
            selected = dirty_candidates[0]
    else:
        unique: dict[tuple[str, str], Candidate] = {}
        for candidate in candidates:
            if candidate.source in {"canonical", "worktree", "ref"}:
                unique.setdefault((candidate.head, candidate.project_tree), candidate)
        maximal: list[Candidate] = []
        for candidate in unique.values():
            if any(
                candidate.head != other.head and _is_ancestor(repo, candidate.head, other.head)
                for other in unique.values()
            ):
                continue
            maximal.append(candidate)
        trees = {candidate.project_tree for candidate in maximal}
        if len(trees) > 1:
            status = "CONFLICT"
            selected = None
            issues.append("divergent project states have no provable causal ordering")
        elif maximal:
            status = "PASS"
            target = maximal[0]
            matching_paths = [
                item for item in authoritative if item.project_tree == target.project_tree
            ]
            selected = matching_paths[0] if matching_paths else target
            if fast_forward_canonical and selected.project_path is None:
                if not fetch_succeeded:
                    ok, reason = False, "automatic fast-forward requires a successful fetch"
                elif not selected.ref or not selected.ref.startswith("refs/remotes/"):
                    ok, reason = False, "selected state is not a fetched remote ref"
                else:
                    ok, reason = _safe_fast_forward(
                        repo,
                        selected.ref,
                        selected.head,
                        selected.project_tree,
                        relative,
                    )
                if ok:
                    selected = Candidate(
                        "canonical", str((repo / relative).resolve()), str(repo), None,
                        selected.head, selected.project_tree, selected.timestamp,
                    )
                else:
                    issues.append(f"automatic fast-forward refused: {reason}")
        else:
            status = "UNKNOWN"
            selected = None
            issues.append("no committed project state could be ordered")

    if any(issue.startswith(("fetch failed", "unreadable", "coordination board", "coordination lease", "missing worktree")) for issue in issues) and status not in {"CONFLICT", "LOCAL_RECOVERABLE"}:
        status = "UNKNOWN"
    planes = {"continuity": "PASS" if status == "PASS" else status}
    return RecoveryReport(
        project_id,
        status,
        selected.project_path if selected else None,
        selected.head if selected else None,
        selected.project_tree if selected else None,
        candidates,
        issues,
        planes,
    )


def _version(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.search(value)
    return tuple(int(part) for part in match.groups()) if match else None


def _content_hashes(project: Path, controlling_plan: str | None = None) -> dict[str, str]:
    paths = [path for path in project.rglob("*.md") if path.is_file()]
    if controlling_plan:
        plan = (project / controlling_plan).resolve()
        if project.resolve() not in plan.parents or not plan.is_file():
            raise ProjectStateError("controlling plan must be a readable file inside the project")
        paths.append(plan)
    return {
        str(path.resolve().relative_to(project.resolve())): _sha_file(path)
        for path in sorted(set(paths))
    }


def semantic_issues(project: Path) -> list[str]:
    """Return contradictions in operational and human-readable current state."""
    project = project.resolve()
    context_path = project / "CONTEXT.md"
    if not context_path.is_file():
        return ["current context is missing"]
    context = context_path.read_text(encoding="utf-8", errors="replace")
    issues: list[str] = []
    state_path = project / STATE_FILE
    state: dict[str, Any] | None = None
    if state_path.exists():
        try:
            state = _load_json(state_path)
            if state.get("schema_version") != STATE_SCHEMA:
                issues.append("current operational state schema is unsupported")
            for key in (
                "project_id", "phase", "status", "controlling_plan", "accepted_baseline",
                "next_actions", "last_session", "session_id", "content_hashes",
                "repository", "project_path", "git_head", "project_tree",
                "source_heads", "updated_at",
            ):
                if key not in state:
                    issues.append(f"current operational state lacks {key}")
        except ProjectStateError as exc:
            issues.append(str(exc))
    current_text: list[str] = []
    for line in context.splitlines():
        lowered = line.lower()
        if lowered.startswith("**phase:") or "current accepted" in lowered or "current baseline" in lowered:
            current_text.append(line)
    if state:
        current_text.extend([str(state.get("phase", "")), str(state.get("accepted_baseline", ""))])
    current_versions = [item for value in current_text if (item := _version(value))]
    all_versions = [tuple(int(part) for part in match.groups()) for match in _VERSION_RE.finditer(context)]
    if current_versions and all_versions and max(current_versions) < max(all_versions):
        newest = ".".join(str(part) for part in max(all_versions))
        current = ".".join(str(part) for part in max(current_versions))
        issues.append(f"current release {current} is older than later recorded release {newest}")
    if state:
        if state.get("project_id") != project.name:
            issues.append("current operational state project id disagrees with its directory")
        plan = (project / str(state.get("controlling_plan", ""))).resolve()
        if project not in plan.parents or not plan.is_file():
            issues.append("current controlling plan is missing or escapes the project")
        hashes = state.get("content_hashes")
        if isinstance(hashes, dict):
            try:
                if hashes != _content_hashes(
                    project, str(state.get("controlling_plan") or "")
                ):
                    issues.append("durable project files changed after current state was written")
            except ProjectStateError as exc:
                issues.append(str(exc))
        else:
            issues.append("current operational state content hashes are malformed")
        latest = _latest_session_date(project)
        if latest and state.get("last_session") != latest:
            issues.append(
                f"current operational state last session {state.get('last_session')} "
                f"is stale; derived value is {latest}"
            )
        marker_start = "<!-- synthesis-current-state:start -->"
        marker_end = "<!-- synthesis-current-state:end -->"
        if marker_start in context or marker_end in context:
            expected = render_context_current_state(project, state)
            match = re.search(
                re.escape(marker_start) + r".*?" + re.escape(marker_end), context, re.S
            )
            if not match or match.group(0) != expected:
                issues.append("compiled current-state block disagrees with operational state")
    return issues


def _git_identity(project: Path) -> tuple[Path, str, str, str]:
    repo = _repository_root(project)
    relative = str(project.resolve().relative_to(repo))
    head = _run(repo, "rev-parse", "HEAD").stdout.strip()
    tree = _tree_at(repo, "HEAD", relative) or "UNCOMMITTED"
    return repo, relative, head, tree


def build_operational_state(
    project: Path,
    *,
    project_id: str,
    phase: str,
    status: str,
    controlling_plan: str,
    accepted_baseline: str,
    next_actions: list[str],
    last_session: str,
    session_id: str,
    source_heads: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Write the machine-readable current state from explicit current facts."""
    project = project.resolve()
    if project.name != project_id:
        raise ProjectStateError("project id does not match the project directory")
    repo, relative, head, tree = _git_identity(project)
    plan = (project / controlling_plan).resolve()
    if project not in plan.parents or not plan.is_file():
        raise ProjectStateError("controlling plan must be a readable file inside the project")
    if not next_actions or not all(isinstance(item, str) and item.strip() for item in next_actions):
        raise ProjectStateError("next_actions must contain at least one substantive action")
    payload: dict[str, Any] = {
        "schema_version": STATE_SCHEMA,
        "project_id": project_id,
        "phase": phase,
        "status": status,
        "controlling_plan": controlling_plan,
        "accepted_baseline": accepted_baseline,
        "next_actions": next_actions,
        "last_session": last_session,
        "session_id": session_id,
        "repository": str(repo),
        "project_path": relative,
        "git_head": head,
        "project_tree": tree,
        "source_heads": dict(sorted((source_heads or {}).items())),
        "content_hashes": {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    compile_context(project, payload)
    payload["content_hashes"] = _content_hashes(project, controlling_plan)
    _atomic_json(project / STATE_FILE, payload)
    return payload


def render_context_current_state(project: Path, state: dict[str, Any]) -> str:
    """Compile the bounded current-state block used by human readers."""
    actions = "\n".join(f"- {item}" for item in state.get("next_actions", []))
    return "\n".join(
        [
            "<!-- synthesis-current-state:start -->",
            f"**Phase:** {state.get('phase', '')}",
            f"**Status:** {state.get('status', '')}",
            f"**Last session:** {state.get('last_session', '')}",
            f"**Accepted baseline:** {state.get('accepted_baseline', '')}",
            f"**Controlling plan:** [{state.get('controlling_plan', '')}]({state.get('controlling_plan', '')})",
            "**Next actions:**",
            actions,
            "<!-- synthesis-current-state:end -->",
        ]
    )


def compile_context(project: Path, state: dict[str, Any]) -> None:
    """Replace or introduce the generated current-state block atomically."""
    context_path = project.resolve() / "CONTEXT.md"
    context = context_path.read_text(encoding="utf-8")
    start = "<!-- synthesis-current-state:start -->"
    end = "<!-- synthesis-current-state:end -->"
    block = render_context_current_state(project, state)
    has_start, has_end = start in context, end in context
    if has_start != has_end:
        raise ProjectStateError("CONTEXT.md has an incomplete current-state marker pair")
    if has_start:
        updated = re.sub(
            re.escape(start) + r".*?" + re.escape(end), block, context, count=1, flags=re.S
        )
    else:
        lines = context.splitlines()
        if not lines or not lines[0].startswith("#"):
            raise ProjectStateError("CONTEXT.md needs a leading heading before compilation")
        remaining = lines[1:]
        while remaining and not remaining[0].strip():
            remaining.pop(0)
        while remaining and re.match(r"^\*\*(Phase|Status|Last session):\*\*", remaining[0], re.I):
            remaining.pop(0)
        while remaining and not remaining[0].strip():
            remaining.pop(0)
        updated = lines[0] + "\n\n" + block + "\n\n" + "\n".join(remaining)
        if context.endswith("\n"):
            updated += "\n"
    _atomic_text(context_path, updated)


def _working_digest(project: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(item for item in project.rglob("*") if item.is_file()):
        if ".git" in path.parts:
            continue
        entries.append((str(path.relative_to(project)), _sha_file(path)))
    return _sha_bytes(json.dumps(entries, separators=(",", ":")).encode())


def _active_claim(path: Path, session_id: str, project_id: str, project: Path) -> dict[str, str]:
    rows = _parse_board_rows(path)
    matches = [
        row for row in rows
        if row.get("session uuid") == session_id
        and row.get("project") == project_id
        and row.get("status", "").lower() == "active"
    ]
    if len(matches) != 1:
        raise ProjectStateError("checkpoint requires exactly one active matching session claim")
    row = matches[0]
    workspace = row.get("workspace(s) / branch", "")
    claimed = row.get("claimed areas (advisory lock)", "")
    repo = str(_repository_root(project))
    if repo not in workspace and str(project) not in claimed and project.name not in claimed:
        raise ProjectStateError("active session claim does not cover the project worktree")
    return row


def _receipt_path(receipt_root: Path, session_id: str, project_id: str) -> Path:
    name = _sha_bytes(f"{session_id}\0{project_id}".encode()) + ".json"
    return receipt_root / name


def checkpoint_project(
    project: Path,
    *,
    session_id: str,
    coordination_board: Path,
    receipt_root: Path,
    source_heads: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Issue a clean checkpoint only when state, claim, Git, and hashes bind."""
    project = project.resolve()
    state = _load_json(project / STATE_FILE)
    project_id = str(state.get("project_id") or "")
    if state.get("schema_version") != STATE_SCHEMA or not project_id:
        raise ProjectStateError("current operational state is invalid")
    if state.get("session_id") != session_id:
        raise ProjectStateError("current operational state belongs to a different session")
    problems = semantic_issues(project)
    current_hashes = _content_hashes(project, str(state.get("controlling_plan") or ""))
    if current_hashes != state.get("content_hashes"):
        problems.append("durable project files changed after current state was written")
    if dict(sorted((source_heads or {}).items())) != state.get("source_heads", {}):
        problems.append("source heads changed after current state was written")
    if problems:
        raise ProjectStateError("; ".join(problems))
    claim = _active_claim(coordination_board.resolve(), session_id, project_id, project)
    _repo, _relative, head, tree = _git_identity(project)
    payload: dict[str, Any] = {
        "receipt_schema": RECEIPT_SCHEMA,
        "session_id": session_id,
        "project_id": project_id,
        "project": str(project),
        "git_head": head,
        "project_tree": tree,
        "working_digest": _working_digest(project),
        "state_hash": _sha_file(project / STATE_FILE),
        "content_hashes": current_hashes,
        "source_heads": dict(sorted((source_heads or {}).items())),
        "claim_hash": _sha_bytes(json.dumps(claim, sort_keys=True).encode()),
        "writer_adapter": os.environ.get("SYNTHESIS_LIFECYCLE_ADAPTER", "shared"),
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _receipt_path(receipt_root.resolve(), session_id, project_id)
    _atomic_json(path, payload)
    payload["receipt_path"] = str(path)
    return payload


def validate_checkpoint(
    project: Path,
    *,
    session_id: str,
    coordination_board: Path,
    receipt_root: Path,
    source_heads: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    """Validate an outgoing receipt without turning missing evidence green."""
    project = project.resolve()
    try:
        state = _load_json(project / STATE_FILE)
    except ProjectStateError as exc:
        return "UNKNOWN", [str(exc)]
    project_id = str(state.get("project_id") or "")
    path = _receipt_path(receipt_root.resolve(), session_id, project_id)
    if not path.is_file():
        return "LOCAL_RECOVERABLE", ["no clean checkpoint receipt exists"]
    try:
        receipt = _load_json(path)
        claim = _active_claim(coordination_board.resolve(), session_id, project_id, project)
    except ProjectStateError as exc:
        return "UNKNOWN", [str(exc)]
    problems: list[str] = []
    if receipt.get("receipt_schema") != RECEIPT_SCHEMA:
        problems.append("checkpoint receipt schema is unsupported")
    if receipt.get("session_id") != session_id or receipt.get("project_id") != project_id:
        problems.append("checkpoint receipt identity mismatch")
    requested_sources = dict(sorted((source_heads or {}).items()))
    if requested_sources != receipt.get("source_heads", {}):
        return "FAIL", ["source heads differ from the clean checkpoint"]
    if _sha_file(project / STATE_FILE) != receipt.get("state_hash"):
        problems.append("current operational state differs from the clean checkpoint")
    if _content_hashes(project, str(state.get("controlling_plan") or "")) != receipt.get("content_hashes"):
        problems.append("durable project files differ from the clean checkpoint")
    if _working_digest(project) != receipt.get("working_digest"):
        problems.append("project working state differs from the clean checkpoint")
    if _sha_bytes(json.dumps(claim, sort_keys=True).encode()) != receipt.get("claim_hash"):
        problems.append("coordination claim differs from the clean checkpoint")
    return ("LOCAL_RECOVERABLE", problems) if problems else ("PASS", [])


def _row_for_event(rows: list[dict[str, str]], payload: dict[str, Any]) -> dict[str, str] | None:
    event_ids = {
        str(payload.get(key) or "").strip()
        for key in ("session_id", "root_task_uuid", "task_id")
    }
    configured = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    if configured:
        event_ids.update({configured, configured.rsplit(":", 1)[-1]})
    matches = []
    for row in rows:
        if row.get("status", "").lower() != "active":
            continue
        client_ref = row.get("client session ref", "")
        if (
            client_ref in event_ids
            or client_ref.rsplit(":", 1)[-1] in event_ids
            or row.get("session uuid", "") in event_ids
        ):
            matches.append(row)
    if len(matches) > 1:
        raise ProjectStateError("lifecycle event matches multiple active coordination seats")
    return matches[0] if matches else None


def _project_from_claim(row: dict[str, str]) -> Path | None:
    project_id = row.get("project", "")
    if not project_id:
        return None
    paths: list[Path] = []
    cells = (
        row.get("claimed areas (advisory lock)", "")
        + ","
        + row.get("workspace(s) / branch", "")
    )
    for raw in re.split(r"(?:<br>|,)", cells):
        value = raw.strip().split(" @ ", 1)[0].removesuffix("/**").removesuffix("/")
        if not value.startswith("/"):
            continue
        path = Path(value)
        marker = ("projects", project_id)
        parts = path.parts
        for index in range(len(parts) - 1):
            if tuple(parts[index : index + 2]) == marker:
                paths.append(Path(*parts[: index + 2]))
        paths.append(path / "projects" / project_id)
    existing = sorted(
        {path.resolve() for path in paths if (path / STATE_FILE).is_file()},
        key=lambda item: (len(str(item)), str(item)),
    )
    if len(existing) > 1:
        matching = []
        for path in existing:
            try:
                if _load_json(path / STATE_FILE).get("session_id") == row.get("session uuid"):
                    matching.append(path)
            except ProjectStateError:
                continue
        if len(matching) == 1:
            return matching[0]
        raise ProjectStateError("active claim names multiple structured project states")
    return existing[0] if existing else None


def _live_source_heads(state: dict[str, Any]) -> dict[str, str]:
    live: dict[str, str] = {}
    for raw in (state.get("source_heads") or {}):
        root = Path(str(raw)).resolve()
        live[str(raw)] = _run(root, "rev-parse", "HEAD").stdout.strip()
    return live


def checkpoint_hook(
    payload: dict[str, Any],
    *,
    coordination_board: Path,
    receipt_root: Path,
    refresh_coordination: bool = True,
) -> tuple[str, list[str]]:
    """Bind a lifecycle event to its seat and issue an exact clean receipt."""
    try:
        if refresh_coordination:
            refresh_issue = _refresh_coordination_board(coordination_board.resolve())
            if refresh_issue:
                return "FAIL", [refresh_issue]
        row = _row_for_event(_parse_board_rows(coordination_board.resolve()), payload)
        if row is None:
            cwd = Path(str(payload.get("cwd") or ".")).resolve()
            for candidate in (cwd, *cwd.parents):
                if (candidate / STATE_FILE).is_file():
                    return "UNKNOWN", ["structured project has no matching active coordination seat"]
            return "NOT_APPLICABLE", []
        project = _project_from_claim(row)
        if project is None:
            return "NOT_APPLICABLE", []
        state = _load_json(project / STATE_FILE)
        session_id = row.get("session uuid", "")
        source_heads = _live_source_heads(state)
        checkpoint_project(
            project,
            session_id=session_id,
            coordination_board=coordination_board,
            receipt_root=receipt_root,
            source_heads=source_heads,
        )
        return validate_checkpoint(
            project,
            session_id=session_id,
            coordination_board=coordination_board,
            receipt_root=receipt_root,
            source_heads=source_heads,
        )
    except (OSError, ProjectStateError) as exc:
        return "FAIL", [str(exc)]


def _source_head_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        path, separator, head = value.partition("=")
        if not separator or not path.strip() or not head.strip():
            raise ProjectStateError(
                "source heads must use an absolute-path=commit value"
            )
        root = Path(path).expanduser().resolve()
        if not root.is_absolute() or not root.is_dir():
            raise ProjectStateError(f"source repository is unreadable: {root}")
        resolved = _run(root, "rev-parse", f"{head.strip()}^{{commit}}").stdout.strip()
        parsed[str(root)] = resolved
    return parsed


def _add_source_heads(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-head",
        action="append",
        default=[],
        metavar="ABSOLUTE_PATH=COMMIT",
        help="bind one implementation source repository (repeatable)",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--project-id", required=True)
    resolve.add_argument("--index", required=True, type=Path)
    resolve.add_argument("--repo-guard-root", type=Path)
    resolve.add_argument("--checkpoint-receipt-root", type=Path)
    resolve.add_argument("--coordination-board", type=Path)
    resolve.add_argument("--pointer", type=Path)
    resolve.add_argument("--no-fetch", action="store_true")
    resolve.add_argument("--fast-forward-canonical", action="store_true")
    resolve.add_argument("--no-coordination-refresh", action="store_true")
    semantic = sub.add_parser("semantic")
    semantic.add_argument("--project", required=True, type=Path)
    build = sub.add_parser("build")
    build.add_argument("--project", required=True, type=Path)
    build.add_argument("--project-id", required=True)
    build.add_argument("--phase", required=True)
    build.add_argument("--status", required=True)
    build.add_argument("--controlling-plan", required=True)
    build.add_argument("--accepted-baseline", required=True)
    build.add_argument("--next-action", action="append", required=True)
    build.add_argument("--last-session", required=True)
    build.add_argument("--session-id", required=True)
    _add_source_heads(build)
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--project", required=True, type=Path)
    checkpoint.add_argument("--session-id", required=True)
    checkpoint.add_argument("--coordination-board", required=True, type=Path)
    checkpoint.add_argument("--receipt-root", required=True, type=Path)
    _add_source_heads(checkpoint)
    validate = sub.add_parser("validate")
    validate.add_argument("--project", required=True, type=Path)
    validate.add_argument("--session-id", required=True)
    validate.add_argument("--coordination-board", required=True, type=Path)
    validate.add_argument("--receipt-root", required=True, type=Path)
    _add_source_heads(validate)
    hook = sub.add_parser("hook")
    hook.add_argument(
        "--coordination-board",
        type=Path,
        default=Path.home() / ".synthesis" / "coordination" / "active-sessions.md",
    )
    hook.add_argument(
        "--receipt-root",
        type=Path,
        default=Path.home() / ".synthesis" / "project-state" / "receipts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "resolve":
        report = resolve_project(
            args.project_id,
            args.index,
            repo_guard_root=args.repo_guard_root,
            checkpoint_receipt_root=args.checkpoint_receipt_root,
            coordination_board=args.coordination_board,
            pointer=args.pointer,
            fetch=not args.no_fetch,
            fast_forward_canonical=args.fast_forward_canonical,
            refresh_coordination=(
                args.coordination_board is not None and not args.no_coordination_refresh
            ),
        )
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0 if report.status in {"PASS", "LOCAL_RECOVERABLE"} else 1
    if args.command == "semantic":
        issues = semantic_issues(args.project)
        print(json.dumps({"status": "PASS" if not issues else "FAIL", "issues": issues}, indent=2))
        return 0 if not issues else 1
    if args.command == "build":
        try:
            payload = build_operational_state(
                args.project,
                project_id=args.project_id,
                phase=args.phase,
                status=args.status,
                controlling_plan=args.controlling_plan,
                accepted_baseline=args.accepted_baseline,
                next_actions=args.next_action,
                last_session=args.last_session,
                session_id=args.session_id,
                source_heads=_source_head_args(args.source_head),
            )
        except (OSError, ProjectStateError) as exc:
            print(json.dumps({"status": "FAIL", "issues": [str(exc)]}, indent=2))
            return 1
        print(json.dumps({"status": "PASS", "state": payload}, indent=2))
        return 0
    if args.command == "checkpoint":
        try:
            payload = checkpoint_project(
                args.project,
                session_id=args.session_id,
                coordination_board=args.coordination_board,
                receipt_root=args.receipt_root,
                source_heads=_source_head_args(args.source_head),
            )
        except (OSError, ProjectStateError) as exc:
            print(json.dumps({"status": "FAIL", "issues": [str(exc)]}, indent=2))
            return 1
        print(json.dumps({"status": "PASS", "receipt": payload}, indent=2))
        return 0
    if args.command == "hook":
        try:
            payload = json.loads(sys.stdin.read() or "{}")
            if not isinstance(payload, dict):
                raise ValueError("hook payload is not an object")
        except (json.JSONDecodeError, ValueError) as exc:
            print(json.dumps({"status": "UNKNOWN", "issues": [str(exc)]}))
            return 2
        verdict, issues = checkpoint_hook(
            payload,
            coordination_board=args.coordination_board,
            receipt_root=args.receipt_root,
        )
        print(json.dumps({"status": verdict, "issues": issues}))
        return 0 if verdict in {"PASS", "NOT_APPLICABLE"} else 2
    verdict, issues = validate_checkpoint(
        args.project,
        session_id=args.session_id,
        coordination_board=args.coordination_board,
        receipt_root=args.receipt_root,
        source_heads=_source_head_args(args.source_head),
    )
    print(json.dumps({"status": verdict, "issues": issues}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

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
import uuid
from typing import Any, Iterable

from plan_reference import PlanReference, resolve_plan_target

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


def _released_versions(
    value: str, *, accepted_baseline: bool = False,
) -> list[tuple[int, int, int]]:
    """Read affirmative release assertions, not an arbitrary version maximum.

    Context also records prospective candidates, examples and dependencies.
    Those mentions are not evidence that the accepted release is stale. Scope
    qualifications to a statement so an unreleased candidate does not suppress
    a separately shipped release on the same line. This is a bounded prose
    consistency check, not an independent verification of publication.
    """
    versions: list[tuple[int, int, int]] = []
    for statement in re.split(r"[;\n]|(?<=[.!?])\s+", value):
        mentions = list(_VERSION_RE.finditer(statement))
        boundaries = [0]
        for previous, following in zip(mentions, mentions[1:]):
            # Split only between distinct versions. An internal conjunction in
            # "v2 runtime and preserved-change candidate" qualifies that one
            # version and must remain attached to it.
            connector = re.search(
                r",|\s+(?:and|but|whereas|while|with)\s+",
                statement[previous.end():following.start()], re.I,
            )
            if connector:
                boundaries.append(previous.end() + connector.end())
        boundaries.append(len(statement))
        assertions: list[tuple[str, int]] = []
        for start, end in zip(boundaries, boundaries[1:]):
            part = statement[start:end]
            lowered = part.lower()
            prospective = re.search(
                r"\b(?:unreleased|planned|proposed|target|pending|awaiting)\b"
                r"|\bunder\s+(?:verification|review|development)\b"
                r"|\b(?:not|never)(?:\s+(?:yet|been|being|be))*\s+"
                r"(?:released|shipped|published|deployed|accepted)\b"
                r"|\bno\s+release\b"
                r"|\b(?:will|would|should|must|may|might|could|can|to)\s+(?:be\s+)?"
                r"(?:release(?:d)?|ship(?:ped)?|publish(?:ed)?|deploy(?:ed)?|accept(?:ed)?)\b",
                lowered,
            )
            completed = re.search(r"\b(?:released|shipped|published|deployed)\b", lowered)
            candidate = re.search(r"\bcandidate(?:\b|(?=v?\d+\.))", lowered)
            reference = re.search(r"\b(?:example|documentation)\b", lowered)
            affirmative = re.search(
                r"\b(?:release|released|shipped|published|deployed|accepted)\b", lowered,
            )
            status = (
                -1 if prospective or reference or (candidate and not completed)
                else 1 if affirmative else 0
            )
            assertions.append((part, status))
        # An unqualified version list can share its explicit release predicate:
        # "Released v1 and v2" or "v1 and v2 shipped". Do not inherit a predicate
        # across mixed released/candidate assertions or across unrelated prose.
        shared_release = {status for _, status in assertions if status} == {1}
        for part, status in assertions:
            if status < 0:
                continue
            remainder = re.sub(
                r"\b(?:and|but|whereas|while|with)\b", "",
                _VERSION_RE.sub("", part), flags=re.I,
            )
            bare_version = not remainder.strip(" \t,.*_`")
            if not (status or accepted_baseline or (shared_release and bare_version)):
                continue
            versions.extend(
                tuple(int(piece) for piece in match.groups())
                for match in _VERSION_RE.finditer(part)
            )
    return versions


def _content_hashes(project: Path, controlling_plan: str | None = None) -> dict[str, str]:
    paths = [path for path in project.rglob("*.md") if path.is_file()]
    hashes = {
        str(path.resolve().relative_to(project.resolve())): _sha_file(path)
        for path in sorted(set(paths))
    }
    if controlling_plan:
        plan_ref = _required_plan(project, controlling_plan)
        hashes[plan_ref.relative_path] = _sha_file(plan_ref.resolved)
    return dict(sorted(hashes.items()))


def _required_plan(project: Path, controlling_plan: object) -> PlanReference:
    plan_ref = resolve_plan_target(project, controlling_plan)
    if plan_ref.resolved is None:
        raise ProjectStateError(plan_ref.detail)
    return plan_ref


def _normalized_state_label(value: str) -> str:
    plain_text = re.sub(r"[*_`]+", "", value)
    plain_text = re.sub(r"^\s*[-+]\s+", "", plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip().casefold()
    return plain_text.strip(" \t:;,.!?—–-")


def _is_current_state_label(value: str, *, heading: bool = False) -> bool:
    normalized = _normalized_state_label(value)
    prefixes = (
        "accepted baseline",
        "next checkpoint",
        "current accepted",
        "current baseline",
        "state as of",
    )
    if heading and (
        normalized == "current" or normalized.startswith("current ")
    ):
        return True
    for prefix in prefixes:
        if normalized == prefix:
            return True
        suffix = normalized[len(prefix) : len(prefix) + 1]
        if normalized.startswith(prefix) and suffix in {
            " ",
            ":",
            "—",
            "–",
            "-",
        }:
            return True
    return False


def _uncompiled_current_state_prose(project: Path, context: str) -> list[str]:
    """Locate mutable current-state labels outside the generated state block.

    A structured project has one operational source and one generated readable
    projection. Allowing a second heading such as ``Current handoff`` or
    ``Accepted baseline`` recreates the contradiction that structured state is
    intended to remove. Historical snapshots remain ordinary Markdown; they
    are safe when their headings label them as history rather than as current.
    """
    marker_start = "<!-- synthesis-current-state:start -->"
    marker_end = "<!-- synthesis-current-state:end -->"
    surfaces: list[tuple[str, str]] = [("CONTEXT.md", context)]
    reference_index = project / "REFERENCE.md"
    if reference_index.is_file():
        surfaces.append(
            (
                "REFERENCE.md",
                reference_index.read_text(encoding="utf-8", errors="replace"),
            )
        )
    reference_dir = project / "reference"
    if reference_dir.is_dir():
        for path in sorted(reference_dir.rglob("*.md")):
            if path.is_file():
                surfaces.append(
                    (
                        str(path.relative_to(project)),
                        path.read_text(encoding="utf-8", errors="replace"),
                    )
                )

    findings: list[str] = []
    for relative, text in surfaces:
        current_lines: list[int] = []
        inside_generated = False
        lines = text.splitlines()
        for index, line in enumerate(lines):
            number = index + 1
            if relative == "CONTEXT.md" and marker_start in line:
                inside_generated = True
                continue
            if relative == "CONTEXT.md" and marker_end in line:
                inside_generated = False
                continue
            if inside_generated:
                continue

            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
            heading_title = heading.group(1) if heading else ""
            if (
                not heading_title
                and line.strip()
                and index + 1 < len(lines)
                and re.match(r"^\s{0,3}(?:=+|-+)\s*$", lines[index + 1])
            ):
                heading_title = line
            if heading_title and _is_current_state_label(
                heading_title, heading=True
            ):
                current_lines.append(number)
                continue

            if _is_current_state_label(line):
                current_lines.append(number)

        if current_lines:
            locations = ", ".join(str(number) for number in current_lines)
            findings.append(
                "uncompiled current-state prose in "
                f"{relative} at line(s) {locations}; structured projects must "
                "keep mutable current claims inside the generated block and "
                "label other snapshots as history"
            )
    return findings


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
    baseline_text: list[str] = []
    phase_text: list[str] = []
    for line in context.splitlines():
        lowered = line.lower().strip()
        if lowered.startswith("**phase:"):
            phase_text.append(line)
        if re.match(
            r"^(?:\*\*)?(?:(?:current\s+)?accepted\s+baseline|current\s+(?:accepted|baseline))\b",
            lowered,
        ):
            baseline_text.append(line)
    if state:
        baseline_text = [str(state.get("accepted_baseline", ""))]
        phase_text = [str(state.get("phase", ""))]
    current_versions = [
        version for value in baseline_text
        for version in _released_versions(value, accepted_baseline=True)
    ]
    if not current_versions:
        current_versions = [
            version for value in phase_text for version in _released_versions(value)
        ]
    recorded_versions = _released_versions(context)
    if current_versions and recorded_versions and max(current_versions) < max(recorded_versions):
        newest = ".".join(str(part) for part in max(recorded_versions))
        current = ".".join(str(part) for part in max(current_versions))
        issues.append(f"current release {current} is older than later recorded release {newest}")
    if state:
        issues.extend(_uncompiled_current_state_prose(project, context))
        if state.get("project_id") != project.name:
            issues.append("current operational state project id disagrees with its directory")
        try:
            _required_plan(project, state.get("controlling_plan"))
        except ProjectStateError as exc:
            issues.append(str(exc))
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
    plan_ref = _required_plan(project, controlling_plan)
    assert plan_ref.relative_path is not None
    controlling_plan = plan_ref.relative_path
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
    plan = str(state.get("controlling_plan", ""))
    plan_target = f"<{plan}>" if re.search(r"\s|[()]", plan) else plan
    return "\n".join(
        [
            "<!-- synthesis-current-state:start -->",
            f"**Phase:** {state.get('phase', '')}",
            f"**Status:** {state.get('status', '')}",
            f"**Last session:** {state.get('last_session', '')}",
            f"**Accepted baseline:** {state.get('accepted_baseline', '')}",
            f"**Controlling plan:** [{plan}]({plan_target})",
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
    try:
        current_hashes = _content_hashes(project, str(state.get("controlling_plan") or ""))
    except (ProjectStateError, OSError, ValueError) as exc:
        problems.append(f"durable project files cannot be verified: {exc}")
    else:
        if current_hashes != receipt.get("content_hashes"):
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
    } - {""}
    configured = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    native = payload.get("session_id")
    if (
        configured.startswith(("cc:", "codex:"))
        and (not isinstance(native, str) or not native or configured.split(":", 1)[1] != native)
    ):
        raise ProjectStateError("native lifecycle identity conflicts with the configured client reference; refusing a foreign checkpoint")
    if configured:
        event_ids.update({configured, configured.rsplit(":", 1)[-1]})
    matches = []
    for row in rows:
        if row.get("status", "").lower() != "active":
            continue
        client_ref = row.get("client session ref", "")
        if (
            (client_ref and client_ref in event_ids)
            or (client_ref and client_ref.rsplit(":", 1)[-1] in event_ids)
            or (row.get("session uuid") and row["session uuid"] in event_ids)
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


def _observer_native_identity(payload: dict[str, Any]) -> tuple[str, str]:
    """Verify an observer from native transcript evidence, not a read-only flag."""
    native = payload.get("session_id")
    try:
        uuid.UUID(native)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProjectStateError("observer Stop requires a valid native session UUID") from exc
    raw = payload.get("transcript_path")
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise ProjectStateError("observer Stop requires this native session's transcript path")
    transcript = Path(raw)
    if transcript.is_symlink() or not transcript.is_file():
        raise ProjectStateError("observer native transcript is missing or unsafe")
    scripts = Path(__file__).resolve().parents[2] / "synthesis-agent-conformance" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from live_receipt import client_root_transcript_path, transcript_binds_session
    except (ImportError, SyntaxError) as exc:
        raise ProjectStateError("observer native transcript validator is unavailable") from exc
    matches = []
    for client, variable in (("claude", "CLAUDE_CONFIG_DIR"), ("codex", "CODEX_HOME")):
        raw_home = os.environ.get(variable, str(Path.home() / f".{client}"))
        if not raw_home.strip() or not Path(raw_home).expanduser().is_absolute():
            continue
        home = Path(raw_home).expanduser()
        if not client_root_transcript_path(transcript, client, native, home):
            continue
        if transcript_binds_session(transcript, client, native):
            matches.append(client)
    if len(matches) != 1:
        raise ProjectStateError("observer transcript does not unambiguously bind this native session")
    return matches[0], native


def _observer_git(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project), *arguments], capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}, timeout=15,
    )


def _observer_project(cwd: Path) -> Path | None:
    for candidate in (cwd, *cwd.parents):
        if (candidate / STATE_FILE).exists() or (candidate / STATE_FILE).is_symlink():
            return candidate
        # A deleted tracked state file must remain an observable obligation.
        tracked = _observer_git(candidate, "ls-files", "--error-unmatch", "--", f":(literal){STATE_FILE}")
        if tracked.returncode == 0:
            return candidate
    return None


def _observer_pending_scope(payload: dict[str, Any], repo_guard_root: Path) -> tuple[str, list[str]] | None:
    """Known exact-session work remains an obligation regardless of cwd."""
    native = payload.get("session_id")
    if not isinstance(native, str) or not native:
        return None
    pending = repo_guard_root / "pending"
    own = pending / (_sha_bytes(native.encode()) + ".json")
    if repo_guard_root.is_symlink() or pending.is_symlink() or own.is_symlink():
        raise ProjectStateError("observer attribution evidence crosses an unsafe symlink")
    if pending.exists() and not pending.is_dir():
        raise ProjectStateError("observer attribution directory is unreadable")
    if own.exists():
        _observer_native_identity(payload)
        attribution = _load_json(own)
        if attribution.get("session_id") != native or type(attribution.get("schema_version")) is not int or attribution.get("schema_version") not in {1, 2}:
            raise ProjectStateError("exact native-session pending attribution is invalid; preserve its evidence")
        paths = attribution.get("paths")
        if not isinstance(paths, list) or not paths or any(not isinstance(path, str) or not Path(path).is_absolute() for path in paths):
            raise ProjectStateError("exact native-session pending attribution has invalid paths")
        return "UNKNOWN", [f"native session has attributed edits but no matching active claim; preserve {own} and recover its own claim/checkpoint authority"]
    return None


def _observer_checkpoint_scope(payload: dict[str, Any], project: Path) -> tuple[str, list[str]]:
    _observer_native_identity(payload)
    dirty = _observer_git(project, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".")
    if dirty.returncode:
        raise ProjectStateError("observer project Git state could not be verified")
    if dirty.stdout:
        return "UNKNOWN", ["unowned structured project has staged, unstaged or untracked changes; absence of native attribution does not prove read-only work"]
    return "NOT_APPLICABLE", ["no active checkpoint ownership or native pending attribution; observed Git project subtree is clean; no checkpoint receipt issued and no recovery/state-health PASS implied"]


def checkpoint_hook(
    payload: dict[str, Any],
    *,
    coordination_board: Path,
    receipt_root: Path,
    refresh_coordination: bool = True,
    repo_guard_root: Path | None = None,
) -> tuple[str, list[str]]:
    """Bind a lifecycle event to its seat and issue an exact clean receipt."""
    try:
        if refresh_coordination:
            refresh_issue = _refresh_coordination_board(coordination_board.resolve())
            if refresh_issue:
                return "FAIL", [refresh_issue]
        row = _row_for_event(_parse_board_rows(coordination_board.resolve()), payload)
        if row is None:
            root = repo_guard_root or Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))) / "repo-guard"
            pending_scope = _observer_pending_scope(payload, root)
            if pending_scope is not None:
                return pending_scope
            cwd = Path(str(payload.get("cwd") or ".")).resolve()
            project = _observer_project(cwd)
            if project is not None:
                return _observer_checkpoint_scope(payload, project)
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
    except (OSError, subprocess.SubprocessError, ProjectStateError) as exc:
        return "FAIL", [str(exc)]


def _emit_checkpoint_hook(verdict: str, issues: list[str], payload: dict[str, Any]) -> int:
    report = {"status": verdict, "issues": issues, "checkpoint_accepted": verdict == "PASS"}
    if verdict == "NOT_APPLICABLE":
        report["no_receipt_issued"] = True
    # Codex validates Stop stdout against an additionalProperties:false schema.
    # Keep diagnostic fields inside the supported string, separate from native
    # lifecycle control. Both clients can retain the exact verdict for review.
    output = {"systemMessage": "PROJECT_CHECKPOINT_JSON: " + json.dumps(report, sort_keys=True)}
    if verdict in {"PASS", "NOT_APPLICABLE"}:
        print(json.dumps(output))
        return 0
    reason = "Project checkpoint remains " + verdict + ": " + "; ".join(issues)
    reason += ". Preserve retained work; resolve only this session's authorized checkpoint obligations. Do not create or release a foreign claim to silence this error."
    # Claude ignores stdout on exit 2 and feeds stderr back to the model.
    # A repeated Stop must end with an explicit blocked result rather than
    # repeatedly spending model turns. continue:false is Claude's documented
    # terminal control, not a PASS or a receipt; Codex retains nonzero failure.
    if payload.get("hook_event_name") == "Stop" and payload.get("stop_hook_active") is True:
        try:
            client, _native = _observer_native_identity(payload)
        except (OSError, ProjectStateError):
            client = None
        if client == "claude":
            output.update({"continue": False, "stopReason": reason})
            print(json.dumps(output))
            print(reason, file=sys.stderr)
            return 0
    print(json.dumps(output))
    print(reason, file=sys.stderr)
    return 2


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
    hook.add_argument("--repo-guard-root", type=Path)
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
            return _emit_checkpoint_hook("UNKNOWN", [str(exc)], {})
        verdict, issues = checkpoint_hook(
            payload,
            coordination_board=args.coordination_board,
            receipt_root=args.receipt_root,
            repo_guard_root=args.repo_guard_root,
        )
        return _emit_checkpoint_hook(verdict, issues, payload)
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

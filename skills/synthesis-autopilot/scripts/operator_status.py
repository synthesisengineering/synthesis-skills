#!/usr/bin/env python3
"""Bounded read-only operator projection of the existing run journal.

No actor is fabricated. Recorded completion, native liveness, current acceptance,
notification delivery and installed/loaded code are deliberately separate facts.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_state

MAX_RUNS = 32
DEFAULT_PAGE_SIZE = 8
MAX_DISCOVERY_ENTRIES = 4096
MAX_JOURNAL_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
SCHEMA = 1


def _text(value, limit=2048):
    return str(value)[:limit] if value is not None else None


def _safe(path, root, *, directory=False):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError("path escaped the selected project")
    # Reject redirects, including broken links, before opening any run content.
    for entry in [root, *[root.joinpath(*path.relative_to(root).parts[:n])
                          for n in range(1, len(path.relative_to(root).parts) + 1)]]:
        mode = entry.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("run path crosses a symbolic link")
    mode = path.lstat().st_mode
    if directory and not stat.S_ISDIR(mode) or not directory and not stat.S_ISREG(mode):
        raise ValueError("unsupported run file type")
    return path


def _guard_journal(project, run_id):
    run_state._uuid(run_id)
    home = project / "resources/autopilot-runs" / run_id
    directory = _safe(home / "events", project, directory=True)
    count, total, entries_seen = 0, 0, 0
    with os.scandir(directory) as entries:
        for entry in entries:
            entries_seen += 1
            if entries_seen > run_state.MAX_EVENTS + 64:
                raise ValueError("journal directory exceeds operator entry bound")
            if entry.name.startswith(".run-"):
                continue  # The existing owner excludes uncommitted temporary files.
            count += 1
            if count > run_state.MAX_EVENTS:
                raise ValueError("journal exceeds owner event bound")
            path = _safe(Path(entry.path), project)
            size = path.stat().st_size
            if size > run_state.MAX_JSON_BYTES:
                raise ValueError("event exceeds owner byte bound")
            total += size
            if total > MAX_JOURNAL_BYTES:
                raise ValueError("journal exceeds operator byte bound; use owner diagnostics")
    return home


def _supervision(state):
    if not state.get("extensions", {}).get("supervision"):
        return {"lifecycle": "not_enrolled", "requests": {}, "automatic_launch": "UNAVAILABLE", "authority_granted": False}
    try:
        import supervision
        view = supervision.status_view(state)
        return {**view, "currentness": "RECORDED_ONLY", "authority_granted": False}
    except (ImportError, ValueError, TypeError, KeyError):
        return {"lifecycle": "unknown", "requests": {}, "automatic_launch": "UNKNOWN", "authority_granted": False,
                "diagnostic": "Recorded supervision requires its matching owner reader."}


def _measured_progress(state):
    """Project the workflow owner's task-keyed histories without inventing proof."""
    histories = state.get("extensions", {}).get("workflow", {}).get("progress", {})
    if not isinstance(histories, dict):
        raise ValueError("workflow progress is not an owner task-history mapping")
    rows = []
    for task_id, history in histories.items():
        if not isinstance(history, list):
            raise ValueError("workflow task progress is not a history")
        for entry in history:
            if not isinstance(entry, dict):
                raise ValueError("workflow progress row is not an owner observation")
            if entry.get("meaningful") is True:
                if not isinstance(entry.get("attempt_id"), str):
                    raise ValueError("measured progress has no attempt identity")
                rows.append((task_id, entry))
    return rows


def _child_status(identity, row):
    """Child delivery, cancellation request and integration audit are distinct."""
    disposition, audit = row.get("disposition", "UNKNOWN"), row.get("audit_status", "UNKNOWN")
    return {"id": identity, "status": disposition, "disposition": disposition,
            "audit_status": audit, "unresolved": disposition != "complete" or audit != "accepted",
            "cancellation_requested": row.get("cancellation_requested", False),
            "artifact_ids": list(row.get("artifact_ids", [])), "evidence_ids": list(row.get("evidence_ids", [])),
            "authority_granted": False}


def _run(project, run_id):
    home = _guard_journal(project, run_id)
    last = None
    progress_revisions = {}
    # Stream the owner-validated chain. Journal order, not dictionary order or
    # wall-clock monotonicity, determines when useful progress was committed.
    for last in run_state._events(project, run_id):
        for task_id, entry in _measured_progress(last["state"]):
            identity = (task_id, entry["attempt_id"], run_state._digest(entry))
            progress_revisions.setdefault(identity, last["state"]["revision"])
    state = last["state"]
    if state.get("owner", {}).get("project_root") != str(project):
        raise ValueError("journal belongs to another project root")
    diagnostics = []
    try:
        projection = _safe(home / "current.json", project)
        if run_state._read(projection) != state:
            raise ValueError("projection differs")
    except (OSError, ValueError, TypeError):
        diagnostics.append("Derived current.json is missing or stale. Ask the admitted owner to rebuild it from the journal.")
    waits = state.get("waits", {})
    pending = [dict(value, id=key) for key, value in waits.items() if value.get("status") == "pending"]
    if len(pending) > 64:
        raise ValueError("pending questions exceed operator bound; use owner diagnostics")
    status = state["status"]
    display = ("completed" if status == "completed" else "cancelled" if status == "cancelled" else
               "unhealthy" if status in {"incomplete", "recovering"} else "waiting" if pending or status.startswith("waiting_") else "working")
    workflow = state.get("extensions", {}).get("workflow", {})
    measured = []
    for task_id, row in _measured_progress(state):
        revision = progress_revisions[(task_id, row["attempt_id"], run_state._digest(row))]
        measured.append({**{key: row.get(key) for key in ("at", "attempt_id", "outcome", "evidence_ids")},
                         "task_id": task_id, "journal_revision": revision,
                         "order_basis": "FIRST_COMMITTED_JOURNAL_REVISION"})
    measured.sort(key=lambda row: (row["journal_revision"], row["task_id"], row["attempt_id"]))
    budget = {}
    if "budget" in workflow:
        import workflow as owner
        budget = owner.budget_summary(state)
    children = workflow.get("children", {})
    effects = state.get("effects", {})
    ext = state.get("extensions", {})
    checkpoint = ext.get("controller", {}).get("checkpoint", {})
    continuation = ext.get("capabilities", {}).get("continuation") or {}
    return {
        "run_id": run_id, "project_id": state["owner"].get("project_id"), "revision": state["revision"],
        "journal_head": last["digest"], "status": display, "recorded_status": status,
        "created_at": state.get("created_at"), "updated_at": state.get("updated_at"),
        "owner": {key: state["owner"].get(key) for key in ("session_uuid", "native_ref")},
        "scope": [_text(x) for x in state.get("contract", {}).get("scope", [])[:16]],
        "questions": [{"id": x["id"], "kind": x["kind"], "reason": _text(x["reason"], 4096),
                       "reason_truncated": len(x["reason"]) > 4096, "at": x.get("at"), "status": "pending"} for x in pending],
        "last_note": {"summary": _text(state.get("progress", {}).get("summary")),
                      "at": state.get("progress", {}).get("at"), "measured": False},
        "last_useful_progress": measured[-1] if measured else None,
        "tasks": [{"id": key, "status": row.get("status")} for key, row in workflow.get("graph", {}).get("nodes", {}).items()],
        "children": [_child_status(key, row) for key, row in children.items()],
        "effects": [{"id": key, "status": row.get("status")} for key, row in effects.items()],
        "resources": budget, "billing": "UNKNOWN", "resource_scope": "owner ledger; estimates and measured usage are not an invoice",
        "checkpoint": {key: checkpoint.get(key) for key in ("at", "reason", "revision")},
        "supervision": _supervision(state),
        "continuation": {"recorded_state": continuation.get("status", "unregistered"), "current_verification": "UNKNOWN"},
        "completion": state.get("completion"), "current_acceptance": "UNKNOWN", "native_liveness": "UNKNOWN",
        "notification_delivery": "UNKNOWN", "loaded_in_native_session": "UNKNOWN", "authority_granted": False,
        "diagnostics": diagnostics, "currentness": "JOURNAL_VERIFIED_RECORDED_STATE",
    }


def inspect_project(project, run_id=None, *, limit=DEFAULT_PAGE_SIZE, cursor=None):
    if type(limit) is not int or not 1 <= limit <= MAX_RUNS:
        raise ValueError('page size must be between 1 and 32')
    if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 512 or run_id):
        raise ValueError('invalid page cursor or exact-run combination')
    supplied = Path(project).absolute()
    # Source may be configured through a canonical root; selected project itself
    # and all descendants must have a real path, not an alias to another project.
    if supplied.is_symlink() or supplied.resolve(strict=True) != supplied:
        raise ValueError("project path must be canonical and cannot cross symbolic links")
    project = _safe(supplied, supplied, directory=True)
    home = project / "resources/autopilot-runs"
    inventory = []
    if not home.exists() and not home.is_symlink():
        if run_id:
            raise ValueError("selected run does not exist")
        ids = []
    else:
        _safe(home, project, directory=True)
        if run_id:
            run_state._uuid(run_id)
            ids = [run_id]
        else:
            ids = []
            entries_seen = 0
            with os.scandir(home) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > MAX_DISCOVERY_ENTRIES:
                        raise ValueError("run directory exceeds operator entry bound; select an exact run")
                    if re.fullmatch(r"\.plan-[a-f0-9]{24}\.lock", entry.name):
                        _safe(Path(entry.path), project)
                        continue  # Existing owner's per-plan lock, not a run.
                    if entry.name.startswith(".run-"):
                        continue
                    info = entry.stat(follow_symlinks=False)
                    inventory.append((entry.name, info.st_mtime_ns, info.st_mode))
            # Filesystem times are discovery hints only. Every displayed state
            # still comes from the complete verified journal, never this index.
            inventory.sort(key=lambda row: (-row[1], row[0]))
            ids = [row[0] for row in inventory]
    inventory_digest = hashlib.sha256(json.dumps([str(project), inventory], separators=(',', ':')).encode()).hexdigest()
    offset = 0
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if (not isinstance(value, list) or len(value) != 3 or value[0] != inventory_digest
                    or type(value[1]) is not int or value[1] < 1 or value[1] >= len(ids)
                    or value[2] != limit):
                raise ValueError('stale or invalid page cursor; refresh the first page')
            offset = value[1]
        except (ValueError, UnicodeError, TypeError) as error:
            raise ValueError('stale or invalid page cursor; refresh the first page') from error
    total = len(ids)
    ids = ids[offset:offset + limit]
    next_cursor = (base64.urlsafe_b64encode(json.dumps([inventory_digest, offset + limit, limit], separators=(',', ':')).encode()).decode()
                   if offset + limit < total else None)
    rows = []
    for identity in ids:
        try:
            rows.append(_run(project, identity))
        except (OSError, ValueError, TypeError, KeyError) as error:
            rows.append({"run_id": identity, "status": "unhealthy", "recorded_status": "UNKNOWN",
                         "currentness": "UNVERIFIABLE", "authority_granted": False,
                         "diagnostics": [_text(str(error))], "questions": [], "current_acceptance": "UNKNOWN"})
    return {"schema_version": SCHEMA, "project": str(project), "observed_at": datetime.now(timezone.utc).isoformat(),
            "scope": "READ_ONLY_OPERATOR_VIEW", "authority_granted": False, "runs": rows,
            "pagination": {"total": total, "offset": offset, "limit": limit, "next_cursor": next_cursor,
                           "order": "FILESYSTEM_RECENCY_HINT", "inventory_sha256": inventory_digest,
                           "questions_scope": "THIS_PAGE_ONLY"},
            "limits": {"runs_per_page": MAX_RUNS, "discovery_entries": MAX_DISCOVERY_ENTRIES, "journal_bytes": MAX_JOURNAL_BYTES, "output_bytes": MAX_OUTPUT_BYTES},
            "helper": {"path": str(Path(__file__).resolve()), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       "loaded_in_native_session": "UNKNOWN"}}


def inspect_registry(index, project_id, run_id=None, *, limit=DEFAULT_PAGE_SIZE, cursor=None,
                     repo_guard_root=None, coordination_board=None, checkpoint_receipt_root=None):
    index = Path(index).absolute()
    if index.resolve(strict=True) != index or index.is_symlink() or not index.is_file() or index.stat().st_size > MAX_OUTPUT_BYTES:
        raise ValueError('project registry is unsafe or exceeds the read bound')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', project_id):
        raise ValueError('invalid registered project identity')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'synthesis-project-management/scripts'))
    import project_state
    synthesis = Path(os.environ.get('SYNTHESIS_HOME', str(Path.home() / '.synthesis')))
    board = Path(coordination_board) if coordination_board is not None else Path(os.environ.get('SYNTHESIS_COORDINATION_BOARD', str(synthesis / 'coordination/active-sessions.md')))
    before = hashlib.sha256(index.read_bytes()).hexdigest()
    recovered = project_state.resolve_project(project_id, index,
        repo_guard_root=Path(repo_guard_root) if repo_guard_root is not None else synthesis / 'repo-guard',
        checkpoint_receipt_root=Path(checkpoint_receipt_root) if checkpoint_receipt_root is not None else synthesis / 'project-state/receipts',
        coordination_board=board if coordination_board is not None or board.exists() else None,
        fetch=False, fast_forward_canonical=False, refresh_coordination=False)
    if hashlib.sha256(index.read_bytes()).hexdigest() != before:
        raise ValueError('project registry changed during resolution; refresh')
    resolution = {"status": recovered.status, "selected_path": recovered.selected_path,
                  "selected_head": recovered.selected_head, "selected_tree": recovered.selected_tree,
                  "issues": [_text(issue) for issue in recovered.issues[:32]],
                  "fetch": False, "refresh_coordination": False, "authority_granted": False}
    if recovered.status in {'PASS', 'LOCAL_RECOVERABLE'} and recovered.selected_path:
        # PM reports resolved paths. Retain the original registry-relative
        # worktree binding too, so resolving a tracked project symlink cannot
        # turn unrelated content into the selected project's operator view.
        repository = project_state._repository_root(index.parent)
        relative = (index.parent / project_id).relative_to(repository)
        selected = Path(recovered.selected_path)
        if not any(candidate.worktree and candidate.project_path == str(selected)
                   and Path(candidate.worktree) / relative == selected
                   and candidate.head == recovered.selected_head and candidate.project_tree == recovered.selected_tree
                   for candidate in recovered.candidates):
            raise ValueError('causal selection is not the exact physical project in its registered worktree')
        result = inspect_project(recovered.selected_path, run_id, limit=limit, cursor=cursor)
    else:
        result = {"schema_version": SCHEMA, "scope": "READ_ONLY_OPERATOR_VIEW", "project": None,
                  "observed_at": datetime.now(timezone.utc).isoformat(), "authority_granted": False, "runs": [],
                  "helper": {"path": str(Path(__file__).resolve()), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             "loaded_in_native_session": "UNKNOWN"}}
    result.update(registry={"path": str(index), "sha256": before, "project_id": project_id}, resolution=resolution)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--project")
    selection.add_argument("--index")
    parser.add_argument("--project-id")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--cursor")
    args = parser.parse_args(argv)
    try:
        if args.index and not args.project_id or args.project and args.project_id:
            raise ValueError('registry selection requires --index and --project-id together')
        result = (inspect_registry(args.index, args.project_id, args.run_id, limit=args.limit, cursor=args.cursor) if args.index
                  else inspect_project(args.project, args.run_id, limit=args.limit, cursor=args.cursor))
        encoded = json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False)
        if len(encoded.encode()) > MAX_OUTPUT_BYTES:
            raise ValueError("operator response exceeds output bound; select an exact run")
        print(encoded)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        print(json.dumps({"schema_version": SCHEMA, "scope": "READ_ONLY_OPERATOR_VIEW", "status": "UNHEALTHY",
                          "authority_granted": False, "diagnostic": _text(str(error))}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

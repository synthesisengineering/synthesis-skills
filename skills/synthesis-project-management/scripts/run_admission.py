#!/usr/bin/env python3
"""PM-owned admission for durable run mutations.

Admission is a fresh coordination/native-identity proof, not action permission.
This module reuses PM's exact physical worktree, segment-glob and native
transcript policies. A workspace listing alone never authorizes a write.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import fcntl as fcntl  # existing consumer/test module re-export
import hashlib
import json
import os as os  # existing consumer/test module re-export
from pathlib import Path
import time

import coordination
from board_grammar import parse_table_rows
from coordination_lock import AdmissionError, bounded_lock
from project_recipient import registry_entries
from project_state import observer_native_identity, row_for_event


_ISSUED = object()
_ACTIVE_OBSERVATION = ContextVar("run_admission_operation", default=None)


def _fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class _AdmittedPaths(dict):
    """Serializable proof data with non-transferable issuance metadata."""

    def __init__(self, value, actor, marker):
        if marker is not _ISSUED:
            raise AdmissionError("admission proof must originate from PM")
        super().__init__(value)
        self._actor = _fingerprint(actor)
        self._digest = _fingerprint(value)
        self._issued_at = time.monotonic()
        self._consumed = False

    def __deepcopy__(self, memo):
        # Stored events and ordinary copies retain facts, not issuance rights.
        return deepcopy(dict(self), memo)


class _PassivePaths(_AdmittedPaths):
    """A separately typed lifecycle observation, never mutation admission."""


class _AdmissionObservation:
    def __init__(self, proof, actor, project, marker):
        if marker is not _ISSUED:
            raise AdmissionError("observation token must originate from PM")
        self.proof = deepcopy(dict(proof))
        self.actor = _fingerprint(actor)
        self.project = str(Path(project).resolve(strict=True))
        self.active = True

    def __deepcopy__(self, memo):
        return self  # Copying context cannot mint another active operation.

    def __reduce__(self):
        raise TypeError("operation admission cannot be serialized")


@contextmanager
def admission_scope(proof, actor, project, *, purpose="mutation"):
    """Reuse one fresh admission solely inside central read-only observation.

    This is neither a receipt cache nor a transferable capability. JSON loses
    issuance metadata; a proof is consumed once; the token expires when this
    context exits. Mutation entry and every later Stop re-admit through PM.
    """
    expected_type = {"mutation": _AdmittedPaths, "passive-stop": _PassivePaths}.get(
        purpose
    )
    if (
        expected_type is None
        or type(proof) is not expected_type
        or proof._consumed
        or proof._digest != _fingerprint(proof)
        or proof._actor != _fingerprint(actor)
        or str(Path(project).resolve(strict=True)) != proof.get("project_root")
        or time.monotonic() - proof._issued_at > 1.0
        or _ACTIVE_OBSERVATION.get() is not None
    ):
        raise AdmissionError(
            "fresh exact unused PM admission is required for this operation"
        )
    proof._consumed = True
    observation = _AdmissionObservation(proof, actor, project, _ISSUED)
    reset = _ACTIVE_OBSERVATION.set(observation)
    try:
        yield observation
    finally:
        observation.active = False
        _ACTIVE_OBSERVATION.reset(reset)


def read_admission_observation(context):
    """Read only a live token in its originating actor/project operation."""
    token = context.get("admission_observation")
    if (
        not isinstance(token, _AdmissionObservation)
        or not token.active
        or _ACTIVE_OBSERVATION.get() is not token
        or token.actor != _fingerprint(context.get("actor"))
        or token.project != str(Path(context["project"]).resolve(strict=True))
        or token.proof != context.get("binding")
    ):
        raise AdmissionError(
            "admission observation is inactive, transferred, or rebound"
        )
    return deepcopy(token.proof)


def safe_path(path: Path, boundary: Path) -> Path:
    """Reject traversal/symlink components below an independently known root."""
    path, boundary = Path(path).absolute(), Path(boundary).resolve(strict=True)
    if ".." in path.parts:
        raise AdmissionError("path contains traversal")
    try:
        relative = path.relative_to(boundary)
    except ValueError as exc:
        raise AdmissionError("path is outside its admitted boundary") from exc
    cursor = boundary
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise AdmissionError("path crosses a symlink")
    if not path.resolve().is_relative_to(boundary):
        raise AdmissionError("physical path is outside its admitted boundary")
    return path


def _snapshot(board: Path, *, readonly: bool = False) -> str:
    if board.is_symlink() or not board.is_file() or board.parent.is_symlink():
        raise AdmissionError("coordination board is missing or unsafe")
    if readonly:
        try:
            return coordination.passive_board_snapshot(board)
        except (OSError, RuntimeError) as exc:
            raise AdmissionError(str(exc)) from exc
    # Same lock and leased CAS fence as coordination._check_staged_board_snapshot.
    # Queue for at most two existing Git operation budgets (60s by default).
    # This is a queue bound, not a guarantee that all remote CAS retries finish
    # inside it. A longer-held lock remains an explicit unresolved admission;
    # the read-only Stop path above never waits or weakens the lease fence.
    with bounded_lock(
        board.parent / ".active-sessions.lock",
        timeout=2 * coordination.LEASE_GIT_TIMEOUT,
    ):
        config = coordination.lease_configuration(board)
        if config is not None:
            coordination.lease_update(
                board, config, lambda text: text, require_fence=True
            )
        text = board.read_text(encoding="utf-8")
        if config is None and coordination.declared_lease(text) is not None:
            raise AdmissionError(
                "declared coordination lease has no local configuration"
            )
        return text


def reconcile_readback(board: Path) -> dict:
    """Refresh an active controller's mirror, never grant admission or mutate a run.

    Owner CAS invalidates the passive stamp. Active callers may reconcile through
    the existing PM lease reader, then must revalidate their exact owner/paths.
    Passive Stop and read-only inspection never invoke this mutating mirror seam.
    No older cache is accepted and no lease is bootstrapped when unavailable.
    """
    board = Path(board).expanduser().absolute()
    if board.is_symlink() or not board.is_file() or board.parent.is_symlink():
        raise AdmissionError("coordination board is missing or unsafe")
    try:
        with bounded_lock(
            board.parent / ".active-sessions.lock",
            timeout=2 * coordination.LEASE_GIT_TIMEOUT,
        ):
            result = coordination._lease_refresh_locked(board)
            if result.get("cache_warning"):
                raise AdmissionError(
                    "fresh PM snapshot could not be retained: "
                    + result["cache_warning"]
                )
            return result
    except (OSError, RuntimeError, ValueError) as exc:
        raise AdmissionError(
            "owner readback refresh unavailable; committed journal remains retained: "
            + str(exc)
        ) from exc


def native_binding(
    board: Path,
    native_payload: dict,
    *,
    readonly: bool = False,
    optional: bool = False,
    _passive_paths=None,
) -> dict | None:
    """Resolve one active native seat without scanning run storage."""
    try:
        board = Path(board).expanduser().absolute()
        if optional and not board.exists():
            return None
        text = _snapshot(board, readonly=readonly)
        if "Team-Contract:" in text or "Board-Schema: 6" in text:
            coordination.validate_team_transition(board, text, text)
        parsed_rows = parse_table_rows(text)
        row = row_for_event(parsed_rows, native_payload, board=board)
        if row is None:
            if optional:
                return None
            raise AdmissionError("native event has no unique active coordination seat")
        client, native = observer_native_identity(native_payload)
        sessions = coordination.sessions_from_parsed_rows(parsed_rows)
        session = coordination.find_session(sessions, row["session uuid"])
        if session is None or session.status.lower() != "active":
            raise AdmissionError("native seat is not active")
        if _passive_paths is not None and not readonly:
            raise AdmissionError("passive inspection cannot authorize a mutation")
        problems = (
            coordination.validate_sessions(sessions)
            if _passive_paths is None
            else coordination.validate_passive_paths(sessions, session, _passive_paths)
        )
        if problems:
            raise AdmissionError(
                "coordination admission is unresolved: " + "; ".join(problems)
            )
        # Validate the human aliases too; a contradictory identity is not proof.
        from coordination_schema import identity_from_uuid

        expected = identity_from_uuid(session.session_uuid)
        if (
            session.compact_id != expected.compact_id
            or session.speakable_id != expected.speakable_id
        ):
            raise AdmissionError("coordination seat aliases do not bind its UUID")
        scope = {
            "session_uuid": session.session_uuid,
            "native_ref": session.client_ref,
            "project_id": session.project,
            "workspaces": sorted(session.workspaces),
            "claims": sorted(session.claims),
            "machine": session.machine,
        }
        if session.person:
            import team_contract

            declared = team_contract.board_principal(
                board, native_payload=native_payload
            )
            scope["team"] = {
                "person": session.person,
                "standing_role": session.standing_role,
                "declaration_sha256": declared["sha256"],
                "inventory": sorted(
                    (
                        s.session_uuid,
                        s.client_ref,
                        s.person,
                        s.standing_role,
                        s.status,
                        s.project,
                        sorted(s.workspaces),
                        sorted(s.claims),
                    )
                    for s in sessions
                ),
            }
        return {
            **scope,
            "claim_hash": hashlib.sha256(
                json.dumps(scope, sort_keys=True).encode()
            ).hexdigest(),
            "client": client,
            "native_session_id": native,
            "board": str(board),
        }
    except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, AdmissionError):
            raise
        raise AdmissionError(f"native admission failed: {exc}") from exc


def admit_paths(
    board: Path,
    project_id: str,
    project: Path,
    paths: list[Path],
    native_payload: dict,
    *,
    expected_claim_hash: str | None = None,
    readonly: bool = False,
) -> dict:
    """Authorize exact paths for a registered project and native coordination seat.

    The returned digest excludes heartbeats, but binds claims, project, seat,
    machine and exact workspaces. Consumers must re-admit each mutation; this
    record is not a transferable capability or a publish/deploy approval.
    """
    return _admit_paths(
        board,
        project_id,
        project,
        paths,
        native_payload,
        expected_claim_hash=expected_claim_hash,
        readonly=readonly,
    )


def inspect_paths(
    board: Path, project_id: str, project: Path, paths: list[Path], native_payload: dict
) -> dict:
    """Fresh, exact, read-only Stop proof; no global-board or write verdict."""
    return _admit_paths(
        board, project_id, project, paths, native_payload, readonly=True, passive=True
    )


def _admit_paths(
    board,
    project_id,
    project,
    paths,
    native_payload,
    *,
    expected_claim_hash=None,
    readonly=False,
    passive=False,
):
    try:
        project = Path(project).absolute()
        repository, branch = coordination._repository_state(project)
        project = safe_path(project, repository)
        if project != repository / "projects" / project_id:
            raise AdmissionError("project is not the exact registry-owned directory")
        registry = safe_path(repository / "projects/index.yaml", repository)
        import team_contract

        team_contract.require_registry(
            registry, board=board, native_payload=native_payload
        )
        if project_id not in registry_entries(registry.read_text(encoding="utf-8")):
            raise AdmissionError("project is not registered")
        if not paths:
            raise AdmissionError("admission requires explicit paths")
        target_workspaces = {}
        targets = []
        repositories = {repository: branch}
        for raw in paths:
            target = Path(raw).absolute()
            if target.is_relative_to(repository):
                target_root, target_branch = repository, branch
            else:
                existing = target
                while not existing.is_dir() and existing != existing.parent:
                    existing = existing.parent
                target_root, target_branch = coordination._repository_state(existing)
            target = safe_path(target, target_root)
            targets.append(target)
            repositories[target_root] = target_branch
            target_workspaces[str(target)] = {
                "repository": str(target_root),
                "branch": target_branch,
            }
        binding = native_binding(
            Path(board),
            native_payload,
            readonly=readonly,
            _passive_paths=targets if passive else None,
        )
        if binding["project_id"] != project_id:
            raise AdmissionError("native seat belongs to a different project")
        if (
            expected_claim_hash is not None
            and binding["claim_hash"] != expected_claim_hash
        ):
            raise AdmissionError("coordination claim changed")
        # Reconstruct no policy: these are the exact functions check-staged uses.
        session = coordination.Session(
            binding["session_uuid"],
            "",
            "",
            "",
            "",
            binding["machine"],
            project_id,
            "",
            "",
            "",
            binding["workspaces"],
            "",
            binding["claims"],
            "",
            "active",
        )
        for target_root, target_branch in repositories.items():
            if not coordination._workspace_registered(
                session, target_root, target_branch
            ):
                raise AdmissionError(
                    "exact physical worktree and branch are not registered"
                )
            relative = [
                str(path.relative_to(target_root))
                for path in targets
                if target_workspaces[str(path)]["repository"] == str(target_root)
            ]
            outside = coordination._outside_claim(session, target_root, relative)
            if outside:
                raise AdmissionError(
                    "write paths are outside the current exact claim: "
                    + ", ".join(outside)
                )
            if coordination._repository_state(target_root) != (
                target_root,
                target_branch,
            ):
                raise AdmissionError("worktree identity changed during admission")
        proof_type = _PassivePaths if passive else _AdmittedPaths
        purpose = (
            {"purpose": "passive-stop", "global_board_validated": False}
            if passive
            else {}
        )
        return proof_type(
            {
                **binding,
                **purpose,
                "project_root": str(project),
                "repository": str(repository),
                "branch": branch,
                "paths": [str(path) for path in targets],
                "target_workspaces": target_workspaces,
            },
            {
                "board": str(Path(board).expanduser().absolute()),
                "native_payload": native_payload,
            },
            _ISSUED,
        )
    except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, AdmissionError):
            raise
        raise AdmissionError(f"run admission failed: {exc}") from exc

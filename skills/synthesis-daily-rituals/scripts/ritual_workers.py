#!/usr/bin/env python3
"""Ritual workers registry: load ``workers.yaml`` with fleet path expansion.

Contract: ``references/ritual-worker-contract.md``. The registry is synced
person-level state, so persisted ``artifact_dir`` values are ``~``-rooted
(fleet design section 6.1) and expand at load. Legacy absolute values keep
loading; relative values fail closed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

CONTRACT_VERSION = 1
WORKER_STATUSES = ("active", "on-demand", "dormant")
DEFAULT_REGISTRY = Path.home() / ".synthesis" / "ritual" / "workers.yaml"


class RitualWorkersError(ValueError):
    """A malformed ritual workers registry."""


@dataclass(frozen=True)
class Worker:
    workspace_id: str
    status: str
    artifact_dir: str
    artifact_dir_raw: str
    seat: str

    def artifact_path(self, name: str) -> Path:
        return Path(self.artifact_dir) / name


def expand_worker_path(value: str) -> str:
    """Expand a persisted worker path for this Mac."""
    return os.path.expandvars(os.path.expanduser(value))


def load_workers(path: Path | None = None) -> dict[str, Worker]:
    """Load the workers registry; absent registry means no workers.

    An absent file is the classic single-session ritual, not an error.
    Present files must carry ``contract_version: 1`` and a workers map
    whose entries validate; anything else fails closed.
    """
    registry = Path(path) if path is not None else DEFAULT_REGISTRY
    try:
        text = registry.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RitualWorkersError(f"workers registry unreadable: {registry}: {exc}")
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RitualWorkersError(f"workers registry is not YAML: {registry}: {exc}")
    if not isinstance(document, dict):
        raise RitualWorkersError(f"workers registry must be a mapping: {registry}")
    if document.get("contract_version") != CONTRACT_VERSION:
        raise RitualWorkersError(
            f"workers registry contract_version must be {CONTRACT_VERSION}: {registry}"
        )
    raw_workers = document.get("workers", {})
    if not isinstance(raw_workers, dict):
        raise RitualWorkersError(f"workers registry workers must be a mapping: {registry}")
    workers: dict[str, Worker] = {}
    for workspace_id, entry in raw_workers.items():
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise RitualWorkersError(f"worker id must be a non-empty string: {registry}")
        if not isinstance(entry, dict):
            raise RitualWorkersError(
                f"worker {workspace_id!r} must be a mapping: {registry}"
            )
        status = entry.get("status")
        if status not in WORKER_STATUSES:
            raise RitualWorkersError(
                f"worker {workspace_id!r} status must be one of "
                f"{list(WORKER_STATUSES)}: {registry}"
            )
        raw_dir = entry.get("artifact_dir")
        if not isinstance(raw_dir, str) or not raw_dir.strip():
            raise RitualWorkersError(
                f"worker {workspace_id!r} artifact_dir must be a non-empty "
                f"path string: {registry}"
            )
        expanded = expand_worker_path(raw_dir.strip())
        if not os.path.isabs(expanded):
            raise RitualWorkersError(
                f"worker {workspace_id!r} artifact_dir must expand to an "
                f"absolute path: {registry}"
            )
        seat = entry.get("seat")
        if not isinstance(seat, str) or not seat.strip():
            raise RitualWorkersError(
                f"worker {workspace_id!r} seat must be a non-empty string: {registry}"
            )
        workers[workspace_id] = Worker(
            workspace_id=workspace_id,
            status=status,
            artifact_dir=expanded,
            artifact_dir_raw=raw_dir.strip(),
            seat=seat.strip(),
        )
    return workers


def active_workers(workers: dict[str, Worker]) -> dict[str, Worker]:
    """Workers due every run; dormant workers never run, on-demand run by day."""
    return {
        workspace_id: worker
        for workspace_id, worker in workers.items()
        if worker.status == "active"
    }

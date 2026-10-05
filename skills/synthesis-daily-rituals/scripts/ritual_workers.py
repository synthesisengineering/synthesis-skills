#!/usr/bin/env python3
"""Ritual workers registry: load ``workers.yaml`` with fleet path expansion.

Contract: ``references/ritual-worker-contract.md``. The registry is synced
person-level state, so persisted ``artifact_dir`` values are ``~``-rooted
(fleet design section 6.1) and expand at load. Legacy absolute values keep
loading; relative values fail closed.
"""

from __future__ import annotations

import os
import hashlib
import re
import stat
from datetime import date, datetime, timezone
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
    workspace_root: str | None = None
    surfaces: tuple[str, ...] = ()

    def artifact_path(self, name: str) -> Path:
        if Path(name).name != name or name in {"", ".", ".."}:
            raise RitualWorkersError("artifact name must be one path component")
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
    override = os.environ.get("RITUAL_WORKERS_FILE")
    if path is None and override:
        scratch = os.environ.get("RITUAL_STATE_DIR")
        production = Path.home() / ".synthesis/rituals"
        if not scratch or Path(scratch).resolve() == production.resolve():
            raise RitualWorkersError(
                "registry override is restricted to an explicit non-production state directory"
            )
    registry = Path(path) if path is not None else Path(override or DEFAULT_REGISTRY)
    try:
        resolved = registry.resolve(strict=True)
    except FileNotFoundError as exc:
        if any(part.is_symlink() for part in (registry, *registry.parents)):
            raise RitualWorkersError(
                f"workers registry has a broken owner link: {registry}"
            ) from exc
        return {}
    except OSError as exc:
        raise RitualWorkersError(
            f"workers registry cannot be resolved: {registry}: {exc}"
        ) from exc
    try:
        text = read_regular(resolved, MAX_REGISTRY_BYTES).decode("utf-8")
    except (OSError, UnicodeError) as exc:
        # Once an existing registry was selected, disappearance is an integrity
        # failure. It must not turn a registered worker into a single session.
        raise RitualWorkersError(
            f"workers registry unreadable: {registry}: {exc}"
        ) from exc
    try:
        document = strict_yaml(text)
    except yaml.YAMLError as exc:
        raise RitualWorkersError(f"workers registry is not YAML: {registry}: {exc}")
    if not isinstance(document, dict):
        raise RitualWorkersError(f"workers registry must be a mapping: {registry}")
    if (
        type(document.get("contract_version")) is not int
        or document["contract_version"] != CONTRACT_VERSION
    ):
        raise RitualWorkersError(
            f"workers registry contract_version must be {CONTRACT_VERSION}: {registry}"
        )
    raw_workers = document.get("workers", {})
    if not isinstance(raw_workers, dict):
        raise RitualWorkersError(
            f"workers registry workers must be a mapping: {registry}"
        )
    workers: dict[str, Worker] = {}
    for workspace_id, entry in raw_workers.items():
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise RitualWorkersError(
                f"worker id must be a non-empty string: {registry}"
            )
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
        workspace_root = entry.get("workspace_root")
        if workspace_root is not None:
            if not isinstance(workspace_root, str) or not os.path.isabs(
                expand_worker_path(workspace_root)
            ):
                raise RitualWorkersError(
                    "workspace_root must expand to an absolute path"
                )
            workspace_root = expand_worker_path(workspace_root)
        surfaces = entry.get("surfaces", [])
        if (
            not isinstance(surfaces, list)
            or any(not isinstance(x, str) or not x.strip() for x in surfaces)
            or len(set(surfaces)) != len(surfaces)
        ):
            raise RitualWorkersError(
                "worker surfaces must be a unique list of nonempty strings"
            )
        workers[workspace_id] = Worker(
            workspace_id=workspace_id,
            status=status,
            artifact_dir=expanded,
            artifact_dir_raw=raw_dir.strip(),
            seat=seat.strip(),
            workspace_root=workspace_root,
            surfaces=tuple(surfaces),
        )
    return workers


def active_workers(workers: dict[str, Worker]) -> dict[str, Worker]:
    """Workers due every run; dormant workers never run, on-demand run by day."""
    return {
        workspace_id: worker
        for workspace_id, worker in workers.items()
        if worker.status == "active"
    }


MAX_REGISTRY_BYTES = 262144
MAX_ARTIFACT_BYTES = 262144
BODY_SECTIONS = (
    "Decisions needed",
    "Calendar & conflicts",
    "On your behalf",
    "Waiting on others",
    "Brief",
    "Backlog deltas",
    "Lesson candidates",
)


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in result:
                raise RitualWorkersError("duplicate YAML key")
            result[key] = loader.construct_object(value_node, deep=deep)
        except TypeError as exc:
            raise RitualWorkersError("YAML keys must be scalar") from exc
    return result


_UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def strict_yaml(text):
    # Size is checked before parsing; token/depth bounds prevent pathological
    # bounded-byte YAML from consuming unbounded parser time or recursion.
    try:
        depth = 0
        for count, token in enumerate(yaml.scan(text), 1):
            if count > 20000:
                raise RitualWorkersError("ritual YAML exceeds token bound")
            if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)):
                raise RitualWorkersError(
                    "YAML aliases are not permitted in ritual evidence"
                )
            if isinstance(
                token,
                (
                    yaml.tokens.BlockMappingStartToken,
                    yaml.tokens.BlockSequenceStartToken,
                    yaml.tokens.FlowMappingStartToken,
                    yaml.tokens.FlowSequenceStartToken,
                ),
            ):
                depth += 1
                if depth > 32:
                    raise RitualWorkersError("ritual YAML exceeds nesting bound")
            elif isinstance(
                token,
                (
                    yaml.tokens.BlockEndToken,
                    yaml.tokens.FlowMappingEndToken,
                    yaml.tokens.FlowSequenceEndToken,
                ),
            ):
                depth -= 1
        return yaml.load(text, Loader=_UniqueLoader)
    except (yaml.YAMLError, RecursionError, UnicodeError) as exc:
        raise RitualWorkersError(
            "ritual YAML is malformed or exceeds parser bounds"
        ) from exc


def read_regular(path: Path, limit: int, *, owner_only=True) -> bytes:
    """Bounded no-follow descriptor read, including every parent directory."""
    if ".." in Path(path).parts:
        raise RitualWorkersError("artifact path traversal")
    path = Path(os.path.abspath(path))
    current = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    parents = [os.fstat(current)]
    fd = None
    try:
        for part in path.parts[1:-1]:
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = next_fd
            parents.append(os.fstat(current))
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current
        )
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RitualWorkersError("artifact must be a singly linked regular file")
        if not before.st_mode & stat.S_IRUSR or before.st_mode & 0o022:
            raise RitualWorkersError(
                "artifact is unreadable or writable by another user"
            )
        if owner_only and before.st_uid != os.getuid():
            raise RitualWorkersError("artifact belongs to another owner")
        if before.st_size > limit:
            raise RitualWorkersError("ritual input exceeds bounded size")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        fields = (
            "st_dev",
            "st_ino",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_gid",
        )
        if len(raw) > limit or any(
            getattr(before, key) != getattr(after, key) for key in fields
        ):
            raise RitualWorkersError("ritual input changed during bounded read")
        # Reopen the pathname through no-follow directory descriptors. A file
        # descriptor alone can still name an old file after its path is replaced.
        verify_fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(verify_fd)
            if (opened.st_dev, opened.st_ino) != (parents[0].st_dev, parents[0].st_ino):
                raise RitualWorkersError("artifact root changed during read")
            for part, original in zip(path.parts[1:-1], parents[1:], strict=True):
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=verify_fd
                )
                os.close(verify_fd)
                verify_fd = child
                opened = os.fstat(verify_fd)
                if (opened.st_dev, opened.st_ino) != (original.st_dev, original.st_ino):
                    raise RitualWorkersError("artifact parent changed during read")
            present = os.stat(path.name, dir_fd=verify_fd, follow_symlinks=False)
            if any(getattr(before, key) != getattr(present, key) for key in fields):
                raise RitualWorkersError("artifact path identity changed during read")
        finally:
            os.close(verify_fd)
        return raw
    finally:
        if fd is not None:
            os.close(fd)
        os.close(current)


def worker_readiness(worker: Worker) -> list[str]:
    gaps = []
    if worker.status == "dormant":
        gaps.append("worker is dormant")
    if not worker.workspace_root:
        gaps.append("registry workspace_root is missing")
    else:
        base = Path(worker.workspace_root)
        artifact_dir = Path(worker.artifact_dir)
        if base == Path(base.anchor) or base == Path.home() or not base.is_dir():
            gaps.append(
                "workspace_root must name an existing bounded workspace directory"
            )
        if (
            not base.is_absolute()
            or ".." in base.parts
            or not artifact_dir.is_relative_to(base)
            or artifact_dir == base
        ):
            gaps.append("artifact directory is outside its declared workspace root")
        if base.resolve() != base or artifact_dir.resolve() != artifact_dir:
            gaps.append("workspace or artifact directory has a symbolic-link alias")
    if not worker.surfaces:
        gaps.append(
            "registry surfaces are missing; declare the actual coverage contract"
        )
    return gaps


def verify_artifact(
    worker: Worker,
    *,
    day: str,
    run_type: str,
    session: str | None,
    outcome: str,
    cwd: Path | None = None,
) -> dict:
    """Validate only this workspace's actual artifact; never invent or repair one."""
    gaps = worker_readiness(worker)
    if gaps:
        raise RitualWorkersError("worker readiness: " + "; ".join(gaps))
    if run_type not in {"day-start", "midday", "day-end", "weekly-review"}:
        raise RitualWorkersError("unsupported worker run type")
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise RitualWorkersError("worker date must be canonical ISO date")
    if outcome not in {
        "clean",
        "complete",
        "completed",
        "success",
        "partial",
        "failed",
        "skipped",
        "blocked",
        "degraded",
    }:
        raise RitualWorkersError(
            "worker outcome must use the explicit completion/partial/failure vocabulary"
        )
    if not session or not session.strip():
        raise RitualWorkersError(
            "worker completion needs the actual --session identity"
        )
    location = Path(cwd or Path.cwd()).resolve()
    if not location.is_relative_to(Path(worker.workspace_root)):
        raise RitualWorkersError(
            "foreign workspace: run from the registered workspace root"
        )
    artifact = worker.artifact_path(f"{day}-{run_type}.md")
    try:
        raw = read_regular(artifact, MAX_ARTIFACT_BYTES)
    except FileNotFoundError as exc:
        raise RitualWorkersError(f"worker artifact absent: {artifact}") from exc
    except OSError as exc:
        raise RitualWorkersError(
            f"worker artifact unreadable or unsafe: {artifact}: {exc.strerror}"
        ) from exc
    try:
        text = raw.decode("utf-8")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise RitualWorkersError("artifact needs YAML frontmatter")
        header, body = text[4:].split("\n---\n", 1)
        data = strict_yaml(header)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise RitualWorkersError("artifact encoding/frontmatter is invalid") from exc
    if not isinstance(data, dict):
        raise RitualWorkersError("artifact frontmatter must be a mapping")
    for key, expected in {
        "contract_version": 1,
        "workspace": worker.workspace_id,
        "seat": worker.seat,
        "date": day,
        "run_type": run_type,
        "session": session,
        "outcome": outcome,
    }.items():
        actual = data.get(key)
        # YAML's unquoted date scalar is accepted only for the date field.
        if key == "date" and type(actual) is date:
            actual = actual.isoformat()
        if actual != expected or (
            key == "contract_version" and type(actual) is not int
        ):
            raise RitualWorkersError(f"foreign or mismatched artifact field: {key}")
    if not isinstance(data.get("agent"), str) or not data["agent"].strip():
        raise RitualWorkersError("artifact agent identity is missing")
    try:
        times = [
            datetime.fromisoformat(str(data[key]).replace("Z", "+00:00"))
            for key in ("started", "finished")
        ]
        if (
            any(t.tzinfo is None for t in times)
            or times[0] > times[1]
            or times[1] > datetime.now(timezone.utc)
        ):
            raise ValueError("times must be ordered, timezone-aware and observed")
    except (KeyError, TypeError, ValueError) as exc:
        raise RitualWorkersError("artifact timestamps are invalid or future") from exc
    coverage = data.get("coverage")
    if not isinstance(coverage, list) or any(
        not isinstance(row, dict) for row in coverage
    ):
        raise RitualWorkersError("artifact coverage is not a list of records")
    names = [row.get("surface") for row in coverage]
    if any(not isinstance(name, str) for name in names):
        raise RitualWorkersError("artifact surface names must be strings")
    if len(names) != len(worker.surfaces) or set(names) != set(worker.surfaces):
        raise RitualWorkersError(
            "artifact coverage does not match declared workspace surfaces"
        )
    for row in coverage:
        if (
            row.get("status") not in {"synced", "partial", "skipped", "failed"}
            or not isinstance(row.get("detail"), str)
            or not row["detail"].strip()
        ):
            raise RitualWorkersError("artifact coverage status/detail is invalid")
    reported_gaps = data.get("gaps")
    if not isinstance(reported_gaps, list) or any(
        not isinstance(gap, str) or not gap.strip() for gap in reported_gaps
    ):
        raise RitualWorkersError("artifact gaps must be explicit strings")
    incomplete = any(row["status"] != "synced" for row in coverage)
    if incomplete and not reported_gaps:
        raise RitualWorkersError("incomplete coverage must declare gaps")
    if outcome in {"clean", "complete", "completed", "success"} and (
        incomplete or reported_gaps
    ):
        raise RitualWorkersError("clean completion cannot conceal coverage gaps")
    candidates = data.get("lesson_candidates")
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise RitualWorkersError(
            "artifact lesson_candidates must be an explicit bounded list"
        )
    candidate_ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {"id", "pointer"}:
            raise RitualWorkersError(
                "lesson candidates carry only id and workspace-local pointer"
            )
        if (
            not isinstance(candidate["id"], str)
            or not candidate["id"].strip()
            or not isinstance(candidate["pointer"], str)
        ):
            raise RitualWorkersError("lesson candidate identity/pointer is invalid")
        if candidate["id"] in candidate_ids:
            raise RitualWorkersError("duplicate lesson candidate identity")
        candidate_ids.add(candidate["id"])
        pointer = Path(candidate["pointer"])
        if (
            not pointer.is_absolute()
            or ".." in pointer.parts
            or not pointer.is_relative_to(Path(worker.workspace_root))
            or pointer.resolve() != pointer
        ):
            raise RitualWorkersError("foreign lesson candidate pointer")
        try:
            meta = pointer.lstat()
            if (
                not stat.S_ISREG(meta.st_mode)
                or meta.st_uid != os.getuid()
                or not meta.st_mode & stat.S_IRUSR
                or meta.st_nlink != 1
            ):
                raise OSError("not an owned regular file")
        except OSError as exc:
            raise RitualWorkersError(
                "lesson candidate pointer is missing or unreadable"
            ) from exc
    headings = re.findall(r"^## (.+)$", body, re.MULTILINE)
    if headings != list(BODY_SECTIONS):
        raise RitualWorkersError(
            "artifact body sections/order differ from worker contract"
        )
    for section in re.split(r"^## .+$", body, flags=re.MULTILINE)[1:]:
        if not section.strip():
            raise RitualWorkersError(
                "artifact body section is empty; use explicit none"
            )
    return {
        "path": str(artifact),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "seat": worker.seat,
        "session": session,
        "lesson_candidates": len(candidates),
    }


# Native memory is an untrusted capture buffer. These bounded observations do
# not parse a harness's memory format or invoke a model/native action.
MEMORY_MAX_FILES = 1024
MEMORY_MAX_BYTES = 32 * 1024 * 1024
MEMORY_MAX_FILE = 8 * 1024 * 1024
MEMORY_SECONDS = 10


def memory_store_snapshot(store: Path) -> dict:
    """Hash one explicitly selected directory without interpreting its format."""
    import json
    import time

    store = Path(store)
    if not store.is_absolute() or ".." in store.parts or store.resolve() != store:
        raise RitualWorkersError("memory store must be an explicit unaliased absolute directory")
    deadline = time.monotonic() + MEMORY_SECONDS
    directories, files, total = {}, [], 0

    def metadata(path):
        info = path.lstat()
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RitualWorkersError("memory store ownership/mode refused")
        return info

    def walk(directory, depth):
        nonlocal total
        if time.monotonic() >= deadline or depth > 16:
            raise RitualWorkersError("memory store time/depth bound exceeded")
        info = metadata(directory)
        if not stat.S_ISDIR(info.st_mode):
            raise RitualWorkersError("memory store directory is not regular")
        names = sorted(os.listdir(directory))
        if len(names) + len(files) + len(directories) > MEMORY_MAX_FILES:
            raise RitualWorkersError("memory store entry bound exceeded")
        directories[directory] = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, names)
        for name in names:
            path = directory / name
            item = metadata(path)
            if stat.S_ISDIR(item.st_mode):
                walk(path, depth + 1)
            elif stat.S_ISREG(item.st_mode):
                raw = read_regular(path, min(MEMORY_MAX_FILE, MEMORY_MAX_BYTES - total))
                total += len(raw)
                files.append({"path": path.relative_to(store).as_posix(),
                              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
            else:
                raise RitualWorkersError("memory store has an unsupported member")
            if time.monotonic() >= deadline:
                raise RitualWorkersError("memory store time bound exceeded")

    walk(store, 0)
    # Revalidate every file and directory, not just the directory mtime. A
    # background consolidator can replace bytes without changing membership.
    for item in files:
        raw = read_regular(store / item["path"], MEMORY_MAX_FILE)
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise RitualWorkersError("memory store changed during hashing")
        if time.monotonic() >= deadline:
            raise RitualWorkersError("memory store time bound exceeded")
    for directory, expected in directories.items():
        info = metadata(directory)
        current = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, sorted(os.listdir(directory)))
        if current != expected:
            raise RitualWorkersError("memory store membership/identity changed")
    identity = directories[store]
    return {"path": str(store), "device": identity[0], "inode": identity[1],
            "sha256": hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "files": len(files), "bytes": total}


def memory_probe(store: Path, *, harness: str, machine: str, board: Path,
                 previous: dict | None = None) -> dict:
    """Fenced coordination preflight. The current harness counts as active too.

    The existing coordination owner may refresh its leased mirror; no native
    store, memory ledger or harness operation is modified by this probe.
    """
    import sys

    if harness not in {"codex", "claude", "muse"} or not machine:
        raise RitualWorkersError("explicit known harness and machine required")
    scripts = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import coordination
    from board_grammar import MAX_MESSAGE_BOARD_BYTES

    # The board uses its existing message-owner bound, not the smaller
    # generic ritual artifact bound. Full bytes still fence every read.
    # Refuse a missing/unsafe selected board before calling its owner (which
    # can otherwise initialize an absent parent). A leased mirror alone is not
    # evidence that this machine has no active harness seats.
    read_regular(Path(board), MAX_MESSAGE_BOARD_BYTES)
    text = coordination._check_staged_board_snapshot(Path(board), lock_timeout=1)
    if text is None:
        raise RitualWorkersError("selected coordination board is absent")
    board_raw = read_regular(Path(board), MAX_MESSAGE_BOARD_BYTES)
    if board_raw.decode("utf-8") != text:
        raise RitualWorkersError("coordination changed after its owner fence")
    sessions = coordination.rows(text, strict=True)
    from team_contract import CLIENT_SCHEMES

    for session in sessions:
        if coordination.active(session) and session.machine in {machine, "unknown", ""}:
            reference = coordination.normalize_client_ref(session.client_ref)
            scheme = reference.split(":", 1)[0] if reference else None
            client = next((name for name, schemes in CLIENT_SCHEMES.items() if scheme in schemes), None)
            if client is None or client == harness:
                return {"status": "PENDING_ACTIVE_HARNESS", "harness": harness,
                        "pending": True, "model_calls": 0}
    current = memory_store_snapshot(store)
    if read_regular(Path(board), MAX_MESSAGE_BOARD_BYTES) != board_raw:
        raise RitualWorkersError("coordination changed during memory preflight")
    if previous is not None:
        if not isinstance(previous, dict) or set(previous) != {"store", "complete"} or type(previous["complete"]) is not bool:
            raise RitualWorkersError("invalid memory ledger observation")
        old = previous["store"]
        if not isinstance(old, dict) or set(old) != set(current):
            raise RitualWorkersError("invalid previous memory store binding")
        if any(old[k] != current[k] for k in ("path", "device", "inode")):
            raise RitualWorkersError("memory store moved or was replaced; owner reconciliation required")
        if old == current:
            return {"status": "UNCHANGED" if previous["complete"] else "PENDING_UNCHANGED",
                    "harness": harness, "store": current, "pending": not previous["complete"], "model_calls": 0}
    if read_regular(Path(board), MAX_MESSAGE_BOARD_BYTES) != board_raw:
        raise RitualWorkersError("coordination changed during memory preflight")
    return {"status": "EXPORT_REQUIRED", "harness": harness, "store": current,
            "board_sha256": hashlib.sha256(board_raw).hexdigest(), "pending": True, "model_calls": 0}

#!/usr/bin/env python3
"""Record sanitized results from authenticated read-only capability probes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:  # POSIX
    import fcntl as posix_lock
except ImportError:  # pragma: no cover - exercised on Windows
    posix_lock = None

try:  # Windows
    import msvcrt as windows_lock
except ImportError:  # pragma: no cover - exercised on POSIX
    windows_lock = None


DEFAULT_DESTINATION = (
    Path.home()
    / ".synthesis"
    / "agent-conformance"
    / "capabilities.json"
)
CLIENTS = ("claude-code", "codex-desktop", "codex-cli")
CAPABILITIES = (
    "repository",
    "project-issue",
    "slack",
    "calendar",
    "mail",
    "workspace",
    "browser",
)
STATUSES = ("PASS", "FAIL", "UNKNOWN", "UNSUPPORTED")
EVIDENCE_KINDS = (
    "live-read-only",
    "client-health",
    "authenticated-cli",
    "environment-restricted",
    "product-boundary",
)


def load(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"schema_version": 1, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(
        payload.get("entries"), dict
    ):
        raise ValueError("capability evidence schema is invalid")
    return payload


def sanitize_detail(detail: str) -> str:
    compact = " ".join(detail.split())
    if not compact or len(compact) > 500:
        raise ValueError("detail must contain 1-500 printable characters")
    credential_pattern = re.compile(
        r"(?i)(?:\b(?:access[_-]?token|refresh[_-]?token|id[_-]?token|token|"
        r"api[_-]?key|x-api-key|client[_-]?secret|password)\b[\"']?\s*[:=]"
        r"|\bauthorization\s*:|\bbearer\s+)"
    )
    if credential_pattern.search(compact):
        raise ValueError("detail appears to contain authentication material")
    credential_value_pattern = re.compile(
        r"(?i)(?:"
        r"\bgh[pousr]_[A-Za-z0-9]{20,}(?![A-Za-z0-9])|"
        r"\bgithub_pat_[A-Za-z0-9_]{20,}(?![A-Za-z0-9_])|"
        r"\bglpat-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])|"
        r"\b(?:xox[baprs]|xapp)-[A-Za-z0-9-]{20,}(?![A-Za-z0-9-])|"
        r"\bsk-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])|"
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])|"
        r"\bAIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])|"
        r"\bnpm_[A-Za-z0-9]{20,}(?![A-Za-z0-9])|"
        r"\bhf_[A-Za-z0-9]{20,}(?![A-Za-z0-9])|"
        r"\bya29\.[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])|"
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])|"
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
        r")"
    )
    if credential_value_pattern.search(compact):
        raise ValueError("detail appears to contain authentication material")
    return compact


@contextmanager
def exclusive_lock(path: Path):
    """Hold one cross-process lock without requiring a third-party package."""
    with path.open("a+b") as lock:
        if posix_lock is not None:
            posix_lock.flock(lock, posix_lock.LOCK_EX)
        elif windows_lock is not None:  # pragma: no cover - Windows only
            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            windows_lock.locking(lock.fileno(), windows_lock.LK_LOCK, 1)
        else:  # pragma: no cover - supported Python platforms provide one
            raise RuntimeError("no supported cross-process file lock is available")
        try:
            yield
        finally:
            if posix_lock is not None:
                posix_lock.flock(lock, posix_lock.LOCK_UN)
            elif windows_lock is not None:  # pragma: no cover - Windows only
                lock.seek(0)
                windows_lock.locking(lock.fileno(), windows_lock.LK_UNLCK, 1)


def record(
    destination: Path,
    *,
    client: str,
    capability: str,
    status: str,
    evidence_kind: str,
    detail: str,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with exclusive_lock(lock_path):
        payload = load(destination)
        entries = payload["entries"]
        assert isinstance(entries, dict)
        entries[f"{client}.{capability}"] = {
            "client": client,
            "capability": capability,
            "status": status,
            "evidence_kind": evidence_kind,
            "detail": sanitize_detail(detail),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=destination.name + ".",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(json.dumps(payload, indent=2) + "\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, destination)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", choices=("record",))
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--client", choices=CLIENTS, required=True)
    parser.add_argument("--capability", choices=CAPABILITIES, required=True)
    parser.add_argument("--status", choices=STATUSES, required=True)
    parser.add_argument("--evidence-kind", choices=EVIDENCE_KINDS, required=True)
    parser.add_argument("--detail", required=True)
    args = parser.parse_args()
    try:
        record(
            args.destination.expanduser(),
            client=args.client,
            capability=args.capability,
            status=args.status,
            evidence_kind=args.evidence_kind,
            detail=args.detail,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"capability evidence failed: {exc}", file=sys.stderr)
        return 2
    print(f"recorded {args.client}.{args.capability}={args.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

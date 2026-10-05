"""Single-use approvals bound to the exact thing approved (R3.1, R3.2).

An approval is recorded only after the human says yes to the exact text or
command. The guard lets exactly one matching call through, then the approval
is spent.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from synthesis import paths

TTL_SECONDS = 30 * 60


def digest(kind: str, subject) -> str:
    canonical = subject if isinstance(subject, str) else json.dumps(subject, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{kind}\0{canonical}".encode("utf-8")).hexdigest()


def _file(key: str) -> Path:
    return paths.state() / "approvals" / f"{key}.json"


def record(kind: str, subject, *, note: str = "") -> str:
    key = digest(kind, subject)
    path = _file(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"kind": kind, "at": time.time(), "note": note}), encoding="utf-8")
    return key


def consume(kind: str, subject) -> bool:
    """True once for a live matching approval; the approval is spent atomically."""
    path = _file(digest(kind, subject))
    spent = path.with_suffix(".spent")
    try:
        os.replace(path, spent)
    except FileNotFoundError:
        return False
    try:
        data = json.loads(spent.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("kind") == kind and time.time() - float(data.get("at", 0)) <= TTL_SECONDS

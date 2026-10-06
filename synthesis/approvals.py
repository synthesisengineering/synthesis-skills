"""Approvals that only the principal can grant, bound to the exact thing approved (R3.1, R3.2).

When a guard blocks a send or a deploy it files a request with a short code.
Only the principal's own prompt containing "approve <code>" grants it: the
UserPromptSubmit hook sees the real prompt, which the agent cannot write. A
granted approval lets exactly one matching call through and expires.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from synthesis import paths

TTL_SECONDS = 15 * 60
CODE = re.compile(r"\bapprove\s+([a-z0-9]{6})\b", re.IGNORECASE)


def digest(kind: str, subject) -> str:
    canonical = subject if isinstance(subject, str) else json.dumps(subject, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{kind}\0{canonical}".encode("utf-8")).hexdigest()


def _dir(name: str) -> Path:
    return paths.state() / name


def request(kind: str, subject, summary: str) -> str:
    """File (or refresh) a pending request; returns the code the principal types."""
    key = digest(kind, subject)
    code = key[:6]
    _expire()
    path = _dir("approval-requests") / f"{code}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"kind": kind, "digest": key, "summary": summary, "at": time.time()}), encoding="utf-8")
    return code


def _expire() -> None:
    """Drop requests and grants older than the TTL, so state never grows (R8.3)."""
    cutoff = time.time() - TTL_SECONDS
    for name in ("approval-requests", "approvals"):
        for path in _dir(name).glob("*.json") if _dir(name).is_dir() else []:
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except FileNotFoundError:
                pass


def grant_from_prompt(prompt: str) -> list[str]:
    """Grant every pending request whose code the principal typed. Returns the summaries granted."""
    granted = []
    for code in {m.lower() for m in CODE.findall(prompt or "")}:
        pending = _dir("approval-requests") / f"{code}.json"
        try:
            data = json.loads(pending.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        target = _dir("approvals") / f"{data['digest']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"kind": data["kind"], "at": time.time(), "summary": data["summary"]}), encoding="utf-8")
        pending.unlink(missing_ok=True)
        granted.append(data["summary"])
    return granted


def consume(kind: str, subject) -> bool:
    """True once for a live granted approval of exactly this subject; it is spent atomically."""
    path = _dir("approvals") / f"{digest(kind, subject)}.json"
    spent = path.with_suffix(".spent")
    try:
        os.replace(path, spent)
    except FileNotFoundError:
        return False
    try:
        data = json.loads(spent.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    finally:
        spent.unlink(missing_ok=True)
    return data.get("kind") == kind and time.time() - float(data.get("at", 0)) <= TTL_SECONDS

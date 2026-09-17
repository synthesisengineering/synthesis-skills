"""Creation-time authority for runtime registrations, never payload removal.

Shared runtime bytes may serve independent installations. Only registrations
changed by this reconciler are restored; preexisting registrations stay owned
by their original installer. User changes fail closed before any removal.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys

from system_contract import ContractError


def _git_values():
    result = subprocess.run(["git", "config", "--global", "--null", "--get-all", "core.hooksPath"],
                            capture_output=True, timeout=15)
    if result.returncode not in {0, 1}:
        raise ContractError("cannot inspect global Git hook registration")
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def _file(path):
    if path.is_symlink():
        return {"kind": "link", "target": os.readlink(path)}
    if path.is_file():
        return {"kind": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if path.exists():
        raise ContractError("runtime registration is not a regular file or link")
    return None


def capture(home):
    return {"git_hooks_path": _git_values(), "paths": {
        str(home / ".local/bin/day-end"): _file(home / ".local/bin/day-end"),
        str(home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist"): _file(home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist"),
    }}


def preflight(receipts, before):
    value = receipts.data.get("runtime_registrations")
    if not value:
        return
    if not isinstance(value, dict) or set(value) != {"schema_version", "git", "paths"} or not isinstance(value["paths"], dict):
        raise ContractError("runtime registration ownership is invalid")
    for text, evidence in value["paths"].items():
        if text not in before["paths"] or before["paths"][text] not in (None, evidence.get("installed")):
            raise ContractError("edited owned runtime registration must be reconciled before activation")
    git = value["git"]
    if git is not None and before["git_hooks_path"] not in (git.get("installed"), git.get("before")):
        raise ContractError("edited owned Git registration must be reconciled before activation")


def record(receipts, home, before, *, service_started):
    previous = receipts.data.get("runtime_registrations", {"schema_version": 1, "git": None, "paths": {}})
    if not isinstance(previous, dict) or set(previous) != {"schema_version", "git", "paths"}:
        raise ContractError("runtime registration ownership is invalid")
    value = {**previous, "paths": dict(previous["paths"])}
    now = _git_values()
    target = str(home / ".synthesis/git-hooks")
    if value["git"] is None and before["git_hooks_path"] != now and now == [target]:
        value["git"] = {"before": before["git_hooks_path"], "installed": now}
    for text, old in before["paths"].items():
        path = Path(text)
        current = _file(path)
        if current is not None and (old is None or text in value["paths"]):
            was_started = value["paths"].get(text, {}).get("service_started", False)
            value["paths"][text] = {"installed": current, "service_started": bool(was_started or service_started and path.suffix == ".plist")}
    receipts.data["runtime_registrations"] = value
    receipts.save()


def retire(receipts, home, *, dry_run=False):
    value = receipts.data.get("runtime_registrations")
    if value is None:
        return {"removed": [], "retained": "No creation-time authority exists for preexisting runtime registrations."}
    if not isinstance(value, dict) or set(value) != {"schema_version", "git", "paths"} or value["schema_version"] != 1 or not isinstance(value["paths"], dict):
        raise ContractError("runtime registration ownership is invalid")
    allowed = {str(home / ".local/bin/day-end"), str(home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist")}
    if set(value["paths"]) - allowed:
        raise ContractError("runtime registration receipt claims an unowned path")
    for text, evidence in value["paths"].items():
        if not isinstance(evidence, dict) or set(evidence) != {"installed", "service_started"} or type(evidence["service_started"]) is not bool:
            raise ContractError("runtime registration evidence is invalid")
        path = Path(text)
        for ancestor in path.parents:
            if ancestor.is_symlink():
                raise ContractError("runtime registration parent changed to symlink")
        current = _file(path)
        if current is not None and current != evidence["installed"]:
            raise ContractError("edited runtime registration is preserved: %s" % path)
    git = value["git"]
    if git is not None:
        if not isinstance(git, dict) or set(git) != {"before", "installed"} or git["installed"] != [str(home / ".synthesis/git-hooks")] or not isinstance(git["before"], list) or any(not isinstance(v, str) for v in git["before"]):
            raise ContractError("Git registration ownership is invalid")
        if _git_values() not in (git["installed"], git["before"]):
            raise ContractError("edited global Git hook registration is preserved")
    if dry_run:
        return {"would_remove": sorted(value["paths"]), "would_restore_git": git is not None}
    removed = []
    # Stop owned services before removing their exact registration file.
    for text, evidence in list(value["paths"].items()):
        path = Path(text)
        if evidence["service_started"]:
            if sys.platform != "darwin":
                raise ContractError("cannot verify removal of the owned macOS service on this platform")
            domain = "gui/%d" % os.getuid()
            service = domain + "/com.synthesis.day-end-nudge"
            active = subprocess.run(["launchctl", "print", service], capture_output=True, timeout=15)
            if active.returncode == 0:
                stopped = subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, timeout=15)
                if stopped.returncode or subprocess.run(["launchctl", "print", service], capture_output=True, timeout=15).returncode == 0:
                    raise ContractError("owned day-end service could not be stopped")
        if _file(path) is not None:
            if _file(path) != evidence["installed"]:
                raise ContractError("runtime registration changed during removal")
            # Retain exact originals next to the lifecycle receipt, outside discovery.
            archive = receipts.path.parent / "archives/runtime-registrations"
            archive.mkdir(parents=True, exist_ok=True)
            import uuid
            destination = archive / (uuid.uuid4().hex + "-" + path.name)
            if path.is_symlink():
                from system_contract import atomic_write_json
                atomic_write_json(destination.with_suffix(destination.suffix + ".link.json"), {"path": str(path), "target": os.readlink(path)})
                path.unlink()
            else:
                path.rename(destination)
        removed.append(text)
        del value["paths"][text]
        receipts.save()
    if git is not None:
        if _git_values() == git["installed"]:
            result = subprocess.run(["git", "config", "--global", "--unset-all", "core.hooksPath"], capture_output=True, timeout=15)
            if result.returncode not in {0, 5}:
                raise ContractError("owned Git registration could not be removed")
            for old in git["before"]:
                subprocess.run(["git", "config", "--global", "--add", "core.hooksPath", old], check=True, capture_output=True, timeout=15)
        if _git_values() != git["before"]:
            raise ContractError("prior global Git registration was not restored")
        value["git"] = None
        receipts.save()
    return {"removed": removed, "retained": "Shared runtime payload bytes and preexisting registrations are preserved."}

#!/usr/bin/env python3
"""Read Codex's authoritative hook inventory and human-review state.

This adapter deliberately asks Codex app-server for ``hooks/list`` instead of
reimplementing Codex's private hook hashing rules.  It is read-only: it never
writes ``hooks.state`` and cannot approve a hook on the user's behalf.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from client_binaries import missing_binary_detail, resolve_client_binary
from codex_app_server import query


def query_hooks(
    binary: str, cwds: list[str], timeout: int = 15
) -> dict[str, object]:
    """Return Codex's normalized hook list for ``cwds``."""
    return query(
        binary,
        "hooks/list",
        {"cwds": cwds},
        title="Synthesis Hook Audit",
        timeout=timeout,
    )


def change_reason(trust_status: str, managed: bool) -> str:
    if managed or trust_status == "managed":
        return "managed by policy"
    return {
        "trusted": "definition matches the last human-reviewed hash",
        "modified": "definition changed after the last human review",
        "untrusted": "definition has not been human-reviewed",
    }.get(trust_status, f"unrecognized trust status: {trust_status or 'missing'}")


def normalized_audit(result: dict[str, object]) -> dict[str, object]:
    records: list[dict[str, object]] = []
    warnings: list[str] = []
    errors: list[str] = []
    data = result.get("data", [])
    if not isinstance(data, list):
        raise ValueError("hooks/list data is not a list")
    for row in data:
        if not isinstance(row, dict):
            continue
        cwd = str(row.get("cwd") or "")
        warnings.extend(str(value) for value in row.get("warnings", []) or [])
        errors.extend(str(value) for value in row.get("errors", []) or [])
        for hook in row.get("hooks", []) or []:
            if not isinstance(hook, dict):
                continue
            trust_status = str(hook.get("trustStatus") or "unknown")
            managed = bool(hook.get("isManaged"))
            records.append(
                {
                    "cwd": cwd,
                    "key": hook.get("key"),
                    "event": hook.get("eventName"),
                    "matcher": hook.get("matcher"),
                    "command": hook.get("command"),
                    "current_hash": hook.get("currentHash"),
                    "source_path": hook.get("sourcePath"),
                    "source_owner": hook.get("source"),
                    "plugin_id": hook.get("pluginId"),
                    "enabled": bool(hook.get("enabled")),
                    "managed": managed,
                    "trust_status": trust_status,
                    "change_reason": change_reason(trust_status, managed),
                }
            )
    pending = [
        record
        for record in records
        if record["enabled"]
        and not record["managed"]
        and record["trust_status"] != "trusted"
    ]
    status = "FAIL" if errors or pending else "PASS"
    return {
        "status": status,
        "hooks": records,
        "pending_review": len(pending),
        "warnings": warnings,
        "errors": errors,
    }


def audit(cwds: list[str]) -> dict[str, object]:
    binary = resolve_client_binary("codex")
    if binary is None:
        return {
            "status": "UNKNOWN",
            "hooks": [],
            "pending_review": None,
            "warnings": [],
            "errors": [missing_binary_detail("codex")],
        }
    try:
        return normalized_audit(query_hooks(binary, cwds))
    except (OSError, subprocess.TimeoutExpired, RuntimeError, TypeError, ValueError) as exc:
        return {
            "status": "UNKNOWN",
            "hooks": [],
            "pending_review": None,
            "warnings": [],
            "errors": [str(exc)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", action="append", dest="cwds")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    cwds = [
        str(Path(value).expanduser().resolve())
        for value in (args.cwds or [os.getcwd()])
    ]
    payload = audit(cwds)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for hook in payload["hooks"]:
            print(
                f"{hook['trust_status'].upper():9} {hook['event']} "
                f"{hook['key']} {hook['current_hash']}"
            )
            print(
                f"          source={hook['source_owner']}:{hook['source_path']} "
                f"reason={hook['change_reason']}"
            )
        for error in payload["errors"]:
            print(f"UNKNOWN: {error}")
        print(
            f"{payload['status']}: {len(payload['hooks'])} hook(s), "
            f"{payload['pending_review']} pending review"
        )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

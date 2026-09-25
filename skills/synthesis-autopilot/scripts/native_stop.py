#!/usr/bin/env python3
"""Compose checkpoint and autopilot Stop checks behind the verified launcher.

Both checks run even if one returns a terminal result. Native termination ends
feedback; it never certifies completion or erases unresolved project evidence.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = None


def _runtime():
    global _RUNTIME
    if _RUNTIME is None:
        path = ROOT / "skills/synthesis-onboarding/scripts/release_runtime.py"
        if path.is_symlink() or not path.is_file():
            raise ValueError("verified runtime helper is unavailable")
        spec = importlib.util.spec_from_file_location("autopilot_stop_release_runtime", path)
        if spec is None or spec.loader is None:
            raise ValueError("verified runtime helper cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _RUNTIME = module
    return _RUNTIME


def _terminal(reason):
    return {"continue": False, "stopReason": reason,
            "systemMessage": reason if reason.startswith("UNRESOLVED:") else "UNRESOLVED: " + reason}


def checkpoint_result(payload):
    runtime = _runtime()
    active = runtime.verified_release()
    if Path(active["release_root"]).resolve() != ROOT:
        raise ValueError("Stop dispatcher does not belong to the verified active release")
    result = runtime.execute(active, "synthesis-project-management/scripts/project_state.py",
                             ["hook"], json.dumps(payload).encode(), timeout=8)
    return runtime.stop_result(payload, result, consume_policy=False)


def _autopilot_result(payload, *, reserve_feedback=True):
    from autopilot import actor_from_hook, default_runtime_root, stop_result
    return stop_result(actor_from_hook(payload), runtime_root=default_runtime_root(), reserve_feedback=reserve_feedback)


def combined_result(payload, *, checkpoint=None, autopilot_check=None):
    """Return one native envelope; injected callables are isolated test seams."""
    try:
        runtime = _runtime()
        if not runtime.valid_stop_payload(payload):
            return runtime.stop_failure(payload, "Combined Stop input lacks valid native identity.", terminal=True)
    except Exception:
        return _terminal("Combined Stop runtime helper is unavailable; protection remains unverified.")
    checks = (("Project checkpoint", checkpoint or checkpoint_result),
              ("Autopilot", autopilot_check or _autopilot_result))
    results = []
    for label, check in checks:
        try:
            if label == "Autopilot" and autopilot_check is None:
                value = _autopilot_result(payload, reserve_feedback=not any(item.get("continue") is False for item in results))
            else:
                value = check(payload)
            wire = json.dumps(value, allow_nan=False).encode()
            # Reuse the public native parser: malformed output, nested terminal
            # results and repeat limits follow the exact outer-launcher contract.
            result = runtime.stop_result(payload, subprocess.CompletedProcess([], 0, wire, b""), consume_policy=False)
        except Exception as exc:
            result = runtime.stop_failure(payload, f"{label} could not be verified: {exc}", terminal=True)
        results.append(result)
    diagnostics = []
    for result in results:
        diagnostic = result.get("systemMessage") or result.get("stopReason") or result.get("reason")
        if diagnostic and diagnostic not in diagnostics:
            diagnostics.append(diagnostic)
    terminal = next((value for value in results if value.get("continue") is False), None)
    if terminal is not None:
        result = _terminal(terminal.get("stopReason") or "Combined Stop protection remains unresolved.")
        if diagnostics:
            result["systemMessage"] = "\n".join(message if message.startswith("UNRESOLVED:") else "UNRESOLVED: " + message for message in diagnostics)
        return result
    blocked = [value["reason"] for value in results if value.get("decision") == "block"]
    if blocked:
        reserved = [value for value in results if value.get("decision") == "block" and value.get("_synthesis_policy")]
        if len(reserved) != 1:
            return runtime.stop_failure(payload, "Combined Stop lacks one current correction reservation.", terminal=True)
        return {"decision": "block", "reason": "\n".join(blocked),
                "systemMessage": "\n".join(diagnostics), "_synthesis_policy": reserved[0]["_synthesis_policy"]}
    return {"systemMessage": "\n".join(diagnostics)} if diagnostics else {}


def main():
    try:
        raw = _runtime().read_payload(1)
        payload = json.loads(raw)
        result = combined_result(payload)
    except Exception as exc:
        result = _terminal(f"Combined Stop input or runtime is unavailable: {exc}")
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

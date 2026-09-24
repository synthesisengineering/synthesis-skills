#!/usr/bin/env python3
"""Codex Stop hook that records local handoff state and verifies guard health.

Routine dirty or ahead state is LOCAL_READY on the same machine and is reported
for the explicit remote-handoff/day-end sync. An unavailable guard or malformed
session checkpoint remains a protection failure and blocks continuation.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


SYNTHESIS_HOME = Path(
    os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
)
# The public hook ships with the public execution engine. Binding that sibling
# by exact path avoids both a private helper dependency and ambient import
# shadowing; the engine verifies the active release before building commands.
RUNTIME_PATH = (Path(__file__).resolve().parents[3]
                / "synthesis-onboarding/scripts/release_runtime.py")
try:
    if not RUNTIME_PATH.is_file() or RUNTIME_PATH.is_symlink() or RUNTIME_PATH.resolve() != RUNTIME_PATH:
        raise ImportError("public execution engine is missing or unsafe")
    _runtime_spec = importlib.util.spec_from_file_location("_repo_guard_public_runtime", RUNTIME_PATH)
    if _runtime_spec is None or _runtime_spec.loader is None:
        raise ImportError("public execution engine cannot be loaded")
    _runtime = importlib.util.module_from_spec(_runtime_spec)
    _runtime_spec.loader.exec_module(_runtime)
except (ImportError, OSError, SyntaxError, ValueError):
    _runtime = None
HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "repo_guard_stop"
PENDING_DIR = SYNTHESIS_HOME / "repo-guard" / "pending"


def public_command(script: str, arguments: list[str]) -> list[str]:
    if _runtime is None:
        raise ValueError("public execution engine is unavailable")
    active = _runtime.verified_release()
    return _runtime.command(active, script, arguments)


def run(
    args: list[str],
    cwd: str | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=30,
    )


def pending_manifest(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return PENDING_DIR / f"{digest}.json"


def marker_root(cwd: str) -> Path | None:
    """Find an enclosing .git marker without depending on the git binary."""
    try:
        candidate = Path(cwd).resolve(strict=True)
    except OSError:
        return None
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / ".git").exists():
            return parent
    return None


def git_root(cwd: str) -> tuple[str, Path | None]:
    marker = marker_root(cwd)
    try:
        result = run(["git", "-C", cwd, "rev-parse", "--show-toplevel"])
    except Exception:
        return ("unavailable", marker) if marker else ("not-git", None)
    if result.returncode != 0:
        return ("unavailable", marker) if marker else ("not-git", None)
    output = result.stdout.strip()
    if not output:
        return "unavailable", marker
    return "git", Path(output)


def block(reason: str, payload: dict | None = None, *, terminal: bool = False,
          system_message: str | None = None) -> int:
    responder = getattr(_runtime, "stop_failure", None)
    if responder is None:
        # Missing infrastructure must halt, never request an endless repair turn.
        result = {"continue": False, "stopReason": reason,
                  "systemMessage": f"UNRESOLVED: {reason}"}
    else:
        result = responder(payload, reason, system_message, terminal=terminal)
    print(json.dumps(result))
    return 0


def doctor() -> int:
    lines, healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"synthesis_home={SYNTHESIS_HOME}")
    lines.append(f"pending_dir={PENDING_DIR}")
    if healthy and hook_enabled(HOOK_NAME):
        try:
            for script in ("synthesis-repo-guard/checkpoint_sync.py", "synthesis-repo-guard/repo_sync_check.py"):
                public_command(script, [])
        except Exception as exc:
            healthy = False
            lines.append(f"UNHEALTHY: public guard execution is unavailable: {exc}")
    print("\n".join(lines))
    return 0 if healthy else 1


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--doctor" in argv:
        return doctor()
    _lines, healthy = doctor_prologue(HOOK_NAME)
    if not healthy:
        return block("Repo guard settings are invalid; protection is unavailable.", terminal=True)
    if not hook_enabled(HOOK_NAME):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return block("Stop hook input is invalid; local continuity cannot be verified.", terminal=True)
    if not isinstance(payload, dict):
        return block("Stop hook input is invalid; local continuity cannot be verified.", terminal=True)

    if _runtime is None:
        return block(
            "Repo guard public execution engine is unavailable; protection fails closed.",
            payload, terminal=True,
        )
    validator = getattr(_runtime, "valid_stop_payload", None)
    if not callable(validator) or not validator(payload):
        return block("Stop hook native identity is invalid; protection remains unverified.",
                     payload, terminal=True)

    cwd = payload.get("cwd") or ""
    if not isinstance(cwd, str) or not cwd:
        return block("Stop hook input has no working directory; local continuity cannot be verified.", payload, terminal=True)
    session_id = str(payload.get("session_id") or "")
    pending = pending_manifest(session_id) if session_id else None
    if pending is not None and os.path.lexists(pending):
        if pending.is_symlink():
            return block(f"Pending project checkpoint is an unsafe symlink: {pending}", payload)
        try:
            checkpoint = run(
                public_command("synthesis-repo-guard/checkpoint_sync.py", ["--hook", "--quiet"]),
                input_text=json.dumps(payload),
            )
        except Exception as exc:
            return block(
                "Project checkpoint could not run at Stop: "
                f"{type(exc).__name__}. The handoff fails closed.", payload, terminal=True,
            )
        if checkpoint.returncode != 0:
            detail = (checkpoint.stderr or checkpoint.stdout).strip()
            return block(
                "Local project handoff evidence could not be recorded. "
                f"The handoff fails closed. {detail[:300]}", payload,
            )
        if checkpoint.stdout.strip():
            try:
                response = json.loads(checkpoint.stdout)
            except ValueError:
                response = None
            if not isinstance(response, dict):
                return block("Project checkpoint returned invalid guard evidence.", payload, terminal=True)
            if response.get("continue") is False:
                print(json.dumps(response))
                return 0
            if response.get("decision") == "block":
                return block(str(response.get("reason") or "Project checkpoint is unresolved."),
                             payload, system_message=response.get("systemMessage"))
            return block("Project checkpoint returned unrecognized guard evidence.", payload, terminal=True)
    state, root = git_root(cwd)
    if state == "not-git":
        return 0
    if state != "git" or root is None:
        return block(
            "Repo guard could not resolve an enclosing git repository even "
            "though a .git marker is present; protection is unavailable.", payload, terminal=True,
        )
    try:
        result = run(
            public_command("synthesis-repo-guard/repo_sync_check.py", [
                "--workspace",
                str(root),
                "--max-depth",
                "0",
                "--json",
                "--dirty-only",
            ])
        )
    except Exception as exc:
        return block(
            f"Repo guard failed to execute inside {root}: "
            f"{type(exc).__name__}. Protection fails closed.", payload, terminal=True,
        )

    if result.returncode == 0:
        return 0

    detail = (result.stderr or result.stdout).strip()
    if result.returncode not in (1,):
        return block(
            f"Repo guard could not verify {root} (exit {result.returncode}). "
            f"Protection fails closed. {detail[:300]}", payload, terminal=True,
        )
    # Dirty and ahead states are valid local continuity. The detector has
    # written detailed state for the explicit remote-handoff/day-end sync.
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Shared settings for promoted hooks: enable flags, principal name, hook params.

Config file (JSON): ~/.synthesis/agent-guardrails/hooks.json, overridden by
GUARDRAILS_HOOKS_CONFIG. Shape:

    {"principal_name": "",
     "hooks": {"bare_filename_detector": true,
               "long_session_detector": {"enabled": true, "hours": 6}}}

A hook entry is `true` (enabled, default params), `false`/absent
(disabled), or a map with `enabled` plus hook-specific params. No config
or an unreadable one disables every hook (defaults-off); a malformed one
additionally reports UNHEALTHY through each hook's --doctor. Nothing is
cached: hooks are one-shot processes, and call-time reads keep tests
hermetic via the env override.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def config_path() -> Path:
    override = os.environ.get("GUARDRAILS_HOOKS_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".synthesis" / "agent-guardrails" / "hooks.json"


def load_settings() -> tuple[dict[str, Any], str | None]:
    """Return (settings, error). Error is None on success; on any failure
    settings is {} (all hooks disabled) and error names the cause."""
    path = config_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, None
    except OSError as exc:
        return {}, f"cannot read {path}: {exc}"
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return {}, f"cannot parse {path}: {exc}"
    if not isinstance(data, dict):
        return {}, f"{path} top-level is not a mapping"
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return {}, f"{path} hooks is not a mapping"
    return data, None


def hook_entry(name: str) -> Any:
    settings, _ = load_settings()
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return False
    return hooks.get(name, False)


def hook_enabled(name: str) -> bool:
    entry = hook_entry(name)
    if isinstance(entry, dict):
        return bool(entry.get("enabled", False))
    return bool(entry)


def hook_params(name: str) -> dict[str, Any]:
    entry = hook_entry(name)
    if isinstance(entry, dict):
        return {key: value for key, value in entry.items() if key != "enabled"}
    return {}


def principal_name() -> str:
    settings, _ = load_settings()
    name = settings.get("principal_name", "")
    return name.strip() if isinstance(name, str) else ""


def principal_display() -> str:
    return principal_name() or "the principal"


def doctor_prologue(hook: str) -> tuple[list[str], bool]:
    """Shared --doctor opening: config path, parse status, enable state."""
    path = config_path()
    _, error = load_settings()
    lines = [f"hook: {hook}", f"config: {path}"]
    if error is not None:
        return lines + [f"UNHEALTHY: {error}"], False
    if not path.exists():
        return lines + ["UNCONFIGURED: no hooks.json; hook is inert"], True
    state = "enabled" if hook_enabled(hook) else "disabled"
    return lines + [f"state: {state}"], True

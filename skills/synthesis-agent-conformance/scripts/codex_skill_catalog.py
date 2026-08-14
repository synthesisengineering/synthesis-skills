#!/usr/bin/env python3
"""Audit the resolved Codex skill catalog against Codex's prompt budget."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

from client_binaries import missing_binary_detail, resolve_client_binary
from codex_app_server import query

try:
    import tomllib
except ImportError:  # Python 3.9/3.10 compatibility
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - exercised with Apple Python 3.9
        tomllib = None  # type: ignore[assignment]

DEFAULT_CHAR_BUDGET = 8_000
CONTEXT_PERCENT = 2
MAX_DESCRIPTION_CHARS = 1_024
ALIAS_INSTRUCTION_RESERVE_TOKENS = 256
PUBLIC_PLUGIN_NAMESPACE = "synthesis-skills:"


def _codex_home(home: Path | None = None) -> Path:
    if home is not None:
        return home / ".codex"
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _configured_model(home: Path | None = None) -> str | None:
    path = _codex_home(home) / "config.toml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if tomllib is not None:
        try:
            payload = tomllib.loads(text)
        except (TypeError, ValueError):
            return None
        model = payload.get("model") if isinstance(payload, dict) else None
        return model if isinstance(model, str) and model else None
    # Apple Python 3.9 has no stdlib TOML parser. Read only a top-level model
    # string and stop at the first table, so inactive profile models can never
    # be mistaken for the default runtime model.
    for line in text.splitlines():
        if re.match(r"^\s*\[", line):
            break
        match = re.match(
            r'''^\s*model\s*=\s*(["'])(.*?)\1\s*(?:#.*)?$''', line
        )
        if match:
            return match.group(2) or None
    return None


def _context_window(home: Path | None, model: str | None) -> int | None:
    if not model:
        return None
    try:
        payload = json.loads(
            (_codex_home(home) / "models_cache.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    models = payload.get("models")
    if not isinstance(models, list):
        return None
    for row in models:
        if not isinstance(row, dict):
            continue
        if row.get("slug") == model and isinstance(row.get("context_window"), int):
            return int(row["context_window"])
    return None


def allows_implicit_invocation(skill_path: Path) -> bool:
    """Mirror the openai.yaml default: visible unless explicitly disabled."""
    metadata = skill_path.parent / "agents" / "openai.yaml"
    try:
        text = metadata.read_text(encoding="utf-8")
    except OSError:
        return True
    return not bool(
        re.search(
            r"^\s*allow_implicit_invocation\s*:\s*false\s*$",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
    )


def _plugin_parts(path: Path) -> tuple[Path, Path] | None:
    parts = path.parts
    for index in range(len(parts) - 5):
        if parts[index : index + 2] != ("plugins", "cache"):
            continue
        marketplace = Path(*parts[: index + 3])
        version = Path(*parts[: index + 5])
        return marketplace, version
    return None


def alias_roots(skills: list[dict[str, object]]) -> list[Path]:
    """Infer the host roots used by Codex's public AliasPlan implementation."""
    skill_paths = [Path(str(skill.get("path") or "")) for skill in skills]
    version_counts = Counter(
        parts[1] for path in skill_paths if (parts := _plugin_parts(path))
    )
    roots: list[Path] = []
    for path in skill_paths:
        plugin = _plugin_parts(path)
        if plugin:
            marketplace, version = plugin
            root = marketplace if version_counts[version] <= 1 else version / "skills"
        else:
            root = path.parent.parent
        if root not in roots:
            roots.append(root)
    return roots


def _locator(path: Path, roots: list[Path]) -> str:
    matches: list[tuple[int, str]] = []
    for index, root in enumerate(roots):
        try:
            suffix = path.relative_to(root)
        except ValueError:
            continue
        matches.append((len(str(root)), f"r{index}/{suffix.as_posix()}"))
    return max(matches)[1] if matches else str(path)


def _line(skill: dict[str, object], roots: list[Path]) -> str:
    name = str(skill.get("name") or "")
    description = str(skill.get("description") or "")[:MAX_DESCRIPTION_CHARS]
    path = Path(str(skill.get("path") or skill.get("skillPath") or "runtime-catalog"))
    return f"- {name}: {description} (file: {_locator(path, roots)})\n"


def normalized_audit(
    result: dict[str, object], *, home: Path | None = None,
    expected_skill_names: set[str] | None = None,
) -> dict[str, object]:
    data = result.get("data", [])
    if not isinstance(data, list):
        raise ValueError("skills/list data is not a list")
    rows = [row for row in data if isinstance(row, dict)]
    if not rows:
        return {
            "status": "UNKNOWN",
            "skill_count": 0,
            "full_cost_tokens": None,
            "budget_tokens": None,
            "model": _configured_model(home),
            "context_window": None,
            "errors": ["skills/list returned no catalog rows"],
        }
    discovered = [
        skill
        for skill in rows[0].get("skills", [])
        if isinstance(skill, dict) and bool(skill.get("enabled", True))
    ]
    discovered_names = set()
    for skill in discovered:
        name = str(skill.get("name") or "")
        if not name:
            continue
        if name.startswith(PUBLIC_PLUGIN_NAMESPACE):
            name = name.removeprefix(PUBLIC_PLUGIN_NAMESPACE)
        discovered_names.add(name)
    missing_skills = sorted((expected_skill_names or set()) - discovered_names)
    skills = [
        skill
        for skill in discovered
        if allows_implicit_invocation(Path(str(skill.get("path") or "")))
    ]
    errors = [str(value) for value in rows[0].get("errors", []) or []]
    model = _configured_model(home)
    context_window = _context_window(home, model)
    roots = alias_roots(skills)
    root_table = "".join(
        f"- `r{index}` = `{root.as_posix()}`\n" for index, root in enumerate(roots)
    )
    rendered = root_table + "".join(_line(skill, roots) for skill in skills)
    metadata_tokens = (len(rendered.encode("utf-8")) + 3) // 4
    full_cost_tokens = metadata_tokens + ALIAS_INSTRUCTION_RESERVE_TOKENS
    if context_window:
        budget_tokens = max(1, context_window * CONTEXT_PERCENT // 100)
        budget_source = "model cache"
    else:
        budget_tokens = DEFAULT_CHAR_BUDGET // 4
        budget_source = "Codex fallback"
    fits = not errors and not missing_skills and full_cost_tokens <= budget_tokens
    return {
        "status": "PASS" if fits else "FAIL",
        "discovered_skill_count": len(discovered),
        "missing_skill_names": missing_skills,
        "skill_count": len(skills),
        "full_cost_tokens": full_cost_tokens,
        "metadata_tokens": metadata_tokens,
        "alias_instruction_reserve_tokens": ALIAS_INSTRUCTION_RESERVE_TOKENS,
        "alias_root_count": len(roots),
        "budget_tokens": budget_tokens,
        "budget_source": budget_source,
        "model": model,
        "context_window": context_window,
        "errors": errors,
    }


def audit(cwd: Path, *, home: Path | None = None) -> dict[str, object]:
    binary = resolve_client_binary("codex")
    if binary is None:
        return {
            "status": "UNKNOWN",
            "skill_count": 0,
            "full_cost_tokens": None,
            "budget_tokens": None,
            "errors": [missing_binary_detail("codex")],
        }
    try:
        result = query(
            binary,
            "skills/list",
            {"cwds": [str(cwd.resolve())], "forceReload": True},
            title="Synthesis Skill Catalog Audit",
        )
        source_skills = Path(__file__).resolve().parents[2]
        expected = {
            skill.parent.name for skill in source_skills.glob("*/SKILL.md")
        }
        return normalized_audit(
            result, home=home, expected_skill_names=expected
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return {
            "status": "UNKNOWN",
            "skill_count": 0,
            "full_cost_tokens": None,
            "budget_tokens": None,
            "errors": [str(exc)],
        }

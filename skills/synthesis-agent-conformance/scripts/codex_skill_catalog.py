#!/usr/bin/env python3
"""Audit the resolved Codex skill catalog against Codex's prompt budget."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from client_binaries import missing_binary_detail, resolve_client_binary
from codex_app_server import query

DEFAULT_CHAR_BUDGET = 8_000
CONTEXT_PERCENT = 2
MAX_DESCRIPTION_CHARS = 1_024
ALIAS_INSTRUCTION_RESERVE_TOKENS = 256


def _configured_model(home: Path) -> str | None:
    try:
        match = re.search(
            r'^model\s*=\s*"([^"]+)"\s*$',
            (home / ".codex" / "config.toml").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    except OSError:
        return None
    return match.group(1) if match else None


def _context_window(home: Path, model: str | None) -> int | None:
    if not model:
        return None
    try:
        payload = json.loads(
            (home / ".codex" / "models_cache.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    for row in payload.get("models", []):
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
    home = home or Path.home()
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
    discovered_names = {
        str(skill.get("name") or "") for skill in discovered if skill.get("name")
    }
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

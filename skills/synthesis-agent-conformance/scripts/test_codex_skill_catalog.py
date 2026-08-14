#!/usr/bin/env python3
"""Tests for Codex's resolved skill-catalog budget audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_skill_catalog import allows_implicit_invocation, normalized_audit


def _skill(root: Path, name: str, description: str = "Short trigger") -> dict[str, object]:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nname: test\ndescription: test\n---\n", encoding="utf-8")
    return {"name": name, "description": description, "path": str(path), "enabled": True}


def _home(tmp_path: Path, context_window: int = 100_000) -> Path:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text('model = "test-model"\n', encoding="utf-8")
    (codex / "models_cache.json").write_text(
        json.dumps(
            {"models": [{"slug": "test-model", "context_window": context_window}]}
        ),
        encoding="utf-8",
    )
    return home


def test_explicit_only_skill_is_not_prompt_visible(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill = _skill(root, "explicit-skill")
    metadata = Path(str(skill["path"])).parent / "agents" / "openai.yaml"
    metadata.parent.mkdir()
    metadata.write_text(
        "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
    )

    assert not allows_implicit_invocation(Path(str(skill["path"])))
    audit = normalized_audit(
        {"data": [{"skills": [skill], "errors": []}]}, home=_home(tmp_path)
    )
    assert audit["discovered_skill_count"] == 1
    assert audit["skill_count"] == 0
    assert audit["status"] == "PASS"


def test_prompt_visible_catalog_fails_when_model_budget_is_exceeded(
    tmp_path: Path,
) -> None:
    root = tmp_path / "skills"
    skills = [_skill(root, f"skill-{index}", "x" * 1_024) for index in range(12)]

    audit = normalized_audit(
        {"data": [{"skills": skills, "errors": []}]},
        home=_home(tmp_path, context_window=10_000),
    )

    assert audit["status"] == "FAIL"
    assert audit["full_cost_tokens"] > audit["budget_tokens"]


def test_malformed_data_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a list"):
        normalized_audit({"data": None}, home=_home(tmp_path))

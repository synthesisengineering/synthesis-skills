#!/usr/bin/env python3
"""Tests for Codex's resolved skill-catalog budget audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import codex_skill_catalog as MODULE

from codex_skill_catalog import (
    _configured_model,
    _context_window,
    allows_implicit_invocation,
    normalized_audit,
)


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


def test_resolved_catalog_fails_when_expected_skill_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    present = _skill(root, "present-skill")

    audit = normalized_audit(
        {"data": [{"skills": [present], "errors": []}]},
        home=_home(tmp_path),
        expected_skill_names={"present-skill", "missing-skill"},
    )

    assert audit["status"] == "FAIL"
    assert audit["missing_skill_names"] == ["missing-skill"]


def test_expected_skill_matches_plugin_namespaced_runtime_name(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill = _skill(root, "synthesis-skills:synthesis-autopilot")

    audit = normalized_audit(
        {"data": [{"skills": [skill], "errors": []}]},
        home=_home(tmp_path),
        expected_skill_names={"synthesis-autopilot"},
    )

    assert audit["status"] == "PASS"
    assert audit["missing_skill_names"] == []


def test_other_plugin_namespace_cannot_substitute_for_expected_skill(
    tmp_path: Path,
) -> None:
    root = tmp_path / "skills"
    skill = _skill(root, "other-plugin:synthesis-autopilot")

    audit = normalized_audit(
        {"data": [{"skills": [skill], "errors": []}]},
        home=_home(tmp_path),
        expected_skill_names={"synthesis-autopilot"},
    )

    assert audit["status"] == "FAIL"
    assert audit["missing_skill_names"] == ["synthesis-autopilot"]


def test_catalog_budget_honors_codex_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = tmp_path / "custom-codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        'model = "custom-model"\n', encoding="utf-8"
    )
    (codex_home / "models_cache.json").write_text(
        json.dumps(
            {"models": [{"slug": "custom-model", "context_window": 80_000}]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    root = tmp_path / "skills"
    skill = _skill(root, "visible-skill")

    audit = normalized_audit({"data": [{"skills": [skill], "errors": []}]})

    assert audit["model"] == "custom-model"
    assert audit["context_window"] == 80_000


def test_configured_model_parses_top_level_toml_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(
        "model = 'active-model' # current default\n"
        "[profiles.inactive]\n"
        'model = "wrong-model"\n',
        encoding="utf-8",
    )

    assert _configured_model(home) == "active-model"


def test_configured_model_fallback_ignores_profile_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(
        "model = 'active-model' # current default\n"
        "[profiles.inactive]\n"
        'model = "wrong-model"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "tomllib", None)

    assert MODULE._configured_model(home) == "active-model"


@pytest.mark.parametrize(
    "payload",
    (
        [],
        {"models": "invalid"},
        {"models": [None, "invalid"]},
    ),
)
def test_context_window_survives_malformed_cache_shapes(
    tmp_path: Path, payload: object
) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "models_cache.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    assert _context_window(home, "test-model") is None

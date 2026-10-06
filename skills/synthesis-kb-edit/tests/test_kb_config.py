from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path



MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kb_config.py"
SPEC = importlib.util.spec_from_file_location("kb_config", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_config() -> dict:
    return {
        "bundle_path": "source",
        "git_host": "github",
        "default_branch": "main",
        "branch_prefix": "kb/",
        "ship": "pr",
        "review": {
            "who_merges": "A maintainer other than the editor",
            "default_reviewers": [],
            "setup_guide": None,
        },
        "editable": ["source/**"],
        "refuse": [".agents/**", "compiled/**"],
        "generated_artifacts": ["compiled/**", "all-knowledge.md"],
        "topic_routing": {"reference": "source/reference"},
        "taxonomy_path": "source/taxonomy.md",
        "frontmatter": {
            "required": ["type"],
            "house": ["title", "tags", "timestamp", "status"],
            "date_field": "timestamp",
            "reserved_files": ["index.md", "log.md"],
        },
        "confidentiality": {
            "forbidden_words_source": None,
            "hook_path": None,
            "visible_to": "Repository readers",
        },
        "notes": "",
    }


def write_repo(tmp_path: Path, config: dict | None = None) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / "source" / "reference").mkdir(parents=True)
    (repo / "source" / "taxonomy.md").write_text("# Taxonomy\n", encoding="utf-8")
    (repo / ".agents" / "knowledge-base.yaml").write_text(
        json.dumps(config or valid_config()),
        encoding="utf-8",
    )
    return repo


def test_valid_contract_and_paths(tmp_path: Path) -> None:
    repo = write_repo(tmp_path)
    _, config = MODULE.load_config(repo, None)
    assert MODULE.validate_config(config) == []
    assert MODULE.check_paths(repo.resolve(), config) == []


def test_classification_precedence() -> None:
    config = valid_config()
    config["editable"] = ["source/**", "compiled/**"]
    assert MODULE.classify("source/reference/item.md", config) == "editable"
    assert MODULE.classify("compiled/bundle.md", config) == "generated"
    assert MODULE.classify(".agents/knowledge-base.yaml", config) == "refused"
    assert MODULE.classify("README.md", config) == "outside"


def test_rejects_frontmatter_date_alias_drift() -> None:
    config = valid_config()
    config["frontmatter"]["date_field"] = "last_updated"
    errors = MODULE.validate_config(config)
    assert any("frontmatter.date_field" in error for error in errors)


def test_rejects_path_escape() -> None:
    config = valid_config()
    config["bundle_path"] = "../outside"
    errors = MODULE.validate_config(config)
    assert any("bundle_path" in error for error in errors)


def test_symlinked_contract_path_that_leaves_the_repo_is_refused(tmp_path: Path) -> None:  # E93
    repo = write_repo(tmp_path)
    outside = tmp_path / "outside-bundle"
    outside.mkdir()
    (repo / "linked").symlink_to(outside, target_is_directory=True)
    config = valid_config()
    config["bundle_path"] = "linked"
    try:
        errors = MODULE.check_paths(repo, config)
    except ValueError as exc:
        errors = [str(exc)]
    assert any("escapes" in error for error in errors), errors

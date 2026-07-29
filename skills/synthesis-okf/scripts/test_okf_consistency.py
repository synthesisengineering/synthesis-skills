from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


MODULE_PATH = Path(__file__).with_name("okf_consistency.py")
SPEC = importlib.util.spec_from_file_location("okf_consistency", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_repo(tmp_path: Path, document: str, name: str = "example-concept.md") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".agents").mkdir()
    bundle = repo / "source"
    concepts = bundle / "reference"
    concepts.mkdir(parents=True)
    taxonomy = concepts / "taxonomy.md"
    taxonomy.write_text(
        "# Taxonomy\n\n"
        "**type**\n"
        "`reference` · `runbook`\n\n"
        "**topic:**\n"
        "`topic:example` · `topic:governance`\n\n"
        "**confidence:**\n"
        "`confidence:draft` · `confidence:canonical`\n",
        encoding="utf-8",
    )
    config = {
        "bundle_path": "source",
        "topic_routing": {"reference": "source/reference"},
        "taxonomy_path": "source/reference/taxonomy.md",
        "frontmatter": {
            "required": ["type"],
            "house": ["title", "description", "tags", "owner", "timestamp", "status", "resource"],
            "date_field": "timestamp",
            "reserved_files": ["index.md", "log.md"],
        },
    }
    (repo / ".agents" / "knowledge-base.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    target = concepts / name
    target.write_text(document, encoding="utf-8")
    return repo, target


def test_clean_document_has_no_findings(tmp_path: Path) -> None:
    repo, target = write_repo(
        tmp_path,
        "---\n"
        "type: reference\n"
        "title: Example Concept\n"
        "tags: [\"topic:example\", \"confidence:draft\"]\n"
        "timestamp: 2026-07-29\n"
        "status: draft\n"
        "---\n\n"
        "# Example Concept\n\n"
        "Durable content.\n",
    )
    config, _ = MODULE.load_contract(repo, None)
    tags, types = MODULE.parse_taxonomy(repo / config["taxonomy_path"])
    findings = MODULE.check_document(
        repo, repo / "source", target, config, tags, types
    )
    assert findings == []


def test_detects_schema_and_body_drift(tmp_path: Path) -> None:
    repo, target = write_repo(
        tmp_path,
        "---\n"
        "type: reference\n"
        "title: Different Title\n"
        "tags: [\"topic:unknown\", \"confidence:canonical\"]\n"
        "timestamp: 2026-07-29\n"
        "last_updated: 2026-07-01\n"
        "status: draft\n"
        "---\n\n"
        "# Example Concept\n\n"
        "**Last Updated:** July 1, 2026\n"
        "**Status:** canonical\n",
        name="Example-2026.md",
    )
    config, _ = MODULE.load_contract(repo, None)
    tags, types = MODULE.parse_taxonomy(repo / config["taxonomy_path"])
    findings = MODULE.check_document(
        repo, repo / "source", target, config, tags, types
    )
    rendered = "\n".join(item.render() for item in findings)
    assert "`last_updated` duplicates configured date field `timestamp`" in rendered
    assert "disagrees with inline date" in rendered
    assert "status 'draft' disagrees with inline 'canonical'" in rendered
    assert "absent from the configured taxonomy" in rendered
    assert "differs from H1" in rendered
    assert "filename is not lowercase kebab-case" in rendered
    assert "filename contains a date" in rendered


def test_taxonomy_parser_separates_types_and_tags(tmp_path: Path) -> None:
    repo, _ = write_repo(
        tmp_path,
        "---\ntype: reference\ntitle: Example\ntags: []\n---\n# Example\n",
    )
    tags, types = MODULE.parse_taxonomy(repo / "source/reference/taxonomy.md")
    assert tags == {
        "topic:example",
        "topic:governance",
        "confidence:draft",
        "confidence:canonical",
    }
    assert types == {"reference", "runbook"}


def test_nested_status_is_not_document_metadata(tmp_path: Path) -> None:
    repo, target = write_repo(
        tmp_path,
        "---\n"
        "type: reference\n"
        "title: Example Concept\n"
        "tags: [\"topic:example\", \"confidence:draft\"]\n"
        "timestamp: 2026-07-29\n"
        "status: draft\n"
        "---\n\n"
        "# Example Concept\n\n"
        "## Component\n\n"
        "**Status:** active development\n",
    )
    config, _ = MODULE.load_contract(repo, None)
    tags, types = MODULE.parse_taxonomy(repo / config["taxonomy_path"])
    findings = MODULE.check_document(
        repo, repo / "source", target, config, tags, types
    )
    assert findings == []

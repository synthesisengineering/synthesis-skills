"""The YAML subset reader: what organization manifests and repos.yaml need, and nothing it would guess at."""

import pytest

from yaml_subset import load

REPOS = """# Workspace repo manifest
workspace: demo
status: active
repos:
  - name: ai-knowledge-demo
    memory:
      family: personal
      workspace: null
    path: ai-knowledge-demo/
    remotes:
      origin: https://example.test/demo/ai-knowledge-demo.git
    default_branches: [main]
    ritual_sync: no
    notes: "Kept # not a comment"
  - name: tool
    path: tool/
    remotes:
      origin: git@example.test:demo/tool.git
      upstream: https://example.test/up/tool.git
    default_branches: [master, main]
    ritual_sync: yes # sync daily
"""


def test_reads_the_workspace_repos_manifest_shape():
    data = load(REPOS)
    assert data["workspace"] == "demo"
    first, second = data["repos"]
    assert first["memory"] == {"family": "personal", "workspace": None}
    assert first["default_branches"] == ["main"] and first["ritual_sync"] is False
    assert first["notes"] == "Kept # not a comment"
    assert second["remotes"]["upstream"] == "https://example.test/up/tool.git"
    assert second["default_branches"] == ["master", "main"] and second["ritual_sync"] is True


def test_reads_literal_blocks_scalar_lists_and_integers():
    text = "version: 2\nauth_help: |\n  Sign in.\n\n  Then rerun.\nwelcome:\n  try_asking:\n    - \"What?\"\n    - Where\n"
    assert load(text) == {"version": 2, "auth_help": "Sign in.\n\nThen rerun.\n",
                          "welcome": {"try_asking": ["What?", "Where"]}}


@pytest.mark.parametrize("text, message", [
    ("a: 1\na: 2\n", "duplicate key"),
    ("a:\n   - x\n  - y\n", "inconsistent list indentation"),
    ("a:\n  - x\n   - y\n", "scalar list item cannot have a nested block"),
    ("just text\n", "expected 'key: value'"),
    ("list:\n  - key:\n      nested: 1\n", "outside the subset"),
    ("a: 1\n  b: 2\n", "cannot also have a nested block"),
    ("a:\n\t b: 1\n", "tabs"),
])
def test_anything_outside_the_subset_fails_closed_with_a_line_number(text, message):
    with pytest.raises(ValueError, match=message):
        load(text, source="m.yaml")


def test_empty_document_is_an_empty_map():
    assert load("# only a comment\n") == {}

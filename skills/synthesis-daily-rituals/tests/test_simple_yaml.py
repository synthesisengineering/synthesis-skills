"""The standard-library YAML reader reads what the manifests use, the way PyYAML
reads it, and refuses what it cannot read instead of half-reading it."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from simple_yaml import load  # noqa: E402

MANIFEST = """# Workspace repo manifest
workspace: demo
status: active
repos:
  - name: app
    path: app
    remotes:
      origin: https://example.com/org/app.git
      mirror: git@example.com:org/app.git
    default_branches: [main, develop]
    ritual_sync: yes   # synced every ritual
    notes: "a note # with a hash"
  - name: kb
    memory:
      family: personal
      workspace: null
    ritual_sync: no
    default_branches: []
projects:
- id: one
  description: >
    A folded description that
    runs over two lines.

    A second paragraph.
      An indented line keeps its break.
  tags:
  - alpha
  - beta
- id: two
  description: 'It''s quoted and
    continues here'
  literal: |
    line one
    line two
  empty: {}
  count: 3
  ratio: 0.5
  when: 2026-09-14
"""


def test_reads_the_shapes_the_manifests_use() -> None:
    data = load(MANIFEST)
    app, kb = data["repos"]
    assert app["remotes"] == {"origin": "https://example.com/org/app.git", "mirror": "git@example.com:org/app.git"}
    assert app["default_branches"] == ["main", "develop"]
    assert app["ritual_sync"] is True and kb["ritual_sync"] is False
    assert app["notes"] == "a note # with a hash"
    assert kb["memory"] == {"family": "personal", "workspace": None} and kb["default_branches"] == []
    one, two = data["projects"]
    assert one["description"] == ("A folded description that runs over two lines.\n"
                                  "A second paragraph.\n  An indented line keeps its break.\n")
    assert one["tags"] == ["alpha", "beta"]
    assert two["description"] == "It's quoted and continues here"
    assert two["literal"] == "line one\nline two\n"
    assert (two["empty"], two["count"], two["ratio"], two["when"]) == ({}, 3, 0.5, "2026-09-14")


def test_agrees_with_pyyaml_where_pyyaml_is_installed() -> None:
    yaml = pytest.importorskip("yaml")
    expected = yaml.safe_load(MANIFEST)
    expected["projects"][1]["when"] = str(expected["projects"][1]["when"])  # PyYAML makes a date
    assert load(MANIFEST) == expected


@pytest.mark.parametrize("text, reason", [
    ("a: &anchor 1\nb: *anchor\n", "anchor"),
    ("a: !!str 1\n", "tag"),
    ("a: {b: 1}\n", "flow mapping"),
    ("a:\n\tb: 1\n", "tab"),
    ("a: 1\na: 2\n", "duplicate"),
    ("a: [1, 2\n", "multi-line flow"),
    ("a: 1\n  b: 2\nc: [x\n", ""),
])
def test_refuses_what_it_cannot_read(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        load(text)


def test_empty_documents_and_top_level_lists() -> None:
    assert load("# only a comment\n") is None
    assert load("- a\n- b: 1\n  c: 2\n") == ["a", {"b": 1, "c": 2}]

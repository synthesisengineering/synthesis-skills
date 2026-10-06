"""The plugin's one YAML reader (synthesis/yamlish.py) reads what synthesis files use, the way
PyYAML reads it, and refuses what it cannot read instead of half-reading it.

The cases come from the six readers it replaced: the rituals' simple_yaml.py, onboarding's
yaml_subset.py, the commit check's policy reader (its strict subset), and the readers embedded
in the Slack preflight, the meeting fetch, the context doctor and the resume probe. Where an old
reader refused a form PyYAML reads, the case now asserts PyYAML's reading.
"""

from __future__ import annotations

import datetime

import pytest

from synthesis.yamlish import load, load_mapping


def agrees_with_pyyaml(text: str, got) -> None:
    """Where PyYAML is installed, it reads `text` as `got` (dates aside: they stay strings here)."""
    try:
        import yaml
    except ImportError:
        return

    def norm(node):
        if isinstance(node, dict):
            return {k: norm(v) for k, v in node.items()}
        if isinstance(node, list):
            return [norm(v) for v in node]
        return str(node) if isinstance(node, (datetime.date, datetime.datetime)) else node

    assert norm(yaml.safe_load(text)) == got


# ---- the rituals' manifests (simple_yaml.py) ------------------------------------------------------

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
    agrees_with_pyyaml(MANIFEST, data)


@pytest.mark.parametrize("text, reason", [
    ("a: &anchor 1\nb: *anchor\n", "anchor"),
    ("a: !!str 1\n", "tag"),
    ("a: {b: 1}\n", "flow mapping"),
    ("a:\n\tb: 1\n", "tab"),
    ("a: 1\na: 2\n", "duplicate"),
    ("a: [1, 2\n", "multi-line flow"),
    ("a: [x, [y]]\n", "nested flow"),
    ("a: 1\n  b: 2\nc: [x\n", "unexpected indentation"),
    ("a: 'open\n", "unterminated single-quoted"),
    ("a: \"open\n", "unterminated double-quoted"),
    ("a: 1\n- b\n", "content after the document ends"),
    ("a: |2\n   x\n", "block scalar header"),  # an indentation indicator: refused, never read as the text "|2 x"
    ("a: >-1\n  x\n", "block scalar header"),
])
def test_refuses_what_it_cannot_read(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        load(text)


def test_empty_documents_and_top_level_lists() -> None:
    assert load("# only a comment\n") is None and load("") is None
    assert load("- a\n- b: 1\n  c: 2\n") == ["a", {"b": 1, "c": 2}]


# ---- onboarding's repos.yaml and organization manifests (yaml_subset.py) ----------------------------

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


def test_reads_the_workspace_repos_manifest_shape() -> None:
    data = load(REPOS)
    assert data["workspace"] == "demo"
    first, second = data["repos"]
    assert first["memory"] == {"family": "personal", "workspace": None}
    assert first["default_branches"] == ["main"] and first["ritual_sync"] is False
    assert first["notes"] == "Kept # not a comment"
    assert second["remotes"]["upstream"] == "https://example.test/up/tool.git"
    assert second["default_branches"] == ["master", "main"] and second["ritual_sync"] is True
    agrees_with_pyyaml(REPOS, data)


def test_reads_literal_blocks_scalar_lists_and_integers() -> None:
    text = "version: 2\nauth_help: |\n  Sign in.\n\n  Then rerun.\nwelcome:\n  try_asking:\n    - \"What?\"\n    - Where\n"
    expected = {"version": 2, "auth_help": "Sign in.\n\nThen rerun.\n", "welcome": {"try_asking": ["What?", "Where"]}}
    assert load(text) == expected
    agrees_with_pyyaml(text, expected)


@pytest.mark.parametrize("text, message", [
    ("a: 1\na: 2\n", "duplicate key"),
    ("a:\n   - x\n  - y\n", "unexpected indentation"),
    ("a: 1\n  b: 2\n", "unexpected indentation"),
    ("a:\n\t b: 1\n", "tab"),
])
def test_anything_outside_the_subset_fails_closed_with_its_source_and_line(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as refused:
        load(text, source="m.yaml")
    assert str(refused.value).startswith("m.yaml: line ")


@pytest.mark.parametrize("text, expected", [
    ("a:\n  - x\n   - y\n", {"a": ["x - y"]}),  # yaml_subset refused it; a more-indented line continues the item
    ("list:\n  - key:\n      nested: 1\n", {"list": [{"key": {"nested": 1}}]}),  # yaml_subset refused it
    ("a:\n- x\n- y\n", {"a": ["x", "y"]}),  # an indentless sequence; the commit check's reader refused it
])
def test_forms_an_old_reader_refused_are_read_as_pyyaml_reads_them(text: str, expected) -> None:
    assert load(text) == expected
    agrees_with_pyyaml(text, expected)


def test_a_manifest_must_be_a_mapping_and_an_empty_one_is_empty() -> None:
    assert load_mapping("# only a comment\n") == {}
    for text in ("just text\n", "- a\n"):
        with pytest.raises(ValueError, match="expected a mapping at the top"):
            load_mapping(text, source="m.yaml")


# ---- the Slack sync config (preflight.py) and the meeting fetch config (fetch-meeting.py) -----------

def test_quotes_escapes_comments_and_booleans() -> None:
    text = ('workspace: w  # trailing comment\n'
            'channels:\n'
            '  # - id: C0COMMENTED\n'
            '  - id: "C0QUOTED"\n'
            '    name: "Alpha \\u2014 Beta # not a comment"\n'
            "    other: 'it''s'\n"
            '    active: false\n'
            'dm_channels: []\n')
    data = load_mapping(text)
    entry = data["channels"][0]
    assert entry == {"id": "C0QUOTED", "name": "Alpha \u2014 Beta # not a comment", "other": "it's", "active": False}
    assert data["dm_channels"] == [] and data["workspace"] == "w"
    agrees_with_pyyaml(text, data)


@pytest.mark.parametrize("text, reason", [
    ("channels:\n  - {id: C1}\n", "flow mapping"),
    ("channels:\n\t- id: C1\n", "tab"),
    ("no colon here\n", "expected a mapping"),
])
def test_a_sync_config_it_cannot_read_is_refused(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        load_mapping(text)


def test_an_indented_first_key_is_a_mapping_as_pyyaml_reads_it() -> None:
    assert load_mapping("  indented: first\n") == {"indented": "first"}  # the preflight's reader refused it


def test_the_meeting_fetch_config_shape() -> None:
    text = ("# synthetic\nworkspace: example\ngoogle_account: reader@example.invalid\ntranscripts_repo: /abs/repo\n"
            "transcripts_path: transcripts\nmeeting_patterns:\n"
            "  standup: 'name contains \"Standup\" and name contains \"Notes by Gemini\"'\n"
            "generic_pattern: 'name contains \"{{name}}\"'  # comment\ntranscript_tab_id:\n")
    data = load_mapping(text)
    assert data["meeting_patterns"]["standup"] == 'name contains "Standup" and name contains "Notes by Gemini"'
    assert data["generic_pattern"] == 'name contains "{{name}}"'
    assert data["transcripts_repo"] == "/abs/repo" and data["transcript_tab_id"] is None
    agrees_with_pyyaml(text, data)


# ---- projects/index.yaml (the context doctor and the resume probe) ---------------------------------

def test_index_entries_keep_their_fields_and_nested_lists_stay_nested() -> None:
    text = ("# Projects Index\nprojects:\n  - id: alpha\n    status: active\n    last_session: 2026-10-05\n"
            "    tags:\n      - nested\n    description: >\n      Folded text: not a field.\n"
            "  - id: beta\n    status: completed\n    completed_date: '2026-09-30'\n")
    alpha, beta = load(text)["projects"]
    assert alpha == {"id": "alpha", "status": "active", "last_session": "2026-10-05", "tags": ["nested"],
                     "description": "Folded text: not a field.\n"}
    assert beta == {"id": "beta", "status": "completed", "completed_date": "2026-09-30"}


def test_an_index_with_other_lists_folded_values_and_a_bare_list() -> None:
    text = ("# comment\ninitiatives:\n- id: not-a-project\nprojects:\n- id: folded\n  status: active\n"
            "  tags:\n    - nested\n  description: >\n    Two lines\n    folded into one.\n  last_session: '2026-10-01'\n"
            "- id: second\n  name: \"Second # not a comment\"\n")
    data = load(text)
    assert data["initiatives"] == [{"id": "not-a-project"}]
    folded, second = data["projects"]
    assert folded["description"] == "Two lines folded into one.\n" and folded["last_session"] == "2026-10-01"
    assert second["name"] == "Second # not a comment"
    assert load("- id: bare\n  status: paused\n") == [{"id": "bare", "status": "paused"}]
    agrees_with_pyyaml(text, data)


def test_a_description_continued_on_indented_lines_is_read_whole() -> None:
    text = "projects:\n  - id: long\n    name: 'It''s long'\n    description: The goal starts here\n      and goes on.\n"
    assert load(text)["projects"][0] == {"id": "long", "name": "It's long", "description": "The goal starts here and goes on."}


# ---- the commit policy and disclosure ledger: the strict subset (commit_check.py) -------------------

def test_strict_keeps_regex_escapes_literal() -> None:
    text = "a:\n  b:\n    - '\\bx\\b'  # comment\n    - \"y\\\\b\"\n    - \"\\bz\\b\"\n  c: []\n  e: [ ]\n  d: 'it''s'\nflag: yes\nn: 3\n"
    assert load_mapping(text, strict=True) == {"a": {"b": ["\\bx\\b", "y\\b", "\\bz\\b"], "c": [], "e": [], "d": "it's"},
                                               "flag": True, "n": 3}


@pytest.mark.parametrize("text, reason", [
    ("a: &anchor x\n", "anchor"),
    ("a:\n  - b: c\n", "inside lists are outside the supported subset"),
    ("a:\n  -\n    - b\n", "inside lists are outside the supported subset"),
    ("a: |\n  x\n", "outside the supported subset"),
    ("a: >-\n  x\n", "outside the supported subset"),
    ("a: [x]\n", "outside the supported subset"),
    ("a: {}\n", "outside the supported subset"),
    ("a: 1\na: 2\n", "duplicate key"),
    ("a: 'open\n  more'\n", "unterminated quoted string"),
    ("a: plain\n  continued\n", "unexpected indentation"),
    ("a: x\tb\n", "line 1: a tab character"),
    ("a:\n  b:\n\t- x\n", "line 3: a tab character"),
])
def test_strict_refuses_everything_outside_the_policy_shapes(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        load_mapping(text, strict=True)

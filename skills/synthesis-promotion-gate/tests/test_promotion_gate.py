"""promotion_gate.py: a built site carrying a configured marker is refused before deploy (E96).

The rendered-representation cases are the 1.0 fixture corpus, whose expected
text was generated with the destination's own HTML parser (parse5 7.3.0); the
gate's reading of each page must agree with what that parser displayed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "promotion_gate.py"
TEMPLATE = SKILL / "templates" / "promotion-markers.example.json"
sys.path.insert(0, str(SCRIPT.parent))

import promotion_gate as gate  # noqa: E402

# (case, html, displayed text, heading text, comment text): lowercased as the corpus recorded them.
CORPUS = [
    ("clean-paragraph", "<p>Clean.</p>", "clean.", "", ""),
    ("clean-heading", "<h1>Clean public page</h1>", "clean public page", "clean public page", ""),
    ("sensitive-comment", "<!-- ORIGINAL OPENER private holdings REDACTED --><p>Clean.</p>", "clean.", "",
     "original opener private holdings redacted"),
    ("sensitive-comment-colon", "<!-- ORIGINAL OPENER: private holdings REDACTED --><p>Public.</p>", "public.", "",
     "original opener: private holdings redacted"),
    ("entity-decoded-date", "<p>&lt;DATE&gt;</p>", "<date>", "", ""),
    ("publication-heading", "<h2>Publication Notes</h2>", "publication notes", "publication notes", ""),
    ("inline-adjacency", "<h2>Public<a href='/x'>ation</a> Notes</h2>", "publication notes", "publication notes", ""),
    ("unclosed-heading-repair", "<h2>Publication Notes", "publication notes", "publication notes", ""),
    ("table-foster-parenting-repair", "<tr><h2><p>Publication Notes", "publication notes", "publication notes", ""),
    ("entity-adjacency", "<h2>Public&#x61;tion&nbsp;Notes</h2>", "publication notes", "publication notes", ""),
    ("attribute-exclusion", '<img alt="Publication Notes"><p>Clean.</p>', "clean.", "", ""),
    ("code-channel-exclusion", "<pre><code>Publication Notes</code></pre><p>Clean.</p>", "clean.", "", ""),
    ("hidden-container-exclusion", "<script>Publication Notes</script><p>Clean.</p>", "clean.", "", ""),
]


@pytest.mark.parametrize("case, page, text, headings, comments", CORPUS, ids=[c[0] for c in CORPUS])
def test_views_agree_with_the_destination_parser(case, page, text, headings, comments):
    seen = gate.views(page)
    assert seen["text"].lower() == text
    assert seen["headings"].lower() == headings
    assert seen["comments"].lower() == comments
    assert seen["source"] == page


def _site(tmp_path, pages):
    dist = tmp_path / "dist"
    for rel, body in pages.items():
        (dist / rel).parent.mkdir(parents=True, exist_ok=True)
        (dist / rel).write_text(body, encoding="utf-8")
    config = tmp_path / "markers.json"
    shutil.copy(TEMPLATE, config)
    return dist, config


def _run(dist, config):
    return subprocess.run([sys.executable, str(SCRIPT), str(dist), "--config", str(config)],
                          capture_output=True, text=True, timeout=60)


def test_a_successful_build_with_the_five_round_two_defects_is_refused(tmp_path):  # E96
    pages = {
        "articles/leak/index.html": "<!-- ORIGINAL OPENER: private holdings REDACTED --><p>Public.</p>",
        "articles/date-a/index.html": "<p>&lt;DATE&gt;</p>",
        "articles/date-b/index.html": "<p>&lt;DATE&gt;</p>",
        "articles/notes-a/index.html": "<h2>Publication Notes</h2>",
        "articles/notes-b/index.html": "<h2>Public<a href='/x'>ation</a> Notes</h2>",
        "articles/clean/index.html": "<h2>Notes on publication</h2><p>I keep publication notes beside the draft.</p>",
    }
    dist, config = _site(tmp_path, pages)
    result = _run(dist, config)
    assert result.returncode == 1, result.stdout + result.stderr
    dirty = {line.split(":")[0] for line in result.stdout.splitlines()[:-1]}
    assert dirty == {p for p in pages if "clean" not in p}
    assert "private-original-opener in comments" in result.stdout
    assert "private-original-opener in source" in result.stdout
    assert "unresolved-date in text" in result.stdout
    assert "publication-notes-section in headings" in result.stdout
    assert result.stdout.rstrip().endswith("do not deploy")


def test_source_hits_carry_their_line(tmp_path):
    dist, config = _site(tmp_path, {"index.html": "<p>ok</p>\n<p>\n<!-- original opener and private holdings --></p>"})
    assert "index.html:3: private-original-opener in source" in _run(dist, config).stdout


def test_a_clean_site_passes(tmp_path):
    dist, config = _site(tmp_path, {"index.html": "<h1>Public</h1><p>Published 2026-08-26.</p>", "feed.xml": "<rss/>"})
    result = _run(dist, config)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 file(s) scanned, 3 marker(s), 0 hit(s): clean" in result.stdout


@pytest.mark.parametrize("layout", ["empty", "missing", "only-images"])
def test_nothing_to_scan_is_not_clean(tmp_path, layout):
    dist, config = _site(tmp_path, {})
    if layout == "empty":
        dist.mkdir()
    elif layout == "only-images":
        dist.mkdir()
        (dist / "logo.png").write_bytes(b"\x89PNG")
    assert _run(dist, config).returncode == 2


def test_symlinked_files_are_not_followed(tmp_path):
    outside = tmp_path / "outside.html"
    outside.write_text("<h2>Publication Notes</h2>")
    dist, config = _site(tmp_path, {"index.html": "<p>Public.</p>"})
    (dist / "linked.html").symlink_to(outside)
    result = _run(dist, config)
    assert result.returncode == 0 and "1 file(s) scanned" in result.stdout


@pytest.mark.parametrize("defect, message", [
    ({"pattern": "publication"}, "negative example"),
    ({"pattern": "never-matches-anything"}, "positive example"),
    ({"in": ["sidecar-flags"]}, "'in' takes"),
    ({"id": "unresolved-date"}, "unique id"),
])
def test_an_inert_or_ambiguous_policy_is_refused(tmp_path, defect, message):
    dist, config = _site(tmp_path, {"index.html": "<p>Public.</p>"})
    data = json.loads(config.read_text())
    data["markers"][2].update(defect)
    config.write_text(json.dumps(data))
    result = _run(dist, config)
    assert result.returncode == 2 and message in result.stderr


def test_a_config_without_markers_is_refused(tmp_path):
    dist, config = _site(tmp_path, {"index.html": "<p>Public.</p>"})
    config.write_text('{"markers": []}')
    assert _run(dist, config).returncode == 2


def test_prompt_hidden_skill_is_reachable_through_router():
    router = (SKILL.parent / "synthesis-skill-router" / "SKILL.md").read_text(encoding="utf-8")
    assert "../synthesis-promotion-gate/SKILL.md" in router
    assert "allow_implicit_invocation: false" in (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

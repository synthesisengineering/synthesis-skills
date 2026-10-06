"""kb_scan.py: read-only reconnaissance over an OKF bundle, its frontmatter read by the plugin's YAML reader."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kb_scan.py"


def _bundle(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    (root / "people").mkdir(parents=True)
    files = {
        "people/alpha.md": "---\ntype: Person\ntitle: 'Alpha: the first'\ntags: [kind:person, {role: lead}]\n"
                           "timestamp: 2026-01-05\n---\n# Alpha\n\nWorks with Example Corp.\n",
        "people/beta.md": '---\ntype: Person\ntitle: "Beta"\ntimestamp: "2026-09-01T10:00:00Z"\n---\n# Beta\n',
        "notes.md": "# Notes without frontmatter\n\nexample corp again.\n",
        "broken.md": "---\ntitle: [unclosed\n---\n# Broken\n",
        "index.md": "# Index\n\nExample Corp is listed here but index files are not concepts.\n",
        "README.md": "# Readme\n",
    }
    for rel, text in files.items():
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=60)


def test_list_reads_type_and_title_and_skips_reserved_files(tmp_path):
    done = _run(_bundle(tmp_path), "--list")
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert "people/alpha.md  [type: Person]  Alpha: the first" in lines
    assert any(l.startswith("people/beta.md") and l.endswith("[type: Person]  Beta") for l in lines)
    assert any(l.startswith("notes.md") and "[type: —]" in l for l in lines)
    assert not any(l.startswith(("index.md", "README.md")) for l in lines)
    assert lines[-1] == "— 4 concept(s)."
    assert "unreadable frontmatter in" in done.stderr and "broken.md" in done.stderr


def test_stale_lists_older_and_undated_concepts_only(tmp_path):
    done = _run(_bundle(tmp_path), "--stale", "2026-06-01")
    assert done.returncode == 0, done.stderr
    listed = {line.split()[-1] for line in done.stdout.splitlines()[:-1]}
    assert listed == {"people/alpha.md", "notes.md", "broken.md"}  # beta is newer; the others are older or undated


def test_entity_finds_every_mention_with_its_line(tmp_path):
    done = _run(_bundle(tmp_path), "--entity", "Example Corp")
    assert done.returncode == 0, done.stderr
    assert "— 2 mention(s) of [Example Corp] across 2 file(s)." in done.stdout
    assert "index.md" not in done.stdout


def test_bad_invocations_exit_2(tmp_path):
    assert _run(_bundle(tmp_path), "--stale", "June").returncode == 2
    assert _run(tmp_path / "missing", "--list").returncode == 2

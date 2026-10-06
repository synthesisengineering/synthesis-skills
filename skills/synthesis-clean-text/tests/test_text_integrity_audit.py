"""text_integrity_audit.py: report hidden characters by position, never change the text (E88).

Moved with the script from synthesis-text-provenance (scripts/test_provenance_tools.py,
IntegrityTests), as pytest functions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "text_integrity_audit.py"
sys.path.insert(0, str(SCRIPT.parent))

import text_integrity_audit as tia  # noqa: E402


def test_reports_format_and_bidi_controls_without_mutation():
    text = "alpha​beta‮gamma\n"
    raw = text.encode("utf-8")
    report = tia.analyze_text(text, raw)
    assert raw == text.encode("utf-8")
    assert len(report["findings"]) == 2
    assert report["finding_counts"] == {"bidi-control": 1, "format-control": 1}
    assert "does not detect" in report["interpretation"]
    assert [(f["line"], f["column"], f["codepoint"]) for f in report["findings"]] == [(1, 6, "U+200B"), (1, 11, "U+202E")]


def test_normal_text_has_no_findings():
    text = "A normal line.\nAnother line.\n"
    assert tia.analyze_text(text, text.encode("utf-8"))["findings"] == []


def test_reports_non_ascii_space_variation_selector_and_noncharacter():
    text = "alpha beta️gamma﷐"
    report = tia.analyze_text(text, text.encode("utf-8"))
    assert report["finding_counts"] == {"non-ascii-space": 1, "unicode-noncharacter": 1, "variation-selector": 1}


def test_file_audit_asserts_two_complete_read_hashes(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("unchanged\n", encoding="utf-8")
    before = source.stat()
    _text, raw, state = tia.read_input(str(source))
    after = source.stat()
    assert state is not None and state["full_read_hashes_match"]
    assert state["sha256_first_read"] == state["sha256_second_read"] == tia.hashlib.sha256(raw).hexdigest()
    assert state["unchanged_during_audit"]
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


def test_file_audit_rejects_change_between_full_reads(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("first", encoding="utf-8")
    with mock.patch.object(Path, "read_bytes", side_effect=[b"first", b"second"]):
        with pytest.raises(ValueError, match="changed between two complete reads"):
            tia.read_input(str(source))


def _run(*args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True,
                          text=True, timeout=30)


def test_cli_reports_and_leaves_the_file_untouched(tmp_path):
    source = tmp_path / "article.txt"
    source.write_bytes("zero​width and \U000e0041 tag\n".encode("utf-8"))
    before = source.read_bytes()
    human = _run(str(source))
    assert human.returncode == 0 and "line 1, column 5: U+200B" in human.stdout
    flagged = _run(str(source), "--format", "json", "--fail-on-findings")
    assert flagged.returncode == 1
    assert json.loads(flagged.stdout)["finding_counts"] == {"format-control": 2}
    assert source.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["article.txt"]  # no cleaned copy written


def test_cli_errors_exit_2(tmp_path):
    assert _run(str(tmp_path / "missing.txt")).returncode == 2
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe not utf-8")
    assert _run(str(bad)).returncode == 2
    assert _run("-", stdin="plain\n").returncode == 0

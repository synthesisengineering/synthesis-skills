"""Tests for skill_outputs: generator provenance verification."""
import hashlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import skill_outputs as so  # noqa: E402


def _page(tmp_path: Path, name: str, *, marker=True, spec="{}", tamper=False,
          spec_file=True, rulings_file=False) -> Path:
    embedded = spec
    digest = hashlib.sha256(embedded.encode()).hexdigest()
    if tamper:
        embedded += "<!-- edited -->"
    head = (f"<!-- synthesis-decision-packet spec-sha256:{digest} -->\n"
            if marker else "")
    html = ("<!doctype html>\n" + head +
            '<script type="application/json" id="spec">' + embedded + "</script>\n")
    page = tmp_path / "resources" / "artifacts" / name
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(html, encoding="utf-8")
    slug = name[len("2026-09-20-"):-len(".html")] if name[:10] == "2026-09-20" else name[:-5]
    if spec_file:
        (page.parent / f"2026-09-20-{slug}-spec.json").write_text("{}", encoding="utf-8")
    if rulings_file:
        (page.parent / f"2026-09-20-{slug}-rulings.json").write_text("{}", encoding="utf-8")
    return page


def test_marked_page_with_filed_spec_passes(tmp_path):
    page = _page(tmp_path, "2026-09-20-x-packet.html")
    assert so.verify_packet(page) == []


def test_unmarked_live_page_is_a_defect(tmp_path):
    page = _page(tmp_path, "2026-09-20-x-packet.html", marker=False)
    (found,) = so.verify_packet(page)
    assert found.severity == "defect"
    assert "build_packet.py" in found.remedy


def test_unmarked_ruled_page_is_a_warning(tmp_path):
    page = _page(tmp_path, "2026-09-20-x-packet.html", marker=False, rulings_file=True)
    (found,) = so.verify_packet(page)
    assert found.severity == "warning"


def test_tampered_page_is_a_defect(tmp_path):
    page = _page(tmp_path, "2026-09-20-x-packet.html", tamper=True)
    (found,) = so.verify_packet(page)
    assert found.severity == "defect"
    assert "do not hand-edit" in found.remedy


def test_missing_spec_is_a_warning(tmp_path):
    page = _page(tmp_path, "2026-09-20-x-packet.html", spec_file=False)
    (found,) = so.verify_packet(page)
    assert found.severity == "warning"


def test_scan_finds_packets_and_skips_other_files(tmp_path):
    _page(tmp_path, "2026-09-20-x-packet.html", marker=False)
    other = tmp_path / "resources" / "artifacts" / "notes.html"
    other.write_text("<html></html>", encoding="utf-8")
    findings = so.scan_project(tmp_path)
    assert len(findings) == 1
    assert findings[0].path.name == "2026-09-20-x-packet.html"


def test_doctor_heartbeat():
    ok, msg = so.doctor()
    assert ok, msg

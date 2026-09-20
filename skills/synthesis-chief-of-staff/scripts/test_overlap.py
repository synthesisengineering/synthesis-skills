"""Cross-owner overlap service over the shared time-block layer.

The shared layer (§3) is a JSON file in the personal repo that every seat
publishes its owned commitments' time blocks to, with real titles. This
script is the global conflict-detection service any seat can call: it takes
a window and returns overlaps across owners. It never calls MCP tools, never
touches a calendar, and never writes — the layer file is read-only here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

OVERLAP = Path(__file__).with_name("overlap.py")
FIXTURES = Path(__file__).with_name("fixtures")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OVERLAP), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_fixtures_exist() -> None:
    assert (FIXTURES / "time-blocks-two-owners.json").is_file()
    assert (FIXTURES / "time-blocks-same-owner.json").is_file()
    assert (FIXTURES / "time-blocks-touching.json").is_file()
    assert (FIXTURES / "time-blocks-invalid.json").is_file()


def test_validate_accepts_well_formed_layer() -> None:
    result = _run("validate", "--layer", str(FIXTURES / "time-blocks-two-owners.json"))
    assert result.returncode == 0, result.stderr


def test_validate_rejects_invalid_layer() -> None:
    result = _run("validate", "--layer", str(FIXTURES / "time-blocks-invalid.json"))
    assert result.returncode == 2
    assert "block 1" in result.stderr


def test_validate_rejects_missing_file() -> None:
    result = _run("validate", "--layer", str(FIXTURES / "does-not-exist.json"))
    assert result.returncode == 2
    assert "cannot read" in result.stderr


def test_validate_rejects_malformed_json(tmp_path: Path) -> None:
    layer = tmp_path / "layer.json"
    layer.write_text("{not json", encoding="utf-8")
    result = _run("validate", "--layer", str(layer))
    assert result.returncode == 2
    assert "not valid JSON" in result.stderr


def test_validate_rejects_wrong_format_tag(tmp_path: Path) -> None:
    layer = tmp_path / "layer.json"
    layer.write_text(json.dumps({"format": "something-else/v9", "blocks": []}), encoding="utf-8")
    result = _run("validate", "--layer", str(layer))
    assert result.returncode == 2
    assert "format" in result.stderr


def test_validate_rejects_end_before_start(tmp_path: Path) -> None:
    layer = tmp_path / "layer.json"
    layer.write_text(
        json.dumps(
            {
                "format": "synthesis-time-blocks/v1",
                "blocks": [
                    {
                        "owner": "personal",
                        "title": "Backwards block",
                        "start": "2026-09-20T15:00:00-04:00",
                        "end": "2026-09-20T14:00:00-04:00",
                        "source": "personal-calendar",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = _run("validate", "--layer", str(layer))
    assert result.returncode == 2
    assert "end" in result.stderr


def test_validate_rejects_naive_datetime(tmp_path: Path) -> None:
    layer = tmp_path / "layer.json"
    layer.write_text(
        json.dumps(
            {
                "format": "synthesis-time-blocks/v1",
                "blocks": [
                    {
                        "owner": "personal",
                        "title": "No offset",
                        "start": "2026-09-20T14:00:00",
                        "end": "2026-09-20T15:00:00",
                        "source": "personal-calendar",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = _run("validate", "--layer", str(layer))
    assert result.returncode == 2
    assert "offset" in result.stderr


def test_overlaps_finds_cross_owner_pair() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-two-owners.json"),
        "--from",
        "2026-09-20T00:00:00-04:00",
        "--to",
        "2026-09-21T00:00:00-04:00",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["window"] == {
        "from": "2026-09-20T00:00:00-04:00",
        "to": "2026-09-21T00:00:00-04:00",
    }
    assert len(payload["overlaps"]) == 1
    [pair] = payload["overlaps"]
    owners = {pair["a"]["owner"], pair["b"]["owner"]}
    assert owners == {"personal", "work"}
    assert pair["overlap_start"] == "2026-09-20T14:30:00-04:00"
    assert pair["overlap_end"] == "2026-09-20T15:00:00-04:00"
    assert pair["a"]["title"] and pair["b"]["title"]


def test_overlaps_excludes_same_owner_pairs() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-same-owner.json"),
        "--from",
        "2026-09-20T00:00:00-04:00",
        "--to",
        "2026-09-21T00:00:00-04:00",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["overlaps"] == []


def test_overlaps_excludes_touching_endpoints() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-touching.json"),
        "--from",
        "2026-09-20T00:00:00-04:00",
        "--to",
        "2026-09-21T00:00:00-04:00",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["overlaps"] == []


def test_overlaps_respects_window() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-two-owners.json"),
        "--from",
        "2026-09-21T00:00:00-04:00",
        "--to",
        "2026-09-22T00:00:00-04:00",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["overlaps"] == []


def test_overlaps_human_output_names_both_sides() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-two-owners.json"),
        "--from",
        "2026-09-20T00:00:00-04:00",
        "--to",
        "2026-09-21T00:00:00-04:00",
    )
    assert result.returncode == 0, result.stderr
    assert "personal" in result.stdout
    assert "work" in result.stdout
    assert "no cross-owner overlaps" not in result.stdout


def test_overlaps_empty_layer_reports_none() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-two-owners.json"),
        "--from",
        "2026-09-21T00:00:00-04:00",
        "--to",
        "2026-09-22T00:00:00-04:00",
    )
    assert result.returncode == 0, result.stderr
    assert "no cross-owner overlaps" in result.stdout


def test_overlaps_rejects_inverted_window() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-two-owners.json"),
        "--from",
        "2026-09-21T00:00:00-04:00",
        "--to",
        "2026-09-20T00:00:00-04:00",
    )
    assert result.returncode == 2
    assert "window" in result.stderr


def test_overlaps_rejects_invalid_layer() -> None:
    result = _run(
        "overlaps",
        "--layer",
        str(FIXTURES / "time-blocks-invalid.json"),
        "--from",
        "2026-09-20T00:00:00-04:00",
        "--to",
        "2026-09-21T00:00:00-04:00",
    )
    assert result.returncode == 2


def test_overlaps_never_writes_the_layer(tmp_path: Path) -> None:
    copy = tmp_path / "layer.json"
    copy.write_bytes((FIXTURES / "time-blocks-two-owners.json").read_bytes())
    before = copy.read_bytes()
    result = _run(
        "overlaps",
        "--layer",
        str(copy),
        "--from",
        "2026-09-20T00:00:00-04:00",
        "--to",
        "2026-09-21T00:00:00-04:00",
    )
    assert result.returncode == 0, result.stderr
    assert copy.read_bytes() == before


def test_overlaps_resolves_layer_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHESIS_TIME_BLOCKS", str(FIXTURES / "time-blocks-two-owners.json"))
    proc = subprocess.run(
        [
            sys.executable,
            str(OVERLAP),
            "overlaps",
            "--from",
            "2026-09-20T00:00:00-04:00",
            "--to",
            "2026-09-21T00:00:00-04:00",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, "SYNTHESIS_TIME_BLOCKS": str(FIXTURES / "time-blocks-two-owners.json")},
    )
    assert proc.returncode == 0, proc.stderr
    assert len(json.loads(proc.stdout)["overlaps"]) == 1


def test_overlaps_without_layer_is_refused() -> None:
    env = {k: v for k, v in __import__("os").environ.items() if k != "SYNTHESIS_TIME_BLOCKS"}
    proc = subprocess.run(
        [
            sys.executable,
            str(OVERLAP),
            "overlaps",
            "--from",
            "2026-09-20T00:00:00-04:00",
            "--to",
            "2026-09-21T00:00:00-04:00",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 2
    assert "SYNTHESIS_TIME_BLOCKS" in proc.stderr

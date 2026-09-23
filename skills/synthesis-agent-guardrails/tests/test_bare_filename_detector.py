#!/usr/bin/env python3
"""Executable source fixtures for the shared bare-filename detector."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parent.parent / "hooks" / "claude" / "bare_filename_detector.py"
SPEC = importlib.util.spec_from_file_location(
    "private_bare_filename_detector_source", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def hook_gate_open(monkeypatch):
    # Hooks ship disabled by default; these tests exercise behavior with the gate open.
    monkeypatch.setattr(MODULE, "hook_enabled", lambda name: True)


def tokens(assistant: str, user: str = "", cwd: str = "") -> set[str]:
    return {
        hit["token"]
        for hit in MODULE.find_violations(assistant, user, cwd)
    }


def test_detector_flags_bare_filenames_and_relative_paths() -> None:
    assert tokens(
        "I updated setb_inventory.py and the results are in dupes.json."
    ) == {"setb_inventory.py", "dupes.json"}
    assert tokens(
        "See resources/scripts/duplicate_detector.py for the instrument."
    ) == {"resources/scripts/duplicate_detector.py"}


def test_detector_flags_an_on_disk_slug(tmp_path: Path) -> None:
    (tmp_path / "batch-2026-04-20.md").write_text("test\n", encoding="utf-8")

    assert tokens(
        "The 87-file batch-2026-04-20 tier is the real work.",
        cwd=str(tmp_path),
    ) == {"batch-2026-04-20"}


@pytest.mark.parametrize(
    ("assistant", "user"),
    [
        (
            "See [duplicate_detector.py](/absolute/x/duplicate_detector.py).",
            "",
        ),
        ("Run `python3 setb_inventory.py --json out.json` to regenerate.", ""),
        ("```bash\npython3 dupes.py --self-test\n```", ""),
        ("Yes, dupes.json was lost in the reboot.", "What happened to dupes.json?"),
        ("Published at https://example.com/blog/vacation-policy/ today.", ""),
        ("The approach is consistent-comprehensible-and-cost-effective.", ""),
    ],
)
def test_detector_preserves_quoted_linked_echoed_and_ordinary_text(
    assistant: str, user: str
) -> None:
    assert tokens(assistant, user) == set()


def test_stripper_keeps_only_the_bare_filename() -> None:
    stripped = MODULE.strip_linked_and_quoted(
        "[a](/absolute/a.md) and `b.md` and c.md"
    )

    assert "c.md" in stripped
    assert "/absolute/a.md" not in stripped
    assert "`b.md`" not in stripped


def test_claude_input_contract_records_source_detector_result(
    tmp_path: Path, monkeypatch
) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "message": {"content": "Please report the result."},
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": "See report.json."}
                            ]
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    log = tmp_path / "violations.jsonl"
    monkeypatch.setattr(MODULE, "LOG_FILE", log)
    monkeypatch.setattr(
        MODULE.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "session_id": "claude-source-test",
                    "cwd": str(tmp_path),
                    "transcript_path": str(transcript),
                }
            )
        ),
    )

    assert MODULE.main() == 0
    entry = json.loads(log.read_text(encoding="utf-8"))
    assert entry["session_id"] == "claude-source-test"
    assert {hit["token"] for hit in entry["violations"]} == {"report.json"}

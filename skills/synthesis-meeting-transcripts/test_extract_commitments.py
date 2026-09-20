"""Step 4.7: candidate commitments surface from saved transcripts.

The verifier proves fidelity; this scanner asks whether anything is owed.
First-person commitment shapes with timestamps and speakers, printed as
candidates only — creation stays with the principal.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCAN = _load("extract_commitments.py")


GEMINI_BOLD = "**Rajiv Pant:** Oh of course, I will be there.\n"
GEMINI_BARE = "Rajiv Pant: Let me send you the draft by Friday.\n"
PLAUD_TS = "**[11:59:18] Rajiv Pant:** Oh of course.\n"
PLAUD_RANGE = "**[00:00 - 00:08] Dana Smith:** I promise I will review it.\n"
UNDIARIZED = "00:01:31\nRajiv Pant: Send me the link.\n"
NO_COMMIT = "**Dana Smith:** The architecture looks sound.\n"
SECOND_PERSON = "**Dana Smith:** You will enjoy the offsite.\n"


def test_gemini_bold_line_flags_shape() -> None:
    result = SCAN.scan(GEMINI_BOLD)
    assert result["dialogue_lines"] == 1
    [candidate] = result["candidates"]
    assert candidate["speaker"] == "Rajiv Pant"
    assert candidate["timestamp"] is None
    assert candidate["shape"] in ("i-will", "of-course")


def test_gemini_bare_line_flags_with_date_shape() -> None:
    result = SCAN.scan(GEMINI_BARE)
    [candidate] = result["candidates"]
    assert candidate["speaker"] == "Rajiv Pant"
    assert candidate["shape"] in ("let-me", "send-me", "by-date", "i-will")


def test_plaud_timestamp_is_captured() -> None:
    result = SCAN.scan(PLAUD_TS)
    [candidate] = result["candidates"]
    assert candidate["timestamp"] == "11:59:18"
    assert candidate["speaker"] == "Rajiv Pant"
    assert candidate["shape"] == "of-course"


def test_plaud_range_uses_range_start() -> None:
    result = SCAN.scan(PLAUD_RANGE)
    [candidate] = result["candidates"]
    assert candidate["timestamp"] == "00:00"
    assert candidate["speaker"] == "Dana Smith"


def test_undiarized_standalone_timestamp_stamps_next_line() -> None:
    result = SCAN.scan(UNDIARIZED)
    assert result["dialogue_lines"] == 1
    [candidate] = result["candidates"]
    assert candidate["timestamp"] == "00:01:31"
    assert candidate["shape"] == "send-me"


def test_non_commitment_and_second_person_are_quiet() -> None:
    assert SCAN.scan(NO_COMMIT)["candidates"] == []
    assert SCAN.scan(SECOND_PERSON)["candidates"] == []


def test_speaker_filter_narrows_to_principal() -> None:
    text = PLAUD_TS + "**[12:00:00] Dana Smith:** I will handle it.\n"
    assert len(SCAN.scan(text)["candidates"]) == 2
    filtered = SCAN.scan(text, speaker="Rajiv Pant")
    assert len(filtered["candidates"]) == 1
    assert filtered["candidates"][0]["speaker"] == "Rajiv Pant"


def test_summary_prose_without_dialogue_reports_zero(tmp_path: Path, capsys) -> None:
    target = tmp_path / "summary.md"
    target.write_text("# Notes\n\nDiscussed X (00:05:12).\n", encoding="utf-8")
    assert SCAN.main([str(target)]) == 0
    out = capsys.readouterr().out
    assert "0 dialogue lines" in out
    assert "no dialogue lines found" in out


def test_missing_file_refuses(tmp_path: Path) -> None:
    assert SCAN.main([str(tmp_path / "absent.md")]) == 2


def test_json_shape(tmp_path: Path, capsys) -> None:
    target = tmp_path / "meeting.md"
    target.write_text(PLAUD_TS, encoding="utf-8")
    assert SCAN.main([str(target), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dialogue_lines"] == 1
    [candidate] = payload["candidates"]
    assert candidate["timestamp"] == "11:59:18"
    assert set(candidate) == {"timestamp", "speaker", "shape", "quote"}


def test_stamp_prints_owner_lines(capsys) -> None:
    assert SCAN.main(["--stamp", "--owner", "personal", "--owner-rule", "2"]) == 0
    out = capsys.readouterr().out
    assert "owner: personal" in out
    assert "owner_rule: 2" in out


def test_stamp_accepts_candidate_confirmed(capsys) -> None:
    assert (
        SCAN.main(["--stamp", "--owner", "work", "--owner-rule", "candidate-confirmed"])
        == 0
    )
    out = capsys.readouterr().out
    assert "owner_rule: candidate-confirmed" in out


def test_stamp_json_shape(capsys) -> None:
    assert (
        SCAN.main(["--stamp", "--owner", "work", "--owner-rule", "1", "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"owner": "work", "owner_rule": "1"}


def test_stamp_rejects_bad_rule() -> None:
    assert SCAN.main(["--stamp", "--owner", "work", "--owner-rule", "7"]) == 2


def test_stamp_rejects_empty_owner() -> None:
    assert SCAN.main(["--stamp", "--owner", "  ", "--owner-rule", "1"]) == 2


def test_stamp_needs_owner_and_rule() -> None:
    assert SCAN.main(["--stamp", "--owner", "work"]) == 2
    assert SCAN.main(["--stamp", "--owner-rule", "1"]) == 2

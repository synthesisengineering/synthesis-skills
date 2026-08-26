#!/usr/bin/env python3
"""Generation-zero acceptance for transcript-primary source classification."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "transcript_primary.py"
SUMMARY = ROOT / "fixtures" / "structured-summary-128-lines.md"
RAW = ROOT / "fixtures" / "raw-message-transcript.md"
KNOWN_PERMALINK = (
    "https://example-workspace.slack.com/archives/"
    "C0123456789/p1700000005000006"
)


def invoke(*args: str) -> tuple[int, dict]:
    if not SCRIPT.is_file():
        return 127, {"error": f"missing production entry point: {SCRIPT.name}"}
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {
            "error": "production entry point did not emit JSON",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    return completed.returncode, payload


def test_fixture_shape() -> None:
    assert len(SUMMARY.read_text(encoding="utf-8").splitlines()) == 128


def test_component_versions_match_skill_metadata() -> None:
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(skill_text.split("---", 2)[1])
    expected = frontmatter["metadata"]["version"]
    for script in (SCRIPT, ROOT / "verify_transcripts.py"):
        completed = subprocess.run(
            [sys.executable, str(script), "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0
        assert completed.stdout.strip() == expected


def test_structured_summary_is_derived() -> None:
    code, result = invoke("classify", str(SUMMARY))
    assert code == 1
    assert result["source_class"] == "derived"
    assert result["primary_source_eligible"] is False


def test_summary_with_bare_message_timestamps_is_derived() -> None:
    injected = SUMMARY.read_text(encoding="utf-8") + """
message_ts: `1800000001.000001`
message_ts: `1800000002.000002`
message_ts: `1800000003.000003`
message_ts: `1800000004.000004`
message_ts: `1800000005.000005`
message_ts: `1800000006.000006`
message_ts: `1800000007.000007`
"""
    with tempfile.TemporaryDirectory() as temporary:
        artifact = Path(temporary) / "summary-with-markers.md"
        artifact.write_text(injected, encoding="utf-8")
        code, result = invoke("classify", str(artifact))
    assert code == 1
    assert result["source_class"] == "derived"
    assert result["evidence"]["raw_message_record_count"] == 0


def test_marker_only_file_is_derived() -> None:
    markers = "\n".join(
        f"message_ts: `180000000{index}.00000{index}`" for index in range(1, 6)
    )
    with tempfile.TemporaryDirectory() as temporary:
        artifact = Path(temporary) / "markers-only.md"
        artifact.write_text(markers + "\n", encoding="utf-8")
        code, result = invoke("classify", str(artifact))
    assert code == 1
    assert result["source_class"] == "derived"
    assert result["evidence"]["raw_message_record_count"] == 0


def test_heading_cannot_upgrade_summary() -> None:
    code, result = invoke("authorize-attribution", str(SUMMARY), "--location", f"permalink:{KNOWN_PERMALINK}")
    assert code == 1
    assert result["enforcement_outcome"] == "refused-derived-source"


def test_raw_message_markers_establish_source_grade() -> None:
    code, result = invoke("classify", str(RAW))
    assert code == 0
    assert result["source_class"] == "verbatim"
    assert result["primary_source_eligible"] is True
    assert result["control_class"] == "diagnostic"
    assert result["issues_authority_receipt"] is False


def test_permalink_and_message_ts_for_one_message_are_deduplicated() -> None:
    rows = ["# Three-message export", ""]
    for index in range(1, 4):
        timestamp = f"170000000{index}.00000{index}"
        permalink_timestamp = timestamp.replace(".", "")
        rows.extend(
            [
                f"## Message {index}",
                (
                    "https://example-workspace.slack.com/archives/"
                    f"C0123456789/p{permalink_timestamp}"
                ),
                f"message_ts: `{timestamp}`",
                "Synthetic message body.",
                "",
            ]
        )
    with tempfile.TemporaryDirectory() as temporary:
        artifact = Path(temporary) / "three-messages.md"
        artifact.write_text("\n".join(rows), encoding="utf-8")
        code, result = invoke("classify", str(artifact))
    assert code == 1
    assert result["source_class"] == "derived"
    assert result["evidence"]["distinct_message_location_count"] == 3


def test_attribution_without_location_is_refused() -> None:
    code, result = invoke("authorize-attribution", str(RAW))
    assert code == 1
    assert result["source_class"] == "verbatim"
    assert result["enforcement_outcome"] == "refused-missing-location"
    assert result["issues_authority_receipt"] is False


def test_unknown_location_is_refused() -> None:
    code, result = invoke(
        "authorize-attribution",
        str(RAW),
        "--location",
        "message_ts:1999999999.999999",
    )
    assert code == 1
    assert result["enforcement_outcome"] == "refused-unresolved-location"


def test_location_must_belong_to_a_complete_raw_record() -> None:
    injected = RAW.read_text(encoding="utf-8") + "\nmessage_ts: `1900000000.000001`\n"
    with tempfile.TemporaryDirectory() as temporary:
        artifact = Path(temporary) / "raw-plus-loose-marker.md"
        artifact.write_text(injected, encoding="utf-8")
        code, result = invoke(
            "authorize-attribution",
            str(artifact),
            "--location",
            "message_ts:1900000000.000001",
        )
    assert code == 1
    assert result["enforcement_outcome"] == "refused-unresolved-location"


def test_mismatched_permalink_and_message_timestamp_refuses_source_grade() -> None:
    mismatched = RAW.read_text(encoding="utf-8").replace(
        "message_ts: `1700000000.000001`",
        "message_ts: `1900000000.000001`",
        1,
    )
    with tempfile.TemporaryDirectory() as temporary:
        artifact = Path(temporary) / "identifier-mismatch.md"
        artifact.write_text(mismatched, encoding="utf-8")
        code, result = invoke("classify", str(artifact))
    assert code == 1
    assert result["source_class"] == "derived"
    assert result["evidence"]["identifier_mismatch_count"] == 1


def test_thread_location_is_not_quote_granular() -> None:
    code, result = invoke(
        "authorize-attribution",
        str(RAW),
        "--location",
        "thread_ts:1700000000.000001",
    )
    assert code == 1
    assert result["enforcement_outcome"] == (
        "refused-thread-location-not-message-granular"
    )


def test_matching_location_issues_hash_bound_receipt() -> None:
    code, result = invoke(
        "authorize-attribution",
        str(RAW),
        "--location",
        f"permalink:{KNOWN_PERMALINK}",
    )
    assert code == 0
    assert result["control_class"] == "enforced-gate"
    assert result["issues_authority_receipt"] is True
    assert result["enforcement_outcome"] == "authorized-attribution-location"
    assert result["receipt"]["input_sha256"]
    assert result["receipt"]["location"] == f"permalink:{KNOWN_PERMALINK}"
    assert result["receipt"]["receipt_id"]


def test_every_result_names_unverified_remainder() -> None:
    scenarios = (
        ("classify", str(SUMMARY)),
        ("classify", str(RAW)),
        ("authorize-attribution", str(RAW)),
        (
            "authorize-attribution",
            str(RAW),
            "--location",
            f"permalink:{KNOWN_PERMALINK}",
        ),
    )
    for scenario in scenarios:
        _, result = invoke(*scenario)
        assert result["unverified_remainder"]


def test_acceptance_manifest_is_closed_and_resolvable() -> None:
    manifest = yaml.safe_load((ROOT / "acceptance-suite.yaml").read_text(encoding="utf-8"))
    assert manifest["membership"] == "closed"
    assert manifest["production_entry_point"] == "transcript_primary.py"
    cases = manifest["cases"]
    assert {case["control_class"] for case in cases} == {
        "acceptance-test",
        "diagnostic",
        "enforced-gate",
    }
    functions = {name for name, value in globals().items() if name.startswith("test_") and callable(value)}
    declared = {case["fixture"].split("::", 1)[1] for case in cases}
    assert declared == functions


def main() -> int:
    failures: list[str] = []
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - standalone acceptance runner
            failures.append(f"{test.__name__}: {type(exc).__name__}: {exc}")
    if failures:
        print(f"FAILED — {len(failures)} of {len(tests)} transcript-primary checks")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK — {len(tests)} transcript-primary checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

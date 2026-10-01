"""The real CLI doctor diagnoses bounded actual source bytes without admission."""

import json
from pathlib import Path
import subprocess
import sys
from copy import deepcopy

import pytest
from test_autopilot_cli import world as world, cli
from test_native_claude_context import record, write_source

__all__ = ["world"]


def doctor(path, **kwargs):
    import native_doctor

    return native_doctor.inspect_source(
        path, client="claude", expected_root_session_id="synthetic-root", **kwargs
    )


def test_empty_source_and_header_only_do_not_certify_enrolled_eof(tmp_path):
    p, b, c = write_source(tmp_path, [])
    result = doctor(p)
    assert result["status"] == "PASS" and result["records_checked"] == 1
    import native_observations

    assert result["normalizer_sha256"] == native_observations.ADAPTER_SHA256
    assert len(result["source_generation"]) == 64
    result = doctor(p, start_offset=p.stat().st_size)
    assert result["status"] == "UNKNOWN" and result["records_checked"] == 0
    assert result["authority_granted"] is False


def test_frozen_tail_scan_reports_partial_coverage_and_unknown_type(tmp_path):
    p, b, c = write_source(tmp_path, [record("edited_text_file") for _ in range(20)])
    result = doctor(p, byte_budget=4096)
    assert result["status"] == "PASS" and result["sample_decode"] == "PASS"
    assert result["source_history_coverage"] == "UNKNOWN"
    assert result["records_checked"] > 0 and result["bounds"]["start"] > 0
    with p.open("a") as f:
        f.write(
            json.dumps({"type": "future_control", "sessionId": "synthetic-root"}) + "\n"
        )
    result = doctor(p, byte_budget=4096)
    assert result["status"] == "FAIL" and result["first_gap"] is not None
    assert result["gap_count"] == 1


@pytest.mark.parametrize(
    "fault", ["foreign", "malformed", "duplicate", "partial", "oversized"]
)
def test_doctor_exposes_failed_and_incomplete_actual_bytes(tmp_path, fault):
    row = record("edited_text_file")
    raw = json.dumps(row).encode() + b"\n"
    if fault == "foreign":
        raw = raw.replace(b"synthetic-root", b"foreign-root")
    elif fault == "duplicate":
        raw = raw.replace(
            b'"type": "attachment"', b'"type": "attachment", "type": "attachment"', 1
        )
    elif fault == "malformed":
        raw = b"{not JSON}\n"
    elif fault == "partial":
        raw = raw[:-9]
    elif fault == "oversized":
        row["attachment"]["payload"] = "x" * (1024 * 1024)
        raw = json.dumps(row).encode() + b"\n"
    p, b, c = write_source(tmp_path, [])
    with p.open("ab") as f:
        f.write(raw)
    result = doctor(p)
    assert result["status"] == ("UNKNOWN" if fault == "partial" else "FAIL")
    assert result["authority_granted"] is False
    assert "SYNTHETIC" not in json.dumps(result)


def test_doctor_rechecks_current_source_and_never_writes(tmp_path, monkeypatch):
    import native_doctor as module

    p, b, c = write_source(tmp_path, [record("edited_text_file")])
    before = p.read_bytes()
    result = doctor(p)
    assert result["status"] == "PASS" and p.read_bytes() == before
    original = module.native.read_page

    def rewrite(*args, **kwargs):
        batch = original(*args, **kwargs)
        p.write_bytes(p.read_bytes().replace(b"UNTRUSTED", b"REWRITTEN", 1))
        return batch

    monkeypatch.setattr(module.native, "read_page", rewrite)
    result = doctor(p)
    assert result["status"] == "FAIL" and result["sample_decode"] == "FAIL"


def test_doctor_read_and_time_bounds_are_reported(tmp_path, monkeypatch):
    import native_doctor as module

    p, b, c = write_source(tmp_path, [record("edited_text_file") for _ in range(40)])
    real = module.native._open
    physical = 0
    largest = 0

    class Count:
        def __init__(self, fp):
            self.fp = fp

        def __getattr__(self, k):
            return getattr(self.fp, k)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.fp.__exit__(*args)

        def read(self, n=-1):
            nonlocal physical, largest
            assert 0 <= n <= 4 * 1024 * 1024
            value = self.fp.read(n)
            physical += len(value)
            largest = max(largest, n)
            return value

    def opened(*args, **kwargs):
        fp, st = real(*args, **kwargs)
        return Count(fp), st

    monkeypatch.setattr(module.native, "_open", opened)
    result = doctor(p, byte_budget=4096, max_pages=1)
    assert result["status"] == "PASS" and result["source_history_coverage"] == "UNKNOWN"
    assert result["pages"] <= 1 and physical < 100000
    assert result["physical_bytes_read"] >= physical
    assert largest <= 4097  # One byte witnesses the tail frame boundary.


def test_actual_cli_diagnoses_actor_source_and_returns_failure(world):
    p = world["transcript"]
    before = p.read_bytes()
    session = world["actor"]["native_payload"]["session_id"]
    row = record("edited_text_file", session)
    row["attachment"] = {"type": "environment", "snapshot": {}}
    with p.open("a") as f:
        f.write(json.dumps(row) + "\n")
    good = cli(world, "doctor")
    assert good.returncode == 0, good.stderr
    report = json.loads(good.stdout)
    assert report["native_source"]["records_checked"] > 0
    assert report["native_source"]["status"] == "PASS"
    with p.open("a") as f:
        f.write(json.dumps({"type": "future_control", "sessionId": session}) + "\n")
    expected = p.read_bytes()
    bad = cli(world, "doctor")
    assert bad.returncode != 0 and p.read_bytes() == expected
    report = json.loads(bad.stdout)
    assert report["status"] == "FAIL"
    assert report["native_source"]["first_gap"] > len(before)
    assert report["native_source"]["authority_granted"] is False


def test_cli_doctor_complete_tail_does_not_claim_whole_history(world):
    session = world["actor"]["native_payload"]["session_id"]
    with world["transcript"].open("a") as f:
        for _ in range(30):
            f.write(json.dumps(record("edited_text_file", session)) + "\n")
    result = cli(world, "doctor", "--native-byte-budget", "4096")
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["native_source"]["sample_decode"] == "PASS"
    assert report["native_source"]["source_history_coverage"] == "UNKNOWN"
    assert report["native_source"]["negative_coverage"] == "UNKNOWN"


def test_cli_actor_identity_is_checked_before_source_compatibility(world):
    world["actor"]["native_payload"][
        "session_id"
    ] = "00000000-0000-0000-0000-000000000000"
    result = cli(world, "doctor")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["native_source"]["status"] == "FAIL"


def test_complete_explicit_nonzero_interval_and_required_truncation(tmp_path):
    p, b, c = write_source(tmp_path, [record("edited_text_file") for _ in range(20)])
    start = b["header_length"]
    complete = doctor(p, start_offset=start)
    assert complete["status"] == "PASS"
    assert complete["requested_interval_coverage"] == "COMPLETE"
    assert complete["source_history_coverage"] == "UNKNOWN"
    partial = doctor(p, start_offset=start, byte_budget=4096)
    assert partial["status"] == "UNKNOWN"
    assert partial["requested_interval_coverage"] == "INCOMPLETE"


def test_append_after_frozen_interval_does_not_invalidate_checked_bytes(
    tmp_path, monkeypatch
):
    import native_doctor as module

    p, b, c = write_source(tmp_path, [record("edited_text_file")])
    frozen = p.stat().st_size
    original = module.native.read_page

    def append_after_read(*args, **kwargs):
        batch = original(*args, **kwargs)
        with p.open("ab") as f:
            f.write(b'{"type":"future_control"}\n')
        return batch

    monkeypatch.setattr(module.native, "read_page", append_after_read)
    report = doctor(p)
    assert report["status"] == "PASS" and report["bounds"]["end"] == frozen
    assert report["bounds"]["appended_after_snapshot_bytes"] > 0
    assert report["source_history_coverage"] == "UNKNOWN"
    assert report["negative_coverage"] == "UNKNOWN"
    monkeypatch.setattr(module.native, "read_page", original)
    assert doctor(p)["status"] == "FAIL"


def test_doctor_physical_ceiling_is_enforced_before_reads(tmp_path, monkeypatch):
    import native_doctor as module

    p, b, c = write_source(tmp_path, [record("edited_text_file")])

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "read_page must not begin without its physical reservation"
        )

    monkeypatch.setattr(module.native, "read_page", forbidden)
    result = doctor(p, physical_byte_budget=1000)
    assert result["status"] == "UNKNOWN"
    assert result["physical_bytes_reserved"] <= 1000
    assert result["physical_bytes_read"] == 0
    assert any(x["code"] == "physical_read_bound" for x in result["diagnostics"])


def test_long_source_default_window_has_scoped_success(tmp_path):
    rows = [record("edited_text_file", body="x" * 80000) for _ in range(40)]
    p, b, c = write_source(tmp_path, rows)
    assert p.stat().st_size > 4 * 1024 * 1024
    report = doctor(p)
    assert report["status"] == "PASS" and report["records_checked"] > 0
    assert report["bounds"]["start"] > 0
    assert report["bounds"]["end"] - report["bounds"]["start"] <= 4 * 1024 * 1024
    assert report["source_history_coverage"] == "UNKNOWN"
    assert (
        report["physical_bytes_read"]
        <= report["physical_bytes_reserved"]
        <= report["limits"]["physical_read_bytes"]
    )


def test_final_header_rewrite_invalidates_tail_qualification(tmp_path, monkeypatch):
    import native_doctor as module

    p, b, c = write_source(tmp_path, [record("edited_text_file") for _ in range(20)])
    original = module.native.read_page

    def change_header(*args, **kwargs):
        batch = original(*args, **kwargs)
        p.write_bytes(p.read_bytes().replace(b"synthetic-root", b"synthetic-other", 1))
        return batch

    monkeypatch.setattr(module.native, "read_page", change_header)
    assert doctor(p, byte_budget=4096)["status"] == "FAIL"


@pytest.mark.parametrize(
    "client,implicit", [("codex", False), ("muse", False), ("muse", True)]
)
def test_other_native_client_cli_doctor_retains_behavior_without_claude_attestation(
    world, monkeypatch, client, implicit
):
    session = world["actor"]["native_payload"]["session_id"]
    root = world["scratch"] / ("fixture-" + client)
    if client == "codex":
        source = root / "sessions" / "synthetic.jsonl"
        row = {
            "type": "session_meta",
            "payload": {"id": session, "session_id": session},
        }
        monkeypatch.setenv("CODEX_HOME", str(root))
    else:
        source = root / "2026" / "01" / "01" / session / "session.jsonl"
        row = {"stream": {"id": session}}
        monkeypatch.setenv("MUSE_SESSIONS_DIR", str(root))
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(row) + "\n")
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", client + ":" + session)
    if implicit:
        world["actor"]["native_payload"].pop("transcript_path")
    else:
        world["actor"]["native_payload"]["transcript_path"] = str(source)
    result = cli(world, "doctor")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["native_source"]["status"] == "NOT_APPLICABLE"
    assert report["native_source"]["client"] == client
    assert report["native_source"]["authority_granted"] is False
    assert "UNKNOWN" in report["native_acceptance"]

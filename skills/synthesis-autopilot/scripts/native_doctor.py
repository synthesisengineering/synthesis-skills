"""Read-only compatibility diagnosis of bounded current native transcript bytes.

This never enrolls an owner, changes a journal, consumes instructions, counts
usage or issues authority. A successfully decoded tail certifies only its stated
diagnostic window; omitted history and negative authority coverage remain UNKNOWN.
All output is counts, bounds and parser diagnostics.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import time

import native_observations as native


MAX_BYTES = 16 * 1024 * 1024
MAX_PAGES = 64
MAX_SECONDS = 15
MAX_PHYSICAL_BYTES = 512 * 1024 * 1024


def inspect_source(
    path,
    *,
    client,
    expected_root_session_id,
    start_offset=None,
    byte_budget=4 * 1024 * 1024,
    max_pages=32,
    max_seconds=10,
    physical_byte_budget=None,
):
    for value, maximum, label in (
        (byte_budget, MAX_BYTES, "byte budget"),
        (max_pages, MAX_PAGES, "page budget"),
        (max_seconds, MAX_SECONDS, "time budget"),
    ):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError("invalid native doctor " + label)
    if start_offset is not None and (type(start_offset) is not int or start_offset < 0):
        raise ValueError("invalid native doctor start offset")
    if physical_byte_budget is None:
        physical_byte_budget = 16 * byte_budget + 4 * native.MAX_RECORD_READBACK_BYTES
    if (
        type(physical_byte_budget) is not int
        or not 1 <= physical_byte_budget <= MAX_PHYSICAL_BYTES
    ):
        raise ValueError("invalid native doctor physical read budget")
    began = time.monotonic()
    report = {
        "status": "UNKNOWN",
        "sample_decode": "UNKNOWN",
        "scope": "bounded current source compatibility diagnosis; not owner admission",
        "authority_granted": False,
        "effects_replayed": False,
        "usage_counted": False,
        "negative_coverage": "UNKNOWN",
        "pre_enrollment": "UNKNOWN",
        "records_checked": 0,
        "event_kinds": {},
        "gap_count": 0,
        "first_gap": None,
        "diagnostics": [],
        "pages": 0,
        "physical_bytes_read": 0,
        "physical_bytes_reserved": 0,
        "physical_accounting": "completed reads counted; each operation reserves its worst-case reads before I/O",
        "source_history_coverage": "UNKNOWN",
        "requested_interval_coverage": "INCOMPLETE",
        "bounds": None,
        "limits": {
            "logical_source_bytes": byte_budget,
            "physical_read_bytes": physical_byte_budget,
            "pages": max_pages,
            "seconds": max_seconds,
        },
        "atomic_snapshot": False,
    }

    def reserve(count):
        if report["physical_bytes_reserved"] + count > physical_byte_budget:
            report["diagnostics"].append({"code": "physical_read_bound"})
            return False
        report["physical_bytes_reserved"] += count
        return True

    try:
        if client != "claude":
            report["status"] = report["sample_decode"] = "NOT_APPLICABLE"
            report["diagnostics"].append({"code": "claude_source_diagnostic_only"})
            return report
        path = Path(path)
        stream, info = native._open(path)
        with stream:
            end = info.st_size
            begin = max(0, end - byte_budget) if start_offset is None else start_offset
            if begin > end:
                raise ValueError("native doctor start exceeds source")
            target = min(end, begin + byte_budget)
            required_end = end
            # Find a genuine frame boundary in a finite tail window. Scanning
            # zero bytes at an EOF enrollment is deliberately UNKNOWN.
            if start_offset is None and begin:
                if not reserve(2 * (target - begin + 1)):
                    return report
                raw = native._stable_read(
                    stream,
                    path,
                    begin - 1,
                    target - begin + 1,
                    (info.st_dev, info.st_ino),
                    end,
                )
                report["physical_bytes_read"] += 2 * len(raw)
                newline = raw.find(b"\n")
                begin = target if newline < 0 else begin + newline
                del raw
        report["bounds"] = {
            "start": begin,
            "end": target,
            "source_size": end,
            "required_end": required_end,
            "omitted_prefix_bytes": begin,
            "omitted_suffix_bytes": end - target,
            "appended_after_snapshot_bytes": 0,
        }
        # enroll_source reads at most one bounded header three times and a
        # two-read boundary witness. Reserve even reads on a failed operation.
        if not reserve(3 * (native.Limits().payload_bytes + 1) + 2):
            return report
        binding, cursor = native.enroll_source(
            path,
            client=client,
            expected_root_session_id=expected_root_session_id,
            mode="native",
            start_offset=begin,
        )
        # Include the bounded enrollment header reads and frame-boundary reads.
        report["physical_bytes_read"] += 3 * binding["header_length"] + (
            2 if begin else 0
        )
        if (binding["device"], binding["inode"]) != (info.st_dev, info.st_ino):
            raise ValueError("native doctor source rotated before diagnosis")
        report["adapter_version"] = binding["producer"]["adapter_version"]
        report["adapter_sha256"] = binding["producer"]["adapter_sha256"]
        report["normalizer_version"] = binding["producer"]["normalizer_version"]
        report["normalizer_sha256"] = binding["producer"]["normalizer_sha256"]
        report["source_generation"] = binding["generation"]
        kinds = Counter()
        ranges = []
        while cursor["offset"] < target and report["pages"] < max_pages:
            if time.monotonic() - began >= max_seconds:
                report["diagnostics"].append({"code": "diagnostic_time_bound"})
                break
            before = cursor["offset"]
            page_bytes = min(1024 * 1024, target - before)
            # Claude has no streaming command branch. This covers the two
            # page/header reads, pending-frame witness and the aggregate 1 MiB
            # current-record readback allowance, before the parser can read.
            physical_upper = 2 * (
                page_bytes
                + binding["header_length"]
                + native.Limits().payload_bytes
                + native.MAX_RECORD_READBACK_BYTES
            )
            if not reserve(physical_upper):
                break
            page = native.read_page(
                binding, cursor, limits=native.Limits(page_bytes=page_bytes)
            )
            report["pages"] += 1
            report["physical_bytes_read"] += page["bytes_read"]
            report["gap_count"] += len(page["gaps"])
            for gap in page["gaps"]:
                if report["first_gap"] is None:
                    report["first_gap"] = gap["offset"]
                if len(report["diagnostics"]) < 8:
                    # Details can contain producer-derived key names. Keep only
                    # the owner's stable code and byte location in this report.
                    report["diagnostics"].append(
                        {
                            "code": gap["code"],
                            "offset": gap["offset"],
                            "length": gap["length"],
                        }
                    )
            for diagnostic in page["diagnostics"]:
                if len(report["diagnostics"]) < 8:
                    report["diagnostics"].append({"code": diagnostic["code"]})
            cursor = page["cursor"]
            kinds.update(event["kind"] for event in page["events"])
            if page["consumed_range"]:
                ranges.append(page["consumed_range"])
            if page["diagnostics"] or cursor["offset"] == before:
                break
        report["records_checked"] = cursor["ordinal"]
        report["event_kinds"] = dict(kinds)
        report["bounds"]["checked_through"] = cursor["offset"]
        report["bounds"]["trusted_through"] = cursor["trusted_through"]
        # A final bounded readback binds the diagnostic to the exact bytes its
        # parser examined. Never use this diagnostic as an owner receipt.
        stream, fresh = native._open(path, binding)
        with stream:
            if not reserve(2 * binding["header_length"]):
                return report
            native._header(stream, binding, fresh.st_size)
            report["physical_bytes_read"] += 2 * binding["header_length"]
            for span in ranges:
                if time.monotonic() - began >= max_seconds:
                    report["diagnostics"].append({"code": "readback_time_bound"})
                    break
                if not reserve(2 * span["length"]):
                    break
                raw = native._stable_read(
                    stream,
                    path,
                    span["offset"],
                    span["length"],
                    (binding["device"], binding["inode"]),
                    end,
                )
                report["physical_bytes_read"] += 2 * len(raw)
                if native._sha(raw) != span["sha256"]:
                    raise ValueError("native doctor source changed during diagnosis")
            # Growth beyond the frozen interval does not invalidate its bytes.
            # It remains uninspected and supplies no current authority coverage.
            report["bounds"]["appended_after_snapshot_bytes"] = max(
                0, fresh.st_size - end
            )
            report["bounds"]["source_size_at_final_read"] = fresh.st_size
        failed = report["gap_count"] or any(
            d["code"] == "source_unavailable" for d in report["diagnostics"]
        )
        complete = (
            target == required_end
            and cursor["offset"] == target
            and cursor["frame_start"] == target
            and report["records_checked"] > 0
            and not report["diagnostics"]
        )
        report["sample_decode"] = (
            "FAIL" if failed else "PASS" if complete else "UNKNOWN"
        )
        report["status"] = "FAIL" if failed else "PASS" if complete else "UNKNOWN"
        if complete:
            report["requested_interval_coverage"] = "COMPLETE"
            if begin == 0 and not report["bounds"]["appended_after_snapshot_bytes"]:
                report["source_history_coverage"] = "COMPLETE_SNAPSHOT"
        if begin or report["bounds"]["appended_after_snapshot_bytes"]:
            report["coverage_note"] = (
                "Decoder success applies only to the stated frozen interval; omitted or appended history remains UNKNOWN."
            )
        if report["status"] == "UNKNOWN":
            report["diagnostics"].append(
                {
                    "code": "incomplete_source_coverage",
                    "action": "Required diagnostic interval is incomplete; inspect remaining bytes within an explicit finite budget.",
                }
            )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report["status"] = report["sample_decode"] = "FAIL"
        report["diagnostics"].append(
            {"code": "source_check_failed", "error_class": type(exc).__name__}
        )
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - began, 6)
    return report

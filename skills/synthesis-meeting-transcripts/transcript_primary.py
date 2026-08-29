#!/usr/bin/env python3
"""Fail closed when a derived note is presented as a primary transcript.

The source-grade classifier is diagnostic. ``authorize-attribution`` is the
enforcing boundary: it issues a receipt only when the artifact has dense,
complete raw provider-message records and the caller supplies an exact
message-level location belonging to one of those records.

Exit codes: 0 accepted, 1 refused, 2 input or invocation unverifiable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "0.9.0"

SLACK_PERMALINK_RE = re.compile(
    r"https://[A-Za-z0-9.-]+\.slack\.com/archives/[A-Z0-9]+/p(\d{16})(?!\d)"
)
PROVIDER_TIMESTAMP_RE = re.compile(r"\d{10}\.\d{6}")
PROVIDER_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?[\"']?(thread_ts|message_ts)[\"']?"
    r"(?:\*\*)?\s*[:=]\s*[`\"']?(\d{10}\.\d{6})[`\"']?\s*,?\s*$",
    re.IGNORECASE,
)
MESSAGE_BODY_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?[\"']?(?:text|body)[\"']?\s*[:=]\s*(.+?)\s*,?\s*$",
    re.IGNORECASE,
)

# AGENT HEURISTIC: the controlling plan requires raw-message structure and
# permalink density, but does not prescribe numeric thresholds or record-span
# bounds. A record must pair one message identifier with nearby message content;
# five distinct records at ten percent of substantive lines rejects the real
# 128-line summary shape and the reviewer's marker-only mutations while
# accepting the observed raw-export shape. Twelve lines accommodates bounded
# provider metadata without allowing a loose identifier elsewhere in the file
# to attach itself to a message. Receipts expose these values so R7 can
# challenge the judgment directly.
MIN_RAW_MESSAGE_RECORDS = 5
MIN_RAW_MESSAGE_RECORD_DENSITY = 0.10
MAX_RECORD_SPAN_LINES = 12

AUTHORITY = {
    "label": "agent-heuristic",
    "provenance_id": "agent-heuristic:r3-transcript-primary-record-density",
}
BASE_UNVERIFIED_REMAINDER = [
    "semantic fidelity of any paraphrase or quotation",
    "speaker identity beyond labels present in the artifact",
    "provider authenticity of the stored identifiers",
    "capture completeness outside the artifact's recorded bounds",
    "the receipt consumer's later use of the verified location",
]


class InputError(Exception):
    """The artifact could not be classified safely."""


def read_artifact(path_value: str) -> tuple[Path, bytes, str]:
    path = Path(path_value).expanduser()
    try:
        if path.is_symlink() or not path.is_file():
            raise InputError("artifact must be an existing nonsymlink regular file")
        payload = path.read_bytes()
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("artifact is not valid UTF-8") from exc
    except OSError as exc:
        raise InputError(f"artifact could not be read: {exc}") from exc
    return path.resolve(), payload, text


def permalink_timestamp(permalink: str) -> str:
    match = SLACK_PERMALINK_RE.fullmatch(permalink)
    if not match:  # pragma: no cover - callers supply regex matches
        raise ValueError("not a Slack message permalink")
    digits = match.group(1)
    return f"{digits[:10]}.{digits[10:]}"


def body_field_has_content(line: str) -> bool:
    match = MESSAGE_BODY_FIELD_RE.match(line)
    if not match:
        return False
    value = match.group(1).strip().strip("`\"'").strip()
    return bool(value and value.lower() not in {"null", "none", "[]", "{}"})


def prose_body_line(line: str) -> bool:
    """Whether a bounded Markdown line carries message content, not structure."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", "<!--")):
        return False
    if SLACK_PERMALINK_RE.search(line) or PROVIDER_FIELD_RE.match(line):
        return False
    if re.match(
        r"^\*\*(?:artifact type|capture bounds|content|author|sender|channel|permalink)"
        r"\*\*\s*:",
        stripped,
        re.IGNORECASE,
    ):
        return False
    return True


def marker_inventory(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    permalinks: set[str] = set()
    message_ts: set[str] = set()
    thread_ts: set[str] = set()
    marker_line_numbers: set[int] = set()
    substantive_line_count = 0
    permalink_occurrences: list[tuple[int, str]] = []
    message_field_occurrences: list[tuple[int, str]] = []

    for line_index, line in enumerate(lines):
        line_number = line_index + 1
        if line.strip():
            substantive_line_count += 1
        line_permalink_matches = list(SLACK_PERMALINK_RE.finditer(line))
        if line_permalink_matches:
            for match in line_permalink_matches:
                permalink = match.group(0)
                permalinks.add(permalink)
                permalink_occurrences.append((line_index, permalink))
            marker_line_numbers.add(line_number)
        field = PROVIDER_FIELD_RE.match(line)
        if field:
            name, value = field.groups()
            target = message_ts if name.lower() == "message_ts" else thread_ts
            target.add(value)
            marker_line_numbers.add(line_number)
            if name.lower() == "message_ts":
                message_field_occurrences.append((line_index, value))

    raw_records: dict[str, dict[str, Any]] = {}
    record_permalinks: set[str] = set()
    record_message_ts: set[str] = set()
    consumed_message_field_lines: set[int] = set()
    identifier_mismatches: set[tuple[str, str]] = set()

    # A permalink record is complete only when nearby bounded content exists.
    # The first message_ts after its anchor is the record's provider field;
    # later loose fields are inventory, not part of the record.
    for occurrence_index, (line_index, permalink) in enumerate(permalink_occurrences):
        next_anchor = (
            permalink_occurrences[occurrence_index + 1][0]
            if occurrence_index + 1 < len(permalink_occurrences)
            else len(lines)
        )
        stop = min(next_anchor, line_index + 1 + MAX_RECORD_SPAN_LINES)
        canonical = permalink_timestamp(permalink)
        associated_field: tuple[int, str] | None = None
        has_body = False
        for candidate_index in range(line_index + 1, stop):
            field = PROVIDER_FIELD_RE.match(lines[candidate_index])
            if field and field.group(1).lower() == "message_ts" and associated_field is None:
                associated_field = (candidate_index, field.group(2))
                continue
            if prose_body_line(lines[candidate_index]):
                has_body = True
                break
        if not has_body:
            continue
        record_permalinks.add(permalink)
        if associated_field:
            field_index, field_value = associated_field
            consumed_message_field_lines.add(field_index)
            record_message_ts.add(field_value)
            if field_value != canonical:
                identifier_mismatches.add((canonical, field_value))
        raw_records[canonical] = {
            "kind": "permalink-record",
            "permalink": permalink,
            "message_ts": associated_field[1] if associated_field else None,
        }

    # Provider exports without permalinks can still establish a record, but a
    # bare message_ts is insufficient: an explicit text/body field must occur
    # in the same bounded record before the next identifier.
    for occurrence_index, (line_index, timestamp) in enumerate(message_field_occurrences):
        if line_index in consumed_message_field_lines:
            continue
        later_message_line = (
            message_field_occurrences[occurrence_index + 1][0]
            if occurrence_index + 1 < len(message_field_occurrences)
            else len(lines)
        )
        later_permalink_lines = [
            anchor_line
            for anchor_line, _ in permalink_occurrences
            if anchor_line > line_index
        ]
        next_anchor = min(later_permalink_lines) if later_permalink_lines else len(lines)
        stop = min(
            later_message_line,
            next_anchor,
            line_index + 1 + MAX_RECORD_SPAN_LINES,
        )
        if any(body_field_has_content(lines[index]) for index in range(line_index + 1, stop)):
            raw_records.setdefault(
                timestamp,
                {
                    "kind": "provider-field-record",
                    "permalink": None,
                    "message_ts": timestamp,
                },
            )
            record_message_ts.add(timestamp)

    # Slack permalink suffixes and message_ts encode the same identity.
    # raw_records is keyed by that canonical identity so presenting both forms
    # never doubles the record count.
    message_locations = {f"slack-message:{value}" for value in raw_records}
    marker_line_density = (
        len(marker_line_numbers) / substantive_line_count
        if substantive_line_count
        else 0.0
    )
    raw_message_record_density = (
        len(raw_records) / substantive_line_count
        if substantive_line_count
        else 0.0
    )
    eligible = (
        len(raw_records) >= MIN_RAW_MESSAGE_RECORDS
        and raw_message_record_density >= MIN_RAW_MESSAGE_RECORD_DENSITY
        and not identifier_mismatches
    )
    return {
        "permalinks": sorted(permalinks),
        "message_ts": sorted(message_ts),
        "thread_ts": sorted(thread_ts),
        "record_permalinks": sorted(record_permalinks),
        "record_message_ts": sorted(record_message_ts),
        "message_locations": sorted(message_locations),
        "marker_line_count": len(marker_line_numbers),
        "substantive_line_count": substantive_line_count,
        "marker_line_density": round(marker_line_density, 6),
        "raw_message_record_count": len(raw_records),
        "raw_message_record_density": round(raw_message_record_density, 6),
        "identifier_mismatch_count": len(identifier_mismatches),
        "minimum_raw_message_records": MIN_RAW_MESSAGE_RECORDS,
        "minimum_raw_message_record_density": MIN_RAW_MESSAGE_RECORD_DENSITY,
        "maximum_record_span_lines": MAX_RECORD_SPAN_LINES,
        "eligible": eligible,
    }


def base_result(path: Path, payload: bytes, inventory: dict[str, Any]) -> dict[str, Any]:
    eligible = bool(inventory["eligible"])
    return {
        "schema_version": 1,
        "script_version": SCRIPT_VERSION,
        "authority": AUTHORITY,
        "artifact": str(path),
        "input_sha256": hashlib.sha256(payload).hexdigest(),
        "source_class": "verbatim" if eligible else "derived",
        "primary_source_eligible": eligible,
        "evidence": {
            "permalink_count": len(inventory["permalinks"]),
            "message_ts_count": len(inventory["message_ts"]),
            "thread_ts_count": len(inventory["thread_ts"]),
            "distinct_message_location_count": len(inventory["message_locations"]),
            "marker_line_count": inventory["marker_line_count"],
            "substantive_line_count": inventory["substantive_line_count"],
            "marker_line_density": inventory["marker_line_density"],
            "raw_message_record_count": inventory["raw_message_record_count"],
            "raw_message_record_density": inventory["raw_message_record_density"],
            "identifier_mismatch_count": inventory["identifier_mismatch_count"],
            "minimum_raw_message_records": inventory["minimum_raw_message_records"],
            "minimum_raw_message_record_density": inventory[
                "minimum_raw_message_record_density"
            ],
            "maximum_record_span_lines": inventory["maximum_record_span_lines"],
        },
        "unverified_remainder": list(BASE_UNVERIFIED_REMAINDER),
    }


def classify(path_value: str) -> tuple[int, dict[str, Any]]:
    path, payload, text = read_artifact(path_value)
    inventory = marker_inventory(text)
    result = base_result(path, payload, inventory)
    result.update(
        {
            "control_class": "diagnostic",
            "issues_authority_receipt": False,
            "enforcement_outcome": (
                "classified-verbatim" if inventory["eligible"] else "classified-derived"
            ),
        }
    )
    return (0 if inventory["eligible"] else 1), result


def resolve_location(location: str, inventory: dict[str, Any]) -> tuple[bool, str]:
    if not location:
        return False, "refused-missing-location"
    kind, separator, value = location.partition(":")
    if not separator or not value:
        return False, "refused-malformed-location"
    if kind == "thread_ts":
        return False, "refused-thread-location-not-message-granular"
    if kind == "message_ts":
        if not PROVIDER_TIMESTAMP_RE.fullmatch(value):
            return False, "refused-malformed-location"
        resolved = value in inventory["record_message_ts"]
    elif kind == "permalink":
        if not SLACK_PERMALINK_RE.fullmatch(value):
            return False, "refused-malformed-location"
        resolved = value in inventory["record_permalinks"]
    else:
        return False, "refused-unsupported-location-kind"
    return resolved, (
        "authorized-attribution-location" if resolved else "refused-unresolved-location"
    )


def authorize_attribution(
    path_value: str, location: str | None
) -> tuple[int, dict[str, Any]]:
    path, payload, text = read_artifact(path_value)
    inventory = marker_inventory(text)
    result = base_result(path, payload, inventory)
    result.update(
        {
            "control_class": "enforced-gate",
            "issues_authority_receipt": False,
        }
    )

    if not inventory["eligible"]:
        result["enforcement_outcome"] = "refused-derived-source"
        result["unverified_remainder"].append(
            "primary-source eligibility for this artifact"
        )
        return 1, result

    resolved, outcome = resolve_location(location or "", inventory)
    result["enforcement_outcome"] = outcome
    if not resolved:
        result["unverified_remainder"].append(
            "a message-level location for the attribution-bearing claim"
        )
        return 1, result

    receipt_body = {
        "schema_version": 1,
        "control": "synthesis-meeting-transcripts:transcript-primary",
        "control_version": SCRIPT_VERSION,
        "input_path": str(path),
        "input_sha256": result["input_sha256"],
        "location": location,
        "source_class": result["source_class"],
        "raw_message_record_count": inventory["raw_message_record_count"],
        "raw_message_record_density": inventory["raw_message_record_density"],
        "minimum_raw_message_records": inventory["minimum_raw_message_records"],
        "minimum_raw_message_record_density": inventory[
            "minimum_raw_message_record_density"
        ],
        "expires_on": "any input-byte change",
    }
    receipt_id = hashlib.sha256(
        json.dumps(receipt_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result["issues_authority_receipt"] = True
    result["receipt"] = {**receipt_body, "receipt_id": receipt_id}
    return 0, result


def error_result(message: str, command: str | None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "script_version": SCRIPT_VERSION,
        "control_class": (
            "enforced-gate" if command == "authorize-attribution" else "diagnostic"
        ),
        "authority": AUTHORITY,
        "issues_authority_receipt": False,
        "enforcement_outcome": "unverifiable-input",
        "error": message,
        "unverified_remainder": [
            "all source-grade and attribution checks because the input was unverifiable"
        ],
    }


def emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    outcome = result.get("enforcement_outcome", "unverifiable-input")
    print(f"Transcript-primary {outcome}: {result.get('artifact', '<unreadable>')}")
    if "source_class" in result:
        evidence = result["evidence"]
        print(
            "Source class: "
            f"{result['source_class']} — {evidence['raw_message_record_count']} "
            "complete raw-message record(s), record density "
            f"{evidence['raw_message_record_density']:.3f}, identifier mismatches "
            f"{evidence['identifier_mismatch_count']}"
        )
    if result.get("issues_authority_receipt"):
        print(f"Receipt: {result['receipt']['receipt_id']}")
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
    print("Unverified remainder:")
    for item in result["unverified_remainder"]:
        print(f"- {item}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    root.add_argument("--version", action="version", version=SCRIPT_VERSION)
    commands = root.add_subparsers(dest="command", required=True)

    classify_parser = commands.add_parser(
        "classify", help="classify an artifact's primary-source eligibility"
    )
    classify_parser.add_argument("artifact")
    classify_parser.add_argument("--json", action="store_true")

    authorize_parser = commands.add_parser(
        "authorize-attribution",
        help="require primary source grade and an exact message-level location",
    )
    authorize_parser.add_argument("artifact")
    authorize_parser.add_argument("--location")
    authorize_parser.add_argument("--json", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "classify":
            code, result = classify(args.artifact)
        else:
            code, result = authorize_attribution(args.artifact, args.location)
    except InputError as exc:
        code = 2
        result = error_result(str(exc), args.command)
    emit(result, args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

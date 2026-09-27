"""Validate bounded acquisition captures before advancing the existing watermark.

This verifies recorded observations and exact archive bytes, not provider honesty,
account authorization, or undiscovered sources. Acquisition adapters must retain raw
responses and their tool-call references; unknown enumeration always stays unknown.
No provider call, archive write, policy activation, or lifecycle owner lives here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re

MAX_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 10000
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024


def read_bytes(path: Path, *, root: Path | None = None) -> bytes:
    # Use the reviewed ritual evidence owner for descriptor-relative no-follow
    # traversal, ownership/mode checks and post-read identity verification.
    path = Path(path)
    if ".." in path.parts:
        raise ValueError("archive path traversal")
    path = Path(os.path.abspath(path))
    if root is not None:
        root = Path(os.path.abspath(root))
        if path == root or not path.is_relative_to(root):
            raise ValueError("archive path is outside its declared root")
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ritual_workers import read_regular

    return read_regular(path, MAX_BYTES)


def read_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("duplicate evidence key")
            result[k] = v
        return result

    try:
        return json.loads(read_bytes(Path(path)), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("acquisition evidence is unreadable or malformed") from exc


def moment(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("naive time")
        return result
    except (TypeError, ValueError) as exc:
        raise ValueError("acquisition timestamps require ISO-8601 offsets") from exc


def items(value, label):
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise ValueError(f"{label} must be a bounded list")
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label} must be nonempty text")
    return value


def observed(record, after, now):
    text(record.get("tool_call_id"), "tool_call_id")
    at = moment(record.get("observed_at"))
    if not after <= at <= now:
        raise ValueError("observation does not cover the current acquisition window")


def complete(record, after, now):
    observed(record, after, now)
    if record.get("complete") is not True or record.get("next_cursor") not in (
        None,
        "",
    ):
        raise ValueError("acquisition coverage is unknown: pagination is incomplete")


def validate_recorder_control(control, *, source, account, after, now):
    if not isinstance(control, dict) or control.get("observed") is not True:
        raise ValueError("recorder positive control was not observed")
    if control.get("source") != source or control.get("account") != account:
        raise ValueError("recorder positive control belongs to another source or account")
    text(control.get("source_id"), "positive control source_id")
    observed(control, after, now)
    return control


def header_id(body):
    found = re.findall(r"^\*\*Source ID:\*\* ([^\s:]+):([^\s]+)\s*$", body[:8192], re.M)
    if len(found) != 1:
        raise ValueError("archive header must carry exactly one provider:source ID")
    return found[0]


def archives(evidence):
    root = Path(text(evidence.get("archive_root"), "archive_root"))
    if not root.is_absolute():
        raise ValueError("archive_root must be absolute")
    result = {}
    total = 0
    for entry in items(evidence.get("archives"), "archives"):
        path = Path(text(entry.get("path"), "archive path"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("archive path must be root-relative")
        key = path.as_posix()
        if key in result:
            raise ValueError("duplicate archive path")
        payload = read_bytes(root / path, root=root)
        total += len(payload)
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("aggregate archive bytes exceeded")
        if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
            raise ValueError("archive bytes differ from saved-file receipt")
        result[key] = payload.decode("utf-8")
    return result


def meeting_coverage(e, start, through, now, saved):
    sources = items(e.get("sources"), "sources")
    declared = items(e.get("declared_sources"), "declared_sources")
    if not declared or len(set(declared)) != len(declared):
        raise ValueError("a unique declared recorder source set is required")
    by_source = {}
    for source in sources:
        source_id = text(source.get("id"), "source id")
        if source_id in by_source:
            raise ValueError("duplicate recorder source")
        by_source[source_id] = source
    if set(by_source) != set(declared):
        raise ValueError("declared recorder source is missing or foreign")
    documents = set()
    for sid, source in by_source.items():
        probe = source.get("readiness", {})
        observed(probe, start, now)
        if now - moment(probe["observed_at"]) > timedelta(hours=24):
            raise ValueError("recorder sign-in observation is stale")
        if probe.get("status") != "authenticated" or text(
            source.get("account"), "account"
        ) != probe.get("account"):
            raise ValueError(
                "recorder sign-in is unavailable, unknown, or for another account"
            )
        listing = source.get("inventory", {})
        complete(listing, through, now)
        if (
            moment(listing.get("from")) > start
            or moment(listing.get("through")) < through
        ):
            raise ValueError("source inventory does not cover the declared window")
        control = listing.get("positive_control", {})
        validate_recorder_control(control, source=sid, account=source["account"], after=through, now=now)
        for doc in items(listing.get("documents"), "documents"):
            key = (sid, text(doc.get("source_id"), "document source_id"))
            at = moment(doc.get("occurred_at"))
            if not start <= at <= through:
                raise ValueError("document is outside the declared acquisition window")
            if key in documents:
                raise ValueError("duplicate source document")
            documents.add(key)
    archived = {}
    for path, body in saved.items():
        key = header_id(body)
        if key in archived:
            raise ValueError("duplicate archived source ID")
        if key not in documents:
            raise ValueError("archive source ID is absent from declared inventory")
        import importlib.util

        verifier_path = (
            Path(__file__).resolve().parents[2]
            / "synthesis-meeting-transcripts/verify_transcripts.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_acquisition_transcript_verifier", verifier_path
        )
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        if not verifier.content_complete(body):
            raise ValueError("archived meeting lacks a complete transcript diagnostic")
        archived[key] = path
    gaps = documents - archived.keys()
    decisions = {}
    for decision in items(e.get("gap_decisions", []), "gap decisions"):
        key = (
            text(decision.get("source"), "decision source"),
            text(decision.get("source_id"), "decision source_id"),
        )
        if key not in gaps or key in decisions:
            raise ValueError("gap decision must name exactly one actual missing source")
        text(decision.get("reason"), "gap decision reason")
        text(decision.get("evidence_ref"), "gap decision evidence_ref")
        if decision.get("disposition") not in (
            "retry",
            "authentication-required",
            "source-unavailable",
            "operator-review",
        ):
            raise ValueError(
                "unsupported gap decision; decisions do not manufacture coverage"
            )
        decisions[key] = decision
    return {
        "declared_documents": len(documents),
        "archived_documents": len(archived),
        "gaps": [
            {"source": s, "source_id": i, "decision": decisions.get((s, i))}
            for s, i in sorted(gaps)
        ],
        "coverage": "gapped" if gaps else "complete",
        "can_advance": not gaps,
    }


def slack_ts(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d{9}\.\d{6}", value):
        raise ValueError("invalid Slack timestamp")
    return Decimal(value)


def slack_coverage(e, start, through, now, saved, targets):
    declared = items(e.get("declared_targets"), "declared_targets")
    if (
        not declared
        or len(set(declared)) != len(declared)
        or set(declared) != set(targets)
    ):
        raise ValueError(
            "Slack acquisition targets must equal the exact advance targets"
        )
    channels = items(e.get("channels"), "channels")
    if len(channels) != len(declared) or {c.get("id") for c in channels} != set(
        declared
    ):
        raise ValueError(
            "Slack channel observations are missing, duplicated or foreign"
        )
    lo, hi = Decimal(str(start.timestamp())), Decimal(str(through.timestamp()))
    captured = set()
    for body in saved.values():
        for channel, ts in re.findall(
            r"^\*\*Message ID:\*\* ([A-Z0-9]+):([1-9]\d{9}\.\d{6})\s*$", body, re.M
        ):
            captured.add((channel, ts))
    required = set()
    checked_threads = 0
    for channel in channels:
        cid = text(channel.get("id"), "channel id")
        history = channel.get("history", {})
        complete(history, through, now)
        if history.get("detail") != "detailed":
            raise ValueError("Slack acquisition requires detailed channel reads")
        if (
            moment(history.get("from")) > start
            or moment(history.get("through")) < through
        ):
            raise ValueError("channel history window is incomplete")
        parents = set(items(channel.get("known_thread_ids", []), "known thread ids"))
        messages = items(history.get("messages"), "history messages")
        for message in messages:
            ts = text(message.get("ts"), "message ts")
            at = slack_ts(ts)
            if lo <= at <= hi:
                required.add((cid, ts))
            if message.get("reply_count", 0):
                parents.add(ts)
        search = channel.get("reply_search", {})
        complete(search, through, now)
        if (
            moment(search.get("from")) > start
            or moment(search.get("through")) < through
        ):
            raise ValueError("thread discovery search window is incomplete")
        hits = items(search.get("messages"), "reply search messages")
        controls = items(search.get("positive_control_ids"), "positive control ids")
        # A positive control is an actual returned, in-window message, never a
        # success boolean or a historical/out-of-window record.
        in_window = set()
        for hit in hits:
            ts = text(hit.get("ts"), "search message ts")
            at = slack_ts(ts)
            if lo <= at <= hi:
                in_window.add(ts)
                required.add((cid, ts))
                if hit.get("thread_ts"):
                    parents.add(hit["thread_ts"])
        if not controls or not set(controls) <= in_window:
            raise ValueError("Slack coverage is unknown: no in-window positive control")
        threads = items(channel.get("threads"), "threads")
        indexed = {t.get("parent_ts"): t for t in threads}
        if len(indexed) != len(threads) or set(indexed) != parents:
            raise ValueError(
                "full thread pass does not cover every discovered and known parent"
            )
        for parent, thread in indexed.items():
            slack_ts(parent)
            complete(thread, through, now)
            if thread.get("oldest") is not None:
                raise ValueError("thread pass must not use oldest")
            rows = items(thread.get("messages"), "thread messages")
            row_ids = [text(m.get("ts"), "thread message ts") for m in rows]
            if parent not in row_ids or len(set(row_ids)) != len(row_ids):
                raise ValueError(
                    "thread response lacks its parent or has duplicate messages"
                )
            for ts in row_ids:
                if lo <= slack_ts(ts) <= hi:
                    required.add((cid, ts))
            for hit in hits:
                if hit.get("thread_ts") == parent and hit["ts"] not in row_ids:
                    raise ValueError("thread pass omitted a discovered in-window reply")
            checked_threads += 1
    missing = required - captured
    return {
        "coverage": "gapped" if missing else "complete",
        "can_advance": not missing,
        "checked_threads": checked_threads,
        "required_messages": len(required),
        "gaps": [{"channel": c, "ts": t} for c, t in sorted(missing)],
    }


def validate(
    evidence, *, workspace, surface, through, previous=None, now=None, targets=()
):
    now = now or datetime.now().astimezone()
    if not isinstance(evidence, dict) or type(evidence.get("schema")) is not int or evidence["schema"] != 1:
        raise ValueError("unsupported acquisition evidence schema")
    if evidence.get("workspace") != workspace or evidence.get("surface") != surface:
        raise ValueError("acquisition evidence belongs to another workspace or surface")
    start = moment(evidence.get("from"))
    end = moment(evidence.get("through"))
    if start > end or end != through or end > now:
        raise ValueError("acquisition evidence window does not match the watermark")
    if previous is not None and start > previous:
        raise ValueError(
            "acquisition evidence leaves a gap after the previous watermark"
        )
    saved = archives(evidence)
    if surface == "meetings":
        result = meeting_coverage(evidence, start, end, now, saved)
    elif surface == "slack":
        result = slack_coverage(evidence, start, end, now, saved, targets)
    else:
        raise ValueError("unsupported acquisition surface")
    return {
        **result,
        "workspace": workspace,
        "surface": surface,
        "from": start.isoformat(),
        "through": end.isoformat(),
        "unverified": [
            "provider authenticity",
            "undeclared source coverage",
            "semantic fidelity",
        ],
        "native_acceptance": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("evidence")
    p.add_argument("--workspace", required=True)
    p.add_argument("--surface", choices=["meetings", "slack"], required=True)
    p.add_argument("--through", required=True)
    p.add_argument("--target", action="append", default=[])
    a = p.parse_args(argv)
    try:
        result = validate(
            read_json(a.evidence),
            workspace=a.workspace,
            surface=a.surface,
            through=moment(a.through),
            targets=a.target,
        )
    except (
        ValueError,
        OSError,
        UnicodeError,
        TypeError,
        KeyError,
        AttributeError,
    ) as exc:
        print(
            json.dumps(
                {"coverage": "unknown", "can_advance": False, "reason": str(exc)}
            )
        )
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["can_advance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

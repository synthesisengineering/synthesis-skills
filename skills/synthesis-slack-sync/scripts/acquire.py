#!/usr/bin/env python3
"""Acquire declared Slack reads, preserve exact raw bodies and advance after readback."""

from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "synthesis-daily-rituals/scripts"))
import connector_replay  # noqa: E402 -- source-relative standalone entry dependencies
import preflight  # noqa: E402 -- source-relative standalone entry dependencies
import slack_workspaces  # noqa: E402 -- source-relative standalone entry dependencies
import thread_checker  # noqa: E402 -- source-relative standalone entry dependencies
from acquisition_evidence import moment, read_bytes, validate  # noqa: E402 -- source-relative standalone entry dependencies
from acquisition_transport import Capture, ReadTransport, output_path  # noqa: E402 -- source-relative standalone entry dependencies
from archive_publish import _publish, publish_json  # noqa: E402 -- source-relative standalone entry dependencies
from slack_read import SlackRead  # noqa: E402 -- source-relative standalone entry dependencies
import sync_watermark  # noqa: E402 -- source-relative standalone entry dependencies


def raw_records(channel):
    cid = channel["id"]
    # A connector's search renders message text differently from its history
    # and thread reads, so it marks search rows discovery-only; the thread read
    # each one leads to is what gets archived.
    all_rows = channel["history"]["messages"] + [
        row
        for row in channel["reply_search"]["messages"]
        if not row.get("discovery_only")
    ]
    for thread in channel["threads"]:
        all_rows += thread["messages"]
    indexed = {}
    for row in all_rows:
        ts = row.get("ts")
        if (
            not isinstance(ts, str)
            or not re.fullmatch(r"[1-9]\d{9}\.\d{6}", ts)
            or not isinstance(row.get("text"), str)
        ):
            raise ValueError("Slack raw body/timestamp unavailable")
        entries = indexed.setdefault(ts, [])
        for old in entries:
            if any(
                key in old and key in row and old[key] != row[key]
                for key in ("text", "user", "thread_ts")
            ):
                raise ValueError(
                    "conflicting same-ID Slack content; preserve raw captures and reacquire"
                )
        if row not in entries:
            entries.append(row)
    return cid, indexed


def render_payload(payload):
    """Deterministic reversible raw codec, retaining IDs, content and metadata."""
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "domain", "channels"}
        or type(payload["schema"]) is not int
        or payload["schema"] != 1
        or not isinstance(payload["channels"], dict)
    ):
        raise ValueError("unknown Slack raw archive schema")
    domain = payload["domain"]
    if domain is not None and (
        not isinstance(domain, str)
        or not re.fullmatch(r"[a-z0-9-]+\.slack\.com", domain)
    ):
        raise ValueError("invalid archived Slack domain")
    lines = ["# Slack raw acquisition", ""]
    for cid, indexed in sorted(payload["channels"].items()):
        if (
            not isinstance(cid, str)
            or not re.fullmatch(r"[CGD][A-Z0-9]+", cid)
            or not isinstance(indexed, dict)
        ):
            raise ValueError("invalid archived Slack channel")
        lines += [f"## #channel ({cid})", ""]
        for ts, variants in sorted(indexed.items()):
            if (
                not isinstance(ts, str)
                or not re.fullmatch(r"[1-9]\d{9}\.\d{6}", ts)
                or not isinstance(variants, list)
                or not variants
            ):
                raise ValueError("invalid archived Slack message")
            parents = set()
            for variant in variants:
                if (
                    not isinstance(variant, dict)
                    or variant.get("ts") != ts
                    or not isinstance(variant.get("text"), str)
                ):
                    raise ValueError("invalid archived Slack message body")
                if "channel" in variant:
                    observed = variant["channel"]
                    observed = (
                        observed.get("id") if isinstance(observed, dict) else observed
                    )
                    if observed != cid:
                        raise ValueError(
                            "archived message belongs to another conversation"
                        )
                if "thread_ts" in variant:
                    if not isinstance(variant["thread_ts"], str) or not re.fullmatch(
                        r"[1-9]\d{9}\.\d{6}", variant["thread_ts"]
                    ):
                        raise ValueError("invalid archived Slack parent identity")
                    parents.add(variant["thread_ts"])
                if any(
                    key in variants[0]
                    and key in variant
                    and variants[0][key] != variant[key]
                    for key in ("text", "user", "thread_ts")
                ):
                    raise ValueError("conflicting archived same-ID variants")
            if len(parents) > 1:
                raise ValueError("conflicting archived parent identity")
            row = variants[0]
            parent = next(iter(parents), ts)
            label = (
                f"#### Message (TS: {ts})"
                if parent == ts
                else f"- Reply (TS: {ts}) to {parent}"
            )
            if domain:
                label += f" [message](https://{domain}/archives/{cid}/p{ts.replace('.', '')})"
            text = row["text"]
            fence = "`" * max(
                3, 1 + max((len(x) for x in re.findall(r"`+", text)), default=0)
            )
            lines += [
                label,
                f"**Message ID:** {cid}:{ts}",
                f"**User ID:** {row.get('user', 'UNKNOWN')}",
                f"**Parent ID:** {cid}:{parent}",
                "",
                fence + "text",
                text,
                fence,
                "",
            ]
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    lines += [
        "<!-- synthesis-slack-raw-v1:" + base64.b64encode(raw).decode() + " -->",
        "",
    ]
    return "\n".join(lines)


def parse_archive(data):
    from acquisition_transport import strict_json

    text = data.decode("utf-8")
    # Only the final codec footer is structural. The exact raw body may quote
    # this marker or arbitrary headings; canonical re-render binds everything.
    lines = text.splitlines()
    marker = (
        re.fullmatch(r"<!-- synthesis-slack-raw-v1:([A-Za-z0-9+/=]+) -->", lines[-1])
        if lines
        else None
    )
    if marker is None:
        raise ValueError(
            "existing archive is not acquisition-owned; preserve and reconcile its format before merging"
        )
    payload = strict_json(base64.b64decode(marker[1], validate=True))
    if render_payload(payload) != text:
        raise ValueError("existing Slack archive differs from its exact raw codec")
    return payload


def render(channel):
    cid, indexed = raw_records(channel)
    return render_payload({"schema": 1, "domain": None, "channels": {cid: indexed}})


def save_channel(path, channel, *, domain=None, force=False):
    return save_channels(path, [channel], domain=domain, force=force)


def save_channels(path, channels, *, domain=None, force=False):
    """Merge every conversation bound for one archive file, then publish once."""
    import os

    payload = {"schema": 1, "domain": domain, "channels": {}}
    expected = "ABSENT"
    exists = os.path.lexists(path)
    if exists:
        old = read_bytes(path)
        expected = hashlib.sha256(old).hexdigest()
        payload = parse_archive(old)
        if payload["domain"] != domain:
            raise ValueError("Slack archive belongs to a different declared workspace")
    for channel in channels:
        cid, indexed = raw_records(channel)
        current = payload["channels"].setdefault(cid, {})
        for ts, variants in indexed.items():
            if ts in current:
                # Repeated observations may add metadata, but conflicting bodies or
                # speaker/parent identities require explicit source reconciliation.
                for old in current[ts]:
                    for row in variants:
                        if any(
                            key in old and key in row and old[key] != row[key]
                            for key in ("text", "user", "thread_ts")
                        ):
                            raise ValueError("conflicting existing same-ID archive content")
                current[ts] += [row for row in variants if row not in current[ts]]
            else:
                current[ts] = variants
    body = render_payload(payload)

    def check(target, digest):
        data = read_bytes(target)
        if hashlib.sha256(data).hexdigest() != digest or data != body.encode():
            raise ValueError(
                "Slack archive differs from exact source-derived serialization"
            )
        parse_archive(data)
        return [{"status": "EXACT_RAW"}]

    # Only a validated owned codec can authorize an additive merge; the digest
    # is checked again under the existing publication lock before any effect.
    return _publish(
        path, body, validate=check, force=exists or force, expected_sha256=expected
    )


def known_threads(cfg, archive_root, targets):
    paths = cfg.get("known_archives", [])
    if not isinstance(paths, list) or len(paths) > 32:
        raise ValueError("known archives must be an explicit bounded list")
    result = {target: set() for target in targets}
    for name in paths:
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("known archive must be root relative")
        data = read_bytes(archive_root / rel, root=archive_root)
        if data.startswith(b"# Slack raw acquisition\n"):
            payload = parse_archive(data)
            for cid, indexed in payload["channels"].items():
                if cid not in result:
                    raise ValueError(
                        "known archive contains an undeclared conversation"
                    )
                for ts, variants in indexed.items():
                    parents = {
                        row["thread_ts"] for row in variants if "thread_ts" in row
                    }
                    result[cid].add(next(iter(parents), ts))
            continue
        if b"synthesis-slack-raw-v1:" in data:
            raise ValueError(
                "owned archive header or footer is malformed; no legacy fallback"
            )
        for thread in thread_checker.extract_threads(
            None, content=data.decode("utf-8"), strict=True
        ):
            if thread["channel_id"] not in result:
                raise ValueError("known archive contains an undeclared conversation")
            result[thread["channel_id"]].add(thread["ts"])
    return result


def acquire(
    cfg,
    registry_path,
    *,
    through,
    backfill,
    capture_root,
    evidence_path,
    mode="fetch",
    advance=False,
    force=False,
    home=None,
    transcripts=(),
    transcript_root=None,
):
    if mode not in {"health", "fetch", "plan"} or advance and mode != "fetch":
        raise ValueError("invalid Slack acquisition mode or advance intent")
    evidence_path = output_path(evidence_path)
    output_path(capture_root, directory=True)
    targets = preflight.resolve_targets(cfg)
    if not targets or any(not t.resolved for t in targets):
        raise ValueError(
            "every declared Slack target must resolve before a provider request"
        )
    ids = preflight.declared_set(targets)["slack"]
    if len(ids) != len(set(ids)) or any(
        not re.fullmatch(r"[CGD][A-Z0-9]+", cid) for cid in ids
    ):
        raise ValueError("declared Slack targets are duplicated or malformed")
    relative_archive = Path(cfg["transcripts_path"])
    if (
        relative_archive.is_absolute()
        or ".." in relative_archive.parts
        or not Path(cfg["transcripts_repo"]).is_absolute()
    ):
        raise ValueError(
            "archive configuration must name an absolute repository and relative transcript path"
        )
    output_path(Path(cfg["transcripts_repo"]) / relative_archive, directory=True)
    channel_names = [t.name.lstrip("#") for t in targets if t.kind == "channel"]
    if len(set(channel_names)) != len(channel_names) or any(
        not re.fullmatch(r"[a-z0-9_-]+", name) or name in {"_dms", "_group-dms"}
        for name in channel_names
    ):
        raise ValueError(
            "declared channel names must have distinct safe archive filenames"
        )
    workspace = cfg.get("workspace")
    if not isinstance(workspace, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", workspace):
        raise ValueError("workspace identity required")
    through = sync_watermark.parse_moment(through, datetime.now().astimezone())
    if through > datetime.now().astimezone():
        raise ValueError("future Slack acquisition window")
    windows = [
        sync_watermark.window(workspace, "slack", target=cid, now=through, home=home)
        for cid in ids
    ]
    start = min(moment(w["from"] or backfill) for w in windows)
    if start > through:
        raise ValueError("invalid Slack acquisition window")
    adapter_cfg = cfg.get("acquisition_adapter", {})
    kind = adapter_cfg.get("kind")
    if kind not in {"slack-web-api-v1", connector_replay.KIND}:
        raise ValueError(
            "explicit supported Slack acquisition adapter required; no undeclared fallback"
        )
    registry = slack_workspaces.load_registry(Path(registry_path))
    entry = slack_workspaces.acquisition_entry(registry, workspace)
    archive_root = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"]
    if not archive_root.is_absolute() or ".." in archive_root.parts:
        raise ValueError("physical absolute Slack archive root required")
    known = known_threads(cfg, archive_root, ids)
    transport = None
    if kind == connector_replay.KIND:
        # The registry's mcp:<server> reference names the one client-managed
        # connector whose recorded calls count; no token is read or held.
        server = entry.token[4:] if entry.token.startswith("mcp:") else ""
        if not server:
            raise ValueError("connector replay requires the registry's mcp:<server> reference")
        if not transcripts:
            raise ValueError("connector replay requires the transcripts that recorded the reads")
        calls, transcript_receipts = connector_replay.load_calls(
            transcripts,
            server=server,
            root=transcript_root or Path.home() / ".claude" / "projects",
        )
        adapter = connector_replay.ConnectorReplay(
            calls, adapter_cfg, server, through=through
        )
    else:
        if mode == "plan" or transcripts:
            raise ValueError("call plans and transcripts apply to connector replay only")
        adapter = SlackRead(entry, adapter_cfg, None)
        capture = Capture(capture_root)
        transport = ReadTransport(entry.token, capture)
        adapter.transport = transport
    try:
        if mode == "plan":
            missing, problems = [], {}
            try:
                adapter.readiness()
            except connector_replay.MissingCall as gap:
                missing.append(gap.call)
            for target in targets:
                adapter.describe(target.read_id)
                try:
                    need, blocked = connector_replay.plan_channel(
                        adapter,
                        target.read_id,
                        start,
                        through,
                        sorted(known[target.read_id]),
                    )
                except ValueError as exc:
                    need, blocked = [], [str(exc)]
                missing += need
                if blocked:
                    problems[target.read_id] = blocked
            return {
                "from": start.isoformat(),
                "through": through.isoformat(),
                "server": adapter.server,
                "missing_calls": missing,
                # Conversations with a problem stay UNKNOWN at their old
                # watermark; fetch still advances every conversation it proves.
                "problems": problems,
                "ready": not missing,
                "can_advance": False,
            }
        readiness = adapter.readiness()
        if mode == "health":
            return {
                "dependencies": "available",
                "service": "responsive",
                "identity": readiness,
                "coverage": "unknown",
                "can_advance": False,
                "native_acceptance": False,
            }
        observations, receipts, acquired, unacquired, pending = [], {}, [], [], {}
        for target in targets:
            adapter.describe(target.read_id)
            # One conversation whose coverage cannot be proven stays UNKNOWN at
            # its old watermark; it never blocks the conversations that can.
            try:
                channel = thread_checker.acquire_channel(
                    target.read_id,
                    start,
                    through,
                    read_channel=adapter.read_channel,
                    read_thread=adapter.read_thread,
                    search_replies=adapter.search_replies,
                    known_thread_ids=sorted(known[target.read_id]),
                    probe_newest=adapter.probe_newest,
                    probe_search_newest=adapter.probe_search_newest,
                )
                raw_records(channel)
            except ValueError as exc:
                unacquired.append({"id": target.read_id, "reason": str(exc)})
                continue
            observations.append(channel)
            acquired.append(target.read_id)
            day = through.astimezone().date().isoformat()
            if target.kind == "channel":
                name = target.name.lstrip("#")
                if not re.fullmatch(r"[a-z0-9_-]+", name):
                    raise ValueError(
                        "declared channel name is not a safe archive filename"
                    )
                filename = name + ".md"
            else:
                filename = "_dms.md" if target.kind == "dm" else "_group-dms.md"
            # DMs and group DMs share one daily file; publish each file once
            # per run so a run's own intermediate bytes are never backed up.
            pending.setdefault(f"slack/{day}/{filename}", []).append(channel)
        if not acquired:
            raise ValueError(
                "no declared conversation has provable coverage: "
                + json.dumps(unacquired, sort_keys=True)
            )
        for name, channels in pending.items():
            saved = save_channels(
                archive_root / name, channels, domain=entry.domain, force=force
            )
            receipts[name] = {"path": name, "sha256": saved["sha256"]}
        receipts = list(receipts.values())
        if transport is None:
            custody = {
                "kind": connector_replay.KIND,
                "server": adapter.server,
                "transcripts": transcript_receipts,
                "calls": [
                    {
                        "tool_call_id": call.call_id,
                        "tool": call.tool,
                        "input": call.arguments,
                        "observed_at": call.observed_at.isoformat(),
                        "transcript": call.source,
                        "result_sha256": hashlib.sha256(call.text.encode()).hexdigest(),
                    }
                    for call in calls
                    if call.call_id in adapter.used
                ],
            }
            custody["receipt"] = publish_json(
                Path(capture_root) / "connector-calls.json", custody
            )
        else:
            custody = capture.summary()
        evidence = {
            "schema": 1,
            "workspace": workspace,
            "surface": "slack",
            "from": start.isoformat(),
            "through": through.isoformat(),
            "archive_root": str(archive_root),
            "archives": receipts,
            "declared_targets": acquired,
            "unacquired_targets": unacquired,
            "channels": observations,
            "readiness": readiness,
            "custody": custody,
            "provider_limitations": [
                "Slack search is affected by user filters and may suppress nearby matches; this proves the declared returned corpus, not undiscoverable provider content."
            ],
        }
        if transport is None:
            evidence["provider_limitations"].append(
                "Connector reads are replayed from the client's own session transcript; "
                "their authenticity rests on that transcript, and the connector's "
                "rendered text stands in for Slack's raw message bodies."
            )
        result = validate(
            evidence, workspace=workspace, surface="slack", through=through, targets=acquired
        )
        receipt = publish_json(evidence_path, evidence)
        output = {
            "coverage": result,
            "evidence": receipt,
            "saved_files": receipts,
            "unacquired_targets": unacquired,
            "custody": custody if transport is None else capture.summary(include_receipts=False),
            "native_acceptance": False,
        }
        if advance:
            output["watermark"] = sync_watermark.advance(
                workspace,
                "slack",
                through.isoformat(),
                targets=acquired,
                acquisition=evidence,
                home=home,
                now=datetime.now().astimezone(),
            )
        return output
    finally:
        if transport is not None:
            transport.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True)
    p.add_argument("--registry", required=True)
    p.add_argument("--mode", choices=["health", "fetch", "plan"], default="fetch")
    p.add_argument("--through", required=True)
    p.add_argument("--backfill-from", required=True)
    p.add_argument("--capture-dir", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--advance", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument(
        "--transcript",
        action="append",
        default=[],
        help="Claude Code session transcript (.jsonl) holding the recorded connector reads; repeat for subagents",
    )
    a = p.parse_args(argv)
    try:
        result = acquire(
            preflight._load_config(Path(a.config)),
            a.registry,
            mode=a.mode,
            through=a.through,
            backfill=a.backfill_from,
            capture_root=a.capture_dir,
            evidence_path=a.evidence,
            advance=a.advance,
            force=a.force,
            transcripts=a.transcript,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                {"coverage": "unknown", "can_advance": False, "reason": str(exc)}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

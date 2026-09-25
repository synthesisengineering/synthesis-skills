"""Native observations under the existing admitted run journal.

This module neither schedules work nor issues outcome/authority receipts. Native
path/header consistency is qualified by the current PM actor; actual native
acceptance remains a distinct external qualification. A caller's mode is a
provenance claim, never authentication. Synthetic mode survives every event.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
from typing import TypedDict

import native_observations as native
import run_state
from run_admission import read_admission_observation, safe_path
from project_state import observer_native_identity

MAX_SOURCES = 64
MAX_GENERATIONS = 128
MAX_DISCOVERY_ENTRIES = 4096
MAX_DISCOVERY_BYTES = 16 * 1024 * 1024
MAX_FRONTIER_BYTES = 256 * 1024
MAX_CONSUMPTION_BYTES = 8 * 1024 * 1024
MAX_CONSUMPTION_BATCHES = 16
MAX_INVALIDATION_BYTES = 1024 * 1024


class CurrentEvents(TypedDict):
    schema_version: int
    run_id: str
    revision: int
    status: str
    events: list[dict]
    coverage: list[dict]
    diagnostics: list[dict]


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or set(required) - value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("native observation request has unsupported or missing fields")


def _extension(state):
    value = deepcopy(state.get("extensions", {}).get("native_observations"))
    if value is None:
        projection = native.empty_projection()
        return {"schema_version": 1, "sources": {}, "event_index": {}, "projection": projection,
                "projection_digest": native._digest(projection), "latest_batch": None,
                "invalidation_index": {}, "invalidation_index_version": 1}
    if (value.get("schema_version") != 1 or value.get("projection_digest") != native._digest(value.get("projection"))
            or set(value.get("event_index", {})) != set(value.get("projection", {}).get("events", {}))):
        raise ValueError("journal observation projection/cursor custody is invalid")
    for source in value["sources"].values():
        native._validate_binding(source["binding"])
        native._validate_cursor(source["binding"], source["cursor"], native.Limits())
    return value


def _root(context):
    proof = read_admission_observation(context)
    client, identity = observer_native_identity(context["actor"]["native_payload"])
    if client != proof["client"] or identity != proof["native_session_id"]:
        raise ValueError("native source identity differs from current admitted owner")
    if client == "muse":
        from live_receipt import resolve_muse_transcript
        path = resolve_muse_transcript(identity)
        if path is None:
            raise ValueError("current Muse source is unavailable")
    else:
        path = context["actor"]["native_payload"]["transcript_path"]
    return proof, client, identity, Path(path)


def _child_admission(context, child_id):
    child = context["state"].get("extensions", {}).get("workflow", {}).get("children", {}).get(child_id)
    proof = read_admission_observation(context)
    if (not child or child.get("integration_owner") != proof["session_uuid"]
            or child.get("mode") != "artifact-only" or child.get("producer") != child_id):
        raise ValueError("child source requires an admitted parent-owned workflow child")
    receipt = child.get("dispatch_receipt_id")
    verify = context.get("verify_receipt")
    bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    if not callable(verify) or not verify(receipt, "delegation", bindings):
        raise ValueError("child source requires current source-backed delegation evidence")
    return child


def _child_path(context, client, root, child_id):
    child = _child_admission(context, child_id)
    parent_id = child.get("parent_child_id")
    parent_thread = root
    if parent_id is not None:
        _child_admission(context, parent_id)
        parent = _extension(context["state"])["sources"].get("child:" + parent_id)
        if parent is None:
            raise ValueError("Grandchild source requires the enrolled admitted parent")
        _admitted_source(context, "child:" + parent_id, parent)
        parent_thread = parent["binding"]["producer"]["thread_id"]
    if client != "codex":
        raise ValueError("this client lacks an owner-qualified child dispatch-to-source locator")
    # This searches bounded headers once at enrollment, never source history.
    # Exhaustion or multiple native matches cannot choose an arbitrary producer.
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().absolute()
    directory = safe_path(home / "sessions", home)
    if not directory.is_dir():
        raise ValueError("Codex source directory is unavailable")
    matches, count, read_bytes = [], 0, 0
    for current, directories, files in os.walk(directory, followlinks=False):
        directories.sort()
        files.sort()
        count += len(directories) + len(files)
        if count > MAX_DISCOVERY_ENTRIES:
            raise ValueError("child source header discovery is incomplete at its entry bound")
        if any((Path(current) / name).is_symlink() for name in directories):
            raise ValueError("child source discovery crosses an unsafe directory")
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            candidate = safe_path(Path(current) / name, directory)
            stream, info = native._open(candidate)
            with stream:
                raw = stream.readline(64 * 1024 + 1)
            read_bytes += len(raw)
            if read_bytes > MAX_DISCOVERY_BYTES:
                raise ValueError("child source header discovery is incomplete at its byte bound")
            if not raw.endswith(b"\n") or len(raw) > 64 * 1024:
                raise ValueError("candidate native header cannot be qualified within the source bound")
            try:
                row = native._json(raw)
            except ValueError:
                continue
            declared = row.get("payload", {})
            if (row.get("type") == "session_meta" and declared.get("session_id") == root
                    and declared.get("parent_thread_id") == parent_thread and declared.get("agent_path") == child_id):
                thread = declared.get("id")
                native._producer(row, client, root, thread, parent_thread, child_id)
                matches.append((candidate, thread))
    if len(matches) != 1:
        raise ValueError("child source native header join is absent or ambiguous")
    return *matches[0], {"root": str(directory), "entries": count, "header_bytes": read_bytes,
                         "complete_within_root": True, "parent_thread_id": parent_thread, "authority_granted": False}


def _worker_source(context, handle):
    """Join captured bytes through the existing admitted native worker receipt."""
    proof = read_admission_observation(context)
    child_id = handle.removeprefix("worker:")
    run_state._id(child_id, "worker child")
    child = context["state"].get("extensions", {}).get("workflow", {}).get("children", {}).get(child_id)
    if (not child or child.get("mode") != "native-cli" or child.get("integration_owner") != proof["session_uuid"]
            or child.get("owner", {}).get("native_ref") != proof["native_ref"]):
        raise ValueError("transport source needs its admitted native CLI child and current parent")
    receipt_id = child.get("worker_receipt_id")
    bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    if not receipt_id or not context["verify_receipt"](receipt_id, "native_worker", bindings):
        raise ValueError("transport source requires a current owner-issued worker receipt")
    data = child.get("worker_observation")
    if not isinstance(data, dict): raise ValueError("worker observation is absent")
    from delegation_boundary import verify_worker_observation
    if not verify_worker_observation(data, context):
        raise ValueError("worker transport custody no longer matches its current raw bytes")
    client, producer = child.get("client"), data.get("producer")
    if client not in {"codex", "claude", "muse"} or not isinstance(producer, str) or not producer.startswith(client + ":"):
        raise ValueError("worker transport has no native session identity; startup remains unresolved")
    session = producer.split(":", 1)[1]
    receipt = safe_path(data["receipt_path"], Path(context["project"]))
    manifest = native._json(receipt.read_bytes())
    dialect = {"codex": "codex.exec_json", "claude": "claude.print_stream"}.get(client)
    path = receipt.parent / "stdout.jsonl"
    if client == "muse":
        # CLI --json is a projection and is not the durable raw record stream.
        startup = manifest.get("startup")
        if not isinstance(startup, dict) or startup.get("session_id") != session:
            raise ValueError("Muse worker lacks a retained durable source join; CLI projection cannot substitute")
        root = safe_path(Path(startup["data_root"]) / "muse" / "sessions", Path(context["project"]))
        paths = list(root.glob("*/*/*/" + session + "/session.jsonl"))
        if len(paths) != 1: raise ValueError("Muse worker durable source is missing or ambiguous")
        path = safe_path(paths[0], Path(context["project"]))
    custody = {"kind": "owner-issued-native-worker", "child_id": child_id, "task_id": child["task_id"],
        "receipt_id": receipt_id, "receipt_digest": data["receipt_digest"], "parent_native_ref": proof["native_ref"],
        "dialect": dialect, "invocation_id": native._digest([context["state"]["run_id"], child_id, data["receipt_digest"]]),
        "native_permission_boundary": deepcopy(data["boundary"]), "external_native_acceptance": "UNKNOWN",
        "authority_granted": False}
    return proof, client, session, session, None, None, path, custody


def _admitted_source(context, handle, source):
    proof, client, root, current_path = _root(context)
    if handle.startswith("worker:"):
        owner, client, session, _, _, _, path, custody = _worker_source(context, handle)
        if (source["qualification"]["session_uuid"] != owner["session_uuid"] or
                source["qualification"].get("discovery") != custody or source["binding"]["path"] != str(path.absolute()) or
                source["binding"]["producer"]["client"] != client or source["binding"]["producer"]["thread_id"] != session):
            raise ValueError("worker transport differs from its admitted custody")
        return
    if (source["binding"]["producer"]["root_session_id"] != root
            or source["binding"]["producer"]["client"] != client
            or source["qualification"]["session_uuid"] != proof["session_uuid"]):
        raise ValueError("source enrollment belongs to another root owner")
    if handle == "root" and str(current_path.absolute()) != source["binding"]["path"]:
        raise ValueError("native root source locator changed; explicit recovery is required")
    if handle != "root":
        child = _child_admission(context, handle[6:])
        stream, info = native._open(Path(source["binding"]["path"]))
        with stream:
            native._header(stream, source["binding"], info.st_size)
        parent_id = child.get("parent_child_id")
        if parent_id is not None:
            parent = _extension(context["state"])["sources"].get("child:" + parent_id)
            if parent is None or source["binding"]["producer"]["parent_thread_id"] != parent["binding"]["producer"]["thread_id"]:
                raise ValueError("Grandchild native parent identity changed")
            _admitted_source(context, "child:" + parent_id, parent)


def _source(context, handle):
    proof, client, root, path = _root(context)
    if isinstance(handle, str) and handle.startswith("worker:"):
        return _worker_source(context, handle)
    if handle == "root":
        return proof, client, root, root, None, None, path, None
    if not isinstance(handle, str) or not handle.startswith("child:") or len(handle) > 512:
        raise ValueError("source handle must name root or an admitted workflow child")
    child = handle.removeprefix("child:")
    path, thread, discovery = _child_path(context, client, root, child)
    return proof, client, root, thread, discovery["parent_thread_id"], child, path, discovery


def _frontier(path):
    stream, info = native._open(path)
    with stream:
        count = min(info.st_size, MAX_FRONTIER_BYTES)
        start = info.st_size - count
        raw = native._stable_read(stream, str(path), start, count, (info.st_dev, info.st_ino), info.st_size)
    position = raw.rfind(b"\n")
    if position < 0:
        raise ValueError("no complete-record enrollment frontier within the bounded source tail")
    end = start + position + 1
    anchor = raw[max(0, position + 1 - 4096):position + 1]
    return end, {"offset": end - len(anchor), "length": len(anchor),
                 "sha256": hashlib.sha256(anchor).hexdigest(), "scope": "enrollment boundary only"}


def _enroll(context, handle, mode, *, start_at_frontier=True, start_offset=None, source_epoch=None):
    if mode not in {"native", "synthetic"}:
        raise ValueError("source mode must be an explicit native or synthetic claim")
    proof, client, root, thread, parent, agent, path, discovery = _source(context, handle)
    frontier, anchor = _frontier(path) if start_at_frontier and handle == "root" else (0, None)
    if start_offset is not None:
        frontier, anchor = start_offset, None
    binding, cursor = native.enroll_source(path, client=client, expected_root_session_id=root,
        expected_thread_id=thread, expected_parent_thread_id=parent, expected_agent_id=agent,
        source_handle=handle, mode=mode, start_offset=frontier, source_epoch=source_epoch,
        dialect=discovery.get("dialect") if discovery else None,
        invocation_id=discovery.get("invocation_id") if discovery and discovery.get("dialect") else None)
    return {"binding": binding, "cursor": cursor, "coverage": None, "history": [], "ranges": [],
            "enrollment": {"generation": binding["generation"], "offset": frontier, "anchor": anchor,
                           "digest": native._digest([binding["generation"], frontier, anchor])},
            "qualification": {"session_uuid": proof["session_uuid"], "native_ref": proof["native_ref"],
                "claim_hash": proof["claim_hash"], "owner_admission": "VERIFIED",
                "source_identity": "current PM path and native header", "mode_claim": mode,
                "external_native_acceptance": "UNKNOWN", "child_root_authority": False,
                "discovery": discovery}}


def _prepare_enroll(context, payload):
    _fields(payload, {"source_handle", "mode"})
    extension = _extension(context["state"])
    handle = payload["source_handle"]
    if handle != "root" and ("root" not in extension["sources"]
            or payload["mode"] != extension["sources"]["root"]["binding"]["mode"]):
        raise ValueError("subordinate source must retain the admitted root provenance mode")
    if handle in extension["sources"]:
        existing = extension["sources"][handle]
        if existing["binding"]["mode"] != payload["mode"]:
            raise ValueError("journaled source provenance claim cannot change")
        _source(context, handle)
        return {"handle": handle, "source": existing}
    if len(extension["sources"]) >= MAX_SOURCES:
        raise ValueError("native source capacity reached")
    return {"handle": handle, "source": _enroll(context, handle, payload["mode"])}


def _reduce_enroll(state, prepared, context):
    result = deepcopy(state)
    extension = _extension(state)
    extension["sources"][prepared["handle"]] = deepcopy(prepared["source"])
    result["extensions"]["native_observations"] = extension
    return result


def _prepare_observe(context, payload):
    _fields(payload, {"source_handle", "through_event", "task_id", "attempt_id"})
    extension = _extension(context["state"])
    handle = payload["source_handle"]
    source = extension["sources"].get(handle)
    if source is None:
        if handle == "root" or "root" not in extension["sources"]:
            raise ValueError("root observation source must be enrolled by the admitted start owner")
        source = _enroll(context, handle, extension["sources"]["root"]["binding"]["mode"], start_at_frontier=False)
    else:
        # Revalidate current root admission and ownership without repeating the
        # potentially large child-header discovery already committed at enroll.
        _admitted_source(context, handle, source)
    for field in ("task_id", "attempt_id"):
        if payload[field] is not None:
            run_state._id(payload[field], field)
    if isinstance(handle, str) and handle.startswith("worker:"):
        child = context["state"]["extensions"]["workflow"]["children"][handle.removeprefix("worker:")]
        if payload["task_id"] != child["task_id"] or payload["attempt_id"] is not None:
            raise ValueError("worker observations must bind the admitted task; attempt outcome remains owner-derived")
    target = payload["through_event"]
    if target is not None:
        _fields(target, {"generation", "offset", "length", "sha256"})
        if (target["generation"] != source["binding"]["generation"]
                or type(target["offset"]) is not int or target["offset"] < source["cursor"]["enrolled_from"]
                or type(target["length"]) is not int or target["length"] <= 0
                or not isinstance(target["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", target["sha256"])):
            raise ValueError("requested source locator is outside the qualified observation scope")
    batch = native.read_page(source["binding"], source["cursor"], run_id=context["state"]["run_id"],
                             task_id=payload["task_id"], attempt_id=payload["attempt_id"])
    batch["requested_through"] = deepcopy(target)
    if target and not any(all(event["native"].get(key) == value for key, value in target.items()) for event in batch["events"]):
        batch["diagnostics"].append({"code": "requested_locator_not_observed", "obligation":
            "continue bounded catch-up or consume an already journaled exact event; no locator is inferred"})
    return {"handle": handle, "source": source, "batch": batch}


def _reduce_observe(state, prepared, context):
    result = deepcopy(state)
    extension = _extension(state)
    source, batch = deepcopy(prepared["source"]), deepcopy(prepared["batch"])
    source.update(cursor=batch["cursor"], coverage=batch["coverage"], last_diagnostics=deepcopy(batch["diagnostics"]))
    witness = batch.get("consumed_range")
    if witness is not None:
        source.setdefault("ranges", []).append(deepcopy(witness))
        if len(source["ranges"]) > run_state.MAX_EVENTS:
            raise ValueError("source witness capacity reached; owner compaction required")
    extension["sources"][prepared["handle"]] = source
    extension["projection"] = native.reduce_observations(extension["projection"], batch)
    extension["projection_digest"] = native._digest(extension["projection"])
    digest = native._digest(batch)
    for index, event in enumerate(batch["events"]):
        extension["event_index"].setdefault(event["event_id"], {
            "revision": state["revision"] + 1, "position": index, "batch_digest": digest,
            "source_handle": prepared["handle"], "generation": batch["source_generation"]})
        if _invalidates(event):
            extension.setdefault("invalidation_index", {})[event["event_id"]] = {
                "source_handle": prepared["handle"], "generation": batch["source_generation"],
                "offset": event["native"]["offset"]}
    extension["latest_batch"] = batch
    result["extensions"]["native_observations"] = extension
    from resource_policy import ingest_native
    ingest_native(result, prepared["handle"], batch)
    return result


def _continuity(old, fresh):
    """Current consumed-range continuity; never pre-enrollment absence."""
    ranges = old.get("ranges", [])
    offset = old["cursor"]["enrolled_from"]
    for item in ranges:
        if item["offset"] != offset:
            raise ValueError("retained range custody is incomplete; use an explicit interval")
        offset += item["length"]
    if offset != old["cursor"]["offset"]:
        raise ValueError("retained range custody is incomplete; use an explicit interval")
    witnesses = ([old["enrollment"]["anchor"]] if old["enrollment"]["anchor"] else []) + ranges
    if sum(item["length"] for item in witnesses) > 1024 * 1024:
        raise ValueError("current continuity exceeds 1 MiB bound; explicitly reconcile an interval and continue bounded catch-up")
    binding = fresh["binding"]
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
        for item in witnesses:
            raw = native._stable_read(stream, binding["path"], item["offset"], item["length"],
                (binding["device"], binding["inode"]), info.st_size)
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("current copied-source range differs; explicit unknown interval reconciliation required")
    return {"scope": "current consumed ranges and enrollment boundary", "ranges": deepcopy(witnesses),
            "pre_enrollment": "UNKNOWN", "prior_positive_generation": "not relabeled"}


def _prepare_reconcile(context, payload):
    _fields(payload, {"source_handle"}, {"reconciliation"})
    extension = _extension(context["state"])
    handle = payload["source_handle"]
    old = extension["sources"].get(handle)
    if old is None:
        raise ValueError("recovery cannot invent or advance an enrollment frontier")
    spec = payload.get("reconciliation")
    if spec is not None:
        _fields(spec, {"prior_generation", "prior_cursor_digest", "new_generation", "mode"}, {"start_offset", "invalidation_resolution"})
        if (spec["prior_generation"] != old["binding"]["generation"]
                or spec["prior_cursor_digest"] != native._digest(old["cursor"])
                or spec["new_generation"] is not None and (not isinstance(spec["new_generation"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", spec["new_generation"]))
                or spec["mode"] not in {"carry", "interval"}):
            raise ValueError("generation reconciliation does not bind the exact prior frontier")
        if spec["mode"] == "interval":
            if type(spec.get("start_offset")) is not int or spec["start_offset"] < 0:
                raise ValueError("interval reconciliation requires an explicit record-boundary start offset")
        elif "start_offset" in spec:
            raise ValueError("carry reconciliation cannot choose or advance a frontier")
        if "invalidation_resolution" in spec and spec["mode"] != "interval":
            raise ValueError("native resume requires an explicit new interval")
    fresh = _enroll(context, handle, old["binding"]["mode"], start_at_frontier=False,
                    source_epoch=old["binding"].get("source_epoch"))
    resolution = (_resolve_invalidation(context, handle, old, fresh, spec)
        if spec and "invalidation_resolution" in spec else None)
    stream, info = native._open(fresh["binding"]["path"], fresh["binding"])
    stream.close()
    same = fresh["binding"]["generation"] == old["binding"]["generation"]
    truncated = info.st_size < old["cursor"]["offset"]
    if same and not truncated and spec is None:
        old["binding"] = fresh["binding"]
        old["qualification"] = fresh["qualification"]
        old.pop("recovery", None)
        return {"handle": handle, "source": old}
    # A same-inode truncation or explicit replacement requires a new logical
    # incarnation, bound to the prior journal frontier rather than stat time.
    if same:
        epoch = native._digest([old["binding"]["generation"], native._digest(old["cursor"]), "owner-generation-reconciliation"])
        fresh = _enroll(context, handle, old["binding"]["mode"], start_at_frontier=False, source_epoch=epoch)
    if spec is None:
        old["recovery"] = {"status": "binding_required", "prior_generation": old["binding"]["generation"],
            "prior_cursor_digest": native._digest(old["cursor"]), "observed_generation": fresh["binding"]["generation"],
            "source_size": info.st_size, "prior_offset": old["cursor"]["offset"],
            "gap": "source generation changed; continuity and negative interval coverage remain UNKNOWN",
            "next": "Supply a carry proof or an explicit interval source_reconciliation; no cursor was reset"}
        return {"handle": handle, "source": old}
    if spec["new_generation"] is not None and spec["new_generation"] != fresh["binding"]["generation"]:
        raise ValueError("new source generation changed since the requested reconciliation")
    if len(old["history"]) >= MAX_GENERATIONS:
        raise ValueError("retained source generation capacity reached")
    if spec["mode"] == "carry":
        continuity = _continuity(old, fresh)
        fresh["cursor"] = {**deepcopy(old["cursor"]), "generation": fresh["binding"]["generation"]}
        fresh["ranges"] = deepcopy(old.get("ranges", []))
        fresh["enrollment"] = {**deepcopy(old["enrollment"]), "generation": fresh["binding"]["generation"]}
        fresh["enrollment"]["digest"] = native._digest([fresh["binding"]["generation"],
            fresh["enrollment"]["offset"], fresh["enrollment"]["anchor"]])
    else:
        fresh = _enroll(context, handle, old["binding"]["mode"], start_at_frontier=False,
            start_offset=spec["start_offset"], source_epoch=fresh["binding"].get("source_epoch"))
        continuity = {"scope": "explicit new-generation interval", "historical_interval": "UNKNOWN",
                      "skipped_prefix": "UNKNOWN", "prior_positive_generation": "not relabeled"}
    fresh["reconciliation"] = {"prior_generation": old["binding"]["generation"],
        "prior_cursor_digest": native._digest(old["cursor"]), "mode": spec["mode"], "continuity": continuity,
        "owner_revision": context["state"]["revision"] + 1}
    if resolution is not None:
        fresh["invalidation_resolution"] = resolution
    elif spec["mode"] == "carry" and old.get("invalidation_resolution"):
        fresh["invalidation_resolution"] = deepcopy(old["invalidation_resolution"])
    fresh["history"] = old["history"] + [{key: deepcopy(old.get(key)) for key in
        ("binding", "cursor", "coverage", "enrollment", "qualification", "ranges", "reconciliation")}]
    return {"handle": handle, "source": fresh}


def _invalidates(event):
    return (event["kind"] in {"message.user", "lifecycle.cancelled"}
        or event["kind"].startswith("lifecycle.")
        and event.get("data", {}).get("native_status") in {"cancelled", "aborted", "interrupted"})


def _resolve_invalidation(context, handle, old, current, spec):
    """Existing native-user receipt admits a new window, not historical absence."""
    resolution = spec["invalidation_resolution"]
    _fields(resolution, {"receipt_id", "resume_locator", "prior_invalidation_ids"})
    ids = resolution["prior_invalidation_ids"]
    if (not isinstance(ids, list) or len(ids) > 512 or any(not isinstance(i, str) for i in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("resume requires bounded exact prior invalidation identities")
    locator = resolution["resume_locator"]
    _fields(locator, {"generation", "offset", "length", "sha256"})
    binding = current["binding"]
    if (locator["generation"] != binding["generation"] or type(locator["offset"]) is not int
            or locator["offset"] < 0 or type(locator["length"]) is not int
            or not 0 < locator["length"] <= native.Limits().payload_bytes
            or not isinstance(locator["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", locator["sha256"])
            or spec["start_offset"] != locator["offset"] + locator["length"]):
        raise ValueError("resume frontier must be the exact current native user record end")
    record = context.get("evidence", {}).get(resolution["receipt_id"])
    verify = context.get("verify_receipt")
    bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    if not record or not callable(verify) or not verify(resolution["receipt_id"], "retry_clearance", bindings):
        raise ValueError("resume requires existing owner-verified native-user retry clearance")
    data = record["data"]
    source = data.get("source", {})
    expected = {"operation": "resume", "source_handle": handle,
        "prior_generation": spec["prior_generation"], "prior_cursor_digest": spec["prior_cursor_digest"],
        "prior_invalidation_ids": ids, "prior_interval": "acknowledged_unknown",
        "resume_message_id": source.get("message_id")}
    if (handle != "root" or source.get("kind") != "native-user" or data.get("approved") is not True
            or not data.get("changed_condition") or data.get("native_invalidation_resolution") != expected):
        raise ValueError("resume receipt does not bind the exact prior scope and explicit resume operation")
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
        raw = native._stable_read(stream, binding["path"], locator["offset"], locator["length"],
            (binding["device"], binding["inode"]), info.st_size)
    if hashlib.sha256(raw).hexdigest() != locator["sha256"] or not raw.endswith(b"\n"):
        raise ValueError("resume user source bytes changed")
    events = native._events(native._json(raw), binding, locator["offset"], locator["length"], locator["sha256"], 0)
    users = [event for event in events if event["kind"] == "message.user"
        and event["native"].get("record_id") == source["message_id"]]
    if not users or any(event["kind"] != "message.user" for event in events):
        raise ValueError("resume locator is not the exact native user authorization message")
    prior = current_invalidation(context, source_handle=handle)
    known = {identity for identity, row in _extension(context["state"]).get("invalidation_index", {}).items()
        if row["source_handle"] == handle and row["generation"] == old["binding"]["generation"]
        and row["offset"] < locator["offset"]}
    known.update(event["event_id"] for event in prior["invalidations"] if event["native"]["offset"] < locator["offset"])
    if set(ids) != known:
        raise ValueError("resume must bind every known prior invalidation identity")
    return {"receipt_id": record["id"], "receipt_digest": record["digest"], "bindings": bindings,
        "prior_generation": old["binding"]["generation"], "prior_cursor_digest": spec["prior_cursor_digest"],
        "prior_invalidation_ids": ids, "prior_interval": {"start": old["cursor"]["enrolled_from"],
            "end": locator["offset"], "coverage": "UNKNOWN", "disposition": "explicit_native_user_resume"},
        "resume_binding": deepcopy(binding), "resume_events": users,
        "owner_revision": context["state"]["revision"] + 1, "authority_granted": False}


def _journal_event(project, run_id, revision):
    home = run_state._home(project, run_id)
    path = safe_path(home / "events" / f"{revision:012d}.json", Path(project))
    event = run_state._read(path)
    if event.get("revision") != revision or event.get("digest") != run_state._digest({key: value for key, value in event.items() if key != "digest"}):
        raise ValueError("selected journal event digest is invalid")
    return event


def _current_head(context):
    state = context["state"]
    home = run_state._home(context["project"], state["run_id"])
    files = list((home / "events").iterdir())
    if not files or len(files) > run_state.MAX_EVENTS or any(not re.fullmatch(r"\d{12}\.json", item.name) for item in files):
        raise ValueError("journal head cannot be established within its supported bounds")
    revision = max(int(item.stem) for item in files)
    event = _journal_event(context["project"], state["run_id"], revision)
    if state != event["state"]:
        raise ValueError("observation consumption must bind the current authoritative journal state")
    return event["digest"]


def current_events(context, event_ids, *, required_interval=None) -> CurrentEvents:
    """Reopen exact committed source ranges in a fresh admitted owner context.

    The owning outcome consumer must still evaluate cancellation/invalidation
    and external native qualification. Current positive bytes do not certify a
    negative historical interval or a domain PASS.
    """
    read_admission_observation(context)
    head = _current_head(context)
    if (not isinstance(event_ids, list) or not 1 <= len(event_ids) <= 512
            or any(not isinstance(item, str) for item in event_ids) or len(set(event_ids)) != len(event_ids)):
        raise ValueError("consumption requires bounded unique journaled observation IDs")
    extension = _extension(context["state"])
    selected, grouped, cached = [], {}, {}
    consumed_bytes = source_bytes = 0
    for identity in event_ids:
        index = extension["event_index"].get(identity)
        if not index:
            raise ValueError("native observation ID is not in the authoritative journal index")
        revision = index["revision"]
        if revision not in cached:
            home = run_state._home(context["project"], context["state"]["run_id"])
            consumed_bytes += (home / "events" / f"{revision:012d}.json").stat().st_size
            if len(cached) >= MAX_CONSUMPTION_BATCHES or consumed_bytes > MAX_CONSUMPTION_BYTES:
                raise ValueError("selected journal consumption exceeds its bound; paginate exact event IDs")
            event = _journal_event(context["project"], context["state"]["run_id"], revision)
            cached[revision] = event["state"]["extensions"]["native_observations"]["latest_batch"]
        batch = cached[revision]
        if native._digest(batch) != index["batch_digest"]:
            raise ValueError("indexed native batch differs from its committed event")
        observed = batch["events"][index["position"]]
        if observed["event_id"] != identity:
            raise ValueError("indexed native event identity differs from its committed event")
        source_bytes += observed["native"]["length"]
        if source_bytes > 1024 * 1024:
            raise ValueError("selected source consumption exceeds its bound; paginate exact event IDs")
        selected.append(deepcopy(observed))
        grouped.setdefault((index["source_handle"], index["generation"]), []).append(observed)
    coverage, diagnostics, statuses = [], [], []
    for (handle, generation), events in grouped.items():
        source = extension["sources"][handle]
        candidates = [source] + source["history"]
        bound = next((item for item in candidates if item["binding"]["generation"] == generation), None)
        if bound is None:
            raise ValueError("source generation is missing from retained journal custody")
        _admitted_source(context, handle, bound)
        interval = required_interval.get(generation) if isinstance(required_interval, dict) else required_interval
        verdict = native.revalidate_observations(bound["binding"], events,
            projection=extension["projection"], required_interval=interval)
        statuses.append(verdict["status"])
        coverage.append({"source_handle": handle, "generation": generation, "mode": bound["binding"]["mode"],
                         "qualification": deepcopy(bound["qualification"]), **verdict})
        diagnostics.extend(verdict.get("diagnostics", []))
    if _current_head(context) != head:
        statuses.append("unknown")
        diagnostics.append({"code": "journal_changed_during_source_consumption"})
    return {"schema_version": 1, "run_id": context["state"]["run_id"], "revision": context["state"]["revision"],
            "status": "invalid" if "invalid" in statuses else "unknown" if "unknown" in statuses else "current",
            "events": selected, "coverage": coverage, "diagnostics": diagnostics}


def current_invalidation(context, *, source_handle="root"):
    """Read current typed invalidations in one enrolled producer's exact scope.

    A clear result is bounded current absence, never an authority grant. No
    stored cursor, stat result or cached digest establishes that absence. The
    pre-enrollment interval stays UNKNOWN; missing enrollment cannot be clear.
    Root and child sources must be requested separately, so a child cancellation
    cannot be interpreted as a root user instruction.
    """
    if context.get("admission_observation") is None:
        fresh = context.get("current_native_invalidation")
        if callable(fresh):
            return fresh(source_handle=source_handle)
    state = context.get("state", {})
    result = {"schema_version": 1, "run_id": state.get("run_id"), "revision": state.get("revision"),
        "source_handle": source_handle, "status": "unknown", "invalidations": [], "coverage": [],
        "diagnostics": [], "authority_granted": False, "pre_enrollment": "UNKNOWN",
        "historical_negative_coverage": "UNKNOWN", "scope": "retained invalidations and current unconsumed source tail",
        "producer_assumption": "cooperating native append-only producer; arbitrary edits to old benign bytes are not excluded"}
    try:
        read_admission_observation(context)
        head = _current_head(context)
        extension = _extension(state)
        source = extension["sources"].get(source_handle)
        if source is None:
            raise ValueError("current native invalidation requires an admitted source enrollment")
        _admitted_source(context, source_handle, source)
        if extension.get("invalidation_index_version") != 1:
            raise ValueError("historical native invalidation index needs owner reconciliation")
        if source.get("recovery") or source["cursor"]["first_gap"] is not None:
            raise ValueError("native interval needs explicit source generation/gap reconciliation")
        resolution = source.get("invalidation_resolution")
        if source.get("reconciliation", {}).get("mode") == "interval" and not resolution:
            raise ValueError("new source interval retains an unresolved prior invalidation scope")
        if resolution:
            if any(resolution["bindings"].get(key) != state[key] for key in ("run_id", "contract_digest", "profile_digest")):
                raise ValueError("native resume binding changed")
            _admitted_source(context, source_handle, {"binding": resolution["resume_binding"],
                "qualification": source["qualification"]})
            resume = native.revalidate_observations(resolution["resume_binding"], resolution["resume_events"])
            if resume["status"] != "current":
                raise ValueError("native resume source is no longer current")
            result["acknowledged_prior_interval"] = deepcopy(resolution["prior_interval"])
        binding = source["binding"]
        stream, info = native._open(binding["path"], binding)
        stream.close()
        if info.st_size < source["cursor"]["offset"]:
            raise ValueError("native source truncated behind the committed frontier")
        frontier = source["cursor"]["enrolled_from"]
        for witness in source.get("ranges", []):
            if witness["offset"] != frontier:
                raise ValueError("committed native page continuity has a skipped interval")
            frontier += witness["length"]
        if frontier != source["cursor"]["offset"]:
            raise ValueError("committed native page witnesses do not reach the cursor")
        acknowledged = set(resolution["prior_invalidation_ids"]) if resolution else set()
        if resolution:
            acknowledged.update(event["event_id"] for event in resolution["resume_events"])
        unresolved = [identity for identity, row in extension["invalidation_index"].items()
            if row["source_handle"] == source_handle and identity not in acknowledged]
        if len(unresolved) > 512:
            raise ValueError("unresolved invalidation witnesses exceed their bounded consumption scope")
        if unresolved:
            retained = current_events(context, unresolved)
            if retained["status"] != "current":
                raise ValueError("retained native invalidation witness is no longer current")
            result["invalidations"].extend(event for event in retained["events"] if not _accepted_rearm_message(context, event))
        start = source["cursor"]["frame_start"]
        verdict = native.revalidate_observations(binding, [], required_interval=(start, info.st_size),
            max_bytes=MAX_INVALIDATION_BYTES, prior_sequence=source["cursor"]["last_sequence"])
        result["coverage"].append({"source_handle": source_handle, "generation": binding["generation"],
            "producer": deepcopy(binding["producer"]), "mode": binding["mode"],
            **{key: value for key, value in verdict.items() if key not in {"events", "interval_events"}}})
        result["diagnostics"].extend(verdict["diagnostics"])
        if (verdict["status"] != "current" or verdict["negative_coverage"] != "CURRENT_BOUNDED_INTERVAL"
                or not verdict["covers_through_source_snapshot"]):
            return result
        for event in verdict["interval_events"]:
            # These native facts only revoke stale execution assumptions. User
            # text is never parsed into approvals or promoted to human identity.
            if _invalidates(event) and not _accepted_rearm_message(context, event):
                result["invalidations"].append(event)
        if _current_head(context) != head:
            raise ValueError("native invalidation journal changed during current source read")
        result["status"] = "invalidated" if result["invalidations"] else "clear"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["diagnostics"].append({"code": "native_invalidation_unknown", "detail": str(exc)[:4096],
            "obligation": "reconcile the exact owner-bound interval before further execution"})
    return result


def _accepted_rearm_message(context, event):
    """A committed re-arm resolves only its exact current native user message."""
    if (event["kind"] != "message.user" or event["native"]["source_handle"] != "root"
            or event["producer"]["thread_id"] != event["producer"]["root_session_id"]):
        return False
    state = context["state"]
    store = state.get("extensions", {}).get("workflow_persistence", {})
    for rearm in store.get("rearms", []):
        source = store.get("sources", {}).get(rearm.get("event_id"), {})
        record = state.get("evidence", {}).get(source.get("receipt_id"), {})
        data = record.get("data", {})
        reference = data.get("source", {})
        if (source.get("criterion_id") is not None or record.get("kind") != "retry_clearance"
                or rearm.get("source_digest") != record.get("digest") or reference.get("kind") != "native-user"
                or reference.get("message_id") != event["native"].get("record_id") or data.get("approved") is not True):
            continue
        try:
            from native_review import _user
            run_state._artifact(context["project"], state["artifacts"][record["artifact_id"]])
            binding = _extension(state)["sources"][event["native"]["source_handle"]]["binding"]
            ref = event["native"]
            stream, info = native._open(binding["path"], binding)
            with stream:
                raw = native._stable_read(stream, binding["path"], ref["offset"], ref["length"],
                    (binding["device"], binding["inode"]), info.st_size)
            if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                return False
            expected = {"schema_version": 1, "kind": "retry_clearance",
                "bindings": {key: state[key] for key in ("run_id", "contract_digest", "profile_digest")},
                "data": {key: value for key, value in data.items() if key != "source"}}
            return _user([native._json(raw)], reference, read_admission_observation(context)) == expected
        except (OSError, ValueError, KeyError, TypeError):
            return False
    return False


def current_muse_page(context, source_handle, message, connection_binding, locators):
    """Fresh owner admission plus current raw ranges; page JSON stays a hint."""
    read_admission_observation(context)
    head = _current_head(context)
    source = _extension(context["state"])["sources"].get(source_handle)
    if source is None: raise ValueError("page source is not enrolled")
    _admitted_source(context, source_handle, source)
    if (not isinstance(locators, dict) or any(not isinstance(row, dict)
            or type(row.get("offset")) is not int or row["offset"] < source["cursor"]["enrolled_from"]
            for row in locators.values())):
        raise ValueError("page ranges precede enrolled scope; explicit historical reconciliation required")
    result = native.revalidate_muse_page(source["binding"], message, connection_binding, locators)
    if head != _current_head(context): raise ValueError("journal changed during page reconciliation")
    return {**result, "run_id": context["state"]["run_id"], "revision": context["state"]["revision"]}


def _prepare_page(context, payload):
    _fields(payload, {"source_handle", "message", "connection_binding", "locators", "task_id", "attempt_id"})
    checked = current_muse_page(context, payload["source_handle"], payload["message"], payload["connection_binding"], payload["locators"])
    # The ordinary source reader is the only cursor owner. Wire cursors cannot
    # skip source bytes, reset a generation, or turn unknown history into clear.
    prepared = _prepare_observe(context, {"source_handle": payload["source_handle"], "through_event": None,
        "task_id": payload["task_id"], "attempt_id": payload["attempt_id"]})
    prepared["batch"]["page_reconciliation"] = {key: value for key, value in checked.items() if key != "raw_events"}
    return prepared


def register(engine):
    engine.register_command("native.page", _reduce_observe, terminal_safe=True)
    engine.register_preparer("native.page", _prepare_page)
    engine.register_command("native.enroll", _reduce_enroll)
    engine.register_preparer("native.enroll", _prepare_enroll)
    engine.register_command("native.observe", _reduce_observe, terminal_safe=True)
    engine.register_preparer("native.observe", _prepare_observe)
    engine.register_command("native.reconcile", _reduce_enroll)
    engine.register_preparer("native.reconcile", _prepare_reconcile)

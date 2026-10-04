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
    if (
        not isinstance(value, dict)
        or set(required) - value.keys()
        or value.keys() - set(required) - set(optional)
    ):
        raise ValueError("native observation request has unsupported or missing fields")


def _extension(state):
    value = run_state._copy_state(state.get("extensions", {}).get("native_observations"))
    if value is None:
        projection = native.empty_projection()
        return {
            "schema_version": 1,
            "sources": {},
            "event_index": {},
            "projection": projection,
            "projection_digest": native._digest(projection),
            "latest_batch": None,
            "invalidation_index": {},
            "invalidation_index_version": 1,
        }
    if (
        value.get("schema_version") != 1
        or value.get("projection_digest") != native._digest(value.get("projection"))
        or set(value.get("event_index", {}))
        != set(value.get("projection", {}).get("events", {}))
    ):
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
    child = (
        context["state"]
        .get("extensions", {})
        .get("workflow", {})
        .get("children", {})
        .get(child_id)
    )
    proof = read_admission_observation(context)
    if (
        not child
        or child.get("integration_owner") != proof["session_uuid"]
        or child.get("mode") != "artifact-only"
        or child.get("producer") != child_id
    ):
        raise ValueError(
            "child source requires an admitted parent-owned workflow child"
        )
    receipt = child.get("dispatch_receipt_id")
    verify = context.get("verify_receipt")
    bindings = {
        key: context["state"][key]
        for key in ("run_id", "contract_digest", "profile_digest")
    }
    if not callable(verify) or not verify(receipt, "delegation", bindings):
        raise ValueError(
            "child source requires current source-backed delegation evidence"
        )
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
        raise ValueError(
            "this client lacks an owner-qualified child dispatch-to-source locator"
        )
    # This searches bounded headers once at enrollment, never source history.
    # Exhaustion or multiple native matches cannot choose an arbitrary producer.
    home = (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        .expanduser()
        .absolute()
    )
    directory = safe_path(home / "sessions", home)
    if not directory.is_dir():
        raise ValueError("Codex source directory is unavailable")
    matches, count, read_bytes = [], 0, 0
    for current, directories, files in os.walk(directory, followlinks=False):
        directories.sort()
        files.sort()
        count += len(directories) + len(files)
        if count > MAX_DISCOVERY_ENTRIES:
            raise ValueError(
                "child source header discovery is incomplete at its entry bound"
            )
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
                raise ValueError(
                    "child source header discovery is incomplete at its byte bound"
                )
            if not raw.endswith(b"\n") or len(raw) > 64 * 1024:
                raise ValueError(
                    "candidate native header cannot be qualified within the source bound"
                )
            try:
                row = native._json(raw)
            except ValueError:
                continue
            declared = row.get("payload", {})
            if (
                row.get("type") == "session_meta"
                and declared.get("session_id") == root
                and declared.get("parent_thread_id") == parent_thread
                and declared.get("agent_path") == child_id
            ):
                thread = declared.get("id")
                native._producer(row, client, root, thread, parent_thread, child_id)
                matches.append((candidate, thread))
    if len(matches) != 1:
        raise ValueError("child source native header join is absent or ambiguous")
    return *matches[0], {
        "root": str(directory),
        "entries": count,
        "header_bytes": read_bytes,
        "complete_within_root": True,
        "parent_thread_id": parent_thread,
        "authority_granted": False,
    }


def _worker_source(context, handle):
    """Join captured bytes through the existing admitted native worker receipt."""
    proof = read_admission_observation(context)
    child_id = handle.removeprefix("worker:")
    run_state._id(child_id, "worker child")
    child = (
        context["state"]
        .get("extensions", {})
        .get("workflow", {})
        .get("children", {})
        .get(child_id)
    )
    if (
        not child
        or child.get("mode") != "native-cli"
        or child.get("integration_owner") != proof["session_uuid"]
        or child.get("owner", {}).get("native_ref") != proof["native_ref"]
    ):
        raise ValueError(
            "transport source needs its admitted native CLI child and current parent"
        )
    receipt_id = child.get("worker_receipt_id")
    bindings = {
        key: context["state"][key]
        for key in ("run_id", "contract_digest", "profile_digest")
    }
    if not receipt_id or not context["verify_receipt"](
        receipt_id, "native_worker", bindings
    ):
        raise ValueError(
            "transport source requires a current owner-issued worker receipt"
        )
    data = child.get("worker_observation")
    if not isinstance(data, dict):
        raise ValueError("worker observation is absent")
    from delegation_boundary import verify_worker_observation

    if not verify_worker_observation(data, context):
        raise ValueError(
            "worker transport custody no longer matches its current raw bytes"
        )
    client, producer = child.get("client"), data.get("producer")
    if (
        client not in {"codex", "claude", "muse", "hermes"}
        or not isinstance(producer, str)
        or not producer.startswith(client + ":")
    ):
        raise ValueError(
            "worker transport has no native session identity; startup remains unresolved"
        )
    session = producer.split(":", 1)[1]
    receipt = safe_path(data["receipt_path"], Path(context["project"]))
    manifest = native._json(receipt.read_bytes())
    dialect = {"codex": "codex.exec_json", "claude": "claude.print_stream"}.get(client)
    if client == "codex" and child.get("required_capabilities") == ["native-callback"]:
        dialect = "codex.app_server_callback"
    if client == "codex" and "permissions" in child.get("file_contract", {}):
        dialect = (
            "codex.app_server_managed"
            if child.get("required_capabilities")
            in (["native-callback"], ["native-permission-probe"])
            else "codex.app_server_managed_turn"
        )
    path = receipt.parent / "stdout.jsonl"
    if client == "muse":
        # CLI --json is a projection and is not the durable raw record stream.
        startup = manifest.get("startup")
        if not isinstance(startup, dict) or startup.get("session_id") != session:
            raise ValueError(
                "Muse worker lacks a retained durable source join; CLI projection cannot substitute"
            )
        root = safe_path(
            Path(startup["data_root"]) / "muse" / "sessions", Path(context["project"])
        )
        paths = list(root.glob("*/*/*/" + session + "/session.jsonl"))
        if len(paths) != 1:
            raise ValueError("Muse worker durable source is missing or ambiguous")
        path = safe_path(paths[0], Path(context["project"]))
    custody = {
        "kind": "owner-issued-native-worker",
        "child_id": child_id,
        "task_id": child["task_id"],
        "receipt_id": receipt_id,
        "receipt_digest": data["receipt_digest"],
        "parent_native_ref": proof["native_ref"],
        "dialect": dialect,
        "invocation_id": native._digest(
            [context["state"]["run_id"], child_id, data["receipt_digest"]]
        ),
        "native_permission_boundary": deepcopy(data["boundary"]),
        "external_native_acceptance": "UNKNOWN",
        "authority_granted": False,
    }
    return proof, client, session, session, None, None, path, custody


def _admitted_source(context, handle, source):
    proof, client, root, current_path = _root(context)
    if source.get("replay", {}).get("status") in {"pending", "failed"}:
        # Explicit reconciliation enrolls the current owner in replay.fresh.
        # The outer enrollment remains historical custody until replay finishes;
        # it must neither authorize the new seat nor be rewritten to impersonate it.
        fresh = source["replay"]["fresh"]
        if _replay_identity(source["binding"]) != _replay_identity(fresh["binding"]):
            raise ValueError("replay enrollment differs from its retained source identity")
        source = fresh
    if handle.startswith("worker:"):
        owner, client, session, _, _, _, path, custody = _worker_source(context, handle)
        if (
            source["qualification"]["session_uuid"] != owner["session_uuid"]
            or source["qualification"].get("discovery") != custody
            or source["binding"]["path"] != str(path.absolute())
            or source["binding"]["producer"]["client"] != client
            or source["binding"]["producer"]["thread_id"] != session
        ):
            raise ValueError("worker transport differs from its admitted custody")
        return
    if (
        source["binding"]["producer"]["root_session_id"] != root
        or source["binding"]["producer"]["client"] != client
        or source["qualification"]["session_uuid"] != proof["session_uuid"]
    ):
        raise ValueError("source enrollment belongs to another root owner")
    if handle == "root" and str(current_path.absolute()) != source["binding"]["path"]:
        raise ValueError(
            "native root source locator changed; explicit recovery is required"
        )
    if handle != "root":
        child = _child_admission(context, handle[6:])
        stream, info = native._open(Path(source["binding"]["path"]))
        with stream:
            native._header(stream, source["binding"], info.st_size)
        parent_id = child.get("parent_child_id")
        if parent_id is not None:
            parent = _extension(context["state"])["sources"].get("child:" + parent_id)
            if (
                parent is None
                or source["binding"]["producer"]["parent_thread_id"]
                != parent["binding"]["producer"]["thread_id"]
            ):
                raise ValueError("Grandchild native parent identity changed")
            _admitted_source(context, "child:" + parent_id, parent)


def _source(context, handle):
    proof, client, root, path = _root(context)
    if isinstance(handle, str) and handle.startswith("worker:"):
        return _worker_source(context, handle)
    if handle == "root":
        return proof, client, root, root, None, None, path, None
    if (
        not isinstance(handle, str)
        or not handle.startswith("child:")
        or len(handle) > 512
    ):
        raise ValueError("source handle must name root or an admitted workflow child")
    child = handle.removeprefix("child:")
    path, thread, discovery = _child_path(context, client, root, child)
    return (
        proof,
        client,
        root,
        thread,
        discovery["parent_thread_id"],
        child,
        path,
        discovery,
    )


def _frontier(path):
    stream, info = native._open(path)
    with stream:
        count = min(info.st_size, MAX_FRONTIER_BYTES)
        start = info.st_size - count
        raw = native._stable_read(
            stream, str(path), start, count, (info.st_dev, info.st_ino), info.st_size
        )
    position = raw.rfind(b"\n")
    if position < 0:
        raise ValueError(
            "no complete-record enrollment frontier within the bounded source tail"
        )
    end = start + position + 1
    anchor = raw[max(0, position + 1 - 4096) : position + 1]
    return end, {
        "offset": end - len(anchor),
        "length": len(anchor),
        "sha256": hashlib.sha256(anchor).hexdigest(),
        "scope": "enrollment boundary only",
    }


def _enroll(
    context,
    handle,
    mode,
    *,
    start_at_frontier=True,
    start_offset=None,
    source_epoch=None,
):
    if mode not in {"native", "synthetic"}:
        raise ValueError("source mode must be an explicit native or synthetic claim")
    proof, client, root, thread, parent, agent, path, discovery = _source(
        context, handle
    )
    frontier, anchor = (
        _frontier(path) if start_at_frontier and handle == "root" else (0, None)
    )
    if start_offset is not None:
        frontier, anchor = start_offset, None
    binding, cursor = native.enroll_source(
        path,
        client=client,
        expected_root_session_id=root,
        expected_thread_id=thread,
        expected_parent_thread_id=parent,
        expected_agent_id=agent,
        source_handle=handle,
        mode=mode,
        start_offset=frontier,
        source_epoch=source_epoch,
        dialect=discovery.get("dialect") if discovery else None,
        invocation_id=discovery.get("invocation_id")
        if discovery and discovery.get("dialect")
        else None,
    )
    return {
        "binding": binding,
        "cursor": cursor,
        "coverage": None,
        "history": [],
        "ranges": [],
        "enrollment": {
            "generation": binding["generation"],
            "offset": frontier,
            "anchor": anchor,
            "digest": native._digest([binding["generation"], frontier, anchor]),
        },
        "qualification": {
            "session_uuid": proof["session_uuid"],
            "native_ref": proof["native_ref"],
            "claim_hash": proof["claim_hash"],
            "owner_admission": "VERIFIED",
            "source_identity": "current PM path and native header",
            "mode_claim": mode,
            "external_native_acceptance": "UNKNOWN",
            "child_root_authority": False,
            "discovery": discovery,
        },
    }


def _prepare_enroll(context, payload):
    _fields(payload, {"source_handle", "mode"})
    extension = _extension(context["state"])
    handle = payload["source_handle"]
    if handle != "root" and (
        "root" not in extension["sources"]
        or payload["mode"] != extension["sources"]["root"]["binding"]["mode"]
    ):
        raise ValueError(
            "subordinate source must retain the admitted root provenance mode"
        )
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


# Replay is a journaled validation operation, never an execution/resume owner.
MAX_REPLAY_PAGE_BYTES = 1024 * 1024


def _replay_stamp(info):
    return [
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
        info.st_nlink,
        info.st_uid,
        info.st_gid,
    ]


def _replay_path_chain(path):
    import stat

    path = Path(path)
    if (
        not path.is_absolute()
        or len(path.parts) > 128
        or any(p in {".", ".."} for p in path.parts)
    ):
        raise ValueError("original replay requires a bounded canonical pathname")
    chain = []
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("original replay refuses aliased source ancestry")
        chain.append([info.st_dev, info.st_ino, info.st_mode])
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("original replay requires one regular unaliased source")
    return chain


def _replay_identity(binding):
    value = deepcopy(binding)
    for key in ("generation", "source_epoch"):
        value.pop(key, None)
    for key in (
        "adapter_version",
        "adapter_sha256",
        "normalizer_version",
        "normalizer_sha256",
    ):
        value["producer"].pop(key, None)
    return value


def _replay_key(event):
    row = event["native"]
    return native._digest(
        [row["offset"], row["length"], row.get("subrecord"), row.get("record_id")]
    )


def _replay_semantic(event):
    # Generation/decoder provenance changes; source bytes and meaning must not.
    material = native._event_material(event)
    material.pop("event_id")
    material["native"] = {
        k: v for k, v in material["native"].items() if k != "generation"
    }
    material["producer"] = {
        k: v
        for k, v in material["producer"].items()
        if k
        not in {
            "adapter_version",
            "adapter_sha256",
            "normalizer_version",
            "normalizer_sha256",
        }
    }
    return native._digest(material)


def _indexed_batch(context, index, *, max_bytes):
    """Select exact indexed bytes along the already admitted successor lineage.

    Full lineage validation belongs to run_state. The current journal's exact
    batch digest is the content authority here; linked run references only route
    this bounded read. Deterministic successor identities prohibit foreign-run
    routing even if an old locator changes during this operation.
    """
    import journal_storage

    state = context["state"]
    run_id, revision = state["run_id"], state["revision"]
    link = state.get("successor")
    used, seen = 0, set()
    for _ in range(run_state.MAX_SUCCESSOR_DEPTH + 1):
        if run_id in seen:
            raise ValueError("indexed native batch lineage is cyclic")
        seen.add(run_id)
        home = run_state._home(context["project"], run_id)
        if index["revision"] <= revision:
            try:
                batch, charged = journal_storage.component(
                    home / "events" / f"{index['revision']:012d}.json",
                    ("state", "extensions", "native_observations", "latest_batch"),
                    max_bytes=max_bytes - used,
                )
            except journal_storage.ComponentAbsent as exc:
                # An unrelated successor revision may lack the historical
                # cache. Only structural absence routes onward; corruption,
                # missing files, bad blocks and capacity failure still refuse.
                batch, charged = None, exc.charged_bytes
            used += charged
            if batch is not None and native._digest(batch) == index["batch_digest"]:
                return batch, used
        if not link:
            break
        reference = link["predecessor"]
        run_state._successor_reference(reference)
        if (
            run_state.successor_identity(context["project"], reference["run_id"])
            != run_id
        ):
            raise ValueError(
                "indexed native batch cannot route outside its owner-linked lineage"
            )
        run_id, revision = reference["run_id"], reference["revision"]
        # Resolve a further link only if this predecessor's exact batch fails.
        home = run_state._home(context["project"], run_id)
        if index["revision"] <= revision:
            try:
                batch, charged = journal_storage.component(
                    home / "events" / f"{index['revision']:012d}.json",
                    ("state", "extensions", "native_observations", "latest_batch"),
                    max_bytes=max_bytes - used,
                )
            except journal_storage.ComponentAbsent as exc:
                # An unrelated successor revision may lack the historical
                # cache. Only structural absence routes onward; corruption,
                # missing files, bad blocks and capacity failure still refuse.
                batch, charged = None, exc.charged_bytes
            used += charged
            if batch is not None and native._digest(batch) == index["batch_digest"]:
                return batch, used
        path = home / "events" / f"{revision:012d}.json"
        digest, charged = journal_storage.component(
            path, ("digest",), max_bytes=max_bytes - used
        )
        used += charged
        if digest != reference["event_digest"]:
            raise ValueError("indexed native predecessor head changed")
        try:
            link, charged = journal_storage.component(
                path, ("state", "successor"), max_bytes=max_bytes - used
            )
        except KeyError as exc:
            raise ValueError(
                "indexed native batch is absent from its verified lineage"
            ) from exc
        used += charged
    raise ValueError("indexed native batch differs from its committed lineage")


def _begin_replay(context, handle, old, fresh, *, historical=False):
    if len(old["history"]) >= MAX_GENERATIONS:
        raise ValueError("retained source generation capacity reached")
    generations = [*old["history"], old]
    start, frontier = old["cursor"]["enrolled_from"], old["cursor"]["offset"]
    ext = _extension(context["state"])
    empty_generations = []
    for row in generations:
        if _replay_identity(row["binding"]) != _replay_identity(fresh["binding"]):
            raise ValueError("original replay cannot adopt rotated, foreign or skipped source history")
        if row["enrollment"]["offset"] != start:
            cursor = row["cursor"]
            generation = row["binding"]["generation"]
            # A tail enrollment followed by an explicit earlier interval is
            # real retained history. Only an actually unconsumed generation
            # may be noncontributing; indexed facts can never be dropped.
            if (row is old or row.get("ranges")
                    or any(cursor[key] != row["enrollment"]["offset"]
                           for key in ("enrolled_from", "offset", "frame_start"))
                    or cursor.get("pending") or cursor.get("oversized")
                    or cursor.get("validator") or cursor.get("span_commitment")
                    or cursor.get("first_gap") is not None
                    or any(index["generation"] == generation for index in ext["event_index"].values())
                    or any(index["generation"] == generation for index in ext["invalidation_index"].values())):
                raise ValueError("original replay cannot adopt rotated, foreign or skipped source history")
            empty_generations.append(generation)
    if old.get("invalidation_resolution"):
        raise ValueError(
            "explicit acknowledged resume interval must retain its separate authority boundary"
        )
    witnesses, seen = [], set()
    for generation in generations:
        offset = generation["enrollment"]["offset"]
        entries = (
            [generation["enrollment"]["anchor"]]
            if generation["enrollment"]["anchor"]
            else []
        )
        for row in generation.get("ranges", []):
            if (
                row["offset"] != offset
                or not 0 < row["length"] <= MAX_REPLAY_PAGE_BYTES
            ):
                raise ValueError(
                    "original replay requires complete bounded retained range custody"
                )
            offset += row["length"]
            entries.append(row)
        if offset != generation["cursor"]["offset"] or (
                offset > frontier and generation["binding"]["generation"] not in empty_generations):
            raise ValueError(
                "original replay range custody does not reach each consumed frontier"
            )
        for witness in entries:
            digest = native._digest(witness)
            if digest not in seen:
                witnesses.append(deepcopy(witness))
                seen.add(digest)
    if len(witnesses) > run_state.MAX_EVENTS:
        raise ValueError("original replay witness capacity exhausted")
    if not historical:
        fresh = _enroll(
            context,
            handle,
            old["binding"]["mode"],
            start_at_frontier=False,
            start_offset=start,
            source_epoch=fresh["binding"].get("source_epoch"),
        )
    stream, info = native._open(fresh["binding"]["path"], fresh["binding"])
    with stream:
        native._header(stream, fresh["binding"], info.st_size)
    if info.st_size < frontier:
        raise ValueError("original replay source is truncated")
    ext = _extension(context["state"])
    allowed = {row["binding"]["generation"] for row in generations}
    indices = {
        key: row
        for key, row in ext["event_index"].items()
        if row["source_handle"] == handle and row["generation"] in allowed
    }
    result = deepcopy(old)
    result.pop("recovery", None)
    result["replay"] = {
        "schema_version": 1,
        "status": "pending",
        "phase": "ranges",
        "prior_generation": old["binding"]["generation"],
        "prior_cursor_digest": native._digest(old["cursor"]),
        "prior_enrollment_digest": native._digest(old["enrollment"]),
        "prior_ranges_digest": native._digest(old.get("ranges", [])),
        "original_offset": start,
        "noncontributing_empty_generations": empty_generations,
        "frontier": frontier,
        "snapshot": _replay_stamp(info),
        "path_chain": _replay_path_chain(fresh["binding"]["path"]),
        "fresh": fresh,
        "witnesses": witnesses,
        "witness_index": 0,
        "indices": indices,
        "revisions": [
            {"revision": revision, "batch_digest": digest}
            for revision, digest in sorted(
                {(row["revision"], row["batch_digest"]) for row in indices.values()}
            )
        ],
        "revision_index": 0,
        "expected": {},
        "matched": [],
        "aliases": {},
        "owner_revision": context["state"]["revision"] + 1,
        "pre_enrollment": "UNKNOWN",
        "effects_replayed": False,
        "authority_granted": False,
    }
    return {"handle": handle, "source": result}


def _begin_refresh(context, handle, old, enrolled):
    """Same-decoder freshness validates bytes once and decodes only new tail.

    The journal retains each prior certificate and charged request. Ordinary
    growth is not a new source/decoder generation and cannot consume lineage
    capacity. A changed decoder continues through _begin_replay instead.
    """
    if (old.get("replay", {}).get("status") != "complete"
            or enrolled["binding"] != old["binding"]):
        raise ValueError("refresh requires the same completely replayed source and decoder")
    offset = old["cursor"]["enrolled_from"]
    witnesses = [deepcopy(old["enrollment"]["anchor"])] if old["enrollment"]["anchor"] else []
    for row in old["ranges"]:
        if row["offset"] != offset or not 0 < row["length"] <= MAX_REPLAY_PAGE_BYTES:
            raise ValueError("refresh requires complete bounded range custody")
        offset += row["length"]
        witnesses.append(deepcopy(row))
    if offset != old["cursor"]["offset"]:
        raise ValueError("refresh requires complete retained byte custody")
    if len(witnesses) > run_state.MAX_EVENTS:
        raise ValueError("refresh range custody capacity exhausted")
    stream, info = native._open(old["binding"]["path"], old["binding"])
    with stream:
        native._header(stream, old["binding"], info.st_size)
    if info.st_size < offset:
        raise ValueError("refresh source was truncated")
    result, fresh = deepcopy(old), deepcopy(old)
    fresh.pop("replay", None)
    fresh["qualification"] = deepcopy(enrolled["qualification"])
    result["replay"] = {**deepcopy(old["replay"]), "mode": "refresh",
        "status": "pending", "phase": "ranges",
        "prior_replay_digest": native._digest(old["replay"]),
        "refresh_count": old["replay"].get("refresh_count", 0) + 1,
        "prior_generation": old["binding"]["generation"],
        "prior_cursor_digest": native._digest(old["cursor"]),
        "prior_enrollment_digest": native._digest(old["enrollment"]),
        "prior_ranges_digest": native._digest(old["ranges"]),
        "original_offset": old["cursor"]["enrolled_from"], "frontier": info.st_size,
        "snapshot": _replay_stamp(info), "path_chain": _replay_path_chain(old["binding"]["path"]),
        "fresh": fresh, "witnesses": witnesses, "witness_index": 0,
        "indices": {}, "revisions": [], "revision_index": 0,
        "expected": {}, "matched": [], "owner_revision": context["state"]["revision"] + 1}
    return {"handle": handle, "source": result}


def _replay_current(source):
    replay = source["replay"]
    if (
        replay["prior_cursor_digest"] != native._digest(source["cursor"])
        or replay["prior_ranges_digest"] != native._digest(source.get("ranges", []))
        or replay["prior_enrollment_digest"] != native._digest(source["enrollment"])
    ):
        raise ValueError("original replay committed frontier changed")
    binding = replay["fresh"]["binding"]
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
    if (
        _replay_stamp(info) != replay["snapshot"]
        or _replay_path_chain(binding["path"]) != replay["path_chain"]
    ):
        raise ValueError("original replay source changed during the bounded snapshot")
    return binding, info


def replay_read_ceiling(source, *, historical=False):
    """Pure pre-I/O ceiling for one admitted validation page, in read bytes.

    PM admission, setup, append and final report readback retain their own
    bounds. Semantic input is the existing aggregate component-read cap, not
    decoded object size. Native stable reads each read twice; streaming does
    two complete stable-read passes. No source file is opened to price a page.
    """
    replay = source.get("replay", {})
    pending = replay.get("status") == "pending"
    active = replay["fresh"] if pending else source
    binding, cursor = active["binding"], active["cursor"]
    limits = native.Limits()
    native._validate_binding(binding)
    native._validate_cursor(binding, cursor, limits)
    header = binding["header_length"]
    if pending and header != source["binding"]["header_length"]:
        raise ValueError("replay read ceiling cannot change its enrolled header length")
    # Historical source fences run before/after prepare and at commit. A
    # completed original interval may additionally start one bounded refresh.
    fences = 8 * header if historical else 0
    if pending:
        phase = replay["phase"]
        if phase in {"ranges", "semantics"}:
            key = "witness" if phase == "ranges" else "revision"
            rows, index = replay[key + ("es" if key == "witness" else "s")], replay[key + "_index"]
            if not isinstance(rows, list) or len(rows) > run_state.MAX_EVENTS or type(index) is not int or not 0 <= index <= len(rows):
                raise ValueError("replay read ceiling requires a bounded current phase index")
            extra = 0
            if index < len(rows):
                if phase == "ranges":
                    witness = rows[index]
                    length, offset = witness["length"], witness["offset"]
                    if (type(length) is not int or not 0 < length <= MAX_REPLAY_PAGE_BYTES
                            or type(offset) is not int or offset < 0):
                        raise ValueError("replay read ceiling requires a bounded retained range")
                    extra = 2 * length
                else:
                    # The first changed component may return one growth-detection
                    # sentinel byte before its existing reader refuses.
                    extra = MAX_CONSUMPTION_BYTES + 1
            # _replay_current reads the exact header before and after work.
            return fences + 4 * header + extra
        if phase != "decode":
            raise ValueError("replay read ceiling requires a known phase")
        frontier = replay["frontier"]
        if type(frontier) is not int or frontier < cursor["offset"]:
            raise ValueError("replay read ceiling requires an ordered captured frontier")
        page = min(MAX_REPLAY_PAGE_BYTES, frontier - cursor["offset"])
        if not page:
            return fences + 4 * header
        headers = 6 * header  # Two outer fences plus read_page's header.
    else:
        page = MAX_REPLAY_PAGE_BYTES  # Growth is unknown until the reader opens.
        headers = 2 * header
    span = cursor["offset"] - cursor["frame_start"] + page
    # Completed frames form disjoint spans inside pending bytes + this page.
    # The separate fixed reader caps remain authoritative even for a very old
    # oversized pending frame. Summing these bounds is conservative.
    compact = 2 * min(native.MAX_RECORD_READBACK_BYTES, span) if span > limits.payload_bytes else 0
    inline = 2 * min(limits.payload_bytes, span) if cursor["pending"] else 0
    stream = 0
    if (binding["producer"]["client"] == "codex" and not binding["producer"].get("dialect")
            and span > native.MAX_RECORD_READBACK_BYTES):
        stream = 4 * min(native.MAX_STREAM_SPAN_BYTES, span)
    return fences + headers + 2 * page + compact + inline + stream


def _prepare_replay_page(context, handle, source):
    result = deepcopy(source)
    replay = result["replay"]
    batch = None
    if replay["status"] != "pending":
        return {"handle": handle, "source": result, "replay_step": True, "batch": None}
    try:
        binding, info = _replay_current(result)
        if replay["phase"] == "ranges":
            i = replay["witness_index"]
            if i < len(replay["witnesses"]):
                witness = replay["witnesses"][i]
                stream, present = native._open(binding["path"], binding)
                with stream:
                    raw = native._stable_read(
                        stream,
                        binding["path"],
                        witness["offset"],
                        witness["length"],
                        (binding["device"], binding["inode"]),
                        present.st_size,
                    )
                if hashlib.sha256(raw).hexdigest() != witness["sha256"]:
                    raise ValueError("original replay retained source range changed")
                replay["witness_index"] += 1
            if replay["witness_index"] == len(replay["witnesses"]):
                replay["phase"] = "decode" if replay.get("mode") == "refresh" else "semantics"
        elif replay["phase"] == "semantics":
            i = replay["revision_index"]
            if i < len(replay["revisions"]):
                descriptor = replay["revisions"][i]
                stored, _ = _indexed_batch(
                    context, descriptor, max_bytes=MAX_CONSUMPTION_BYTES
                )
                digest = native._digest(stored)
                for identity, index in replay["indices"].items():
                    if any(
                        index[key] != descriptor[key]
                        for key in ("revision", "batch_digest")
                    ):
                        continue
                    event = stored["events"][index["position"]]
                    if digest != index["batch_digest"] or event["event_id"] != identity:
                        raise ValueError(
                            "original replay event differs from its journal witness"
                        )
                    location = event["native"]
                    if (
                        location["offset"] < replay["original_offset"]
                        or location["offset"] + location["length"] > replay["frontier"]
                    ):
                        raise ValueError(
                            "retained event lies outside original enrolled interval"
                        )
                    key, semantic = _replay_key(event), _replay_semantic(event)
                    expected = replay["expected"].setdefault(
                        key, {"semantic": semantic, "ids": []}
                    )
                    if expected["semantic"] != semantic:
                        raise ValueError(
                            "retained source generations disagree semantically"
                        )
                    expected["ids"].append(identity)
                replay["revision_index"] += 1
            if replay["revision_index"] == len(replay["revisions"]):
                replay["phase"] = "decode"
        else:
            fresh = replay["fresh"]
            remaining = replay["frontier"] - fresh["cursor"]["offset"]
            if remaining:
                batch = native.read_page(
                    binding,
                    fresh["cursor"],
                    run_id=context["state"]["run_id"],
                    limits=native.Limits(
                        page_bytes=min(MAX_REPLAY_PAGE_BYTES, remaining)
                    ),
                )
                if batch["gaps"] or batch["diagnostics"]:
                    raise ValueError(
                        "original interval remains unsupported or unreadable under current decoder"
                    )
                if batch["cursor"]["offset"] <= fresh["cursor"]["offset"]:
                    raise ValueError("original replay made no bounded progress")
                fresh["cursor"], fresh["coverage"] = (
                    deepcopy(batch["cursor"]),
                    deepcopy(batch["coverage"]),
                )
                fresh["ranges"].append(deepcopy(batch["consumed_range"]))
                new = []
                for event in batch["events"]:
                    key = _replay_key(event)
                    expected = replay["expected"].get(key)
                    if expected is None:
                        new.append(event)
                    else:
                        if expected["semantic"] != _replay_semantic(event):
                            raise ValueError(
                                "current decoder disagrees with an original observation"
                            )
                        for identity in expected["ids"]:
                            replay["aliases"][identity] = event["event_id"]
                        if key not in replay["matched"]:
                            replay["matched"].append(key)
                # Identical old events are validation only, not new usage/effects.
                batch["events"] = new
            if fresh["cursor"]["offset"] == replay["frontier"]:
                if set(replay["matched"]) != set(replay["expected"]):
                    raise ValueError(
                        "complete replay omitted an original event or record boundary"
                    )
                if replay.get("mode") != "refresh":
                    # Reproduce raw partial-frame custody with the current
                    # decoder. Old serialized validators are never adopted.
                    for key in ("frame_start", "pending", "oversized", "span_commitment"):
                        if fresh["cursor"].get(key) != source["cursor"].get(key):
                            raise ValueError("original replay partial-frame custody changed")
                replay["status"] = "complete"
                replay["pending_bytes"] = fresh["cursor"]["offset"] - fresh["cursor"]["frame_start"]
                replay["negative_coverage"] = "UNKNOWN"
        _replay_current(result)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        replay["status"] = "failed"
        replay["failure"] = {"detail": str(exc)[:4096], "negative_coverage": "UNKNOWN"}
        # Preserve the exact attempted page and diagnostics without admitting it.
        replay["failed_batch"] = batch
        batch = None
    return {"handle": handle, "source": result, "replay_step": True, "batch": batch}


def _promote_replay_source(source, revision):
    replay = source["replay"]
    if replay["status"] == "complete":
        fresh = replay.pop("fresh")
        fresh["history"] = source["history"] + ([] if replay.get("mode") == "refresh" else [
            {
                key: deepcopy(source.get(key))
                for key in (
                    "binding",
                    "cursor",
                    "coverage",
                    "enrollment",
                    "qualification",
                    "ranges",
                    "reconciliation",
                    "replay",
                )
            }
        ])
        if replay.get("mode") != "refresh":
            fresh["history"][-1].pop("replay", None)
        fresh["enrollment"]["anchor"] = deepcopy(source["enrollment"]["anchor"])
        fresh["enrollment"]["digest"] = native._digest(
            [
                fresh["binding"]["generation"],
                fresh["enrollment"]["offset"],
                fresh["enrollment"]["anchor"],
            ]
        )
        fresh["reconciliation"] = {
            "mode": "replay",
            "prior_generation": replay["prior_generation"],
            "prior_cursor_digest": replay["prior_cursor_digest"],
            "owner_revision": revision,
            "continuity": {
                "scope": "complete original enrolled interval",
                "pre_enrollment": "UNKNOWN",
            },
        }
        fresh["replay"] = replay
        source = fresh
    return source


def _reduce_replay_page(state, prepared, context):
    result = run_state._copy_state(state)
    extension = _extension(state)
    source, batch = deepcopy(prepared["source"]), deepcopy(prepared["batch"])
    if batch is not None:
        extension["projection"] = native.reduce_observations(
            extension["projection"], batch
        )
        extension["projection_digest"] = native._digest(extension["projection"])
        digest = native._digest(batch)
        for i, event in enumerate(batch["events"]):
            extension["event_index"][event["event_id"]] = {
                "revision": state["revision"] + 1,
                "position": i,
                "batch_digest": digest,
                "source_handle": prepared["handle"],
                "generation": batch["source_generation"],
            }
            if _invalidates(event):
                extension["invalidation_index"][event["event_id"]] = {
                    "source_handle": prepared["handle"],
                    "generation": batch["source_generation"],
                    "offset": event["native"]["offset"],
                }
        extension["latest_batch"] = batch
        from resource_policy import ingest_native

        if any(event["kind"] == "usage.snapshot" for event in batch["events"]):
            ingest_native(result, prepared["handle"], batch)
    source = _promote_replay_source(source, state["revision"] + 1)
    extension["sources"][prepared["handle"]] = source
    result["extensions"]["native_observations"] = extension
    return result


def _replayed_event(event, binding):
    result = deepcopy(event)
    row = result["native"]
    row["generation"] = binding["generation"]
    result["producer"] = deepcopy(binding["producer"])
    result["event_id"] = "sha256:" + native._digest(
        [
            binding["generation"],
            row["offset"],
            row["length"],
            row.get("subrecord"),
            row.get("record_id"),
        ]
    )
    return result


def _prepare_observe(context, payload):
    _fields(payload, {"source_handle", "through_event", "task_id", "attempt_id"})
    extension = _extension(context["state"])
    handle = payload["source_handle"]
    source = extension["sources"].get(handle)
    if source is None:
        if handle == "root" or "root" not in extension["sources"]:
            raise ValueError(
                "root observation source must be enrolled by the admitted start owner"
            )
        source = _enroll(
            context,
            handle,
            extension["sources"]["root"]["binding"]["mode"],
            start_at_frontier=False,
        )
    else:
        # Revalidate current root admission and ownership without repeating the
        # potentially large child-header discovery already committed at enroll.
        _admitted_source(context, handle, source)
    for field in ("task_id", "attempt_id"):
        if payload[field] is not None:
            run_state._id(payload[field], field)
    if isinstance(handle, str) and handle.startswith("worker:"):
        child = context["state"]["extensions"]["workflow"]["children"][
            handle.removeprefix("worker:")
        ]
        if payload["task_id"] != child["task_id"] or payload["attempt_id"] is not None:
            raise ValueError(
                "worker observations must bind the admitted task; attempt outcome remains owner-derived"
            )
    target = payload["through_event"]
    if target is not None:
        _fields(target, {"generation", "offset", "length", "sha256"})
        if (
            target["generation"] != source["binding"]["generation"]
            or type(target["offset"]) is not int
            or target["offset"] < source["cursor"]["enrolled_from"]
            or type(target["length"]) is not int
            or target["length"] <= 0
            or not isinstance(target["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", target["sha256"])
        ):
            raise ValueError(
                "requested source locator is outside the qualified observation scope"
            )
    if source.get("replay", {}).get("status") in {"pending", "failed"}:
        return _prepare_replay_page(context, handle, source)
    batch = native.read_page(
        source["binding"],
        source["cursor"],
        run_id=context["state"]["run_id"],
        task_id=payload["task_id"],
        attempt_id=payload["attempt_id"],
    )
    batch["requested_through"] = deepcopy(target)
    if target and not any(
        all(event["native"].get(key) == value for key, value in target.items())
        for event in batch["events"]
    ):
        batch["diagnostics"].append(
            {
                "code": "requested_locator_not_observed",
                "obligation": "continue bounded catch-up or consume an already journaled exact event; no locator is inferred",
            }
        )
    return {"handle": handle, "source": source, "batch": batch}


def _reduce_observe(state, prepared, context):
    if prepared.get("replay_step"):
        return _reduce_replay_page(state, prepared, context)
    result = run_state._copy_state(state)
    extension = _extension(state)
    source, batch = deepcopy(prepared["source"]), deepcopy(prepared["batch"])
    source.update(
        cursor=batch["cursor"],
        coverage=batch["coverage"],
        last_diagnostics=deepcopy(batch["diagnostics"]),
    )
    witness = batch.get("consumed_range")
    if witness is not None:
        source.setdefault("ranges", []).append(deepcopy(witness))
        if len(source["ranges"]) > run_state.MAX_EVENTS:
            raise ValueError(
                "source witness capacity reached; owner compaction required"
            )
    extension["sources"][prepared["handle"]] = source
    extension["projection"] = native.reduce_observations(extension["projection"], batch)
    extension["projection_digest"] = native._digest(extension["projection"])
    digest = native._digest(batch)
    for index, event in enumerate(batch["events"]):
        extension["event_index"].setdefault(
            event["event_id"],
            {
                "revision": state["revision"] + 1,
                "position": index,
                "batch_digest": digest,
                "source_handle": prepared["handle"],
                "generation": batch["source_generation"],
            },
        )
        if _invalidates(event):
            extension.setdefault("invalidation_index", {})[event["event_id"]] = {
                "source_handle": prepared["handle"],
                "generation": batch["source_generation"],
                "offset": event["native"]["offset"],
            }
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
            raise ValueError(
                "retained range custody is incomplete; use an explicit interval"
            )
        offset += item["length"]
    if offset != old["cursor"]["offset"]:
        raise ValueError(
            "retained range custody is incomplete; use an explicit interval"
        )
    witnesses = (
        [old["enrollment"]["anchor"]] if old["enrollment"]["anchor"] else []
    ) + ranges
    if sum(item["length"] for item in witnesses) > 1024 * 1024:
        raise ValueError(
            "current continuity exceeds 1 MiB bound; explicitly reconcile an interval and continue bounded catch-up"
        )
    binding = fresh["binding"]
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
        for item in witnesses:
            raw = native._stable_read(
                stream,
                binding["path"],
                item["offset"],
                item["length"],
                (binding["device"], binding["inode"]),
                info.st_size,
            )
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError(
                    "current copied-source range differs; explicit unknown interval reconciliation required"
                )
    return {
        "scope": "current consumed ranges and enrollment boundary",
        "ranges": deepcopy(witnesses),
        "pre_enrollment": "UNKNOWN",
        "prior_positive_generation": "not relabeled",
    }


def _prepare_reconcile(context, payload):
    _fields(payload, {"source_handle"}, {"reconciliation"})
    extension = _extension(context["state"])
    handle = payload["source_handle"]
    old = extension["sources"].get(handle)
    if old is None:
        raise ValueError("recovery cannot invent or advance an enrollment frontier")
    spec = payload.get("reconciliation")
    if old.get("replay", {}).get("status") in {"pending", "failed"} and spec is None:
        _admitted_source(context, handle, old)
        return {"handle": handle, "source": old}
    if spec is not None:
        _fields(
            spec,
            {"prior_generation", "prior_cursor_digest", "new_generation", "mode"},
            {"start_offset", "invalidation_resolution"},
        )
        if (
            spec["prior_generation"] != old["binding"]["generation"]
            or spec["prior_cursor_digest"] != native._digest(old["cursor"])
            or spec["new_generation"] is not None
            and (
                not isinstance(spec["new_generation"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", spec["new_generation"])
            )
            or spec["mode"] not in {"carry", "interval", "replay"}
        ):
            raise ValueError(
                "generation reconciliation does not bind the exact prior frontier"
            )
        if spec["mode"] == "interval":
            if type(spec.get("start_offset")) is not int or spec["start_offset"] < 0:
                raise ValueError(
                    "interval reconciliation requires an explicit record-boundary start offset"
                )
        elif "start_offset" in spec:
            raise ValueError("carry reconciliation cannot choose or advance a frontier")
        if "invalidation_resolution" in spec and spec["mode"] != "interval":
            raise ValueError("native resume requires an explicit new interval")
    fresh = _enroll(
        context,
        handle,
        old["binding"]["mode"],
        start_at_frontier=False,
        source_epoch=old["binding"].get("source_epoch"),
    )
    resolution = (
        _resolve_invalidation(context, handle, old, fresh, spec)
        if spec and "invalidation_resolution" in spec
        else None
    )
    stream, info = native._open(fresh["binding"]["path"], fresh["binding"])
    stream.close()
    same = fresh["binding"]["generation"] == old["binding"]["generation"]
    truncated = info.st_size < old["cursor"]["offset"]
    if (
        spec is None
        and not same
        and _replay_identity(old["binding"]) == _replay_identity(fresh["binding"])
    ):
        return _begin_replay(context, handle, old, fresh)
    if spec and spec["mode"] == "replay":
        if same:
            fresh = _enroll(
                context,
                handle,
                old["binding"]["mode"],
                start_at_frontier=False,
                source_epoch=native._digest(
                    [
                        old["binding"]["generation"],
                        native._digest(old["cursor"]),
                        "original-interval-replay",
                    ]
                ),
            )
        if (
            spec["new_generation"] is not None
            and spec["new_generation"] != fresh["binding"]["generation"]
        ):
            raise ValueError("requested replay generation changed")
        return _begin_replay(context, handle, old, fresh)
    if (
        same
        and not truncated
        and spec is None
        and old.get("replay", {}).get("status") == "complete"
        and (_replay_stamp(info) != old["replay"]["snapshot"]
             or old["cursor"]["offset"] < info.st_size)
    ):
        return _begin_refresh(context, handle, old, fresh)
    if same and not truncated and spec is None:
        old["binding"] = fresh["binding"]
        old["qualification"] = fresh["qualification"]
        old.pop("recovery", None)
        return {"handle": handle, "source": old}
    # A same-inode truncation or explicit replacement requires a new logical
    # incarnation, bound to the prior journal frontier rather than stat time.
    if same:
        epoch = native._digest(
            [
                old["binding"]["generation"],
                native._digest(old["cursor"]),
                "owner-generation-reconciliation",
            ]
        )
        fresh = _enroll(
            context,
            handle,
            old["binding"]["mode"],
            start_at_frontier=False,
            source_epoch=epoch,
        )
    if spec is None:
        old["recovery"] = {
            "status": "binding_required",
            "prior_generation": old["binding"]["generation"],
            "prior_cursor_digest": native._digest(old["cursor"]),
            "observed_generation": fresh["binding"]["generation"],
            "source_size": info.st_size,
            "prior_offset": old["cursor"]["offset"],
            "gap": "source generation changed; continuity and negative interval coverage remain UNKNOWN",
            "next": "Supply a carry proof or an explicit interval source_reconciliation; no cursor was reset",
        }
        return {"handle": handle, "source": old}
    if (
        spec["new_generation"] is not None
        and spec["new_generation"] != fresh["binding"]["generation"]
    ):
        raise ValueError(
            "new source generation changed since the requested reconciliation"
        )
    if len(old["history"]) >= MAX_GENERATIONS:
        raise ValueError("retained source generation capacity reached")
    if spec["mode"] == "carry":
        continuity = _continuity(old, fresh)
        fresh["cursor"] = {
            **deepcopy(old["cursor"]),
            "generation": fresh["binding"]["generation"],
        }
        fresh["ranges"] = deepcopy(old.get("ranges", []))
        fresh["enrollment"] = {
            **deepcopy(old["enrollment"]),
            "generation": fresh["binding"]["generation"],
        }
        fresh["enrollment"]["digest"] = native._digest(
            [
                fresh["binding"]["generation"],
                fresh["enrollment"]["offset"],
                fresh["enrollment"]["anchor"],
            ]
        )
    else:
        fresh = _enroll(
            context,
            handle,
            old["binding"]["mode"],
            start_at_frontier=False,
            start_offset=spec["start_offset"],
            source_epoch=fresh["binding"].get("source_epoch"),
        )
        continuity = {
            "scope": "explicit new-generation interval",
            "historical_interval": "UNKNOWN",
            "skipped_prefix": "UNKNOWN",
            "prior_positive_generation": "not relabeled",
        }
    fresh["reconciliation"] = {
        "prior_generation": old["binding"]["generation"],
        "prior_cursor_digest": native._digest(old["cursor"]),
        "mode": spec["mode"],
        "continuity": continuity,
        "owner_revision": context["state"]["revision"] + 1,
    }
    if resolution is not None:
        fresh["invalidation_resolution"] = resolution
    elif spec["mode"] == "carry" and old.get("invalidation_resolution"):
        fresh["invalidation_resolution"] = deepcopy(old["invalidation_resolution"])
    fresh["history"] = old["history"] + [
        {
            key: deepcopy(old.get(key))
            for key in (
                "binding",
                "cursor",
                "coverage",
                "enrollment",
                "qualification",
                "ranges",
                "reconciliation",
            )
        }
    ]
    return {"handle": handle, "source": fresh}


def _invalidates(event):
    return (
        event["kind"] in {"message.user", "lifecycle.cancelled"}
        or event["kind"].startswith("lifecycle.")
        and event.get("data", {}).get("native_status")
        in {"cancelled", "aborted", "interrupted"}
    )


def _resolve_invalidation(context, handle, old, current, spec):
    """Existing native-user receipt admits a new window, not historical absence."""
    resolution = spec["invalidation_resolution"]
    _fields(resolution, {"receipt_id", "resume_locator", "prior_invalidation_ids"})
    ids = resolution["prior_invalidation_ids"]
    if (
        not isinstance(ids, list)
        or len(ids) > 512
        or any(not isinstance(i, str) for i in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError("resume requires bounded exact prior invalidation identities")
    locator = resolution["resume_locator"]
    _fields(locator, {"generation", "offset", "length", "sha256"})
    binding = current["binding"]
    if (
        locator["generation"] != binding["generation"]
        or type(locator["offset"]) is not int
        or locator["offset"] < 0
        or type(locator["length"]) is not int
        or not 0 < locator["length"] <= native.Limits().payload_bytes
        or not isinstance(locator["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", locator["sha256"])
        or spec["start_offset"] != locator["offset"] + locator["length"]
    ):
        raise ValueError(
            "resume frontier must be the exact current native user record end"
        )
    record = context.get("evidence", {}).get(resolution["receipt_id"])
    verify = context.get("verify_receipt")
    bindings = {
        key: context["state"][key]
        for key in ("run_id", "contract_digest", "profile_digest")
    }
    if (
        not record
        or not callable(verify)
        or not verify(resolution["receipt_id"], "retry_clearance", bindings)
    ):
        raise ValueError(
            "resume requires existing owner-verified native-user retry clearance"
        )
    data = record["data"]
    source = data.get("source", {})
    expected = {
        "operation": "resume",
        "source_handle": handle,
        "prior_generation": spec["prior_generation"],
        "prior_cursor_digest": spec["prior_cursor_digest"],
        "prior_invalidation_ids": ids,
        "prior_interval": "acknowledged_unknown",
        "resume_message_id": source.get("message_id"),
    }
    if (
        handle != "root"
        or source.get("kind") != "native-user"
        or data.get("approved") is not True
        or not data.get("changed_condition")
        or data.get("native_invalidation_resolution") != expected
    ):
        raise ValueError(
            "resume receipt does not bind the exact prior scope and explicit resume operation"
        )
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
        raw = native._stable_read(
            stream,
            binding["path"],
            locator["offset"],
            locator["length"],
            (binding["device"], binding["inode"]),
            info.st_size,
        )
    if hashlib.sha256(raw).hexdigest() != locator["sha256"] or not raw.endswith(b"\n"):
        raise ValueError("resume user source bytes changed")
    events = native._events(
        native._json(raw),
        binding,
        locator["offset"],
        locator["length"],
        locator["sha256"],
        0,
    )
    users = [
        event
        for event in events
        if event["kind"] == "message.user"
        and event["native"].get("record_id") == source["message_id"]
    ]
    if not users or any(event["kind"] != "message.user" for event in events):
        raise ValueError(
            "resume locator is not the exact native user authorization message"
        )
    prior = current_invalidation(context, source_handle=handle)
    known = {
        identity
        for identity, row in _extension(context["state"])
        .get("invalidation_index", {})
        .items()
        if row["source_handle"] == handle
        and row["generation"] == old["binding"]["generation"]
        and row["offset"] < locator["offset"]
    }
    known.update(
        event["event_id"]
        for event in prior["invalidations"]
        if event["native"]["offset"] < locator["offset"]
    )
    if set(ids) != known:
        raise ValueError("resume must bind every known prior invalidation identity")
    return {
        "receipt_id": record["id"],
        "receipt_digest": record["digest"],
        "bindings": bindings,
        "prior_generation": old["binding"]["generation"],
        "prior_cursor_digest": spec["prior_cursor_digest"],
        "prior_invalidation_ids": ids,
        "prior_interval": {
            "start": old["cursor"]["enrolled_from"],
            "end": locator["offset"],
            "coverage": "UNKNOWN",
            "disposition": "explicit_native_user_resume",
        },
        "resume_binding": deepcopy(binding),
        "resume_events": users,
        "owner_revision": context["state"]["revision"] + 1,
        "authority_granted": False,
    }


def _journal_event(project, run_id, revision):
    home = run_state._home(project, run_id)
    path = safe_path(home / "events" / f"{revision:012d}.json", Path(project))
    event = run_state._read(path)
    if event.get("revision") != revision or event.get("digest") != run_state._digest(
        {key: value for key, value in event.items() if key != "digest"}
    ):
        raise ValueError("selected journal event digest is invalid")
    return event


def _current_head(context):
    state = context["state"]
    home = run_state._home(context["project"], state["run_id"])
    files = list((home / "events").iterdir())
    if (
        not files
        or len(files) > run_state.MAX_EVENTS
        or any(not re.fullmatch(r"\d{12}\.json", item.name) for item in files)
    ):
        raise ValueError(
            "journal head cannot be established within its supported bounds"
        )
    revision = max(int(item.stem) for item in files)
    event = _journal_event(context["project"], state["run_id"], revision)
    if state != event["state"]:
        raise ValueError(
            "observation consumption must bind the current authoritative journal state"
        )
    return event["digest"]


def current_events(context, event_ids, *, required_interval=None) -> CurrentEvents:
    """Reopen exact committed source ranges in a fresh admitted owner context.

    The owning outcome consumer must still evaluate cancellation/invalidation
    and external native qualification. Current positive bytes do not certify a
    negative historical interval or a domain PASS.
    """
    read_admission_observation(context)
    head = _current_head(context)
    if (
        not isinstance(event_ids, list)
        or not 1 <= len(event_ids) <= 512
        or any(not isinstance(item, str) for item in event_ids)
        or len(set(event_ids)) != len(event_ids)
    ):
        raise ValueError(
            "consumption requires bounded unique journaled observation IDs"
        )
    extension = _extension(context["state"])
    selected, grouped, cached = [], {}, {}
    consumed_bytes = source_bytes = 0
    for identity in event_ids:
        index = extension["event_index"].get(identity)
        if not index:
            raise ValueError(
                "native observation ID is not in the authoritative journal index"
            )
        key = (index["revision"], index["batch_digest"])
        if key not in cached:
            if len(cached) >= MAX_CONSUMPTION_BATCHES:
                raise ValueError(
                    "selected journal consumption exceeds its batch bound; paginate exact event IDs"
                )
            batch, charged = _indexed_batch(
                context, index, max_bytes=MAX_CONSUMPTION_BYTES - consumed_bytes
            )
            consumed_bytes += charged
            cached[key] = batch
        batch = cached[key]
        if native._digest(batch) != index["batch_digest"]:
            raise ValueError("indexed native batch differs from its committed event")
        observed = batch["events"][index["position"]]
        if observed["event_id"] != identity:
            raise ValueError(
                "indexed native event identity differs from its committed event"
            )
        source_bytes += observed["native"]["length"]
        if source_bytes > 1024 * 1024:
            raise ValueError(
                "selected source consumption exceeds its bound; paginate exact event IDs"
            )
        selected.append(deepcopy(observed))
        grouped.setdefault((index["source_handle"], index["generation"]), []).append(
            observed
        )
    coverage, diagnostics, statuses = [], [], []
    for (handle, generation), events in grouped.items():
        source = extension["sources"][handle]
        candidates = [source] + source["history"]
        bound = next(
            (
                item
                for item in candidates
                if item["binding"]["generation"] == generation
            ),
            None,
        )
        if bound is None:
            raise ValueError(
                "source generation is missing from retained journal custody"
            )
        validation_events = events
        replay = source.get("replay", {})
        if (
            replay.get("status") == "complete"
            and generation != source["binding"]["generation"]
        ):
            if not all(event["event_id"] in replay["aliases"] for event in events):
                raise ValueError("retained event has no complete original replay proof")
            bound = source
            validation_events = [
                _replayed_event(event, bound["binding"]) for event in events
            ]
            if any(
                replay["aliases"][old["event_id"]] != new["event_id"]
                for old, new in zip(events, validation_events)
            ):
                raise ValueError(
                    "replay event alias differs from the current source generation"
                )
        if validation_events is not events:
            wanted = {event["event_id"] for event in events}
            for pair in extension["projection"]["pairs"].values():
                if pair["status"] in {
                    "duplicate",
                    "conflict",
                    "out_of_order",
                    "unlinked_generations",
                    "coverage_gap",
                } and wanted.intersection(
                    row["event_id"] for row in pair["calls"] + pair["results"]
                ):
                    raise ValueError(
                        "known native pair contradiction survives decoder replay"
                    )
        _admitted_source(context, handle, bound)
        interval = (
            required_interval.get(generation)
            if isinstance(required_interval, dict)
            else required_interval
        )
        verdict = native.revalidate_observations(
            bound["binding"],
            validation_events,
            projection=extension["projection"] if validation_events is events else None,
            required_interval=interval,
        )
        statuses.append(verdict["status"])
        coverage.append(
            {
                "source_handle": handle,
                "generation": generation,
                "mode": bound["binding"]["mode"],
                "qualification": deepcopy(bound["qualification"]),
                **verdict,
            }
        )
        diagnostics.extend(verdict.get("diagnostics", []))
    if _current_head(context) != head:
        statuses.append("unknown")
        diagnostics.append({"code": "journal_changed_during_source_consumption"})
    return {
        "schema_version": 1,
        "run_id": context["state"]["run_id"],
        "revision": context["state"]["revision"],
        "status": "invalid"
        if "invalid" in statuses
        else "unknown"
        if "unknown" in statuses
        else "current",
        "events": selected,
        "coverage": coverage,
        "diagnostics": diagnostics,
    }


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
    result = {
        "schema_version": 1,
        "run_id": state.get("run_id"),
        "revision": state.get("revision"),
        "source_handle": source_handle,
        "status": "unknown",
        "invalidations": [],
        "coverage": [],
        "diagnostics": [],
        "authority_granted": False,
        "pre_enrollment": "UNKNOWN",
        "historical_negative_coverage": "UNKNOWN",
        "scope": "retained invalidations and current unconsumed source tail",
        "producer_assumption": "cooperating native append-only producer; arbitrary edits to old benign bytes are not excluded",
    }
    try:
        read_admission_observation(context)
        head = _current_head(context)
        extension = _extension(state)
        source = extension["sources"].get(source_handle)
        if source is None:
            raise ValueError(
                "current native invalidation requires an admitted source enrollment"
            )
        _admitted_source(context, source_handle, source)
        if extension.get("invalidation_index_version") != 1:
            raise ValueError(
                "historical native invalidation index needs owner reconciliation"
            )
        if source.get("replay", {}).get("status") in {"pending", "failed"}:
            raise ValueError(
                "original enrolled interval replay is incomplete; negative coverage remains UNKNOWN"
            )
        if source.get("recovery") or source["cursor"]["first_gap"] is not None:
            raise ValueError(
                "native interval needs explicit source generation/gap reconciliation"
            )
        resolution = source.get("invalidation_resolution")
        if (
            source.get("reconciliation", {}).get("mode") == "interval"
            and not resolution
        ):
            raise ValueError(
                "new source interval retains an unresolved prior invalidation scope"
            )
        if resolution:
            if any(
                resolution["bindings"].get(key) != state[key]
                for key in ("run_id", "contract_digest", "profile_digest")
            ):
                raise ValueError("native resume binding changed")
            _admitted_source(
                context,
                source_handle,
                {
                    "binding": resolution["resume_binding"],
                    "qualification": source["qualification"],
                },
            )
            resume = native.revalidate_observations(
                resolution["resume_binding"], resolution["resume_events"]
            )
            if resume["status"] != "current":
                raise ValueError("native resume source is no longer current")
            result["acknowledged_prior_interval"] = deepcopy(
                resolution["prior_interval"]
            )
        binding = source["binding"]
        stream, info = native._open(binding["path"], binding)
        stream.close()
        if source.get("replay", {}).get("status") == "complete" and (
            _replay_stamp(info) != source["replay"]["snapshot"]
            or _replay_path_chain(binding["path"]) != source["replay"]["path_chain"]
        ):
            raise ValueError(
                "original replay snapshot changed; a new bounded replay is required"
            )
        if info.st_size < source["cursor"]["offset"]:
            raise ValueError("native source truncated behind the committed frontier")
        frontier = source["cursor"]["enrolled_from"]
        for witness in source.get("ranges", []):
            if witness["offset"] != frontier:
                raise ValueError(
                    "committed native page continuity has a skipped interval"
                )
            frontier += witness["length"]
        if frontier != source["cursor"]["offset"]:
            raise ValueError("committed native page witnesses do not reach the cursor")
        acknowledged = (
            set(resolution["prior_invalidation_ids"]) if resolution else set()
        )
        if resolution:
            acknowledged.update(
                event["event_id"] for event in resolution["resume_events"]
            )
        unresolved = [
            identity
            for identity, row in extension["invalidation_index"].items()
            if row["source_handle"] == source_handle and identity not in acknowledged
        ]
        if len(unresolved) > 512:
            raise ValueError(
                "unresolved invalidation witnesses exceed their bounded consumption scope"
            )
        if unresolved:
            retained = current_events(context, unresolved)
            if retained["status"] != "current":
                raise ValueError(
                    "retained native invalidation witness is no longer current"
                )
            result["invalidations"].extend(
                event
                for event in retained["events"]
                if not _accepted_rearm_message(context, event)
            )
        start = source["cursor"]["frame_start"]
        verdict = native.revalidate_observations(
            binding,
            [],
            required_interval=(start, info.st_size),
            max_bytes=MAX_INVALIDATION_BYTES,
            prior_sequence=source["cursor"]["last_sequence"],
        )
        result["coverage"].append(
            {
                "source_handle": source_handle,
                "generation": binding["generation"],
                "producer": deepcopy(binding["producer"]),
                "mode": binding["mode"],
                **{
                    key: value
                    for key, value in verdict.items()
                    if key not in {"events", "interval_events"}
                },
            }
        )
        result["diagnostics"].extend(verdict["diagnostics"])
        if (
            verdict["status"] != "current"
            or verdict["negative_coverage"] != "CURRENT_BOUNDED_INTERVAL"
            or not verdict["covers_through_source_snapshot"]
        ):
            return result
        for event in verdict["interval_events"]:
            # These native facts only revoke stale execution assumptions. User
            # text is never parsed into approvals or promoted to human identity.
            if _invalidates(event) and not _accepted_rearm_message(context, event):
                result["invalidations"].append(event)
        if _current_head(context) != head:
            raise ValueError(
                "native invalidation journal changed during current source read"
            )
        if source.get("replay", {}).get("status") == "complete":
            stream, after = native._open(binding["path"], binding)
            stream.close()
            if (
                _replay_stamp(after) != source["replay"]["snapshot"]
                or _replay_path_chain(binding["path"]) != source["replay"]["path_chain"]
            ):
                raise ValueError(
                    "original replay source changed during current invalidation consumption"
                )
        result["status"] = "invalidated" if result["invalidations"] else "clear"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["diagnostics"].append(
            {
                "code": "native_invalidation_unknown",
                "detail": str(exc)[:4096],
                "obligation": "reconcile the exact owner-bound interval before further execution",
            }
        )
    return result


def _accepted_rearm_message(context, event):
    """A committed re-arm resolves only its exact current native user message."""
    if (
        event["kind"] != "message.user"
        or event["native"]["source_handle"] != "root"
        or event["producer"]["thread_id"] != event["producer"]["root_session_id"]
    ):
        return False
    state = context["state"]
    store = state.get("extensions", {}).get("workflow_persistence", {})
    for rearm in store.get("rearms", []):
        source = store.get("sources", {}).get(rearm.get("event_id"), {})
        record = state.get("evidence", {}).get(source.get("receipt_id"), {})
        data = record.get("data", {})
        reference = data.get("source", {})
        if (
            source.get("criterion_id") is not None
            or record.get("kind") != "retry_clearance"
            or rearm.get("source_digest") != record.get("digest")
            or reference.get("kind") != "native-user"
            or reference.get("message_id") != event["native"].get("record_id")
            or data.get("approved") is not True
        ):
            continue
        try:
            from native_review import _user

            run_state._artifact(
                context["project"], state["artifacts"][record["artifact_id"]]
            )
            binding = _extension(state)["sources"][event["native"]["source_handle"]][
                "binding"
            ]
            ref = event["native"]
            stream, info = native._open(binding["path"], binding)
            with stream:
                raw = native._stable_read(
                    stream,
                    binding["path"],
                    ref["offset"],
                    ref["length"],
                    (binding["device"], binding["inode"]),
                    info.st_size,
                )
            if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                return False
            expected = {
                "schema_version": 1,
                "kind": "retry_clearance",
                "bindings": {
                    key: state[key]
                    for key in ("run_id", "contract_digest", "profile_digest")
                },
                "data": {key: value for key, value in data.items() if key != "source"},
            }
            return (
                _user(
                    [native._json(raw)], reference, read_admission_observation(context)
                )
                == expected
            )
        except (OSError, ValueError, KeyError, TypeError):
            return False
    return False


def current_muse_page(context, source_handle, message, connection_binding, locators):
    """Fresh owner admission plus current raw ranges; page JSON stays a hint."""
    read_admission_observation(context)
    head = _current_head(context)
    source = _extension(context["state"])["sources"].get(source_handle)
    if source is None:
        raise ValueError("page source is not enrolled")
    _admitted_source(context, source_handle, source)
    if not isinstance(locators, dict) or any(
        not isinstance(row, dict)
        or type(row.get("offset")) is not int
        or row["offset"] < source["cursor"]["enrolled_from"]
        for row in locators.values()
    ):
        raise ValueError(
            "page ranges precede enrolled scope; explicit historical reconciliation required"
        )
    result = native.revalidate_muse_page(
        source["binding"], message, connection_binding, locators
    )
    if head != _current_head(context):
        raise ValueError("journal changed during page reconciliation")
    return {
        **result,
        "run_id": context["state"]["run_id"],
        "revision": context["state"]["revision"],
    }


def _prepare_page(context, payload):
    _fields(
        payload,
        {
            "source_handle",
            "message",
            "connection_binding",
            "locators",
            "task_id",
            "attempt_id",
        },
    )
    checked = current_muse_page(
        context,
        payload["source_handle"],
        payload["message"],
        payload["connection_binding"],
        payload["locators"],
    )
    # The ordinary source reader is the only cursor owner. Wire cursors cannot
    # skip source bytes, reset a generation, or turn unknown history into clear.
    prepared = _prepare_observe(
        context,
        {
            "source_handle": payload["source_handle"],
            "through_event": None,
            "task_id": payload["task_id"],
            "attempt_id": payload["attempt_id"],
        },
    )
    prepared["batch"]["page_reconciliation"] = {
        key: value for key, value in checked.items() if key != "raw_events"
    }
    return prepared


# Historical qualification is derived evidence in the current run. It does not
# replace native_observations, import a budget, or create successor ancestry.
def validate_historical_subject(subject):
    _fields(subject, {"run_id", "revision", "event_digest", "state_digest", "source_handle", "source_digest"})
    run_state._uuid(subject["run_id"])
    if type(subject["revision"]) is not int or not 1 <= subject["revision"] <= run_state.MAX_EVENTS:
        raise ValueError("historical subject revision exceeds owner bound")
    if subject["source_handle"] != "root":
        raise ValueError("historical qualification requires the exact native root")
    for key in ("event_digest", "state_digest", "source_digest"):
        if not isinstance(subject[key], str) or re.fullmatch(r"[0-9a-f]{64}", subject[key]) is None:
            raise ValueError("historical subject requires exact journal and source digests")


def _history_limits(value):
    _fields(value, {"steps", "bytes", "sources", "wall_millis"})
    caps = {"steps": 4096, "bytes": 16 * 1024**3, "sources": 64, "wall_millis": 900000}
    if any(type(value[key]) is not int or not 1 <= value[key] <= caps[key] for key in caps):
        raise ValueError("historical validation requires finite owner limits")
    return deepcopy(value)


def _history_tick(record):
    if run_state._time(run_state._now()) >= run_state._time(record["deadline"]):
        raise ValueError("historical validation original deadline exhausted")


def _history_head(context, subject, *, record=None):
    """Existing journal owner proves history once; exact file witnesses fence it.

    Subsequent pages rehash the selected logical head and recheck the complete
    physical journal membership captured around the original full chain replay.
    No source-selected cache or caller attestation is accepted as authority.
    """
    import time
    project = context["project"]
    if subject["run_id"] == context["state"]["run_id"]:
        raise ValueError("historical subject must be a distinct closed interval")
    until = time.monotonic() + run_state.MAX_SUCCESSOR_SECONDS
    if record is None:
        witness_state = {"run_id": subject["run_id"]}
        witnesses = run_state._successor_journal_witnesses(project, [witness_state], until)
        last, consumed = None, 0
        for event in run_state._events(project, subject["run_id"]):
            run_state._successor_tick(until)
            consumed += len(run_state._json(event))
            if consumed > context["history_byte_limit"]:
                raise ValueError("historical journal exceeds admitted validation byte ceiling")
            last = event
        if last is None:
            raise ValueError("historical subject has no journal head")
    else:
        witnesses = record["journal_witnesses"]
        run_state._successor_recheck_files(project, {k: tuple(v) for k, v in witnesses.items()}, until)
        last = _journal_event(project, subject["run_id"], subject["revision"])
        consumed = len(run_state._json(last))
    state = last["state"]
    read_admission_observation(context)
    if (state["revision"] != subject["revision"] or last["digest"] != subject["event_digest"]
            or run_state._digest(state) != subject["state_digest"]
            or state["status"] not in run_state.TERMINAL
            or state["project_id"] != context["state"]["project_id"]
            or state["owner"]["project_root"] != str(Path(project).resolve())):
        raise ValueError("historical subject differs from exact closed same-project journal")
    source = _extension(state)["sources"].get("root")
    if source is None or native._digest(source) != subject["source_digest"]:
        raise ValueError("historical subject source custody changed")
    run_state._successor_recheck_files(project, {k: tuple(v) for k, v in witnesses.items()}, until)
    return state, witnesses, consumed, len(run_state._json(last))


def _historical_enrollment(context, subject_state, old):
    # Identity comes from the already authenticated historical journal and its
    # actual header, not from whichever client is currently validating it.
    read_admission_observation(context)
    binding = old["binding"]
    producer = binding["producer"]
    original = old["qualification"]
    if original["native_ref"] != subject_state["owner"]["native_ref"]:
        raise ValueError("historical source is not bound to its own admitted owner")
    current, cursor = native.enroll_source(
        binding["path"], client=producer["client"],
        expected_root_session_id=producer["root_session_id"],
        expected_thread_id=producer["thread_id"],
        expected_parent_thread_id=producer.get("parent_thread_id"),
        expected_agent_id=producer.get("agent_id"), source_handle="root",
        mode=binding["mode"], start_offset=old["enrollment"]["offset"],
        source_epoch=binding.get("source_epoch"),
        dialect=producer.get("dialect"), invocation_id=producer.get("invocation_id"))
    return {"binding": current, "cursor": cursor, "coverage": None,
        "history": [], "ranges": [],
        "enrollment": {"generation": current["generation"], "offset": old["enrollment"]["offset"],
            "anchor": None, "digest": native._digest([current["generation"], old["enrollment"]["offset"], None])},
        "qualification": {**deepcopy(original),
            "source_identity": "exact historical journal enrollment and current header; not current authority",
            "external_native_acceptance": "UNKNOWN"}}


def _historical_frontier(source):
    cursor = source["cursor"]
    offset = cursor["offset"]
    if cursor["frame_start"] == offset:
        return offset, 0
    binding = source["replay"]["fresh"]["binding"]
    maximum = cursor["frame_start"] + native.MAX_STREAM_SPAN_BYTES
    charged = 0
    stream, info = native._open(binding["path"], binding)
    with stream:
        while offset < min(maximum, info.st_size):
            raw = native._stable_read(stream, binding["path"], offset,
                min(MAX_REPLAY_PAGE_BYTES, maximum - offset, info.st_size - offset),
                (binding["device"], binding["inode"]), info.st_size)
            charged += len(raw)
            boundary = raw.find(b"\n")
            if boundary >= 0:
                return offset + boundary + 1, charged
            offset += len(raw)
    raise ValueError("historical pending record is incomplete or exceeds the supported span bound")


def _history_source_fence(record):
    source = record["source"]
    replay = source["replay"]
    binding = replay.get("fresh", source)["binding"]
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
    if (_replay_stamp(info) != replay["snapshot"]
            or _replay_path_chain(binding["path"]) != replay["path_chain"]):
        raise ValueError("historical source changed during its bounded snapshot")


def _prepare_history(context, payload):
    from datetime import timedelta
    import time
    _fields(payload, {"subject", "limits"})
    subject = payload["subject"]
    validate_historical_subject(subject)
    limits = _history_limits(payload["limits"])
    identity = native._digest(subject)
    records = context["state"].get("extensions", {}).get("native_history", {})
    record = deepcopy(records.get(identity))
    if record is not None:
        if record["current_run_id"] != context["state"]["run_id"]:
            raise ValueError("inherited historical validation is not current-run admission")
        if record["subject"] != subject or record["limits"] != limits:
            raise ValueError("historical request cannot reset its original allowance")
        _history_tick(record)
        if record["status"] != "pending":
            raise ValueError("historical validation is terminal; retained result is not a fresh admission")
        # Refuse known exhaustion before reopening any historical source or
        # journal. A changed caller request cannot refill this stored allowance.
        page_cost = replay_read_ceiling(record["source"], historical=True)
        if (record["steps"] >= limits["steps"] or record["validation_bytes_charged"]
                + record["journal_page_bytes"] + page_cost > limits["bytes"]):
            raise ValueError("historical validation original finite allowance exhausted")
    elif len(records) >= MAX_SOURCES:
        raise ValueError("historical subject capacity exhausted")
    old, witnesses, journal_bytes, journal_page_bytes = _history_head(
        {**context, "history_byte_limit": limits["bytes"]}, subject, record=record)
    old_source = _extension(old)["sources"]["root"]
    shadow = {**context, "state": old}
    if record is None:
        now = run_state._time(context["now"])
        budget_deadline = context["state"].get("extensions", {}).get("workflow", {}).get("budget", {}).get("deadline")
        if budget_deadline is None:
            raise ValueError("historical validation requires current admitted resource deadline")
        deadline = min(now + timedelta(milliseconds=limits["wall_millis"]), run_state._time(budget_deadline))
        fresh = _historical_enrollment(context, old, old_source)
        prepared = _begin_replay(shadow, "root", old_source, fresh, historical=True)
        frontier, scanned = _historical_frontier(prepared["source"])
        record = {"schema_version": 1, "subject": deepcopy(subject), "limits": limits,
            "qualified_frontier": frontier,
            "coverage_scope": "original consumed interval plus only its pending record; later tail unqualified",
            "current_run_id": context["state"]["run_id"],
            "contract_digest": context["state"]["contract_digest"],
            "profile_digest": context["state"]["profile_digest"],
            "owner_native_ref": read_admission_observation(context)["native_ref"],
            "subject_terminal": deepcopy(old.get("terminal")),
            "subject_deadline": old.get("extensions", {}).get("workflow", {}).get("budget", {}).get("deadline"),
            "subject_budget_digest": native._digest(old.get("extensions", {}).get("workflow", {}).get("budget")),
            "prior_invalidation_count": len(_extension(old)["invalidation_index"]),
            "prior_invalidation_digest": native._digest(_extension(old)["invalidation_index"]),
            "journal_page_bytes": journal_page_bytes,
            "journal_witnesses": {key: list(value) for key, value in witnesses.items()}, "source": prepared["source"],
            "derived_projection": native.empty_projection(), "derived_invalidation_ids": [],
            "status": "pending", "stage": "original", "steps": 0,
            "validation_bytes_charged": 0, "started_at": context["now"],
            "deadline": deadline.isoformat(), "authority_granted": False,
            "effects_replayed": False, "native_acceptance": "UNKNOWN",
            "negative_coverage": "UNKNOWN", "pre_enrollment": "UNKNOWN"}
        page_cost = 6 * native.MAX_HEADER_BYTES + 2 * scanned
    else:
        if any(record[key] != context["state"][key] for key in ("contract_digest", "profile_digest")):
            raise ValueError("historical qualification current contract/profile changed")
        _history_source_fence(record)
        source = record["source"]
        page_cost = replay_read_ceiling(source, historical=True)
        if record["steps"] >= limits["steps"] or record["validation_bytes_charged"] + journal_bytes + page_cost > limits["bytes"]:
            raise ValueError("historical validation original finite allowance exhausted")
        prepared = _prepare_replay_page(shadow, "root", source)
        source, batch = prepared["source"], prepared["batch"]
        if batch is not None:
            record["derived_projection"] = native.reduce_observations(record["derived_projection"], batch)
            for event in batch["events"]:
                if _invalidates(event) and event["event_id"] not in record["derived_invalidation_ids"]:
                    record["derived_invalidation_ids"].append(event["event_id"])
        source = _promote_replay_source(source, context["state"]["revision"] + 1)
        if source["replay"]["status"] == "complete":
            # Finish the exact captured physical tail, including a partial old
            # frame, without mutating old cursor/history or current native root.
            if record["stage"] == "original" and source["cursor"]["offset"] < record["qualified_frontier"]:
                source = _begin_refresh(shadow, "root", source, source)["source"]
                source["replay"]["frontier"] = record["qualified_frontier"]
                record["stage"] = "pending-record"
            else:
                record["status"] = "complete"
        elif source["replay"]["status"] == "failed":
            record["status"] = "failed"
        record["source"] = source
    if record["validation_bytes_charged"] + journal_bytes + page_cost > limits["bytes"]:
        raise ValueError("historical validation original finite allowance exhausted")
    record["steps"] += 1
    record["validation_bytes_charged"] += journal_bytes + page_cost
    record["invalidation_status"] = "invalidated" if record["prior_invalidation_count"] or record["derived_invalidation_ids"] else "UNKNOWN"
    record["owner_revision"] = context["state"]["revision"] + 1
    _history_tick(record)
    _history_source_fence(record)
    run_state._successor_recheck_files(context["project"], {k: tuple(v) for k, v in witnesses.items()}, time.monotonic() + 5)
    return {"identity": identity, "record": record}


def _reduce_history(state, prepared, context):
    result = deepcopy(state)
    result["extensions"].setdefault("native_history", {})[prepared["identity"]] = deepcopy(prepared["record"])
    return result


def _history_constraint(state, command, payload, context):
    if command != "native.history":
        return
    import time
    record = state["extensions"]["native_history"][native._digest(payload["subject"])]
    _history_tick(record)
    _history_source_fence(record)
    run_state._successor_recheck_files(Path(state["owner"]["project_root"]),
        {k: tuple(v) for k, v in record["journal_witnesses"].items()}, time.monotonic() + 5)


def register(engine):
    engine.register_command("native.history", _reduce_history)
    engine.register_preparer("native.history", _prepare_history)
    engine.register_constraint("native-historical-custody", _history_constraint)
    engine.register_command("native.page", _reduce_observe, terminal_safe=True)
    engine.register_preparer("native.page", _prepare_page)
    engine.register_command("native.enroll", _reduce_enroll)
    engine.register_preparer("native.enroll", _prepare_enroll)
    engine.register_command("native.observe", _reduce_observe, terminal_safe=True)
    engine.register_preparer("native.observe", _prepare_observe)
    engine.register_command("native.reconcile", _reduce_enroll)
    engine.register_preparer("native.reconcile", _prepare_reconcile)

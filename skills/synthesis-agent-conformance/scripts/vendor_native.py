#!/usr/bin/env python3
"""Consume admitted Claude stream or Codex ephemeral callback evidence.

The existing native-worker owner authenticates captured protocol, exact registry
outcome and current installed/source bytes. This does not prove desktop loading,
all-hook coverage, recovery, vendor certification or permission to contact
anybody. PM/journal integrity assumes cooperating admitted host writers, not a
hostile same-UID filesystem editor. Local JSON, portable signatures and generic
worker success alone are insufficient."""

from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys

PREFIX = "SYNTHESIS_NATIVE_RECEIPT "
MAX_AGE_SECONDS = 300
SELECTION_FIELDS = {
    "project",
    "run_id",
    "actor",
    "source_handle",
    "source_generation",
    "event_ids",
    "registry_latest",
}


def _owner_imports():
    skills = Path(__file__).resolve().parents[2]
    for name in ("synthesis-autopilot", "synthesis-onboarding"):
        directory = str(skills / name / "scripts")
        if directory not in sys.path:
            sys.path.insert(0, directory)


def callback_witness(record, latest):
    from live_receipt import callback_witness as issue

    return issue(record, latest)


def _witness(stdout):
    from signed_receipt import strict_json

    if not isinstance(stdout, str) or len(stdout.encode("utf-8")) > 64 * 1024:
        raise ValueError("native callback output is missing or exceeds its bound")
    envelope = strict_json(stdout.encode("utf-8"))
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"continue", "hookSpecificOutput"}
        or envelope["continue"] is not True
    ):
        raise ValueError(
            "native callback envelope is not a successful context delivery"
        )
    specific = envelope["hookSpecificOutput"]
    if (
        not isinstance(specific, dict)
        or set(specific) != {"hookEventName", "additionalContext"}
        or specific["hookEventName"] != "SessionStart"
        or not isinstance(specific["additionalContext"], str)
    ):
        raise ValueError("native callback event is not SessionStart")
    return _context_witness(specific["additionalContext"])


def _context_witness(text):
    from signed_receipt import strict_json

    if not isinstance(text, str) or len(text.encode("utf-8")) > 64 * 1024:
        raise ValueError("delivered callback context exceeds its bound")
    lines = text.splitlines()
    matches = [line for line in lines if line.startswith(PREFIX)]
    if len(matches) != 1 or not lines or matches[0] != lines[-1]:
        raise ValueError("native callback lacks one final registry witness")
    witness = strict_json(matches[0][len(PREFIX) :].encode("utf-8"))
    if (
        not isinstance(witness, dict)
        or set(witness) != {"event_id", "sha256"}
        or not isinstance(witness["sha256"], str)
        or not re.fullmatch("[0-9a-f]{64}", witness["sha256"])
    ):
        raise ValueError("native callback registry witness is invalid")
    return witness


def _claude_witness(events, rows):
    start, response, terminal = events
    a, b = start["data"], response["data"]
    if (
        start["kind"] != "runtime.hook"
        or response["kind"] != "runtime.hook"
        or a.get("native_subtype") != "hook_started"
        or b.get("native_subtype") != "hook_response"
        or not isinstance(a.get("hook_id"), str)
        or not a["hook_id"]
        or a["hook_id"] != b.get("hook_id")
        or not isinstance(a.get("hook_name"), str)
        or not a["hook_name"]
        or a["hook_name"] != b.get("hook_name")
        or a.get("hook_event") != "SessionStart"
        or b.get("hook_event") != "SessionStart"
        or type(b.get("exit_code")) is not int
        or b["exit_code"] != 0
        or b.get("outcome") != "success"
        or terminal["kind"] != "lifecycle.completed"
        or terminal["status"] != "observed"
        or terminal["data"].get("is_error") is not False
        or terminal["data"].get("native_status") != "success"
    ):
        raise ValueError(
            "native callback/terminal outcomes do not prove a successful paired SessionStart"
        )
    callbacks = [
        r
        for r in rows
        if r.get("type") == "system"
        and r.get("hook_id") == a["hook_id"]
        and r.get("subtype") in {"hook_started", "hook_response"}
    ]
    terminals = [r for r in rows if r.get("type") == "result"]
    if (
        len(callbacks) != 2
        or len(terminals) != 1
        or [r.get("uuid") for r in callbacks]
        != [start["native"]["record_id"], response["native"]["record_id"]]
        or terminals[0].get("uuid") != terminal["native"]["record_id"]
    ):
        raise ValueError("native callback or terminal is duplicated/ambiguous")
    return _witness(b.get("stdout"))


def _codex_witness(events, rows, sid, plugin, dialect="codex.app_server_callback"):
    import native_codex

    sessions = [e for e in events if e["kind"] == "session.started"]
    if len(sessions) != 1:
        raise ValueError(
            "Codex callback requires one actual ephemeral session response"
        )
    response = sessions[0]["data"].get("response")
    if not isinstance(response, dict):
        raise ValueError("Codex callback session response is malformed")
    binding = {
        "producer": {"client": "codex", "thread_id": sid, "root_session_id": sid},
        "dialect": dialect,
        "mode": "native",
        "callback_thread": response.get("thread"),
    }
    native_codex.callback_thread(binding["callback_thread"], binding["producer"])
    facts = [f for row in rows for f in native_codex.decode_wire(row, binding)]
    starts = [
        e
        for e in events
        if e["kind"] == "runtime.hook"
        and e["data"].get("native_subtype") == "hook_started"
        and e["data"].get("hook_event") == "SessionStart"
    ]
    ends = [
        e
        for e in events
        if e["kind"] == "runtime.hook"
        and e["data"].get("native_subtype") == "hook_response"
        and e["data"].get("hook_event") == "SessionStart"
    ]
    if len(starts) != 1 or len(ends) != 1 or len(sessions) != 1:
        raise ValueError(
            "Codex requires its paired callback and actual ephemeral session response"
        )
    a, b = starts[0]["data"], ends[0]["data"]
    if (
        a.get("hook_id") != b.get("hook_id")
        or a.get("hook_event") != "SessionStart"
        or b.get("outcome") != "completed"
        or a.get("source") != "plugin"
        or a.get("source_path") != str(plugin / "hooks/hooks.json")
        or b.get("source_path") != a.get("source_path")
        or starts[0]["status"] != "observed"
        or ends[0]["status"] != "observed"
        or sessions[0]["data"].get("callback_only")
        is not (dialect != "codex.app_server_managed_turn")
    ):
        raise ValueError("Codex callback is not the selected installed plugin context")
    pair = [
        f
        for f in facts
        if f["kind"] == "runtime.hook" and f["data"]["hook_id"] == a["hook_id"]
    ]
    if len(pair) != 2 or pair[0]["data"] != a or pair[1]["data"] != b:
        raise ValueError(
            "Codex callback selection differs from complete native transport"
        )
    context = [e["text"] for e in b["entries"] if e["kind"] == "context"]
    if len(context) != 1 or any(e["kind"] in {"error", "stop"} for e in b["entries"]):
        raise ValueError("Codex did not deliver one successful callback context")
    # No stdout/exit status is synthesized: this is native delivered context.
    return _context_witness(context[0])


def _current(root, client, entry, version, inventory, selection):
    from signed_receipt import canonical_path, read_regular, strict_json, instant
    from live_receipt import receipt_event_path
    from vendor_bundle import source_inventory, digest
    import autopilot
    from system_contract import canonical_tree_digest, verify_native_release_inventory

    if not isinstance(selection, dict) or set(selection) != SELECTION_FIELDS:
        raise ValueError(
            "native selection requires exact existing project/run/actor/source/event custody"
        )
    ids = selection["event_ids"]
    if (
        not isinstance(ids, list)
        or not 3 <= len(ids) <= 256
        or any(not isinstance(x, str) for x in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError(
            "native selection requires three distinct callback/terminal events"
        )
    project = canonical_path(selection["project"])
    root, plugin = canonical_path(root), canonical_path(entry["plugin_root"])
    receipt_path = canonical_path(entry["receipt"])
    runtime = autopilot.engine()
    state = runtime.load_run(project, selection["run_id"])
    context = runtime.inspect_context(state, selection["actor"], project=project)
    selected = context["current_native_events"](ids)
    handle = selection["source_handle"]
    source = (
        state.get("extensions", {})
        .get("native_observations", {})
        .get("sources", {})
        .get(handle)
    )
    if (
        not isinstance(handle, str)
        or not handle.startswith("worker:")
        or not source
        or source["binding"]["generation"] != selection["source_generation"]
        or source["binding"]["mode"] != "native"
        or source["binding"]["producer"]["client"] != client
        or selected["status"] != "current"
        or len(selected["coverage"]) != 1
        or selected["coverage"][0]["generation"] != selection["source_generation"]
        or selected["coverage"][0]["source_handle"] != handle
        or selected["coverage"][0]["qualification"]["discovery"].get("kind")
        != "owner-issued-native-worker"
    ):
        raise ValueError(
            "native callback is not in the current admitted worker generation"
        )
    child = state["extensions"]["workflow"]["children"].get(
        handle.removeprefix("worker:")
    )
    if (
        not child
        or child["worker_observation"]["client"] != client
        or child["worker_observation"]["terminal"] != "completed"
        or child["worker_observation"]["boundary"]["status"] != "ENFORCED"
    ):
        raise ValueError(
            "native worker execution or permission boundary is not qualified"
        )
    productive = (
        client == "codex"
        and source["binding"]["producer"].get("dialect")
        == "codex.app_server_managed_turn"
    )
    if productive:
        proof = child["worker_observation"]["boundary"]
        if (
            child.get("required_capabilities")
            in (["native-callback"], ["native-permission-probe"])
            or proof.get("protocol") != "codex-managed-probe-turn-v1"
        ):
            raise ValueError(
                "Managed productive evidence lacks its actual same-connection protection"
            )
    if (
        client == "codex"
        and not productive
        and (
            (
                child.get("required_capabilities"),
                source["binding"]["producer"].get("dialect"),
            )
            not in (
                (["native-callback"], "codex.app_server_callback"),
                (["native-callback"], "codex.app_server_managed"),
                (["native-permission-probe"], "codex.app_server_managed"),
            )
        )
    ):
        raise ValueError(
            "Codex candidate requires the admitted ephemeral callback capability"
        )
    # The bridge revalidates the actual launch/prompt/raw/result files through
    # its registered native_worker evidence verifier. Never trust this shape
    # without that preceding current_native_events owner invocation.
    coverage = source["coverage"]
    if (
        not coverage
        or source["cursor"]["first_gap"] is not None
        or coverage["pending_bytes"] != 0
        or coverage["backlog_bytes"] != 0
        or source["cursor"]["trusted_through"] != source["cursor"]["offset"]
    ):
        raise ValueError("native callback source is only partially observed")
    events = sorted(selected["events"], key=lambda e: e["native"]["offset"])
    sid = source["binding"]["producer"]["thread_id"]
    if any(
        e["mode"] != "native"
        or e["producer"]["client"] != client
        or e["producer"]["thread_id"] != sid
        or e["native"]["source_handle"] != handle
        for e in events
    ):
        raise ValueError(
            "callback events mix sessions, source handles or evidence planes"
        )
    # Re-read every captured frame so selecting affirmative events cannot hide
    # a contradictory or duplicate callback elsewhere in the same generation.
    from native_review import _json

    raw_stream = read_regular(Path(source["binding"]["path"]), limit=16 * 1024 * 1024)
    if not raw_stream.endswith(b"\n") or len(raw_stream) != source["cursor"]["offset"]:
        raise ValueError("native stream custody is incomplete")
    rows = [_json(line) for line in raw_stream.splitlines()]
    witness = (
        _codex_witness(
            events, rows, sid, plugin, source["binding"]["producer"]["dialect"]
        )
        if client == "codex"
        else _claude_witness(events, rows)
    )
    if productive:
        from native_codex_turn import transcript

        proof = child["worker_observation"]["boundary"]
        if proof.get("thread_id") != sid:
            raise ValueError("Productive protection belongs to another native session")
        terminal = transcript(rows, sid, proof.get("turn_id"))
        starts = [e for e in events if e["kind"] == "lifecycle.started"]
        ends = [e for e in events if e["kind"] == "lifecycle.completed"]
        if (
            terminal["status"] != "completed"
            or len(starts) != 1
            or len(ends) != 1
            or any(
                e["data"].get("turn_id") != proof.get("turn_id") for e in starts + ends
            )
            or starts[0]["native"]["offset"] >= ends[0]["native"]["offset"]
            or ends[0]["data"].get("native_status") != "completed"
        ):
            raise ValueError(
                "Selected evidence omits or contradicts the actual productive turn"
            )
    elif len(ids) != 3:
        raise ValueError(
            "Callback-only evidence requires its exact three context events"
        )
    raw = read_regular(receipt_path)
    receipt = strict_json(raw)
    if not isinstance(receipt, dict):
        raise ValueError("native registry outcome is invalid")
    expected_path = receipt_event_path(
        canonical_path(selection["registry_latest"]),
        client=client,
        session_id=sid,
        event_id=witness["event_id"],
    )
    if (
        receipt_path != expected_path
        or hashlib.sha256(raw).hexdigest() != witness["sha256"]
        or receipt.get("receipt_schema") != 2
        or type(receipt.get("receipt_schema")) is not int
        or receipt.get("client") != client
        or receipt.get("session_id") != sid
        or receipt.get("receipt_event_id") != witness["event_id"]
        or receipt.get("hook_event_name") != "SessionStart"
        or receipt.get("context_outcome") != "INJECTED"
        or (
            receipt.get("provenance_env") != client + "-transcript"
            and not (
                client == "codex"
                and receipt.get("provenance_env") == "codex-callback-candidate"
                and receipt.get("callback_candidate") is True
                and receipt.get("transcript_path") in (None, "")
                and receipt.get("transcript_bound_at_record") is False
            )
        )
        or receipt.get("plugin_version") != version
        or canonical_path(receipt.get("plugin_root")) != plugin
    ):
        raise ValueError("native callback registry/source identity differs")
    now = datetime.now(timezone.utc)
    times = [receipt.get("recorded_at"), *(e.get("ingested_at") for e in events)]
    if any(
        not 0 <= (now - instant(t)).total_seconds() <= MAX_AGE_SECONDS for t in times
    ):
        raise ValueError("native callback evidence is stale or future dated")
    from live_receipt import callback_generation

    if receipt.get("callback_generation") != callback_generation(
        plugin, receipt.get("execution_root")
    ):
        raise ValueError(
            "native callback source/install generation no longer matches its emitted receipt"
        )
    initial_source = source_inventory(root)
    if initial_source != inventory:
        raise ValueError("native source generation changed before qualification")
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        if strict_json(read_regular(root / manifest)).get("version") != version:
            raise ValueError("selected native version differs from source manifests")
    source_digest = canonical_tree_digest(root)
    installation_digest = verify_native_release_inventory(plugin, root, source_digest)
    execution = canonical_path(receipt.get("execution_root"))
    if verify_native_release_inventory(execution, root, source_digest) != source_digest:
        raise ValueError("native callback execution bytes differ from source")
    # A currently valid callback cannot be used after a registry, source,
    # installation, claim or journal mutation during consumption.
    if read_regular(receipt_path) != raw or source_inventory(root) != initial_source:
        raise ValueError("native evidence changed during consumption")
    if (
        verify_native_release_inventory(plugin, root, source_digest)
        != installation_digest
    ):
        raise ValueError("native installation changed during consumption")
    if verify_native_release_inventory(execution, root, source_digest) != source_digest:
        raise ValueError("native execution tree changed during consumption")
    final = runtime.load_run(project, state["run_id"])
    if final != state:
        raise ValueError("native journal changed during consumption")
    reread = runtime.inspect_context(final, selection["actor"], project=project)[
        "current_native_events"
    ](ids)
    if (
        reread["status"] != "current"
        or reread["events"] != selected["events"]
        or [
            (c["source_handle"], c["generation"], c["qualification"])
            for c in reread["coverage"]
        ]
        != [
            (c["source_handle"], c["generation"], c["qualification"])
            for c in selected["coverage"]
        ]
    ):
        raise ValueError(
            "native admission or observed bytes changed during consumption"
        )
    final_now = datetime.now(timezone.utc)
    if any(
        not 0 <= (final_now - instant(t)).total_seconds() <= MAX_AGE_SECONDS
        for t in times
    ):
        raise ValueError("native callback evidence expired during qualification")
    return {
        "status": "PASS",
        "scope": "admitted-managed-protected-foreground-turn"
        if productive
        else "admitted-ephemeral-callback-context"
        if client == "codex"
        else "admitted-cli-session-start-context",
        "model_turn_completed": True
        if productive
        else False
        if client == "codex"
        else "NOT_ASSESSED",
        "native_recovery": "UNKNOWN",
        "client": client,
        "session_id": sid,
        "event_id": witness["event_id"],
        "receipt_sha256": witness["sha256"],
        "source_sha256": source_digest,
        "installation_sha256": installation_digest,
        "source_inventory_sha256": digest(inventory),
        "source_generation": selection["source_generation"],
        "journal_revision": state["revision"],
        "action_authorized": False,
        "desktop_live_loading": "UNKNOWN",
        "all_hooks": "UNKNOWN",
    }


def current_callback(root, client, entry, version, inventory, selection):
    """Fresh owner readback. Unsupported dialects do not acquire evidence."""
    if client not in {"claude", "codex", "hermes"}:
        return {
            "status": "UNKNOWN",
            "reason": "No accepted callback-result grammar for this client",
            "action_authorized": False,
        }
    _owner_imports()
    try:
        if client == "hermes":
            from vendor_hermes import current
            return current(root, entry, version, inventory, selection)
        return _current(root, client, entry, version, inventory, selection)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        ImportError,
        RuntimeError,
    ) as exc:
        return {
            "status": "UNKNOWN",
            "reason": str(exc)[:400],
            "action_authorized": False,
        }

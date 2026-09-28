"""Existing vendor consumer's admitted Hermes context-only qualification.

No local observation, signature, SQLite row or caller PASS is sufficient.
The current PM journal authenticates the worker/capture; installed source and
registry candidate are joined to the actual native assembled-request callback.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path


def current(root, entry, version, inventory, selection):
    import autopilot
    import hermes_transport
    from signed_receipt import canonical_path, read_regular, strict_json, instant
    from vendor_native import SELECTION_FIELDS, MAX_AGE_SECONDS
    from vendor_bundle import source_inventory, digest
    from system_contract import canonical_tree_digest, verify_native_release_inventory
    from live_receipt import callback_generation, hermes_source_binding

    if not isinstance(selection, dict) or set(selection) != SELECTION_FIELDS:
        raise ValueError("exact existing PM selection required")
    ids = selection["event_ids"]
    if not isinstance(ids, list) or len(ids) != 2 or len(set(ids)) != 2:
        raise ValueError("exact producer and consumer events required")
    root = canonical_path(root)
    plugin = canonical_path(entry["plugin_root"])
    project = canonical_path(selection["project"])
    runtime = autopilot.engine()
    state = runtime.load_run(project, selection["run_id"])
    context = runtime.inspect_context(state, selection["actor"], project=project)
    selected = context["current_native_events"](ids)
    handle = selection["source_handle"]
    sources = (
        state.get("extensions", {}).get("native_observations", {}).get("sources", {})
    )
    source = sources.get(handle)
    if (
        not isinstance(handle, str)
        or not handle.startswith("worker:")
        or not source
        or selected["status"] != "current"
        or len(selected["coverage"]) != 1
        or source["binding"]["generation"] != selection["source_generation"]
        or source["binding"]["mode"] != "native"
        or source["binding"]["producer"]["client"] != "hermes"
        or selected["coverage"][0]["qualification"]["discovery"].get("kind")
        != "owner-issued-native-worker"
    ):
        raise ValueError("Hermes source lacks current admitted transport custody")
    child = state["extensions"]["workflow"]["children"][handle.removeprefix("worker:")]
    observation = child["worker_observation"]
    if (
        child["required_capabilities"] != [hermes_transport.CAPABILITY]
        or observation["terminal"] != "completed"
        or observation.get("model_turns_started") != 0
        or observation["boundary"]["status"] != "UNKNOWN"
        or observation["boundary"]["mechanism"] != "hermes-local-peer-observation"
    ):
        raise ValueError(
            "Hermes capture cannot substitute execution or permission claims"
        )
    coverage, cursor = source["coverage"], source["cursor"]
    if (
        not coverage
        or coverage["pending_bytes"]
        or coverage["backlog_bytes"]
        or cursor["first_gap"] is not None
        or cursor["offset"] != cursor["trusted_through"]
    ):
        raise ValueError("Hermes source coverage is partial")
    wire = read_regular(
        Path(source["binding"]["path"]), limit=hermes_transport.MAX_CAPTURE
    )
    if not wire.endswith(b"\n") or len(wire) != cursor["offset"]:
        raise ValueError("Hermes transport bytes are incomplete")
    # Native transport records follow the admitted native JSON bound; the
    # smaller signed-receipt bound remains for registry/receipt metadata.
    rows = [hermes_transport._json(line) for line in wire.splitlines()]
    receipt_manifest = strict_json(read_regular(Path(observation["receipt_path"])))
    chosen = receipt_manifest["configuration"]["selection"]
    witness = hermes_transport.validate_pair(rows[1:], chosen)
    events = sorted(selected["events"], key=lambda e: e["native"]["offset"])
    if any(
        e["mode"] != "native"
        or e["producer"]["client"] != "hermes"
        or e["producer"]["thread_id"] != chosen["session_id"]
        or e["native"]["source_handle"] != handle
        for e in events
    ):
        raise ValueError("mixed native identity or evidence planes")
    if [e["data"].get("observation") for e in events] != rows[1:]:
        raise ValueError("selected events differ from complete native consumer pair")
    state_home = canonical_path(chosen["state_home"])
    # registry_latest selects the existing registry root, never an arbitrary file.
    if canonical_path(selection["registry_latest"]) != state_home:
        raise ValueError("Hermes registry scope differs from admitted selection")
    expected = (
        state_home
        / "agent-conformance/observations/hermes"
        / hashlib.sha256(chosen["session_id"].encode()).hexdigest()
        / (witness["event_id"] + ".json")
    )
    path = canonical_path(entry["receipt"])
    raw = read_regular(path)
    record = strict_json(raw)
    if path != expected or hashlib.sha256(raw).hexdigest() != witness["sha256"]:
        raise ValueError("registry candidate is foreign or changed")
    text = rows[1]["result"]["context"].rsplit("\nSYNTHESIS_NATIVE_RECEIPT ", 1)[0]
    if (
        record.get("kind") != "callback-source-observation"
        or record.get("client") != "hermes"
        or record.get("candidate_only") is not True
        or record.get("native_live") != "UNKNOWN"
        or record.get("authority") is not False
        or record.get("hook_event_name") != "pre_llm_call"
        or record.get("plugin_version") != version
        or record.get("event_id") != witness["event_id"]
        or record.get("context_sha256") != hashlib.sha256(text.encode()).hexdigest()
        or record.get("turn_id") != rows[1]["payload"]["extra"]["turn_id"]
        or canonical_path(record.get("plugin_root")) != plugin
        or record.get("callback_generation") != callback_generation(plugin, plugin)
    ):
        raise ValueError(
            "Hermes candidate does not bind exact context/source generation"
        )
    binding = hermes_source_binding(
        Path(chosen["profile_home"]),
        chosen["session_id"],
        profile=chosen["profile"],
        cwd=chosen["cwd"],
    )
    if (
        binding["status"] != "BOUND"
        or record["source_binding"]["session_id"] != chosen["session_id"]
    ):
        raise ValueError("current native session/profile is unavailable")
    if (
        rows[1]["release"]["release_root"] != str(plugin)
        or rows[1]["release"]["content_digest"] != record["source_digest"]
        or rows[1]["release"]["version"] != version
    ):
        raise ValueError("native callback release identity differs")
    times = [record["recorded_at"], *(e["ingested_at"] for e in events)]

    def fresh():
        now = datetime.now(timezone.utc)
        if any(
            not 0 <= (now - instant(t)).total_seconds() <= MAX_AGE_SECONDS
            for t in times
        ):
            raise ValueError("Hermes observation is stale or future dated")

    fresh()
    if source_inventory(root) != inventory:
        raise ValueError("source inventory changed")
    for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        if strict_json(read_regular(root / name)).get("version") != version:
            raise ValueError("selected native version differs from source manifests")
    sha = canonical_tree_digest(root)
    if record["source_digest"] != sha:
        raise ValueError(
            "observed release descriptor differs from the full selected source"
        )
    installed = verify_native_release_inventory(plugin, root, sha)
    if (
        source_inventory(root) != inventory
        or read_regular(path) != raw
        or verify_native_release_inventory(plugin, root, sha) != installed
    ):
        raise ValueError("source/install/registry changed during consumption")
    final = runtime.load_run(project, state["run_id"])
    reread = runtime.inspect_context(final, selection["actor"], project=project)[
        "current_native_events"
    ](ids)

    def current_identity(value):
        return (
            value["status"],
            value["events"],
            [
                (c["source_handle"], c["generation"], c["qualification"])
                for c in value["coverage"]
            ],
        )

    if final != state or current_identity(reread) != current_identity(selected):
        raise ValueError("native PM/source admission changed during consumption")
    if hermes_source_binding(
        Path(chosen["profile_home"]), chosen["session_id"],
        profile=chosen["profile"], cwd=chosen["cwd"],
    ) != binding:
        raise ValueError("native session/profile changed during consumption")
    fresh()
    return {
        "status": "PASS",
        "scope": "admitted-hermes-context-consumption-only",
        "client": "hermes",
        "session_id": chosen["session_id"],
        "event_id": witness["event_id"],
        "receipt_sha256": witness["sha256"],
        "source_sha256": sha,
        "installation_sha256": installed,
        "source_inventory_sha256": digest(inventory),
        "source_generation": selection["source_generation"],
        "journal_revision": state["revision"],
        "action_authorized": False,
        "model_turn_completed": False,
        "model_turns_started": 0,
        "native_permissions": "UNKNOWN",
        "protected_execution": "UNKNOWN",
        "native_recovery": "UNKNOWN",
        "desktop_live_loading": "UNKNOWN",
        "all_hooks": "UNKNOWN",
    }

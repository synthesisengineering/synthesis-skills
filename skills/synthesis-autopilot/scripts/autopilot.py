#!/usr/bin/env python3
"""Durable autopilot command line. Mutations require a live PM-native actor.

The CLI never turns a receipt file or a spoken label into action authority.
Existing action owners remain responsible for authorization and external I/O.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def default_runtime_root():
    return Path(os.environ.get("SYNTHESIS_AUTOPILOT_RUNTIME", "~/.synthesis/autopilot")).expanduser()


def engine():
    import run_state
    import capabilities
    import evidence_bridge
    import consumer_checks
    import workflow
    capabilities.register_commands(run_state.register_command)
    workflow.register_commands(run_state.register_command)
    capabilities_guard = capabilities.validate_command
    run_state.register_constraint("capabilities", capabilities_guard)
    workflow.register_constraints(run_state.register_constraint)
    evidence_bridge.register_sources(run_state.register_evidence_source)
    evidence_bridge.register_acceptance_predicates(run_state.register_acceptance)
    evidence_bridge.register_observers(run_state.register_observer)
    consumer_checks.register_observers(run_state.register_observer)
    return run_state


def read_json(path):
    if path is None:
        raise ValueError("required input file is missing")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result
    value = json.loads(Path(path).read_text(), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def actor_from_hook(payload):
    return {"board": os.environ.get("SYNTHESIS_COORDINATION_BOARD", str(Path.home() / ".synthesis/coordination/active-sessions.md")),
            "native_payload": payload}


def surface_for(payload):
    explicit = payload.get("synthesis_surface") if isinstance(payload, dict) else None
    if explicit:
        return explicit
    if os.environ.get("SYNTHESIS_HOOK_CLIENT") == "muse":
        return "muse-cli"
    native = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "")
    if native.startswith("ccd:"):
        return "claude-code-desktop"
    if native.startswith("cc:"):
        return "claude-code-cli"
    if native.startswith("codex:"):
        return "codex-cli"
    if native.startswith("muse:") or (isinstance(payload, dict) and payload.get("client") == "muse"):
        return "muse-cli"
    # Discover only a family established by the PM-native transcript validator.
    # Desktop vs CLI capabilities still require an explicit surface observation.
    try:
        from run_admission import observer_native_identity
        family, _ = observer_native_identity(payload)
        return {"codex": "codex-cli", "claude": "claude-code-cli", "muse": "muse-cli"}[family]
    except (ValueError, OSError, ImportError, KeyError, TypeError, RuntimeError):
        return None


def stop_result(actor, *, runtime_root=None):
    from capabilities import normalize_event, stop_response, continuation_status, wait_delivery_status
    payload = actor.get("native_payload", {}) if isinstance(actor, dict) else {}
    surface = surface_for(payload)
    if surface is None:
        message = "UNRESOLVED: autopilot cannot identify this native client; no completion or continuation is inferred."
        return {"continue": False, "stopReason": message, "systemMessage": message}
    try:
        normalize_event(surface, payload)
        runtime = engine()
        root = runtime_root if runtime_root is not None else default_runtime_root()
        legacy = runtime.legacy_for_stop(actor, Path(root) / "engagements", runtime_root=root)
        if legacy["health"] != "PASS":
            return stop_response(surface, payload, legacy["action"], terminal=True)
        corrupt = [item for item in legacy["unattributed"] if item.get("blocking")]
        if corrupt:
            return stop_response(surface, payload,
                "Owned legacy engagement is unresolved; preserve it and inspect its recovery evidence: "
                + "; ".join(item["source"] for item in corrupt), terminal=True)
        runs = runtime.inspect_owned_runs(actor, runtime_root=runtime_root)
        unresolved = [f"legacy engagement requires explicit import or verified closure: {item['source']}"
                      for item in legacy["owned_active"]]
        for state, context in runs:
            continuation = continuation_status(state, context)
            if continuation.get("continuation_verified"):
                continue
            # A wait is not evidence of a wake or of successful notification.
            # It terminates corrective injection only with an observed delivery.
            alerted = wait_delivery_status(state, context)["delivered"]
            if state.get("status") == "waiting_user" and alerted:
                continue
            unresolved.append(f"run {state['run_id']}: {state['status']}; continuation {continuation['state']}")
        if unresolved:
            return stop_response(surface, payload,
                "Autopilot remains incomplete. Preserve the run, establish verified continuation, "
                "or record an honest incomplete/cancelled disposition. " + "; ".join(unresolved))
        return stop_response(surface, payload)
    except (ValueError, OSError, ImportError, KeyError, TypeError, RuntimeError) as exc:
        return stop_response(surface, payload, f"Autopilot state or native ownership cannot be verified: {exc}", terminal=True)


def summary(state, context=None):
    criteria = state.get("contract", {}).get("criteria", [])
    receipts = state.get("verification", state.get("verifications", {}))
    inspected = engine().criterion_report(state, context) if context is not None else None
    return {"schema_version": state.get("schema_version"), "run_id": state["run_id"],
            "revision": state["revision"], "status": state["status"],
            "contract_digest": state.get("contract_digest"), "profile_digest": state.get("profile_digest"),
            "remaining_criteria": ([c["id"] for c in criteria if state["status"] != "completed"]
                                   if inspected is None else [c["id"] for c in inspected["criteria"] if c["status"] != "PASS"]),
            "criterion_inspection": inspected or {"status": "UNKNOWN", "reason": "Recorded status only; supply current native actor for verification."},
            "verification": receipts, "waits": state.get("waits", {}), "effects": state.get("effects", {}),
            "workflow": state.get("extensions", {}).get("workflow", {}),
            "capabilities": state.get("extensions", {}).get("capabilities", {}),
            "completion": state.get("completion"),
            "interpretation": "Status describes recorded execution; external effects and subjective quality require their bound evidence."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "command", "observe", "status", "rebuild", "import", "explain", "doctor", "stop"))
    for name in ("project", "plan", "contract", "profile", "actor", "payload", "legacy"):
        parser.add_argument("--" + name, type=Path)
    for name in ("project-id", "run-id", "command-id", "name", "surface"):
        parser.add_argument("--" + name)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--index-legacy", action="store_true",
                        help="Prepare host-local ownership discovery outside Stop; preserve source records")
    args = parser.parse_args(argv)
    try:
        if args.action == "explain":
            from capabilities import supported_surfaces
            from delegation_boundary import capability as worker_capability
            registry = supported_surfaces()
            for surface, declaration in registry["surfaces"].items():
                client = declaration["dialect"] if declaration["level"] == "native" else surface
                declaration["native_worker"] = worker_capability(client)
            if args.surface:
                if args.surface not in registry["surfaces"]:
                    raise ValueError("unknown surface")
                output = {**registry["surfaces"][args.surface], "surface": args.surface,
                          "unattended_admitted": False,
                          "reason": "Runtime observations bound to this run are required; static support is not a receipt."}
            else:
                output = registry
        elif args.action == "stop":
            payload = json.load(sys.stdin)
            output = stop_result(actor_from_hook(payload), runtime_root=default_runtime_root())
        else:
            runtime = engine()
            if args.action == "doctor":
                output = {"status": "PASS", "scope": "module imports and supported schema", "runtime_root": str(default_runtime_root()),
                          "native_acceptance": "UNKNOWN without current client receipts"}
                if args.project is not None:
                    output.update(read_only_in_session=True, unattended_admitted=False)
                    try:
                        if not args.project_id:
                            raise ValueError("project ID is required for durable admission")
                        from run_admission import admit_paths
                        actor = read_json(args.actor)
                        proof = admit_paths(Path(actor["board"]), args.project_id, args.project,
                            [args.project / "resources/autopilot-runs"], actor["native_payload"], readonly=True)
                        output["durable_admission"] = {"status":"PASS", "project_id":proof["project_id"],
                                                       "native_ref":proof["native_ref"], "claim_hash":proof["claim_hash"]}
                        output["next_step"] = "Resolve the effective profile and create the scoped run through project management ownership."
                    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
                        output["status"] = "UNKNOWN"
                        output["durable_admission"] = {"status":"UNKNOWN", "reason":str(exc)}
                        output["next_step"] = "Use project management's existing registry, creation and exact claim protocol; independent read-only work remains available."
                if args.index_legacy:
                    inventory = runtime.index_legacy(read_json(args.actor), args.legacy or default_runtime_root() / "engagements",
                                                     runtime_root=default_runtime_root())
                    output["legacy_inventory"] = inventory
                    if inventory["unattributed"]:
                        output["status"] = "UNKNOWN"
                        output["interpretation"] = "Ownership index prepared; unassignable records require their owning recovery review."
            elif args.action == "status":
                if args.project is None or not args.run_id:
                    raise ValueError("status requires --project and --run-id")
                state = runtime.load_run(args.project, args.run_id)
                context = runtime.inspect_context(state, read_json(args.actor)) if args.actor else None
                output = summary(state, context)
            else:
                actor = read_json(args.actor)
                if args.project is None:
                    raise ValueError("--project is required")
                if args.action == "create":
                    if not args.project_id or args.plan is None or not args.command_id:
                        raise ValueError("create requires project-id, plan and command-id")
                    output = runtime.create_run(args.project, project_id=args.project_id, plan=args.plan,
                        contract=read_json(args.contract), profile=read_json(args.profile), actor=actor,
                        command_id=args.command_id, runtime_root=default_runtime_root(), run_id=args.run_id)
                elif args.action in {"command", "observe"}:
                    if not args.run_id or not args.name or args.expected_revision is None or not args.command_id:
                        raise ValueError("command requires run-id, name, expected-revision and command-id")
                    mutate = runtime.observe if args.action == "observe" else runtime.apply_command
                    output = mutate(args.project, args.run_id, args.name, read_json(args.payload),
                        expected_revision=args.expected_revision, command_id=args.command_id, actor=actor,
                        runtime_root=default_runtime_root())
                elif args.action == "rebuild":
                    if not args.run_id:
                        raise ValueError("rebuild requires run-id")
                    output = runtime.rebuild_projections(args.project, args.run_id, actor=actor)
                else:
                    if args.legacy is None or not args.project_id or args.plan is None or not args.command_id:
                        raise ValueError("import requires legacy, project-id, plan and command-id")
                    output = runtime.import_legacy(args.project, args.legacy, project_id=args.project_id,
                        plan=args.plan, contract=read_json(args.contract), profile=read_json(args.profile),
                        actor=actor, command_id=args.command_id, runtime_root=default_runtime_root())
        print(json.dumps(output, indent=2, sort_keys=True, default=str, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ImportError, RuntimeError) as exc:
        if args.action == "stop":
            text = "UNRESOLVED: autopilot runtime failed: " + str(exc)
            print(json.dumps({"continue": False, "stopReason": text, "systemMessage": text}))
            return 0
        parser.exit(2, f"autopilot: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

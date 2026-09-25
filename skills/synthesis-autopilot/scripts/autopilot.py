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
    import observation_bridge
    import controller
    capabilities.register_commands(run_state.register_command)
    workflow.register_commands(run_state.register_command)
    workflow.register_preparers(run_state.register_preparer)
    capabilities_guard = capabilities.validate_command
    run_state.register_constraint("capabilities", capabilities_guard)
    workflow.register_constraints(run_state.register_constraint)
    evidence_bridge.register_sources(run_state.register_evidence_source)
    evidence_bridge.register_acceptance_predicates(run_state.register_acceptance)
    evidence_bridge.register_observers(run_state.register_observer)
    consumer_checks.register_observers(run_state.register_observer)
    observation_bridge.register(run_state)
    controller.register(run_state)
    return run_state


def read_json(path):
    if path is None:
        raise ValueError("required input file is missing")
    from controller import _read_json_bytes
    return _decode_json(_read_json_bytes(Path(path)))


def _decode_json(raw):
    from controller import MAX_REQUEST_BYTES, _bounded, _unique
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("input exceeds the strict JSON size bound")
    value = json.loads(raw, object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("input must be finite JSON")))
    _bounded(value)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def actor_from_hook(payload):
    return {"board": os.environ.get("SYNTHESIS_COORDINATION_BOARD", str(Path.home() / ".synthesis/coordination/active-sessions.md")),
            "native_payload": payload}


def _observer_identity(payload):
    # Combined Stop calls this before engine() or a CLI request decoder has
    # imported PM. Resolve the canonical owner explicitly; import order and
    # optional harness environment hints must not decide whether it exists.
    scripts = HERE.parents[1] / "synthesis-project-management/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from project_state import observer_native_identity
    return observer_native_identity(payload)


def surface_for(payload):
    from capabilities import supported_surfaces
    explicit = payload.get("synthesis_surface") if isinstance(payload, dict) else None
    if explicit:
        entry = supported_surfaces()["surfaces"].get(explicit) if isinstance(explicit, str) else None
        return explicit if entry and entry["dialect"] in {"claude", "codex", "muse", "cursor", "copilot"} else None
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
        family, _ = _observer_identity(payload)
        return {"codex": "codex-cli", "claude": "claude-code-cli", "muse": "muse-cli"}[family]
    except (ValueError, OSError, ImportError, KeyError, TypeError, RuntimeError):
        return None


def stop_result(actor, *, runtime_root=None, reserve_feedback=True):
    from capabilities import normalize_event, stop_response, continuation_status, wait_delivery_status, supported_surfaces
    payload = actor.get("native_payload", {}) if isinstance(actor, dict) else {}
    surface = surface_for(payload)
    if surface is None:
        message = "UNRESOLVED: autopilot cannot identify this native client; no completion or continuation is inferred."
        return {"continue": False, "stopReason": message, "systemMessage": message}
    try:
        normalize_event(surface, payload)
        # A surface/ref hint chooses a wire dialect, never ownership. Prove
        # native identity even when no runtime index exists, so an absent or
        # invalid transcript cannot be mistaken for an inactive engagement.
        family, _ = _observer_identity(payload)
        if family != supported_surfaces()["surfaces"][surface]["dialect"]:
            raise ValueError("native transcript does not bind the selected Stop surface")
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
        unresolved_runs = []
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
            unresolved_runs.append((state, context))
        if unresolved:
            import workflow
            message = "Autopilot remains incomplete. " + "; ".join(unresolved)
            if reserve_feedback is not True:
                return stop_response(surface, payload, message + "; sibling checkpoint vetoed corrective emission", terminal=True)
            if legacy["owned_active"] or not unresolved_runs:
                return stop_response(surface, payload, message, terminal=True)
            screens = [workflow.stop_feedback_status(state, context) for state, context in unresolved_runs]
            if any(screen.get("action") != "eligible" for screen in screens):
                return stop_response(surface, payload, message + "; " + "; ".join(
                    screen.get("reason_code", "unverified_policy_state") for screen in screens), terminal=True)
            # Read-only screens cannot spend a correction. Reserve exactly one
            # only after all unresolved runs have passed the deny-only screen.
            selected = unresolved_runs[0][0]
            disposition = workflow.reserve_stop_feedback(runtime, selected, actor,
                project=Path(selected["owner"]["project_root"]), runtime_root=root)
            return stop_response(surface, payload, message, policy_disposition=disposition)
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
    parser.add_argument("action", choices=("create", "command", "observe", "status", "rebuild", "import", "explain", "doctor", "stop",
        "start", "next", "record", "checkpoint", "cancel", "recover", "finish"))
    for name in ("project", "plan", "contract", "profile", "actor", "payload", "legacy"):
        parser.add_argument("--" + name, type=Path)
    for name in ("project-id", "run-id", "command-id", "name", "surface"):
        parser.add_argument("--" + name)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--request", help="Strict bounded operation request file, or - for stdin")
    parser.add_argument("--source-mode", choices=("native", "synthetic"), default="native",
                        help="Declared source mode; never proof of native qualification")
    parser.add_argument("--index-legacy", action="store_true",
                        help="Prepare host-local ownership discovery outside Stop; preserve source records")
    args = parser.parse_args(argv)
    try:
        if args.request is not None or args.action in {"start", "next", "record", "checkpoint", "cancel", "recover", "finish"}:
            import controller
            if args.action not in controller.OPERATIONS or args.project is None or args.request is None:
                raise ValueError("facade operation requires --project and --request")
            request = controller.read_request(args.request)
            if request["operation"] != args.action:
                raise ValueError("request operation does not match CLI action")
            output = controller.handle(request, project=args.project,
                actor=read_json(args.actor) if args.actor else None,
                runtime_root=default_runtime_root(), source_mode=args.source_mode)
            print(controller.encode_response(output).decode("utf-8"))
            return 0
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
            from controller import MAX_REQUEST_BYTES
            payload = _decode_json(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
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
                    payload = read_json(args.payload)
                    if args.action == "command" and args.name == "workflow.grade":
                        import workflow
                        current = runtime.load_run(args.project, args.run_id)
                        request_id = "cli-grade." + runtime._digest(args.command_id)
                        binding = {"request_id": request_id, "request_digest": runtime._digest({"command": args.name, "payload": payload}),
                            "operation": "record", "step": "grade", "initial_revision": args.expected_revision}
                        runtime._check_request(current, binding)
                        rearm = workflow.prepare_grade(current, payload, runtime.inspect_context(current, actor))
                        if rearm is not None:
                            current = runtime.apply_command(args.project, args.run_id, "workflow.rearm", rearm,
                                expected_revision=current["revision"], command_id="rearm." + runtime._digest(args.command_id),
                                actor=actor, runtime_root=default_runtime_root(), request_binding={**binding, "step": "rearm"})
                        output = runtime.apply_command(args.project, args.run_id, args.name, payload,
                            expected_revision=current["revision"], command_id=args.command_id, actor=actor,
                            runtime_root=default_runtime_root(), request_binding=binding)
                    else:
                        mutate = runtime.observe if args.action == "observe" else runtime.apply_command
                        output = mutate(args.project, args.run_id, args.name, payload,
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

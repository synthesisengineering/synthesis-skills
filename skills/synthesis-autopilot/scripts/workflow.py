"""Pure workflow policy for the autopilot engine's single transaction boundary.

This module neither persists state nor claims files, sends messages, schedules
turns, authenticates grants, or verifies files. The engine supplies fresh PM
admissions and verified evidence. A workflow verdict cannot grant authority or
complete the core run. Resource units are explicit integers; unmeasured use is
retained as an unresolved reservation, never silently converted to zero.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone


DOMAINS = {"software": "behavior", "research": "sources", "writing": "reader",
           "data": "reconcile", "browser": "outcome", "knowledge": "recovery", "operations": "reconcile"}
CORE_CHECKS = ("core.outcome", "core.authority", "core.evidence", "core.recovery")
MAX_NODES = 256
MAX_ATTEMPTS = 8
MAX_QUALITY_ROUNDS = 2
TERMINAL_CHILD = {"complete", "partial", "failed", "blocked", "cancelled"}


def _object(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("Invalid fields: expected " + ", ".join(sorted(allowed)))
    return value


def _text(value, label="text"):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("Expected nonempty bounded " + label)
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ValueError("Invalid identifier")
    return value


def _integer(value, minimum=0, maximum=10**15):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Expected bounded integer units")
    return value


def _strings(value, *, nonempty=False):
    if not isinstance(value, list) or len(value) > MAX_NODES or (nonempty and not value):
        raise ValueError("Expected bounded list")
    for item in value:
        _text(item)
    if len(set(value)) != len(value):
        raise ValueError("Duplicate list values")
    return value


def _time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Naive time")
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Expected timezone-qualified timestamp") from exc


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _bindings(state):
    return {key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}


def _base(state, context, *, current=True):
    result = copy.deepcopy(state)
    flow = result.get("extensions", {}).get("workflow")
    if not isinstance(flow, dict):
        raise ValueError("Configure workflow first")
    if current and flow["bindings"] != _bindings(state):
        raise ValueError("Core amendment requires explicit workflow rebind")
    _time(context["now"])
    return result, flow


def _admission_open(flow, context):
    ledger = flow.get("budget")
    if ledger and ledger.get("breaches"):
        raise ValueError("Observed resource overrun blocks further work admission")
    if ledger and _time(context["now"]) >= _time(ledger["deadline"]):
        raise ValueError("Run deadline exhausted; preserve work and reconcile")


def _evidence(state, context, ident, kind):
    _id(ident)
    verifier = context.get("verify_receipt")
    record = context.get("evidence", {}).get(ident)
    if not callable(verifier) or not isinstance(record, dict) or not verifier(ident, kind, _bindings(state)):
        raise ValueError("Missing, stale, unbound or unverified evidence")
    if record.get("kind") != kind or any(record.get("bindings", {}).get(k) != v for k, v in _bindings(state).items()):
        raise ValueError("Evidence binding mismatch")
    if not isinstance(record.get("data"), dict):
        raise ValueError("Evidence has no typed observation")
    return record


def resolve_profile(dimensions, layers=None):
    """Resolve explainable workflow preferences; never infer an action grant."""
    _object(dimensions, {"domains", "uncertainty", "effect", "horizon", "parallelizable"},
            {"domains", "uncertainty", "effect", "horizon", "parallelizable"})
    _strings(dimensions["domains"], nonempty=True)
    if set(dimensions["domains"]) - DOMAINS.keys():
        raise ValueError("Unknown domain")
    for key, choices in (("uncertainty", {"low", "high"}), ("effect", {"none", "local-reversible", "external"}),
                         ("horizon", {"turn", "session", "reboot"})):
        if dimensions[key] not in choices:
            raise ValueError("Invalid task dimension: " + key)
    if type(dimensions["parallelizable"]) is not bool:
        raise ValueError("parallelizable must be boolean")
    checks = {name: {"status": "required", "provenance": [{"source": "invariant", "reason": "Outcome, authority and recovery remain binding"}]} for name in CORE_CHECKS}
    for domain in dimensions["domains"]:
        checks[domain + "." + DOMAINS[domain]] = {"status": "required", "provenance": [{"source": "domain", "reason": domain + " outcome checks"}]}
    if dimensions["uncertainty"] == "high":
        checks["evidence.independent"] = {"status": "required", "provenance": [{"source": "dimension", "reason": "High uncertainty"}]}
    if dimensions["effect"] == "external":
        checks["effect.reconciliation"] = {"status": "required", "provenance": [{"source": "dimension", "reason": "Ambiguous external effects require reconciliation"}]}
    if dimensions["horizon"] == "reboot":
        checks["continuation.survival"] = {"status": "required", "provenance": [{"source": "dimension", "reason": "Proved restart survival is required"}]}
    checks["optional.exploration"] = {"status": "enabled" if dimensions["uncertainty"] == "high" else "not_applicable", "provenance": [{"source": "default", "reason": "Budgeted exploration follows uncertainty"}]}
    if layers is None:
        layers = []
    if not isinstance(layers, list) or len(layers) > 16:
        raise ValueError("Invalid profile layers")
    for layer in layers:
        _object(layer, {"source", "checks"}, {"source", "checks"})
        source = _text(layer["source"])
        if not isinstance(layer["checks"], dict) or len(layer["checks"]) > 128:
            raise ValueError("Invalid check overrides")
        for name, override in layer["checks"].items():
            _id(name)
            _object(override, {"enabled", "reason", "description"}, {"enabled"})
            if type(override["enabled"]) is not bool:
                raise ValueError("Check enabled must be boolean")
            if name not in checks and not name.startswith("custom."):
                raise ValueError("Unknown check; personal checks use custom namespace")
            prior = checks.get(name, {"status": "enabled", "provenance": []})
            if prior["status"] == "required" and not override["enabled"]:
                raise ValueError("Workflow preference cannot weaken a required check")
            reason = override.get("reason", "Explicit profile preference")
            _text(reason)
            if not override["enabled"] and "reason" not in override:
                raise ValueError("Disabled check requires a reason")
            if "description" in override:
                _text(override["description"])
                prior["description"] = override["description"]
            if prior["status"] != "required":
                prior["status"] = "enabled" if override["enabled"] else "disabled_by_instruction"
            prior["provenance"].append({"source": source, "reason": reason})
            checks[name] = prior
    return {"dimensions": copy.deepcopy(dimensions), "checks": checks, "authority_granted": False,
            "preferences": {"wip_limit": 2 if dimensions["parallelizable"] else 1,
                            "identical_transient_retries": 1, "max_task_attempts": MAX_ATTEMPTS,
                            "checkpoint": "consequential_boundaries" if dimensions["effect"] == "external" else "task_boundaries"},
            "explanation": ["Required checks follow each domain independently", "User preferences do not change the contract or grant authority"]}


def configure(state, payload, context):
    _object(payload, {"dimensions", "layers", "reason"}, {"dimensions"})
    profile = resolve_profile(payload["dimensions"], payload.get("layers", []))
    result = copy.deepcopy(state)
    extensions = result.setdefault("extensions", {})
    old = extensions.get("workflow")
    if old:
        if old["bindings"] == _bindings(state):
            if old["profile"] != profile:
                raise ValueError("Profile changes require a typed core amendment")
            return result
        _text(payload.get("reason"), "amendment reason")
        if any(c["disposition"] == "running" or c["audit_status"] == "required" for c in old["children"].values()):
            raise ValueError("Reconcile child work before rebinding workflow")
        if any(n["status"] == "running" for n in old.get("graph", {}).get("nodes", {}).values()):
            raise ValueError("Stop active work before rebinding workflow")
        extensions.setdefault("workflow_history", []).append(copy.deepcopy(old))
    flow = {"schema_version": 1, "bindings": _bindings(state), "profile": profile,
            "children": {}, "quality": {}, "quality_history": {}, "progress": {}, "configured_at": context["now"]}
    if old:
        if "budget" in old:
            flow["budget"] = old["budget"]  # Amendments never reset the total-run ledger.
        flow["retained_children"] = old.get("retained_children", []) + list(old["children"].values())
    extensions["workflow"] = flow
    return result


def _criteria(state):
    return {criterion["id"]: criterion for criterion in state["contract"]["criteria"]}


def graph(state, payload, context):
    _object(payload, {"nodes", "wip_limit", "reason"}, {"nodes", "wip_limit"})
    result, flow = _base(state, context)
    _admission_open(flow, context)
    _integer(payload["wip_limit"], 1, 32)
    if not isinstance(payload["nodes"], list) or not 1 <= len(payload["nodes"]) <= MAX_NODES:
        raise ValueError("Graph must contain bounded nodes")
    criteria = _criteria(state)
    nodes = {}
    for node in payload["nodes"]:
        _object(node, {"id", "deps", "criteria", "estimate"}, {"id", "deps", "criteria", "estimate"})
        ident = _id(node["id"])
        if ident in nodes:
            raise ValueError("Duplicate task")
        _strings(node["deps"])
        _strings(node["criteria"])
        _integer(node["estimate"], 1, 100000)
        if set(node["criteria"]) - criteria.keys():
            raise ValueError("Task expands the accepted outcome")
        nodes[ident] = {**copy.deepcopy(node), "status": "pending"}
    remaining = set(nodes)
    visited = set()
    while remaining:
        ready = {ident for ident in remaining if set(nodes[ident]["deps"]) <= visited}
        if not ready:
            raise ValueError("Graph has a cycle or missing dependency")
        remaining -= ready
        visited |= ready
    covered = {criterion for node in nodes.values() for criterion in node["criteria"]}
    if {ident for ident, criterion in criteria.items() if criterion["required"]} - covered:
        raise ValueError("Graph omits required acceptance criteria")
    old = flow.get("graph")
    if old:
        _text(payload.get("reason"), "graph amendment reason")
        for ident, previous in old["nodes"].items():
            if previous["status"] != "pending":
                if ident not in nodes or any(previous[k] != nodes[ident][k] for k in ("deps", "criteria", "estimate")):
                    raise ValueError("Graph amendment loses retained or active work")
                nodes[ident] = previous
        if sum(n["status"] == "running" for n in nodes.values()) > payload["wip_limit"]:
            raise ValueError("WIP reduction conflicts with active work")
    flow["graph"] = {"nodes": nodes, "wip_limit": payload["wip_limit"], "revision": old["revision"] + 1 if old else 1}
    return result


def ready_tasks(state, now=None):
    """Return a bounded dependency-ready frontier, prioritizing critical paths."""
    flow = state["extensions"]["workflow"]
    if flow["bindings"] != _bindings(state):
        return []
    graph = flow.get("graph", {"nodes": {}, "wip_limit": 1})
    nodes = graph["nodes"]
    available = graph["wip_limit"] - sum(n["status"] == "running" for n in nodes.values())
    if available <= 0:
        return []
    downstream = {ident: [] for ident in nodes}
    for ident, node in nodes.items():
        for dep in node["deps"]:
            downstream[dep].append(ident)
    scores = {}
    def score(ident):
        if ident not in scores:
            scores[ident] = nodes[ident]["estimate"] + max((score(child) for child in downstream[ident] if nodes[child]["status"] != "done"), default=0)
        return scores[ident]
    ready = []
    for ident, node in nodes.items():
        if node["status"] != "pending" or not all(nodes[dep]["status"] == "done" for dep in node["deps"]):
            continue
        decision = retry_decision(state, ident)
        if decision["action"] not in {"continue", "retry"}:
            continue
        if now and decision.get("not_before") and _time(now) < _time(decision["not_before"]):
            continue
        ready.append(ident)
    return sorted(ready, key=lambda ident: (-score(ident), ident))[:available]


def _node(flow, ident):
    _id(ident)
    try:
        return flow["graph"]["nodes"][ident]
    except KeyError as exc:
        raise ValueError("Unknown task") from exc


def retry_binding(state, task_id):
    """Bind a clearance to the exact current blocked attempt or manual condition."""
    flow = state["extensions"]["workflow"]
    node = _node(flow, task_id)
    if node["status"] != "blocked":
        raise ValueError("Retry binding requires a blocked task")
    history = flow["progress"].get(task_id, [])
    return {"task_id": task_id, "blocking_digest": _digest({
        "task_id": task_id, "last_attempt_id": history[-1]["attempt_id"] if history else None,
        "reason": node.get("reason"),
    })}


def task(state, payload, context):
    _object(payload, {"task_id", "action", "reason", "receipt_id"}, {"task_id", "action"})
    result, flow = _base(state, context)
    node = _node(flow, payload["task_id"])
    if any(c["task_id"] == node["id"] and c["audit_status"] != "accepted" for c in flow["children"].values()):
        raise ValueError("Delegated work requires integration disposition")
    action = payload["action"]
    if action == "start":
        _admission_open(flow, context)
        if node["id"] not in ready_tasks(result, context["now"]):
            raise ValueError("Task is not dependency, budget, retry and WIP ready")
        node["status"] = "running"
    elif action == "block":
        if node["status"] not in {"pending", "running"}:
            raise ValueError("Only active work can become blocked")
        node.update(status="blocked", reason=_text(payload.get("reason")))
    elif action == "complete":
        if node["status"] != "running":
            raise ValueError("Only running work may complete")
        evidence = _evidence(state, context, payload.get("receipt_id"), "task_completion")
        if evidence["data"].get("task_id") != node["id"] or set(evidence["data"].get("criteria", [])) != set(node["criteria"]):
            raise ValueError("Completion evidence does not cover the task")
        node.update(status="done", completion_receipt=payload["receipt_id"])
    elif action == "retry":
        if node["status"] != "blocked":
            raise ValueError("Only blocked work needs clearance")
        evidence = _evidence(state, context, payload.get("receipt_id"), "retry_clearance")
        binding = retry_binding(state, node["id"])
        if any(evidence["data"].get(key) != value for key, value in binding.items()):
            raise ValueError("Retry clearance does not match the current blocked attempt")
        _text(evidence["data"].get("changed_condition"), "verified changed condition")
        history = flow["progress"].get(node["id"], [])
        if history and _time(evidence["observed_at"]) < _time(history[-1]["at"]):
            raise ValueError("Retry clearance predates the blocked attempt")
        # Source bytes and observation content survive receipt-id aliasing.
        fingerprint = _digest({key: evidence.get(key) for key in ("kind", "data", "source")})
        consumed = node.setdefault("consumed_clearances", [])
        if fingerprint in consumed or len(consumed) >= MAX_ATTEMPTS or len(history) >= MAX_ATTEMPTS:
            raise ValueError("Retry clearance was consumed or retry budget is exhausted")
        consumed.append(fingerprint)
        node.update(status="pending", retry_clearance=payload["receipt_id"],
                    cleared_attempts=len(history))
    elif action == "cancel":
        if node["status"] == "done":
            raise ValueError("Completed work is retained")
        node.update(status="cancelled", reason=_text(payload.get("reason")))
    else:
        raise ValueError("Unknown task transition")
    return result


def budget(state, payload, context):
    _object(payload, {"limits", "deadline"}, {"limits", "deadline"})
    result, flow = _base(state, context)
    if not isinstance(payload["limits"], dict) or not payload["limits"] or len(payload["limits"]) > 16:
        raise ValueError("Invalid resource dimensions")
    for name, limit in payload["limits"].items():
        _id(name)
        _object(limit, {"limit", "enforcement"}, {"limit", "enforcement"})
        if limit["enforcement"] not in {"hard", "forecast"}:
            raise ValueError("Resource enforcement must be explicit")
        if limit["limit"] is None:
            if limit["enforcement"] != "forecast":
                raise ValueError("Unknown provider usage cannot have a hard cap")
        else:
            _integer(limit["limit"])
    if _time(payload["deadline"]) <= _time(context["now"]):
        raise ValueError("Deadline must be in the future")
    if "budget" in flow:
        if any(flow["budget"][k] != payload[k] for k in ("limits", "deadline")):
            raise ValueError("Run budget cannot be silently reset or expanded")
        return result
    flow["budget"] = {"limits": copy.deepcopy(payload["limits"]), "deadline": payload["deadline"], "reservations": {}}
    return result


def _amounts(ledger, amounts):
    if not isinstance(amounts, dict) or set(amounts) - ledger["limits"].keys():
        raise ValueError("Invalid resource amounts")
    return {name: _integer(amounts.get(name, 0)) for name in ledger["limits"]}


def _children(ledger, ident):
    return [r for r in ledger["reservations"].values() if r["parent_id"] == ident]


def _consumed(ledger, reservation, name):
    return (reservation["actual"] or {}).get(name, 0) + sum(_consumed(ledger, child, name) for child in _children(ledger, reservation["id"]))


def _committed(ledger, reservation, name):
    consumed = _consumed(ledger, reservation, name)
    return consumed if reservation["status"] == "settled" else max(consumed, reservation["amounts"].get(name, 0))


def budget_summary(state):
    ledger = state["extensions"]["workflow"]["budget"]
    roots = [r for r in ledger["reservations"].values() if r["parent_id"] is None]
    result = {}
    for name, policy in ledger["limits"].items():
        known_spent = sum(_consumed(ledger, root, name) for root in roots)
        committed = sum(_committed(ledger, root, name) for root in roots)
        unknown = sorted(r["id"] for r in ledger["reservations"].values()
                         if r["status"] == "unknown" and name not in (r["actual"] or {}) and r["amounts"].get(name, 0) > 0)
        unmeasured_forecast = policy["enforcement"] == "forecast" and not any(name in (r["actual"] or {}) for r in ledger["reservations"].values())
        result[name] = {**policy, "spent": None if unknown or unmeasured_forecast else known_spent,
                        "known_spent": known_spent, "committed": committed,
                        "available": None if policy["limit"] is None else policy["limit"] - committed,
                        "unknown_reservations": unknown,
                        "by_category": {category: sum((r["actual"] or {}).get(name, 0) for r in ledger["reservations"].values() if r["category"] == category)
                                        for category in sorted({r["category"] for r in ledger["reservations"].values()})}}
    return result


def reserve(state, payload, context):
    _object(payload, {"reservation_id", "amounts", "category", "parent_id"}, {"reservation_id", "amounts", "category"})
    result, flow = _base(state, context)
    _admission_open(flow, context)
    ledger = flow.get("budget")
    if ledger is None:
        raise ValueError("Configure run budget first")
    ident = _id(payload["reservation_id"])
    if ident in ledger["reservations"]:
        raise ValueError("Reservation identity already exists")
    if payload["category"] not in {"work", "integration", "verification", "recovery", "overhead"}:
        raise ValueError("Unknown resource category")
    amounts = _amounts(ledger, payload["amounts"])
    parent_id = payload.get("parent_id")
    parent = None
    if parent_id is not None:
        parent = ledger["reservations"].get(_id(parent_id))
        if parent is None or parent["status"] != "reserved":
            raise ValueError("Parent reservation unavailable")
        for name, amount in amounts.items():
            remaining = parent["amounts"][name] - sum(_committed(ledger, child, name) for child in _children(ledger, parent_id))
            if amount > remaining:
                raise ValueError("Nested reservation exceeds parent envelope")
    else:
        summary = budget_summary(result)
        for name, amount in amounts.items():
            if summary[name]["enforcement"] == "hard" and amount > summary[name]["available"]:
                raise ValueError("Run resource limit exhausted")
    ledger["reservations"][ident] = {"id": ident, "parent_id": parent_id, "amounts": amounts, "actual": None,
                                     "status": "reserved", "category": payload["category"]}
    return result



def _reservation_accounted(ledger, reservation):
    """Unknown forecasts may remain committed after observed work finishes.

    This is resource bookkeeping, not task acceptance. A null/interrupted
    settlement, an active reservation, or any unmeasured hard dimension still
    blocks completion. Quality, child integration and authority remain separate
    gates. Neither this predicate nor close changes an unknown usage value.
    """
    status = reservation.get("status")
    if status not in {"settled", "unknown"} or not isinstance(reservation.get("actual"), dict):
        return False
    if status == "unknown" and reservation.get("settlement_observed") is not True:
        return False
    amounts = reservation.get("amounts")
    if not isinstance(amounts, dict):
        return False
    for name, amount in amounts.items():
        if amount > 0 and name not in reservation["actual"]:
            if ledger.get("limits", {}).get(name, {}).get("enforcement") != "forecast":
                return False
    return all(_reservation_accounted(ledger, child) for child in _children(ledger, reservation["id"]))


def _settle(ledger, ident, actual):
    reservation = ledger["reservations"].get(_id(ident))
    if reservation is None:
        raise ValueError("Unknown reservation")
    if actual is not None:
        _amounts(ledger, actual)
    normalized = None if actual is None else dict(actual)
    if reservation["status"] == "settled":
        if normalized != reservation["actual"]:
            raise ValueError("Settled usage is immutable")
        return
    if normalized is None:
        reservation.update(status="unknown", settlement_observed=False)
        return
    previous = reservation["actual"] or {}
    if any(name in normalized and normalized[name] != amount for name, amount in previous.items()):
        raise ValueError("Known partial usage cannot be rewritten during reconciliation")
    normalized = {**previous, **normalized}
    children = _children(ledger, ident)
    for name, amount in normalized.items():
        consumed = amount + sum(_consumed(ledger, child, name) for child in children)
        if consumed > reservation["amounts"][name] and ledger["limits"][name]["enforcement"] == "hard":
            breach = {"reservation_id": ident, "resource": name,
                      "reserved": reservation["amounts"][name], "observed": consumed}
            breaches = ledger.setdefault("breaches", [])
            prior = next((entry for entry in breaches if entry["reservation_id"] == ident and entry["resource"] == name), None)
            if prior is None:
                breaches.append(breach)
            else:
                prior["observed"] = max(prior["observed"], consumed)
    missing = {name for name, amount in reservation["amounts"].items() if amount > 0 and name not in normalized}
    if missing:
        reservation.update(actual=normalized, status="unknown", settlement_observed=True)
        return
    if any(not _reservation_accounted(ledger, child) for child in children):
        raise ValueError("Reconcile descendants before closing parent reservation")
    # A parent must retain its envelope when a descendant forecast remains
    # unknown; marking it settled would refund that unmeasured child usage.
    status = "unknown" if any(child["status"] != "settled" for child in children) else "settled"
    reservation.update(actual=normalized, status=status, settlement_observed=True)


def settle(state, payload, context):
    _object(payload, {"reservation_id", "actual"}, {"reservation_id", "actual"})
    result, flow = _base(state, context, current=False)
    if any(child["reservation_id"] == payload["reservation_id"] and child["audit_status"] == "required" for child in flow["children"].values()) and payload["actual"] is not None:
        raise ValueError("Child usage needs verified integration audit")
    _settle(flow["budget"], payload["reservation_id"], payload["actual"])
    return result


def dispatch(state, payload, context):
    fields = {"child_id", "task_id", "deliverables", "paths", "criteria", "reservation_id", "integration_reservation_id",
              "integration_owner", "admission_id", "return_contract", "cancellation", "file_contract"}
    _object(payload, fields | {"admission_requests", "mode", "dispatch_receipt_id", "client", "required_capabilities"}, fields)
    result, flow = _base(state, context)
    _admission_open(flow, context)
    mode = payload.get("mode", "peer")
    if mode not in {"peer", "artifact-only", "native-cli"}:
        raise ValueError("Unknown delegation mode")
    ident = payload["child_id"]
    if mode == "artifact-only":
        if not isinstance(ident, str) or not re.fullmatch(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)+", ident) or len(ident) > 256:
            raise ValueError("Artifact-only delegation needs the observed canonical child identity")
    else:
        _id(ident)
    if ident in flow["children"]:
        raise ValueError("Child identity already exists")
    node = _node(flow, payload["task_id"])
    if node["id"] not in ready_tasks(result, context["now"]):
        raise ValueError("Delegation task is not ready")
    _strings(payload["deliverables"], nonempty=True)
    if len(payload["deliverables"]) > 5:
        raise ValueError("Child brief exceeds five deliverables")
    _strings(payload["criteria"])
    if set(payload["criteria"]) != set(node["criteria"]):
        raise ValueError("Child brief changes task acceptance")
    paths = _strings(payload["paths"], nonempty=True)
    admission = context.get("admissions", {}).get(payload["admission_id"])
    if not isinstance(admission, dict) or admission.get("project_id") != state["project_id"] or set(admission.get("paths", [])) != set(paths):
        raise ValueError("Missing fresh exact child claim admission")
    for key in ("session_uuid", "native_ref", "claim_hash"):
        _text(admission.get(key))
    if payload["integration_owner"] != context["binding"]["session_uuid"]:
        raise ValueError("Independent integration owner must own this command")
    from delegation_boundary import validate_file_contract
    validate_file_contract(payload["file_contract"], context, paths)
    if mode == "native-cli":
        from delegation_boundary import validate_requirements
        validate_requirements(payload.get("client"), payload.get("required_capabilities"))
        if (payload.get("client") not in {"claude", "codex", "muse"} or "dispatch_receipt_id" in payload
                or admission["session_uuid"] != context["binding"]["session_uuid"]
                or admission["native_ref"] != context["binding"].get("native_ref")):
            raise ValueError("Native CLI work needs its current parent admission and known client")
    elif "client" in payload or "required_capabilities" in payload:
        raise ValueError("Only native CLI dispatch selects a worker client and capabilities")
    if mode == "artifact-only":
        if (admission["session_uuid"] != context["binding"]["session_uuid"]
                or admission["native_ref"] != context["binding"].get("native_ref")):
            raise ValueError("Artifact-only work stays under the current parent's exact admission")
        proof = _evidence(state, context, payload.get("dispatch_receipt_id"), "delegation")
        brief = {key: value for key, value in payload.items()
                 if key not in {"admission_id", "admission_requests", "dispatch_receipt_id"}}
        if proof["data"] != brief:
            raise ValueError("Native dispatch evidence does not match the complete delegated brief")
    elif mode == "peer" and (admission["session_uuid"] == payload["integration_owner"] or "dispatch_receipt_id" in payload):
        raise ValueError("A peer needs its own authenticated claim; native dispatch is artifact-only")
    _strings(payload["return_contract"], nonempty=True)
    if set(payload["return_contract"]) != {"artifact_ids", "evidence_ids", "disposition"}:
        raise ValueError("Typed child evidence return contract required")
    _text(payload["cancellation"])
    ledger = flow.get("budget", {}).get("reservations", {})
    worker = ledger.get(payload["reservation_id"])
    integration = ledger.get(payload["integration_reservation_id"])
    if not worker or worker["status"] != "reserved" or worker["category"] != "work":
        raise ValueError("Worker budget reservation unavailable")
    if not integration or integration["status"] != "reserved" or integration["category"] != "integration" or not any(integration["amounts"].values()):
        raise ValueError("Reserve integration headroom before dispatch")
    if any(c["reservation_id"] == worker["id"] for c in flow["children"].values()):
        raise ValueError("Worker reservation already assigned")
    flow["children"][ident] = {key: copy.deepcopy(value) for key, value in payload.items() if key != "admission_requests"}
    flow["children"][ident].update(owner=copy.deepcopy(admission), mode=mode,
                                    producer=None if mode == "native-cli" else ident if mode == "artifact-only" else admission["native_ref"],
                                    write_enforcement="UNVERIFIED",
                                    disposition="running", audit_status="required", authority_granted=False,
                                    artifact_ids=[], evidence_ids=[], cancellation_requested=False)
    node["status"] = "running"
    return result



def worker_record(state, payload, context):
    _object(payload, {"child_id", "receipt_id"}, {"child_id", "receipt_id"})
    result, flow = _base(state, context)
    child = flow["children"].get(payload["child_id"])
    if (not child or child.get("mode") != "native-cli" or child.get("worker_receipt_id")
            or child["integration_owner"] != context["binding"]["session_uuid"]):
        raise ValueError("Native worker observation needs its current integration owner and unused slot")
    data = _evidence(state, context, payload["receipt_id"], "native_worker")["data"]
    producer = data.get("producer")
    if (data.get("child_id") != child["child_id"] or data.get("client") != child["client"]
            or data.get("file_contract_digest") != _digest(child["file_contract"])
            or data.get("boundary", {}).get("status") not in {"ENFORCED", "UNKNOWN", "UNAVAILABLE"}
            or (producer is not None and (not isinstance(producer, str) or not producer.startswith(child["client"] + ":")
                                         or not producer.split(":", 1)[1]))
            or (data.get("terminal") == "completed" and producer is None)):
        raise ValueError("Native worker observation is not bound to its real producer and boundary")
    child.update(producer=producer, worker_receipt_id=payload["receipt_id"],
                 worker_observation=copy.deepcopy(data),
                 write_enforcement="VERIFIED" if data["boundary"]["status"] == "ENFORCED" else data["boundary"]["status"])
    return result


def child_return(state, payload, context):
    _object(payload, {"child_id", "disposition", "artifact_ids", "evidence_ids", "reason"}, {"child_id", "disposition", "artifact_ids", "evidence_ids", "reason"})
    result, flow = _base(state, context, current=False)
    child = flow["children"].get(payload["child_id"])
    if child is None or child["disposition"] != "running" or payload["disposition"] not in TERMINAL_CHILD:
        raise ValueError("Invalid or duplicate child return")
    if child.get("mode") == "native-cli" and payload["disposition"] == "complete":
        observed = child.get("worker_observation", {})
        if (not child.get("worker_receipt_id") or observed.get("terminal") != "completed"
                or observed.get("preservation") != "PASS" or observed.get("native_exit_code") != 0
                or observed.get("boundary", {}).get("status") != "ENFORCED") :
            raise ValueError("Native worker completion requires its successful preserved launch observation")
    _strings(payload["artifact_ids"])
    _strings(payload["evidence_ids"])
    _text(payload["reason"])
    if child.get("mode") == "native-cli":
        from pathlib import PurePosixPath
        observed = child.get("worker_observation", {}).get("output_manifest", {})
        for ident in payload["artifact_ids"]:
            artifact = context.get("artifacts", {}).get(ident)
            if (not isinstance(artifact, dict) or not artifact.get("path")
                    or observed.get(str(PurePosixPath(context["binding"]["project_root"]) / artifact["path"])) != artifact.get("digest")):
                raise ValueError("Returned artifact was not observed in this native worker output")
    child.update(copy.deepcopy(payload))
    child["audit_status"] = "required"
    _node(flow, child["task_id"]).update(status="blocked", reason="Child return requires integration audit")
    _settle(flow["budget"], child["reservation_id"], None)
    return result


def cancel_child(state, payload, context):
    _object(payload, {"child_id", "reason"}, {"child_id", "reason"})
    result, flow = _base(state, context, current=False)
    child = flow["children"].get(payload["child_id"])
    if child is None or child["disposition"] != "running":
        raise ValueError("Only a running child can receive cancellation")
    child.update(cancellation_requested=True, cancellation_reason=_text(payload["reason"]))
    return result


def integrate(state, payload, context):
    _object(payload, {"child_id", "receipt_id"}, {"child_id", "receipt_id"})
    result, flow = _base(state, context)
    child = flow["children"].get(payload["child_id"])
    if child is None or child["disposition"] not in TERMINAL_CHILD or child["audit_status"] != "required":
        raise ValueError("Child has no pending integration audit")
    data = _evidence(state, context, payload["receipt_id"], "child_integration")["data"]
    producer = child.get("producer", child["owner"]["native_ref"])
    reviewer = _text(data.get("reviewer"), "native reviewer identity")
    producing_identities = {producer, child["child_id"]}
    if child.get("mode", "peer") == "peer":
        producing_identities.update((child["owner"]["native_ref"], child["owner"]["session_uuid"]))
    if (data.get("child_id") != child["child_id"] or data.get("task_id") != child["task_id"]
            or data.get("integration_owner") != child["integration_owner"]
            or data.get("integration_owner") != context["binding"]["session_uuid"]
            or data.get("producer") != producer
            or reviewer in producing_identities
            or set(data.get("artifact_ids", [])) != set(child["artifact_ids"]) or type(data.get("accepted")) is not bool):
        raise ValueError("Integration audit is not bound to returned work and independent owner")
    digests = data.get("artifact_digests")
    if not isinstance(digests, dict) or set(digests) != set(child["artifact_ids"]):
        raise ValueError("Integration audit needs every returned artifact digest")
    for ident, digest in digests.items():
        artifact = context.get("artifacts", {}).get(ident)
        if not isinstance(artifact, dict) or artifact.get("digest") != digest or not isinstance(digest, str):
            raise ValueError("Integrated artifact is missing or changed since review")
    if data["accepted"] and (child["disposition"] != "complete" or set(data.get("criteria", [])) != set(child["criteria"])):
        raise ValueError("Partial work cannot be accepted as complete")
    if child.get("mode") == "native-cli":
        actual = data.get("actual")
        observed = child.get("worker_observation", {})
        usage = observed.get("usage", {})
        expected = {**usage, "wall_millis": observed.get("elapsed_millis")}
        if not isinstance(actual, dict):
            raise ValueError("Native integration must retain measured resource usage")
        for name, value in expected.items():
            if value is None:
                if name in actual:
                    raise ValueError("Unmeasured native usage cannot be invented")
            elif type(actual.get(name)) is not int or actual[name] != value:
                raise ValueError("Integration contradicts measured native usage")
    _settle(flow["budget"], child["reservation_id"], data.get("actual"))
    child.update(audit_status="accepted" if data["accepted"] else "rejected", audit_receipt=payload["receipt_id"])
    _node(flow, child["task_id"]).update(status="done" if data["accepted"] else "blocked", reason="Integration audit recorded")
    return result


def _observed_quality(domain, observation):
    """Domain-specific comparisons over verified observations, not vote counts."""
    boolean_fields = {
        "research": {"sources_verified", "decisive_claims_verified", "counterevidence_checked"},
        "writing": {"source_fidelity", "reader_purpose", "structure", "voice"},
    }
    if domain in boolean_fields:
        fields = boolean_fields[domain]
        _object(observation, fields, fields)
        if any(type(observation[field]) is not bool for field in fields):
            raise ValueError("Rubric dimensions require boolean observations")
        return all(observation.values())
    comparable = {"software": ("expected", "observed", "consumer_verified"),
                  "browser": ("expected_state", "observed_state", "independent_readback"),
                  "knowledge": ("expected_hashes", "recovered_hashes", "foreign_preserved"),
                  "operations": ("expected_state", "observed_state", "effects_reconciled")}
    if domain in comparable:
        expected, observed, independent = comparable[domain]
        _object(observation, {expected, observed, independent}, {expected, observed, independent})
        if type(observation[independent]) is not bool or observation[expected] is None or observation[observed] is None:
            raise ValueError("Consumer observation is incomplete")
        if domain == "knowledge" and (not isinstance(observation[expected], dict) or not observation[expected] or not isinstance(observation[observed], dict)):
            raise ValueError("Recovery requires an explicit preservation inventory")
        return _digest(observation[expected]) == _digest(observation[observed]) and observation[independent]
    if domain == "data":
        fields = {"expected_rows", "observed_rows", "expected_total", "observed_total", "missing_explained"}
        _object(observation, fields, fields)
        _integer(observation["expected_rows"])
        _integer(observation["observed_rows"])
        if type(observation["missing_explained"]) is not bool:
            raise ValueError("Missing data disposition is required")
        _text(observation["expected_total"])
        _text(observation["observed_total"])
        return observation["expected_rows"] == observation["observed_rows"] and observation["expected_total"] == observation["observed_total"] and observation["missing_explained"]
    raise ValueError("Unsupported quality domain")


def quality_receipt_verdict(data, independent):
    """Compute one typed quality observation's verdict without changing state."""
    if independent and (data["reviewer"] == data["producer"] or data.get("independent") is not True):
        return "UNKNOWN"
    if data["domain"] in {"writing", "research"} and data.get("calibrated") is not True:
        return "UNKNOWN"
    return "PASS" if _observed_quality(data["domain"], data.get("observations")) else "FAIL"


def grade(state, payload, context):
    _object(payload, {"criterion_id", "receipt_ids", "independent", "resolution_receipt_id"}, {"criterion_id", "receipt_ids", "independent"})
    result, flow = _base(state, context)
    criterion = _criteria(state).get(payload["criterion_id"])
    if criterion is None or type(payload["independent"]) is not bool:
        raise ValueError("Unknown criterion or independence requirement")
    ids = _strings(payload["receipt_ids"])
    old = flow["quality"].get(payload["criterion_id"])
    outcomes = []
    receipt_bindings = {}
    independent = payload["independent"] or flow["profile"]["checks"].get("evidence.independent", {}).get("status") == "required"
    for ident in ids:
        record = _evidence(state, context, ident, "quality_observation")
        data = record["data"]
        reviewed = context.get("artifacts", {}).get(data.get("artifact_id"))
        if (data.get("criterion_id") != payload["criterion_id"] or data.get("artifact_id") not in criterion["artifact_ids"]
                or not isinstance(reviewed, dict) or not isinstance(data.get("artifact_digest"), str)
                or reviewed.get("digest") != data["artifact_digest"]):
            raise ValueError("Quality evidence is not bound to criterion artifact")
        receipt_bindings[ident] = {"digest": record["digest"], "artifact_id": data["artifact_id"], "artifact_digest": data["artifact_digest"]}
        _text(data.get("rubric"))
        _text(data.get("method"))
        _text(data.get("producer"))
        _text(data.get("reviewer"))
        _strings(data.get("findings"))
        if data.get("domain") not in flow["profile"]["dimensions"]["domains"]:
            raise ValueError("Quality evidence does not assess a configured domain")
        outcomes.append(quality_receipt_verdict(data, independent))
    known = set(outcomes) - {"UNKNOWN"}
    verdict = "DISAGREEMENT" if known == {"PASS", "FAIL"} else "FAIL" if "FAIL" in known else "UNKNOWN" if not outcomes or "UNKNOWN" in outcomes else "PASS"
    if old and set(old["receipt_ids"]) == set(ids):
        if (old.get("receipt_bindings") != receipt_bindings or old["verdict"] != verdict
                or old["independent"] != independent):
            raise ValueError("Graded receipt identities cannot be replaced or reinterpreted")
        return result  # Only freshly revalidated, exactly identical proof is idempotent.
    if old and old["round"] >= MAX_QUALITY_ROUNDS:
        raise ValueError("Quality resolution budget exhausted; needs named human or evidence condition")
    resolution_binding = None
    if old and old["verdict"] in {"FAIL", "DISAGREEMENT"}:
        record = _evidence(state, context, payload.get("resolution_receipt_id"), "quality_resolution")
        resolution = record["data"]
        expected = quality_resolution_requirements(old, payload["criterion_id"], receipt_bindings)
        if any(resolution.get(key) != value for key, value in expected.items()):
            raise ValueError("Quality resolution does not bind the exact prior failure and repaired evidence")
        _text(resolution.get("changed_evidence"), "changed evidence explanation")
        resolution_binding = {"receipt_id": payload["resolution_receipt_id"], "digest": record["digest"]}
    evaluation = {"verdict": verdict, "receipt_ids": ids, "receipt_bindings": receipt_bindings,
                  "receipt_verdicts": dict(zip(ids, outcomes)),
                  "round": old["round"] + 1 if old else 1, "independent": independent, "certifies_authority": False}
    if resolution_binding:
        evaluation["resolution"] = resolution_binding
    evaluation["grade_digest"] = _digest(evaluation)
    if old:
        flow.setdefault("quality_history", {}).setdefault(payload["criterion_id"], []).append(copy.deepcopy(old))
    flow["quality"][payload["criterion_id"]] = evaluation
    return result


def quality_resolution_requirements(prior, criterion_id, receipt_bindings):
    """Pure exact-diff contract; a source verifier must establish its inputs.

    Historical failing receipts deliberately need not describe current bytes.
    Their grade-time fingerprints remain the negative basis. This comparison
    establishes a changed output, never successful repair or action authority.
    """
    if (not isinstance(prior, dict) or prior.get("verdict") not in {"FAIL", "DISAGREEMENT"}
            or prior.get("grade_digest") != _digest({key: value for key, value in prior.items() if key != "grade_digest"})):
        raise ValueError("Quality repair requires an intact historical failed grade")
    previous = prior.get("receipt_bindings")
    if (not isinstance(previous, dict) or not previous or set(previous) != set(prior["receipt_ids"])
            or not receipt_bindings or set(previous) & set(receipt_bindings)):
        raise ValueError("Repair requires new immutable review attempts and all prior fingerprints")
    before, after = {}, {}
    for record in previous.values():
        before.setdefault(record["artifact_id"], set()).add(record["artifact_digest"])
    for record in receipt_bindings.values():
        after.setdefault(record["artifact_id"], set()).add(record["artifact_digest"])
    if set(before) != set(after) or any(len(hashes) != 1 for hashes in after.values()):
        raise ValueError("Repair must reassess exactly the prior reviewed artifacts")
    changed = {ident: {"before": sorted(hashes), "after": next(iter(after[ident]))}
               for ident, hashes in before.items() if hashes != after[ident]}
    if not changed:
        raise ValueError("A fresh review alone is not a changed reviewed output")
    verdicts = prior.get("receipt_verdicts")
    if (not isinstance(verdicts, dict) or set(verdicts) != set(previous)
            or any(value not in {"PASS", "FAIL", "UNKNOWN"} for value in verdicts.values())):
        raise ValueError("Historical quality repair requires every computed receipt verdict")
    failing_artifacts = {previous[identity]["artifact_id"] for identity, verdict in verdicts.items() if verdict == "FAIL"}
    if not failing_artifacts or failing_artifacts - set(changed):
        raise ValueError("Every failing artifact must change before replacing its negative review")
    return {"criterion_id": criterion_id, "prior_grade_digest": prior["grade_digest"],
            "prior_receipt_ids": list(prior["receipt_ids"]),
            "prior_receipt_digests": {key: value["digest"] for key, value in previous.items()},
            "receipt_ids": list(receipt_bindings),
            "new_receipt_digests": {key: value["digest"] for key, value in receipt_bindings.items()},
            "changed_artifacts": changed}


def progress(state, payload, context):
    fields = {"task_id", "attempt_id", "input_digest", "output_digest", "evidence_ids", "outcome", "summary"}
    _object(payload, fields, fields)
    result, flow = _base(state, context)
    node = _node(flow, payload["task_id"])
    _id(payload["attempt_id"])
    if node["status"] in {"done", "cancelled"}:
        raise ValueError("Terminal task cannot generate progress")
    for key in ("input_digest", "output_digest"):
        if not isinstance(payload[key], str) or not re.fullmatch("[0-9a-f]{64}", payload[key]):
            raise ValueError("Progress requires exact input and output digests")
    if payload["outcome"] not in {"artifact", "evidence", "transient_failure", "permanent_failure", "ambiguous_effect", "authority_blocked", "blocked_dependency"}:
        raise ValueError("Unknown progress outcome")
    _text(payload["summary"])
    _strings(payload["evidence_ids"])
    history = flow["progress"].setdefault(node["id"], [])
    if len(history) >= MAX_ATTEMPTS or any(p["attempt_id"] == payload["attempt_id"] for p in history):
        raise ValueError("Task attempt budget exhausted or attempt identity replayed")
    fingerprints = []
    for ident in payload["evidence_ids"]:
        evidence = _evidence(state, context, ident, "progress_observation")
        if evidence["data"].get("task_id") != node["id"]:
            raise ValueError("Progress evidence belongs to a different task")
        fingerprints.append(_digest({k: evidence[k] for k in ("artifact_id", "digest", "data")}))
    prior = {fingerprint for item in history for fingerprint in item["fingerprints"]}
    meaningful = bool(set(fingerprints) - prior)
    if payload["outcome"] in {"artifact", "evidence"} and not fingerprints:
        raise ValueError("Claimed useful progress requires verified evidence")
    history.append({**copy.deepcopy(payload), "at": context["now"], "fingerprints": fingerprints, "meaningful": meaningful})
    decision = retry_decision(result, node["id"])
    if decision["action"] not in {"continue", "retry"}:
        node.update(status="blocked", reason=decision["condition"])
    elif node["status"] == "running" and payload["outcome"] == "transient_failure":
        node["status"] = "pending"
    return result


def retry_decision(state, task_id):
    history = state["extensions"]["workflow"]["progress"].get(task_id, [])
    if not history:
        return {"action": "continue", "condition": None}
    latest = history[-1]
    if len(history) >= MAX_ATTEMPTS:
        return {"action": "wait", "condition": "Task attempt budget exhausted; requires explicit run disposition"}
    node = state["extensions"]["workflow"].get("graph", {}).get("nodes", {}).get(task_id, {})
    if node.get("cleared_attempts") == len(history) and node.get("retry_clearance"):
        return {"action": "continue", "condition": "Verified changed condition"}
    outcome = latest["outcome"]
    if outcome == "ambiguous_effect":
        return {"action": "reconcile", "condition": "Independent effect reconciliation evidence"}
    if outcome in {"authority_blocked", "blocked_dependency"}:
        return {"action": "wait", "condition": "Verified authority receipt" if outcome == "authority_blocked" else "Dependency completion evidence"}
    if outcome == "permanent_failure":
        return {"action": "change_strategy", "condition": "Reviewed changed approach with new evidence"}
    if outcome == "transient_failure":
        identical = sum(p["outcome"] == outcome and p["input_digest"] == latest["input_digest"] for p in history)
        if identical > 1:
            return {"action": "wait", "condition": "Repeated failed input requires verified changed condition"}
        return {"action": "retry", "condition": "One bounded transient retry", "not_before": (_time(latest["at"]) + timedelta(seconds=2)).isoformat()}
    if not latest["meaningful"]:
        return {"action": "change_strategy", "condition": "New verified evidence or artifact change required"}
    return {"action": "continue", "condition": None}


def validate_command(state, command, payload, context):
    """Completion cannot bypass workflow obligations through a core command.

    Incomplete/cancelled dispositions remain available and retain unresolved
    work. Re-evaluate receipt content at completion; a cached PASS is not proof.
    """
    if command != "close" or payload.get("status") != "completed":
        return
    flow = state.get("extensions", {}).get("workflow")
    if flow is None:
        return
    if flow["bindings"] != _bindings(state):
        raise ValueError("Workflow bindings are stale after a core amendment")
    graph = flow.get("graph")
    if not graph or any(node["status"] != "done" for node in graph["nodes"].values()):
        raise ValueError("Workflow contains unfinished task obligations")
    if any(child["disposition"] == "running" or child["audit_status"] == "required" for child in flow["children"].values()):
        raise ValueError("Workflow contains unreconciled child work")
    ledger = flow.get("budget", {})
    if ledger.get("breaches") or any(not _reservation_accounted(ledger, reservation) for reservation in ledger.get("reservations", {}).values()):
        raise ValueError("Workflow resource accounting is unresolved")
    covered_domains = set()
    for ident, criterion in _criteria(state).items():
        if not criterion["required"]:
            continue
        evaluation = flow["quality"].get(ident)
        if not evaluation or evaluation["verdict"] != "PASS":
            raise ValueError("Required domain quality is not satisfied")
        fresh = copy.deepcopy(state)
        fresh["extensions"]["workflow"]["quality"].pop(ident)
        checked = grade(fresh, {"criterion_id": ident, "receipt_ids": evaluation["receipt_ids"],
                                "independent": evaluation["independent"]}, context)
        if checked["extensions"]["workflow"]["quality"][ident]["verdict"] != "PASS":
            raise ValueError("Quality verdict is no longer supported by current evidence")
        covered_domains.update(context["evidence"][receipt_id]["data"]["domain"]
                               for receipt_id in evaluation["receipt_ids"])
    if set(flow["profile"]["dimensions"]["domains"]) - covered_domains:
        raise ValueError("Fresh quality evidence does not cover every configured domain")
    if flow["profile"]["checks"].get("continuation.survival", {}).get("status") == "required":
        from capabilities import validate_horizon
        validate_horizon(state, flow["profile"]["dimensions"]["horizon"], context)


def register_constraints(register_constraint):
    register_constraint("workflow.completion", validate_command)


def register_commands(register_command):
    """Register reducers with the engine; the engine owns all writes/admission."""
    for name, reducer in {"configure": configure, "graph": graph, "task": task, "budget": budget,
                          "reserve": reserve, "settle": settle, "dispatch": dispatch, "return": child_return,
                          "cancel_child": cancel_child, "worker_record": worker_record, "integrate": integrate, "grade": grade, "progress": progress}.items():
        register_command("workflow." + name, reducer, allowed_fields=("extensions",))

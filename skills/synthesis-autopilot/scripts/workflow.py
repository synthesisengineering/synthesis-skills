"""Workflow reducers and authenticated adapters for the engine transaction.

The existing engine owns admission, persistence, claims, grants and scheduling.
Trusted preparers join current registered artifacts and native source facts;
reducers retain their policy projection in that same journal. A workflow
verdict cannot grant authority or complete the core run. Resource units are
explicit integers; unmeasured use remains an unresolved reservation.
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
    if ledger:
        for name, policy in ledger["limits"].items():
            if policy["enforcement"] != "hard":
                continue
            reservations = list(ledger["reservations"].values())
            if any(item["status"] == "unknown" and name not in (item["actual"] or {})
                   and item["amounts"].get(name, 0) > 0 for item in reservations):
                raise ValueError("Unknown hard resource usage requires reconciliation")
            if sum((item["actual"] or {}).get(name, 0) for item in reservations) >= policy["limit"]:
                raise ValueError("Hard resource limit exhausted; preserve work and reconcile")


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
                            "identical_transient_retries": 1,
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
        if fingerprint in consumed:
            raise ValueError("Retry clearance was consumed")
        consumed.append(fingerprint)
        node.update(status="pending", retry_clearance=payload["receipt_id"],
                    cleared_attempts=len(history))
    elif action == "cancel":
        if node["status"] == "done":
            raise ValueError("Completed work is retained")
        node.update(status="cancelled", reason=_text(payload.get("reason")))
        store = _store(result)
        obligation = _lineage(state, node["criteria"])
        store["lineages"].setdefault(obligation, sorted(node["criteria"]))
        for related in _related_obligations(result, node["criteria"]):
            if related not in store["cancelled_obligations"]:
                store["cancelled_obligations"].append(related)
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
        source = proof["data"].get("source")
        if (not isinstance(source, dict) or set(source) != {"kind", "call_id"}
                or source["kind"] != "native-dispatch" or not isinstance(source["call_id"], str)
                or not source["call_id"] or len(source["call_id"]) > 256
                or {key: value for key, value in proof["data"].items() if key != "source"} != brief):
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
    if isinstance(observation, dict) and observation.get("kind") == "domain-assessment":
        from domain_quality import observation_verdict
        return observation_verdict(domain, observation) == "PASS"
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


def quality_receipt_verdict(data, independent, context=None):
    """Compute one typed quality observation's verdict without changing state."""
    if independent and (data["reviewer"] == data["producer"] or data.get("independent") is not True):
        return "UNKNOWN"
    if "domain_review" in data or (isinstance(data.get("observations"), dict)
                                  and data["observations"].get("kind") == "domain-assessment"):
        from domain_quality import observation_verdict, rederive_review
        if context is not None:
            owner_root = context.get("binding", {}).get("project_root")
            stored_root = context.get("state", {}).get("owner", {}).get("project_root")
            if not owner_root or (stored_root is not None and owner_root != stored_root):
                raise ValueError("Quality readback lacks the current owner-bound project root")
            if context.get("project") is not None and str(context["project"]) != owner_root:
                raise ValueError("Quality readback project differs from current owner")
            return rederive_review(data, {**context, "project": owner_root})
        # Historical repair checks the grade-bound observation. It must not
        # demand old source bytes be current after a verified output change.
        verdict = observation_verdict(data["domain"], data["observations"])
        return verdict if data.get("calibrated") is True else "UNKNOWN"
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
        outcomes.append(quality_receipt_verdict(data, independent, {**context, "state": state}))
    known = set(outcomes) - {"UNKNOWN"}
    verdict = "DISAGREEMENT" if known == {"PASS", "FAIL"} else "FAIL" if "FAIL" in known else "UNKNOWN" if not outcomes or "UNKNOWN" in outcomes else "PASS"
    if old and set(old["receipt_ids"]) == set(ids):
        if (old.get("receipt_bindings") != receipt_bindings or old["verdict"] != verdict
                or old["independent"] != independent):
            raise ValueError("Graded receipt identities cannot be replaced or reinterpreted")
        return result  # Only freshly revalidated, exactly identical proof is idempotent.
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
    if context.get("journal_head") and not context.get("quality_readonly"):
        _record_grade_policy(result, state, context, payload, evaluation)
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
    if "condition" in payload:
        return attempt(state, payload, context)
    if context.get("journal_head"):
        raise ValueError("Authenticated progress preparer is required at the runtime boundary")
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
    if any(p["attempt_id"] == payload["attempt_id"] for p in history):
        raise ValueError("Attempt identity replayed")
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
    flow = state["extensions"]["workflow"]
    persistence = state.get("extensions", {}).get("workflow_persistence", {})
    node = _node(flow, task_id)
    obligation = _lineage(state, node["criteria"])
    decisions = [persistence["decisions"][key] for key in _related_obligations(state, node["criteria"])
                 if key in persistence.get("decisions", {})]
    if any(key in persistence.get("cancelled_obligations", []) for key in _related_obligations(state, node["criteria"])):
        return {"action": "wait", "condition": "cancelled"}
    if decisions:
        decision = next((item for item in decisions if not item["allow_attempt"]), decisions[0])
        return {"action": decision["action"] if decision["allow_attempt"] else "wait",
                "condition": decision["reason_code"], "policy": copy.deepcopy(decision)}
    history = flow["progress"].get(task_id, [])
    if not history:
        return {"action": "continue", "condition": None}
    latest = history[-1]
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


def validate_native_command(state, command, payload, context):
    """Fresh native instructions constrain owner-admitted work transitions."""
    # Native instructions can invalidate work whose positive observation came
    # from a local owner rather than a native tool result. Use the same current
    # source reader at admission; an old journal projection is not absence proof.
    if state.get("extensions", {}).get("workflow") is not None and (
            (command == "workflow.task" and payload.get("action") in {"start", "retry", "complete"})
            or command in {"workflow.dispatch", "workflow.attempt", "workflow.progress"}
            or (command == "close" and payload.get("status") == "completed")):
        _require_native_clear(state, context)


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
                                "independent": evaluation["independent"]}, {**context, "quality_readonly": True})
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
    register_constraint("workflow.native_admission", validate_native_command)


def register_commands(register_command):
    """Register reducers with the engine; the engine owns all writes/admission."""
    for name, reducer in {"configure": configure, "graph": graph, "task": task, "budget": budget,
                          "reserve": reserve, "settle": settle, "dispatch": dispatch, "return": child_return,
                          "cancel_child": cancel_child, "worker_record": worker_record, "integrate": integrate, "grade": grade, "progress": progress, "attempt": attempt, "rearm": rearm, "stop_feedback": stop_feedback, "stop_emit": stop_emit}.items():
        register_command("workflow." + name, reducer, allowed_fields=("extensions",))


# The following adapters execute only inside the existing run_state admission
# and journal owner. This extension is a projection of that journal, not a
# second store, authority issuer, or scheduler. Native outcome interpretation
# below is restricted to exact declared structured process consumers.
def _store(state):
    return state.setdefault("extensions", {}).setdefault("workflow_persistence", {
        "schema_version": 1, "attempts": [], "rearms": [], "sources": {},
        "decisions": {}, "feedback": [], "cancelled_obligations": [], "lineages": {}})


def _obligation(criteria):
    return "criteria-" + _digest(sorted(criteria))


def _related_obligations(state, criteria):
    selected = set(criteria)
    lineages = state.get("extensions", {}).get("workflow_persistence", {}).get("lineages", {})
    return sorted(key for key, retained in lineages.items() if selected.intersection(retained)) or [_obligation(criteria)]


def _lineage(state, criteria):
    return _related_obligations(state, criteria)[0]


def _head(state, context):
    head = context.get("journal_head")
    if (not isinstance(head, dict) or set(head) != {"revision", "digest", "scope"}
            or head["revision"] != state["revision"] or head["scope"] != "full_run"
            or not re.fullmatch("[a-f0-9]{64}", str(head["digest"]))):
        raise ValueError("Verified complete journal head is required")
    return head


def _history(state, context):
    head = _head(state, context)
    store = state.get("extensions", {}).get("workflow_persistence", {})
    attempts, rearms = store.get("attempts", []), store.get("rearms", [])
    # Old raw progress cannot silently disappear behind a new task/profile.
    archived = state.get("extensions", {}).get("workflow_history", [])
    flows = archived + [state.get("extensions", {}).get("workflow", {})]
    accounted = {item["attempt_id"] for item in attempts}
    complete = all(item.get("attempt_id") in accounted for flow in flows
                   for records in flow.get("progress", {}).values() for item in records)
    grade_sources = {source.get("grade_digest"): event for event, source in store.get("sources", {}).items()
                     if source.get("kind") == "grade"}
    by_event = {item["event_id"]: item for item in attempts}
    for flow in flows:
        grades = list(flow.get("quality", {}).values()) + [item for rows in flow.get("quality_history", {}).values() for item in rows]
        for grade_record in grades:
            event = grade_sources.get(grade_record.get("grade_digest"))
            retained = by_event.get(event, {})
            if (grade_record.get("grade_digest") != _digest({key: value for key, value in grade_record.items() if key != "grade_digest"})
                    or retained.get("source_digest") != _digest(grade_record.get("receipt_bindings"))
                    or set(retained.get("evidence_ids", [])) != set(grade_record.get("receipt_ids", []))):
                complete = False
    return {"schema_version": 1, "attempts": copy.deepcopy(attempts), "rearms": copy.deepcopy(rearms),
        "coverage": {"schema_version": 1, "status": "complete" if complete else "unknown", "scope": "full_run",
            "run_id": state["run_id"], "head_revision": head["revision"], "head_digest": head["digest"],
            "attempt_count": len(attempts), "rearm_count": len(rearms),
            "projection_digest": _digest({"attempts": attempts, "rearms": rearms}),
            "evidence_id": "journal:" + head["digest"]}}


def _policy_admission(state, context, obligation):
    head = _head(state, context)
    flow = state["extensions"]["workflow"]
    resources = "available"
    try:
        _admission_open(flow, context)
    except ValueError as exc:
        resources = "unknown" if str(exc).startswith("Unknown hard resource") else "exhausted"
    if resources == "available" and flow.get("budget"):
        hard = [row for row in budget_summary(state).values() if row["enforcement"] == "hard"]
        if any(row["known_spent"] >= row["limit"] for row in hard):
            resources = "exhausted"
        elif any(row["unknown_reservations"] for row in hard):
            resources = "unknown"
    effects = [key for key, effect in state.get("effects", {}).items()
               if effect.get("status") in {"dispatching", "unknown", "ambiguous", "reconciliation_required"}]
    binding = context.get("binding", {})
    return {"schema_version": 1, "run_id": state["run_id"], "bindings_digest": _digest(_bindings(state)),
        "journal_head_digest": head["digest"], "journal_revision": head["revision"],
        "identity": "verified" if binding.get("native_ref") and binding.get("session_uuid") else "missing",
        "runtime": "verified", "ownership": "admitted" if binding.get("claim_hash") else "unknown",
        "authority": "admitted", "resources": resources, "storage": "available",
        "cancelled": state["status"] == "cancelled" or obligation in state.get("extensions", {}).get("workflow_persistence", {}).get("cancelled_obligations", []),
        "terminal": state["status"] in {"completed", "cancelled", "incomplete"},
        "unresolved_effect_ids": sorted(effects), "evidence_ids": ["journal:" + head["digest"]]}


def _strategy(state, context, ident, rationale_ref):
    if ident is not None:
        _id(ident)
    if rationale_ref is None:
        return {key + "_digest": _digest([key, "owner-observation"])
                for key in ("method", "intervention", "discriminator")} | {"rationale_ref": "owner-observation"}
    _id(rationale_ref)
    from pathlib import Path
    from run_admission import safe_path
    record = context.get("artifacts", {}).get(rationale_ref)
    if not isinstance(record, dict) or record.get("role") != "input":
        raise ValueError("Strategy rationale must be a current registered input artifact")
    project = Path(context["project"])
    path = safe_path(project / record["path"], project)
    raw = path.read_bytes()
    if len(raw) > 32768 or hashlib.sha256(raw).hexdigest() != record["digest"]:
        raise ValueError("Strategy input changed or exceeds capacity")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate strategy field")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    _object(data, {"schema_version", "strategy_id", "method", "intervention", "discriminator"},
            {"schema_version", "strategy_id", "method", "intervention", "discriminator"})
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or (ident is not None and data["strategy_id"] != ident):
        raise ValueError("Strategy input identity mismatch")
    _id(data["strategy_id"])
    _object(data["method"], {"kind", "script_artifact_id"}, {"kind", "script_artifact_id"})
    _object(data["intervention"], {"artifact_ids"}, {"artifact_ids"})
    _object(data["discriminator"], {"check_id"}, {"check_id"})
    if data["method"]["kind"] != "python-consumer":
        raise ValueError("Unsupported owner-verifiable strategy method")
    script_id = _id(data["method"]["script_artifact_id"])
    check_id = _id(data["discriminator"]["check_id"])
    outputs = _strings(data["intervention"]["artifact_ids"], nonempty=True)
    program = context["artifacts"].get(script_id)
    check = context["artifacts"].get(check_id)
    if not program or not check or program["role"] != "input" or check["role"] != "input" or not program["path"].endswith(".py"):
        raise ValueError("Strategy must bind current registered consumer inputs")
    from consumer_checks import _registered
    _registered(context, script_id)
    for output_id in outputs:
        _registered(context, output_id)
    raw_check = safe_path(project / check["path"], project).read_bytes()
    if len(raw_check) > 32768 or hashlib.sha256(raw_check).hexdigest() != check["digest"]:
        raise ValueError("Strategy discriminator changed or exceeds capacity")
    spec = json.loads(raw_check, object_pairs_hook=unique)
    _object(spec, {"schema_version", "kind", "criterion_id", "artifact_id", "script_artifact_id", "expected", "argv", "timeout_seconds"},
            {"schema_version", "kind", "criterion_id", "artifact_id", "script_artifact_id", "expected", "argv", "timeout_seconds"})
    criterion = _criteria(state).get(spec["criterion_id"])
    if (type(spec["schema_version"]) is not int or spec["schema_version"] != 1
            or spec["kind"] != "python-consumer" or spec["script_artifact_id"] != script_id or not criterion
            or set(outputs) != {spec["artifact_id"]} or spec["artifact_id"] not in criterion["artifact_ids"]):
        raise ValueError("Strategy changes its declared operation or output lineage")
    if (not isinstance(spec["argv"], list) or len(spec["argv"]) > 32
            or any(not isinstance(arg, str) or len(arg) > 4096 or "\0" in arg for arg in spec["argv"])
            or type(spec["timeout_seconds"]) is not int or not 1 <= spec["timeout_seconds"] <= 60):
        raise ValueError("Strategy discriminator has invalid bounded arguments or timeout")
    return {"method_digest": _digest(["python-consumer", program["digest"]]),
        "intervention_digest": _digest(sorted(outputs)),
        "discriminator_digest": _digest({key: spec[key] for key in ("criterion_id", "artifact_id", "expected", "argv", "timeout_seconds")}),
        "rationale_ref": rationale_ref}


def _consumer_strategy(context, data):
    from consumer_checks import _registered, _json
    path, _ = _registered(context, data["check_id"])
    spec = _json(path.read_text())
    _, program = _registered(context, spec["script_artifact_id"])
    return {"method_digest": _digest(["python-consumer", program["digest"]]),
        "intervention_digest": _digest([spec["artifact_id"]]),
        "discriminator_digest": _digest({key: spec[key] for key in ("criterion_id", "artifact_id", "expected", "argv", "timeout_seconds")}),
        "rationale_ref": data["check_id"]}


def _current_native(context, ids, required_interval=None):
    reader = context.get("current_native_events")
    if callable(reader):
        return reader(ids, required_interval)
    from observation_bridge import current_events
    return current_events(context, ids, required_interval=required_interval)


def _require_native_clear(state, context):
    """Require a fresh owner-bound root instruction/cancellation interval."""
    from observation_bridge import current_invalidation
    current = current_invalidation(context)
    # A command constraint sees its proposed next revision while its trusted
    # readback still binds the existing head. No proposed mutation is evidence.
    revision = context.get("journal_head", {}).get("revision", state["revision"])
    if (current.get("run_id") != state["run_id"]
            or current.get("revision") != revision
            or current.get("status") != "clear"):
        raise ValueError("Native instruction or cancellation is unresolved; current owner reconciliation is required")
    return current


def _native_process(state, context, payload, native):
    """Interpret one exact declared process consumer, never generic tool text."""
    from pathlib import Path
    import shlex
    import sys
    from consumer_checks import _registered, _json
    owner_root = context.get("binding", {}).get("project_root")
    if not owner_root or owner_root != state.get("owner", {}).get("project_root"):
        raise ValueError("Native consumer has no current owner-bound project")
    if context.get("project") is not None and str(context["project"]) != owner_root:
        raise ValueError("Native consumer project differs from current owner")
    context = {**context, "project": owner_root}
    reference = payload["rationale_ref"]
    if reference is None:
        raise ValueError("Native process requires a registered task/operation specification")
    path, record = _registered(context, reference)
    if record["role"] != "input" or path.stat().st_size > 32768:
        raise ValueError("Native process specification is not a bounded input")
    spec = _json(path.read_text())
    fields = {"schema_version", "kind", "task_id", "strategy_id", "call_id", "script_artifact_id", "artifact_id", "expected", "argv"}
    _object(spec, fields, fields)
    if (type(spec["schema_version"]) is not int or spec["schema_version"] != 1 or spec["kind"] != "native-python-consumer"
            or any(spec[key] != payload[key] for key in ("task_id", "strategy_id"))):
        raise ValueError("Native process specification does not bind this task/strategy")
    _id(spec["call_id"])
    node = _node(state["extensions"]["workflow"], payload["task_id"])
    declared = {ident for criterion in node["criteria"] for ident in _criteria(state)[criterion]["artifact_ids"]}
    if spec["artifact_id"] not in declared:
        raise ValueError("Native process expands task output scope")
    script, program = _registered(context, spec["script_artifact_id"])
    _, output = _registered(context, spec["artifact_id"])
    if program["role"] != "input" or script.suffix != ".py":
        raise ValueError("Native process must identify a registered Python input")
    argv = spec["argv"]
    if not isinstance(argv, list) or len(argv) > 32 or any(not isinstance(arg, str) or len(arg) > 4096 or "\0" in arg for arg in argv):
        raise ValueError("Native consumer arguments exceed the closed bound")
    events = native["events"]
    calls = [item for item in events if item["kind"] == "tool.call"]
    results = [item for item in events if item["kind"] == "tool.result"]
    if len(events) != 2 or len(calls) != 1 or len(results) != 1:
        raise ValueError("Native attempt requires exactly one call/result pair")
    call, result = calls[0], results[0]
    if (any(item["producer"]["client"] != "codex" or item["native"]["call_id"] != spec["call_id"]
            or item["run_id"] != state["run_id"] or item["task_id"] != payload["task_id"]
            or item["attempt_id"] != payload["attempt_id"] for item in events)
            or call["native"]["generation"] != result["native"]["generation"]
            or call["producer"] != result["producer"] or call["native"]["offset"] >= result["native"]["offset"]):
        raise ValueError("Native pair does not bind one ordered task attempt and source lineage")
    # Registered inputs precede the actual call; a post-hoc prose mapping is
    # not an executable task contract. Native clocks remain source observations.
    at = _time(call.get("native_timestamp"))
    if any(_time(item["registered_at"]) > at for item in (record, program)):
        raise ValueError("Native task operation was declared after execution")
    args = call["data"]["arguments"]
    name, namespace = call["data"]["name"], call["data"].get("namespace")
    if name in {"exec", "functions.exec"} and namespace in {None, "functions"}:
        # One literal call only: never execute or heuristically parse JavaScript.
        match = re.fullmatch(r"\s*text\(await tools\.exec_command\((\{.*\})\)\);?\s*", args, re.S)
        if match is None:
            raise ValueError("Native exec wrapper is not one literal process call")
        args = match.group(1)
    elif name not in {"exec_command", "functions.exec_command"} or namespace not in {None, "functions"}:
        raise ValueError("Native tool has no supported structured process contract")
    args = _json(args)
    _object(args, {"cmd", "workdir", "yield_time_ms", "max_output_tokens"}, {"cmd", "workdir"})
    for key, lower, upper in (("yield_time_ms", 250, 30000), ("max_output_tokens", 1, 10**7)):
        if key in args and (type(args[key]) is not int or not lower <= args[key] <= upper):
            raise ValueError("Native process request has invalid bounded controls")
    expected = shlex.join([sys.executable, "-I", str(script), *argv])
    if args["cmd"] != expected or args["workdir"] != str(Path(context["binding"]["project_root"])):
        raise ValueError("Native command does not match the exact declared consumer")
    raw = result["data"].get("output")
    if isinstance(raw, list):
        if (len(raw) != 2 or any(not isinstance(block, dict) or set(block) != {"type", "text"}
                or block["type"] != "input_text" or not isinstance(block["text"], str) for block in raw)
                or re.fullmatch(r"Script completed\nWall time [0-9]+(?:\.[0-9]+)? seconds\nOutput:\n", raw[0]["text"]) is None):
            raise ValueError("Native wrapper result is not one exact completed process response")
        raw = raw[1]["text"]
    process = _json(raw) if isinstance(raw, str) else raw
    _object(process, {"exit_code", "output", "wall_time_seconds", "chunk_id", "original_token_count", "session_id"},
            {"exit_code", "output", "wall_time_seconds"})
    if (type(process["exit_code"]) is not int or not -255 <= process["exit_code"] <= 255
            or not isinstance(process["output"], str) or len(process["output"]) > 65536
            or type(process["wall_time_seconds"]) not in {int, float} or not 0 <= process["wall_time_seconds"] <= 86400
            or process.get("session_id") is not None or result["data"].get("is_error") is True):
        raise ValueError("Native process has no complete unambiguous structured exit")
    if ("original_token_count" in process and (type(process["original_token_count"]) is not int or not 0 <= process["original_token_count"] <= 10**15)
            or "chunk_id" in process and (not isinstance(process["chunk_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", process["chunk_id"]))):
        raise ValueError("Native process metadata is malformed")
    # Re-read through the current source snapshot to catch appended cancellation,
    # duplicate results, changed instruction, gaps, or a changed producer.
    intervals = {row["generation"]: (min(item["native"]["offset"] for item in events), row["source_size_at_snapshot"])
                 for row in native["coverage"]}
    fresh = _current_native(context, payload["observation_ids"], intervals)
    if fresh["status"] != "current" or any(row.get("negative_coverage") != "CURRENT_BOUNDED_INTERVAL"
            or not row.get("covers_through_source_snapshot") for row in fresh["coverage"]):
        raise ValueError("Native attempt lacks complete current causal interval coverage")
    for row in fresh["coverage"]:
        for event in row.get("interval_events", []):
            if (event["kind"] in {"message.user", "lifecycle.cancelled"}
                    or event["data"].get("native_status") in {"cancelled", "interrupted", "turn_aborted"}
                    or event["data"].get("cancellation_scope")):
                raise ValueError("Native source contains a later instruction or cancellation requiring owner reconciliation")
    outcome = "failure" if process["exit_code"] else "evidence"
    if not process["exit_code"]:
        actual = _json(process["output"])
        if _digest(actual) != _digest(spec["expected"]):
            raise ValueError("Native consumer mismatch requires a quality owner observation")
    if payload["outcome"] != outcome:
        raise ValueError("Requested classification differs from structured native process outcome")
    strategy = {"method_digest": _digest(["native-python-consumer", program["digest"]]),
        "intervention_digest": _digest([spec["artifact_id"]]),
        "discriminator_digest": _digest({"expected": spec["expected"], "argv": argv}), "rationale_ref": reference}
    facts = {"artifacts": {spec["artifact_id"]: output["digest"]},
        "execution": {"exit_code": process["exit_code"], "stdout_digest": hashlib.sha256(process["output"].encode()).hexdigest(),
                      "script_digest": program["digest"], "spec_digest": _digest({key: value for key, value in spec.items() if key not in {"call_id", "strategy_id"}})},
        "effect": {}}
    source_digest = _digest({"native": [{key: item["native"][key] for key in ("generation", "offset", "length", "sha256", "subrecord")} for item in events],
        "script": program["digest"], "spec": record["digest"], "output": output["digest"]})
    return outcome, None if outcome == "evidence" else "permanent_tool", strategy, facts, source_digest


def _authenticated_observations(state, context, ids):
    _strings(ids, nonempty=True)
    for ident in ids:
        _id(ident)
    records, native = [], []
    for ident in ids:
        record = state.get("observations", {}).get(ident)
        if record is None:
            native.append(ident)
            continue
        if record.get("digest") != _digest({key: value for key, value in record.items() if key != "digest"}):
            raise ValueError("Immutable engine observation changed")
        verified = _evidence(state, context, ident, record["kind"])
        if any(verified.get(key) != record.get(key) for key in ("id", "kind", "data", "digest", "bindings")):
            raise ValueError("Observation is not the committed owner record")
        records.append(record)
    native_result = None
    if native:
        from observation_bridge import current_events
        native_result = _current_native(context, native)
        if native_result["status"] != "current":
            raise ValueError("Native observation ranges are not currently verified")
    if records and native:
        raise ValueError("One attempt cannot mix independently produced owner/native outcomes")
    return records, native_result


def _derive_attempt(state, context, payload):
    fields = {"task_id", "attempt_id", "strategy_id", "outcome", "observation_ids", "rationale_ref"}
    _object(payload, fields, fields)
    _require_native_clear(state, context)
    for key in ("task_id", "attempt_id", "strategy_id"):
        _id(payload[key])
    flow = state["extensions"]["workflow"]
    node = _node(flow, payload["task_id"])
    if node["status"] in {"done", "cancelled"}:
        raise ValueError("Terminal task cannot record a new attempt")
    records, native = _authenticated_observations(state, context, payload["observation_ids"])
    consumed = {ident for item in state.get("extensions", {}).get("workflow_persistence", {}).get("attempts", [])
                for ident in item["evidence_ids"]}
    if consumed.intersection(payload["observation_ids"]):
        raise ValueError("Source observation already finalized another attempt")
    native_semantic = _native_process(state, context, payload, native) if native else None
    artifact_hashes, outcomes, family, effect_id, grade_digest = {}, set(), None, None, None
    facts = {"artifacts": {}, "execution": {}, "effect": {}}
    executed_strategies = []
    for record in records:
        data, kind = record["data"], record["kind"]
        if kind in {"progress_observation", "task_completion"}:
            if data.get("task_id") != node["id"] or not data.get("artifact_digests"):
                raise ValueError("Owner observation does not cover the selected task")
            artifact_hashes.update(data["artifact_digests"])
            outcomes.add("artifact" if kind == "progress_observation" else "evidence")
        elif kind == "consumer-check":
            if data.get("criterion_id") not in node["criteria"]:
                raise ValueError("Consumer outcome belongs to a different obligation")
            execution = data.get("execution", {})
            if execution.get("sandbox_verified") is not True:
                raise ValueError("Consumer execution is not verified")
            artifact_hashes[data["artifact_id"]] = data["artifact_digest"]
            executed_strategies.append(_consumer_strategy(context, data))
            facts["execution"] = {key: execution.get(key) for key in ("returncode", "timed_out", "output_exceeded")}
            if execution.get("timed_out") is True:
                outcomes.add("failure"); family = "transient_tool"
            elif execution.get("returncode") != 0 or execution.get("output_exceeded") is True:
                outcomes.add("failure"); family = "permanent_tool"
            elif data.get("passed") is True:
                outcomes.add("evidence")
            else:
                raise ValueError("Failed quality comparison requires workflow.grade")
        elif kind == "effect-readback":
            raise ValueError("Effect readback belongs to the effect reconciliation owner, not task outcome classification")
        else:
            raise ValueError("Observation kind has no task outcome semantics")
    if native_semantic:
        native_outcome, family, native_strategy, facts, native_digest = native_semantic
        outcomes = {native_outcome}
        artifact_hashes = facts["artifacts"]
    if len(outcomes) != 1 or payload["outcome"] not in outcomes:
        raise ValueError("Requested classification does not equal the derived owner outcome")
    facts["artifacts"] = artifact_hashes
    obligation = _lineage(state, node["criteria"])
    if payload["outcome"] == "artifact" and any(item["obligation_id"] == obligation and
            item["condition_digest"] == _digest(facts) for item in state.get("extensions", {}).get("workflow_persistence", {}).get("attempts", [])):
        raise ValueError("Fresh receipt labels do not establish changed artifact progress")
    source_digest = native_semantic[4] if native_semantic else _digest({"records": [record["digest"] for record in records]})
    event_id = "attempt:" + payload["attempt_id"]
    strategy = native_semantic[2] if native_semantic else _strategy(state, context, payload["strategy_id"], payload["rationale_ref"])
    if executed_strategies:
        actual_keys = [{key: item[key] for key in ("method_digest", "intervention_digest", "discriminator_digest")} for item in executed_strategies]
        if any(item != actual_keys[0] for item in actual_keys):
            raise ValueError("One attempt cannot combine different executed strategies")
        if payload["rationale_ref"] is not None and any(strategy[key] != actual_keys[0][key] for key in actual_keys[0]):
            raise ValueError("Declared strategy does not match actual executed consumer")
        strategy = executed_strategies[0]
    from persistence_policy import classify_failure
    condition = classify_failure({"schema_version": 1, "run_id": state["run_id"], "task_id": node["id"],
        "obligation_id": obligation, "attempt_id": payload["attempt_id"], "event_id": event_id,
        "revision": state["revision"] + 1, "source_digest": source_digest, "bindings_digest": _digest(_bindings(state)),
        "outcome": payload["outcome"], "subject_digest": _digest(sorted(node["criteria"])),
        "strategy": strategy,
        "relevant_state": {"facts": facts, "evidence_ids": payload["observation_ids"]},
        "evidence_ids": payload["observation_ids"], "failure_family": family, "effect_id": effect_id,
        "grade_digest": grade_digest}, {"schema_version": 1, "status": "complete", "event_id": event_id,
            "source_digest": source_digest, "generation": "owner-journal", "evidence_id": "journal:" + _head(state, context)["digest"]})
    return condition


def prepare_attempt(context, payload):
    from evidence_bridge import _fresh
    _fresh(context)
    state = context["state"]
    condition = _derive_attempt(state, context, payload)
    return {"condition": condition, "source": copy.deepcopy(payload), "head": _head(state, context)}


def attempt(state, payload, context):
    _object(payload, {"condition", "source", "head"}, {"condition", "source", "head"})
    if payload["head"] != _head(state, context):
        raise ValueError("Attempt preparation does not bind current journal head")
    result, flow = _base(state, context)
    condition = payload["condition"]
    store = _store(result)
    if any(item["attempt_id"] == condition["attempt_id"] or item["event_id"] == condition["event_id"] for item in store["attempts"]):
        raise ValueError("Attempt identity is already finalized")
    from persistence_policy import decide_attempt
    decision = decide_attempt(condition, _history(state, context), None,
                              _policy_admission(state, context, condition["obligation_id"]))
    # Preserve negative evidence even when policy disallows another attempt.
    store["lineages"][condition["obligation_id"]] = sorted(set(store["lineages"].get(condition["obligation_id"], [])) | set(_node(flow, condition["task_id"])["criteria"]))
    store["attempts"].append(copy.deepcopy(condition))
    store["sources"][condition["event_id"]] = copy.deepcopy(payload["source"])
    store["decisions"][condition["obligation_id"]] = decision
    node = _node(flow, condition["task_id"])
    flow["progress"].setdefault(node["id"], []).append({"attempt_id": condition["attempt_id"],
        "outcome": condition["outcome"], "at": context["now"], "evidence_ids": condition["evidence_ids"],
        "fingerprints": [condition["source_digest"]], "meaningful": condition["family"] == "productive_work"})
    if not decision["allow_attempt"]:
        node.update(status="blocked", reason=decision["reason_code"])
    return result


def prepare_progress(context, payload):
    fields = {"task_id", "attempt_id", "input_digest", "output_digest", "evidence_ids", "outcome", "summary"}
    _object(payload, fields, fields)
    return prepare_attempt(context, {"task_id": payload["task_id"], "attempt_id": payload["attempt_id"],
        "strategy_id": "owner-observation", "outcome": payload["outcome"], "observation_ids": payload["evidence_ids"], "rationale_ref": None})


def _record_grade_policy(result, state, context, payload, evaluation):
    from persistence_policy import classify_failure, decide_attempt
    criterion_id = payload["criterion_id"]
    obligation = _lineage(state, [criterion_id])
    store = _store(result)
    old = state["extensions"]["workflow"]["quality"].get(criterion_id)
    if old and old["verdict"] in {"FAIL", "DISAGREEMENT"}:
        prior = next((item for item in reversed(store["attempts"]) if item["grade_digest"] == old["grade_digest"]), None)
        if prior is None or not any(item["prior_failure_digest"] == prior["failure_digest"] for item in store["rearms"]):
            raise ValueError("An exact quality rearm must be committed before the next grade")
    ids = payload["receipt_ids"]
    if not ids:
        return
    event_id = "grade:" + evaluation["grade_digest"]
    verdict = evaluation["verdict"]
    family = "quality_failure" if verdict == "FAIL" else "review_disagreement" if verdict == "DISAGREEMENT" else "coverage_unknown" if verdict == "UNKNOWN" else None
    source_digest = _digest(evaluation["receipt_bindings"])
    condition = classify_failure({"schema_version": 1, "run_id": state["run_id"], "task_id": "quality:" + criterion_id,
        "obligation_id": obligation, "attempt_id": event_id, "event_id": event_id, "revision": state["revision"] + 1,
        "source_digest": source_digest, "bindings_digest": _digest(_bindings(state)),
        "subject_digest": _digest([criterion_id]), "outcome": "evidence" if verdict == "PASS" else "blocked" if verdict == "UNKNOWN" else "failure",
        "strategy": _strategy(state, context, "quality-owner", None),
        "relevant_state": {"facts": {"artifacts": {item["artifact_id"]: item["artifact_digest"] for item in evaluation["receipt_bindings"].values()}}, "evidence_ids": ids},
        "evidence_ids": ids, "failure_family": family, "effect_id": None,
        "grade_digest": evaluation["grade_digest"] if family in {"quality_failure", "review_disagreement"} else None},
        {"schema_version": 1, "status": "complete", "event_id": event_id, "source_digest": source_digest,
         "generation": "owner-journal", "evidence_id": "journal:" + _head(state, context)["digest"]})
    decision = decide_attempt(condition, _history(state, context), None, _policy_admission(state, context, obligation))
    store["lineages"][obligation] = sorted(set(store["lineages"].get(obligation, [])) | {criterion_id})
    store["attempts"].append(condition)
    store["sources"][event_id] = {"kind": "grade", "criterion_id": criterion_id, "receipt_ids": ids, "grade_digest": evaluation["grade_digest"]}
    store["decisions"][obligation] = decision


def prepare_rearm(context, payload):
    from evidence_bridge import _fresh
    _fresh(context)
    state = context["state"]
    fields = {"task_id", "criterion_id", "receipt_id", "rationale_ref"}
    _object(payload, fields, fields)
    if (payload["task_id"] is None) == (payload["criterion_id"] is None):
        raise ValueError("Rearm requires one stable task or quality obligation")
    criterion = payload["criterion_id"]
    criteria = [criterion] if criterion is not None else _node(state["extensions"]["workflow"], payload["task_id"])["criteria"]
    obligation = _lineage(state, criteria)
    store = _store(copy.deepcopy(state))
    prior = next((item for item in reversed(store["attempts"]) if item["obligation_id"] == obligation and item["failure_id"]), None)
    if prior is None:
        raise ValueError("Rearm has no retained failed condition")
    kind = "quality_resolution" if criterion is not None else "retry_clearance"
    record = _evidence(state, context, payload["receipt_id"], kind)
    data = record["data"]
    facts = copy.deepcopy(prior["relevant_state"]["facts"])
    strategy = copy.deepcopy(prior["strategy"])
    quality = None
    if criterion is not None:
        old = state["extensions"]["workflow"]["quality"].get(criterion)
        if not old or old["grade_digest"] != prior["grade_digest"]:
            raise ValueError("Quality rearm is not the current failed grade")
        new = {}
        for ident in data.get("receipt_ids", []):
            review = _evidence(state, context, ident, "quality_observation")
            new[ident] = {"digest": review["digest"], "artifact_id": review["data"]["artifact_id"], "artifact_digest": review["data"]["artifact_digest"]}
        expected = quality_resolution_requirements(old, criterion, new)
        if any(data.get(key) != value for key, value in expected.items()):
            raise ValueError("Rearm resolution does not bind the exact repaired output")
        facts["artifacts"] = {item["artifact_id"]: item["artifact_digest"] for item in new.values()}
        quality = {"mode": "grade_resolution", "prior_grade_digest": prior["grade_digest"], "receipt_id": record["id"], "digest": record["digest"]}
        rearm_kind = "quality_repair"
    else:
        binding = retry_binding(state, payload["task_id"])
        if any(data.get(key) != value for key, value in binding.items()):
            raise ValueError("Retry evidence does not bind current blocking condition")
        # Only authenticated user instruction is an explicit rearm. Native
        # retry-clearance already verifies its exact tool/user source.
        source = data.get("source", {})
        if source.get("kind") != "native-user":
            raise ValueError("Retry rearm needs an authenticated new user instruction")
        if payload["rationale_ref"] is not None:
            strategy = _strategy(state, context, None, payload["rationale_ref"])
            rearm_kind = "strategy_change"
        else:
            rearm_kind = "explicit_instruction"
    raw = {"schema_version": 1, "event_id": "rearm:" + context["command_id"], "source_digest": record["digest"],
        "revision": state["revision"] + 1, "run_id": state["run_id"], "obligation_id": obligation,
        "bindings_digest": _digest(_bindings(state)), "failure_id": prior["failure_id"],
        "prior_failure_digest": prior["failure_digest"], "prior_attempt_id": prior["attempt_id"],
        "kind": rearm_kind, "strategy": strategy, "relevant_state": {"facts": facts, "evidence_ids": [record["id"]]},
        "evidence_ids": [record["id"]], "effect_id": None, "effect_status": None, "quality_resolution": quality}
    from persistence_policy import decide_attempt
    decision = decide_attempt(prior, _history(state, context), raw, _policy_admission(state, context, obligation))
    if decision["accepted_rearm"] is None or not decision["allow_attempt"]:
        raise ValueError("Current owner policy does not admit the proposed rearm")
    return {"rearm": decision["accepted_rearm"], "decision": decision, "source": copy.deepcopy(payload), "head": _head(state, context)}


def rearm(state, payload, context):
    _object(payload, {"rearm", "decision", "source", "head"}, {"rearm", "decision", "source", "head"})
    if payload["head"] != _head(state, context):
        raise ValueError("Rearm preparation became stale")
    result, flow = _base(state, context)
    store = _store(result)
    store["rearms"].append(copy.deepcopy(payload["rearm"]))
    store["sources"][payload["rearm"]["event_id"]] = copy.deepcopy(payload["source"])
    store["decisions"][payload["rearm"]["obligation_id"]] = copy.deepcopy(payload["decision"])
    if payload["source"]["task_id"]:
        _node(flow, payload["source"]["task_id"]).update(status="pending", reason="Verified policy rearm")
    return result


def prepare_grade(state, payload, context):
    """Return an exact rearm command requirement; the facade commits the step."""
    _head(state, context)
    criterion = payload["criterion_id"]
    old = state["extensions"]["workflow"]["quality"].get(criterion)
    if not old or old["verdict"] not in {"FAIL", "DISAGREEMENT"}:
        return None
    ident = payload.get("resolution_receipt_id")
    proof = _evidence(state, context, ident, "quality_resolution")
    if proof["data"].get("prior_grade_digest") != old["grade_digest"]:
        raise ValueError("Grade preparation requires the exact prior failure")
    store = state.get("extensions", {}).get("workflow_persistence", {})
    existing = [item for item in store.get("rearms", []) if (item.get("quality_resolution") or {}).get("prior_grade_digest") == old["grade_digest"]]
    if existing:
        if existing[-1]["quality_resolution"]["digest"] != proof["digest"]:
            raise ValueError("Prior quality rearm already consumed another resolution")
        return None
    return {"task_id": None, "criterion_id": criterion, "receipt_id": ident, "rationale_ref": None}


def register_preparers(register_preparer):
    register_preparer("workflow.attempt", prepare_attempt)
    register_preparer("workflow.progress", prepare_progress)
    register_preparer("workflow.rearm", prepare_rearm)
    register_preparer("workflow.stop_feedback", prepare_stop_feedback)
    register_preparer("workflow.stop_emit", prepare_stop_emit)


def _current_policy(state, context, task_id):
    from persistence_policy import decide_attempt
    _require_native_clear(state, context)
    flow = state["extensions"]["workflow"]
    node = _node(flow, task_id)
    obligation = _lineage(state, node["criteria"])
    store = state.get("extensions", {}).get("workflow_persistence", {})
    prior = next((item for item in reversed(store.get("attempts", [])) if item["obligation_id"] == obligation), None)
    if prior is None or node["status"] in {"done", "cancelled"}:
        raise ValueError("No current unresolved authenticated attempt")
    active_rearm = next((item for item in reversed(store.get("rearms", []))
                        if item["obligation_id"] == obligation and item["revision"] > prior["revision"]), None)
    source = store.get("sources", {}).get((active_rearm or prior)["event_id"])
    if not isinstance(source, dict):
        raise ValueError("Retained policy observation has no source binding")
    if active_rearm:
        _evidence(state, context, source["receipt_id"], "quality_resolution" if source["criterion_id"] else "retry_clearance")
        if source["rationale_ref"] is not None:
            strategy_context = {**context, "project": context["binding"]["project_root"]}
            if _strategy(state, strategy_context, None, source["rationale_ref"]) != active_rearm["strategy"]:
                raise ValueError("Admitted strategy changed after its rearm commit")
    elif source.get("kind") == "grade":
        for ident in source["receipt_ids"]:
            _evidence(state, context, ident, "quality_observation")
    else:
        records, native = _authenticated_observations(state, context, source["observation_ids"])
        # The native readback carries a current revision. Source identity uses
        # immutable normalized events rather than that observation timestamp.
        if native:
            semantic = _native_process(state, context, source, native)
            if semantic[4] != prior["source_digest"]:
                raise ValueError("Native consumer input/output binding changed after its outcome")
        elif not records:
            raise ValueError("Current attempt source is unqualified")
    decision = decide_attempt(prior, _history(state, context), None, _policy_admission(state, context, obligation))
    for related in _related_obligations(state, node["criteria"]):
        if related == obligation:
            continue
        other = next((item for item in reversed(store.get("attempts", [])) if item["obligation_id"] == related), None)
        if other:
            restriction = decide_attempt(other, _history(state, context), None, _policy_admission(state, context, related))
            if not restriction["allow_attempt"]:
                return restriction
    return decision


def stop_feedback_status(state, context):
    result = {"action": "terminal", "reason_code": "no_authenticated_unresolved_attempt",
              "run_id": state["run_id"], "task_id": None, "obligation_id": None}
    try:
        _head(state, context)
        flow = state.get("extensions", {}).get("workflow", {})
        if state["status"] in {"completed", "cancelled", "incomplete"}:
            return {**result, "reason_code": "terminal_run"}
        nodes = flow.get("graph", {}).get("nodes", {})
        candidates = []
        for task_id, node in nodes.items():
            if node["status"] in {"done", "cancelled"} or not all(nodes[dep]["status"] == "done" for dep in node["deps"]):
                continue
            obligation = _lineage(state, node["criteria"])
            if not any(item["obligation_id"] == obligation for item in state.get("extensions", {}).get("workflow_persistence", {}).get("attempts", [])):
                continue
            decision = _current_policy(state, context, task_id)
            if not decision["allow_attempt"]:
                return {**result, "task_id": task_id, "obligation_id": decision["obligation_id"], "reason_code": decision["reason_code"]}
            used = state.get("extensions", {}).get("workflow_persistence", {}).get("feedback", [])
            if any(row["correction_id"] == decision["correction_id"] for row in used):
                return {**result, "task_id": task_id, "reason_code": "correction_already_reserved"}
            candidates.append((task_id, decision))
        if candidates:
            task_id, decision = candidates[0]
            return {**result, "action": "eligible", "task_id": task_id,
                    "obligation_id": decision["obligation_id"], "reason_code": decision["reason_code"]}
    except (ValueError, KeyError, TypeError, ImportError, OSError):
        return {**result, "reason_code": "owner_verification_unavailable"}
    return result


def _native_session(context, native_event):
    if (not isinstance(native_event, dict) or set(native_event) != {"hook_event_name", "session_id", "stop_hook_active"}
            or native_event["hook_event_name"] not in {"Stop", "SubagentStop"}
            or type(native_event["stop_hook_active"]) is not bool):
        raise ValueError("Invalid native Stop identity")
    native_ref = context["binding"]["native_ref"]
    if native_event["session_id"] != native_ref.split(":", 1)[-1]:
        raise ValueError("Stop native identity does not match the current owner")


def prepare_stop_feedback(context, payload):
    from evidence_bridge import _fresh
    from persistence_policy import stop_disposition
    _fresh(context)
    _object(payload, {"task_id", "native_event"}, {"task_id", "native_event"})
    _native_session(context, payload["native_event"])
    state = context["state"]
    preview = stop_feedback_status(state, context)
    if preview["action"] != "eligible" or preview["task_id"] != payload["task_id"]:
        raise ValueError("Current run does not admit this corrective feedback")
    decision = _current_policy(state, context, payload["task_id"])
    store = state.get("extensions", {}).get("workflow_persistence", {})
    feedback = store.get("feedback", [])
    readback = {"schema_version": 1, "status": "verified", "run_id": state["run_id"],
        "native_session_id": payload["native_event"]["session_id"],
        **{key: decision[key] for key in ("bindings_digest", "decision_digest", "admission_digest", "journal_head_digest", "journal_revision", "history_digest")},
        "cancelled": False, "terminal": False, "evidence_id": "journal:" + _head(state, context)["digest"]}
    disposition = stop_disposition(decision, payload["native_event"], {"schema_version": 1, "status": "verified",
        "run_id": state["run_id"], "diagnostic_ids": sorted({row["diagnostic_id"] for row in feedback}),
        "correction_ids": [row["correction_id"] for row in feedback], "quarantined": [], "owner_readback": readback})
    if disposition["action"] != "corrective":
        raise ValueError("Policy refused corrective feedback")
    return {"task_id": payload["task_id"], "native_event": payload["native_event"],
        "disposition": disposition, "decision": decision, "command_id": context["command_id"], "head": _head(state, context)}


def stop_feedback(state, payload, context):
    if payload["head"] != _head(state, context):
        raise ValueError("Stop reservation became stale")
    result = copy.deepcopy(state)
    store = _store(result)
    disposition = payload["disposition"]
    if any(row["correction_id"] == disposition["correction_id"] for row in store["feedback"]):
        raise ValueError("Stop correction is already reserved")
    row = {"correction_id": disposition["correction_id"], "diagnostic_id": disposition["diagnostic_id"],
        "task_id": payload["task_id"], "native_event": payload["native_event"], "command_id": payload["command_id"],
        "revision": state["revision"] + 1, "status": "reserved", "decision": payload["decision"], "disposition": disposition}
    row["reservation_digest"] = _digest(row)
    store["feedback"].append(row)
    return result


def reserve_stop_feedback(runtime, state, actor, *, project, runtime_root):
    """Reserve exactly one correction in the existing owner transaction."""
    context = runtime.inspect_context(state, actor, project=project)
    preview = stop_feedback_status(state, context)
    if preview["action"] != "eligible":
        return {"schema_version": 1, "action": "terminal", "allow_attempt": False, "emit_diagnostic": True,
            "diagnostic_id": None, "correction_id": None, "reason_code": preview["reason_code"],
            "authority_granted": False, "completion_granted": False, "run_id": state["run_id"], "task_id": preview["task_id"]}
    native = {key: actor["native_payload"][key] for key in ("hook_event_name", "session_id", "stop_hook_active")}
    import uuid
    command_id = "stop-reserve-" + uuid.uuid4().hex
    changed = runtime.apply_command(project, state["run_id"], "workflow.stop_feedback",
        {"task_id": preview["task_id"], "native_event": native}, actor=actor,
        expected_revision=state["revision"], command_id=command_id, runtime_root=runtime_root)
    row = next(row for row in changed["extensions"]["workflow_persistence"]["feedback"] if row["command_id"] == command_id)
    proof = {"schema_version": 1, "run_id": state["run_id"], "project": str(project), "task_id": row["task_id"],
        "correction_id": row["correction_id"], "command_id": command_id, "revision": row["revision"],
        "reservation_digest": row["reservation_digest"]}
    return {**row["disposition"], "run_id": state["run_id"], "task_id": row["task_id"], "reservation": proof}


def _reserved(state, context, proof, native_event):
    fields = {"schema_version", "run_id", "project", "task_id", "correction_id", "command_id", "revision", "reservation_digest"}
    _object(proof, fields, fields)
    if proof["schema_version"] != 1 or proof["run_id"] != state["run_id"] or proof["project"] != str(context["binding"]["project_root"]):
        raise ValueError("Stop proof does not bind this run/project")
    _native_session(context, native_event)
    row = next((item for item in state.get("extensions", {}).get("workflow_persistence", {}).get("feedback", [])
                if item["command_id"] == proof["command_id"]), None)
    if (not row or row["status"] != "reserved" or row["native_event"] != native_event
            or any(row.get(key) != proof[key] for key in ("task_id", "correction_id", "revision", "reservation_digest"))
            or row["reservation_digest"] != _digest({key: value for key, value in row.items() if key != "reservation_digest"})):
        raise ValueError("Stop reservation is missing, changed, emitted or mismatched")
    decision = _current_policy(state, context, proof["task_id"])
    if not decision["allow_attempt"] or decision["correction_id"] != proof["correction_id"]:
        raise ValueError("Stop reservation is no longer eligible")
    return row


def prepare_stop_emit(context, payload):
    from evidence_bridge import _fresh
    _fresh(context)
    _object(payload, {"reservation", "native_event"}, {"reservation", "native_event"})
    _reserved(context["state"], context, payload["reservation"], payload["native_event"])
    return {**copy.deepcopy(payload), "head": _head(context["state"], context)}


def stop_emit(state, payload, context):
    if payload["head"] != _head(state, context):
        raise ValueError("Stop emission became stale")
    result = copy.deepcopy(state)
    row = next(row for row in _store(result)["feedback"] if row["command_id"] == payload["reservation"]["command_id"])
    if row["status"] != "reserved":
        raise ValueError("Stop reservation already emitted")
    row.update(status="emitted", emitted_revision=state["revision"] + 1)
    return result


def validate_stop_reservation(native_event, proof, *, consume=True):
    """Public launcher boundary. Verify and spend through the original journal."""
    from autopilot import actor_from_hook, default_runtime_root, engine
    actor = actor_from_hook(native_event)
    runtime = engine()
    project = proof["project"]
    state = runtime.load_run(project, proof["run_id"])
    context = runtime.inspect_context(state, actor, project=project)
    _reserved(state, context, proof, {key: native_event[key] for key in ("hook_event_name", "session_id", "stop_hook_active")})
    if consume:
        import uuid
        runtime.apply_command(project, state["run_id"], "workflow.stop_emit",
            {"reservation": proof, "native_event": {key: native_event[key] for key in ("hook_event_name", "session_id", "stop_hook_active")}},
            actor=actor, command_id="stop-emit-" + uuid.uuid4().hex,
            expected_revision=state["revision"], runtime_root=default_runtime_root())
    return True

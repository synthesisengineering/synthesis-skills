#!/usr/bin/env python3
"""Decisive questions and real observations in the existing run journal.

Questions explain which decision changes, the two predicted observations,
their consequences and their affected acceptance closure. Registered Python
consumers supply observations through the existing sandbox/evidence owner.
No confidence score, prose resolution, or caller-provided result is accepted.
"""
from __future__ import annotations

from copy import deepcopy

from consumer_checks import _json, _registered, _same_json, current_observation
from domain_quality import _id, _ids, _object, _text, digest

FIELDS = {"id", "decision", "why_decisive", "if_supported", "if_refuted", "affected_criteria",
          "observation_check_id", "cost_rank", "expected_supported", "expected_refuted"}
MAX_QUESTIONS = 64


def _items(state):
    return state.get("extensions", {}).get("decision_uncertainty", {}).get("items", {})


def validate_question(value):
    _object(value, FIELDS, "decisive uncertainty")
    _id(value["id"]); _id(value["observation_check_id"])
    for key in ("decision", "why_decisive", "if_supported", "if_refuted"):
        _text(value[key], key)
    _ids(value["affected_criteria"])
    if (value["if_supported"].strip() == value["if_refuted"].strip()
            or _same_json(value["expected_supported"], value["expected_refuted"])):
        raise ValueError("decisive uncertainty needs distinct predictions and decision branches")
    if type(value["cost_rank"]) is not int or not 0 <= value["cost_rank"] <= 1000000:
        raise ValueError("observation cost rank must be a bounded relative priority, not measured cost")
    if len(str(value["expected_supported"])) + len(str(value["expected_refuted"])) > 32768:
        raise ValueError("predicted observations exceed the bound")
    return deepcopy(value)


def prepare_question(context, payload):
    value = validate_question(payload)
    state = context["state"]
    criteria = {row["id"] for row in state["contract"]["criteria"]}
    if not set(value["affected_criteria"]) <= criteria:
        raise ValueError("uncertainty cannot invent acceptance criteria")
    path, registered = _registered(context, value["observation_check_id"])
    spec = _json(path.read_bytes())
    if (registered.get("role") != "input" or not isinstance(spec, dict)
            or spec.get("kind") != "python-consumer" or spec.get("schema_version") != 1
            or spec.get("criterion_id") not in value["affected_criteria"]):
        raise ValueError("uncertainty needs an existing affected-criterion consumer specification")
    _, program = _registered(context, spec.get("script_artifact_id"))
    if program.get("role") != "input":
        raise ValueError("uncertainty observation program must be a registered input")
    value["bindings"] = {"run_id": state["run_id"]}
    value["criteria_digests"] = {row["id"]: digest(row) for row in state["contract"]["criteria"] if row["id"] in value["affected_criteria"]}
    prior = _items(state).get(value["id"])
    if prior and {key: prior[key] for key in value} != value:
        raise ValueError("decisive question identity is immutable; retain the earlier decision record")
    return value


def register_question(state, prepared, context):
    result = deepcopy(state)
    rows = result.setdefault("extensions", {}).setdefault("decision_uncertainty", {"schema_version": 1, "items": {}})["items"]
    if prepared["id"] not in rows:
        if len(rows) >= MAX_QUESTIONS:
            raise ValueError("decisive uncertainty collection exceeds its bound")
        rows[prepared["id"]] = {**deepcopy(prepared), "resolutions": []}
    elif any(rows[prepared["id"]].get(key) != value for key, value in prepared.items()):
        raise ValueError("decisive question identity is immutable")
    return result


def _resolution(item, receipt_id, context):
    if any(item["bindings"][key] != context["state"][key] for key in item["bindings"]):
        raise ValueError("uncertainty belongs to an earlier contract or profile")
    current_criteria = {row["id"]: digest(row) for row in context["state"]["contract"]["criteria"] if row["id"] in item["affected_criteria"]}
    if current_criteria != item["criteria_digests"]:
        raise ValueError("affected acceptance criteria changed; explicitly revise the decisive question")
    record, spec, observed = current_observation(context, receipt_id, item["observation_check_id"])
    if spec["criterion_id"] not in item["affected_criteria"]:
        raise ValueError("observation no longer belongs to the affected decision")
    branch = next((name for name in ("supported", "refuted") if _same_json(observed, item["expected_" + name])), None)
    if branch is None:
        raise ValueError("actual observation establishes neither predicted decision branch")
    return {"receipt_id": receipt_id, "receipt_digest": record["digest"], "branch": branch,
            "observation_digest": digest(observed), "input_digests": deepcopy(record["data"]["input_digests"])}


def prepare_resolution(context, payload):
    _object(payload, {"id", "receipt_id"}, "uncertainty observation")
    _id(payload["id"]); _id(payload["receipt_id"])
    item = _items(context["state"]).get(payload["id"])
    if item is None:
        raise ValueError("unknown decisive question")
    return {"id": payload["id"], "resolution": _resolution(item, payload["receipt_id"], context)}


def resolve_question(state, prepared, context):
    result = deepcopy(state)
    row = result["extensions"]["decision_uncertainty"]["items"][prepared["id"]]
    resolution = prepared["resolution"]
    if resolution not in row["resolutions"]:
        if len(row["resolutions"]) >= 32:
            raise ValueError("uncertainty resolution history exhausted; repeated work requires a new admitted outcome plan")
        row["resolutions"].append(deepcopy(resolution))
    return result


def question_digest(item):
    return digest({key: value for key, value in item.items() if key != "prior_versions"})


def prepare_revision(context, payload):
    _object(payload, {"id", "expected_question_digest", "question", "reason"}, "uncertainty revision")
    _id(payload["id"])
    _text(payload["reason"], "question revision reason")
    old = _items(context["state"]).get(payload["id"])
    if old is None or payload["expected_question_digest"] != question_digest(old):
        raise ValueError("question revision basis is missing, changed or stale")
    if not isinstance(payload["question"], dict) or payload["question"].get("id") != payload["id"]:
        raise ValueError("question revision cannot change its identity")
    candidate = deepcopy(context["state"])
    candidate["extensions"]["decision_uncertainty"]["items"].pop(payload["id"])
    fresh = prepare_question({**context, "state": candidate}, payload["question"])
    if all(old.get(key) == value for key, value in fresh.items()):
        raise ValueError("unchanged question does not justify another revision")
    if len(old.get("prior_versions", [])) >= 16:
        raise ValueError("question revision history exhausted; preserve it in a newly admitted plan")
    return {"id": payload["id"], "expected_question_digest": payload["expected_question_digest"],
            "reason": payload["reason"], "question": fresh}


def revise_question(state, prepared, context):
    result = deepcopy(state)
    rows = result["extensions"]["decision_uncertainty"]["items"]
    old = rows[prepared["id"]]
    if question_digest(old) != prepared["expected_question_digest"]:
        raise ValueError("question changed after revision preparation")
    history = deepcopy(old.get("prior_versions", []))
    history.append({"question": {key: value for key, value in old.items() if key != "prior_versions"},
                    "reason": prepared["reason"], "digest": question_digest(old)})
    rows[prepared["id"]] = {**deepcopy(prepared["question"]), "resolutions": [], "prior_versions": history}
    return result


def status_view(state, context=None):
    """Current source evidence, never an invented numerical confidence."""
    if context is not None:
        context = {**context, "state": state, "project": context.get("project") or context.get("binding", {}).get("project_root")}
    opened, resolved = [], []
    for identity, item in sorted(_items(state).items(), key=lambda pair: (pair[1]["cost_rank"], pair[0])):
        row = {key: deepcopy(item[key]) for key in ("decision", "why_decisive", "affected_criteria", "observation_check_id", "cost_rank")}
        row["id"] = identity
        row["question_digest"] = question_digest(item)
        proof = item["resolutions"][-1] if item["resolutions"] else None
        current = False
        detail = "No committed observation has resolved this decisive question"
        if context is None:
            detail = "Current evidence owner is unavailable"
        elif proof:
            try:
                current = _resolution(item, proof["receipt_id"], context) == proof
                detail = "Exact current executed observation" if current else "Recorded observation proof changed"
            except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
                detail = str(exc)
        row["evidence_status"] = "current" if current else "unknown" if context is None else "unresolved"
        row["evidence_reason"] = detail
        if current:
            resolved.append({**row, **deepcopy(proof), "consequence": item["if_" + proof["branch"]]})
        else:
            opened.append(row)
    return {"status": "unknown" if opened and context is None else "unresolved" if opened else "clear",
            "open": opened, "resolved": resolved,
            "affected_criteria": sorted({identity for item in opened for identity in item["affected_criteria"]})}


def validate_command(state, command, payload, context):
    if not _items(state):
        return
    affected = None
    if command == "workflow.task" and payload.get("action") in {"start", "retry", "complete"}:
        node = state.get("extensions", {}).get("workflow", {}).get("graph", {}).get("nodes", {}).get(payload.get("task_id"), {})
        affected = set(node.get("criteria", []))
    elif command == "workflow.dispatch":
        node = state.get("extensions", {}).get("workflow", {}).get("graph", {}).get("nodes", {}).get(payload.get("task_id"), {})
        affected = set(node.get("criteria", [])) | set(payload.get("criteria", []))
    elif command == "verify":
        affected = set(payload.get("criteria", []))
    elif command == "close" and payload.get("status") == "completed":
        affected = {row["id"] for row in state["contract"]["criteria"]}
    if affected is not None and affected.intersection(status_view(state, context)["affected_criteria"]):
        raise ValueError("decisive uncertainty remains unresolved for the requested acceptance closure")


def register(engine):
    engine.register_command("decision.question", register_question)
    engine.register_preparer("decision.question", prepare_question)
    engine.register_command("decision.resolve", resolve_question)
    engine.register_preparer("decision.resolve", prepare_resolution)
    engine.register_command("decision.revise", revise_question)
    engine.register_preparer("decision.revise", prepare_revision)
    engine.register_constraint("decision.uncertainty", validate_command)

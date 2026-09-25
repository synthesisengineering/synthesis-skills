#!/usr/bin/env python3
"""Pure stable MSP translation, not a host, permission owner or scheduler.

The exact stable schema is exported by Muse 1.3.0-R3401.1. The official Python
SDK documentation describes a different experimental fingerprint; this adapter
never opts into that surface. Native status, approval and acknowledgement facts
cannot complete portable work or authorize an effect. The existing owner keeps
wire custody, opaque-cursor reconciliation, item revision folding and tombstones.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import math
import uuid


ADAPTER_VERSION = "muse-dialect-v1"
STABLE_FINGERPRINT = "sha256:7469c9e352e67def4a59df7e439984d7194fa351e1c8b7abb34060fd977ced81"
DOCUMENTED_EXPERIMENTAL_FINGERPRINT = "sha256:2db88d9ee93131257757ab3cf74026eab9079813a4cb82c45cc231901a170fc6"
SUPPORTED_SCHEMAS = ("runtime.session.terminal", "tool_batch.effect.terminal")
NOTIFICATION_FIELDS = {
    "session/tokenUsage": {"cumulative", "promptTokens", "sessionId", "sourceRange", "totalTokens", "turnId", "usage", "viewCursor"},
    "session/goalChanged": {"sessionId", "sourceRange", "viewCursor"},
    "turn/started": {"commandId", "sessionId", "sourceRange", "turnId", "viewCursor"},
    "turn/completed": {"sessionId", "sourceRange", "terminal", "turnId", "viewCursor"},
    "item/started": {"item", "sessionId", "viewCursor"},
    "item/updated": {"item", "sessionId", "sourceRange", "viewCursor"},
    "item/completed": {"item", "sessionId", "sourceRange", "viewCursor"},
    "item/delta": {"delta", "itemId", "sessionId", "viewCursor"},
    "approval/requested": {"approvalId", "availableChoices", "currentRequirementId", "itemId", "judgeEscalated", "protectedWrite",
                           "rawArgs", "sessionId", "sourceRange", "subject", "taskId", "toolCallId", "toolName", "turnId", "viewCursor"},
    "approval/updated": {"approvalId", "availableChoices", "change", "currentRequirementId", "sessionId", "sourceRange", "subject", "viewCursor"},
    "approval/resolved": {"approvalId", "decision", "itemId", "policyResult", "resolvedBy", "sessionId", "sourceRange", "stageEvidence", "turnId", "viewCursor"},
    "view/gap": {"after", "next", "sessionId"},
}
# Required and accepted parameters from the stable export. This deliberately
# excludes approval/decide, configuration/grant writes and experimental methods.
REQUEST_FIELDS = {
    "session/read": ({"sessionId"}, {"sessionId", "excludeItems"}),
    "session/resume": ({"commandId", "sessionId"}, {"commandId", "sessionId", "cursor", "excludeItems", "history"}),
    "view/page": ({"sessionId", "limit"}, {"sessionId", "limit", "cursor", "anchor", "direction"}),
    "view/subscribe": ({"sessionId"}, {"sessionId", "after"}),
    "view/unsubscribe": ({"sessionId"}, {"sessionId"}),
    "item/readOutput": ({"sessionId", "itemId", "outputRef"}, {"sessionId", "itemId", "outputRef", "offsetBytes", "lengthBytes"}),
    "goal/set": ({"sessionId", "commandId", "objective"}, {"sessionId", "commandId", "objective"}),
    "goal/edit": ({"sessionId", "commandId", "objective"}, {"sessionId", "commandId", "objective"}),
    "goal/pause": ({"sessionId", "commandId"}, {"sessionId", "commandId"}),
    "goal/resume": ({"sessionId", "commandId"}, {"sessionId", "commandId"}),
    "goal/clear": ({"sessionId", "commandId"}, {"sessionId", "commandId"}),
    "turn/interrupt": ({"sessionId", "commandId"}, {"sessionId", "commandId", "turnId", "retract"}),
    "turn/cancel": ({"sessionId", "commandId"}, {"sessionId", "commandId", "turnId"}),
    "turn/unqueue": ({"sessionId", "commandId", "turnId"}, {"sessionId", "commandId", "turnId"}),
    "task/stop": ({"sessionId", "commandId", "taskId"}, {"sessionId", "commandId", "taskId"}),
    "task/stopAll": ({"sessionId", "commandId"}, {"sessionId", "commandId"}),
    "subagent/stop": ({"sessionId", "commandId", "subagentId"}, {"sessionId", "commandId", "subagentId", "reason"}),
    "subagent/interrupt": ({"sessionId", "commandId", "subagentId"}, {"sessionId", "commandId", "subagentId", "reason"}),
    "workflow/cancel": ({"sessionId", "commandId", "workflowRunId"}, {"sessionId", "commandId", "workflowRunId"}),
    "workflow/childControl": ({"sessionId", "commandId", "workflowRunId", "childId", "attempt", "action"},
                              {"sessionId", "commandId", "workflowRunId", "childId", "attempt", "action"}),
    "approval/listPending": ({"sessionId"}, {"sessionId"}),
    "usage/read": (set(), set()),
}
CANCELLATION_SCOPES = {
    "turn/interrupt": "foreground_turn", "turn/cancel": "foreground_turn_normal_lane",
    "turn/unqueue": "queued_turn", "task/stop": "single_background_task",
    "task/stopAll": "background_tasks_excludes_subagents", "subagent/stop": "single_subagent",
    "subagent/interrupt": "single_subagent_turn", "workflow/cancel": "single_workflow",
    "workflow/childControl": "exact_workflow_child_attempt",
}


class DialectError(ValueError):
    """Malformed, unsupported or conflicting candidate; never an authorization."""


def _object(value, label):
    if not isinstance(value, dict): raise DialectError(f"{label} must be an object")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise DialectError(f"invalid {label}")
    return value


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum: raise DialectError(f"invalid {label}")
    return value


def _require(value, fields, label):
    _object(value, label)
    if not fields <= value.keys(): raise DialectError(f"{label} lacks required fields")


def _bounded(value, depth=0, _budget=None):
    # This cap applies to the whole candidate, not separately to every string.
    budget = _budget if _budget is not None else {"nodes": 0, "bytes": 0}
    budget["nodes"] += 1
    if depth > 32 or budget["nodes"] > 16384:
        raise DialectError("JSON structure exceeds decoder bound")
    if isinstance(value, dict):
        if len(value) > 1024 or any(not isinstance(key, str) for key in value):
            raise DialectError("invalid or oversized object")
        for key, item in value.items():
            _bounded(key, depth + 1, budget)
            _bounded(item, depth + 1, budget)
    elif isinstance(value, list):
        if len(value) > 1024:
            raise DialectError("array exceeds decoder bound")
        for item in value:
            _bounded(item, depth + 1, budget)
    elif isinstance(value, str):
        if len(value) > 1024 * 1024:
            raise DialectError("string exceeds decoder bound")
        try:
            budget["bytes"] += len(value.encode("utf-8"))
        except UnicodeError as exc:
            raise DialectError("invalid Unicode scalar") from exc
        if budget["bytes"] > 1024 * 1024:
            raise DialectError("combined JSON body exceeds decoder bound")
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise DialectError("non-JSON value")
    elif isinstance(value, float) and not math.isfinite(value):
        raise DialectError("nonfinite number")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _producer(producer):
    _object(producer, "producer")
    if producer.get("client") != "muse": raise DialectError("wrong client")
    _text(producer.get("thread_id"), "native session")
    _text(producer.get("root_session_id"), "root session")
    return producer


def _source_range(value):
    _require(value, {"stream", "first", "last"}, "source range")
    _require(value["stream"], {"kind", "id"}, "stream")
    for key in ("kind", "id"): _text(value["stream"][key], "stream " + key)
    for endpoint in ("first", "last"):
        _require(value[endpoint], {"id", "sequence"}, "record position")
        _text(value[endpoint]["id"], "record id")
        _integer(value[endpoint]["sequence"], "record sequence")
    # No ordering arithmetic or raw-log lookup is inferred from this token.


def _fact(kind, status, data, params, binding, *, index=0, record=None):
    mode = binding.get("mode", "synthetic")
    if mode not in {"synthetic", "native"}: raise DialectError("invalid mode")
    row = record or {}
    return {"kind": kind, "status": status, "data": deepcopy(data),
            "native": {"record_id": row.get("id"), "ordinal": None, "sequence": row.get("sequence"),
                       "subrecord": index, "call_id": data.get("call_id"), "parent_call_id": None,
                       "view_cursor": params.get("viewCursor"), "source_range": deepcopy(params.get("sourceRange"))},
            "native_timestamp": row.get("recorded_at"), "source_locator": deepcopy(binding.get("source_locator")),
            "mode": mode, "authentication": "owner_admission_required"}


def qualify_source(header, *, expected_root_session_id, expected_thread_id=None,
                   expected_parent_thread_id=None, expected_agent_id=None):
    _bounded(header); _object(header, "source header")
    _text(expected_root_session_id, "expected root")
    thread = expected_thread_id if expected_thread_id is not None else expected_root_session_id
    _text(thread, "expected thread")
    if thread != expected_root_session_id or expected_parent_thread_id is not None or expected_agent_id is not None:
        raise DialectError("Muse raw child lineage requires an owner-qualified dispatch source")
    stream = _object(header.get("stream"), "native stream")
    if type(header.get("schema_version")) is not int or header["schema_version"] != 1 or stream.get("kind") != "session" or stream.get("id") != thread:
        raise DialectError("native session source mismatch")
    return {"client": "muse", "surface": "source-file", "thread_id": thread,
            "root_session_id": expected_root_session_id, "parent_thread_id": None,
            "adapter_version": ADAPTER_VERSION, "authentication": "owner_admission_required", "root_authority": False}


def is_ignored_projection(projected, producer):
    _producer(producer)
    return False


def decode_record(row, producer, *, mode="synthetic", source_locator=None):
    """Only genuine selected raw terminal dialects are enrolled, not all log kinds."""
    _bounded(row); _producer(producer)
    _require(row, {"schema_version", "id", "stream", "sequence", "payload_type", "payload_schema_version", "payload"}, "raw record")
    if (type(row["schema_version"]) is not int or type(row["payload_schema_version"]) is not int
            or row["schema_version"] != 1 or row["payload_schema_version"] != 1):
        raise DialectError("unsupported raw schema version")
    if row["stream"] != {"kind": "session", "id": producer["thread_id"]}:
        raise DialectError("raw session stream mismatch")
    _integer(row["sequence"], "source sequence"); _text(row["id"], "record identity")
    payload = _object(row["payload"], "payload")
    binding = {"producer": producer, "mode": mode, "source_locator": source_locator}
    if row["payload_type"] == "runtime.session":
        event = _object(payload.get("event"), "runtime event")
        if event.get("kind") != "terminal": raise DialectError("unsupported raw runtime event")
        terminal = _text(event.get("terminal"), "run terminal")
        data = {"run_id": _text(payload.get("run_id"), "run id"), "native_status": terminal,
                "native_reason": event.get("reason"), "portable_completion": False,
                "source_run_record_id": payload.get("source_run_record_id"),
                "source_run_record_sequence": payload.get("source_run_record_sequence")}
        status = "failed" if terminal == "failed" else "observed" if terminal in {"completed", "cancelled"} else "terminal_unknown"
        return [_fact("lifecycle.completed", status, data, {}, binding, record=row)]
    if row["payload_type"] == "tool_batch.effect.terminal":
        effect = _object(payload.get("record"), "effect record")
        if effect.get("kind") != "terminal": raise DialectError("contradictory effect terminal")
        outcome = _object(effect.get("outcome"), "effect outcome")
        native_status = _text(outcome.get("kind"), "effect status")
        data = {"run_id": _text(payload.get("run_id"), "run identity"),
                "effect_id": _text(effect.get("effect_id"), "effect id"),
                "task_id": _text(effect.get("task_id"), "task id"),
                "call_id": _text(effect.get("call_id"), "call id"), "native_status": native_status,
                "native_outcome": outcome, "portable_completion": False,
                "effect_ambiguity": "owner_reconciliation_required"}
        return [_fact("tool.result", "failed" if native_status in {"failed", "rejected"} else "observed" if native_status in {"completed", "cancelled"} else "terminal_unknown", data, {}, binding, record=row)]
    raise DialectError("unsupported Muse raw record or retained frame")


def _wire_binding(binding):
    _object(binding, "wire binding"); _producer(binding.get("producer"))
    if binding.get("schema_fingerprint") != STABLE_FINGERPRINT or binding.get("experimental_api") is not False:
        raise DialectError("stable wire fingerprint/feature set not matched")
    return binding["producer"]


def _raw_usage(value):
    _require(value, {"inputTokens", "outputTokens", "cachedTokens", "reasoningTokens"}, "raw usage")
    allowed = {"inputTokens", "outputTokens", "cachedTokens", "reasoningTokens", "cacheReadTokens", "cacheWriteTokens"}
    for key in allowed & value.keys(): _integer(value[key], key)
    return deepcopy(value)


def _usage(params, producer):
    raw = _raw_usage(params["usage"])
    for key in ("promptTokens", "totalTokens"): _integer(params[key], key)
    if params["promptTokens"] + raw["outputTokens"] != params["totalTokens"]:
        raise DialectError("counted-once total contradicts components")
    totals = _object(params["cumulative"], "cumulative counters")
    _require(totals, {"promptTokens", "outputTokens", "totalTokens"}, "cumulative counters")
    for key in ("promptTokens", "outputTokens", "totalTokens"): _integer(totals[key], key)
    if totals["promptTokens"] + totals["outputTokens"] != totals["totalTokens"]:
        raise DialectError("cumulative total contradiction")
    last = {"prompt_tokens": params["promptTokens"], "output_tokens": raw["outputTokens"], "total_tokens": params["totalTokens"]}
    return {"grammar": "muse.session_usage", "scope": {"kind": "native_session", **{key: producer.get(key)
             for key in ("thread_id", "root_session_id", "parent_thread_id")}}, "units": "tokens",
            "measurement_id": ["muse", producer["thread_id"], params["viewCursor"]],
            "response_id": None, "turn_id": params["turnId"], "phase": "final", "countable": True,
            "last": last, "totals": {"prompt_tokens": totals["promptTokens"], "output_tokens": totals["outputTokens"], "total_tokens": totals["totalTokens"]},
            "turn_totals": None, "raw_usage": raw, "counters_digest": _digest({"counted": last, "raw": raw}),
            "aggregation": "per_response", "child_usage_included": False, "scope_nonoverlap": "UNKNOWN",
            "billing_cost": None, "missingness": ["full_execution_tree_not_proven"]}


def _notification(method, params, binding):
    if method not in NOTIFICATION_FIELDS: raise DialectError("unsupported MSP notification")
    _require(params, NOTIFICATION_FIELDS[method], "notification")
    producer = binding["producer"]
    if params["sessionId"] != producer["thread_id"]: raise DialectError("wire session mismatch")
    if "viewCursor" in params: _text(params["viewCursor"], "opaque view cursor")
    if "sourceRange" in params: _source_range(params["sourceRange"])
    if method == "view/gap":
        for field in ("after", "next"): _text(params[field], field)
        return [_fact("coverage.gap", "unknown", {"after": params["after"], "next": params["next"],
                      "coverage_complete": False, "gap_reconciled": False}, params, binding)]
    if method == "session/tokenUsage":
        _text(params["turnId"], "turn id")
        return [_fact("usage.snapshot", "observed", _usage(params, producer), params, binding)]
    if method == "session/goalChanged":
        if "goal" not in params:
            return [_fact("goal.snapshot", "unknown", {"native_status": "unknown", "portable_completion": False,
                          "missingness": ["goal_member_absent"]}, params, binding)]
        goal = params["goal"]
        if goal is None:
            return [_fact("goal.cleared", "observed", {"native_status": "cleared", "portable_completion": False,
                          "schema_note": "explicit_null_is_documented_in_stable_field_description"}, params, binding)]
        _require(goal, {"objective", "status", "percentComplete"}, "goal")
        _text(goal["objective"], "objective"); _text(goal["status"], "goal status")
        if type(goal["percentComplete"]) is not int: raise DialectError("goal percent must be an integer")
        data = {"objective_digest": _digest(goal["objective"]), "native_status": goal["status"],
                "percent_complete": goal["percentComplete"], "native_goal_epoch": None,
                "portable_completion": False, "missingness": ["native_goal_epoch_not_supplied"]}
        # The protocol intentionally does not close the Goal status vocabulary.
        return [_fact("goal.updated", "unknown", data, params, binding)]
    if method.startswith("turn/"):
        _text(params["turnId"], "turn identity")
        if method == "turn/started":
            _text(params["commandId"], "command identity")
            return [_fact("lifecycle.started", "observed", {"turn_id": params["turnId"], "command_id": params["commandId"],
                          "native_status": "started", "portable_completion": False}, params, binding)]
        terminal = _text(params["terminal"], "terminal status")
        status = "failed" if terminal == "failed" else "observed" if terminal in {"completed", "cancelled"} else "terminal_unknown"
        data = {"turn_id": params["turnId"], "native_status": terminal, "native_error": params.get("error"),
                "native_reason": params.get("reason"), "portable_completion": False,
                "aggregate_usage": _raw_usage(params["usage"]) if "usage" in params else None,
                "usage_aggregation": "turn_aggregate_not_additive_to_response_usage"}
        return [_fact("lifecycle.completed", status, data, params, binding)]
    if method == "item/delta":
        _text(params["itemId"], "item id")
        if not isinstance(params["delta"], str) or ("field" in params and not isinstance(params["field"], str)):
            raise DialectError("item delta must remain typed text")
        return [_fact("item.delta", "observed", {"item_id": params["itemId"], "field": params.get("field"),
                      "delta": params["delta"], "ephemeral": True, "portable_completion": False}, params, binding)]
    if method.startswith("item/"):
        item = _object(params["item"], "item")
        _require(item, {"itemId", "kind", "revision", "status"}, "item")
        for field in ("itemId", "kind", "status"): _text(item[field], field)
        for field in ("callId", "taskId", "childSessionId", "subagentId", "workflowRunId", "approvalId", "turnId", "commandId"):
            if field in item: _text(item[field], field)
        _integer(item["revision"], "revision", 1)
        if "usage" in item: _raw_usage(item["usage"])
        if "children" in item:
            if not isinstance(item["children"], list): raise DialectError("workflow children must be an array")
            for child in item["children"]:
                _require(child, {"attempt", "childId", "status"}, "workflow child")
                _integer(child["attempt"], "child attempt", 1)
                _text(child["childId"], "child id"); _text(child["status"], "child status")
                if "usage" in child: _raw_usage(child["usage"])
        native_status = item["status"]
        known = {"inProgress", "completed", "failed", "cancelled", "rejected", "timedOut"}
        status = "failed" if native_status in {"failed", "rejected", "timedOut"} else "observed" if native_status in known else "terminal_unknown" if method == "item/completed" else "unknown"
        if method == "item/completed" and native_status == "inProgress": raise DialectError("completed item remains in progress")
        data = {"item_id": item["itemId"], "item_kind": item["kind"], "revision": item["revision"],
                "replacement_key": [producer["thread_id"], item["itemId"]], "native_status": native_status,
                "call_id": item.get("callId"), "child_session_id": item.get("childSessionId"),
                "native_item": item, "portable_completion": False, "output_complete": item.get("truncated") is False,
                "effect_ambiguity": "owner_reconciliation_required",
                "usage_aggregation": "owning_item_transitive_aggregate" if "usage" in item else None,
                "scope_nonoverlap": "UNKNOWN"}
        return [_fact("item." + method.split("/")[1], status, data, params, binding)]
    _text(params["approvalId"], "approval id")
    for field in ("itemId", "turnId", "taskId", "toolCallId", "toolName", "decision", "policyResult", "resolvedBy"):
        if field in params: _text(params[field], field)
    for field in ("availableChoices", "stageEvidence"):
        if field in params and not isinstance(params[field], list): raise DialectError("approval field must be an array")
    for field in ("judgeEscalated", "protectedWrite"):
        if field in params and type(params[field]) is not bool: raise DialectError("approval flag must be boolean")
    if "rawArgs" in params and not isinstance(params["rawArgs"], str): raise DialectError("approval args must stay text")
    if "currentRequirementId" in params:
        requirement = params["currentRequirementId"]
        _require(requirement, {"approvalId", "sourceIndex"}, "approval requirement")
        if requirement["approvalId"] != params["approvalId"]: raise DialectError("approval requirement mismatch")
        _integer(requirement["sourceIndex"], "approval source index")
    return [_fact("approval." + method.split("/")[1], "observed", {
        "approval_id": params["approvalId"], "native_approval": params,
        "grants_authority": False, "human_identity_proven": False, "portable_completion": False}, params, binding)]


def _response(message, binding):
    request = _object(binding.get("pending_request"), "pending request")
    if "id" not in request or "id" not in message or type(request["id"]) is not type(message["id"]) or request["id"] != message["id"]:
        raise DialectError("unbound or stale request result")
    method = request.get("method")
    if method not in REQUEST_FIELDS: raise DialectError("unsupported response operation")
    params = _object(request.get("params", {}), "pending params")
    producer = binding["producer"]
    if method != "usage/read" and params.get("sessionId") != producer["thread_id"]:
        raise DialectError("pending request session mismatch")
    if ("result" in message) == ("error" in message): raise DialectError("wire response requires exactly one result or error")
    if "error" in message:
        error = _object(message["error"], "wire error")
        if type(error.get("code")) is not int: raise DialectError("wire error lacks numeric code")
        return [_fact("command.rejected", "failed", {"operation": method, "request_id": message["id"],
                      "native_error": error, "effect_ambiguity": "owner_reconciliation_required",
                      "portable_completion": False}, {}, binding)]
    result = _object(message["result"], "wire result")
    if "commandId" in params and method != "session/resume":
        _require(result, {"commandId", "status"}, "command acknowledgement")
        if result["commandId"] != params["commandId"]: raise DialectError("stale command acknowledgement")
        _text(result["status"], "ack status")
        if method in {"goal/pause", "goal/clear"} and "turnId" in result:
            raise DialectError("pause/clear acknowledgement cannot name a turn")
        if "turnId" in params and "turnId" in result and params["turnId"] != result["turnId"]:
            raise DialectError("turn acknowledgement target mismatch")
        return [_fact("command.acknowledged", "observed" if result["status"] == "accepted" else "unknown", {
            "operation": method, "request_id": message["id"], "command_id": result["commandId"],
            "native_status": result["status"], "turn_id": result.get("turnId"), "delivery_proven": False,
            "portable_completion": False, "cancellation_scope": CANCELLATION_SCOPES.get(method)}, {}, binding)]
    if method == "view/page":
        _require(result, {"events", "nextCursor"}, "page")
        if not isinstance(result["events"], list) or len(result["events"]) > 1000:
            raise DialectError("invalid or oversized page")
        limit = _integer(params.get("limit"), "requested page limit", 1)
        if limit > 1000 or len(result["events"]) > limit: raise DialectError("page exceeds requested bound")
        if result["nextCursor"] is not None: _text(result["nextCursor"], "next cursor")
        facts = [_fact("coverage.page", "observed", {"request_cursor": params.get("cursor"), "request_anchor": params.get("anchor"),
                      "next_cursor": result["nextCursor"], "event_count": len(result["events"]),
                      "resolved_anchor": result.get("resolvedAnchor"), "gap_reconciled": False}, {}, binding)]
        for index, event in enumerate(result["events"], 1):
            _require(event, {"method", "params"}, "page event")
            children = _notification(event["method"], event["params"], binding)
            for child in children: child["native"]["subrecord"] = index
            facts.extend(children)
        return facts
    if method == "item/readOutput":
        _require(result, {"byteLen", "content", "encoding", "eof", "mediaType", "offsetBytes"}, "output page")
        size = _integer(result["byteLen"], "byte length")
        offset = _integer(result["offsetBytes"], "byte offset")
        if size > 1024 * 1024 or ("lengthBytes" in params and size > _integer(params["lengthBytes"], "requested output length")):
            raise DialectError("output exceeds requested bound")
        if offset != params.get("offsetBytes", 0): raise DialectError("output page offset mismatch")
        if type(result["eof"]) is not bool or not isinstance(result["content"], str): raise DialectError("invalid output page")
        if result["encoding"] == "utf8":
            stored = result["content"].encode("utf-8")
        elif result["encoding"] == "base64":
            try: stored = base64.b64decode(result["content"], validate=True)
            except ValueError as exc: raise DialectError("invalid base64 output") from exc
        else: raise DialectError("unsupported output encoding")
        if len(stored) != size: raise DialectError("output byte length mismatch")
        return [_fact("output.page", "observed", {"item_id": params.get("itemId"), "output_ref": params.get("outputRef"),
                      "offset": offset, "byte_length": size, "next_offset": offset + size,
                      "complete": result["eof"] and offset == 0, "range_eof": result["eof"],
                      "missingness": ["prior_output_ranges_not_supplied"] if offset else [],
                      "content": result["content"], "encoding": result["encoding"],
                      "content_digest": hashlib.sha256(stored).hexdigest()}, {}, binding)]
    if method in {"session/read", "session/resume"}:
        _require(result, {"session", "history", "pendingRequests", "viewCursor"}, "session snapshot")
        _text(result["viewCursor"], "snapshot cursor")
        session = _object(result["session"], "session")
        if session.get("sessionId") != producer["thread_id"]: raise DialectError("session readback mismatch")
        return [_fact("session.snapshot", "observed", {"native_session": session, "history": result["history"],
                      "pending_requests": result["pendingRequests"], "gap_reconciled": False,
                      "portable_completion": False, "operation": method}, result, binding)]
    if method == "view/subscribe":
        _text(result.get("viewCursor"), "subscription cursor")
        return [_fact("coverage.subscription", "observed", {"head_cursor": result["viewCursor"],
                      "after": params.get("after"), "coverage_complete": False}, result, binding)]
    if method in {"approval/listPending", "usage/read", "view/unsubscribe"}:
        return [_fact("native.readback", "observed", {"operation": method, "result": result,
                      "grants_authority": False, "portable_completion": False,
                      "usage_semantics": "last_observed_limit_window_not_expenditure" if method == "usage/read" else None}, {}, binding)]
    raise DialectError("unsupported response grammar")


def decode_wire(message, connection_binding):
    _bounded(message); _object(message, "wire message"); _wire_binding(connection_binding)
    if message.get("jsonrpc") != "2.0": raise DialectError("invalid MSP envelope version")
    if "method" in message:
        if "result" in message or "error" in message: raise DialectError("notification mixes response fields")
        if "id" in message:
            # Server requests need a presentation receipt. They are not native
            # decisions; do not silently decode them as approval notifications.
            raise DialectError("server request requires existing presentation owner")
        return _notification(message["method"], message.get("params"), connection_binding)
    return _response(message, connection_binding)


def request_shape(operation, native_target, payload):
    _producer(native_target); _bounded(payload); _object(payload, "request")
    if operation not in REQUEST_FIELDS: raise DialectError("operation unavailable to this adapter")
    params = deepcopy(payload)
    if operation != "usage/read":
        if params.get("sessionId", native_target["thread_id"]) != native_target["thread_id"]:
            raise DialectError("request target substitution")
        params["sessionId"] = native_target["thread_id"]
    required, allowed = REQUEST_FIELDS[operation]
    if not required <= params.keys() or set(params) - allowed: raise DialectError("unsupported or missing request parameter")
    for key in required - {"limit", "attempt"}: _text(params[key], key)
    for key in set(params) - required:
        if key.endswith("Id") or key in {"outputRef", "objective", "reason"}: _text(params[key], key)
    if "commandId" in params:
        try: command = uuid.UUID(params["commandId"])
        except (ValueError, AttributeError) as exc: raise DialectError("command id must be UUIDv7") from exc
        if command.version != 7: raise DialectError("command id must be UUIDv7")
    for key in ("excludeItems", "retract"):
        if key in params and type(params[key]) is not bool: raise DialectError("invalid boolean parameter")
    for key in ("offsetBytes", "lengthBytes", "attempt", "limit"):
        if key in params: _integer(params[key], key, 1 if key in {"attempt", "limit"} else 0)
    if "limit" in params and params["limit"] > 1000: raise DialectError("page limit exceeds stable bound")
    if "lengthBytes" in params and params["lengthBytes"] > 1024 * 1024: raise DialectError("output request exceeds adapter bound")
    if "cursor" in params and "anchor" in params: raise DialectError("cursor and anchor are exclusive")
    for field in ("cursor", "after"):
        if field in params and params[field] is not None:
            _text(params[field], field)
            if params[field] not in native_target.get("observed_cursors", []):
                raise DialectError("cursor must have been observed by the admitted owner")
    if "anchor" in params and params["anchor"] != "latestCompaction": raise DialectError("unsupported cold anchor")
    if "direction" in params and params["direction"] not in {"forward", "backward"}: raise DialectError("invalid page direction")
    if "history" in params and params["history"] not in {"auto", "inline", "snapshot", "anchored"}: raise DialectError("invalid history preference")
    if operation == "workflow/childControl" and params["action"] not in {"skip", "retry"}:
        raise DialectError("unknown workflow child action")
    effect = "read"
    if operation == "session/resume": effect = "native_session_write"
    elif operation.startswith("goal/"): effect = "native_goal_write"
    elif operation in CANCELLATION_SCOPES: effect = "native_workload_control"
    elif operation in {"view/subscribe", "view/unsubscribe"}: effect = "connection_subscription"
    return {"transport": "muse_msp_owner", "operation": operation, "params": params, "effect": effect,
            "executable": False, "authority": "existing_owner_and_native_policy_required",
            "required_fingerprint": STABLE_FINGERPRINT, "experimental_api": False,
            "cancellation_scope": CANCELLATION_SCOPES.get(operation)}


def describe_contract():
    return {"adapter_version": ADAPTER_VERSION, "client": "muse", "supported_schemas": list(SUPPORTED_SCHEMAS),
            "wire_methods": sorted(NOTIFICATION_FIELDS), "request_operations": sorted(REQUEST_FIELDS),
            "stable_fingerprint": STABLE_FINGERPRINT, "experimental_api": False,
            "official_python_option": {"packages": ["muse-code-sdk", "muse-code-msp"],
                "documented_fingerprint": DOCUMENTED_EXPERIMENTAL_FINGERPRINT,
                "installed_or_handshake_tested": False, "source": "https://meta-models.github.io/muse-code-sdk/next/"},
            "authentication": "owner_admission_required", "portable_completion": False,
            "transport_reachability": "unqualified", "schema_notes": [
                "Goal status is an open string; no native value grants portable completion.",
                "goalChanged explicit null is described by the stable field contract although its JSON Schema ref is not nullable."],
            "unsupported": ["experimental_surface", "raw_child_lineage", "unknown_raw_records_or_retained_frames",
                "cron_registration_wake", "approval_decision_execution", "automatic_gap_closure", "server_request_presentation"]}

#!/usr/bin/env python3
"""Pure Codex dialect translation. No I/O, admission, execution or completion.

Rollout grammar comes from bounded native root/child records. App-server fields
come from the stable 0.155.0-alpha.16.4 schema export. Wire declarations do not
qualify a reachable transport. The caller owns source custody, ordered reduction,
current-byte verification, cancellation tombstones and PM/native authorization.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math


ADAPTER_VERSION = "codex-dialect-v1"
SUPPORTED_SCHEMAS = (
    "session_meta", "turn_context", "token_usage_record", "event_msg.token_count",
    "event_msg.task_started", "event_msg.task_complete", "event_msg.turn_aborted",
    "event_msg.user_message", "event_msg.agent_message", "event_msg.agent_reasoning",
    "response_item.function_call", "response_item.custom_tool_call",
    "response_item.function_call_output", "response_item.custom_tool_call_output",
    "response_item.message", "response_item.agent_message", "response_item.reasoning",
)
WIRE_METHODS = (
    "thread/goal/updated", "thread/goal/cleared", "thread/tokenUsage/updated",
    "turn/started", "turn/completed",
)
COUNTERS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
            "output_tokens", "reasoning_output_tokens", "total_tokens")
GOAL_STATUSES = {"active", "paused", "blocked", "usageLimited", "budgetLimited", "complete"}
REQUESTS = {"create_goal", "get_goal", "update_goal", "thread/goal/get", "turn/interrupt", "hooks/list"}


class DialectError(ValueError):
    """Unsupported, malformed or contradictory candidate; record a scoped gap."""


def _object(value, name):
    if not isinstance(value, dict):
        raise DialectError(f"{name} must be an object")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise DialectError(f"invalid {name}")
    return value


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise DialectError(f"invalid {name}")
    return value


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
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _producer(producer):
    _object(producer, "producer")
    if producer.get("client") != "codex":
        raise DialectError("wrong client")
    _text(producer.get("thread_id"), "thread identity")
    _text(producer.get("root_session_id"), "root identity")
    return producer


def qualify_source(header, *, expected_root_session_id, expected_thread_id=None,
                   expected_parent_thread_id=None, expected_agent_id=None):
    """Match claimed native lineage only; never authenticate a PM root seat."""
    _bounded(header)
    row = _object(header, "header")
    value = _object(row.get("payload"), "header payload")
    _text(expected_root_session_id, "expected root")
    thread = expected_thread_id if expected_thread_id is not None else expected_root_session_id
    _text(thread, "expected thread")
    if row.get("type") != "session_meta" or value.get("id") != thread:
        raise DialectError("source thread mismatch")
    root = value.get("session_id", value.get("id"))
    if root != expected_root_session_id:
        raise DialectError("source root mismatch")
    parent, agent = value.get("parent_thread_id"), value.get("agent_path")
    if thread == root:
        if parent is not None or agent is not None:
            raise DialectError("root source claims child lineage")
    else:
        _text(parent, "parent thread")
        if parent == thread or not isinstance(agent, str) or not agent.startswith("/root/"):
            raise DialectError("child lineage is incomplete")
    if expected_parent_thread_id is not None and parent != expected_parent_thread_id:
        raise DialectError("parent thread mismatch")
    if expected_agent_id is not None and agent != expected_agent_id:
        raise DialectError("agent path mismatch")
    return {"client": "codex", "surface": "source-file", "thread_id": thread,
            "root_session_id": root, "parent_thread_id": parent, "agent_path": agent,
            "producer_version": value.get("cli_version"), "adapter_version": ADAPTER_VERSION,
            "authentication": "owner_admission_required", "root_authority": False}


def _fact(kind, status, data, row, *, mode, source_locator, call_id=None, subrecord=0):
    if mode not in {"synthetic", "native"}:
        raise DialectError("invalid observation mode")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return {"kind": kind, "status": status, "data": deepcopy(data),
            "native": {"record_id": row.get("uuid", payload.get("id")), "ordinal": row.get("ordinal"),
                       "sequence": row.get("ordinal"), "subrecord": subrecord, "call_id": call_id,
                       "parent_call_id": payload.get("parent_call_id")},
            "native_timestamp": row.get("timestamp"), "source_locator": deepcopy(source_locator),
            "mode": mode, "authentication": "owner_admission_required"}


def _counts(value):
    if value is None:
        return None
    _object(value, "counters")
    if not value or set(value) - set(COUNTERS):
        raise DialectError("unsupported counter schema")
    for key, amount in value.items():
        _integer(amount, key)
    if {"input_tokens", "output_tokens", "total_tokens"} <= value.keys():
        if value["input_tokens"] + value["output_tokens"] != value["total_tokens"]:
            raise DialectError("counter total contradiction")
    return deepcopy(value)


def _usage(producer, *, grammar, last=None, totals=None, response_id=None, turn_id=None,
           root_turn_id=None, turn_totals=None):
    measured = response_id is not None and last is not None
    countable = measured and {"input_tokens", "output_tokens", "total_tokens"} <= last.keys()
    identity = ["codex", producer["thread_id"], response_id] if response_id else None
    return {"grammar": grammar, "scope": {"kind": "native_thread", **{key: producer.get(key)
            for key in ("thread_id", "root_session_id", "parent_thread_id")}}, "units": "tokens",
            "last": last, "totals": totals, "turn_totals": turn_totals, "response_id": response_id,
            "turn_id": turn_id, "root_turn_id": root_turn_id, "measurement_id": identity,
            "phase": "final" if measured else "unknown", "countable": countable,
            "aggregation": "per_response" if response_id else "cumulative_snapshot",
            "counters_digest": _digest(last) if measured else None,
            "scope_nonoverlap": "UNKNOWN", "billing_cost": None,
            "missingness": ([] if measured else ["no_unique_response_measurement"])
                          + (["incomplete_response_counters"] if measured and not countable else [])
                          + ["full_execution_tree_not_proven"]}


def is_ignored_projection(projected, producer):
    """Only the bounded reader's explicit nonmaterial projection may be ignored."""
    _producer(producer)
    for field, expected in (("thread_id", producer["thread_id"]), ("session_id", producer["root_session_id"])):
        for key in (field, "payload." + field):
            if key in projected and projected[key] != expected:
                return False
    return (projected.get("type") == "turn_context"
            or (projected.get("type"), projected.get("payload.type")) in {
                ("response_item", "reasoning"), ("event_msg", "agent_reasoning"),
                ("event_msg", "agent_message")})


def decode_record(row, producer, *, mode="synthetic", source_locator=None):
    _bounded(row); _object(row, "record"); _producer(producer)
    if "ordinal" in row: _integer(row["ordinal"], "record ordinal")
    value = _object(row.get("payload"), "payload")
    for declared in (row, value):
        for key, expected in (("thread_id", producer["thread_id"]), ("session_id", producer["root_session_id"])):
            if key in declared and declared[key] != expected:
                raise DialectError("native producer mismatch")
    outer, subtype = row.get("type"), value.get("type")
    def fact(kind, status, data, **extra):
        return [_fact(kind, status, data, row, mode=mode, source_locator=source_locator, **extra)]
    if outer == "session_meta":
        qualified = qualify_source(row, expected_root_session_id=producer["root_session_id"],
                                   expected_thread_id=producer["thread_id"],
                                   expected_parent_thread_id=producer.get("parent_thread_id"))
        if qualified.get("agent_path") != producer.get("agent_path"):
            raise DialectError("contradictory agent path")
        return []
    if is_ignored_projection({"type": outer, "payload.type": subtype}, producer):
        return []
    if outer == "token_usage_record":
        for key in ("thread_id", "session_id", "response_id", "turn_id", "root_turn_id"):
            _text(value.get(key), key)
        last, totals = _counts(value.get("usage")), _counts(value.get("thread_token_usage"))
        data = _usage(producer, grammar="codex.response_usage", last=last, totals=totals,
                      response_id=value["response_id"], turn_id=value["turn_id"],
                      root_turn_id=value["root_turn_id"], turn_totals=_counts(value.get("turn_token_usage")))
        return fact("usage.snapshot", "observed" if last is not None else "unknown", data)
    if outer == "event_msg" and subtype == "token_count":
        info = value.get("info")
        if info is not None:
            _object(info, "token_count info")
        data = _usage(producer, grammar="codex.token_count",
                      totals=_counts(info.get("total_token_usage")) if info else None,
                      last=_counts(info.get("last_token_usage")) if info else None)
        data["model_context_window"] = info.get("model_context_window") if info else None
        return fact("usage.snapshot", "observed" if data["totals"] is not None else "unknown", data)
    if outer == "response_item":
        if subtype in {"function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"}:
            call = _text(value.get("call_id"), "call identity")
            if subtype.endswith("_output"):
                if "output" not in value:
                    raise DialectError("tool result lacks output")
                data = {"output": value["output"], "native_status": value.get("status"), "is_error": value.get("is_error")}
                return fact("tool.result", "failed" if value.get("is_error") is True or value.get("status") in {"error", "failed"} else "observed", data, call_id=call)
            args = value.get("arguments" if subtype == "function_call" else "input")
            if not isinstance(args, str):
                raise DialectError("native call arguments must remain a string")
            return fact("tool.call", "observed", {"name": _text(value.get("name"), "tool name"),
                        "namespace": value.get("namespace"), "arguments": args,
                        "interpretation": "opaque_native_call"}, call_id=call)
        if subtype in {"message", "agent_message"}:
            role = value.get("role") if subtype == "message" else "peer"
            return fact("message." + (role if role in {"user", "assistant", "peer"} else "unknown"),
                        "observed", {"content": value.get("content"), "role": role, "grants_authority": False})
    if outer == "event_msg":
        if subtype == "user_message":
            return fact("message.user", "observed", {"native": value, "grants_authority": False})
        kinds = {"task_started": "lifecycle.started", "task_complete": "lifecycle.completed", "turn_aborted": "lifecycle.cancelled"}
        if subtype in kinds:
            return fact(kinds[subtype], "observed", {"turn_id": _text(value.get("turn_id"), "turn identity"),
                        "root_turn_id": value.get("root_turn_id"), "native_status": subtype,
                        "native": value, "portable_completion": False})
    raise DialectError("unsupported Codex rollout grammar")


def _goal(goal, producer):
    _object(goal, "goal")
    if goal.get("threadId") != producer["thread_id"]:
        raise DialectError("goal thread mismatch")
    objective = _text(goal.get("objective"), "objective")
    status = _text(goal.get("status"), "goal status")
    for field in ("createdAt", "updatedAt", "tokensUsed", "timeUsedSeconds"):
        _integer(goal.get(field), field)
    if goal.get("tokenBudget") is not None:
        _integer(goal["tokenBudget"], "token budget")
    return {"native_status": status, "objective_digest": _digest(objective),
            "native_goal_epoch": {"created_at": goal["createdAt"], "objective_digest": _digest(objective)},
            "updated_at": goal["updatedAt"], "tokens_used": goal["tokensUsed"],
            "time_used_seconds": goal["timeUsedSeconds"], "token_budget": goal.get("tokenBudget"),
            "counter_scope": "native_goal_epoch_only", "portable_completion": False}


def decode_wire(message, connection_binding):
    _bounded(message); _object(message, "wire message")
    producer = _producer(connection_binding.get("producer"))
    mode = connection_binding.get("mode", "synthetic")
    method, params = message.get("method"), message.get("params")
    if method is None:
        request = _object(connection_binding.get("pending_request"), "pending request")
        if (type(message.get("id")) is not type(request.get("id"))
                or message.get("id") != request.get("id") or "id" not in message
                or "result" not in message or "error" in message):
            raise DialectError("unbound wire result")
        if request.get("method") == "thread/goal/get":
            if request.get("params", {}).get("threadId") != producer["thread_id"]:
                raise DialectError("readback target mismatch")
            result = _object(message["result"], "readback")
            goal = result.get("goal")
            data = _goal(goal, producer) if goal is not None else {"native_status": "absent" if "goal" in result else "unknown", "portable_completion": False}
            return [_fact("goal.snapshot", "observed" if "goal" in result else "unknown", data, {}, mode=mode, source_locator=None)]
        if request.get("method") == "turn/interrupt" and request.get("params", {}).get("threadId") == producer["thread_id"]:
            return [_fact("command.acknowledged", "observed", {"operation": "turn/interrupt", "request_id": message["id"],
                "turn_id": request["params"].get("turnId"), "delivery_proven": False, "portable_completion": False,
                "cancellation_scope": "foreground_turn"}, {}, mode=mode, source_locator=None)]
        raise DialectError("unsupported or unbound wire response")
    if method not in WIRE_METHODS:
        raise DialectError("unsupported Codex wire method")
    _object(params, "wire params")
    if params.get("threadId") != producer["thread_id"]:
        raise DialectError("wire target mismatch")
    kind, status = method.replace("thread/", "").replace("/", "."), "observed"
    if method == "thread/goal/updated":
        data = _goal(params.get("goal"), producer)
        status = "observed" if data["native_status"] in GOAL_STATUSES else "unknown"
    elif method == "thread/goal/cleared":
        data = {"native_status": "cleared", "portable_completion": False}
    elif method.startswith("turn/"):
        turn = _object(params.get("turn"), "turn")
        _text(turn.get("id"), "turn id")
        if not isinstance(turn.get("items"), list):
            raise DialectError("turn items missing")
        native_status = _text(turn.get("status"), "turn status")
        if method == "turn/started" and native_status != "inProgress":
            raise DialectError("start has contradictory terminal status")
        if method == "turn/completed" and native_status == "inProgress":
            raise DialectError("completed turn remains in progress")
        kind = "lifecycle.started" if method.endswith("started") else "lifecycle.completed"
        status = "failed" if native_status == "failed" else "observed" if native_status in {"completed", "interrupted", "inProgress"} else "terminal_unknown"
        data = {"turn_id": turn["id"], "native_status": native_status, "error": turn.get("error"),
                "items_view": turn.get("itemsView", "full"), "portable_completion": False}
    else:
        usage = _object(params.get("tokenUsage"), "token usage")
        mapping = {"inputTokens": "input_tokens", "cachedInputTokens": "cached_input_tokens", "cacheWriteInputTokens": "cache_write_input_tokens",
                   "outputTokens": "output_tokens", "reasoningOutputTokens": "reasoning_output_tokens", "totalTokens": "total_tokens"}
        def wire_counts(value):
            _object(value, "wire counters")
            if not (set(mapping) - {"cacheWriteInputTokens"}) <= value.keys():
                raise DialectError("wire usage lacks required counters")
            return _counts({target: value[key] for key, target in mapping.items() if key in value})
        data = _usage(producer, grammar="codex.wire_usage", last=wire_counts(usage.get("last")),
                      totals=wire_counts(usage.get("total")), turn_id=_text(params.get("turnId"), "turn id"))
        kind = "usage.snapshot"
    return [_fact(kind, status, data, {}, mode=mode, source_locator=connection_binding.get("source_locator"))]


def request_shape(operation, native_target, payload):
    """Return a proposal only. Raw Goal mutations are intentionally unavailable."""
    _producer(native_target); _bounded(payload); _object(payload, "request payload")
    if operation not in REQUESTS:
        raise DialectError("operation is not in the qualified non-executing allowlist")
    params = deepcopy(payload)
    if operation == "create_goal":
        if set(params) - {"objective", "token_budget"}:
            raise DialectError("unsupported Goal parameter")
        _text(params.get("objective"), "objective")
        if "token_budget" in params and _integer(params["token_budget"], "budget") == 0:
            raise DialectError("budget must be positive")
    elif operation == "update_goal":
        if set(params) != {"status"} or params["status"] not in {"complete", "paused", "blocked"}:
            raise DialectError("native model tool cannot resume or edit budgets")
    elif operation in {"get_goal", "hooks/list"}:
        if params:
            raise DialectError("unexpected parameters")
    else:
        allowed = {"threadId"} | ({"turnId"} if operation == "turn/interrupt" else set())
        if set(params) - allowed or params.get("threadId", native_target["thread_id"]) != native_target["thread_id"]:
            raise DialectError("request target substitution or unsupported field")
        params["threadId"] = native_target["thread_id"]
        if operation == "turn/interrupt":
            _text(params.get("turnId"), "turn id")
    model_tool = operation in {"create_goal", "get_goal", "update_goal"}
    return {"transport": "native_model_tool" if model_tool else "codex_app_server_owner",
            "operation": operation, "params": params, "executable": False,
            "authority": "existing_owner_and_native_policy_required",
            "goal_tool_restrictions_apply": model_tool,
            "cancellation_scope": "foreground_turn" if operation == "turn/interrupt" else None}


def describe_contract():
    return {"adapter_version": ADAPTER_VERSION, "client": "codex", "supported_schemas": list(SUPPORTED_SCHEMAS),
            "wire_methods": list(WIRE_METHODS), "wire_schema_build": "0.155.0-alpha.16.4",
            "request_operations": sorted(REQUESTS), "transport_reachability": "unqualified",
            "authentication": "owner_admission_required", "portable_completion": False,
            "unsupported": ["raw_goal_mutation", "desktop_automation_update_delete_schema",
                            "unobserved_rollout_goal_grammar", "generic_exec_nested_call_extraction"]}

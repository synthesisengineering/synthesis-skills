#!/usr/bin/env python3
"""Pure Claude interactive and print-stream translation; never an executor.

Interactive child identity and response finality are native observations. Their
use still requires the existing owner to prove source custody and parent dispatch.
Goal evaluator, workflow and dynamic-loop grammars remain explicitly unsupported.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math


ADAPTER_VERSION = "claude-dialect-v2"
SUPPORTED_SCHEMAS = ("assistant.message.content.tool_use", "user.message.content.tool_result",
                     "assistant.message.usage", "assistant.message.content.text",
                     "assistant.message.content.thinking", "user.message.content.text")
PRINT_SCHEMAS = ("system.init", "system.hook_started", "system.hook_response", "system.informational", "rate_limit_event", "assistant", "user", "result")
FINAL_REASONS = {"end_turn", "tool_use", "max_tokens", "stop_sequence"}
COUNTERS = {"input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"}
REQUESTS = {"CronCreate", "CronList", "CronDelete"}


class DialectError(ValueError):
    """Candidate cannot be normalized; the owner must retain a scoped gap."""


def _text(value, label):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise DialectError(f"invalid {label}")
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise DialectError(f"{label} must be an object")
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
                                     allow_nan=False).encode()).hexdigest()


def _producer(producer):
    _object(producer, "producer")
    if producer.get("client") != "claude": raise DialectError("wrong client")
    _text(producer.get("thread_id"), "producer identity")
    _text(producer.get("root_session_id"), "root identity")
    return producer


def qualify_source(header, *, expected_root_session_id, expected_thread_id=None,
                   expected_parent_thread_id=None, expected_agent_id=None):
    """Match native session/agent fields; a filename is never identity evidence."""
    _bounded(header); _object(header, "header")
    root = _text(expected_root_session_id, "expected root")
    thread = expected_thread_id if expected_thread_id is not None else root
    _text(thread, "expected thread")
    if header.get("sessionId") != root:
        raise DialectError("native root session mismatch")
    agent, sidechain = header.get("agentId"), header.get("isSidechain")
    if thread == root:
        if agent is not None or sidechain is True or expected_agent_id is not None:
            raise DialectError("child cannot qualify as a root source")
    else:
        if not expected_agent_id or agent != expected_agent_id or thread != agent or sidechain is not True:
            raise DialectError("child lacks an exact owner-bound native agent identity")
    return {"client": "claude", "surface": "source-file", "root_session_id": root,
            "thread_id": thread, "agent_id": agent, "parent_thread_id": None,
            "expected_parent_thread_id": expected_parent_thread_id,
            "parent_binding": "owner_dispatch_required" if agent else "root_source",
            "adapter_version": ADAPTER_VERSION, "authentication": "owner_admission_required",
            "root_authority": False}


def _identity(row, producer):
    if row.get("sessionId") != producer["root_session_id"]:
        raise DialectError("native session mismatch")
    agent = producer.get("agent_id")
    if agent:
        if row.get("agentId") != agent or row.get("isSidechain") is not True or producer["thread_id"] != agent:
            raise DialectError("child producer mismatch")
    elif row.get("agentId") is not None or row.get("isSidechain") is True:
        raise DialectError("root source contains child identity")


def _fact(kind, status, data, row, mode, locator, index=0, call=None):
    if mode not in {"synthetic", "native"}: raise DialectError("invalid mode")
    return {"kind": kind, "status": status, "data": deepcopy(data),
            "native": {"record_id": row.get("uuid"), "ordinal": None, "sequence": None,
                       "subrecord": index, "call_id": call,
                       "parent_call_id": row.get("parent_tool_use_id"), "parent_record_id": row.get("parentUuid")},
            "native_timestamp": row.get("timestamp"), "source_locator": deepcopy(locator),
            "mode": mode, "authentication": "owner_admission_required"}


def _usage(usage, producer, *, message_id=None, request_id=None, stop_reason=None, aggregate=False):
    _object(usage, "native usage")
    counters = {}
    for key in COUNTERS:
        if key in usage:
            if type(usage[key]) is not int or usage[key] < 0:
                raise DialectError("invalid native token counter")
            counters[key] = usage[key]
    if not {"input_tokens", "output_tokens"} <= counters.keys():
        raise DialectError("usage lacks measured input/output")
    phase = "final" if stop_reason in FINAL_REASONS else "provisional" if stop_reason is None else "unknown"
    if aggregate: phase = "aggregate"
    identity = ["claude", producer["root_session_id"], producer["thread_id"], message_id] if message_id and not aggregate else None
    return {"grammar": "claude.print_result_usage" if aggregate else "claude.response_usage",
            "scope": {"kind": "native_thread", **{key: producer.get(key)
                      for key in ("thread_id", "root_session_id", "parent_thread_id", "agent_id")}},
            "units": "tokens", "response_id": message_id, "request_id": request_id,
            "measurement_id": identity, "counters_digest": _digest(counters), "last": counters,
            "totals": None, "turn_totals": None, "raw_usage": deepcopy(usage),
            "phase": phase, "countable": bool(identity) and phase == "final",
            "aggregation": "turn_aggregate" if aggregate else "per_response",
            "native_stop_reason": stop_reason, "scope_nonoverlap": "UNKNOWN", "billing_cost": None,
            "missingness": (["no_terminal_response_usage"] if phase in {"provisional", "unknown"} else [])
                            + (["aggregate_must_reconcile_with_responses"] if aggregate else [])
                            + ["full_execution_tree_not_proven"]}


def is_ignored_projection(projected, producer):
    """No giant Claude wrapper is discarded: siblings can contain usage/tools."""
    _producer(producer)
    return False


def decode_record(row, producer, *, mode="synthetic", source_locator=None):
    _bounded(row); _object(row, "record"); _producer(producer); _identity(row, producer)
    kind = row.get("type")
    if kind not in {"assistant", "user"}:
        raise DialectError("unsupported Claude interactive record; do not reinterpret as print stream")
    message = _object(row.get("message"), "message")
    generated = row.get("is_api_error_message") is True or message.get("model") == "<synthetic>"
    if "is_api_error_message" in row and type(row["is_api_error_message"]) is not bool:
        raise DialectError("API error marker is not boolean")
    if generated:
        # This is genuine client output but not a provider-generated response.
        return [_fact("runtime.error", "failed", {"error": row.get("error"),
            "client_generated": True, "provider_response": False, "provider_usage": "UNKNOWN",
            "raw_usage": deepcopy(message.get("usage")), "portable_completion": False}, row, mode, source_locator)]
    content = message.get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list): raise DialectError("message content must be a list or text")
    facts = []
    for index, block in enumerate(content):
        _object(block, "content block")
        subtype = block.get("type")
        if kind == "assistant" and subtype == "tool_use":
            call = _text(block.get("id"), "call identity")
            args = _object(block.get("input"), "tool input")
            data = {"name": _text(block.get("name"), "tool name"), "namespace": None,
                    "arguments": args, "interpretation": "opaque_native_call"}
            facts.append(_fact("tool.call", "observed", data, row, mode, source_locator, index, call))
        elif kind == "user" and subtype == "tool_result":
            call = _text(block.get("tool_use_id"), "result call identity")
            if "content" not in block: raise DialectError("tool result lacks content")
            if "is_error" in block and type(block["is_error"]) is not bool:
                raise DialectError("tool error flag is not boolean")
            data = {"output": block["content"], "is_error": block.get("is_error"), "native_status": None}
            facts.append(_fact("tool.result", "failed" if block.get("is_error") else "observed", data,
                               row, mode, source_locator, index, call))
        elif kind == "user" and subtype == "text":
            if not isinstance(block.get("text"), str):
                raise DialectError("user text block lacks text")
            facts.append(_fact("message.user", "observed", {"content": block["text"], "role": "user",
                               "grants_authority": False, "human_identity_proven": False},
                               row, mode, source_locator, index))
        elif subtype in {"text", "thinking", "redacted_thinking"}:
            continue
        else:
            raise DialectError("unsupported Claude content block")
    if kind == "assistant" and message.get("usage") is not None:
        identity = _text(message.get("id"), "message identity")
        data = _usage(message["usage"], producer, message_id=identity, request_id=row.get("requestId"),
                      stop_reason=message.get("stop_reason"))
        facts.append(_fact("usage.snapshot", "observed" if data["phase"] == "final" else "unknown",
                           data, row, mode, source_locator, len(content)))
    return facts


def qualify_transport(header, *, expected_session_id, invocation_id):
    _bounded(header); _text(expected_session_id, "expected session"); _text(invocation_id, "invocation")
    if header.get("session_id") != expected_session_id or header.get("type") != "system":
        raise DialectError("print stream lacks an expected system identity")
    if header.get("subtype") not in {"init", "hook_started", "hook_response"}:
        raise DialectError("unqualified print stream preamble")
    return {"client": "claude", "surface": "captured-transport", "thread_id": expected_session_id,
            "root_session_id": expected_session_id, "parent_thread_id": None, "agent_id": None,
            "dialect": "claude.print_stream", "invocation_id": invocation_id,
            "adapter_version": ADAPTER_VERSION, "authentication": "owner_admission_required", "root_authority": False}


def decode_wire(message, connection_binding):
    """CLI print JSON is a separate dialect, not a general SDK control protocol."""
    _bounded(message); _object(message, "print record")
    if connection_binding.get("dialect") != "claude.print_stream":
        raise DialectError("print-stream dialect must be explicitly selected")
    producer = _producer(connection_binding.get("producer"))
    if producer.get("agent_id"):
        raise DialectError("child print-stream identity not qualified")
    if message.get("session_id") != producer["root_session_id"]:
        raise DialectError("print-stream session mismatch")
    mode, locator = connection_binding.get("mode", "synthetic"), connection_binding.get("source_locator")
    kind = message.get("type")
    if kind == "system" and message.get("subtype") == "init":
        return [_fact("runtime.configuration", "observed", {"tools": message.get("tools"),
            "native_model": message.get("model"), "grants_authority": False}, message, mode, locator)]
    if kind == "rate_limit_event":
        info = _object(message.get("rate_limit_info"), "rate limit observation")
        return [_fact("capacity.snapshot", "observed", {"native_rate_limit": info,
            "usage_semantics": "account_limit_not_expenditure", "grants_authority": False}, message, mode, locator)]
    if kind == "system" and message.get("subtype") == "informational":
        if not isinstance(message.get("content"), str): raise DialectError("informational record lacks text")
        return [_fact("runtime.notice", "observed", {"content": message["content"], "level": message.get("level"),
            "interpretation": "opaque_native_notice", "grants_authority": False}, message, mode, locator)]
    if kind == "system" and message.get("subtype") in {"hook_started", "hook_response"}:
        return [_fact("runtime.hook", "observed", {"native_subtype": message["subtype"],
            "hook_id": message.get("hook_id"), "hook_name": message.get("hook_name"),
            "exit_code": message.get("exit_code"), "grants_authority": False}, message, mode, locator)]
    if kind in {"assistant", "user"}:
        if "sessionId" in message and message["sessionId"] != producer["root_session_id"]:
            raise DialectError("contradictory interactive identity inside print stream")
        interactive = {**message, "sessionId": producer["root_session_id"]}
        return decode_record(interactive, producer, mode=mode, source_locator=locator)
    if kind != "result": raise DialectError("unsupported Claude print-stream record")
    subtype = _text(message.get("subtype"), "result subtype")
    if type(message.get("is_error")) is not bool:
        raise DialectError("result lacks native error flag")
    status = "failed" if message["is_error"] else "observed" if subtype == "success" else "terminal_unknown"
    facts = [_fact("lifecycle.completed", status, {"native_status": subtype, "is_error": message["is_error"],
                   "result": message.get("result"), "terminal_reason": message.get("terminal_reason"),
                   "native_stop_reason": message.get("stop_reason"), "api_error_status": message.get("api_error_status"),
                   "provider_usage": "UNKNOWN" if message["is_error"] else "aggregate_only",
                   "portable_completion": False}, message, mode, locator)]
    if message.get("usage") is not None:
        data = _usage(message["usage"], producer, aggregate=True)
        if message["is_error"]:
            data.update(phase="unknown", countable=False, missingness=data["missingness"] + ["client_error_provider_usage_unknown"])
        facts.append(_fact("usage.snapshot", "unknown" if message["is_error"] else "observed", data,
                           message, mode, locator, 1))
    return facts


def request_shape(operation, native_target, payload):
    _producer(native_target); _bounded(payload); _object(payload, "request")
    if operation not in REQUESTS:
        raise DialectError("unqualified Claude native operation")
    required = {"CronCreate": {"cron", "prompt", "recurring"}, "CronDelete": {"id"}, "CronList": set()}[operation]
    if set(payload) != required: raise DialectError("unsupported or missing native tool parameter")
    for field in required - {"recurring"}: _text(payload[field], field)
    if "recurring" in payload and type(payload["recurring"]) is not bool:
        raise DialectError("recurring must be boolean")
    return {"transport": "native_model_tool", "operation": operation, "params": deepcopy(payload),
            "executable": False, "authority": "existing_owner_and_native_policy_required",
            "cancellation_scope": "native_job_only" if operation == "CronDelete" else None}


def describe_contract():
    return {"adapter_version": ADAPTER_VERSION, "client": "claude", "supported_schemas": list(SUPPORTED_SCHEMAS),
            "print_schemas": list(PRINT_SCHEMAS), "request_operations": sorted(REQUESTS),
            "authentication": "owner_admission_required", "portable_completion": False,
            "transport_reachability": "unqualified", "unsupported": ["goal_evaluator_records", "workflow_records",
                "dynamic_loop_tool_contract", "child_print_stream_identity", "remote_routine_control"],
            "nonmaterial": ["assistant text/thinking content blocks; sibling usage and tool blocks remain material"]}

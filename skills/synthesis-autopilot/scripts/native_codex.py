#!/usr/bin/env python3
"""Pure Codex dialect translation. No I/O, admission, execution or completion.

Rollout grammar comes from bounded native root/child records. App-server fields
come from the stable 0.155.0-alpha.16.4 schema export. Wire declarations do not
qualify a reachable transport. The caller owns source custody, ordered reduction,
current-byte verification, cancellation tombstones and PM/native authorization.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import re


ADAPTER_VERSION = "codex-dialect-v11"
SUPPORTED_SCHEMAS = (
    "session_meta", "turn_context", "compacted", "world_state", "event_msg.thread_settings_applied", "inter_agent_communication_metadata", "token_usage_record", "event_msg.token_count",
    "event_msg.task_started", "event_msg.task_complete", "event_msg.turn_aborted",
    "event_msg.user_message", "event_msg.agent_message", "event_msg.agent_reasoning",
    "event_msg.item_completed",
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


def supports_record_readback(projected, producer):
    """Route qualified item/compaction shapes to the existing bounded readback.

    This projection is only a routing hint. Complete current bytes still pass
    strict JSON, producer and whole-envelope validation before emitting a fact.
    Compaction's embedded usage supplies the native identities at that boundary.
    """
    _producer(producer)
    if (projected.get("type") in {"compacted", "world_state"}
            or (projected.get("type"), projected.get("payload.type")) == ("event_msg", "thread_settings_applied")):
        return all(projected.get(key, expected) == expected for key, expected in (
            ("thread_id", producer["thread_id"]), ("session_id", producer["root_session_id"]),
            ("payload.thread_id", producer["thread_id"]),
            ("payload.session_id", producer["root_session_id"])))
    return (projected.get("type") == "event_msg"
        and projected.get("payload.type") == "item_completed"
        and projected.get("payload.thread_id") == producer["thread_id"]
        and projected.get("payload.item.type") in ("CommandExecution", "FileChange", "Reasoning",
            "AgentMessage", "SubAgentActivity", "ContextCompaction", "McpToolCall", "Extension")
        and all(projected.get(key, expected) == expected for key, expected in (
            ("thread_id", producer["thread_id"]), ("session_id", producer["root_session_id"]),
            ("payload.session_id", producer["root_session_id"]))))


def _completed_item(value, producer):
    """Read a native rollout item projection without inventing a tool pair.

    These records accompany response_item records. Their item IDs are not
    call IDs, and completing an item does not complete the enclosing turn.
    Keep the bounded observation and digest without duplicating output bodies.
    """
    if value.get("thread_id") != producer["thread_id"]:
        raise DialectError("item projection lacks the bound native thread")
    turn = _text(value.get("turn_id"), "item turn identity")
    start = _integer(value.get("started_at_ms"), "item start")
    end = _integer(value.get("completed_at_ms"), "item end")
    if end < start:
        raise DialectError("item completion precedes start")
    item = _object(value.get("item"), "completed item")
    ident = _text(item.get("id"), "item identity")
    kind, status = item.get("type"), "observed"
    if kind == "CommandExecution":
        command = item.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
            raise DialectError("invalid item command")
        _text(item.get("cwd"), "item cwd")
        native_status = _text(item.get("status"), "item status")
        code = item.get("exit_code")
        if code is not None and type(code) is not int:
            raise DialectError("invalid item exit code")
        for field in ("stdout", "stderr", "aggregated_output"):
            if not isinstance(item.get(field), str):
                raise DialectError("invalid item output")
        status = ("failed" if native_status == "failed" or code not in (None, 0)
                  else "observed" if native_status == "completed" and code == 0 else "unknown")
    elif kind == "FileChange":
        # These are digest-only native item observations, not portable writes.
        # Qualified add/content and update/diff envelopes retain exact fields.
        _closed(value, {"type", "thread_id", "turn_id", "item", "started_at_ms", "completed_at_ms"})
        _closed(item, {"type", "id", "changes", "status", "stdout", "stderr"})
        changes = _object(item.get("changes"), "item changes")
        if not changes:
            raise DialectError("empty item changes")
        for path, change in changes.items():
            _text(path, "change path")
            _object(change, "file change")
            if change.get("type") == "add":
                if set(change) != {"type", "content"} or not isinstance(change["content"], str):
                    raise DialectError("unsupported FileChange add grammar")
            elif change.get("type") == "update":
                if (set(change) != {"type", "unified_diff", "move_path"}
                        or not isinstance(change["unified_diff"], str)
                        or (change["move_path"] is not None and not isinstance(change["move_path"], str))):
                    raise DialectError("unsupported FileChange update grammar")
            else:
                raise DialectError("unsupported FileChange change grammar")
        native_status = _text(item.get("status"), "item status")
        if any(not isinstance(item.get(field), str) for field in ("stdout", "stderr")):
            raise DialectError("invalid item output")
        status = "failed" if native_status == "failed" else "observed" if native_status == "completed" else "unknown"
    elif kind == "McpToolCall":
        _closed(value, {"type", "thread_id", "turn_id", "item", "started_at_ms", "completed_at_ms"})
        _closed(item, {"type", "id", "server", "tool", "arguments", "pluginId", "status", "result", "duration"}
                | ({"readOnlyHint"} if "readOnlyHint" in item else set()))
        if "readOnlyHint" in item:
            _flag(item["readOnlyHint"])
        if start > 2**63 - 1 or end > 2**63 - 1:
            raise DialectError("MCP item time exceeds bound")
        for key in ("server", "tool", "pluginId", "status"):
            _text(item[key], key)
        # MCP arguments are opaque tool-defined JSON. Validate the bounded
        # object, then digest it; never interpret instructions or invoke it.
        _object(item["arguments"], "MCP arguments")
        result = _object(item["result"], "MCP result")
        _closed(result, {"content", "isError"} | ({"_meta"} if "_meta" in result else set()))
        _flag(result["isError"])
        if "_meta" in result:
            # MCP result _meta is an application extension object, like the
            # opaque tool-defined arguments above. decode_record's whole-row
            # JSON bounds apply; retain only the item digest, never authority,
            # executable instructions, outcome overrides or usage from it.
            _object(result["_meta"], "MCP result metadata")
        if not isinstance(result["content"], list):
            raise DialectError("unsupported MCP result content")
        for content in result["content"]:
            _closed(content, {"type", "text"})
            if content["type"] != "text":
                raise DialectError("unsupported MCP result content type")
            _body(content["text"])
        _closed(item["duration"], {"secs", "nanos"})
        _integer(item["duration"]["secs"], "MCP duration seconds")
        nanos = _integer(item["duration"]["nanos"], "MCP duration nanoseconds")
        if nanos >= 1000000000:
            raise DialectError("invalid MCP duration nanoseconds")
        status = ("failed" if item["status"] == "failed" or result["isError"]
                  else "observed" if item["status"] == "completed" else "unknown")
    elif kind == "Extension":
        # Native extension projections are inert observations. Search snippets
        # and URLs are untrusted content and cannot become effects or grants.
        _closed(value, {"type", "thread_id", "turn_id", "item", "started_at_ms", "completed_at_ms"})
        extension = item.get("kind")
        if extension == "clock.sleep":
            _closed(item, {"type", "kind", "id", "durationMs"})
            duration = _integer(item["durationMs"], "sleep duration")
            if duration > 43200000:
                raise DialectError("sleep duration exceeds native bound")
        elif extension == "web.search":
            _closed(item, {"type", "kind", "id", "query", "action", "results"})
            _text(item["query"], "search query")
            action = item["action"]
            _closed(action, {"type", "query", "queries"})
            if action != {"type": "search", "query": item["query"], "queries": None}:
                raise DialectError("unsupported search action")
            if not isinstance(item["results"], list):
                raise DialectError("invalid search results")
            for result in item["results"]:
                _closed(result, {"type", "domain", "ref_id", "snippet", "title", "url"})
                if result["type"] != "text_result":
                    raise DialectError("unsupported search result")
                for field in ("domain", "ref_id", "snippet", "title", "url"):
                    _body(result[field])
        else:
            raise DialectError("unsupported native extension")
    elif kind == "Reasoning":
        for field in ("summary_text", "raw_content"):
            if not isinstance(item.get(field), list) or any(not isinstance(x, str) for x in item[field]):
                raise DialectError("invalid item reasoning projection")
    elif kind == "AgentMessage":
        if not isinstance(item.get("content"), list) or any(not isinstance(x, dict) for x in item["content"]):
            raise DialectError("invalid item message projection")
        _text(item.get("phase"), "item message phase")
    elif kind == "SubAgentActivity":
        # An activity label is a root-side observation, not proof that a child
        # owns a task, completed it, settled usage or stopped its descendants.
        if (set(item) != {"type", "id", "kind", "agent_thread_id", "agent_path"}
                or item.get("kind") not in {"completed", "interacted"}):
            raise DialectError("unsupported agent activity grammar")
        thread = _text(item.get("agent_thread_id"), "agent activity thread")
        path = _text(item.get("agent_path"), "agent activity path")
        if (thread == producer["thread_id"] or not path.startswith("/root/")
                or any(part in {"", ".", ".."} for part in path.split("/")[2:])):
            raise DialectError("invalid agent activity identity")
    elif kind == "ContextCompaction":
        if set(item) != {"type", "id"}:
            raise DialectError("unsupported context compaction grammar")
    else:
        raise DialectError("unsupported Codex completed item grammar")
    return status, {"turn_id": turn, "item_id": ident, "native_type": kind,
        "native_status": item.get("status"), "item_digest": _digest(item),
        "started_at_ms": start, "completed_at_ms": end,
        "portable_completion": False, "grants_authority": False}


def _compacted(row, producer):
    """Observe context replacement without replaying history or charging usage.

    This closed grammar is pinned to the observed native compaction envelope.
    Unknown retained item/context shapes remain coverage gaps. History bodies
    are authenticated by digests, never promoted into messages, tool calls,
    permissions or additive measurements by this translation.
    """
    def fields(value, required, optional=()):
        _object(value, "compaction object")
        if not set(required) <= value.keys() or set(value) - set(required) - set(optional):
            raise DialectError("unsupported compaction fields")

    def boolean(value):
        if type(value) is not bool:
            raise DialectError("compaction flag must be boolean")

    def string(value):
        # Body text may exceed identity bounds. The reader either bounds the
        # whole decoder input or validates and elides inert strings in a span.
        if not isinstance(value, str):
            raise DialectError("compaction body must be text")

    def array(value):
        if not isinstance(value, list):
            raise DialectError("compaction collection must be an array")

    fields(row, {"type", "payload", "timestamp", "ordinal"}, {"thread_id", "session_id"})
    stamp = row["timestamp"]
    if (not isinstance(stamp, str) or len(stamp) > 64
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?(?:Z|[+-][0-9]{2}:[0-9]{2})", stamp)):
        raise DialectError("invalid compaction timestamp")
    if not stamp.endswith("Z") and (int(stamp[-5:-3]) > 23 or int(stamp[-2:]) > 59):
        raise DialectError("invalid compaction timezone offset")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DialectError("invalid compaction timestamp") from exc
    if parsed.utcoffset() is None:
        raise DialectError("compaction timestamp lacks timezone")

    value = row["payload"]
    fields(value, {"message", "replacement_history", "replacement_history_metadata", "retained_context",
                   "window_number", "first_window_id", "previous_window_id", "window_id",
                   "compaction_response_id", "latest_token_usage_record"})
    string(value["message"])
    _integer(value["window_number"], "window number")
    for key in ("first_window_id", "previous_window_id", "window_id", "compaction_response_id"):
        _text(value[key], key)
    history, metadata = value["replacement_history"], value["replacement_history_metadata"]
    array(history); array(metadata)
    if not history or len(history) != len(metadata):
        raise DialectError("compaction history metadata cardinality mismatch")
    content_kinds = {"user.text", "user.image", "images.resize_notice", "unknown", "generic.developer_instructions",
                     "memories.instructions", "host_skills.instructions", "permissions.instructions",
                     "collaboration_mode.instructions", "multi_agent.role_instructions",
                     "multi_agent.mode_instructions", "agents_md.instructions", "environments.environment_context"}
    for item, item_metadata in zip(history, metadata):
        fields(item_metadata, {"client_authored"}, {"user_input_order", "compaction_model_hash"})
        boolean(item_metadata["client_authored"])
        if "user_input_order" in item_metadata:
            _integer(item_metadata["user_input_order"], "retained input order")
        if "compaction_model_hash" in item_metadata:
            _text(item_metadata["compaction_model_hash"], "compaction model hash")
        _object(item, "retained history item")
        if item.get("type") == "message":
            fields(item, {"type", "id", "role", "content", "internal_chat_message_metadata_passthrough"})
            if item["role"] not in ("user", "developer"):
                raise DialectError("unsupported retained message role")
            array(item["content"])
            passthrough = item["internal_chat_message_metadata_passthrough"]
            fields(passthrough, {"turn_id", "content_item_kinds"}, {"create_time"})
            array(passthrough["content_item_kinds"])
            if (not item["content"] or len(item["content"]) != len(passthrough["content_item_kinds"])
                    or any(not isinstance(kind, str) or kind not in content_kinds
                           for kind in passthrough["content_item_kinds"])):
                raise DialectError("unsupported retained content metadata")
            if "create_time" in passthrough:
                instant = passthrough["create_time"]
                if (type(instant) not in (int, float) or instant < 0
                        or (type(instant) is float and not math.isfinite(instant))):
                    raise DialectError("invalid retained creation time")
            for part in item["content"]:
                _object(part, "retained content item")
                if part.get("type") == "input_text":
                    fields(part, {"type", "text"}); string(part["text"])
                elif part.get("type") == "input_image":
                    fields(part, {"type", "detail", "image_url"})
                    if part["detail"] not in ("auto", "low", "high", "original"):
                        raise DialectError("unsupported retained image detail")
                    string(part["image_url"])
                else:
                    raise DialectError("unsupported retained content item")
        elif item.get("type") == "compaction":
            fields(item, {"type", "id", "encrypted_content", "internal_chat_message_metadata_passthrough"})
            string(item["encrypted_content"])
            passthrough = item["internal_chat_message_metadata_passthrough"]
            fields(passthrough, {"turn_id"})
        else:
            raise DialectError("unsupported retained history item")
        _text(item["id"], "retained item identity")
        _text(passthrough["turn_id"], "retained turn identity")

    retained = value["retained_context"]
    fields(retained, {"verified_answers", "incomplete", "user_messages", "user_messages_incomplete", "next_order"})
    # No nonempty verified-answer schema was observed; do not infer its meaning.
    if retained["verified_answers"] != []:
        raise DialectError("unsupported retained verified-answer schema")
    boolean(retained["incomplete"]); boolean(retained["user_messages_incomplete"])
    _integer(retained["next_order"], "retained next order")
    array(retained["user_messages"])
    for message in retained["user_messages"]:
        fields(message, {"complete", "message_id", "order", "text", "turn_id"})
        boolean(message["complete"]); _integer(message["order"], "retained message order")
        string(message["text"])
        _text(message["message_id"], "retained message identity")
        _text(message["turn_id"], "retained message turn")

    usage = value["latest_token_usage_record"]
    fields(usage, {"thread_id", "session_id", "response_id", "turn_id", "root_turn_id",
                   "usage", "turn_token_usage", "thread_token_usage"})
    if usage["thread_id"] != producer["thread_id"] or usage["session_id"] != producer["root_session_id"]:
        raise DialectError("compaction usage producer mismatch")
    for key in ("thread_id", "session_id", "response_id", "turn_id", "root_turn_id"):
        _text(usage[key], key)
    for key in ("usage", "turn_token_usage", "thread_token_usage"):
        fields(usage[key], COUNTERS)
        _counts(usage[key])
    return {"native_type": "compacted", "window_number": value["window_number"],
            **{key: value[key] for key in ("first_window_id", "previous_window_id", "window_id", "compaction_response_id")},
            "message_digest": _digest(value["message"]), "replacement_history_count": len(history),
            "replacement_history_digest": _digest(history),
            "replacement_history_metadata_digest": _digest(metadata),
            "retained_context_digest": _digest(retained),
            "retained_user_message_count": len(retained["user_messages"]),
            "retained_usage": deepcopy(usage), "retained_usage_counted": False,
            "usage_semantics": "historical_snapshot_not_additive", "history_replayed": False,
            "grants_authority": False, "portable_completion": False, "recovery_proven": False}


def decode_streamed_compaction(row, producer, *, digest, mode, source_locator):
    """Normalize a strict streaming projection after complete wire validation.

    The reader elides only known body strings and authenticates every original
    byte with two stable passes. Reuse this owner's complete schema and counter
    validation; never report body digests calculated from those placeholders.
    """
    if not isinstance(row, dict) or row.get("type") != "compacted":
        raise DialectError("unsupported streamed context grammar")
    facts = decode_record(row, producer, mode=mode, source_locator=source_locator)
    data = facts[0]["data"]
    for key in ("message_digest", "replacement_history_digest",
                "replacement_history_metadata_digest", "retained_context_digest"):
        del data[key]
    data.update(record_digest=digest, commitment_algorithm="codex-compaction-wire-sha256-v1",
                body_retained=False)
    return facts


def _closed(value, required):
    _object(value, "native context object")
    if set(value) != set(required):
        raise DialectError("unsupported native context fields")


def _body(value):
    if not isinstance(value, str):
        raise DialectError("native context body must be text")


def _flag(value):
    if type(value) is not bool:
        raise DialectError("native context flag must be boolean")


def _string_fields(value, fields):
    _closed(value, fields)
    for key in fields:
        _body(value[key])


def _context_envelope(row):
    if (not {"type", "payload", "timestamp", "ordinal"} <= row.keys()
            or set(row) - {"type", "payload", "timestamp", "ordinal", "thread_id", "session_id"}):
        raise DialectError("unsupported native context envelope")
    stamp = row["timestamp"]
    if (not isinstance(stamp, str) or len(stamp) > 64
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?(?:Z|[+-][0-9]{2}:[0-9]{2})", stamp)):
        raise DialectError("invalid native context timestamp")
    if not stamp.endswith("Z") and (int(stamp[-5:-3]) > 23 or int(stamp[-2:]) > 59):
        raise DialectError("invalid native context timezone")
    try:
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DialectError("invalid native context timestamp") from exc


def _world_state(value):
    """Qualify the observed full snapshot; instructions remain inert content."""
    _closed(value, {"full", "state"})
    if value["full"] is False:
        # Observed midnight date update only, not a synthesized full snapshot.
        _closed(value["state"], {"environments"})
        _closed(value["state"]["environments"], {"current_date"})
        date = value["state"]["environments"]["current_date"]
        if not isinstance(date, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date):
            raise DialectError("unsupported date patch")
        try:
            datetime.fromisoformat(date)
        except ValueError as exc:
            raise DialectError("invalid date patch") from exc
        return
    if value["full"] is not True:
        raise DialectError("world-state full flag must be boolean")
    state = value["state"]
    flags = {"apps_instructions", "environments_instructions", "git_attribution", "plugins_instructions"}
    bodies = {"context_window_guidance", "model", "multi_agent_usage_hint"}
    _closed(state, flags | bodies | {"agents_md", "collaboration_mode", "environments", "host_skills",
            "managed_developer_instructions", "multi_agent_mode", "orchestrator_skills", "permissions",
            "persistent_mode", "realtime", "skills"})
    for key in flags: _flag(state[key])
    for key in bodies: _body(state[key])
    _string_fields(state["agents_md"], {"directory", "text"})
    _string_fields(state["collaboration_mode"], {"mode", "model", "instructions"})
    _string_fields(state["multi_agent_mode"], {"mode", "usage_hint_hash"})
    _closed(state["managed_developer_instructions"], set())
    _closed(state["persistent_mode"], set())
    for name, keys in (("orchestrator_skills", {"includeInstructions", "enabled"}),
                       ("realtime", {"active"}), ("skills", {"includeInstructions"})):
        _closed(state[name], keys)
        for key in keys: _flag(state[name][key])
    _closed(state["host_skills"], {"body", "includeInstructions"})
    _body(state["host_skills"]["body"]); _flag(state["host_skills"]["includeInstructions"])
    env = state["environments"]
    _closed(env, {"environments", "current_date", "timezone", "filesystem", "subagents"})
    for key in ("current_date", "timezone", "filesystem", "subagents"): _body(env[key])
    _object(env["environments"], "environment map")
    for name, entry in env["environments"].items():
        _text(name, "environment identity")
        _string_fields(entry, {"cwd", "shell", "status"})
    permissions = state["permissions"]
    _closed(permissions, {"instructions", "approved_command_prefixes"})
    _body(permissions["instructions"])
    prefixes = permissions["approved_command_prefixes"]
    if (not isinstance(prefixes, list) or any(not isinstance(prefix, list) or not prefix
            or any(not isinstance(part, str) for part in prefix) for prefix in prefixes)):
        raise DialectError("unsupported command-prefix observation")


def _thread_settings(value, producer):
    """Validate a reported configuration, never configure the current owner."""
    _closed(value, {"type", "thread_id", "thread_settings"})
    if value["thread_id"] != producer["thread_id"]:
        raise DialectError("thread settings producer mismatch")
    settings = _object(value["thread_settings"], "thread settings")
    strings = {"model", "model_provider_id", "service_tier", "approval_policy", "approvals_reviewer",
               "cwd", "reasoning_effort", "reasoning_summary", "personality"}
    # Native settings may omit the active profile descriptor. Absence is an
    # observation of missing metadata, never an unrestricted profile or grant.
    _closed(settings, strings | {"permission_profile", "runtime_workspace_roots",
                                 "collaboration_mode", "disabled_plugin_ids"}
            | ({"active_permission_profile"} if "active_permission_profile" in settings else set()))
    for key in strings: _body(settings[key])
    for key in ("runtime_workspace_roots", "disabled_plugin_ids"):
        if not isinstance(settings[key], list) or any(not isinstance(x, str) for x in settings[key]):
            raise DialectError("unsupported thread settings list")
    if "active_permission_profile" in settings:
        _string_fields(settings["active_permission_profile"], {"id"})
    mode = settings["collaboration_mode"]
    _closed(mode, {"mode", "settings"}); _body(mode["mode"])
    _string_fields(mode["settings"], {"model", "reasoning_effort", "developer_instructions"})
    profile = settings["permission_profile"]
    _closed(profile, {"type", "file_system", "network"}); _body(profile["network"])
    if profile["type"] != "managed":
        raise DialectError("unsupported reported permission profile")
    fs = profile["file_system"]
    _closed(fs, {"type", "entries"})
    if fs["type"] != "restricted" or not isinstance(fs["entries"], list):
        raise DialectError("unsupported reported filesystem profile")
    for entry in fs["entries"]:
        _object(entry, "reported filesystem entry")
        _closed(entry, {"path", "access"} | ({"missing_path_behavior"} if "missing_path_behavior" in entry else set()))
        _body(entry["access"])
        if "missing_path_behavior" in entry: _body(entry["missing_path_behavior"])
        path = _object(entry["path"], "reported permission path")
        if path.get("type") == "path":
            _closed(path, {"type", "path"}); _body(path["path"])
        elif path.get("type") == "special":
            _closed(path, {"type", "value"}); _string_fields(path["value"], {"kind"})
        else:
            raise DialectError("unsupported reported permission path type")


def _context_observation(row, producer):
    _context_envelope(row)
    value = row["payload"]
    if row["type"] == "world_state":
        _world_state(value)
        native_type = "world_state"
    else:
        _thread_settings(value, producer)
        native_type = "thread_settings_applied"
    return {"native_type": native_type, "context_digest": _digest(value),
            "effects_replayed": False, "settings_applied": False, "usage_counted": False,
            "grants_authority": False, "portable_completion": False, "recovery_proven": False}


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
    if outer == "inter_agent_communication_metadata":
        # Native routing metadata records an observed trigger flag. It cannot
        # prove delivery, a wake, worker termination, authority or completion.
        if (set(row) - {"type", "payload", "timestamp", "ordinal", "thread_id", "session_id"}
                or set(value) != {"trigger_turn"}
                or type(value["trigger_turn"]) is not bool):
            raise DialectError("unsupported communication metadata grammar")
        if "timestamp" in row:
            stamp = row["timestamp"]
            if (not isinstance(stamp, str) or len(stamp) > 64
                    or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?(?:Z|[+-][0-9]{2}:[0-9]{2})", stamp)):
                raise DialectError("invalid communication metadata timestamp")
            if (not stamp.endswith("Z")
                    and (int(stamp[-5:-3]) > 23 or int(stamp[-2:]) > 59)):
                raise DialectError("invalid communication metadata timezone offset")
            try:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise DialectError("invalid communication metadata timestamp") from exc
            if parsed.utcoffset() is None:
                raise DialectError("communication metadata timestamp lacks timezone")
        return fact("communication.observation", "observed", {
            "trigger_turn": value["trigger_turn"], "portable_completion": False,
            "grants_authority": False, "proves_wake": False})
    if outer == "world_state":
        return fact("context.world_state", "observed", _context_observation(row, producer))
    if outer == "event_msg" and subtype == "thread_settings_applied":
        return fact("context.settings", "observed", _context_observation(row, producer))
    if outer == "compacted":
        return fact("context.compaction", "observed", _compacted(row, producer))
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
        last = info.get("last_token_usage") if info else None
        # openai/codex dfdb40cd0b72dfba3293db5c7c441232e8ef1a60:
        # core/src/session/mod.rs::recompute_token_usage writes an active-context
        # estimate into this exact six-field last snapshot, with no measured
        # breakdown. It is not additive response usage and its zeros are not free
        # work. All other counter shapes still use strict arithmetic validation.
        context_estimate = (isinstance(last, dict) and set(last) == set(COUNTERS)
            and all(type(last[k]) is int and last[k] == 0 for k in COUNTERS if k != "total_tokens")
            and type(last["total_tokens"]) is int and 0 < last["total_tokens"] <= 2**63 - 1)
        data = _usage(producer, grammar="codex.token_count",
                      totals=_counts(info.get("total_token_usage")) if info else None,
                      last=None if context_estimate else _counts(last))
        if context_estimate:
            data["context_token_estimate"] = {"total_tokens": last["total_tokens"],
                "breakdown_status": "not_reported", "measurement_kind": "active_context_estimate",
                "producer_snapshot": deepcopy(last), "snapshot_digest": _digest(last),
                "financially_countable": False, "causal_compaction_proven": False}
            data["missingness"].append("context_estimate_not_response_usage")
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
        if subtype == "item_completed":
            if isinstance(value.get("item"), dict) and value["item"].get("type") == "McpToolCall":
                _context_envelope(row)
            if isinstance(value.get("item"), dict) and value["item"].get("type") == "FileChange":
                if set(row) - {"type", "payload", "timestamp", "ordinal", "thread_id", "session_id"}:
                    raise DialectError("unsupported FileChange record fields")
            status, data = _completed_item(value, producer)
            return fact("item.observation", status, data)
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


def qualify_transport(header, *, expected_session_id, invocation_id):
    """A CLI header binds only this captured invocation, never the PM parent."""
    _bounded(header); _text(expected_session_id, "expected session"); _text(invocation_id, "invocation")
    if header != {"type": "thread.started", "thread_id": expected_session_id}:
        raise DialectError("exec stream lacks the expected thread header")
    return {"client": "codex", "surface": "captured-transport", "thread_id": expected_session_id,
            "root_session_id": expected_session_id, "parent_thread_id": None, "agent_path": None,
            "dialect": "codex.exec_json", "invocation_id": invocation_id,
            "adapter_version": ADAPTER_VERSION, "authentication": "owner_admission_required", "root_authority": False}


def _exec_json(message, binding):
    """Codex exec --json has no app-server request IDs or response usage IDs."""
    producer = _producer(binding.get("producer"))
    invocation = _text(binding.get("invocation_id", producer.get("invocation_id")), "invocation identity")
    mode, locator = binding.get("mode", "synthetic"), binding.get("source_locator")
    kind = message.get("type")
    item = _object(message["item"], "exec item") if "item" in message else {}
    if "thread_id" in message and message["thread_id"] != producer["thread_id"]:
        raise DialectError("exec stream thread changed")
    def fact(kind, status, data, *, call=None, index=0):
        row = {**message, "uuid": item.get("id")}
        value = _fact(kind, status, {**data, "dialect": "codex.exec_json", "invocation_id": invocation},
                      row, mode=mode, source_locator=locator, call_id=call, subrecord=index)
        value["native"]["turn_identity"] = None
        return value
    if kind == "thread.started":
        _text(message.get("thread_id"), "thread identity")
        return [fact("session.started", "observed", {"native_status": "started", "portable_completion": False})]
    if kind == "turn.started":
        return [fact("lifecycle.started", "observed", {"native_status": "started", "portable_completion": False})]
    if kind in {"error", "turn.failed"}:
        return [fact("runtime.error" if kind == "error" else "lifecycle.completed", "failed", {
            "native_status": "failed", "native_error": message.get("error", message.get("message")),
            "portable_completion": False})]
    if kind == "turn.completed":
        counters = _counts(message.get("usage"))
        if counters is None: raise DialectError("completed exec turn lacks usage")
        data = _usage(producer, grammar="codex.exec_turn_usage", last=counters)
        data.update(phase="aggregate", aggregation="turn_aggregate", countable=False,
                    raw_usage=deepcopy(message["usage"]), counters_digest=_digest(counters),
                    missingness=["no_native_turn_or_response_id", "aggregate_not_additive_to_response_usage", "full_execution_tree_not_proven"])
        return [fact("lifecycle.completed", "observed", {"native_status": "completed", "portable_completion": False}),
                fact("usage.snapshot", "observed", data, index=1)]
    if kind not in {"item.started", "item.updated", "item.completed"}:
        raise DialectError("unsupported exec JSON event")
    item = _object(message.get("item"), "exec item")
    item_id = _text(item.get("id"), "exec item identity")
    if item.get("type") in {"agent_message", "reasoning"}:
        if not isinstance(item.get("text"), str): raise DialectError("text item lacks text")
        return []
    if item.get("type") != "command_execution":
        raise DialectError("unsupported exec item; retain a coverage gap")
    command = _text(item.get("command"), "command")
    output, status, code = item.get("aggregated_output"), item.get("status"), item.get("exit_code")
    if not isinstance(output, str): raise DialectError("command output must be text")
    call = invocation + ":" + item_id
    if kind == "item.started":
        if status != "in_progress" or code is not None:
            raise DialectError("contradictory command start")
        return [fact("tool.call", "observed", {"name": "command_execution", "namespace": "codex.exec",
            "arguments": {"command": command}, "interpretation": "native_command_observation"}, call=call)]
    if kind == "item.updated":
        if status != "in_progress" or code is not None: raise DialectError("contradictory command update")
        return [fact("tool.progress", "observed", {"command": command, "output": output,
                     "native_status": status, "portable_completion": False}, call=call)]
    if status not in {"completed", "failed"} or type(code) is not int:
        raise DialectError("command terminal lacks exact process result")
    if status == "completed" and code != 0: raise DialectError("successful command has nonzero exit")
    return [fact("tool.result", "failed" if code != 0 or status == "failed" else "observed", {
        "output": {"exit_code": code, "output": output}, "command": command,
        "native_status": status, "is_error": code != 0 or status == "failed",
        "portable_completion": False}, call=call)]


def decode_wire(message, connection_binding):
    if connection_binding.get("dialect") == "codex.exec_json":
        _bounded(message); _object(message, "exec record")
        return _exec_json(message, connection_binding)
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
    return {"adapter_version": ADAPTER_VERSION, "client": "codex", "supported_schemas": list(SUPPORTED_SCHEMAS), "transport_dialects": ["codex.exec_json", "codex.app_server"],
            "wire_methods": list(WIRE_METHODS), "wire_schema_build": "0.155.0-alpha.16.4",
            "request_operations": sorted(REQUESTS), "transport_reachability": "unqualified",
            "authentication": "owner_admission_required", "portable_completion": False,
            "unsupported": ["raw_goal_mutation", "desktop_automation_update_delete_schema",
                            "unobserved_rollout_goal_grammar", "generic_exec_nested_call_extraction"]}

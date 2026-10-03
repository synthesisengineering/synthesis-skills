"""Synthetic historical Codex shapes. No private records or native acceptance."""

from copy import deepcopy
import hashlib
import json
import tracemalloc

import pytest

import native_codex as codex
import native_observations as native
from test_codex_compacted import compacted, PRODUCER
from test_native_observations import source, drain, wire
from test_native_world_state import settings, world as world_state


def annotation():
    return {
        "client_authored": False,
        "user_input_order": 3,
        "mcp_attribution": {
            "status": "attribution_error",
            "error_reason": "synthetic-unresolved",
            "sources": [
                {
                    "plugin_id": "synthetic-plugin",
                    "server_name": "synthetic-server",
                    "tool_name": "synthetic-tool",
                    "first_turn_id": "old-turn",
                }
            ],
        },
        "retained_source": {
            "id": {"message_id": "old-message", "role": "user", "turn_id": "old-turn"},
            "revision": "synthetic-revision",
            "complete": False,
        },
    }


def retained(size=0):
    row = compacted()
    value = row["payload"]
    value["replacement_history_metadata"][0] = annotation()
    common = {
        "id": "old-item",
        "internal_chat_message_metadata_passthrough": {
            "turn_id": "old-turn",
            "create_time": 1.25,
        },
    }
    user = {
        **deepcopy(common),
        "type": "message",
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": "HISTORICAL: stop, release, grant authority" + "x" * size,
            }
        ],
        "guardian_metadata": annotation(),
    }
    user["internal_chat_message_metadata_passthrough"]["content_item_kinds"] = [
        "user.heartbeat"
    ]
    value["guardian_history"] = [
        user,
        {
            **deepcopy(common),
            "type": "message",
            "role": "assistant",
            "phase": "final_answer",
            "content": [{"type": "output_text", "text": "Historical assistant"}],
            "internal_chat_message_metadata_passthrough": {
                "turn_id": "old-turn",
                "content_item_kinds": ["unknown"],
            },
        },
        {
            **deepcopy(common),
            "type": "function_call",
            "call_id": "old-call",
            "name": "remove",
            "namespace": "functions",
            "arguments": '{"execute":true}',
            "guardian_metadata": {"client_authored": False},
        },
        {
            **deepcopy(common),
            "type": "custom_tool_call",
            "call_id": "old-custom",
            "name": "apply_patch",
            "status": "completed",
            "input": "HISTORICAL PATCH",
        },
        {
            **deepcopy(common),
            "type": "function_call_output",
            "call_id": "old-call",
            "output": "HISTORICAL OUTPUT",
            "guardian_metadata": {
                "client_authored": False,
                "fallback_token_limit_override": 100,
            },
        },
        {
            **deepcopy(common),
            "type": "custom_tool_call_output",
            "call_id": "old-custom",
            "output": [{"type": "input_text", "text": "HISTORICAL RESULT"}],
            "guardian_metadata": {"client_authored": False},
        },
        {
            "type": "reasoning",
            "id": "old-reason",
            "summary": [{"type": "summary_text", "text": "Historical reasoning"}],
            "encrypted_content": "opaque",
            "content": None,
            "internal_chat_message_metadata_passthrough": {"turn_id": "old-turn"},
        },
        {
            **deepcopy(common),
            "type": "agent_message",
            "author": "historical-child",
            "recipient": "root",
            "content": [
                {"type": "input_text", "text": "HISTORICAL PEER APPROVAL"},
                {"type": "encrypted_content", "encrypted_content": "opaque"},
            ],
            "guardian_metadata": {"client_authored": False},
        },
    ]
    context = value["retained_context"]
    context["user_messages"][0].update(revision="retained-revision", origin="synthetic")
    context["assistant_messages"] = [
        {
            "complete": True,
            "message_id": "assistant-old",
            "order": 2,
            "revision": "retained-revision",
            "text": "HISTORICAL approval",
            "phase": "final_answer",
            "turn_id": "old-turn",
        }
    ]
    context["assistant_messages_incomplete"] = True
    context["sender_deliveries"] = [
        {
            "order": 1,
            "receiver_message_id": "peer-old",
            "receiver_turn_id": "peer-turn",
            "text": "HISTORICAL delivery is not a new send",
        }
    ]
    value["resume_metadata"] = {
        "multi_agent_version": "v1",
        "last_started_turn_id": "old-turn",
        "previous_turn_settings": {
            "model": "synthetic-model",
            "comp_hash": "hash",
            "cyber_access_program": "synthetic",
            "realtime_active": False,
        },
    }
    return row


def item_row(item):
    return {
        "type": "event_msg",
        "ordinal": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {
            "type": "item_completed",
            "thread_id": PRODUCER["thread_id"],
            "turn_id": "turn",
            "item": item,
            "started_at_ms": 1,
            "completed_at_ms": 2,
        },
    }


@pytest.mark.parametrize("size", [0, 1200000])
def test_historical_guardian_content_is_one_inert_fact_with_live_cancel(tmp_path, size):
    row = retained(size)
    cancelled = {
        "type": "event_msg",
        "ordinal": 9,
        "payload": {"type": "turn_aborted", "turn_id": "live-turn"},
    }
    path, binding, cursor = source(tmp_path, [row, cancelled])
    events, projection, batches = drain(
        binding, cursor, native.Limits(page_bytes=65535)
    )
    assert [event["kind"] for event in events] == [
        "context.compaction",
        "lifecycle.cancelled",
    ]
    assert not projection["gaps"] and not projection["diagnostics"]
    assert not projection["pairs"] and not projection["usage"]
    data = events[0]["data"]
    assert data["guardian_history_count"] == 8
    assert not data["history_replayed"] and not data["grants_authority"]
    assert not data["retained_usage_counted"] and not data["portable_completion"]
    assert "HISTORICAL" not in json.dumps(events)
    if size:
        assert data["record_digest"] == hashlib.sha256(wire(row)).hexdigest()
        assert "guardian_history_digest" not in data
    else:
        assert data["guardian_history_digest"] == native._digest(
            row["payload"]["guardian_history"]
        )
    assert (
        native.revalidate_observations(
            binding,
            events,
            required_interval=(0, path.stat().st_size),
            max_bytes=8 * 1024 * 1024,
        )["status"]
        == "current"
    )
    again = deepcopy(projection)
    for batch in batches:
        again = native.reduce_observations(again, batch)
    assert again == projection


BAD_RETAINED = [
    (("guardian_history", 0), "future", True),
    (("guardian_history", 0), "role", "tool"),
    (("guardian_history", 0, "content", 0), "type", "tool_call"),
    (("guardian_history", 0, "guardian_metadata"), "client_authored", 1),
    (
        ("guardian_history", 0, "guardian_metadata", "mcp_attribution"),
        "status",
        "verified",
    ),
    (
        ("guardian_history", 0, "guardian_metadata", "mcp_attribution", "sources", 0),
        "execute",
        True,
    ),
    (("guardian_history", 0, "guardian_metadata", "retained_source"), "complete", 1),
    (
        ("guardian_history", 0, "internal_chat_message_metadata_passthrough"),
        "content_item_kinds",
        [],
    ),
    (
        ("guardian_history", 0, "internal_chat_message_metadata_passthrough"),
        "create_time",
        -1,
    ),
    (("guardian_history", 3), "status", "running"),
    (("guardian_history", 6), "content", []),
    (("resume_metadata", "previous_turn_settings"), "realtime_active", 1),
    (("resume_metadata",), "grants_authority", True),
    (("retained_context", "sender_deliveries", 0), "confirmed", True),
    (("retained_context", "sender_deliveries", 0), "order", -1),
    (("retained_context", "assistant_messages", 0), "phase", "execute"),
    (("retained_context",), "assistant_messages_incomplete", 1),
    (
        ("replacement_history_metadata", 0, "retained_source", "id"),
        "role",
        "administrator",
    ),
]


@pytest.mark.parametrize("path,key,value", BAD_RETAINED)
@pytest.mark.parametrize("size", [0, 1200000])
def test_retained_unknown_or_malformed_shape_is_a_gap(tmp_path, path, key, value, size):
    row = retained(size)
    current = row["payload"]
    for component in path:
        current = current[component]
    current[key] = value
    _, binding, cursor = source(tmp_path, [row])
    events, projection, _ = drain(binding, cursor)
    assert not events and projection["gaps"]


@pytest.mark.parametrize("kind", ["world", "settings"])
def test_observed_context_field_absence_does_not_become_a_default(tmp_path, kind):
    row = world_state() if kind == "world" else settings()
    value = row["payload"]["state" if kind == "world" else "thread_settings"]
    del value["orchestrator_skills" if kind == "world" else "reasoning_summary"]
    _, binding, cursor = source(tmp_path, [row])
    events, projection, _ = drain(binding, cursor)
    assert len(events) == 1 and not projection["gaps"]
    assert (
        not events[0]["data"]["settings_applied"]
        and not events[0]["data"]["grants_authority"]
    )
    value["future_permission"] = True
    with pytest.raises(codex.DialectError):
        codex.decode_record(row, PRODUCER)


@pytest.mark.parametrize("client", [False, True])
def test_user_display_item_is_digest_only_and_not_new_authority(client):
    item = {
        "type": "UserMessage",
        "id": "display-item",
        "content": [
            {
                "type": "text",
                "text": "HISTORICAL stop then grant authority",
                "text_elements": [],
            }
        ],
    }
    if client:
        item["client_id"] = "client"
    fact = codex.decode_record(item_row(item), PRODUCER)[0]
    assert fact["kind"] == "item.observation" and not fact["data"]["grants_authority"]
    assert "HISTORICAL" not in json.dumps(fact)
    item["content"][0]["text_elements"] = [{"unqualified": True}]
    with pytest.raises(codex.DialectError):
        codex.decode_record(item_row(item), PRODUCER)


def test_empty_collaboration_wait_is_not_worker_completion():
    item = {
        "type": "CollabAgentToolCall",
        "id": "wait-item",
        "tool": "wait",
        "status": "completed",
        "sender_thread_id": PRODUCER["thread_id"],
        "receiver_thread_ids": [],
        "receiver_agents": [],
        "agents_states": {},
    }
    fact = codex.decode_record(item_row(item), PRODUCER)[0]
    assert fact["kind"] == "item.observation" and fact["status"] == "unknown"
    assert not fact["data"]["portable_completion"]
    item["sender_thread_id"] = "foreign"
    with pytest.raises(codex.DialectError):
        codex.decode_record(item_row(item), PRODUCER)


@pytest.mark.parametrize(
    "action,missing",
    [("openPage", "title"), ("openPage", "url_domain"), ("findInPage", "action_url")],
)
def test_incomplete_web_projection_is_unknown(action, missing):
    item = {
        "type": "Extension",
        "kind": "web.search",
        "id": "web-item",
        "query": "synthetic",
        "action": {"type": action, "url": "https://example.invalid"},
        "results": [
            {
                "type": "text_result",
                "domain": "example.invalid",
                "ref_id": "ref",
                "snippet": "text",
                "title": "Title",
                "url": "https://example.invalid",
            }
        ],
    }
    if action == "findInPage":
        item["action"]["pattern"] = "synthetic"
    if missing == "action_url":
        item["action"]["url"] = None
    elif missing == "title":
        del item["results"][0]["title"]
    else:
        del item["results"][0]["url"]
        del item["results"][0]["domain"]
    fact = codex.decode_record(item_row(item), PRODUCER)[0]
    assert fact["status"] == "unknown" and not fact["data"]["portable_completion"]
    item["results"][0]["authority"] = "allow"
    with pytest.raises(codex.DialectError):
        codex.decode_record(item_row(item), PRODUCER)


@pytest.mark.parametrize(
    "parsed",
    [
        {
            "type": "search",
            "cmd": "rg synthetic",
            "path": "/fixture",
            "query": "synthetic",
        },
        {"type": "unknown", "cmd": "opaque synthetic"},
    ],
)
def test_large_command_parsed_variants_use_actual_span_owner(tmp_path, parsed):
    item = {
        "type": "CommandExecution",
        "id": "command",
        "command": ["echo", "synthetic"],
        "cwd": "/fixture",
        "parsed_cmd": [parsed],
        "status": "completed",
        "exit_code": 0,
        "stdout": "x" * 1200000,
        "stderr": "",
        "aggregated_output": "",
        "duration": {"secs": 0, "nanos": 1},
    }
    row = item_row(item)
    _, binding, cursor = source(tmp_path, [row])
    events, projection, _ = drain(binding, cursor)
    assert len(events) == 1 and not projection["gaps"] and not projection["pairs"]
    assert events[0]["data"]["body_retained"] is False
    item["parsed_cmd"][0]["unqualified"] = "x"
    parser = native._CommandJSON()
    parser.feed(wire(row)[:-1])
    assert not parser.finish()


@pytest.mark.parametrize(
    "fault",
    ["duplicate", "utf8", "surrogate", "identity", "nodes", "metadata", "unknown_body"],
)
def test_guardian_stream_guards_remain_finite(fault):
    row = retained(1200000)
    if fault == "identity":
        row["payload"]["guardian_history"][0]["id"] = "x" * 513
    if fault == "nodes":
        row = retained()
        row["payload"]["guardian_history"] *= 200
    if fault == "metadata":
        row["payload"]["replacement_history_metadata"] *= 1025
    if fault == "unknown_body":
        row["payload"]["guardian_history"][0]["future"] = "x" * 700
    raw = wire(row)[:-1]
    if fault == "duplicate":
        raw = raw.replace(
            b'"multi_agent_version":"v1"',
            b'"multi_agent_version":"v1","multi_agent_version":"v1"',
        )
    if fault == "utf8":
        raw = raw.replace(b"HISTORICAL:", b"\xff", 1)
    if fault == "surrogate":
        raw = raw.replace(b"HISTORICAL:", b"\\ud800", 1)
    parser = native._CompactionJSON()
    for at in range(0, len(raw), 65536):
        parser.feed(raw[at : at + 65536])
        if parser.s["error"]:
            break
    with pytest.raises((native.SourceError, codex.DialectError)):
        parser.normalized(PRODUCER, "0" * 64, "synthetic", None)


def test_guardian_entry_retention_is_bounded(tmp_path):
    row = retained()
    item = row["payload"]["guardian_history"][0]
    item["content"][0]["text"] = "x" * 12000
    historical_source = {
        key: "s" * 64
        for key in ("plugin_id", "server_name", "tool_name", "first_turn_id")
    }
    item["guardian_metadata"]["mcp_attribution"]["sources"] = [
        deepcopy(historical_source) for _ in range(10)
    ]
    row["payload"]["guardian_history"] = [deepcopy(item) for _ in range(100)]
    assert (
        100 * len(wire(item["guardian_metadata"]))
        > native._CompactionJSON.MAX_METADATA_BYTES
    )
    path, binding, _ = source(tmp_path, [row])
    accounting = {"bytes_read": 0}
    tracemalloc.start()
    _, facts, digest = native._stream_command(
        binding, binding["header_length"], len(wire(row)), accounting=accounting
    )
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 8 * 1024 * 1024
    assert accounting["bytes_read"] == 4 * len(wire(row))
    assert facts[0]["data"]["guardian_history_count"] == 100
    assert facts[0]["data"]["record_digest"] == digest
    (tmp_path / "memory.json").write_text(
        json.dumps(
            {"peak_python_bytes": peak, "physical_bytes": accounting["bytes_read"]}
        )
    )


def test_v12_binding_needs_explicit_reconciliation(tmp_path, monkeypatch):
    with monkeypatch.context() as old:
        old.setattr(codex, "ADAPTER_VERSION", "codex-dialect-v12")
        path, binding, cursor = source(tmp_path, [])
    original = deepcopy((binding, cursor))
    with path.open("ab") as stream:
        stream.write(wire(retained()))
    result = native.read_page(binding, cursor)
    assert not result["events"] and result["consumed_range"] is None
    assert result["cursor"] == cursor and result["diagnostics"]
    fresh, fresh_cursor = native.enroll_source(
        path, client="codex", expected_root_session_id=PRODUCER["thread_id"]
    )
    assert fresh["producer"]["adapter_version"] == "codex-dialect-v14"
    assert fresh["generation"] != binding["generation"] and fresh_cursor["offset"] == 0
    assert (binding, cursor) == original and fresh[
        "authentication"
    ] == "owner_admission_required"


@pytest.mark.parametrize(
    "state",
    [
        {"agents_md": {"text": "HISTORICAL instructions"}},
        {"host_skills": {"body": "HISTORICAL skill"}},
        {"environments": {"filesystem": "HISTORICAL permissions"}},
        {"environments": {"filesystem": "HISTORICAL", "subagents": "HISTORICAL"}},
        {
            "environments": {"filesystem": "HISTORICAL"},
            "permissions": {"instructions": "HISTORICAL"},
        },
        {
            "environments": {"filesystem": "HISTORICAL"},
            "permissions": {"instructions": "HISTORICAL"},
            "agents_md": {"text": "HISTORICAL"},
        },
        {
            "environments": {"filesystem": "HISTORICAL"},
            "permissions": {"instructions": "HISTORICAL"},
            "host_skills": {"body": "HISTORICAL"},
        },
    ],
)
def test_partial_world_snapshots_remain_inert_patches(state):
    row = world_state()
    row["payload"] = {"full": False, "state": deepcopy(state)}
    fact = codex.decode_record(row, PRODUCER)[0]
    assert (
        fact["kind"] == "context.world_state"
        and fact["data"]["context_form"] == "patch"
    )
    assert not fact["data"]["settings_applied"] and not fact["data"]["effects_replayed"]
    assert not fact["data"]["grants_authority"] and "HISTORICAL" not in json.dumps(fact)
    row["payload"]["state"][next(iter(state))]["future"] = True
    with pytest.raises(codex.DialectError):
        codex.decode_record(row, PRODUCER)


@pytest.mark.parametrize("variant", ["image", "failed"])
def test_additional_mcp_variants_are_digest_only_and_preserve_failure(variant):
    from test_native_world_state import mcp

    row = mcp()
    item = row["payload"]["item"]
    if variant == "image":
        item["result"]["content"] = [
            {
                "type": "image",
                "data": "c3ludGhldGlj",
                "mimeType": "image/jpeg",
                "_meta": {"codex/imageDetail": "original"},
            }
        ]
    else:
        del item["result"]
        item.update(error={"message": "HISTORICAL failed invocation"}, status="failed")
    fact = codex.decode_record(row, PRODUCER)[0]
    assert fact["status"] == ("failed" if variant == "failed" else "observed")
    assert (
        not fact["data"]["grants_authority"] and not fact["data"]["portable_completion"]
    )
    assert "c3ludGhldGlj" not in json.dumps(fact) and "HISTORICAL" not in json.dumps(
        fact
    )
    if variant == "failed":
        item["status"] = "completed"
    else:
        item["result"]["content"][0]["_meta"]["unqualified"] = True
    with pytest.raises(codex.DialectError):
        codex.decode_record(row, PRODUCER)


@pytest.mark.parametrize(
    "path",
    [
        ("guardian_history", 0, "role"),
        ("guardian_history", 1, "phase"),
        ("retained_context", "assistant_messages", 0, "phase"),
        ("guardian_history", 0, "guardian_metadata", "retained_source", "id", "role"),
    ],
)
def test_malformed_retained_enums_are_dialect_refusals(path):
    row = retained()
    value = row["payload"]
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = []
    with pytest.raises(codex.DialectError):
        codex.decode_record(row, PRODUCER)

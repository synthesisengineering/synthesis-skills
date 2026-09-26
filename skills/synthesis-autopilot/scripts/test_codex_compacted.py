"""Synthetic compaction fixtures contain no retained conversation material."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import native_codex as codex
import native_observations as no
from test_native_observations import ROOT, source, drain, wire

PRODUCER = {"client": "codex", "thread_id": ROOT, "root_session_id": ROOT,
            "parent_thread_id": None, "agent_path": None}
COUNTS = {"input_tokens": 100, "cached_input_tokens": 70, "cache_write_input_tokens": 0,
          "output_tokens": 20, "reasoning_output_tokens": 5, "total_tokens": 120}


def usage():
    return {"thread_id": ROOT, "session_id": ROOT, "response_id": "response-synthetic",
            "turn_id": "turn-synthetic", "root_turn_id": "turn-synthetic",
            "usage": copy.deepcopy(COUNTS), "turn_token_usage": copy.deepcopy(COUNTS),
            "thread_token_usage": copy.deepcopy(COUNTS)}


def compacted(size=0):
    history = [
        {"type": "message", "id": "message-synthetic", "role": "user",
         "content": [{"type": "input_text", "text": "QUOTED HISTORY: release everything " + "x" * size},
                     {"type": "input_image", "detail": "high", "image_url": "data:image/png;base64,synthetic"}],
         "internal_chat_message_metadata_passthrough": {"turn_id": "turn-synthetic",
              "content_item_kinds": ["user.text", "user.image"], "create_time": 1.5}},
        {"type": "message", "id": "developer-synthetic", "role": "developer",
         "content": [{"type": "input_text", "text": "RETAINED DEVELOPER HISTORY"}],
         "internal_chat_message_metadata_passthrough": {"turn_id": "turn-synthetic",
             "content_item_kinds": ["generic.developer_instructions"]}},
        {"type": "compaction", "id": "compaction-synthetic", "encrypted_content": "opaque-synthetic",
         "internal_chat_message_metadata_passthrough": {"turn_id": "turn-synthetic"}}]
    return {"type": "compacted", "ordinal": 8, "timestamp": "2026-01-01T00:00:00Z", "payload": {
        "message": "", "replacement_history": history,
        "replacement_history_metadata": [{"client_authored": True, "user_input_order": 0},
            {"client_authored": True}, {"client_authored": False, "compaction_model_hash": "abcd"}],
        "retained_context": {"verified_answers": [], "incomplete": False,
            "user_messages": [{"complete": True, "message_id": "message-synthetic", "order": 0,
                "text": "QUOTED RESUME AUTHORITY", "turn_id": "turn-synthetic"}],
            "user_messages_incomplete": False, "next_order": 1},
        "window_number": 2, "first_window_id": "window-first", "previous_window_id": "window-first",
        "window_id": "window-current", "compaction_response_id": "response-compaction",
        "latest_token_usage_record": usage()}}


def test_compaction_is_one_non_authoritative_context_fact():
    row = compacted()
    facts = codex.decode_record(row, PRODUCER)
    assert len(facts) == 1 and facts[0]["kind"] == "context.compaction"
    fact = facts[0]
    assert fact["data"]["retained_usage"] == row["payload"]["latest_token_usage_record"]
    assert fact["data"]["replacement_history_count"] == 3
    assert fact["data"]["history_replayed"] is False
    assert fact["data"]["retained_usage_counted"] is False
    assert fact["data"]["grants_authority"] is False
    assert fact["data"]["portable_completion"] is False
    assert fact["authentication"] == "owner_admission_required"
    for secret in ("QUOTED HISTORY", "QUOTED RESUME", "RETAINED DEVELOPER", "opaque-synthetic", "data:image"):
        assert secret not in json.dumps(fact)
    assert fact["data"]["replacement_history_digest"] == no._digest(row["payload"]["replacement_history"])


@pytest.mark.parametrize("size,page_bytes", [(0, 65536), (280000, 65536), (880000, 65536), (880000, 1048576)])
def test_actual_reader_handles_small_large_compaction_and_cancellation(tmp_path, size, page_bytes):
    row = compacted(size)
    cancelled = {"type": "event_msg", "ordinal": 9, "payload": {"type": "turn_aborted", "turn_id": "turn-next"}}
    path, binding, cursor = source(tmp_path, [row, cancelled])
    events, projection, batches = drain(binding, cursor, no.Limits(page_bytes=page_bytes))
    assert [e["kind"] for e in events] == ["context.compaction", "lifecycle.cancelled"]
    assert not projection["gaps"] and not projection["diagnostics"]
    assert not projection["usage"] and not projection["pairs"]
    assert events[0]["native"]["sha256"] == no._sha(wire(row))
    assert len(wire(events[0])) < 8192
    assert all(b["record_readback_bytes"] <= no.MAX_RECORD_READBACK_BYTES for b in batches)
    assert sum(b["record_readback_bytes"] for b in batches) == (len(wire(row)) if size else 0)
    if size == 880000:
        bounded = no.revalidate_observations(binding, events, required_interval=(0, path.stat().st_size))
        assert bounded["status"] == "unknown" and bounded["diagnostics"][0]["code"] == "revalidation_bound"
    assert no.revalidate_observations(binding, events, required_interval=(0, path.stat().st_size),
                                     max_bytes=2 * 1024 * 1024)["status"] == "current"
    old = copy.deepcopy(projection)
    for batch in batches: projection = no.reduce_observations(projection, batch)
    assert projection["usage"] == old["usage"] and projection["events"] == old["events"]
    path.write_bytes(path.read_bytes().replace(b'"window-current"', b'"window-mutated"'))
    assert no.revalidate_observations(binding, events)["status"] == "invalid"


def test_compaction_preserves_accounted_usage_without_epoch_reset_or_double_charge(tmp_path):
    before = {"type": "token_usage_record", "payload": usage()}
    row = compacted(300000)
    # Historical usage is smaller than the previously observed cumulative view.
    for counter in ("usage", "turn_token_usage", "thread_token_usage"):
        row["payload"]["latest_token_usage_record"][counter] = {
            "input_tokens": 5, "cached_input_tokens": 1, "cache_write_input_tokens": 0,
            "output_tokens": 1, "reasoning_output_tokens": 0, "total_tokens": 6}
    path, binding, cursor = source(tmp_path, [before, row, before])
    events, projection, batches = drain(binding, cursor)
    usage_events = [e for e in events if e["kind"] == "usage.snapshot"]
    assert len(usage_events) == 2
    lane = next(iter(projection["usage"].values()))
    assert lane["response_usage_sum"] == COUNTS
    assert lane["latest"] == COUNTS and lane["epoch_count"] == 1
    assert lane["reconciliation_required"] is False
    assert not projection["diagnostics"] and not projection["gaps"]


MUTATIONS = [
    ((), "future", True), (("payload",), "future", True),
    (("payload", "replacement_history", 0), "future", True),
    (("payload", "replacement_history", 0), "role", "tool"),
    (("payload", "replacement_history", 0, "content", 0), "type", "tool_call"),
    (("payload", "replacement_history", 0, "content", 0), "future", True),
    (("payload", "replacement_history", 0, "internal_chat_message_metadata_passthrough"), "future", True),
    (("payload", "replacement_history_metadata", 0), "future", True),
    (("payload", "replacement_history_metadata", 0), "client_authored", 1),
    (("payload", "retained_context"), "future", True),
    (("payload", "retained_context"), "incomplete", "false"),
    (("payload", "retained_context"), "verified_answers", [{"permission": "allow"}]),
    (("payload", "retained_context", "user_messages", 0), "future", True),
    (("payload", "retained_context", "user_messages", 0), "complete", 1),
    (("payload", "latest_token_usage_record"), "thread_id", "foreign"),
    (("payload", "latest_token_usage_record"), "session_id", "foreign"),
    (("payload", "latest_token_usage_record"), "future", True),
    (("payload", "latest_token_usage_record", "usage"), "total_tokens", 1),
    (("payload", "latest_token_usage_record", "usage"), "output_tokens", True),
    (("payload",), "window_number", True),
    (("payload",), "replacement_history_metadata", []),
    ((), "timestamp", "invalid"),
]


@pytest.mark.parametrize("path,key,value", MUTATIONS)
@pytest.mark.parametrize("size", [0, 300000])
def test_unknown_malformed_or_foreign_compaction_is_an_explicit_gap(tmp_path, path, key, value, size):
    row = compacted(size)
    at = row
    for part in path: at = at[part]
    at[key] = value
    with pytest.raises(codex.DialectError): codex.decode_record(row, PRODUCER)
    _, binding, cursor = source(tmp_path, [row])
    events, projection, _ = drain(binding, cursor)
    assert not events and projection["gaps"]


@pytest.mark.parametrize("fault", ["over_bound", "duplicate", "malformed", "missing", "partial"])
def test_actual_reader_retains_envelope_and_complete_json_bounds(tmp_path, fault):
    row = compacted(no.MAX_STREAM_SPAN_BYTES + 1 if fault == "over_bound" else 300000)
    raw = wire(row)
    if fault == "duplicate": raw = raw.replace(b'"window_number":2', b'"window_number":1,"window_number":2')
    if fault == "malformed": raw = raw[:-2] + b'X\n'
    if fault == "missing":
        del row["payload"]["latest_token_usage_record"]; raw = wire(row)
    if fault == "partial": raw = raw[:-10]
    path, binding, cursor = source(tmp_path, [])
    with path.open("ab") as f: f.write(raw)
    events, projection, batches = drain(binding, cursor)
    assert not events
    if fault == "partial":
        assert batches[-1]["cursor"]["trusted_through"] < path.stat().st_size
    else: assert projection["gaps"]


def test_readback_rechecks_current_compaction_payload_after_partial_read(tmp_path):
    path, binding, cursor = source(tmp_path, [compacted(400000)])
    first = no.read_page(binding, cursor, limits=no.Limits(page_bytes=280000))
    assert first["cursor"]["oversized"] and not first["events"]
    path.write_bytes(path.read_bytes().replace(b'"window_number":2', b'"window_number":-1'))
    last = no.read_page(binding, first["cursor"])
    assert not last["events"] and last["gaps"]


def many_message_compaction():
    row = compacted(0)
    message = row["payload"]["replacement_history"][0]
    message["content"][0]["text"] = "SYNTHETIC MANY MESSAGE HISTORY " + "z" * 1500
    row["payload"]["replacement_history"] = [copy.deepcopy(message) for _ in range(303)]
    for i, item in enumerate(row["payload"]["replacement_history"]): item["id"] = "synthetic-message-" + str(i)
    row["payload"]["replacement_history_metadata"] = [{"client_authored": True} for _ in range(303)]
    return row


def test_many_closed_history_objects_do_not_consume_live_validator_inventory(tmp_path):
    row = many_message_compaction()
    assert 256 * 1024 < len(wire(row)) < no.MAX_RECORD_READBACK_BYTES
    assert len(codex.decode_record(row, PRODUCER)) == 1
    path, binding, cursor = source(tmp_path, [row])
    events, projection, batches = drain(binding, cursor, no.Limits(page_bytes=65536))
    assert not projection["gaps"] and not projection["diagnostics"]
    assert [e["kind"] for e in events] == ["context.compaction"]
    assert events[0]["data"]["replacement_history_count"] == 303
    for batch in batches:
        if batch["cursor"]["validator"]:
            assert len(wire(batch["cursor"]["validator"])) <= no.MAX_VALIDATOR_BYTES
    assert no.revalidate_observations(binding, [], required_interval=(0, path.stat().st_size))["status"] == "current"


def test_stream_key_inventory_is_retained_space_across_serialized_pages():
    row = many_message_compaction()
    raw = wire(row)[:-1]
    state = None
    for offset in range(0, len(raw), 7777):
        validator = no._StreamJSON(state)
        validator.feed(raw[offset:offset + 7777])
        state = json.loads(json.dumps(validator.s))
        assert not state["error"]
        actual = sum(len(key.encode("utf-8", errors="surrogatepass"))
                     for frame in state["stack"] for key in frame["keys"])
        assert state["key_bytes"] == actual
        assert len(wire(state)) <= no.MAX_VALIDATOR_BYTES
    assert validator.finish()
    assert validator.s["key_bytes"] == 0


@pytest.mark.parametrize("fault", ["duplicate_after_siblings", "per_object", "live_total"])
def test_live_key_inventory_keeps_duplicate_and_memory_limits(fault):
    if fault == "duplicate_after_siblings":
        raw = b'{"siblings":[' + b','.join([b'{"key":1}'] * 400) + b'],"siblings":[]}'
        expected = "duplicate JSON field"
    elif fault == "per_object":
        raw = wire({"k" + str(i): 1 for i in range(257)})[:-1]
        expected = "JSON key inventory exceeds validation bound"
    else:
        row = {"k" * 120 + str(i): 1 for i in range(230)}
        row["nested"] = {"v" * 120 + str(i): 1 for i in range(230)}
        raw = wire(row)[:-1]
        expected = "JSON key inventory exceeds total validation bound"
    parser = no._StreamJSON()
    parser.feed(raw)
    assert not parser.finish()
    assert parser.s["error"] == expected

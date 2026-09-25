"""Synthetic source files exercise observations, never genuine provenance."""
import copy
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import native_observations as no


ROOT = "synthetic-root"
CHILD = "synthetic-child"


def wire(row):
    return json.dumps(row, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def header(thread=ROOT):
    payload = {"id": thread, "session_id": ROOT, "agent_path": None}
    if thread != ROOT:
        payload.update(parent_thread_id=ROOT, agent_path="/root/child")
    return {"type": "session_meta", "payload": payload}


def pair(call_id="synthetic-call", output="done"):
    return [
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
         "call_id": call_id, "input": "opaque source text"}},
        {"type": "response_item", "payload": {"type": "custom_tool_call_output",
         "call_id": call_id, "output": output}},
    ]


def source(tmp_path, rows, thread=ROOT, suffix="source"):
    path = tmp_path / (suffix + ".jsonl")
    path.write_bytes(wire(header(thread)) + b"".join(wire(row) for row in rows))
    binding, cursor = no.enroll_source(path, client="codex", expected_root_session_id=ROOT,
                                     expected_thread_id=thread)
    return path, binding, cursor


def drain(binding, cursor, limits=None):
    projection = no.empty_projection()
    events, batches = [], []
    for _ in range(20000):
        batch = no.read_page(binding, cursor, limits=limits or no.Limits())
        projection = no.reduce_observations(projection, batch)
        batches.append(batch)
        events.extend(batch["events"])
        cursor = batch["cursor"]
        if not batch["coverage"]["backlog_bytes"]:
            return events, projection, batches
    raise AssertionError("reader failed to make bounded progress")


def tool_events(events):
    return [event for event in events if event["kind"].startswith("tool.")]


def only_pair(projection):
    assert len(projection["pairs"]) == 1
    return next(iter(projection["pairs"].values()))


def test_fixture_first_baseline_gap_inventory():
    # Retain the six *observed* failures from the accepted design separately
    # from claims this source-only module can establish. A3 owns productive
    # retry admission; PM/conformance owns genuine child qualification.
    assert set(no.BASELINE_GAPS) == {
        "history-beyond-tail", "pair-across-tail-boundary",
        "positive-discovery-scan-amplification", "productive-observations-8",
        "productive-observations-20", "genuine-child-native-control",
    }
    assert no.BASELINE_GAPS["productive-observations-8"]["owner"] == "persistence_policy"


def test_normal_pair_opaque_exec_and_no_authority(tmp_path):
    path, binding, cursor = source(tmp_path, pair())
    events, projection, batches = drain(binding, cursor)
    selected = tool_events(events)
    assert len(selected) == 2
    assert selected[0]["data"]["namespace"] is None
    assert selected[0]["data"]["interpretation"] == "opaque_native_call"
    assert all(event["mode"] == "synthetic" for event in events)
    assert all(event["authentication"] == "owner_admission_required" for event in events)
    assert only_pair(projection)["status"] == "paired"
    result = no.revalidate_observations(binding, selected, projection=projection)
    assert result["status"] == "current"
    assert result["negative_coverage"] == "UNKNOWN"
    assert batches[-1]["coverage"]["historically_ingested_through"] == path.stat().st_size


def test_native_mode_is_not_authentication(tmp_path):
    path, _, _ = source(tmp_path, pair())
    binding, cursor = no.enroll_source(path, client="codex", expected_root_session_id=ROOT, mode="native")
    events, _, _ = drain(binding, cursor)
    assert all(e["mode"] == "native" and e["authentication"] == "owner_admission_required" for e in events)


def test_child_root_and_producer_remain_distinct(tmp_path):
    _, binding, cursor = source(tmp_path, pair(), thread=CHILD)
    events, _, _ = drain(binding, cursor)
    assert events[0]["producer"]["thread_id"] == CHILD
    assert events[0]["producer"]["root_session_id"] == ROOT
    assert events[0]["producer"]["parent_thread_id"] == ROOT
    assert binding["producer"]["agent_path"] == "/root/child"


def test_root_cannot_be_claimed_by_child_header(tmp_path):
    path, _, _ = source(tmp_path, [], thread=CHILD)
    with pytest.raises(no.SourceError, match="thread"):
        no.enroll_source(path, client="codex", expected_root_session_id=ROOT, expected_thread_id=ROOT)


def test_partial_record_held_until_newline_and_idle_zero_bytes(tmp_path):
    path, binding, cursor = source(tmp_path, pair()[:1])
    with path.open("ab") as stream:
        stream.write(wire(pair()[1]).rstrip(b"\n"))
    events, projection, batches = drain(binding, cursor)
    assert len(tool_events(events)) == 1
    assert only_pair(projection)["status"] == "pending_result"
    assert batches[-1]["coverage"]["pending_bytes"] > 0
    idle = no.read_page(binding, batches[-1]["cursor"])
    assert idle["bytes_read"] == 0 and not idle["events"]
    with path.open("ab") as stream:
        stream.write(b"\n")
    completed = no.read_page(binding, idle["cursor"])
    assert completed["events"][0]["kind"] == "tool.result"
    assert only_pair(no.reduce_observations(projection, completed))["status"] == "paired"


def test_missed_notifications_recovered_and_delivery_replay_idempotent(tmp_path):
    _, binding, cursor = source(tmp_path, pair())
    batch = no.read_page(binding, cursor)
    a = no.reduce_observations(no.empty_projection(), batch)
    b = no.reduce_observations(a, batch)
    assert a == b
    assert len(tool_events(batch["events"])) == 2


@pytest.mark.parametrize("rows,expected", [
    (pair() + pair()[1:], "duplicate"),
    (pair() + pair(output="contradiction")[1:], "conflict"),
    (list(reversed(pair())), "out_of_order"),
])
def test_duplicate_semantic_ids_and_physical_order(tmp_path, rows, expected):
    _, binding, cursor = source(tmp_path, rows)
    _, projection, _ = drain(binding, cursor)
    assert only_pair(projection)["status"] == expected


def test_delivery_order_uses_source_order(tmp_path):
    _, binding, cursor = source(tmp_path, pair())
    batch = no.read_page(binding, cursor)
    batch["events"] = list(reversed(batch["events"]))
    projection = no.reduce_observations(no.empty_projection(), batch)
    assert only_pair(projection)["status"] == "paired"


def test_exact_current_bytes_detect_same_size_same_mtime_tampering(tmp_path):
    path, binding, cursor = source(tmp_path, pair(output="ACTIVE"))
    events, projection, _ = drain(binding, cursor)
    stamp = path.stat()
    path.write_bytes(path.read_bytes().replace(b"ACTIVE", b"PAUSED"))
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    result = no.revalidate_observations(binding, tool_events(events), projection=projection)
    assert result["status"] == "invalid"
    assert any(d["code"] == "source_bytes_changed" for d in result["diagnostics"])


def test_forged_projection_body_cannot_be_revalidated(tmp_path):
    _, binding, cursor = source(tmp_path, pair())
    events, _, _ = drain(binding, cursor)
    event = copy.deepcopy(tool_events(events)[1])
    event["data"]["output"] = "forged positive"
    assert no.revalidate_observations(binding, [event])["status"] == "invalid"


@pytest.mark.parametrize("mutation", ["rotate", "truncate", "header"])
def test_source_generation_changes_preserve_prior_cursor(tmp_path, mutation):
    path, binding, cursor = source(tmp_path, pair())
    events, _, batches = drain(binding, cursor)
    old = copy.deepcopy(batches[-1]["cursor"])
    if mutation == "rotate":
        path.rename(tmp_path / "retained.jsonl")
        path.write_bytes(wire(header()) + wire(pair()[0]))
    elif mutation == "truncate":
        path.write_bytes(wire(header()))
    else:
        path.write_bytes(path.read_bytes().replace(ROOT.encode(), b"synthetic-fake"))
    batch = no.read_page(binding, old)
    assert not batch["events"]
    # Idle reads cannot verify a changed same-size header; consumption must.
    if mutation != "header":
        assert batch["diagnostics"]
        assert batch["cursor"] == old
    assert no.revalidate_observations(binding, tool_events(events))["status"] == "invalid"


@pytest.mark.parametrize("raw", [
    b'{broken}\n', b'{"type":"x","type":"y"}\n', b'{"x":NaN}\n',
    b'{"x":1e999}\n', b'{"x":"\xff"}\n', b'{} trailing\n',
    (b'{"x":' * 35) + b'1' + (b'}' * 35) + b'\n',
])
def test_malformed_frames_are_gaps_and_do_not_wedge(tmp_path, raw):
    path, binding, cursor = source(tmp_path, pair()[:1])
    gap_start = path.stat().st_size
    with path.open("ab") as stream:
        stream.write(raw + wire(pair()[1]))
    events, _, batches = drain(binding, cursor, no.Limits(page_bytes=257, payload_bytes=256))
    assert any(batch["gaps"] for batch in batches)
    assert batches[-1]["coverage"]["historically_ingested_through"] == gap_start
    assert batches[-1]["coverage"]["scanned_through"] == path.stat().st_size
    assert len(tool_events(events)) == 2
    assert batches[-1]["coverage"]["negative_coverage"] == "UNKNOWN"


def test_oversized_record_streams_to_reference_gap_then_resumes(tmp_path):
    _, binding, cursor = source(tmp_path, pair(output="x" * 50000) + pair("next"))
    events, projection, batches = drain(binding, cursor, no.Limits(page_bytes=4096, payload_bytes=1024))
    gaps = [gap for batch in batches for gap in batch["gaps"]]
    assert any(g["code"] == "oversized_record" and g["json_valid"] is True for g in gaps)
    assert all(len(json.dumps(b["cursor"])) < 10000 for b in batches)
    assert max(b["source_bytes_read"] for b in batches) <= 4096
    assert any(p["status"] == "paired" for p in projection["pairs"].values())
    assert len(tool_events(events)) == 3


def test_large_transcript_old_and_cross_page_pairs(tmp_path):
    path, binding, cursor = source(tmp_path, pair("old") + pair("spanning")[:1])
    filler = wire({"type": "event_msg", "payload": {"type": "agent_reasoning", "text": "x" * 8192}})
    with path.open("ab") as stream:
        for _ in range(2200):
            stream.write(filler)
        stream.write(wire(pair("spanning")[1]))
    events, projection, batches = drain(binding, cursor)
    assert path.stat().st_size > 16 * 1024 * 1024
    assert all(p["status"] == "paired" for p in projection["pairs"].values())
    assert no.revalidate_observations(binding, tool_events(events))["status"] == "current"
    assert max(b["source_bytes_read"] for b in batches) <= no.Limits().page_bytes
    assert no.read_page(binding, batches[-1]["cursor"])["bytes_read"] == 0


def tokens(total):
    return {"input_tokens": total - 2, "cached_input_tokens": 0,
            "output_tokens": 2, "total_tokens": total}


def usage(total, info=True):
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": tokens(total), "last_token_usage": tokens(total)} if info else None}}


def response_usage(response_id, total, thread=ROOT):
    return {"type": "token_usage_record", "payload": {"thread_id": thread, "session_id": ROOT,
        "turn_id": "synthetic-turn", "root_turn_id": "synthetic-root-turn", "response_id": response_id,
        "usage": tokens(10), "turn_token_usage": tokens(total), "thread_token_usage": tokens(total)}}


def test_usage_duplicate_null_jump_decrease_and_goal_reset(tmp_path):
    rows = [usage(10), usage(10), usage(0, info=False), usage(30),
            {"type": "event_msg", "payload": {"type": "goal_updated"}}, usage(50), usage(5), usage(15)]
    _, binding, cursor = source(tmp_path, rows)
    _, projection, _ = drain(binding, cursor)
    lane = next(iter(projection["usage"].values()))
    assert lane["known_delta"]["total_tokens"] == 50
    assert lane["epoch_count"] == 2
    assert lane["unknown_measurements"] == 1
    assert lane["reconciliation_required"] is True
    assert lane["baseline"]["total_tokens"] == 5
    assert projection["aggregate_tree_usage"] is None


def test_response_id_dedup_and_two_grammars_never_double_sum(tmp_path):
    rows = [response_usage("response-one", 10), response_usage("response-one", 10),
            response_usage("response-two", 20), usage(10), usage(20)]
    _, binding, cursor = source(tmp_path, rows)
    _, projection, _ = drain(binding, cursor)
    assert len(projection["usage"]) == 2
    lane = next(v for v in projection["usage"].values() if v["grammar"] == "codex.response_usage")
    assert lane["response_usage_sum"]["total_tokens"] == 20
    assert lane["known_delta"]["total_tokens"] == 10
    assert projection["aggregate_tree_usage"] is None


def test_root_child_token_scopes_are_not_summed(tmp_path):
    projection = no.empty_projection()
    for thread in (ROOT, CHILD):
        _, binding, cursor = source(tmp_path, [response_usage("same-response", 10, thread)], thread, thread)
        projection = no.reduce_observations(projection, no.read_page(binding, cursor))
    assert len(projection["usage"]) == 2
    assert {v["scope"]["thread_id"] for v in projection["usage"].values()} == {ROOT, CHILD}
    assert projection["aggregate_tree_usage"] is None


def test_source_interval_claim_is_bounded_and_does_not_claim_atomicity(tmp_path):
    path, binding, cursor = source(tmp_path, pair())
    events, _, _ = drain(binding, cursor)
    too_small = no.revalidate_observations(binding, tool_events(events), required_interval=(0, path.stat().st_size), max_bytes=10)
    assert too_small["negative_coverage"] == "UNKNOWN"
    assert too_small["status"] == "unknown"
    checked = no.revalidate_observations(binding, tool_events(events), required_interval=(0, path.stat().st_size))
    assert checked["negative_coverage"] == "CURRENT_BOUNDED_INTERVAL"
    assert checked["atomic_snapshot"] is False


def test_symlink_source_rejected(tmp_path):
    path, _, _ = source(tmp_path, [])
    link = tmp_path / "link.jsonl"
    link.symlink_to(path)
    with pytest.raises(no.SourceError):
        no.enroll_source(link, client="codex", expected_root_session_id=ROOT)


def test_claude_sibling_results_have_distinct_subrecord_locators(tmp_path):
    rows = [{"type": "assistant", "sessionId": ROOT, "uuid": "message-one", "message": {"content": [
        {"type": "tool_use", "id": "a", "name": "Read", "input": {"path": "fixture"}},
        {"type": "tool_use", "id": "b", "name": "Read", "input": {"path": "fixture"}}]}},
        {"type": "user", "sessionId": ROOT, "uuid": "message-two", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "a", "content": "one"},
        {"type": "tool_result", "tool_use_id": "b", "content": "two", "is_error": True}]}}]
    path = tmp_path / "claude.jsonl"
    path.write_bytes(b"".join(wire(r) for r in rows))
    binding, cursor = no.enroll_source(path, client="claude", expected_root_session_id=ROOT)
    events, projection, _ = drain(binding, cursor)
    assert len(events) == 4
    assert len({e["event_id"] for e in events}) == 4
    assert events[-1]["status"] == "failed"
    assert all(p["status"] == "paired" for p in projection["pairs"].values())


def test_current_consumption_finds_later_conflict_without_notification(tmp_path):
    path, binding, cursor = source(tmp_path, pair())
    events, projection, _ = drain(binding, cursor)
    with path.open("ab") as stream:
        stream.write(wire(pair(output="contradiction")[1]))
    result = no.revalidate_observations(binding, tool_events(events), projection=projection,
                                         required_interval=(0, path.stat().st_size))
    assert result["status"] == "invalid"
    assert result["negative_coverage"] == "UNKNOWN"


def test_incomplete_interval_never_proves_no_later_invalidation(tmp_path):
    path, binding, cursor = source(tmp_path, pair())
    events, _, _ = drain(binding, cursor)
    old_end = path.stat().st_size
    with path.open("ab") as stream:
        stream.write(wire(pair(output="contradiction")[1]))
    result = no.revalidate_observations(binding, tool_events(events), required_interval=(0, old_end))
    assert result["status"] == "current"
    assert result["interval"] == [0, old_end]
    assert result["negative_coverage"] == "UNKNOWN"
    assert result["covers_through_source_snapshot"] is False


def test_current_consumption_requires_interval_to_cover_selected_events(tmp_path):
    path, binding, cursor = source(tmp_path, pair())
    events, _, _ = drain(binding, cursor)
    result = no.revalidate_observations(binding, tool_events(events),
                                         required_interval=(path.stat().st_size, path.stat().st_size))
    assert result["status"] == "invalid"


def test_gap_between_call_result_prevents_affirmative_pair(tmp_path):
    path, binding, cursor = source(tmp_path, pair()[:1])
    with path.open("ab") as stream:
        stream.write(b'{broken}\n' + wire(pair()[1]))
    events, projection, _ = drain(binding, cursor)
    assert only_pair(projection)["status"] == "coverage_gap"
    assert no.revalidate_observations(binding, tool_events(events), projection=projection)["status"] == "invalid"


@pytest.mark.parametrize("mode", ["tamper", "truncate", "rotate"])
def test_source_changes_during_page_read_fail_closed(tmp_path, mode):
    path, binding, cursor = source(tmp_path, pair(output="ACTIVE"))
    original = path.read_bytes()
    original_open = Path.open
    changed = False

    class Reader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, length=-1):
            nonlocal changed
            data = self.stream.read(length)
            if not changed and length > binding["header_length"]:
                changed = True
                if mode == "rotate":
                    path.rename(tmp_path / "retained-original.jsonl")
                with original_open(path, "wb") as writer:
                    writer.write(original.replace(b"ACTIVE", b"PAUSED") if mode == "tamper"
                                 else original[:20] if mode == "truncate" else original)
            return data

    def opened(target, *args, **kwargs):
        value = original_open(target, *args, **kwargs)
        return Reader(value) if target == path and args and args[0] == "rb" else value

    with patch.object(Path, "open", opened):
        batch = no.read_page(binding, cursor)
    assert changed
    assert batch["cursor"] == cursor and not batch["events"]
    assert batch["diagnostics"]


def test_cached_partial_frame_tamper_is_rechecked_before_normalization(tmp_path):
    path, binding, cursor = source(tmp_path, pair(output="ACTIVE"))
    result_raw = wire(pair(output="ACTIVE")[1])
    before_last_byte = path.stat().st_size - 1
    first = no.read_page(binding, cursor, limits=no.Limits(page_bytes=before_last_byte))
    assert first["coverage"]["pending_bytes"] == len(result_raw) - 1
    old = path.stat()
    path.write_bytes(path.read_bytes().replace(b"ACTIVE", b"PAUSED"))
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    last = no.read_page(binding, first["cursor"])
    assert not last["events"]
    assert "between source pages" in last["gaps"][0]["detail"]


@pytest.mark.parametrize("tail,valid", [
    ('\\u00e9"}', True), ('\\"quoted\\""}', True), ('\\z"}', False),
    ('"}junk', False), ('","later":NaN}', False), ('","later":1e999}', False),
    ('","later":1,"later":2}', False),
])
def test_oversized_stream_validator_checks_the_suffix(tmp_path, tail, valid):
    path, binding, cursor = source(tmp_path, [])
    with path.open("ab") as stream:
        stream.write(b'{"large":"' + b"x" * 10000 + tail.encode() + b"\n")
    _, _, batches = drain(binding, cursor, no.Limits(page_bytes=1024, payload_bytes=512))
    gap = next(g for b in batches for g in b["gaps"])
    assert gap["code"] == "oversized_record"
    assert gap["json_valid"] is valid


def test_unicode_split_across_oversized_pages_is_valid(tmp_path):
    path, binding, cursor = source(tmp_path, [])
    with path.open("ab") as stream:
        stream.write(wire({"large": "é" * 10000}))
    _, _, batches = drain(binding, cursor, no.Limits(page_bytes=257, payload_bytes=256))
    assert next(g for b in batches for g in b["gaps"])["json_valid"] is True


def test_json_serialized_cursor_recovery_and_batch_replay(tmp_path):
    _, binding, cursor = source(tmp_path, pair(output="x" * 4000) + pair("after"))
    limits = no.Limits(page_bytes=512, payload_bytes=1024)
    projection = no.empty_projection()
    for _ in range(30):
        # This is the crash-before-commit seam: the same old cursor yields
        # exactly the same native identities, independent of ingestion time.
        batch = no.read_page(binding, cursor, limits=limits)
        repeated = no.read_page(binding, cursor, limits=limits)
        assert [e["event_id"] for e in batch["events"]] == [e["event_id"] for e in repeated["events"]]
        projection = no.reduce_observations(projection, batch)
        assert projection == no.reduce_observations(projection, batch)
        cursor = json.loads(json.dumps(batch["cursor"]))
        if not batch["coverage"]["backlog_bytes"]:
            break
    else:
        raise AssertionError("recovery stalled")
    assert any(p["status"] == "paired" for p in projection["pairs"].values())


def test_new_generation_never_joins_old_call_implicitly(tmp_path):
    path, binding, cursor = source(tmp_path, pair()[:1])
    _, projection, _ = drain(binding, cursor)
    path.rename(tmp_path / "retained.jsonl")
    path.write_bytes(wire(header()) + wire(pair()[1]))
    new_binding, new_cursor = no.enroll_source(path, client="codex", expected_root_session_id=ROOT)
    assert new_binding["generation"] != binding["generation"]
    projection = no.reduce_observations(projection, no.read_page(new_binding, new_cursor))
    assert only_pair(projection)["status"] == "unlinked_generations"


def test_native_sequence_gap_is_an_obligation(tmp_path):
    rows = pair()
    rows[0]["ordinal"], rows[1]["ordinal"] = 100, 102
    _, binding, cursor = source(tmp_path, rows)
    _, projection, batches = drain(binding, cursor)
    assert any(g["code"] == "native_sequence_gap" for b in batches for g in b["gaps"])
    assert only_pair(projection)["status"] == "coverage_gap"


@pytest.mark.parametrize('ordinals', [[1, 3], [2, 2], [2, 1], [True, 2]])
def test_current_interval_refuses_uningested_sequence_holes(tmp_path, ordinals):
    path, binding, cursor = source(tmp_path, pair())
    events, _, _ = drain(binding, cursor)
    with path.open('ab') as stream:
        for ordinal in ordinals:
            stream.write(wire({'type': 'event_msg', 'ordinal': ordinal,
                'payload': {'type': 'agent_message', 'message': 'Synthetic ordinary progress'}}))
    result = no.revalidate_observations(binding, tool_events(events), required_interval=(0, path.stat().st_size))
    assert result['status'] != 'current'
    assert result['negative_coverage'] == 'UNKNOWN'


def test_current_interval_accepts_exact_contiguous_sequence(tmp_path):
    rows = pair()
    rows[0]['ordinal'], rows[1]['ordinal'] = 101, 102
    path, binding, cursor = source(tmp_path, rows)
    events, _, _ = drain(binding, cursor)
    result = no.revalidate_observations(binding, tool_events(events), required_interval=(0, path.stat().st_size))
    assert result['status'] == 'current'
    assert result['negative_coverage'] == 'CURRENT_BOUNDED_INTERVAL'


def test_current_interval_checks_sequence_across_committed_frontier(tmp_path):
    rows = pair()
    rows[0]['ordinal'], rows[1]['ordinal'] = 5, 6
    path, binding, cursor = source(tmp_path, rows)
    events, _, batches = drain(binding, cursor)
    offset = path.stat().st_size
    with path.open('ab') as stream:
        stream.write(wire({'type': 'event_msg', 'ordinal': 8,
            'payload': {'type': 'agent_message', 'message': 'Synthetic continuation'}}))
    result = no.revalidate_observations(binding, [], required_interval=(offset, path.stat().st_size),
        prior_sequence=batches[-1]['cursor']['last_sequence'])
    assert result['status'] != 'current'
    assert any(item['code'] == 'native_sequence_gap' for item in result['diagnostics'])


def test_enrollment_at_current_boundary_discloses_earlier_unobserved_work(tmp_path):
    path, _, _ = source(tmp_path, pair("old"))
    start = path.stat().st_size
    with path.open("ab") as stream:
        stream.write(b"".join(wire(r) for r in pair("new")))
    binding, cursor = no.enroll_source(path, client="codex", expected_root_session_id=ROOT, start_offset=start)
    events, projection, batches = drain(binding, cursor)
    assert len(events) == 2 and only_pair(projection)["status"] == "paired"
    assert "work before enrollment" in batches[-1]["coverage"]["unobservable"]
    with pytest.raises(no.SourceError):
        no.enroll_source(path, client="codex", expected_root_session_id=ROOT, start_offset=start - 2)


def test_same_response_id_with_changed_usage_is_retained_conflict(tmp_path):
    changed = response_usage("same", 20)
    changed["payload"]["usage"] = tokens(11)
    _, binding, cursor = source(tmp_path, [response_usage("same", 10), changed])
    events, projection, _ = drain(binding, cursor)
    lane = next(iter(projection["usage"].values()))
    assert len(events) == 2
    assert lane["response_usage_sum"]["total_tokens"] == 10
    assert lane["reconciliation_required"] is True
    assert any(d["code"] == "conflicting_response_usage" for d in projection["diagnostics"])


def test_foreign_usage_thread_and_boolean_counters_are_gaps(tmp_path):
    row = response_usage("one", 10, CHILD)
    bad = usage(10)
    bad["payload"]["info"]["total_token_usage"]["total_tokens"] = True
    _, binding, cursor = source(tmp_path, [row, bad])
    events, _, batches = drain(binding, cursor)
    assert not events
    assert sum(len(b["gaps"]) for b in batches) == 2


def test_observation_capacity_failure_keeps_input_projection_unchanged(tmp_path):
    _, binding, cursor = source(tmp_path, pair())
    batch = no.read_page(binding, cursor)
    original = no.empty_projection()
    before = copy.deepcopy(original)
    with patch.object(no, "MAX_INDEX_ENTRIES", 1), pytest.raises(no.SourceError, match="capacity"):
        no.reduce_observations(original, batch)
    assert original == before


@pytest.mark.parametrize("change", [
    {"offset": True}, {"pending": "a" * 2000000}, {"offset": 40, "pending": ""}, {"generation": "wrong"},
])
def test_cursor_corruption_cannot_supply_unbounded_or_fabricated_bytes(tmp_path, change):
    _, binding, cursor = source(tmp_path, pair())
    cursor.update(change)
    with pytest.raises(no.SourceError):
        no.read_page(binding, cursor)


def test_binding_cache_cannot_change_source_identity_silently(tmp_path):
    _, binding, cursor = source(tmp_path, pair())
    binding["producer"]["thread_id"] = CHILD
    with pytest.raises(no.SourceError, match="binding"):
        no.read_page(binding, cursor)


def test_large_ignored_record_is_fully_validated_without_a_false_gap(tmp_path):
    rows = pair("across-large-ignored")
    rows[0]["ordinal"], rows[1]["ordinal"] = 1, 3
    filler = {"type": "event_msg", "ordinal": 2,
              "payload": {"text": "x" * 40000, "type": "agent_reasoning"}}
    path, binding, cursor = source(tmp_path, [rows[0], filler, rows[1]])
    events, projection, batches = drain(binding, cursor, no.Limits(page_bytes=1024, payload_bytes=512))
    assert not any(batch["gaps"] for batch in batches)
    assert len(events) == 2
    assert only_pair(projection)["status"] == "paired"
    assert batches[-1]["coverage"]["historically_ingested_through"] == path.stat().st_size
    assert all(len(json.dumps(batch["cursor"])) < 5000 for batch in batches)


@pytest.mark.parametrize("suffix", [
    b',"type":"tool_result"}',
    b',"session_id":null}',
    b',"thread_id":"synthetic-foreign"}',
    b',"bad":"\\z"}',
])
def test_large_ignored_projection_cannot_hide_ambiguous_suffix(tmp_path, suffix):
    path, binding, cursor = source(tmp_path, [])
    with path.open("ab") as stream:
        stream.write(b'{"type":"event_msg","payload":{"type":"agent_reasoning","text":"'
                     + b"x" * 10000 + b'"}' + suffix + b"\n")
    _, _, batches = drain(binding, cursor, no.Limits(page_bytes=1024, payload_bytes=512))
    assert any(batch["gaps"] for batch in batches)


def test_current_interval_exposes_cancellation_for_owning_policy(tmp_path):
    path, binding, cursor = source(tmp_path, pair())
    events, _, _ = drain(binding, cursor)
    with path.open("ab") as stream:
        stream.write(wire({"type": "event_msg", "payload": {"type": "turn_aborted", "turn_id": "synthetic-turn"}}))
    result = no.revalidate_observations(binding, tool_events(events), required_interval=(0, path.stat().st_size))
    assert result["negative_coverage"] == "CURRENT_BOUNDED_INTERVAL"
    assert result["invalidation_status"] == "owner_evaluation_required"
    assert any(event["kind"] == "lifecycle.cancelled" for event in result["interval_events"])


def test_native_ordinal_is_source_derived_at_consumption(tmp_path):
    rows = pair()
    rows[0]["ordinal"], rows[1]["ordinal"] = 18, 19
    _, binding, cursor = source(tmp_path, rows)
    events, _, _ = drain(binding, cursor)
    assert events[0]["native"]["ordinal"] == 18
    events[0]["native"]["ordinal"] = 99
    assert no.revalidate_observations(binding, events)["status"] == "invalid"


def test_actual_utf8_codepoint_split_in_large_frame(tmp_path):
    path, binding, cursor = source(tmp_path, [])
    with path.open("ab") as stream:
        stream.write(b'{"type":"event_msg","payload":{"type":"agent_reasoning","text":"'
                     + ("é" * 10000).encode("utf-8") + b'"}}\n')
    _, _, batches = drain(binding, cursor, no.Limits(page_bytes=257, payload_bytes=256))
    assert not any(batch["gaps"] for batch in batches)


def integration_response_usage(response_id, last, total):
    return {'type': 'token_usage_record', 'payload': {'thread_id': ROOT, 'session_id': ROOT,
        'response_id': response_id, 'turn_id': 'turn', 'root_turn_id': 'turn',
        'usage': {'input_tokens': last, 'output_tokens': 0, 'total_tokens': last},
        'thread_token_usage': {'input_tokens': total, 'output_tokens': 0, 'total_tokens': total},
        'turn_token_usage': {'input_tokens': total, 'output_tokens': 0, 'total_tokens': total}}}


def test_redelivered_response_with_later_cumulative_view_is_not_conflict(tmp_path):
    _, binding, cursor = source(tmp_path, [integration_response_usage('response', 10, 100),
                                          integration_response_usage('response', 10, 120)])
    events, projection, _ = drain(binding, cursor)
    lane = next(iter(projection['usage'].values()))
    assert len(events) == 2
    assert lane['reconciliation_required'] is False
    assert lane['response_usage_sum']['total_tokens'] == 10
    assert lane['latest']['total_tokens'] == 120


def test_claude_provisional_final_is_one_measurement(tmp_path):
    rows = []
    for final, output in [(False, 2), (True, 7675), (True, 7675)]:
        rows.append({'type': 'assistant', 'sessionId': ROOT, 'uuid': 'record-' + str(len(rows)),
            'message': {'id': 'response', 'role': 'assistant',
                        'content': [{'type': 'thinking', 'thinking': 'synthetic'}],
                        'stop_reason': 'tool_use' if final else None,
                        'usage': {'input_tokens': 2, 'cache_creation_input_tokens': 4147,
                                  'cache_read_input_tokens': 65828, 'output_tokens': output}}})
    path = tmp_path / 'claude.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    binding, cursor = no.enroll_source(path, client='claude', expected_root_session_id=ROOT)
    events, projection, batches = drain(binding, cursor)
    assert not any(batch['gaps'] for batch in batches)
    lane = next(iter(projection['usage'].values()))
    assert len([event for event in events if event['kind'] == 'usage.snapshot']) == 3
    assert lane['response_usage_sum']['output_tokens'] == 7675
    assert lane['reconciliation_required'] is False


def test_distinct_final_response_counters_stay_conflict(tmp_path):
    _, binding, cursor = source(tmp_path, [integration_response_usage('response', 10, 100),
                                          integration_response_usage('response', 11, 111)])
    _, projection, _ = drain(binding, cursor)
    lane = next(iter(projection['usage'].values()))
    assert lane['reconciliation_required'] is True
    assert lane['response_usage_sum']['total_tokens'] == 10

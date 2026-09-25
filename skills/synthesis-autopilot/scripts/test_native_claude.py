"""Synthetic Claude interactive/print-stream cases; no model execution."""
from copy import deepcopy
import unittest

import native_claude as adapter


ROOT = {"client": "claude", "thread_id": "session", "root_session_id": "session", "agent_id": None}
CHILD = {**ROOT, "thread_id": "worker", "agent_id": "worker", "parent_thread_id": "session"}


def message(final=False, output=2, producer=ROOT):
    return {"type": "assistant", "uuid": "record", "sessionId": "session",
        "agentId": producer.get("agent_id"), "isSidechain": bool(producer.get("agent_id")),
        "requestId": "request", "timestamp": "2026-01-01T00:00:00Z", "message": {
        "id": "message", "stop_reason": "tool_use" if final else None,
        "usage": {"input_tokens": 2, "output_tokens": output, "cache_creation_input_tokens": 4,
                  "cache_read_input_tokens": 20},
        "content": [{"type": "tool_use", "id": "call", "name": "Read", "input": {"path": "synthetic"}}]}}


def usage_fact(events):
    return next(item for item in events if item["kind"] == "usage.snapshot")


class ClaudeTests(unittest.TestCase):
    def test_child_qualification_requires_exact_native_agent(self):
        row = message(producer=CHILD)
        q = adapter.qualify_source(row, expected_root_session_id="session", expected_thread_id="worker", expected_agent_id="worker")
        self.assertEqual(q["thread_id"], "worker")
        self.assertFalse(q["root_authority"])
        for kwargs in ({"expected_thread_id": "session"}, {"expected_thread_id": "worker", "expected_agent_id": "other"}):
            with self.assertRaises(ValueError): adapter.qualify_source(row, expected_root_session_id="session", **kwargs)

    def test_provisional_and_final_have_one_measurement_identity(self):
        before = usage_fact(adapter.decode_record(message(), ROOT))
        after = usage_fact(adapter.decode_record(message(True, 7675), ROOT))
        self.assertEqual(before["data"]["measurement_id"], after["data"]["measurement_id"])
        self.assertEqual(before["data"]["phase"], "provisional")
        self.assertEqual(after["data"]["phase"], "final")
        self.assertFalse(before["data"]["countable"])
        self.assertTrue(after["data"]["countable"])

    def test_duplicate_and_conflicting_final_fragments(self):
        one = usage_fact(adapter.decode_record(message(True, 20), ROOT))["data"]
        copy = message(True, 20); copy["uuid"] = "another-fragment"
        duplicate = usage_fact(adapter.decode_record(copy, ROOT))["data"]
        conflict = usage_fact(adapter.decode_record(message(True, 21), ROOT))["data"]
        self.assertEqual(one["measurement_id"], duplicate["measurement_id"])
        self.assertEqual(one["counters_digest"], duplicate["counters_digest"])
        self.assertNotEqual(one["counters_digest"], conflict["counters_digest"])

    def test_child_scope_and_finality_remain_explicit(self):
        event = usage_fact(adapter.decode_record(message(True, producer=CHILD), CHILD))
        self.assertEqual(event["data"]["scope"]["thread_id"], "worker")
        self.assertEqual(event["data"]["scope_nonoverlap"], "UNKNOWN")
        with self.assertRaises(ValueError): adapter.decode_record(message(producer=CHILD), ROOT)

    def test_tool_result_error_is_not_task_failure_policy(self):
        row = {"type": "user", "uuid": "result", "sessionId": "session", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "call", "content": "Synthetic failure", "is_error": True}]}}
        event = adapter.decode_record(row, ROOT)[0]
        self.assertEqual(event["status"], "failed")
        self.assertEqual(event["native"]["call_id"], "call")
        self.assertNotIn("failure_family", event["data"])

    def test_interactive_and_print_stream_cannot_be_mixed(self):
        row = {"type": "result", "subtype": "success", "session_id": "session", "is_error": False, "result": "Synthetic result"}
        with self.assertRaises(ValueError): adapter.decode_record(row, ROOT)
        event = adapter.decode_wire(row, {"producer": ROOT, "dialect": "claude.print_stream", "mode": "synthetic"})[0]
        self.assertEqual(event["kind"], "lifecycle.completed")
        self.assertFalse(event["data"]["portable_completion"])

    def test_print_result_usage_is_aggregate_not_a_response(self):
        row = {"type": "result", "subtype": "success", "session_id": "session", "is_error": False,
               "usage": {"input_tokens": 10, "output_tokens": 3}}
        data = usage_fact(adapter.decode_wire(row, {"producer": ROOT, "dialect": "claude.print_stream"}))["data"]
        self.assertEqual(data["aggregation"], "turn_aggregate")
        self.assertIsNone(data["measurement_id"])

    def test_unknown_stop_reason_and_unobserved_goal_grammar(self):
        row = message(True); row["message"]["stop_reason"] = "future_reason"
        data = usage_fact(adapter.decode_record(row, ROOT))["data"]
        self.assertEqual(data["phase"], "unknown")
        self.assertFalse(data["countable"])
        with self.assertRaises(ValueError):
            adapter.decode_record({"type": "goal_met", "sessionId": "session"}, ROOT)

    def test_malformed_and_boolean_counter_rejected(self):
        row = message(); row["message"]["usage"]["output_tokens"] = True
        with self.assertRaises(ValueError): adapter.decode_record(row, ROOT)
        row = message(); row["message"]["content"][0]["id"] = None
        with self.assertRaises(ValueError): adapter.decode_record(row, ROOT)

    def test_requests_use_qualified_cron_tools_only(self):
        shape = adapter.request_shape("CronCreate", ROOT, {"cron": "*/5 * * * *", "prompt": "Synthetic", "recurring": True})
        self.assertFalse(shape["executable"])
        self.assertEqual(shape["transport"], "native_model_tool")
        for operation in ("GoalCreate", "ScheduleWakeup", "Monitor", "WorkflowLaunch"):
            with self.assertRaises(ValueError): adapter.request_shape(operation, ROOT, {})

    def test_print_init_is_observation_not_permission(self):
        row = {"type": "system", "subtype": "init", "session_id": "session", "tools": ["Read"]}
        event = adapter.decode_wire(row, {"producer": ROOT, "dialect": "claude.print_stream"})[0]
        self.assertEqual(event["authentication"], "owner_admission_required")
        self.assertFalse(event["data"]["grants_authority"])

    def test_inputs_not_mutated(self):
        row = message(); before = deepcopy(row)
        adapter.decode_record(row, ROOT)
        self.assertEqual(row, before)

    def test_user_text_and_tool_result_siblings_remain_distinct(self):
        row = {"type": "user", "uuid": "user-record", "sessionId": "session", "message": {"content": [
            {"type": "text", "text": "Cancel this synthetic task"},
            {"type": "tool_result", "tool_use_id": "call", "content": "Synthetic result"}]}}
        events = adapter.decode_record(row, ROOT)
        self.assertEqual([event["kind"] for event in events], ["message.user", "tool.result"])
        self.assertEqual([event["native"]["subrecord"] for event in events], [0, 1])
        self.assertFalse(events[0]["data"]["grants_authority"])
        self.assertFalse(events[0]["data"]["human_identity_proven"])

    def test_qualification_rejects_empty_requested_identity(self):
        with self.assertRaises(ValueError): adapter.qualify_source(message(), expected_root_session_id="session", expected_thread_id="")

    def test_print_assistant_cannot_smuggle_interactive_session_identity(self):
        row = message(True); row["session_id"] = "session"; row["sessionId"] = "other"
        with self.assertRaises(ValueError): adapter.decode_wire(row, {"producer": ROOT, "dialect": "claude.print_stream"})


if __name__ == "__main__": unittest.main()

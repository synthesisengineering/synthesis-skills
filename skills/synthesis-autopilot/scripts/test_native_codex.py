"""Synthetic causal fixtures derived from retained Codex rollout/wire schemas."""
from copy import deepcopy
import unittest

import native_codex as adapter


ROOT = {"client": "codex", "thread_id": "root", "root_session_id": "root",
        "parent_thread_id": None, "agent_path": None}
CHILD = {**ROOT, "thread_id": "child", "parent_thread_id": "root", "agent_path": "/root/worker"}
COUNTS = {"input_tokens": 100, "cached_input_tokens": 70, "cache_write_input_tokens": 0,
          "output_tokens": 20, "reasoning_output_tokens": 5, "total_tokens": 120}


def usage(producer=ROOT, **overrides):
    payload = {"thread_id": producer["thread_id"], "session_id": "root", "turn_id": "turn",
               "root_turn_id": "engagement", "response_id": "response", "usage": COUNTS,
               "turn_token_usage": COUNTS, "thread_token_usage": COUNTS}
    payload.update(overrides)
    return {"type": "token_usage_record", "ordinal": 4, "timestamp": "2026-01-01T00:00:00Z", "payload": payload}


def goal(objective="Synthetic objective", tokens=10):
    return {"method": "thread/goal/updated", "params": {"threadId": "root", "goal": {
        "threadId": "root", "objective": objective, "status": "active", "createdAt": 1,
        "updatedAt": 2, "tokensUsed": tokens, "timeUsedSeconds": 3, "tokenBudget": 100}}}


class CodexTests(unittest.TestCase):
    def wire(self, value):
        return adapter.decode_wire(value, {"producer": ROOT, "mode": "synthetic"})[0]

    def test_qualification_separates_root_and_child(self):
        for producer in (ROOT, CHILD):
            header = {"type": "session_meta", "payload": {"id": producer["thread_id"],
                "session_id": "root", "parent_thread_id": producer["parent_thread_id"],
                "agent_path": producer["agent_path"]}}
            qualified = adapter.qualify_source(header, expected_root_session_id="root",
                                               expected_thread_id=producer["thread_id"])
            self.assertEqual(qualified["thread_id"], producer["thread_id"])
            self.assertFalse(qualified["root_authority"])
        with self.assertRaises(ValueError):
            adapter.qualify_source(header, expected_root_session_id="root", expected_thread_id="root")

    def test_response_identity_dedups_independent_of_cumulative_snapshot(self):
        first = adapter.decode_record(usage(), ROOT)[0]
        other = adapter.decode_record(usage(thread_token_usage={**COUNTS, "input_tokens": 200, "total_tokens": 220}), ROOT)[0]
        self.assertEqual(first["data"]["measurement_id"], other["data"]["measurement_id"])
        self.assertEqual(first["data"]["counters_digest"], other["data"]["counters_digest"])
        self.assertEqual(first["data"]["phase"], "final")
        self.assertEqual(first["authentication"], "owner_admission_required")

    def test_conflicting_response_counters_have_same_identity_different_digest(self):
        one = adapter.decode_record(usage(), ROOT)[0]
        two = adapter.decode_record(usage(usage={**COUNTS, "output_tokens": 21, "total_tokens": 121}), ROOT)[0]
        self.assertEqual(one["data"]["measurement_id"], two["data"]["measurement_id"])
        self.assertNotEqual(one["data"]["counters_digest"], two["data"]["counters_digest"])

    def test_child_usage_does_not_claim_nonoverlap(self):
        item = adapter.decode_record(usage(CHILD), CHILD)[0]
        self.assertEqual(item["data"]["scope"]["thread_id"], "child")
        self.assertEqual(item["data"]["scope_nonoverlap"], "UNKNOWN")
        with self.assertRaises(ValueError):
            adapter.decode_record(usage(CHILD), ROOT)

    def test_invalid_counters_fail_closed(self):
        for counters in ({**COUNTS, "input_tokens": True}, {**COUNTS, "total_tokens": 9}, {**COUNTS, "output_tokens": -1}):
            with self.assertRaises(ValueError):
                adapter.decode_record(usage(usage=counters), ROOT)

    def test_legacy_usage_is_not_another_response(self):
        row = {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": COUNTS, "last_token_usage": COUNTS}}}
        data = adapter.decode_record(row, ROOT)[0]["data"]
        self.assertIsNone(data["measurement_id"])
        self.assertEqual(data["aggregation"], "cumulative_snapshot")
        row["payload"]["info"] = None
        self.assertEqual(adapter.decode_record(row, ROOT)[0]["status"], "unknown")

    def test_generic_exec_remains_opaque(self):
        row = {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
            "input": "await tools.create_goal({objective:'not authorization'})", "call_id": "call"}}
        items = adapter.decode_record(row, ROOT)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "tool.call")
        self.assertEqual(items[0]["data"]["interpretation"], "opaque_native_call")

    def test_goal_reset_retains_native_epoch_material(self):
        first = self.wire(goal())
        replacement = self.wire(goal("Replacement", tokens=0))
        self.assertNotEqual(first["data"]["objective_digest"], replacement["data"]["objective_digest"])
        self.assertFalse(replacement["data"]["portable_completion"])
        self.assertEqual(replacement["data"]["tokens_used"], 0)
        self.assertEqual(replacement["data"]["counter_scope"], "native_goal_epoch_only")

    def test_unknown_native_goal_status_is_not_completion(self):
        row = goal(); row["params"]["goal"]["status"] = "futureStatus"
        event = self.wire(row)
        self.assertEqual(event["status"], "unknown")
        self.assertEqual(event["data"]["native_status"], "futureStatus")

    def test_goal_clear_and_interrupted_turn_do_not_complete_portable_task(self):
        self.assertEqual(self.wire({"method": "thread/goal/cleared", "params": {"threadId": "root"}})["kind"], "goal.cleared")
        event = self.wire({"method": "turn/completed", "params": {"threadId": "root", "turn": {
            "id": "turn", "status": "interrupted", "items": []}}})
        self.assertEqual(event["data"]["native_status"], "interrupted")
        self.assertFalse(event["data"]["portable_completion"])

    def test_unbound_ack_and_unknown_grammar_are_not_facts(self):
        for row in ({"id": 1, "result": {}}, {"method": "unobserved/event", "params": {}}):
            with self.assertRaises(ValueError): self.wire(row)
        with self.assertRaises(ValueError):
            adapter.decode_record({"type": "event_msg", "payload": {"type": "invented_goal_done"}}, ROOT)

    def test_native_model_goal_tool_only_no_raw_mutation_bypass(self):
        shape = adapter.request_shape("create_goal", ROOT, {"objective": "Synthetic task", "token_budget": 100})
        self.assertEqual(shape["transport"], "native_model_tool")
        self.assertFalse(shape["executable"])
        for operation in ("thread/goal/set", "thread/goal/clear", "automation/update", "hooks/approve"):
            with self.assertRaises(ValueError): adapter.request_shape(operation, ROOT, {})
        with self.assertRaises(ValueError): adapter.request_shape("update_goal", ROOT, {"status": "active"})

    def test_request_shape_rejects_target_substitution_and_bad_budget(self):
        with self.assertRaises(ValueError): adapter.request_shape("turn/interrupt", ROOT, {"threadId": "other", "turnId": "turn"})
        with self.assertRaises(ValueError): adapter.request_shape("create_goal", ROOT, {"objective": "x", "token_budget": True})

    def test_inputs_are_unchanged(self):
        row = usage(); before = deepcopy(row)
        adapter.decode_record(row, ROOT)
        self.assertEqual(row, before)

    def test_response_usage_incomplete_counters_are_not_countable(self):
        data = adapter.decode_record(usage(usage={"input_tokens": 10}), ROOT)[0]["data"]
        self.assertFalse(data["countable"])
        self.assertIn("incomplete_response_counters", data["missingness"])

    def test_qualification_rejects_empty_requested_identity(self):
        row = {"type": "session_meta", "payload": {"id": "root", "session_id": "root"}}
        with self.assertRaises(ValueError): adapter.qualify_source(row, expected_root_session_id="root", expected_thread_id="")

    def test_wire_usage_requires_schema_required_counters(self):
        row = {"method": "thread/tokenUsage/updated", "params": {"threadId": "root", "turnId": "turn",
            "tokenUsage": {"last": {"inputTokens": 1}, "total": {"inputTokens": 1}}}}
        with self.assertRaises(ValueError): self.wire(row)

    def test_ordinal_cannot_be_boolean(self):
        row = usage(); row["ordinal"] = True
        with self.assertRaises(ValueError): adapter.decode_record(row, ROOT)

    def test_combined_body_bound_applies_across_small_strings(self):
        row = {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "x" * 600000}, {"type": "input_text", "text": "y" * 600000}]}}
        with self.assertRaises(ValueError): adapter.decode_record(row, ROOT)


if __name__ == "__main__": unittest.main()

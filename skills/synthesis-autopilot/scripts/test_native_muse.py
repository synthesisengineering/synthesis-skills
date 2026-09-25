"""Synthetic stable MSP cases. No host, model, native approval or Goal is run."""
from copy import deepcopy
import unittest

import native_muse as adapter


PRODUCER = {"client": "muse", "thread_id": "session", "root_session_id": "session"}
COMMAND_ID = "01900000-0000-7000-8000-000000000001"
SOURCE_RANGE = {"stream": {"kind": "session", "id": "session"},
                "first": {"id": "record", "sequence": 1}, "last": {"id": "record", "sequence": 1}}


def binding(**values):
    return {"producer": PRODUCER, "mode": "synthetic", "schema_fingerprint": adapter.STABLE_FINGERPRINT,
            "experimental_api": False, **values}


def notification(method, **values):
    return {"jsonrpc": "2.0", "method": method, "params": {
        "sessionId": "session", "viewCursor": "opaque:1", "sourceRange": SOURCE_RANGE, **values}}


def usage(**values):
    return notification("session/tokenUsage", turnId="turn", promptTokens=100, totalTokens=105,
        usage={"inputTokens": 100, "outputTokens": 5, "cachedTokens": 70, "reasoningTokens": 2},
        cumulative={"promptTokens": 200, "outputTokens": 10, "totalTokens": 210}, **values)


class MuseTests(unittest.TestCase):
    def decode(self, row, **values):
        return adapter.decode_wire(row, binding(**values))

    def test_stable_fingerprint_and_feature_gate(self):
        self.assertTrue(self.decode(usage()))
        for values in ({"schema_fingerprint": "other"}, {"experimental_api": True}):
            with self.assertRaises(ValueError): self.decode(usage(), **values)

    def test_usage_preserves_provider_raw_and_counted_once_values(self):
        data = self.decode(usage())[0]["data"]
        self.assertEqual(data["last"], {"prompt_tokens": 100, "output_tokens": 5, "total_tokens": 105})
        self.assertEqual(data["raw_usage"]["cachedTokens"], 70)
        self.assertEqual(data["scope_nonoverlap"], "UNKNOWN")
        self.assertEqual(data["child_usage_included"], False)
        self.assertEqual(data["aggregation"], "per_response")

    def test_duplicate_cursor_and_conflicting_usage_are_reconcilable(self):
        one = self.decode(usage())[0]["data"]
        other = usage(); other["params"]["totalTokens"] = 106; other["params"]["usage"]["outputTokens"] = 6
        two = self.decode(other)[0]["data"]
        self.assertEqual(one["measurement_id"], two["measurement_id"])
        self.assertNotEqual(one["counters_digest"], two["counters_digest"])

    def test_tool_completion_does_not_turn_failed_run_into_success(self):
        tool = self.decode(notification("item/completed", item={"itemId": "item", "kind": "toolCall",
            "revision": 2, "status": "completed", "callId": "call", "tool": "Read"}))[0]
        failed = self.decode(notification("turn/completed", turnId="turn", terminal="failed"))[0]
        self.assertEqual(tool["data"]["native_status"], "completed")
        self.assertEqual(failed["status"], "failed")
        self.assertFalse(tool["data"]["portable_completion"])

    def test_item_complete_without_start_and_reversed_revisions(self):
        old = notification("item/updated", item={"itemId": "item", "kind": "toolCall", "revision": 1, "status": "inProgress"})
        new = notification("item/completed", item={"itemId": "item", "kind": "toolCall", "revision": 2, "status": "completed"})
        results = [self.decode(x)[0] for x in (new, old)]
        self.assertEqual([x["data"]["revision"] for x in results], [2, 1])
        self.assertEqual(results[0]["data"]["replacement_key"], results[1]["data"]["replacement_key"])

    def test_unknown_item_status_is_terminal_unknown(self):
        event = self.decode(notification("item/completed", item={"itemId": "item", "kind": "futureKind",
            "revision": 3, "status": "futureStatus"}))[0]
        self.assertEqual(event["status"], "terminal_unknown")
        self.assertEqual(event["data"]["native_status"], "futureStatus")

    def test_goal_verbatim_percent_and_unknown_status_are_not_acceptance(self):
        item = self.decode(notification("session/goalChanged", goal={"objective": "Synthetic",
            "status": "futureStatus", "percentComplete": 130}))[0]
        self.assertEqual(item["data"]["percent_complete"], 130)
        self.assertEqual(item["status"], "unknown")
        self.assertFalse(item["data"]["portable_completion"])
        clear = self.decode(notification("session/goalChanged", goal=None))[0]
        self.assertEqual(clear["kind"], "goal.cleared")

    def test_goal_ack_requires_exact_request_and_is_admission_only(self):
        value = {"jsonrpc": "2.0", "id": 7, "result": {"commandId": "command", "status": "accepted", "turnId": "already-busy"}}
        request = {"id": 7, "method": "goal/set", "params": {"sessionId": "session", "commandId": "command", "objective": "Synthetic"}}
        event = self.decode(value, pending_request=request)[0]
        self.assertEqual(event["kind"], "command.acknowledged")
        self.assertFalse(event["data"]["delivery_proven"])
        self.assertFalse(event["data"]["portable_completion"])
        for bad in ({**request, "id": 8}, {**request, "params": {**request["params"], "commandId": "other"}}):
            with self.assertRaises(ValueError): self.decode(value, pending_request=bad)
        with self.assertRaises(ValueError): self.decode(value)

    def test_gap_requires_owner_reconciliation_no_cursor_sorting(self):
        row = {"jsonrpc": "2.0", "method": "view/gap", "params": {"sessionId": "session", "after": "z", "next": "a"}}
        event = self.decode(row)[0]
        self.assertEqual(event["kind"], "coverage.gap")
        self.assertEqual(event["data"]["after"], "z")
        self.assertEqual(event["data"]["next"], "a")
        self.assertFalse(event["data"]["coverage_complete"])

    def test_page_response_does_not_silently_close_gap(self):
        request = {"id": 2, "method": "view/page", "params": {"sessionId": "session", "cursor": "z", "limit": 10}}
        row = {"jsonrpc": "2.0", "id": 2, "result": {"events": [], "nextCursor": None}}
        event = self.decode(row, pending_request=request)[0]
        self.assertEqual(event["kind"], "coverage.page")
        self.assertFalse(event["data"]["gap_reconciled"])
        self.assertIsNone(event["data"]["next_cursor"])

    def test_incomplete_output_is_preserved(self):
        request = {"id": 1, "method": "item/readOutput", "params": {"sessionId": "session", "itemId": "item", "outputRef": "stored-output", "offsetBytes": 0, "lengthBytes": 100}}
        row = {"jsonrpc": "2.0", "id": 1, "result": {"byteLen": 3, "content": "abc", "encoding": "utf8", "eof": False,
            "mediaType": "text/plain", "offsetBytes": 0}}
        data = self.decode(row, pending_request=request)[0]["data"]
        self.assertFalse(data["complete"])
        self.assertEqual(data["next_offset"], 3)

    def test_native_approval_observation_cannot_grant_permission(self):
        row = notification("approval/resolved", approvalId="approval", itemId="item", turnId="turn",
            decision="approved", policyResult="allow", resolvedBy="user", stageEvidence=[])
        event = self.decode(row)[0]
        self.assertFalse(event["data"]["grants_authority"])
        with self.assertRaises(ValueError): adapter.request_shape("approval/decide", PRODUCER, {})

    def test_requests_preserve_distinct_cancellation_scopes(self):
        turn = adapter.request_shape("turn/interrupt", PRODUCER, {"turnId": "turn", "commandId": COMMAND_ID})
        tasks = adapter.request_shape("task/stopAll", PRODUCER, {"commandId": COMMAND_ID})
        self.assertEqual(turn["cancellation_scope"], "foreground_turn")
        self.assertEqual(tasks["cancellation_scope"], "background_tasks_excludes_subagents")
        self.assertFalse(turn["executable"])

    def test_request_cursor_is_observed_only_and_resume_is_not_read(self):
        with self.assertRaises(ValueError): adapter.request_shape("view/page", PRODUCER, {"cursor": "invented", "limit": 10})
        target = {**PRODUCER, "observed_cursors": ["opaque:1"]}
        request = adapter.request_shape("view/page", target, {"cursor": "opaque:1", "limit": 10})
        self.assertEqual(request["params"]["cursor"], "opaque:1")
        self.assertEqual(adapter.request_shape("session/read", PRODUCER, {})["effect"], "read")
        self.assertEqual(adapter.request_shape("session/resume", PRODUCER, {"commandId": COMMAND_ID})["effect"], "native_session_write")
        with self.assertRaises(ValueError): adapter.request_shape("turn/interrupt", PRODUCER, {"turnId": "turn"})

    def test_unknown_wire_grammar_and_wrong_session_rejected(self):
        row = usage(); row["params"]["sessionId"] = "other"
        with self.assertRaises(ValueError): self.decode(row)
        with self.assertRaises(ValueError): self.decode({"method": "invented/event", "params": {}})

    def test_boolean_revision_and_counter_rejected(self):
        with self.assertRaises(ValueError): self.decode(notification("item/completed", item={"itemId": "item", "kind": "toolCall", "revision": True, "status": "completed"}))
        row = usage(); row["params"]["promptTokens"] = True
        with self.assertRaises(ValueError): self.decode(row)

    def test_inputs_unchanged(self):
        row = usage(); before = deepcopy(row)
        self.decode(row)
        self.assertEqual(row, before)

    def test_child_control_has_exact_stable_actions_and_attempt(self):
        payload = {"commandId": COMMAND_ID, "workflowRunId": "workflow", "childId": "child", "attempt": 2}
        for action in ("skip", "retry"):
            result = adapter.request_shape("workflow/childControl", PRODUCER, {**payload, "action": action})
            self.assertEqual(result["params"]["attempt"], 2)
        for action in ("stop", "resume", "invented"):
            with self.assertRaises(ValueError): adapter.request_shape("workflow/childControl", PRODUCER, {**payload, "action": action})
        with self.assertRaises(ValueError): adapter.request_shape("workflow/childControl", PRODUCER, {**payload, "action": "retry", "attempt": 0})

    def test_last_output_range_does_not_prove_missing_prefix(self):
        request = {"id": 1, "method": "item/readOutput", "params": {"sessionId": "session", "itemId": "item", "outputRef": "ref", "offsetBytes": 10}}
        row = {"jsonrpc": "2.0", "id": 1, "result": {"byteLen": 3, "content": "abc", "encoding": "utf8", "eof": True,
            "mediaType": "text/plain", "offsetBytes": 10}}
        data = self.decode(row, pending_request=request)[0]["data"]
        self.assertTrue(data["range_eof"])
        self.assertFalse(data["complete"])
        self.assertIn("prior_output_ranges_not_supplied", data["missingness"])

    def test_retained_frame_and_unknown_raw_grammar_stay_gaps(self):
        with self.assertRaises(ValueError): adapter.decode_record({"retained_frame": {}}, PRODUCER)

    def test_raw_native_terminal_controls_preserve_failed_run(self):
        wrapper = {"schema_version": 1, "payload_schema_version": 1, "id": "record", "sequence": 2,
            "stream": {"kind": "session", "id": "session"}, "payload_type": "runtime.session",
            "payload": {"kind": "run", "run_id": "run", "event": {"kind": "terminal", "terminal": "failed"}}}
        event = adapter.decode_record(wrapper, PRODUCER)[0]
        self.assertEqual(event["status"], "failed")
        self.assertFalse(event["data"]["portable_completion"])
        self.assertFalse(adapter.qualify_source(wrapper, expected_root_session_id="session")["root_authority"])

    def test_malformed_approval_and_item_identity_are_gaps(self):
        row = notification("approval/resolved", approvalId="approval", itemId="item", turnId="turn",
                           decision=3, policyResult="allow", resolvedBy="user", stageEvidence=[])
        with self.assertRaises(ValueError): self.decode(row)
        row = notification("item/completed", item={"itemId": "item", "kind": "toolCall", "revision": 1,
                           "status": "completed", "callId": 123})
        with self.assertRaises(ValueError): self.decode(row)

    def test_delta_is_typed_text_and_envelope_cannot_mix_response(self):
        row = notification("item/delta", itemId="item", delta={"not": "text"})
        with self.assertRaises(ValueError): self.decode(row)
        row = usage(); row["result"] = {}
        with self.assertRaises(ValueError): self.decode(row)

    def test_cancel_optional_target_type_is_validated(self):
        with self.assertRaises(ValueError):
            adapter.request_shape("turn/interrupt", PRODUCER, {"commandId": COMMAND_ID, "turnId": 123})

    def test_page_cannot_exceed_requested_bound(self):
        request = {"id": 2, "method": "view/page", "params": {"sessionId": "session", "limit": 1}}
        one = notification("session/goalChanged", goal=None)
        event = {"method": one["method"], "params": one["params"]}
        row = {"jsonrpc": "2.0", "id": 2, "result": {"events": [event, event], "nextCursor": None}}
        with self.assertRaises(ValueError): self.decode(row, pending_request=request)

    def test_output_cannot_exceed_requested_bound(self):
        request = {"id": 1, "method": "item/readOutput", "params": {"sessionId": "session", "itemId": "item", "outputRef": "ref", "lengthBytes": 2}}
        row = {"jsonrpc": "2.0", "id": 1, "result": {"byteLen": 3, "content": "abc", "encoding": "utf8", "eof": True,
            "mediaType": "text/plain", "offsetBytes": 0}}
        with self.assertRaises(ValueError): self.decode(row, pending_request=request)

    def test_combined_wire_body_bound_and_experimental_fingerprint(self):
        row = notification("item/completed", item={"itemId": "item", "kind": "toolCall", "revision": 1,
            "status": "completed", "visibleOutput": "x" * 600000, "args": "y" * 600000})
        with self.assertRaises(ValueError): self.decode(row)
        with self.assertRaises(ValueError): self.decode(usage(), schema_fingerprint=adapter.DOCUMENTED_EXPERIMENTAL_FINGERPRINT)


if __name__ == "__main__": unittest.main()

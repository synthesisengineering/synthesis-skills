#!/usr/bin/env python3
"""Read native review provenance; never execute supplied code or decrypt bodies.

The bounded envelope is ``autopilot_review`` in both the native child prompt
and its structured result. It binds schema_version, kind, current run/contract/
profile, and registered artifact hashes. The result carries ``data``; the
request carries ``artifact_digests`` and ``producer``. The native tool/message
identity determines reviewer identity, rather than a caller's verified flag.

Claude Agent/Task pairs and Codex collaboration plaintext messages are accepted
grammars. Encrypted content, unsupported Muse records, truncated history and
ambiguous pairs mean unknown. Native provenance establishes who reported an
observation, not its correctness: domain acceptance remains a separate gate.
User authorizations use a distinct exact ``autopilot_authorization`` envelope.
No native message is sent by this module.
"""
from __future__ import annotations

import json
import hashlib
import os
import stat
from pathlib import Path
import re

MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024
REVIEW_KINDS = frozenset({"quality_observation", "quality_resolution", "child_integration"})
AUTHORIZATION_KINDS = frozenset({"profile-amendment", "contract-amendment", "wait-resolution", "authority",
                               "effect-authorization", "retry_clearance"})


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate native field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite native value")))


def _text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list) or not content:
        return None
    if any(not isinstance(item, dict) or item.get("type") not in {"text", "input_text", "output_text"}
           or not isinstance(item.get("text"), str) for item in content):
        return None  # Never infer text hidden in an encrypted block.
    return "".join(item["text"] for item in content)


def _envelope(content, key="autopilot_review"):
    if not isinstance(content, dict):
        text = _text(content)
        if text is None:
            return None
        # Collaboration displays a host-generated routing header before a
        # plaintext payload. Only its exact grammar is stripped.
        header = re.fullmatch(r"Message Type: (?:MESSAGE|FINAL_ANSWER)\nTask name: /[a-z0-9_/]+\nSender: /[a-z0-9_/]+\nPayload:\n([\s\S]+)", text)
        if header:
            text = header.group(1)
        content = _json(text)
    if not isinstance(content, dict) or set(content) != {key} or not isinstance(content[key], dict):
        return None
    return content[key]


def _records(path):
    """Read one bounded complete-line snapshot, permitting verified appends.

    Native runtimes append while their completed earlier events are being
    consumed. Growth does not invalidate those bytes: if metadata changed,
    reread the exact selected initial prefix and require equality. Replacement,
    truncation and changes inside the selected window remain unknown. This is
    a new snapshot for every call, never a cross-operation evidence cache.
    """
    path = Path(path)
    named = path.lstat()
    if not stat.S_ISREG(named.st_mode):
        raise ValueError("unsafe native transcript")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        identity = (before.st_dev, before.st_ino)
        if identity != (named.st_dev, named.st_ino) or not stat.S_ISREG(before.st_mode):
            raise ValueError("native transcript changed before bounded read")
        offset = max(0, before.st_size - MAX_TRANSCRIPT_BYTES)
        length = before.st_size - offset
        stream.seek(offset)
        raw = stream.read(length)
        after = os.fstat(stream.fileno())
        current = path.lstat()
        if (len(raw) != length or after.st_size < before.st_size
                or (current.st_dev, current.st_ino) != identity
                or not stat.S_ISREG(current.st_mode)):
            raise ValueError("native transcript was replaced or truncated")
        # Check even a same-size rewrite; native append is the only tolerated
        # mutation. The second read cannot incorporate any newly appended row.
        metadata = lambda info: (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if metadata(before) != metadata(after) or metadata(before) != metadata(current):
            stream.seek(offset)
            if stream.read(length) != raw:
                raise ValueError("native transcript selected bytes changed")
            final = os.fstat(stream.fileno())
            named_final = path.lstat()
            if (final.st_size < before.st_size or named_final.st_size < before.st_size
                    or (named_final.st_dev, named_final.st_ino) != identity
                    or not stat.S_ISREG(named_final.st_mode)):
                raise ValueError("native transcript was replaced or truncated")
    if offset:
        newline = raw.find(b"\n")
        raw = raw[newline + 1:] if newline >= 0 else b""
    # A writer may not have finished its newest line at the snapshot boundary.
    # Never parse or infer that partial event, even if the bytes form valid JSON.
    end = raw.rfind(b"\n")
    if end < 0:
        raise ValueError("native transcript has no complete bounded record")
    raw = raw[:end + 1]
    result = []
    for line in raw.splitlines():
        value = _json(line)
        if isinstance(value, dict):
            result.append(value)
    return result


def parse_codex_child(records, source):
    """Pure parser for authenticated Codex records; None is unknown."""
    try:
        if set(source) != {"kind", "call_id", "message_id"} or source["kind"] != "native-child":
            return None
        calls, messages = [], []
        for position, event in enumerate(records):
            if event.get("type") != "response_item" or not isinstance(event.get("payload"), dict):
                continue
            item = event["payload"]
            if item.get("type") == "function_call" and item.get("call_id") == source["call_id"]:
                calls.append((position, item))
            if item.get("type") == "agent_message" and item.get("id") == source["message_id"]:
                messages.append((position, item))
        if len(calls) != 1 or len(messages) != 1 or calls[0][0] >= messages[0][0]:
            return None
        call, message = calls[0][1], messages[0][1]
        if call.get("namespace") != "collaboration" or call.get("name") not in {"followup_task", "send_message", "spawn_agent"}:
            return None
        args = _json(call["arguments"])
        reviewer, recipient = message.get("author"), message.get("recipient")
        if not isinstance(reviewer, str) or not isinstance(recipient, str) or not reviewer.startswith(recipient + "/"):
            return None
        if call["name"] == "spawn_agent":
            if reviewer != recipient + "/" + args.get("task_name", ""):
                return None
        elif args.get("target") not in {reviewer, reviewer.removeprefix(recipient + "/")}:
            return None
        request = _envelope(args.get("message"))
        response = _envelope(message.get("content"))
        if request is None or response is None:
            return None
        return {"request": request, "response": response, "reviewer": reviewer}
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def parse_codex_dispatch(records, source):
    """Observe an acknowledged native dispatch, never grant child write rights."""
    try:
        if set(source) != {"kind", "call_id"} or source["kind"] != "native-dispatch":
            return None
        calls, results = [], []
        for position, event in enumerate(records):
            if event.get("type") != "response_item":
                continue
            item = event.get("payload", {})
            if item.get("call_id") != source["call_id"]:
                continue
            if item.get("type") == "function_call":
                calls.append((position, item))
            elif item.get("type") == "function_call_output":
                results.append((position, item))
        if len(calls) != 1 or len(results) != 1 or calls[0][0] >= results[0][0]:
            return None
        call, result = calls[0][1], results[0][1]
        if call.get("namespace") != "collaboration" or call.get("name") not in {"followup_task", "send_message"}:
            return None
        # These two native tools currently acknowledge successful dispatch
        # with an empty result. Any error/prose/new schema remains unknown.
        if result.get("output") != "":
            return None
        args = _json(call["arguments"])
        request = _envelope(args.get("message"), "autopilot_delegation")
        child = request.get("data", {}).get("child_id") if request else None
        if not isinstance(child, str) or not re.fullmatch(r"/root/[a-z0-9_/]+", child) or args.get("target") != child:
            return None
        return request
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def _claude_agent(records, source, native):
    if set(source) != {"kind", "call_id"} or source["kind"] != "native-agent":
        return None
    calls, results = [], []
    for position, event in enumerate(records):
        if event.get("sessionId") != native:
            continue
        content = event.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if event.get("type") == "assistant" and item.get("type") == "tool_use" and item.get("id") == source["call_id"]:
                calls.append((position, item))
            if event.get("type") == "user" and item.get("type") == "tool_result" and item.get("tool_use_id") == source["call_id"]:
                results.append((position, item))
    if len(calls) != 1 or len(results) != 1 or calls[0][0] >= results[0][0]:
        return None
    call, result = calls[0][1], results[0][1]
    if call.get("name") not in {"Agent", "Task"} or result.get("is_error"):
        return None
    request = _envelope(call.get("input", {}).get("prompt"))
    response = _envelope(result.get("content"))
    if request is None or response is None:
        return None
    return {"request": request, "response": response, "reviewer": "claude-agent:" + source["call_id"]}


def _muse_pair(records, call_id, native):
    calls, results = [], []
    for position, record in enumerate(records):
        if record.get("stream", {}).get("id") != native or record.get("record_type") != "event" or record.get("payload_type") != "runtime.session":
            continue
        payload = record.get("payload", {})
        if payload.get("kind") != "run":
            continue
        event = payload.get("event", {})
        if event.get("kind") == "assistant_tool_calls_committed":
            calls.extend((position, item) for item in event.get("tool_calls", []) if item.get("call_id") == call_id)
        if event.get("kind") == "tool_result_batch_committed":
            results.extend((position, item) for item in event.get("results", []) if item.get("tool_call_id") == call_id)
    if len(calls) != 1 or len(results) != 1 or calls[0][0] >= results[0][0]:
        return None
    call = calls[0][1]
    return {"name": call.get("name"), "args": _json(call["args"]), "result": _json(results[0][1]["text"]),
            "call_position": calls[0][0], "result_position": results[0][0]}


def parse_muse_review(records, source, native):
    """Current Muse committed native spawn/readback grammar, not shell output."""
    try:
        if set(source) != {"kind", "spawn_call_id", "result_call_id"} or source["kind"] != "native-muse-child":
            return None
        spawn = _muse_pair(records, source["spawn_call_id"], native)
        read = _muse_pair(records, source["result_call_id"], native)
        if not spawn or not read or spawn["name"] != "subagent_spawn" or read["name"] not in {"subagent_read_result", "subagent_wait"}:
            return None
        if spawn["result_position"] >= read["call_position"]:
            return None
        launched, completed = spawn["result"], read["result"]
        child = launched.get("subagent_id")
        initial = re.fullmatch(r"(task/[A-Za-z0-9_-]+)#([0-9]{1,12})", str(launched.get("task_ref", "")))
        final = re.fullmatch(r"(task/[A-Za-z0-9_-]+)#([0-9]{1,12})", str(completed.get("task_ref", "")))
        if (launched.get("status") != "accepted" or completed.get("status") != "ready" or not isinstance(child, str)
            or not initial or not final or initial[1] != final[1] or int(final[2]) < int(initial[2])
            or read["args"].get("subagent_id") != child or completed.get("subagent_id") != child):
            return None
        # Native task versions advance while the child executes, including
        # before its first wait result. A later parent instruction changes the
        # review experiment: it cannot reuse the original objective's proof.
        for record in records[spawn["result_position"] + 1:read["call_position"]]:
            if (record.get("stream", {}).get("id") != native or record.get("record_type") != "event"
                or record.get("payload_type") != "runtime.session" or record.get("payload", {}).get("kind") != "run"):
                continue
            event = record["payload"].get("event", {})
            if event.get("kind") != "assistant_tool_calls_committed":
                continue
            for call in event.get("tool_calls", []):
                if (str(call.get("name", "")).startswith("subagent_")
                    and call.get("name") not in {"subagent_read_result", "subagent_wait"}
                    and _json(call["args"]).get("subagent_id") == child):
                    return None
        request = _envelope(spawn["args"].get("objective"))
        response = _envelope(completed.get("summary"))
        if request is None or response is None:
            return None
        return {"request": request, "response": response, "reviewer": "muse-subagent:" + child}
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def _user(records, source, proof):
    if set(source) != {"kind", "message_id"} or source["kind"] != "native-user":
        return None
    matches = []
    for event in records:
        if proof["client"] == "claude":
            if event.get("type") == "user" and event.get("uuid") == source["message_id"] and event.get("sessionId") == proof["native_session_id"]:
                message = event.get("message", {})
                if message.get("role") == "user" and not event.get("isMeta"):
                    matches.append(_envelope(message.get("content"), "autopilot_authorization"))
        elif event.get("type") == "response_item":
            message = event.get("payload", {})
            if message.get("type") == "message" and message.get("role") == "user" and message.get("id") == source["message_id"]:
                matches.append(_envelope(message.get("content"), "autopilot_authorization"))
    return matches[0] if len(matches) == 1 else None


def parse_codex_question(records, source, title, approve_option):
    """Consume a native asynchronous UI reply; delivery is not approval."""
    try:
        if set(source) != {"kind", "call_id", "message_id", "question_index"} or source["kind"] != "native-question":
            return False
        index = source["question_index"]
        if type(index) is not int or index < 0:
            return False
        calls, acknowledgments, replies = [], [], []
        for position, event in enumerate(records):
            if event.get("type") != "response_item":
                continue
            item = event.get("payload", {})
            if item.get("call_id") == source["call_id"]:
                if item.get("type") == "function_call":
                    calls.append((position, item))
                elif item.get("type") == "function_call_output":
                    acknowledgments.append((position, item))
            if item.get("type") == "message" and item.get("id") == source["message_id"] and item.get("role") == "user":
                replies.append((position, item))
        if len(calls) != 1 or len(acknowledgments) != 1 or len(replies) != 1:
            return False
        call = calls[0][1]
        if call.get("name") != "request_user_input_async" or call.get("namespace") not in (None, "functions"):
            return False
        if not calls[0][0] < acknowledgments[0][0] < replies[0][0] or _json(acknowledgments[0][1]["output"]) != {"accepted": True}:
            return False
        question = _json(call["arguments"])["questions"][index]
        if question.get("title") != title or approve_option not in question.get("options", []):
            return False
        text = _text(replies[0][1].get("content"))
        match = re.fullmatch(r"<send_user_message_question_reply>\s*([\s\S]+?)\s*</send_user_message_question_reply>", text or "")
        if not match:
            return False
        answers = [row for row in _json(match.group(1)) if
                   _json(row.get("questionItemId", "null")) == ["request_user_input_async", source["call_id"], index]]
        return len(answers) == 1 and answers[0].get("question") == title and answers[0].get("answer") == approve_option
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return False


def _registered_json(context, artifact_id):
    from run_admission import safe_path
    record = context["artifacts"].get(artifact_id)
    if not isinstance(record, dict):
        raise ValueError("observation specification is not a current registered artifact")
    path = safe_path(Path(context["project"]) / record["path"], Path(context["project"]))
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("observation specification is missing or oversized")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record["digest"]:
        raise ValueError("observation specification changed")
    return _json(raw), record


def authorization_question(context, proposal_id):
    """Render ordinary UI choices from a prepared, registered review artifact.

    The user selects an option; no JSON reply or separate permission database
    is needed. The exact proposal bytes/run bindings appear in the native
    question, preventing retrospective attachment to a generic old approval.
    """
    proposal, artifact = _registered_json(context, proposal_id)
    expected = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    if (set(proposal) != {"schema_version", "kind", "bindings", "summary", "approve_option", "decline_option", "data"}
        or proposal["schema_version"] != 1 or proposal["kind"] not in AUTHORIZATION_KINDS
        or proposal["bindings"] != expected or not isinstance(proposal["data"], dict)):
        raise ValueError("authorization proposal does not bind this current run")
    if any(not isinstance(proposal[key], str) or not proposal[key].strip() for key in ("summary", "approve_option", "decline_option")):
        raise ValueError("authorization requires a readable proposal and explicit choices")
    if proposal["approve_option"] == proposal["decline_option"]:
        raise ValueError("authorization choices must differ")
    title = (proposal["summary"] + "\nReviewed proposal: " + str(Path(context["project"]) / artifact["path"]) +
             " (sha256 " + artifact["digest"] + ").\nRun " + expected["run_id"] +
             "; contract " + expected["contract_digest"] + "; profile " + expected["profile_digest"] + ".")
    return {"title": title, "options": [proposal["approve_option"], proposal["decline_option"]]}


def _calibration(data, context, request):
    """Derive calibration from blind controls; preserve an authentic failure."""
    if data.get("domain") not in {"writing", "research"}:
        return True
    calibration = data.get("calibration")
    if not isinstance(calibration, dict) or type(data.get("calibrated")) is not bool:
        return False
    fields = {"manifest_id", "manifest_digest", "reviewer", "rubric_artifact_id", "rubric_digest", "observations"}
    if set(calibration) != fields or calibration["reviewer"] != data.get("reviewer"):
        return False
    manifest, artifact = _registered_json(context, calibration["manifest_id"])
    if artifact["digest"] != calibration["manifest_digest"] or calibration["manifest_id"] in request["artifact_digests"]:
        return False  # The native request must not supply gold-label bytes.
    if (set(manifest) != {"schema_version", "domain", "rubric", "rubric_artifact_id", "rubric_digest", "controls"}
        or manifest["schema_version"] != 1 or manifest["domain"] != data.get("domain") or manifest["rubric"] != data.get("rubric")
        or manifest["rubric_artifact_id"] != calibration["rubric_artifact_id"] or manifest["rubric_digest"] != calibration["rubric_digest"]
        or request["artifact_digests"].get(manifest["rubric_artifact_id"]) != manifest["rubric_digest"]):
        return False
    controls, judgments = manifest["controls"], calibration["observations"]
    if not isinstance(controls, list) or not isinstance(judgments, list) or not 2 <= len(controls) <= 32 or len(judgments) != len(controls):
        return False
    expected = {}
    for row in controls:
        if (not isinstance(row, dict) or set(row) != {"artifact_id", "artifact_digest", "expected"}
            or row["artifact_id"] in expected or row["expected"] not in {"PASS", "FAIL"}
            or request["artifact_digests"].get(row["artifact_id"]) != row["artifact_digest"]):
            return False
        expected[row["artifact_id"]] = row
    if {row["expected"] for row in controls} != {"PASS", "FAIL"}:
        return False
    seen, matched = set(), True
    for row in judgments:
        if not isinstance(row, dict) or set(row) != {"artifact_id", "artifact_digest", "verdict"}:
            return False
        ident = row["artifact_id"]
        if ident in seen or ident not in expected or row["artifact_digest"] != expected[ident]["artifact_digest"] or row["verdict"] not in {"PASS", "FAIL"}:
            return False
        seen.add(ident)
        matched = matched and row["verdict"] == expected[ident]["expected"]
    return data["calibrated"] is matched


def verify_source(record, context):
    """Revalidate native source and exact current bindings; unknown is False."""
    try:
        from evidence_bridge import _fresh
        proof = _fresh(context)
        if proof["client"] not in {"claude", "codex", "muse"}:
            return False
        kind, data = record["kind"], record["data"]
        source = data.get("source")
        if not isinstance(source, dict):
            return False
        expected = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
        if any(record.get("bindings", {}).get(key) != value for key, value in expected.items()):
            return False
        if proof["client"] == "muse":
            from live_receipt import resolve_muse_transcript
            transcript = resolve_muse_transcript(proof["native_session_id"])
            if transcript is None:
                return False
        else:
            transcript = context["actor"]["native_payload"]["transcript_path"]
        records = _records(transcript)
        reported = {key: value for key, value in data.items() if key != "source"}
        if kind == "delegation":
            dispatch = parse_codex_dispatch(records, source) if proof["client"] == "codex" else None
            return bool(dispatch == {"schema_version": 1, "kind": kind, "bindings": expected, "data": reported}
                        and reported.get("mode") == "artifact-only"
                        and reported.get("integration_owner") == proof["session_uuid"])
        if kind in AUTHORIZATION_KINDS:
            if source.get("kind") == "native-question" and proof["client"] == "codex":
                proposal_id = source.get("proposal_id")
                proposal, _ = _registered_json(context, proposal_id)
                question = authorization_question(context, proposal_id)
                return bool(proposal["kind"] == kind and proposal["data"] == reported and
                    parse_codex_question(records, {key: value for key, value in source.items() if key != "proposal_id"},
                                         question["title"], question["options"][0]))
            authorization = _user(records, source, proof)
            return bool(authorization and authorization == {"schema_version": 1, "kind": kind,
                        "bindings": expected, "data": reported} and
                        (reported.get("approved") is True or (kind == "wait-resolution" and reported.get("resolved") is True)))
        if kind not in REVIEW_KINDS:
            return False
        observation = (_claude_agent(records, source, proof["native_session_id"]) if proof["client"] == "claude" else
                       parse_muse_review(records, source, proof["native_session_id"]) if proof["client"] == "muse" else
                       parse_codex_child(records, source))
        if observation is None:
            return False
        request, response = observation["request"], observation["response"]
        if response != {"schema_version": 1, "kind": kind, "bindings": expected, "data": reported}:
            return False
        if set(request) != {"schema_version", "kind", "bindings", "artifact_digests", "producer"}:
            return False
        if request["schema_version"] != 1 or request["kind"] != kind or request["bindings"] != expected:
            return False
        dependencies = request["artifact_digests"]
        if not isinstance(dependencies, dict) or not dependencies or any(
            context["artifacts"].get(key, {}).get("digest") != digest for key, digest in dependencies.items()):
            return False
        children = context["state"].get("extensions", {}).get("workflow", {}).get("children", {})
        producers = set()
        for child in children.values():
            if (kind == "child_integration" and child.get("child_id") == reported.get("child_id")) or (
                kind == "quality_observation" and reported.get("artifact_id") in child.get("artifact_ids", [])):
                producers.add(child["child_id"] if child.get("mode") == "artifact-only" else child.get("owner", {}).get("native_ref"))
        if not producers:
            producers.add(proof["native_ref"])
        if len(producers) != 1 or request["producer"] not in producers:
            return False
        if reported.get("reviewer") != observation["reviewer"] or reported.get("producer") != request["producer"]:
            return False
        if reported["reviewer"] == reported["producer"] or (kind == "quality_observation" and reported.get("independent") is not True):
            return False
        if kind == "quality_observation" and dependencies.get(reported.get("artifact_id")) != reported.get("artifact_digest"):
            return False
        return _calibration(reported, context, request) if kind == "quality_observation" else True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError):
        return False

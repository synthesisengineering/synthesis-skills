#!/usr/bin/env python3
"""Read-only evidence sources for autopilot's pure reducers.

Receipt files identify observations; they do not certify themselves. Local
facts are rederived through PM and content hashes. Native observations come
only from authenticated session transcripts and a fixed non-executing tool
vocabulary. A supported tool's response proves only its explicit result, never
future execution, model correctness, independent review, or action permission.
Unobservable claims return False, including any proposed generic attestation.
"""
from __future__ import annotations

from datetime import datetime
import copy
import hashlib
import json
import re
from pathlib import Path
import sys

PM = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))
from run_admission import admit_paths, safe_path, read_admission_observation

MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024
BINDING_KEYS = ("project_id", "project_root", "session_uuid", "native_ref",
                "claim_hash", "repository", "branch")
LOCAL_KINDS = ("project-resolution", "native-identity", "claim-ownership", "working-input")
# Explicit native interfaces only. Shell, exec, arbitrary code and pasted
# output are deliberately absent even if their output happens to be JSON.
NATIVE_TOOLS = frozenset({"CronCreate", "CronList", "CronDelete",
    "mcp__codex_app__automation_update", "mcp__codex_app__send_message_to_thread",
    "mcp__codex_app__read_thread", "mcp__codex_app__wait_threads"})
KINDS = LOCAL_KINDS + ("delivery", "recovery", "capability", "continuation-registration",
    "continuation-renewal", "continuation-wake", "continuation-cancellation", "quality_observation",
    "quality_resolution", "task_completion", "retry_clearance", "child_integration",
    "progress_observation", "effect-readback", "effect-authorization", "profile",
    "profile-amendment", "contract-amendment", "delegation", "wait-resolution", "authority", "consumer-check", "native_worker")


def _time(raw):
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("observation timestamp must be timezone-aware")
    return value.timestamp()


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate native JSON field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def _fresh(context):
    if "admission_observation" in context:
        return read_admission_observation(context)
    state, actor = context["state"], context["actor"]
    project = Path(context["project"]).absolute()
    targets = context["binding"].get("paths") or [str(project / "CONTEXT.md")]
    proof = admit_paths(Path(actor["board"]), state["project_id"], project,
        [Path(path) for path in targets], actor["native_payload"],
        expected_claim_hash=context["binding"]["claim_hash"], readonly=True)
    if any(proof.get(key) != context["binding"].get(key) for key in BINDING_KEYS):
        raise ValueError("native/project/claim observation changed")
    return proof


def observe_local(kind, context, *, artifact_id=None):
    """Return actual local facts; no mutation, issuance or network refresh."""
    proof = _fresh(context)
    if kind == "project-resolution":
        root = Path(proof["repository"])
        registry = safe_path(root / "projects/index.yaml", root)
        return {"project_id": proof["project_id"], "project_root": proof["project_root"],
                "registry_digest": hashlib.sha256(registry.read_bytes()).hexdigest()}
    if kind == "native-identity":
        return {"native_ref": proof["native_ref"], "session_uuid": proof["session_uuid"]}
    if kind == "claim-ownership":
        return {"claim_hash": proof["claim_hash"], "claims": sorted(proof["claims"])}
    if kind == "working-input":
        if not isinstance(artifact_id, str) or artifact_id not in context["artifacts"]:
            raise ValueError("working input is not a registered artifact")
        artifact = context["artifacts"][artifact_id]
        project = Path(proof["project_root"])
        path = safe_path(project / artifact["path"], project)
        if not path.is_file():
            raise ValueError("working input is unavailable")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != artifact["digest"]:
            raise ValueError("working input changed after registration")
        return {"artifact_id": artifact_id, "path": str(path.relative_to(project)), "digest": digest}
    raise ValueError("kind has no deterministic local observation")


def _result(raw):
    """Parse a structured native result without mining prose for JSON."""
    if isinstance(raw, str):
        raw = _json(raw)
    if isinstance(raw, dict) and raw.get("isError"):
        return None
    if isinstance(raw, dict) and isinstance(raw.get("structuredContent"), (dict, list)):
        return raw["structuredContent"]
    if isinstance(raw, list) and len(raw) == 1 and raw[0].get("type") == "text":
        return _result(raw[0].get("text"))
    if isinstance(raw, dict) and set(raw) <= {"content", "isError", "_meta"}:
        return _result(raw.get("content"))
    return raw if isinstance(raw, (dict, list)) else None


def _codex_native_call(item):
    """Recognize native calls and one literal wrapper without executing code."""
    if item.get("namespace") == "functions" and item.get("name") == "exec":
        raw = item.get("input") if item.get("type") == "custom_tool_call" else _json(item["arguments"]).get("code")
        if not isinstance(raw, str):
            return None
        matched = re.fullmatch(r"\s*text\(\s*await\s+tools\.(mcp__codex_app__\w+)\(\s*(\{.*\})\s*\)\s*\)\s*;?\s*", raw, re.DOTALL)
        if not matched or matched[1] not in NATIVE_TOOLS:
            return None
        arguments = _json(matched[2])
        return {"tool": matched[1], "arguments": arguments} if isinstance(arguments, dict) else None
    if item.get("namespace") == "mcp__codex_app" and item.get("type") == "function_call":
        name = item.get("name", "")
        tool = name if name.startswith("mcp__codex_app__") else "mcp__codex_app__" + name
        if tool in NATIVE_TOOLS:
            return {"tool": tool, "arguments": _json(item["arguments"])}
    return None


def _native_tool_index(records, proof, identities):
    """Pair selected calls/results in one already byte-bounded snapshot.

    A duplicate retains an invalid marker instead of accumulating unbounded
    candidates. Call and result positions come from these same snapshot bytes;
    a later read cannot silently change the negative-coverage interval.
    """
    if any(not isinstance(identity, str) or not identity or len(identity) > 512 for identity in identities):
        raise ValueError("invalid native call identity")
    calls, results = {}, {}
    def remember(target, identity, value):
        target[identity] = None if identity in target else value
    for position, event in enumerate(records):
        if proof["client"] == "claude":
            if event.get("sessionId") != proof["native_session_id"]:
                continue
            message = event.get("message", {})
            if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                continue
            content = message["content"]
            siblings = sum(isinstance(item, dict) and item.get("type") == "tool_result" for item in content)
            for item in content:
                if not isinstance(item, dict):
                    continue
                identity = item.get("id") if item.get("type") == "tool_use" else item.get("tool_use_id")
                if not isinstance(identity, str) or identity not in identities:
                    continue
                if event.get("type") == "assistant" and item.get("type") == "tool_use":
                    remember(calls, identity, {"tool": item.get("name"), "arguments": item.get("input"), "call_position": position})
                if event.get("type") == "user" and item.get("type") == "tool_result":
                    structured = event.get("toolUseResult", event.get("tool_use_result"))
                    raw = structured if structured is not None and siblings == 1 else item.get("content")
                    remember(results, identity, (None if item.get("is_error") else _result(raw), position, event.get("timestamp")))
        elif proof["client"] == "codex" and event.get("type") == "response_item":
            item = event.get("payload", {})
            identity = item.get("call_id")
            if not isinstance(identity, str) or identity not in identities:
                continue
            if item.get("type") in {"function_call", "custom_tool_call"}:
                call = _codex_native_call(item)
                remember(calls, identity, {**(call or {"tool": None, "arguments": None}), "call_position": position})
            elif item.get("type") in {"function_call_output", "custom_tool_call_output"}:
                remember(results, identity, (_result(item.get("output")), position, event.get("timestamp")))
    observations = {}
    for identity in identities:
        call, result = calls.get(identity), results.get(identity)
        if (call is None or result is None or call["tool"] not in NATIVE_TOOLS or result[0] is None
                or not isinstance(call["arguments"], dict) or call["call_position"] >= result[1]):
            observations[identity] = None
        else:
            observations[identity] = {**call, "result": result[0], "result_position": result[1], "call_id": identity,
                                      "native_ref": proof["native_ref"], "result_timestamp": result[2]}
    return observations


def native_tool_observation(context, call_id):
    """Read one unambiguous tool call/result from this authenticated session.

    Reads are bounded. A missing record in this window means unknown, not that
    the tool never ran. Muse lacks an accepted result grammar here and remains
    unknown; its native Stop conformance is a separate evidence plane.
    """
    try:
        if not isinstance(call_id, str) or not call_id or len(call_id) > 512:
            return None
        proof = _fresh(context)
        if proof["client"] not in {"claude", "codex"}:
            return None
        path = Path(context["actor"]["native_payload"]["transcript_path"])
        from native_review import _records
        records = _records(path)
        return _native_tool_index(records, proof, {call_id})[call_id]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def _recent_native(observation, context, *, after=None):
    if not observation or not isinstance(observation.get("result_timestamp"), str):
        return False
    try:
        observed = _time(observation["result_timestamp"])
        now = _time(context["now"])
        return 0 <= now - observed <= 300 and (after is None or observed > _time(after))
    except (ValueError, TypeError, AttributeError):
        return False


def _continuation_prompt(raw, context):
    prompt = _json(raw)
    body = prompt.get("autopilot_continuation") if isinstance(prompt, dict) and set(prompt) == {"autopilot_continuation"} else None
    required = {"schema_version", "bindings"}
    optional = {"role", "generation", "worker_job_id"}
    if (not isinstance(body, dict) or not required <= set(body) or set(body) - required - optional
            or body["schema_version"] != 1 or body["bindings"] != {
                key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}):
        raise ValueError("native continuation prompt does not bind this run")
    if "role" in body:
        if body["role"] not in {"worker", "backstop"} or not isinstance(body.get("generation"), str) or not body["generation"]:
            raise ValueError("native continuation role/generation is invalid")
        if (body["role"] == "backstop") != (isinstance(body.get("worker_job_id"), str) and bool(body["worker_job_id"])):
            raise ValueError("backstop must identify its distinct worker job")
    elif optional & set(body):
        raise ValueError("native continuation role is required")
    return body


def _schedule_deadline(schedule, observed_at):
    """Control-plane late boundary, not a host-reported future execution time.

    Claude documents recurring jitter <= half the interval, capped at 30 min:
    https://code.claude.com/docs/en/scheduled-tasks#jitter. The supported minute
    steps divide an hour and use the observer host's local minute slots, as
    required by this local native facility. Busy-session delay
    remains unbounded: crossing this boundary means overdue, never guaranteed.
    """
    match = re.fullmatch(r"(\*|\*/([1-9][0-9]?)) \* \* \* \*", schedule)
    step = 1 if match and match[1] == "*" else int(match[2]) if match else 0
    if step < 1 or step > 30 or 60 % step:
        raise ValueError("native schedule has no supported deadline computation")
    interval = step * 60
    observed = _time(observed_at)
    offset = datetime.fromtimestamp(observed).astimezone().utcoffset().total_seconds()
    nominal = (int(observed + offset) // interval + 1) * interval - offset
    jitter = min(1800, interval / 2)
    return {"kind": "control-plane-derived", "schedule": schedule,
            "nominal_at": nominal, "maximum_jitter_seconds": jitter,
            "late_after": nominal + jitter, "basis_observed_at": observed_at,
            "timezone_basis": "observer-host-local", "utc_offset_seconds": offset,
            "documented_source": "https://code.claude.com/docs/en/scheduled-tasks#jitter",
            "scope": "same-session-turn-end", "busy_session_delay_bounded": False}


def observe_native_registration(context, create_call_id, readback_call_id, *, capability_receipt=None, monitor_create_call_id=None):
    """Prove native registration only; scheduling is not a future wake proof."""
    created = native_tool_observation(context, create_call_id)
    listed = native_tool_observation(context, readback_call_id)
    if not created or not listed or created["tool"] != "CronCreate" or listed["tool"] != "CronList" or created["result_position"] >= listed["call_position"]:
        raise ValueError("native registration requires ordered create and readback")
    if not _recent_native(listed, context):
        raise ValueError("native registration readback is stale or has no host timestamp")
    args, result = created["arguments"], created["result"]
    if not isinstance(result, dict) or not isinstance(result.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9]{8}", result["id"]):
        raise ValueError("native registration has no accepted job identity")
    job_id = result["id"]
    jobs = listed["result"].get("jobs") if isinstance(listed["result"], dict) else listed["result"]
    if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
        raise ValueError("native registration list is not complete structured output")
    matches = [job for job in jobs if job.get("id") == job_id]
    if len(matches) != 1 or any(matches[0].get(key) != args.get(key) for key in ("cron", "prompt")):
        raise ValueError("native registration readback differs from the requested job")
    # Current native CronList omits recurrence; CronCreate's paired structured
    # result carries it. A list that explicitly supplies it must agree too.
    observed_recurring = result.get("recurring", matches[0].get("recurring"))
    if type(observed_recurring) is not bool or observed_recurring != args.get("recurring") or (
            "recurring" in matches[0] and matches[0]["recurring"] != observed_recurring):
        raise ValueError("native recurrence differs from the requested job")
    body = _continuation_prompt(args["prompt"], context)
    if not isinstance(args.get("cron"), str) or type(args.get("recurring")) is not bool:
        raise ValueError("native registration does not bind this run and schedule")
    data = {"source": {"kind": "native-tool", "call_id": create_call_id, "readback_call_id": readback_call_id},
            "surface": "claude-code-cli", "mechanism": "claude-session-cron", "job_id": job_id,
            "schedule": args["cron"], "recurring": args["recurring"], "registration_status": "observed",
            "wake_status": "unknown", "survival": []}
    if capability_receipt is not None:
        bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
        if not context["verify_receipt"](capability_receipt, "capability", bindings):
            raise ValueError("continuation requires current observed facility capability")
        capability = context["evidence"][capability_receipt]["data"]
        current_monitor = observe_native_registration(context, monitor_create_call_id, readback_call_id)
        monitor_call = native_tool_observation(context, monitor_create_call_id)
        monitor_body = _continuation_prompt(monitor_call["arguments"]["prompt"], context)
        monitor_id = current_monitor["job_id"]
        if (not args["recurring"] or body.get("role") != "worker"
                or capability["capabilities"].get("survival") != ["turn_end"]
                or monitor_id == job_id or not current_monitor["recurring"]
                or monitor_body.get("role") != "backstop" or monitor_body.get("worker_job_id") != job_id
                or sum(job.get("id") == monitor_id for job in jobs) != 1):
            raise ValueError("current worker and independent backstop are not both registered")
        # A fresh-looking earlier list cannot override later native cancellation
        # or a complete list showing either member of the current pair missing.
        # Timestamps gate affirmative freshness, not later invalidation. A
        # missing or skewed clock cannot hide an authenticated cancellation.
        for later in _native_observations(context, fresh_only=False, after_observation=listed):
            if later["call_position"] <= listed["result_position"]:
                continue
            if later["tool"] == "CronDelete" and later["arguments"].get("id") in {job_id, monitor_id}:
                raise ValueError("native continuation pair was subsequently cancelled")
            if later["tool"] == "CronList":
                later_jobs = later["result"].get("jobs") if isinstance(later["result"], dict) else later["result"]
                if not isinstance(later_jobs, list) or not {job_id, monitor_id} <= {job.get("id") for job in later_jobs if isinstance(job, dict)}:
                    raise ValueError("native continuation pair no longer appears in current readback")
        deadline = _schedule_deadline(args["cron"], listed["result_timestamp"])
        lease = min(_time(context["evidence"][capability_receipt]["expires_at"]),
                    _time(listed["result_timestamp"]) + 300)
        # Registration remains historical proof through its unchanged lease;
        # later genuine wakes supersede the initial next-wake boundary. Fresh
        # admission still requires a future first deadline in the reducer.
        if not deadline["late_after"] < lease or _time(context["now"]) >= lease:
            raise ValueError("observed schedule exceeds the current control-plane lease")
        data["source"]["capability_receipt"] = capability_receipt
        data["source"]["monitor_create_call_id"] = monitor_create_call_id
        data.update(owner=_fresh(context)["native_ref"], observer_id="native-job:" + monitor_id,
                    next_wake_at=deadline["late_after"], lease_expires_at=lease,
                    deadline_provenance=deadline, lease_provenance="control-plane-five-minute-maximum",
                    survival=["turn_end"])
    return data


def observe_native_renewal(context, readback_call_id, previous_lease_receipt):
    """Read the same pair again without adopting another job or reviving expiry."""
    bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    previous = context["evidence"].get(previous_lease_receipt)
    if (not previous or previous["kind"] not in {"continuation-registration", "continuation-renewal"}
            or not context["verify_receipt"](previous_lease_receipt, previous["kind"], bindings)):
        raise ValueError("renewal requires its admitted previous native lease")
    prior = previous["data"]
    if _time(context["now"]) >= prior["lease_expires_at"]:
        raise ValueError("expired continuation cannot be renewed")
    original_ref = prior.get("registration_receipt", previous_lease_receipt)
    original = context["evidence"].get(original_ref)
    if (not original or original["kind"] != "continuation-registration"
            or not context["verify_receipt"](original_ref, "continuation-registration", bindings)):
        raise ValueError("renewal lost its original native registration")
    source = original["data"]["source"]
    data = observe_native_registration(context, source["call_id"], readback_call_id,
        capability_receipt=source["capability_receipt"], monitor_create_call_id=source["monitor_create_call_id"])
    data["lease_expires_at"] = min(data["lease_expires_at"], _time(original["expires_at"]), _time(previous["expires_at"]))
    listed = native_tool_observation(context, readback_call_id)
    if (_time(listed["result_timestamp"]) <= _time(previous["observed_at"])
            or data["lease_expires_at"] <= prior["lease_expires_at"]
            or any(data[key] != prior[key] for key in ("job_id", "surface", "mechanism", "owner", "observer_id"))):
        raise ValueError("renewal needs a newer readback of the same native pair")
    data.update(source={"kind": "native-renewal", "readback_call_id": readback_call_id,
                       "previous_lease_receipt": previous_lease_receipt},
        registration_receipt=original_ref, previous_lease_receipt=previous_lease_receipt,
        readback_at=listed["result_timestamp"])
    return data


def observe_native_wake(context, create_call_id, readback_call_id, event_id, *, registration_receipt=None, lease_receipt=None):
    """Bind the observed native queued prompt to one uniquely registered job."""
    from native_review import _records
    registration = observe_native_registration(context, create_call_id, readback_call_id)
    proof = _fresh(context)
    if proof["client"] != "claude":
        raise ValueError("native wake grammar has not been observed for this client")
    created = native_tool_observation(context, create_call_id)
    listed = native_tool_observation(context, readback_call_id)
    prompt = created["arguments"]["prompt"]
    records = _records(context["actor"]["native_payload"]["transcript_path"])
    creations, wakes, queues = [], [], []
    for position, event in enumerate(records):
        if event.get("sessionId") != proof["native_session_id"]:
            continue
        message = event.get("message", {})
        if event.get("type") == "assistant" and isinstance(message, dict) and isinstance(message.get("content"), list):
            creations.extend(item.get("id") for item in message["content"] if isinstance(item, dict)
                and item.get("type") == "tool_use" and item.get("name") == "CronCreate"
                and item.get("input", {}).get("prompt") == prompt)
        if event.get("type") == "queue-operation" and event.get("operation") == "enqueue" and event.get("content") == prompt:
            queues.append((position, event))
        if event.get("type") == "user" and event.get("uuid") == event_id:
            wakes.append((position, event))
    if creations != [create_call_id] or len(wakes) != 1:
        raise ValueError("wake prompt is not uniquely bound to this native job")
    position, event = wakes[0]
    if (event.get("isMeta") is not True or event.get("queueSkipAttachments") is not True
            or event.get("promptSource") != "sdk" or not isinstance(event.get("promptId"), str)
            or event.get("message", {}).get("role") != "user" or event["message"].get("content") != prompt
            or position <= listed["result_position"]
            or not _recent_native({"result_timestamp": event.get("timestamp")}, context)):
        raise ValueError("event is not an observed native scheduler prompt")
    preceding = [(index, queued) for index, queued in queues if listed["result_position"] < index < position]
    if not preceding or not _time(listed["result_timestamp"]) <= _time(preceding[-1][1]["timestamp"]) <= _time(event["timestamp"]):
        raise ValueError("wake lacks its ordered native enqueue")
    data = {"source": {"kind": "native-scheduler", "create_call_id": create_call_id,
                "readback_call_id": readback_call_id, "event_id": event_id},
            "job_id": registration["job_id"], "event_id": event_id, "native_observed_at": event["timestamp"],
            "next_wake_status": "unknown", "one_shot": not registration["recurring"]}
    if registration_receipt is not None:
        bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
        if not context["verify_receipt"](registration_receipt, "continuation-registration", bindings):
            raise ValueError("wake requires current admitted native registration")
        admitted = context["evidence"][registration_receipt]["data"]
        if admitted["job_id"] != registration["job_id"] or not registration["recurring"]:
            raise ValueError("wake belongs to another continuation registration")
        if lease_receipt is not None and lease_receipt != registration_receipt:
            if not context["verify_receipt"](lease_receipt, "continuation-renewal", bindings):
                raise ValueError("wake requires a verified current renewal")
            admitted = context["evidence"][lease_receipt]["data"]
            if admitted["registration_receipt"] != registration_receipt or admitted["job_id"] != registration["job_id"]:
                raise ValueError("renewed wake changed its original registration")
        deadline = _schedule_deadline(registration["schedule"], event["timestamp"])
        if deadline["late_after"] >= admitted["lease_expires_at"]:
            raise ValueError("next wake falls beyond the current control-plane lease")
        data["source"]["registration_receipt"] = registration_receipt
        if lease_receipt is not None:
            data["source"]["lease_receipt"] = lease_receipt
        data.update(next_wake_at=deadline["late_after"], next_wake_status="control-plane-derived",
                    deadline_provenance=deadline)
    return data


def observe_native_capability(context, arguments):
    basic = {"create_call_id", "readback_call_id"}
    full = basic | {"wake_event_id", "monitor_create_call_id", "monitor_readback_call_id",
                    "monitor_wake_event_id", "monitor_check_call_id", "cancellation_call_id",
                    "cancellation_readback_call_id"}
    if set(arguments) not in (basic, full):
        raise ValueError("capability components require exact native observations")
    registration = observe_native_registration(context, arguments["create_call_id"], arguments["readback_call_id"])
    data = {"source": {"kind": "native-components", **arguments}, "surface": registration["surface"],
            "capabilities": {"native_identity": True, "registration_readback": True,
                "wake_observation": False, "cancellation_readback": False, "independent_observer": False,
                "survival": [], "mechanisms": [registration["mechanism"]]},
            "unknown": ["wake_observation", "cancellation_readback", "independent_observer", "survival"]}
    if set(arguments) == basic:
        return data
    from native_review import _records
    worker = observe_native_wake(context, arguments["create_call_id"], arguments["readback_call_id"], arguments["wake_event_id"])
    monitor = observe_native_registration(context, arguments["monitor_create_call_id"], arguments["monitor_readback_call_id"])
    monitoring = observe_native_wake(context, arguments["monitor_create_call_id"], arguments["monitor_readback_call_id"], arguments["monitor_wake_event_id"])
    worker_call = native_tool_observation(context, arguments["create_call_id"])
    monitor_call = native_tool_observation(context, arguments["monitor_create_call_id"])
    body = _continuation_prompt(monitor_call["arguments"]["prompt"], context)
    if (monitor["job_id"] == worker["job_id"] or body.get("role") != "backstop"
            or body.get("worker_job_id") != worker["job_id"] or not registration["recurring"]
            or not monitor["recurring"]):
        raise ValueError("backstop is not a distinct recurring monitor for this worker")
    deadline = _schedule_deadline(registration["schedule"], worker["native_observed_at"])
    if _time(monitoring["native_observed_at"]) <= deadline["late_after"]:
        raise ValueError("backstop has not observed an overdue worker interval")
    checked = native_tool_observation(context, arguments["monitor_check_call_id"])
    cancelled = native_tool_observation(context, arguments["cancellation_call_id"])
    readback = native_tool_observation(context, arguments["cancellation_readback_call_id"])
    if (not _recent_native(checked, context, after=monitoring["native_observed_at"])
            or checked["tool"] != "CronList" or not cancelled or cancelled["tool"] != "CronDelete"
            or cancelled["arguments"].get("id") != worker["job_id"]
            or (isinstance(cancelled["result"], dict) and cancelled["result"].get("deleted", True) is not True)
            or not _recent_native(readback, context) or readback["tool"] != "CronList"
            or cancelled["result_position"] >= readback["call_position"]):
        raise ValueError("monitor check or cancellation readback is not native and ordered")
    for observation in (checked, readback):
        jobs = observation["result"].get("jobs") if isinstance(observation["result"], dict) else observation["result"]
        if (not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs)
                or any(job.get("id") == worker["job_id"] for job in jobs)
                or sum(job.get("id") == monitor["job_id"] for job in jobs) != 1):
            raise ValueError("positive monitor listing does not establish worker absence")
    records = _records(context["actor"]["native_payload"]["transcript_path"])
    session = _fresh(context)["native_session_id"]
    prompt = worker_call["arguments"]["prompt"]
    window = [event for event in records if event.get("sessionId") == session
              and event.get("type") == "user" and event.get("isMeta") is True
              and event.get("message", {}).get("content") == prompt
              and isinstance(event.get("timestamp"), str)
              and _time(worker["native_observed_at"]) < _time(event["timestamp"]) <= _time(monitoring["native_observed_at"])]
    if window:
        raise ValueError("worker did wake in the supposed missing interval")
    data["capabilities"].update(wake_observation=True, cancellation_readback=True,
        independent_observer=True, survival=["turn_end"])
    data["unknown"] = ["process_death", "app_exit", "logout", "reboot", "offline", "machine_transfer"]
    data["backstop"] = {"status": "missed", "worker_job_id": worker["job_id"],
        "observer_job_id": monitor["job_id"], "worker_wake": worker["native_observed_at"],
        "observed_at": checked["result_timestamp"], "deadline_provenance": deadline,
        "independence_scope": "distinct-native-job-same-session", "shared_failure_domain": "native-session"}
    return data


def _delivery(data, context, record=None):
    source = data.get("source")
    if not isinstance(source, dict) or set(source) != {"kind", "call_id"} or source["kind"] != "native-tool":
        return False
    observation = native_tool_observation(context, source["call_id"])
    accepted_at = context["now"]
    saved = context["state"].get("extensions", {}).get("capabilities", {}).get("deliveries", {}).get(data.get("delivery_id"), {})
    if (record and saved.get("receipt") == record.get("id")
            and saved.get("receipt_digest") == record.get("digest")
            and saved.get("observed_at") == record.get("observed_at")
            and saved.get("recorded_at")):
        # A delivered message remains a past fact. Only the identical receipt
        # previously admitted by the reducer may reuse its trusted intake time;
        # new or substituted envelopes still require a recent native result.
        accepted_at = saved["recorded_at"]
        if _time(accepted_at) > _time(context["now"]):
            return False
    if not _recent_native(observation, {"now": accepted_at}) or observation["tool"] != "mcp__codex_app__send_message_to_thread":
        return False
    args, result = observation["arguments"], observation["result"]
    if not isinstance(result, dict) or context["state"]["run_id"] not in str(args.get("prompt", "")):
        return False
    # No inferred acceptance/notification from a created or queued request.
    status = result.get("status")
    if status not in {"queued", "delivered", "acknowledged", "failed", "unknown", "suppressed"}:
        return False
    if result.get("threadId") != args.get("threadId") or not args.get("threadId"):
        return False
    expected = {"source": source, "delivery_id": source["call_id"], "channel": "codex-task", "status": status}
    wait_fields = {"wait_ids", "wait_digest", "run_revision"}
    if wait_fields & data.keys():
        from capabilities import wait_binding
        binding = wait_binding(context["state"])
        prompt = _json(args["prompt"])
        if not isinstance(prompt, dict) or prompt.get("run_id") != context["state"]["run_id"]:
            return False
        if any(prompt.get(key) != data.get(key) for key in wait_fields):
            return False
        if data.get("wait_ids") != binding["wait_ids"] or data.get("wait_digest") != binding["wait_digest"]:
            return False
        if type(data.get("run_revision")) is not int or data["run_revision"] > binding["run_revision"]:
            return False
        expected.update({key: data[key] for key in wait_fields})
    return data == expected


def _current_artifacts(context, ids):
    project = Path(context["project"])
    result = {}
    for key in sorted(ids):
        artifact = context["artifacts"][key]
        path = safe_path(project / artifact["path"], project)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if artifact["digest"] != digest:
            raise ValueError("registered observation input changed")
        result[key] = digest
    return result


def observe_workflow(kind, context, *, task_id=None):
    """Derive bookkeeping truth from current core verification and artifacts."""
    _fresh(context)
    state = context["state"]
    report = context.get("criterion_report")
    if callable(report):
        report = report()
    if not isinstance(report, dict) or any(report.get(k) != state[k] for k in ("run_id", "revision", "contract_digest", "profile_digest")):
        raise ValueError("current criterion report is unavailable")
    statuses = {item["id"]: item["status"] for item in report["criteria"]}
    criteria = {item["id"]: item for item in state["contract"]["criteria"]}
    if kind == "profile":
        from profile_evidence import observe_profile
        return observe_profile(context, report)
    node = state["extensions"]["workflow"]["graph"]["nodes"][task_id]
    ids = sorted(node["criteria"])
    artifacts = {key for ident in ids for key in criteria[ident].get("artifact_ids", [])}
    hashes = _current_artifacts(context, artifacts)
    if kind == "task_completion":
        if not ids or any(statuses.get(ident) != "PASS" for ident in ids):
            raise ValueError("task criterion verification is incomplete")
        return {"task_id": task_id, "criteria": ids, "artifact_digests": hashes}
    if kind == "progress_observation":
        if not hashes:
            raise ValueError("progress has no observed artifact")
        return {"task_id": task_id, "artifact_digests": hashes}
    raise ValueError("unsupported workflow observation")


def _cancelled(data, context):
    source = data.get("source")
    if not isinstance(source, dict) or set(source) != {"kind", "call_id", "readback_call_id"} or source["kind"] != "native-tool":
        return False
    job = context["state"].get("extensions", {}).get("capabilities", {}).get("continuation")
    if not job or job.get("job_id") != data.get("job_id"):
        return False
    binding = {key: context["binding"][key] for key in BINDING_KEYS}
    binding.update({key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")})
    if job.get("binding") != binding:
        return False
    deleted = native_tool_observation(context, source["call_id"])
    readback = native_tool_observation(context, source["readback_call_id"])
    if (not deleted or not readback or deleted["result_position"] >= readback["call_position"]
            or not _recent_native(readback, context, after=job.get("cancel_requested_at"))):
        return False
    if deleted["tool"] == "CronDelete" and readback["tool"] == "CronList":
        if deleted["arguments"].get("id") != job["job_id"]:
            return False
        jobs = readback["result"].get("jobs") if isinstance(readback["result"], dict) else readback["result"]
        if not isinstance(jobs, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in jobs):
            return False
        targets = {job["job_id"]}
        if str(job.get("observer_id", "")).startswith("native-job:"):
            targets.add(job["observer_id"].removeprefix("native-job:"))
        cancelled = all(item["id"] not in targets for item in jobs)
        return data == {"source": source, "job_id": job["job_id"], "cancelled": cancelled}
    return False


def _event_observation(record, context):
    """Validate output issued by the core's trusted observer transaction."""
    observation = context["state"].get("observations", {}).get(record.get("id"))
    if not isinstance(observation, dict) or not str(record.get("artifact_id", "")).startswith("event:"):
        return False
    if any(record.get(key) != observation.get(key) for key in ("id", "kind", "bindings", "data", "digest", "observed_at", "expires_at")):
        return False
    hashes = observation.get("artifact_digests")
    return isinstance(hashes, dict) and bool(hashes) and _current_artifacts(context, hashes) == hashes


def _historical_quality_attempt(state, identity, binding):
    """Inspect the proof accepted at grade time without regrading old bytes."""
    record = state.get("evidence", {}).get(identity)
    if (not isinstance(record, dict) or record.get("id") != identity
            or record.get("kind") != "quality_observation" or record.get("digest") != binding.get("digest")
            or not isinstance(record.get("data"), dict)
            or any(record["data"].get(key) != binding.get(key) for key in ("artifact_id", "artifact_digest"))):
        raise ValueError("Historical quality attempt no longer matches its graded fingerprint")
    if record.get("provenance") == "engine-observation":
        observation = state.get("observations", {}).get(identity)
        fields = ("id", "kind", "bindings", "data", "digest", "observed_at", "expires_at")
        if (not isinstance(observation, dict)
                or any(record.get(key) != observation.get(key) for key in fields)
                or observation["digest"] != hashlib.sha256(json.dumps(
                    {key: value for key, value in observation.items() if key != "digest"},
                    sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()):
            raise ValueError("Historical observer output is not intact")
    return record


def _quality_resolution(context, arguments, *, historical=False):
    from workflow import quality_receipt_verdict, quality_resolution_requirements
    if (not isinstance(arguments, dict) or set(arguments) != {"criterion_id", "prior_grade_digest", "receipt_ids"}
            or not isinstance(arguments["criterion_id"], str) or not isinstance(arguments["prior_grade_digest"], str)
            or not isinstance(arguments["receipt_ids"], list) or not arguments["receipt_ids"]
            or any(not isinstance(value, str) or not value for value in arguments["receipt_ids"])
            or len(set(arguments["receipt_ids"])) != len(arguments["receipt_ids"])):
        raise ValueError("Quality resolution requires one exact prior grade and new immutable attempts")
    _fresh(context)
    state = context["state"]
    bindings = {key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}
    flow = state.get("extensions", {}).get("workflow", {})
    if flow.get("bindings") != bindings:
        raise ValueError("Quality resolution workflow bindings are stale")
    criterion = next((item for item in state["contract"]["criteria"] if item["id"] == arguments["criterion_id"]), None)
    if criterion is None:
        raise ValueError("Quality resolution criterion is not declared")
    current = flow.get("quality", {}).get(arguments["criterion_id"])
    grades = [current]
    if historical:
        grades += flow.get("quality_history", {}).get(arguments["criterion_id"], [])
    matches = [item for item in grades if isinstance(item, dict) and item.get("grade_digest") == arguments["prior_grade_digest"]]
    if len(matches) != 1:
        raise ValueError("Quality resolution does not identify one retained prior grade")
    prior = matches[0]
    fingerprints = prior.get("receipt_bindings")
    if not isinstance(fingerprints, dict) or not fingerprints:
        raise ValueError("Historical quality grade lacks its accepted receipt fingerprints")
    verdicts = prior.get("receipt_verdicts")
    if (not isinstance(verdicts, dict) or set(verdicts) != set(fingerprints)
            or type(prior.get("independent")) is not bool):
        raise ValueError("Historical quality grade lacks its computed review verdicts")
    for identity, binding in fingerprints.items():
        record = _historical_quality_attempt(state, identity, binding)
        if (record["data"].get("criterion_id") != criterion["id"]
                or any(record.get("bindings", {}).get(key) != value for key, value in bindings.items())):
            raise ValueError("Historical quality attempt has different criterion or run bindings")
        if verdicts[identity] != quality_receipt_verdict(record["data"], prior["independent"]):
            raise ValueError("Historical quality verdict differs from its retained observation")
    new = {}
    for identity in arguments["receipt_ids"]:
        record = context.get("evidence", {}).get(identity)
        if (not isinstance(record, dict) or record != state.get("evidence", {}).get(identity)
                or not context["verify_receipt"](identity, "quality_observation", bindings)):
            raise ValueError("Repair requires fresh authentic quality observations")
        data = record["data"]
        artifact = context.get("artifacts", {}).get(data.get("artifact_id"))
        if (data.get("criterion_id") != criterion["id"] or data.get("artifact_id") not in criterion["artifact_ids"]
                or not isinstance(artifact, dict) or artifact.get("digest") != data.get("artifact_digest")):
            raise ValueError("Repair review does not bind the current criterion output")
        new[identity] = {"digest": record["digest"], "artifact_id": data["artifact_id"], "artifact_digest": data["artifact_digest"]}
    required = quality_resolution_requirements(prior, criterion["id"], new)
    explanation = "Reviewed output bytes changed for " + ", ".join(sorted(required["changed_artifacts"])) + "; new authenticated review attempts are retained. This comparison grants no approval or quality verdict."
    return {**required, "changed_evidence": explanation}


def observe_quality_resolution(context, arguments):
    """Derive a bounded repair comparison; grade and authority remain separate."""
    return _quality_resolution(context, arguments)


def _native_intake_context(record, context):
    """Only an identical reducer-admitted envelope retains its intake clock.

    This does not cache authority or native bytes. The outer verifier has just
    checked current ownership/expiry; each native source is still read again.
    New envelopes, including backdated copies, use the actual current clock.
    """
    from capabilities import receipt_fingerprint
    saved = context["state"].get("extensions", {}).get("capabilities", {}).get("native_intakes", {}).get(record.get("id"))
    if not saved or saved.get("fingerprint") != receipt_fingerprint(record):
        return context
    when = saved.get("recorded_at")
    if not _time(record["observed_at"]) <= _time(when) <= _time(context["now"]):
        raise ValueError("native receipt intake time is invalid")
    # Only this exact admitted envelope can replay its entire historical
    # invalidation interval. The source is still reparsed inside the native
    # snapshot's fixed byte limit; this does not widen a new/current intake.
    return {**context, "now": when, "_historical_native_intake": saved["fingerprint"]}


def verify_source(record, context):
    """Revalidate an observation, returning False for any unsupported claim."""
    try:
        if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
            return False
        proof = _fresh(context)
        expected = {key: proof[key] for key in BINDING_KEYS}
        expected.update({key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")})
        event_owned = _event_observation(record, context)
        if any(record.get("bindings", {}).get(key) != value for key, value in expected.items()) and not event_owned:
            return False
        if not _time(record["observed_at"]) <= _time(context["now"]) < _time(record["expires_at"]):
            return False
        kind, data = record["kind"], record["data"]
        if kind == "native_worker":
            if not event_owned:
                return False
            from delegation_boundary import verify_worker_observation
            return verify_worker_observation(data, context) is True
        if event_owned and kind in {"consumer-check", "quality_observation"}:
            return True
        if event_owned and kind == "quality_resolution":
            arguments = {key: data.get(key) for key in ("criterion_id", "prior_grade_digest", "receipt_ids")}
            return data == _quality_resolution(context, arguments, historical=True)
        if kind in LOCAL_KINDS:
            return data == observe_local(kind, context, artifact_id=data.get("artifact_id"))
        if kind == "delivery":
            return _delivery(data, context, record)
        if kind in {"capability", "continuation-registration", "continuation-renewal", "continuation-wake"}:
            context = _native_intake_context(record, context)
        if kind == "continuation-registration":
            source = data["source"]
            return data == observe_native_registration(context, source["call_id"], source["readback_call_id"],
                capability_receipt=source.get("capability_receipt"), monitor_create_call_id=source.get("monitor_create_call_id"))
        if kind == "continuation-renewal":
            source = data["source"]
            return data == observe_native_renewal(context, source["readback_call_id"], source["previous_lease_receipt"])
        if kind == "continuation-wake":
            source = data["source"]
            return data == observe_native_wake(context, source["create_call_id"], source["readback_call_id"], source["event_id"],
                registration_receipt=source.get("registration_receipt"), lease_receipt=source.get("lease_receipt"))
        if kind == "capability":
            source = data["source"]
            if not isinstance(source, dict) or source.get("kind") != "native-components":
                return False
            return data == observe_native_capability(context, {key: value for key, value in source.items() if key != "kind"})
        if kind in {"task_completion", "progress_observation", "profile"}:
            return data == observe_workflow(kind, context, task_id=data.get("task_id"))
        if kind == "continuation-cancellation":
            return _cancelled(data, context)
        if kind == "recovery":
            return _recovery_valid(data, context, record.get("id"))
        if kind == "effect-readback":
            return event_owned and data == _local_effect_readback(context, data.get("id"))
        if kind in {"quality_observation", "quality_resolution", "child_integration", "profile-amendment", "contract-amendment", "delegation", "wait-resolution", "authority", "effect-authorization", "retry_clearance"}:
            import native_review
            return native_review.verify_source(record, context) is True
        # A native facility's availability or registration cannot establish
        # survival, future wake, independent review or external-effect truth.
        return False
    except (ImportError, OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError):
        return False


def register_sources(register_evidence_source):
    """Install trusted sources; unsupported kinds explicitly deny attestation."""
    for kind in KINDS:
        register_evidence_source(kind, verify_source)


def _accept(record, state, criterion, context):
    """An authentic observation may report a failure; acceptance is separate."""
    try:
        kind, data = record["kind"], record["data"]
        if kind == "consumer-check":
            from consumer_checks import accept
            return accept(record, state, criterion, context)
        if kind in LOCAL_KINDS:
            return True  # Source already rederived these concrete local facts.
        if kind == "task_completion":
            return bool(data.get("criteria")) and bool(data.get("artifact_digests"))
        if kind == "progress_observation":
            return bool(data.get("artifact_digests"))
        if kind == "profile":
            from profile_evidence import accept_profile
            return accept_profile(data, state)
        if kind == "delivery":
            return data.get("status") in {"delivered", "acknowledged"}
        if kind == "continuation-cancellation":
            return data.get("cancelled") is True
        if kind == "continuation-wake":
            return bool(data.get("event_id")) and bool(data.get("job_id"))
        if kind in {"continuation-registration", "continuation-renewal"}:
            return bool(data.get("job_id")) and _time(data["lease_expires_at"]) > _time(context["now"])
        if kind == "capability":
            caps = data.get("capabilities", {})
            return all(caps.get(key) is True for key in ("native_identity", "registration_readback", "wake_observation", "cancellation_readback", "independent_observer"))
        if kind == "quality_observation":
            from workflow import quality_receipt_verdict
            if data.get("criterion_id") != criterion["id"] or data.get("artifact_id") not in criterion.get("artifact_ids", []):
                return False
            independent = state.get("extensions", {}).get("workflow", {}).get("profile", {}).get("checks", {}).get("evidence.independent", {}).get("status") == "required"
            return quality_receipt_verdict(data, independent, {**context, "state": state}) == "PASS"
        if kind == "child_integration":
            return data.get("accepted") is True
        if kind == "quality_resolution":
            return bool(data.get("changed_evidence"))
        if kind == "retry_clearance":
            return bool(data.get("changed_condition"))
        if kind == "wait-resolution":
            return data.get("resolved") is True
        if kind in {"authority", "effect-authorization", "profile-amendment"}:
            return data.get("approved") is True
        if kind == "effect-readback":
            return data.get("status") == "confirmed"
        if kind == "recovery":
            return isinstance(data.get("remaining"), list) and isinstance(data.get("input_receipts"), list)
        return False
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def register_acceptance_predicates(register_acceptance):
    for kind in KINDS:
        register_acceptance(kind, _accept)


def _report(context):
    report = context.get("criterion_report")
    if callable(report):
        return report()
    if isinstance(report, dict):
        return report
    from run_state import criterion_report
    return criterion_report(context["state"], context)


def _remaining(context):
    state = context["state"]
    # Recovery cannot authenticate itself through a recursive criterion. Its
    # component proofs below establish recovery separately from task outcomes.
    remaining = [item["id"] for item in _report(context)["criteria"]
                 if item["required"] and item["status"] != "PASS" and item["method"] != "recovery"]
    remaining.extend("wait:" + key for key, item in state.get("waits", {}).items() if item["status"] == "pending")
    remaining.extend("effect:" + key for key, item in state.get("effects", {}).items() if item["status"] in {"prepared", "unknown", "retryable"})
    return sorted(set(remaining))


def _recovery_components(arguments, context):
    fields = {"resolver_receipt", "native_receipt", "claim_receipt", "input_receipts"}
    if set(arguments) != fields or not isinstance(arguments["input_receipts"], list):
        raise ValueError("recovery requires its explicit component receipt references")
    if len(arguments["input_receipts"]) != len(set(arguments["input_receipts"])):
        raise ValueError("duplicate recovery input receipt")
    bindings = {key: context["binding"][key] for key in BINDING_KEYS}
    bindings.update({key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")})
    refs = [(arguments["resolver_receipt"], "project-resolution"),
            (arguments["native_receipt"], "native-identity"), (arguments["claim_receipt"], "claim-ownership")]
    refs.extend((key, "working-input") for key in arguments["input_receipts"])
    for reference, kind in refs:
        if not context["verify_receipt"](reference, kind, bindings):
            raise ValueError("recovery component observation is not current")
    return copy.deepcopy(arguments)


def _recovery_valid(data, context, reference):
    state = context["state"]
    arguments = {key: data.get(key) for key in ("resolver_receipt", "native_receipt", "claim_receipt", "input_receipts")}
    _recovery_components(arguments, context)
    saved = state.get("extensions", {}).get("capabilities", {}).get("recovery", {})
    revision = data.get("run_revision")
    current = revision == state["revision"]
    recorded = (saved.get("receipt") == reference and saved.get("recorded_revision") == state["revision"]
                and saved.get("run_revision") == revision)
    return (type(revision) is int and (current or recorded)
            and data == {**arguments, "run_revision": revision, "remaining": _remaining(context)})


def _native_observations(context, *, fresh_only=True, after_observation=None):
    """Read bounded authenticated events; positive facts require freshness."""
    from native_review import _records
    proof = _fresh(context)
    records = _records(context["actor"]["native_payload"]["transcript_path"])
    identities = []
    for position, event in enumerate(records):
        if proof["client"] == "claude" and event.get("type") == "assistant" and event.get("sessionId") == proof["native_session_id"]:
            content = event.get("message", {}).get("content", [])
            if isinstance(content, list):
                identities.extend((position, item.get("id")) for item in content if isinstance(item, dict) and item.get("type") == "tool_use" and item.get("name") in NATIVE_TOOLS)
        elif proof["client"] == "codex" and event.get("type") == "response_item":
            item = event.get("payload", {})
            if item.get("type") in {"function_call", "custom_tool_call"}:
                identities.append((position, item.get("call_id")))
    if after_observation is not None:
        anchor = after_observation
        if [position for position, identity in identities if identity == anchor["call_id"]] != [anchor["call_position"]]:
            raise ValueError("native invalidation readback anchor is missing or changed")
        selected = [(position, identity) for position, identity in identities
                    if position > anchor["result_position"]]
        if len(selected) > 64 and not context.get("_historical_native_intake"):
            raise ValueError("native invalidation interval exceeds bounded coverage")
        # Current intake retains its 64-call coverage limit. Historical replay
        # must not acquire a lifetime call ceiling: pair all selected events in
        # one bounded snapshot instead of rescanning that snapshot per call.
        # Every later negative event remains visible, regardless of timestamp;
        # a newer affirmative list never revives a cancelled or missing pair.
        indexed = _native_tool_index(records, proof, {anchor["call_id"], *(identity for _, identity in selected)})
        if indexed[anchor["call_id"]] != anchor:
            raise ValueError("native invalidation readback anchor is missing or changed")
        result = [indexed[identity] for _, identity in selected]
        if any(item is None or item["call_position"] != position
               for (position, _), item in zip(selected, result)):
            raise ValueError("native invalidation interval has ambiguous or changed calls")
    else:
        # Positive discovery may consider only the newest calls. This bounded
        # suffix cannot certify absence of invalidation since an older readback.
        selected = list(dict.fromkeys(identity for _, identity in identities))[-64:]
        result = [native_tool_observation(context, identity) for identity in selected]
    return sorted((item for item in result if item is not None
                   and (not fresh_only or _recent_native(item, context))),
                  key=lambda item: item["result_position"])


def observe_native_cleanup(kind, arguments, context):
    observations = _native_observations(context)
    if kind == "delivery":
        if set(arguments) != {"thread_id"} or not isinstance(arguments["thread_id"], str) or not arguments["thread_id"]:
            raise ValueError("delivery observer requires an exact predeclared thread")
        for item in reversed(observations):
            if item["tool"] != "mcp__codex_app__send_message_to_thread" or item["arguments"].get("threadId") != arguments["thread_id"] or not isinstance(item["result"], dict):
                continue
            terminal_at = context["state"].get("terminal", {}).get("at")
            if terminal_at and not _recent_native(item, context, after=terminal_at):
                continue
            data = {"source": {"kind": "native-tool", "call_id": item["call_id"]},
                    "delivery_id": item["call_id"], "channel": "codex-task", "status": item["result"].get("status")}
            try:
                prompt = _json(item["arguments"].get("prompt", ""))
            except (TypeError, ValueError):
                prompt = None
            if isinstance(prompt, dict) and {"wait_ids", "wait_digest", "run_revision"} <= prompt.keys():
                data.update({key: prompt[key] for key in ("wait_ids", "wait_digest", "run_revision")})
            if _delivery(data, context):
                return data
        raise ValueError("current native delivery outcome is not observable")
    if kind == "continuation-cancellation":
        if set(arguments) != {"job_id"}:
            raise ValueError("cancellation observer requires a predeclared native job")
        job = context["state"].get("extensions", {}).get("capabilities", {}).get("continuation")
        if not job or job["job_id"] != arguments["job_id"] or not job.get("cancel_requested_at"):
            raise ValueError("cancellation has no matching current requested job")
        for listed in reversed(observations):
            if listed["tool"] != "CronList":
                continue
            jobs = listed["result"].get("jobs") if isinstance(listed["result"], dict) else listed["result"]
            if not isinstance(jobs, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in jobs):
                continue
            for deleted in reversed(observations):
                if deleted["tool"] != "CronDelete" or deleted["arguments"].get("id") != job["job_id"] or not _recent_native(deleted, context, after=job["cancel_requested_at"]):
                    continue
                targets = {job["job_id"]}
                if str(job.get("observer_id", "")).startswith("native-job:"):
                    targets.add(job["observer_id"].removeprefix("native-job:"))
                data = {"source": {"kind": "native-tool", "call_id": deleted["call_id"], "readback_call_id": listed["call_id"]},
                        "job_id": job["job_id"], "cancelled": not any(item["id"] in targets for item in jobs)}
                if _cancelled(data, context):
                    return data
        raise ValueError("current native cancellation readback is not observable")
    raise ValueError("unsupported terminal cleanup observer")


def _local_effect_readback(context, effect_id):
    """Observe a declared local target's state, not causal execution history."""
    _fresh(context)
    item = context["state"]["effects"].get(effect_id)
    if not item or not item["target"].startswith("file:"):
        raise ValueError("effect target has no supported readback adapter")
    relative = Path(item["target"][5:])
    if not str(relative) or str(relative) == "." or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("effect target must be an exact project-relative file")
    root = Path(context["project"]).resolve()
    target = safe_path(root / relative, root)
    if not target.parent.is_dir():
        raise ValueError("missing target parent is not a verified absence")
    digest = None
    if target.exists():
        if not target.is_file() or target.stat().st_size > MAX_TRANSCRIPT_BYTES:
            raise ValueError("effect target is not a bounded regular file")
        before = target.stat()
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        after = target.stat()
        content_metadata = lambda info: (info.st_dev, info.st_ino, info.st_size,
                                         info.st_mtime_ns, info.st_ctime_ns)
        if content_metadata(after) != content_metadata(before):
            raise ValueError("effect target changed during readback")
    status = "absent" if digest is None else "confirmed" if digest == item["payload_digest"] else "failed"
    return {**{key: item[key] for key in ("id", "target", "payload_digest", "idempotency_key")},
            "status": status, "observed_digest": digest, "scope": "local-file-state"}


def _spec(kind, context, payload):
    if not isinstance(payload, dict) or set(payload) != {"check_id"}:
        raise ValueError("observer accepts only a registered check_id")
    identity = payload["check_id"]
    current = observe_local("working-input", context, artifact_id=identity)
    if context["artifacts"][identity].get("role") != "input":
        raise ValueError("observation specification must be a registered input")
    path = Path(context["project"]) / current["path"]
    spec = _json(path.read_text())
    if not isinstance(spec, dict) or set(spec) != {"schema_version", "kind", "arguments"}:
        raise ValueError("invalid registered observation specification")
    if spec["schema_version"] != 1 or spec["kind"] != kind or not isinstance(spec["arguments"], dict):
        raise ValueError("observation specification kind/schema mismatch")
    return spec["arguments"]


def _observe(kind, context, payload):
    arguments = _spec(kind, context, payload)
    if kind == "native_worker":
        if (set(arguments) != {"child_id", "timeout_seconds"}
                or not isinstance(arguments["child_id"], str)
                or type(arguments["timeout_seconds"]) is not int
                or not 1 <= arguments["timeout_seconds"] <= 3600):
            raise ValueError("native worker needs one dispatched child and a bounded deadline")
        state = context["state"]
        child = state.get("extensions", {}).get("workflow", {}).get("children", {}).get(arguments["child_id"])
        if not isinstance(child, dict) or child.get("mode") != "native-cli":
            raise ValueError("native worker requires an admitted native-cli dispatch")
        from delegation_boundary import run_worker
        return run_worker(state, arguments["child_id"], context, client=child["client"],
            runtime_root=Path(context["project"]) / "resources/autopilot-runs" / state["run_id"] / "native-worker-attempts",
            timeout_seconds=arguments["timeout_seconds"])
    if kind in LOCAL_KINDS:
        expected = {"artifact_id"} if kind == "working-input" else set()
        if set(arguments) != expected:
            raise ValueError("invalid local observation arguments")
        return observe_local(kind, context, artifact_id=arguments.get("artifact_id"))
    if kind in {"task_completion", "progress_observation", "profile"}:
        if set(arguments) != (set() if kind == "profile" else {"task_id"}):
            raise ValueError("invalid workflow observation arguments")
        observed = {**context, "criterion_report": _report(context)}
        return observe_workflow(kind, observed, task_id=arguments.get("task_id"))
    if kind == "recovery":
        result = _recovery_components(arguments, context)
        return {**result, "run_revision": context["state"]["revision"] + 1,
                "remaining": _remaining(context)}
    if kind == "quality_resolution":
        return observe_quality_resolution(context, arguments)
    if kind in {"delivery", "continuation-cancellation"}:
        return observe_native_cleanup(kind, arguments, context)
    if kind == "continuation-registration":
        if set(arguments) not in ({"create_call_id", "readback_call_id"}, {"create_call_id", "readback_call_id", "capability_receipt", "monitor_create_call_id"}):
            raise ValueError("registration observation needs exact native calls")
        return observe_native_registration(context, arguments["create_call_id"], arguments["readback_call_id"],
            capability_receipt=arguments.get("capability_receipt"), monitor_create_call_id=arguments.get("monitor_create_call_id"))
    if kind == "continuation-wake":
        if set(arguments) not in ({"create_call_id", "readback_call_id", "event_id"}, {"create_call_id", "readback_call_id", "event_id", "registration_receipt"},
                                 {"create_call_id", "readback_call_id", "event_id", "registration_receipt", "lease_receipt"}):
            raise ValueError("wake observation requires its exact native source")
        return observe_native_wake(context, arguments["create_call_id"], arguments["readback_call_id"], arguments["event_id"],
            registration_receipt=arguments.get("registration_receipt"), lease_receipt=arguments.get("lease_receipt"))
    if kind == "continuation-renewal":
        if set(arguments) != {"readback_call_id", "previous_lease_receipt"}:
            raise ValueError("renewal needs an exact newer readback and previous lease receipt")
        return observe_native_renewal(context, arguments["readback_call_id"], arguments["previous_lease_receipt"])
    if kind == "capability":
        return observe_native_capability(context, arguments)
    if kind == "effect-readback":
        if set(arguments) != {"effect_id"}:
            raise ValueError("readback needs a declared effect identity")
        return _local_effect_readback(context, arguments["effect_id"])
    if kind == "quality_observation":
        if arguments.get("mode") == "native-cli":
            from native_review_observer import observe_native_cli_review
            return observe_native_cli_review(context, arguments)
        if set(arguments) != {"observation_id"}:
            raise ValueError("quality projection requires a trusted consumer observation")
        identity = arguments["observation_id"]
        evidence = context["evidence"].get(identity)
        bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
        if not evidence or evidence.get("provenance") != "engine-observation" or not context["verify_receipt"](identity, "consumer-check", bindings):
            raise ValueError("quality projection requires current actual consumer evidence")
        data = copy.deepcopy(evidence["data"])
        data["independent"] = False  # Actual execution is not independent test design.
        return data
    raise ValueError("no trusted observer for this kind")


# Stable function identities make repeated CLI/Stop engine registration safe.
def _make_observer(kind):
    def observe(context, payload):
        return _observe(kind, context, payload)
    return observe


_OBSERVERS = {kind: _make_observer(kind) for kind in LOCAL_KINDS +
              ("task_completion", "progress_observation", "profile", "recovery", "quality_observation", "quality_resolution", "effect-readback", "continuation-registration", "continuation-renewal", "capability", "delivery", "continuation-cancellation", "continuation-wake", "native_worker")}


def register_observers(register_observer):
    for kind, callback in _OBSERVERS.items():
        register_observer(kind, callback, terminal_safe=kind in {"delivery", "continuation-cancellation"})

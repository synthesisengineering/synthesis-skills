"""Bounded eight-operation facade over the existing PM/run/workflow owners.

Requests carry intent, never receipts or action grants. Each step uses the
existing journal/CAS transaction; interruption preserves its committed prefix.
No separate request store, scheduler, native launcher or acceptance engine is
created here. Failed/unknown consumer results remain actual observations.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Literal, NotRequired, TypedDict
import uuid

import run_state
import run_profile
import workflow
import observation_bridge
from run_admission import admit_paths, read_admission_observation, safe_path

OPERATIONS = frozenset({"start", "next", "record", "checkpoint", "explain", "cancel", "recover", "finish"})
MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024


class Request(TypedDict):
    schema_version: Literal[1]
    request_id: str
    operation: str
    project_id: str
    run_id: NotRequired[str]
    expected_revision: NotRequired[int]
    input: dict


class Response(TypedDict):
    schema_version: Literal[1]
    request_id: str
    run_id: str | None
    revision: int | None
    status: str
    committed_event_ids: list[str]
    next: list[dict]
    coverage: dict
    diagnostics: list[dict]


def _object(value, required, optional=()):
    if not isinstance(value, dict) or set(required) - value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("request object has unsupported or missing fields")


def _text(value, label, maximum=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("request requires bounded nonempty " + label)
    return value


def _bounded(value):
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 32 or count > 32768:
            raise ValueError("request exceeds JSON depth or node bound")
        if isinstance(item, dict):
            if len(item) > 1024 or any(not isinstance(key, str) for key in item):
                raise ValueError("request object keys exceed bounds")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > 4096:
                raise ValueError("request array exceeds bound")
            pending.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in {str, bool, int, float}:
            raise ValueError("request must be finite JSON")
    try:
        raw = run_state._json(value)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("request must be finite valid Unicode JSON") from exc
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds size bound")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate request JSON key")
        result[key] = value
    return result


def decode_request(raw: bytes) -> Request:
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request exceeds size bound")
    try:
        value = json.loads(raw, object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite request JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("request is not bounded valid JSON") from exc
    return validate_request(value)


def read_request(path, stream=None) -> Request:
    if str(path) == "-":
        if stream is None:
            import sys
            stream = sys.stdin.buffer
        return decode_request(stream.read(MAX_REQUEST_BYTES + 1))
    return decode_request(_read_json_bytes(Path(path)))


def _read_json_bytes(path):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("request/reference file crosses a symlink")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_REQUEST_BYTES:
            raise ValueError("request/reference file is not regular or exceeds size bound")
        raw = stream.read(MAX_REQUEST_BYTES + 1)
        after = os.fstat(stream.fileno())
        present = path.lstat()
        if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size) or (
                present.st_dev, present.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("request/reference file changed while reading")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request/reference file exceeds size bound")
    return raw


def validate_request(value) -> Request:
    _bounded(value)
    _object(value, {"schema_version", "request_id", "operation", "project_id", "input"}, {"run_id", "expected_revision"})
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["operation"] not in OPERATIONS:
        raise ValueError("unsupported request schema or operation")
    for field in ("request_id", "project_id"):
        run_state._id(value[field], field)
    operation, data = value["operation"], value["input"]
    if operation == "start":
        if "run_id" in value or "expected_revision" in value:
            raise ValueError("start obtains its deterministic run identity from the existing owner")
        _object(data, {"plan_ref", "outcome_contract", "dimensions", "resource_envelope"}, {"preference_layer_refs", "graph"})
        _text(data["plan_ref"], "plan reference")
        run_state._contract(data["outcome_contract"])
        workflow.resolve_profile(data["dimensions"])
        _object(data["resource_envelope"], {"limits", "deadline"})
        if "graph" in data:
            _object(data["graph"], {"nodes", "wip_limit"})
            if not isinstance(data["graph"]["nodes"], list) or not 1 <= len(data["graph"]["nodes"]) <= 256:
                raise ValueError("task graph exceeds node bound")
        if "preference_layer_refs" in data:
            _object(data["preference_layer_refs"], set(), {"user", "project", "deltas"})
            for path in data["preference_layer_refs"].values():
                _text(path, "preference layer reference")
    else:
        run_state._uuid(value.get("run_id"))
        if operation == "next":
            _object(data, {"mode"}, {"task_id"})
            if data["mode"] not in {"inspect", "start"}:
                raise ValueError("invalid next mode")
            if "task_id" in data:
                run_state._id(data["task_id"], "task ID")
        elif operation == "record":
            if not isinstance(data, dict):
                raise ValueError("record input must be an object")
            kind = data.get("kind")
            if kind == "artifact":
                _object(data, {"kind", "artifact_id", "path", "role", "required", "retention"})
                run_state._id(data["artifact_id"], "artifact ID")
                _text(data["path"], "artifact path")
                if data["role"] not in {"input", "output", "evidence"} or data["retention"] != "durable" or type(data["required"]) is not bool:
                    raise ValueError("artifact role, retention or requirement is invalid")
            elif kind == "check":
                _object(data, {"kind", "observer_kind", "arguments"})
                run_state._id(data["observer_kind"], "observer kind")
                if not isinstance(data["arguments"], dict):
                    raise ValueError("observer arguments must be an object")
            elif kind == "native":
                _object(data, {"kind", "source_handle", "through_event", "task_id", "attempt_id"})
                _text(data["source_handle"], "source handle", 512)
                if data["through_event"] is not None and not isinstance(data["through_event"], dict):
                    raise ValueError("native locator must be an object or null")
            elif kind == "profile_obligation":
                _object(data, {"kind", "obligation_id", "obligation_kind", "artifact_ids", "criterion_ids", "reason"})
                run_state._id(data["obligation_id"], "profile obligation ID")
                if data["obligation_kind"] not in {"decision", "reusable-finding"}:
                    raise ValueError("unsupported profile obligation kind")
                _text(data["reason"], "profile obligation reason")
                for field in ("artifact_ids", "criterion_ids"):
                    refs = data[field]
                    if (not isinstance(refs, list) or len(refs) > 256 or any(not isinstance(ref, str) for ref in refs)
                            or len(set(refs)) != len(refs)):
                        raise ValueError("profile obligation requires bounded unique references")
                    for ref in refs:
                        run_state._id(ref, field)
                if not data["artifact_ids"]:
                    raise ValueError("profile obligation needs current source artifacts")
            elif kind == "note":
                _object(data, {"kind", "summary"})
                _text(data["summary"], "note")
            elif kind == "attempt":
                _object(data, {"kind", "task_id", "attempt_id", "strategy_id", "outcome", "observation_ids", "rationale_ref"})
                for field in ("task_id", "attempt_id", "strategy_id"):
                    run_state._id(data[field], field)
                if data["outcome"] not in {"artifact", "evidence", "failure", "blocked", "ambiguous_effect", "cancelled"}:
                    raise ValueError("unsupported requested attempt outcome")
                if (not isinstance(data["observation_ids"], list) or not 1 <= len(data["observation_ids"]) <= 512
                        or any(not isinstance(item, str) for item in data["observation_ids"])
                        or len(set(data["observation_ids"])) != len(data["observation_ids"])):
                    raise ValueError("attempt needs bounded unique existing observation references")
                if data["rationale_ref"] is not None:
                    run_state._id(data["rationale_ref"], "rationale artifact ID")
            else:
                raise ValueError("unsupported record kind")
        elif operation == "checkpoint":
            _object(data, {"reason", "include_pm"})
            _text(data["reason"], "checkpoint reason")
            if type(data["include_pm"]) is not bool:
                raise ValueError("include_pm must be boolean")
        elif operation == "explain":
            _object(data, {"view"}, {"diagnostic_id"})
            if data["view"] not in {"run", "capabilities", "coverage", "diagnostic"}:
                raise ValueError("unsupported explain view")
            if "diagnostic_id" in data:
                _text(data["diagnostic_id"], "diagnostic ID", 160)
        elif operation == "cancel":
            _object(data, {"reason", "target"}, {"target_id"})
            _text(data["reason"], "cancellation reason")
            if data["target"] not in {"run", "task", "child"}:
                raise ValueError("unsupported cancellation target")
            if data["target"] != "run":
                _text(data.get("target_id"), "cancellation target", 256)
            elif "target_id" in data:
                raise ValueError("run cancellation does not accept a separate target")
        elif operation == "recover":
            _object(data, {"reconcile_sources"}, {"capsule_ref", "source_reconciliations"})
            if type(data["reconcile_sources"]) is not bool:
                raise ValueError("reconcile_sources must be boolean")
            if "capsule_ref" in data:
                _text(data["capsule_ref"], "capsule reference")
            if "source_reconciliations" in data:
                rows = data["source_reconciliations"]
                if (not data["reconcile_sources"] or not isinstance(rows, list) or not 1 <= len(rows) <= 64):
                    raise ValueError("explicit source reconciliations require enabled bounded recovery")
                handles = set()
                for row in rows:
                    _object(row, {"source_handle", "prior_generation", "prior_cursor_digest", "new_generation", "mode"}, {"start_offset", "invalidation_resolution"})
                    _text(row["source_handle"], "source handle", 512)
                    if row["source_handle"] in handles:
                        raise ValueError("duplicate source reconciliation handle")
                    handles.add(row["source_handle"])
                    for field in ("prior_generation", "prior_cursor_digest", "new_generation"):
                        if field == "new_generation" and row[field] is None:
                            continue
                        if not isinstance(row[field], str) or re.fullmatch(r"[0-9a-f]{64}", row[field]) is None:
                            raise ValueError("source reconciliation requires exact generation/frontier digests")
                    if row["mode"] not in {"carry", "interval"}:
                        raise ValueError("unsupported source reconciliation mode")
                    if row["mode"] == "interval":
                        if type(row.get("start_offset")) is not int or row["start_offset"] < 0:
                            raise ValueError("interval recovery requires explicit start offset")
                    elif "start_offset" in row:
                        raise ValueError("carry recovery cannot advance a frontier")
                    if "invalidation_resolution" in row:
                        if row["mode"] != "interval":
                            raise ValueError("resume requires an explicit interval")
                        resolution = row["invalidation_resolution"]
                        _object(resolution, {"receipt_id", "resume_locator", "prior_invalidation_ids"})
                        _text(resolution["receipt_id"], "resume receipt ID", 160)
                        if not isinstance(resolution["prior_invalidation_ids"], list) or len(resolution["prior_invalidation_ids"]) > 512:
                            raise ValueError("resume invalidation identities exceed their bound")
                        _object(resolution["resume_locator"], {"generation", "offset", "length", "sha256"})
        elif operation == "finish":
            _object(data, {"disposition"}, {"reason"})
            if data["disposition"] not in {"completed", "incomplete"}:
                raise ValueError("unsupported finish disposition")
            if data["disposition"] == "incomplete" or "reason" in data:
                _text(data.get("reason"), "finish reason")
        readonly = operation == "explain" or operation == "next" and data["mode"] == "inspect"
        if not readonly or "expected_revision" in value:
            if type(value.get("expected_revision")) is not int or value["expected_revision"] < 1:
                raise ValueError("mutation requires an integer expected revision")
    return deepcopy(value)


def preregister_evaluation(**spec):
    """Fresh facade-managed evaluation studies use the accepted schema 2 owner."""
    import evaluation
    if "schema_version" in spec:
        raise ValueError("fresh evaluation registration has fixed schema_version 2")
    return evaluation.preregister(schema_version=2, **spec)


def _reference(project, value):
    path = Path(value)
    path = path if path.is_absolute() else project / path
    path = safe_path(path, project)
    parsed = json.loads(_read_json_bytes(path), object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite reference JSON")))
    _bounded(parsed)
    return parsed


def _profile(project, data):
    refs = data.get("preference_layer_refs", {})
    layers = {}
    for name in ("user", "project", "deltas"):
        if name in refs:
            layers[name] = _reference(project, refs[name])
        elif name == "project" and (project / run_profile.PROJECT_OVERLAY_NAME).exists():
            layers[name] = _reference(project, run_profile.PROJECT_OVERLAY_NAME)
        elif name == "user" and Path(run_profile.USER_PROFILE_DEFAULT).is_file():
            layers[name] = json.loads(_read_json_bytes(Path(run_profile.USER_PROFILE_DEFAULT)), object_pairs_hook=_unique)
    effective = run_profile.resolve_layers(layers.get("user"), layers.get("project"), layers.get("deltas"), dimensions=data["dimensions"])
    adaptive = [{"source": name, "checks": layer["checks"]} for name, layer in layers.items() if "checks" in layer]
    return effective, adaptive


class _Transaction:
    def __init__(self, request, project, actor, runtime_root, source_mode):
        import autopilot
        self.engine = autopilot.engine()
        self.request, self.project, self.actor, self.runtime_root = request, Path(project).resolve(strict=True), actor, runtime_root
        self.digest = run_state._digest({"request": request, "source_mode": source_mode if request["operation"] == "start" else None})
        self.run_id = request.get("run_id")
        self.state = None
        self.initial_revision = request.get("expected_revision", 0)
        if self.run_id:
            self.refresh()
            if self.state["project_id"] != request["project_id"]:
                raise ValueError("request project does not match the authoritative run")

    def refresh(self):
        self.state = self.engine.load_run(self.project, self.run_id)
        return self.state

    def binding(self, step):
        return {"request_id": self.request["request_id"], "request_digest": self.digest,
                "operation": self.request["operation"], "step": step, "initial_revision": self.initial_revision}

    def committed(self, step):
        if len(step) > 160:
            step = "step." + run_state._digest(step)
        if self.state is None:
            return None
        run_state._check_request(self.state, self.binding(step))
        return self.state.get("extensions", {}).get("controller", {}).get("requests", {}).get(
            self.request["request_id"], {}).get("steps", {}).get(step)

    def command_id(self, step):
        return "controller." + run_state._digest([self.request["request_id"], step])

    def step(self, step, command, payload):
        if len(step) > 160:
            step = "step." + run_state._digest(step)
        self.refresh()
        committed = self.committed(step)
        if committed:
            self.state = self.engine.replay_request_step(self.project, self.run_id,
                request_binding=self.binding(step), command=command, actor=self.actor)
            return committed["command_id"]
        saved = self.state.get("extensions", {}).get("controller", {}).get("requests", {}).get(self.request["request_id"])
        expected = self.state["revision"] if saved else self.initial_revision
        identity = self.command_id(step)
        self.engine.apply_command(self.project, self.run_id, command, payload,
            expected_revision=expected, command_id=identity, actor=self.actor, runtime_root=self.runtime_root,
            request_binding=self.binding(step))
        self.refresh()
        return identity

    def observe(self, step, kind, arguments):
        if kind not in self.engine._OBSERVERS:
            raise ValueError("observer kind is not registered by the current package")
        spec = ({"schema_version": 1, "kind": "python-consumer", **arguments} if kind == "consumer-check"
                else {"schema_version": 1, "kind": kind, "arguments": arguments})
        if kind == "consumer-check" and {"schema_version", "kind"} & arguments.keys():
            raise ValueError("consumer observer arguments cannot replace its typed specification")
        check_id = "input." + run_state._digest([self.request["request_id"], step])
        self.step("input:" + step, "input.materialize", {"id": check_id, "value": spec})
        return self.step("observe:" + step, "observe:" + kind, {"check_id": check_id})

    def context(self):
        return {**self.engine.inspect_context(self.state, self.actor, project=self.project),
                "state": deepcopy(self.state), "project": self.project, "actor": deepcopy(self.actor)}


def _start(tx, mode):
    data = tx.request["input"]
    effective, layers = _profile(tx.project, data)
    run_profile.validate_profile_contract(effective, data["outcome_contract"])
    proof = run_state.native_binding(Path(tx.actor["board"]), tx.actor["native_payload"])
    command_id = tx.command_id("create")
    tx.run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tx.project}:{proof['session_uuid']}:{command_id}"))
    tx.engine.create_run(tx.project, project_id=tx.request["project_id"], plan=Path(data["plan_ref"]),
        contract=data["outcome_contract"], profile=effective, actor=tx.actor, command_id=command_id,
        runtime_root=tx.runtime_root, request_binding=tx.binding("create"))
    tx.refresh()
    # This admitted start step commits the frontier before work becomes ready.
    # Earlier source bytes stay explicitly outside the new observation scope.
    tx.step("enroll", "native.enroll", {"source_handle": "root", "mode": mode})
    tx.step("configure", "workflow.configure", {"dimensions": data["dimensions"], "layers": layers})
    tx.step("budget", "workflow.budget", data["resource_envelope"])
    graph = data.get("graph", {"nodes": [{"id": "work", "deps": [],
        "criteria": [row["id"] for row in data["outcome_contract"]["criteria"]], "estimate": 1}], "wip_limit": 1})
    tx.step("graph", "workflow.graph", graph)
    tx.step("running", "transition", {"status": "running"})


def _catch_up(tx, prefix):
    sources = tx.state.get("extensions", {}).get("native_observations", {}).get("sources", {})
    for handle in sorted(sources):
        tx.step(prefix + ":" + handle, "native.observe", {"source_handle": handle,
            "through_event": None, "task_id": None, "attempt_id": None})


def _record(tx, data):
    kind = data["kind"]
    if kind == "artifact":
        tx.step("artifact", "artifact.register", {"id": data["artifact_id"], **{
            key: data[key] for key in ("path", "role", "required", "retention")}})
    elif kind == "check":
        tx.observe("check", data["observer_kind"], data["arguments"])
    elif kind == "native":
        tx.step("native", "native.observe", {key: value for key, value in data.items() if key != "kind"})
    elif kind == "note":
        tx.step("note", "progress", {"summary": data["summary"]})
    elif kind == "profile_obligation":
        tx.step("profile_obligation", "controller.profile_obligation", {"id": data["obligation_id"],
            "kind": data["obligation_kind"], **{key: data[key] for key in ("artifact_ids", "criterion_ids", "reason")}})
    elif kind == "attempt":
        tx.step("attempt", "workflow.attempt", {key: value for key, value in data.items() if key != "kind"})


def _prepare_profile_obligation(context, payload):
    _object(payload, {"id", "kind", "artifact_ids", "criterion_ids", "reason"})
    probe = {"schema_version": 1, "request_id": "validate", "operation": "record",
        "project_id": context["state"]["project_id"], "run_id": context["state"]["run_id"],
        "expected_revision": context["state"]["revision"], "input": {
            "kind": "profile_obligation", "obligation_id": payload["id"], "obligation_kind": payload["kind"],
            **{key: payload[key] for key in ("artifact_ids", "criterion_ids", "reason")}}}
    validate_request(probe)
    read_admission_observation(context)
    criteria = {row["id"] for row in context["state"]["contract"]["criteria"]}
    if any(identity not in context["artifacts"] for identity in payload["artifact_ids"]):
        raise ValueError("profile obligation source artifact is missing, unsafe or changed")
    if not set(payload["criterion_ids"]) <= criteria:
        raise ValueError("profile obligation cannot invent capture criterion references")
    row = {"id": payload["id"], "kind": payload["kind"], "reason": payload["reason"],
        "artifact_digests": {identity: context["artifacts"][identity]["digest"] for identity in sorted(payload["artifact_ids"])},
        "criterion_ids": sorted(payload["criterion_ids"]),
        "bindings": {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")},
        "observed_revision": context["state"]["revision"] + 1}
    existing = context["state"].get("extensions", {}).get("controller", {}).get("profile_obligations", {}).get(payload["id"])
    if existing is not None:
        if {key: value for key, value in row.items() if key != "observed_revision"} != {
                key: value for key, value in existing.items() if key != "observed_revision"}:
            raise ValueError("profile obligation identity is immutable")
        return deepcopy(existing)
    return row


def _profile_obligation_reducer(state, prepared, context):
    result = deepcopy(state)
    rows = result["extensions"].setdefault("controller", {"schema_version": 1}).setdefault("profile_obligations", {})
    if len(rows) >= 256 and prepared["id"] not in rows:
        raise ValueError("profile obligation collection exceeds its bound")
    rows[prepared["id"]] = deepcopy(prepared)
    return result


def _prepare_checkpoint(context, payload):
    _object(payload, {"reason", "include_pm"})
    _text(payload["reason"], "checkpoint reason")
    if type(payload["include_pm"]) is not bool:
        raise ValueError("checkpoint include_pm must be boolean")
    proof = read_admission_observation(context)
    state, project = context["state"], Path(context["project"])
    data = {"reason": payload["reason"], "at": context["now"], "revision": state["revision"],
        "missing_or_changed_artifacts": sorted(set(state["artifacts"]) - set(context["artifacts"])),
        "waits": deepcopy(state["waits"]), "effects": deepcopy(state["effects"]), "pm": None}
    if payload["include_pm"]:
        import project_state
        paths = [project / "CONTEXT.md", project / project_state.STATE_FILE]
        admit_paths(Path(context["actor"]["board"]), state["project_id"], project, paths,
                    context["actor"]["native_payload"])
        if not paths[1].is_file():
            raise ValueError("PM checkpoint needs the existing owner's adopted CURRENT_STATE.json build")
        adopted = json.loads(_read_json_bytes(paths[1]), object_pairs_hook=_unique)
        if adopted.get("session_id") != proof["session_uuid"] or adopted.get("project_id") != state["project_id"]:
            raise ValueError("PM adopted state is not owned by this current session")
        fields = ("phase", "status", "controlling_plan", "accepted_baseline", "next_actions", "last_session")
        if any(field not in adopted for field in fields):
            raise ValueError("PM adopted state lacks its existing structured fields")
        project_state.build_operational_state(project, project_id=state["project_id"],
            **{field: adopted[field] for field in fields}, session_id=proof["session_uuid"],
            source_heads=adopted.get("source_heads"))
        import execution_checkpoint
        data["pm"] = execution_checkpoint.observe_execution_basis(context)
    import profile_evidence
    data["basis"] = profile_evidence.checkpoint_basis(context)
    return data


def _prepare_closure(context, payload):
    _object(payload, {"request_id", "request_digest"})
    run_state._id(payload["request_id"], "request ID")
    if not isinstance(payload["request_digest"], str) or re.fullmatch(r"[0-9a-f]{64}", payload["request_digest"]) is None:
        raise ValueError("closure requires the exact request digest")
    proof = read_admission_observation(context)
    state = context["state"]
    sources = state.get("extensions", {}).get("native_observations", {}).get("sources", {})
    synthetic = bool(sources) and all(source["binding"]["mode"] == "synthetic" for source in sources.values())
    root = (Path(context["runtime_root"]).parent / "project-state/receipts" if synthetic
            else Path.home() / ".synthesis/project-state/receipts")
    if root.is_relative_to(Path(context["project"])):
        raise ValueError("final PM receipt root must be external to the changing project")
    if any(item.is_symlink() for item in (root, *root.parents)):
        raise ValueError("final PM receipt root crosses a symlink")
    return {"schema_version": 1, **payload, **{key: state[key] for key in ("run_id", "contract_digest", "profile_digest")},
        "plan_digest": context["plan_digest"], "owner": {key: proof[key] for key in ("session_uuid", "native_ref")},
        "receipt_root": str(root), "postamble": "pending", "required_pm": True}


def _closure_reducer(state, prepared, context):
    result = deepcopy(state)
    result["extensions"].setdefault("controller", {"schema_version": 1})["closure_intent"] = deepcopy(prepared)
    return result


def _postamble(tx):
    """Finalize normal PM checkpoint after the last terminal projection write.

    The terminal journal retains pending intent. Its current external PM
    receipt resolves that intent without another journal mutation or replay.
    """
    import project_state
    state = tx.refresh()
    intent = state.get("extensions", {}).get("controller", {}).get("closure_intent")
    if not intent or state["status"] != "completed":
        return None
    if (intent["request_id"] != tx.request["request_id"] or intent["request_digest"] != tx.digest
            or any(intent[key] != state[key] for key in ("run_id", "contract_digest", "profile_digest"))):
        raise ValueError("closure postamble does not bind this terminal request")
    proof = run_state._binding(tx.project, state, tx.actor)
    if intent["owner"] != {key: proof[key] for key in ("session_uuid", "native_ref")}:
        raise ValueError("terminal postamble owner differs from the committed intent")
    paths = [tx.project / "CONTEXT.md", tx.project / project_state.STATE_FILE]
    admit_paths(Path(tx.actor["board"]), state["project_id"], tx.project, paths, tx.actor["native_payload"])
    adopted = json.loads(_read_json_bytes(paths[1]), object_pairs_hook=_unique)
    if adopted.get("session_id") != proof["session_uuid"] or adopted.get("project_id") != state["project_id"]:
        raise ValueError("terminal PM state changed owner or project")
    fields = ("phase", "status", "controlling_plan", "accepted_baseline", "next_actions", "last_session")
    if any(field not in adopted for field in fields):
        raise ValueError("terminal PM state lacks its existing structured fields")
    root = Path(intent["receipt_root"])
    if root.is_relative_to(tx.project) or any(item.is_symlink() for item in (root, *root.parents)):
        raise ValueError("terminal PM receipt location is unsafe")
    status, _ = project_state.validate_checkpoint(tx.project, session_id=proof["session_uuid"],
        coordination_board=Path(tx.actor["board"]), receipt_root=root, source_heads=adopted.get("source_heads"))
    if status != "PASS":
        project_state.build_operational_state(tx.project, project_id=state["project_id"],
            **{field: adopted[field] for field in fields}, session_id=proof["session_uuid"], source_heads=adopted.get("source_heads"))
        run_state._binding(tx.project, state, tx.actor)
        project_state.checkpoint_project(tx.project, session_id=proof["session_uuid"],
            coordination_board=Path(tx.actor["board"]), receipt_root=root, source_heads=adopted.get("source_heads"),
            native_event=tx.actor["native_payload"])
    status, issues = project_state.validate_checkpoint(tx.project, session_id=proof["session_uuid"],
        coordination_board=Path(tx.actor["board"]), receipt_root=root, source_heads=adopted.get("source_heads"))
    if status != "PASS":
        raise ValueError("terminal PM postamble remains pending: " + "; ".join(issues))
    # A concurrent late observation invalidates this exact terminal snapshot;
    # the next same-request postamble must checkpoint the then-current journal.
    if tx.engine.load_run(tx.project, tx.run_id) != state:
        raise ValueError("terminal journal changed during final PM checkpoint")
    return {"status": "PASS", "scope": "normal PM clean checkpoint after terminal journal",
            "receipt_path": str(project_state._receipt_path(root, proof["session_uuid"], state["project_id"]))}


def _checkpoint_reducer(state, prepared, context):
    result = deepcopy(state)
    result["extensions"].setdefault("controller", {"schema_version": 1})["checkpoint"] = deepcopy(prepared)
    return result


def register(engine):
    engine.register_command("controller.checkpoint", _checkpoint_reducer)
    engine.register_preparer("controller.checkpoint", _prepare_checkpoint)
    engine.register_command("controller.profile_obligation", _profile_obligation_reducer)
    engine.register_preparer("controller.profile_obligation", _prepare_profile_obligation)
    engine.register_command("controller.closure_intent", _closure_reducer)
    engine.register_preparer("controller.closure_intent", _prepare_closure)


def _checkpoint(tx, data):
    _catch_up(tx, "catch-up")
    tx.step("checkpoint", "controller.checkpoint", data)


def _fresh_evidence(tx, criterion, kind):
    context = tx.context()
    values = []
    for identity, evidence in context["evidence"].items():
        data = evidence.get("data", {})
        if (evidence.get("kind") == kind and data.get("criterion_id") == criterion["id"]
                and data.get("artifact_id") in criterion.get("artifact_ids", [])
                and context["verify_receipt"](identity, kind, {})):
            values.append(identity)
    def committed_order(identity):
        evidence = context["evidence"][identity]
        locator = evidence.get("artifact_id", "")
        revision = (int(locator.removeprefix("event:"))
            if evidence.get("provenance") == "engine-observation"
            and re.fullmatch(r"event:[1-9][0-9]*", locator) else -1)
        return revision, identity
    # Journal-assigned observation revisions survive sorted JSON serialization.
    # Native timestamps and lexicographic receipt IDs do not establish order.
    values.sort(key=committed_order)
    return values


def _finish(tx, data):
    if data["disposition"] == "incomplete":
        tx.step("close", "close", {"status": "incomplete", "reason": data["reason"]})
        return
    _catch_up(tx, "finish-catch-up")
    _require_current_native(tx)
    for source in tx.state.get("extensions", {}).get("native_observations", {}).get("sources", {}).values():
        coverage = source.get("coverage") or {}
        if (coverage.get("backlog_bytes") or coverage.get("pending_bytes") or coverage.get("first_gap") is not None
                or source.get("recovery") or source.get("last_diagnostics")):
            raise ValueError("native observation catch-up has pending bytes or coverage gaps")
    tx.step("verifying", "transition", {"status": "verifying"})
    graph = tx.state.get("extensions", {}).get("workflow", {}).get("graph", {}).get("nodes", {})
    enabled = [item for item in tx.state["profile"]["items"] if item.get("enabled", True)]
    enabled_ids = {item["id"] for item in enabled}
    closure_ids = {row["id"] for row in tx.state["contract"]["criteria"] if row["required"]}
    closure_ids.update(identity for node in graph.values() for identity in node.get("criteria", []))
    closure_ids.update(identity for item in enabled for identity in item.get("criterion_ids", []))
    closure_ids.update(row["id"] for row in tx.state["contract"]["criteria"]
        if enabled_ids.intersection(row.get("profile_item_ids", [])))
    closure_ids.update(identity for item in tx.state.get("extensions", {}).get("controller", {}).get(
        "profile_obligations", {}).values() for identity in item.get("criterion_ids", []))
    for criterion in tx.state["contract"]["criteria"]:
        if criterion["id"] not in closure_ids:
            continue
        quality = _fresh_evidence(tx, criterion, "quality_observation")
        consumers = _fresh_evidence(tx, criterion, "consumer-check")
        if consumers:
            quality = [tx.observe("quality:" + criterion["id"], "quality_observation", {"observation_id": consumers[-1]})]
        if quality:
            grade = {"criterion_id": criterion["id"], "receipt_ids": quality, "independent": False}
            context = tx.context()
            prior = tx.state.get("extensions", {}).get("workflow", {}).get("quality", {}).get(criterion["id"])
            if prior and prior["verdict"] in {"FAIL", "DISAGREEMENT"}:
                bindings = {identity: {"digest": context["evidence"][identity]["digest"],
                    "artifact_id": context["evidence"][identity]["data"]["artifact_id"],
                    "artifact_digest": context["evidence"][identity]["data"]["artifact_digest"]} for identity in quality}
                expected = workflow.quality_resolution_requirements(prior, criterion["id"], bindings)
                candidates = [identity for identity, row in context["evidence"].items() if row["kind"] == "quality_resolution"
                    and all(row["data"].get(key) == value for key, value in expected.items())
                    and context["verify_receipt"](identity, "quality_resolution", {})]
                if len(candidates) != 1:
                    raise ValueError("failed quality grade needs one exact owner-verified repair resolution")
                grade["resolution_receipt_id"] = candidates[0]
            rearm = workflow.prepare_grade(tx.state, grade, context)
            if rearm is not None:
                tx.step("quality-rearm:" + criterion["id"], "workflow.rearm", rearm)
            tx.step("grade:" + criterion["id"], "workflow.grade", grade)
        method = criterion["method"]
        chosen = quality if method == "quality_observation" else consumers if method == "consumer-check" else []
        if chosen:
            for slot in criterion.get("evidence_ids", []):
                prior = tx.state.get("criterion_evidence_bindings", {}).get(criterion["id"], {}).get(slot)
                prior_id = prior["receipt_id"] if prior else slot if slot in tx.state["evidence"] else None
                prior_digest = prior["digest"] if prior else tx.state["evidence"][prior_id]["digest"] if prior_id else None
                if (prior_id == chosen[-1] and prior_digest == tx.state["evidence"][chosen[-1]]["digest"]
                        and (prior is None or all(prior.get(key) == tx.state[key]
                             for key in ("contract_digest", "profile_digest")))):
                    # A declared exact receipt is already routed. Verification
                    # still rederives its source and domain acceptance below.
                    continue
                tx.step("bind:" + criterion["id"] + ":" + slot, "criterion.evidence.bind", {
                    "criterion_id": criterion["id"], "slot": slot, "receipt_id": chosen[-1],
                    "expected_prior_receipt_id": prior_id, "expected_prior_digest": prior_digest})
        tx.step("verify:" + criterion["id"], "verify", {"criteria": [criterion["id"]]})
    graph = tx.state.get("extensions", {}).get("workflow", {}).get("graph", {}).get("nodes", {})
    for identity, node in graph.items():
        if node["status"] == "running":
            receipt = tx.observe("task:" + identity, "task_completion", {"task_id": identity})
            tx.step("complete:" + identity, "workflow.task", {"task_id": identity, "action": "complete", "receipt_id": receipt})
    import project_state
    applicability, _ = project_state.checkpoint_applicability(tx.project)
    if applicability not in {"REQUIRED", "NOT_APPLICABLE"}:
        raise ValueError("PM adoption is unresolved")
    include_pm = applicability == "REQUIRED"
    _checkpoint(tx, {"reason": "Current owner verified declared outcomes before closure", "include_pm": include_pm})
    profile = tx.observe("profile", "profile", {})
    tx.step("verify-profile", "verify", {"criteria": [row["id"] for row in tx.state["contract"]["criteria"] if row["id"] in closure_ids],
                                          "profile_evidence": profile})
    report = tx.engine.completion_report(tx.project, tx.run_id, actor=tx.actor)
    if report["status"] != "PASS":
        raise ValueError("existing completion owner rejected closure: " + "; ".join(report["issues"]))
    if include_pm:
        tx.step("closure-intent", "controller.closure_intent", {"request_id": tx.request["request_id"], "request_digest": tx.digest})
    tx.step("close", "close", {"status": "completed", "reason": data.get("reason", "Existing outcome consumers verified the declared contract")})


def _require_current_native(tx):
    from observation_bridge import current_invalidation
    result = current_invalidation(tx.context())
    if result["status"] != "clear":
        raise ValueError("current native execution scope is " + result["status"] + ": " +
            "; ".join(row.get("detail", row.get("code", "")) for row in result["diagnostics"]))
    return result


def _next(state):
    result = []
    if state["status"] in run_state.TERMINAL:
        flow = state.get("extensions", {}).get("workflow", {})
        result.extend({"owner": "workflow", "kind": "child_cleanup", "child_id": identity}
                      for identity, child in flow.get("children", {}).items() if child.get("disposition") == "running")
        continuation = state.get("extensions", {}).get("capabilities", {}).get("continuation")
        if continuation:
            result.append({"owner": "capabilities", "kind": "native_cleanup_readback", "job_id": continuation.get("job_id")})
        return result
    try:
        result.extend({"owner": "workflow", "kind": "ready_task", "task_id": identity}
                      for identity in workflow.ready_tasks(state))
    except (KeyError, ValueError):
        result.append({"owner": "workflow", "kind": "configure_or_reconcile"})
    result.extend({"owner": "run_state", "kind": "wait", "wait_id": identity, "reason": item["reason"]}
                  for identity, item in state["waits"].items() if item["status"] == "pending")
    result.extend({"owner": "run_state", "kind": "effect_reconciliation", "effect_id": identity}
                  for identity, item in state["effects"].items() if item["status"] in {"prepared", "unknown", "retryable"})
    return result


def _response(request, state, status, *, context=None, diagnostics=None):
    events = []
    diagnostics = deepcopy(diagnostics or [])
    coverage = {"owner_admission": "VERIFIED" if context is not None else "UNVERIFIED",
                "native": {}, "interpretation": "Historical ingestion is separate from current positive ranges and negative interval coverage."}
    next_steps = []
    if state is not None:
        entry = state.get("extensions", {}).get("controller", {}).get("requests", {}).get(request["request_id"], {})
        events = [row["command_id"] for row in sorted(entry.get("steps", {}).values(), key=lambda row: row["revision"])]
        next_steps = _next(state)
        extension = state.get("extensions", {}).get("native_observations", {})
        for handle, source in extension.get("sources", {}).items():
            coverage["native"][handle] = {"enrollment": source["enrollment"], "coverage": source.get("coverage"),
                "qualification": source["qualification"], "negative_coverage": "UNKNOWN",
                "recovery": source.get("recovery"), "reconciliation": source.get("reconciliation")}
            diagnostics.extend({"source_handle": handle, **row} for row in source.get("last_diagnostics", []))
            if source.get("recovery"):
                next_steps.append({"owner": "observation_bridge", "kind": "generation_reconciliation",
                    "source_handle": handle, **source["recovery"]})
        if context is not None:
            profile_ref = state.get("profile_evidence")
            profile = context.get("evidence", {}).get(profile_ref)
            if profile and context["verify_receipt"](profile_ref, "profile", {}):
                coverage["completion_report"] = deepcopy(profile["data"].get("completion_report"))
                pm = state.get("extensions", {}).get("controller", {}).get("checkpoint", {}).get("pm")
                if isinstance(pm, dict):
                    from execution_checkpoint import current_proof
                    coverage["current_completion_proof"] = current_proof(context, pm)
            report = run_state.criterion_report(state, context)
            next_steps.extend({"owner": "run_state", "kind": "acceptance", "criterion_id": row["id"], "issues": row["issues"]}
                              for row in report["criteria"] if row["status"] != "PASS")
            if request["operation"] == "explain":
                import capabilities
                coverage["view"] = {"criteria": report, "capabilities": capabilities.status_view(state, context)}
        elif request["operation"] == "explain":
            coverage["recorded_status"] = state["status"]
    return {"schema_version": 1, "request_id": request["request_id"], "run_id": state["run_id"] if state else request.get("run_id"),
        "revision": state["revision"] if state else None, "status": status, "committed_event_ids": events,
        "next": next_steps, "coverage": coverage, "diagnostics": diagnostics or []}


def encode_response(response: Response) -> bytes:
    raw = run_state._json(response)
    if len(raw) <= MAX_RESPONSE_BYTES:
        return raw
    bounded = {**response, "next": [], "committed_event_ids": [],
        "coverage": {"owner_admission": response["coverage"]["owner_admission"],
                     "result_ref": {"run_id": response["run_id"], "journal_revision": response["revision"]}},
        "diagnostics": [{"code": "response_pagination_required", "owner": "run_state",
            "detail": "Read the exact committed revision through the existing journal owner; response contents exceeded the 1 MiB bound."}]}
    return run_state._json(bounded)


def handle(request: Request, *, project: Path, actor=None, runtime_root=None, source_mode="native") -> Response:
    request = validate_request(request)
    if source_mode not in {"native", "synthetic"}:
        raise ValueError("source mode must be native or synthetic claim")
    tx = None
    current_acceptance = None
    native_current = None
    try:
        tx = _Transaction(request, project, actor, runtime_root, source_mode)
        operation, data = request["operation"], request["input"]
        readonly = operation == "explain" or operation == "next" and data["mode"] == "inspect"
        if not readonly and actor is None:
            raise ValueError("mutation requires the existing PM/native owner admission; complete its registry/claim setup")
        if not readonly and tx.state is not None:
            run_state._check_request(tx.state, tx.binding("admission"))
            run_state._binding(tx.project, tx.state, actor)
        last_step = {"next": "start-task", "checkpoint": "checkpoint", "recover": "checkpoint",
                     "finish": "close"}.get(operation)
        if operation == "record":
            last_step = "observe:check" if data["kind"] == "check" else data["kind"]
        if operation == "cancel":
            last_step = {"run": "cancel", "task": "cancel-task", "child": "cancel-child"}[data["target"]]
        completed_prefix = bool(last_step and tx.committed(last_step)) if not readonly else False
        if completed_prefix:
            tx.state = tx.engine.replay_request_step(tx.project, tx.run_id,
                request_binding=tx.binding(last_step), actor=actor)
        elif operation == "start":
            _start(tx, source_mode)
        elif readonly:
            pass
        elif operation == "next":
            ready = workflow.ready_tasks(tx.state)
            selected = data.get("task_id") or (ready[0] if ready else None)
            if selected not in ready:
                raise ValueError("no requested dependency, budget, retry and WIP ready task")
            tx.step("start-task", "workflow.task", {"task_id": selected, "action": "start"})
        elif operation == "record":
            _record(tx, data)
        elif operation == "checkpoint":
            _checkpoint(tx, data)
        elif operation == "cancel":
            if data["target"] == "run":
                tx.step("cancel", "close", {"status": "cancelled", "reason": data["reason"]})
            elif data["target"] == "task":
                tx.step("cancel-task", "workflow.task", {"task_id": data["target_id"], "action": "cancel", "reason": data["reason"]})
            else:
                tx.step("cancel-child", "workflow.cancel_child", {"child_id": data["target_id"], "reason": data["reason"]})
        elif operation == "recover":
            if "capsule_ref" in data:
                capsule = _reference(tx.project, data["capsule_ref"])
                if capsule.get("run_id") != tx.run_id or capsule.get("project_id") != request["project_id"]:
                    raise ValueError("recovery capsule does not name this run/project; it grants no ownership transfer")
            # Existing two-phase transfer remains mandatory for a new owner.
            if data["reconcile_sources"]:
                sources = tx.state.get("extensions", {}).get("native_observations", {}).get("sources", {})
                specs = {row["source_handle"]: row for row in data.get("source_reconciliations", [])}
                if set(specs) - set(sources):
                    raise ValueError("recovery cannot introduce an unbound source handle")
                for handle in sorted(sources):
                    payload = {"source_handle": handle}
                    if handle in specs:
                        payload["reconciliation"] = {key: value for key, value in specs[handle].items() if key != "source_handle"}
                    tx.step("reconcile:" + handle, "native.reconcile", payload)
            _checkpoint(tx, {"reason": "Current owner reconstructed the authoritative journal", "include_pm": False})
        elif operation == "finish":
            _finish(tx, data)
        finishing = operation == "finish" and data["disposition"] == "completed"
        if finishing:
            native_current = _require_current_native(tx)
            before = tx.context()
            if (any(row["required"] and identity not in before["artifacts"] for identity, row in tx.state["artifacts"].items())
                    or run_state.criterion_report(tx.state, before)["status"] != "PASS"):
                current_acceptance = tx.engine.completion_report(tx.project, tx.run_id, actor=actor)
                raise ValueError("terminal completion proof is no longer current: " + "; ".join(current_acceptance["issues"]))
        postamble = _postamble(tx) if finishing else None
        context = tx.context() if actor is not None else None
        status = tx.state["status"].upper() if tx.state["status"] in run_state.TERMINAL else "RECORDED" if operation in {"record", "checkpoint"} else "READY"
        if finishing:
            current_acceptance = tx.engine.completion_report(tx.project, tx.run_id, actor=actor)
            if current_acceptance["status"] != "PASS":
                status = "UNRESOLVED"
        if tx.state["status"] not in run_state.TERMINAL:
            sources = tx.state.get("extensions", {}).get("native_observations", {}).get("sources", {})
            if any(source.get("recovery") or (source.get("coverage") or {}).get("first_gap") is not None
                    or any(row.get("code") == "source_unavailable" for row in source.get("last_diagnostics", [])) for source in sources.values()):
                status = "RECONCILE"
            elif any((source.get("coverage") or {}).get("backlog_bytes") or (source.get("coverage") or {}).get("pending_bytes")
                    or any(row.get("code") == "requested_locator_not_observed" for row in source.get("last_diagnostics", [])) for source in sources.values()):
                status = "WAIT"
        response = _response(request, tx.state, status, context=context)
        if current_acceptance is not None:
            response["coverage"]["current_acceptance"] = current_acceptance
            response["coverage"]["journal_terminal"] = tx.state["status"]
            if current_acceptance["status"] != "PASS":
                response["next"].append({"owner": "run_state", "kind": "current_completion_proof",
                    "issues": current_acceptance["issues"]})
        if native_current is not None:
            response["coverage"]["current_native_invalidation"] = native_current
        if postamble is not None:
            response["coverage"]["closure_postamble"] = postamble
        return response
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, ImportError) as exc:
        state = tx.state if tx else None
        if tx and tx.run_id:
            try:
                state = tx.refresh()
            except (ValueError, OSError, KeyError, TypeError, RuntimeError):
                pass
        response = _response(request, state, "UNRESOLVED", diagnostics=[{
            "code": "owner_obligation", "owner": "existing PM/run/workflow/evidence owner", "detail": str(exc)[:4096]}])
        response["next"].append({"kind": "resolve_owner_obligation", "owner": "existing owner", "detail": str(exc)[:4096]})
        if current_acceptance is not None:
            response["coverage"]["current_acceptance"] = current_acceptance
            response["coverage"]["journal_terminal"] = state["status"] if state else None
        if state and state["status"] == "completed" and state.get("extensions", {}).get("controller", {}).get("closure_intent"):
            response["coverage"]["closure_postamble"] = {"status": "PENDING", "journal_terminal": "completed", "request_id": request["request_id"]}
            response["next"].append({"kind": "retry_terminal_postamble", "owner": "PM", "request_id": request["request_id"]})
        return response

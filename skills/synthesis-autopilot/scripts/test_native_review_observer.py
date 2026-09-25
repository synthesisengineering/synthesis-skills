"""Bounded native CLI review executes once and grades blind controls itself."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run_state import engine, world, create, command  # noqa: F401


@pytest.fixture
def observer():
    return importlib.import_module("native_review_observer")


@pytest.fixture
def review(tmp_path):
    files = {"draft": "The sample is five.", "rubric": "Reject unsupported facts.",
             "one": "The sample is five.", "two": "The sample is five hundred."}
    artifacts = {}
    def add(key, body):
        (tmp_path / (key + ".txt")).write_text(body)
        artifacts[key] = {"path": key + ".txt", "digest": hashlib.sha256(body.encode()).hexdigest(),
                          "role": "output" if key == "draft" else "input"}
    for key, body in files.items():
        add(key, body)
    manifest = {"schema_version": 1, "domain": "writing", "rubric": "Source fidelity",
                "rubric_artifact_id": "rubric", "rubric_digest": artifacts["rubric"]["digest"],
                "controls": [{"artifact_id": key, "artifact_digest": artifacts[key]["digest"], "expected": value}
                             for key, value in (("one", "PASS"), ("two", "FAIL"))]}
    add("gold", json.dumps(manifest))
    context = {"project": tmp_path, "artifacts": artifacts, "evidence": {},
        "binding": {"session_uuid": "owner"},
        "state": {"run_id": "run-one", "contract_digest": "a" * 64, "profile_digest": "b" * 64,
                  "contract": {"criteria": [{"id": "accept", "artifact_ids": ["draft"]}]},
                  "extensions": {"workflow": {"budget": {"limits": {"usd_micros": {"enforcement": "forecast"}}, "reservations": {
                      "review-one": {"status": "reserved", "category": "verification", "amounts": {"wall_millis": 120000, "usd_micros": 2000000}}}}}}}}
    arguments = {"mode": "native-cli", "client": "claude", "criterion_id": "accept", "artifact_id": "draft",
                 "calibration_manifest_id": "gold", "reservation_id": "review-one", "timeout_seconds": 120,
                 "max_cost_usd": 2}
    return context, arguments


def result(prompt, failed=False):
    request = json.loads(prompt.split("\nREQUEST\n", 1)[1])
    response = {"bindings": request["bindings"], "artifact_digest": request["artifact_digest"],
        "observations": {"source_fidelity": True, "reader_purpose": True, "structure": True, "voice": True},
        "findings": [], "controls": [{"artifact_id": c["artifact_id"], "artifact_digest": c["digest"],
            "verdict": "PASS" if c["content"] == "The sample is five." or failed else "FAIL"} for c in request["controls"]]}
    return {"response": response, "session_id": "native-child", "model": "configured-native-model",
            "usage": {"cost_usd": 0.1}, "stdout_digest": "c" * 64, "wall_seconds": 1,
            "returncode": 0, "tool_calls": [], "client": "claude"}


def test_observer_hides_gold_and_derives_calibration(observer, review, monkeypatch):
    context, args = review
    def execute(client, prompt, **kwargs):
        assert '"expected"' not in prompt and '"gold"' not in prompt
        return result(prompt)
    monkeypatch.setattr(observer, "execute_native", execute)
    actual = observer.observe_native_cli_review(context, args)
    assert actual["calibrated"] is True and actual["passed"] is True
    assert actual["independent"] is True and actual["reviewer"] == "claude-cli:native-child"
    assert actual["execution"]["usage"]["cost_usd"] == 0.1
    with pytest.raises(ValueError, match="attempt"):
        observer.observe_native_cli_review(context, args)


def test_bad_blind_control_remains_authentic_failed_calibration(observer, review, monkeypatch):
    context, args = review
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw: result(prompt, True))
    actual = observer.observe_native_cli_review(context, args)
    assert actual["calibrated"] is False and actual["passed"] is False


@pytest.mark.parametrize("defect", ["tool", "binding", "artifact", "returncode", "duplicate-control"])
def test_invalid_native_observation_does_not_become_evidence(observer, review, monkeypatch, defect):
    context, args = review
    def execute(client, prompt, **kwargs):
        native = result(prompt)
        if defect == "tool": native["tool_calls"] = ["shell"]
        if defect == "binding": native["response"]["bindings"]["run_id"] = "elsewhere"
        if defect == "artifact": (context["project"] / "draft.txt").write_text("changed")
        if defect == "returncode": native["returncode"] = 1
        if defect == "duplicate-control": native["response"]["controls"][1] = native["response"]["controls"][0]
        return native
    monkeypatch.setattr(observer, "execute_native", execute)
    with pytest.raises(ValueError): observer.observe_native_cli_review(context, args)


def test_review_without_reserved_resources_does_not_launch(observer, review, monkeypatch):
    context, args = review
    context["state"]["extensions"]["workflow"]["budget"]["reservations"].clear()
    monkeypatch.setattr(observer, "execute_native", lambda *a, **kw: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="reservation"):
        observer.observe_native_cli_review(context, args)


@pytest.mark.parametrize("client", ["claude", "codex", "muse"])
def test_forecast_only_native_review_cannot_accept_hard_currency_policy(observer, review, monkeypatch, client):
    context, args = review
    args['client'] = client
    context['state']['extensions']['workflow']['budget']['limits']['usd_micros']['enforcement'] = 'hard'
    monkeypatch.setattr(observer, 'execute_native', lambda *a, **kw: pytest.fail('hard cap cannot launch forecast adapter'))
    with pytest.raises(ValueError, match='forecast'):
        observer.observe_native_cli_review(context, args)
    assert not (context['project']/'resources').exists()


def test_interrupted_attempt_cannot_repeat_provider_call(observer, review, monkeypatch):
    context, args = review
    def interrupt(*a, **kw): raise TimeoutError("native review timed out")
    monkeypatch.setattr(observer, "execute_native", interrupt)
    with pytest.raises(TimeoutError): observer.observe_native_cli_review(context, args)
    with pytest.raises(ValueError, match="attempt"): observer.observe_native_cli_review(context, args)


@pytest.mark.parametrize("client", ["claude", "codex", "muse"])
def test_supported_native_argv_has_restricted_tools_and_no_shell_override(observer, tmp_path, client):
    argv = observer.native_argv(client, "/tools/" + client, tmp_path, {"model": "chosen", "model_reasoning_effort": "high"})
    assert not any(flag in argv for flag in ("--yolo", "--disable-sandbox", "--dangerously-bypass-approvals-and-sandbox"))
    if client == "claude": assert "--safe-mode" in argv and argv[argv.index("--tools") + 1] == ""
    if client == "codex":
        assert "read-only" in argv and "--ignore-user-config" in argv and "shell_tool" in argv
        assert argv.index("exec") < argv.index("--ignore-user-config")
    if client == "muse": assert all(v in argv for v in ("--disable-write", "--disable-shell", "--disable-web-tools"))


def test_native_parsers_require_actual_completed_identity(observer):
    answer = {"bindings": {}, "controls": []}
    claude = [{"type": "system", "subtype": "init", "session_id": "native", "model": "configured", "tools": []},
              {"type": "result", "subtype": "success", "is_error": False, "session_id": "native", "result": json.dumps(answer), "total_cost_usd": 0.1}]
    assert observer.parse_native("claude", claude)["response"] == answer
    with pytest.raises(ValueError): observer.parse_native("claude", claude[1:])
    codex = [{"type": "thread.started", "thread_id": "native"}, {"type": "turn.started"},
             {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(answer)}},
             {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 4}}]
    assert observer.parse_native("codex", codex)["session_id"] == "native"
    with pytest.raises(ValueError): observer.parse_native("codex", codex[:-1])


def test_muse_parser_binds_native_completion_and_rejects_tool_activity(observer):
    def event(seq, kind, payload):
        return {"schema_version": 1, "stream": {"kind": "session", "id": "native"}, "sequence": seq,
                "causation_id": "command", "payload_type": kind,
                "payload": {"command_id": "command", **payload}}
    events = [event(1, "runtime.command.accepted", {"kind": "command_accepted", "command_kind": "turn.submit"}),
              event(2, "turn.input.user", {"kind": "turn_input_user", "prompt": "review"}),
              event(3, "run.terminal.completed", {"kind": "run_terminal", "terminal": "completed",
                  "run_stream": {"kind": "run", "id": "command"}, "text": '{"answer":5}', "reason": None})]
    assert observer.parse_native("muse", events)["response"] == {"answer": 5}
    with pytest.raises(ValueError): observer.parse_native("muse", events[:-1])
    events.insert(2, event(2.5, "runtime.session", {"kind": "run", "event": {"kind": "assistant_tool_calls_committed", "tool_calls": [{"name": "read_file"}]}}))
    with pytest.raises(ValueError): observer.parse_native("muse", events)


def test_review_consumes_real_workflow_verification_reservation(observer, review, engine, world, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import workflow
    workflow.register_commands(engine.register_command)
    state = create(engine, world)
    state = command(engine, world, state, "workflow.configure", {"dimensions": {
        "domains": ["writing"], "uncertainty": "low", "effect": "local-reversible",
        "horizon": "session", "parallelizable": False}})
    state = command(engine, world, state, "workflow.budget", {"limits": {
        "wall_millis": {"limit": 120000, "enforcement": "hard"},
        "usd_micros": {"limit": 2000000, "enforcement": "forecast"}},
        "deadline": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()})
    state = command(engine, world, state, "workflow.reserve", {"reservation_id": "review-one",
        "amounts": {"wall_millis": 120000, "usd_micros": 2000000}, "category": "verification"})
    context, args = review
    context["state"]["extensions"]["workflow"]["budget"] = state["extensions"]["workflow"]["budget"]
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw: result(prompt))
    assert observer.observe_native_cli_review(context, args)["passed"] is True


def test_muse_boundary_uses_empty_toolset_and_native_auth_reference(observer, tmp_path):
    source = tmp_path / 'original-config' / 'muse'
    source.mkdir(parents=True)
    settings = {'schema_version': 1, 'provider': 'meta', 'model': 'user-selected',
                'reasoning_effort': 'max', 'run': {'toolset': ['read_file']},
                'private_unrelated_setting': 'do-not-copy'}
    (source / 'settings.json').write_text(json.dumps(settings))
    (source / 'auth.json').write_text('synthetic-auth-only')
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    scratch = tmp_path / 'review'; scratch.mkdir()
    env, proof = observer.prepare_muse_boundary(scratch, {'XDG_CONFIG_HOME': str(source.parent), 'PATH': '/bin'})
    config = Path(env['XDG_CONFIG_HOME']) / 'muse'
    selected = json.loads((config / 'settings.json').read_text())
    assert selected == {'schema_version': 1, 'provider': 'meta', 'model': 'user-selected',
                        'reasoning_effort': 'max', 'run': {'toolset': [], 'reminder_roster': {'agents': []}}}
    assert (config / 'auth.json').is_symlink()
    assert (config / 'auth.json').resolve() == source / 'auth.json'
    assert not (config / 'trust.json').exists()
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original
    assert proof['model'] == 'user-selected'
    assert all(Path(env[k]).is_relative_to(scratch) for k in ['XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'])
    assert not list(Path(env['XDG_DATA_HOME']).rglob('*'))


@pytest.mark.parametrize('changed', [None, {'model': None}, {'provider': 'echo'}, {'reasoning_effort': 3}])
def test_muse_boundary_rejects_unresolved_original_native_selection(observer, tmp_path, changed):
    source = tmp_path / 'config' / 'muse'; source.mkdir(parents=True)
    settings = {'schema_version': 1, 'provider': 'meta', 'model': 'chosen', 'reasoning_effort': 'max'}
    if changed is None:
        (source / 'settings.json').write_text('{bad')
    else:
        settings.update(changed); (source / 'settings.json').write_text(json.dumps(settings))
    (source / 'auth.json').write_text('synthetic')
    scratch = tmp_path / 'review'; scratch.mkdir()
    with pytest.raises(ValueError):
        observer.prepare_muse_boundary(scratch, {'XDG_CONFIG_HOME': str(source.parent)})


def muse_runtime_log(tmp_path, toolsets):
    session = '019c0000-0000-7000-8000-000000000001'
    path = tmp_path / 'muse' / 'sessions' / '2026' / '09' / '24' / session / 'session.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [{'stream': {'kind': 'session', 'id': session}, 'sequence': i + 1,
               'payload_type': 'runtime.session', 'payload': {'event': {'kind': 'model_request_configured',
               'toolset': toolset, 'reminder_roster': {'source': 'settings', 'agents': []}}}} for i, toolset in enumerate(toolsets)]
    path.write_text(''.join(json.dumps(e) + '\n' for e in events))
    return session


@pytest.mark.parametrize('toolsets', [[], [{'source': 'default', 'mode': 'all', 'active_tools': []}],
    [{'source': 'settings', 'mode': 'named', 'active_tools': ['read_file']}],
    [{'source': 'settings', 'mode': 'named', 'active_tools': []},
     {'source': 'settings', 'mode': 'named', 'active_tools': ['cron_create']}],
    [{'source': 'settings', 'mode': 'named'}]])
def test_muse_boundary_requires_actual_empty_native_toolset(observer, tmp_path, toolsets):
    session = muse_runtime_log(tmp_path, toolsets)
    with pytest.raises(ValueError): observer.verify_muse_boundary(tmp_path, session)


def test_muse_boundary_accepts_native_empty_toolset_and_rejects_changed_identity(observer, tmp_path):
    session = muse_runtime_log(tmp_path, [{'source': 'settings', 'mode': 'named', 'active_tools': []}])
    proof = observer.verify_muse_boundary(tmp_path, session)
    assert proof['toolset'] == [] and len(proof['source_digest']) == 64
    with pytest.raises(ValueError): observer.verify_muse_boundary(tmp_path, '../other')


def test_muse_paid_request_never_starts_if_offline_boundary_preflight_fails(observer, tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(observer.shutil, 'which', lambda _: '/native/muse')
    monkeypatch.setattr(observer, 'prepare_muse_boundary', lambda scratch, env: (env, {'model': 'chosen'}), raising=False)
    def preflight(*args, **kwargs):
        called.append('preflight'); raise ValueError('tools remain available')
    monkeypatch.setattr(observer, 'preflight_muse_boundary', preflight, raising=False)
    monkeypatch.setattr(observer, '_bounded_process', lambda *a, **k: pytest.fail('paid call must not run'))
    with pytest.raises(ValueError, match='tools remain available'):
        observer.execute_native('muse', 'private registered input', timeout_seconds=45, max_cost_usd=1)
    assert called == ['preflight']


@pytest.mark.parametrize('roster', [None, {'source': 'runtime', 'agents': []}, {'source': 'settings', 'agents': [{'id': 'extra'}]}])
def test_muse_boundary_rejects_unbounded_reminder_lane(observer, tmp_path, roster):
    session = muse_runtime_log(tmp_path, [{'source': 'settings', 'mode': 'named', 'active_tools': []}])
    path = next(tmp_path.rglob('session.jsonl'))
    event = json.loads(path.read_text())
    event['payload']['event']['reminder_roster'] = roster
    path.write_text(json.dumps(event) + '\n')
    with pytest.raises(ValueError): observer.verify_muse_boundary(tmp_path, session)


def test_muse_boundary_accepts_native_retained_permission_frame(observer, tmp_path):
    session = muse_runtime_log(tmp_path, [{'source': 'settings', 'mode': 'named', 'active_tools': []}])
    path = next(tmp_path.rglob('session.jsonl'))
    configured = json.loads(path.read_text()); configured['sequence'] = 3
    records = [{'stream': {'kind': 'session', 'id': session}, 'sequence': i + 1,
                'payload_type': kind, 'payload': {}} for i, kind in enumerate(
                ['runtime.session.permission_format_declared', 'runtime.session.permission_profile_committed'])]
    frame = {'retained_frame': 'session_permission_transaction', 'frame_schema_version': 1,
             'outer_log_ordinal': 1, 'transaction_id': 'transaction',
             'children': [{'child_index': i, 'record_json': json.dumps(record)} for i, record in enumerate(records)]}
    path.write_text(json.dumps(frame) + '\n' + json.dumps(configured) + '\n')
    assert observer.verify_muse_boundary(tmp_path, session)['toolset'] == []


@pytest.mark.parametrize('bad', ['foreign-identity', 'bad-index', 'unknown-frame', 'non-string-record'])
def test_muse_boundary_rejects_invalid_native_permission_frame(observer, tmp_path, bad):
    session = muse_runtime_log(tmp_path, [{'source': 'settings', 'mode': 'named', 'active_tools': []}])
    path = next(tmp_path.rglob('session.jsonl')); configured = path.read_text()
    record = {'stream': {'kind': 'session', 'id': session}, 'sequence': 0,
              'payload_type': 'runtime.session.permission_format_declared', 'payload': {}}
    if bad == 'foreign-identity': record['stream']['id'] = 'different'
    frame = {'retained_frame': 'other' if bad == 'unknown-frame' else 'session_permission_transaction',
             'frame_schema_version': 1, 'outer_log_ordinal': 1, 'transaction_id': 'transaction',
             'children': [{'child_index': 1 if bad == 'bad-index' else 0,
                           'record_json': record if bad == 'non-string-record' else json.dumps(record)}]}
    path.write_text(json.dumps(frame) + '\n' + configured)
    with pytest.raises(ValueError): observer.verify_muse_boundary(tmp_path, session)


def domain_review_context(tmp_path, family="writing"):
    from test_domain_quality import make_package
    context, defects = make_package(tmp_path, family)
    context["state"]["extensions"] = {"workflow": {"budget": {
        "limits": {"usd_micros": {"enforcement": "forecast"}}, "reservations": {
            "review-domain": {"status": "reserved", "category": "verification",
                              "amounts": {"wall_millis": 120000, "usd_micros": 2000000}}}}}}
    return context, {"mode": "native-cli", "client": "claude", "criterion_id": "accept", "artifact_id": "draft",
                     "calibration_manifest_id": "gold", "reservation_id": "review-domain", "timeout_seconds": 120,
                     "max_cost_usd": 2}, defects


def domain_native_result(observer, client, prompt, defects, mutate=None, event_mutate=None):
    """Programmed domain judgments through the real native event parsers."""
    from test_domain_quality import assessment
    request = json.loads(prompt.split("\nREQUEST\n", 1)[1])
    documents = {doc["artifact_id"]: doc for doc in [request["artifact"], *request["sources"], *request["controls"]]}
    response = {"bindings": request["bindings"], "artifact_digest": request["artifact_digest"],
                "assessment": assessment(request["rubric"], documents, request["artifact"]["artifact_id"],
                                         defects.get(request["artifact"]["content"])),
                "controls": [{"artifact_id": doc["artifact_id"], "artifact_digest": doc["digest"],
                    "assessment": assessment(request["rubric"], documents, doc["artifact_id"], defects.get(doc["content"]))}
                    for doc in request["controls"]]}
    if mutate: mutate(response)
    if client == "claude":
        events = [{"type": "system", "subtype": "init", "session_id": "domain-child", "model": "configured", "tools": []},
                  {"type": "result", "subtype": "success", "is_error": False, "session_id": "domain-child",
                   "result": json.dumps(response), "total_cost_usd": 0.1}]
    elif client == "codex":
        events = [{"type": "thread.started", "thread_id": "domain-child"},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(response)}},
                  {"type": "turn.completed", "usage": {"input_tokens": 30, "output_tokens": 20}}]
    else:
        events = [{"stream": {"kind": "session", "id": "domain-child"}, "sequence": index + 1,
                   "causation_id": "command", "payload_type": kind, "payload": payload} for index, (kind, payload) in enumerate([
            ("runtime.command.accepted", {"command_id": "command", "command_kind": "turn.submit"}),
            ("run.terminal.completed", {"command_id": "command", "kind": "run_terminal", "terminal": "completed",
                "run_stream": {"kind": "run", "id": "command"}, "reason": None, "text": json.dumps(response)})])]
    if event_mutate:
        event_mutate(events)
    parsed = observer.parse_native(client, events)
    return {**parsed, "returncode": 0, "wall_seconds": 1,
            "stdout_digest": hashlib.sha256(json.dumps(events).encode()).hexdigest()}


@pytest.mark.parametrize("position", ["before-thread", "after-completion", "before-turn",
                                      "duplicate-turn", "turn-before-thread", "turn-after-completion"])
def test_typed_native_route_rejects_codex_answer_outside_turn_lifecycle(observer, tmp_path, monkeypatch, position):
    context, args, defects = domain_review_context(tmp_path)
    args["client"] = "codex"
    def move_event(events):
        if position == "before-thread": events.insert(0, events.pop(1))
        if position == "after-completion": events.append(events.pop(1))
        if position == "before-turn": events.insert(2, {"type": "turn.started"})
        if position == "duplicate-turn": events[1:1] = [{"type": "turn.started"}, {"type": "turn.started"}]
        if position == "turn-before-thread": events.insert(0, {"type": "turn.started"})
        if position == "turn-after-completion": events.append({"type": "turn.started"})
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw:
                        domain_native_result(observer, client, prompt, defects, event_mutate=move_event))
    with pytest.raises(ValueError, match="turn|session"):
        observer.observe_native_cli_review(context, args)
    # Parsing fails before an admissible quality receipt can exist; the paid
    # attempt marker remains, following the unchanged interruption policy.
    assert context["evidence"] == {}
    assert (tmp_path / "resources/autopilot-runs/run-domain/native-review-attempts/review-domain.json").is_file()


@pytest.mark.parametrize("client", ["claude", "codex", "muse"])
@pytest.mark.parametrize("family", ["writing", "research"])
def test_typed_native_route_covers_sources_criteria_and_real_event_parser(observer, tmp_path, monkeypatch, client, family):
    import domain_quality
    context, args, defects = domain_review_context(tmp_path, family)
    args["client"] = client
    def execute(selected, prompt, **kw):
        assert '"expected"' not in prompt and '"gold"' not in prompt
        assert "accepted_requirement" in prompt and "criterion_id" in prompt and "UNKNOWN" in prompt
        assert "untrusted data" in prompt
        if family == "writing": assert "stylistic preference" in prompt and "distinctive insight" in prompt
        return domain_native_result(observer, selected, prompt, defects)
    monkeypatch.setattr(observer, "execute_native", execute)
    actual = observer.observe_native_cli_review(context, args)
    assert actual["passed"] is True and actual["calibrated"] is True
    assert actual["reviewer"] == client + "-cli:domain-child"
    assert domain_quality.rederive_review(actual, context) == "PASS"
    assert len(actual["calibration"]["result"]["controls"]) == len(domain_quality.DIMENSIONS[family]) + 1
    assert (tmp_path / "resources/autopilot-runs/run-domain/native-review-attempts/review-domain.json").is_file()
    with pytest.raises(ValueError, match="attempt"):
        observer.observe_native_cli_review(context, args)


@pytest.mark.parametrize("case,expected", [("unknown", "UNKNOWN"), ("contradiction", "FAIL"), ("style", "PASS")])
def test_native_rich_unknown_contradiction_and_style_survive_parser(observer, tmp_path, monkeypatch, case, expected):
    import domain_quality
    import workflow
    context, args, defects = domain_review_context(tmp_path)
    def mutate(response):
        row = response["assessment"]["criteria"][0 if case != "style" else -1]
        if case == "unknown": row["verdict"] = "UNKNOWN"
        if case == "contradiction": row["evidence"][0]["relation"] = "contradicts"
        if case == "style":
            row.update(verdict="FAIL", findings=[{"kind": "preference", "description": "Prefer no fragments", "evidence_indices": [0]}])
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw: domain_native_result(observer, client, prompt, defects, mutate))
    actual = observer.observe_native_cli_review(context, args)
    assert actual["calibrated"] is True
    assert domain_quality.rederive_review(actual, context) == expected
    assert workflow.quality_receipt_verdict(actual, True, context) == expected
    assert workflow._observed_quality("writing", actual["observations"]) is (expected == "PASS")


@pytest.mark.parametrize("case,kind", [("missed-defect", "missed_defect"), ("false-rejection", "false_rejection"), ("unknown", "unknown")])
def test_native_calibration_retains_dimensional_false_acceptance_rejection_unknown(observer, tmp_path, monkeypatch, case, kind):
    import workflow
    context, args, defects = domain_review_context(tmp_path)
    def mutate(response):
        if case == "missed-defect":
            row = response["controls"][1]["assessment"]["criteria"][0]
            row.update(verdict="PASS", findings=[])
        else:
            row = response["controls"][0]["assessment"]["criteria"][-1]
            row["verdict"] = "UNKNOWN" if case == "unknown" else "FAIL"
            if case == "false-rejection":
                row["findings"] = [{"kind": "defect", "description": "Synthetic mistaken voice judgment", "evidence_indices": [0]}]
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw: domain_native_result(observer, client, prompt, defects, mutate))
    actual = observer.observe_native_cli_review(context, args)
    assert actual["calibrated"] is False and actual["passed"] is False
    assert actual["calibration"]["result"]["verdict"] == "FAIL"
    assert actual["calibration"]["result"]["mismatches"][0]["kind"] == kind
    assert workflow.quality_receipt_verdict(actual, True, context) == "UNKNOWN"


@pytest.mark.parametrize("case", ["quote", "omitted-criterion", "duplicate-control", "mutated-source", "mutated-gold"])
def test_native_route_rejects_missing_or_changed_evidence(observer, tmp_path, monkeypatch, case):
    context, args, defects = domain_review_context(tmp_path)
    def mutate(response):
        if case == "quote": response["assessment"]["criteria"][0]["evidence"][0]["quote"] = "A fabricated quotation"
        if case == "omitted-criterion": response["assessment"]["criteria"].pop()
        if case == "duplicate-control": response["controls"][-1] = response["controls"][0]
        if case == "mutated-source": (tmp_path / "brief.txt").write_text("different source")
        if case == "mutated-gold": (tmp_path / "gold.txt").write_text("different gold")
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw: domain_native_result(observer, client, prompt, defects, mutate))
    with pytest.raises(ValueError): observer.observe_native_cli_review(context, args)


def test_incomplete_dimension_calibration_prevents_native_invocation(observer, tmp_path, monkeypatch):
    from test_domain_quality import add_document
    context, args, _ = domain_review_context(tmp_path)
    manifest = json.loads((tmp_path / "gold.txt").read_text())
    manifest["controls"].pop()
    add_document(context, "gold", json.dumps(manifest))
    monkeypatch.setattr(observer, "execute_native", lambda *a, **kw: pytest.fail("invalid calibration cannot launch a provider"))
    with pytest.raises(ValueError, match="dimension"):
        observer.observe_native_cli_review(context, args)
    assert not (tmp_path / "resources").exists()

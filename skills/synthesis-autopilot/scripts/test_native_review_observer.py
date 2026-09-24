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

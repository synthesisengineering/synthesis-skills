"""Stop feedback is bounded without converting failed protection into success."""
import json
import fcntl
import os
import subprocess
import time
from pathlib import Path

import pytest

import release_runtime as runtime
import system_contract
from test_release_runtime import active, replace, SCRIPT  # noqa: F401


@pytest.fixture(autouse=True)
def isolated_launcher_environment(monkeypatch):
    # CLI entrypoints export the descriptor for their child. Direct function
    # fixtures must restore that export before unrelated installer tests run.
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", os.environ.get("SYNTHESIS_ACTIVE_DESCRIPTOR", ""))


def event(**changes):
    return {"hook_event_name": "Stop", "session_id": "fixture-session",
            "turn_id": "fixture-turn", "stop_hook_active": False, **changes}


def launch(active, payload, *args):
    pointer, _, data = active
    return subprocess.run([data["launcher"]["path"], "exec-public", "--hook-event", "Stop",
                           *args, SCRIPT], input=payload, capture_output=True, timeout=5)


def assert_terminal(result):
    assert result.returncode == 0, result.stderr.decode()
    output = json.loads(result.stdout)
    assert output["continue"] is False
    assert output["stopReason"]
    assert "UNRESOLVED" in output["systemMessage"]
    assert "decision" not in output
    return output


def test_stop_failure_without_owner_reservation_is_terminal_across_turns():
    first = runtime.stop_failure(event(), "unfinished", "status=UNKNOWN")
    assert first["continue"] is False
    assert "UNKNOWN" in first["systemMessage"]
    assert "decision" not in first
    for reason in ("unfinished", "changed error family"):
        repeated = runtime.stop_failure(event(stop_hook_active=True), reason, "status=UNKNOWN")
        assert repeated["continue"] is False
        assert "UNKNOWN" in repeated["systemMessage"]
        assert "decision" not in repeated
    fresh = runtime.stop_failure(event(turn_id="new-human-turn"), "unfinished")
    assert fresh["continue"] is False
    assert "decision" not in fresh


@pytest.mark.parametrize("payload", [None, {}, [], event(session_id=""), event(stop_hook_active="false")])
def test_unidentifiable_stop_is_terminal(payload):
    assert runtime.stop_failure(payload, "unverified")["continue"] is False


@pytest.mark.parametrize("damage", ["missing-descriptor", "digest", "interpreter", "entrypoint"])
def test_embedded_launcher_dependency_failure_is_terminal(active, damage):
    pointer, root, data = active
    if damage == "missing-descriptor":
        pointer.unlink()
    elif damage == "digest":
        replace(pointer, data, content_digest="0" * 64)
    elif damage == "interpreter":
        replace(pointer, data, interpreter={**data["interpreter"], "sha256": "0" * 64})
    else:
        (root / "skills" / SCRIPT).unlink()
    assert_terminal(launch(active, json.dumps(event()).encode()))


@pytest.mark.parametrize("payload", [b"broken", b"[]", b"{}", b"\xff"])
def test_embedded_launcher_bad_native_input_is_terminal(active, payload):
    assert_terminal(launch(active, payload))


def child(active, program):
    pointer, root, data = active
    (root / "skills" / SCRIPT).write_text(program)
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))


@pytest.mark.parametrize("program", ["import sys; sys.exit(2)",
    "print('not native JSON')", "print('[]')", "print('{\"decision\":\"block\",\"reason\":\"fix it\"}')"])
def test_embedded_launcher_repeated_child_failure_is_terminal(active, program):
    child(active, program)
    assert_terminal(launch(active, json.dumps(event(stop_hook_active=True)).encode()))


def test_embedded_launcher_timeout_is_terminal_on_first_failure(active):
    child(active, "import time; time.sleep(10)")
    assert_terminal(launch(active, json.dumps(event()).encode(), "--timeout-seconds", "0.02"))


def test_healthy_repeated_stop_preserves_child_result(active):
    child(active, "print('{\"systemMessage\":\"HEALTHY\"}')")
    result = launch(active, json.dumps(event(stop_hook_active=True)).encode())
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"systemMessage": "HEALTHY"}


def test_pretooluse_failure_stays_nonzero_and_never_terminalizes(active):
    pointer, _, data = active
    pointer.unlink()
    result = subprocess.run([data["launcher"]["path"], "exec-public", SCRIPT],
        input=json.dumps({"hook_event_name": "PreToolUse"}).encode(), capture_output=True, timeout=5)
    assert result.returncode == 2
    assert b'"continue"' not in result.stdout


@pytest.mark.parametrize("native_event", ["PreToolUse", "PermissionRequest"])
def test_misconfigured_stop_route_cannot_weaken_native_tool_denial(active, native_event):
    result = launch(active, json.dumps({"hook_event_name": native_event, "session_id": "fixture"}).encode())
    assert result.returncode == 2
    assert b'"continue"' not in result.stdout
    assert b"event" in result.stderr


@pytest.mark.parametrize("native_event", ["UnknownEvent", "", 42])
@pytest.mark.parametrize("invalid_arguments", [False, True])
def test_declared_stop_with_malformed_event_stays_terminal(active, native_event, invalid_arguments):
    arguments = ["--unknown-option"] if invalid_arguments else []
    assert_terminal(launch(active, json.dumps(event(hook_event_name=native_event)).encode(), *arguments))


def test_parser_failure_cannot_weaken_native_permission_request(active):
    result = launch(active, json.dumps({"hook_event_name": "PermissionRequest"}).encode(), "--unknown-option")
    assert result.returncode == 2 and result.stdout == b""


PARSE_FAILURE_ARGUMENTS = [
    ("--unknown-option",),
    ("--timeout-seconds", "not-a-number"),
    ("--timeout-seconds", "nan"),
    ("--timeout-seconds", "-1"),
    ("--stdin-wait-seconds", "not-a-number"),
    ("--stdin-wait-seconds", "nan"),
    ("--stdin-wait-seconds", "-1"),
    ("--success-exit-code", "2"),
    ("--hook-event", "UnknownEvent"),
]


@pytest.mark.parametrize("arguments", PARSE_FAILURE_ARGUMENTS)
@pytest.mark.parametrize("repeated", [False, True])
def test_native_stop_parser_failure_is_terminal(active, arguments, repeated):
    """Parser failures occur before child imports but still have native input."""
    result = launch(active, json.dumps(event(stop_hook_active=repeated)).encode(), *arguments)
    output = assert_terminal(result)
    assert "argument" in output["stopReason"].lower()


@pytest.mark.parametrize("arguments", PARSE_FAILURE_ARGUMENTS)
def test_nonstop_parser_failure_stays_nonzero(active, arguments):
    result = launch(active, json.dumps({"hook_event_name": "PreToolUse"}).encode(), *arguments)
    assert result.returncode == 2
    assert result.stdout == b""


@pytest.mark.parametrize("arguments", [[], ["not-a-declared/script.py"], ["--timeout-seconds"]])
def test_native_stop_parser_failure_without_declared_event_is_terminal(active, arguments):
    _, _, data = active
    result = subprocess.run([data["launcher"]["path"], "exec-public", *arguments],
                            input=json.dumps(event()).encode(), capture_output=True, timeout=5)
    assert_terminal(result)


def test_declared_stop_parser_failure_with_bad_input_is_terminal(active):
    assert_terminal(launch(active, b"unreadable input", "--unknown-option"))


def test_parser_failure_cannot_infer_stop_from_child_arguments(active):
    _, _, data = active
    result = subprocess.run([data["launcher"]["path"], "exec-public", "unknown/script.py",
                             "--hook-event", "Stop"], input=b"broken", capture_output=True, timeout=5)
    assert result.returncode == 2 and result.stdout == b""


def test_parser_failure_fallback_input_wait_is_bounded(active):
    _, _, data = active
    reader, writer = os.pipe()
    try:
        os.write(writer, b'{"hook_event_name":"Stop"')
        started = time.monotonic()
        result = subprocess.run([data["launcher"]["path"], "exec-public", "--hook-event", "Stop",
                                 "--timeout-seconds", "0.03", "--unknown-option", SCRIPT],
                                stdin=reader, capture_output=True, timeout=1)
        assert time.monotonic() - started < 0.8
        assert_terminal(result)
    finally:
        os.close(reader)
        os.close(writer)


def test_launcher_help_remains_zero_without_reading_native_input(active):
    _, _, data = active
    reader, writer = os.pipe()
    try:
        result = subprocess.run([data["launcher"]["path"], "exec-public", "--help"],
                                stdin=reader, capture_output=True, timeout=1)
        assert result.returncode == 0
        assert result.stdout.startswith(b"usage:")
        assert b'"continue"' not in result.stdout
    finally:
        os.close(reader)
        os.close(writer)


def test_stalled_pipe_is_bounded_and_never_runs_a_child(active):
    pointer, _, data = active
    reader, writer = os.pipe()
    try:
        os.write(writer, b'{"hook_event_name":"Stop"')
        started = time.monotonic()
        result = subprocess.run([data["launcher"]["path"], "exec-public", "--hook-event", "Stop",
            "--stdin-wait-seconds", "0.03", SCRIPT], stdin=reader, capture_output=True, timeout=2)
        assert time.monotonic() - started < 1
        assert_terminal(result)
    finally:
        os.close(reader)
        os.close(writer)


def test_held_activation_lock_is_terminal_without_waiting_for_host_timeout(active):
    pointer, _, _ = active
    with pointer.with_name(pointer.name + ".lock").open("rb") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        started = time.monotonic()
        result = launch(active, json.dumps(event()).encode())
        assert time.monotonic() - started < 1
        assert_terminal(result)


def test_stop_execution_budget_includes_input_and_verification(active, monkeypatch, capsys):
    pointer, _, _ = active
    clock = [10.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    def read(_):
        clock[0] += 4.0
        return json.dumps(event()).encode()
    def verify(_):
        clock[0] += 4.0
        return {}
    monkeypatch.setattr(runtime, "read_payload", read)
    monkeypatch.setattr(runtime, "verified_release", verify)
    def execute(*args, timeout):
        assert timeout == 12.0
        return subprocess.CompletedProcess([], 0, b'{}', b'')
    monkeypatch.setattr(runtime, "execute", execute)
    assert runtime.exec_public_main(["--hook-event", "Stop", "--timeout-seconds", "20", SCRIPT], pointer) == 0


@pytest.mark.parametrize("hook_event", ["Stop", "PreToolUse"])
def test_exhausted_total_deadline_never_dispatches_worker(active, monkeypatch, capsys, hook_event):
    pointer, _, _ = active
    clock = [10.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event(hook_event_name=hook_event)).encode())
    def verify(_):
        clock[0] += 21.0
        return {}
    def forbidden(*args, **kwargs):
        pytest.fail("expired launcher must not dispatch a worker")
    monkeypatch.setattr(runtime, "verified_release", verify)
    monkeypatch.setattr(runtime, "execute", forbidden)
    code = runtime.exec_public_main(["--timeout-seconds", "20", SCRIPT], pointer)
    output = capsys.readouterr()
    if hook_event == "Stop":
        assert code == 0
        result = json.loads(output.out)
        assert result["continue"] is False and "decision" not in result
        assert "UNRESOLVED" in result["systemMessage"]
    else:
        assert code == 2 and not output.out
    assert "deadline" in output.err


def test_timeout_bounds_descendants_holding_output_pipes(active):
    child(active, "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)'])\ntime.sleep(2)\n")
    started = time.monotonic()
    assert_terminal(launch(active, json.dumps(event()).encode(), "--timeout-seconds", "0.15"))
    assert time.monotonic() - started < 1.2


@pytest.mark.parametrize("changes", [{"hook_event_name": []}, {"session_id": []},
                                    {"session_id": 1}, {"stop_hook_active": {} }])
def test_invalid_stop_field_types_are_terminal(active, changes):
    assert_terminal(launch(active, json.dumps(event(**changes)).encode()))


def test_configured_stop_launchers_have_explicit_event_and_deadline_margin():
    root = Path(__file__).resolve().parents[3]
    hooks = json.loads((root / "hooks/hooks.json").read_text())["hooks"]
    import shlex
    for group in hooks["Stop"]:
        for hook in group["hooks"]:
            argv = shlex.split(hook["command"])
            assert argv[argv.index("--hook-event") + 1] == "Stop"
            inner = float(argv[argv.index("--timeout-seconds") + 1])
            assert 0 < inner <= hook["timeout"] - 2


def test_slow_verification_is_interrupted_before_native_host_deadline(active, monkeypatch, capsys):
    pointer, _, _ = active
    monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event()).encode())
    monkeypatch.setattr(runtime, "verified_release", lambda _: time.sleep(0.3))
    started = time.monotonic()
    assert runtime.exec_public_main(["--hook-event", "Stop", "--timeout-seconds", "0.03", SCRIPT], pointer) == 0
    assert time.monotonic() - started < 0.2
    assert json.loads(capsys.readouterr().out)["continue"] is False


@pytest.mark.parametrize("output", [{'decision': 'approve'}, {'suppressOutput': 'true'},
                                    {'hookSpecificOutput': {}}, {'decision': []}])
def test_invalid_native_output_fields_terminalize_without_losing_failure(output):
    result = subprocess.CompletedProcess([], 0, json.dumps(output).encode(), b'')
    wire = runtime.stop_result(event(), result)
    assert wire["continue"] is False
    assert "UNRESOLVED" in wire["systemMessage"]


def test_deadline_cannot_be_swallowed_by_dependency_value_error_recovery(active, monkeypatch, capsys):
    pointer, _, _ = active
    monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event()).encode())
    recovered = []
    def slow_verifier(_):
        try:
            time.sleep(0.3)
        except ValueError:
            recovered.append(True)
            time.sleep(0.3)
        return {}
    monkeypatch.setattr(runtime, "verified_release", slow_verifier)
    started = time.monotonic()
    assert runtime.exec_public_main(["--hook-event", "Stop", "--timeout-seconds", "0.03", SCRIPT], pointer) == 0
    assert time.monotonic() - started < 0.2
    assert not recovered
    assert json.loads(capsys.readouterr().out)["continue"] is False


@pytest.mark.parametrize("boundary", ["timeout", "invalid-input", "child-success", "child-failure", "stderr"])
def test_execution_alarm_cannot_interrupt_terminal_response(monkeypatch, capsys, boundary):
    """Deliver the armed alarm at the old output boundary without wall-clock luck."""
    import signal

    payload = json.dumps(event()).encode() if boundary != "invalid-input" else b"broken"
    monkeypatch.setattr(runtime, "read_payload", lambda _: payload)
    monkeypatch.setattr(runtime, "verified_release", lambda _: {})
    monkeypatch.setattr(runtime, "command", lambda *args: ["synthetic-worker"])
    observed = []
    if boundary == "timeout":
        def run(*args, **kwargs):
            observed.append("subprocess.TimeoutExpired")
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        monkeypatch.setattr(runtime.subprocess, "run", run)
    else:
        code = 2 if boundary == "child-failure" else 0
        monkeypatch.setattr(runtime, "execute", lambda *args, **kwargs:
                            subprocess.CompletedProcess([], code, b'{"systemMessage":"HEALTHY"}', b"diagnostic"))
    original_failure = runtime.stop_failure
    def failure(*args, **kwargs):
        if boundary == "timeout":
            assert "failed to start or finish" in args[1]
            observed.append("RuntimeContractError")
        return original_failure(*args, **kwargs)
    monkeypatch.setattr(runtime, "stop_failure", failure)

    def fire_if_armed():
        # The real timer/installed handler are the oracle. Production formatting
        # must be outside that scope, rather than catching a second alarm/retrying.
        if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
            observed.append("alarm-during-response")
            signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)

    original_dumps = runtime.json.dumps
    def dumps(value, *args, **kwargs):
        if boundary != "stderr":
            fire_if_armed()
        return original_dumps(value, *args, **kwargs)
    monkeypatch.setattr(runtime.json, "dumps", dumps)
    if boundary == "stderr":
        class DiagnosticStream:
            @property
            def buffer(self):
                return self
            def write(self, value):
                fire_if_armed()
                return len(value)
            def flush(self):
                pass
        monkeypatch.setattr(runtime.sys, "stderr", DiagnosticStream())
    result = runtime.exec_public_main(["--hook-event", "Stop", SCRIPT], Path("/synthetic/descriptor"))
    captured = capsys.readouterr()
    assert result == 0
    assert len(captured.out.splitlines()) == 1
    output = json.loads(captured.out)
    if boundary in {"child-success", "stderr"}:
        assert output == {"systemMessage": "HEALTHY"}
    else:
        assert output["continue"] is False and output["stopReason"]
        if boundary == "child-failure":
            assert output["systemMessage"] == "HEALTHY"  # Preserve the child diagnostic verbatim.
        else:
            assert "UNRESOLVED" in output["systemMessage"]
    assert "alarm-during-response" not in observed
    if boundary == "timeout":
        assert observed == ["subprocess.TimeoutExpired", "RuntimeContractError"]


@pytest.mark.parametrize("event_name", ["Stop", "PreToolUse", "PermissionRequest"])
def test_execution_deadline_still_bounds_stop_policy_and_worker(monkeypatch, capsys, event_name):
    import signal

    monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event(hook_event_name=event_name)).encode())
    monkeypatch.setattr(runtime, "verified_release", lambda _: {})
    def execute(*args, **kwargs):
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
        if event_name != "Stop":
            signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)
        return subprocess.CompletedProcess([], 0, b'{"decision":"block","reason":"repair","_synthesis_policy":{}}', b"")
    def policy(*args, **kwargs):
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
        signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)
    monkeypatch.setattr(runtime, "execute", execute)
    monkeypatch.setattr(runtime, "_policy_reservation", policy)
    code = runtime.exec_public_main([SCRIPT], Path("/synthetic/descriptor"))
    output = capsys.readouterr()
    assert "deadline" in output.err
    if event_name == "Stop":
        assert code == 0 and json.loads(output.out)["continue"] is False
        assert len(output.out.splitlines()) == 1
    else:
        assert code == 2 and output.out == ""


@pytest.mark.parametrize("branch", ["success", "timeout", "invalid-input", "invalid-arguments"])
def test_launcher_restores_caller_alarm_ownership(monkeypatch, capsys, branch):
    import signal

    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    calls = []
    def caller(signum, frame):
        calls.append(signum)
    signal.signal(signal.SIGALRM, caller)
    signal.setitimer(signal.ITIMER_REAL, 20, 7)
    started = time.monotonic()
    try:
        payload = b"broken" if branch == "invalid-input" else json.dumps(event()).encode()
        monkeypatch.setattr(runtime, "read_payload", lambda _: payload)
        monkeypatch.setattr(runtime, "verified_release", lambda _: {})
        def execute(*args, **kwargs):
            if branch == "timeout":
                raise runtime.RuntimeContractError("synthetic worker timeout")
            return subprocess.CompletedProcess([], 0, b'{}', b'')
        monkeypatch.setattr(runtime, "execute", execute)
        arguments = ["--hook-event", "Stop"]
        if branch == "invalid-arguments":
            arguments += ["--unknown-option"]
        assert runtime.exec_public_main([*arguments, SCRIPT], Path("/synthetic/descriptor")) == 0
        elapsed = time.monotonic() - started
        remaining, interval = signal.getitimer(signal.ITIMER_REAL)
        assert signal.getsignal(signal.SIGALRM) is caller
        assert 20 - elapsed - 0.1 <= remaining <= 20
        assert interval == 7
        assert not calls
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


def test_queued_execution_alarm_does_not_escape_to_caller(monkeypatch, capsys):
    import signal

    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    calls = []
    def caller(signum, frame):
        calls.append(signum)
    signal.signal(signal.SIGALRM, caller)
    try:
        monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event()).encode())
        monkeypatch.setattr(runtime, "verified_release", lambda _: {})
        def execute(*args, **kwargs):
            # Queue precisely the launcher-owned alarm while delivery is blocked.
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
            os.kill(os.getpid(), signal.SIGALRM)
            assert signal.SIGALRM in signal.sigpending()
            return subprocess.CompletedProcess([], 0, b'{}', b'')
        monkeypatch.setattr(runtime, "execute", execute)
        assert runtime.exec_public_main(["--hook-event", "Stop", SCRIPT], Path("/synthetic/descriptor")) == 0
        assert signal.getsignal(signal.SIGALRM) is caller
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == old_mask | {signal.SIGALRM}
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        assert calls == []
        assert json.loads(capsys.readouterr().out)["continue"] is False
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if signal.SIGALRM in signal.sigpending():
            signal.sigwait({signal.SIGALRM})
        signal.signal(signal.SIGALRM, old_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


def test_inherited_alarm_mask_cannot_disable_execution_deadline(monkeypatch, capsys):
    import signal

    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    try:
        monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event()).encode())
        monkeypatch.setattr(runtime, "verified_release", lambda _: time.sleep(0.3))
        started = time.monotonic()
        code = runtime.exec_public_main(["--hook-event", "Stop", "--timeout-seconds", "0.03", SCRIPT],
                                        Path("/synthetic/descriptor"))
        assert code == 0 and time.monotonic() - started < 0.2
        assert json.loads(capsys.readouterr().out)["continue"] is False
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == previous_mask | {signal.SIGALRM}
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def test_pending_caller_alarm_is_not_consumed_or_reassigned(monkeypatch, capsys):
    import signal

    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    calls = []
    signal.signal(signal.SIGALRM, lambda signum, frame: calls.append(signum))
    try:
        os.kill(os.getpid(), signal.SIGALRM)
        def forbidden(*args, **kwargs):
            pytest.fail("pending caller alarm must refuse before reading input or dispatch")
        monkeypatch.setattr(runtime, "read_payload", forbidden)
        monkeypatch.setattr(runtime, "execute", forbidden)
        assert runtime.exec_public_main(["--hook-event", "Stop", SCRIPT], Path("/synthetic/descriptor")) == 0
        assert signal.SIGALRM in signal.sigpending()
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        assert calls == [signal.SIGALRM]
        assert "caller alarm" in json.loads(capsys.readouterr().out)["stopReason"]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if signal.SIGALRM in signal.sigpending():
            signal.sigwait({signal.SIGALRM})
        signal.signal(signal.SIGALRM, old_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


def test_unexpected_worker_exception_restores_timer_without_success(monkeypatch, capsys):
    import signal

    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    def caller(signum, frame):
        raise AssertionError("caller timer should not expire during this control")
    signal.signal(signal.SIGALRM, caller)
    signal.setitimer(signal.ITIMER_REAL, 20, 7)
    try:
        monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event()).encode())
        monkeypatch.setattr(runtime, "verified_release", lambda _: {})
        def broken(*args, **kwargs):
            raise LookupError("unclassified worker failure")
        monkeypatch.setattr(runtime, "execute", broken)
        with pytest.raises(LookupError, match="unclassified"):
            runtime.exec_public_main(["--hook-event", "Stop", SCRIPT], Path("/synthetic/descriptor"))
        assert capsys.readouterr().out == ""
        assert signal.getsignal(signal.SIGALRM) is caller
        remaining, interval = signal.getitimer(signal.ITIMER_REAL)
        assert 19 < remaining <= 20 and interval == 7
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, *old_timer)


@pytest.mark.parametrize("event_name", ["Stop", "SubagentStop", "PreToolUse", "PermissionRequest"])
def test_caught_execution_deadline_cannot_authorize_result(monkeypatch, capsys, event_name):
    payload = {"hook_event_name": event_name, "session_id": "sticky-fixture", "turn_id": "sticky-turn", "stop_hook_active": False}
    monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(payload).encode())
    monkeypatch.setattr(runtime, "verified_release", lambda _: {})
    caught = []
    def catches_deadline(*args, **kwargs):
        try:
            time.sleep(0.2)
        except runtime.ExecutionDeadline:
            caught.append("expired")
        return True
    stop = event_name in ("Stop", "SubagentStop")
    if stop:
        monkeypatch.setattr(runtime, "execute", lambda *a, **kw: subprocess.CompletedProcess([], 0, b'{"decision":"block","reason":"repair","_synthesis_policy":{}}', b""))
        monkeypatch.setattr(runtime, "_policy_reservation", catches_deadline)
    else:
        def worker(*args, **kwargs):
            catches_deadline()
            return subprocess.CompletedProcess([], 0, b"allowed", b"")
        monkeypatch.setattr(runtime, "execute", worker)
    args = ["--timeout-seconds", "0.02"]
    if stop:
        args += ["--hook-event", event_name]
    code = runtime.exec_public_main(args + [SCRIPT], Path("/synthetic/descriptor"))
    output = capsys.readouterr()
    assert caught == ["expired"]
    if stop:
        assert code == 0 and json.loads(output.out)["continue"] is False
        assert len(output.out.splitlines()) == 1
    else:
        assert code == 2 and output.out == ""


@pytest.mark.parametrize("pending", [False, True])
def test_caller_cancellation_survives_owned_alarm_cleanup(monkeypatch, capsys, pending):
    import signal
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        monkeypatch.setattr(runtime, "read_payload", lambda _: json.dumps(event()).encode())
        monkeypatch.setattr(runtime, "verified_release", lambda _: {})
        def interrupt(*args, **kwargs):
            if pending:
                signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
                os.kill(os.getpid(), signal.SIGALRM)
                assert signal.SIGALRM in signal.sigpending()
            signal.raise_signal(signal.SIGINT)
        monkeypatch.setattr(runtime, "execute", interrupt)
        with pytest.raises(KeyboardInterrupt):
            runtime.exec_public_main(["--hook-event", "Stop", SCRIPT], Path("/synthetic/descriptor"))
        assert capsys.readouterr().out == ""
    finally:
        signal.signal(signal.SIGINT, previous)

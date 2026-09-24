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


def test_stop_failure_has_one_corrective_continuation_then_terminal():
    first = runtime.stop_failure(event(), "unfinished", "status=UNKNOWN")
    assert first["decision"] == "block"
    for reason in ("unfinished", "changed error family"):
        repeated = runtime.stop_failure(event(stop_hook_active=True), reason, "status=UNKNOWN")
        assert repeated["continue"] is False
        assert "UNKNOWN" in repeated["systemMessage"]
        assert "decision" not in repeated
    assert runtime.stop_failure(event(turn_id="new-human-turn"), "unfinished")["decision"] == "block"


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
    monkeypatch.setattr(runtime, "read_payload", lambda _: (time.sleep(0.04) or json.dumps(event()).encode()))
    monkeypatch.setattr(runtime, "verified_release", lambda _: (time.sleep(0.04) or {}))
    def execute(*args, timeout):
        assert 0 < timeout < 0.13
        return subprocess.CompletedProcess([], 0, b'{}', b'')
    monkeypatch.setattr(runtime, "execute", execute)
    assert runtime.exec_public_main(["--hook-event", "Stop", "--timeout-seconds", "0.2", SCRIPT], pointer) == 0


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

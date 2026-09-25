"""Composed Muse Stop coverage; all command effects remain fixture-local."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills/synthesis-autopilot/scripts/native_stop.py"
SPEC = importlib.util.spec_from_file_location("autopilot_native_stop_fixture", SCRIPT)
assert SPEC and SPEC.loader
NATIVE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NATIVE
SPEC.loader.exec_module(NATIVE)


def payload(repeat=False):
    return {"session_id": "native-fixture", "hook_event_name": "Stop", "stop_hook_active": repeat}


def test_muse_wrapper_uses_verified_outer_launcher_and_combined_entrypoint():
    wrapper = (ROOT / ".muse-plugin/hooks/synthesis-session-stop.sh").read_text()
    assert 'SYNTHESIS_HOOK_CLIENT=muse' in wrapper
    assert 'PYTHONDONTWRITEBYTECODE=1' in wrapper
    assert 'exec-public --hook-event Stop --timeout-seconds 13' in wrapper
    assert 'synthesis-autopilot/scripts/autopilot_gate.py --combined-stop' in wrapper
    assert 'exec python3' not in wrapper


def test_missing_launcher_has_native_terminal_output_not_a_shell_retry(tmp_path):
    done = subprocess.run(["sh", str(ROOT / ".muse-plugin/hooks/synthesis-session-stop.sh")],
        input=json.dumps(payload()), capture_output=True, text=True, timeout=3,
        env={"HOME": str(tmp_path), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "SYNTHESIS_INSTALL_BIN_DIR": str(tmp_path / "missing")})
    assert done.returncode == 0
    result = json.loads(done.stdout)
    assert result["continue"] is False
    assert result["systemMessage"].startswith("UNRESOLVED:")


def test_both_checkpoint_and_autopilot_run_even_when_one_is_terminal():
    calls = []

    def checkpoint(event):
        calls.append("checkpoint")
        return {"continue": False, "stopReason": "checkpoint unavailable", "systemMessage": "UNRESOLVED: checkpoint"}

    def autopilot(event):
        calls.append("autopilot")
        return {"decision": "block", "reason": "remaining work"}

    result = NATIVE.combined_result(payload(), checkpoint=checkpoint, autopilot_check=autopilot)
    assert calls == ["checkpoint", "autopilot"]
    assert result["continue"] is False
    assert result.get("decision") != "block"
    assert "checkpoint unavailable" in result["stopReason"]
    assert "remaining work" in result["systemMessage"]


@pytest.mark.parametrize("terminal_index", [0, 1])
def test_terminal_result_has_precedence_over_sibling_corrective_result(terminal_index, monkeypatch):
    # This seam isolates composition, not the independently tested journal owner.
    # A corrective sibling now requires its owner-issued reservation.
    proof = {"synthetic_reservation": "composition-only"}
    monkeypatch.setattr(NATIVE._runtime(), "_policy_reservation",
        lambda event, supplied, *, consume: supplied == proof and not consume)
    responses = [{"decision": "block", "reason": "unfinished", "_synthesis_policy": proof}] * 2
    responses[terminal_index] = {"continue": False, "stopReason": "infrastructure failure"}
    result = NATIVE.combined_result(payload(), checkpoint=lambda _: responses[0], autopilot_check=lambda _: responses[1])
    assert result["continue"] is False
    assert result.get("decision") != "block"
    assert "infrastructure failure" in result["stopReason"]


@pytest.mark.parametrize("repeat", [False, True])
def test_composed_feedback_without_owner_reservation_is_terminal(repeat):
    result = NATIVE.combined_result(payload(repeat), checkpoint=lambda _: {},
        autopilot_check=lambda _: {"decision": "block", "reason": "unfinished"})
    assert result.get("continue") is False
    assert result.get("decision") != "block"
    assert "unfinished" in result["systemMessage"]


@pytest.mark.parametrize("malformed", [None, [], {}, {"session_id": "n", "hook_event_name": "Stop", "stop_hook_active": "false"}])
def test_malformed_event_never_runs_children_or_reenters(malformed):
    def unexpected(_):
        raise AssertionError("malformed native identity must not reach a child")
    result = NATIVE.combined_result(malformed, checkpoint=unexpected, autopilot_check=unexpected)
    assert result["continue"] is False
    assert result["systemMessage"].startswith("UNRESOLVED:")


@pytest.mark.parametrize("failure", [OSError("missing helper"), subprocess.TimeoutExpired("fixture", 1), ValueError("bad state")])
def test_child_infrastructure_failure_is_terminal_but_other_check_still_runs(failure):
    calls = []
    def checkpoint(_):
        calls.append("checkpoint")
        raise failure
    def autopilot(_):
        calls.append("autopilot")
        return {}
    result = NATIVE.combined_result(payload(), checkpoint=checkpoint, autopilot_check=autopilot)
    assert calls == ["checkpoint", "autopilot"]
    assert result["continue"] is False


@pytest.mark.parametrize("invalid", [[], "text", {"continue": "false"}, {"decision": "block"}, {"unrecognized": True}])
def test_invalid_child_result_is_terminal(invalid):
    result = NATIVE.combined_result(payload(), checkpoint=lambda _: invalid, autopilot_check=lambda _: {})
    assert result["continue"] is False


def test_healthy_children_do_not_create_feedback():
    assert NATIVE.combined_result(payload(), checkpoint=lambda _: {}, autopilot_check=lambda _: {}) == {}


def test_actual_autopilot_child_imports_and_runs_current_runtime(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    monkeypatch.syspath_prepend(str(ROOT / "skills/synthesis-project-management/scripts"))
    # A parent client selector must not mask the real native-discovery path.
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
    monkeypatch.delenv("SYNTHESIS_HOOK_CLIENT", raising=False)
    monkeypatch.setenv("SYNTHESIS_AUTOPILOT_RUNTIME", str(tmp_path / "runtime"))
    monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(tmp_path / "missing-board"))
    # No injected child: exercise the actual import and the production dispatcher.
    result = NATIVE._autopilot_result(payload())
    assert result.get("continue") is False
    assert "cannot identify this native client" in result["systemMessage"]
    assert "cannot import" not in result.get("systemMessage", "")


def test_verified_checkpoint_execution_preserves_terminal_wire_result(monkeypatch):
    calls = []
    class Runtime:
        def verified_release(self):
            calls.append("verified")
            return {"release_root": str(ROOT)}
        def execute(self, active, script, arguments, body, *, timeout):
            calls.append((active, script, arguments, json.loads(body), timeout))
            return subprocess.CompletedProcess([], 0, b'{"continue":false,"stopReason":"terminal"}', b'')
        def stop_result(self, event, result, *, consume_policy=True):
            calls.append(("consume_policy", consume_policy))
            return json.loads(result.stdout)
    monkeypatch.setattr(NATIVE, "_runtime", lambda: Runtime())
    result = NATIVE.checkpoint_result(payload())
    assert result["continue"] is False
    assert calls[0] == "verified"
    assert calls[1][1] == "synthesis-project-management/scripts/project_state.py"
    assert calls[1][2] == ["hook"]
    assert 0 < calls[1][4] < 13
    assert calls[2] == ("consume_policy", False)


def test_checkpoint_refuses_a_different_verified_release_root(monkeypatch, tmp_path):
    class Runtime:
        def verified_release(self):
            return {"release_root": str(tmp_path)}
        def execute(self, *args, **kwargs):
            raise AssertionError("cannot execute foreign installed release")
    monkeypatch.setattr(NATIVE, "_runtime", lambda: Runtime())
    with pytest.raises(ValueError):
        NATIVE.checkpoint_result(payload())


def test_composed_terminal_diagnostic_does_not_repeat_unresolved_prefix():
    module = NATIVE
    payload = {"hook_event_name": "Stop", "session_id": "native-1", "stop_hook_active": True}
    result = module.combined_result(payload,
        checkpoint=lambda event: {"continue": False, "stopReason": "failure", "systemMessage": "UNRESOLVED: failure"},
        autopilot_check=lambda event: {})
    assert result["systemMessage"] == "UNRESOLVED: failure"

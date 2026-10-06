"""R6: non-interactive Codex dispatch closes stdin, detects a stall by output that stops growing
rather than by elapsed time, and finds the current binary past a stale PATH launcher
(2026-08-30 stdin hang; 4.149.8 stale launcher). Discovery is `synthesis doctor`'s finder, whose
own cases are in tests/test_doctor.py; these check the wrapper reaches it unchanged."""

import importlib.util
import os
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "codex_dispatch_under_test", Path(__file__).resolve().parents[1] / "scripts" / "codex_dispatch.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _fake(tmp_path, name, body):
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_dispatch_finds_codex_with_the_doctors_finder(monkeypatch):
    from synthesis import doctor
    assert MODULE.synthesis_doctor is doctor and not hasattr(MODULE, "WELL_KNOWN")
    calls = []
    monkeypatch.setattr(doctor, "find_client", lambda name, which, locations: calls.append((name, which, locations))
                        or "/opt/codex")
    assert MODULE.find_binary() == Path("/opt/codex")
    assert calls == [("codex", MODULE.shutil.which, None)]  # PATH lookup at call time; the doctor's vendor list


def test_a_probe_that_cannot_be_cleaned_up_is_not_hidden_by_a_fallback(monkeypatch):
    def refuses(*args, **kwargs):
        raise PermissionError("cannot signal the probe's process group")
    monkeypatch.setattr(MODULE.synthesis_doctor, "find_client", refuses)
    assert MODULE.find_binary() is None


def test_dispatch_discovery_honors_explicit_absence(monkeypatch):
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", "")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/stale/codex")
    assert MODULE.find_binary() is None


def test_dispatch_uses_executable_override(tmp_path, monkeypatch):
    binary = _fake(tmp_path, "codex", "exit 0\n")
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(binary))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/stale/codex")
    assert MODULE.find_binary() == binary


def test_a_stale_path_launcher_is_skipped_for_one_that_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    stale = _fake(tmp_path, "stale-codex", "exit 1\n")
    current = _fake(tmp_path, "codex", 'if [ "$1" = "--version" ]; then echo codex 1.0; fi\n')
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: str(stale))
    assert MODULE.find_binary(locations=(str(current),)) == current


def test_stdin_is_closed_so_a_reader_of_stdin_cannot_hang(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "POLL_SECONDS", 0.05)
    reader = _fake(tmp_path, "codex", "cat\necho codex\necho REVIEW DONE\n")  # blocks forever on an open stdin
    rc, out, why = MODULE.dispatch(reader, "prompt", tmp_path / "out.txt", stall_seconds=2, quiet=True)
    assert rc == 0 and "REVIEW DONE" in out and why == ""
    assert MODULE.final_report(out) == "REVIEW DONE"


def test_silence_is_a_stall_and_slow_steady_output_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "POLL_SECONDS", 0.05)
    silent = _fake(tmp_path, "silent", "sleep 30\n")
    rc, _, why = MODULE.dispatch(silent, "prompt", tmp_path / "a.txt", stall_seconds=1, quiet=True)
    assert rc == 124 and "no output growth" in why
    slow = _fake(tmp_path, "slow", "for i in 1 2 3 4 5 6; do echo tick $i; sleep 0.3; done\n")
    rc, out, why = MODULE.dispatch(slow, "prompt", tmp_path / "b.txt", stall_seconds=1, quiet=True)
    assert rc == 0 and "tick 6" in out  # ran longer than the stall window, but kept producing


def test_the_known_stdin_hang_is_named_when_seen(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "POLL_SECONDS", 0.05)
    hung = _fake(tmp_path, "hung", f"echo '{MODULE.HANG_MARKER}...'\nsleep 30\n")
    rc, _, why = MODULE.dispatch(hung, "prompt", tmp_path / "c.txt", stall_seconds=1, quiet=True)
    assert rc == 124 and "BLOCKED ON STDIN" in why
    assert os.path.exists(tmp_path / "c.txt")

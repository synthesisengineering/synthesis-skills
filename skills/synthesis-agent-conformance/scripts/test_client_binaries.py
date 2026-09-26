from __future__ import annotations

import importlib.util
import os
import stat
import sys
import time
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("client_binaries.py")
SPEC = importlib.util.spec_from_file_location("client_binaries", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fake_binary(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_env_override_wins_over_path(tmp_path: Path, monkeypatch) -> None:
    override = fake_binary(tmp_path / "custom" / "codex")
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(override))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/codex")
    assert MODULE.resolve_client_binary("codex") == str(override)


def test_env_override_set_but_empty_means_absent(monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", "")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/codex")
    assert MODULE.resolve_client_binary("codex") is None


def test_env_override_pointing_nowhere_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_CLAUDE_BIN", str(tmp_path / "missing"))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/claude")
    assert MODULE.resolve_client_binary("claude") is None


def test_path_resolution(tmp_path: Path, monkeypatch) -> None:
    binary = fake_binary(tmp_path / "path" / "codex")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: str(binary))
    assert MODULE.resolve_client_binary("codex") == str(binary)


def test_well_known_fallback(tmp_path: Path, monkeypatch) -> None:
    fallback = fake_binary(tmp_path / "bundle" / "codex")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: None)
    monkeypatch.setitem(MODULE.WELL_KNOWN_LOCATIONS, "codex", (str(fallback),))
    assert MODULE.resolve_client_binary("codex") == str(fallback)


def test_absent_everywhere_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: None)
    monkeypatch.setitem(MODULE.WELL_KNOWN_LOCATIONS, "codex", ())
    assert MODULE.resolve_client_binary("codex") is None


def test_missing_binary_detail_names_override() -> None:
    detail = MODULE.missing_binary_detail("codex")
    assert "SYNTHESIS_CODEX_BIN" in detail
    assert "codex" in detail


def test_unknown_client_has_no_well_known_locations(monkeypatch) -> None:
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: None)
    assert MODULE.resolve_client_binary("unknown-client") is None


def test_muse_env_override_wins_over_path(tmp_path: Path, monkeypatch) -> None:
    override = fake_binary(tmp_path / "custom" / "muse")
    monkeypatch.setenv("SYNTHESIS_MUSE_BIN", str(override))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/muse")
    assert MODULE.resolve_client_binary("muse") == str(override)


def test_muse_env_override_set_but_empty_means_absent(monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_MUSE_BIN", "")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/muse")
    assert MODULE.resolve_client_binary("muse") is None


def test_muse_well_known_locations_configured() -> None:
    assert "~/.local/bin/muse" in MODULE.WELL_KNOWN_LOCATIONS["muse"]


def test_missing_binary_detail_names_muse_override() -> None:
    detail = MODULE.missing_binary_detail("muse")
    assert "SYNTHESIS_MUSE_BIN" in detail
    assert "muse" in detail


def test_failed_path_launcher_falls_back_to_working_bundle(tmp_path, monkeypatch):
    broken = fake_binary(tmp_path / "path" / "codex")
    broken.write_text("#!/bin/sh\nexit 127\n")
    bundle = fake_binary(tmp_path / "app" / "codex-cli" / "bin" / "codex")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: str(broken))
    monkeypatch.setitem(MODULE.WELL_KNOWN_LOCATIONS, "codex", (str(broken), str(bundle)))
    assert MODULE.resolve_client_binary("codex") == str(bundle)


def test_current_desktop_layout_is_a_known_candidate():
    assert "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex" in MODULE.WELL_KNOWN_LOCATIONS["codex"]


def test_explicit_broken_override_never_selects_another_install(tmp_path, monkeypatch):
    broken = fake_binary(tmp_path / "explicit" / "codex")
    broken.write_text("#!/bin/sh\nexit 127\n")
    fallback = fake_binary(tmp_path / "fallback" / "codex")
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(broken))
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: str(fallback))
    # Explicit selection remains authoritative; its caller reports any execution failure.
    assert MODULE.resolve_client_binary("codex") == str(broken)


def test_hung_candidate_is_bounded_and_its_child_is_reaped(tmp_path, monkeypatch):
    child_marker = tmp_path / "child-survived"
    hung = fake_binary(tmp_path / "hung" / "codex")
    hung.write_text(f"#!/bin/sh\n(sleep 1; touch '{child_marker}') &\nwait\n")
    bundle = fake_binary(tmp_path / "bundle" / "codex")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: str(hung))
    monkeypatch.setitem(MODULE.WELL_KNOWN_LOCATIONS, "codex", (str(hung), str(bundle)))
    monkeypatch.setattr(MODULE, "PROBE_TIMEOUT_SECONDS", 0.1, raising=False)
    start = time.monotonic()
    assert MODULE.resolve_client_binary("codex") == str(bundle)
    assert time.monotonic() - start < 1
    time.sleep(1.1)
    assert not child_marker.exists()


def test_version_probe_closes_stdin_and_never_sends_a_model_prompt(tmp_path, monkeypatch):
    args = tmp_path / "args"
    candidate = fake_binary(tmp_path / "codex")
    candidate.write_text(f"#!/bin/sh\nprintf '%s' \"$*\" > '{args}'\nread value && exit 9\nexit 0\n")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda _name: str(candidate))
    assert MODULE.resolve_client_binary("codex") == str(candidate)
    assert args.read_text() == "--version"


def test_unconfirmed_probe_cleanup_cannot_report_success(tmp_path, monkeypatch):
    candidate = fake_binary(tmp_path / "codex")
    waits = []
    class Process:
        pid = 987654
        def wait(self, timeout):
            waits.append(timeout)
            if len(waits) == 1:
                return 0
            raise MODULE.subprocess.TimeoutExpired("codex", timeout)
    monkeypatch.setattr(MODULE.subprocess, "Popen", lambda *args, **kwargs: Process())
    monkeypatch.setattr(MODULE.os, "killpg", lambda *args: None)
    assert not MODULE._codex_launcher_works(candidate)
    assert waits == [MODULE.PROBE_TIMEOUT_SECONDS, 1.0]


def review_shell(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o700)
    return path


def test_relative_explicit_override_runs_selected_file(monkeypatch,tmp_path):
    import subprocess, signal
    helper = MODULE
    expected=review_shell(tmp_path/'explicit','echo SELECTED'); alternate=review_shell(tmp_path/'path/explicit','echo WRONG')
    monkeypatch.chdir(tmp_path); monkeypatch.setenv('PATH',str(alternate.parent)); monkeypatch.setenv('SYNTHESIS_CODEX_BIN','./explicit')
    selected=helper.resolve_client_binary('codex'); result=subprocess.run([selected,'--version'],text=True,capture_output=True,timeout=2)
    assert result.stdout.strip()=='SELECTED', {'selected':selected,'actual':result.stdout.strip()}


def test_unconfirmed_cleanup_stops_entire_discovery(monkeypatch,tmp_path):
    import subprocess, signal
    helper = MODULE
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    pidfile=tmp_path/'child'; bad=review_shell(tmp_path/'bad',f'/bin/sleep 30 &\necho $! > "{pidfile}"\nexit 127'); good=review_shell(tmp_path/'good','exit 0')
    monkeypatch.setattr(helper.shutil,'which',lambda name:str(bad)); monkeypatch.setitem(helper.WELL_KNOWN_LOCATIONS,'codex',(str(good),)); original=helper.os.killpg; attempted=[]
    def deny_first(pid,sig):
        attempted.append(pid)
        if len(attempted)==1: raise PermissionError('synthetic cleanup denial')
        return original(pid,sig)
    monkeypatch.setattr(helper.os,'killpg',deny_first)
    try:
        selected=helper.resolve_client_binary('codex'); assert selected is None, {'selected_despite_unresolved_child':selected,'child':pidfile.read_text().strip()}
    finally:
        if attempted:
            try: original(attempted[0],signal.SIGKILL)
            except ProcessLookupError: pass


def test_unconfirmed_wait_stops_before_next_candidate(monkeypatch,tmp_path):
    import subprocess, signal
    helper = MODULE
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    first=review_shell(tmp_path/'first','exit 0'); second=review_shell(tmp_path/'second','exit 0'); calls=[]
    class Fake:
        pid=99999991
        def __init__(self): self.waits=0
        def wait(self,timeout):
            self.waits+=1
            if self.waits==1: return 0
            raise subprocess.TimeoutExpired('synthetic',timeout)
    def popen(*args,**kwargs): calls.append(args); return Fake()
    monkeypatch.setattr(helper.shutil,'which',lambda name:str(first)); monkeypatch.setitem(helper.WELL_KNOWN_LOCATIONS,'codex',(str(second),)); monkeypatch.setattr(helper.subprocess,'Popen',popen); monkeypatch.setattr(helper.os,'killpg',lambda *args:None)
    assert helper.resolve_client_binary('codex') is None
    assert len(calls)==1, {'dispatched_after_unconfirmed_wait':len(calls)}

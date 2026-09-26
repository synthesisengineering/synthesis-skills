"""Real onboarding entrypoints share executable discovery and explicit selection."""
import os
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import onboard


def binary(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o700)
    return path


def test_onboard_skips_failed_path_launcher(tmp_path, monkeypatch):
    stale = binary(tmp_path / "bin/codex", "exit 127")
    usable = binary(tmp_path / "bundle/codex", "exit 0")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(onboard.shutil, "which", lambda _name: str(stale))
    monkeypatch.setitem(onboard.CLIENT_WELL_KNOWN, "codex", [usable])
    assert onboard.resolve_client("codex") == str(usable)


def test_onboard_explicit_missing_binary_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(tmp_path / "absent"))
    assert onboard.resolve_client("codex") is None


def test_direct_copy_discovery_uses_packaged_resolver(tmp_path):
    # Source only the literal resolver function; no installer action is invoked.
    source = (SCRIPTS / "direct_copy.sh").read_text()
    function = source[source.index("resolve_codex_bin() {"):source.index("\nclaude_plugin_installed()")]
    env = {**os.environ, "SYNTHESIS_CODEX_BIN": "", "SCRIPT_ROOT": str(SCRIPTS.parents[2])}
    result = subprocess.run(["sh", "-c", function + "\nresolve_codex_bin\n"], env=env, text=True, capture_output=True, timeout=5)
    assert result.returncode == 0 and result.stdout == ""
    stale = binary(tmp_path / "path/codex", "exit 127")
    usable = binary(tmp_path / "home/.local/bin/codex", "exit 0")
    env.pop("SYNTHESIS_CODEX_BIN")
    env.update(HOME=str(tmp_path / "home"), PATH=str(stale.parent) + os.pathsep + os.environ["PATH"])
    result = subprocess.run(["sh", "-c", function + "\nresolve_codex_bin\n"], env=env, text=True, capture_output=True, timeout=5)
    assert result.returncode == 0 and result.stdout.strip() == str(usable)

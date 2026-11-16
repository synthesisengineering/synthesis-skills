"""5.24.0: a session start never replaces an installed runtime from the folder its harness passes.

The session-start hook installed the runtime from the plugin folder the harness loaded whenever that folder carried a
newer release. That folder is the harness's own plugin cache, which the guard does not protect, so an agent that wrote
a higher version into it had its code made the runtime at the next session start (open item 1 of review round 1,
live in 5.23.0). The principal's sandbox rulings of 2026-11-15 settle it: seal everything the guard trusts, and install
only from the protected release tool, which verifies the tag on GitHub's main and that it is newer. So a session start
installs from the harness's folder only where no runtime exists at all (the first install); otherwise it says once
that a newer plugin is loaded and names the line that installs it, and the doctor warns while the two differ.
"""

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import doctor, hook, install, paths

ROOT = Path(__file__).resolve().parents[1]
LINE = "~/.synthesis/v5/bin/synthesis-release --install-only --tag v{}"


def _plugin(tmp_path, name, version):
    copy = tmp_path / name
    shutil.copytree(ROOT / "synthesis", copy / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "synthesis" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    shutil.copy2(ROOT / "CHANGELOG.md", copy / "CHANGELOG.md")
    return copy


def _session_start(monkeypatch, capsys, plugin, session="S-1") -> dict:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": session, "cwd": str(plugin)})))
    assert hook.main(["hook.py", "session-start", str(plugin)]) == 0
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else {}


def test_a_session_start_on_a_newer_plugin_keeps_the_runtime_and_says_so_once(tmp_path, isolated_home, monkeypatch, capsys):
    install.install(_plugin(tmp_path, "old", "1.0.0"))
    kept = install.current_hash()
    said = _session_start(monkeypatch, capsys, _plugin(tmp_path, "new", "1.0.1"))
    assert install.current_hash() == kept and install.version(paths.home() / "current") == (1, 0, 0)
    told = said.get("systemMessage", "")
    assert "1.0.1" in told and "1.0.0" in told and LINE.format("1.0.1") in told, said
    assert LINE.format("1.0.1") in said["hookSpecificOutput"]["additionalContext"]
    again = _session_start(monkeypatch, capsys, tmp_path / "new", session="S-2")
    assert LINE.format("1.0.1") not in json.dumps(again)  # once
    assert install.current_hash() == kept


def test_a_session_start_with_no_runtime_installs_from_the_harness_folder(tmp_path, isolated_home, monkeypatch, capsys):
    """The first install: no runtime exists yet, so there is no guard to keep, and no release tool to install with."""
    _session_start(monkeypatch, capsys, _plugin(tmp_path, "first", "1.0.0"))
    assert install.version(paths.home() / "current") == (1, 0, 0)


def test_the_session_start_route_never_replaces_an_installed_runtime(tmp_path, isolated_home):
    install.install(_plugin(tmp_path, "old", "1.0.0"))
    kept = install.current_hash()
    said = install.install(_plugin(tmp_path, "new", "9.0.0"), first_only=True)
    assert "kept" in said and install.current_hash() == kept


def test_the_first_install_bootstrap_installs_only_where_no_runtime_exists(tmp_path, isolated_home):
    """hooks.json runs `python3 -B -S <plugin>/synthesis/install.py <plugin>` when the stable hook is missing."""
    install.install(_plugin(tmp_path, "old", "1.0.0"))
    kept = install.current_hash()
    newer = _plugin(tmp_path, "new", "1.0.1")
    done = subprocess.run([sys.executable, "-B", "-S", str(newer / "synthesis" / "install.py"), str(newer)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0 and install.current_hash() == kept, done.stdout + done.stderr


def test_the_doctor_warns_while_the_harness_holds_a_newer_plugin(tmp_path, isolated_home):
    install.install(_plugin(tmp_path, "old", "1.0.0"))
    runtime = install.current_hash()
    check = doctor.check_package("claude", _plugin(tmp_path, "new", "1.0.1"), runtime)
    assert check.status == "warn" and LINE.format("1.0.1") in check.detail and "1.0.0" in check.detail, check
    check = doctor.check_package("claude", _plugin(tmp_path, "older", "0.9.0"), runtime)
    assert check.status == "fail" and "start a session" not in check.detail, check  # a session start never updates it
    assert doctor.check_package("claude", tmp_path / "old", runtime).status == "ok"

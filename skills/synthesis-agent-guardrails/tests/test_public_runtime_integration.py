"""Public guard packaging must work without a private helper or import mocks.

These fixtures copy real public implementation files into a disposable release,
use the production launcher generator and receipt verifier, and execute the
actual hooks in fresh processes. Every state write stays under the fixture HOME.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[3]
ONBOARDING = REPOSITORY / "skills/synthesis-onboarding/scripts"
STOP_HOOK = "synthesis-agent-guardrails/hooks/codex/repo_guard_stop.py"
ARTIFACT_GUARD = "synthesis-agent-guardrails/guards/installed_artifact_guard.py"


@pytest.fixture
def public_installation(tmp_path, monkeypatch):
    """Materialize public files with a real, receipt-bound temporary launcher."""
    monkeypatch.syspath_prepend(str(ONBOARDING))
    import release_runtime
    import system_contract

    monkeypatch.setenv("SYNTHESIS_RUNTIME_POLICY", "packaged-python-v1")
    monkeypatch.delenv("SYNTHESIS_PUBLIC_SKILLS_SOURCE", raising=False)
    base = tmp_path.resolve()
    generation = base / "generation"
    for skill in (
        "synthesis-agent-guardrails",
        "synthesis-onboarding",
        "synthesis-project-management",
        "synthesis-repo-guard",
    ):
        shutil.copytree(
            REPOSITORY / "skills" / skill,
            generation / "skills" / skill,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
    for client in ("claude", "codex", "muse"):
        manifest = generation / ("." + client + "-plugin") / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "synthesis-skills", "version": "9.8.7"}))

    home = base / "isolated-home"
    home.mkdir()
    state = home / ".local/state/synthesis"
    state.mkdir(parents=True)
    descriptor = state / "active-release.json"
    descriptor.with_name(descriptor.name + ".lock").touch()
    pin = release_runtime.interpreter_pin(str(Path(sys.executable).absolute()))
    launcher = home / ".local/bin/synthesis"
    launcher.parent.mkdir(parents=True)
    content = system_contract.launcher_bytes(descriptor, pin)
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    descriptor.write_text(json.dumps({
        "schema_version": 1,
        "version": "9.8.7",
        "channel": "pin",
        "ref": "v9.8.7",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(generation),
        "digest_algorithm": "sha256-tree-v1",
        "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/skills.git",
        "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(generation),
        "interpreter": pin,
        "launcher": {
            "path": str(launcher),
            "runtime_schema": 1,
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }))
    config = home / ".synthesis/agent-guardrails/hooks.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"hooks": {"repo_guard_stop": True}}))
    # Deliberately do not inherit PYTHONPATH, PYTHONHOME, real state locations,
    # active-descriptor overrides, coordination identity, or private helpers.
    environment = {
        "HOME": str(home),
        "PATH": os.defpath,
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "SYNTHESIS_HOME": str(home / ".synthesis"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "SYNTHESIS_ACTIVE_DESCRIPTOR": str(descriptor),
        "GUARDRAILS_HOOKS_CONFIG": str(config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    workspace = base / "workspace"
    workspace.mkdir()
    verified = release_runtime.verified_release(descriptor)
    assert verified["release_root"] == str(generation)
    return {
        "root": generation,
        "home": home,
        "descriptor": descriptor,
        "launcher": launcher,
        "config": config,
        "environment": environment,
        "workspace": workspace,
    }


def invoke(installation, script, arguments=(), *, payload=None, through_launcher=False):
    if through_launcher:
        command = [str(installation["launcher"]), "exec-public", script, "--", *arguments]
    else:
        command = [sys.executable, "-B", str(installation["root"] / "skills" / script), *arguments]
    return subprocess.run(
        command,
        input=json.dumps(payload or {}),
        text=True,
        capture_output=True,
        cwd=installation["workspace"],
        env=installation["environment"],
        timeout=30,
        check=False,
    )


def test_packaged_stop_executes_real_repo_detector_without_private_helpers(public_installation):
    installation = public_installation
    workspace = installation["workspace"]
    subprocess.run(
        ["git", "init", "--quiet", str(workspace)],
        env=installation["environment"], capture_output=True, check=True,
    )
    (workspace / "retained-work.txt").write_text("uncommitted work must survive\n")
    result = invoke(installation, STOP_HOOK, through_launcher=True, payload={
        "cwd": str(workspace), "session_id": "public-packaging-fixture", "hook_event_name": "Stop",
        "stop_hook_active": False,
    })
    assert result.returncode == 0, result.stderr
    assert not result.stdout.strip() or json.loads(result.stdout) == {}, result.stdout
    report = installation["home"] / ".synthesis/repo-guard/last-report.json"
    assert report.is_file(), "a silent hook alone does not prove the detector executed"
    assert str(workspace) in report.read_text()
    assert (workspace / "retained-work.txt").read_text() == "uncommitted work must survive\n"


def test_enabled_packaged_stop_doctor_checks_valid_public_runtime(public_installation):
    result = invoke(public_installation, STOP_HOOK, ["--doctor"], through_launcher=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "state: enabled" in result.stdout
    assert "UNHEALTHY" not in result.stdout


@pytest.mark.parametrize("damage", ["missing-descriptor", "tampered-launcher", "malformed-config"])
def test_enabled_stop_doctor_refuses_broken_execution_prerequisites(public_installation, damage):
    installation = public_installation
    if damage == "missing-descriptor":
        installation["descriptor"].unlink()
    elif damage == "tampered-launcher":
        with installation["launcher"].open("a") as handle:
            handle.write("\n# changed after activation\n")
    else:
        installation["config"].write_text("{invalid settings")
    # Invoke the doctor's own boundary: the outer launcher would reject a
    # damaged receipt first and conceal a doctor which incorrectly reports OK.
    result = invoke(installation, STOP_HOOK, ["--doctor"])
    assert result.returncode != 0, result.stdout + result.stderr
    assert "UNHEALTHY" in result.stdout + result.stderr


def test_unconfigured_packaged_stop_remains_inert_without_a_runtime(public_installation):
    installation = public_installation
    installation["config"].unlink()
    installation["descriptor"].unlink()
    result = invoke(installation, STOP_HOOK, payload={"cwd": str(installation["workspace"])})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""
    doctor = invoke(installation, STOP_HOOK, ["--doctor"])
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "UNCONFIGURED" in doctor.stdout


@pytest.mark.parametrize("protected", [False, True], ids=["ordinary-source", "installed-artifact"])
def test_packaged_artifact_guard_parses_shell_with_verified_public_parser(public_installation, protected):
    installation = public_installation
    destination = (installation["home"] / ".agents/skills/example/SKILL.md"
                   if protected else installation["workspace"] / "source.txt")
    result = invoke(installation, ARTIFACT_GUARD, ["--client", "codex"], payload={
        "cwd": str(installation["workspace"]),
        "tool_name": "exec_command",
        "tool_input": {"command": f"touch '{destination}'"},
    })
    assert result.returncode == 0, result.stderr
    if protected:
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert "installed skill artifact" in decision["permissionDecisionReason"]
        assert "could not parse" not in decision["permissionDecisionReason"]
    else:
        assert result.stdout == "", result.stdout
    assert not destination.exists(), "inspection must not execute the supplied command"


def test_packaged_artifact_guard_refuses_changed_parser_without_executing_it(public_installation):
    installation = public_installation
    sentinel = installation["workspace"] / "unexpected-parser-execution"
    parser = installation["root"] / "skills/synthesis-project-management/scripts/publication_command.py"
    parser.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n")
    result = invoke(installation, ARTIFACT_GUARD, ["--client", "codex"], payload={
        "cwd": str(installation["workspace"]),
        "tool_input": {"command": "touch source.txt"},
    })
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "could not parse" in decision["permissionDecisionReason"]
    assert not sentinel.exists()

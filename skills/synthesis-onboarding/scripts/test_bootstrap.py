#!/usr/bin/env python3
"""Immutable bootstrap materialization tests."""

from __future__ import annotations

import json
import copy
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))

import bootstrap  # noqa: E402
import system_contract  # noqa: E402
import release_runtime  # noqa: E402
from test_system_contract import git, release_repo  # noqa: E402


@pytest.fixture
def bytecode_release(tmp_path):
    checkout = release_repo(tmp_path)
    directory = checkout / "skills/synthesis-autopilot/scripts"
    directory.mkdir(parents=True)
    (directory / "fixture_dep.py").write_text('VALUE = "verified cached import"\n')
    (directory / "autopilot_gate.py").write_text(
        'import sys,json\n'
        'def audit(event,args):\n'
        '    if event == "compile" and str(args[1]).endswith("fixture_dep.py"):\n'
        '        raise RuntimeError("dependency was recompiled instead of using verified bytecode")\n'
        'sys.addaudithook(audit)\n'
        'import fixture_dep\n'
        'print(json.dumps({"fixture":fixture_dep.VALUE}))\n')
    git(checkout, "add", "--all")
    git(checkout, "commit", "-q", "-m", "fixture cached dependency")
    git(checkout, "branch", "-f", "stable", "HEAD")
    git(checkout, "tag", "-f", "v9.8.7", "HEAD")
    source_descriptor = system_contract.release_descriptor_from_checkout(checkout, "stable", "stable", "https://example.test/synthesis-skills.git")
    generation, descriptor = bootstrap.materialize_release(checkout, tmp_path / "generations",
        channel="stable", ref="stable", source_url="https://example.test/synthesis-skills.git")
    return checkout, generation, descriptor, source_descriptor


def test_materialization_builds_checked_hash_cache_without_changing_source_identity(bytecode_release):
    checkout, generation, descriptor, source_descriptor = bytecode_release
    assert descriptor["content_digest"] == source_descriptor["content_digest"]
    cache = descriptor["bytecode"]
    assert cache["schema_version"] == 1
    assert cache["source_content_digest"] == descriptor["content_digest"]
    assert cache["abi"]["cache_tag"] == sys.implementation.cache_tag
    assert cache["abi"]["magic"] == importlib.util.MAGIC_NUMBER.hex()
    assert cache["abi"]["optimize"] == 0
    assert not list(checkout.rglob("*.pyc"))
    assert cache["files"]
    for relative, proof in cache["files"].items():
        compiled = (generation / relative).read_bytes()
        source = (generation / proof["source"]).read_bytes()
        assert compiled[:4] == importlib.util.MAGIC_NUMBER
        assert int.from_bytes(compiled[4:8], "little") == 3
        assert compiled[8:16] == importlib.util.source_hash(source)
        assert hashlib.sha256(compiled).hexdigest() == proof["sha256"]
        assert hashlib.sha256(source).hexdigest() == proof["source_sha256"]
        assert (generation / relative).stat().st_mode & 0o222 == 0
    system_contract.verify_materialized_release(generation, descriptor)


def test_activated_launcher_imports_verified_cache_without_compilation(bytecode_release, tmp_path):
    _, generation, descriptor, _ = bytecode_release
    launcher, pointer = tmp_path / "bin/synthesis", tmp_path / "state/active.json"
    system_contract.activate_cli(generation, descriptor, launcher, pointer)
    payload = {"hook_event_name": "Stop", "session_id": "synthetic-bytecode-acceptance", "stop_hook_active": False}
    result = subprocess.run([str(launcher), "exec-public", "--hook-event", "Stop",
        "synthesis-autopilot/scripts/autopilot_gate.py"], input=json.dumps(payload), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"fixture": "verified cached import"}
    assert release_runtime.verified_release(pointer)["bytecode"] == descriptor["bytecode"]


@pytest.mark.parametrize("damage", ["body", "missing", "extra", "magic", "unchecked", "source", "symlink", "abi", "manifest-path"])
def test_verified_cache_rejects_body_header_source_and_inventory_drift(bytecode_release, tmp_path, damage):
    _, generation, original, _ = bytecode_release
    descriptor = copy.deepcopy(original)
    relative, proof = next((path, item) for path, item in descriptor["bytecode"]["files"].items()
                           if item["source"].endswith("fixture_dep.py"))
    path = generation / relative
    metadata = path.stat()
    path.chmod(0o644)
    if damage == "body":
        raw = path.read_bytes()
        assert raw.count(b"verified cached import") == 1
        replacement = raw.replace(b"verified cached import", b"tampered cached import")
        assert len(replacement) == len(raw)
        path.write_bytes(replacement)
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    elif damage == "missing":
        path.parent.chmod(0o755);path.unlink()
    elif damage == "extra":
        path.parent.chmod(0o755);(path.parent / "foreign.cpython-312.pyc").write_bytes(path.read_bytes())
    elif damage in {"magic", "unchecked"}:
        raw = bytearray(path.read_bytes())
        raw[:4] = b"BAD!" if damage == "magic" else raw[:4]
        if damage == "unchecked": raw[4:8] = (1).to_bytes(4, "little")
        path.write_bytes(raw)
        proof["sha256"] = hashlib.sha256(raw).hexdigest()
    elif damage == "source":
        source = generation / proof["source"];source.chmod(0o644);source.write_text('VALUE = "unverified source"\n')
    elif damage == "symlink":
        outside = tmp_path / "outside.pyc";outside.write_bytes(path.read_bytes())
        path.parent.chmod(0o755);path.unlink();path.symlink_to(outside)
    elif damage == "abi":descriptor["bytecode"]["abi"]["interpreter_sha256"] = "0" * 64
    elif damage == "manifest-path":
        descriptor["bytecode"]["files"]["../escape.pyc"] = descriptor["bytecode"]["files"].pop(relative)
    if path.exists() and not path.is_symlink():path.chmod(0o444)
    with pytest.raises((system_contract.ContractError, release_runtime.RuntimeContractError)):
        system_contract.verify_materialized_release(generation, descriptor)


@pytest.fixture(autouse=True)
def isolated_bootstrap_home(tmp_path, monkeypatch):
    """A release fixture must never consume the invoking machine's selection."""
    for name in tuple(os.environ):
        if name.startswith(("SYNTHESIS_", "XDG_", "GIT_")) or name in {
            "CODEX_HOME", "CLAUDE_CONFIG_DIR", "PYTHONPATH",
        }:
            monkeypatch.delenv(name, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    for name, value in {
        "HOME": home, "SYNTHESIS_HOME": home,
        "XDG_CONFIG_HOME": home / ".config", "XDG_STATE_HOME": home / ".local/state",
        "XDG_CACHE_HOME": home / ".cache", "XDG_DATA_HOME": home / ".local/share",
        "CODEX_HOME": home / ".codex", "CLAUDE_CONFIG_DIR": home / ".claude",
        "SYNTHESIS_BOOTSTRAP_PYTHON": sys.executable,
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }.items():
        monkeypatch.setenv(name, str(value))


def test_verified_cli_can_use_org_ssh_without_enabling_local_transports(tmp_path, monkeypatch):
    checkout = release_repo(tmp_path)
    calls = []
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "https")
    monkeypatch.setenv("GIT_PROTOCOL_FROM_USER", "0")
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda command, env=None: calls.append((command, env)) or 0)
    assert bootstrap.main([
        "--checkout", str(checkout), "--releases-dir", str(tmp_path / "releases"),
        "--launcher", str(tmp_path / "bin/synthesis"),
        "--active-descriptor", str(tmp_path / "state/active.json"),
        "--channel", "stable", "--ref", "stable",
        "--source-url", "https://example.test/synthesis-skills.git", "--", "update",
    ]) == 0
    environment = calls[0][1]
    assert environment["GIT_ALLOW_PROTOCOL"] == "https:ssh"
    assert environment["GIT_PROTOCOL_FROM_USER"] == "0"
    assert os.environ["GIT_ALLOW_PROTOCOL"] == "https"
    for forbidden in (checkout.as_uri(), "ext::git --version"):
        blocked = subprocess.run(["git", "ls-remote", forbidden], env=environment,
            capture_output=True, text=True)
        assert blocked.returncode != 0 and "not allowed" in blocked.stderr


def test_materialization_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "cache" / "releases"
    first, descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    second, second_descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert first == second == releases / descriptor["content_digest"]
    assert second_descriptor["content_digest"] == descriptor["content_digest"]
    assert not (first / ".git").exists()
    assert len(list(releases.iterdir())) == 1


def test_materialized_generation_is_read_only(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    generation, _descriptor = bootstrap.materialize_release(
        checkout,
        tmp_path / "releases",
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert generation.stat().st_mode & 0o222 == 0
    assert all(path.stat().st_mode & 0o222 == 0 for path in generation.rglob("*"))


def test_existing_generation_permissions_are_reasserted(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "releases"
    generation, _descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    target = generation / ".codex-plugin" / "plugin.json"
    os.chmod(generation, 0o755)
    os.chmod(target, 0o644)
    same, _ = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert same == generation
    assert generation.stat().st_mode & 0o222 == 0
    assert target.stat().st_mode & 0o222 == 0


def test_floating_bootstrap_keeps_a_verified_newer_active_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    newer = release_repo(tmp_path / "newer", version="9.8.7")
    older = release_repo(tmp_path / "older", version="9.8.6")
    (newer / "onboard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    git(newer, "add", "onboard.sh")
    git(newer, "commit", "-q", "-m", "bootstrap")
    git(newer, "branch", "-f", "stable", "HEAD")
    git(newer, "tag", "-f", "v9.8.7")
    releases = tmp_path / "releases"
    generation, descriptor = bootstrap.materialize_release(
        newer,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    system_contract.activate_cli(generation, descriptor, launcher, active)
    calls = []
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda command, env=None: calls.append((command, env)) or 0)
    assert bootstrap.main(
        [
            "--checkout", str(older),
            "--releases-dir", str(releases),
            "--launcher", str(launcher),
            "--active-descriptor", str(active),
            "--channel", "stable",
            "--ref", "stable",
            "--source-url", "https://example.test/synthesis-skills.git",
            "--", "update",
        ]
    ) == 0
    assert json.loads(active.read_text(encoding="utf-8"))["version"] == "9.8.7"
    assert str(generation) in calls[0][0][2]


def test_floating_bootstrap_honors_an_explicit_channel_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stable = release_repo(tmp_path / "stable", version="9.8.7")
    edge = release_repo(tmp_path / "edge", version="9.8.6")
    git(edge, "branch", "main-edge", "HEAD")
    releases = tmp_path / "releases"
    stable_generation, stable_descriptor = bootstrap.materialize_release(
        stable,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    system_contract.activate_cli(stable_generation, stable_descriptor, launcher, active)
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda _command, env=None: 0)
    assert bootstrap.main(
        [
            "--checkout", str(edge),
            "--releases-dir", str(releases),
            "--launcher", str(launcher),
            "--active-descriptor", str(active),
            "--channel", "edge",
            "--ref", "main",
            "--source-url", "https://example.test/synthesis-skills.git",
            "--", "setup",
        ]
    ) == 0
    selected = json.loads(active.read_text(encoding="utf-8"))
    assert selected["version"] == "9.8.6"
    assert selected["channel"] == "edge"
    assert selected["ref"] == "main"


@pytest.mark.parametrize("saved_profile", [None, "modular"])
def test_onboard_handoff_consumes_resolution_policy_before_update_cli(
    tmp_path: Path,
    saved_profile,
) -> None:
    checkout = release_repo(tmp_path / "source")
    fixture_scripts = checkout / "skills" / "synthesis-onboarding" / "scripts"
    # Use the real runtime dependency closure, including modular update support.
    # Only the terminal CLI is a recorder; parser-to-projection execution is real.
    import modular
    for relative in modular.runtime_files(REPO_ROOT):
        if relative in {".claude-plugin/plugin.json", ".codex-plugin/plugin.json"}:
            continue  # Keep this fixture's deliberately separate release identity.
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, target)
        target.chmod((REPO_ROOT / relative).stat().st_mode & 0o777)
    shutil.copytree(REPO_ROOT / "skills/synthesis-writing-craft", checkout / "skills/synthesis-writing-craft")
    marker = tmp_path / "cli-argv.json"
    (fixture_scripts / "synthesis_cli.py").write_text(
        "import argparse, json, os, sys\n"
        "from pathlib import Path\n\n\n"
        "def build_parser():\n"
        "    parser = argparse.ArgumentParser(prog='synthesis')\n"
        "    commands = parser.add_subparsers(dest='command', required=True)\n"
        "    for name in ('setup', 'update'):\n"
        "        commands.add_parser(name)\n"
        "    return parser\n\n\n"
        "if __name__ == '__main__':\n"
        "    if sys.argv[1:] != ['update']:\n"
        "        raise SystemExit(2)\n"
        "    Path(os.environ['SYNTHESIS_TEST_CLI_MARKER']).write_text("
        "json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "handoff fixture")
    git(checkout, "branch", "-f", "stable", "HEAD")
    git(checkout, "tag", "-f", "v9.8.7")
    environment = dict(os.environ)
    environment.update(
        {
            "SYNTHESIS_ONBOARD_SOURCE_DIR": str(checkout),
            "SYNTHESIS_ONBOARD_CHANNEL": "stable",
            "SYNTHESIS_HOME": str(tmp_path / "home"),
            "SYNTHESIS_ONBOARD_CACHE_DIR": str(tmp_path / "cache"),
            "SYNTHESIS_INSTALL_BIN_DIR": str(tmp_path / "bin"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "SYNTHESIS_TEST_CLI_MARKER": str(marker),
        }
    )
    if saved_profile:
        state = system_contract.SystemState(tmp_path / "home")
        state.config_dir.mkdir(parents=True)
        state.desired_path.write_text(json.dumps(system_contract.default_desired_state(
            profile=saved_profile, channel="stable", clients=["codex"],
            modular={"roots": ["synthesis-writing-craft"], "stage_core": False},
        )))
    completed = subprocess.run(
        ["sh", str(REPO_ROOT / "onboard.sh"), "update"],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(marker.read_text(encoding="utf-8")) == ["update"]
    active = json.loads((tmp_path / "state/synthesis/active-release.json").read_text())
    if saved_profile:
        assert active["projection"]["selection"]["roots"] == ["synthesis-writing-craft"]
        assert active["projection"]["selection"]["stage_core"] is False
        assert (Path(active["release_root"]) / "skills/synthesis-onboarding/scripts/modular.py").is_file()
    else:
        assert "projection" not in active


def test_existing_corrupt_generation_is_rejected(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "releases"
    generation, descriptor = bootstrap.materialize_release(
        checkout,
        releases,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    target = generation / ".codex-plugin" / "plugin.json"
    target.chmod(0o644)
    target.write_text(json.dumps({"version": "0.0.0"}), encoding="utf-8")
    with pytest.raises(system_contract.ContractError):
        bootstrap.materialize_release(
            checkout,
            releases,
            channel="stable",
            ref="stable",
            source_url="https://example.test/synthesis-skills.git",
        )
    assert generation == releases / descriptor["content_digest"]


def test_ignored_build_artifacts_never_enter_materialized_release(tmp_path: Path) -> None:
    checkout = release_repo(tmp_path)
    ignored = checkout / "skills" / "synthesis-onboarding" / "scripts" / "__pycache__"
    ignored.mkdir()
    (ignored / "bootstrap.cpython-312.pyc").write_bytes(b"ignored test residue")
    (checkout / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(checkout, "add", ".gitignore")
    git(checkout, "commit", "-q", "-m", "ignore build residue")
    git(checkout, "branch", "-f", "stable", "HEAD")
    git(checkout, "tag", "-f", "v9.8.7")

    generation, _descriptor = bootstrap.materialize_release(
        checkout,
        tmp_path / "releases",
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert not (generation / "skills" / "synthesis-onboarding" / "scripts" / "__pycache__").exists()

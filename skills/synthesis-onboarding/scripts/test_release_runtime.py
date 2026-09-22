"""Installed execution uses one verified release and one recorded interpreter."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import socket
import subprocess
import sys

import pytest

import release_runtime as runtime
import system_contract


SCRIPT = "synthesis-repo-guard/repo_sync_check.py"


@pytest.fixture
def active(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHESIS_PUBLIC_SKILLS_SOURCE", raising=False)
    root = tmp_path / "generation"
    target = root / "skills" / SCRIPT
    target.parent.mkdir(parents=True)
    target.write_text("import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\nsys.exit(int(sys.argv[1]) if len(sys.argv) > 1 else 0)\n")
    for client in ("claude", "codex"):
        manifest = root / ("." + client + "-plugin") / "plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({"name": "synthesis-skills", "version": "9.8.7"}))
    pointer = tmp_path / "state" / "active-release.json"
    pointer.parent.mkdir()
    pointer.with_name(pointer.name + ".lock").touch()
    data = {
        "schema_version": 1, "version": "9.8.7", "channel": "stable", "ref": "stable",
        "commit": "1" * 40, "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(root),
        "digest_algorithm": "sha256-tree-v1", "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/skills.git", "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(root), "interpreter": runtime.interpreter_pin(),
    }
    launcher = pointer.parent.parent / "bin/synthesis"
    launcher.parent.mkdir()
    content = system_contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    data["launcher"] = {"path": str(launcher), "runtime_schema": 1, "sha256": hashlib.sha256(content).hexdigest()}
    pointer.write_text(json.dumps(data))
    return pointer, root, data


def replace(pointer, data, **changes):
    data = {**data, **changes}
    pointer.write_text(json.dumps(data))
    return data


def test_setup_records_current_absolute_interpreter_identity():
    pin = runtime.interpreter_pin()
    assert Path(pin["executable"]).is_absolute()
    assert Path(pin["resolved_executable"]) == Path(pin["executable"]).resolve()
    assert pin["version"] == ".".join(str(v) for v in sys.version_info[:3])
    assert pin["sha256"] == hashlib.sha256(Path(pin["resolved_executable"]).read_bytes()).hexdigest()
    assert runtime.verify_interpreter(pin) == pin["executable"]


def test_macos_pin_uses_prescribed_framework_and_refuses_other_version(monkeypatch):
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    assert runtime.selected_interpreter() == "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    with pytest.raises(runtime.RuntimeContractError, match="3.12.3"):
        runtime.validate_python_version("3.14.0", platform="darwin")


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("version", "3.14.0"), ("executable", "python3")])
def test_interpreter_drift_or_unpinned_path_refuses(active, field, value):
    pointer, _, data = active
    replace(pointer, data, interpreter={**data["interpreter"], field: value})
    with pytest.raises(runtime.RuntimeContractError):
        runtime.verified_release(pointer)


def test_active_release_is_verified_and_uses_current_pinned_executable(active):
    pointer, root, _ = active
    verified = runtime.verified_release(pointer)
    assert runtime.command(verified, SCRIPT, ["--example"]) == [sys.executable, "-B", str(root / "skills" / SCRIPT), "--example"]


def test_tree_hash_contract_matches_the_existing_release_format(active):
    _, root, data = active
    assert runtime.tree_digest(root) == data["content_digest"]


@pytest.mark.parametrize("change", ["missing", "invalid-json", "wrong-root", "tree-drift", "symlink-root", "symlink-file"])
def test_unverified_release_never_becomes_an_execution_root(active, tmp_path, change):
    pointer, root, data = active
    if change == "missing":
        pointer.unlink()
    elif change == "invalid-json":
        pointer.write_text("broken")
    elif change == "wrong-root":
        replace(pointer, data, release_root=str(tmp_path / "absent"))
    elif change == "tree-drift":
        (root / "skills" / SCRIPT).write_text("raise SystemExit(0)\n")
    elif change == "symlink-root":
        link = tmp_path / "linked-generation"
        link.symlink_to(root)
        replace(pointer, data, release_root=str(link))
    else:
        target = root / "skills" / SCRIPT
        target.unlink()
        target.symlink_to(pointer)
    with pytest.raises(runtime.RuntimeContractError):
        runtime.verified_release(pointer)


@pytest.mark.parametrize("script", ["../outside.py", "/tmp/outside.py", "synthesis-repo-guard/../repo_sync_check.py", "unknown/script.py"])
def test_only_declared_contained_public_entrypoints_are_executable(active, script):
    pointer, _, _ = active
    verified = runtime.verified_release(pointer)
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, [])


def test_canonical_source_override_is_explicitly_rejected(active, monkeypatch):
    pointer, root, _ = active
    monkeypatch.setenv("SYNTHESIS_PUBLIC_SKILLS_SOURCE", str(root / "skills"))
    with pytest.raises(runtime.RuntimeContractError, match="source override"):
        runtime.verified_release(pointer)


def test_child_bytes_and_attention_exit_are_preserved(active):
    pointer, _, _ = active
    verified = runtime.verified_release(pointer)
    result = runtime.execute(verified, SCRIPT, ["1"], b"\x00payload\xff", timeout=2)
    assert result.returncode == 1
    assert result.stdout == b"\x00payload\xff"
    assert result.stderr == b""


def test_hostile_path_cannot_choose_child_interpreter(active, tmp_path, monkeypatch):
    pointer, _, _ = active
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    fake = hostile / "python3"
    fake.write_text("#!/bin/sh\nprintf hijacked\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(hostile))
    result = runtime.execute(runtime.verified_release(pointer), SCRIPT, [], b"expected", timeout=2)
    assert result.stdout == b"expected"


def test_child_timeout_and_start_failure_are_not_normalized(active, monkeypatch):
    pointer, _, _ = active
    verified = runtime.verified_release(pointer)
    for error in (subprocess.TimeoutExpired(["fixture"], 0.01), OSError("injected start failure")):
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(runtime.subprocess, "run", fail)
        with pytest.raises(runtime.RuntimeContractError):
            runtime.execute(verified, SCRIPT, [], b"", timeout=0.01)


def managed_fixture(active):
    pointer, root, data = active
    launcher = pointer.parent.parent / "bin/synthesis"
    launcher.parent.mkdir(exist_ok=True)
    content = system_contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    data = replace(pointer, data, launcher={"path": str(launcher), "runtime_schema": 1, "sha256": hashlib.sha256(content).hexdigest()})
    return launcher, data


def test_managed_public_cli_preserves_bytes_and_explicit_attention_adapter(active):
    launcher, _ = managed_fixture(active)
    result = subprocess.run([str(launcher), "exec-public", "--success-exit-code", "1", SCRIPT, "--", "1"], input=b"\x00exact\xff", capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"\x00exact\xff"
    unadapted = subprocess.run([str(launcher), "exec-public", SCRIPT, "--", "1"], input=b"payload", capture_output=True)
    assert unadapted.returncode == 1 and unadapted.stdout == b"payload"


def test_managed_public_cli_cannot_normalize_runtime_failure(active):
    pointer, root, data = active
    (root / "skills" / SCRIPT).write_text("import time\ntime.sleep(1)\n")
    data = replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    launcher, _ = managed_fixture((pointer, root, data))
    result = subprocess.run([str(launcher), "exec-public", "--timeout-seconds", "0.01", "--success-exit-code", "1", SCRIPT], input=b"", capture_output=True)
    assert result.returncode == 2 and b"failed to start or finish" in result.stderr
    forbidden = subprocess.run([str(launcher), "exec-public", "--success-exit-code", "2", SCRIPT], input=b"", capture_output=True)
    assert forbidden.returncode == 2 and b"invalid choice" in forbidden.stderr


def test_public_cli_reads_payload_from_held_open_harness_socket(active):
    launcher, _ = managed_fixture(active)
    reader, writer = socket.socketpair()
    try:
        writer.sendall(b"socket payload")
        result = subprocess.run([str(launcher), "exec-public", "--stdin-wait-seconds", "0.01", SCRIPT], stdin=reader, capture_output=True, timeout=2)
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"socket payload"
    finally:
        reader.close()
        writer.close()


def test_doctor_checks_launcher_and_guardian_against_setup_pin(active, tmp_path):
    launcher, data = managed_fixture(active)
    assert runtime.runtime_health(data, home=tmp_path)["status"] == "verified"
    plist = tmp_path / "Library/LaunchAgents/org.synthesisengineering.synthesis-skills-cache-guardian.plist"
    plist.parent.mkdir(parents=True)
    plist.write_bytes(plistlib.dumps({"ProgramArguments": [data["interpreter"]["executable"], "-B", "/fixture/guardian.py", "--watch"]}))
    assert runtime.runtime_health(data, home=tmp_path)["guardian_declarations"] == 1
    plist.write_bytes(plistlib.dumps({"ProgramArguments": ["python3", "/fixture/guardian.py", "--watch"]}))
    with pytest.raises(runtime.RuntimeContractError, match="guardian service"):
        runtime.runtime_health(data, home=tmp_path)
    alias = tmp_path / "python3-alias"
    alias.symlink_to(data["interpreter"]["executable"])
    plist.write_bytes(plistlib.dumps({"ProgramArguments": [str(alias), "-B", "/fixture/guardian.py", "--watch"]}))
    assert runtime.runtime_health(data, home=tmp_path)["guardian_declarations"] == 1
    plist.unlink()
    launcher.write_bytes(launcher.read_bytes() + b"\n# unreceipted edit\n")
    with pytest.raises(runtime.RuntimeContractError, match="launcher differs"):
        runtime.runtime_health(data, home=tmp_path)


def write_receipt(pointer, root, data):
    blob = pointer.read_bytes()
    meta = pointer.lstat()
    receipt = runtime.build_activation_receipt(
        release_root=root, descriptor_bytes=blob, descriptor_meta=meta,
        launcher_sha256=data["launcher"]["sha256"],
        interpreter_sha256=data["interpreter"]["sha256"],
        generation=data.get("generation", data.get("version")),
        content_digest=data["content_digest"], projection=data.get("projection"))
    runtime.activation_receipt_path(pointer).write_text(json.dumps(receipt))
    return receipt


def test_receipt_fast_path_skips_the_tree_digest(active, monkeypatch):
    pointer, root, data = active
    write_receipt(pointer, root, data)
    monkeypatch.setattr(runtime, "tree_digest",
                        lambda root: (_ for _ in ()).throw(AssertionError("full digest ran")))
    checked = runtime.verified_release(pointer)
    assert checked["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    argv = runtime.command(checked, SCRIPT, [])
    assert argv[1:] and argv[1] == "-B"


def test_stat_walk_catches_a_modified_helper(active):
    pointer, root, data = active
    write_receipt(pointer, root, data)
    target = root / "skills" / SCRIPT
    target.write_text(target.read_text() + "\n# drift\n")
    with pytest.raises(runtime.RuntimeContractError, match="stat drifted"):
        runtime.verified_release(pointer)


def test_same_size_mtime_swap_passes_fast_but_fails_full(active):
    import os
    pointer, root, data = active
    write_receipt(pointer, root, data)
    target = root / "skills" / SCRIPT
    original = target.read_bytes()
    swapped = bytes(b ^ 0x01 for b in original)
    assert len(swapped) == len(original)
    meta = target.lstat()
    target.write_bytes(swapped)
    os.utime(target, ns=(meta.st_atime_ns, meta.st_mtime_ns))
    checked = runtime.verified_release(pointer)  # the accepted A1 residual
    assert checked["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    report = runtime.full_digest_report(root)
    assert report["tree_digest"] != data["content_digest"]
    assert report["files"] >= 1


def test_swapped_descriptor_refuses_next_call(active):
    import os
    pointer, root, data = active
    write_receipt(pointer, root, data)
    replace(pointer, data, resolved_at="2026-06-06T06:06:06Z")
    with pytest.raises(runtime.RuntimeContractError, match="replaced since activation"):
        runtime.verified_release(pointer)
    receipt = json.loads(runtime.activation_receipt_path(pointer).read_text())
    meta = pointer.lstat()
    os.utime(pointer, ns=(meta.st_atime_ns, receipt["descriptor_mtime_ns"]))
    with pytest.raises(runtime.RuntimeContractError, match="descriptor bytes drifted"):
        runtime.verified_release(pointer)


def test_missing_receipt_keeps_the_legacy_full_digest(active):
    pointer, root, data = active
    checked = runtime.verified_release(pointer)
    assert checked["_verification_mode"] == runtime.VERIFICATION_MODE_FULL
    target = root / "skills" / SCRIPT
    target.write_text(target.read_text() + "\n# drift\n")
    with pytest.raises(runtime.RuntimeContractError, match="content digest drifted"):
        runtime.verified_release(pointer)


def test_entrypoint_swap_refuses_on_the_public_route(active):
    import os
    pointer, root, data = active
    write_receipt(pointer, root, data)
    target = root / "skills" / SCRIPT
    original = target.read_bytes()
    meta = target.lstat()
    target.write_bytes(bytes(b ^ 0x01 for b in original))
    os.utime(target, ns=(meta.st_atime_ns, meta.st_mtime_ns))
    checked = runtime.verified_release(pointer)
    with pytest.raises(runtime.RuntimeContractError, match="entrypoint bytes drifted"):
        runtime.command(checked, SCRIPT, [])


def test_modular_projection_pays_one_stat_walk(active, monkeypatch):
    pointer, root, data = active
    inventory = {rel: {"sha256": "0" * 64, "mode": fields[1]}
                 for rel, fields in runtime.stat_walk(root).items()}
    data = replace(pointer, data, projection={
        "schema_version": 1, "kind": "modular",
        "content_digest": data["content_digest"],
        "source_content_digest": data["content_digest"],
        "selection": {"roots": ["a"], "skills": ["a"], "support_skills": [], "stage_core": False},
        "files": inventory})
    write_receipt(pointer, root, data)
    walks = []
    real_walk = runtime.stat_walk

    def counting_walk(root):
        walks.append(1)
        return real_walk(root)

    monkeypatch.setattr(runtime, "stat_walk", counting_walk)
    monkeypatch.setattr(runtime, "tree_digest",
                        lambda root: (_ for _ in ()).throw(AssertionError("full digest ran")))
    checked = runtime.verified_release(pointer)
    assert checked["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    assert len(walks) == 1


GUARD = "synthesis-agent-guardrails/guards/account_routing_guard.py"


def test_declared_guard_entrypoint_executes_from_the_verified_release(tmp_path, monkeypatch):
    assert GUARD in runtime.PUBLIC_ENTRYPOINTS
    monkeypatch.delenv("SYNTHESIS_PUBLIC_SKILLS_SOURCE", raising=False)
    root = tmp_path / "generation"
    target = root / "skills" / GUARD
    target.parent.mkdir(parents=True)
    target.write_text("import sys\nsys.stdout.write('guard-ok\\n')\n")
    for client in ("claude", "codex"):
        manifest = root / ("." + client + "-plugin") / "plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({"name": "synthesis-skills", "version": "9.8.7"}))
    pointer = tmp_path / "state" / "active-release.json"
    pointer.parent.mkdir()
    pointer.with_name(pointer.name + ".lock").touch()
    data = {
        "schema_version": 1, "version": "9.8.7", "channel": "stable", "ref": "stable",
        "commit": "1" * 40, "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(root),
        "digest_algorithm": "sha256-tree-v1", "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/skills.git", "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(root), "interpreter": runtime.interpreter_pin(),
    }
    launcher = pointer.parent.parent / "bin/synthesis"
    launcher.parent.mkdir()
    content = system_contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    data["launcher"] = {"path": str(launcher), "runtime_schema": 1, "sha256": hashlib.sha256(content).hexdigest()}
    pointer.write_text(json.dumps(data))
    verified = runtime.verified_release(pointer)
    assert runtime.command(verified, GUARD, ["--doctor"]) == [sys.executable, "-B", str(target), "--doctor"]
    result = runtime.execute(verified, GUARD, [], b"{}", timeout=10)
    assert result.returncode == 0
    assert result.stdout == b"guard-ok\n"

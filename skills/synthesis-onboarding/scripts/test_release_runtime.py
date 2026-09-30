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
    target.write_text(
        "import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\nsys.exit(int(sys.argv[1]) if len(sys.argv) > 1 else 0)\n"
    )
    for client in ("claude", "codex"):
        manifest = root / ("." + client + "-plugin") / "plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(
            json.dumps({"name": "synthesis-skills", "version": "9.8.7"})
        )
    pointer = tmp_path / "state" / "active-release.json"
    pointer.parent.mkdir()
    pointer.with_name(pointer.name + ".lock").touch()
    data = {
        "schema_version": 1,
        "version": "9.8.7",
        "channel": "stable",
        "ref": "stable",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(root),
        "digest_algorithm": "sha256-tree-v1",
        "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/skills.git",
        "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(root),
        "interpreter": runtime.interpreter_pin(),
    }
    launcher = pointer.parent.parent / "bin/synthesis"
    launcher.parent.mkdir()
    content = system_contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    data["launcher"] = {
        "path": str(launcher),
        "runtime_schema": 1,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
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
    assert (
        pin["sha256"]
        == hashlib.sha256(Path(pin["resolved_executable"]).read_bytes()).hexdigest()
    )
    assert runtime.verify_interpreter(pin) == pin["executable"]


def test_macos_pin_uses_prescribed_framework_and_refuses_other_version(monkeypatch):
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    assert (
        runtime.selected_interpreter()
        == "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    )
    with pytest.raises(runtime.RuntimeContractError, match="3.12.3"):
        runtime.validate_python_version("3.14.0", platform="darwin")


@pytest.mark.parametrize(
    "field,value",
    [("sha256", "0" * 64), ("version", "3.14.0"), ("executable", "python3")],
)
def test_interpreter_drift_or_unpinned_path_refuses(active, field, value):
    pointer, _, data = active
    replace(pointer, data, interpreter={**data["interpreter"], field: value})
    with pytest.raises(runtime.RuntimeContractError):
        runtime.verified_release(pointer)


def test_active_release_is_verified_and_uses_current_pinned_executable(active):
    pointer, root, _ = active
    verified = runtime.verified_release(pointer)
    argv = runtime.command(verified, SCRIPT, ["--example"])
    assert argv[:5] == [sys.executable, "-B", "-I", "-S", "-c"]
    assert argv[-2:] == [str(root / "skills" / SCRIPT), "--example"]
    assert argv[6] == str(root)


def test_tree_hash_contract_matches_the_existing_release_format(active):
    _, root, data = active
    assert runtime.tree_digest(root) == data["content_digest"]


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "invalid-json",
        "wrong-root",
        "tree-drift",
        "symlink-root",
        "symlink-file",
    ],
)
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


@pytest.mark.parametrize(
    "script",
    [
        "../outside.py",
        "/tmp/outside.py",
        "synthesis-repo-guard/../repo_sync_check.py",
        "unknown/script.py",
    ],
)
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
    result = runtime.execute(
        runtime.verified_release(pointer), SCRIPT, [], b"expected", timeout=2
    )
    assert result.stdout == b"expected"


def test_child_timeout_and_start_failure_are_not_normalized(active, monkeypatch):
    pointer, _, _ = active
    verified = runtime.verified_release(pointer)
    for error in (
        subprocess.TimeoutExpired(["fixture"], 0.01),
        OSError("injected start failure"),
    ):

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
    data = replace(
        pointer,
        data,
        launcher={
            "path": str(launcher),
            "runtime_schema": 1,
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )
    return launcher, data


def test_managed_public_cli_preserves_bytes_and_explicit_attention_adapter(active):
    launcher, _ = managed_fixture(active)
    result = subprocess.run(
        [str(launcher), "exec-public", "--success-exit-code", "1", SCRIPT, "--", "1"],
        input=b"\x00exact\xff",
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"\x00exact\xff"
    unadapted = subprocess.run(
        [str(launcher), "exec-public", SCRIPT, "--", "1"],
        input=b"payload",
        capture_output=True,
    )
    assert unadapted.returncode == 1 and unadapted.stdout == b"payload"


def test_managed_public_cli_cannot_normalize_runtime_failure(active):
    pointer, root, data = active
    (root / "skills" / SCRIPT).write_text("import time\ntime.sleep(1)\n")
    data = replace(
        pointer, data, content_digest=system_contract.canonical_tree_digest(root)
    )
    launcher, _ = managed_fixture((pointer, root, data))
    result = subprocess.run(
        [
            str(launcher),
            "exec-public",
            "--timeout-seconds",
            "0.01",
            "--success-exit-code",
            "1",
            SCRIPT,
        ],
        input=b"",
        capture_output=True,
    )
    assert result.returncode == 2
    assert any(
        reason in result.stderr
        for reason in (b"failed to start or finish", b"exceeded its total deadline")
    )
    forbidden = subprocess.run(
        [str(launcher), "exec-public", "--success-exit-code", "2", SCRIPT],
        input=b"",
        capture_output=True,
    )
    assert forbidden.returncode == 2 and b"invalid choice" in forbidden.stderr


def test_public_cli_reads_payload_from_held_open_harness_socket(active):
    launcher, _ = managed_fixture(active)
    reader, writer = socket.socketpair()
    try:
        writer.sendall(b"socket payload")
        result = subprocess.run(
            [str(launcher), "exec-public", "--stdin-wait-seconds", "0.01", SCRIPT],
            stdin=reader,
            capture_output=True,
            timeout=2,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"socket payload"
    finally:
        reader.close()
        writer.close()


def test_doctor_checks_launcher_and_guardian_against_setup_pin(active, tmp_path):
    launcher, data = managed_fixture(active)
    assert runtime.runtime_health(data, home=tmp_path)["status"] == "verified"
    plist = (
        tmp_path
        / "Library/LaunchAgents/org.synthesisengineering.synthesis-skills-cache-guardian.plist"
    )
    plist.parent.mkdir(parents=True)
    plist.write_bytes(
        plistlib.dumps(
            {
                "ProgramArguments": [
                    data["interpreter"]["executable"],
                    "-B",
                    "/fixture/guardian.py",
                    "--watch",
                ]
            }
        )
    )
    assert runtime.runtime_health(data, home=tmp_path)["guardian_declarations"] == 1
    plist.write_bytes(
        plistlib.dumps(
            {"ProgramArguments": ["python3", "/fixture/guardian.py", "--watch"]}
        )
    )
    with pytest.raises(runtime.RuntimeContractError, match="guardian service"):
        runtime.runtime_health(data, home=tmp_path)
    alias = tmp_path / "python3-alias"
    alias.symlink_to(data["interpreter"]["executable"])
    plist.write_bytes(
        plistlib.dumps(
            {"ProgramArguments": [str(alias), "-B", "/fixture/guardian.py", "--watch"]}
        )
    )
    assert runtime.runtime_health(data, home=tmp_path)["guardian_declarations"] == 1
    plist.unlink()
    launcher.write_bytes(launcher.read_bytes() + b"\n# unreceipted edit\n")
    with pytest.raises(runtime.RuntimeContractError, match="launcher differs"):
        runtime.runtime_health(data, home=tmp_path)


def write_receipt(pointer, root, data):
    blob = pointer.read_bytes()
    meta = pointer.lstat()
    receipt = runtime.build_activation_receipt(
        release_root=root,
        descriptor_bytes=blob,
        descriptor_meta=meta,
        launcher_sha256=data["launcher"]["sha256"],
        interpreter_sha256=data["interpreter"]["sha256"],
        generation=data.get("generation", data.get("version")),
        content_digest=data["content_digest"],
        projection=data.get("projection"),
    )
    runtime.activation_receipt_path(pointer).write_text(json.dumps(receipt))
    return receipt


def test_receipt_fast_path_skips_the_tree_digest(active, monkeypatch):
    pointer, root, data = active
    write_receipt(pointer, root, data)
    monkeypatch.setattr(
        runtime,
        "tree_digest",
        lambda root: (_ for _ in ()).throw(AssertionError("full digest ran")),
    )
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
    receipt = write_receipt(pointer, root, data)
    replace(pointer, data, resolved_at="2026-06-06T06:06:06Z")
    # Filesystems may coalesce immediate rewrites into one timestamp tick.
    # Exercise metadata refusal deterministically before the byte-drift case.
    os.utime(
        pointer,
        ns=(pointer.stat().st_atime_ns, receipt["descriptor_mtime_ns"] + 1_000_000_000),
    )
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
    inventory = {
        rel: {"sha256": "0" * 64, "mode": fields[1]}
        for rel, fields in runtime.stat_walk(root).items()
    }
    data = replace(
        pointer,
        data,
        projection={
            "schema_version": 1,
            "kind": "modular",
            "content_digest": data["content_digest"],
            "source_content_digest": data["content_digest"],
            "selection": {
                "roots": ["a"],
                "skills": ["a"],
                "support_skills": [],
                "stage_core": False,
            },
            "files": inventory,
        },
    )
    write_receipt(pointer, root, data)
    walks = []
    real_walk = runtime.stat_walk

    def counting_walk(root):
        walks.append(1)
        return real_walk(root)

    monkeypatch.setattr(runtime, "stat_walk", counting_walk)
    monkeypatch.setattr(
        runtime,
        "tree_digest",
        lambda root: (_ for _ in ()).throw(AssertionError("full digest ran")),
    )
    checked = runtime.verified_release(pointer)
    assert checked["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    assert len(walks) == 1


GUARDS = (
    "synthesis-agent-guardrails/guards/account_routing_guard.py",
    "synthesis-agent-guardrails/guards/publish_guard.py",
)


HOOKS = (
    "synthesis-agent-guardrails/hooks/claude/bare_filename_detector.py",
    "synthesis-agent-guardrails/hooks/claude/lazy_shortcut_detector.py",
    "synthesis-agent-guardrails/hooks/claude/long_session_detector.py",
    "synthesis-agent-guardrails/hooks/claude/pre_tool_temporal_reminder.py",
    "synthesis-agent-guardrails/hooks/claude/quote_provenance_checker.py",
    "synthesis-agent-guardrails/hooks/claude/sub_agent_brief_scanner.py",
    "synthesis-agent-guardrails/hooks/codex/bare_filename_detector.py",
    "synthesis-agent-guardrails/hooks/codex/installed_skill_edit_guard.py",
    "synthesis-agent-guardrails/hooks/codex/lazy_shortcut_detector.py",
    "synthesis-agent-guardrails/hooks/codex/quote_provenance_checker.py",
    "synthesis-agent-guardrails/hooks/codex/repo_guard_stop.py",
    "synthesis-agent-guardrails/hooks/codex/session_end_checkpoint.py",
    "synthesis-agent-guardrails/hooks/muse/lazy_shortcut_detector.py",
)


@pytest.mark.parametrize("guard", GUARDS)
def test_declared_guard_entrypoint_executes_from_the_verified_release(
    tmp_path, monkeypatch, guard
):
    assert guard in runtime.PUBLIC_ENTRYPOINTS
    monkeypatch.delenv("SYNTHESIS_PUBLIC_SKILLS_SOURCE", raising=False)
    root = tmp_path / "generation"
    target = root / "skills" / guard
    target.parent.mkdir(parents=True)
    target.write_text("import sys\nsys.stdout.write('guard-ok\\n')\n")
    for relative in runtime.ENTRYPOINT_DEPENDENCIES.get(guard, ()):
        helper = root / "skills" / relative
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_text("pass\n")
    for client in ("claude", "codex"):
        manifest = root / ("." + client + "-plugin") / "plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(
            json.dumps({"name": "synthesis-skills", "version": "9.8.7"})
        )
    pointer = tmp_path / "state" / "active-release.json"
    pointer.parent.mkdir()
    pointer.with_name(pointer.name + ".lock").touch()
    data = {
        "schema_version": 1,
        "version": "9.8.7",
        "channel": "stable",
        "ref": "stable",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(root),
        "digest_algorithm": "sha256-tree-v1",
        "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/skills.git",
        "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(root),
        "interpreter": runtime.interpreter_pin(),
    }
    launcher = pointer.parent.parent / "bin/synthesis"
    launcher.parent.mkdir()
    content = system_contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    data["launcher"] = {
        "path": str(launcher),
        "runtime_schema": 1,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    pointer.write_text(json.dumps(data))
    verified = runtime.verified_release(pointer)
    argv = runtime.command(verified, guard, ["--doctor"])
    assert argv[:5] == [sys.executable, "-B", "-I", "-S", "-c"]
    assert argv[-2:] == [str(target), "--doctor"]
    assert argv[6] == str(root)
    result = runtime.execute(verified, guard, [], b"{}", timeout=10)
    assert result.returncode == 0
    assert result.stdout == b"guard-ok\n"


@pytest.mark.parametrize("hook", HOOKS)
def test_declared_hook_entrypoint_executes_from_the_verified_release(
    tmp_path, monkeypatch, hook
):
    assert hook in runtime.PUBLIC_ENTRYPOINTS
    assert hook in runtime.RECEIPT_ENTRYPOINTS
    monkeypatch.delenv("SYNTHESIS_PUBLIC_SKILLS_SOURCE", raising=False)
    root = tmp_path / "generation"
    target = root / "skills" / hook
    target.parent.mkdir(parents=True)
    target.write_text("import sys\nsys.stdout.write('hook-ok\\n')\n")
    for client in ("claude", "codex"):
        manifest = root / ("." + client + "-plugin") / "plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(
            json.dumps({"name": "synthesis-skills", "version": "9.8.7"})
        )
    pointer = tmp_path / "state" / "active-release.json"
    pointer.parent.mkdir()
    pointer.with_name(pointer.name + ".lock").touch()
    data = {
        "schema_version": 1,
        "version": "9.8.7",
        "channel": "stable",
        "ref": "stable",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(root),
        "digest_algorithm": "sha256-tree-v1",
        "tree_policy": "regular-files-and-directories-no-links-v1",
        "source_url": "https://example.test/skills.git",
        "resolved_at": "2026-01-01T00:00:00Z",
        "release_root": str(root),
        "interpreter": runtime.interpreter_pin(),
    }
    launcher = pointer.parent.parent / "bin/synthesis"
    launcher.parent.mkdir()
    content = system_contract.launcher_bytes(pointer, data["interpreter"])
    launcher.write_bytes(content)
    launcher.chmod(0o755)
    data["launcher"] = {
        "path": str(launcher),
        "runtime_schema": 1,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    pointer.write_text(json.dumps(data))
    verified = runtime.verified_release(pointer)
    argv = runtime.command(verified, hook, ["--doctor"])
    assert argv[:5] == [sys.executable, "-B", "-I", "-S", "-c"]
    assert argv[-2:] == [str(target), "--doctor"]
    assert argv[6] == str(root)
    result = runtime.execute(verified, hook, [], b"{}", timeout=10)
    assert result.returncode == 0
    assert result.stdout == b"hook-ok\n"


@pytest.mark.parametrize("relative_root", [False, True])
def test_stat_inventory_preserves_nested_names_and_exact_metadata(
    tmp_path, monkeypatch, relative_root
):
    root = tmp_path / "release tree"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".git/ignored").write_text("outside release inventory")
    expected = {}
    for name, mode in [
        ("top.py", 0o640),
        ("nested/.git/retained", 0o600),
        ("nested/space [x]/café.py", 0o755),
    ]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
        path.chmod(mode)
        meta = path.stat()
        expected[name] = [meta.st_size, mode, meta.st_mtime_ns]
    monkeypatch.chdir(tmp_path)
    selected = Path("release tree") if relative_root else root
    assert runtime.stat_walk(selected) == expected
    (root / "added").write_text("new file")
    assert set(runtime.stat_walk(selected)) == set(expected) | {"added"}


@pytest.mark.parametrize("object_kind", ["file-link", "directory-link", "fifo"])
def test_stat_inventory_refuses_nested_link_or_special_object(tmp_path, object_kind):
    root = tmp_path / "release"
    root.mkdir()
    nested = root / "nested"
    nested.mkdir()
    target = nested / "untrusted"
    if object_kind == "fifo":
        import os

        os.mkfifo(target)
    else:
        outside = tmp_path / "outside"
        if object_kind == "directory-link":
            outside.mkdir()
        else:
            outside.write_text("retained sentinel")
        target.symlink_to(outside, target_is_directory=object_kind == "directory-link")
    with pytest.raises(runtime.RuntimeContractError, match="link or special"):
        runtime.stat_walk(root)


RITUAL_HELPERS = (
    "portfolio_review",
    "decay_sweep",
    "pr_queue_scan",
    "sync_watermark",
    "gchat_preflight",
)


@pytest.mark.parametrize("name", RITUAL_HELPERS)
def test_real_ritual_helper_uses_verified_owner_and_help_only(active, name):
    """Actual shipped source and owned dependency, no provider or workspace read."""
    pointer, root, data = active
    repository = Path(__file__).resolve().parents[3]
    script = f"synthesis-daily-rituals/scripts/{name}.py"
    for relative in (script, *runtime.ENTRYPOINT_DEPENDENCIES.get(script, ())):
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repository / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    result = runtime.execute(verified, script, ["--help"], b"", timeout=5)
    assert result.returncode == 0, result.stderr
    assert b"usage:" in result.stdout.lower()


@pytest.mark.parametrize("change", ["missing", "link", "same-stat-tamper"])
def test_ritual_owned_dependency_refuses_before_execution(active, change, monkeypatch):
    pointer, root, data = active
    script = "synthesis-daily-rituals/scripts/pr_queue_scan.py"
    dependency = runtime.ENTRYPOINT_DEPENDENCIES[script][0]
    for relative in (script, dependency):
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("pass\n")
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    monkeypatch.setattr(
        runtime,
        "_load_activation_receipt",
        lambda p: {
            "entrypoints": {
                relative: runtime.file_digest(root / "skills" / relative)
                for relative in (script, dependency)
            }
        },
    )
    hashes = {
        relative: runtime.file_digest(root / "skills" / relative)
        for relative in (script, dependency)
    }
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda p: {"entrypoints": hashes}
    )
    helper = root / "skills" / dependency
    if change == "missing":
        helper.unlink()
    elif change == "link":
        helper.unlink()
        helper.symlink_to(root / "skills" / script)
    else:
        before = helper.stat()
        helper.write_text("fail\n")
        os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, ["--help"])


def test_callable_ritual_surface_is_the_explicit_owned_helpers():
    declared = {
        Path(path).stem
        for path in runtime.PUBLIC_ENTRYPOINTS
        if path.startswith("synthesis-daily-rituals/")
    }
    assert declared == set(RITUAL_HELPERS) | {"ritual_state", "repo_state"}
    assert (
        "synthesis-daily-rituals/scripts/ritual_workers.py"
        not in runtime.PUBLIC_ENTRYPOINTS
    )
    assert (
        "synthesis-daily-rituals/scripts/credential_paths.py"
        not in runtime.PUBLIC_ENTRYPOINTS
    )


def test_modular_pr_scan_without_optional_bitbucket_helper_retains_github_availability(
    active, monkeypatch
):
    pointer, root, data = active
    script = "synthesis-daily-rituals/scripts/pr_queue_scan.py"
    target = root / "skills" / script
    target.parent.mkdir(parents=True)
    target.write_bytes(
        (Path(__file__).resolve().parents[3] / "skills" / script).read_bytes()
    )
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {script: runtime.file_digest(target)}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda p: {"entrypoints": hashes}
    )
    result = runtime.execute(verified, script, ["--help"], b"", timeout=5)
    assert result.returncode == 0, result.stderr


TRANSACTION_HELPER = "synthesis-context-lifecycle/scripts/record_transaction.py"
TRANSACTION_CONSUMERS = (
    "synthesis-context-lifecycle/scripts/context_doctor.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-agent-conformance/scripts/conformance.py",
    "synthesis-agent-conformance/scripts/session_context.py",
    "synthesis-repo-guard/checkpoint_sync.py",
    "synthesis-autopilot/scripts/autopilot_gate.py",
)


@pytest.mark.parametrize(
    "helper_name",
    [
        TRANSACTION_HELPER,
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
    ],
)
@pytest.mark.parametrize("script", TRANSACTION_CONSUMERS)
@pytest.mark.parametrize("damage", ["missing", "link", "same-stat-tamper"])
def test_transaction_dependency_is_verified_before_managed_execution(
    active, monkeypatch, script, damage, helper_name
):
    pointer, root, data = active
    target = root / "skills" / script
    helper = root / "skills" / helper_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("pass\n")
    dependency_names = runtime.ENTRYPOINT_DEPENDENCIES[script]
    for name in dependency_names:
        dependency = root / "skills" / name
        dependency.parent.mkdir(parents=True, exist_ok=True)
        dependency.write_text("pass\n")
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {
        name: runtime.file_digest(root / "skills" / name)
        for name in (script, *dependency_names)
    }
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda p: {"entrypoints": hashes}
    )
    assert runtime.command(verified, script, ["--help"])
    if damage == "missing":
        helper.unlink()
    elif damage == "link":
        helper.unlink()
        helper.symlink_to(target)
    else:
        before = helper.stat()
        helper.write_text("fail\n")
        os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, ["--help"])


@pytest.mark.parametrize("script", TRANSACTION_CONSUMERS)
def test_real_managed_transaction_consumer_help_uses_complete_release(active, script):
    import shutil

    pointer, root, data = active
    repository = Path(__file__).resolve().parents[3]
    shutil.copytree(
        repository / "skills",
        root / "skills",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    result = runtime.execute(
        runtime.verified_release(pointer), script, ["--help"], b"", timeout=10
    )
    assert result.returncode == 0, result.stderr
    expected = (
        b"native stop entry point"
        if script.endswith("/autopilot_gate.py")
        else b"usage:"
    )
    assert expected in result.stdout.lower()


def test_acquisition_dependency_closure_runs_real_installed_owner(
    active, tmp_path, monkeypatch
):
    """No provider or global write: exact real selected-release source, synthetic refusal."""
    pointer, root, data = active
    repository = Path(__file__).resolve().parents[3]
    script = "synthesis-daily-rituals/scripts/sync_watermark.py"
    for relative in (script, *runtime.ENTRYPOINT_DEPENDENCIES[script]):
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repository / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "synthetic-state"))
    result = runtime.execute(
        runtime.verified_release(pointer),
        script,
        [
            "advance",
            "--workspace",
            "fixture",
            "--surface",
            "meetings",
            "--through",
            "2026-09-25T00:00:00+00:00",
        ],
        b"",
        timeout=10,
    )
    assert result.returncode == 2
    assert b"acquisition evidence" in result.stderr
    assert not (tmp_path / "synthetic-state/sync-watermarks/fixture.json").exists()


@pytest.mark.parametrize(
    "relative",
    [
        "synthesis-daily-rituals/scripts/acquisition_evidence.py",
        "synthesis-daily-rituals/scripts/ritual_workers.py",
        "synthesis-meeting-transcripts/verify_transcripts.py",
    ],
)
def test_acquisition_owned_dependency_cannot_be_missing(active, relative):
    pointer, root, data = active
    script = "synthesis-daily-rituals/scripts/sync_watermark.py"
    for path in (script, *runtime.ENTRYPOINT_DEPENDENCIES[script]):
        if path == relative:
            continue
        target = root / "skills" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('raise AssertionError("must never execute")\n')
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    with pytest.raises(runtime.RuntimeContractError):
        runtime.execute(
            runtime.verified_release(pointer), script, ["--help"], b"", timeout=5
        )


@pytest.mark.parametrize("script", TRANSACTION_CONSUMERS)
@pytest.mark.parametrize("damage", ["missing", "link", "same-stat-tamper"])
def test_publication_proof_dependency_verified_before_consumer(
    active, monkeypatch, script, damage
):
    pointer, root, data = active
    dep = "synthesis-repo-guard/publication_receipt.py"
    names = tuple(
        dict.fromkeys((script, *runtime.ENTRYPOINT_DEPENDENCIES[script], dep))
    )
    for name in names:
        target = root / "skills" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("pass\n")
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _p: {"entrypoints": hashes}
    )
    helper = root / "skills" / dep
    if damage == "missing":
        helper.unlink()
    elif damage == "link":
        helper.unlink()
        helper.symlink_to(root / "skills" / script)
    else:
        before = helper.stat()
        helper.write_text("fail\n")
        os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, ["--help"])


@pytest.mark.parametrize(
    "script",
    [
        "synthesis-daily-rituals/scripts/repo_state.py",
        "synthesis-project-management/scripts/team_contract.py",
        "synthesis-agent-conformance/scripts/provider_intake.py",
        "synthesis-adversarial-review/scripts/review_contract.py",
    ],
)
def test_new_team_review_intake_entrypoint_is_verified_and_help_only(active, script):
    pointer, root, data = active
    source = Path(__file__).resolve().parents[3]
    for relative in (script, *runtime.ENTRYPOINT_DEPENDENCIES.get(script, ())):
        destination = root / "skills" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((source / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    result = runtime.execute(
        runtime.verified_release(pointer), script, ["--help"], b"", timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert b"usage:" in result.stdout.lower()


@pytest.mark.parametrize(
    "script,dependency",
    [
        (
            "synthesis-daily-rituals/scripts/repo_state.py",
            "synthesis-project-management/scripts/coordination_process.py",
        ),
        (
            "synthesis-agent-conformance/scripts/conformance.py",
            "synthesis-project-management/scripts/team_contract.py",
        ),
    ],
)
def test_new_owned_dependency_is_not_accepted_after_receipt_tamper(
    active, script, dependency, monkeypatch
):
    pointer, root, data = active
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    for relative in names:
        p = root / "skills" / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("pass\n")
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    target = root / "skills" / dependency
    target.write_text("raise RuntimeError('unreviewed')\n")
    with pytest.raises(runtime.RuntimeContractError):
        runtime.execute(verified, script, [], b"", timeout=5)


@pytest.mark.parametrize(
    "script",
    [
        "synthesis-agent-conformance/scripts/hermes_adapter.py",
        "synthesis-agent-conformance/scripts/vendor_bundle.py",
    ],
)
def test_actual_adapter_and_vendor_entrypoints_bind_dependencies_before_execution(
    active, script, monkeypatch
):
    pointer, root, data = active
    source = Path(__file__).resolve().parents[3]
    names = tuple(dict.fromkeys((script, *runtime.ENTRYPOINT_DEPENDENCIES[script])))
    for relative in names:
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    result = runtime.execute(verified, script, ["--help"], b"", timeout=10)
    assert result.returncode == 0, result.stderr
    assert b"usage:" in result.stdout
    hashes = {
        relative: runtime.file_digest(root / "skills" / relative) for relative in names
    }
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda p: {"entrypoints": hashes}
    )
    for dependency in runtime.ENTRYPOINT_DEPENDENCIES[script]:
        helper = root / "skills" / dependency
        before = helper.read_bytes()
        st = helper.stat()
        helper.write_bytes(before + b"\n# drift\n")
        os.utime(helper, ns=(st.st_atime_ns, st.st_mtime_ns))
        with pytest.raises(runtime.RuntimeContractError):
            runtime.command(verified, script, ["--help"])
        helper.write_bytes(before)


@pytest.mark.parametrize(
    "script",
    [
        "synthesis-agent-conformance/scripts/hermes_adapter.py",
        "synthesis-agent-conformance/scripts/vendor_bundle.py",
        "synthesis-agent-conformance/scripts/conformance.py",
        "synthesis-agent-conformance/scripts/session_context.py",
    ],
)
@pytest.mark.parametrize(
    "dependency",
    [
        "synthesis-agent-conformance/scripts/report_contract.py",
        "synthesis-agent-conformance/references/conformance-report-v1.schema.json",
        "synthesis-onboarding/scripts/first_run_store.py",
        "synthesis-project-management/scripts/native_identity.py",
    ],
)
def test_composed_native_consumers_bind_newer_dependency_before_effect(
    active, script, dependency, monkeypatch
):
    pointer, root, data = active
    assert dependency in runtime.ENTRYPOINT_DEPENDENCIES[script]
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    source = Path(__file__).resolve().parents[3]
    for relative in names:
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    runtime.command(verified, script, ["--help"])
    helper = root / "skills" / dependency
    before = helper.read_bytes()
    previous = helper.stat()
    helper.write_bytes(before + b"\n ")
    os.utime(helper, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, ["--help"])


ACQUISITION_ENTRIES = (
    "synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py",
    "synthesis-slack-sync/scripts/acquire.py",
)


@pytest.mark.parametrize("script", ACQUISITION_ENTRIES)
def test_actual_acquisition_entry_and_all_dependencies_are_release_verified(
    active, script, monkeypatch
):
    pointer, root, data = active
    source = Path(__file__).resolve().parents[3]
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    for relative in names:
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    result = runtime.execute(verified, script, ["--help"], b"", timeout=10)
    assert result.returncode == 0, result.stderr
    assert b"usage:" in result.stdout.lower()
    if "meeting-transcripts" in script:
        result = runtime.execute(
            verified, script, ["--mode", "health", "--help"], b"", timeout=10
        )
        assert result.returncode == 0 and b"--capture-dir" in result.stdout
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    for relative in runtime.ENTRYPOINT_DEPENDENCIES[script]:
        helper = root / "skills" / relative
        before = helper.read_bytes()
        st = helper.stat()
        helper.write_bytes(before + b"\n# source drift\n")
        os.utime(helper, ns=(st.st_atime_ns, st.st_mtime_ns))
        with pytest.raises(runtime.RuntimeContractError):
            runtime.command(verified, script, ["--help"])
        helper.write_bytes(before)
        parked = helper.with_name(helper.name + ".retained-test")
        helper.rename(parked)
        with pytest.raises(runtime.RuntimeContractError):
            runtime.command(verified, script, ["--help"])
        parked.rename(helper)


# Stop imports its registered owners lazily, including desktop identity and the
# combined checkpoint route. Receipt-mode trust must cover code, not only stats.
STOP_ENTRIES = (
    "synthesis-autopilot/scripts/autopilot_gate.py",
    "synthesis-project-management/scripts/project_state.py",
)


def _stop_import_closure(entry):
    import ast

    skills = Path(__file__).resolve().parents[2]
    paths = {
        p
        for p in skills.rglob("*.py")
        if not p.name.startswith("test_") and "__pycache__" not in p.parts
    }
    names = {}
    for path in paths:
        names.setdefault(path.stem, set()).add(path)
    pending, seen = [skills / entry], set()
    # These are executable file-path edges, not dotted Python imports. The
    # checkpoint subprocess is coordination.py, already reached by imports.
    explicit = {
        "synthesis-autopilot/scripts/native_stop.py": (
            "synthesis-onboarding/scripts/release_runtime.py",
            "synthesis-project-management/scripts/project_state.py",
        ),
    }
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        pending.extend(
            skills / p for p in explicit.get(path.relative_to(skills).as_posix(), ())
        )
        for node in ast.walk(ast.parse(path.read_text())):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module]
            for name in imports:
                name = name.split(".")[0]
                local = path.with_name(name + ".py")
                matches = {local} if local in paths else names.get(name, set())
                assert len(matches) <= 1, (path, name, matches)
                pending.extend(matches)
    return {p.relative_to(skills).as_posix() for p in seen}


@pytest.mark.parametrize("entry", STOP_ENTRIES)
def test_stop_receipt_covers_direct_and_lazy_source_closure(entry):
    required = _stop_import_closure(entry)
    assert required <= {entry, *runtime.ENTRYPOINT_DEPENDENCIES[entry]}
    assert required <= set(runtime.RECEIPT_ENTRYPOINTS)



@pytest.mark.parametrize("entry", [
    "synthesis-autopilot/scripts/autopilot_gate.py",
    "synthesis-project-management/scripts/team_records.py",
    "synthesis-agent-conformance/scripts/vendor_bundle.py",
    "synthesis-local-messaging/scripts/local_messaging_cli.py",
])
def test_native_doctor_same_stat_drift_refuses_before_dispatch(active, entry):
    doctor = "synthesis-autopilot/scripts/native_doctor.py"
    # Team and messaging dispatch the controller by an explicit file-path edge.
    assert doctor in _stop_import_closure("synthesis-autopilot/scripts/autopilot.py")
    pointer, root, verified = _stop_release_with_receipt(active)
    assert runtime.command(verified, entry, ["--help"])
    target = root / "skills" / doctor
    before, original = target.stat(), target.read_bytes()
    offset = original.index(b"Read-only")
    target.write_bytes(original[:offset] + b"read-only" + original[offset + 9:])
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    try:
        assert target.stat().st_ino == before.st_ino
        assert runtime.stat_walk(root) == json.loads(
            runtime.activation_receipt_path(pointer).read_text()
        )["tree_stat"]
        current = runtime.verified_release(pointer)
        with pytest.raises(runtime.RuntimeContractError,
                           match="entrypoint bytes drifted since activation"):
            runtime.execute(current, entry, ["--help"], b"", timeout=5)
    finally:
        target.write_bytes(original)
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert runtime.command(verified, entry, ["--help"])


def _stop_release_with_receipt(active):
    import shutil

    pointer, root, data = active
    skills = Path(__file__).resolve().parents[2]
    shutil.copytree(
        skills,
        root / "skills",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    data = replace(
        pointer, data, content_digest=system_contract.canonical_tree_digest(root)
    )
    write_receipt(pointer, root, data)
    verified = runtime.verified_release(pointer)
    assert verified["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    return pointer, root, verified


@pytest.mark.parametrize("entry", STOP_ENTRIES)
def test_stop_every_imported_helper_same_stat_drift_refuses_before_dispatch(
    active, entry
):
    import time

    pointer, root, verified = _stop_release_with_receipt(active)
    required = sorted(_stop_import_closure(entry) - {entry})
    timings = []
    # One retained generation is sufficient: restore exact bytes and metadata
    # between independent substitutions rather than duplicating the whole tree.
    for relative in required:
        target = root / "skills" / relative
        before, original = target.stat(), target.read_bytes()
        offset = next(
            i
            for i, value in enumerate(original)
            if 65 <= value <= 90 or 97 <= value <= 122
        )
        replacement = b"Q" if original[offset] != ord("Q") else b"R"
        target.write_bytes(original[:offset] + replacement + original[offset + 1 :])
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        try:
            assert target.stat().st_ino == before.st_ino
            assert (
                runtime.stat_walk(root)
                == json.loads(runtime.activation_receipt_path(pointer).read_text())[
                    "tree_stat"
                ]
            )
            current = runtime.verified_release(pointer)
            assert current["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
            with pytest.raises(
                runtime.RuntimeContractError,
                match="entrypoint bytes drifted since activation",
            ):
                runtime.execute(current, entry, ["--help"], b"", timeout=5)
        finally:
            target.write_bytes(original)
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        started = time.monotonic()
        assert runtime.command(verified, entry, ["--help"])
        timings.append(time.monotonic() - started)
    (pointer.parent / (Path(entry).stem + "-dependency-cost.json")).write_text(
        json.dumps(
            {
                "helpers": len(required),
                "command_seconds": timings,
                "scope": "actual receipt hash validation; excludes interpreter startup and native execution",
            },
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("mode", ["--gate", "--combined-stop"])
@pytest.mark.parametrize(
    "fault", ["none", "coordination", "native_stop", "missing-hash"]
)
def test_stop_actual_receipt_cold_consumer_before_effect(
    active, tmp_path, monkeypatch, mode, fault
):
    scripts = Path(__file__).resolve().parents[2] / "synthesis-autopilot/scripts"
    monkeypatch.syspath_prepend(str(scripts))
    from test_stop_identity import native_fixture

    pointer, root, _ = _stop_release_with_receipt(active)
    payload, env, _ = native_fixture(
        tmp_path / "synthetic-native", "claude-code-desktop"
    )
    for key in tuple(os.environ):
        if key.startswith(("SYNTHESIS_", "CLAUDE_", "CODEX_", "MUSE_", "PYTHONPATH")):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_review_runtime")
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(pointer))
    entry = STOP_ENTRIES[0]
    relative = (
        "synthesis-autopilot/scripts/native_stop.py"
        if fault == "native_stop"
        else "synthesis-project-management/scripts/coordination.py"
    )
    if fault == "missing-hash":
        receipt = json.loads(runtime.activation_receipt_path(pointer).read_text())
        receipt["entrypoints"].pop(relative, None)
        runtime.activation_receipt_path(pointer).write_text(json.dumps(receipt))
    elif fault != "none":
        target = root / "skills" / relative
        before, original = target.stat(), target.read_bytes()
        offset = next(
            i
            for i, value in enumerate(original)
            if 65 <= value <= 90 or 97 <= value <= 122
        )
        changed = (
            original[:offset]
            + (b"Q" if original[offset] != ord("Q") else b"R")
            + original[offset + 1 :]
        )
        target.write_bytes(changed)
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert (
            runtime.stat_walk(root)
            == json.loads(runtime.activation_receipt_path(pointer).read_text())[
                "tree_stat"
            ]
        )
    current = runtime.verified_release(pointer)
    assert current["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    if fault != "none":
        with pytest.raises(
            runtime.RuntimeContractError,
            match="(entrypoint bytes drifted|no activation hash)",
        ):
            runtime.execute(
                current, entry, [mode], json.dumps(payload).encode(), timeout=20
            )
    else:
        result = runtime.execute(
            current, entry, [mode], json.dumps(payload).encode(), timeout=20
        )
        assert result.returncode == 0, result.stderr
        decoded = json.loads(result.stdout)
        if mode == "--gate":
            assert decoded == {}
        else:
            # The synthetic native transcript has no PM project. Real combined
            # execution must retain that checkpoint diagnostic, not invent one.
            assert isinstance(decoded, dict)
            assert "runtime helper is unavailable" not in json.dumps(decoded)
            assert "dependency" not in json.dumps(decoded)


@pytest.mark.parametrize("tamper", [False, True])
def test_stop_reservation_lazy_loader_verifies_receipt_before_import(
    active, tmp_path, monkeypatch, tamper
):
    scripts = Path(__file__).resolve().parents[2] / "synthesis-autopilot/scripts"
    monkeypatch.syspath_prepend(str(scripts))
    from test_stop_identity import native_fixture

    pointer, root, _ = _stop_release_with_receipt(active)
    payload, env, _ = native_fixture(tmp_path / "native", "claude-code-desktop")
    for key in tuple(os.environ):
        if key.startswith(("SYNTHESIS_", "CLAUDE_", "CODEX_", "MUSE_", "PYTHONPATH")):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(pointer))
    target = root / "skills/synthesis-autopilot/scripts/workflow.py"
    sentinel = tmp_path / "untrusted-import-effect"
    if tamper:
        before, original = target.stat(), target.read_bytes()
        body = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n".encode()
        assert len(body) < len(original)
        target.write_bytes(body + b"#" + b" " * (len(original) - len(body) - 1))
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert (
            runtime.stat_walk(root)
            == json.loads(runtime.activation_receipt_path(pointer).read_text())[
                "tree_stat"
            ]
        )
    assert (
        runtime.verified_release(pointer)["_verification_mode"]
        == runtime.VERIFICATION_MODE_RECEIPT
    )
    if tamper:
        error = None
        try:
            runtime._policy_reservation(payload, {}, consume=False)
        except Exception as exc:
            error = exc
        (tmp_path / "reservation-import-observation.json").write_text(
            json.dumps(
                {
                    "effect": sentinel.exists(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            )
            + "\n"
        )
        assert not sentinel.exists(), "unverified reservation owner executed"
        assert isinstance(error, runtime.RuntimeContractError)
        assert "entrypoint bytes drifted" in str(error)
    else:
        # The real unchanged owner reaches its ordinary missing-proof refusal;
        # no journal, native authority, mocked validation or consumption is used.
        with pytest.raises(KeyError, match="project"):
            runtime._policy_reservation(payload, {}, consume=False)
        assert not sentinel.exists()


def test_stop_legacy_verification_cannot_authorize_later_changed_helper(active):
    pointer, root, _ = _stop_release_with_receipt(active)
    receipt = runtime.activation_receipt_path(pointer)
    receipt.rename(receipt.with_suffix(".retained"))
    current = runtime.verified_release(pointer)
    assert current["_verification_mode"] == runtime.VERIFICATION_MODE_FULL
    target = root / "skills/synthesis-project-management/scripts/coordination.py"
    before = target.stat()
    raw = target.read_bytes()
    target.write_bytes(raw.replace(b"canonical", b"canonICAL", 1))
    assert target.read_bytes() != raw
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError, match="content digest drifted"):
        runtime.execute(current, STOP_ENTRIES[0], ["--gate"], b"{}", timeout=5)


PEER_DELIVERY_ENTRIES = (
    "synthesis-project-management/scripts/peer_send_gate.py",
    "synthesis-project-management/scripts/board_inbox.py",
)


@pytest.mark.parametrize("entry", PEER_DELIVERY_ENTRIES)
def test_delivery_repair_receipt_covers_actual_peer_closure(entry):
    required = _stop_import_closure(entry)
    assert required <= {entry, *runtime.ENTRYPOINT_DEPENDENCIES[entry]}
    assert required <= set(runtime.RECEIPT_ENTRYPOINTS)


@pytest.mark.parametrize("entry", PEER_DELIVERY_ENTRIES)
@pytest.mark.parametrize("fault", ["bytes", "missing-hash", "symlink"])
def test_delivery_repair_actual_peer_receipt_refuses_every_helper(active, entry, fault):
    import shutil

    pointer, root, data = active
    skills = Path(__file__).resolve().parents[2]
    # The real command owner needs exactly its declared executable closure,
    # not unrelated test modules or another copy of the whole release tree.
    for relative in {entry, *runtime.ENTRYPOINT_DEPENDENCIES[entry]}:
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skills / relative, target)
    data = replace(
        pointer, data, content_digest=system_contract.canonical_tree_digest(root)
    )
    write_receipt(pointer, root, data)
    receipt_path = runtime.activation_receipt_path(pointer)
    original_receipt = receipt_path.read_bytes()
    verified = runtime.verified_release(pointer)
    assert verified["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    assert runtime.command(verified, entry, ["--help"])
    for relative in sorted(_stop_import_closure(entry) - {entry}):
        target = root / "skills" / relative
        before, original = target.stat(), target.read_bytes()
        retained = target.with_suffix(".retained-original")
        if fault == "bytes":
            offset = next(
                i
                for i, value in enumerate(original)
                if 65 <= value <= 90 or 97 <= value <= 122
            )
            target.write_bytes(
                original[:offset]
                + (b"Q" if original[offset] != ord("Q") else b"R")
                + original[offset + 1 :]
            )
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            assert runtime.stat_walk(root) == json.loads(original_receipt)["tree_stat"]
        elif fault == "missing-hash":
            receipt = json.loads(original_receipt)
            del receipt["entrypoints"][relative]
            receipt_path.write_text(json.dumps(receipt))
        else:
            target.rename(retained)
            target.symlink_to(retained.name)
        try:
            with pytest.raises(runtime.RuntimeContractError):
                current = runtime.verified_release(pointer)
                runtime.command(current, entry, ["--help"])
        finally:
            if fault == "symlink":
                target.unlink()
                retained.rename(target)
            elif fault == "bytes":
                target.write_bytes(original)
                os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            else:
                receipt_path.write_bytes(original_receipt)
        assert runtime.command(runtime.verified_release(pointer), entry, ["--help"])


@pytest.mark.parametrize("cache_mode", ["TIMESTAMP", "CHECKED_HASH", "UNCHECKED_HASH"])
@pytest.mark.parametrize("verification", ["receipt", "full"])
@pytest.mark.parametrize("route", ["execute", "launcher", "outer-cli"])
def test_source_contract_ignores_cached_helper_code(
    active, tmp_path, monkeypatch, cache_mode, verification, route
):
    """Synthetic stale-value cache; actual source execution must return source."""
    import importlib.util
    import py_compile

    pointer, root, data = active
    directory = root / "skills/synthesis-repo-guard"
    helper = directory / "synthetic_helper.py"
    source = b"VALUE = 'source'\n"
    helper.write_bytes(b"VALUE = 'cached'\n")
    stamp = 1700000000000000000
    os.utime(helper, ns=(stamp, stamp))
    prefix = tmp_path / "external-cache"
    old_prefix = sys.pycache_prefix
    sys.pycache_prefix = str(prefix)
    try:
        cache = Path(importlib.util.cache_from_source(str(helper)))
    finally:
        sys.pycache_prefix = old_prefix
    cache.parent.mkdir(parents=True)
    py_compile.compile(
        str(helper),
        cfile=str(cache),
        doraise=True,
        invalidation_mode=getattr(py_compile.PycInvalidationMode, cache_mode),
    )
    helper.write_bytes(source)
    os.utime(helper, ns=(stamp, stamp))
    if cache_mode == "CHECKED_HASH":
        content = cache.read_bytes()
        cache.write_bytes(
            content[:8] + importlib.util.source_hash(source) + content[16:]
        )
    target = directory / "repo_sync_check.py"
    target.write_text("import synthetic_helper\nprint(synthetic_helper.VALUE)\n")
    if route == "outer-cli":
        import shutil

        source_root = Path(__file__).resolve().parents[3]
        for dependency in runtime.ENTRYPOINT_DEPENDENCIES[
            "synthesis-onboarding/scripts/synthesis_cli.py"
        ]:
            origin = source_root / "skills" / dependency
            destination = root / "skills" / dependency
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, destination)
        target = root / "skills/synthesis-onboarding/scripts/synthesis_cli.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "import sys\nsys.path.insert(0, "
            + repr(str(directory))
            + ")\nimport synthetic_helper\nprint(synthetic_helper.VALUE)\n"
        )
    data = replace(pointer, data, content_digest=runtime.tree_digest(root))
    launcher, data = managed_fixture((pointer, root, data))
    if verification == "receipt":
        write_receipt(pointer, root, data)
    checked = runtime.verified_release(pointer)
    assert checked["_verification_mode"] == (
        runtime.VERIFICATION_MODE_RECEIPT
        if verification == "receipt"
        else runtime.VERIFICATION_MODE_FULL
    )
    monkeypatch.setenv("PYTHONPYCACHEPREFIX", str(prefix))
    if route == "execute":
        result = runtime.execute(checked, SCRIPT, [], b"", timeout=10)
    else:
        args = [str(launcher)] + (
            ["exec-public", SCRIPT] if route == "launcher" else []
        )
        result = subprocess.run(args, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"source\n"
    assert helper.read_bytes() == source


def test_source_contract_preserves_relative_and_installed_library_imports(active):
    pointer, root, data = active
    directory = root / "skills/synthesis-repo-guard"
    package = directory / "synthetic_package"
    package.mkdir()
    (package / "__init__.py").write_text("from .values import VALUE\n")
    (package / "values.py").write_text("VALUE = 'relative'\n")
    (directory / "repo_sync_check.py").write_text(
        "import yaml, synthetic_package, sys\n"
        "print(yaml.safe_load('message: installed')['message'], synthetic_package.VALUE)\n"
        "sys.stdout.buffer.flush()\n"
    )
    data = replace(pointer, data, content_digest=runtime.tree_digest(root))
    result = runtime.execute(
        runtime.verified_release(pointer), SCRIPT, [], b"", timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"installed relative\n"


def test_source_contract_refuses_sourceless_release_import(active):
    import py_compile

    pointer, root, data = active
    directory = root / "skills/synthesis-repo-guard"
    helper = directory / "source_absence.py"
    helper.write_text("VALUE = 'cached'\n")
    py_compile.compile(
        str(helper), cfile=str(directory / "source_absence.pyc"), doraise=True
    )
    helper.rename(directory / "source_absence.retained")
    (directory / "repo_sync_check.py").write_text(
        "import source_absence\nprint(source_absence.VALUE)\n"
    )
    data = replace(pointer, data, content_digest=runtime.tree_digest(root))
    result = runtime.execute(
        runtime.verified_release(pointer), SCRIPT, [], b"", timeout=10
    )
    assert result.returncode != 0
    assert b"requires Python source" in result.stderr
    assert b"cached" not in result.stdout


def test_policy_loader_ignores_cached_code_with_unchanged_source(
    active, tmp_path, monkeypatch
):
    import py_compile

    pointer, root, data = _stop_release_with_receipt(active)
    helper = root / "skills/synthesis-autopilot/scripts/workflow.py"
    original = helper.read_bytes()
    stamp = helper.stat()
    helper.write_bytes(b"raise RuntimeError('cached fixture selected')\n")
    cache = Path(
        py_compile.compile(
            str(helper),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )
    )
    helper.write_bytes(original)
    os.utime(helper, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    data = replace(pointer, data, content_digest=runtime.tree_digest(root))
    write_receipt(pointer, root, data)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(pointer))
    with pytest.raises(KeyError, match="project"):
        runtime._policy_reservation({}, {}, consume=False)
    assert helper.read_bytes() == original
    assert cache.is_file()

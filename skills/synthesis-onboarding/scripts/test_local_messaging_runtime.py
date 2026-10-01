"""Real managed launcher with synthetic SQLite and receipt-bound source only."""

from pathlib import Path
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

import pytest

import release_runtime as runtime
import system_contract
import test_release_runtime as fixtures

active = fixtures.active
ENTRY = "synthesis-local-messaging/scripts/local_messaging_cli.py"
SOURCE = Path(__file__).resolve().parents[3]


def installed(active):
    pointer, root, data = active
    for name in (ENTRY, *runtime.ENTRYPOINT_DEPENDENCIES.get(ENTRY, ())):
        origin = SOURCE / "skills" / name
        if not origin.exists():  # Baseline must reach the real undeclared route.
            continue
        target = root / "skills" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    data = fixtures.replace(
        pointer, data, content_digest=system_contract.canonical_tree_digest(root)
    )
    launcher, data = fixtures.managed_fixture((pointer, root, data))
    receipt = fixtures.write_receipt(pointer, root, data)
    return pointer, root, data, launcher, receipt


def invoke(launcher, *arguments):
    return subprocess.run(
        [
            str(launcher),
            "exec-public",
            "--timeout-seconds",
            "20",
            ENTRY,
            "--",
            *arguments,
        ],
        input=b"",
        capture_output=True,
        timeout=25,
    )


@pytest.mark.parametrize("document", ["SKILL.md", "references/messages-boundary.md"])
def test_installed_local_messaging_route_help(active, document):
    _pointer, _root, _data, launcher, _receipt = installed(active)
    body = (SOURCE / "skills/synthesis-local-messaging" / document).read_text()
    commands = re.findall(r"`(synthesis exec-public [^`]+)`", body)
    assert len(commands) == 1
    command = shlex.split(commands[0])
    assert command == [
        "synthesis",
        "exec-public",
        ENTRY,
        "--",
        "--request",
        "REQUEST.json",
        "--state",
        "STATE_DIR",
    ]
    result = subprocess.run(
        [str(launcher), *command[1:4], "--help"],
        input=b"",
        capture_output=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert b"--request" in result.stdout and b"--state" in result.stdout
    assert b"--worker" not in result.stdout and b"--send" not in result.stdout


def test_messaging_receipt_covers_transitive_imports_and_native_asset():
    assert ENTRY in runtime.PUBLIC_ENTRYPOINTS
    required = set()
    for name in (
        ENTRY,
        "synthesis-local-messaging/scripts/messages_native.py",
        "synthesis-autopilot/scripts/evaluation_artifacts.py",
        "synthesis-project-management/scripts/coordination_process.py",
        "synthesis-message-guard/scripts/message_guard.py",
    ):
        required.update(fixtures._stop_import_closure(name))
    # The guard's existing dynamic board owner is already explicitly declared.
    required.update(
        runtime.ENTRYPOINT_DEPENDENCIES[
            "synthesis-message-guard/scripts/message_guard.py"
        ]
    )
    required.add("synthesis-local-messaging/scripts/messages_transport.js")
    assert required <= {ENTRY, *runtime.ENTRYPOINT_DEPENDENCIES[ENTRY]}
    assert required <= set(runtime.RECEIPT_ENTRYPOINTS)


def test_installed_route_reads_selected_synthetic_database_and_replays(
    active, tmp_path
):
    _pointer, _root, _data, launcher, _receipt = installed(active)
    scripts = SOURCE / "skills/synthesis-local-messaging/scripts"
    sys.path.insert(0, str(scripts))
    try:
        from test_local_messaging import imessage, add, request

        database, writer = imessage(tmp_path / "source")
        add(writer)
        writer.close()
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        request_file = tmp_path / "request.json"
        request_file.write_text(json.dumps(request(database)))
        state = tmp_path / "scan-state"
        first = invoke(launcher, "--request", str(request_file), "--state", str(state))
        assert first.returncode == 0, (first.stdout, first.stderr)
        result = json.loads(first.stdout)
        assert result["coverage"]["complete"] and result["coverage"]["examined"] == 1
        assert result["notes"][0]["pointer"]["id"] == "fixture-0"
        assert "Can you review" not in first.stdout.decode()
        assert list(state.glob("page-*.json"))
        assert result["confinement"] in ("macos-sandbox-exec", "linux-bubblewrap")
        attempts = list(state.glob("attempt-*"))
        second = invoke(launcher, "--request", str(request_file), "--state", str(state))
        assert second.returncode == 0 and json.loads(second.stdout) == result
        assert list(state.glob("attempt-*")) == attempts
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    finally:
        sys.path.remove(str(scripts))


@pytest.mark.parametrize(
    "flag", ["--worker", "--request-digest", "--send", "--approval"]
)
def test_public_reader_cli_refuses_internal_or_send_options(active, tmp_path, flag):
    _pointer, _root, _data, launcher, _receipt = installed(active)
    state = tmp_path / "uncreated-state"
    result = invoke(
        launcher,
        "--request",
        str(tmp_path / "unread-request"),
        "--state",
        str(state),
        flag,
        "untrusted",
    )
    assert result.returncode == 2
    assert not state.exists()
    assert b"unrecognized arguments" in result.stderr


@pytest.mark.parametrize("fault", ["missing", "symlink", "same-stat-bytes"])
def test_every_messaging_entry_dependency_and_asset_refuses_before_dispatch(
    active, monkeypatch, fault
):
    pointer, root, _data, _launcher, receipt = installed(active)
    active_descriptor = runtime.verified_release(pointer)
    assert active_descriptor["_verification_mode"] == runtime.VERIFICATION_MODE_RECEIPT
    names = (ENTRY, *runtime.ENTRYPOINT_DEPENDENCIES[ENTRY])
    assert all(name in receipt["entrypoints"] for name in names)
    launched = []
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: launched.append((args, kwargs)),
    )
    for name in names:
        path = root / "skills" / name
        original = path.read_bytes()
        metadata = path.stat()
        retained = path.with_name(path.name + ".retained-control")
        if fault == "missing":
            path.rename(retained)
        elif fault == "symlink":
            path.rename(retained)
            path.symlink_to(retained)
        else:
            changed = bytearray(original)
            changed[-1] ^= 1
            path.write_bytes(changed)
            os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        try:
            with pytest.raises(runtime.RuntimeContractError):
                runtime.command(active_descriptor, ENTRY, ["--help"])
        finally:
            if fault == "symlink":
                path.unlink()
                retained.rename(path)
            elif fault == "missing":
                retained.rename(path)
            else:
                path.write_bytes(original)
                path.chmod(metadata.st_mode & 0o777)
                os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        assert not launched


def test_native_modules_and_raw_workers_are_not_public_cli_routes(active):
    pointer, _root, _data, _launcher, _receipt = installed(active)
    verified = runtime.verified_release(pointer)
    for name in (
        "local_messaging.py",
        "messages_outbound.py",
        "messages_native.py",
        "messages_boundary.py",
        "messages_transport.js",
    ):
        relative = "synthesis-local-messaging/scripts/" + name
        assert relative not in runtime.PUBLIC_ENTRYPOINTS
        with pytest.raises(runtime.RuntimeContractError, match="not declared"):
            runtime.command(verified, relative, ["--worker", "/untrusted"])


def test_reader_cli_rejects_duplicate_request_keys_before_state(active, tmp_path):
    _pointer, _root, _data, launcher, _receipt = installed(active)
    request_file = tmp_path / "request.json"
    request_file.write_text('{"schema":1,"schema":1}')
    state = tmp_path / "scan-state"
    result = invoke(launcher, "--request", str(request_file), "--state", str(state))
    assert result.returncode == 2 and b"duplicate JSON key" in result.stdout
    assert not state.exists()


def test_modular_selection_materializes_receipt_owned_messaging_route(
    active, tmp_path, monkeypatch
):
    import modular

    pointer, root, data = active
    # A materialized release has no checkout pointer or interpreter cache.
    # Copying the caller's .git selects the committed-checkout contract instead.
    shutil.copytree(
        SOURCE,
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".pytest_cache", ".ruff_cache"
        ),
    )
    assert not (root / ".git").exists()
    version = json.loads((root / ".claude-plugin/plugin.json").read_bytes())["version"]
    data = fixtures.replace(
        pointer,
        data,
        version=version,
        content_digest=system_contract.canonical_tree_digest(root),
    )
    launcher, data = fixtures.managed_fixture((pointer, root, data))
    fixtures.write_receipt(pointer, root, data)
    monkeypatch.setattr(
        modular, "active_release_descriptor", lambda: runtime.verified_release(pointer)
    )
    selection = modular.resolve_selection(root, ["synthesis-local-messaging"], False)
    assert selection["source"]["kind"] == "release"
    names = {
        "skills/" + name for name in (ENTRY, *runtime.ENTRYPOINT_DEPENDENCIES[ENTRY])
    }
    assert names <= set(selection["required_files"])
    assert not selection["optional_core_files"]
    target = tmp_path / "selected-payload"
    modular.materialize_payload(root, target, selection["files"])
    modular.verify_payload(target, selection["files"])
    assert all(
        (target / name).read_bytes() == (root / name).read_bytes() for name in names
    )
    projection = {
        "schema_version": 1,
        "kind": "modular",
        "content_digest": system_contract.canonical_tree_digest(target),
        "source_content_digest": data["content_digest"],
        "selection": {
            key: selection[key]
            for key in ("roots", "skills", "support_skills", "stage_core")
        },
        "files": selection["files"],
    }
    data = fixtures.replace(
        pointer, data, release_root=str(target), projection=projection
    )
    fixtures.write_receipt(pointer, target, data)
    result = invoke(launcher, "--help")
    assert result.returncode == 0, result.stderr
    assert b"--request" in result.stdout
    verified = runtime.verified_release(pointer)
    runtime.verify_dependencies(verified, ENTRY)
    asset = target / "skills/synthesis-local-messaging/scripts/messages_transport.js"
    asset.write_bytes(asset.read_bytes() + b"\n// synthetic replacement\n")
    refused = invoke(launcher, "--help")
    assert refused.returncode != 0
    assert b"--request" not in refused.stdout

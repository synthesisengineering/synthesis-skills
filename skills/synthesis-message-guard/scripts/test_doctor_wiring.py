import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path
import pytest

ENGINE = Path(__file__).with_name("message_guard.py")
spec = importlib.util.spec_from_file_location("root_guard", ENGINE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.mark.parametrize(
    "command",
    [
        "echo message_guard.py",
        "true # message_guard.py",
        "python3 /nonexistent/message_guard.py --gate",
        "python3 message_guard.py --gate",
        "python3 -c \"print('message_guard.py')\"",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(ENGINE))} --doctor",
        f"true || {shlex.quote(sys.executable)} {shlex.quote(str(ENGINE))} --gate",
    ],
)
def test_doctor_cannot_attest_non_guard_command(tmp_path, command):
    p = tmp_path / "hooks.json"
    p.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [{"type": "command", "command": command}],
                        }
                    ]
                }
            }
        )
    )
    assert not guard.hook_config_covers(p, ["fixture.send"])


@pytest.mark.parametrize("mode", ["--gate", "--dispatch"])
def test_current_real_engine_command_is_recognized(tmp_path, mode):
    p = tmp_path / "hooks.json"
    command = f"{shlex.quote(sys.executable)} -B {shlex.quote(str(ENGINE))} {mode}"
    p.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [{"type": "command", "command": command}],
                        }
                    ]
                }
            }
        )
    )
    assert guard.hook_config_covers(p, ["fixture.send"])


@pytest.mark.parametrize("kind", ["fifo", "symlink", "oversized", "different-engine"])
def test_doctor_refuses_unverified_engine_input(tmp_path, kind):
    engine = tmp_path / "message_guard.py"
    if kind == "fifo":
        os.mkfifo(engine)
    elif kind == "symlink":
        engine.symlink_to(ENGINE)
    elif kind == "oversized":
        engine.write_bytes(b"x" * (1024 * 1024 + 1))
    else:
        engine.write_text('print("not a guard")\n')
    p = tmp_path / "hooks.json"
    p.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": shlex.join(
                                        [sys.executable, str(engine), "--gate"]
                                    ),
                                }
                            ],
                        }
                    ]
                }
            }
        )
    )
    assert not guard.hook_config_covers(p, ["fixture.send"])


def test_doctor_refuses_fifo_hook_config(tmp_path):
    p = tmp_path / "hooks.json"
    os.mkfifo(p)
    assert not guard.hook_config_covers(p, ["fixture.send"])


def test_exact_installed_copy_qualifies(tmp_path):
    engine = tmp_path / "message_guard.py"
    engine.write_bytes(ENGINE.read_bytes())
    assert (
        guard._doctor_guard_mode(
            {"command": shlex.join([sys.executable, "-B", str(engine), "--gate"])}
        )
        == "--gate"
    )


@pytest.fixture
def managed_route(tmp_path, monkeypatch):
    import hashlib

    source = ENGINE.resolve().parents[3]
    scripts = source / "skills/synthesis-onboarding/scripts"
    sys.path.insert(0, str(scripts))
    import system_contract

    root = tmp_path / "release"
    target = root / "skills/synthesis-message-guard/scripts/message_guard.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(ENGINE.read_bytes())
    runtime = root / "skills/synthesis-onboarding/scripts/release_runtime.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes((scripts / "release_runtime.py").read_bytes())
    pointer = tmp_path / "active-release.json"
    launcher = tmp_path / "bin/synthesis"
    launcher.parent.mkdir()
    pin = {"executable": str(Path(sys.executable).resolve())}
    launcher.write_bytes(system_contract.launcher_bytes(pointer, pin))
    launcher.chmod(0o755)
    descriptor = {
        "schema_version": 1,
        "release_root": str(root),
        "interpreter": pin,
        "launcher": {
            "runtime_schema": 1,
            "path": str(launcher),
            "sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
        },
    }
    pointer.write_text(json.dumps(descriptor))
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(pointer))
    monkeypatch.setenv("SYNTHESIS_INSTALL_BIN_DIR", str(launcher.parent))
    return pointer, launcher, target


@pytest.mark.parametrize("mode", ["--gate", "--dispatch"])
def test_managed_installer_route_stored_binding(managed_route, mode):
    command = (
        '"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis" exec-public synthesis-message-guard/scripts/message_guard.py -- '
        + mode
    )
    assert guard._doctor_guard_mode({"command": command}) == mode


@pytest.mark.parametrize(
    "change",
    ["launcher", "source", "schema", "pointer-fifo", "wrong-script", "other-expansion"],
)
def test_managed_route_refuses_changed_binding(managed_route, change):
    pointer, launcher, target = managed_route
    command = '"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis" exec-public synthesis-message-guard/scripts/message_guard.py -- --gate'
    if change == "launcher":
        launcher.write_text("#!/bin/sh\necho message_guard.py\n")
    elif change == "source":
        target.write_text("print('not a guard')\n")
    elif change == "schema":
        value = json.loads(pointer.read_text())
        value["schema_version"] = True
        pointer.write_text(json.dumps(value))
    elif change == "pointer-fifo":
        pointer.rename(pointer.with_suffix(".retained"))
        os.mkfifo(pointer)
    elif change == "wrong-script":
        command = command.replace(
            "synthesis-message-guard/scripts/message_guard.py", "other/message_guard.py"
        )
    else:
        command = command.replace("SYNTHESIS_INSTALL_BIN_DIR", "UNDECLARED_BIN_DIR")
    assert guard._doctor_guard_mode({"command": command}) is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"hooks": []},
        {"hooks": {"PreToolUse": {}}},
        {"hooks": {"PreToolUse": [None]}},
        {"hooks": {"PreToolUse": [{"matcher": [], "hooks": []}]}},
    ],
)
def test_malformed_hook_structure_cannot_attest_wiring(tmp_path, value):
    p = tmp_path / "hooks.json"
    p.write_text(json.dumps(value))
    assert guard.hook_config_covers(p, ["fixture.send"]) is False


def test_managed_receipt_cannot_turn_arbitrary_launcher_into_owner(managed_route):
    import hashlib

    pointer, launcher, _ = managed_route
    launcher.write_text(
        "#!/bin/sh\n# generated by synthesis-onboarding; managed file\necho message_guard.py\n"
    )
    record = json.loads(pointer.read_text())
    record["launcher"]["sha256"] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    pointer.write_text(json.dumps(record))
    command = shlex.join(
        [
            str(launcher),
            "exec-public",
            "synthesis-message-guard/scripts/message_guard.py",
            "--",
            "--gate",
        ]
    )
    assert guard._doctor_guard_mode({"command": command}) is None

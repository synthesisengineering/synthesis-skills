"""Read-only declared service ownership and actual CLI/runtime consumers."""

import hashlib
import json
from pathlib import Path
import pytest
import runtime_payload as runtime
import machine_review
import synthesis_cli
import release_runtime
from system_contract import ContractError, SystemState

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "platform,env,kernel,family,manager",
    [
        ("darwin", {}, "", "macos", "launchd-user"),
        ("linux", {}, "Linux", "linux", "systemd-user"),
        ("linux", {"WSL_DISTRO_NAME": "Synthetic"}, "Linux", "wsl", "systemd-user"),
        ("linux", {}, "Linux microsoft-standard-WSL2", "wsl", "systemd-user"),
        ("win32", {}, "", "native-windows", None),
    ],
)
def test_platform_mapping_is_exact_and_mutation_negative(
    tmp_path, platform, env, kernel, family, manager
):
    home = tmp_path / "home"
    home.mkdir()
    state = home / "state"
    before = list(home.rglob("*"))
    v = runtime.platform_ownership(
        home, state, platform=platform, environ=env, proc_version=kernel
    )
    assert v["platform"] == family and v["console_manager"] == manager
    assert not v["mutation_authorized"] and v["native_service_status"] == "UNKNOWN"
    assert list(home.rglob("*")) == before
    if family == "native-windows":
        assert (
            not v["runtime_supported"]
            and v["runtime_paths"] == {}
            and v["console_unit"] is None
        )
    else:
        assert v["console_python"] == str(
            home / ".local/share/synthesis-console/python-runtime"
        )
        assert v["console_receipt"] == str(
            home / ".local/state/synthesis-console/autostart.json"
        )
        assert v["runtime_paths"]["kernel"] == str(state / "bin")
        assert v["console_unit"] == str(
            home
            / (
                "Library/LaunchAgents/org.synthesisengineering.console.plist"
                if family == "macos"
                else ".config/systemd/user/synthesis-console.service"
            )
        )


@pytest.mark.parametrize("value", ["relative", "/tmp/a/../b", "/tmp//b", "/tmp/b/"])
def test_ambiguous_xdg_root_refuses(tmp_path, value):
    with pytest.raises(ContractError):
        runtime.platform_ownership(
            tmp_path,
            tmp_path / "state",
            platform="linux",
            environ={"XDG_CONFIG_HOME": value},
            proc_version="Linux",
        )


def test_xdg_overrides_are_preserved_exactly(tmp_path):
    env = {
        k: str(tmp_path / k)
        for k in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME")
    }
    v = runtime.platform_ownership(
        tmp_path,
        tmp_path / "state",
        platform="linux",
        environ=env,
        proc_version="Linux",
    )
    assert (
        v["console_unit"]
        == env["XDG_CONFIG_HOME"] + "/systemd/user/synthesis-console.service"
    )
    assert (
        v["console_python"]
        == env["XDG_DATA_HOME"] + "/synthesis-console/python-runtime"
    )


@pytest.mark.parametrize(
    "case", ["absent", "exact", "foreign", "partial", "receipt-mode", "symlink"]
)
def test_declared_service_review_preserves_files_and_never_implies_runtime(
    tmp_path, monkeypatch, case
):
    home = tmp_path / "home"
    home.mkdir()
    owner = SystemState(home)
    mapping = runtime.platform_ownership(
        home, owner.state_dir, platform="linux", environ={}, proc_version="Linux"
    )
    monkeypatch.setattr(runtime, "platform_ownership", lambda *_: mapping)
    unit = Path(mapping["console_unit"])
    receipt = Path(mapping["console_receipt"])
    if case != "absent":
        unit.parent.mkdir(parents=True)
        unit.write_bytes(b"synthetic owned unit")
        unit.chmod(0o644)
        receipt.parent.mkdir(parents=True)
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "target": str(unit),
                    "sha256": hashlib.sha256(unit.read_bytes()).hexdigest(),
                    "mode": 0o644,
                }
            )
        )
        receipt.chmod(0o600)
        if case == "foreign":
            unit.write_text("foreign")
        if case == "partial":
            receipt.unlink()
        if case == "receipt-mode":
            receipt.chmod(0o644)
        if case == "symlink":
            unit.rename(unit.with_suffix(".retained"))
            unit.symlink_to(unit.with_suffix(".retained"))

    def snap():
        return {
            str(p): (
                p.lstat().st_mode,
                p.readlink().as_posix() if p.is_symlink() else p.read_bytes(),
            )
            for p in home.rglob("*")
            if p.is_file() or p.is_symlink()
        }

    before = snap()
    report = machine_review.review(
        owner,
        {
            "schema": 1,
            "components": [
                {"id": "console", "kind": "service", "component": "console"}
            ],
            "registries": [],
        },
        source_root=ROOT,
    )
    assert snap() == before and not report["repair_authorized"]
    row = report["results"][0]
    assert row["status"] == (
        "ABSENT" if case == "absent" else "OBSERVED" if case == "exact" else "UNKNOWN"
    )
    if case == "exact":
        assert "UNKNOWN" in row["detail"]


def test_explain_never_constructs_mutable_state(monkeypatch, capsys):
    monkeypatch.setattr(
        synthesis_cli,
        "SystemState",
        lambda *a, **k: pytest.fail("explain constructed state"),
    )
    assert synthesis_cli.main(["explain", "--json"]) == 0
    v = json.loads(capsys.readouterr().out)
    assert v["changes_made"] is False
    assert (
        "Unknown" in v["unknown"]
        and "hook trust" in v["trust"]
        and "keyboard" in v["navigation"]
    )
    assert synthesis_cli.main(["explain"]) == 0
    assert "changes nothing" in capsys.readouterr().out


def test_actual_cli_mapping_is_readonly(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    owner = SystemState(home)
    before = list(home.rglob("*"))
    assert synthesis_cli.main(["machine", "platform", "--json"], state=owner) == 0
    value = json.loads(capsys.readouterr().out)
    assert not value["mutation_authorized"]
    assert list(home.rglob("*")) == before


def test_activation_receipt_authenticates_actual_new_dependency_bytes(tmp_path):
    # Exercise actual activation inventory, not membership in a dependency literal.
    pointer = tmp_path / "active.json"
    pointer.write_bytes(b"{}")
    receipt = release_runtime.build_activation_receipt(
        release_root=ROOT,
        descriptor_bytes=b"{}",
        descriptor_meta=pointer.stat(),
        launcher_sha256="0" * 64,
        interpreter_sha256="1" * 64,
        generation="fixture",
        content_digest="2" * 64,
        projection=None,
    )
    for relative in (
        "synthesis-agent-conformance/scripts/report_contract.py",
        "synthesis-agent-conformance/references/conformance-report-v1.schema.json",
        "synthesis-onboarding/references/platform-ownership-v1.json",
    ):
        assert (
            receipt["entrypoints"][relative]
            == hashlib.sha256((ROOT / "skills" / relative).read_bytes()).hexdigest()
        )


def test_modular_runtime_inventory_contains_actual_contract_data():
    import modular

    files = modular.runtime_files(ROOT)
    for relative in (
        "skills/synthesis-agent-conformance/scripts/report_contract.py",
        "skills/synthesis-agent-conformance/references/conformance-report-v1.schema.json",
        "skills/synthesis-onboarding/references/platform-ownership-v1.json",
    ):
        assert (
            files[relative]["sha256"]
            == hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        )

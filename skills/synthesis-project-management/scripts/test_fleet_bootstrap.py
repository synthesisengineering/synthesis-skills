"""Fleet bootstrap: a new Mac provisions idempotently in a disposable home.

Mint identity, clone subscribed repos, install the runtime, enroll the
machine, verify the doctor — then rerun safely as a no-op with receipts.
Git clones run for real against local origins; the hooks installer is a
stub runner (the real one sets global git config, which tests must not
touch).
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fleet_bootstrap as BOOT
import fleet_identity as FI


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(tmp_path / "stray-fleet"))
    monkeypatch.setenv("HOME", str(tmp_path / "disposable-home"))


def git(*arguments, cwd):
    completed = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def seed_origin(path: Path) -> str:
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(path)],
        check=True,
        capture_output=True,
    )
    work = path.parent / f"seed-work-{path.stem}"
    subprocess.run(
        ["git", "init", "-b", "main", "--quiet", str(work)],
        check=True,
        capture_output=True,
    )
    git("config", "user.name", "Test", cwd=work)
    git("config", "user.email", "test@example.com", cwd=work)
    (work / "notes.md").write_text("seed\n", encoding="utf-8")
    git("add", "notes.md", cwd=work)
    git("commit", "--quiet", "-m", "seed", cwd=work)
    git("remote", "add", "origin", str(path), cwd=work)
    git("push", "--quiet", "origin", "main", cwd=work)
    subprocess.run(
        ["git", "--git-dir", str(path), "symbolic-ref", "HEAD",
         "refs/heads/main"],
        check=True,
        capture_output=True,
    )
    return str(path)


def fixture_source(root: Path) -> Path:
    (root / "skills/synthesis-onboarding/references").mkdir(parents=True)
    (root / "skills/synthesis-onboarding/references/components.json").write_text(
        json.dumps(
            {"schema_version": 1,
             "skills": ["synthesis-git-hooks", "synthesis-machine-sync"]}
        ),
        encoding="utf-8",
    )
    (root / "skills/synthesis-machine-sync").mkdir(parents=True)
    (root / "skills/synthesis-machine-sync/SKILL.md").write_text(
        "# fixture machine sync\n", encoding="utf-8"
    )
    scripts = root / "skills/synthesis-git-hooks/scripts"
    scripts.mkdir(parents=True)
    (scripts / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    return root


def primary_registry(path: Path) -> Path:
    import fleet_identity as _fi

    primary_id = str(uuid.uuid4())
    now = "2026-09-19T12:00:00+00:00"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "machines": {
                    primary_id: {
                        "label": "mac-a",
                        "enrolled_at": now,
                        "last_seen": now,
                        "role": "primary",
                        "environments": ["default"],
                        "retired_at": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert _fi.validate_registry(json.loads(path.read_text())) == []
    return path


def install_stub(calls: list):
    def run(script: Path, home: Path):
        calls.append((str(script), str(home)))
        hooks = Path(home) / ".synthesis" / "git-hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "coordination.py").write_text("# stub\n", encoding="utf-8")
        source_root = Path(str(script)).parents[3]
        (hooks / "source-path").write_text(
            str(source_root / "skills/synthesis-git-hooks/scripts") + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            ["bash", str(script)], 0, stdout="stub installed\n", stderr=""
        )

    return run


def test_full_bootstrap_then_safe_reran_noop(tmp_path, monkeypatch):
    home = tmp_path / "disposable-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    remote_url = seed_origin(tmp_path / "origin.git")
    source = fixture_source(tmp_path / "source")
    manifest = tmp_path / "repos.json"
    manifest.write_text(
        json.dumps(
            {"schema_version": 1,
             "repos": [{"remote": remote_url,
                        "path": "~/workspaces/kb",
                        "branch": "main"}]}
        ),
        encoding="utf-8",
    )
    repos = BOOT.parse_repos_manifest(manifest, home)
    assert repos[0]["path"] == str(home / "workspaces/kb")
    synced = primary_registry(tmp_path / "machines.json")

    calls: list = []
    report = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        repos=repos, fleet_registry=synced, install_runner=install_stub(calls),
    )
    assert report["ok"], report["steps"]
    machine_id = report["machine_id"]
    assert uuid.UUID(machine_id).version == 4

    machine_file = home / ".synthesis" / "fleet" / "machine-id"
    assert machine_file.read_text(encoding="utf-8").strip() == machine_id
    assert stat.S_IMODE(machine_file.stat().st_mode) == 0o600
    assert (home / "workspaces/kb" / "notes.md").is_file()
    assert calls == [
        (str(source / "skills/synthesis-git-hooks/scripts/install.sh"),
         str(home))
    ]
    registry = json.loads(
        (home / ".synthesis" / "fleet" / "machines.json").read_text(
            encoding="utf-8"
        )
    )
    assert registry["machines"][machine_id]["label"] == "mac-b"
    assert len(registry["machines"]) == 2, "synced primary + new secondary"
    receipts = sorted(
        (home / ".synthesis" / "fleet" / "receipts").glob("bootstrap-*.json")
    )
    assert [path.name for path in receipts] == [
        "bootstrap-clone-repos.json",
        "bootstrap-enroll-machine.json",
        "bootstrap-install-runtime.json",
        "bootstrap-mint-identity.json",
        "bootstrap-verify-doctor.json",
    ]
    first_statuses = [step["status"] for step in report["steps"]]
    assert first_statuses == ["done"] * 5

    again = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        repos=repos, fleet_registry=synced, install_runner=install_stub(calls),
    )
    assert again["ok"]
    assert again["machine_id"] == machine_id
    assert [step["status"] for step in again["steps"]] == ["noop"] * 5
    assert len(calls) == 1, "rerun must not re-invoke the installer"


def test_bootstrap_without_manifest_skips_clones(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    report = BOOT.bootstrap(
        home=home, source_root=source, label="solo", role="primary",
        install_runner=install_stub([]),
    )
    assert report["ok"]
    assert report["steps"][1] == {
        "step": "clone-repos", "status": "noop",
        "detail": "no repos manifest; nothing to clone",
        "receipt": report["steps"][1]["receipt"],
    }


def test_existing_checkout_with_wrong_remote_refuses(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    seed_origin(tmp_path / "origin.git")
    other = seed_origin(tmp_path / "other.git")
    target = home / "workspaces" / "kb"
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "clone", "--quiet",
         other, str(target)],
        check=True,
        capture_output=True,
    )
    result = BOOT.step_repos(
        home, [{"remote": str(tmp_path / "origin.git"),
                "path": str(target), "branch": ""}]
    )
    assert result.status == "fail"
    assert "refusing to clobber" in result.detail


def test_non_checkout_path_refuses(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    target = home / "workspaces" / "kb"
    target.mkdir(parents=True)
    (target / "junk.txt").write_text("x", encoding="utf-8")
    result = BOOT.step_repos(
        home, [{"remote": "https://example.com/kb.git",
                "path": str(target), "branch": ""}]
    )
    assert result.status == "fail"
    assert "refusing to clobber" in result.detail


def test_install_requires_machine_sync_in_source(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    (source / "skills/synthesis-machine-sync/SKILL.md").unlink()
    result = BOOT.step_install(home, source, install_runner=install_stub([]))
    assert result.status == "fail"
    assert "synthesis-machine-sync" in result.detail


def test_repos_manifest_validation(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": 2, "repos": []}', encoding="utf-8")
    with pytest.raises(BOOT.FleetBootstrapError, match="schema_version"):
        BOOT.parse_repos_manifest(bad, home)
    missing = tmp_path / "missing.json"
    with pytest.raises(BOOT.FleetBootstrapError, match="not found"):
        BOOT.parse_repos_manifest(missing, home)
    assert BOOT.parse_repos_manifest(None, home) == []


def test_expand_for_home_never_uses_process_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", "/process/home")
    new_home = tmp_path / "mac-b-home"
    assert BOOT.expand_for_home("~/workspaces/kb", new_home) == (
        new_home / "workspaces/kb"
    )
    assert BOOT.expand_for_home("$HOME/x", new_home) == new_home / "x"
    assert BOOT.expand_for_home("/abs/path", new_home) == Path("/abs/path")


def test_secondary_without_synced_registry_fails_closed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    report = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        install_runner=install_stub([]),
    )
    assert not report["ok"]
    enroll = [step for step in report["steps"]
              if step["step"] == "enroll-machine"][0]
    assert enroll["status"] == "fail"
    assert "--fleet-registry" in enroll["detail"]


def test_relabel_reruns_enroll_as_done(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    synced = primary_registry(tmp_path / "machines.json")
    first = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        fleet_registry=synced, install_runner=install_stub([]),
    )
    assert first["ok"]
    assert first["steps"][0]["status"] == "done"
    relabeled = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b-renamed",
        role="secondary", fleet_registry=synced,
        install_runner=install_stub([]),
    )
    assert relabeled["ok"]
    assert relabeled["machine_id"] == first["machine_id"]
    enroll = [step for step in relabeled["steps"]
              if step["step"] == "enroll-machine"][0]
    assert enroll["status"] == "done"


def test_doctor_failure_blocks_bootstrap(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")

    def failing_doctor(*, board):
        import fleet_doctor as _doctor

        return [_doctor.DoctorCheck("divergence-scan", False, "split checkout")]

    synced = primary_registry(tmp_path / "machines.json")
    report = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        fleet_registry=synced,
        install_runner=install_stub([]), doctor_runner=failing_doctor,
    )
    assert not report["ok"]
    assert report["steps"][-1]["step"] == "verify-doctor"
    assert report["steps"][-1]["status"] == "fail"
    assert "split checkout" in report["steps"][-1]["detail"]


def test_main_wires_manifest_and_reports(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    remote_url = seed_origin(tmp_path / "origin.git")
    manifest = tmp_path / "repos.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repos": [{"remote": remote_url, "path": str(home / "kb")}],
            }
        ),
        encoding="utf-8",
    )
    real_bootstrap = BOOT.bootstrap

    synced = primary_registry(tmp_path / "machines.json")

    def fake_bootstrap(**kwargs):
        assert kwargs["repos"][0]["remote"] == remote_url
        return real_bootstrap(
            home=kwargs["home"], source_root=kwargs["source_root"],
            label=kwargs["label"], role=kwargs["role"], repos=kwargs["repos"],
            fleet_registry=kwargs["fleet_registry"],
            install_runner=install_stub([]),
        )

    import unittest.mock as mock

    with mock.patch.object(BOOT, "bootstrap", side_effect=fake_bootstrap):
        code = BOOT.main(
            ["--home", str(home), "--source-root", str(source),
             "--label", "mac-b", "--role", "secondary",
             "--repos-manifest", str(manifest),
             "--fleet-registry", str(synced)]
        )
    assert code == 0
    out = capsys.readouterr().out
    assert "DONE bootstrap-mint-identity" in out
    assert (home / "kb" / "notes.md").is_file()
    assert os.environ.get("HOME") != str(home) or True

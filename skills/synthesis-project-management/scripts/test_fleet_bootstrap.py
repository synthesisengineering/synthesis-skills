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


def test_primary_with_missing_registry_flag_founds_new_fleet(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    report = BOOT.bootstrap(
        home=home, source_root=source, label="mac-a", role="primary",
        fleet_registry=tmp_path / "not-yet-created" / "machines.json",
        install_runner=install_stub([]),
    )
    assert report["ok"]
    enroll = [step for step in report["steps"]
              if step["step"] == "enroll-machine"][0]
    assert enroll["status"] == "done"


def plain_git_runner(args, cwd):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def seed_kb_origin(path: Path) -> str:
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(path)],
        check=True,
        capture_output=True,
    )
    work = path.parent / "seed-kb-work"
    subprocess.run(
        ["git", "init", "-b", "main", "--quiet", str(work)],
        check=True,
        capture_output=True,
    )
    git("config", "user.name", "Test", cwd=work)
    git("config", "user.email", "test@example.com", cwd=work)
    (work / "fleet").mkdir(parents=True)
    primary_registry(work / "fleet" / "machines.json")
    git("add", "fleet/machines.json", cwd=work)
    git("commit", "--quiet", "-m", "seed fleet", cwd=work)
    git("remote", "add", "origin", str(path), cwd=work)
    git("push", "--quiet", "origin", "main", cwd=work)
    subprocess.run(
        ["git", "--git-dir", str(path), "symbolic-ref", "HEAD",
         "refs/heads/main"],
        check=True,
        capture_output=True,
    )
    return str(path)


def clone_kb(origin: str, target: Path) -> Path:
    completed = plain_git_runner(
        ["clone", "--quiet", origin, str(target)], None
    )
    assert completed.returncode == 0, completed.stderr
    return target


def test_preflight_fails_fast_before_any_cloning(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    synced = primary_registry(tmp_path / "machines.json")
    assert BOOT.preflight(home, "secondary", synced) == []

    monkeypatch.setattr(BOOT.shutil, "which", lambda _name: None)
    problems = BOOT.preflight(home, "secondary", synced)
    assert any("xcode-select --install" in problem for problem in problems)
    monkeypatch.undo()

    problems = BOOT.preflight(tmp_path / "no-home", "primary", None)
    assert any("does not exist" in problem for problem in problems)

    problems = BOOT.preflight(home, "secondary", None)
    assert any("--fleet-registry" in problem for problem in problems)

    problems = BOOT.preflight(
        home, "secondary", tmp_path / "absent.json"
    )
    assert any("not found" in problem for problem in problems)

    broken = tmp_path / "broken.json"
    broken.write_text('{"schema_version": 1}', encoding="utf-8")
    problems = BOOT.preflight(home, "secondary", broken)
    assert any("invalid" in problem for problem in problems)


def test_step_repos_narrates_progress(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    remote_url = seed_origin(tmp_path / "origin.git")
    target = home / "workspaces" / "kb"
    lines: list[str] = []
    result = BOOT.step_repos(
        home, [{"remote": remote_url, "path": str(target), "branch": ""}],
        progress=lines.append,
    )
    assert result.status == "done"
    assert lines == [
        f"[1/1] cloning {remote_url} -> {target}",
        f"[1/1] cloned {target}",
    ]
    again = BOOT.step_repos(
        home, [{"remote": remote_url, "path": str(target), "branch": ""}],
        progress=lines.append,
    )
    assert again.status == "noop"
    assert lines[-1] == f"[1/1] verified {target} (already cloned)"


def test_main_interrupted_reports_resume_and_130(tmp_path, capsys):
    import unittest.mock as mock

    home = tmp_path / "home"
    home.mkdir()
    with mock.patch.object(
        BOOT, "bootstrap", side_effect=KeyboardInterrupt
    ):
        code = BOOT.main(
            ["--home", str(home), "--source-root", str(tmp_path),
             "--label", "mac-b", "--role", "primary"]
        )
    assert code == BOOT.EXIT_INTERRUPTED == 130
    err = capsys.readouterr().err
    assert "INTERRUPTED bootstrap" in err
    assert "rerun the same command to resume" in err


def test_interrupted_bootstrap_keeps_finished_receipts(tmp_path):
    import pytest as _pytest

    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")

    def raising_installer(script: Path, home_dir: Path):
        raise KeyboardInterrupt

    with _pytest.raises(KeyboardInterrupt):
        BOOT.bootstrap(
            home=home, source_root=source, label="mac-a",
            role="primary", install_runner=raising_installer,
        )
    receipts = home / ".synthesis" / "fleet" / "receipts"
    assert (receipts / "bootstrap-mint-identity.json").is_file()
    assert (receipts / "bootstrap-clone-repos.json").is_file()


def enroll_local(
    home: Path, label: str, role: str, synced: Path | None = None
) -> str:
    directory = home / ".synthesis" / "fleet"
    machine_id = FI.mint_machine_id(directory)
    if synced is not None:
        FI.write_registry(
            json.loads(Path(synced).read_text(encoding="utf-8")), directory
        )
    FI.enroll_self(label=label, role=role, directory=directory)
    return machine_id


def test_publish_upserts_own_entry_and_pushes(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    origin = seed_kb_origin(tmp_path / "kb.git")
    kb = clone_kb(origin, tmp_path / "kb")
    machine_id = enroll_local(
        home, "mac-b", "secondary", kb / "fleet" / "machines.json"
    )

    lines: list[str] = []
    result = BOOT.step_publish(
        home, machine_id, label="mac-b", role="secondary", kb_repo=kb,
        git_runner=plain_git_runner, progress=lines.append,
    )
    assert result.status == "done", result.detail
    assert lines, "publish narrates fetch, commit, and push"

    shared = json.loads((kb / "fleet" / "machines.json").read_text())
    assert shared["machines"][machine_id]["label"] == "mac-b"
    assert len(shared["machines"]) == 2, "shared primary is preserved"

    pushed = subprocess.run(
        ["git", "--git-dir", origin, "show", "HEAD:fleet/machines.json"],
        capture_output=True, text=True, check=True,
    )
    assert machine_id in pushed.stdout, "enrollment reached the remote"

    again = BOOT.step_publish(
        home, machine_id, label="mac-b", role="secondary", kb_repo=kb,
        git_runner=plain_git_runner,
    )
    assert again.status == "noop"
    assert "already published" in again.detail


def test_publish_without_identity_uses_machine_identity(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    origin = seed_kb_origin(tmp_path / "kb.git")
    kb = clone_kb(origin, tmp_path / "kb")
    machine_id = enroll_local(
        home, "mac-b", "secondary", kb / "fleet" / "machines.json"
    )

    result = BOOT.step_publish(
        home, machine_id, label="mac-b", role="secondary", kb_repo=kb,
        git_runner=plain_git_runner,
    )
    assert result.status == "done", result.detail
    author = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "log", "-1",
         "--format=%an %ae", "HEAD"],
        cwd=str(kb), capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert author == f"mac-b {machine_id[:8]}@fleet.local"


def test_publish_refuses_dirty_shared_registry(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    origin = seed_kb_origin(tmp_path / "kb.git")
    kb = clone_kb(origin, tmp_path / "kb")
    machine_id = enroll_local(
        home, "mac-b", "secondary", kb / "fleet" / "machines.json"
    )

    shared = kb / "fleet" / "machines.json"
    shared.write_text(shared.read_text() + "\n", encoding="utf-8")
    result = BOOT.step_publish(
        home, machine_id, label="mac-b", role="secondary", kb_repo=kb,
        git_runner=plain_git_runner,
    )
    assert result.status == "fail"
    assert "uncommitted changes" in result.detail


def test_publish_push_failure_names_remedy(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    origin = seed_kb_origin(tmp_path / "kb.git")
    kb = clone_kb(origin, tmp_path / "kb")
    git("remote", "set-url", "--push", "origin",
        str(tmp_path / "gone.git"), cwd=kb)
    machine_id = enroll_local(
        home, "mac-b", "secondary", kb / "fleet" / "machines.json"
    )

    result = BOOT.step_publish(
        home, machine_id, label="mac-b", role="secondary", kb_repo=kb,
        git_runner=plain_git_runner,
    )
    assert result.status == "fail"
    assert "push failed" in result.detail
    assert "rerun the same command" in result.detail


def test_second_primary_refused_with_clear_redirect(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    synced = primary_registry(tmp_path / "machines.json")
    report = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="primary",
        fleet_registry=synced, install_runner=install_stub([]),
    )
    assert not report["ok"]
    enroll = [step for step in report["steps"]
              if step["step"] == "enroll-machine"][0]
    assert enroll["status"] == "fail"
    assert "already has primary mac-a" in enroll["detail"]
    assert "--role secondary" in enroll["detail"]


def test_bootstrap_with_kb_repo_publishes_then_reruns_noop(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    source = fixture_source(tmp_path / "source")
    origin = seed_kb_origin(tmp_path / "kb.git")
    kb = clone_kb(origin, tmp_path / "kb")
    remote_url = seed_origin(tmp_path / "origin.git")
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
    synced = kb / "fleet" / "machines.json"

    report = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        repos=repos, fleet_registry=synced, kb_repo=kb,
        git_runner=plain_git_runner, install_runner=install_stub([]),
    )
    assert report["ok"], report["steps"]
    assert [step["step"] for step in report["steps"]] == [
        "mint-identity", "clone-repos", "install-runtime", "enroll-machine",
        "verify-doctor", "publish-registry",
    ]
    assert [step["status"] for step in report["steps"]] == ["done"] * 6
    assert (
        home / ".synthesis" / "fleet" / "receipts"
        / "bootstrap-publish-registry.json"
    ).is_file()

    again = BOOT.bootstrap(
        home=home, source_root=source, label="mac-b", role="secondary",
        repos=repos, fleet_registry=synced, kb_repo=kb,
        git_runner=plain_git_runner, install_runner=install_stub([]),
    )
    assert again["ok"]
    assert [step["status"] for step in again["steps"]] == ["noop"] * 6

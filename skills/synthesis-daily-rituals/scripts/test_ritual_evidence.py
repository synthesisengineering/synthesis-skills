"""Causal worker evidence and names-only ritual controls; all inputs synthetic."""

from __future__ import annotations
import dataclasses
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml
import ritual_workers as workers
import ritual_state as state
import credential_paths as paths

SCRIPT = Path(state.__file__)


@pytest.fixture
def worker(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    artifacts = root / "private/ritual-workers"
    artifacts.mkdir(parents=True)
    return workers.Worker(
        "alpha",
        "active",
        str(artifacts),
        str(artifacts),
        "operations",
        str(root),
        ("mail", "calendar"),
    )


def payload(worker):
    return {
        "contract_version": 1,
        "workspace": "alpha",
        "seat": "operations",
        "run_type": "day-end",
        "date": "2026-09-26",
        "session": "s-synthetic-worker",
        "agent": "synthetic fixture",
        "started": "2026-09-26T00:00:00+00:00",
        "finished": "2026-09-26T01:00:00+00:00",
        "outcome": "clean",
        "coverage": [
            {"surface": x, "status": "synced", "detail": "synthetic fixture checked"}
            for x in worker.surfaces
        ],
        "gaps": [],
        "lesson_candidates": [],
    }


def artifact(worker, data=None, body=None):
    path = worker.artifact_path("2026-09-26-day-end.md")
    if body is None:
        body = "\n".join("## " + h + "\nnone\n" for h in workers.BODY_SECTIONS)
    path.write_text(
        "---\n"
        + yaml.safe_dump(data if data is not None else payload(worker))
        + "---\n"
        + body
    )
    return path


def verify(worker, **kw):
    return workers.verify_artifact(
        worker,
        day="2026-09-26",
        run_type="day-end",
        session="s-synthetic-worker",
        outcome="clean",
        cwd=Path(worker.workspace_root),
        **kw,
    )


def registry(tmp_path, worker):
    path = tmp_path / "workers.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": 1,
                "workers": {
                    "alpha": {
                        "status": worker.status,
                        "artifact_dir": worker.artifact_dir,
                        "seat": worker.seat,
                        "workspace_root": worker.workspace_root,
                        "surfaces": list(worker.surfaces),
                    }
                },
            }
        )
    )
    return path


def test_actual_artifact_bound_to_workspace_and_digest(worker):
    path = artifact(worker)
    result = verify(worker)
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (
        result["session"] == "s-synthetic-worker" and result["lesson_candidates"] == 0
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace", "beta"),
        ("seat", "other"),
        ("date", "2026-09-25"),
        ("run_type", "day-start"),
        ("session", "foreign"),
        ("outcome", "partial"),
        ("contract_version", True),
        ("agent", ""),
    ],
)
def test_foreign_identity_is_refused(worker, field, value):
    data = payload(worker)
    data[field] = value
    artifact(worker, data)
    with pytest.raises(workers.RitualWorkersError):
        verify(worker)


@pytest.mark.parametrize(
    "change",
    [
        "absent",
        "symlink",
        "hardlink",
        "fifo",
        "unreadable",
        "group-writable",
        "directory",
        "oversized",
    ],
)
def test_bad_artifact_storage_refused(worker, change):
    path = artifact(worker)
    if change == "absent":
        path.unlink()
    elif change == "symlink":
        target = path.with_suffix(".target")
        path.rename(target)
        path.symlink_to(target)
    elif change == "hardlink":
        os.link(path, path.with_suffix(".link"))
    elif change == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif change == "unreadable":
        path.chmod(0)
    elif change == "group-writable":
        path.chmod(0o664)
    elif change == "directory":
        path.unlink()
        path.mkdir()
    else:
        path.write_bytes(b"x" * (workers.MAX_ARTIFACT_BYTES + 1))
    try:
        with pytest.raises(workers.RitualWorkersError):
            verify(worker)
    finally:
        if change == "unreadable":
            path.chmod(0o644)


def test_parent_link_refused(worker, tmp_path):
    artifact(worker)
    real = Path(worker.artifact_dir)
    link = real.with_name("alias")
    link.symlink_to(real)
    with pytest.raises(workers.RitualWorkersError):
        verify(dataclasses.replace(worker, artifact_dir=str(link)))


def test_cross_workspace_cwd_refused(worker, tmp_path):
    artifact(worker)
    with pytest.raises(workers.RitualWorkersError, match="foreign workspace"):
        workers.verify_artifact(
            worker,
            day="2026-09-26",
            run_type="day-end",
            session="s-synthetic-worker",
            outcome="clean",
            cwd=tmp_path,
        )


@pytest.mark.parametrize(
    "change",
    [
        "coverage-missing",
        "coverage-duplicate",
        "coverage-partial",
        "gap",
        "future",
        "no-zone",
        "backward",
        "section-missing",
        "section-empty",
        "aliases",
        "duplicate-key",
        "lesson-absent",
        "lesson-foreign",
        "lesson-missing",
    ],
)
def test_false_completion_and_unsafe_frontmatter_refused(worker, tmp_path, change):
    data = payload(worker)
    if change == "coverage-missing":
        data["coverage"].pop()
    elif change == "coverage-duplicate":
        data["coverage"][1] = data["coverage"][0]
    elif change == "coverage-partial":
        data["coverage"][0]["status"] = "partial"
    elif change == "gap":
        data["gaps"] = ["unread surface"]
    elif change == "future":
        data["finished"] = "2999-01-01T00:00:00Z"
    elif change == "no-zone":
        data["finished"] = "2026-09-26T01:00:00"
    elif change == "backward":
        data["finished"] = "2026-09-25T00:00:00Z"
    elif change == "lesson-absent":
        del data["lesson_candidates"]
    elif change == "lesson-foreign":
        data["lesson_candidates"] = [
            {"id": "lesson1", "pointer": str(tmp_path / "foreign.md")}
        ]
    elif change == "lesson-missing":
        data["lesson_candidates"] = [
            {"id": "lesson1", "pointer": str(Path(worker.workspace_root) / "absent.md")}
        ]
    path = artifact(worker, data)
    if change == "section-missing":
        path.write_text(path.read_text().replace("## Lesson candidates\nnone\n", ""))
    elif change == "section-empty":
        path.write_text(
            path.read_text().replace(
                "## Lesson candidates\nnone\n", "## Lesson candidates\n"
            )
        )
    elif change == "aliases":
        path.write_text(path.read_text().replace("gaps: []", "gaps: &g []\nother: *g"))
    elif change == "duplicate-key":
        path.write_text(
            path.read_text().replace(
                "workspace: alpha", "workspace: alpha\nworkspace: alpha"
            )
        )
    with pytest.raises(workers.RitualWorkersError):
        verify(worker)


def test_partial_evidence_records_partial_not_clean(worker):
    data = payload(worker)
    data["coverage"][0]["status"] = "failed"
    data["gaps"] = ["mail unavailable"]
    data["outcome"] = "partial"
    artifact(worker, data)
    result = workers.verify_artifact(
        worker,
        day="2026-09-26",
        run_type="day-end",
        session="s-synthetic-worker",
        outcome="partial",
        cwd=Path(worker.workspace_root),
    )
    assert result["sha256"]


def test_lesson_pointer_stays_local_and_contents_not_read(worker, monkeypatch):
    lesson = Path(worker.workspace_root) / "lesson.md"
    lesson.write_text("synthetic private fixture")
    data = payload(worker)
    data["lesson_candidates"] = [{"id": "candidate-1", "pointer": str(lesson)}]
    artifact(worker, data)
    original = workers.read_regular

    def read(path, *a, **k):
        assert Path(path) != lesson
        return original(path, *a, **k)

    monkeypatch.setattr(workers, "read_regular", read)
    assert verify(worker)["lesson_candidates"] == 1


def test_real_record_owner_is_atomic_on_refusal_and_records_receipt(worker, tmp_path):
    reg = registry(tmp_path, worker)
    env = {**os.environ, "RITUAL_WORKERS_FILE": str(reg)}
    directory = tmp_path / "state"
    argv = [
        sys.executable,
        str(SCRIPT),
        "--state-dir",
        str(directory),
        "record",
        "--workspace",
        "alpha",
        "--direction",
        "day-end",
        "--date",
        "2026-09-26",
        "--session",
        "s-synthetic-worker",
    ]
    failed = subprocess.run(
        argv,
        env=env,
        cwd=worker.workspace_root,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert failed.returncode != 0 and not (directory / "history.jsonl").exists()
    p = artifact(worker)
    passed = subprocess.run(
        argv,
        env=env,
        cwd=worker.workspace_root,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert passed.returncode == 0, passed.stderr
    record = json.loads((directory / "history.jsonl").read_text())
    assert record["artifact"]["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert record["workspace"] == "alpha"


def test_migration_markers_neither_open_nor_close_real_work():
    real = {
        "date": "2026-09-26",
        "direction": "day-start",
        "workspace": "alpha",
        "mode": "full",
    }
    marker = {**real, "mode": "migration"}
    today = datetime.date(2026, 9, 26)
    assert state.q_open([marker], today) == []
    assert state.q_open([real, {**marker, "direction": "day-end"}], today) == [
        ("alpha", "2026-09-26")
    ]
    assert state.q_open([real, {**real, "direction": "day-end"}], today) == []


def init_repo(root, name):
    repo = root / name
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(repo)], check=True, capture_output=True, timeout=5
    )
    return repo


def manifest(root, entries):
    p = root / ".agents/repos.yaml"
    p.parent.mkdir(exist_ok=True)
    p.write_text(yaml.safe_dump({"repos": entries}))


def test_names_only_real_git_includes_dormant_unsynced_deleted_and_weird_names(
    tmp_path, monkeypatch
):
    root = tmp_path / "workspace"
    root.mkdir()
    repo = init_repo(root, "private")
    names = [
        ".env",
        "credentials.json",
        "keys/client.pem",
        "line\nbreak.secret",
        "normal.md",
        ".env.example",
    ]
    for n in names:
        p = repo / n
        p.parent.mkdir(exist_ok=True)
        p.write_text("SYNTHETIC CONTENT NEVER TO BE READ")
    subprocess.run(
        ["git", "-C", str(repo), "add", "--all"],
        check=True,
        capture_output=True,
        timeout=5,
    )
    # A tracked path can be unreadable/deleted/FIFO: the inventory must not open it.
    (repo / "credentials.json").chmod(0)
    (repo / ".env").unlink()
    pem = repo / "keys/client.pem"
    pem.unlink()
    os.mkfifo(pem)
    manifest(
        root,
        [
            {
                "name": "private",
                "path": "private",
                "status": "dormant",
                "ritual_sync": False,
            }
        ],
    )
    old = paths.read_regular

    def read(path, *a, **kw):
        assert Path(path).name == "repos.yaml"
        return old(path, *a, **kw)

    monkeypatch.setattr(paths, "read_regular", read)
    report = paths.inventory(root)
    assert report["complete"] and report["secret_contents_read"] is False
    assert {x["path"] for x in report["findings"]} == set(names) - {"normal.md"}
    assert report["repositories"][0]["tracked_count"] == len(names)
    (repo / "credentials.json").chmod(0o644)


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "foreign",
        "linked",
        "duplicate",
        "malformed",
        "empty",
        "bad-git",
        "oversized",
        "timeout",
        "invalid-utf8",
    ],
)
def test_inventory_cannot_hide_unscanned_repos(tmp_path, monkeypatch, kind):
    root = tmp_path / "workspace"
    root.mkdir()
    repo = init_repo(root, "repo")
    entries = [{"name": "repo"}]
    if kind == "missing":
        entries.append({"name": "absent"})
    elif kind == "foreign":
        entries[0]["path"] = str(tmp_path / "elsewhere")
    elif kind == "linked":
        (root / "alias").symlink_to(repo)
        entries[0]["path"] = "alias"
    elif kind == "duplicate":
        entries.append({"name": "repo"})
    elif kind == "malformed":
        entries = [None]
    elif kind == "empty":
        entries = []
    elif kind == "bad-git":
        monkeypatch.setattr(
            paths,
            "_git_names",
            lambda *a: (_ for _ in ()).throw(paths.RitualWorkersError("failed")),
        )
    elif kind == "oversized":
        monkeypatch.setattr(
            paths, "_git_names", lambda *a: b"x" * (paths.MAX_TRACKED_BYTES + 1)
        )
    elif kind == "timeout":
        monkeypatch.setattr(
            paths,
            "_git_names",
            lambda *a: (_ for _ in ()).throw(subprocess.TimeoutExpired(["fixture"], 1)),
        )
    elif kind == "invalid-utf8":
        monkeypatch.setattr(paths, "_git_names", lambda *a: b"\xff\0")
    manifest(root, entries)
    report = paths.inventory(root)
    assert not report["complete"] and report["gaps"]


def test_manifest_symlink_only_inside_workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    _repo = init_repo(root, "repo")
    manifest(root, [{"name": "repo"}])
    original = root / ".agents/repos.yaml"
    target = root / "repos.yaml"
    original.rename(target)
    original.symlink_to(target)
    assert paths.inventory(root)["complete"]
    target.rename(tmp_path / "foreign.yaml")
    original.unlink()
    original.symlink_to(tmp_path / "foreign.yaml")
    assert not paths.inventory(root)["complete"]


def test_registry_override_cannot_bypass_production_worker_check(tmp_path, monkeypatch):
    monkeypatch.setenv("RITUAL_WORKERS_FILE", str(tmp_path / "missing"))
    monkeypatch.delenv("RITUAL_STATE_DIR", raising=False)
    with pytest.raises(workers.RitualWorkersError, match="non-production"):
        workers.load_workers()


def test_changed_artifact_during_read_is_refused(worker, monkeypatch):
    p = artifact(worker)
    old = workers.os.read
    changed = False

    def raced(fd, size):
        nonlocal changed
        out = old(fd, size)
        if not changed:
            changed = True
            with p.open("ab") as stream:
                stream.write(b"changed\n")
        return out

    monkeypatch.setattr(workers.os, "read", raced)
    with pytest.raises(workers.RitualWorkersError, match="changed"):
        verify(worker)


def test_deep_yaml_refuses_with_bounded_diagnostic():
    with pytest.raises(workers.RitualWorkersError, match="nesting"):
        workers.strict_yaml("[" * 40 + "0" + "]" * 40)


def test_invalid_yaml_refuses_as_diagnostic(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    manifest(root, [{"name": "one"}])
    (root / ".agents/repos.yaml").write_text("repos: [\n")
    report = paths.inventory(root)
    assert not report["complete"] and report["gaps"]


def test_worker_missing_readiness_is_not_silently_inferred(worker):
    assert workers.worker_readiness(
        dataclasses.replace(worker, workspace_root=None, surfaces=())
    ) == [
        "registry workspace_root is missing",
        "registry surfaces are missing; declare the actual coverage contract",
    ]


def test_credential_command_does_not_treat_findings_as_secret_proof(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    repo = init_repo(root, "repo")
    (repo / "token.json").write_text("synthetic")
    subprocess.run(
        ["git", "-C", str(repo), "add", "token.json"],
        check=True,
        capture_output=True,
        timeout=5,
    )
    manifest(root, [{"name": "repo"}])
    done = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "credential-paths",
            "--workspace-root",
            str(root),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["complete"] and result["findings"] == [
        {"repo": "repo", "path": "token.json"}
    ]
    assert result["secret_contents_read"] is False


@pytest.mark.parametrize("kind", ["output-bound", "stderr-bound", "timeout"])
def test_owned_git_process_bounded_and_reaped(tmp_path, monkeypatch, kind):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "git"
    body = {
        "output-bound": "import os\nwhile True: os.write(1,b'x'*65536)\n",
        "stderr-bound": "import os\nwhile True: os.write(2,b'e'*65536)\n",
        "timeout": "import time\ntime.sleep(30)\n",
    }[kind]
    exe.write_text("#!" + sys.executable + "\n" + body)
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(paths, "MAX_TRACKED_BYTES", 1024)
    monkeypatch.setattr(paths, "PER_REPO_SECONDS", 0.2)
    pids = []
    original = paths.subprocess.Popen

    def launch(*a, **k):
        p = original(*a, **k)
        pids.append(p)
        return p

    monkeypatch.setattr(paths.subprocess, "Popen", launch)
    with pytest.raises(paths.RitualWorkersError):
        paths._git_names(tmp_path, 1)
    assert len(pids) == 1 and pids[0].poll() is not None


def test_total_tracked_path_bound_preserves_coverage_gap(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    init_repo(root, "a")
    init_repo(root, "b")
    manifest(root, [{"name": "a"}, {"name": "b"}])
    monkeypatch.setattr(paths, "MAX_TOTAL_TRACKED_BYTES", 5)
    monkeypatch.setattr(paths, "_git_names", lambda *a: b".env\0")
    result = paths.inventory(root)
    assert not result["complete"] and result["repositories"][1]["status"] == "unscanned"
    assert result["findings"] == [{"repo": "a", "path": ".env"}]


def test_cli_cannot_hide_real_work_as_migration(tmp_path):
    done = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--state-dir",
            str(tmp_path / "state"),
            "record",
            "--workspace",
            "alpha",
            "--direction",
            "day-start",
            "--date",
            "2026-09-26",
            "--mode",
            "migration",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert done.returncode != 0 and "reserved" in done.stderr
    assert not (tmp_path / "state/history.jsonl").exists()


def test_installed_copy_has_worker_evidence_dependency_closure(worker, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "RITUAL_WORKERS_FILE": str(registry(tmp_path, worker)),
    }
    installer = SCRIPT.with_name("install_day_end.py")
    result = subprocess.run(
        [sys.executable, str(installer), "--no-launchctl"],
        env=env,
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stderr
    installed = home / ".synthesis/day-end/bin/ritual_state.py"
    artifact(worker)
    result = subprocess.run(
        [
            sys.executable,
            str(installed),
            "--state-dir",
            str(tmp_path / "state"),
            "record",
            "--workspace",
            "alpha",
            "--direction",
            "day-end",
            "--date",
            "2026-09-26",
            "--session",
            "s-synthetic-worker",
        ],
        env=env,
        cwd=worker.workspace_root,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "state/history.jsonl").read_text())["artifact"][
        "sha256"
    ]
    for helper in ("ritual_workers.py", "credential_paths.py"):
        assert (
            installed.with_name(helper).read_bytes()
            == SCRIPT.with_name(helper).read_bytes()
        )


def test_exited_parent_with_child_holding_pipe_does_not_escape_cleanup(
    tmp_path, monkeypatch
):
    import time
    import signal

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "git"
    marker = tmp_path / "child-survived"
    # The child retains the Git command's pipe after its direct parent exits.
    code = (
        "import os,time\npid=os.fork()\nif pid: os._exit(0)\ntime.sleep(0.7)\nopen("
        + repr(str(marker))
        + ",'w').write('survived')\n"
    )
    exe.write_text("#!" + sys.executable + "\n" + code)
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(paths, "PER_REPO_SECONDS", 0.1)
    groups = []
    original = paths.os.killpg

    def kill(group, sig):
        groups.append((group, sig))
        return original(group, sig)

    monkeypatch.setattr(paths.os, "killpg", kill)
    with pytest.raises(paths.RitualWorkersError, match="timed out"):
        paths._git_names(tmp_path, 1)
    assert groups and groups[-1][1] == signal.SIGKILL
    time.sleep(0.8)
    assert not marker.exists()


def test_unknown_outcome_cannot_rename_a_partial_run_as_done(worker):
    data = payload(worker)
    data["outcome"] = "done"
    data["coverage"][0]["status"] = "failed"
    data["gaps"] = ["failed"]
    artifact(worker, data)
    with pytest.raises(workers.RitualWorkersError, match="vocabulary"):
        workers.verify_artifact(
            worker,
            day="2026-09-26",
            run_type="day-end",
            session="s-synthetic-worker",
            outcome="done",
            cwd=Path(worker.workspace_root),
        )


def test_owner_registry_may_link_to_its_versioned_file(worker, tmp_path):
    target = registry(tmp_path, worker)
    link = tmp_path / "installed-workers.yaml"
    link.symlink_to(target)
    assert workers.load_workers(link)["alpha"].workspace_root == worker.workspace_root

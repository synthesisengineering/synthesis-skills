from pathlib import Path
import sys
import json
import os
import subprocess
import pytest

P = Path(__file__).resolve().parents[3]
D = P / "skills/synthesis-daily-rituals/scripts"
sys.path.insert(0, str(D))
import ritual_state  # noqa: E402 - register sibling script path first
import credential_paths  # noqa: E402 - register sibling script path first


def git(path, *args):
    env = dict(
        os.environ,
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_OPTIONAL_LOCKS="0",
    )
    return subprocess.run(
        ["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(path), *args],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )


def test_short_write_does_not_report_success(tmp_path, monkeypatch):
    monkeypatch.setenv("RITUAL_STATE_DIR", str(tmp_path / "state"))
    real = ritual_state.os.write

    def partial(fd, data):
        return real(fd, data[:3])

    monkeypatch.setattr(ritual_state.os, "write", partial)
    ritual_state.append_record(
        {"date": "2026-09-26", "direction": "day-end", "workspace": "fixture"}
    )
    data = ritual_state.log_path().read_bytes()
    assert json.loads(data)["workspace"] == "fixture"


def test_record_fsync_failure_is_observed(tmp_path, monkeypatch):
    monkeypatch.setenv("RITUAL_STATE_DIR", str(tmp_path / "state"))

    def fail(fd):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(ritual_state.os, "fsync", fail)
    with pytest.raises((OSError, SystemExit)):
        ritual_state.append_record(
            {"date": "2026-09-26", "direction": "day-end", "workspace": "fixture"}
        )


def test_inventory_refuses_foreign_gitdir(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    git(foreign, "init")
    (foreign / "foreign-credentials.json").write_text("synthetic fixture")
    git(foreign, "add", "foreign-credentials.json")
    declared = root / "named"
    declared.mkdir()
    (declared / ".git").write_text("gitdir: " + str(foreign / ".git") + "\n")
    (root / ".agents").mkdir()
    (root / ".agents/repos.yaml").write_text("repos:\n  - name: named\n")
    report = credential_paths.inventory(root)
    assert not report["complete"], report
    assert not report["findings"], "foreign repository paths must not enter the output"


def test_inventory_genuine_local_positive(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    repo = root / "named"
    repo.mkdir()
    git(repo, "init")
    (repo / "credentials.json").write_text("synthetic fixture")
    git(repo, "add", "credentials.json")
    (root / ".agents").mkdir()
    (root / ".agents/repos.yaml").write_text("repos:\n  - name: named\n")
    report = credential_paths.inventory(root)
    assert report["complete"], report
    assert report["findings"] == [{"repo": "named", "path": "credentials.json"}]


def test_inventory_refuses_other_repository_alias_inside_workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    other = root / "other"
    other.mkdir()
    git(other, "init")
    (other / "other-credentials.json").write_text("synthetic")
    git(other, "add", "other-credentials.json")
    declared = root / "named"
    declared.mkdir()
    (declared / ".git").write_text("gitdir: " + str(other / ".git") + "\n")
    (root / ".agents").mkdir()
    (root / ".agents/repos.yaml").write_text("repos:\n  - name: named\n")
    result = credential_paths.inventory(root)
    assert not result["complete"]
    assert not result["findings"]


def test_inventory_linked_local_worktree_positive(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    other = root / "other"
    other.mkdir()
    git(other, "init")
    (other / "credentials.json").write_text("synthetic")
    git(other, "add", "credentials.json")
    git(
        other,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    git(other, "worktree", "add", str(root / "named"), "-b", "fixture")
    (root / ".agents").mkdir()
    (root / ".agents/repos.yaml").write_text("repos:\n  - name: named\n")
    result = credential_paths.inventory(root)
    assert result["complete"], result
    assert result["findings"] == [{"repo": "named", "path": "credentials.json"}]


@pytest.mark.parametrize(
    "kind",
    ["symlink", "hardlink", "partial", "zero-write", "write-error", "parent-alias"],
)
def test_append_unsafe_or_incomplete_refuses(tmp_path, monkeypatch, kind):
    state = tmp_path / "state"
    state.mkdir()
    p = state / "history.jsonl"
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"original\n")
    monkeypatch.setenv("RITUAL_STATE_DIR", str(state))
    if kind == "symlink":
        p.symlink_to(sentinel)
    elif kind == "hardlink":
        os.link(sentinel, p)
    elif kind == "partial":
        p.write_bytes(b'{"interrupted":')
    elif kind == "parent-alias":
        link = tmp_path / "alias"
        link.symlink_to(state, target_is_directory=True)
        monkeypatch.setenv("RITUAL_STATE_DIR", str(link))
    elif kind == "zero-write":
        monkeypatch.setattr(ritual_state.os, "write", lambda *a: 0)
    else:

        def fail(*a):
            raise OSError("synthetic write failure")

        monkeypatch.setattr(ritual_state.os, "write", fail)
    with pytest.raises((OSError, SystemExit)):
        ritual_state.append_record(
            {"date": "2026-09-26", "direction": "day-end", "workspace": "fixture"}
        )
    assert sentinel.read_bytes() == b"original\n"
    if kind == "partial":
        assert p.read_bytes() == b'{"interrupted":'


def test_concurrent_short_writers_keep_whole_records(tmp_path):
    state = tmp_path / "state"
    program = """import sys,os
sys.path.insert(0,sys.argv[1])
import ritual_state  # noqa: E402 - register sibling script path first
real=ritual_state.os.write
ritual_state.os.write=lambda fd,data:real(fd,data[:3])
for n in range(10):ritual_state.append_record({'date':'2026-09-26','direction':'day-end','workspace':sys.argv[2],'number':n})
"""
    children = []
    try:
        for seat in range(4):
            children.append(
                subprocess.Popen(
                    [sys.executable, "-B", "-c", program, str(D), str(seat)],
                    env=dict(os.environ, RITUAL_STATE_DIR=str(state)),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
            )
        for child in children:
            stdout, stderr = child.communicate(timeout=10)
            assert child.returncode == 0, (stdout, stderr)
        rows = [
            json.loads(line)
            for line in (state / "history.jsonl").read_bytes().splitlines()
        ]
        assert len(rows) == 40
        assert {(row["workspace"], row["number"]) for row in rows} == {
            (str(seat), n) for seat in range(4) for n in range(10)
        }
    finally:
        for child in children:
            if child.poll() is None:
                import signal

                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
            child.stdout.close()
            child.stderr.close()


def test_git_index_change_is_not_attributed_to_prior_source(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    repo = root / "named"
    repo.mkdir()
    git(repo, "init")
    (repo / "credentials.json").write_text("synthetic")
    git(repo, "add", "credentials.json")
    (root / ".agents").mkdir()
    (root / ".agents/repos.yaml").write_text("repos:\n  - name: named\n")
    real = credential_paths._git_names

    def change(repo, remaining):
        raw = real(repo, remaining)
        index = repo / ".git/index"
        index.write_bytes(index.read_bytes() + b"synthetic damage")
        return raw

    monkeypatch.setattr(credential_paths, "_git_names", change)
    report = credential_paths.inventory(root)
    assert not report["complete"] and not report["findings"]


def test_missing_parent_under_alias_is_refused_before_directory_creation(
    tmp_path, monkeypatch
):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(foreign, target_is_directory=True)
    monkeypatch.setenv("RITUAL_STATE_DIR", str(alias / "new/state"))
    with pytest.raises(OSError):
        ritual_state.append_record(
            {"date": "2026-09-26", "direction": "day-end", "workspace": "fixture"}
        )
    assert not (foreign / "new").exists()

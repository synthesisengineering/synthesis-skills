from pathlib import Path
import json
import os
import sys
import subprocess
import pytest

R = Path(__file__).resolve().parents[3]
P = R / "skills/synthesis-project-management/scripts"
C = R / "skills/synthesis-context-lifecycle/scripts"
sys.path[:0] = [str(P), str(C)]
import project_state as state  # noqa: E402 - candidate sibling modules require source path first
from test_project_state import init_repo, commit_version, run  # noqa: E402 - candidate sibling modules require source path first


@pytest.mark.parametrize("held_project", ["alpha", "beta"])
def test_fast_forward_cannot_change_managed_reader_generation(
    tmp_path, monkeypatch, held_project
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo, project = init_repo(tmp_path)
    beta = repo / "projects/beta"
    beta.mkdir()
    (beta / "CONTEXT.md").write_text("beta old\n")
    run("git", "add", "projects/beta", cwd=repo)
    run("git", "commit", "-m", "Fixture beta", cwd=repo)
    run("git", "push", "origin", "main", cwd=repo)
    peer = tmp_path / "peer"
    run("git", "clone", str(tmp_path / "remote.git"), str(peer), cwd=tmp_path)
    for key, value in [
        ("user.email", "fixture@example.invalid"),
        ("user.name", "Fixture"),
        ("core.hooksPath", str(tmp_path / "fixture-hooks")),
    ]:
        run("git", "config", key, value, cwd=peer)
    newer = commit_version(peer, peer / "projects/alpha", "2.0.0")
    (peer / "projects/beta/CONTEXT.md").write_text("beta new\n")
    run("git", "add", "projects/beta", cwd=peer)
    run("git", "commit", "-m", "Fixture beta advance", cwd=peer)
    run("git", "push", "origin", "main", cwd=peer)
    held = repo / "projects" / held_project
    code = "import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import record_transaction as rt\np=Path(sys.argv[2])\nwith rt.managed(p):\n before=(p/'CONTEXT.md').read_text();print('ready',flush=True);sys.stdin.readline();print(json.dumps({'before':before,'after':(p/'CONTEXT.md').read_text()}),flush=True)\n"
    child = subprocess.Popen(
        [sys.executable, "-B", "-c", code, str(C), str(held)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        report = state.resolve_project(
            "alpha",
            repo / "projects/index.yaml",
            fetch=True,
            fast_forward_canonical=True,
        )
        output, error = child.communicate("\n", timeout=10)
        assert child.returncode == 0, error
        observed = json.loads(output)
        assert observed["before"] == observed["after"], (
            "managed reader observed a fast-forwarded generation during its shared lock"
        )
        assert report.status == "UNKNOWN" and any(
            "bounded lock" in x for x in report.issues
        )
        fresh = state.resolve_project(
            "alpha",
            repo / "projects/index.yaml",
            fetch=True,
            fast_forward_canonical=True,
        )
        assert fresh.status == "PASS" and fresh.selected_head == newer
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_resolver_invalid_locator_is_unknown_not_uncaught(tmp_path):
    index = tmp_path / "projects/index.yaml"
    index.parent.mkdir()
    index.write_text("- id: alpha\n")
    result = state.resolve_project("alpha", index, fetch=False)
    assert result.status == "UNKNOWN" and result.selected_path is None

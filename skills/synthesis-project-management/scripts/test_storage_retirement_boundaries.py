import os
from pathlib import Path
import sys
import pytest

SOURCE = Path(__file__).resolve().parents[3]
PM = SOURCE / "skills/synthesis-project-management/scripts"
sys.path.insert(0, str(PM))
import test_coordination as c
import test_retire_worktree as r
import fleet_doctor as doctor

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for key in ("SYNTHESIS_COORDINATION_SESSION", "SYNTHESIS_CLIENT_SESSION_REF", "CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDECODE", "MUSE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

def test_actual_nested_retirement(tmp_path):
    _, repo = r.build_repo(tmp_path)
    target = repo / ".claude/worktrees/baseline"
    target.parent.mkdir(parents=True)
    r.git(repo, "worktree", "add", "--detach", str(target), "main")
    env = dict(os.environ, SYNTHESIS_HOME=str(tmp_path / "state"))
    import subprocess
    result = subprocess.run([sys.executable, "-B", str(r.SCRIPT), "--repository", str(repo), "--worktree", str(target)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not target.exists()
    intents = list((tmp_path / "state/repo-guard/retired-worktrees").glob("*.json"))
    assert intents
    import json
    assert all(json.loads(p.read_text())["state"] == "completed" for p in intents)

@pytest.mark.parametrize("peer", [False, True])
def test_ambiguous_claim_refuses_before_board_write(tmp_path, peer):
    board = tmp_path / "board.md"
    if peer:
        q = c.claim_args(board, session_id="B", project="foreign", workspace=f"{tmp_path}/other @ main", area=f"{tmp_path}/other/source/**", context_role="none")
        assert c.MODULE.command_claim(q) == 0
    before = board.read_bytes() if board.exists() else None
    q = c.claim_args(board, session_id="A", project="p", workspace=f"{tmp_path}/one @ main", area="projects/p/CONTEXT.md")
    q.workspace.append(f"{tmp_path}/two @ main")
    assert c.MODULE.command_claim(q) != 0
    assert (board.read_bytes() if board.exists() else None) == before

def test_namespace_claim_refuses_before_board_write(tmp_path):
    board = tmp_path / "board.md"
    q = c.claim_args(board, session_id="A", project="p", workspace=f"{tmp_path}/repo @ main", area="repo:source/**", context_role="none")
    assert c.MODULE.command_claim(q) != 0
    assert not board.exists()

def test_bad_repo_does_not_hide_explicit_missing_venv(tmp_path):
    venv = tmp_path / "lost-venv"
    result = doctor.check_storage([tmp_path / "not-a-repo"], venvs=[venv])
    assert not result.ok
    assert str(venv) in result.detail
    assert "missing" in result.detail or "unavailable" in result.detail

def test_absolute_colon_claim_reaches_staged_consumer(tmp_path):
    repo = c.staged_repository(tmp_path)
    (repo / "source:part").mkdir()
    (repo / "source:part/file.py").write_text("x=1\n")
    assert c.git(repo, "add", ".").returncode == 0
    board = tmp_path / "board.md"
    c.claim_staged_repository(board, repo, area=str(repo / "source:part/**"))
    assert c.MODULE.command_check_staged(c.check_staged_args(board, repo)) == 0

def test_relative_claim_stays_bound_after_workspace_addition(tmp_path,monkeypatch):
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF','codex:scope-owner')
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    first=c.staged_repository(a);second=c.staged_repository(b);board=tmp_path/'board.md'
    q=c.claim_args(board,session_id='A',project='p',workspace=f'{first} @ main',area='source/**')
    assert c.MODULE.command_claim(q)==0
    q=c.claim_args(board,session_id='A',project='p',workspace=f'{second} @ main',area='other/**')
    assert c.MODULE.command_claim(q)==0
    row=c.MODULE.rows(board.read_text())[0]
    assert row.claims==[str(first/'source/**'),str(second/'other/**')]
    (second/'source').mkdir();(second/'source/file').write_text('foreign scope')
    assert c.git(second,'add','.').returncode==0
    assert c.MODULE.command_check_staged(c.check_staged_args(board,second))!=0
    assert c.git(second,'rm','--cached','source/file').returncode==0
    (second/'other').mkdir();(second/'other/file').write_text('owned scope')
    assert c.git(second,'add','other/file').returncode==0
    assert c.MODULE.command_check_staged(c.check_staged_args(board,second))==0

def test_legacy_temporary_claim_is_recoverable_but_doctor_reports_exposure(tmp_path):
    board=tmp_path/'board.md'
    q=c.claim_args(board,session_id='A',project='p',workspace=f'{tmp_path} @ main',area=str(tmp_path/'owned/**'))
    assert c.MODULE.command_claim(q)==0
    row=c.MODULE.rows(board.read_text())[0]
    checks=doctor.run_all(board=board,repos=[],machine_id=row.machine)
    storage=next(check for check in checks if check.id=='storage-custody')
    assert not storage.ok and str(tmp_path) in storage.detail
    assert 'claimable for recovery' in storage.detail

def test_release_mutex_never_grants_same_spelled_file_write(tmp_path):
    repo=c.staged_repository(tmp_path);board=tmp_path/'board.md'
    (repo/'release-train:fixture').write_text('not authorized by virtual mutex')
    c.git(repo,'add','.')
    c.claim_staged_repository(board,repo,area='release-train:fixture')
    assert c.MODULE.command_check_staged(c.check_staged_args(board,repo))!=0

def test_narrow_then_new_workspace_does_not_rebind_retained_claim(tmp_path,monkeypatch):
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF','codex:owner-a')
    board=tmp_path/'board.md';a=tmp_path/'a';b=tmp_path/'b'
    q=c.claim_args(board,session_id='A',project='p',workspace=f'{a} @ main',area='source/**')
    assert c.MODULE.command_claim(q)==0
    assert c.MODULE.command_narrow(c.narrow_args(board,session_id='A',workspace=[f'{a} @ main']))==0
    q=c.claim_args(board,session_id='A',project='p',workspace=f'{b} @ main',area='other/**')
    assert c.MODULE.command_claim(q)==0
    row=c.MODULE.rows(board.read_text())[0]
    assert str(a/'source/**') in row.claims
    assert c.MODULE._outside_claim(row,b,['source/file'])==['source/file']
    assert c.MODULE._outside_claim(row,b,['other/file'])==[]

def test_succession_binds_each_prior_workspace_before_merge(tmp_path,monkeypatch):
    board=tmp_path/'board.md';a=tmp_path/'a';b=tmp_path/'b'
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF','codex:predecessor')
    assert c.MODULE.command_claim(c.claim_args(board,session_id='A',project='pa',workspace=f'{a} @ main',area='source/**'))==0
    prior=c.MODULE.rows(board.read_text())[0];c._park_row(board,prior.compact_id)
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF','codex:heir')
    assert c.MODULE.command_claim(c.claim_args(board,session_id='B',project='pb',workspace=f'{b} @ main',area='other/**'))==0
    assert c.MODULE.command_succeed(c.succeed_args(board,from_id='A',session_id='B'))==0
    row=next(r for r in c.MODULE.rows(board.read_text()) if r.legacy_id=='B')
    assert row.claims==[str(b/'other/**'),str(a/'source/**')]
    assert c.MODULE._outside_claim(row,b,['source/file'])==['source/file']
    assert c.MODULE._outside_claim(row,a,['source/file'])==[]

"""Real Git metadata batching controls; wall-clock acceptance is separate."""
from pathlib import Path
import subprocess
import pytest
import project_state as state
from test_project_state import init_repo,commit_version,run

def traced(monkeypatch):
 calls=[];original=state._run
 def record(repo,*args,**kw):calls.append((str(repo),args,kw));return original(repo,*args,**kw)
 monkeypatch.setattr(state,'_run',record);return calls

def test_distinct_repository_heads_batch_project_trees(tmp_path,monkeypatch):
 repo,project=init_repo(tmp_path)
 for n in range(12):
  (repo/'unrelated.txt').write_text(str(n));run('git','add','unrelated.txt',cwd=repo);run('git','commit','-m','fixture',cwd=repo);run('git','branch',f'fixture-{n}',cwd=repo)
 calls=traced(monkeypatch);report=state.resolve_project('alpha',repo/'projects/index.yaml',fetch=False)
 assert report.status=='PASS'
 assert len([x for x in report.candidates if x.source=='ref'])==14
 per_tree=[x for x in calls if x[1][0]=='rev-parse'and':projects/alpha'in' '.join(x[1])]
 batches=[x for x in calls if x[1][0]=='cat-file']
 assert not per_tree and len(batches)==1,(len(per_tree),len(batches))
 assert len({x.project_tree for x in report.candidates if x.source in{'ref','canonical','worktree'}})==1
 assert len([x for x in calls if x[1][0]=='log'])==13

def test_batch_matches_independent_single_queries_and_missing_tree(tmp_path):
 repo,project=init_repo(tmp_path);first=run('git','rev-parse','HEAD',cwd=repo);second=commit_version(repo,project,'2.0.0')
 for relative in ['projects/alpha','projects/not-present']:
  got=state._trees_at(repo,[first,second,first],relative)
  expected={h:state._tree_at(repo,h,relative)for h in [first,second]}
  assert got==expected

@pytest.mark.parametrize('damage',['missing','extra','malformed','wrong-missing'])
def test_batch_refuses_truncated_or_malformed_response(tmp_path,monkeypatch,damage):
 repo,project=init_repo(tmp_path);head=run('git','rev-parse','HEAD',cwd=repo);original=state._run
 def broken(repo,*args,**kw):
  r=original(repo,*args,**kw)
  if args[0]=='cat-file':
   raw={'missing':'','extra':r.stdout+r.stdout,'malformed':'not-an-object\n','wrong-missing':'foreign:projects/alpha missing\n'}[damage]
   return subprocess.CompletedProcess(r.args,0,raw,'')
  return r
 monkeypatch.setattr(state,'_run',broken)
 with pytest.raises(state.ProjectStateError):state._trees_at(repo,[head],'projects/alpha')

@pytest.mark.parametrize('relative',['projects/white space','projects/new\nline'])
def test_legal_git_path_queries_keep_literal_semantics(tmp_path,relative):
 repo,project=init_repo(tmp_path);d=repo/relative;d.mkdir();(d/'CONTEXT.md').write_text('literal');run('git','add','.',cwd=repo);run('git','commit','-m','fixture',cwd=repo);head=run('git','rev-parse','HEAD',cwd=repo)
 assert state._trees_at(repo,[head],relative)=={head:state._tree_at(repo,head,relative)}

def test_prefix_resolved_once_and_refreshed_before_acceptance(tmp_path,monkeypatch):
 repo,project=init_repo(tmp_path);calls=0;original=Path.resolve
 def resolve(self,*args,**kw):
  nonlocal calls
  if self==project:calls+=1
  return original(self,*args,**kw)
 monkeypatch.setattr(Path,'resolve',resolve)
 # This asserts bounded prefix resolution while every manifest path remains
 # resolved independently. Production profiling identified this repetition.
 original_inventory=state._manifest_inventory
 manifests=[{'_kind':'receipt','session_id':'outside','paths':[str(repo/'outside'/str(i))for i in range(100)]}]
 monkeypatch.setattr(state,'_manifest_inventory',lambda *_:(manifests,[]))
 report=state.resolve_project('alpha',repo/'projects/index.yaml',fetch=False)
 assert report.status=='PASS';assert calls<20,calls


def test_batch_honors_existing_replacement_reference(tmp_path):
    repo, project = init_repo(tmp_path)
    first = run('git', 'rev-parse', 'HEAD', cwd=repo)
    second = commit_version(repo, project, '2.0.0')
    run('git', 'replace', first, second, cwd=repo)
    assert state._trees_at(repo, [first, second], 'projects/alpha') == {
        head: state._tree_at(repo, head, 'projects/alpha')
        for head in (first, second)
    }


def test_canonical_project_target_movement_is_unresolved(tmp_path, monkeypatch):
    import shutil
    repo, project = init_repo(tmp_path)
    replacement = tmp_path / 'replacement-project'
    shutil.copytree(project, replacement)
    original = state._run
    moved = False

    def race(path, *args, **kwargs):
        nonlocal moved
        result = original(path, *args, **kwargs)
        if args[0] == 'log' and not moved:
            moved = True
            project.rename(tmp_path / 'retained-project')
            project.symlink_to(replacement, target_is_directory=True)
        return result

    monkeypatch.setattr(state, '_run', race)
    report = state.resolve_project('alpha', repo / 'projects/index.yaml', fetch=False)
    assert moved
    assert report.status == 'UNKNOWN'
    assert report.selected_path is None
    assert any('changed during' in issue for issue in report.issues)
    assert (tmp_path / 'retained-project' / 'CONTEXT.md').is_file()


def test_object_batch_has_a_finite_per_process_bound(monkeypatch, tmp_path):
    calls = []
    heads = [f'{n:040x}' for n in range(600)]

    def controlled_git(repo, *args, **kwargs):
        assert args == ('cat-file', '--batch-check=%(objectname)')
        queries = kwargs['input_text'].splitlines()
        calls.append(queries)
        return subprocess.CompletedProcess(args, 0,
            ''.join('a' * 40 + '\n' for _ in queries), '')

    monkeypatch.setattr(state, '_run', controlled_git)
    result = state._trees_at(tmp_path, heads, 'projects/alpha')
    assert [len(batch) for batch in calls] == [256, 256, 88]
    assert set(result) == set(heads)
    assert all(value == 'a' * 40 for value in result.values())


def test_bounded_history_pool_preserves_each_real_git_result(tmp_path):
    repo, project = init_repo(tmp_path)
    first = run('git', 'rev-parse', 'HEAD', cwd=repo)
    second = commit_version(repo, project, '2.0.0')
    (repo / 'other.txt').write_text('unrelated')
    run('git', 'add', '.', cwd=repo)
    run('git', 'commit', '-m', 'fixture', cwd=repo)
    third = run('git', 'rev-parse', 'HEAD', cwd=repo)
    trees = state._trees_at(repo, [first, second, third], 'projects/alpha')
    got = state._project_metadata_at(repo, trees, 'projects/alpha')
    expected = {}
    for head in trees:
        value = state._run(repo, 'log', '-1', '--format=%H%x00%cI', head,
                           '--', 'projects/alpha').stdout.strip()
        changed, _, timestamp = value.partition('\0')
        expected[head] = (changed or None, trees[head], timestamp)
    assert got == expected
    assert got[second] == got[third]
    assert got[first] != got[second]


def test_history_pool_limits_two_children_and_joins_before_return(tmp_path, monkeypatch):
    import threading
    import time
    lock = threading.Lock()
    rendezvous = threading.Barrier(2)
    active = 0
    maximum = 0
    completed = []
    heads = {f'{n:040x}': 'a' * 40 for n in range(6)}

    def controlled_git(repo, *args, **kwargs):
        nonlocal active, maximum
        assert args[:3] == ('log', '-1', '--format=%H%x00%cI')
        with lock:
            active += 1
            maximum = max(maximum, active)
        rendezvous.wait(timeout=5)
        time.sleep(0.01)
        with lock:
            active -= 1
            completed.append(args[3])
        return subprocess.CompletedProcess(args, 0,
            args[3] + '\0' + '2026-09-25T00:00:00+00:00\n', '')

    monkeypatch.setattr(state, '_run', controlled_git)
    result = state._project_metadata_at(tmp_path, heads, 'projects/alpha')
    assert active == 0
    assert maximum == 2
    assert set(completed) == set(heads) == set(result)

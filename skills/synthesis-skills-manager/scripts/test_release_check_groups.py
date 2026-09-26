"""Causal controls for exact grouped release collection and finite execution."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
import release_check_groups as groups


def ids():
    return [groups.AP+'/test_'+name+'.py::test_one' for name in
            ('run_state','native_codex','evaluation','brand_new_surface')]


def test_complete_nonoverlapping_inventory_includes_new_tests():
    result=groups.partition(ids())
    assert [result[g] for g in groups.GROUPS] == [[n] for n in ids()]
    assert sorted(sum(result.values(),[])) == sorted(ids())


@pytest.mark.parametrize('bad',[[],['outside.py::x'],ids()+ids()[:1]])
def test_invalid_collection_refused(bad):
    with pytest.raises(ValueError):groups.partition(bad)


def test_overlapping_rules_refused(monkeypatch):
    monkeypatch.setattr(groups,'NATIVE_PREFIXES',groups.STATE_PREFIXES)
    with pytest.raises(ValueError,match='overlapping'):groups.partition(ids())


def plugin(tmp_path):
    p=groups.InventoryPlugin('core',tmp_path/'report.json')
    p.full=ids();p.selected=[ids()[-1]]
    return p


def phase(p,node,when='call',outcome='passed'):
    p.pytest_runtest_logreport(SimpleNamespace(nodeid=node,when=when,outcome=outcome,duration=.1))


def finish(p):
    session=SimpleNamespace(exitstatus=0)
    p.pytest_sessionfinish(session,0)
    return session


def test_positive_execution_covers_all_phases(tmp_path):
    p=plugin(tmp_path)
    for when in ('setup','call','teardown'):phase(p,p.selected[0],when)
    assert finish(p).exitstatus==0
    assert json.loads(p.report.read_text())['errors']==[]


@pytest.mark.parametrize('defect',['omitted','duplicate','extra','skipped','failed','teardown'])
def test_execution_counterexamples_remain_failure(tmp_path,defect):
    p=plugin(tmp_path);node=p.selected[0]
    for when in ('setup','call','teardown'):
        if defect=='omitted' and when=='call':continue
        phase(p,node,when,('skipped' if defect=='skipped' else 'failed') if when=='call' and defect in ('failed','skipped') else 'failed' if defect=='teardown' and when=='teardown' else 'passed')
    if defect=='duplicate':phase(p,node)
    if defect=='extra':phase(p,'extra')
    assert finish(p).exitstatus==1


def test_source_hash_detects_mutation(tmp_path):
    (tmp_path/'source.py').write_text('one')
    before=groups.source_digest(tmp_path)
    (tmp_path/'source.py').write_text('two')
    assert groups.source_digest(tmp_path)!=before


@pytest.mark.parametrize('kind',['symlink','fifo','directory-link'])
def test_source_refuses_special_members_without_opening_them(tmp_path,kind):
    p=tmp_path/'member'
    if kind=='fifo':os.mkfifo(p)
    elif kind=='directory-link':p.symlink_to(tmp_path,target_is_directory=True)
    else:p.symlink_to('/no-such-fixture')
    with pytest.raises((ValueError,OSError)):groups.source_digest(tmp_path)


def test_source_size_limit_is_fail_closed(tmp_path,monkeypatch):
    (tmp_path/'source').write_bytes(b'xx');monkeypatch.setattr(groups,'MAX_SOURCE_BYTES',1)
    with pytest.raises(ValueError,match='ceiling'):groups.source_digest(tmp_path)


def test_bounded_owner_timeout_and_pipe_closure(tmp_path):
    for script in ('import time;time.sleep(20)', 'import os,time;os.close(1);os.close(2);time.sleep(20)'):
        start=time.monotonic();r=groups.bounded_run([sys.executable,'-c',script],tmp_path,.15)
        assert r.returncode!=0 and time.monotonic()-start<4


def test_bounded_owner_output_limit(tmp_path,monkeypatch):
    monkeypatch.setattr(groups,'OUTPUT_BYTES',1024)
    r=groups.bounded_run([sys.executable,'-c',"print('x'*2000)"],tmp_path,1)
    assert r.returncode!=0 and 'byte ceiling' in r.stdout and len(r.stdout)<1200


def test_bounded_owner_preserves_required_environment(tmp_path):
    r=groups.bounded_run([sys.executable,'-c',"import os;print(os.environ['SYNTHESIS_TEST_CHROMIUM'])"],tmp_path,2,{'SYNTHESIS_TEST_CHROMIUM':'exact-chromium'})
    assert r.returncode==0 and r.stdout.strip()=='exact-chromium'


def test_bounded_owner_reaps_group_descendant(tmp_path):
    marker=tmp_path/'child.json'
    script="import os,signal,time,json\npid=os.fork()\nif pid==0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)\nelse:\n open('child.json','w').write(json.dumps({'pid':pid,'group':os.getpgrp()}));time.sleep(30)\n"
    r=groups.bounded_run([sys.executable,'-c',script],tmp_path,.25)
    assert r.returncode!=0
    info=json.loads(marker.read_text())
    # Some Unix init implementations retain a killed orphan briefly as a zombie.
    status=subprocess.run(['ps','-o','stat=','-p',str(info['pid'])],capture_output=True,text=True,timeout=2)
    assert not status.stdout.strip() or status.stdout.strip().startswith('Z')


def test_nonzero_check_exit_remains_failure(tmp_path):
    assert groups.bounded_run([sys.executable,'-c','raise SystemExit(7)'],tmp_path,2).returncode==7


def test_release_and_ci_require_each_group():
    import ast,yaml
    root=Path(__file__).resolve().parents[3]
    tree=ast.parse((root/'skills/synthesis-skills-manager/scripts/release.py').read_text())
    checks=dict(ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.AnnAssign) and getattr(n.target,'id','')=='REQUIRED_CHECKS')))
    ci=yaml.safe_load((root/'.github/workflows/validate.yml').read_text())
    commands=[s.get('run','') for s in ci['jobs']['conformance']['steps']]
    for group in groups.GROUPS:
        command=['python3','skills/synthesis-skills-manager/scripts/release_check_groups.py','--group',group]
        assert checks['pytest.autopilot.'+group]==command
        assert 'python '+' '.join(command[1:]) in commands
    assert groups.GROUP_SECONDS<groups.CHECK_SECONDS==900


def synthetic_root(tmp_path):
    root=tmp_path/'source';directory=root/groups.AP;directory.mkdir(parents=True)
    for name in ('run_state','native_codex','evaluation','brand_new_surface'):
        (directory/('test_'+name+'.py')).write_text('def test_one():\n    assert True\n')
    return root


def test_actual_pytest_groups_run_every_parameter_and_preserve_full_inventory(tmp_path,monkeypatch):
    root=synthetic_root(tmp_path)
    (root/groups.AP/'test_brand_new_surface.py').write_text('import pytest\n@pytest.mark.parametrize("x",[1,2,3])\ndef test_one(x):\n    assert x>0\n')
    monkeypatch.setenv('PYTEST_ADDOPTS','-k never-matches')
    observed=[];inventories=[]
    for group in groups.GROUPS:
        code,payload=groups.run_group(root,group)
        assert code==0,payload
        observed.extend(payload['selected']);inventories.append(payload['inventory'])
    assert len(observed)==6 and len(set(observed))==6
    assert all(sorted(i)==sorted(observed) for i in inventories)


@pytest.mark.parametrize('defect',['syntax','mutation','failure','skip'])
def test_actual_pytest_refusal_and_mutation_are_failures(tmp_path,defect):
    root=synthetic_root(tmp_path);file=root/groups.AP/'test_brand_new_surface.py'
    file.write_text({'syntax':'not legal python !',
        'mutation':'from pathlib import Path\ndef test_one():\n    Path("unexpected-source").write_text("changed")\n',
        'failure':'def test_one():\n    assert False\n',
        'skip':'import pytest\ndef test_one():\n    pytest.skip("cannot execute")\n'}[defect])
    code,_=groups.run_group(root,'core')
    assert code!=0


def test_release_owner_refuses_changed_source_before_acceptance(tmp_path,monkeypatch):
    import release
    (tmp_path/'source').write_text('original')
    monkeypatch.setattr(release,'REQUIRED_CHECKS',(('fixture',[sys.executable,'-c','pass']),))
    def mutation(*args,**kwargs):
        (tmp_path/'source').write_text('changed')
        return subprocess.CompletedProcess([],0,'ok','')
    monkeypatch.setattr(release,'bounded_run',mutation)
    monkeypatch.setattr(release,'consume_acceptance',lambda *a:pytest.fail('mutated source consumed acceptance'))
    result=release.Result()
    assert release.run_required_checks(tmp_path,result,False) is None
    assert not result.steps[-1].ok and 'source changed' in result.steps[-1].detail


def test_interruption_returns_failure_and_restores_signal_handlers(tmp_path):
    old=signal.getsignal(signal.SIGTERM)
    script='import os,signal,time\nos.kill(os.getppid(),signal.SIGTERM)\ntime.sleep(30)\n'
    start=time.monotonic();result=groups.bounded_run([sys.executable,'-c',script],tmp_path,2)
    assert result.returncode!=0 and 'interrupted' in result.stdout
    assert time.monotonic()-start<4 and signal.getsignal(signal.SIGTERM)==old


def test_unreadable_directory_cannot_disappear_from_source_inventory(tmp_path,monkeypatch):
    source=tmp_path/'subdirectory';source.mkdir();(source/'guard.py').write_text('required')
    original=groups.os.scandir
    def unreadable(path):
        if isinstance(path,int) and os.fstat(path).st_ino==source.stat().st_ino:
            raise PermissionError('synthetic unreadable required directory')
        return original(path)
    monkeypatch.setattr(groups.os,'scandir',unreadable)
    with pytest.raises(PermissionError):groups.source_digest(tmp_path)


def test_executable_mode_is_part_of_source_input(tmp_path):
    source=tmp_path/'launch';source.write_text('same bytes');source.chmod(0o600)
    before=groups.source_digest(tmp_path);source.chmod(0o700)
    assert groups.source_digest(tmp_path)!=before


def test_pathname_replacement_while_descriptor_is_open_refused(tmp_path,monkeypatch):
    source=tmp_path/'guard.py';source.write_text('original bytes')
    original=groups.os.read;changed=False
    def replacement(fd,size):
        nonlocal changed
        if not changed:
            changed=True;source.rename(tmp_path/'retained-original')
            source.write_text('replacement bytes')
        return original(fd,size)
    monkeypatch.setattr(groups.os,'read',replacement)
    with pytest.raises(ValueError,match='changed'):groups.source_digest(tmp_path)


def test_directory_replaced_by_symlink_cannot_redirect_scan(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir();directory=root/'sub';directory.mkdir()
    (directory/'guard.py').write_text('required')
    outside=tmp_path/'outside';outside.mkdir();(outside/'different').write_text('foreign')
    original=groups.os.open;swapped=False
    def replacement(path,flags,*args,**kwargs):
        nonlocal swapped
        if path=='sub' and not swapped:
            swapped=True;directory.rename(root/'retained-sub');directory.symlink_to(outside,target_is_directory=True)
        return original(path,flags,*args,**kwargs)
    monkeypatch.setattr(groups.os,'open',replacement)
    with pytest.raises((OSError,ValueError)):groups.source_digest(root)


@pytest.mark.parametrize('injection',['selection','plugin'])
def test_common_owner_rejects_inherited_pytest_deselection(tmp_path,monkeypatch,injection):
    (tmp_path/'test_required.py').write_text('def test_passing():\n    assert True\ndef test_required_failing():\n    assert False\n')
    (tmp_path/'hostile_plugin.py').write_text('def pytest_collection_modifyitems(items):\n    items[:]=[item for item in items if "passing" in item.nodeid]\n')
    monkeypatch.setenv('PYTHONPATH',str(tmp_path))
    if injection=='selection':monkeypatch.setenv('PYTEST_ADDOPTS','-k passing')
    else:monkeypatch.setenv('PYTEST_PLUGINS','hostile_plugin')
    command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider']
    control=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=5)
    assert control.returncode==0,control.stdout+control.stderr
    guarded=groups.bounded_run(command,tmp_path,5)
    assert guarded.returncode==1 and 'test_required_failing' in guarded.stdout


def test_common_owner_ignores_poisoned_same_header_bytecode(tmp_path,monkeypatch):
    import importlib.util,py_compile
    source=tmp_path/'required_module.py';source.write_text("VALUE = 'wrong'\n");stamp=source.stat()
    # The plain control child explicitly uses the ordinary cache, even when
    # this test itself is running inside a required owner's private prefix.
    with monkeypatch.context() as ordinary_cache:
        ordinary_cache.setattr(sys,'pycache_prefix',None)
        cache=Path(importlib.util.cache_from_source(str(source)))
    py_compile.compile(str(source),cfile=str(cache),doraise=True,invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    source.write_text("VALUE = 'right'\n");os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    command=[sys.executable,'-c','import required_module;print(required_module.VALUE)']
    plain=dict(os.environ);plain.pop('PYTHONPYCACHEPREFIX',None)
    control=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=5,env=plain)
    assert control.returncode==0 and control.stdout.strip()=='wrong'
    monkeypatch.delenv('PYTHONPYCACHEPREFIX',raising=False)
    guarded=groups.bounded_run(command,tmp_path,5)
    assert guarded.returncode==0 and guarded.stdout.strip()=='right'
    assert cache.exists(),'original untrusted cache must remain untouched'


def test_common_owner_uses_fresh_cache_each_time_and_preserves_dependency_env(tmp_path,monkeypatch):
    monkeypatch.setenv('SYNTHESIS_TEST_CHROMIUM','verified-browser')
    monkeypatch.setenv('PYTHONPATH',str(tmp_path))
    paths=[]
    for _ in range(2):
        result=groups.bounded_run([sys.executable,'-c',"import os,json;print(json.dumps({k:os.environ.get(k) for k in ('PYTHONPYCACHEPREFIX','PYTHONDONTWRITEBYTECODE','PYTHONPATH','SYNTHESIS_TEST_CHROMIUM','PYTEST_DISABLE_PLUGIN_AUTOLOAD')}))"],tmp_path,5)
        assert result.returncode==0,result.stdout
        env=json.loads(result.stdout)
        assert env['PYTHONPATH']==str(tmp_path) and env['SYNTHESIS_TEST_CHROMIUM']=='verified-browser'
        assert env['PYTHONDONTWRITEBYTECODE']=='1' and env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']=='1'
        paths.append(env['PYTHONPYCACHEPREFIX'])
    assert paths[0]!=paths[1]
    assert all(not Path(p).exists() for p in paths)

"""Real processes prove overlap, admission limits and cleanup under failure."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest
import release_check_groups as groups
import release


def test_real_checks_overlap_and_keep_order(tmp_path):
    def worker(index,cancel):
        command=[sys.executable,'-c',f'import time;print({index},flush=True);time.sleep(.4)']
        return groups.bounded_run(command,tmp_path,timeout=5,env=dict(os.environ,TMPDIR=str(tmp_path)),cancel_event=cancel)
    start=time.monotonic();results=groups.bounded_map(range(4),worker,workers=4)
    elapsed=time.monotonic()-start
    assert all(r.returncode==0 for r in results)
    assert [r.stdout.strip() for r in results]==['0','1','2','3']
    assert elapsed<1.6


@pytest.mark.parametrize("close_output", [False, True])
def test_failure_stops_admission_and_drains_real_running_check(tmp_path, close_output):
    marker=tmp_path/'running.pid';admitted=[]
    def worker(index,cancel):
        admitted.append(index)
        if index==0:
            script=f'import pathlib,time; p=pathlib.Path({str(marker)!r}); end=time.monotonic()+3\nwhile not p.exists() and time.monotonic()<end: time.sleep(.01)\nprint("original-failure",flush=True);raise SystemExit(7)'
        else:
            script=f'import os,pathlib,time;pathlib.Path({str(marker)!r}).write_text(str(os.getpid()));print("partial-running",flush=True);{('os.close(1);os.close(2);' if close_output else '')}time.sleep(20)'
        return groups.bounded_run([sys.executable,'-c',script],tmp_path,timeout=5,env=dict(os.environ,TMPDIR=str(tmp_path)),cancel_event=cancel)
    started=time.monotonic()
    results=groups.bounded_map(range(8),worker,workers=2,stop_when=lambda r:r.returncode!=0)
    assert time.monotonic()-started<3
    assert sorted(admitted)==[0,1] and all(r is None for r in results[2:])
    assert results[0].returncode==7 and 'original-failure' in results[0].stdout
    assert results[1].returncode!=0 and 'partial-running' in results[1].stdout
    pid=int(marker.read_text())
    with pytest.raises(ProcessLookupError):os.kill(pid,0)
    os.kill(os.getpid(),0)


def test_source_change_stops_before_acceptance(tmp_path,monkeypatch):
    monkeypatch.setattr(release,'REQUIRED_CHECKS',[('first',['unused'])])
    versions=iter(['before','changed'])
    monkeypatch.setattr(release,'source_digest',lambda _: next(versions))
    monkeypatch.setattr(release,'fixture_root',lambda _:tmp_path)
    calls=[];monkeypatch.setattr(release,'consume_acceptance',lambda *a:calls.append(a))
    result=release.Result()
    assert release.run_required_checks(tmp_path,result,False) is None and not calls
    assert result.failed


@pytest.mark.parametrize('workers',[0,5,True])
def test_invalid_concurrency_refused_before_work(workers):
    calls=[]
    with pytest.raises(ValueError):groups.bounded_map([1],lambda *a:calls.append(a),workers=workers)
    assert calls==[]


def test_exclusive_check_drains_previous_workers_before_execution(tmp_path):
    def worker(index, cancel):
        script = ("import time,json,pathlib; begin=time.monotonic(); time.sleep(.15); "
                  "pathlib.Path(" + repr(str(tmp_path / (str(index) + '.json')))
                  + ").write_text(json.dumps([begin,time.monotonic()]))")
        return groups.bounded_run([sys.executable, '-c', script], tmp_path, timeout=5,
                                  env=dict(os.environ, TMPDIR=str(tmp_path)), cancel_event=cancel)
    results = groups.bounded_map(range(5), worker, workers=2, exclusive_when=lambda i: i == 2)
    assert all(r.returncode == 0 for r in results)
    import json
    intervals = [json.loads((tmp_path / (str(i) + '.json')).read_text()) for i in range(5)]
    assert max(intervals[i][1] for i in (0, 1)) <= intervals[2][0]
    assert intervals[2][1] <= min(intervals[i][0] for i in (3, 4))
    assert max(intervals[i][0] for i in (0, 1)) < min(intervals[i][1] for i in (0, 1))
    assert max(intervals[i][0] for i in (3, 4)) < min(intervals[i][1] for i in (3, 4))

# SPDX-License-Identifier: Apache-2.0
"""Run Python under the operating system's sandbox: read-only roots, one writable scratch
directory, no network, and CPU, file-size and descriptor limits.

macOS uses `sandbox-exec`; Linux uses bubblewrap (`bwrap`). There is no unsandboxed fallback:
when neither is usable, the caller refuses. Moved unchanged in behaviour from the old autopilot
engine's `evaluation_artifacts.py` (lines 201-289), whose only real consumer was the local
messaging reader (v5 code evaluation, autopilot row G: KEEP).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

MAX_BYTES = 1024 * 1024


def _safe(root, name):
    root = Path(root).resolve(strict=True)
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Artifact escapes worker boundary')
    cursor = root
    for part in Path(name).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError('Artifact crosses a symlink')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Artifact escapes physical worker boundary')
    return path


def _read(root, name):
    path = _safe(root, name)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Missing or oversized artifact: ' + name)
    return path.read_bytes()


def _sandbox_command(root, scratch, script, argv):
    python = Path(sys.executable).resolve()
    if platform.system() == 'Darwin' and Path('/usr/bin/sandbox-exec').is_file():
        read_roots = {str(root), str(scratch), sys.base_prefix, '/System/Library', '/usr/lib', '/usr/share/zoneinfo', '/Library/Apple/System/Library'}
        reads = ' '.join('(subpath ' + json.dumps(path) + ')' for path in sorted(read_roots))
        # macOS realpath traverses ancestor directories before the permitted
        # runtime subtree. Directory literals expose no neighboring file data.
        ancestors = {str(parent) for path in read_roots for parent in Path(path).parents}
        traversals = ' '.join('(literal ' + json.dumps(path) + ')' for path in sorted(ancestors))
        executables = {str(python)}
        framework_python = Path(sys.base_prefix)/'Resources/Python.app/Contents/MacOS/Python'
        if framework_python.is_file():
            executables.add(str(framework_python.resolve()))
        executable_rules = ' '.join('(literal ' + json.dumps(path) + ')' for path in sorted(executables))
        policy = '(version 1)(deny default)(allow process-exec ' + executable_rules + ')(allow sysctl-read)(allow process-info*)(allow signal (target self))(allow file-read* ' + reads + ' ' + traversals + ' (literal "/dev/null") (literal "/dev/urandom"))(allow file-write* (subpath ' + json.dumps(str(scratch)) + ') (literal "/dev/null"))'
        return ['/usr/bin/sandbox-exec','-p',policy,str(python),'-I',str(script),*argv], 'macos-sandbox-exec'
    bwrap = shutil.which('bwrap')
    if platform.system() == 'Linux' and bwrap:
        cmd = [bwrap,'--die-with-parent','--unshare-all','--new-session','--proc','/proc','--dev','/dev']
        roots = {str(root), sys.base_prefix, '/usr'}
        for path in ('/lib','/lib64'):
            # ELF loader paths retain these names on usr-merged systems.
            # Resolving the source also as the mount destination loses them.
            if Path(path).exists(): roots.add(path)
        for path in sorted(roots): cmd += ['--ro-bind',path,path]
        cmd += ['--bind',str(scratch),str(scratch),'--remount-ro','/',
                '--chdir',str(root),'--',str(python),'-I',str(script),*argv]
        return cmd, 'linux-bubblewrap'
    raise ValueError('Verified OS sandbox is unavailable; worker code was not executed')


def sandbox_available():
    """Observe a harmless sandboxed Python process, not merely a binary path."""
    try:
        with tempfile.TemporaryDirectory(prefix='synthesis-sandbox-probe-') as name:
            root = Path(name).resolve(); script = root/'probe.py'; script.write_text('print("sandbox-ready")\n')
            cmd, _ = _sandbox_command(root,root,script,[])
            result = subprocess.run(cmd,capture_output=True,text=True,timeout=3,env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
            return result.returncode == 0 and result.stdout.strip() == 'sandbox-ready'
    except (OSError, ValueError, subprocess.TimeoutExpired): return False


def run_python_check(script, root, argv=None, *, timeout_seconds=5, output_limit=65536):
    """Run only Python under an observed filesystem/network sandbox and deadline."""
    root = Path(root).resolve(strict=True); script = Path(script).absolute()
    if not script.is_relative_to(root): raise ValueError('Check script is outside the admitted root')
    _read(root, str(script.relative_to(root)))
    argv = [] if argv is None else argv
    if not isinstance(argv,list) or len(argv)>32 or any(not isinstance(a,str) or len(a)>4096 for a in argv): raise ValueError('Invalid Python check arguments')
    if type(timeout_seconds) not in (int,float) or not 0 < timeout_seconds <= 60 or type(output_limit) is not int or not 1 <= output_limit <= MAX_BYTES: raise ValueError('Invalid execution bounds')
    if not sandbox_available(): raise ValueError('Verified OS sandbox is unavailable; worker code was not executed')
    with tempfile.TemporaryDirectory(prefix='synthesis-check-scratch-') as name:
        scratch=Path(name).resolve()
        bootstrap=scratch/'bounded.py'
        bootstrap.write_text('import os,resource,runpy,sys\nresource.setrlimit(resource.RLIMIT_CPU,('+str(max(1,int(timeout_seconds)+1))+',)*2)\nresource.setrlimit(resource.RLIMIT_FSIZE,('+str(MAX_BYTES)+',)*2)\nresource.setrlimit(resource.RLIMIT_NOFILE,(64,64))\nscript=sys.argv[1];sys.argv=sys.argv[1:];sys.path.insert(0,os.path.dirname(script));runpy.run_path(script,run_name="__main__")\n')
        cmd,provider=_sandbox_command(root,scratch,bootstrap,[str(script),*argv])
        env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(scratch)}
        proc=subprocess.Popen(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ,'stdout');selector.register(proc.stderr,selectors.EVENT_READ,'stderr')
        chunks={'stdout':bytearray(),'stderr':bytearray()};deadline=time.monotonic()+timeout_seconds;timed_out=False;exceeded=False
        try:
            while selector.get_map() or proc.poll() is None:
                if time.monotonic()>=deadline:timed_out=True;break
                wait=min(.05,max(0,deadline-time.monotonic()))
                if not selector.get_map():
                    time.sleep(wait)
                    continue
                for key,_ in selector.select(wait):
                    data=os.read(key.fileobj.fileno(),8192)
                    if not data:selector.unregister(key.fileobj);continue
                    chunks[key.data].extend(data)
                    if sum(map(len,chunks.values()))>output_limit:exceeded=True;break
                if exceeded:break
            if timed_out or exceeded:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            proc.wait(timeout=2)
        finally:
            selector.close()
            # A child cannot survive completion or leave a pipe-reading process.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait(timeout=2)
            proc.stdout.close();proc.stderr.close()
        return {'returncode':proc.returncode,'stdout':bytes(chunks['stdout'][:output_limit]).decode('utf-8','replace'),
                'stderr':bytes(chunks['stderr'][:output_limit]).decode('utf-8','replace'),'timed_out':timed_out,
                'output_exceeded':exceeded,'sandbox_verified':True,'sandbox_provider':provider}

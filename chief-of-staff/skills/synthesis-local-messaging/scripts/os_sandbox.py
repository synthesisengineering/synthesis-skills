# SPDX-License-Identifier: Apache-2.0
"""The command that runs Python under the operating system's sandbox: read-only roots, one
writable scratch directory, no network. The local messaging reader runs its worker with it.

macOS uses `sandbox-exec`; Linux uses bubblewrap (`bwrap`). There is no unsandboxed fallback:
when neither is usable, the caller refuses. Moved from the old autopilot engine's
`evaluation_artifacts.py` (lines 201-289), whose only real consumer was the local messaging
reader (v5 code evaluation, autopilot row G: KEEP). Its general runner, `run_python_check`, was
removed on 2026-10-13: the reader never called it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


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

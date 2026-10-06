"""Install the v5 runtime at one stable path, and keep it current (R7.1, R7.5).

Hooks call ~/.synthesis/v5/bin/synthesis-hook, whose command text never
changes between releases, so a harness's hook approval survives upgrades and a
harness deleting an old plugin folder never breaks a running task. At each
session start the hook passes the plugin folder the harness loaded; if its code
differs from the installed copy, it is installed beside the old one and
`current` switches atomically.

Run: python3 -S <plugin>/synthesis/install.py [plugin root]
"""

import hashlib
import os
import shutil
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOOK_SCRIPT = """#!/bin/sh
# Stable entry for every synthesis hook. Its text never changes between releases.
d=$(cd "$(dirname "$0")/.." && pwd)
exec python3 -S "$d/current/synthesis/hook.py" "$@"
"""
GIT_HOOK_SCRIPT = """#!/bin/sh
# Global git hook (core.hooksPath): the synthesis commit check, then the repository's own hook.
d=$(cd "$(dirname "$0")/.." && pwd)
SYNTHESIS_GIT_HOOK=$(basename "$0") exec python3 -S "$d/current/synthesis/commit_check.py" "$@"
"""
GIT_HOOKS = ("pre-commit", "pre-merge-commit")
CLI_SCRIPT = """#!/bin/sh
d=$(cd "$(dirname "$0")/.." && pwd)
PYTHONPATH="$d/current" exec python3 -m synthesis "$@"
"""


def _home() -> Path:
    from synthesis import paths
    return paths.home()


def package_hash(plugin_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((plugin_root / "synthesis").glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:16]


def current_hash() -> str:
    try:
        return (_home() / "current" / "HASH").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _write_exec(path: Path, text: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.chmod(0o755)
    os.replace(tmp, path)


def install(plugin_root: Path) -> str:
    """Install the plugin's runtime if it differs from the current one. Returns a one-line report."""
    plugin_root = Path(plugin_root).resolve()
    if not (plugin_root / "synthesis" / "hook.py").is_file():
        return f"not a synthesis plugin: {plugin_root}"
    home = _home()
    wanted = package_hash(plugin_root)
    if wanted != current_hash():
        release = home / "releases" / wanted
        if not release.is_dir():
            staging = home / "releases" / f".{wanted}.{os.getpid()}"
            shutil.copytree(plugin_root / "synthesis", staging / "synthesis",
                            ignore=shutil.ignore_patterns("__pycache__"))
            (staging / "HASH").write_text(wanted + "\n", encoding="utf-8")
            (staging / "SOURCE").write_text(f"{plugin_root}\n{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n", encoding="utf-8")
            os.replace(staging, release)
        link = home / f".current.{os.getpid()}"
        link.symlink_to(release)
        os.replace(link, home / "current")  # atomic switch: a running hook sees old or new, never neither
    _write_exec(home / "bin" / "synthesis-hook", HOOK_SCRIPT)
    _write_exec(home / "bin" / "synthesis", CLI_SCRIPT)
    for name in GIT_HOOKS:
        _write_exec(home / "git-hooks" / name, GIT_HOOK_SCRIPT)
    config = home / "config.json"
    if not config.exists():
        config.write_text("{}\n", encoding="utf-8")
    return f"synthesis runtime {wanted} at {home / 'current'}"


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    print(install(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

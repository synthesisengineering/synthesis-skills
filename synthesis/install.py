"""Install the v5 runtime at one stable path, and keep it current (R7.1, R7.5).

Hooks call ~/.synthesis/v5/bin/synthesis-hook, whose command text never
changes between releases, so a harness's hook approval survives upgrades and a
harness deleting an old plugin folder never breaks a running task. At each
session start the hook passes the plugin folder the harness loaded; if its code
differs from the installed copy, it is installed beside the old one and
`current` switches atomically.

Run: python3 -S <plugin>/synthesis/install.py [plugin root] [--git-hooks]
     python3 -S <plugin>/synthesis/install.py uninstall [--dry-run]

`--git-hooks` points the global core.hooksPath at the v5 commit check after
recording the value it replaces; uninstall restores that value unless the user
changed it since, and removes only files install wrote that are still unedited.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import paths  # noqa: E402

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
GIT_HOOKS = ("pre-commit", "pre-merge-commit", "commit-msg")
DAY_END = ("day-end", "day-end-nudge.sh")  # the rituals' launcher and nudge ride every release into bin/
# Scripts run outside a session (scheduled sweeps, autopilot wakes and backstops) need a stable path too.
STABLE_SKILL_SCRIPTS = ("synthesis-inbox-cleanup", "synthesis-autopilot", "synthesis-promotion-gate")
CLI_SCRIPT = """#!/bin/sh
d=$(cd "$(dirname "$0")/.." && pwd)
PYTHONPATH="$d/current" exec python3 -m synthesis "$@"
"""


def _home() -> Path:
    return paths.home()


def package_hash(plugin_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((plugin_root / "synthesis").glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    for rel, path in _stable_skill_files(plugin_root):
        digest.update(rel.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:16]


def _stable_skill_files(plugin_root: Path):
    for name in STABLE_SKILL_SCRIPTS:
        folder = Path(plugin_root) / "skills" / name / "scripts"
        for path in sorted(folder.iterdir()) if folder.is_dir() else []:
            if path.is_file() and not path.name.startswith("test_"):
                yield f"skills/{name}/scripts/{path.name}", path


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
            for rel, path in _stable_skill_files(plugin_root):
                (staging / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, staging / rel)
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
    copies = {}
    for name in DAY_END:
        source = plugin_root / "skills" / "synthesis-daily-rituals" / "scripts" / name
        if source.is_file():
            copies[name] = source.read_text(encoding="utf-8")
            _write_exec(home / "bin" / name, copies[name])
    record = _registrations(home)
    if copies and record.get("copies") != {n: _sha(v) for n, v in copies.items()}:  # so uninstall can tell edits
        record["copies"] = {n: _sha(v) for n, v in copies.items()}
        (home / "registrations.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    config = home / "config.json"
    if not config.exists():
        config.write_text("{}\n", encoding="utf-8")
    return f"synthesis runtime {wanted} at {home / 'current'}"


# ---- owned registrations: the global git hooks path, recorded so uninstall can restore it ----

def _git_global(*args):
    return subprocess.run(["git", "config", "--global", *args], capture_output=True, text=True,
                          timeout=15, stdin=subprocess.DEVNULL)


def hooks_path_values() -> list:
    found = _git_global("--get-all", "core.hooksPath")
    if found.returncode not in (0, 1):  # 1 means unset
        raise RuntimeError(f"cannot read the global core.hooksPath: {found.stderr.strip()}")
    return [v for v in found.stdout.splitlines() if v]


def _set_hooks_path(values: list) -> None:
    unset = _git_global("--unset-all", "core.hooksPath")
    if unset.returncode not in (0, 5):  # 5 means it was not set
        raise RuntimeError(f"cannot change core.hooksPath: {unset.stderr.strip()}")
    for value in values:
        if _git_global("--add", "core.hooksPath", value).returncode:
            raise RuntimeError(f"cannot set core.hooksPath to {value}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _registrations(home: Path) -> dict:
    return paths.read_json(home / "registrations.json")


def register_git_hooks(home: Path = None) -> str:
    """Point the global core.hooksPath at the v5 commit check, recording the value it replaces."""
    home = home or _home()
    target = str(home / "git-hooks")
    before = hooks_path_values()
    if before == [target]:
        return f"core.hooksPath already {target}"
    record = _registrations(home)
    if "git_hooks_path" not in record:  # the value from before our first install is the one to restore
        record["git_hooks_path"] = {"before": before, "installed": target}
        (home / "registrations.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    _set_hooks_path([target])
    note = f" (was {', '.join(before)}: git no longer runs hooks from there)" if before else ""
    return f"core.hooksPath -> {target}{note}"


def _owned_files(home: Path) -> list:
    """(path, sha256 of what install wrote) for every file install owns."""
    files = [(home / "bin" / "synthesis-hook", _sha(HOOK_SCRIPT)), (home / "bin" / "synthesis", _sha(CLI_SCRIPT))]
    files += [(home / "bin" / name, sha) for name, sha in (_registrations(home).get("copies") or {}).items()]
    return files + [(home / "git-hooks" / name, _sha(GIT_HOOK_SCRIPT)) for name in GIT_HOOKS]


def uninstall(home: Path = None, dry_run: bool = False) -> list:
    """Remove what install created; restore core.hooksPath; keep anything the user changed."""
    home, report, verb = home or _home(), [], "would remove" if dry_run else "removed"
    registered = _registrations(home).get("git_hooks_path")
    if registered:
        now = hooks_path_values()
        if now != [registered["installed"]]:
            report.append(f"kept core.hooksPath {now or 'unset'}: it changed since install")
        else:
            if not dry_run:
                _set_hooks_path(registered["before"])
            report.append(f"{'would restore' if dry_run else 'restored'} core.hooksPath to "
                          f"{', '.join(registered['before']) or 'unset'}")
    for path, sha in _owned_files(home):
        if path.is_file() and _sha(path.read_text(encoding="utf-8")) != sha:
            report.append(f"kept {path}: edited since install")
        elif path.is_file():
            if not dry_run:
                path.unlink()
            report.append(f"{verb} {path}")
    if (home / "current").is_symlink() and not dry_run:
        (home / "current").unlink()
    for release in sorted((home / "releases").glob("*")) if (home / "releases").is_dir() else []:
        if release.name.startswith(".") or package_hash(release) != release.name:
            report.append(f"kept {release}: its files changed since install")
            continue
        if not dry_run:
            shutil.rmtree(release)
        report.append(f"{verb} {release}")
    if (home / "registrations.json").exists() and not dry_run:
        (home / "registrations.json").unlink()
    report.append(f"kept {home / 'config.json'} and {home / 'state'} (your settings, board and approvals)")
    return report


if __name__ == "__main__":  # the bootstrap hooks.json runs before the stable `synthesis` command exists
    from synthesis import cli
    sys.exit(cli.main(sys.argv[1:] if sys.argv[1:2] == ["uninstall"] else ["install", *sys.argv[1:]]))

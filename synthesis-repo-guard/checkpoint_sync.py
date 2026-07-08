#!/usr/bin/env python3
"""
checkpoint_sync.py — Event-driven auto-commit + push for private context repos.

The REMEDIATOR layer of synthesis-repo-guard (see SKILL.md for the full
three-layer design). Invoked at WORKFLOW EVENTS, never on a wall-clock timer:

  - AI-tool turn/session end (e.g., Claude Code Stop hook), throttled
  - synthesis-console after a cockpit write (`--repo <path> --now`)
  - daily rituals / mac-sync sweeps

Design rules (agreed 2026-07-08; companion lesson
2026-07-08-alert-channel-confidentiality-and-event-driven-checkpoints):

  1. NO background timers. Runs only at interactive workflow moments, on the
     machine where the change originated. Read-only status polling elsewhere
     is fine; mutation is event-driven only.
  2. RUNTIME REMOTE GUARD: regardless of config, a repo is touched only if
     EVERY push remote matches an allowed prefix (the owner's private
     GitHub namespace). Config declares intent; the guard verifies reality.
  3. Safe ordering: commit local first (snapshot), then fetch, push only if
     fast-forward. On divergence: leave the commit local and alert. Never
     rebase, never force-push, never --no-verify. Pre-commit hook failures
     abort that repo's checkpoint and alert.
  4. Quiescence: skip a repo if any dirty file changed in the last N minutes
     (never commit mid-thought). `--now` bypasses (console just finished its
     own write). Deleted paths are inherently quiescent.
  5. Stale index.lock (> 10 min): report, never delete.
  6. Alerts are GENERIC on audio/banner surfaces (no repo/client names —
     same rule as repo_sync_check.py); detail goes to the state file that
     synthesis-console renders.

Config: ~/.synthesis/checkpoint-sync.yaml (see checkpoint-sync.example.yaml).
State:  ~/.synthesis/repo-guard/checkpoint-state.json (+ throttle stamp).

Exit codes: 0 = nothing needed / all healed; 1 = alerts raised; 2 = error.

Examples:
  ./checkpoint_sync.py --hook --quiet        # throttled sweep (Stop hook)
  ./checkpoint_sync.py --repo ~/x/plan.md --now   # single-repo, post-write
  ./checkpoint_sync.py --dry-run             # show what would happen
  ./checkpoint_sync.py --no-throttle         # manual "Sync now" button
"""

import argparse
import fnmatch
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# SYNTHESIS_HOME overrides the state root (tests, sandboxes). Default ~/.synthesis
SYNTHESIS_HOME = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
CONFIG_PATH = SYNTHESIS_HOME / "checkpoint-sync.yaml"
STATE_DIR = SYNTHESIS_HOME / "repo-guard"
STATE_FILE = STATE_DIR / "checkpoint-state.json"
THROTTLE_STAMP = STATE_DIR / "last-checkpoint-run"
QUIET_AUDIO_FLAG = SYNTHESIS_HOME / "quiet-audio"

DEFAULTS = {
    "repos": [],
    "repo_globs": [],
    "allowed_remote_prefixes": [],
    "quiescence_minutes": 15,
    "throttle_minutes": 10,
    "commit_author_name": "Synthesis Checkpoint",
    "commit_author_email": "checkpoint@synthesisengineering.org",
}


# ---------------------------------------------------------------------------
# Config — PyYAML if present, else a minimal parser for the flat subset used
# ---------------------------------------------------------------------------

def _mini_yaml(text: str) -> dict:
    """Parse the restricted YAML subset this config uses: top-level
    `key: value` scalars and `key:` followed by `- item` lists. Comments and
    blank lines ignored. Sufficient and dependency-free."""
    data: dict = {}
    current_list = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_list is None:
                raise ValueError(f"list item outside a list key: {raw!r}")
            data[current_list].append(line.split("- ", 1)[1].strip().strip("'\""))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip().strip("'\"")
            if value == "":
                data[key] = []
                current_list = key
            else:
                data[key] = value
                current_list = None
    return data


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_yaml(text)


def resolve_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in load_config(path).items() if v is not None})
    cfg["quiescence_minutes"] = int(cfg["quiescence_minutes"])
    cfg["throttle_minutes"] = int(cfg["throttle_minutes"])
    return cfg


def configured_repos(cfg: dict) -> list[Path]:
    """Expand explicit paths + globs into existing repo paths (deduped)."""
    found: list[Path] = []
    seen = set()
    for entry in cfg.get("repos", []):
        p = Path(os.path.expanduser(str(entry)))
        if p.is_dir() and (p / ".git").exists() and str(p) not in seen:
            seen.add(str(p))
            found.append(p)
    for pattern in cfg.get("repo_globs", []):
        pattern = os.path.expanduser(str(pattern))
        # Glob over the filesystem: expand each path segment via Path.glob
        base = Path("/")
        try:
            import glob as _glob
            for hit in sorted(_glob.glob(pattern)):
                p = Path(hit)
                if p.is_dir() and (p / ".git").exists() and str(p) not in seen:
                    seen.add(str(p))
                    found.append(p)
        except Exception:
            continue
    return found


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(repo: Path, *args: str, timeout: int = 60, env: dict | None = None,
        strip: bool = True) -> tuple[int, str, str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        r = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True, text=True, timeout=timeout, env=merged_env,
        )
        out = r.stdout.strip() if strip else r.stdout
        return r.returncode, out, r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", "git not found"


def remote_guard(repo: Path, allowed_prefixes: list[str]) -> tuple[bool, str]:
    """A repo may be auto-touched only if every push remote URL starts with an
    allowed prefix. Empty allowed list => guard fails (fail closed)."""
    if not allowed_prefixes:
        return False, "no allowed_remote_prefixes configured (fail closed)"
    rc, out, err = git(repo, "remote", "-v")
    if rc != 0:
        return False, f"git remote failed: {err or out}"
    push_urls = [
        line.split()[1]
        for line in out.splitlines()
        if line.strip().endswith("(push)") and len(line.split()) >= 2
    ]
    if not push_urls:
        return False, "no push remotes"
    for url in push_urls:
        if not any(url.startswith(p) for p in allowed_prefixes):
            return False, f"push remote outside allowed namespace: {url}"
    return True, "ok"


def dirty_paths(repo: Path) -> list[str]:
    # strip=False: porcelain lines for unstaged states begin with a SPACE
    # (" M path"). A global strip() eats that space on the FIRST line and the
    # fixed-width `line[3:]` slice then chops the path's first character.
    # (Found live 2026-07-08: producer mode saw "rojects/…" and matched nothing.)
    rc, out, _ = git(repo, "status", "--porcelain", strip=False)
    if rc != 0 or not out.strip():
        return []
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1: two status chars, one space, then the path
        # (or `old -> new` for renames)
        p = line[3:]
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        p = p.strip().strip('"')
        if p:
            paths.append(p)
    return paths


def newest_mtime(repo: Path, rel_paths: list[str]) -> float:
    newest = 0.0
    for rel in rel_paths:
        fp = repo / rel
        try:
            newest = max(newest, fp.stat().st_mtime)
        except OSError:
            continue  # deleted paths are inherently quiescent
    return newest


def ahead_behind(repo: Path, branch: str) -> tuple[int, int]:
    rc, out, _ = git(repo, "rev-list", "--left-right", "--count", f"origin/{branch}...{branch}")
    if rc != 0:
        return (0, 0)
    parts = out.split()
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])  # (behind, ahead)
    return (0, 0)


# ---------------------------------------------------------------------------
# Checkpoint core
# ---------------------------------------------------------------------------

def summarize_paths(paths: list[str], limit: int = 3) -> str:
    shown = ", ".join(paths[:limit])
    extra = len(paths) - limit
    return shown + (f" +{extra} more" if extra > 0 else "")


def checkpoint_repo(repo: Path, cfg: dict, *, skip_quiescence: bool, dry_run: bool,
                    only_file: Path | None = None) -> dict:
    """Attempt to checkpoint one repo. Returns an outcome record.

    only_file (producer mode): stage and commit JUST that file — other dirty
    files in the repo may belong to an in-flight session and are left for the
    next quiescence-respecting sweep."""
    rec: dict = {"repo": str(repo), "name": repo.name, "action": "none", "alert": None}

    ok, reason = remote_guard(repo, cfg["allowed_remote_prefixes"])
    if not ok:
        rec.update(action="guard-rejected", alert=f"remote guard: {reason}")
        return rec

    # Stale lock check — report, never delete
    lock = repo / ".git" / "index.lock"
    if lock.exists():
        age_min = (time.time() - lock.stat().st_mtime) / 60
        if age_min > 10:
            rec.update(action="skipped", alert=f"stale index.lock ({age_min:.0f} min old) — investigate manually")
        else:
            rec.update(action="skipped-lock-active")
        return rec

    rc, branch, _ = git(repo, "branch", "--show-current")
    if rc != 0 or not branch:
        rec.update(action="skipped", alert="detached HEAD or no branch")
        return rec

    paths = dirty_paths(repo)
    if only_file is not None:
        try:
            rel = str(only_file.resolve().relative_to(repo.resolve()))
        except ValueError:
            rel = None
        paths = [p for p in paths if rel is not None and p == rel]

    if paths and not skip_quiescence:
        quiet_s = cfg["quiescence_minutes"] * 60
        if time.time() - newest_mtime(repo, paths) < quiet_s:
            rec.update(action="skipped-quiescence", detail=f"{len(paths)} file(s) changed recently")
            return rec

    committed = False
    if paths:
        if dry_run:
            rec.update(action="would-commit", files=len(paths), detail=summarize_paths(paths))
            return rec
        if only_file is not None:
            rc, _, err = git(repo, "add", "--", *paths)
        else:
            rc, _, err = git(repo, "add", "-A")
        if rc != 0:
            rec.update(action="failed", alert=f"git add failed: {err}")
            return rec
        msg = f"checkpoint auto-sync: {summarize_paths(paths)}"
        author_env = {
            "GIT_AUTHOR_NAME": cfg["commit_author_name"],
            "GIT_AUTHOR_EMAIL": cfg["commit_author_email"],
            "GIT_COMMITTER_NAME": cfg["commit_author_name"],
            "GIT_COMMITTER_EMAIL": cfg["commit_author_email"],
        }
        rc, out, err = git(repo, "commit", "-m", msg, env=author_env, timeout=120)
        if rc != 0:
            # Most likely a pre-commit hook rejection — never bypass it.
            rec.update(action="hook-blocked", alert=f"commit blocked (pre-commit hook?): {(err or out)[:300]}")
            return rec
        committed = True
        rec.update(files=len(paths), detail=summarize_paths(paths))

    # Push anything unpushed (this run's commit or an earlier stranded one)
    rc, _, err = git(repo, "fetch", "origin", timeout=120)
    if rc != 0:
        rec.update(action="committed-no-push" if committed else "fetch-failed",
                   alert=f"fetch failed (offline?): {err[:200]}")
        return rec
    behind, ahead = ahead_behind(repo, branch)
    if ahead > 0:
        if behind > 0:
            rec.update(action="committed-diverged" if committed else "diverged",
                       alert=f"diverged from origin/{branch} (ahead {ahead}, behind {behind}) — resolve manually; commit is safe locally")
            return rec
        if dry_run:
            rec.update(action="would-push", ahead=ahead)
            return rec
        rc, out, err = git(repo, "push", "origin", branch, timeout=180)
        if rc != 0:
            rec.update(action="committed-push-failed" if committed else "push-failed",
                       alert=f"push failed: {(err or out)[:200]}")
            return rec
        rec.update(action="committed-pushed" if committed else "pushed-stranded", ahead=ahead)
    elif committed:
        rec.update(action="committed-pushed")  # shouldn't happen (ahead>=1), defensive
    elif not paths:
        rec.update(action="clean")
    return rec


# ---------------------------------------------------------------------------
# Generic attention ping (same confidentiality rule as repo_sync_check)
# ---------------------------------------------------------------------------

def audio_muted() -> bool:
    return QUIET_AUDIO_FLAG.exists()


def generic_alert_ping(alert_count: int, speak: bool, notify: bool) -> None:
    if sys.platform != "darwin" or audio_muted():
        return
    noun = "item needs" if alert_count == 1 else "items need"
    msg = f"Repo checkpoint: {alert_count} {noun} your attention. Details are in your synthesis console."
    if notify:
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "Repo checkpoint"'],
            capture_output=True,
        )
    if speak:
        subprocess.run(["say", msg], capture_output=True)


# ---------------------------------------------------------------------------
# State + throttle
# ---------------------------------------------------------------------------

def write_state(mode: str, results: list[dict], running: bool) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": socket.gethostname(),
        "mode": mode,
        "running": running,
        "results": results,
        "alerts": [r for r in results if r.get("alert")],
    }
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(STATE_FILE)


def throttled(minutes: int) -> bool:
    try:
        return (time.time() - THROTTLE_STAMP.stat().st_mtime) < minutes * 60
    except OSError:
        return False


def stamp_throttle() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    THROTTLE_STAMP.touch()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG_PATH, help=f"Config path (default {CONFIG_PATH})")
    ap.add_argument("--repo", type=Path, default=None,
                    help="Single-repo mode: any path inside the repo (resolved via git rev-parse)")
    ap.add_argument("--hook", action="store_true", help="Hook mode: honor throttle, quiet by default")
    ap.add_argument("--now", action="store_true", help="Bypass throttle AND quiescence (post-write producer mode)")
    ap.add_argument("--no-throttle", action="store_true", help="Bypass throttle only (manual Sync-now button)")
    ap.add_argument("--dry-run", action="store_true", help="Report what would happen; change nothing")
    ap.add_argument("--quiet", "-q", action="store_true", help="No stdout (state file still written)")
    ap.add_argument("--json", "-j", action="store_true", help="Print outcomes as JSON")
    ap.add_argument("--speak", action="store_true", help="Generic spoken ping if alerts (mute-aware)")
    ap.add_argument("--notify", action="store_true", help="Generic banner if alerts (mute-aware)")
    args = ap.parse_args()

    cfg = resolve_config(args.config.expanduser())

    skip_quiescence = bool(args.now)
    skip_throttle = bool(args.now or args.no_throttle or args.repo or args.dry_run)

    if args.hook and not skip_throttle and throttled(cfg["throttle_minutes"]):
        if not args.quiet:
            print("checkpoint_sync: throttled (recent run) — nothing done")
        return 0

    # Target set
    if args.repo:
        rc = subprocess.run(
            ["git", "-C", str(args.repo.expanduser() if args.repo.is_dir() else args.repo.expanduser().parent),
             "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if rc.returncode != 0:
            print(f"Error: {args.repo} is not inside a git repo", file=sys.stderr)
            return 2
        targets = [Path(rc.stdout.strip())]
        only_file = args.repo.expanduser() if args.repo.expanduser().is_file() else None
    else:
        only_file = None
        targets = configured_repos(cfg)
        if not targets:
            if not args.quiet:
                print(f"checkpoint_sync: no configured repos found (config: {args.config})")
            return 0

    if not args.dry_run:
        write_state("single" if args.repo else ("hook" if args.hook else "manual"), [], running=True)

    results = [
        checkpoint_repo(t, cfg, skip_quiescence=skip_quiescence, dry_run=args.dry_run,
                        only_file=only_file)
        for t in targets
    ]

    if not args.dry_run:
        write_state("single" if args.repo else ("hook" if args.hook else "manual"), results, running=False)
        if args.hook:
            stamp_throttle()

    alerts = [r for r in results if r.get("alert")]
    if alerts:
        generic_alert_ping(len(alerts), speak=args.speak, notify=args.notify)

    if not args.quiet:
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                line = f"{r['name']}: {r['action']}"
                if r.get("detail"):
                    line += f" ({r['detail']})"
                if r.get("alert"):
                    line += f"  ⚠ {r['alert']}"
                print(line)

    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())

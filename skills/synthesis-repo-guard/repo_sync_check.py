#!/usr/bin/env python3
"""
repo_sync_check.py — Detect unsynced git repositories in a workspace. (v2)

Scans a workspace root for git repositories and reports any that have:
  - Uncommitted changes (modified, staged, or untracked files)
  - Unpushed commits (ahead of remote)
  - Unpulled commits (behind remote)

Designed to run standalone from a terminal, as an AI tool session-end hook
(Claude Code, Codex, Cursor, etc.), on demand from synthesis-console, or
after a workflow event. Zero external dependencies — Python stdlib + git CLI.

v2 (three-layer redesign: detector / messenger / remediator):
  - DETECTOR (this file's scan) is unchanged in behavior.
  - MESSENGER: every run now writes report files (text + JSON + history.jsonl)
    to --report-dir (default ~/.synthesis/repo-guard/) for consumption by
    synthesis-console tiles and agent sessions.
  - AUDIO/NOTIFICATION CONFIDENTIALITY (ABSOLUTE): --speak and --notify emit
    GENERIC content only — a count and a pointer to the console/report.
    Repo names, workspace names, and client names are NEVER spoken or shown
    in notification banners: audible surfaces reach whoever is nearby or on
    an unmuted call, and banners appear during screen-shares. Identifying
    detail belongs only in pull channels (report files, synthesis-console).
  - MUTE FLAG: --speak/--alert/--notify honor ~/.synthesis/quiet-audio
    (created/removed by the synthesis-console toggle; or `touch` it manually).
  - REMEDIATOR: companion script checkpoint_sync.py auto-commits+pushes the
    configured private context-repo class at workflow events. See SKILL.md.

Exit codes:
  0 — All repos clean and synced
  1 — One or more repos need attention
  2 — Error (e.g., git not found, workspace doesn't exist)

Examples:
  ./repo_sync_check.py                          # scan ~/workspaces, write reports
  ./repo_sync_check.py --json --quiet           # machine-readable, no stdout text
  ./repo_sync_check.py --speak --notify         # generic ping if dirty (mute-aware)
  ./repo_sync_check.py --no-report              # ad-hoc scan, don't touch reports
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# SYNTHESIS_HOME overrides the state root (tests, sandboxes). Default ~/.synthesis
SYNTHESIS_HOME = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
QUIET_AUDIO_FLAG = SYNTHESIS_HOME / "quiet-audio"
DEFAULT_REPORT_DIR = SYNTHESIS_HOME / "repo-guard"


def find_git_repos(workspace: Path, max_depth: int = 3) -> list[Path]:
    """Find all git repositories under workspace, up to max_depth."""
    repos = []
    workspace = workspace.resolve()

    def _scan(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            git_dir = directory / ".git"
            if git_dir.exists():
                repos.append(directory)
                return  # Don't recurse into nested repos
            for child in sorted(directory.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    _scan(child, depth + 1)
        except PermissionError:
            pass

    _scan(workspace, 0)
    return repos


def git_cmd(repo: Path, *args: str, strip: bool = True) -> tuple[int, str]:
    """Run a git command in a repo directory. Returns (exit_code, stdout).

    strip=False preserves column-significant output (git status --porcelain
    lines start with a space for unstaged states — a global strip corrupts
    the first line's status columns)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip() if strip else result.stdout
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except FileNotFoundError:
        return -1, "git not found"


def check_repo(repo: Path) -> dict:
    """Check a single repo for unsynced state. Returns a status dict."""
    name = repo.name
    status = {
        "name": name,
        "path": str(repo),
        "clean": True,
        "issues": [],
    }

    # Check for uncommitted changes (strip=False: porcelain columns matter)
    rc, output = git_cmd(repo, "status", "--porcelain", strip=False)
    if rc != 0:
        status["clean"] = False
        status["issues"].append({"type": "error", "detail": f"git status failed: {output.strip()}"})
        return status

    if output.strip():
        lines = [ln for ln in output.splitlines() if ln.strip()]
        status["clean"] = False
        status["issues"].append({
            "type": "uncommitted",
            "detail": f"{len(lines)} uncommitted file(s)",
            "files": lines[:10],  # Cap at 10 for readability
            "total": len(lines),
        })

    # Get current branch
    rc, branch = git_cmd(repo, "branch", "--show-current")
    if rc != 0 or not branch:
        # Detached HEAD or error — report and move on
        if not output:  # Only if no uncommitted changes already reported
            status["issues"].append({"type": "detached", "detail": "detached HEAD or no branch"})
        return status

    # Check ahead/behind remote
    rc, counts = git_cmd(repo, "rev-list", "--left-right", "--count", f"origin/{branch}...{branch}")
    if rc != 0:
        # No remote tracking — not necessarily a problem
        return status

    parts = counts.split()
    if len(parts) == 2:
        behind, ahead = int(parts[0]), int(parts[1])
        if ahead > 0:
            status["clean"] = False
            status["issues"].append({
                "type": "unpushed",
                "detail": f"{ahead} unpushed commit(s) on {branch}",
                "count": ahead,
            })
        if behind > 0:
            status["clean"] = False
            status["issues"].append({
                "type": "behind",
                "detail": f"{behind} commit(s) behind origin/{branch}",
                "count": behind,
            })

    return status


# ---------------------------------------------------------------------------
# Messenger layer — generic audio/banner, detailed reports
# ---------------------------------------------------------------------------

def audio_muted() -> bool:
    """True when the synthesis-console quiet-audio toggle (or a manual touch)
    has muted all audible output."""
    return QUIET_AUDIO_FLAG.exists()


def play_alert() -> None:
    """Play macOS alert sound. Mute-aware. No-op on other platforms."""
    if sys.platform == "darwin" and not audio_muted():
        sound = "/System/Library/Sounds/Glass.aiff"
        for _ in range(3):
            subprocess.run(["afplay", sound], capture_output=True)


def spoken_warning_text(dirty_count: int) -> str:
    """GENERIC spoken warning. Deliberately carries no repo/workspace/client
    names — audible surfaces are public-adjacent. Do not add names here."""
    noun = "repository needs" if dirty_count == 1 else "repositories need"
    return f"Repo guard: {dirty_count} {noun} attention. Details are in your synthesis console."


def speak_warning(dirty_count: int) -> None:
    """Speak a GENERIC warning on macOS. Mute-aware. No-op elsewhere."""
    if sys.platform == "darwin" and not audio_muted():
        subprocess.run(["say", spoken_warning_text(dirty_count)], capture_output=True)


def notify_generic(dirty_count: int) -> None:
    """Post a GENERIC macOS notification banner. Banners are visible during
    screen-shares — same confidentiality rule as audio: count + pointer only."""
    if sys.platform != "darwin" or audio_muted():
        return
    noun = "repository needs" if dirty_count == 1 else "repositories need"
    msg = f"{dirty_count} {noun} attention — open synthesis console for details"
    script = f'display notification "{msg}" with title "Repo guard"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def write_reports(results: list[dict], report_dir: Path) -> None:
    """Write the detailed report files (the pull channel). Names and file
    lists are fine here — these live on the private disk and are rendered
    only by surfaces the user deliberately opens (synthesis-console, editor)."""
    report_dir.mkdir(parents=True, exist_ok=True)
    dirty = [r for r in results if not r["clean"]]
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    payload = {
        "generated_at": now,
        "host": socket.gethostname(),
        "total_repos": len(results),
        "dirty_count": len(dirty),
        "repos": results,
    }
    (report_dir / "last-report.json").write_text(json.dumps(payload, indent=2) + "\n")
    (report_dir / "last-report.txt").write_text(
        f"Repo guard report — {now} on {socket.gethostname()}\n\n"
        + format_text_report(results) + "\n"
    )
    history_entry = {
        "ts": now,
        "host": socket.gethostname(),
        "total": len(results),
        "dirty": [r["name"] for r in dirty],
    }
    with open(report_dir / "history.jsonl", "a") as fh:
        fh.write(json.dumps(history_entry) + "\n")


def format_text_report(results: list[dict]) -> str:
    """Format results as human-readable text, including remediation hints."""
    dirty = [r for r in results if not r["clean"]]
    clean_count = len(results) - len(dirty)

    if not dirty:
        return f"All {len(results)} repositories clean and synced."

    lines = []
    lines.append(f"Repositories needing attention: {len(dirty)} of {len(results)}")
    lines.append("")

    for repo in dirty:
        lines.append(f"  {repo['name']}/")
        for issue in repo["issues"]:
            marker = {
                "uncommitted": "dirty",
                "unpushed": "ahead",
                "behind": "behind",
                "detached": "detached",
                "error": "error",
            }.get(issue["type"], issue["type"])
            lines.append(f"    [{marker}] {issue['detail']}")
            if "files" in issue:
                for f in issue["files"]:
                    lines.append(f"      {f}")
                if issue.get("total", 0) > len(issue.get("files", [])):
                    lines.append(f"      ... and {issue['total'] - len(issue['files'])} more")
        lines.append(f"    fix: cd {repo['path']} && git status")
        lines.append("")

    lines.append(f"Clean: {clean_count} repositories")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check workspace git repositories for unsynced state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--workspace", "-w",
        type=Path,
        default=Path.home() / "workspaces",
        help="Workspace root to scan (default: ~/workspaces)",
    )
    parser.add_argument(
        "--max-depth", "-d",
        type=int,
        default=3,
        help="Maximum directory depth for repo discovery (default: 3)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress stdout — exit code only (reports still written)",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--alert", "-a",
        action="store_true",
        help="Play macOS alert sound if repos are dirty (mute-aware)",
    )
    parser.add_argument(
        "--speak", "-s",
        action="store_true",
        help="Speak a GENERIC warning (count only — never names) if dirty (mute-aware)",
    )
    parser.add_argument(
        "--notify", "-n",
        action="store_true",
        help="Post a GENERIC macOS notification banner if dirty (mute-aware)",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help=f"Where to write last-report.txt/.json + history.jsonl (default: {DEFAULT_REPORT_DIR})",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing report files (ad-hoc scans)",
    )
    parser.add_argument(
        "--dirty-only",
        action="store_true",
        help="Only include dirty repos in output (skip clean repos)",
    )
    args = parser.parse_args()

    # Validate workspace
    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        if not args.quiet:
            print(f"Error: workspace not found: {workspace}", file=sys.stderr)
        return 2

    # Verify git is available
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        if not args.quiet:
            print("Error: git is not installed or not in PATH", file=sys.stderr)
        return 2

    # Find and check repos
    repos = find_git_repos(workspace, args.max_depth)
    if not repos:
        if not args.quiet:
            print(f"No git repositories found under {workspace}")
        return 0

    results = [check_repo(repo) for repo in repos]
    dirty = [r for r in results if not r["clean"]]

    # Reports — the detailed pull channel (written on every run unless opted out)
    if not args.no_report:
        try:
            write_reports(results, args.report_dir.expanduser())
        except OSError as e:
            print(f"Warning: could not write reports: {e}", file=sys.stderr)

    # Output
    if not args.quiet:
        if args.json:
            output = results if not args.dirty_only else dirty
            print(json.dumps(output, indent=2))
        else:
            print(format_text_report(results))

    # Attention pings — GENERIC by design (see module docstring)
    if dirty:
        if args.alert:
            play_alert()
        if args.speak:
            speak_warning(len(dirty))
        if args.notify:
            notify_generic(len(dirty))

    return 1 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())

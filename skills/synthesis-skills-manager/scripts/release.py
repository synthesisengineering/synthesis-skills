"""Release synthesis-skills: preflight, one releaser at a time, publish, install in every harness,
then prove the installed bytes equal the tag.

    python3 skills/synthesis-skills-manager/scripts/release.py [--repo-root .] [--dry-run]
    python3 skills/synthesis-skills-manager/scripts/release.py --install-only   # new Mac or drift

Pushing is publishing (the marketplaces point at the repository), but each harness keeps its
own installed copy that does not follow the remote, so a pushed-but-uninstalled release
leaves every harness behind with nothing visibly wrong. The script therefore ends only when
each harness's installed files equal the tagged files, read at the folder the harness
reports loading, whatever its version label says.

Stages, each gating the next:
  1. Preflight: clean tree on the default branch, not a plugin cache; the three plugin
     manifests agree; the CHANGELOG's newest entry is this version; CI passed for HEAD.
  2. Release train: a board claim on the main checkout's CHANGELOG.md. Another live session
     holding it means another release is under way: refuse and name it.
  3. Publish: create the tag, push main, stable and the tag to every push remote in one
     atomic push each; success is read back with `git ls-remote`, never from an exit status.
  4. Install with each harness's own commands (onboarding's setup.py), then verify bytes.
  5. Update the stable runtime from a verified copy and run `synthesis doctor`.
Exit 0 only when every found harness verified and doctor is healthy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
for path in (REPO, REPO / "skills" / "synthesis-onboarding" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import setup  # noqa: E402  (each harness's install commands)
from synthesis import board, doctor, install, paths  # noqa: E402

MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json")
LOADABLE = ("skills/", "synthesis/", "hooks/", ".claude-plugin/", ".codex-plugin/", ".muse-plugin/")
IGNORED = ("__pycache__", ".DS_Store")


def git(repo: Path, *args: str, timeout: float = 600) -> subprocess.CompletedProcess:
    return setup.run(["git", "-C", str(repo), *args], timeout)


def manifest_version(repo: Path) -> tuple:
    found = {}
    for name in MANIFESTS:
        try:
            found[name] = json.loads((repo / name).read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError) as exc:
            return None, f"{name}: {exc}"
    versions = set(found.values())
    if len(versions) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", str(next(iter(versions)))):
        return None, "manifest versions disagree or are missing: " + ", ".join(f"{k}={v}" for k, v in found.items())
    return versions.pop(), "the three manifests agree"


def changelog_version(repo: Path) -> str:
    match = re.search(r"^## \[?(\d+\.\d+\.\d+)\]?", (repo / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else ""


def ci_state(repo: Path, sha: str, run=setup.run) -> tuple:
    """(passed, detail) for HEAD's CI on GitHub. Unknown is not passed."""
    proc = run(["gh", "run", "list", "--commit", sha, "--json", "status,conclusion,workflowName", "--limit", "50"],
               60, cwd=str(repo))
    runs = setup._json(proc.stdout) if proc.returncode == 0 else None
    if not isinstance(runs, list):
        return False, f"cannot read CI for {sha[:12]} (is gh installed and signed in?): {setup._tail(proc)}"
    if not runs:
        return False, f"no CI run for {sha[:12]} yet; push it and wait for CI"
    pending = [r.get("workflowName", "?") for r in runs if r.get("status") != "completed"]
    failed = [r.get("workflowName", "?") for r in runs if r.get("status") == "completed"
              and r.get("conclusion") not in ("success", "skipped", "neutral")]
    if pending or failed:
        return False, f"CI for {sha[:12]}: running {pending or 'none'}, failed {failed or 'none'}"
    return True, f"CI passed for {sha[:12]} ({len(runs)} run(s))"


def preflight(repo: Path, install_only: bool, ci=ci_state) -> tuple:
    """(version, problems). Nothing is pushed or installed unless problems is empty."""
    problems = []
    if "cache" in repo.parts and "plugins" in repo.parts or "muse-bundle" in repo.parts:
        return None, [f"{repo} is an installed plugin copy, not a source checkout"]
    if Path(git(repo, "rev-parse", "--show-toplevel").stdout.strip() or "/").resolve() != repo.resolve():
        return None, [f"{repo} is not the root of a git checkout"]
    if git(repo, "status", "--porcelain").stdout.strip():
        problems.append("the tree has uncommitted changes")
    default = (git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").stdout.strip() or "origin/main")
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != default.split("/", 1)[-1]:
        problems.append(f"on {branch or 'a detached HEAD'}, not the default branch {default.split('/', 1)[-1]}")
    version, detail = manifest_version(repo)
    if version is None:
        return None, problems + [detail]
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    tag = git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/v{version}^{{commit}}").stdout.strip()
    if install_only:
        if tag != head:
            problems.append(f"v{version} is {'missing' if not tag else 'not HEAD'}; install from the tagged commit")
        return version, problems
    if changelog_version(repo) != version:
        problems.append(f"CHANGELOG's newest entry is {changelog_version(repo) or 'missing'}, manifests say {version}")
    if tag and tag != head:
        problems.append(f"v{version} already tags another commit; bump the version")
    passed, detail = ci(repo, head)
    if not passed:
        problems.append(detail)
    return version, problems


def train_path(repo: Path) -> str:
    """CHANGELOG.md of the main checkout, so releases from different worktrees still collide."""
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip())
    return str((common.parent if common.name == ".git" else repo) / "CHANGELOG.md")


def hold_train(repo: Path, session: str, version: str) -> str:
    try:
        board.claim(session, [train_path(repo)], goal=f"release v{version}", harness=paths.harness())
    except board.ClaimConflict as exc:
        raise setup.SetupError(f"another release is under way: {exc}. Wait for it, or message that session "
                               "with `synthesis msg`; a stale holder is the principal's to release")
    return train_path(repo)


def publish(repo: Path, version: str, dry_run: bool = False) -> list:
    head, tag = git(repo, "rev-parse", "HEAD").stdout.strip(), f"v{version}"
    refspecs = ["HEAD:refs/heads/main", "HEAD:refs/heads/stable", f"refs/tags/{tag}:refs/tags/{tag}"]
    remotes = sorted({line.split()[0] for line in git(repo, "remote", "-v").stdout.splitlines()
                      if line.endswith("(push)")})
    if not remotes:
        raise setup.SetupError("no push remote is configured")
    if dry_run:
        return [f"would tag {tag} at {head[:12]} and push {' '.join(refspecs)} to {', '.join(remotes)}"]
    if not git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}").stdout.strip():
        made = git(repo, "tag", "-a", tag, "-m", f"Release {tag}")
        if made.returncode:
            raise setup.SetupError(f"cannot create {tag}: {setup._tail(made)}")
    lines = []
    for remote in remotes:  # one atomic push per remote: main, stable and the tag move together or not at all
        pushed = git(repo, "push", "--atomic", remote, *refspecs)
        seen = dict(reversed(line.split("\t")) for line in git(
            repo, "ls-remote", remote, "refs/heads/main", "refs/heads/stable", f"refs/tags/{tag}*",
            timeout=120).stdout.splitlines() if "\t" in line)
        seen[f"refs/tags/{tag}"] = seen.get(f"refs/tags/{tag}^{{}}", seen.get(f"refs/tags/{tag}"))  # peeled
        wrong = [r for r in ("refs/heads/main", "refs/heads/stable", f"refs/tags/{tag}") if seen.get(r) != head]
        if wrong:
            raise setup.SetupError(f"{remote}: {', '.join(wrong)} do not point at {head[:12]} after the push "
                                   f"({setup._tail(pushed)})")
        lines.append(f"{remote}: main, stable and {tag} at {head[:12]}")
    return lines


def blob_id(path: Path) -> str:
    data = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_differences(repo: Path, ref: str, root: Path) -> list:
    """Every tracked file at `ref` must be in `root` with the same bytes; an extra loadable file
    (one a harness would read as a skill, hook or runtime) is a difference too."""
    listing = git(repo, "ls-tree", "-r", "-z", ref).stdout.split("\0")
    tracked, problems = {}, []
    for line in filter(None, listing):
        meta, path = line.split("\t", 1)
        tracked[path] = meta.split()[2]
    for path, sha in sorted(tracked.items()):
        installed = root / path
        if not os.path.lexists(installed):
            problems.append(f"missing {path}")
        elif blob_id(installed) != sha:
            problems.append(f"differs {path}")
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and rel.startswith(LOADABLE) and rel not in tracked and not any(i in rel for i in IGNORED):
            problems.append(f"extra {rel}")
    return problems


def installed_root(client: str, binary: str):
    entry = setup.plugin_entry(client, binary)
    if not entry:
        return None, ""
    path = entry.get("cache_path") if client == "muse" else entry.get("path")
    return (Path(path) if path else None), str(entry.get("version", ""))


def install_and_verify(repo: Path, version: str, clients: list, dry_run: bool = False) -> tuple:
    """(lines, verified roots, harnesses found). A harness not on this Mac is skipped, not failed."""
    lines, verified, found = [], {}, []
    for client in clients:
        binary = doctor.find_client(client)
        if not binary:
            lines.append(f"{client}: not on this Mac; skipped")
            continue
        found.append(client)
        try:
            lines.append(setup.install_muse(binary, repo, ref=f"v{version}", dry_run=dry_run) if client == "muse"
                         else setup.install_plugin(client, binary, dry_run=dry_run))
            if dry_run:
                continue
            root, reported = installed_root(client, binary)
            problems = [f"reports {reported or 'nothing'}, not {version}"] if reported != version else []
            problems += tree_differences(repo, f"v{version}", root) if root else ["reports no installed folder"]
        except setup.SetupError as exc:
            problems = [str(exc)]
        if problems:
            lines.append(f"{client}: NOT verified: " + "; ".join(problems[:6]))
        else:
            verified[client] = root
            lines.append(f"{client}: verified, the installed files at {root} equal v{version}")
    return lines, verified, found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="release.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", type=Path, default=REPO)
    parser.add_argument("--clients", default="claude,codex,muse")
    parser.add_argument("--install-only", action="store_true", help="install and verify the tag HEAD carries")
    parser.add_argument("--dry-run", action="store_true", help="check and print the plan; change nothing")
    parser.add_argument("--session", default="", help="this session's id (default: the harness's own)")
    args = parser.parse_args(argv)
    repo, clients = args.repo_root.resolve(), [c for c in args.clients.split(",") if c in doctor.HARNESSES]
    version, problems = preflight(repo, args.install_only)
    if problems:
        print("refused before publishing anything:\n  " + "\n  ".join(problems))
        return 1
    lines, train = [f"preflight: v{version} ready"], ""
    try:
        if not args.install_only:
            session = args.session or paths.session_id()
            if not session:
                raise setup.SetupError("no session id to hold the release train; run inside a harness or pass --session")
            holders = board.holders(train_path(repo), exclude=session)
            if args.dry_run and holders:
                raise setup.SetupError(f"another release is under way: {holders[0].session} ({holders[0].goal})")
            train = "" if args.dry_run else hold_train(repo, session, version)
            lines += publish(repo, version, args.dry_run)
        installed, verified, found = install_and_verify(repo, version, clients, args.dry_run)
        lines += installed
    except setup.SetupError as exc:
        print("\n".join(lines + [f"stopped: {exc}"] + ([f"the release train ({train}) stays claimed by this "
                                                         "session; fix the cause and rerun"] if train else [])))
        return 1
    if train:
        board.release(args.session or paths.session_id(), [train])
    healthy = True
    if verified and not args.dry_run:
        lines.append(install.install(next(iter(verified.values()))))  # the stable runtime from verified bytes
    print("\n".join(lines), flush=True)
    if verified and not args.dry_run:
        healthy = doctor.main([]) == 0
    complete = args.dry_run or (healthy and found and set(verified) == set(found))
    print(("release complete: " if complete else "release NOT complete: ") + f"v{version}")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())

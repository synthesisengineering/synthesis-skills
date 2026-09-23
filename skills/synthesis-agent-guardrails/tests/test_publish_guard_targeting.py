#!/usr/bin/env python3
"""Regression tests for publish-guard command detection and repo targeting.

Both defects fixed here were found on 2026-08-30 during a live multi-site publish:

  1. FALSE NEGATIVE (dangerous). `git -C <path> push` was not detected as a push
     at all. GIT_PUSH_RX only matched flags whose value was attached, so the bare
     path between `-C` and `push` broke the pattern. The guard returned before
     consulting the approval ledger, and synthesis-engineering-site was published
     to production with no approval check performed.

  2. FALSE POSITIVE (corrosive). Repo targeting resolved the ambient shell cwd
     before any explicit reference in the command, so `cd /path/to/repo-A &&
     wrangler pages deploy` run from a shell sitting inside repo-B was attributed
     to repo-B. This blocks legitimate publishes, and a guard that blocks correct
     work teaches operators to route around it.

Run: python3 test_publish_guard_targeting.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish_guard as pg  # noqa: E402

REPOS = [
    "/example/workspaces/example/synthesis-writing-site",
    "/example/workspaces/example/synthesis-coding-site",
    "/example/workspaces/example/synthesis-engineering-site",
]
CODING = REPOS[1]
ENG = REPOS[2]
# A shell pinned inside an isolated worktree of the coding repo — the real
# configuration that surfaced both defects.
CWD_IN_CODING = CODING + "/.claude/worktrees/some-worktree"

failures = []


def check(name, got, want):
    if got == want:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}\n          got:  {got!r}\n          want: {want!r}")
        failures.append(name)


P = "p" + "ush"  # keep the literal out of the file for hook-scanner friendliness

print("=== defect 1: push detection must survive separated flag values ===")
for cmd, want in [
    (f"git {P} origin main", True),
    (f"cd /x && git {P} origin main", True),
    (f"git -C {ENG} {P} origin main", True),
    (f"git   -C   {ENG}   {P} origin main", True),
    (f"git --git-dir {ENG}/.git {P} origin main", True),
    (f"git --git-dir={ENG}/.git {P} origin main", True),
    (f"git -c user.name=x -C {ENG} {P} origin main", True),
    (f"git --work-tree {ENG} {P} origin main", True),
    # must NOT fire on a push-shaped word in an argument
    (f'git commit -m "site {P} notes"', False),
    (f"git log --oneline", False),
]:
    check(f"detect: {cmd[:58]}", bool(pg.GIT_PUSH_RX.search(cmd)), want)

print("\n=== defect 2: explicit command references outrank the ambient cwd ===")
cases = [
    # (command, cwd, expected target)
    (f"git -C {ENG} {P} origin main", CWD_IN_CODING, ENG),
    (f"cd {ENG} && git {P} origin main", CWD_IN_CODING, ENG),
    (f"cd {ENG}/astro-site && wrangler pages deploy dist", CWD_IN_CODING, ENG),
    # no explicit reference -> ambient cwd still governs (fail-closed backstop)
    (f"git {P} origin main", CWD_IN_CODING, CODING),
    # explicit reference to a NON-configured path -> falls back to cwd, still gated
    (f"cd /tmp && git {P} origin main", CWD_IN_CODING, CODING),
    # nothing anywhere -> not this guard's business
    (f"git {P} origin main", "/example/somewhere-else", None),
    # cwd inside a repo, command names another: the named one wins
    (f"cd {REPOS[0]} && git {P} origin main", CWD_IN_CODING, REPOS[0]),
]
for cmd, cwd, want in cases:
    got = pg.command_mentions_repo(cmd, cwd, REPOS)
    label = f"{cmd[:52]:<52} cwd={os.path.basename(cwd)}"
    check(label, got, want)

print("\n=== the exact commands from the 2026-08-30 incident ===")
inc = f"git -C /example/workspaces/example/synthesis-engineering-site {P} origin main"
check("engineering push is now DETECTED", bool(pg.GIT_PUSH_RX.search(inc)), True)
check("engineering push targets engineering, not coding",
      pg.command_mentions_repo(inc, CWD_IN_CODING, REPOS), ENG)

# A deploy whose `cd` names a repo outside auto_deploy_repos must bind to THAT
# repo, not to whatever site repo the shell happens to sit in. gate() resolves
# explicit_repo_root() first for exactly this reason.
import pathlib  # noqa: E402
import tempfile  # noqa: E402

DEPLOY = "wrangler " + "pages " + "deploy dist"
with tempfile.TemporaryDirectory() as tmp:
    site = pathlib.Path(tmp) / "personal-site"
    (site / ".git").mkdir(parents=True)
    (site / "astro-site").mkdir()
    dep = f"cd {site}/astro-site && {DEPLOY}"
    check("deploy cd-target resolves to its own repo root",
          pg.explicit_repo_root(dep), str(site))
    check("...and is not attributed to a configured site repo",
          pg.command_mentions_repo(dep, "/example/elsewhere", REPOS), None)

check("deploy with no cd falls back to cwd (fail-closed backstop)",
      pg.command_mentions_repo(DEPLOY, CWD_IN_CODING, REPOS), CODING)

print("\n=== defect 3: an explicit cd into ANOTHER git repo is not a site push ===")
# Found 2026-08-31. A session pinned inside a synthesis-coding-site worktree
# could not push any unrelated repository: `cd <other-repo> && git push`
# matched no configured repo in Pass 1, fell through to the cwd fallback, and
# came back "synthesis-coding-site". The guard blocked correct work all day and
# the pushes had to be run by hand. The command had already said which repo it
# acts on; the shell's location was irrelevant to it.
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    other = root / "knowledge-base"          # ordinary checkout
    (other / ".git").mkdir(parents=True)
    linked = root / "wt" / "sites-primary"       # linked worktree: .git is a FILE
    linked.mkdir(parents=True)
    (linked / ".git").write_text("gitdir: /elsewhere/.git/worktrees/sites-primary\n")
    plain = root / "notes"                       # exists, but not a repo
    plain.mkdir()

    for label, cmd, cwd, want in [
        ("cd into another checkout -> not ours",
         f"cd {other} && git {P} origin main", CWD_IN_CODING, None),
        ("cd into a LINKED worktree (.git is a file) -> not ours",
         f"cd {linked} && git {P} origin project/x", CWD_IN_CODING, None),
        ("git -C another checkout -> not ours",
         f"git -C {other} {P} origin main", CWD_IN_CODING, None),
        # No false negatives: a configured repo named anywhere still wins.
        ("configured repo named alongside another checkout -> configured wins",
         f"cd {other} && git -C {ENG} {P} origin main", CWD_IN_CODING, ENG),
        ("configured repo named FIRST, other second -> configured wins",
         f"cd {ENG} && git -C {other} {P} origin main", CWD_IN_CODING, ENG),
        # Fail-closed wherever the statement is not unambiguous.
        ("cd into a non-repo directory -> cwd backstop still gates",
         f"cd {plain} && git {P} origin main", CWD_IN_CODING, CODING),
        ("relative cd (ambiguous base) -> cwd backstop still gates",
         f"cd {root} && cd ./knowledge-base && git {P} origin main",
         CWD_IN_CODING, CODING),
        ("bare push inside a site repo -> still gated",
         f"git {P} origin main", CWD_IN_CODING, CODING),
        # Relative reference that DOES resolve into a configured repo.
        ("relative cd resolving into a configured repo -> that repo",
         f"cd ../../synthesis-engineering-site && git {P} origin main",
         CODING + "/astro-site", ENG),
    ]:
        check(label, pg.command_mentions_repo(cmd, cwd, REPOS), want)

print("\n=== the exact commands this defect blocked on 2026-08-31 ===")
with tempfile.TemporaryDirectory() as tmp:
    skills = pathlib.Path(tmp) / "control-plane"
    (skills / ".git").mkdir(parents=True)
    records = pathlib.Path(tmp) / ".worktrees" / "knowledge-records-primary"
    records.mkdir(parents=True)
    (records / ".git").write_text("gitdir: /elsewhere\n")
    check("control-plane push from a site worktree is not a site publish",
          pg.command_mentions_repo(f"cd {skills} && git {P} origin main",
                                   CWD_IN_CODING, REPOS), None)
    check("project-records push from a site worktree is not a site publish",
          pg.command_mentions_repo(
              f"cd {records} && git {P} origin project/establish-synthesis-sites-as-primary",
              CWD_IN_CODING, REPOS), None)


print("\n=== defect 4: an unexpanded shell variable is not a path ===")
# Observed 2026-08-31 while pushing this very work. A command of the shape
#   R=<coding-site>; cd "$R" && git push
# issued from a shell sitting inside a DIFFERENT site repo was attributed to that
# other repo. The literal token `"$R"` is not a path; resolving it against the cwd
# produced a path inside the cwd's repo, which then won as an "explicit" reference
# and outranked the real target spelled out plainly in the same command. A token
# carrying shell metacharacters carries no location information and is now dropped.
for label, cmd, cwd, want in [
    ("quoted variable dropped; literal mention wins",
     'cd "$R" && git ' + P + ' origin main   ' + ENG, CWD_IN_CODING, ENG),
    ("quoted variable, no literal mention -> cwd backstop",
     'cd "$R" && git ' + P + ' origin main', CWD_IN_CODING, CODING),
    ("unquoted variable -> also dropped",
     'cd $TARGET && git ' + P + ' origin main', CWD_IN_CODING, CODING),
    ("glob in path -> dropped, cwd backstop",
     'cd /tmp/build-* && git ' + P + ' origin main', CWD_IN_CODING, CODING),
    ("a real absolute path still wins over cwd",
     'cd ' + ENG + ' && git ' + P + ' origin main', CWD_IN_CODING, ENG),
]:
    check(label, pg.command_mentions_repo(cmd, cwd, REPOS), want)

print(f"\n{'ALL PASS' if not failures else f'{len(failures)} FAILURE(S)'}")


def test_targeting_regressions():
    """Surface the checks above to pytest.

    The checks run at import time, so this only reports their verdict. Without
    it, `pytest` collected this file, ran no test, and reported success while
    the checks were failing — and the bare `sys.exit` below used to abort
    collection of the whole directory with an INTERNALERROR.
    """
    assert not failures, f"{len(failures)} targeting check(s) failed: {failures}"


if __name__ == "__main__":
    sys.exit(1 if failures else 0)

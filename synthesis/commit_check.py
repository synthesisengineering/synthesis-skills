"""Git pre-commit check (R2.1, R3.3): secrets, unapproved disclosures, other sessions' claims.

Installed as the global pre-commit hook (core.hooksPath). A global hooks path
makes git skip every repository's own hooks, so after its own checks this runs
them (E37): the repository's `.githooks/pre-commit` delegate, then its
`.git/hooks/pre-commit`, each once and never itself. A repository that declares
`.githooks/required` (on disk, or still in the index being committed, E38)
refuses the commit when its delegate is missing or not executable.
"""

import os
import re
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CREDENTIALS = {
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
    "GitHub token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    "Anthropic key": r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",
    "OpenAI key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
}
HOOK = os.environ.get("SYNTHESIS_GIT_HOOK", "pre-commit")  # pre-merge-commit sets this
# Holds the git directory whose commit was already checked, so a repository hook that calls the
# synthesis check again returns at once, while a commit in another repository is still checked.
CHAINED = "SYNTHESIS_COMMIT_CHECKED"


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def staged_paths():
    out = _git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").stdout
    return [p for p in out.split("\0") if p]


def added_lines():
    """(path, line) for every added line in the staged diff."""
    current, found = "", []
    for line in _git("diff", "--cached", "-U0", "--no-color").stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            found.append((current, line[1:]))
    return found


def strict_repo(config):
    url = _git("remote", "get-url", "origin").stdout.strip()
    return any(re.search(p, url) for p in config.get("disclosure", {}).get("strict_remotes", []))


def problems(config, session_id, repo_root):
    from synthesis import board

    found = []
    lines = added_lines()
    for path, line in lines:
        for name, pattern in CREDENTIALS.items():
            if re.search(pattern, line):
                found.append(f"{path}: looks like a {name}; remove it and rotate it if it was real")
    if strict_repo(config):
        for rule in config.get("disclosure", {}).get("patterns", []):
            for path, line in lines:
                if re.search(rule["pattern"], line, re.IGNORECASE):
                    found.append(f"{path}: unapproved disclosure ({rule.get('name', rule['pattern'])}) in a public repo")
    for rel in staged_paths():
        holders = board.holders(os.path.join(repo_root, rel), exclude=session_id)
        if holders:
            h = holders[0]
            found.append(f"{rel}: inside a claim held by {h.session} ({h.project or '-'}: {h.goal or 'no goal'})")
    return found


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def repository_hooks(repo_root, common_dir, running):
    """(hooks to run, problem): the repository's own pre-commit hooks, minus the one running now."""
    delegate = os.path.join(repo_root, ".githooks", HOOK)
    declared = os.path.lexists(os.path.join(repo_root, ".githooks", "required")) or _git(
        "-C", repo_root, "ls-files", "--error-unmatch", "--", ".githooks/required").returncode == 0
    if declared:  # an unstaged rm leaves the declaration in the index; a staged `git rm` withdraws it
        if not os.path.lexists(delegate):
            return [], ".githooks/required is declared but .githooks/pre-commit is missing: create it as an executable file and commit it beside the marker"
        if not os.path.isfile(delegate):
            return [], ".githooks/required is declared but .githooks/pre-commit is not a regular file: replace it with an executable file"
        if not os.access(delegate, os.X_OK):
            return [], ".githooks/required is declared but .githooks/pre-commit is not executable: run chmod +x .githooks/pre-commit"
    chain = []
    for hook in (delegate, os.path.join(common_dir, "hooks", HOOK)):
        if not os.path.isfile(hook) or any(_same(hook, h) for h in [running] + chain):
            continue
        if os.access(hook, os.X_OK):
            chain.append(hook)
        else:
            print(f"synthesis commit check: skipped {hook}: not executable"
                  + (" (add .githooks/required to make this an error)" if hook == delegate else ""), file=sys.stderr)
    return chain, None


def main(argv=None):
    from synthesis import paths

    where = _git("rev-parse", "--show-toplevel", "--absolute-git-dir", "--git-common-dir", "--git-path", f"hooks/{HOOK}")
    lines = where.stdout.splitlines()
    if where.returncode != 0 or len(lines) != 4:
        print(f"synthesis commit check: cannot locate the repository ({where.stderr.strip()}); commit blocked", file=sys.stderr)
        return 1
    repo_root, git_dir, common_dir, running = lines[0], lines[1], os.path.abspath(lines[2]), os.path.abspath(lines[3])
    if os.environ.get(CHAINED) == git_dir:  # a repository hook called the check again: already done
        return 0
    try:
        config = paths.config()
    except (OSError, ValueError) as exc:
        print(f"synthesis commit check: config unreadable ({exc}); commit blocked", file=sys.stderr)
        return 1
    found = problems(config, paths.session_id(), repo_root)
    chain, problem = repository_hooks(repo_root, common_dir, running)
    found += [problem] if problem else []
    if found:
        print("synthesis commit check refused this commit:\n  " + "\n  ".join(found), file=sys.stderr)
        return 1
    for hook in chain:
        code = subprocess.run([hook, *(sys.argv[1:] if argv is None else argv)], env={**os.environ, CHAINED: git_dir}).returncode
        if code != 0:
            print(f"synthesis commit check: the repository's own hook {hook} refused this commit (exit {code})", file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())

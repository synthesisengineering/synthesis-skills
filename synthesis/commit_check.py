"""Git pre-commit check (R2.1, R3.3): secrets, unapproved disclosures, other sessions' claims.

Installed as the global pre-commit hook; it then runs the repository's own
pre-commit hook, if it has one, so per-repo checks still apply.
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


CHAINED = "SYNTHESIS_COMMIT_CHECKED"


def main():
    from synthesis import paths

    if os.environ.get(CHAINED) == "1":  # re-entered through the repository's own hook: already checked
        return 0
    repo_root = _git("rev-parse", "--show-toplevel").stdout.strip()
    try:
        config = paths.config()
    except (OSError, ValueError) as exc:
        print(f"synthesis commit check: config unreadable ({exc}); commit blocked", file=sys.stderr)
        return 1
    found = problems(config, paths.session_id(), repo_root)
    if found:
        print("synthesis commit check refused this commit:\n  " + "\n  ".join(found), file=sys.stderr)
        return 1
    local = os.path.join(_git("rev-parse", "--git-common-dir").stdout.strip() or ".git", "hooks", "pre-commit")
    if os.access(local, os.X_OK):
        return subprocess.run([local], env={**os.environ, CHAINED: "1"}).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())

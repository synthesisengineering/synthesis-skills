---
name: synthesis-git-hooks
description: "Commit-time protection: blocks credentials, private keys and credential files in every repo, and unapproved disclosures where outsiders read it (class read from push remotes, with a disclosure ledger). Use to install, configure or debug the commit check, or when a commit is refused."
license: "Apache-2.0"
depends_on: ["synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Git Hooks

One global `core.hooksPath` sends git's pre-commit, pre-merge-commit and commit-msg hooks in every repository on the machine through `synthesis/commit_check.py`. It refuses credentials everywhere, refuses unapproved disclosures where outsiders read the repository, refuses commits into another session's claim, and then runs the repository's own hooks. The rules live in code that runs outside the model, so they hold under load.

## Binding rules

1. **Fail closed.** A policy, ledger, board or diff the check can't read with certainty blocks the commit and says why. Protection that fails open manufactures false confidence (2026-07-28: commits passed unscanned when one interpreter lacked a YAML package).
2. **Never `git commit --no-verify`** without the principal's explicit approval for that commit. Fix a false positive at its source, the policy or the checker, at equal strength.
3. **Credentials block in every repository,** before any path exclusion or allowlist line, and wherever they move. A private key is a key header followed by key body lines; a header alone (a detection rule, a doc example) passes.
4. **The class follows the publication surface,** read from the push remotes at every commit: strict, public-surface or personal. Any strict remote, no remote, or no match means strict; mixed remotes take the stricter class.
5. **Public-surface repositories allow only ledgered names.** A ledger entry needs evidence and may subtract only an identity pattern; a missing or unparsable ledger blocks commits there.
6. **Commit messages stay generic** in strict and public-surface repositories, with no ledger allowance: every real public-repo leak a history audit found came through a message (2025-12-21).
7. **Moved text is not new.** A disclosure line that already exists, whole, in HEAD passes; a new one blocks.
8. **Repository hooks are additive.** The check runs a repository's `.githooks/<hook>` and `.git/hooks/<hook>` after its own; never delete one as redundant. `.githooks/required` makes a missing or non-executable delegate block.
9. **Claims hold at the commit.** A staged path, either side of a rename, inside another live session's claim is refused. No board on the machine advises; a board that can't be read blocks.
10. **Protection is verified, not assumed.** On a new Mac, install the hooks and run `synthesis doctor` before the first commit.

## Contents

- **Procedure**, then **When to apply, and when not** (below): install, configure, check a class, act on a refusal.
- [references/policy-file.md](references/policy-file.md): every policy key, the YAML subset, the `config.json` keys, the ledger contract. Read when writing or changing a policy or ledger.
- [references/scanning.md](references/scanning.md): what the check reads and how: the byte-safe diff, bounds, keys, credential file names, moved lines, messages, claims, the hook chain, each with its test. Read when a refusal surprises you.
- [references/tier-classification.md](references/tier-classification.md): how push remotes become the class, with examples. Read when a repository classifies unexpectedly.
- [references/threat-model.md](references/threat-model.md): why two tiers, what each protects, what the check does not protect against. Read when deciding which tier a pattern belongs in.
- [references/per-repo-overrides.md](references/per-repo-overrides.md): repository hooks, `.githooks/required`, `SYNTHESIS_REPO_CLASS`, allowlist lines. Read when a repository needs a rule the global policy can't express.
- [references/coverage-map.md](references/coverage-map.md): where every part of 2.8.4 lives now (ruling D8).
- [references/preserved.md](references/preserved.md): what was not kept and why, with the 2.8.4 text verbatim. Read only to review the cut.

## Procedure

1. **Install** with the runtime: `python3 -S <plugin>/synthesis/install.py --git-hooks`. It writes `~/.synthesis/v5/git-hooks/{pre-commit,pre-merge-commit,commit-msg}` and points the global `core.hooksPath` there, recording the value it replaced so `install.py uninstall` can restore it. `synthesis doctor` then shows `git hooks: core.hooksPath -> ~/.synthesis/v5/git-hooks`.
2. **Configure.** Copy [git-hook-config.example.yaml](git-hook-config.example.yaml) somewhere private, fill it in, and set `"commit_policy": "<path>"` in `~/.synthesis/v5/config.json` (and `"disclosure_ledger"` to override the ledger path the policy names). Without a policy the check still refuses credentials, keys, credential file names and claimed paths.
3. **Check a repository's class:** from inside it, `python3 -S ~/.synthesis/v5/current/synthesis/commit_check.py --classify` prints `strict`, `public-surface` or `personal`. `git remote -v | awk '/\(push\)/ {print $2}'` shows the remotes it read.
4. **When a commit is refused,** git exits non-zero and nothing was committed. The message names each finding:

   ```text
   synthesis commit check refused this commit (strict repository):
     notes/kickoff.md:3: Kickoff with <name>  <- unapproved disclosure for this repository's audience
   ```

   A credential: remove it, and rotate it if it was real. A disclosure: remove or generalize it; only the principal adds a ledger entry, with evidence, for a name they have published. A message: reword it generically (no names, codenames, rationale or timing). A claim: `synthesis who`, then `synthesis msg <holder> "..."`. The policy can't be read: fix the file it names; never point the config away from it.
5. **A false positive** in tier 1: a reviewed `allowlist_lines` entry for the legitimate context, or a `diff_exclude_paths` entry for a file whose purpose is the pattern catalog. In tier 0: fix the checker in synthesis-skills with a test. Never weaken a pattern to get one commit through.
6. **New machine or drift:** `synthesis doctor`; if `core.hooksPath` points elsewhere, rerun step 1.

## When to apply, and when not

- Setting up a new workstation as part of the synthesis-engineering install
- Auditing a system where false positives are driving repeated `--no-verify` bypasses
- Adopting synthesis engineering as a team (the policy schema is per-user; the engine is shared)

Not for: one-off scripts or throwaway repos where policy infrastructure is overkill; environments where you genuinely need to commit credentials (very rare; almost always indicates a missing secrets store); CI/CD pipelines that run their own credential-leak scanners (the pre-commit is a developer-side layer; CI/CD-side scanning is a complementary, not redundant, control).

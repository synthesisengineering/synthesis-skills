# Tier classification

How `git remote -v` becomes the repo's class, and what that means for the active pattern set.

## The classifier

The commit check reads every URL marked as a push remote:

```bash
git remote -v | awk '/\(push\)/ {print $2}'
```

It decides strict-first, matching patterns case-insensitively:

1. Any push remote matches `strict_repo_patterns`, or there is no push remote: `strict`.
2. Every push remote matches `public_surface_patterns`: `public-surface`. Some but not all
   match: `strict` (escalation, never demotion through a broad personal pattern).
3. Every push remote matches `personal_remote_patterns`: `personal`.
4. Anything else: `strict`.

Empty remote list (e.g., `git init` with no upstream yet) classifies as `strict` — the safe default.

To see the result for a repository, run from inside it:
`python3 -S ~/.synthesis/v5/current/synthesis/commit_check.py --classify`.

## Examples

Given this config:

```yaml
personal_remote_patterns:
  - '[:/]YOUR-PERSONAL-ORG/'
public_surface_patterns:
  - '[:/]YOUR-PERSONAL-ORG/your-site(\.git)?$'
```

| Push remotes | Class | Reason |
|---|---|---|
| `git@github.com:YOUR-PERSONAL-ORG/some-notes.git` | personal | All push remotes match |
| `git@github.com:YOUR-PERSONAL-ORG/repo-1.git` + `git@github.com:YOUR-PERSONAL-ORG/repo-1-mirror.git` | personal | Both match |
| `git@github.com:YOUR-PERSONAL-ORG/your-site.git` | public-surface | Every push remote is a published surface |
| `git@github.com:public-foundation/upstream.git` | strict | No push remote matches |
| `git@github.com:YOUR-PERSONAL-ORG/repo.git` + `git@github.com:client-org/shared-project.git` | strict | One non-personal push remote suffices |
| `(no remotes)` | strict | Safe default |

## Why every-must-match, not any-may-match

The classification picks the MORE RESTRICTIVE outcome when remotes are mixed. Reason: if even one non-personal remote can receive a push, the content is no longer sole-owner — someone other than you could read it.

The alternative (any-may-match) would relax security as soon as a single personal remote is added, even alongside non-personal ones. That's the wrong direction of failure.

## Effects on the active pattern set

| Class | Diff | Message |
|---|---|---|
| `personal` | Tier 0 only | Tier 0 only |
| `public-surface` | Tier 0, plus the `public_surface_groups` of tier 1 minus the ledger's allowances | Tier 0 plus all of tier 1, no allowances |
| `strict` | Tier 0 plus all of tier 1 | Tier 0 plus all of tier 1 |

## Why auto-derive, not declare

This was a deliberate design choice. The five-mode analysis (in the design-rationale artifact) walks through alternatives. The summary:

| Approach | Failure mode |
|---|---|
| Per-repo flag file (`.githooks/sole-owner`) | Silent erosion if the file persists after the repo's profile changes |
| Auto-detect from remotes | None equivalent — remote changes propagate to security profile immediately |

Auto-derivation has no "did I add the flag file?" ritual. New sole-owner repos classify correctly on first commit. Repos that gain a collaborator's remote tighten automatically.

The remote configuration IS the security profile. Anything else is a shadow that can drift.

- **Single source of truth.** A flag file is a SHADOW of the real security profile (the remotes). Two sources of truth drift; one doesn't.
- **No silent erosion.** If a repo's profile changes (a new collaborator's remote is added), auto-detect tightens immediately. A flag file would stay relaxed even after reality changed.
- **Zero per-repo ritual.** A new sole-owner repo classifies correctly on its first commit. No "did I add the flag file?" checklist.
- **Self-documenting.** `git remote -v` is one command; the classification logic is one regex match against URLs.

Counter-analogy from CSP allowlists (which ARE static for adversarial reasons): doesn't apply here. The user isn't adversarial against themselves, and no third party can manipulate the remote set.

## Edge cases

### A repo with no remote

Classifies as `strict`. The safe default for a fresh `git init` or a repo where the user hasn't yet configured the upstream. Once the user adds remotes, the next commit re-evaluates.

### A repo with a mirror remote

If the mirror is in your personal namespace, both URLs match → personal. If the mirror is on a different host (e.g., bitbucket alongside github), the mirror URL must also be in `personal_remote_patterns` for the repo to classify as personal.

For example, a self-hosted git server needs its own pattern beside the GitHub one:

```yaml
personal_remote_patterns:
  - '[:/]YOUR-PERSONAL-ORG/'              # GitHub user
  - 'git\.your-domain\.com:YOUR-NAME/'    # self-hosted
```

### A monorepo with submodules

The classification is per-repo, not per-submodule. Submodule repos are evaluated independently when their own pre-commit fires. Each submodule's remote set determines its own class.

### Working in a clone where you don't own the upstream

If you've cloned a repo you don't own (e.g., a public project for which you're preparing a PR), the `origin` push remote will point to the original org or a fork. The classification depends on the URL. PRs to non-personal repos: strict (correct — you don't want to leak credentials or client names into a public-facing PR).

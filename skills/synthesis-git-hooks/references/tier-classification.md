# Tier classification

How `git remote -v` becomes the repo's class, and what that means for the active pattern set.

## The classifier

The sidecar `_load_config.py` runs `git remote -v` and extracts every URL marked as a push remote:

```bash
git remote -v | awk '/\(push\)/ {print $2}'
```

It compares each URL against the regexes in `personal_remote_patterns`. If **every** URL matches at least one pattern, the repo classifies as `personal`. Otherwise `strict`.

Empty remote list (e.g., `git init` with no upstream yet) classifies as `strict` — the safe default.

## Examples

Given this config:

```yaml
personal_remote_patterns:
  - '[:/]rajivpant/'
```

| Push remotes | Class | Reason |
|---|---|---|
| `git@github.com:YOUR-PERSONAL-ORG/some-notes.git` | personal | All push remotes match |
| `git@github.com:YOUR-PERSONAL-ORG/repo-1.git` + `git@github.com:YOUR-PERSONAL-ORG/repo-1-mirror.git` | personal | Both match |
| `git@github.com:public-foundation/upstream.git` | strict | No push remote matches |
| `git@github.com:YOUR-PERSONAL-ORG/repo.git` + `git@github.com:client-org/shared-project.git` | strict | One non-personal push remote suffices |
| `(no remotes)` | strict | Safe default |

## Why every-must-match, not any-may-match

The classification picks the MORE RESTRICTIVE outcome when remotes are mixed. Reason: if even one non-personal remote can receive a push, the content is no longer sole-owner — someone other than you could read it.

The alternative (any-may-match) would relax security as soon as a single personal remote is added, even alongside non-personal ones. That's the wrong direction of failure.

## Effects on the active pattern set

```python
# Pseudocode from _load_config.py
active_patterns = flatten(tier_0_always)
if repo_class == "strict":
    active_patterns += flatten(tier_1_strict_only)
active_regex = "|".join(deduplicate(active_patterns))
```

In `personal` mode: ~12 patterns (8 API-key signatures + 4 private-key markers).

In `strict` mode: ~12 + the Tier 1 set (financial 4, HR 5, confidentiality 3, plus your client names, private skill names, internal URLs — typically 30-50 patterns total).

The single regex is then `grep -E`'d against the staged diff.

## Why auto-derive, not declare

This was a deliberate design choice. The five-mode analysis (in the design-rationale artifact) walks through alternatives. The summary:

| Approach | Failure mode |
|---|---|
| Per-repo flag file (`.githooks/sole-owner`) | Silent erosion if the file persists after the repo's profile changes |
| Auto-detect from remotes | None equivalent — remote changes propagate to security profile immediately |

Auto-derivation has no "did I add the flag file?" ritual. New sole-owner repos classify correctly on first commit. Repos that gain a collaborator's remote tighten automatically.

The remote configuration IS the security profile. Anything else is a shadow that can drift.

## Edge cases

### A repo with no remote

Classifies as `strict`. The safe default for a fresh `git init` or a repo where the user hasn't yet configured the upstream. Once the user adds remotes, the next commit re-evaluates.

### A repo with a mirror remote

If the mirror is in your personal namespace, both URLs match → personal. If the mirror is on a different host (e.g., bitbucket alongside github), the mirror URL must also be in `personal_remote_patterns` for the repo to classify as personal.

For example, a self-hosted git server at `git.your-domain.com:rajiv/...` requires a regex like `[:/]rajiv/` AND a host match in `personal_remote_patterns`:

```yaml
personal_remote_patterns:
  - '[:/]rajivpant/'        # GitHub user
  - 'git\.your-domain\.com:rajiv/'  # self-hosted
```

### A monorepo with submodules

The classification is per-repo, not per-submodule. Submodule repos are evaluated independently when their own pre-commit fires. Each submodule's remote set determines its own class.

### Working in a clone where you don't own the upstream

If you've cloned a repo you don't own (e.g., a public project for which you're preparing a PR), the `origin` push remote will point to the original org or a fork. The classification depends on the URL. PRs to non-personal repos: strict (correct — you don't want to leak credentials or client names into a public-facing PR).

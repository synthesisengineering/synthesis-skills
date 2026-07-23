---
name: synthesis-git-hooks
description: "Deterministic pre-commit policy for the synthesis-engineering workflow. Auto-classifies each repo by its push remotes (personal vs strict), applies a tiered pattern set: Tier 0 credentials always; Tier 1 financial / HR / confidentiality / client names only in strict repos. YAML-driven policy lives in ~/.synthesis/git-hook-config.yaml. Use when asked to: install git hooks, configure pre-commit policy, prevent credential leaks, prevent confidential-name leaks in public repos, set up the synthesis-engineering enforcement layer."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Git Hooks

A YAML-driven pre-commit policy engine. Part of the synthesis-engineering operational layer — deterministic enforcement that catches credential leaks and exposure-sensitive content at the commit boundary, before the diff persists.

The engine is small (one bash script + one Python sidecar). The policy is data — a YAML file at `~/.synthesis/git-hook-config.yaml` that anyone adopting synthesis engineering fills in with their own personal-remote patterns, client names, and internal URLs.

## What this enforces

| Tier | Patterns | When applied |
|---|---|---|
| **Tier 0 — credentials** | API keys (AWS, OpenAI, Anthropic, Google, GitHub, GitLab, Slack), private key markers (RSA, OpenSSH, EC, PGP) | Every repo. Credentials don't belong in git regardless of who reads. |
| **Tier 1 — exposure-sensitive** | Financial, HR/employment, confidentiality markers, confidential client/company names, private skill names, internal URLs | Skip when the repo classifies as `personal` (every push remote matches a configured `personal_remote_patterns` regex). Run otherwise. |

The classification is derived from `git remote -v` on every commit — no per-repo flag file, no static declaration, no drift potential. The remote configuration IS the security profile.

## When to apply

- Setting up a new workstation as part of the synthesis-engineering install
- Auditing a system where false positives are driving repeated `--no-verify` bypasses
- Adopting synthesis engineering as a team (the policy schema is per-user; the engine is shared)

## When NOT to apply

- One-off scripts or throwaway repos where policy infrastructure is overkill
- Environments where you genuinely need to commit credentials (very rare; almost always indicates a missing secrets store)
- CI/CD pipelines that run their own credential-leak scanners (the pre-commit is a developer-side layer; CI/CD-side scanning is a complementary, not redundant, control)

## Install

```bash
# 1. Install this skill into ~/.claude/skills/ (or equivalent for your agent)
npx skills add synthesisengineering/synthesis-skills --skill synthesis-git-hooks --copy

# 2. Run the install script — copies the engine to ~/.synthesis/git-hooks/,
#    sets git's core.hooksPath, and seeds an initial config from the template.
~/.claude/skills/synthesis-git-hooks/scripts/install.sh

# 3. Edit ~/.synthesis/git-hook-config.yaml with YOUR personal-remote patterns
#    (your GitHub user/org), confidential names, internal URLs.
```

After install, every `git commit` on the workstation runs the policy. No per-repo configuration needed; classification is automatic from each repo's push remotes.

## Verifying classification for any repo

```bash
cd <repo>
~/.synthesis/git-hooks/_load_config.py --classify
# → personal | strict
```

Inspect the underlying remotes:

```bash
git remote -v | awk '/\(push\)/ {print $2}'
```

## Override path / bypass

| Need | Mechanism |
|---|---|
| Use a different config file for one invocation | `SYNTHESIS_GIT_HOOK_CONFIG=/path/to/custom.yaml git commit ...` |
| Skip the hook once (last resort) | `git commit --no-verify` |
| Add a legitimate match to the allowlist | Add a regex to `allowlist_lines` in the config |
| Add a new personal org (sole-owner repos there) | Add a regex to `personal_remote_patterns` in the config |

The `--no-verify` escape valve is genuine, but each use weakens the discipline. If a pattern fires repeatedly as a false positive, fix the underlying signal: rename the variable, extend `allowlist_lines`, or — if the repo really is sole-owner — add the right `personal_remote_patterns` entry.

## Repo-local hooks are additive, not superseded

If a repo has its own `.githooks/pre-commit` (version-controlled, executable), this engine **chains to it** — runs its own Tier-0/Tier-1 pass first, then `exec`s the repo-local hook. It does not replace or subsume it.

This matters because it's easy to assume the opposite: "the global hook already covers confidentiality, so the repo-local one is redundant — delete it." That assumption is wrong and removes protection rather than deduplicating it. A repo-local hook typically exists because the repo needs a check the global config can't express safely — for example, a repo whose whole purpose is documenting a specific client relationship needs `personal`-class handling (so the client's own name isn't flagged as a leak) while still blocking a different category the global patterns don't cover, like engagement financials or a partner's personnel names. Verify what a repo-local hook actually checks before assuming it's covered elsewhere, and don't delete it as part of unrelated cleanup.

## Why auto-derive instead of per-repo flag files

The classification could have been a per-repo flag file (`.githooks/sole-owner` or similar). It isn't. Reasons:

- **Single source of truth.** A flag file is a SHADOW of the real security profile (the remotes). Two sources of truth drift; one doesn't.
- **No silent erosion.** If a repo's profile changes (a new collaborator's remote is added), auto-detect tightens immediately. A flag file would stay relaxed even after reality changed.
- **Zero per-repo ritual.** A new sole-owner repo classifies correctly on its first commit. No "did I add the flag file?" checklist.
- **Self-documenting.** `git remote -v` is one command; the classification logic is one regex match against URLs.

Counter-analogy from CSP allowlists (which ARE static for adversarial reasons): doesn't apply here. The user isn't adversarial against themselves, and no third party can manipulate the remote set.

## Reciprocal layers in the synthesis-engineering enforcement stack

This skill is one of four deterministic-enforcement layers. Each runs at a different point in the agentic workflow:

| Layer | What it enforces | Trigger |
|---|---|---|
| `synthesis-anti-shortcuts` | Costume-vocabulary detection in agent outputs | Stop hook + PreToolUse hook |
| (agent-rules sync) | Single source of truth for CLAUDE.md / AGENTS.md / ~/.codex/AGENTS.md | PostToolUse hook on edits |
| **`synthesis-git-hooks` (this skill)** | **Credential + exposure-sensitive pattern check at commit boundary** | **pre-commit** |
| `synthesis-repo-guard` | Uncommitted changes + unpushed commits | Session-end skill |

The discipline isn't a prompt the agent has to remember — it's a runtime check the agent can't route around. This is the differentiator from vibe coding / agentic coding / spec-driven development: methodology becomes runtime infrastructure, not a Markdown file the agent may or may not consult.

## Files in this skill

```
synthesis-git-hooks/
├── SKILL.md                          # this file
├── scripts/
│   ├── pre-commit                    # bash engine — wired via core.hooksPath
│   ├── _load_config.py               # YAML→regex sidecar
│   ├── install.sh                    # idempotent installer
│   └── git-hook-config.example.yaml  # template config (adopters customize)
└── references/
    ├── threat-model.md               # why two tiers; what each tier protects
    ├── tier-classification.md        # how `git remote -v` becomes the class
    └── per-repo-overrides.md         # delegation to repo-local .githooks
```

## Companion artifacts

- Design rationale (full five-mode analysis) will be published in the synthesis-engineering blog series.
- Operational lesson on the recurring infrastructure-design shortcut pattern that prompted this redesign — included as a reference in the `synthesis-anti-shortcuts` skill.

## License

Apache-2.0. Engine and scripts may be used, modified, and redistributed under the terms of the LICENSE-APACHE file at the root of the synthesis-skills repository.

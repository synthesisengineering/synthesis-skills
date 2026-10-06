# The commit policy file

The policy is data: a YAML file the principal writes and keeps private, named by
`commit_policy` in `~/.synthesis/v5/config.json`. The engine is public; the policy holds
personal-remote patterns, client names and internal URLs. The shipped template is
[git-hook-config.example.yaml](../git-hook-config.example.yaml).

## Contents

- [config.json keys](#configjson-keys)
- [What this enforces](#what-this-enforces)
- [Policy keys](#policy-keys)
- [Pattern dialect](#pattern-dialect)
- [The YAML subset](#the-yaml-subset)
- [The disclosure ledger](#the-disclosure-ledger)
- [Common changes](#common-changes)
- [Keys the v5 check ignores](#keys-the-v5-check-ignores)

## config.json keys

| Key | Meaning |
|---|---|
| `commit_policy` | Path to the policy YAML (`~` allowed). Absent: only credentials, private keys, credential file names and claims are checked. Present but missing, unreadable or invalid: every commit blocks until it is fixed. |
| `disclosure_ledger` | Optional. Path to the disclosure ledger; overrides the policy's own `disclosure_ledger`. |
| `line_allowances` | Optional. Path to the lines the principal approved ([scanning.md](scanning.md#approved-lines)); default `line-allowances.json` beside the policy. Missing: no line is approved yet. Present but unreadable: every commit where exposure patterns apply blocks until it is repaired. Keep it where the policy lives, so it travels to every Mac with the policy. |

A 2.x policy and ledger carry over unchanged: point these keys at the files where they
already are. The v5 reader parses them exactly as the 2.x loader did.

## What this enforces

| Tier | Patterns | When applied |
|---|---|---|
| **Tier 0 — credentials** | API keys (AWS, OpenAI, Anthropic, Google, GitHub, GitLab, Slack), private key markers (RSA, OpenSSH, EC, PGP, generic and encrypted PKCS#8) | Every repo. Credentials don't belong in git regardless of who reads. |
| **Tier 1 — exposure-sensitive** | Financial, HR/employment, confidentiality markers, confidential client/company names, private skill names, internal URLs | Skip when the repo classifies as `personal`. Run in `strict` and `public-surface` repos — in `public-surface`, minus only the exact name patterns the disclosure ledger records as published precedent. |

Tier 0 is the check's built-in credential list plus the policy's `tier_0_always`
patterns. A private-key header on a line is left to the key rule (a header followed by
key body lines, see [scanning.md](scanning.md#private-keys)) whatever pattern names it, so
the marker literals in `tier_0_always.private_key_markers` never block a bare header; any
other expression matches unconditionally. Vendors' published example keys pass by exact
value; nothing else in tier 0 is approvable.

Classification is derived from `git remote -v` on every commit and follows
the PUBLICATION SURFACE, strict-first:

1. **`strict`** — ANY push remote matches `strict_repo_patterns` (public OSS
   repos pinned strict even under a personal org), the remote list is empty,
   or nothing else matches. Full Tier 1, commit-message scan on.
2. **`public-surface`** — EVERY push remote matches
   `public_surface_patterns`: sites and other surfaces whose content the
   user personally authors and publishes, regardless of repository
   visibility. Full Tier 1 minus ledger allowances; commit-message scan on.
3. **`personal`** — EVERY push remote matches `personal_remote_patterns`:
   content only the user reads. Tier 0 only.

A repository whose remotes match a public surface only in part is strict: escalation,
never demotion through a broad personal pattern.

## Policy keys

| Key | Meaning |
|---|---|
| `config_version` | Required, 2 or later. A version-1 file blocks commits: it would silently skip the surface classes and the ledger. |
| `personal_remote_patterns` | Remote-URL regexes; every push remote matching one makes the repo `personal`. |
| `strict_repo_patterns` | Any push remote matching one makes the repo `strict`. |
| `public_surface_patterns` | Every push remote matching one makes the repo `public-surface`. |
| `disclosure_ledger` | Path to the ledger; read only for public-surface repos. |
| `public_surface_groups` | Which `tier_1_strict_only` groups apply on public surfaces (published surfaces enforce the identity boundary, not private-notes vocabulary). Absent: every group applies. |
| `ledger_allowance_groups` | Groups a ledger entry may subtract from. Default `confidential_names`: an allowance may subtract who, never what. |
| `ledger_registers` | Registers a ledger entry may declare. Default `biography`. |
| `tier_0_always` | Groups of credential patterns; applied in every repo, to every added line and every message. |
| `tier_1_strict_only` | Groups of exposure patterns: financial, HR, confidentiality markers, names, private skill names, internal URLs. |
| `allowlist_lines` | Regexes matched against an added line with a leading `+` (as git shows it). A match exempts that line from tier 1 only, and never a line with invalid UTF-8. |
| `diff_exclude_paths` | Path regexes (case-sensitive) whose files skip tier 1: files whose purpose is the pattern catalog. Never tier 0; never a path with invalid UTF-8 or a newline. Built in: `.githooks/pre-commit`, `.githooks/extra-patterns.yaml`, `git-hook-config.yaml` and its example, `anti-shortcut-catalog.yaml`, `skills/synthesis-disclosure-policy/`, `skills/synthesis-git-hooks/`, and the policy and ledger files that `commit_policy` and `disclosure_ledger` name, when they live in the repository being committed. |
| `check_commit_message` | Default true. `false` turns off the tier-1 message scan; credentials in messages are still refused. |

## Pattern dialect

Patterns are written for `grep -E`, as the 2.x engine ran them. The check runs them with
Python's `re`, translating POSIX bracket classes such as `[[:space:]]` and `[^[:alnum:]_]`.
Content and remote matching ignore case; path matching does not. Every pattern is
compiled when the policy loads; an empty pattern, a control character (a regex escape
that a double-quoted scalar turned into a literal) or an invalid regex blocks commits
and names the key.

## The YAML subset

The check reads the policy without third-party packages, so any `python3` gives
byte-identical policy. The supported subset is: comments, nested mappings by indentation, quoted/bare string lists, empty sequences as mapping values (`key: []`, including spaces inside the brackets), and scalar values — anything outside it (tabs, nonempty flow sequences, flow mappings, anchors, block scalars) is a **hard parse error that blocks commits** rather than a guess.

Double-quoted scalars are literal text: `"\b"` stays a backslash and a `b`, because
decoding escapes would turn a regex word boundary into a backspace character. The
pattern would still compile and the protection would be dead.

## The disclosure ledger

The ledger records names the principal has personally published, each with evidence; see
the [`synthesis-disclosure-policy`](../../synthesis-disclosure-policy/SKILL.md) skill.
Under `entities:`, each entry carries:

- `evidence`: one or more citations. Precedent without evidence is not precedent; an
  entry without it blocks public-surface commits.
- `registers`: one or more of `ledger_registers` (default `biography`).
- `hook_patterns` (optional): strings that must textually equal entries of an
  allowance group in `tier_1_strict_only`. Exact string equality keeps every allowance
  auditable, with no regex-subsumption reasoning.

A configured ledger that is missing or unparsable fails closed: public-surface commits
block until it is fixed. No per-repo flag file, no static declaration, no drift
potential: the remote configuration plus the ledger IS the security profile.

## Common changes

| Need | Mechanism |
|---|---|
| Add a new personal org (sole-owner repos there) | Add a regex to `personal_remote_patterns` in the config |
| Pin a public repository under a personal org as strict | Add it to `strict_repo_patterns` |
| Let one legitimate Tier-1 line through | The principal approves that line at the commit ([scanning.md](scanning.md#approved-lines)); never reword or split it to get past the check |
| Add a legitimate Tier-1 match to the allowlist | Review a narrow `allowlist_lines` entry; it cannot subtract credentials |
| Allow a name the principal has published, on their own sites | A ledger entry with evidence, whose `hook_patterns` equals the policy's pattern |
| Repeated detector-rule false positive | Preserve the refusal and correct the checker through its source owner, with a test |
| Test the engine against a different policy | `SYNTHESIS_HOME=<scratch>` with its own `config.json` (per-repo-overrides.md) |

A recurring false positive requires a source-owner correction with retained controls. Repository classification, path exclusions and line allowlists do not exempt Tier 0.

## Keys the v5 check ignores

`coordination_board` (v5 claims live on the v5 board and always apply) and
`team_policy_files` (the team-policy layer was cut; no team policy was ever configured).

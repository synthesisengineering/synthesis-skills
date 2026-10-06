# Preserved: synthesis-git-hooks 2.8.4

What 3.0.0 did not carry, and why, followed by the 2.8.4 text verbatim. Nothing here is
an instruction; it is the record of what was cut. Read only to review the cut.

## Contents

- What was not kept, and why
- Lines of 2.x reference files that changed
- The 2.8.4 SKILL.md, verbatim
- references/marker-rules.md, verbatim
- Replaced in the final v5 sweep

## What was not kept, and why

- **The Bash engine and Python sidecars** (`pre-commit`, `commit-msg`, `pre-merge-commit`,
  `_load_config.py`, `_scan_staged.py`): replaced by one stdlib module,
  `synthesis/commit_check.py`, which the v5 install wires as the global hooks. The sidecar's
  OK sentinel guarded a Bash `eval` of Python output; with one process there is nothing to
  eval, and failing closed is the module catching its own errors and exiting 1. The lesson
  behind the sentinel (2026-07-28: an engine that treated "broken" as "nothing to scan")
  is binding rule 1.
- **`install.sh`**: replaced by `install.py --git-hooks`, which records and restores the
  previous `core.hooksPath`. Copying the coordination runtime went with the old board.
- **The pattern-validation cache (2.6.0)**: compiling every pattern in-process takes
  milliseconds; there is no `grep -E` subprocess per pattern to cache.
- **The team-policy layer**: no team policy was ever configured, and team use was not wanted.
- **Drift-source resolution (2.3.0)** and the doctor's source-location heuristics:
  `synthesis doctor` compares the installed runtime with the plugin by content hash.
- **The 2.4.0 coordination receipt chain** (`check-staged`, lease-backed claims, override
  reasons recorded on the board, hash-bound receipts): replaced by the v5 claim check, a
  direct read of the board in `commit_check.py` (scanning.md, Claims).
- **The detection-rule discrimination of marker-rules.md** (YAML and Python rule-syntax
  proofs, captured traditional-diff fragments, blob custody): replaced by one rule, a key
  header blocks only when key body lines follow (scanning.md, Private keys). What it
  protected still holds: an unchanged header with a new body blocks, a quoted or escaped
  key blocks, and a file name or policy-looking path grants no exemption.
- **Exact-copy detection through git's copy heuristics (2.1.2)**: replaced by the moved-text
  rule, which also covers files split into parts and never exempts a credential.
- **The "Reciprocal layers" table**: it described the old anti-shortcut hooks and the
  agent-rules sync, both retired in v5. The enforcement layers now are the PreToolUse
  guards (synthesis-agent-guardrails, synthesis-message-guard), this commit check, and
  the read-only stranded-work scan (synthesis-repo-guard).
- **Plugin install commands (2.1.1)**: the plugin install is documented once, in
  synthesis-onboarding; this skill documents only the hook step.
- **`SYNTHESIS_GIT_HOOK_CONFIG`**: replaced by `commit_policy` in config.json, and by
  `SYNTHESIS_HOME` for engine testing.

## Lines of 2.x reference files that changed

Each block holds the 2.x lines of that file that 3.0.0 rewrote; the rest of the file is
carried verbatim in the new reference of the same name.

### references/per-repo-overrides.md (2.x lines that changed)

```text
The default policy (Tier 0 always + Tier 1 in strict) is read from `~/.synthesis/git-hook-config.yaml` and is sufficient for almost all cases. This reference covers the rare cases where you want a repo to do MORE than the default.
The universal engine at `~/.synthesis/git-hooks/pre-commit` chains to a repo-local hook if one exists:
# Inside the engine, after the universal check passes:
REPO_ROOT=$(git rev-parse --show-toplevel)
REPO_HOOK="$REPO_ROOT/.githooks/pre-commit"
if [ -f "$REPO_HOOK" ] && [ -x "$REPO_HOOK" ]; then
    exec "$REPO_HOOK"
The repo-local hook receives `$SYNTHESIS_REPO_CLASS` (`personal` or `strict`) in its environment, so the repo-local logic can adapt to the same classification the universal engine used.
For one-off testing, set `SYNTHESIS_GIT_HOOK_CONFIG`:
SYNTHESIS_GIT_HOOK_CONFIG=/tmp/test-policy.yaml git commit -m "test"
```

### references/threat-model.md (2.x lines that changed)

```text
Patterns in Tier 0 are LITERAL credential signatures: AWS access key prefix `AKIA…`, OpenAI's `sk-…T3BlbkFJ`, Anthropic's `sk-ant-api…`, Google's `AIza…`, GitHub's `ghp_…`, GitLab's `glpat-…`, Slack's `xoxb-…` / `xoxp-…`, and the standard private-key BEGIN markers (RSA, OpenSSH, EC, PGP). These are designed by the issuers to be regex-detectable — finding them is unambiguous.
When the repo classifies as `personal` — i.e., every push remote points to your personal namespace (e.g., `github.com:rajivpant/...`), AND no other human can push to or pull from the repo. In this state:
```

### references/tier-classification.md (2.x lines that changed)

```text
The sidecar `_load_config.py` runs `git remote -v` and extracts every URL marked as a push remote:
It compares each URL against the regexes in `personal_remote_patterns`. If **every** URL matches at least one pattern, the repo classifies as `personal`. Otherwise `strict`.
  - '[:/]rajivpant/'
```python
# Pseudocode from _load_config.py
active_patterns = flatten(tier_0_always)
if repo_class == "strict":
    active_patterns += flatten(tier_1_strict_only)
active_regex = "|".join(deduplicate(active_patterns))
In `personal` mode: ~12 patterns (8 API-key signatures + 4 private-key markers).
In `strict` mode: ~12 + the Tier 1 set (financial 4, HR 5, confidentiality 3, plus your client names, private skill names, internal URLs — typically 30-50 patterns total).
The single regex is then `grep -E`'d against the staged diff.
For example, a self-hosted git server at `git.your-domain.com:rajiv/...` requires a regex like `[:/]rajiv/` AND a host match in `personal_remote_patterns`:
  - '[:/]rajivpant/'        # GitHub user
  - 'git\.your-domain\.com:rajiv/'  # self-hosted
```

## The 2.8.4 SKILL.md, verbatim

# Synthesis Git Hooks

A YAML-driven pre-commit policy engine. Part of the synthesis-engineering operational layer — deterministic enforcement that catches credential leaks and exposure-sensitive content at the commit boundary, before the diff persists.

The engine is a Bash boundary plus standard-library Python sidecars. The policy
is data — a YAML file at `~/.synthesis/git-hook-config.yaml` that anyone
adopting synthesis engineering fills in with personal-remote patterns, client
names, internal URLs, and optionally a coordination-board path.

## Automatic merge commits

Git's `pre-merge-commit` entry point invokes the same `pre-commit` owner for
clean automatic merge commits. Claims, bound receipts, staged-content scanning
and required repository delegates therefore apply to these merge commits too.
Missing or non-executable commit-owner code refuses the merge. The installer,
runtime payload inventory and doctor include the merge entry point; a missing
or non-executable entry point is an explicit doctor alarm because Git would
otherwise skip it. Conflict resolution completed with `git commit` continues
through `pre-commit`. Fast-forward merges create no commit and do not invoke
this commit boundary.

## Staged bytes and commit-message scanning

The Bash hooks delegate content scanning to the required `_scan_staged.py`
sidecar. It reads Git's declared hunk lengths and decodes Git-quoted destination
paths. Added lines that resemble diff headers remain content. Paths and policy
patterns are passed as arguments and input bytes; neither becomes shell code.
Tier 0 examines all added lines before any path exclusions or line allowlist.
Exact copies retain the existing Git copy-detection semantics.

The policy engine still uses the invoking locale and `grep -E`, including its
Unicode case matching. For invalid UTF-8, the scanner creates a deterministic
replacement-character view for pattern evaluation and binds every matching line
back to its original bytes. Invalid-byte lines cannot gain allowlist exemptions;
invalid-UTF-8 or newline-containing paths cannot gain path exclusions. NUL bytes
do not turn matches into an uninspectable binary-file summary. The same owner
scans commit messages when the selected surface requires that control.

A scan has a 60-second deadline. Staged diff acquisition is limited to 256 MiB,
commit messages to 1 MiB, and displayed evidence to 16 KiB with an explicit
truncation digest. Missing dependencies, malformed diffs, invalid policies,
changing or non-regular message files, and exceeded bounds fail closed. These
limits do not change staged files. Installation, lifecycle reconciliation and
`--doctor` include the new sidecar in their exact runtime dependency inventory.

## v2.6.0 — Cached pattern validation

The sidecar validates the configured pattern set once per config digest and
grep identity and reuses that result on later commits instead of re-running
every pattern through `grep -E` at each commit boundary; a changed config or
grep invalidates the cache. Install writes the cache directory with the
engine. Refusals and surface classes are unchanged.

## v2.5.0 — Required repo-local delegate, fail closed

Global `core.hooksPath` makes this chain the only path to a repository's own
`.githooks/pre-commit`; an absent or mode-644 delegate used to be skipped
silently, so a repository's own commit guards reported success while running
nothing. Declaring `.githooks/required` opts in — declared means the marker
is present in the working tree or listed in the index; content is ignored.
With the declaration, a missing, non-regular, or non-executable delegate (a
symlink is judged by its target) blocks the commit and names the remedy
(`create .githooks/pre-commit` or `chmod +x .githooks/pre-commit`); without
it nothing changes. Withdrawal is a staged `git rm .githooks/required` in a
reviewed commit; an unstaged `rm` leaves the index entry, and the
declaration, standing, unless the commit itself stages the removal
(`git commit -a`, or a partial commit naming `.githooks/required`). The
doctor's `delegate-required` control applies the same rule and reports the
same verdict.

## v2.4.0 — Coordination claims at the commit boundary

When `coordination_board` is configured, pre-commit invokes
`synthesis-project-management`'s `check-staged` before content scanning or a
repo-local hook. It refuses unless the selected active session owns the exact
worktree and branch and every staged source/destination path is covered by the
session's claims. `SYNTHESIS_COORDINATION_SESSION` supplies the committing
session when the active-project pointer does not. A deliberate outside-claim
exception requires `SYNTHESIS_COORDINATION_OVERRIDE_REASON`; the checker
atomically records it on the board before the commit proceeds. Missing runtime,
board, lease refresh, selector, or index evidence fails closed.
The hook accepts only `passed-inside-claim` and `recorded-override`, requires the
outcome and outside-path list to match their hash-bound receipt fields, and
revalidates the board and index before continuing. A coordination refusal is
reported separately from content-policy-engine unavailability.

Repositories remain usable when coordination is not adopted: omitting
`coordination_board` does not block, and each hook invocation explicitly says
that this control is absent. The credential and exposure scanners still run.

## v2.3.0 — Portable drift-source resolution

v2.3.0 (2026-08-03) removes the doctor's hardcoded personal checkout path.
The drift check's source now resolves portably: `$SYNTHESIS_GIT_HOOKS_SOURCE`
when set (authoritative — an empty value skips the check deliberately; an
invalid value is a doctor problem, fail closed), else the running script's
own directory when it is not itself an installed engine copy (repo
checkouts, worktrees, client plugin caches), else the documented locations
the ecosystem's own installers create (direct-copy skill installs, the
shared installer's cached clone). A source must carry the complete current engine
file inventory to qualify, and the doctor names the resolved source in its output.
The v2.4.0 installer also persists its absolute source directory beside the
installed engine. Later direct doctor runs use that pointer before documented
fallback locations; an invalid or missing pointed source is a doctor failure.

## Private-key material and detection-rule syntax

Tier 0 remains mandatory before path exclusions or allowlists, including commit
messages when optional exposure checks are disabled. Exact supported bare marker
entries under `tier_0_always.private_key_markers` carry their vocabulary through
the existing loader/scanner interface. Other configured credential expressions,
including custom expressions in that group, retain unconditional matching.

The scanner distinguishes bounded, complete detection-rule syntax from key
material using captured staged blobs and the existing strict policy grammar.
An unchanged header with a newly added body still refuses. A filename, quote,
policy-looking key, or valid/invalid cryptographic body grants no exemption.
The template includes generic and encrypted PKCS#8 as well as RSA, OpenSSH, EC
and PGP. Existing user configuration is preserved during installation; vocabulary
updates belong to its source-managed owner and require an explicit reviewed delta.
See [the precise marker contract](references/marker-rules.md) for accepted syntax,
limits, closure requirements and discriminating controls.

## v2.1.2 — Exact-copy migration calibration

v2.1.2 (2026-07-30) recognizes exact copies from already-committed files before
scanning added lines. Canonical instruction migrations such as
`CLAUDE.md` to `AGENTS.md` therefore scan the new adapter and any actual edits
without treating the unchanged historical instruction body as a fresh leak.
Genuinely new sensitive lines still block, covered by a paired regression.

## v2.1.1 — Native dual-runtime setup

v2.1.1 (2026-07-29) makes the native synthesis plugin the primary skill setup
for Codex and Claude Code. The enforcement runtime remains agent-neutral under
`~/.synthesis/git-hooks/`; both clients invoke and diagnose the same installed
engine.

## v2.0.0 — fail closed, zero dependencies, self-diagnosing

Three design guarantees, added after a field incident in which the v1 engine silently passed commits unscanned when its Python dependency was missing in the invoking environment:

1. **Fail closed.** If the policy engine cannot run — missing config, unparsable config, sidecar crash, invalid pattern, missing interpreter — the commit is **blocked** with a loud diagnostic, never passed unscanned. The engine verifies a `SYNTHESIS_SIDECAR_OK=1` sentinel emitted as the sidecar's final line, so even a partial failure blocks. A protective control that fails open is worse than no control, because it manufactures false confidence.
2. **Zero third-party dependencies.** v1 required PyYAML; which `python3` won PATH resolution therefore silently determined whether protection ran at all (a machine can carry several interpreters — an OS-bundled one, a package-manager one, a python.org one — with different site-packages). v2 vendors a strict YAML-subset parser using only the standard library: any python3 ≥ 3.6, in any environment, yields byte-identical policy. The supported subset is: comments, nested mappings by indentation, quoted/bare string lists, empty sequences as mapping values (`key: []`, including spaces inside the brackets), and scalar values — anything outside it (tabs, nonempty flow sequences, flow mappings, anchors, block scalars) is a **hard parse error that blocks commits** rather than a guess.
3. **Commit-message scanning (v2.1.0).** A sibling `commit-msg` hook scans the commit message itself against the strict-class pattern set — closing the channel pre-commit cannot cover (git gives pre-commit no reliable access to the new message). A history audit showed the only real public-repo confidentiality violations had arrived through commit messages, the one channel the engine never scanned; hygiene-by-discipline demonstrably fails. Personal-class repos skip message scanning by design (`check_commit_message` config flag); fail-closed semantics are identical to pre-commit.
4. **`--doctor` self-check.** `python3 ~/.synthesis/git-hooks/_load_config.py --doctor` verifies the whole chain: config parses, every pattern compiles under both Python `re` and `grep -E`, `core.hooksPath` is wired, the **installed engine matches the skill source** (drift detection — installed copies that were hot-fixed but never synced back are themselves a protection failure), and the cwd repo's classification plus chained repo-local hook. Wire it into a daily ritual and into new-machine bootstrap; a protection layer nobody monitors is a protection layer that is quietly broken.


## What this enforces

| Tier | Patterns | When applied |
|---|---|---|
| **Tier 0 — credentials** | API keys (AWS, OpenAI, Anthropic, Google, GitHub, GitLab, Slack), private key markers (RSA, OpenSSH, EC, PGP, generic and encrypted PKCS#8) | Every repo. Credentials don't belong in git regardless of who reads. |
| **Tier 1 — exposure-sensitive** | Financial, HR/employment, confidentiality markers, confidential client/company names, private skill names, internal URLs | Skip when the repo classifies as `personal`. Run in `strict` and `public-surface` repos — in `public-surface`, minus only the exact name patterns the disclosure ledger records as published precedent. |

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

Ledger allowances come from `disclosure_ledger` (see the
[`synthesis-disclosure-policy`](../synthesis-disclosure-policy/SKILL.md)
skill): each ledger entity carries evidence citations and `hook_patterns`
strings that must textually equal `tier_1_strict_only` entries. A
configured ledger that is missing or unparsable fails closed — commits on
public-surface repos block until it is fixed. No per-repo flag file, no
static declaration, no drift potential: the remote configuration plus the
ledger IS the security profile.

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
# 1. Install the native plugin in the client you use
codex plugin marketplace add synthesisengineering/synthesis-skills
codex plugin add synthesis-skills@synthesis-engineering

# Claude Code equivalent
claude plugin marketplace add synthesisengineering/synthesis-skills
claude plugin install synthesis-skills@synthesis-engineering

# 2. Run the install script — copies the engine to ~/.synthesis/git-hooks/,
#    sets git's core.hooksPath, and seeds an initial config from the template.
<synthesis-git-hooks-root>/scripts/install.sh

# 3. Edit ~/.synthesis/git-hook-config.yaml with YOUR personal-remote patterns
#    (your GitHub user/org), confidential names, internal URLs.

# 4. To enforce lease-backed source-area claims, enable the optional boundary:
# coordination_board: '~/.synthesis/coordination/active-sessions.md'
# Then export SYNTHESIS_COORDINATION_SESSION=<your board selector> in commit
# processes that do not own the active-project pointer.
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
| Repeated detector-rule false positive | Preserve the refusal and correct the scanner through its source owner |
| Add a legitimate Tier-1 match to the allowlist | Review a narrow `allowlist_lines` entry; it cannot subtract credentials or team-mandatory rules |
| Add a new personal org (sole-owner repos there) | Add a regex to `personal_remote_patterns` in the config |

A recurring false positive requires a source-owner correction with retained controls. Repository classification, path exclusions and line allowlists do not exempt Tier 0. Preserve immutable evidence bytes and use the ordinary guarded path after the correction is verified.

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
| **`synthesis-git-hooks` (this skill)** | **Coordination-claim enforcement plus credential and exposure-sensitive checks at the commit boundary** | **pre-commit** |
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

The installer also copies `coordination.py`, `claim_scope.py`, `coordination_schema.py`,
`pointer_lock.py`, `peer_addressing.py`, and the versioned session-word asset from the declared
`synthesis-project-management` dependency into the shared runtime. Their
canonical source remains in that owning skill; the git-hooks doctor compares
the installed copies with those source paths and reports drift. `source-path`
records the install-time source directory so direct installed-doctor runs can
repeat that comparison without an environment override.

## Companion artifacts

- Design rationale (full five-mode analysis) will be published in the synthesis-engineering blog series.
- Operational lesson on the recurring infrastructure-design shortcut pattern that prompted this redesign — included as a reference in the `synthesis-anti-shortcuts` skill.

## License

Apache-2.0. Engine and scripts may be used, modified, and redistributed under the terms of the LICENSE-APACHE file at the root of the synthesis-skills repository.

## references/marker-rules.md, verbatim

# Detection rules and private-key material

The credential boundary distinguishes an exact rule literal from key material.
It never exempts a file, path, repository class or every quoted string.

## Supported rule syntax

The configured exact bare strings for RSA, OpenSSH, EC, PGP, generic and encrypted
private keys are typed only within `tier_0_always.private_key_markers`. Arbitrary
regular expressions, entries in other groups, overlapping custom expressions and
team-mandatory expressions retain ordinary matching semantics.

For staged content, a YAML document must parse completely with the existing
strict config grammar, including empty mapping-value sequences (`key: []` or
`key: [ ]`). This admits no sequence items, nested flow collections, aliases,
or nonempty flow syntax. Quoted `"[]"` remains a string. A complete
`private_key_markers` sequence at document root,
or directly inside `tier_0_always`, must contain only exact supported bare-marker
scalars. Rule syntax uses the engine's complete supported vocabulary, even when
the active policy selects only a subset. This allows adding supported detection
rules without classifying unchanged catalog entries as an open key. It does not
change the active material patterns or custom expressions. Mixed body values, aliases, malformed syntax and unsupported nesting do
not establish a rule. A Python data-only module may contain raw-string
`private_key_marker` assignments with those exact values. Expressions, function
calls, concatenated material and arbitrary quotes are insufficient. Unknown
syntax keeps the conservative marker refusal; it does not become an exemption.

A complete captured traditional unified diff may also carry a literal marker-list
fragment. The entire capture must consist of `---` / `+++` header pairs followed
by complete, ordered hunks whose declared old and new line counts match. Each
hunk must change at least one line and contain a supported marker scalar. Every
payload line on both sides must be an exact quoted supported marker-list scalar
at one consistent indentation, a blank line, or a marker-free comment. Only the
scalar lines receive rule classification; paths, headers and comments never do.
This recognizes the captured fragment itself without inventing its omitted YAML
parent. It does not reconstruct or apply the patch.

Missing headers, truncated or overlapping hunks, nested captures, extra prose,
unsupported payloads, inconsistent indentation, missing final newline, and
no-newline annotations do not establish this proof. Git extended-header patches
are not this traditional-diff syntax. Unknown syntax retains ordinary sensitive
marker refusal. A `.diff` filename, quoting, or a policy-looking path grants no
exemption. Key headers or bodies on either side invalidate the fragment, including
material added below a previously admitted captured rule. Existing scanner
byte, file and deadline bounds apply; no additional configuration is introduced.

Other credential expressions scan all added bytes before rule classification.
The rest of the file and diff remain in the scan, so a valid rule cannot hide a
second credential, key block, or custom-policy finding. Tier-1 and mandatory-team
policy remain distinct. Optional commit-message settings affect exposure checks;
credentials remain mandatory even for a personal repository.

## Staged context and finite failure

The scanner captures index object IDs before acquiring the diff, reads changed
blobs by their immutable object IDs, verifies each blob hash and every added-line
binding, then checks the index again. Working-tree text cannot substitute for
staged bytes. Each changed file is inspected for key regions, including an old
header above a new body. Full, incomplete, header-only, indented and quoted or
ASCII-escaped material refuse without requiring cryptographic validity. A bare
END phrase is not an armored footer. A closed old block does not make unrelated
new lines sensitive.

One scan has a 60-second deadline, 256 MiB Git acquisition bound, and a cumulative
32 MiB / 1,024-file marker-context bound. Exceeded limits, missing objects, changed
index/blob/parser source, unsupported index modes and malformed evidence refuse.
The policy grammar is captured from the existing sibling `_load_config.py` as
bounded regular-file bytes, checked for identity changes and compiled directly;
a cached `.pyc` does not replace it. No extra installed module or global cache is
introduced. The loader, scanner and both shell consumers ship together, and the
existing installer/doctor covers that dependency closure.

## Explicit vocabulary ownership

The public template seeds only absent configuration. It lists generic and
encrypted PKCS#8 signatures in addition to RSA, OpenSSH, EC and PGP (whose armored
form includes `PRIVATE KEY BLOCK`). Existing settings are not silently rewritten.
A source-managed policy receives a separately reviewed marker-only source delta,
then its existing backed-up deployment owner applies it. Updating the engine or
template alone does not claim that an existing user policy has the new signatures.

## Verification boundary

Use actual staged Git and commit-message consumers with synthetic unusable key
bodies. Keep rule-positive cases, material/token refusals, unchanged-header/body,
custom-pattern overlap, index/worktree divergence, changed-source, parser custody,
footer, bounds and performance controls. Preserve original failures and fixture
hashes. Deterministic source tests do not establish installation, policy deployment,
real-account health or authority for a peer's next commit.

## Replaced in the final v5 sweep

On 2026-10-05 one line of 3.0.0's [per-repo-overrides.md](per-repo-overrides.md) still
linked `marker-rules.md`, which 3.0.0 retired into this file. The line now names where a
tier-0 correction is made and links the key-marker rule in
[scanning.md](scanning.md#private-keys). The 3.0.0 line (unchanged from 2.8.4), verbatim:

```text
2. A Tier-0 detection-rule false positive requires a scanner-owner correction. Preserve the exact finding and its positive material controls; neither an allowlist nor a path exception can admit it. See [marker rules](marker-rules.md).
```


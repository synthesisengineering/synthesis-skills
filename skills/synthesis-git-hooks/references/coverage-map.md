# Coverage map: synthesis-git-hooks 2.8.4 to 3.0.0 (v5)

Ruling D8: every part of the 2.8.4 text has a new home, or sits in
[preserved.md](preserved.md) with the reason it was cut. "Verbatim" means the old lines
appear unchanged in the named file. Code verdicts come from the v5 code evaluation
(guards and rituals report, git-hooks rows).

## Contents

- Coverage check result
- SKILL.md sections
- Reference files
- Scripts and their verdicts
- Edge cases and the tests that hold them
- Frontmatter before v5 (verbatim)
- Changed in the final v5 sweep

## Coverage check result

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-git-hooks
synthesis-git-hooks: 479 old lines, 0 not found verbatim
```

Every 2.8.4 line is in a 3.0.0 file: still-true text in the references named below,
everything else in [preserved.md](preserved.md).

## SKILL.md sections

| 2.8.4 section | 3.0.0 home | How |
|---|---|---|
| Frontmatter description | SKILL.md description | Reworded to the 300-character limit; old text below |
| Title and the two framing paragraphs | SKILL.md purpose paragraph | Reworded: one module, not a Bash engine plus sidecars |
| Automatic merge commits | [scanning.md](scanning.md#the-hooks-and-their-order); binding rule 8 | Reworded; the merge runs the same `.githooks/pre-commit` delegate (`test_a_clean_merge_runs_the_checks_and_the_same_pre_commit_delegate`) |
| Staged bytes and commit-message scanning | [scanning.md](scanning.md#the-staged-diff-byte-for-byte) | Reworded; bounds kept (60 s, 256 MiB, 1 MiB) |
| v2.6.0 cached pattern validation | preserved.md | Cut: nothing left to cache |
| v2.5.0 required repo-local delegate | [scanning.md](scanning.md#repository-hooks); [per-repo-overrides.md](per-repo-overrides.md); binding rule 8 | Reworded, same rules (declared on disk or in the index; staged `git rm` withdraws) |
| v2.4.0 coordination claims | [scanning.md](scanning.md#claims); binding rule 9 | Replaced by the v5 board check; override reasons and receipts cut (preserved.md) |
| v2.3.0 drift-source resolution | preserved.md | Cut: `synthesis doctor` compares installed and plugin bytes |
| Private-key material and detection-rule syntax | [scanning.md](scanning.md#private-keys); binding rule 3 | Replaced by the simpler header-plus-body rule (verdict) |
| v2.1.2 exact-copy calibration | [scanning.md](scanning.md#disclosures-and-moved-text); binding rule 7 | Replaced by the moved-text rule |
| v2.1.1 native dual-runtime setup | preserved.md | Cut: plugin install lives in synthesis-onboarding |
| v2.0.0 point 1, fail closed | Binding rule 1; [scanning.md](scanning.md#failing-closed) | Reworded; sentinel cut with the Bash eval (preserved.md) |
| v2.0.0 point 2, zero dependencies and the YAML subset | [policy-file.md](policy-file.md#the-yaml-subset) | Subset sentence verbatim; parser parity checked against 2.x on the real policy and ledger |
| v2.0.0 point 3, commit-message scanning and the history audit | Binding rule 6; [scanning.md](scanning.md#commit-messages) | Reworded |
| v2.0.0 point 4, `--doctor` | Binding rule 10; procedure step 6 | Replaced by `synthesis doctor` (hooks path) and the fail-closed load (patterns compiled on every commit) |
| What this enforces: tier table, three classes, ledger | [policy-file.md](policy-file.md#what-this-enforces) and [the ledger section](policy-file.md#the-disclosure-ledger) | Verbatim |
| When to apply, When NOT to apply | SKILL.md, When to apply, and when not | Verbatim |
| Install | Procedure steps 1 and 2 | Replaced by `install.py --git-hooks` and `commit_policy` |
| Verifying classification for any repo | Procedure step 3; [tier-classification.md](tier-classification.md) | `--classify` kept as a commit_check mode |
| Override path / bypass | [policy-file.md](policy-file.md#common-changes); procedure step 5 | Verbatim rows kept; the config-file override replaced by `SYNTHESIS_HOME` |
| Repo-local hooks are additive, not superseded | [per-repo-overrides.md](per-repo-overrides.md#repo-local-hooks-are-additive-not-superseded); binding rule 8 | Verbatim |
| Why auto-derive instead of per-repo flag files | [tier-classification.md](tier-classification.md#why-auto-derive-not-declare) | Verbatim |
| Reciprocal layers | preserved.md | Cut: described retired hooks |
| Files in this skill | SKILL.md Contents | Replaced |
| Companion artifacts | preserved.md | Cut: pointers to unpublished artifacts |
| License | Frontmatter `license` | Kept |

## Reference files

| 2.8.4 file | 3.0.0 home |
|---|---|
| marker-rules.md | Retired into [preserved.md](preserved.md) verbatim; its surviving guarantees are in [scanning.md](scanning.md#private-keys) |
| per-repo-overrides.md | Kept; delegation, class variable and config-override sections rewritten for v5 (old lines in preserved.md) |
| threat-model.md | Kept verbatim except the tier-0 paragraph (keys, file names) and an anonymized example |
| tier-classification.md | Kept; classifier, examples and pseudocode rewritten for three classes (old lines in preserved.md) |
| (new) policy-file.md, scanning.md | The policy contract and the scanning rules, gathered from SKILL.md and the scripts' docstrings |

## Scripts and their verdicts

| 2.8.4 script | Verdict | Now |
|---|---|---|
| `pre-commit` (388 lines) | SLIM | `synthesis/commit_check.py` main path; receipt validator replaced by the direct claim check |
| `commit-msg` (112) | KEEP (as behavior) | `commit_check.py` commit-msg mode; install adds `commit-msg` to its hook list |
| `pre-merge-commit` (11) | KEEP (as behavior) | `commit_check.py` with `SYNTHESIS_GIT_HOOK=pre-merge-commit` |
| `_load_config.py` (1,838) | SLIM | `commit_check.py`: YAML reader, classification, ledger, pattern build; team layer, validation cache and source heuristics cut |
| `_scan_staged.py` (871) | SLIM | `commit_check.py`: byte-safe diff, bounds, simpler key rule |
| `install.sh` (279) | REPLACE | `synthesis/install.py --git-hooks` |
| `git-hook-config.example.yaml` | KEEP | Moved to the skill root; header comments rewritten for v5 |
| Eight test files (3,754 lines) | REPLACE | `tests/test_commit_policy.py`, `tests/test_commit_check.py`, `tests/test_commit_chaining.py` |

## Edge cases and the tests that hold them

Section 3 of the guards evaluation, scenarios 42 to 51:

| Scenario | Test |
|---|---|
| 42 sidecar fails or prints partial output: blocked | `test_a_policy_that_cannot_be_read_with_certainty_blocks_every_commit`, `test_an_unreadable_config_blocks_the_commit` (one process, no sidecar) |
| 43 identical policy under any python3 | stdlib only; parity with 2.x checked on the real files (report) |
| 44 strict, no remote, unrecognized remote | `test_exposure_patterns_follow_the_repository_class`, `test_mixed_remotes_take_the_stricter_class` |
| 45 public surface: ledgered passes, unledgered blocks, missing ledger blocks | `test_a_public_surface_allows_ledgered_names_and_blocks_the_rest`, `test_a_missing_or_malformed_ledger_blocks_public_surface_commits`, `test_a_ledger_entry_without_evidence_or_outside_the_identity_groups_is_refused` |
| 46 strict commit message names a protected name | `test_messages_are_scanned_in_strict_and_public_surface_repos_without_ledger_allowances` |
| 47 rename with one new line blocks; exact copy not rescanned | `test_an_exact_copy_is_not_rescanned_but_an_edited_rename_is`, `test_a_line_already_in_head_moves_without_counting_as_a_new_disclosure` |
| 48 exclusions never exempt tier 0; odd names and invalid UTF-8 | `test_catalog_paths_skip_exposure_patterns_but_never_credentials`, `test_unusual_file_names_cannot_hide_a_credential`, `test_invalid_utf8_cannot_hide_a_match_or_earn_an_allowlist_exemption` |
| 49 `.githooks/required` with a missing or non-executable delegate | `test_a_declared_delegate_that_cannot_run_blocks_the_commit` |
| 50 `.env`, `id_rsa`, `*.pem` refused | `test_credential_file_names_are_refused_whatever_they_hold` |
| 51 key header without body passes; with body blocks | `test_a_key_header_alone_is_a_rule_not_a_key`, `test_a_key_header_followed_by_key_body_lines_blocks`, `test_an_unchanged_header_with_a_new_body_blocks` |
| 17, 18 refused commit exits non-zero; merges checked | `test_the_synthesis_checks_run_before_any_repository_hook`, `test_a_clean_merge_runs_the_checks_and_the_same_pre_commit_delegate` |
| R2.6 board missing advises, unreadable blocks | `test_no_board_on_the_machine_advises_and_an_unreadable_board_blocks` |
| R2.1 rename out of a claim; no identity | `test_a_rename_out_of_another_sessions_claim_is_refused`, `test_a_committer_with_no_session_identity_is_told_how_to_identify` |

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-git-hooks
description: "Deterministic pre-commit policy for the synthesis-engineering workflow. Enforces staged paths against an active session's lease-backed coordination claim when a board is configured. Classifies each repo by publication surface (personal / public-surface / strict) from its push remotes, applies a tiered pattern set: Tier 0 credentials always; Tier 1 financial / HR / confidentiality / client names in strict and public-surface repos — public-surface minus only the disclosure ledger's published-precedent names. YAML-driven policy lives in ~/.synthesis/git-hook-config.yaml. Use when asked to: install git hooks, configure pre-commit policy, enforce coordination claims, prevent credential leaks, prevent confidential-name leaks, allow published bio names on my own sites, disclosure ledger enforcement, set up the synthesis-engineering enforcement layer."
license: "Apache-2.0"
depends_on: ["synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "2.8.4"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## Changed in the final v5 sweep

| Where | Old | Now | Why |
|---|---|---|---|
| per-repo-overrides.md, "Override pattern: extra allowlist", solution 2 | "See [marker rules](marker-rules.md)." | names the correction (`synthesis/commit_check.py` with a test) and links [scanning.md](scanning.md#private-keys) | `marker-rules.md` was retired into preserved.md in 3.0.0, so the link pointed at nothing; the rule it pointed to lives in scanning.md, "Private keys" |

The old line is verbatim in [preserved.md](preserved.md#replaced-in-the-final-v5-sweep). SKILL.md is unchanged.


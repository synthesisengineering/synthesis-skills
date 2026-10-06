# Coverage map: skills-manager 2.9.3 to 3.0.0 (v5)

Ruling D8: every section of the old text has a new home or a stated retirement reason.
"Verbatim" means the old lines appear unchanged in the named file; "reworded" means the
rule is kept in plain words there and the old wording is in [preserved.md](preserved.md)
or [preserved-release-protocol.md](preserved-release-protocol.md).

## Contents

- [Coverage check result](#coverage-check-result)
- [Frontmatter before v5 (verbatim)](#frontmatter-before-v5-verbatim)
- [2.9.3 SKILL.md](#293-skillmd)
- [references/release-protocol.md](#referencesrelease-protocolmd)
- [Scripts by verdict](#scripts-by-verdict)
- [Edge cases and the tests that hold them](#edge-cases-and-the-tests-that-hold-them)
- [Changed in the final v5 sweep](#changed-in-the-final-v5-sweep)

## Coverage check result

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-skills-manager
synthesis-skills-manager: 557 old lines, 0 not found verbatim
```

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-skills-manager
description: "Agent-native skill installer and manager for the synthesis skills ecosystem. Handles installation, drift detection, synthesis merge for conflicts, provenance tracking, and cross-repo coordination. Use when asked to: install skills, update skills, check skill drift, manage skills, skill status, skill inventory, sync skills."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.9.3"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

v5 changes: description rewritten to 300 characters around release, install, drift and
provenance triggers; `depends_on` gains `synthesis-onboarding` because `release.py` uses
its `setup.py` for each harness's install commands; version 3.0.0; `format: v5`.

## 2.9.3 SKILL.md

| Old section | v5 home | How |
|---|---|---|
| Version notes 2.9.3 back to 2.5.0 | [preserved.md](preserved.md) | Retired: they describe bounded check groups, Codex cache snapshots, the cache guardian, acceptance receipts and hosted-result reuse, all removed |
| Opening paragraph (three repositories, executable methodology, plugin for public skills) | [skills-and-provenance.md](skills-and-provenance.md); SKILL.md purpose | Verbatim |
| Architecture: repositories table, deployment targets 1 to 6, `~/.codex/skills` is not a target | [skills-and-provenance.md](skills-and-provenance.md); Procedure "Private and shared skills" | Verbatim |
| Provenance Tracking (`.source.json`) | [skills-and-provenance.md](skills-and-provenance.md) | Verbatim |
| Commands: install, update, status, drift, merge, merge protocol, "what makes this different from git merge" | [skills-and-provenance.md](skills-and-provenance.md); Binding rule 7 | Verbatim |
| Dependency Access Hierarchy, Checking Dependencies | [skills-and-provenance.md](skills-and-provenance.md); `tests/test_source_lint.py` checks every `depends_on` resolves | Verbatim |
| Configuration Separation | [skills-and-provenance.md](skills-and-provenance.md) | Verbatim |
| Workflow Examples (first-time setup, drift detected, both sides changed) | [skills-and-provenance.md](skills-and-provenance.md), with a note that step 6 is now doctor plus the source lint | Verbatim |
| Error Handling | [skills-and-provenance.md](skills-and-provenance.md) | Verbatim |
| Implementation Notes (agent merges, `install.sh` fallbacks, whole-directory drift backups, verification custody) | [skills-and-provenance.md](skills-and-provenance.md) | Verbatim |
| Gated cross-client release (mandatory protocol, atomic refs, Codex cache snapshots and guardian) | [release.md](release.md) | Reworded: v5 keeps atomic main, stable and tag per remote and per-harness install; snapshots and the guardian are retired (cache_guardian REPLACE) |
| The stable path: the 2026-09-01 incident | [release.md](release.md#the-stable-path-never-pin-a-version); Binding rule 6 | Incident verbatim; mechanism reworded to `~/.synthesis/v5/bin/synthesis-hook` and `~/.synthesis/v5/current` |
| The stable path: two kinds of caller; `parity.stable-path` daily check | [release.md](release.md#the-stable-path-never-pin-a-version); doctor's `runtime` and `hook script` checks | Reworded: hooks call the stable hook; instructed commands call `synthesis` |
| The release train: the 2026-09-01 incident and why board messages failed as a serializer | [release.md](release.md#the-release-train-one-publisher-at-a-time); Binding rule 4 | Verbatim |
| The release train: virtual resource `release-train:synthesis-skills`, `coordination.py`, lease, `SYNTHESIS_COORDINATION_SESSION` | [release.md](release.md#the-release-train-one-publisher-at-a-time) | Reworded: a v5 board claim on the main checkout's `CHANGELOG.md`, taken by `release.py` |
| The release train: protocol (claim before the bump, hold through release, release after; a crashed holder blocks, the user frees it) | [release.md](release.md#the-release-train-one-publisher-at-a-time); Procedure | Verbatim in substance |
| Source Update Protocol: the sequence, must-nots, why non-negotiable (2026-04-29) | [source-update-protocol.md](source-update-protocol.md); Binding rules 1 and 2 | Verbatim, with a v5 note on steps 6 and 7 |

## references/release-protocol.md

| Old section | v5 home | How |
|---|---|---|
| Why the script exists (pushing is publishing; pinned installs) | [release.md](release.md#why-release-is-a-script) | Verbatim |
| Command modes (`--dry-run`, `--check-only`, `--acceptance-only`, `--install-only`) | [release.md](release.md#the-procedure) | `--dry-run` and `--install-only` kept; check and acceptance modes retired with release_check_groups and hosted_validation |
| Stage list | [release.md](release.md#what-the-script-refuses-and-why) | Reworded to v5's five stages |
| One complete candidate validation; reuse at publication | Retired | PR CI is the only gate (R7.3); GitHub required checks do this natively (hosted_validation REPLACE) |
| Preflight (manifests agree, CHANGELOG matches, clean tree, not an installed cache) | [release.md](release.md#what-the-script-refuses-and-why); `preflight()` | Kept, plus default branch and CI for HEAD |
| Acceptance consumption | Retired | Receipts and acceptance manifests removed in v5 |
| Publish: atomic `main`, `stable`, tag per remote, immutable commit | [release.md](release.md#what-the-script-refuses-and-why); `publish()` | Kept; success read with `git ls-remote` |
| Activate public CLI | Retired | The launcher and release store are replaced by the stable runtime |
| Install: each client's own commands; Codex upgrade before add | [release.md](release.md#each-harnesss-own-commands) | Verbatim for Codex; Claude and Muse commands kept |
| Install: cache snapshots, recovery archive, guardian, 512 MiB budget, quiet window | Retired | The stable hook path makes old cache folders irrelevant (cache_guardian REPLACE); remove the agent and archives at cutover |
| Verify: CLI report and the manifest at the loaded path; complete inventory | [release.md](release.md#why-a-clients-own-version-report-is-not-sufficient-evidence); `tree_differences()` | Kept as byte comparison at the reported folder |
| Reconcile lifecycle | Retired | Desired-state generations removed in v5 |
| Why a client's own version report is not sufficient evidence | [release.md](release.md#why-a-clients-own-version-report-is-not-sufficient-evidence) | Verbatim, plus the 2026-08-24 date |
| Required autopilot check partitions; required-check fixture custody | Retired | release_check_groups CUT: v5 CI is plain pytest under 10 minutes |

## Scripts by verdict

| Old script | Lines | Verdict | Now |
|---|---:|---|---|
| `scripts/release.py` | 4,963 | SLIM | `scripts/release.py`, 267 lines: preflight, train, publish, per-harness install through onboarding's `setup.py`, byte verification, doctor |
| `scripts/release_check_groups.py` | 2,413 | CUT | Deleted; CI is `pytest tests/ skills/*/tests/` |
| `scripts/cache_guardian.py` | 840 | REPLACE | Deleted; the stable hook path (`synthesis/install.py`, tested in `tests/test_install.py::test_a_running_task_keeps_working_after_its_plugin_folder_is_deleted`) |
| `scripts/hosted_validation.py` | 149 | REPLACE | Deleted; PR CI with required checks, read by `ci_state()` |
| Tests in `scripts/` (10,805 lines) | | | Replaced by `tests/test_skills_manager_release.py` |

## Edge cases and the tests that hold them

From the install-release evaluation, section 3:

| Scenario | Test |
|---|---|
| 9: a second session is refused with the holder's name | `test_a_second_session_is_refused_with_the_first_ones_name`, `test_main_refuses_while_another_session_releases`, `test_releases_from_two_worktrees_claim_the_same_file` |
| 12: a release in progress with differing versions is reported, never repaired | `tests/test_doctor.py::test_versions_agree_differ_or_a_release_is_in_progress` |
| 28, 29: Codex upgrade before add; Claude marketplace update then plugin update | onboarding `test_codex_update_upgrades_the_snapshot_before_adding`, `test_claude_update_refreshes_the_marketplace_then_the_plugin` |
| 31: Muse grammar, absolute bundle path, update after first install | onboarding `test_muse_first_install_stages_a_bundle_and_later_runs_update`, `test_muse_without_plugin_commands_is_refused_before_staging`, `test_muse_record_from_a_foreign_or_relative_path_is_refused` |
| 32: bytes against the tag, at the folder the harness reports | `test_installed_bytes_must_equal_the_tag_whatever_the_label`, `test_verification_reads_the_folder_the_harness_reports`, `test_a_wrong_reported_version_fails_even_with_matching_bytes` |
| 33: manifests disagree, CHANGELOG differs, dirty tree, plugin cache as root | `test_preflight_refuses_before_pushing`, `test_preflight_refuses_a_plugin_cache_as_the_repository` |
| 34: every push remote, one atomic push of the same commit | `test_publish_pushes_main_stable_and_the_tag_to_every_remote`, `test_a_rejected_push_is_caught_by_reading_the_remote` |
| 35: success read from `git ls-remote` | `test_a_rejected_push_is_caught_by_reading_the_remote` |
| 36: a deleted version folder never breaks a running task | `tests/test_install.py::test_a_running_task_keeps_working_after_its_plugin_folder_is_deleted` |
| 37: the stable path moves only after verification; doctor fails if missing or changed | `release.py` installs the runtime from a verified root; `tests/test_doctor.py::test_missing_runtime_fails`, `test_runtime_files_changed_after_install_fail` |
| CI must pass for HEAD (R7.3) | `test_preflight_refuses_when_ci_has_not_passed`, `test_ci_state_reads_github_runs` |

## Changed in the final v5 sweep

| Where | Old | Now | Why |
|---|---|---|---|
| skills-and-provenance.md, Implementation Notes | "The `install.sh` scripts in each repo serve as bootstrap/fallback installers ..." | "The `install.sh` scripts in the personal and team-shared repositories serve ..." with a parenthesis: the public repository's `install.sh` only runs `onboard.sh` | In v5 the public repository's `install.sh` is a two-line shim to `onboard.sh`; it copies no skills and keeps no drift backups. The private installers still do what the paragraph describes |

The old sentence is verbatim in [preserved.md](preserved.md) (the 2.9.3 Implementation Notes). The `install.sh update` lines in [source-update-protocol.md](source-update-protocol.md) stay: that section is the 2.9.3 protocol verbatim, its "In v5" preface routes public skills to `release.py`, and private and shared repositories still run their own `install.sh update`. SKILL.md is unchanged.


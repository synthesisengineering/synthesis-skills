# Coverage map: onboarding 2.10.4 to 3.0.0 (v5)

Ruling D8: every section of the old text has a new home or a stated retirement reason.
"Verbatim" means the old lines appear unchanged in the named file; "reworded" means the
rule is kept in plain words there and the old wording is in [preserved.md](preserved.md)
or the named preserved file.

## Contents

- [Coverage check result](#coverage-check-result)
- [Frontmatter before v5 (verbatim)](#frontmatter-before-v5-verbatim)
- [2.10.4 SKILL.md](#2104-skillmd)
- [Reference files](#reference-files)
- [Scripts and data by verdict](#scripts-and-data-by-verdict)
- [Edge cases and the tests that hold them](#edge-cases-and-the-tests-that-hold-them)

## Coverage check result

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-onboarding
synthesis-onboarding: 950 old lines, 0 not found verbatim
```

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-onboarding
description: "Install, update, repair, diagnose, and uninstall the synthesis work system through one stable public CLI. Covers immutable release acquisition, stable and edge channels, exact pins, full, skills-only and modular profiles, tracked dual-client workspace instructions, optional declarative organization enrollment, transactional desired and observed state, plugin currency, and outcome verification. Use when asked to onboard, install synthesis, set up the ecosystem, configure a knowledge workspace, update or repair an installation, enroll an organization, verify an install, or diagnose onboarding."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.10.4"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

v5 changes: description rewritten to 300 characters (now naming Muse, new Macs and
organizations); version 3.0.0; `format: v5`.

## 2.10.4 SKILL.md

| Old section | v5 home | How |
|---|---|---|
| First useful task (journeys, plan consent, artifact verification, studies) | [first-useful-task.md](first-useful-task.md) | Journey table and the never-invent rule verbatim; plan digests, `journey` commands and studies retired (first_run REPLACE, first_run_store CUT) |
| One bootstrap and one stable `synthesis` command; convergent, transactional engine | SKILL.md purpose; Binding rule 2 | Reworded: `setup.py`, safe to rerun; transactions and receipts retired |
| Declared maintenance and campaigns | [preserved-declared-maintenance.md](preserved-declared-maintenance.md) | Retired (machine_review, upgrade_campaigns CUT) |
| Team contract pointer | Retired | team_enrollment CUT: the live organization manifest does not use one; `team_contract` is still accepted by the validator |
| Accessible setup and platform ownership | [preserved-platform-ownership.md](preserved-platform-ownership.md) | Retired with the catalogs; Linux/WSL is an open decision (evaluation section 5) |
| Start here: the one-liner and explicit commands | SKILL.md Procedure | Reworded: clone to `~/.synthesis/v5/source`, run `setup.py`; the `onboard.sh` one-liner changes at cutover |
| Full correspondence setup needs reviewed transport declarations | [harness-install.md](harness-install.md#first-config); [preserved-message-guard-onboarding.md](preserved-message-guard-onboarding.md) | Reworded: v5's send guard asks for approval of every send, so no declaration is needed to be safe and nothing silently blocks |
| `synthesis` command list | SKILL.md Procedure | `setup` → `setup.py`; `enroll` → `setup.py org`; `update` and `repair` → rerun `setup.py plugin`; `status`/`doctor` → `synthesis doctor`; `workspace ensure` → `setup.py workspace --new`; `fleet join` → `setup.py workspace`; `uninstall` → `setup.py uninstall`; `stage-core`, `activate`, `deactivate`, `outcome verify`, `onboard`, `journey`, `study`, `team`, `machine`, `campaign` retired (synthesis_cli REPLACE) |
| `synthesis onboard`: detect, recommend, interview; needs a terminal | `setup.py` with no command; Binding rule 7 | Reworded (onboard_flow SLIM) |
| `status`/`doctor` plain summary, `--json` | `synthesis doctor [--json]` | Kept in the core doctor |
| Update migrates plugin-only receipts; "no refresh needed" | Retired | No receipts in v5; reruns report each harness's state |
| Updates reconcile shared runtime code (git hooks, message guard, kernel, day-end) | [harness-install.md](harness-install.md#the-runtime-the-commit-check-and-the-cli) | Reworded: one runtime at `~/.synthesis/v5/current`; runtime_payload REPLACE |
| Day-end helper dependency | Retired here | The day-end launcher belongs to the rituals skills |
| Doctor compares runtime bytes and runs installed doctors | `synthesis doctor` (runtime, package, hook checks) | Reworded |
| Uninstall and `--purge` | [harness-install.md](harness-install.md#restart-verify-uninstall); `install.uninstall` | Reworded: config and the board are kept; owned registrations restored |
| `install.sh` compatibility; direct copies never chosen automatically | Retired | direct_copy REPLACE: native plugins only (Binding rule 1); `install.sh` changes at cutover |
| Profiles and visible layers | Retired | Catalog files CUT; one install |
| Release identity: stable, edge, `--pin` | [harness-install.md](harness-install.md#each-harnesss-own-commands) | Reworded to `--ref stable | main | vX.Y.Z` |
| TLS through an operating-system CA bundle, never disabled | Core `doctor.fetch_text` (`--latest`) | Kept |
| Trust contract (tag, commit, tree digest) | Retired | bootstrap SLIM: harness marketplaces fetch the tag; release verification compares bytes |
| State and recovery (desired/observed state, generations) | Retired | system_contract CUT |
| Floating install never downgraded; exact pins exact | [harness-install.md](harness-install.md#each-harnesss-own-commands); doctor `--latest` | Kept |
| Release-driven repair with digests | Retired | release.py installs and verifies directly |
| Tracked instructions for both clients (`workspace ensure`, seeds, entry points) | [new-mac.md](new-mac.md#starting-a-workspace-from-nothing); `assets/workspace/` | Kept: seeds are the user's, refused commits report git's reason, identity checked first |
| Organization instruction provenance and personal layer | [org-manifest.md](org-manifest.md#instruction-provenance) | Reworded: generated marker, rewrite only generated files, `--personal-source` recorded and replayed |
| Existing workspace files preserved; explicit adoption archives first | [new-mac.md](new-mac.md#workspace-instructions); Binding rule 3 | Kept |
| Declarative organization enrollment (data only, clones, layouts, transports, schema-1 refusal) | [org-manifest.md](org-manifest.md) | Kept; journals, ownership receipts and invites retired |
| Fleet enrollment (flag-free, discovery, narration, resume, terminal) | [new-mac.md](new-mac.md) | Kept; machine labels, roles and the registry retired (fleet_join, fleet_bootstrap SLIM) |
| Doctor and truth planes; per-execution digest; exit codes | `synthesis doctor` | Reworded; six planes retired with receipts |
| Update lifecycle (restart; resume the conversation) | [harness-install.md](harness-install.md#restart-verify-uninstall); Binding rule 8 | Reworded; the transcript-bound SessionStart proof retired |
| Codex hook trust is a human setting, never auto-approved | Binding rule 5; [harness-install.md](harness-install.md#hook-trust-stays-with-the-person) | Kept |
| Ownership boundaries | Binding rules 3 and 6; [org-manifest.md](org-manifest.md) | Reworded |
| Maintainer contract | `python3 -m pytest -q tests/ skills/` (repository AGENTS.md) | Reworded |
| macOS protected-file diagnostics | synthesis-agent-conformance `references/macos-file-access.md` | The pointed-to text is kept there verbatim |

## Reference files

| Old file | v5 home | How |
|---|---|---|
| `org-manifest.md` | [org-manifest.md](org-manifest.md); old in [preserved-org-manifest.md](preserved-org-manifest.md) | Example and migration table verbatim; commands, check command and repository rules updated |
| `kernel.example.md` | [kernel.example.md](kernel.example.md); old in [preserved-kernel.md](preserved-kernel.md) | Enforcement declarations name v5's guards |
| `first-run-journeys.md` | [first-useful-task.md](first-useful-task.md); [preserved-first-run-journeys.md](preserved-first-run-journeys.md) | Table verbatim |
| `declared-maintenance.md`, `message-guard-onboarding.md`, `modular-lifecycle.md`, `platform-ownership.md`, `web-distribution-contract.md` | `preserved-*.md` | Retired with their scripts and catalogs |
| `release-capabilities.json`, `components.json`, `layers.json`, `platform-ownership-v1.json`, five `*.schema.json` | Deleted | CUT: catalogs the old engine checked itself against |
| `scaffolds.json` | `tests/test_source_lint.py::test_every_fail_closed_config_has_a_shipped_example` | SLIM: the rule detects the skills itself |
| `personal-policy.example.json` | `setup.py` first-config interview (`knowledge_roots`, `forbidden_phrases`) | SLIM: v5 config keys replace the policy file |

## Scripts and data by verdict

| Old script | Lines | Verdict | Now |
|---|---:|---|---|
| `onboard.py` | 6,617 | SLIM | `scripts/setup.py` (plugin, Codex overlay, runtime, first config, uninstall) and `scripts/workspace.py` (workspaces, organizations, scaffold); YAML reader in `scripts/yaml_subset.py`, since replaced by the plugin's one reader, `synthesis/yamlish.py` (its cases are in `tests/test_yamlish.py`) |
| `system_contract.py` | 3,410 | CUT | `validate_org_manifest` and `validate_repository_url` salvaged into `workspace.py` |
| `synthesis_cli.py` | 2,699 | REPLACE | `setup.py` commands and the core `synthesis` CLI |
| `release_runtime.py` | 2,331 | SLIM | The core stable hook (`synthesis/install.py` HOOK_SCRIPT, `synthesis/hook.py`) |
| `first_run.py` | 1,162 | REPLACE | [first-useful-task.md](first-useful-task.md) |
| `fleet_join.py` | 859 | SLIM | `workspace.bring_workspace`, `discover_kb`, `setup.ask/choose/confirm` |
| `direct_copy.sh` | 858 | REPLACE | Native plugin install |
| `runtime_payload.py` | 739 | REPLACE | One runtime at `~/.synthesis/v5/current` |
| `modular.py` | 693 | REPLACE | One install; tools read skill files directly |
| `enrollment.py`, `machine_review.py`, `upgrade_campaigns.py`, `first_run_store.py`, `check_capabilities.py`, `maintenance_cli.py`, `team_retirement.py`, `team_enrollment.py` | 2,526 | CUT | Deleted |
| `whole_system.py` | 500 | SLIM | `setup.first_config` |
| `bootstrap.py` | 466 | SLIM | Source clone plus `install.install` from it |
| `plugin_currency.py` | 378 | SLIM | Core `doctor.check_latest` and `fetch_text` (`synthesis doctor --latest`) |
| `onboard_flow.py` | 300 | SLIM | `setup.py` interactive mode and terminal prompts |
| `fleet_sync.py` | 275 | REPLACE | Rituals' repo sync and `setup.py workspace` reruns |
| `organization.py` | 185 | SLIM | `workspace.acquire_org`, `org_git_env`, `org_root` |
| `owned_registrations.py` | 145 | SLIM | Core `install.register_git_hooks` and `install.uninstall` (the git hooks path); `setup.register_day_end` and `unregister_day_end` (the day-end link and LaunchAgent, removed only when they point at this install) |
| rituals `install_day_end.py` (guards-rituals evaluation) | 160 | REPLACE | Every `install.install` copies `day-end` and `day-end-nudge.sh` into `~/.synthesis/v5/bin/`; `setup.py --day-end` registers them; tests `tests/test_install.py::test_every_install_carries_the_day_end_launcher_and_nudge` and `test_onboarding_setup.py::test_day_end_*` |
| `check_scaffolds.py` | 141 | SLIM | `tests/test_source_lint.py` |
| `kernel_sync.py` | 135 | REPLACE | One authored AGENTS.md; doctor measures Codex's instruction chain |
| `reload_guidance.py` | 33 | SLIM | `setup.RESTART`, one sentence |
| Tests in `scripts/` (22,392 lines) | | | `tests/test_onboarding_setup.py`, `test_onboarding_workspace.py`, `test_onboarding_yaml.py`, and core `tests/test_install.py` |

## Edge cases and the tests that hold them

From the install-release evaluation, section 3 (test files under this skill's `tests/`
unless named):

| Scenario | Test |
|---|---|
| 16, 69: Codex hooks on unless explicitly false; owned keys only; backup | `test_overlay_sets_only_the_owned_keys`, `test_overlay_keeps_an_explicit_hooks_false_and_says_guards_will_not_run`, `test_configure_codex_backs_up_before_writing` |
| 17: no hook silently blocks a new user's sends | `test_first_config_interview_only_for_a_fresh_config` (the guard asks for approval by design) |
| 18: every fail-closed config has a shipped example | `tests/test_source_lint.py::test_every_fail_closed_config_has_a_shipped_example` |
| 19: previous `core.hooksPath` recorded and restored | `tests/test_install.py::test_git_hooks_option_records_the_previous_path_and_uninstall_restores_it`, `test_uninstall_keeps_a_hooks_path_the_user_changed_since` |
| 24: absent harness skipped | `test_absent_harnesses_are_skipped_without_failing` |
| 25, 26: Codex in the desktop app; bounded probe | `tests/test_doctor.py::test_codex_inside_the_desktop_app_is_found_off_path`, `test_version_probe_is_bounded_closes_stdin_and_reaps` |
| 27: each plugin-list shape; text output never crashes | `test_plugin_list_shapes_and_text_output` |
| 28, 29: Codex upgrade before add; Claude update order | `test_codex_update_upgrades_the_snapshot_before_adding`, `test_claude_update_refreshes_the_marketplace_then_the_plugin` |
| 30: marketplace on a different ref re-added | `test_a_marketplace_on_another_ref_is_removed_and_added_again`, `test_an_already_added_marketplace_is_re_added` |
| 31: Muse grammar, absolute bundle path, update after install | `test_muse_first_install_stages_a_bundle_and_later_runs_update`, `test_muse_without_plugin_commands_is_refused_before_staging`, `test_muse_record_from_a_foreign_or_relative_path_is_refused`, `test_an_unreadable_muse_inventory_is_not_taken_for_absence` |
| 38: no downgrade of an install ahead of the channel | `test_without_an_explicit_ref_an_install_on_another_channel_is_never_moved`; `tests/test_doctor.py::test_latest_release_compares_semantically_and_never_asks_for_a_downgrade` |
| 39, 40: CA fallback; semantic versions | `tests/test_doctor.py::test_fetch_retries_with_the_system_ca_bundle_only_on_certificate_failures`, `test_latest_release_compares_semantically_and_never_asks_for_a_downgrade` |
| 41: rerun changes nothing; dry run touches nothing | `tests/test_install.py::test_install_rerun_changes_nothing`, `test_overlay_sets_only_the_owned_keys` (rerun), `test_dry_run_runs_no_harness_command` |
| 42: prompts read the terminal under a pipe; without one, name the flag | `test_questions_read_the_terminal_when_stdin_is_a_pipe`, `test_questions_without_a_terminal_name_the_flag`, `test_discovery_without_a_terminal_names_the_flag` |
| 43: progress per repository; Ctrl-C resume line; rerun skips finished | `test_new_mac_clones_every_listed_repository_with_progress`, `test_interrupt_prints_a_resume_line`, `test_an_interrupted_clone_leaves_nothing_at_the_target_and_a_rerun_finishes` |
| 44: discovery through `gh`, clone `repos.yaml`, fast-forward, skip dirty or diverged by name | `test_discovery_uses_the_one_knowledge_repo_gh_lists`, `test_clone_then_fast_forward_then_skip_by_name`, `test_new_mac_clones_every_listed_repository_with_progress` |
| 45: existing clone with another origin refused, not repointed | `test_a_checkout_with_another_origin_is_refused_and_not_repointed`, `test_the_knowledge_repository_with_a_wrong_origin_stops_everything` |
| 46: Codex fallback filenames include CLAUDE.md; instruction bytes ≥ 98,304 | `test_overlay_sets_only_the_owned_keys`, `test_overlay_raises_a_low_instruction_limit_and_adds_a_features_table` |
| 49: no organization code runs; unknown keys exit 2; dirty clone refused; same name, separate folders; https and ssh only, no injected config | `test_manifest_validation_accepts_schema_2_and_refuses_unknown_keys`, `test_manifest_check_command_exits_2_on_unknown_keys`, `test_a_dirty_organization_clone_is_refused`, `test_same_repository_name_in_two_organizations_gets_two_folders`, `test_organization_git_runs_with_only_https_and_ssh_and_no_injected_config`, `test_only_authenticated_https_and_ssh_urls_are_accepted` |
| 50: a failed clone shows `auth_help`, needs action, rerun resumes | `test_a_clone_failure_shows_the_organizations_auth_help` |
| 51: workspace files someone else wrote are preserved; adoption archives first | `test_existing_workspace_instructions_are_kept_unless_adopted_and_then_archived`, `test_reenrollment_keeps_an_edited_skill_copy_and_regenerates_its_own_file` |
| 52: no git identity, no change before a commit | `test_a_new_workspace_without_a_git_identity_changes_nothing` |
| 54: uninstall removes only what install created | `tests/test_install.py::test_uninstall_removes_only_unedited_files_install_wrote`, `test_uninstall_dry_run_changes_nothing`; `test_uninstall_removes_the_plugin_with_each_harness_command` |
| 13, 14, 20, 36: pinned interpreter, valid output on a hook timeout, no bytecode in the plugin folder, version-independent hook path | Core: `tests/test_install.py::test_bootstrap_command_writes_no_bytecode_into_the_plugin_folder`, `test_a_running_task_keeps_working_after_its_plugin_folder_is_deleted`; hook deadlines belong to the core hook |

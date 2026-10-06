# Coverage map: agent-conformance 1.14.1 to 2.0.0 (v5)

Ruling D8: every section of the old text has a new home or a stated retirement reason.
"Verbatim" means the old lines appear unchanged in the named file; "reworded" means the
rule is kept in plain words there and the old wording is in [preserved.md](preserved.md)
or the named preserved file.

## Contents

- [Coverage check result](#coverage-check-result)
- [Frontmatter before v5 (verbatim)](#frontmatter-before-v5-verbatim)
- [1.14.1 SKILL.md](#1141-skillmd)
- [Reference files](#reference-files)
- [Scripts and data by verdict](#scripts-and-data-by-verdict)
- [Edge cases and the tests that hold them](#edge-cases-and-the-tests-that-hold-them)
- [Reworded lines (old wording)](#reworded-lines-old-wording)

## Coverage check result

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-agent-conformance
synthesis-agent-conformance: 1071 old lines, 0 not found verbatim
```

Before the reworded paragraph below was quoted here, the check listed exactly its four
lines.

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-agent-conformance
description: Audit, install, and verify a synthesis ecosystem across multiple AI agent runtimes. Use for Claude Code and OpenAI Codex parity audits, AGENTS.md and CLAUDE.md instruction migrations, skill or plugin deployment checks, lifecycle-hook health, Mac bootstrap validation, active-project handoffs, post-compaction recovery, and any request to make synthesis project management portable between agent clients.
license: "Apache-2.0"
depends_on: ["synthesis-project-management", "synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.14.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

v5 changes: description rewritten to 300 characters and now names Muse; version 2.0.0;
`format: v5`. `depends_on` unchanged.

## 1.14.1 SKILL.md

| Old section | v5 home | How |
|---|---|---|
| Opening ("continuously tested system, not a file-count comparison") | SKILL.md purpose; [audit.md](audit.md#the-five-planes) | Verbatim |
| Pointers to provider intake, signed observations, Hermes pilot, vendor packages | Retired; files kept verbatim as `preserved-*.md` | Scripts CUT: Hermes is not a v5 harness; vendor packaging belongs to the movement project; receipts signed receipts |
| Operating model: five planes | [audit.md](audit.md#the-five-planes); Binding rules 1 to 3 | Planes 1, 2 and 5 verbatim; 3 and 4 reworded (no receipts, leases or pointers) |
| Shared report contract; UNKNOWN never becomes PASS | Binding rule 3; [audit.md](audit.md#the-five-planes) | The rule kept; the schema cut (report_contract CUT; doctor prints plain JSON) |
| Name the plane when facts conflict | Binding rule 2; [audit.md](audit.md#the-five-planes) | Verbatim |
| Diagnostic payload parity; controlling-plan resolver | Retired | Served receipts, pointers and the old renderers; v5 SessionStart reads the project's own files |
| Workflow: bundled PyYAML | Retired, [preserved-yaml-runtime.md](preserved-yaml-runtime.md) | Vendored PyYAML REPLACE: core is standard-library only; onboarding's YAML subset reader |
| 1. Inventory: the `conformance.py` subcommands | [audit.md](audit.md); Procedure 1 and 2 | Reworded: the source lint (`tests/test_source_lint.py`) and `synthesis doctor` |
| `hook-live` and exact-session receipts; transcript identity validation | Retired | live_receipt and native_transcript_identity REPLACE/CUT: SessionStart output and doctor's self-test; v5 reads the session id from the harness |
| `--json`; PASS, FAIL, WARN, UNKNOWN, UNSUPPORTED | [audit.md](audit.md#installed-what-doctor-checks) | Reworded: `synthesis doctor --json`; ok, warn, fail, info |
| `--local` (no network, no writes) | [audit.md](audit.md#installed-what-doctor-checks) | Reworded: doctor never writes and makes no network call unless `--latest` |
| 2. Repair from source (eight rules) | [audit.md](audit.md#repair-from-source); Binding rules 5 and 6 | Verbatim, plus Muse |
| 3. Activate durable project state (pointer, leases, pending manifests) | [architecture.md](architecture.md#5-durable-project-handoff); `synthesis use` | Reworded: each session's project is in its own board file |
| 4. Verify handoff (pointer, continuity local and remote, causal recovery) | [audit.md](audit.md#continuity-the-handoff-exercise); Procedure 4 | Reworded to `synthesis brief` and `synthesis handoff` |
| 5. Close the loop; fix every failed check; record boundaries with evidence; on-disk parity since 1.7.0 | [audit.md](audit.md#repair-from-source); Procedure 6; doctor's per-harness package check | Verbatim in substance; the on-disk lesson is Binding rule 1 |
| Lifecycle hooks: `session_context.py` (time, pointer, discovery, registry audit, receipts, REFUSED lines, runtime digest line) | v5 SessionStart in `synthesis/hook.py` and `synthesis/project.py` (core, project-state helper) | Reworded; see edge cases R1 below |
| Codex reruns SessionStart after compaction | [architecture.md](architecture.md#4-lifecycle-controls); R1.2 | Kept |
| Codex hook trust via `hooks/list`, never edit `hooks.state` | [architecture.md](architecture.md#4-lifecycle-controls); doctor `codex hook trust` | Reworded: doctor reproduces Codex's trust hash, never writes it |
| No global current project; same-Mac and cross-Mac continuity | [architecture.md](architecture.md#5-durable-project-handoff) | Reworded to v5 board and `synthesis handoff` |
| Skill catalog contract | [audit.md](audit.md#skill-catalog-contract); Binding rule 7 | Verbatim |
| Skill-output provenance | [audit.md](audit.md#skill-output-provenance); Binding rule 8; doctor `decision packets` | Reworded (skill_outputs SLIM into doctor) |
| Detailed architecture; browser outcome review | [architecture.md](architecture.md); [autopilot-browser-quality.md](autopilot-browser-quality.md) | Linked |
| Instruction-kernel pattern | [instruction-kernel-pattern.md](instruction-kernel-pattern.md) | Verbatim except its last paragraph (below) |
| macOS protected-file diagnostics | [macos-file-access.md](macos-file-access.md); Binding rule 9 | Verbatim |

## Reference files

| Old file | v5 home | How |
|---|---|---|
| `architecture.md` | [architecture.md](architecture.md); old text in [preserved-architecture.md](preserved-architecture.md) | Sections 1 to 3 verbatim plus Muse; 4 to 7 updated for the stable hook, board files, `synthesis handoff` |
| `instruction-kernel-pattern.md` | [instruction-kernel-pattern.md](instruction-kernel-pattern.md) | Verbatim; last paragraph names doctor's checks |
| `macos-file-access.md`, `autopilot-browser-quality.md` | Same names | Verbatim |
| `conformance-report-v1.schema.json`, `report-contract.md` | Cut; [preserved-report-contract.md](preserved-report-contract.md) | report_contract CUT |
| `hermes-cli-pilot.md` | [preserved-hermes-cli-pilot.md](preserved-hermes-cli-pilot.md) | Hermes CUT |
| `provider-change-intake.md` | [preserved-provider-change-intake.md](preserved-provider-change-intake.md) | provider_intake CUT |
| `signed-observations.md` | [preserved-signed-observations.md](preserved-signed-observations.md) | signed_receipt CUT |
| `vendor-demo-protocol.md`, `vendor-review-packages.md` | `preserved-vendor-*.md` | vendor_bundle CUT |
| `yaml-runtime.md` | [preserved-yaml-runtime.md](preserved-yaml-runtime.md) | Vendored PyYAML REPLACE |

## Scripts and data by verdict

| Old | Lines | Verdict | Now |
|---|---:|---|---|
| `conformance.py` | 2,977 | SLIM | Source rules: `tests/test_source_lint.py`. Parity, Codex instruction budget, adapters, hook definitions and trust: `synthesis doctor`. Receipt, pointer and capability checks cut |
| `session_context.py` | 1,262 | SLIM | v5 SessionStart in `synthesis/hook.py` and `synthesis/project.py` (not in this skill's ownership; edge cases listed below) |
| `project_context.py` | 88 | KEEP | Ported into `synthesis/project.py` by the project-state helper |
| `client_binaries.py` | 153 | KEEP | Moved into core as `doctor.find_client` and `doctor._version_ok` (the runtime only carries `synthesis/`); tests in `tests/test_doctor.py` |
| `codex_app_server.py` | 103 | KEEP | Moved into core as `doctor.app_server_query` for the catalog check |
| `codex_skill_catalog.py` | 254 | SLIM | `doctor.catalog_cost` and `check_codex_catalog`; CI uses `catalog_cost` in the source lint |
| `codex_hook_audit.py` | 168 | SLIM | `doctor.check_codex_trust` (hash reproduced, pinned to Codex-stored vectors) |
| `skill_outputs.py` | 194 | SLIM | `doctor.check_packets` |
| `active_project.py` | 518 | REPLACE | Board session files (`synthesis use`) |
| `live_receipt.py` | 441 | REPLACE | SessionStart output and doctor checks |
| `yaml_runtime.py`, `vendor/pyyaml/` | 116 + 5,971 | REPLACE | Standard-library core; onboarding `scripts/yaml_subset.py` |
| `vendor_bundle.py`, `vendor_native.py`, `vendor_hermes.py`, `vendor_probe.py`, `hermes_adapter.py`, `hermes_source.py`, `signed_receipt.py`, `provider_intake.py`, `native_transcript_identity.py`, `report_contract.py`, `capability_evidence.py` | 4,684 | CUT | Deleted; reasons in the install-release evaluation |
| Tests in `scripts/` (10,845 lines) | | | Replaced by `tests/test_doctor.py` and `tests/test_source_lint.py` |

## Edge cases and the tests that hold them

| Scenario (install-release section 3) | Where |
|---|---|
| 1 to 7, 55 (SessionStart anchor, next actions, freshness from fetched refs with no network, unknown upstream, wrong-project names, early Claude SessionStart, verified local time) | v5 SessionStart and `synthesis/project.py`, owned by the project-state helper; not covered in this skill's tests |
| 15, 70: a changed hook needs Codex re-approval | `tests/test_doctor.py::test_changed_and_disabled_codex_hooks_need_approval`, `test_untrusted_codex_hook_needs_hooks_approval` |
| 21: Codex catalog cost (2%, 8,000-character fallback, 1,024-character cut, explicit-only excluded, every skill under `synthesis-skills:`) | `tests/test_doctor.py::test_catalog_*`; `tests/test_source_lint.py::test_codex_catalog_fits_even_its_fallback_budget` |
| 22: instruction chain under the limit minus 4 KiB | `tests/test_doctor.py::test_instruction_chain_is_measured_against_the_limit_with_a_reserve` |
| 23: hand-made or edited packets flagged | `tests/test_doctor.py::test_hand_made_or_edited_packets_are_flagged` |
| 25, 26, 72: Codex inside the desktop app; override rules; bounded probe; stale launcher | `tests/test_doctor.py::test_codex_inside_the_desktop_app_is_found_off_path`, `test_client_override_is_authoritative`, `test_version_probe_is_bounded_closes_stdin_and_reaps`, `test_a_stale_codex_launcher_on_path_is_skipped` |
| 47, 74: AGENTS.md with CLAUDE.md importing it; conflicts reported, nothing overwritten | `tests/test_doctor.py::test_instruction_adapters_report_each_divergence_and_change_nothing` |
| 53: no personal path in the public repository | `tests/test_source_lint.py::test_no_personal_paths_anywhere_in_the_repository` |
| 12: release in progress reported, not repaired | `tests/test_doctor.py::test_versions_agree_differ_or_a_release_is_in_progress` |

## Reworded lines (old wording)

The last paragraph of `instruction-kernel-pattern.md` in 1.14.1, replaced by a paragraph
naming doctor's checks:

The instruction-budget and catalog checks in this skill's `conformance.py` are
the mechanical layer for steps 3–4: `instruction-budget` enforces the gate,
`catalog` verifies the skill homes are visible to each client, and `hook-live`
proves the enforcement declarations true.

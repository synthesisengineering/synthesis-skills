# Coverage map: inbox cleanup 1.6.2 to 2.0.0

Every part of the 1.6.2 SKILL.md and where it lives now. Nothing was removed. The prompt-injection rules keep their numbers 1 to 8, so any citation of "Rule N" still resolves: binding rule N in SKILL.md summarizes it and references/injection-rules.md holds it in full. No script or test reads text from SKILL.md; every command, flag and path is kept exactly as written.

| 1.6.2 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters, keeping its trigger words: clean up inbox, sweep email, categorize senders, build email rules, archive promotions, set up Gmail filters |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `platform` | Kept (the installer and source checks read them) |
| Title and the two opening paragraphs | SKILL.md (verbatim) |
| v1.6.2, v1.6.0, v1.5.0 and v1.4.0 notes | references/release-notes.md (verbatim); the v1.6.0 impersonation rule is binding rule 13 |
| Architecture: public engine, private rules | references/setup-and-scoping.md (verbatim) |
| Workspace scoping | references/setup-and-scoping.md (verbatim); binding rule 12 |
| When to invoke this skill, When NOT to invoke | SKILL.md (verbatim) |
| Three tool stacks, one methodology | references/workflow.md (verbatim apart from one link path) |
| The categorization taxonomy | references/workflow.md (verbatim); binding rule 10 |
| The workflow, steps 1 to 6, Microsoft 365 and outlook.com, Gmail paths A and B | references/workflow.md (verbatim apart from link paths); binding rules 9, 11 and 14 |
| Prompt-injection defenses, Rules 1 to 8 | references/injection-rules.md (verbatim apart from one link path); binding rules 1 to 8 |
| Pitfalls table | references/workflow.md (verbatim apart from one link path) |
| Setup | references/setup-and-scoping.md (verbatim apart from one link path) |
| License, Author | references/release-notes.md (verbatim) |

## Existing reference files

All five keep their content. Short contents lists were added at the top of the three over 150 lines: manifest-schema.md, pitfalls.md and prompt-injection-defenses.md. `scripts/sanitize.py` and `tests/run_poisoned.py` cite references/prompt-injection-defenses.md by path; it stays where it was.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports 5 lines as not found verbatim. Each is a line moved from SKILL.md into references/ whose relative link gained the change a move one folder down needs: `references/x.md` targets became `x.md` and `templates/x` became `../templates/x`. The wording is unchanged.

- Three tool stacks: "The methodology — census new senders, draft a plan, apply with dry-run-first — is the same across all three..."
- Gmail: "**Path B — server-side filters:** the LLM agent uses `manage_gmail_filter`..."
- Prompt-injection defenses: "See [`references/prompt-injection-defenses.md`]... for the full threat model, attack vectors, and design rationale."
- Pitfalls: "The IMAP substring pitfall and the circumstantial-inference pitfall are documented in detail in [`references/pitfalls.md`]..."
- Setup: "For Gmail and M365 setup details, see [`references/three-tool-stacks.md`]..."

## v5 script changes (2026-10-05)

Verdicts from the v5 code evaluation (`tool-scripts.md`, synthesis-inbox-cleanup rows): every script KEEP except `install.sh` (SLIM, "the v5 plugin install gives a stable path"); carry IR-19 into `scan_impersonation.py` from the unshipped branch `fix/phase1-reported-breakage-20261005`.

| Script | Verdict | Now |
|---|---|---|
| `_lib.py`, `icloud_plan.py`, `icloud_tail.py`, `icloud_census.py`, `icloud_apply.py`, `icloud_archive_senders.py`, `icloud_inspect_senders.py`, `icloud_catchall_google_purge.py`, `resolve_scope.py`, `sanitize.py`, `m365_mailapp_cleanup.template.applescript` | KEEP | Unchanged |
| `scan_impersonation.py` | KEEP, plus IR-19 | The principal rule from the branch: `principal.names` and exact `principal.addresses` in the private `impersonation.yaml`, refusal (exit 2) before any mail access when they are missing or invalid, `--check-config`. The branch's triple file-identity check on the config read became one bounded regular-file read with unique keys. 234 lines before, 394 after |
| `templates/impersonation.example.yaml` | New, from the branch | Synthetic shape for the private file |
| `install.sh` | SLIM | Seeds the private folder (700) and `config.yaml`, `rules.yaml` (600) without overwriting; refuses `/`, home, symlinked or file roots; reports certifi, the Keychain password, a missing stable engine path and a leftover 1.x engine copy (never deleted). The engine release copy, digest checks and pointer swap are gone: v5 installs the engine at `~/.synthesis/v5/current/skills/synthesis-inbox-cleanup/scripts`. 210 lines of bash before, 86 of POSIX sh after |
| `tests/test_runtime_installer.sh`, `tests/fixtures/mv-no-h` | Removed | They tested the engine copy and its pointer (the 2026-08-24 `mv` regression); with no copy there is no pointer. The incident is in [preserved.md](preserved.md). `tests/test_inbox_installer.py` covers the new contract |

Scenarios from section 3 of the evaluation and where each is held:

| Scenario | Held by |
|---|---|
| E55 Trash, never a permanent delete | `tests/test_inbox_engine.py::test_apply_moves_by_uid_to_recoverable_mailboxes`, `test_without_move_capability_only_the_copied_uids_are_expunged`; binding rule 10 |
| E56 nothing moves without `--apply` | `test_dry_run_moves_nothing`; binding rule 9 |
| E57 moves are addressed by UID | the two `--apply` tests (stub sequence numbers differ from UIDs) |
| E58 planner and executor agree | `test_planner_and_executor_share_one_resolver`; `tests/run_resolver.py` (run by `test_standalone_suites_pass`) |
| E59 a bulk archive honours `never_touch` | binding rule 16; references/pitfalls.md (2026-09-28). No script takes a bulk request, so the rule is prose |
| E60 a forged `</UNTRUSTED_EMAIL>` stays inside the nonce fence | `tests/run_poisoned.py` (`delimiter_breakout.eml`), run by `test_standalone_suites_pass`; binding rule 3 |
| E61 a brand claimed from a domain that is not the brand's | `tests/test_impersonation.py::test_exact_name_boundary_and_brand_rules_remain_distinct` |
| E62 a display name equal to the principal's own (IR-19) | `test_principal_names_and_aliases_from_unlisted_addresses_are_high` and the rest of `tests/test_impersonation.py`; binding rule 15 |
| E63 an unknown workspace exits 2 | `tests/test_resolve_scope.py::test_unknown_workspace_is_unverifiable_not_empty`; binding rule 12 |
| E64 catch-all Google notices trashed, the owner's addresses and Workspace or billing senders spared | `tests/test_inbox_engine.py::test_catchall_purge_trashes_strangers_and_spares_the_owner`, `test_lifecycle_rule_never_matches_workspace_or_billing_senders` |
| E65 the Gmail API, not a Mail.app loop | binding rule 17; references/pitfalls.md (2026-08-29) |
| E66 the recipient axis as well as the sender | binding rule 17; references/pitfalls.md (2026-08-29) |
| E67 iCloud Message-ID needs a fetched map; "0 found" is a tool failure | references/pitfalls.md (2026-09-28). No public script moves by Message-ID |

Prose changed with the scripts: references/setup-and-scoping.md (the architecture tree, setup steps 6 and 7, and a paragraph on what the installer reports; the old lines are verbatim in [preserved.md](preserved.md)); references/release-notes.md (a v2.0.0 note); references/pitfalls.md (three anonymized sweep pitfalls from the 2026-08-29 and 2026-09-28 lessons); SKILL.md (binding rules 15 to 17, the scan command in Contents).

**2026-10-06.** `_lib.py`, `resolve_scope.py` and `scan_impersonation.py` read YAML through the plugin's standard-library reader (`synthesis/yamlish.py`) instead of PyYAML, which now reads one-line flow mappings such as `- {match: {from: x}, action: archive}`; the private rules, scopes and configuration files on the author's Mac read identically under both. The installer no longer reports PyYAML, and the engine, scope and impersonation tests run in CI instead of skipping there.

## The 1.6.2 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-inbox-cleanup
description: "Manifest-driven email inbox cleanup across three tool stacks: iCloud / generic IMAP via Python + YAML rules; Microsoft 365 + outlook.com via Mail.app AppleScript; Gmail via workspace-mcp Gmail API and server-side filters. Engine is public; per-user rules live privately at ~/.synthesis/inbox-cleanup/. Ships with prompt-injection defenses (sanitization module + adversarial test fixtures) for any LLM-augmented path. Use when asked to: clean up inbox, sweep email, categorize senders, build email rules, archive promotions, set up Gmail filters, build email cleanup automation."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.6.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  platform: "macOS (Apple Silicon and Intel)"
---
```

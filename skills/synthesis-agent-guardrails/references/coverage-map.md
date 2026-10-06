# Coverage map: synthesis-agent-guardrails 1.0.3 to 2.0.0 (v5)

Ruling D8: every part of the 1.0.3 text and of its scripts' purpose has a new home, or sits
in [preserved.md](preserved.md) with the reason it was cut. Code verdicts come from the v5
code evaluation (guards and rituals report, agent-guardrails rows; project-state report,
row G for the shell classifier).

## Contents

- Coverage check result
- SKILL.md sections
- Scripts and their verdicts
- Edge cases and the tests that hold them
- Frontmatter before v5 (verbatim)

## Coverage check result

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-agent-guardrails
synthesis-agent-guardrails: 121 old lines, 0 not found verbatim
```

## SKILL.md sections

| 1.0.3 section | 2.0.0 home | How |
|---|---|---|
| Frontmatter description | SKILL.md description | Rewritten: the guards are live, not landing |
| The Problem | SKILL.md purpose paragraph | Reworded, same argument |
| Account routing gate | [account-routing.md](account-routing.md); binding rule 1 | Reworded for `guards.check_account` |
| Account routing configuration | [config.md](config.md) | `workspaces.json` became `account_routing` in config.json |
| `--doctor` controls | tests (account-routing.md, Tests) | Replaced |
| Publication authority gate | [deploys.md](deploys.md); binding rules 2 to 4 | Reworded for `guards.check_deploy` |
| Publication configuration | [config.md](config.md#from-the-1x-config-files) | `push_deploys`, `deploy_content` |
| Defaults-off | config.md; binding rule 7 | Reworded: defaults are safe, unreadable config blocks |
| Hooks (per-client detector suite) | [reply-and-provenance.md](reply-and-provenance.md); preserved.md | Two checks kept where the model reads them; the rest cut |
| Layout and Roadmap | SKILL.md Contents | Replaced |

## Scripts and their verdicts

| 1.0.3 path | Lines | Verdict | Now |
|---|---:|---|---|
| `guards/account_routing_guard.py` | 329 | KEEP | `synthesis/guards.py` `check_account` (ported before M3) |
| `guards/publish_guard.py` | 1,907 | SLIM | `synthesis/guards.py` `check_deploy`, `check_dates`, the shell reader |
| `guards/installed_artifact_guard.py` | 431 | CUT | `synthesis doctor` |
| `hooks/_settings.py` | 97 | CUT | `hooks/hooks.json` |
| `hooks/claude/_anti_shortcut_catalog.py` | 392 | REPLACE | anti-shortcuts skill content; `shortcut_phrases` |
| `hooks/claude/_transcript_state.py` | 329 | CUT | none |
| `lazy_shortcut_detector.py` (claude, codex, muse) | 512 | REPLACE | `synthesis/reply_check.py` |
| `quote_provenance_checker.py` (claude, codex) | 692 | SLIM | `scripts/provenance_scan.py` (about 190 lines) |
| `bare_filename_detector.py` (claude, codex) | 299 | SLIM | file-link rule in `synthesis/reply_check.py` |
| `long_session_detector.py` | 133 | REPLACE | R1.2 date in the re-injected brief (not yet in `hook.py`) |
| `pre_tool_temporal_reminder.py` | 118 | REPLACE | same |
| `sub_agent_brief_scanner.py` | 196 | REPLACE | anti-shortcuts skill prose (preserved.md lists what moves) |
| `hooks/codex/repo_guard_stop.py`, `session_end_checkpoint.py`, `installed_skill_edit_guard.py` | 492 | CUT | none |
| `publication_command.py` (in project-management, used here) | 897 | SLIM | the shell reader in `synthesis/guards.py` |
| `schemas/*.json` | 82 | REPLACE | config.md tables |

## Edge cases and the tests that hold them

| Scenario | Test |
|---|---|
| Guards report 29: wrong-account calendar or mail call blocked; reads and Slack not | `tests/test_account_routing.py` |
| 31, 33, 37: `git -C` push, `cd` attribution, linked worktree | `tests/test_deploy_rules.py` (incident shapes, attribution, worktree) |
| 32: `git commit -m "fix site push"` is not a push | `test_every_incident_shape_of_a_site_push_is_a_deploy` (not_pushes) |
| 34: a push to an auto-deploy repo needs approval | `tests/test_guards.py::test_push_to_a_repo_that_deploys_on_push_counts_as_a_deploy` |
| 35: HEAD moves after approval | `test_an_approval_is_bound_to_the_commit_it_was_given_for` |
| 36: `git push && git push` | `test_one_command_deploying_a_site_twice_is_refused_before_any_approval` |
| 38 to 40: future date, re-dating, rapid redeploy, both layouts | `tests/test_deploy_rules.py` |
| 41: unparsable read-only commands run | `test_an_unreadable_command_with_no_deploy_word_is_never_blocked`, `test_text_that_only_mentions_a_push_or_a_delete_is_neither` |
| 52: `git worktree remove` allowed | no guard touches it (deploys.md, Destruction) |
| Project-state R3.2: wrappers, `bash -c`, `$(...)`, backticks, unquoted heredocs; quoted and argument words are data | `test_a_deploy_that_runs_is_caught_however_it_is_wrapped`, `test_the_same_words_as_data_are_never_a_deploy` |
| Project-state R3.2 / R8.2: unbalanced quotes, nesting past the bound | `test_an_unreadable_command_with_a_deploy_word_is_judged_on_its_raw_words`, `test_nesting_past_the_bound_is_judged_on_raw_words` |
| The 2026-10-05 comparison with the old shell tests (ANSI-C quoting, echo and grep, heredoc substitution, timeout) | `test_the_cases_found_by_comparing_with_the_old_shell_tests` |
| Hook under 50 ms | `tests/test_budgets.py::test_bash_guard_hook_is_fast`; `test_reading_a_long_command_stays_fast` |
| 68: day-end provenance check | `skills/synthesis-agent-guardrails/tests/test_provenance_scan.py` |
| 77: advisory checks reach the model | the reply check's Stop decision, `tests/test_reply_check.py` |
| File links in replies, both directions | `tests/test_reply_check.py` (file-link tests) |

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-agent-guardrails
description: "Fail-closed session and tool guards for agent harnesses: cross-account artifact routing and publication authority today; output detectors landing next. Every guard ships inert until its principal configures it."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.3"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

# Coverage map: bitbucket 1.2.2 to 2.0.0, and the M3 script pass

Read when checking where a rule of the 1.2.2 text lives now (ruling D8). Every part of the 1.2.2 SKILL.md and where it lives now. Nothing was removed by the prose restructure; the M3 script pass below then cut the binding validator and turned its rule into binding rule 4.

| 1.2.2 section | Now |
|---|---|
| Frontmatter description (464 characters) | Shortened to 297 characters. It keeps every trigger phrase ("bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api") and names the PR lifecycle, reads, the `bkt api` escape hatch, repository binding and write safety. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on`, and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title and the three opening paragraphs (what `bkt` is, the rule in one line, companion skills) | SKILL.md (verbatim) |
| Install and pin | references/setup.md (verbatim); Binding rule 7 |
| Authenticate | references/setup.md (verbatim); Binding rule 8 |
| Configure connection context and bind each repository, with the context-host gotcha | references/setup.md (verbatim); Binding rule 8 |
| Explicit repository binding | SKILL.md (verbatim) until M3. In M3 its last paragraph, about `scripts/repository_binding.py`, was replaced by a short paragraph saying the rule is applied by the agent, and binding rules 4 and 5 were reworded the same way; the old lines are in [preserved.md](preserved.md) |
| Command catalog: Read, Write, Escape hatch | SKILL.md (verbatim); Binding rule 6 restates the `pipeline run` warning |
| `gh` → `bkt` map, with the no-labels and PR-states note | SKILL.md (verbatim) |
| PR queue | references/pr-queue.md (verbatim) |
| Safety rules 1 to 3 | Binding rules 1 to 3 (verbatim, same numbers) |
| When NOT to apply | SKILL.md (verbatim) |

## Lines the coverage check reports, and why

Before this map existed, `v5-skill-coverage-check.py` reported one line: the heading `## Safety rules`. This map quotes it, so the check now reports none. It was renamed: the three safety rules are now the first three Binding rules, word for word and with the same numbers, under the `## Binding rules` heading the v5 format requires. The moved text has no relative links, so no link paths changed.

## Scripts in v5 (M3)

Verdicts from the v5 code evaluation (tool scripts, bitbucket). Line counts are `wc -l`.

| Old file (lines) | Verdict | Now |
|---|---|---|
| `scripts/pr_queue.py` (283) | KEEP | Unchanged (283) |
| `scripts/repository_binding.py` (1,752) | CUT: no caller outside its tests | Binding rule 4 and the paragraph under "Explicit repository binding"; old text in [preserved.md](preserved.md) |
| `scripts/test_pr_queue.py` (395) | Kept | `tests/test_bitbucket_pr_queue.py`, E-numbers added to the test names, one new E76 test |
| `scripts/test_help_contract.py` (44), `scripts/fixtures/help-0.30.0.json` | Kept without the validator | `tests/test_bitbucket_skill_contract.py`, `tests/fixtures/help-0.30.0.json` |
| `scripts/test_repository_binding.py` (63) | Cut with the validator | E80 doc check in `tests/test_bitbucket_skill_contract.py` |

| Scenario | Test |
|---|---|
| E75 reviewers requested explicitly; a missing reviewer field is unscanned | `test_e75_reviewer_fields_are_requested_explicitly_for_the_named_repository`, `test_e75_missing_reviewer_field_is_unscanned_even_with_participants`, `test_e75_missing_or_invalid_reviewer_inventory_is_unscanned` |
| E76 ownership by uuid or account_id only | `test_e76_buckets_by_uuid`, `test_e76_matches_identity_by_account_id_when_reviewer_has_no_uuid`, `test_e76_identity_without_uuid_or_account_id_is_refused`, `test_e76_a_reviewer_named_like_the_user_is_not_the_user` |
| E77 no partial classifications | `test_e77_second_page_failure_discards_all_classifications`, `test_e77_repeated_pr_on_second_page_refuses_complete_scan`, `test_e77_page_cap_is_total_not_a_partial_success` |
| E78 404, timeout or missing `bkt` is unscanned with the reason | `test_e78_404_is_unscanned_with_the_stderr_reason`, `test_e78_timeout_is_unscanned`, `test_e78_missing_bkt_binary_is_unscanned` |
| E79 explicitly empty final page is a scanned empty queue | `test_e79_explicitly_empty_final_page_is_a_scanned_empty_queue` |
| E80 every repository-acting command names its repository | Binding rule 4; `test_e80_every_documented_repository_command_names_exactly_one_repo`, `test_e80_api_paths_are_canonical_and_literal` |

## Frontmatter before v5 (verbatim)

The 1.2.2 frontmatter, kept whole so the old description and keys stay on record.

```yaml
---
name: synthesis-bitbucket
description: "Work with Bitbucket Cloud repos through the open-source bkt CLI — PR lifecycle (list, view, diff, comment, approve, merge), repo/branch reads, and the bkt api escape hatch. Encodes auth setup, the context-host gotcha, a gh-to-bkt command map, and write-safety rules so agents use one consistent command surface instead of reinventing REST calls. Use when asked to: bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.2.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

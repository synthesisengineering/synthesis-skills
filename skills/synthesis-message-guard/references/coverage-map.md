# Coverage map: synthesis-message-guard 1.8.0 to 2.0.0 (v5)

Ruling D8: every part of the 1.8.0 text has a new home, or sits in
[preserved.md](preserved.md) with the reason it was cut. Code verdicts come from the v5
code evaluation (guards and rituals report, message-guard rows and its section table).

## Contents

- Coverage check result
- SKILL.md sections
- Reference files and assets
- message_guard.py, section by section
- Edge cases and the tests that hold them
- Frontmatter before v5 (verbatim)

## Coverage check result

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-message-guard
synthesis-message-guard: 367 old lines, 0 not found verbatim
```

## SKILL.md sections

| 1.8.0 section | 2.0.0 home | How |
|---|---|---|
| Frontmatter description | SKILL.md description | Reworded to 300 characters |
| Version notes 1.3.0, 1.2.0, 1.1.0 | 1.2.0 header hygiene: binding rule 6 and composing.md; 1.3.0 example config: config.md and `config.example.json`; 1.1.0 | Reworded |
| "Prose rules do not survive ..." paragraph | SKILL.md purpose paragraph | Verbatim |
| Grounding-envelope pointer | preserved.md | Cut with the ledger |
| Why it exists | [composing.md](composing.md#why-it-exists) | Verbatim, plus what replaced the ledger |
| Architecture | SKILL.md purpose and procedure | Replaced: approval instead of ledger |
| Peer-session sends | preserved.md; composing.md (session messages are not correspondence) | Replaced by board messages |
| Currency claims carry read freshness | Binding rule 2; [composing.md](composing.md#why-it-exists) | Reworded: a rule for the agent |
| The ledger contract | [composing.md checklist](composing.md#before-you-ask-for-approval-the-checklist) | Each attestation kept as a check before approval |
| Modes | Procedure; preserved.md | Replaced by the hook and `synthesis approvals` |
| Guarantee 1, fail closed | Binding rule 9; config.md | Reworded |
| Guarantee 2, positive controls (2026-08-03) | [config.md calibration](config.md#calibration); tests | Reworded: the controls are tests |
| Guarantee 3, calibration | [config.md calibration](config.md#calibration) | Verbatim |
| Guarantee 4, monitored across clients | [config.md wiring](config.md#wiring-and-health) | Replaced by `synthesis doctor` |
| Known limits | [composing.md](composing.md#known-limits--stated-not-hidden) | Verbatim, ledger wording adjusted |
| Composing under the guard | [composing.md workflow](composing.md#the-honest-workflow) | Steps 1 to 4 verbatim; step 5 rewritten for approval |
| Multipart integrity and email defaults | Binding rules 1, 3, 4; [composing.md checks](composing.md#what-the-guard-checks-and-the-words-it-blocks-with); [config.md](config.md#keys) | Rules kept; constructors cut |
| Owner-managed capability enrollment | preserved.md | Cut (verdict) |
| Engine migration | preserved.md | Cut (verdict) |
| Readback and ritual monitoring | Binding rule 8 (readback); preserved.md (tools) | Tools cut (verdict); readback kept as procedure |
| Related | [composing.md](composing.md#related) | Verbatim, plus two links |
| Other human-readable correspondence | Binding rule 4; composing.md | Reworded |
| Configuration and policy preflight paragraph | preserved.md | Cut (verdict) |

## Reference files and assets

| 1.8.0 file | 2.0.0 home |
|---|---|
| references/grounding-envelope.md | preserved.md, verbatim (the ledger is gone) |
| patterns.example.json | `config.example.json` (v5 keys); [config.md](config.md#from-the-1x-patterns-file) maps every old key |
| (new) references/composing.md, references/config.md | Gathered from SKILL.md |

## message_guard.py, section by section

| Lines | Section | Verdict | Now |
|---|---|---|---|
| 1-276 | Config, ledger store, orphan sweep, validation | SLIM | `paths.config()` and the hook's fail-closed load |
| 277-403 | Register scan, whole-call digest, field extraction | KEEP | `guards.message_problems` (every string, rendered HTML too); `approvals.digest` of the whole call |
| 404-757 | Capability enrollment, catalog, readiness | CUT | none |
| 758-1302 | HTML and paragraph checks; constructors, MIME, readback, monitoring | KEEP the checks; CUT the rest | `guards._rendered`, `guards.broken_paragraph`, email rules in `message_problems` |
| 1303-1400 | Signature wire check; header hygiene | KEEP | `message_problems` (markdown in email, persona domain as text, Message-ID checks) |
| 1401-1564 | Grounding envelope and ledger validation | REPLACE | `synthesis/approvals.py` |
| 1565-1649 | Peer-session send resolution | REPLACE | `synthesis msg` (board) |
| 1650-1829 | The gate | SLIM | `guards.check_send` |
| 1830-2401 | Doctor | SLIM to the positive controls | `tests/test_send_guard.py`, `tests/test_signed_message.py` |
| 2402-2808 | Inline test suite | Move to tests | `tests/test_send_guard.py` |
| 2809-3165 | Program mode, migration | CUT | none |
| 3166-3314 | CLI | SLIM | none needed: the hook and `synthesis approvals` |

The seven 1.8.0 test files (2,549 lines) are replaced by `tests/test_send_guard.py`,
`tests/test_signed_message.py` and the send cases in `tests/test_guards.py`.

## Edge cases and the tests that hold them

Section 3 of the guards evaluation, scenarios 21 to 30:

| Scenario | Test |
|---|---|
| 21 any field changed after approval blocks | `test_an_approval_covers_every_field_of_the_call` |
| 22 two sessions' approvals never overwrite each other | `test_two_sessions_composing_at_once_keep_separate_approvals` |
| 23 signed message passes, miscased brand blocks | `test_positive_controls_...`, `tests/test_signed_message.py` |
| 24 banned phrase split by tags or entities | `test_a_banned_phrase_hidden_by_markup_or_entities_still_blocks` |
| 25 escaped or unbalanced Message-ID | `test_threading_headers_carry_literal_message_ids` |
| 26 line break in a paragraph; plain-text-only email | `test_email_is_html_with_whole_paragraphs_and_no_markdown`, `test_a_plain_only_transport_is_allowed_only_when_the_principal_lists_it` |
| 27 markdown in email blocks; Slack mrkdwn passes | `test_email_is_html_...`, `test_chat_text_never_breaks_a_paragraph_but_lists_quotes_and_code_keep_their_lines` |
| 28 session-to-session `send_message` is not email | `test_session_to_session_messages_are_not_correspondence` |
| 30 CI without `~/.synthesis` uses the example config | `tests/test_send_guard.py` loads `config.example.json` and says so |
| Persona signature must be a link (2026-08-30) | `test_a_persona_signature_is_a_link_on_channels_that_render_links` |
| Unreadable config blocks sends | `tests/test_guards.py::test_unreadable_config_blocks_sends_and_bash_but_not_other_tools` |

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-message-guard
description: Fail-closed pre-send enforcement for agent-drafted correspondence. A PreToolUse hook blocks every message-sending or draft-creating tool call unless the outgoing text passes a deterministic register scan AND a fresh, single-use grounding ledger — sha256-bound to the entire tool input — attests that the composing agent read the full thread, searched prior correspondence, and mapped every factual claim to a source. Use when setting up, debugging, or composing under the guard; when a send is blocked; or when asked about message grounding, voice enforcement, or pre-send gates.
license: "Apache-2.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "1.8.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

# Coverage map: slack sync 3.14.0 to 4.0.0, and the M3 script pass

Read when checking where a rule of the 3.14.0 text lives now (ruling D8). Every part of the 3.14.0 SKILL.md and where it lives now. The prose restructure removed nothing; the M3 script pass below retired the acquisition, token and retrofit text, verbatim in [preserved.md](preserved.md), with the reason for each.

| 3.14.0 section | Now |
|---|---|
| Frontmatter description | Shortened to under 300 characters; keeps Slack MCP, local transcripts, the daily action plan, thread re-reads, and every trigger phrase (slack sync, sync from slack, check slack, read channels, sync messages, sync transcripts, what's new on slack). "Workspace-scoped repos" and "mid-day re-syncs with thread staleness detection" are covered by the binding rules and the step outline |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 4.0.0; `format: v5` added |
| Title and first paragraph | SKILL.md (verbatim) |
| Second and third paragraphs (protocol versus config; pointers to version history, formats and templates) | references/configuration.md, "Protocol and config" (verbatim apart from the pointer line's link paths); the pointers are also SKILL.md Contents entries |
| Configuration (YAML with schema comments) | references/configuration.md (verbatim) |
| Multi-workspace registry (v3.11.0), path resolution summary, ADR-014 paragraph | references/configuration.md (verbatim) until M3, when the registry paragraph was restated for the workspace map in the synthesis config (no tokens; `slack_workspaces.py` without `doctor`); old paragraph in preserved.md. Path summary and ADR-014 unchanged |
| Prerequisites | references/configuration.md (verbatim) |
| ⛔ NEVER Use Slack Search API for Lookups: first paragraph and "The only valid uses" | SKILL.md (verbatim) and references/lookups-and-absence.md (verbatim); binding rule 1 |
| The rest of that section: Slack-search failure paragraph, The question-shape trigger, A zero-result search is NEVER evidence of absence, Backfills and archive imports | references/lookups-and-absence.md (verbatim apart from three link paths); binding rules 1, 2 and 11 |
| Sync Protocol, Steps 0 to 5 and Draft Message Format (MANDATORY) | references/sync-protocol.md (verbatim apart from four link paths; in M3 the two acquisition paragraphs were replaced by the Step 1 read rules, Source D and the Step 4 denominator and Step 5 never-sends bullets were added, and the `synthesis exec-public` and `--acquisition-evidence` commands were restated; old lines in preserved.md). SKILL.md keeps the same step headings, the protocol's opening sentence and a one-line outline of each step carrying its exact command; binding rules 3 to 7 and 10 distill the steps |
| Transcript Files and Permalinks | references/sync-protocol.md (verbatim apart from one link path; the retrofit bullet retired in M3); binding rule 9 |
| Provenance Discipline and its five subsections | references/provenance-and-errors.md (verbatim; in M3 the Automated backstop paragraph, about an old private Stop hook, was restated for v5's turn-end reply check); SKILL.md keeps the heading with a one-line summary; binding rule 8 |
| Date Verification | references/provenance-and-errors.md (verbatim); binding rule 12 |
| Following Continuing Conversations | references/lookups-and-absence.md (verbatim) |
| Error Handling | references/provenance-and-errors.md (verbatim) |
| When This Skill Runs | SKILL.md (verbatim) |

## Text other tests read

Before M3, three tests read this skill's prose: synthesis-daily-rituals' `test_skill_documents.py` and `test_sync_watermark.py`, and this skill's `scripts/test_preflight.py`. The daily-rituals helper removed or rewrote its two in the same milestone. This skill's preflight test moved to `tests/test_slack_preflight.py`; it still requires "scripts/preflight.py --config" and "census" (now read from SKILL.md and references/sync-protocol.md together), the absence of "produced by hand", and that the daily-rituals skill's Markdown names `preflight.py` and "never a stored copy".

## Existing reference files and templates

- version-history.md and transcript-formats.md are over 150 lines, so each gained a short contents list under its title.
- version-history.md gained a v4.0.0 entry, newest first, as its own convention requires, and two broken template links were corrected (see below). In M3 the v4.0.0 entry gained a paragraph on the script verdicts.
- transcript-formats.md: one pointer was corrected (see below). In M3 its "Deterministic acquisition output" section and the retrofit section were retired (verbatim in [preserved.md](preserved.md)); a short "Older daily plans" note replaces the latter.
- cross-workspace-visibility.md: in M3 its registry and token lines were restated for the workspace map in the synthesis config (old lines in preserved.md); the doctrine is unchanged.
- slack-token-guide.md: retired whole in M3 with the token machinery it described (verbatim in preserved.md).
- templates/draft-block.md and templates/sent-marker.md are unchanged.

## Scripts in v5 (M3)

Verdicts from the v5 code evaluation (tool scripts, slack sync). Line counts are `wc -l`.

| Old script (lines) | Verdict | Now (lines) |
|---|---|---|
| `thread_checker.py` (583) | SLIM: keep the checklist half | `scripts/thread_checker.py` (196): every thread parent and every unsent draft's target; a draft's target is now read from its own section only (reading 20 lines past the next heading took the following draft's target) |
| `scripts/preflight.py` (173) | KEEP, "drop the `--json` set it emits for the gate" | `scripts/preflight.py` (251). `--json`/`--out` kept: their consumer is not the cut acquisition gate but the watermark status (`sync_watermark.py status --targets-from`), which the daily-rituals slim keeps, and whose file must be derived this run (2026-09-01). PyYAML replaced by a standard-library block-YAML reader (or JSON), so it runs on Apple's Python 3.9 |
| `scripts/slack_workspaces.py` (427) | SLIM: the map and the visibility rule | `scripts/slack_workspaces.py` (91), reading `slack_workspaces` from the synthesis config; `init`, `list`, `doctor`, `readable` and tokens gone |
| `scripts/acquire.py` (585), `scripts/connector_replay.py` (698) | CUT: served the acquisition gate | Read rules in sync-protocol.md |
| `scripts/slack_read.py` (280) | CUT: never configured | The Slack connector |
| `retrofit_permalinks.py` (294) | CUT: job finished | — |
| Tests (1,403 lines in `scripts/`) | Kept where they test kept code | `tests/test_slack_preflight.py`, `tests/test_slack_thread_checker.py`, `tests/test_slack_workspaces.py`, `tests/test_slack_sync_protocol.py`; `test_preflight_is_in_the_shared_ci_group` (read the retired `validate.yml`) removed |

## Edge cases and where each is held

| Scenario | Rule | Test |
|---|---|---|
| E01 whole thread re-read, no lower bound | sync-protocol.md Step 2 ("Never use the `oldest` parameter") | `test_slack_sync_protocol.py::test_e01_*` |
| E02 replies to older threads found by search | Step 2 Source D | `test_e02_*` |
| E03 DMs read by `D` id; `U` refused; missing `D` reported by name | preflight | `test_slack_preflight.py::test_e03_*` |
| E04 quiet only after a positive control | Step 1 read rules; binding rule 13 | `test_e04_*` |
| E05 repeated cursor or unclear end is incomplete | Step 1 read rules | `test_e05_*` |
| E06 detailed reads | Step 1 read rules | `test_e06_*` |
| E07 every declared target re-read from its last read moment | Step 1 ("Every declared target is read every sync") | `test_e07_*` |
| E08 a message from another channel is not filed under the requested one | Step 1 read rules | `test_e08_*` |
| E09 a saved connector read advances the watermark, no token or receipt | Step 1 read rules; Step 4; binding rule 6 | `test_e09_*` |
| E10 an unsent draft's target thread is on the re-read list | thread checker | `test_slack_thread_checker.py::test_e10_*` |
| E11 Slack Connect messages saved like any other | Step 1 read rules | `test_e11_*` |
| E12 isolated mode reads no other workspace | cross-workspace-visibility.md; `slack_workspaces.py` | `test_slack_workspaces.py::test_e12_*` |
| E13 a sync calls no send or draft tool | Step 5; binding rule 14 | `test_e13_*` |
| E14 the report names its denominator and every unread target | Step 4; binding rule 13 | `test_e14_*` |

## Lines the coverage check reports, and why

Since M3 the check reports two lines, deliberately: references/version-history.md, "Aggregation conventions", and references/transcript-formats.md, "Channel file", the example channel file names. The 3.14.0 lines named channels of a client workspace; this is a public repository (requirement R7.4), so the examples are now generic (`team-general.md`, `eng-pull-requests.md`) and the old lines are not quoted anywhere in the skill. They are readable with `git show origin/main:skills/synthesis-slack-sync/references/version-history.md` and `.../transcript-formats.md`.

Thirteen lines are not carried over verbatim; `v5-skill-coverage-check.py` reported them until this block quoted them.

- Nine lines of the 3.14.0 SKILL.md moved into references/ with their wording unchanged and only a relative link target adjusted, because a link written for SKILL.md breaks one directory down (`references/x.md` became `x.md`, `templates/x.md` became `../templates/x.md`, `../synthesis-x/...` became `../../synthesis-x/...`): the pointer line to version history, formats and templates (configuration.md); the grounding-discipline paragraph, the backfill analysis rule and the catchup-ledger line (lookups-and-absence.md); the acquisition-entry and acquisition-evidence paragraphs, the two draft-template lines and the transcript-formats pointer (sync-protocol.md).
- Two lines of references/version-history.md had a broken link fixed: the v3.3.0 entry linked `templates/draft-block.md` and `templates/sent-marker.md` relative to SKILL.md's folder since v3.9.0 moved it into references/, so both links pointed at files that do not exist. They now use `../templates/`; the words are unchanged.
- Two lines of references/transcript-formats.md were reworded deliberately: they said the binding rules are summarized in SKILL.md under "Transcript Files and Permalinks", a section that now lives in references/sync-protocol.md. They now point there and to SKILL.md binding rule 9.

The lines below are exactly as 3.14.0 had them, kept only as a record.

````markdown
Version history and the incidents behind each rule: [references/version-history.md](references/version-history.md). Transcript and permalink formats: [references/transcript-formats.md](references/transcript-formats.md). Draft templates: [templates/draft-block.md](templates/draft-block.md) and [templates/sent-marker.md](templates/sent-marker.md).
Absence claims are a grounding problem: a negative result is only evidence if the instrument could have produced a positive one. The general discipline — positive controls, scoped negative findings, truncated-output rules — lives in [synthesis-grounding-discipline](../synthesis-grounding-discipline/SKILL.md); this section is its Slack instance.
**The analysis rule, which matters more than the retrieval.** Everything in a backfill is history, and it all reads present-tense. **Do not report anything from it as currently open without reconciling against newer material already held locally.** A conversation that stops is not a question that stayed unanswered — the thread often continued somewhere else. Scope every finding to where you looked ("unanswered in this conversation through <date>"), and title the output by what it establishes: a list of where conversations stopped, not a list of open loops. The general discipline, with the incident that produced it, is entry 12 of [synthesis-grounding-discipline](../synthesis-grounding-discipline/SKILL.md).
Candidate open items surfaced this way are exactly what [synthesis-catchup-ledger](../synthesis-catchup-ledger/SKILL.md) exists to classify — route them through its still-relevant / obsolete / ambiguous triage rather than reporting them raw.
Use `synthesis exec-public synthesis-slack-sync/scripts/acquire.py` with the explicitly declared structured Web API adapter, following [declared acquisition entries](../synthesis-daily-rituals/references/acquisition-entry.md). Recorded connector calls remain source custody, but their rendered message strings cannot prove author or message boundaries. Connector replay therefore reports a blocking problem and refuses attributable archives or watermark advancement; repeating those same reads cannot repair that limitation. The owner consumes preflight and the current registry and never discovers targets or falls back to direct credentials. Keep unsupported connector coverage UNKNOWN.
Before advancing a Slack watermark, read the mandatory [acquisition evidence contract](../synthesis-daily-rituals/references/acquisition-evidence.md). Use detailed channel/DM reads with complete pagination, independently search within the declared window for replies (including old parents), and follow the union of local known threads, history indicators, and search parents. `thread_checker.acquire_channel` provides this bounded read-only adapter flow. Retain actual in-window positive controls and raw call references; historical controls or empty/concise reads cannot establish absence. Save exact message IDs and bytes, then pass the complete receipt to `sync_watermark.py advance --acquisition-evidence`. If a connector lacks required detail or pagination, report unknown coverage and keep the watermark.
The canonical structural format for a draft block lives in [`templates/draft-block.md`](templates/draft-block.md). Read it as the literal template; this section gives the protocol-level rules for when and how to apply it.
**When marking drafts as SENT** — see [`templates/sent-marker.md`](templates/sent-marker.md) for the canonical form. Summary: wrap the H3 title in `~~...~~`, and append a `**Sent:** <human-time> — by <Name> in <target> · (TS=...) <permalink>` paragraph between the body and the Grounding `<details>` block.
The per-channel, `_dms.md`, and `_group-dms.md` file shapes, the permalink construction rule, the `Send to:` line form, and the retrofit script are in [references/transcript-formats.md](references/transcript-formats.md). The rules that bind every write:
message takes. The binding rules are summarized in [SKILL.md](../SKILL.md)
("Transcript Files and Permalinks"); this file is the literal format.
- [`templates/draft-block.md`](templates/draft-block.md) — active draft template (schema v1)
- [`templates/sent-marker.md`](templates/sent-marker.md) — sent-state marker template (schema v1)
````

## Frontmatter before v5 (verbatim)

The 3.14.0 frontmatter, kept whole so the old description and keys stay on record.

```yaml
---
name: synthesis-slack-sync
description: "Slack channel sync protocol for AI-assisted workflows. Reads channels and threads via Slack MCP, saves to local transcript files in workspace-scoped repos, and updates person-scoped daily action plans. Handles mid-day re-syncs with thread staleness detection. Use when asked to: slack sync, sync from slack, check slack, read channels, sync messages, sync transcripts, what's new on slack."
license: "CC0-1.0"
depends_on: ["synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "3.14.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

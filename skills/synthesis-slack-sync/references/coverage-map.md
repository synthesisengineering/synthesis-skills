# Coverage map: slack sync 3.14.0 to 4.0.0

Every part of the 3.14.0 SKILL.md and where it lives now. Nothing was removed.

| 3.14.0 section | Now |
|---|---|
| Frontmatter description | Shortened to under 300 characters; keeps Slack MCP, local transcripts, the daily action plan, thread re-reads, and every trigger phrase (slack sync, sync from slack, check slack, read channels, sync messages, sync transcripts, what's new on slack). "Workspace-scoped repos" and "mid-day re-syncs with thread staleness detection" are covered by the binding rules and the step outline |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 4.0.0; `format: v5` added |
| Title and first paragraph | SKILL.md (verbatim) |
| Second and third paragraphs (protocol versus config; pointers to version history, formats and templates) | references/configuration.md, "Protocol and config" (verbatim apart from the pointer line's link paths); the pointers are also SKILL.md Contents entries |
| Configuration (YAML with schema comments) | references/configuration.md (verbatim) |
| Multi-workspace registry (v3.11.0), path resolution summary, ADR-014 paragraph | references/configuration.md (verbatim); the `scripts/slack_workspaces.py doctor` pre-sync check is also named in SKILL.md under Sync Protocol |
| Prerequisites | references/configuration.md (verbatim) |
| ⛔ NEVER Use Slack Search API for Lookups: first paragraph and "The only valid uses" | SKILL.md (verbatim) and references/lookups-and-absence.md (verbatim); binding rule 1 |
| The rest of that section: Slack-search failure paragraph, The question-shape trigger, A zero-result search is NEVER evidence of absence, Backfills and archive imports | references/lookups-and-absence.md (verbatim apart from three link paths); binding rules 1, 2 and 11 |
| Sync Protocol, Steps 0 to 5 and Draft Message Format (MANDATORY) | references/sync-protocol.md (verbatim apart from four link paths). SKILL.md keeps the same step headings, the protocol's opening sentence and a one-line outline of each step carrying its exact command; binding rules 3 to 7 and 10 distill the steps |
| Transcript Files and Permalinks | references/sync-protocol.md (verbatim apart from one link path); binding rule 9 |
| Provenance Discipline and its five subsections | references/provenance-and-errors.md (verbatim); SKILL.md keeps the heading with a one-line summary; binding rule 8 |
| Date Verification | references/provenance-and-errors.md (verbatim); binding rule 12 |
| Following Continuing Conversations | references/lookups-and-absence.md (verbatim) |
| Error Handling | references/provenance-and-errors.md (verbatim) |
| When This Skill Runs | SKILL.md (verbatim) |

## Text other tests read from SKILL.md

These tests read this SKILL.md, so the text they look for stays in it:

- `skills/synthesis-daily-rituals/scripts/test_skill_documents.py`: the headings "## ⛔ NEVER Use Slack Search API for Lookups", "### Step 0: Preflight", "### Step 2: Re-read ALL active threads", "#### Draft Message Format (MANDATORY)" and "## Provenance Discipline"; the phrases "A zero-result search is NEVER evidence of absence", `WINDOW_OLDEST`, `RESOLVED_CONVERSATION_ID`, `sync_watermark.py advance`, "own outbound", "Always record the TS" and "never invent a domain"; and the name of every file in references/ and templates/. Its moved-block checks read version-history.md and transcript-formats.md, whose headings are unchanged.
- `skills/synthesis-daily-rituals/scripts/test_sync_watermark.py`: `sync_watermark.py window`, `sync_watermark.py advance`, `WINDOW_OLDEST`, "own outbound", "unanswered", "status --since run", "preflight", "banned", `dm_id`, "### Step 0: Preflight" and "resolved-target list"; and the absence of `LAST_SYNC_TIMESTAMP`, "For each channel in the config" and "For each DM channel in the config".
- `scripts/test_preflight.py`: "scripts/preflight.py --config" and "census", and the absence of "produced by hand".

## Existing reference files and templates

- version-history.md and transcript-formats.md are over 150 lines, so each gained a short contents list under its title.
- version-history.md gained a v4.0.0 entry, newest first, as its own convention requires, and two broken template links were corrected (see below); nothing else in it changed.
- transcript-formats.md: one pointer was corrected (see below); nothing else changed.
- cross-workspace-visibility.md, slack-token-guide.md, templates/draft-block.md and templates/sent-marker.md are unchanged.

## Scripts and tests

Every script and test (`thread_checker.py`, `retrofit_permalinks.py`, `scripts/*.py`) is unchanged, and every documented command, flag and path is kept exactly as written, in SKILL.md, references/sync-protocol.md or references/configuration.md. `scripts/test_preflight.py::test_preflight_is_in_the_shared_ci_group` failed before this change and still fails: it reads `.github/workflows/validate.yml`, which the v5 branch replaced with `ci.yml`.

## Lines the coverage check reports, and why

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

## The 3.14.0 frontmatter

Kept whole, so the old description and keys stay on record.

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

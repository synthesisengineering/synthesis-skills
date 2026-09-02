# Slack sync — version history and rationale

The sync protocol lives in [SKILL.md](../SKILL.md). This file keeps the
release-by-release record of why each rule exists — the incidents and the
design choices — so the main document stays within the repository's
500-line budget without losing the reasoning. Newest first.

## v3.10.0 — The preflight script owns target resolution

v3.10.0 (2026-09-01) ships extraction item P2: `scripts/preflight.py` reads
the sync config, resolves the one read id per target (`dm_id` for DMs,
never the user id), validates the id prefix per class, prints the
resolved-target table with a prefix census, writes the declared set the
daily-rituals watermark gate consumes, and fails closed on an empty set or
a malformed config. Origin: on the day the gate shipped, a careful reader
with the config open — warned about the two-id trap minutes earlier —
still derived every DM target as a user id. A per-seat derivation is a
correctness surface, not a convenience, and the census turns a wrong
derivation into a visibly wrong shape.

## v3.9.0 — Restructured under the 500-line budget

v3.9.0 (2026-09-01) moves version history, the transcript and permalink
formats, and the draft example out of SKILL.md into `references/` (this
file and `transcript-formats.md`), leaving every step of the protocol and
every rule in the main document. A pinned test in synthesis-daily-rituals
(`scripts/test_skill_documents.py`, the CI group both skills share) fails
when SKILL.md reaches 500 lines, when a load-bearing rule anchor leaves it,
when a moved block is missing from its reference, or when a reference or
template is not linked from the main document. Nothing in the protocol
changed.

## v3.8.0 — Windows are computed, coverage is recorded, the user's own outbound counts

v3.8.0 (2026-09-01) closes three defects from one day. A hand-typed `oldest`
(07:50 *today* instead of yesterday) reported five channels empty that were
not; two mid-day syncs re-read only the targets the morning had skipped,
so a DM answered at 09:27 was reported unanswered at 17:51 on a 09:15 read;
and the user's own replies were not treated as sweep state that discharges
owed items. Steps 1, 3, and 3b now take `oldest` from
`sync_watermark.py window` (synthesis-daily-rituals) and quote its
human-readable bounds in the report; Step 4 records every saved read with
`sync_watermark.py advance --target`; Step 5 cross-references the user's
own outbound against every owed item and forbids "unanswered" or "unsent"
on a read older than the current run, which `status --since run` proves.
Every sync re-reads every declared target — "already read today" is a
statement about the past.

## v3.7.0 — The sweep steps consume preflight instead of contradicting it

v3.7.0 (2026-08-29) closes the gap an external adversarial review found in
v3.6.0: the rule banned config-derived ids while the numbered steps still
said "for each channel in the config." Step 0 now defines the mandatory
resolved-target preflight, Steps 1/3/3b iterate only its output, an empty
resolved set refuses the sweep, and unresolved surfaces are reported as
unresolved. The deterministic preflight script is extraction item P2; the
contract binds now either way. Frontmatter version also catches up — v3.6.0
shipped with stale skill metadata.

## v3.6.0 — Read targets come from preflight; deriving ids in the sweep is banned

v3.6.0 (2026-08-27) fixes a class of bug that hides for months and then looks
like something else entirely.

**The defect.** A DM config entry carries two id-like fields: `id`, the user id
(`U…`), and `dm_id`, the conversation id (`D…`). A reader that reaches for `id`
hands a user id to a conversation-read API. That resolves implicitly while the
account is active, so the mistake is invisible — and it starts failing only once
that person leaves. The symptom then appears as a phantom "dead surface" for
exactly one person, which reads as a configuration problem. It cost days of
false unreadable-DM reports and a wrong public claim that the config was
misaligned, when the config was correct and the reader was not.

**The rule.** Sweeps take their read targets from preflight output, which emits
the resolved read id per surface and fails closed when one cannot be resolved.
Deriving ids from config inside the sweep is banned. A sweep that cannot obtain
a resolved read target reports that surface as unresolved — never as unreadable,
and never as a config defect, since it has no evidence for either.

**Generalize it.** Any config whose entries carry two id-like fields has this
trap, and the failure is always asymmetric: the wrong field usually works, so
the bug is discovered by an unrelated change months later. Where two ids exist,
resolution belongs in one place that fails closed, and every reader takes the
resolved value from it rather than choosing a field.

## v3.5.0 — Backfills and archive imports

v3.5.0 (2026-08-19) adds a section for the operation a windowed sync is not: reading a
conversation to its first message. Retrieval rules (page to the true beginning and report the
earliest date as proof, expand every thread, name a partial capture by its date range rather
than "full history") sit alongside the rule that matters more — **everything in a backfill is
history and reads present-tense, so nothing in it may be reported as currently open without
reconciling against newer material already held.** Origin: a backfill reported a colleague's
settled employment arrangement as a six-week-old open loop, to the person who had settled it,
while a calendar query run two hours earlier already showed the completed account migration.

## v3.4.0 — Question-shape trigger + zero-result absence protocol

v3.4.0 (2026-08-18) hardens the transcripts-first rule at the two seams where it
historically failed to fire. First, the **question-shape trigger**: verification
questions ("did X get sent?", "did anyone reply?", "did that happen?") are
historical lookups wearing a different hat — the rule triggers on the question
shape, never on whether the task felt like a lookup. Second, **a zero-result
search is never evidence of absence**: absence claims require a bounded direct
channel read with the bounds stated in the finding, and any null from a
modifier-bearing query must be re-run without the modifier before it is trusted.
Both sections live inside the "NEVER Use Slack Search API" block; the general
evidence discipline is cross-linked to the new synthesis-grounding-discipline
skill.

## v3.3.1 — Runtime-resolved checker

v3.3.1 (2026-07-29) invokes the thread checker relative to the skill root
resolved by the active plugin runtime. The protocol no longer binds Slack sync
to an `.agents` copy, so Codex and Claude Code execute the same checker from the
same committed skill version.

## v3.3.0 — Two-Tier Draft Block: Templates Move into Files

In v3.3.0 (2026-04-29), the draft block format gets restructured around a glanceable summary at the top and collapsed verification detail at the bottom. The templates also move out of this prose file and into dedicated files in `templates/`.

The earlier shape (v3.2.0 and prior) put all metadata at uniform visual weight in the rendered output: title + Send-to + body + Grounding bullets all rendered inline as paragraphs and lists. That made the most frequent purpose of the daily plan — glanceable "what's next" reading — hostile, because the verification trail (Grounding) crowded the substance (the message body) at the same visual scale.

v3.3.0 separates two tiers explicitly in the source:

1. **Always-visible glance surface.** Brief H3 title (≤60 char target, ≤80 hard cap), compressed `**Send to:**` line, optional one-line context, the message body itself.
2. **Click-to-expand detail.** Grounding wrapped in `<details>/<summary>` — markdown-it (and any CommonMark-compliant renderer) renders this as a native HTML collapsible. Closed by default, click to expand. The verification trail is one click away, not occupying glance-bar real estate.

The brief-title rule is the same axis: keep H3 a scannable label, not a summary. Routing metadata, status markers, IDs, timestamps, commit hashes, compound clauses NEVER go in the title; they live in `**Send to:**`, the optional context paragraph, the body, the Grounding `<details>`, or the `**Sent:**` paragraph.

### Templates in their own files

The canonical formats now live as standalone artifacts:

- [`templates/draft-block.md`](templates/draft-block.md) — active draft template (schema v1)
- [`templates/sent-marker.md`](templates/sent-marker.md) — sent-state marker template (schema v1)

The agent reads the template files literally when writing a draft into a daily plan. SKILL.md describes WHEN and WHY to use the template; the template files ARE the canonical structural form. This separation establishes a pattern the rest of the synthesis-skills ecosystem can adopt — `templates/<name>.md` as a sibling to `SKILL.md` for any skill whose protocol generates a structural artifact.

Why split:

- The template IS the producer-consumer contract artifact. Easier to diff template changes without scrolling through protocol prose.
- Agents can read template files directly (cheap to load, no parse-the-protocol-prose-to-find-the-format).
- Independent versioning: protocol stays at v3.x; template can ship its own schema version (`schema v1` in the file header).

### Backward compatibility

Pre-v3.3.0 draft sections (everything inline at uniform visual weight) continue to render correctly through the cockpit's existing parser — the parser doesn't require `<details>` blocks, just recognizes them when present. New drafts written by agents should follow the v3.3.0 templates. Agents rewriting an existing draft for any reason (mid-day update, edit before send, mark sent) should also rewrite the structure to the v3.3.0 form at that opportunity.

This release follows the producer-consumer-contract pattern: when the consumer is the synthesis-console cockpit and the producer is a generative agent, the format and the parser must change together. Cross-reference: synthesis-console `docs/cockpit-design.md` "Drafts" section.

## v3.2.0 — Canonical Sent-State Marker Location

In v3.2.0 (2026-04-29), the prescribed format for marking a draft as SENT changes from H3-jammed metadata to a separate `**Sent:**` paragraph below the draft body.

The pre-v3.2.0 form jammed the entire SENT metadata into the H3 heading text:

```markdown
### ~~Draft N: title~~ ✅ SENT by Rajiv at Thu Apr 2 6:16 PM EDT in #channel-name
```

That format renders as four lines of giant strikethrough in synthesis-console (H3 typography is ~1.75rem; long heading text wraps painfully). It also breaks the cockpit's sent-state detection — synthesis-console's parser looks for `**Sent:**` paragraphs to recognize sent drafts and replace the action bar with a "Sent" badge + "Open in Slack" link. With SENT in the H3, the parser doesn't notice, and the user sees Copy/Edit/Send buttons on a draft that already shipped.

The v3.2.0 canonical form keeps the H3 short and puts the metadata in its own paragraph:

```markdown
### ~~Draft N: title~~

**Send to:** ...

` ` `
[Message text]
` ` `

**Sent:** Thu Apr 2 6:16 PM EDT — by Rajiv in #channel-name (TS=1775141956.643419) https://acme.slack.com/archives/C0XXXXXX/p1775141956643419

**Grounding:**
- ...
```

**Backward compatibility.** The skill's `thread_checker.py` and synthesis-console v0.8.6+'s parser both accept the legacy H3-jammed form as well as the new canonical form. Existing daily-plan files don't need to be rewritten retroactively — but new SENT markers should use the canonical form, and any time the agent rewrites a sent draft for any reason, it should bring it to the canonical form.

This release follows the same producer-consumer-contract pattern as recent updates to other skills: when the consumer is the synthesis-console cockpit and the producer is a generative agent, the format and the parser must change together. Cross-reference: synthesis-console's `docs/cockpit-design.md` "Drafts" section.

## v3.1.0 — Workspace Domain, Permalinks, and Provenance Discipline

In v3.1.0 (2026-04-29), the skill gains three changes that work together:

1. **A new optional `slack_workspace_domain` config field.** Each project's `slack-sync.yaml` declares the Slack workspace's URL host (e.g., `acme.slack.com`). The skill stays generic — workspace-specific values live in per-project config, never hardcoded.

2. **Clickable permalinks replace bare Unix timestamps in transcript and draft formats.** Previous format wrote `(TS: 1234567890.123456)` as visible text. The new format hides the TS inside a Slack permalink URL — the visible text is the human-readable date/time, the link target is `https://{slack_workspace_domain}/archives/{channel_id}/p{ts_no_dot}`. The TS is still machine-readable (extractable from the URL); it's just not cluttering the rendered view in synthesis-console or any other Markdown viewer. Both formats are accepted by `thread_checker.py` during the transition; new sync output should use the permalink form when `slack_workspace_domain` is configured.

3. **Provenance discipline becomes explicit.** Every `## ... sync (~HH:MM TZ)` section header added to a transcript file MUST be backed by a `slack_read_channel` or `slack_read_thread` call in the same turn. Section bodies may ONLY contain messages those MCP calls returned. If MCP returned no new messages, the section says "No new messages since last sync" and stops — no quotes, no TSes, no claims about specific people having sent specific things. See the dedicated "Provenance Discipline" section below for the full rule and the rationale (2026-04-29 fabrication incident).

### Why these three changes are coupled

Permalinks make TSes machine-traceable in the file (every linked time is a TS visible in the URL), which makes provenance violations grep-able. The Stop-hook backstop at `~/.claude/hooks/quote-provenance-checker.py` looks for TSes that appear in transcript writes but nowhere else in the session — and it parses TSes from BOTH the legacy `(TS: ...)` text and the new `/pNNNNNNNNNNNNNNNN` URL form. The format change and the discipline change reinforce each other.

## v3.0.0 — Per-Channel-Per-Day Layout

In v3.0.0 (2026-04-22 afternoon), the transcript layout changed again within the same day as v2.0.0 was released. The refinement:

**Transcripts now live one-file-per-channel-per-day** inside a dated directory:

```
{transcripts_repo}/{transcripts_path}/slack/
├── YYYY-MM-DD/
│   ├── <channel-name>.md       (one file per channel)
│   ├── _dms.md                  (all 1:1 DMs for the day, aggregated)
│   ├── _group-dms.md            (all group DMs for the day, aggregated)
│   └── _misc.md                 (cross-channel sync notes, if any)
└── _historical-pre-v3/          (legacy pre-v3 content if any)
```

### Why v3.0.0

v2.0.0 used one-file-per-day-per-type (`channels/YYYY-MM-DD.md`, `dms/YYYY-MM-DD.md`, `group-dms/YYYY-MM-DD.md`). That worked but had two weaknesses:

1. **Heavy days produced large channel files.** A busy day with 50+ active channels would pack everything into one file.
2. **Type-based directories made new primitives awkward.** Adding Slack huddles or canvases would mean new top-level folders.

Per-channel-per-day solves both: each file is scoped to one channel's activity on one day (naturally smaller), and new primitives within Slack are new file patterns within the same dated dir, not new folders.

### Aggregation conventions

- **Channels get one file each per day.** `mmc-product-growth-squad.md`, `tech-csa-pull-requests.md`, etc.
- **DMs are aggregated** into `_dms.md` per day. DMs are typically lower-volume; daily context across all people is more useful than per-person files.
- **Group DMs are aggregated** into `_group-dms.md` per day. Same rationale.
- **The `_`-prefix** on `_dms.md` and `_group-dms.md` sorts them to the top of the directory listing, visually signaling they are aggregators rather than channel files.

### `-private` Discovery Protocol (ADR-014)

Any repo matching `ai-knowledge-*-private` is filtered from auto-discovery by default. This skill writes to a `-private` repo intentionally — the config file points at it explicitly. Other tools (ragbot auto-discovery, etc.) must NOT include these repos in their discovery scans unless running in explicit owner context. A sentinel file `.ai-knowledge-private-owner` at the repo root confirms ownership.

## Why Each Step Matters

These steps were developed through real incidents, not theory:

- **Step 2 (thread re-reading):** On 2026-03-24, a mid-day sync skipped thread re-reads. The action plan showed a draft as "unsent" when the user had already sent it hours earlier. The agent proposed sending it again, which would have been a duplicate message.
- **Step 4 (save to local):** Transcripts are the persistence layer. Without them, every sync starts from scratch, re-reading entire channels. With them, syncs are incremental and fast.
- **Step 5 (action plan update):** The action plan is the user's dashboard. If it shows stale information (unsent drafts that were sent, unresolved items that were resolved), the user makes wrong decisions.

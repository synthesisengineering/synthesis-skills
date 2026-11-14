# Preserved: the 2.45.1 SKILL.md, part 2 of 2 (verbatim)

Lines 207 to 500 of the 2.45.1 SKILL.md, word for word: draft rules, plan structure, the
mid-day, observer and concurrent-seats modes, the Day-End Checklist, the persistence protocol
and audio alerts. History, not instructions; see [coverage-map.md](coverage-map.md) for where
each rule lives in v5. Part 1 is [preserved-skill-v2-part1.md](preserved-skill-v2-part1.md).

Contents: Draft Message Rules · Daily Plan Structure · Mid-Day Sync Protocol · Vacation /
Observer Mode Ritual · Concurrent-Seats Mode Ritual · Day-End Checklist (modes, Steps 1 to 11) ·
Ritual Persistence Protocol · Autonomous Work and Audio Alerts.

---


## Draft Message Rules

Every draft is grounded, temporally correct, Slack-formatted, and numbered. The full protocol — research by question type, the investigate-first rule with its incident, the verification checklist, formatting examples, and appreciation quality — is in [references/draft-grounding.md](references/draft-grounding.md). The rules:

- **Ground every draft in primary sources before writing** — code, config, PRs, `git log`, deploy state, instruction files — never in transcripts or conversation memory alone; cite file paths, PR numbers, config values, or SHAs; flag any claim that cannot be verified instead of guessing. Applies to morning messages, mid-day replies, day-end communications, and ad-hoc requests alike.
- **Investigate first, ask questions later.** Before drafting a reply to a bug report or user issue, spend ten minutes in the code, config, and logs; if the fix fits in those minutes, ship it and lead the reply with the fix. Ask only for what you genuinely cannot obtain yourself.
- **Temporal integrity at send time, not write time.** Check whether the recipient already has the information, whether forward-looking statements still hold, whether a scheduled message uses the right tense, what happened since drafting, and whether the topic moved to another channel or medium — sweep every synced surface and email for the recipient and topic, re-pull full email threads before replying, and give drafts older than 24 hours full re-verification.
- **Verification checklist before finalizing:** every technical claim cites a source; every status claim is verified against the live system; every attribution is cross-checked (`gh pr view`, `git log`); no stale information — the target thread re-read via MCP AND the topic swept across other channels, DMs, and email; numbers come from tool output; temporal integrity passes.
- **Pre-send review gate:** every drafts section carries the verbatim reviewer notice before its first draft — drafts are research-backed starting points the human reads fully, edits into their own voice, and judges for the moment.
- **Slack formatting:** a blank line after every bullet (otherwise they collapse); Slack markdown (`*bold*`, `_italic_`, `>` quotes, backtick code); a thread locator on every reply draft (channel, human-readable parent time, author, first ~10 words; the TS as secondary reference); concise — over ~15 lines folds behind "Show more".
- **Draft numbering:** sequential integers (Draft 1, Draft 2, …), never letters or `K-2` sub-versions; before adding a draft, scan for the highest existing `Draft N` and use N+1; a retracted draft keeps its number with a `— retracted` marker and a pointer to the session log rather than renumbering.
- **Appreciation is specific:** name the work product, what made it good, and the observable impact; generic praise is weak and reads as automated.

---

## Daily Plan Structure

The daily plan is both a live dashboard and the day's record. **Preserve all information, reorganize for clarity:** never delete completed tasks, sent messages, timestamps, or decisions; consolidate freely so the file has ONE section per concern and reads cleanly top to bottom after every update — a full rewrite that preserves everything is maintenance, not data loss. The canonical structure, the H2 vocabulary the synthesis-console cockpit types (Decisions needed / Priority Tasks / Drafts — Ready to Send / Standup Highlights / Sent Messages / Waiting On Others / Open PR Queue / Sync state / Completed Today / Things to Know / Carried Items), the internal conventions the parser reads (decision options and `**Decided:**` markers, task done markers, draft `**Send to:**` and `**Sent:**` paragraphs, the 3-versus-4-backtick fence rule), and the file-revert protection protocol are in [references/plan-format.md](references/plan-format.md). Stay within that vocabulary; propose new section types as additions to the contract, never ad hoc. If a file revert is detected, re-read the entire file from disk, compare it with what you know was written, reconstruct anything missing from sync data and transcripts, and never silently accept the reverted file.

---

## Mid-Day Sync Protocol

The day-start checklist does a full sync. The user will ask for syncs repeatedly throughout the day ("sync from Slack", "what's new", "check channels"). **A sync request covers EVERY surface the workspace routinely syncs — not Slack alone, and not only chat surfaces (v2.19.0):**

1. **Slack** — always.
2. **Google Chat** — when `.agents/gchat-sync.yaml` exists; per target, from the declared set `gchat_preflight.py` writes this run (v2.34.0).
3. **Email** — when the workspace routinely syncs it (evidenced by an established `transcripts/email/` directory or an explicit config). Use the workspace's designated email tooling and account; sweep inbound AND the user's own sent mail for the window.
4. **Meeting transcripts** — when `.agents/meeting-transcripts.yaml` exists: any meeting that ended during the window gets its transcript fetched (or re-checked, for ones whose notes had not yet generated).
5. **Document comments** — when the workspace has an established docs-sweep practice (evidenced by `transcripts/docs/` or an explicit config): Drive documents modified in the window, and open comment threads addressed to the user.

**The complete-surface rule:** the surfaces a workspace syncs are a declared set, exactly like the repo list in the source-code sync (v2.12.1's no-agent-judgment rule applies here too). A sync that runs fewer surfaces than the workspace's declared/established set MUST name the omission explicitly in its report — "email and docs not swept this run" — never report as if the sync were complete. Origin incident (2026-08-09): a mid-day sync ran Slack and Chat only, while the day's most consequential correspondence — a CEO-facing email delivering two Google Docs — had happened entirely on the omitted surfaces; the gap was invisible because the sync reported quiet channels without naming what it had not checked.

**Run `/synthesis-slack-sync`.** The `synthesis-slack-sync` skill handles the Slack portion's complete protocol: read channels, re-read all threads with replies, check DMs, save to local transcripts, and update the action plan. See that skill for the detailed five-step protocol.

The key discipline encoded in that skill: **every sync must re-read ALL threads with replies from today**, not just fetch new channel-level messages. Thread replies don't appear as channel messages — skipping thread re-reads causes stale action plans and duplicate message sends.

**Every sync re-reads every declared target (v2.30.0).** A DM or channel read at day-start is not current at mid-day: "already read today" is a statement about the past, not about now, and a twelve-minute-old reply is the normal case for a DM. Open each sync with `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py begin --workspace <W> --label mid-day`, take each target's `oldest` from `sync_watermark.py window --target <resolved id>`, record each saved read with `sync_watermark.py advance --target <resolved id>`, and close with `sync_watermark.py status --workspace <W> --surface <s> --since run --targets-from <declared.json>` (the declared set written this run by the Slack skill's `preflight.py --json --out`, never a stored copy) — its BLOCKING list is exactly the set this sync skipped, and the sync is not complete while it is non-empty. The user's own outbound is first-class sweep state: list every owed item their messages discharged since the window opened, and never call anything "unanswered" or "unsent" on a read older than this run. Origin (2026-09-01): two mid-day syncs covered group DMs and channels only; a DM answered at 09:27 was reported unanswered at 17:51 on the strength of a 09:15 read.

**Record after every sync.** Any sync that creates or updates transcripts, daily plans, or context files must leave session-attributed local state. Day-start and mid-day sync do not push merely to make same-machine client switching work; day-end and explicit remote handoff publish the batch.

---

## Vacation / Observer Mode Ritual

Use this variant when the user signals they are not actively working ("I'm on vacation", "observer mode", "just keeping up", "don't want to send messages"). Common phrasings: "do the modified ritual", "do what you did the last few days", "stay in observer mode".

Observer mode is a specific sync and context pattern. Its changes become LOCAL_READY immediately and REMOTE_READY at day-end or explicit remote handoff.

### Steps

1. **Verify the date** — run `date` to confirm today and translate any day-of-week references correctly.
2. **Check Downloads** for standup transcripts, meeting notes, shared Google Docs, or forwarded emails. Move each to `~/workspaces/{workspace}/ai-knowledge-{workspace}-rajiv-private/transcripts/meetings/` with appropriate naming. Delete originals from Downloads.
3. **Full Slack sync** — run `/synthesis-slack-sync`. Read every channel, DM, group DM. Follow threads with replies. Save to transcripts.
4. **Create today's daily plan** in observer mode:
   - Header says "Mode: VACATION CATCH-UP (awareness only — team is operating independently)" or equivalent
   - NO draft messages to send
   - NO "things to do today" for the user
   - DO include: "Things to Know for Return" section with 5-10 items
   - DO include: any decisions, incidents, product signals, or concerns that would be hard to catch up on later
5. **Update CONTEXT.md** and session archive with the day's events. Follow the context lifecycle skill's archival protocol if needed.
6. **Record local handoff state** for files touched in this invocation. Publish them only in day-end or explicit remote-handoff mode.

### What Observer Mode Skips (Deliberately)

From the normal Day-Start:
- Step 6 "Morning Messages" — no messages posted on the user's behalf

From the normal Day-End:
- Step 3 "Communications" — no replies, no end-of-day status
- Step 5 "Career Amplification" — no thought leadership capture unless explicitly requested

### What Observer Mode Keeps (Non-Negotiable)

- Date verification
- Full Slack sync (no channels or DMs skipped, no threads skipped)
- Transcript capture
- Daily plan creation (in observer format)
- CONTEXT.md + session archive updates
- **Attributed local persistence** — observer mode records every changed file; its batch reaches the remote at day-end or explicit remote handoff.

---

## Concurrent-Seats Mode Ritual (v2.41.0)

Use this variant whenever the board shows other live seats — autonomous or interactive — working while the ritual runs. The failure it prevents is real and repeated: parity checks fail while a release is in flight, and the ritual "repairs" the drift by refreshing clients into the live release; code sync fast-forwards branches a peer is landing; shared-state maintenance collides with seats that read the same state. The mode's rule of thumb: **the ritual observes and reports around live seats; it never mutates state a live seat owns.** Origin: operations-seat findings 10–11, adopted as ITEM23.

### The six mechanical rules

1. **Claim file-by-file.** The ritual seat claims exactly the files it will write — daily plan, CONTEXT.md, session log, state file — never whole directories. Directory claims block peer landings; named files do not.
2. **Fetch-all, fast-forward-only-unheld.** `git fetch --all` everywhere (fetching is read-only and safe), but `git pull --ff-only` only on branches no live seat holds. A held branch that moved is a `decision` with the holder named.
3. **Report parity, never repair it.** A PENDING parity check names its holder; the briefing carries the line verbatim and the ritual moves on. No marketplace refresh, no plugin reinstall, no stable-pointer touch while the holder is live.
4. **Skip shared-state maintenance while seats are live.** Index rebuilds, inventory regeneration, watermark advances, decay sweeps — anything every seat reads — waits for a clear board. The ritual reports `deferred: seats live` rather than half-running them.
5. **Fold, don't run, others' artifacts.** A day-end artifact or handoff filed by another seat is folded into the briefing as-is. The ritual never executes, regenerates, or "verifies by re-running" a peer's artifact — re-running someone else's step under their claim is a collision wearing diligence as a costume.
6. **Release claims at end.** Every claim the ritual took is released (or narrowed to nothing retained) before the run closes, so the next seat starts from a clean board.

### What Concurrent-Seats Mode Keeps (Non-Negotiable)

- Board + inbox read at start, and the ritual's own seat registered with its file claims
- Full sync reads (fetch, channel reads, transcript capture) — reads never need a window
- Daily plan creation with the `decision`/`deferred` lines the rules above produce
- CONTEXT.md + session archive updates for the ritual's own files
- `ritual_state.py record` with `--mode concurrent-seats`

---

## Day-End Checklist

**Distributed mode (v2.23.0):** each worker runs its workspace's close steps and files a `day-end` artifact; the desk folds artifacts, runs the guardian review and the publication boundary, and writes the one close-out with its coverage line.

### Day-End Modes (v2.14.0) — ask first, every time

Before Step 1, ask the user the one-letter mode question — **f** (full) / **q** (Quick Close) / **o** (observer) — every time, even when a mode seems obvious. If a launcher or opening prompt already named the mode, confirm it in one line instead of re-asking. Record the chosen mode in the state file (Step 7).

| Mode | Human moments | Steps run | Steps skipped |
|------|---------------|-----------|---------------|
| **Full** | as written | 1-11 | — |
| **Quick Close** (~10 min; the recommended default for ordinary evenings) | exactly three | 1, 4, 5, 7, 10 (only if owed), 11 | 2, 3, 6, 8, 9 |
| **Observer** | none | per the Vacation / Observer Mode section | comms + career steps |

**Quick Close's three human moments:** (1) the **send-or-release pass** over all due or overdue decay-tagged items (Step 4) — the step that protects overnight communication timing; (2) **keep/drop** on the day's `## 🌱 Lesson candidates` (Step 5); (3) the **closure read-back** — the agent ends with one on-screen paragraph: "Day closed. N sent, M released, lessons kept: X. Tomorrow opens with Y." Any audio accompanying it stays generic per the alert-confidentiality rules below. Everything else in Quick Close runs agentlessly around those three moments.

The Weekly Loose-Ends Review (Step 10) attaches to whichever ritual runs first on/after Friday, in any mode — a Friday Quick Close carries it. Every mode, observer included, records the ritual in Step 7 (`ritual_state.py record`).

### 1. Transcript Sync

- [ ] **Run `/synthesis-slack-sync`** for final capture of the day. The `synthesis-slack-sync` skill ensures all channels, threads, and DMs are captured.
- [ ] **Google Chat final capture (v2.17.0)** — if the workspace declares `.agents/gchat-sync.yaml`, run the same Chat sweep as Day-Start Step 3b for the day's window (fresh space enumeration through `gchat_preflight.py`, per-target reads and advances, raw sender IDs preserved).
- [ ] **Email + document-comment final capture (v2.19.0)** — when the workspace syncs those surfaces (per Day-Start 3b's declared-set rule): the day's inbound and sent mail, meeting transcripts for any meeting that ended since the last sync, and document comments/engagement for the day's window. Name any surface not swept.
- [ ] **Watermark gate (v2.30.0):** the final capture opened with `sync_watermark.py begin --workspace <W> --label day-end` and recorded each saved read with `advance`; now run `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py status --workspace <W> --surface <s> --since run` with every declared surface and read target passed explicitly (same rule and same reason as Day-Start Step 3b's gate). The day does not close over a surface or target this run did not re-read: read it or defer it with a reason now.
- [ ] Update CONTEXT.md to mark any items resolved by day's conversations (so tomorrow's day-start does not re-propose them).

### 2. Source-Code Sync

End-of-day code sync ensures local main/develop reflects everything that landed during the day and that tomorrow's day-start begins from a clean, current state. Run the same source-code sync as Day-Start Step 3a — same workspace repo list, same fetch + fast-forward semantics, same surfacing of divergence.

- [ ] Read the pending repo-guard manifests first. For every recorded source path owned by this ritual session, run its required tests, inspect the staged index, commit only attributed paths, and push under the repository's branch, review, and deployment policy. Do not mutate another active claim. Any path that cannot be published keeps the affected project below `REMOTE_READY`.

- [ ] For every repo the workspace manifest marks for sync (`<workspace>/.agents/repos.yaml` `ritual_sync: yes`; fallback: the `AGENTS.md` table's Yes rows — the complete set, no activity judgment; v2.12.1/v2.13.0): `git fetch --all`, then `git pull --ff-only` on each long-running branch (typically `main` and `develop`).
- [ ] Surface any branches that are diverged or have local-only commits not yet pushed. These are decisions to make NOW, not at next day-start, so the agent can act on them while context is fresh.
- [ ] Note the day's net change per repo (e.g., "develop +11 commits, includes ticket-id-here"). This summary becomes part of the day-end log and feeds tomorrow's day-start briefing.

This step is intentionally not "merge ready PRs" — that's Integration Sweep below. This step is pure sync: pull latest state, surface divergence, do not modify history.

### 3. Integration Sweep

- [ ] Check PR queue — merge any ready PRs, push to staging.
- [ ] Close GitHub PRs with integration comments (if using adopt-and-adapt pattern).
- [ ] If a new version was deployed to staging or production, follow your team's release notification process. Best practice: list all PRs included, credit all contributors by name and PR number, post to both product and engineering channels.

### 4. Communications — the send-or-release pass (v2.14.0)

#### 4a. Calendar Guardian — tomorrow's review (v2.20.0)

Runs first inside Step 4, in **every mode including Quick Close** — the next-day review is the highest-value evening act the ritual performs, and it generates drafts the send-or-release pass below then handles. The review protocol itself lives in the chief-of-staff skill's **Calendar guardian** section; this step is its evening cadence.

- [ ] Review the **next working day** across every configured calendar — and on the last working day of the week, the **weekend too**. Run the full per-entry checklist (real? answered? prepared? outcome? shape? physically possible?) and the whole-day overcommitment check against config thresholds.
- [ ] **Place holds over tomorrow's remaining open windows** per the same-day shield: generically titled, busy, id-tracked in the holds ledger, auto-expiring. Release/move only holds the ledger says the agent created.
- [ ] Conflicts and overcommitment produce **named candidates to move with drafted reschedule notes** — into the plan's drafts region, where this step's parent pass picks them up. A warning without candidates is not done.
- [ ] Anything only the principal can decide → one line each in the plan's decisions region. Tomorrow's calendar picture → the plan's calendar section.
- [ ] **Lead-time prep packs (v2.26.0):** when `.agents/meeting-preps.yaml` exists, generate or refresh the prep pack for every flagged meeting whose lead window includes tomorrow — built from the declared `sources` (prior transcript, mandate sources, project contexts), per the v2.26.0 rules and the `.agents/meeting-preps.yaml` schema in [references/version-history.md](references/version-history.md); the pack states its own basis (which declared sources were read, and the newest source's date). This runs in every mode including Quick Close, because it rides the tomorrow-review that already does.

- [ ] Run `synthesis exec-public synthesis-daily-rituals/scripts/decay_sweep.py --as-of <verified-current-date> --plans-dir <declared-daily-plans-directory> --json`, repeating declared roots and adding this workspace's `--artifacts-dir` when applicable. Collect every unresolved `**Decays:**` date on or before today across the complete declared plan/archive scope, with **no lookback cutoff**, plus unanswered threads from today. Source boundaries, carry-forward identity and outcome rules: [references/decay-sweep.md](references/decay-sweep.md).
- [ ] Read the returned source items and reconcile their current outcomes. `BLOCKED` or any unscanned source is an explicit coverage gap, never an empty pass; due items remain visible alongside gaps. Continue reviewing recovered candidates and running the remaining ritual steps, while recording the incomplete sweep; the gap blocks a clean sweep/closure conclusion, not all ritual work. `REVIEW` requires the decisions below. Only a complete, reconciled scan can support a clean closure; the helper's exit 0 grants no send authority. Workers report their own coverage in existing artifacts; the desk reports missing worker coverage without reading across workspace boundaries.
- [ ] For each item, one of three outcomes — nothing decay-tagged carries silently past its date: **send now** (with the user's one-tap approval; nothing sends without them), **re-date** with a stated reason on the Decays line, or **release** (strike through with a one-line why).
- [ ] Post end-of-day status updates; send appreciation for the day's contributions (grounded per the appreciation rule in the Draft Message Rules above).
- [ ] In Quick Close this pass is human moment #1: it caps at the tagged set plus a one-line "anything else you want to send tonight?" check.

### 5. Lessons Learned

- [ ] **Curate the day's `## 🌱 Lesson candidates` (v2.14.0):** present the accumulated one-liners from today's plan; the user answers keep/drop per line. Keepers get promoted to `lessons/` or folded into the owning project's docs; drops get struck through in place. In Quick Close this is human moment #2.
- [ ] Document any additional reusable lessons in `lessons/` (patterns, mistakes, solutions that apply beyond this session).
- [ ] Update project REFERENCE.md with any new stable facts discovered today.

### 5a. Native memory capture-buffer sweep

- [ ] Follow the complete [native memory capture-buffer sweep](references/ritual-worker-contract.md#native-memory-capture-buffer-sweep): keep memory ON, skip active harnesses as pending, archive before ingestion and require separate native clear qualification.

### 6. Career Amplification

- [ ] Review today's work for content opportunities: blog posts, articles, videos, talks.
- [ ] Note ideas in a running list (see thought-leadership writing skill for the full workflow when ready to write).
- [ ] Themes to watch for: novel patterns, hard-won solutions, process innovations, team dynamics insights, industry observations.

### 7. Context Capture

**Date discipline (matches Day-Start Step 1 and the global agent rules).** All session-log entries and CONTEXT.md updates written tonight MUST use today's verified date—not a date inferred from session continuity or memory. If the conversation has been running for multiple days, the agent's sense of "today" may be wrong by hours or days. Re-anchor before writing.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` once at the start of this step. Use the output as today's authoritative date for every file write that follows. (If `synthesis-checkpoint` is loaded, invoke it instead — it does this anchoring plus a git-log cross-check.)
- [ ] For each project worked on today: append a session-log entry to `sessions/YYYY-MM.md` with today's verified date in the header. Format the date as ISO `YYYY-MM-DD` (e.g., `## 2026-05-27 (Wed) — Day-end summary`).
- [ ] Update CONTEXT.md. Refresh the "Last session" field with today's verified date and update "Recent Sessions" with a one-line summary. **Every live entry in an open-items section carries its own age:** stamp it `(as of YYYY-MM-DD, review Nd)` when you write it, and re-stamp it only when you have actually re-checked it — a stamp advanced without a check is a false receipt, which is worse than an obviously old one. Entries that are genuinely done are closed out into `sessions/YYYY-MM.md` — write them there, verify they landed, then remove them from CONTEXT.md. `context_doctor.py` reports a stamped entry as `item-currency` once it passes its review horizon (14 days when `review Nd` is omitted); match the horizon to the item — owed work at the default, backlogs and wishlists at `(as of YYYY-MM-DD, review 180d)` — and park a settled decision under a decisions heading, since the section heading is what the checker reads as owed.

- [ ] Update MEMORY.md if current state info is stale (version numbers, environment status, team assignments).
- [ ] Update `last_session` date in `index.yaml` for each active project worked on today — use today's verified date.
- [ ] **Local context gate:** run context_doctor.py --project <active-project-path> --readiness local for every project worked today. Structural defects block; expected local-only Git state remains visible.
- [ ] **Record the ritual (v2.28.0):** `synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py record --direction day-end --workspace <ws> --date <logical workday> --mode <mode> --outcome <outcome> [--count k=v] --session <actual session identity> [--pointer <session log>]`. **`--date` is the workday being closed, never inferred from the clock** — closes are routinely written the next morning, and one person's workspace workdays open and close at different times. Records are structured data capped at 2048B so the append stays atomic under concurrent seats; the narrative belongs in the session log the `--pointer` names. Every mode records, observer included; day-start uses `--direction day-start`.

### 8. Skills Maintenance

- [ ] If any installed skill copies changed, check whether those edits need to be synced back to the source repo. Use `synthesis-skills-manager` or check `.source.json` provenance files.
- [ ] If skills were updated in source repos, verify they were installed to the Claude Code, Codex, and cross-agent locations that use them.

### 9. Machine Sync

- [ ] Run mac-sync (credentials, config, git remotes across machines).

### 10. Weekly Loose-Ends Review (owed weekly — v2.14.0)

**Owed-weekly gating (replaces the v2.8.0 Friday-only rule).** The review is owed once per week per workspace, anchored to Friday, and tracked as `weekly-review` records in the append-only ritual log. Run `synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py query weekly-review --workspace <ws>`: if the date it returns is on/after the most recent Friday, skip this step silently. If it predates the most recent Friday, or there is none, and today is on/after that Friday, run the scan below — in whichever ritual notices first (Day-Start Step 1 checks the same condition), in any day-end mode including Quick Close — then `ritual_state.py record --direction weekly-review --workspace <ws> --date <today>`. A `synthesis-catchup-ledger` sweep on/after that Friday counts as the week's review (record its date); and if this scan finds 2+ consecutive missed rituals, suggest running that skill — it is the recovery tool for broken cadence. This decoupling exists because a Friday-evening-only review is disabled by exactly the skip it is meant to catch.

**Scope: past 14 calendar days.** Look back from today through 14 days ago. This captures the current week + the previous week — enough to surface items deferred across one weekend boundary, which is the typical failure mode.

**Sources to scan (read each one; do not infer):**

- [ ] **Calendar Guardian — week and month horizons (v2.20.0).** Part of the owed-weekly review, so a skipped Friday still gets caught by the same gating:
  - **Week ahead:** sweep all configured calendars for collisions, overcommitted days (config thresholds), unanswered RSVPs, and prep-less meetings — while there is still time to move things. Flag every lead-time meeting (`.agents/meeting-preps.yaml`) in the coming week so research that needs more than a day starts early (v2.26.0). Candidates-to-move come with drafted notes, same contract as the nightly review.
  - **Month ahead:** scan for anything needing lead time — travel, conferences, deadlines, visits. Any commitment that should start an absence-coordination notification clock (its `notify_on_commit` cohort, or a lead-time deadline inside the coming month) gets flagged NOW; this scan is what makes "people hear as soon as it is known" true in practice rather than in intention.
- [ ] **The pull-request queue for this workspace's own repos (v2.35.0).** Run `synthesis exec-public synthesis-daily-rituals/scripts/pr_queue_scan.py --workspace <W>`. It reads the workspace's `.agents/repos.yaml` — the same declaration the source-code sync uses — and reports, oldest first: review requests naming the principal, their own open PRs, and PRs in the declared repos that nobody else was asked to review (where dependency bots land). **Scope follows the manifest, so each workspace's review sees only its own repos** and no second list has to be maintained. The scan is deliberately NOT filtered by `ritual_sync`: that flag governs whether a working copy is fast-forwarded, which is a different question from whether a repo has a request waiting on a human — skill sources and context repos carry `ritual_sync: no` and still have PRs. It exits 0 always and names every repo it could not read, because **an unscanned queue must never read as an empty one**. Since v2.36.0 the scan dispatches by origin host: `bitbucket.org` repositories are scanned through the `pr_queue` helper the synthesis-bitbucket skill ships, and any other non-GitHub host stays NOT SCANNED with the host named as the reason. Origin: on 2026-08-28 the review reported one waiting-on item past seven days while a review request naming the principal sat 139 days old, unseen — the review had not missed it, it had not looked. The gap was written down that day and stayed open until 2026-09-05 because the day that found it never closed.
- [ ] `daily-plans/YYYY-MM-DD.md` for the past 14 calendar days. In each plan, look for:
  - Drafts (`### Draft N: ...`) without a following `**Sent:**` marker — these are unsent and the deadline already passed
  - Items under `## Priority Tasks → Do today — not negotiable` that lack a completion marker (✅ or "DONE" or strikethrough)
  - Existing `## Carryover open items` / `## Stale targets` sections — these are last week's loose ends that may or may not still be relevant
  - Anything under `## Decisions needed from Rajiv` that did not get a decision recorded
- [ ] Each active project's `CONTEXT.md` "Open Items" / "Decisions Needed" / "Open Questions" sections — flag items whose surrounding text has not changed in 14+ days
- [ ] Each active project's `## Waiting On Others` table — flag rows whose "Last asked" / "Asked at" timestamp is >7 days ago (one full work-week without a follow-up signals the ask got buried or forgotten)
- [ ] `sessions/YYYY-MM.md` for the current AND previous calendar month — scan for explicit personal commitments (Rajiv saying "I'll do X tomorrow" or "I'll send Y by EOD") and verify each has a matching completion record. Pattern-match on first-person future-tense verbs in Rajiv's own text, not in quoted teammate messages.

**Classify each surfaced item:**

- **STILL RELEVANT** → carry into Monday by appending to Friday's daily plan `## Carried Items` section in the canonical format the cockpit reads. Include: the item description, the original date it surfaced, the original source (which plan / which CONTEXT.md / which Slack thread). This is what Monday's day-start picks up.
- **OBSOLETE** → annotate IN PLACE on the original source file with a one-line reason (e.g., "obviated by Y on YYYY-MM-DD", "stakeholder OOO through Z", "decision moot post-X"). These items stop appearing in future weekly reviews because they're now marked. Do NOT delete — the annotation is the record that the item was triaged.
- **AMBIGUOUS** → surface to the user with a brief context block. They decide carry-forward vs close. Do not guess; for items that touch other people's commitments or strategic direction, the user must be the one to call it.

**Output requirements:**

- [ ] Add a `## Weekly Loose-Ends Review` section to today's (Friday's) daily plan. Structure: scan summary at top (count of items by classification + per-source breakdown), then the explicit STILL RELEVANT list (these are what Monday picks up), then OBSOLETE-with-reason list (audit trail), then AMBIGUOUS list (decision queue for the user).
- [ ] If items in STILL RELEVANT need to be tracked across the weekend, populate today's daily plan `## Carried Items` section. (Monday's plan, when created, will pull from there as part of normal day-start.)
- [ ] Annotate OBSOLETE items in their ORIGINAL source files (not in this review section) so they get marked once and stay marked.
- [ ] Leave every changed plan and annotation session-attributed; Step 11 publishes the final day-end batch.

**Failure mode to avoid:** writing a `## Weekly Loose-Ends Review` section header without actually scanning the sources. The value is in the scan. If sources have not been read in this invocation, do not write the section — note "Weekly Loose-Ends Review skipped — scan not performed this invocation" in the plan and surface the gap to the user.

### 11. Remote Readiness and Final Verification

**This step is mandatory and is the final mutating day-end step.**

- [ ] Re-read the lease-backed coordination board. Do not mutate paths held by another active session; report them as active local work rather than defects in this ritual.
- [ ] Publish every pending source path owned by this ritual under its repository policy. Inspect status and the staged index before each exact-path commit; run required tests and normal hooks.
- [ ] Run `checkpoint_sync.py --flush-pending`. Any retained relevant manifest blocks day-end remote readiness.
- [ ] For every project worked today, run `context_doctor.py --project <path> --readiness remote` and `conformance.py continuity --project <path> --readiness remote`. Require PASS.
- [ ] Run `repo_sync_check.py` across the full workspace. Every path owned by this ritual must be clean and upstream-current. Dirty state protected by another active coordination claim is reported and left untouched.
- [ ] Verify intended remote heads independently. Record `REMOTE_READY` in day-end state only when the project gates pass; otherwise record `blocked` with the local recovery state intact.

This gate distinguishes incomplete publication from legitimate parallel work. It never sweeps another session, discards local changes, bypasses hooks, or turns a local-only pass into a cross-machine claim.

---

## Ritual Persistence Protocol

Day-start, mid-day sync, and observer mode leave their writes session-attributed and locally recoverable. They do not commit or push merely to preserve same-machine continuity. Day-end and explicit remote-handoff mode publish the batch.

### Local mode

Track every file this invocation changes. Update project tiers before a natural pause and release or narrow coordination claims. PostToolUse manifests and Stop receipts provide automatic local continuity; an interrupted run remains recoverable from its manifest plus Git status and diff.

### Remote mode

Publish source paths first under each repository branch, review, test, and deployment policy. Then flush exact private-context paths through synthesis-repo-guard. Before each source commit, inspect the full staged index and include only attributed paths. Never use broad staging, never touch another active claim, and never bypass hooks.

Commit messages follow the global hygiene rule: generic in public and private repositories, with no sensitive names, titles, rationale, or prior values. Git history is not a session transcript.

Remote publication is complete only when remote-mode context doctor and continuity conformance pass, intended remote heads are verified, and no relevant pending manifest remains.

---

## Autonomous Work and Audio Alerts

When the user signals stepping away ("going to take a shower", "heading out", "don't wait on me", "continue without me"):

1. **Activate autonomous mode** — complete all planned work without prompting for confirmations.
2. **On completion of any significant task**, play the audio alert. **Alert-confidentiality rule (v2.14.0, matching the synthesis-repo-guard v2 alert model):** spoken text and notification banners carry ZERO identifying content — no client, repo, workspace, project, or person names. Others hear speakers on calls and see banners on screen-shares. Generic wording only, and honor the mute flag:
   ```bash
   [ -f ~/.synthesis/quiet-audio ] || { afplay /System/Library/Sounds/Glass.aiff && \
   afplay /System/Library/Sounds/Glass.aiff && \
   afplay /System/Library/Sounds/Glass.aiff && \
   say "The current task is complete. Details are on your screen."; }
   ```
   `~/.synthesis/quiet-audio` (console-managed) silences all audio; on-screen detail is unaffected.
3. **If a blocker requires input**, play the alert FIRST (same generic wording — never speak the blocker's subject), then display the question on screen.
4. **This is not limited to deployments** — any significant milestone (PR review posted, integration complete, deployment done, tests passing after a fix) should alert if the user is away, always with the generic wording.

**Prerequisite:** the current tool must be authorized to run the local alert commands (`afplay` and `say` on macOS). If not, warn at the start of autonomous mode.

# Day-End Checklist

Read at day-end. `<rituals>` is this skill's folder; `<W>` is the workspace name.
**Distributed mode (v2.23.0):** each worker runs its workspace's close steps and files a
`day-end` artifact; the desk folds artifacts, runs the guardian review and the publication
boundary, and writes the one close-out with its coverage line
([ritual-worker-contract.md](ritual-worker-contract.md)).

Contents: Day-end modes · 1 Transcript sync · 2 Source-code sync · 3 Integration sweep · 4
Communications: the send-or-release pass (4a Calendar Guardian, 4b deadlines and lapses) · 5
Lessons learned · 5a Native-memory sweep · 5b Provenance scan · 6 Career amplification · 7
Context capture · 8 Skills maintenance · 9 Machine sync · 10 Weekly loose-ends review · 11
Remote readiness and final verification · Publishing at day-end.

## Day-End Modes (v2.14.0) — ask first, every time

Before Step 1, ask the user the one-letter mode question — **f** (full) / **q** (Quick Close) / **o** (observer) — every time, even when a mode seems obvious. If a launcher or opening prompt already named the mode, confirm it in one line instead of re-asking. Record the chosen mode in Step 7.

| Mode | Human moments | Steps run | Steps skipped |
|------|---------------|-----------|---------------|
| **Full** | as written | 1-11 | — |
| **Quick Close** (~10 min; the recommended default for ordinary evenings) | exactly three | 1, 4, 5, 7, 10 (only if owed), 11 | 2, 3, 6, 8, 9 |
| **Observer** | none | per the [Vacation / Observer Mode](mid-day-and-modes.md#vacation--observer-mode-ritual) section | comms + career steps |

**Quick Close's three human moments:** (1) the **send-or-release pass** over all due or overdue decay-tagged items (Step 4) — the step that protects overnight communication timing; (2) **keep/drop** on the day's `## 🌱 Lesson candidates` (Step 5); (3) the **closure read-back** — the agent ends with one on-screen paragraph: "Day closed. N sent, M released, lessons kept: X. Tomorrow opens with Y." Any audio accompanying it stays generic per the alert-confidentiality rules. Everything else in Quick Close runs agentlessly around those three moments. Steps 5a and 5b ride Quick Close too: they are reads and moves, with no human moment of their own.

The Weekly Loose-Ends Review (Step 10) attaches to whichever ritual runs first on/after Friday, in any mode — a Friday Quick Close carries it. Every mode, observer included, records the ritual in Step 7 (`ritual_state.py record`).

## 1. Transcript Sync

- [ ] Open the run: `python3 <rituals>/scripts/sync_watermark.py begin --workspace <W> --label day-end`.
- [ ] **Run `/synthesis-slack-sync`** for final capture of the day. The `synthesis-slack-sync` skill ensures all channels, threads, and DMs are captured.
- [ ] **Google Chat final capture (v2.17.0)** — if the workspace declares `.agents/gchat-sync.yaml`, run the same Chat sweep as Day-Start Step 3b for the day's window (fresh space enumeration through `gchat_preflight.py`, per-target reads and advances, raw sender IDs preserved).
- [ ] **Email + document-comment final capture (v2.19.0)** — when the workspace syncs those surfaces (per Day-Start 3b's declared-set rule): the day's inbound and sent mail, meeting transcripts for any meeting that ended since the last sync, and document comments/engagement for the day's window. Name any surface not swept.
- [ ] **Watermark gate (v2.30.0):** the final capture recorded each saved read with `advance`; now run `python3 <rituals>/scripts/sync_watermark.py status --workspace <W> --surface <s> --since run` with every declared surface and read target passed explicitly (same rule and same reason as Day-Start Step 3b's gate). The day does not close over a surface or target this run did not re-read: read it or defer it with a reason now.
- [ ] Update CONTEXT.md to mark any items resolved by day's conversations (so tomorrow's day-start does not re-propose them).

## 2. Source-Code Sync

End-of-day code sync ensures local main/develop reflects everything that landed during the day and that tomorrow's day-start begins from a clean, current state. Run the same source-code sync as Day-Start Step 3a — same workspace repo list, same fetch + fast-forward semantics, same surfacing of divergence.

- [ ] Publish this ritual session's own source work first: for each repo where this session holds a claim (`synthesis who` shows it), run its required tests, inspect `git -C <repo> diff --cached --name-only`, commit only the paths inside the claim, and push under the repository's branch, review, and deployment policy. Do not touch another active claim.
- [ ] `python3 <rituals>/scripts/repo_state.py --workspace-root ~/workspaces/<W> --fetch --ff` for every repo the workspace manifest marks for sync (`<workspace>/.agents/repos.yaml` `ritual_sync: yes`; fallback: the `AGENTS.md` table's Yes rows — the complete set, no activity judgment; v2.12.1/v2.13.0).
- [ ] Surface any branches that are diverged or have local-only commits not yet pushed. These are decisions to make NOW, not at next day-start, so the agent can act on them while context is fresh.
- [ ] Note the day's net change per repo (e.g., "develop +11 commits, includes ticket-id-here"). This summary becomes part of the day-end log and feeds tomorrow's day-start briefing.

This step is intentionally not "merge ready PRs" — that's Integration Sweep below. This step is pure sync: pull latest state, surface divergence, do not modify history.

## 3. Integration Sweep

- [ ] Check PR queue — merge any ready PRs, push to staging.
- [ ] Close GitHub PRs with integration comments (if using adopt-and-adapt pattern).
- [ ] If a new version was deployed to staging or production, follow your team's release notification process. Best practice: list all PRs included, credit all contributors by name and PR number, post to both product and engineering channels. Production deploys need the principal's explicit approval each time; the deploy guard holds the command until they type `approve <code>`.

## 4. Communications — the send-or-release pass (v2.14.0)

### 4a. Calendar Guardian — tomorrow's review (v2.20.0)

Runs first inside Step 4, in **every mode including Quick Close** — the next-day review is the highest-value evening act the ritual performs, and it generates drafts the send-or-release pass below then handles. The review protocol itself lives in the chief-of-staff skill's **Calendar guardian** section; this step is its evening cadence.

- [ ] Review the **next working day** across every configured calendar — and on the last working day of the week, the **weekend too**. Run the full per-entry checklist (real? answered? prepared? outcome? shape? physically possible?) and the whole-day overcommitment check against config thresholds.
- [ ] **Place holds over tomorrow's remaining open windows** per the same-day shield: generically titled, busy, id-tracked in the holds ledger, auto-expiring. Release/move only holds the ledger says the agent created.
- [ ] Conflicts and overcommitment produce **named candidates to move with drafted reschedule notes** — into the plan's drafts region, where this step's parent pass picks them up. A warning without candidates is not done.
- [ ] Anything only the principal can decide → one line each in the plan's decisions region. Tomorrow's calendar picture → the plan's calendar section.
- [ ] **Lead-time prep packs (v2.26.0):** when `.agents/meeting-preps.yaml` exists, generate or refresh the prep pack for every flagged meeting whose lead window includes tomorrow — built from the declared `sources` (prior transcript, mandate sources, project contexts), per the v2.26.0 rules and the `.agents/meeting-preps.yaml` schema in [version-history-2.3-to-2.26.md](version-history-2.3-to-2.26.md); the pack states its own basis (which declared sources were read, and the newest source's date). This runs in every mode including Quick Close, because it rides the tomorrow-review that already does.

### 4b. Deadlines, sends and lapses

- [ ] Run `python3 <rituals>/scripts/decay_sweep.py --as-of <verified-current-date> --plans-dir <declared-daily-plans-directory> --json`, repeating declared roots and adding this workspace's `--artifacts-dir` when applicable. Collect every unresolved `**Decays:**` date on or before today across the complete declared plan/archive scope, with **no lookback cutoff**, plus unanswered threads from today. Source boundaries, carry-forward identity and outcome rules: [decay-sweep.md](decay-sweep.md).
- [ ] Read the returned source items and reconcile their current outcomes. `BLOCKED` (exit 2) or any unscanned source is an explicit coverage gap, never an empty pass; due items remain visible alongside gaps. Continue reviewing recovered candidates and running the remaining ritual steps, while recording the incomplete sweep; the gap blocks a clean sweep/closure conclusion, not all ritual work. `REVIEW` requires the decisions below. Only a complete, reconciled scan can support a clean closure; the helper's exit 0 grants no send authority. Workers report their own coverage in existing artifacts; the desk reports missing worker coverage without reading across workspace boundaries.
- [ ] For each item, one of three outcomes — nothing decay-tagged carries silently past its date: **send now** (with the user's one-tap approval; nothing sends without them), **re-date** with a stated reason on the Decays line, or **release** (strike through with a one-line why).
- [ ] **Lapses are recorded, never relabeled.** When a decay-tagged item, a decision or an owed reply has passed its date with no decision from the principal, it **lapsed**; it was not released. Mark it where it sat with `**Lapsed:** YYYY-MM-DD — <what lapsed, and where it waited>`, and append one row to the workspace's lapse register (`| Lapsed | Item | Where it waited | Why it lapsed | Outcome |`; the workspace instructions name the file, which lives in that workspace's own records). Keep "released" for an explicit decision to let something go. An item that sat past its date until the principal let it go is marked `**Released:**` at its source as their decision, and also gets a register row with the outcome "let go after its date". **The register is permanent history: append rows, never remove or rewrite them.** The weekly and longer reviews read it ([weekly-and-longer.md](weekly-and-longer.md)).
- [ ] Post end-of-day status updates; send appreciation for the day's contributions (grounded per the appreciation rule in [draft-grounding.md](draft-grounding.md)).
- [ ] In Quick Close this pass is human moment #1: it caps at the tagged set plus a one-line "anything else you want to send tonight?" check.

## 5. Lessons Learned

- [ ] **Curate the day's `## 🌱 Lesson candidates` (v2.14.0):** present the accumulated one-liners from today's plan; the user answers keep/drop per line. Keepers get promoted to `lessons/` or folded into the owning project's docs; drops get struck through in place. In Quick Close this is human moment #2.
- [ ] Document any additional reusable lessons in `lessons/` (patterns, mistakes, solutions that apply beyond this session).
- [ ] Update project REFERENCE.md with any new stable facts discovered today.

## 5a. Native-Memory Sweep

Native memory stays ON in every harness as a capture buffer; synthesis records are authoritative and win any conflict. This step moves what the harnesses remembered today into the records. Listing the stores is one command, so there is no script.

- [ ] **List what changed since the last close** (the session-start ritual line names the last day-end date):
  `find ~/.claude/projects/*/memory ~/.codex/memories -type f -newermt "<last day-end date>" 2>/dev/null`
  Claude Code keeps one store per project folder (`MEMORY.md` plus topic files); Codex keeps `~/.codex/memories/` (`MEMORY.md`, `memory_summary.md`, `raw_memories.md`, rollout summaries). Muse has no memory store to sweep; do not invent one. A store that is missing, moved or unreadable is reported as a gap, never as "nothing new".
- [ ] **Read each changed entry and decide whether it is durable.** Route durable ones by kind: reusable lessons to the personal lessons folder, project facts to the owning project's REFERENCE.md, voice and drafting patterns to the owning private skill, workspace-private content to that workspace's records (its deletion unit). Contracts, pay and equity, hiring and negotiation, termination, reviews about the principal, IP assignments and dispute evidence always go to the personal records, even from a workspace store. Unknown ownership stays a decision for the principal.
- [ ] **Archive first.** Before writing any derived entry, copy the raw memory text as it is into the destination project's `resources/memory-archive/<harness>/<date>.md`, then write the canonical entry, then check both landed. Exact text already in the records is not written twice. An entry that contradicts a canonical record never overwrites it; it becomes a decision. A candidate for public writing is a publication decision, never an automatic edit.
- [ ] **Never delete, edit or empty a raw memory file, and never turn native memory off** to make the sweep tidier. A harness session that is live now may still be writing its store: read it again at the end of the ritual, and leave anything written after that for tomorrow.
- [ ] Report counts only in any alert: "memory sweep: 2 stores changed, 3 entries recorded, 1 decision".

## 5b. Provenance Scan

A quote or timestamp written into a record must come from something a tool actually read. An agent once fabricated a chat message by tweaking a real message's timestamp.

- [ ] Run `python3 <synthesis-agent-guardrails>/scripts/provenance_scan.py --since <today> <today's transcripts, daily plan, and the CONTEXT.md and session logs written today>`. Each Slack timestamp written today must match a synced read; the scan names every one that does not. Fix or remove each named line before the close (correct it from the source, or mark it unverified); never "fix" it by inventing a source.

## 6. Career Amplification

- [ ] Review today's work for content opportunities: blog posts, articles, videos, talks.
- [ ] Note ideas in a running list (see thought-leadership writing skill for the full workflow when ready to write).
- [ ] Themes to watch for: novel patterns, hard-won solutions, process innovations, team dynamics insights, industry observations.

## 7. Context Capture

**Date discipline (matches Day-Start Step 1 and the global agent rules).** All session-log entries and CONTEXT.md updates written tonight MUST use today's verified date—not a date inferred from session continuity or memory. If the conversation has been running for multiple days, the agent's sense of "today" may be wrong by hours or days. Re-anchor before writing.

- [ ] Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` once at the start of this step. Use the output as today's authoritative date for every file write that follows. (If `synthesis-checkpoint` is loaded, invoke it instead — it does this anchoring plus a git-log cross-check.)
- [ ] For each project worked on today: append a session-log entry to `sessions/YYYY-MM.md` with today's verified date in the header. Format the date as ISO `YYYY-MM-DD` (e.g., `## 2026-05-27 (Wed) — Day-end summary`).
- [ ] Update CONTEXT.md. Refresh the "Last session" field with today's verified date and update "Recent Sessions" with a one-line summary. **Every live entry in an open-items section carries its own age:** stamp it `(as of YYYY-MM-DD, review Nd)` when you write it, and re-stamp it only when you have actually re-checked it — a stamp advanced without a check is a false receipt, which is worse than an obviously old one. Entries that are genuinely done are closed out into `sessions/YYYY-MM.md` — write them there, verify they landed, then remove them from CONTEXT.md. `context_doctor.py` reports a stamped entry as `item-currency` once it passes its review horizon (14 days when `review Nd` is omitted); match the horizon to the item — owed work at the default, backlogs and wishlists at `(as of YYYY-MM-DD, review 180d)` — and park a settled decision under a decisions heading, since the section heading is what the checker reads as owed.
- [ ] Update MEMORY.md if current state info is stale (version numbers, environment status, team assignments).
- [ ] Update `last_session` date in `index.yaml` for each active project worked on today — use today's verified date. Where the index is generated from each project's own status, update the project's own status line instead.
- [ ] **Local context gate:** run `python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --project <path>` for every project worked today. Exit 1 names the file and the defect; fix structural defects before the close. Exit 2 (cannot tell) is never a pass.
- [ ] **Record the ritual (v2.28.0):** `python3 <rituals>/scripts/ritual_state.py record --direction day-end --workspace <W> --date <logical workday> --mode <mode> --outcome <outcome> [--count k=v] --session <this session's id> [--pointer <session log>]`. **`--date` is the workday being closed, never inferred from the clock** — closes are routinely written the next morning, and one person's workspace workdays open and close at different times. Records are structured data capped at 2048B so the append stays atomic under concurrent seats; the narrative belongs in the session log the `--pointer` names. Every mode records, observer included; day-start uses `--direction day-start`. Outcomes: clean, complete, completed, success, partial, failed, skipped, blocked, degraded; an unread or failed surface makes the run partial, never clean.

## 8. Skills Maintenance

- [ ] If any installed skill copies changed, check whether those edits need to be synced back to the source repo. `synthesis doctor` reports installed files that differ from their source.
- [ ] If skills were updated in source repos, verify they were installed to the Claude Code, Codex, and Muse locations that use them.

## 9. Machine Sync

- [ ] If work moves to another Mac tonight, run the leave procedure in `synthesis-machine-sync` (handoff per project, then the strand scan). For config and repository sync across Macs, run `synthesis-mac-sync`.

## 10. Weekly Loose-Ends Review (owed weekly — v2.14.0)

- [ ] If `ritual_state.py query weekly-review --workspace <W>` says `owed: true`, run the review in [weekly-and-longer.md](weekly-and-longer.md), in any day-end mode including Quick Close, and record it.

## 11. Remote Readiness and Final Verification

**This step is mandatory and is the final mutating day-end step.**

- [ ] Re-read the board (`synthesis who`). Do not mutate paths held by another active session; report them as active local work rather than defects in this ritual.
- [ ] Publish every source path owned by this ritual under its repository policy (Step 2). Inspect status and the staged index before each exact-path commit; run required tests and normal hooks.
- [ ] For every project worked today, run `synthesis handoff -m "<generic message>"`. It commits and pushes only the records inside this session's claims, and refuses dirty or unpushed records rather than reporting ready. Read its report; a refusal names what to fix.
- [ ] Run the context records doctor with `--project <path>` for each of those projects. Require exit 0.
- [ ] Run the strand scan across the full workspace: `python3 <rituals>/scripts/repo_state.py --discover ~/workspaces/<W> --fetch`. Every path owned by this ritual must be clean and upstream-current. Dirty state protected by another active claim is reported and left untouched.
- [ ] Verify intended remote heads independently (`git -C <repo> status -sb` shows no `ahead`). The day-end outcome is `clean` only when these gates pass. If Step 7 already recorded `clean` and a gate here fails, append a corrected record (`ritual_state.py record --direction day-end ... --outcome blocked` or `partial`, same `--date`): the later record wins, and the log is never edited. Leave the local recovery state intact.

This gate distinguishes incomplete publication from legitimate parallel work. It never sweeps another session, discards local changes, bypasses hooks, or turns a local-only pass into a cross-machine claim.

## Publishing at day-end

Day-start, mid-day sync, and observer mode leave their writes on disk. They do not commit or push merely to preserve same-machine continuity: on one Mac the files are the handoff, and Claude Code, Codex and Muse all read them. Day-end and an explicit move to another Mac publish the batch.

Publish source paths first under each repository branch, review, test, and deployment policy. Then hand off the project records with `synthesis handoff`. Before each source commit, inspect the full staged index and include only paths inside this session's claims: another session may have staged its own work in the same index (`git add` adds to whatever is there), so commit with explicit paths. Never use broad staging, never touch another active claim, never bypass hooks, and never retry a refused commit with `--no-verify`. Leave a `.git/index.lock` you did not create where it is and report it. If the remote moved ahead, fetch and push only as a fast-forward; on divergence leave the local commit and report it; never rebase or force-push on its own. With the network down, keep the local commit and report it unpushed; a rerun pushes it. Judge a commit by `git log` and `git status`, not by the absence of an error line.

Commit messages follow the global hygiene rule: generic in public and private repositories, with no sensitive names, titles, rationale, or prior values. Git history is not a session transcript.

Remote publication is complete only when the context records doctor passes for each project, intended remote heads are verified, and no claimed record is left dirty or unpushed.

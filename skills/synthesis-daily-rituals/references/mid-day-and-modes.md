# Mid-Day Sync and the Ritual Modes

Read when the user asks for a sync during the day, says they are away or only keeping up,
other sessions are live while a ritual runs, or the user steps away mid-task. `<rituals>` is
this skill's folder.

Contents: Mid-Day Sync Protocol · Vacation / Observer Mode Ritual · Concurrent-Seats Mode
Ritual · Autonomous Work and Audio Alerts.

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

**Every sync re-reads every declared target (v2.30.0).** A DM or channel read at day-start is not current at mid-day: "already read today" is a statement about the past, not about now, and a twelve-minute-old reply is the normal case for a DM. Open each sync with `python3 <rituals>/scripts/sync_watermark.py begin --workspace <W> --label mid-day`, take each target's `oldest` from `sync_watermark.py window --target <resolved id>`, record each saved read with `sync_watermark.py advance --target <resolved id>`, and close with `sync_watermark.py status --workspace <W> --surface <s> --since run --targets-from <declared.json>` (the declared set written this run by the preflight scripts, never a stored copy) — its BLOCKING list is exactly the set this sync skipped, and the sync is not complete while it is non-empty. The user's own outbound is first-class sweep state: list every owed item their messages discharged since the window opened, and never call anything "unanswered" or "unsent" on a read older than this run. Origin (2026-09-01): two mid-day syncs covered group DMs and channels only; a DM answered at 09:27 was reported unanswered at 17:51 on the strength of a 09:15 read.

**Record after every sync.** Any sync that creates or updates transcripts, daily plans, or context files leaves them on disk under this session's claims. Day-start and mid-day sync do not push merely to make same-machine client switching work; day-end and an explicit move to another Mac publish the batch.

## Vacation / Observer Mode Ritual

Use this variant when the user signals they are not actively working ("I'm on vacation", "observer mode", "just keeping up", "don't want to send messages"). Common phrasings: "do the modified ritual", "do what you did the last few days", "stay in observer mode".

Observer mode is a specific sync and context pattern. Its changes are on disk at once, and reach the remote at day-end or an explicit move to another Mac.

### Steps

1. **Verify the date** — run `date` to confirm today and translate any day-of-week references correctly.
2. **Check Downloads** for standup transcripts, meeting notes, shared Google Docs, or forwarded emails. Move each to `~/workspaces/{workspace}/ai-knowledge-{workspace}-{person}-private/transcripts/meetings/` with appropriate naming. Delete originals from Downloads.
3. **Full Slack sync** — run `/synthesis-slack-sync`. Read every channel, DM, group DM. Follow threads with replies. Save to transcripts.
4. **Create today's daily plan** in observer mode:
   - Header says "Mode: VACATION CATCH-UP (awareness only — team is operating independently)" or equivalent
   - NO draft messages to send
   - NO "things to do today" for the user
   - DO include: "Things to Know for Return" section with 5-10 items
   - DO include: any decisions, incidents, product signals, or concerns that would be hard to catch up on later
5. **Update CONTEXT.md** and session archive with the day's events. Follow the context lifecycle skill's archival protocol if needed.
6. **Leave every file touched in this invocation on disk under this session's claims.** Publish them only at day-end or on an explicit move to another Mac.

### What Observer Mode Skips (Deliberately)

From the normal Day-Start:
- Step 7 "Morning Messages" — no messages posted on the user's behalf

From the normal Day-End:
- Step 4's sends "Communications" — no replies, no end-of-day status
- Step 6 "Career Amplification" — no thought leadership capture unless explicitly requested

### What Observer Mode Keeps (Non-Negotiable)

- Date verification
- Full Slack sync (no channels or DMs skipped, no threads skipped)
- Transcript capture
- Daily plan creation (in observer format)
- CONTEXT.md + session archive updates
- **Recorded state** — observer mode records the ritual (`ritual_state.py record --mode observer`) and leaves every changed file on disk; its batch reaches the remote at day-end or an explicit move to another Mac.

When observer mode is reinvented per conversation, the agent often drops durable state. The rule is now explicit: every observer run leaves its files and its ritual record, while day-end or a move to another Mac owns publication.

## Concurrent-Seats Mode Ritual

Use this variant whenever the board (`synthesis who`) shows other live seats — autonomous or interactive — working while the ritual runs. The failure it prevents is real and repeated: parity checks fail while a release is in flight, and the ritual "repairs" the drift by refreshing clients into the live release; code sync fast-forwards branches a peer is landing; shared-state maintenance collides with seats that read the same state. The mode's rule of thumb: **the ritual observes and reports around live seats; it never mutates state a live seat owns.** Origin: operations-seat findings 10–11, adopted as ITEM23.

### The six mechanical rules

1. **Claim file-by-file.** The ritual seat claims exactly the files it will write — daily plan, CONTEXT.md, session log, state file — never whole directories. Directory claims block peer landings; named files do not.
2. **Fetch-all, fast-forward-only-unheld.** `git fetch --all` everywhere (fetching is read-only and safe), but fast-forward only branches no live seat holds: pass `repo_state.py --skip <name>` for each repo a live claim covers. A held branch that moved is a `decision` with the holder named.
3. **Report health, never repair it under a live seat.** When `synthesis doctor` reports a client behind or a hook drifted while another session holds the release or install area, the briefing carries the line verbatim and the ritual moves on. No plugin reinstall, no runtime switch while the holder is live.
4. **Skip shared-state maintenance while seats are live.** Index rebuilds, inventory regeneration, watermark advances, decay sweeps — anything every seat reads — waits for a clear board. The ritual reports `deferred: seats live` rather than half-running them.
5. **Fold, don't run, others' artifacts.** A day-end artifact or handoff filed by another seat is folded into the briefing as-is. The ritual never executes, regenerates, or "verifies by re-running" a peer's artifact — re-running someone else's step under their claim is a collision wearing diligence as a costume.
6. **Release claims at end.** Every claim the ritual took is released (`synthesis release`), or narrowed to nothing retained, before the run closes, so the next seat starts from a clean board.

### What Concurrent-Seats Mode Keeps (Non-Negotiable)

- Board + inbox read at start (`synthesis who`, `synthesis inbox`), and the ritual's own seat registered with its file claims
- Full sync reads (fetch, channel reads, transcript capture) — reads never need a window
- Daily plan creation with the `decision`/`deferred` lines the rules above produce
- CONTEXT.md + session archive updates for the ritual's own files
- `ritual_state.py record` with `--mode concurrent-seats`

## Autonomous Work and Audio Alerts

When the user signals stepping away ("going to take a shower", "heading out", "don't wait on me", "continue without me"):

1. **Activate autonomous mode** — complete all planned work without prompting for confirmations. (A whole delegated task run to the end, overnight or longer, is `synthesis-autopilot`'s job.)
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

The same rule binds every banner and spoken line the ritual produces: the 16:55 nudge shows fixed text, and any count-bearing alert says counts plus a pointer to the screen ("3 decisions waiting. Details are on your screen."), never a name.

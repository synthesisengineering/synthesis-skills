# Draft messages — grounding protocol and formatting rules

The full protocol behind the draft rules in [SKILL.md](../SKILL.md):
research by question type, the investigate-first rule and its incident,
the verification checklist, the pre-send review gate, Slack formatting
with examples, draft numbering, temporal integrity, and appreciation
quality. The rules bind as written here; SKILL.md carries the digest.

## Grounding Protocol for Draft Messages

Every draft message must be grounded in primary sources before it is written. The depth of research scales with the type of claim being made, but the requirement applies to ALL drafts — not just ones that feel technical.

### Research by question type

| Question type | What to check | Examples |
|--------------|---------------|----------|
| **Technical** (architecture, how something works, root cause) | Source code, config files, PRs, `git log` | "How does X work?", "Why did Y break?" |
| **Status** (what's deployed, what's working) | Deploy scripts, version files, environment config, running services | "Is X on production?", "When was Y released?" |
| **Infrastructure** (secrets, credentials, environments, CI/CD) | Terraform, deploy scripts, `.env.example`, CI/CD workflows, docs | "How do we manage secrets?", "Where does X run?" |
| **Process** (PR workflow, branching, review, release) | Agent instruction files, contributor guides, recent git history, skill files | "What's the merge process?", "Who reviews?" |
| **Product** (feature behavior, user-facing text, prompts) | Component code, prompt YAML files, test files | "Does the tool do X?", "What does the user see?" |

### Investigate First, Ask Questions Later

**Before drafting ANY reply to a bug report or user issue, spend 10 minutes investigating.** Read the relevant code, check the config, search for the pattern. If you can fix it in those 10 minutes, fix it and draft a reply with the fix — not a reply asking for more information.

This principle applies to ALL draft messages that respond to reported problems:

- **Do NOT draft** "Can you share the URL?" when you could search the config and find the missing domain yourself.
- **Do NOT draft** "We're looking into it" when you could have already shipped the fix.
- **Do NOT draft** "Can you try again?" when you haven't investigated the root cause.
- **DO investigate** code, config, logs, and infrastructure before composing a reply.
- **DO fix the problem first** if possible, then draft a reply that leads with the fix.
- **Only ask the user** for information you genuinely cannot obtain yourself (specific reproduction steps, subjective preferences, environment details unique to them).

**Why:** The user's time is more valuable than the agent's. A fix shipped in 10 minutes builds more trust than a reply asking for more info. Action before questions.

**Example:** A user flagged "Import Failed" on certain stories. The initial draft asked for the specific URL. Instead, investigating the config found that a domain was simply missing from the allowed list. The fix took 10 minutes. No round-trip needed.

### The process

1. **Identify the claim.** Before writing, ask: "What factual assertions will this message make?"
2. **Research each claim.** Use Grep, Read, Glob, git log, or other tools to find the primary source.
3. **Note the evidence.** Record file paths, line numbers, config values, or PR numbers that support the claim.
4. **Draft with citations.** Include specific references where they add credibility (e.g., "We use GCP Secret Manager — see `terraform/modules/secrets/main.tf`").
5. **Flag uncertainty.** If a claim can't be fully verified, say so in the draft rather than guessing.

### Why this matters

The user's professional reputation depends on accuracy. A wrong technical claim in Slack is visible to the entire team and cannot be unsent. A delayed but accurate response is always better than a fast but wrong one.

**Incident (2026-03-17):** A technical reply was drafted based on conversation memory alone. It was partially wrong. The next day, another reply was drafted after reading the actual code — it was fully correct. The difference was 5 minutes of research.

### Scope

This protocol applies everywhere draft messages are created:
- Morning messages (Day-Start Step 7)
- Mid-day sync replies (synthesis-slack-sync Step 5)
- End-of-day communications (Day-End Step 3)
- Ad-hoc message requests throughout the day


## Draft Message Formatting Rules

All draft messages in the daily action plan must follow these formatting and quality rules. The user copy-pastes these directly into Slack — formatting errors waste time and look unprofessional.

### Slack Formatting

1. **Blank line after every bullet.** Slack requires a blank line between bullet points for them to render as separate items. Without blank lines, bullets collapse into a single paragraph. This is the most common formatting error — check every draft before saving.

   **Wrong (collapses in Slack):**
   ```
   • Item one
   • Item two
   • Item three
   ```

   **Right (renders as separate bullets):**
   ```
   • Item one

   • Item two

   • Item three
   ```

2. **Use Slack markdown, not GitHub markdown.** Slack uses `*bold*` not `**bold**`. Use `_italic_` not `*italic*`. Use `>` for blockquotes. Use `` `code` `` for inline code.

3. **Thread locators for every reply draft.** Include: channel name, human-readable date/time of parent message, author name, and first ~10 words of the message being replied to. Use the format: `**Channel:** #channel-name — Author Name, Mon Mar 30 at 11:31 AM EDT — "First ten words of the message..."`. The Slack thread TS (Unix timestamp) should be included for technical reference but is NOT the primary locator — the human-readable context is what the user needs to find the thread.

4. **Keep messages concise.** Slack messages over ~15 lines get collapsed behind a "Show more" fold. Front-load the most important information.

### Draft Numbering Convention

Drafts in a daily plan are labeled with sequential integers, not alphabet letters. The first draft of the day is **Draft 1**; each subsequent draft increments by 1.

**Do:**

- `### Draft 1: Multi-provider routing announcement`
- `### Draft 2: Reply to Oliver — Terraform readiness`
- `### Draft 11: Patrick public praise — release window`
- `### Draft 12: User-channel supplement (L&E)` (when same theme is routed to multiple audiences, each variant still gets its own integer)

**Do NOT:**

- `### Draft A: ...`, `### Draft B: ...` (alphabet labels — replaced by integers in v2.6.0)
- `### Draft K-2: ...`, `### Draft K-3: ...` (letter-with-suffix sub-versioning — replaced by sequential integers)

**Pre-draft step:** before adding a new draft, grep or scan the file for the highest existing `Draft N` integer and use N+1.

**Retraction:** if a draft is retracted (e.g., a fabricated message caught and removed), keep the number reserved in the file (`### Draft N — retracted` with a one-line pointer to the session log) rather than renumbering subsequent drafts. The reserved slot is the durable historical record.

See the v2.6.0 section of version-history.md for the full rationale (counting tax, lexicographic ordering, sub-version ugliness, cross-file consistency).

### Temporal Integrity

Every draft message must be accurate *at the time it will be sent*, not at the time it was written. This is the most common source of anachronistic messages.

**Before finalizing each draft, check:**

1. **Has the recipient already received this information?** If the same person was tagged in an earlier message or was present at a meeting where this was discussed, don't repeat it. Restructure the message to cover only what's new or what still needs their input.

2. **Do forward-looking statements match reality?** "Will review next" is a commitment. "Staging is ready for QA" is stale if QA already started. "Welcome back" is odd if the person was just in a meeting with you. Audit every verb tense.

3. **Are scheduled-for-later messages written in the right tense?** A message drafted Monday but scheduled for Tuesday must say "yesterday" not "today" when referencing Monday events. The easiest way to catch this: read the message as if you are the recipient reading it at the scheduled send time.

4. **Does the message acknowledge what happened since it was drafted?** If a standup, deployment, or Slack conversation happened between drafting and sending, re-check the message. Information that was "upcoming" may now be "completed."

5. **Has the topic moved to another channel or medium?** Obsolescence is cross-channel and cross-medium: a Slack question may have been answered in email, a meeting, or a different channel entirely. Before sending, sweep recent transcripts across ALL synced surfaces for the recipient + topic, and search email when the subject could plausibly have crossed mediums. For email replies, always re-pull the FULL thread first — the latest message may supersede the one being answered. Drafts older than 24 hours get full fact re-verification, not just a thread re-read. (Agent-assisted send paths should enforce this as a mandatory send-time gate — see the user's send-system skill if one exists.)

**Common temporal integrity failures:**
- "Welcome back" to someone who was at the meeting you just attended together
- "Staging is ready for QA" sent to someone who was already tagged in a staging notification
- "Good that you're meeting with X today" in a message scheduled for tomorrow
- "I'll review this next" when you've already moved on to other work

### Grounding Verification Checklist

Before finalizing each draft message, verify:

- [ ] **Every technical claim cites a source** — file path, line number, PR number, config value, or git SHA.
- [ ] **Every status claim is current** — verified against the actual system state (git log, deploy status, environment), not just memory or transcripts.
- [ ] **Every attribution is correct** — the right person is credited for the right work. Cross-reference PR authors via `gh pr view` or `git log`, not memory.
- [ ] **No stale information — checked beyond the thread.** Re-read the target thread via MCP to confirm no one has replied or resolved it, AND sweep for the topic across OTHER channels, DMs, and email — resolutions frequently happen outside the thread where the question was asked. A message rendered obsolete by a communication anywhere is obsolete everywhere.
- [ ] **Numbers are accurate** — test counts, file counts, line counts, character counts are from actual tool output, not estimates.
- [ ] **Temporal integrity passes** — message is accurate at the time it will be read, not just at the time it was written. See Temporal Integrity section above.

### Pre-Send Review Gate

Every draft message section in a daily plan must include the following notice before the first draft:

> **Review before sending.** These drafts are grounded in real data — code commits, test results, deployment logs, Slack threads, and project context — but they are starting points, not final messages. Read each one, edit it in your own voice, and add the personal touch only you can. Human-to-human communication deserves human effort.

This is not optional. Draft messages are research-backed starting points — not automated communications. The human must:
1. Read each draft fully before sending
2. Edit the tone and phrasing to match their voice
3. Add personal context that only they have (relationship nuance, recent conversations, political awareness)
4. Verify the message is appropriate for the current moment (not just factually correct)

The grounding section shows the research behind the draft. The human adds the judgment, timing, and personal touch that make the message authentic.

### Appreciation Message Quality

Appreciation messages must be specific and grounded, not generic. Each should reference:
- The specific work product (PR number, feature name, article title)
- What made it good (thorough test plan, clean architecture, consistent output, specific design decision)
- Observable impact (unblocks X, addresses user feedback Y, improves process Z)

**Generic (weak):** "Great work on the PR, Emil!"
**Grounded (strong):** "Emil — PR #96 was clean with solid UUID validation and 6 permission tests covering all access paths. The immediate user sync on org assignment was the right architectural call — avoids the confusion of next-login delays."


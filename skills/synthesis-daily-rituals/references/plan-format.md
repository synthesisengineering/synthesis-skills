# Daily plan format — structure, vocabulary, and revert protection

The producer side of the daily-plan contract. The consumer side is
synthesis-console's `docs/cockpit-design.md`; the two change together.
Cockpit Mode, the `## 📅 Calendar` section, and meeting-prep packs are
specified in [version-history.md](version-history.md) (v2.10.0–v2.12.0);
the draft fence and numbering conventions in v2.5.0 and v2.6.0 there.

## Daily Plan Structure: Preserve and Reorganize

The daily action plan is both a **live dashboard** (scannable current state) and a **historical record** (what happened today). These goals conflict if the file is treated as append-only — by evening, sections are scattered and duplicated, making the file unreadable.

### The Rule: Preserve All Information, Reorganize for Clarity

**Never delete information.** Completed tasks, sent messages, timestamps, decisions, and resolved items must always be preserved somewhere in the file.

**Reorganize freely.** Consolidate scattered sections, merge duplicate lists, reorder for readability. The file should have ONE section for each concern, not multiple sections that accumulated through the day. After every sync or major update, the file should read cleanly from top to bottom.

### Required File Structure (v2.4.0+)

The daily plan follows this canonical structure. On each update, consolidate into these sections rather than appending new ones. The synthesis-console v0.8+ cockpit parses these section names to typed regions; staying within the canonical vocabulary maximizes the typed UI surface.

```markdown
# Daily Action Plan — [Day], [Date]

**[Status line: version, key people, blockers]**

---

## Decisions needed from Rajiv     ← cockpit: NEEDS YOU region
[H3 question per decision. Each H3 may have **Option A:** / **Option B:** lines
 and a **Recommendation:** line. The cockpit renders option buttons that record
 a `**Decided:** Option X — <ISO>` marker back to the file on click.]

## Priority Tasks                  ← cockpit: TODAY region
### Do today — not negotiable      ← collapsible bucket (P0, expanded by default)
1. **Task title** — description    ← cockpit renders as checkbox; click writes
                                       `~~**Title**~~ ✅ **DONE HH:MM TZ**` in place

### Do today — should make it      ← P1 bucket (collapsed by default)
### Do today — can slip            ← P2 bucket
### Watch / waiting                ← muted styling
### Stale targets                  ← muted styling

## Drafts — Ready to Send          ← cockpit: DRAFTS region
> **Review before sending.** [Standard reviewer notice — keep verbatim.]

### Draft A — [Description]
**Send to:** `#channel-name` — [thread locator]
```
[message body in fenced code block — use 3 backticks if the body has no internal code blocks; use 4 backticks (````) if the body contains any internal ``` blocks. See v2.5.0 — Draft Fence Convention in version-history.md.]
```
**Grounding:**
- [bullet]
- [bullet]

## Standup Highlights              ← cockpit: lower-row collapsible (context tone)
## What Happened Yesterday         ← cockpit: lower-row collapsible (briefing)
## Things to Know                  ← cockpit: lower-row collapsible (briefing)
## Mid-day Sync                    ← cockpit: lower-row collapsible (briefing)
## Waiting On Others               ← cockpit: lower-row collapsible (waiting tone)
## Open PR Queue                   ← cockpit: lower-row collapsible
## Sent Messages                   ← cockpit: lower-row collapsible (done tone)
## Completed Today                 ← cockpit: lower-row collapsible (done tone)
## Sync state                      ← cockpit: lower-row collapsible
## Bugs (Open)                     ← cockpit: lower-row collapsible (briefing)
## Carried Items                   ← cockpit: lower-row collapsible (briefing)
```

### Canonical Section Vocabulary (Authoritative)

The synthesis-console v0.8+ parser classifies each H2 heading into one of these kinds. Use the canonical name where possible. The "synonyms" column lists variants the parser also recognizes via substring + case-insensitive match — these exist for backward compatibility but new plans should prefer the canonical name.

| Cockpit region / kind | Canonical H2 name | Recognized synonyms |
|----------------------|-------------------|---------------------|
| **decisions** (NEEDS YOU) | `Decisions needed` | "Decisions to make", "Open ask", "Asks for Rajiv", "Open Items", "Needs your attention", "Open Quality Concerns" |
| **priority-tasks** (TODAY) | `Priority Tasks` | "Tasks", "Tasks for Rajiv", "Tasks Today", "Today's Tasks", "Today's Priorities", "Still To Do", "This Week", "Remaining Tasks", "Pending This Session", "Pending from Before Vacation" |
| **drafts** (DRAFTS) | `Drafts — Ready to Send` | "Drafts", "Unsent — Ready to Send", "Unsent Drafts", "DM Reply Drafts", "Draft Messages", "Messages", "Next Steps", "Pending Emails", "Scheduled for Tomorrow / Later" |
| **standup** | `Standup Highlights` | "Standup Transcript", any heading with "standup", "Newsroom Training" |
| **sent-messages** | `Sent Messages` | "Messages Sent" |
| **waiting** | `Waiting On Others` | "Waiting on", "Delegated to Team" |
| **pr-queue** | `Open PR Queue` | "PR Queue", "Open PRs", "New PRs", "PRs Ready for Review", "PR Reviews Completed" |
| **sync-state** | `Sync state` | "Staging/Deployment Status", "Deployment Status", "Pre-Migration Status", "Post-Release Status", "Files Created/Modified", "Test Results", "Staging:" |
| **completed** | `Completed Today` | "Completed This Morning" |
| **briefing** | `Things to Know` | "What Happened", "What Changed", "Big Things", "Things Rajiv Should Know", "Carried From / Items / Forward", "Carry Forward", "Mid-day Sync", "Morning Sync", "From Slack Sync", "State Catch-Up", "Day Summary", "End of Day Summary", "Bugs (Open)", "QA Findings", "QA Results", "CRITICAL:", "Context", "What to Watch", "Future Work", "Post-Release Issues", "Feature Requests (Carryover)", "Release Process Sync" |
| **other** (fallback) | (any unrecognized H2) | Renders as plain markdown in the lower-row collapsibles. Nothing is lost; the section just isn't specially typed. |

### Internal Structure Conventions

Within each section, the parser also recognizes structural patterns. Adhering to these makes the UI work correctly:

**Decisions section** (`## Decisions needed`):
- One H3 per decision (`### 1. Force-push origin/develop?`)
- Options as bold paragraphs: `**Option A:** description`, `**Option B:** description`
- Optional: `Recommendation: **A** with rationale`
- After click: skill / human appends `**Decided:** Option X — <ISO>` directly under the H3
- **Synthetic asks**: an H2 like `## Open ask for Rajiv` with prose body and NO H3s also surfaces in NEEDS YOU as a single card with the prose verbatim. Use this for one-off requests that don't fit the A/B/C structure.

**Priority Tasks section** (`## Priority Tasks`):
- One H3 per bucket (`### Do today — not negotiable`)
- Tasks as numbered list items (`1. **Title** — description`) OR checkbox items (`- [ ] **Title** — description`). Both formats supported.
- Already-done tasks may be marked any of these ways (parser detects all): `~~Title~~ ✅ DONE HH:MM`, `[x]`, leading `✅`, leading `DONE` or `SENT`.
- The cockpit's TODAY region surfaces tasks as live checkboxes that write the canonical done marker back to the file on click.

**Drafts section** (`## Drafts — Ready to Send`):
- One H3 per draft (`### Draft A — Description`)
- A `**Send to:** target — locator` paragraph identifying the recipient. `**Channel:**` is also accepted.
- A fenced code block OR blockquote with the message body. **Fence convention (v2.5.0+):** default is 3 backticks; if the body contains any internal triple-backtick code blocks (install commands, log excerpts), use a 4-backtick outer fence (or any length strictly greater than the longest internal fence). The 4-backtick outer fence renders correctly in synthesis-console AND survives the Copy button intact (outer fence stripped, inner ` ``` ` preserved for Slack to re-interpret).
- Optional: a `**Grounding:**` paragraph or bullet list with research backing.
- After send: skill / cockpit appends `**Sent:** <ISO> (TS=...) <permalink>` directly under the body.
- **Drafts may also appear under non-drafts H2s.** When a draft is added to a topical context (e.g., a draft DM written into "Things to Know" alongside the situation that prompted it), the cockpit's DRAFTS region aggregates it from wherever it lives in the document. The canonical placement is still under `## Drafts`, but topical inline drafts work too.

**Pre-Send Review Notice**: every drafts H2 SHOULD include this verbatim blockquote before the first H3 draft (the cockpit doesn't currently re-display it in the DRAFTS region but it remains in the file for archival and Full-Markdown view):

```
> **Review before sending.** These drafts are grounded in real data — code commits, test results, deployment logs, Slack threads, and project context — but they are starting points, not final messages. Read each one, edit it in your own voice, and add the personal touch only you can. Human-to-human communication deserves human effort.
```

### What This Means in Practice

- When a draft is sent: move it from "Unsent" to "Sent Messages" with a timestamp. Don't create a new "More Sent Messages" section.
- When a bug is resolved: update the entry in "Bugs" to show it's resolved. Don't leave the old entry and add a new one elsewhere.
- When a sync finds new info: update the relevant existing section. Don't append a new section for each sync.
- When the file gets messy: do a full rewrite that preserves all information in the canonical structure. This is expected and encouraged — it's maintenance, not data loss.

### Why This Replaced "Append-Only"

The original "append-only" rule was designed to prevent accidental deletion of sent message records. The intent was correct — losing records causes duplicate sends and confusion. But in practice, append-only caused the file to balloon with scattered duplicate sections ("More Sent Messages (afternoon)", "More Sent Messages (afternoon, continued)", "Unsent — Ready to Send", "Unsent — Evening"), becoming unreadable by end of day.

The preserve-and-reorganize approach achieves the same safety goal (no information loss) while maintaining readability. The transcript files (`{workspace}/channels/YYYY-MM-DD.md`, `{workspace}/dms/YYYY-MM-DD.md`, `{workspace}/group-dms/YYYY-MM-DD.md`) are the authoritative append-only historical records. The daily plan is the dashboard.

### File Revert Protection

If a file revert is detected (system reminder says "file was externally modified"):
1. Re-read the ENTIRE file from disk before making any edits.
2. Compare the on-disk content against your in-memory understanding of the file.
3. If content is missing (items you know were written earlier are gone), reconstruct the missing content from Slack sync data, session memory, and transcript files.
4. Never silently accept a reverted file — always verify and restore.


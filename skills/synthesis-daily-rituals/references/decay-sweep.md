# Deadline collection and reconciliation

Day-End Step 4 selects by a tag's target date, not the date of its plan. A
deadline noticed in an older plan must remain visible when due, even after a
long interruption. The collector is read-only and grants no send authority.

## Design decision

Two approaches were considered: widening the agent's plan-reading window, or
collecting dated tags deterministically across the complete declared plan
scope. A wider window is simple but still loses old unresolved deadlines and
requires rereading every old plan with paid tokens. The deterministic collector
is selected: it reads all locally available dated plans, returns source
locators and coverage, and leaves contextual decisions to the agent and user.
It does not infer that local files represent all history or all workspaces.

## Source boundary

Run `python3 <skill-root>/scripts/decay_sweep.py --as-of YYYY-MM-DD
--plans-dir <declared-daily-plans-directory> --json`. Repeat `--plans-dir` for
each plan directory declared for this seat. Include archived subdirectories
under each declared root: there is no lookback cutoff. Supply `--artifacts-dir
<declared-ritual-workers-directory>` for this workspace's worker artifacts when
the distributed contract uses them. That option accepts dated day-start,
midday and day-end Markdown artifacts; plan directories accept dated Markdown
plans (`YYYY-MM-DD.md`). Pass today's verified calendar date as `--as-of`, even
when closing an earlier logical workday.

The desk reads its person-scoped plans. Workers collect their own workspace
records and put the count, source pointers and gaps in their existing artifact;
the desk folds those results and names missing worker coverage. Do not crawl
other workspaces or follow a plan's links into workspace-owned source records.
Declare any separately stored plan archive explicitly, under its owning seat.

The helper reports every selected file, skipped future file, excluded unrelated
file, malformed date, unreadable directory/file and refused symlink. Missing or
empty declared roots, incomplete enumeration, invalid tags, ambiguous identity
or conflicting same-day states produce `BLOCKED` and exit 2. Existing candidates
remain in the result alongside gaps. A scan with due candidates is `REVIEW`;
only a complete scan without due candidates is `CLEAR`. Successful scans exit 0;
that means collection succeeded, not that communications are approved or the
day may close. Fenced examples and blockquotes are not operative plan items.

## Item identity and outcomes

Keep the existing `**Decays:** YYYY-MM-DD (reason)` grammar. For new items add
an optional `**Decay ID:** <stable-id>` line in the same item block. Use a unique
ID per obligation, retain it when carrying or re-dating that obligation, and
never reuse it for a new task. This is ordinary Markdown metadata; it does not
change the Decays field or require rewriting old plans. IDs are scoped to the
declared plan/artifact roots passed in one invocation for the same seat.

An item block starts at a Markdown heading or list item and ends at the next
heading or peer list item. Put metadata directly under that heading/list item,
not in a separate subheading. The collector does not use a matching title to
merge obligations. Existing tags without IDs retain a source-path-and-line
identity and remain review candidates until a grounded outcome is recorded at
their original item. Do not bulk-generate IDs or infer resolutions from prose.

Carry the ID and Decays line into the new plan, including on the due date. A
later dated plan with that ID can re-date the obligation with a stated reason,
or record `**Sent:** <ISO timestamp>`, `**Released:** YYYY-MM-DD (reason)` or
`**Resolved:** YYYY-MM-DD (reason)`. Record only user-authorized actions or
directly verified outcomes. A checked task (`[x]`) or struck-through item title
also closes its own item; preserve the accompanying reason/evidence. Copied
plain prose without identity does not extinguish the original tagged item.

Identical copies with the same ID coalesce. The latest plan date determines the
operative entry; within one file the last entry wins. Day-start, midday and
day-end artifacts follow that declared run order. Different states in separate
files at the same date/run rank are ambiguous: the scan keeps the candidate
and reports a conflict rather than guessing which author won. A changed date
without a reason is likewise blocked. Future plans and future completion
timestamps cannot close today's obligations.

Read every returned item at its source, reconcile against current sent/released
evidence, then ask for the actual send, re-date or release decision. Do not send,
delete, re-date or mark complete merely because a script surfaced the item.

## Regression contract

Fixtures cover an old tag due today, an unresolved tag older than fourteen days,
future tags, invalid dates, unrelated files and quoted examples. Additional
tests cover carry-forward deduplication, reasoned re-dating, later resolution,
distinct obligations with matching titles, missing/unreadable sources, symlink
boundaries and invalid timestamps. The same helper and tests serve both clients.

# Step 0: the declared-window sweep

How a ritual sync carries out binding rule 1. The day-start sync (3c), the mid-day sync and the day-end sync
(step 1) of synthesis-daily-rituals each run this sweep for the window since the last sync, because the rule
needs a procedure that fetches every declared meeting. A request that names one meeting runs Steps 1 to 6 in
[protocol-steps.md](protocol-steps.md) instead.

The declared list decides what is fetched. Relevance is judged after fetching, from content, never before: no
judgment about which meetings look interesting stands between the list and the fetch, and every declared
meeting ends the sweep fetched or reported as an open gap.

## 1. Inventory the window

Read as the declared account first. An HTTP health check shows the server is up, not which account answers,
and unknown sign-in is an open gap (binding rule 2).

With the optional workspace-mcp helper ([README](../optional-workspace-mcp/README.md)), list the window:

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py" --window FROM THROUGH
```

It prints JSON: `documents`, every doc the declared patterns find, each marked saved or unsaved; `unsaved`;
`advance_through`, the moment the watermark may move to, with `advance_reason`; `scope`, which names the only
patterns searched; `undeclared`, the Gemini notes docs no declared pattern finds (declare a recurring one in
`meeting_patterns` to cover it); and `bounded_patterns`, the searches that may hide more docs. It exits 0 when
every declared doc is saved and `advance_through` is set, and 1 otherwise. A tool error prints
`{"coverage": "unknown", ...}` and exits 1.

With hosted connectors, run the same Drive search for each declared pattern with the window's `modifiedTime`
bounds, follow every page, and compare each doc ID with the IDs the saved files name. A saved file names its
doc in one of the three forms `--window` reads: a `**Source ID:**` header, a Google Doc link, or the first
backticked ID on a `> Source:` line (`` > Source: Gemini doc `<id>` ``).

Filter the inventory by nothing but the declared patterns: never by meeting title or perceived relevance.

## 2. Enumerate the declared set

From `.agents/meeting-transcripts.yaml`, take every declared meeting pattern crossed with every occurrence
that ended inside the window. That enumeration is the complete decision about what to fetch.

## 3. Fetch every member

Run Steps 2 to 5 of [protocol-steps.md](protocol-steps.md) for every member of the declared set. Judge
relevance afterwards, from content.

## 4. Account for every member

The sync report carries one line per declared member: fetched, with its saved path, or an open gap naming the
member, the window and the failure ("no doc found", "fetch failed", "verbatim half missing"). A member missing
from the report is the failure this step exists to prevent. A gap is closed this run or carried forward as a
blocking item, never dropped.

## 5. Advance the meetings watermark

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-daily-rituals/scripts/sync_watermark.py" advance --workspace <W> --surface meetings --through <T>
```

T, written with its offset, is the earliest of three moments:

- the window's end, read as Drive reads its days, in UTC;
- two hours before the check ran, since a meeting still under way may have no doc yet;
- one second before each unsaved doc was created.

`fetch-meeting.py --window` prints this moment as `advance_through`. Leave the watermark where it is after a
failed search, a full page, a next-page token, Drive's `incompleteSearch` warning or an unknown tab list
(binding rules 2 and 3).

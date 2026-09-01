# Sync watermarks — contract and rationale

`scripts/sync_watermark.py` keeps, per workspace, the last MOMENT each sync
surface — and each declared read target within a surface — was actually
written to the local mirror. Every sync computes its window from that
record, and a run proves its own coverage before the ritual proceeds.

## Why a moment and not a day (v2.30.0, 2026-09-01)

v2.27.0 introduced per-surface watermarks so a skipped run's hole would be
revisited automatically. They were day-granular, and a day cannot see the
hours. On one day-start a Slack surface was written at 09:15 and counted as
current for the rest of the day; the mid-day passes re-read only the targets
the morning had skipped, on the assumption that a DM read once was still
current; and at 17:51 the agent told the principal a question was still
unanswered, citing the 09:15 read, when the answer had gone out at 09:27.
Four defects were filed from that day and one mechanism closes them:

1. **Day-granular watermarks** → watermarks are ISO-8601 timestamps with
   offset, and `status` judges freshness against an explicit bound.
2. **Mid-day passes not re-reading what the morning read** → a surface
   carries one watermark per declared read target, and `status --since run`
   lists every target this run did not re-read.
3. **The principal's own outbound unmonitored** → the sweep's contract
   (synthesis-slack-sync Step 5) treats the user's own messages as first-class
   sweep state, and an "unanswered" or "unsent" claim must rest on a read
   inside the current run — which the same gate proves.
4. **Window parameters unverified** → `window` computes the epoch `oldest`
   a read call takes and prints it beside human-readable bounds. A first pass
   that morning had used an `oldest` of 07:50 *today* and reported five
   channels empty that were not. A window parameter is a claim about time,
   and it is computed, not typed.

## The verbs

```bash
python3 <skill-root>/scripts/sync_watermark.py begin   --workspace <W> --label day-start
python3 <skill-root>/scripts/sync_watermark.py window  --workspace <W> --surface slack --target <resolved id>
python3 <skill-root>/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <latest>
python3 <skill-root>/scripts/sync_watermark.py defer   --workspace <W> --surface slack --target <resolved id> --reason "<why>"
python3 <skill-root>/scripts/sync_watermark.py status  --workspace <W> --surface <s> ... --targets-from <declared.json> --since run
```

- **`begin`** stamps the run. Everything the run must re-read is judged
  against this moment.
- **`window`** prints `<surface>: <from> → <to> (<span>)` and
  `oldest=<epoch> latest=<epoch>`. The `oldest` is what the read call takes;
  copy it, never derive it. With `--target`, the window follows that target's
  own watermark, falling back to the surface's and saying so. A bootstrap
  window (nothing written yet) says to read to the workspace's backfill bound
  and to state that bound.
- **`advance`** records a successful write and moves only forward, never into
  the future. `--through` is the read's `latest` — an ISO timestamp, `now`,
  or a bare `YYYY-MM-DD`, which means complete through the **END of that day**
  and is therefore refused for today until the day is over: a mid-day run
  records the moment it read, not the date. With `--target` (repeatable)
  each target's own watermark advances; without it the surface's does.
- **`defer`** records a gap that genuinely cannot close this run, with a
  reason, for one day. A stale deferral is re-surfaced as blocking.
- **`status`** takes the declared set — every surface with `--surface`, every
  read target with `--target surface:id` or `--targets-from` (a JSON object
  `{"slack": ["C…", "D…"]}` or a list of `"surface:id"`) — and one freshness
  bound: `--since run`, `--since <timestamp>`, or `--max-age <duration>`.
  It exits non-zero while any declared surface or target is missing or older
  than the bound and not deferred, and names the keys. The store only knows
  what has been written, so a status without the declared set is refused.

## Store

`~/.synthesis/sync-watermarks/<workspace>.json`, schema 2:

```json
{
  "schema": 2,
  "run": {"started_at": "2026-09-01T11:39:02-04:00", "label": "mid-day"},
  "surfaces": {
    "slack": {
      "through": "2026-09-01T09:15:00-04:00",
      "updated_at": "2026-09-01T09:15:40-04:00",
      "targets": {"C0123": {"through": "2026-09-01T11:45:12-04:00", "updated_at": "…"}}
    }
  },
  "deferrals": {"slack:D0456": {"reason": "member left", "deferred_at": "…"}}
}
```

A schema-1 store (bare dates) is read as what it meant — complete through
the end of that day, capped by the moment the entry was written and never a
moment in the future — and rewritten as schema 2 on the next write.

## Where the ritual calls it

- Day-Start Step 3b and Day-End Step 1 open with `begin`, take every read
  window from `window`, record every saved read with `advance`, and close
  with `status … --since run`.
- The Mid-Day Sync Protocol does the same on every sync request: every
  declared target is re-read every sync. "Already read today" is a statement
  about the past, not about now.
- `synthesis-slack-sync` Steps 1, 3, 3b take `oldest` from `window`; Step 4
  records each saved read with `advance`; Step 5 cross-references the user's
  own outbound against owed items and forbids "unanswered" on a read older
  than the run.

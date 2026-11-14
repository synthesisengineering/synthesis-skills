# Preserved: retired passages of synthesis-daily-rituals 2.45.1

Read only to review what the v5 rewrite did not carry, and why. The whole 2.45.1 SKILL.md is
kept word for word in [preserved-skill-v2-part1.md](preserved-skill-v2-part1.md) and
[preserved-skill-v2-part2.md](preserved-skill-v2-part2.md); four retired reference files are
kept whole in [preserved-retired-references.md](preserved-retired-references.md). This file
holds the passages that left the references v5 kept, each with its reason.

Contents: Retired from ritual-worker-contract.md · Retired from ownership-routing.md · Retired from sync-watermarks.md · Retired
from decay-sweep.md · Retired from SKILL.md (what and why) · Anonymized lines.

## Retired from ritual-worker-contract.md

**Reason:** the fleet doctor is gone (the fleet machinery was cut, `project-state.md` section B);
the evidence contract described artifact custody receipts the code evaluation cut; the
native-memory sweep described `context_edit.py memory-probe`, `memory-ingest` and
`memory-clear-plan`, the old project-transaction machinery. v5's sweep is Day-End Step 5a in
[day-end.md](day-end.md): list the stores with one command, route durable entries archive-first,
never delete raw memory, never disable memory. The rules that still hold (memory stays on,
archive before ingesting, contradictions and public candidates become decisions, active
harnesses are pending, a missing store is a gap, counts only in alerts) carried over.

Old lines, verbatim:

registry syncs across the fleet, and the loader expands `~`/`$HOME` per Mac.
The fleet doctor fails on unexpanded absolute home paths in this file.

## Executable evidence contract

The mandatory [ritual evidence reference](ritual-evidence.md) defines the enforced
workspace root, full surface declaration, session/outcome binding, local lesson
candidate pointers, final Lesson candidates section, and bounded artifact checks.
Read it before any worker completion. The recorder verifies the actual artifact;
its digest receipt is file evidence, not a native identity attestation. Missing
artifacts and readiness gaps never justify backfill or a false clean record.

## Native memory capture-buffer sweep

- [ ] Keep native memory ON in every installed harness. Select each harness's
  actual machine/store and read the current coordination board with
  `context_edit.py memory-probe`; follow the complete native-memory protocol in
  `synthesis-context-lifecycle`. This bounded directory hash needs no model call.
- [ ] Skip active harnesses with explicit pending coverage, including the current
  harness. Unchanged incomplete work stays pending; missing/moved/unsupported
  stores are refusals, never an empty success. Do not infer NOT_APPLICABLE from
  a missing directory or CLI command.
- [ ] A changed store requires a qualified own-harness native export. Shared
  `memory-ingest` applies reviewed deterministic routing through the existing
  PM transaction owner, archives first, deduplicates exact canonical content and
  leaves contradictions/public candidates as decisions. Save returned pending
  identities and private evidence pointers in the existing worker artifact.
- [ ] Complete ordinary exact-session guarded publication at Step 11 before
  preparing `memory-clear-plan`. Only exact receipted archive/canonical bytes
  qualify; the source owner currently returns a non-executing native capability
  pending plan. No raw-file/database deletion or disabling native memory is
  permitted. Complete native clear only through a separately qualified native
  operation with a fresh active-seat check and exact unchanged hashes; retain its
  actual receipt before marking the memory ledger complete.
- [ ] Report counts and coverage gaps only in alerts. Continue the rest of the
  ritual while a harness is active or lacks qualified export/clear support. Such
  a gap prevents claiming a clean memory sweep, not all project work.

## Retired from ownership-routing.md

**Reason:** the chief-of-staff skill retired `scripts/overlap.py` and the shared time-block layer
in its own v5 change (its coverage map: no seat ever published `time-blocks.json`, and
`SYNTHESIS_TIME_BLOCKS` was never set). Each account's calendar is read through its own
connector, with the account-routing guard choosing the account. The surviving rule, that a
window nobody has read is not a free window, is in the reference's opening paragraph; the
routing rules and the movable-side rule are unchanged.

The opening paragraph's closing lines read:

commitment is the opposite: owned by the creating workspace but visible
to every seat, read-only, through the shared time-block layer. Time
cannot be separated even when tasks can.

The time-block layer text was:

## The shared time-block layer

One JSON file, synced across the principal's machines through the
personal repo — never per-machine local state, or seats strand:

```
<personal-repo>/coordination/time-blocks.json
```

Schema (`synthesis-time-blocks/v1`): an object with the `format` tag and
a `blocks` list. Each block carries `owner`, real-title `title`,
ISO-8601 `start`/`end` with a UTC offset, and `source` calendar, plus
optional `published_by` seat and `published_at` moment. Labels carry
real titles — every seat is the principal's own trusted team, and full
detail makes better conflict calls than opaque Busy markers. The repo is
private to the principal; nothing here is publishable elsewhere.

## Seat publish procedure (every ritual sweep)

1. Read this seat's owned calendars for the look-ahead window through
   the seat's own calendar access (MCP tools a script cannot call —
   publishing is a seat duty, not a script).
2. Rewrite each owned commitment as one block: owner workspace,
   start/end, real title, source calendar.
3. Hand-enter blocks for accounts beyond the agent's reach (by hand
   means by the AI system, from whatever the principal can see — never
   ask the principal to type calendar data) so the layer covers what no
   single seat's calendar check can.
4. Replace only this seat's own blocks in the shared file; other seats'
   blocks are theirs to publish. Then `overlap.py validate --layer` the
   file — a seat that cannot validate does not publish.
5. This procedure never writes to a calendar. Shared reads come first;
   agent writes to calendars are a later design, not this one.

## The overlap call (any seat, any window)

```bash
python3 <synthesis-chief-of-staff-root>/scripts/overlap.py overlaps \
    --layer <personal-repo>/coordination/time-blocks.json \
    --from <ISO-8601> --to <ISO-8601> [--json]
```

`--layer` may be omitted when `$SYNTHESIS_TIME_BLOCKS` points at the
file. The script takes a window and returns overlaps across owners —
same-owner pairs are excluded, touching endpoints are not overlaps —
with no MCP calls and no writes, so it runs identically in tests and in
rituals. Fixture layers live beside the script in
`synthesis-chief-of-staff/scripts/fixtures/`.

## Coverage reporting

The layer report names its denominator like every other sweep: how many
owner workspaces published fresh blocks for the window, which seats are
stale or missing, and which accounts entered by hand. "No overlaps"
without that denominator is not a result — it may mean no seat
published.

---

The conflict paragraph's first sentence was:

The script reports pairs; the calling seat applies Rule 3 and names the
movable side. When one seat sees both sides it resolves inline; across
seats it messages the owning seat on the coordination bus. Movability is
a judgment call recorded in the report — `movable: <side> because
<reason>` — never a silent default. A report that cannot determine
movability goes to the principal as a candidate, and the principal is
loudly informed of every machine-made movability decision with the
opportunity to reverse it: the seat uses its full intelligence and
context toward the principal's best interests, and asks whenever doubt
exceeds the very small.

## Retired from sync-watermarks.md

**Reason:** the commands ran through `synthesis exec-public`, which v5 removes (scripts run with
plain `python3`); the store moved under the v5 home; schema-1 reading was backward compatibility,
a non-goal (the live store has been schema 2 since 2026-09-01); the slack-sync step numbers
changed with that skill's own rewrite.

```bash
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py begin   --workspace <W> --label day-start
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py window  --workspace <W> --surface slack --target <resolved id>
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <latest>
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py defer   --workspace <W> --surface slack --target <resolved id> --reason "<why>"
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py status  --workspace <W> --surface <s> ... --targets-from <declared.json> --since run
```

`~/.synthesis/sync-watermarks/<workspace>.json`, schema 2:

A schema-1 store (bare dates) is read as what it meant — complete through
the end of that day, capped by the moment the entry was written and never a
moment in the future — and rewritten as schema 2 on the next write.

- `synthesis-slack-sync` Steps 1, 3, 3b take `oldest` from `window`; Step 4
  records each saved read with `advance`; Step 5 cross-references the user's
  own outbound against owed items and forbids "unanswered" on a read older
  than the run.

## Retired from decay-sweep.md

**Reason:** the command ran through `synthesis exec-public`. The same flags now run with
`python3 <rituals>/scripts/decay_sweep.py`.

Run `synthesis exec-public synthesis-daily-rituals/scripts/decay_sweep.py --as-of YYYY-MM-DD
--plans-dir <declared-daily-plans-directory> --json`. Repeat `--plans-dir` for

## Retired from SKILL.md (what and why)

Each passage is in the preserved SKILL.md parts word for word.

| Passage (2.45.1) | Why it was retired | What v5 does instead |
|---|---|---|
| Configuration table (`daily_plans_path`, `transcripts_path_in_private`, `personal_repo`, `workspace_private_repo_pattern`, `index_yaml_path`, `lessons_path`, `downloads_path`, `alert_sound`, `slack_auth_command`) | Defaults that the references state where they are used | Paths named in the steps that use them |
| "The day-end installer copies the launcher, nudge, its sibling ritual-state query helper..." | `install_day_end.py` REPLACED by `synthesis install` | `synthesis install` lays out `day-end` and the nudge; the nudge reads `current/synthesis/rituals.py` |
| Script invocation through `synthesis exec-public` | The verified launcher is cut (a directory walk on every call) | `python3 <rituals>/scripts/<name>.py` |
| Mandatory ritual evidence route; mechanical owner map; declared acquisition entries | Evidence custody and acquisition receipts CUT; they caused the 2026-10-01 regression | The watermark gate with connector reads; [preserved-retired-references.md](preserved-retired-references.md) |
| Step 1: `_load_config.py --doctor`, `message_guard.py --doctor`, email capability readiness and `--monitor-email`, `conformance.py parity` | Old guards and their doctors replaced by v5 guards | `synthesis doctor` checks runtime, hooks, guards and drift; the rationale sentence "a protective control that nobody monitors is one that is quietly broken" kept |
| Step 1: `coordination.py archive`, `prune_tool_snapshots.py`, `coordination.py stale` | The leased board and snapshot store are gone | `synthesis who --all` shows stale claims; releasing stays the principal's decision |
| Step 1: `ritual_state.py credential-paths` (names-only review) | `credential_paths.py` REPLACED by the commit check's filename rule (scenario 50) | The commit check refuses `.env`, `id_rsa`, `*.pem` and similar names at commit time |
| Step 3c: acquisition evidence before meeting coverage | Acquisition CUT | A saved transcript advances the meetings watermark; an unsaved one is a named gap |
| Day-End Step 2: "Read the pending repo-guard manifests first..." | Pending manifests CUT | Claims say which paths are this session's; commit only those |
| Day-End Step 5a: the native memory capture-buffer sweep through the worker contract | `context_edit.py` memory commands are old machinery | Day-End Step 5a in [day-end.md](day-end.md) |
| Day-End Step 11: lease-backed board, `checkpoint_sync.py --flush-pending`, `conformance.py continuity`, `repo_sync_check.py`, `REMOTE_READY` | Receipts, manifests and the readiness vocabulary CUT; handoff REPLACED | `synthesis handoff`, the records doctor, `repo_state.py --discover` |
| Ritual Persistence Protocol: local mode (PostToolUse manifests and Stop receipts) and remote mode (flush through repo-guard) | Same | Files on disk are the handoff on one Mac (R1.3); day-end publishes with `synthesis handoff`; the commit hygiene paragraph is kept verbatim in [day-end.md](day-end.md) |
| Concurrent-seats rule 3: "Report parity, never repair it. A PENDING parity check names its holder..." | The parity check is gone | The same rule against `synthesis doctor` findings |

## Anonymized lines

This is a public repository. Sixteen lines of the 2.45.1 references named private people, a
client project and personal email addresses: five example lines in `draft-grounding.md`, six in
`mailbox-manifest.md` (an incident sentence naming a friend, and five manifest example lines), and
five in `version-history.md` (an incident sentence and four example lines). v5 keeps each line's
meaning with neutral placeholders (a friend, `person@...example`, Pat Example, Kim) and does not
copy the originals here. The originals remain in the repository's history before v5.

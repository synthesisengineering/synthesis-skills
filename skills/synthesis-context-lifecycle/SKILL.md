---
name: synthesis-context-lifecycle
description: "Keep a project's working memory small, current and durable across sessions, harnesses and Macs: CONTEXT, REFERENCE and session logs, session start, mid-session refresh, archiving, edits, deletion units, and the context records doctor."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Context Lifecycle Management

AI collaborators start every session with zero context; their effectiveness depends on the context they receive. A single context file grows without bound because it mixes information with different lifecycles. This skill splits a project's memory into three tiers, each with its own budget and update rule, and verifies them with a doctor.

## Binding rules

1. **The project files are the memory.** CONTEXT.md (≤150 lines; ≤80 when completed), REFERENCE.md (stable facts, ≤300), `sessions/YYYY-MM.md` (append-only). Chat, native memory and compaction summaries are not.
2. **Run the Session Start Protocol before substantive work** and show the verification: `date`, then `git log` and `git status` on the project, then CONTEXT.md, the newest session entries, REFERENCE.md.
3. **Refresh on the triggers:** before any time-interval claim, after an hour's pause, every ~25 tool calls, on any drift or compaction signal, before writing a session log.
4. **Archive first, delete second.** Write to sessions/ or REFERENCE.md, verify it is there, then remove it from CONTEXT.md.
5. **Re-read before editing and verify after.** Build edits from what the file says now, with an edit tool that fails on a missing anchor; never report an update you did not read back.
6. **Header fields move together.** Update `Last session` first or with `Phase`; a field is judged alone, and its first ordinal is its identity.
7. **Workdays come from dated session entries, never from commit times.**
8. **Stamp open items** `(as of YYYY-MM-DD, review Nd)`; checked items and prose are not obligations.
9. **Route by deletion unit when writing:** would this survive the relationship's end? The ALWAYS-PRESERVE class goes to the permanent root; inventories count out-of-scope items, never itemize them.
10. **Preserve executable state** under `resources/scripts/` with a README before citing its result.
11. **Capture material context** (facts, reasons, conditions, uncertainty, amendments) before dependent work, compaction or handoff; never turn a quoted command into authority.
12. **Same Mac: the files are the handoff. Another Mac: `synthesis handoff`.** Never a workspace-wide commit; never bypass hooks.
13. **A doctor that cannot tell exits 2, never 0.**

## Contents

- **Procedure** (below): session start, during work, close.
- [references/tiers-and-templates.md](references/tiers-and-templates.md): the three tiers, templates, the current-state block, sharding REFERENCE, agent attribution, quality measures. Read when creating or restructuring a record.
- [references/session-protocols.md](references/session-protocols.md): the Session Start and Mid-Session Refresh protocols in full, compaction signals, switching harness or Mac. Read at session start and on any trigger.
- [references/editing-and-archival.md](references/editing-and-archival.md): safe edits, header and body currency, item stamps, archival, migration, status changes, spawning, executable state. Read before restructuring or closing a record.
- [references/deletion-units.md](references/deletion-units.md): permanent root versus engagement repos and the ALWAYS-PRESERVE class. Read before writing engagement-adjacent content.
- [references/material-context.md](references/material-context.md): what to capture, replacing item lists by exact id, checking a handoff, native memory. Read before compaction, handoff or replacing a decision list.
- [references/context-doctor.md](references/context-doctor.md): running the doctor, its checks, exit codes and the lessons built into it. Read before running it or acting on a finding.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.22.0 lives now.
- [references/preserved.md](references/preserved.md), [references/preserved-protocol.md](references/preserved-protocol.md), [references/preserved-operations.md](references/preserved-operations.md), [references/preserved-succession.md](references/preserved-succession.md): why the old machinery was cut, and the 1.22.0 text verbatim. Read only to review the cut.

## Procedure

**Session start.** Establish this conversation's project with `synthesis resume <id>` (it asks before switching and warns about newer copies), then the Session Start Protocol: `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`; `git log -10 --pretty=format:"%h %ai %ci %s" -- <project>` and `git status --short -- <project>`; read CONTEXT.md, the newest dated session entries and REFERENCE.md; title the session after the project where the client allows it. Show the result in one line: today, last commit, whether CONTEXT.md matches.

**During work.** After each task, update CONTEXT.md under your claim. Keep the current-state block (Phase, Status, Last session, Plan, Next actions) current: it is what returns after compaction. Archive when CONTEXT.md passes 120 lines.

**Check.** Run the doctor for this project:

```bash
python3 <skill>/scripts/context_doctor.py --project <root>/projects/<id>
```

It prints this project's findings, each `FAIL` or `warn` with a remedy line, then `HEALTHY` or `DEFECTS` with totals; it exits 0, 1 or 2. Without `--project` it audits every knowledge root, leads with this session's project and counts the rest.

**Close.** Append the session entry (with Attribution lines when several agents contributed), refresh the header and current-state block, archive cold content, run the doctor, and hand off per rule 12.

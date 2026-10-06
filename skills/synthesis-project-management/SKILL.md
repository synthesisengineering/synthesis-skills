---
name: synthesis-project-management
description: "Run synthesis projects as markdown records in git and keep parallel sessions from colliding. Use for project setup, naming, index, lessons, session start and end, claims before writes, one context owner, peer messages, worktrees, handoff between harnesses or Macs, Codex dispatch."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Project Management

Projects live as plain markdown in git under `ai-knowledge-{workspace}/projects/`,
so any session in Claude Code, Codex or Muse, on this Mac or another, continues
from files rather than chat. This skill sets projects up and runs them, and
keeps parallel sessions from overwriting each other through the `synthesis`
board (one small file per session).

## Binding rules

1. **Records live in one place.** Write project records only in the canonical knowledge checkout, never a worktree copy; `synthesis resume` names any newer or diverged copy. Chat, native memory and compaction summaries are not records.
2. **Read the board, then claim before writing.** `synthesis who`, then `synthesis claim` on the smallest coherent area. A refused claim stops that write and everything depending on it.
3. **One context owner per project.** Only one live session writes CONTEXT.md, REFERENCE.md, sessions/, the plan and the index entry; others write `resources/artifacts/contributions/<short id>.md` for the owner to reconcile.
4. **`projects/index.yaml` has many writers.** Claim the file and re-read it before editing, commit only it, then release it; a lock cannot fix a single-slot file, a claim serializes it.
5. **Autonomous claims keep priority** over interactive ones unless the principal reorders them.
6. **Stale claims are advisory, never deleted by hand.** After 8 quiet hours a claim stops blocking commits; take over only with `synthesis claim --take`, which tells the holder. Never release or edit another session's claims.
7. **Address peers by board id only:** session id, short name or `project:<id>`. Ambiguous addresses are refused, never guessed; display names are not addresses (seven misdeliveries, 2026-08-19 to 09-02).
8. **Commit only your own paths.** `git add` extends the index; check `git diff --cached --name-only`, then `git commit -o <paths>`. Never bypass hooks.
9. **A different project is a question, not a switch.** When the named project contradicts the session's own, name both and ask (wrong records, 2026-08-20).
10. **Re-derive scope before dispatch.** A count in a record is a claim from when it was written; recount from live files and fix the record in the same pass.
11. **A reader meeting newer state names its version and the update.** Never rewrite or "repair" a file a newer version wrote.
12. **Dispatch Codex only through `scripts/codex_dispatch.py`;** never call Codex unavailable without `--doctor`.

## Contents

- **Procedure** (below): start, work, pause, hand off. Read at every session start.
- [references/records-and-conventions.md](references/records-and-conventions.md): folder layout, design principles, index fields and status vocabulary, project naming, tiers, lesson formats, agent attribution. Read when creating a project, a lesson or an attribution line.
- [references/coordination.md](references/coordination.md): how claims behave, scope over a task, context ownership and contribution files, the index claim, priority and stale claims, peer messages, worktrees, release trains, crashes, version skew, durable placement. Read before claiming alongside other sessions, and when a claim or message is refused.
- [references/discovery-and-handoff.md](references/discovery-and-handoff.md): project discovery and the wrong-project guard, scope re-verification, status table, session start and end, handoff to another harness or Mac, work briefs between agents, sub-agent fan-out, common mistakes. Read when resuming, handing off or dispatching.
- [references/codex-dispatch.md](references/codex-dispatch.md): the wrapper, its output, and the failures it removes. Read before dispatching to Codex.
- [references/coverage-map.md](references/coverage-map.md): where every part of 2.21.6 and its scripts lives now.
- [references/preserved.md](references/preserved.md), [references/preserved-coordination.md](references/preserved-coordination.md), [references/preserved-state.md](references/preserved-state.md): why the old machinery was cut, the incidents behind the kept rules, and the 2.21.6 text verbatim. Read only to review the cut.

## Procedure

**Start.**

1. Run `date`, `synthesis who` and `synthesis inbox`.
2. `synthesis resume <id>` prints the directive, current state, phase, next actions, plan, and warnings (newer copies, upstream changes, other sessions here). If it asks a question (another project, unknown id), ask the principal; after a yes to a switch, `synthesis resume <id> --switch`.
3. Run the context-lifecycle Session Start Protocol and search `lessons/`.
4. `synthesis claim <absolute paths> --project <id> --goal "<goal>"`; a trailing `/**` claims a subtree. It prints `claimed:` and the paths, or `refused:` with the holder's id, harness, project and goal.

**Work.**

5. Task done, then update CONTEXT.md, then the next task.
6. Claim more before writing outside the claim; `synthesis release <paths>` as areas finish.
7. Parallel same-file work: `synthesis worktree create <repo> <path> <branch>`; retire merged trees with `synthesis worktree retire <path>`, never by hand.
8. Peers: `synthesis msg <address> "<text>"`, with `--durable` for a project handoff later sessions must see.

**Pause or end.**

9. Update CONTEXT.md, REFERENCE.md, `sessions/YYYY-MM.md` (with Attribution lines when several agents contributed) and plans under `resources/artifacts/`.
10. Same Mac, another harness: nothing to commit. Another Mac: `synthesis handoff -m "<message>"`, which must end `READY`; `NOT READY` lists what blocks it and nothing is forced.
11. `synthesis release`.

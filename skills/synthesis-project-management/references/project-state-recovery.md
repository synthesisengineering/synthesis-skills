# Project-state recovery

`scripts/project_state.py resolve` discovers a named project's state across the
canonical checkout, registered isolated worktrees, local and remote refs,
attributed dirty paths, lifecycle manifests and receipts, the active-project
pointer, and coordination claims. Each candidate records its worktree or ref,
project-touching commit, project tree, timestamp, dirty-path hashes, and owning
session where one is provable.

Equality and Git ancestry are the only ordering evidence. Timestamps describe
observations but never select a winner. A dirty state extends its exact base
commit; if a newer committed project state exists, the two are divergent until
reconciled. Two distinct attributed dirty states are also divergent. Missing
worktrees, unreadable evidence, and failed fetches are `UNKNOWN`; divergent
states are `CONFLICT`; an attributed interruption is `LOCAL_RECOVERABLE`.

A canonical checkout may fast-forward automatically only when its current head
is an ancestor of the selected head, tracked and staged state are clean, no
untracked path would be overwritten, and the selected project still exists
after the move. Otherwise the resolver reports the exact fresher source without
mutating unrelated state.

Structured projects store mutable operational truth in `CURRENT_STATE.json`:
phase, status, accepted baseline, controlling plan, next actions, last session,
owning coordination session, repository/project identity, durable Markdown
hashes, and source-repository heads. The bounded current-state block in
CONTEXT.md is compiled from it; narrative and historical acceptance remain
Markdown.

`scripts/plan_reference.py` is the shared controlling-plan resolver for state
and client context. A structured `controlling_plan` field takes precedence;
otherwise an explicit context field takes precedence over legacy artifact links.
Malformed, missing or ambiguous references refuse resolution. Parent-project
plans are allowed only inside the same repository, without traversing internal
symlinks. Outside Git, plans remain project-local. Stored paths are portable
project-relative references, not worktree-specific absolute names.

Parent-plan bytes enter semantic state and checkpoint hashes. Editing or deleting
that plan invalidates the prior receipt; deletion reports recoverable rather
than throwing an unhandled exception. Historical prose is retained, not rewritten
to match a newer structured field. If structured state is absent, competing
explicit legacy fields remain ambiguous and require reconciliation.

Release-currency prose checks prioritize the structured accepted baseline over
a candidate phase. Candidate, planned and example versions are not shipped
evidence; separately affirmed releases still expose a stale baseline. This is
a bounded consistency check, not proof of publication. Verify Git, release
receipts and installed payloads before making an external-state claim.

Use the same executable to create and verify that state; do not hand-edit the
compiled block:

```bash
python3 scripts/project_state.py build \
  --project /absolute/project/path --project-id example \
  --phase "implementation" --status active \
  --controlling-plan resources/artifacts/plan.md \
  --accepted-baseline 1.2.3 --next-action "Run acceptance" \
  --last-session 2026-09-03 --session-id SESSION_UUID \
  --source-head /absolute/source/repository=COMMIT

python3 scripts/project_state.py checkpoint \
  --project /absolute/project/path --session-id SESSION_UUID \
  --coordination-board /absolute/active-sessions.md \
  --receipt-root /absolute/project-state/receipts \
  --source-head /absolute/source/repository=COMMIT
```

Every repeated `--source-head` is resolved to a commit before the state or
receipt is issued. `validate` accepts the same source bindings. A changed
source head invalidates the prior clean receipt instead of being treated as a
fresh handoff.

The lifecycle hook first refreshes the coordination lease, then issues a clean
receipt only when the event matches one active coordination seat and its
project, state, claim, Git identity, durable hashes, and live source heads all
validate. An interrupted event retains the file-attributed pending manifest
and remains recoverable, but never receives a clean receipt. Foreign project
sessions never block one another.

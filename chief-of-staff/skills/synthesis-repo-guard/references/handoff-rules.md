# Rules for committing records

2.x carried these in `checkpoint_sync.py`, which recorded every edit in per-session
manifests and committed context repositories at day-end. v5 replaces the manifests with
claims (a session's claims name the paths it owns) and the committer with
`synthesis handoff`, which commits and pushes the changes inside this session's claims
and ends its report with READY or NOT READY. The rules are the part worth keeping; each
says whether `synthesis handoff` enforces it today.

## Contents

- [The rules](#the-rules)
- [Where each rule came from](#where-each-rule-came-from)
- [What the handoff does not yet do](#what-the-handoff-does-not-yet-do)

## The rules

| Rule | Enforced by `synthesis handoff` |
|---|---|
| Commit only the paths this session changed inside its own claims, by exact path; anything another session staged stays staged and uncommitted. | Yes: `git commit --only -- <paths>` with literal pathspecs. |
| Every hook runs. Never `--no-verify`, never retry around a refusal. | Yes. |
| Read the result from `git log` and `git status`, never from the absence of an error line. | Yes: NOT committed is reported with what git log still shows. |
| An `index.lock` is reported and left in place, never deleted. | Yes. |
| A detached HEAD commits nothing. | Yes. |
| Fetch, then push only as a fast-forward. On divergence keep the local commit, report both counts, and stop: never rebase, never force. | Yes. |
| Network down: keep the local commit, report it unpushed; a rerun pushes it. | Yes. |
| A checkout behind its upstream is reported, so nobody works on stale records. | Yes. |
| A record repository is touched only if every push remote is in the principal's own namespace, checked at run time whatever config or glob selected it; an empty allowed list refuses everything. | Not yet (see below). |
| A path this session changed and another session then overwrote is skipped and reported, not committed under this session. | Not by content: claims keep other sessions out of the path; nothing compares bytes. |
| A first commit on a new branch is pushed with an upstream, to that branch, never to main. | No: a branch with no upstream is reported NOT READY and nothing is pushed. |
| Paths with spaces, quotes or newlines, or more than fit on a command line, go into one commit. | Spaces and quotes, yes (literal pathspecs); very long path lists are not batched. |
| Never schedule any of this; it runs when the principal or a ritual asks. | Yes: it is a command. |

## Where each rule came from

- **Attribution before automation** (2026-05-13, `git add` adds to an index other agents
  share): an agent's commit swept in a peer's staged work. Inspect the index before
  committing, or commit with `--only`.
- **Never auto-commit what you cannot attribute** (2026-09-21): a flush that retired a
  whole repository's pending entries at once published another session's work as this
  one's. Retire per path, not per root.
- **A refused commit must read as refused** (2026-09-23): a commit gate's refusal printed
  a line that looked like success; the result is what git log says.
- **Config declares intent; the guard verifies reality** (2026-07-08, point 5): an
  innocent-looking glob for private context repositories matched a repository whose
  push remote belonged to a client organization. The runtime remote check refused it
  every time.
- **Event-driven, never wall-clock** (2026-07-08): mutation on a timer races the same
  repositories on another Mac; only reads poll.

## What the handoff does not yet do

The runtime remote check, the overwritten-path check, the first-push-with-upstream rule
and batching for very long path lists are listed for the owner of `synthesis handoff`
(the project-state part of v5) as scenarios R1.4 3, 4, 6, 11 and 12 of the code
evaluation. Until they land, before running `synthesis handoff` in a repository the
principal does not own outright, read `git remote -v` yourself and stop if any push
remote is outside their namespace.

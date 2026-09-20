# Fleet handoff: move work between machines

Work moves; processes do not. The unit of handoff is a repo plus its
flushed manifests, sealed under a ticket id, meeting at the git remote
plus the leased coordination board. The protocol reference is the
`synthesis-machine-sync` skill; the engine is `fleet_handoff.py`.

## Source Mac: park and seal

1. Quiesce the handing-off scope: commit or manifest everything, so
   nothing is dirty, unpushed, or unpulled.
2. `fleet_handoff.create_handoff_offer` runs the source gate. Readiness
   is `REMOTE_READY` when manifests were flushed, `CLEAN` when there is
   nothing to move, and `BLOCKED` when any alert fires (dirty files,
   unpushed or unpulled commits, a missing remote or upstream).
   `BLOCKED` refuses before anything is posted to the board and returns
   the alert list; resolve the alerts first.
3. On `REMOTE_READY` or `CLEAN`, the offer posts a `handoff-offer`
   message addressed to the destination machine-id, the source row
   parks (claims frozen, not freed — recoverable), and the offer seals
   into an artifact named `<ticket>.sealed.json` carrying the ticket id
   and the per-repo `(remote, branch, sha)` triples.

Verify a sealed artifact at any time (the CLI's one verb; it refuses
tampered or corrupted artifacts):

```bash
python3 skills/synthesis-project-management/scripts/fleet_handoff.py verify --artifact <ticket>.sealed.json
```

## Destination Mac: pull, verify, claim, accept, resume

1. Pull the board and find the offer addressed to this Mac's
   machine-id: `coordination.py status` refreshes the board mirror
   (authority reads always fence through the lease).
2. `fleet_handoff.verify_destination` checks every repo by remote URL:
   the destination holds a clone of the offered remote, the offered
   SHA is reachable from that remote, and the destination tree is
   clean. Dirty state refuses with the file list, and the source row
   stays parked so the work is recoverable. The source's local paths
   never enter verification — only `(remote, branch, sha)`.
3. Claim the scope through the normal claim verb. Overlap with the
   parked source annotates `overlaps-parked` with provenance (a
   warning, not an error); overlap with an active row stays an error.
   Then `fleet_handoff.accept_handoff` posts `handoff-accept` naming
   the accepted SHAs.
4. Complete the resume checklist and write the resume receipt
   (`fleet_handoff.resume_checklist` +
   `fleet_handoff.write_resume_receipt`, producing
   `<ticket>.resume.json`). A resume without a receipt is incomplete;
   the doctor flags it.

## Resume checklist

The engine reports five named checks; every one must pass before the
receipt is written:

| Check | Meaning |
|---|---|
| `board-truth` | A fresh board shows the destination row active with its `handoff-accept` posted. |
| `code-truth` | The destination tree is clean on the handoff paths and `HEAD` equals each offered SHA or a documented descendant. |
| `context-truth` | The offer is sourceless-complete: every repo carries `(remote, branch, sha)`, so nothing source-local is required. Re-read project context from the synced stores; anything the source knew but did not write down does not transfer, by design. |
| `claim-truth` | No active row besides the destination's holds an overlapping claim; any `overlaps-parked` successors are listed and their branches are never force-pushed over. |
| `receipt` | Written on completion; a failing checklist writes nothing. |

## Any-harness resume contract

Resume is harness-neutral: plan file plus git plus board only. The
handoff path holds no harness session formats and no step branches on
the destination client lane — the sealed loop passes identically no
matter which client runs the destination seat. What transfers is what
is durable: the board (offer, accept, claims), the code (shas on the
remote), and the synced stores (project context re-read, never
carried). If it was only in the source session's memory, it does not
transfer.

## See also

- [Enroll a second Mac](fleet-setup.md).
- [Daily fleet care](fleet-operations.md).

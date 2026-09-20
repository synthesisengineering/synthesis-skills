---
name: synthesis-machine-sync
description: "Enroll, sync, hand off, and retire Macs in a personal fleet with git plus the leased coordination board. Use when asked to: machine sync, enroll a Mac, fleet handoff, move work to another Mac, resume on another Mac, fleet doctor, bootstrap a new Mac, retire a Mac, workspace subscriptions."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Machine Sync

Keep a personal fleet of Macs (N=2 first) working as one system. Git remotes
plus the leased coordination board are the only transports: every shared
write goes through compare-and-swap, every Mac keeps its own machine
identity, and no file-replication transport sits in any write path.

This skill is the **protocol** — enroll/sync/leave/handoff plus the engines
that enforce them. Your personal stores (fleet registry copy, repos
manifest, subscriptions) travel in the personal knowledge repo and
materialize to each Mac.

## Non-negotiables

- Each Mac mints its own stable machine-id once
  (`~/.synthesis/fleet/machine-id`, mode 0600). The file never moves to
  another Mac; only the enrollment receipt names it.
- The fleet registry (`machines.json`) names exactly one primary. A
  secondary enrolls against the synced copy, never by founding a second
  fleet.
- Shared board rows identify sessions by `(machine_id, session_uuid,
  client_ref)`. Liveness is heartbeat age on the board, never a pid from
  another Mac.
- Secrets ride the `synthesis-fleet-secrets` provider, never synced files.
  No secret value appears in any synced store, board message, or receipt.
- Resume is harness-neutral: plan file + git + board only. No step in the
  handoff path branches on the destination client lane.

## Enroll a new Mac

Clean-install path only — never copy one Mac's state onto another. One
command downloads and installs everything, then onboards by asking
questions: it finds the knowledge repo over GitHub sign-in (running it
when needed) or asks for it, derives home, label, skill source,
workspace, and manifest, asks which workspace only when several match,
founds a new fleet when the repo holds none and otherwise joins as a
secondary, narrates every repo as it lands, and publishes the
enrollment back on success:

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- fleet join
```

On a Mac with no installation the same command runs the guided setup
first (answering its questions) and the join continues after it, so
one paste is the whole procedure from a bare machine. The join mints identity, clones subscribed repos, installs the hooks
runtime plus the skill set, enrolls the machine, verifies the doctor, and
publishes the enrollment to the shared registry. Every step writes a
receipt under `~/.synthesis/fleet/receipts/`; a rerun after any failure
or interrupt resumes safely and reports `noop` for finished steps. The
flags `--kb`, `--label`, `--role`, and `--workspace` override the
interactive answers for scripted runs. The underlying
`fleet_bootstrap.py` script is an agent-and-test entry point; humans use
the one-command installer above (or `synthesis fleet join` once set up).

## Sync (fetch shared state)

Syncing means pulling authority through git, on each Mac, independently:

1. Refresh the board mirror: `coordination.py status` (authority reads
   always fence through the lease; display reads label their lease SHA).
2. Pull subscribed repos; the divergence scan refuses split checkouts
   before they become push races.
3. Keep synced configs `~`-rooted: the doctor fails closed on literal
   home paths in synced files, and every consumer expands on load.

Never copy `~/.synthesis` subtrees, seats, spools, or transcript caches
between Macs. Per-machine state stays per-machine; shared state arrives
only through its remote.

## Handoff (move work across Macs)

Work moves; processes do not. The unit is a repo plus its flushed
manifests, sealed under a ticket id.

Source Mac — the gate refuses `BLOCKED` before posting anything:

1. Quiesce: commit or manifest everything; nothing dirty, unpushed, or
   unpulled in the handing-off scope.
2. `fleet_handoff.create_handoff_offer`: readiness `REMOTE_READY` (or
   `CLEAN` when nothing moves) posts a `handoff-offer` addressed to the
   destination machine-id, parks the source row (claims frozen, not
   freed), and seals the artifact.
3. The sealed artifact (`<ticket>.sealed.json`) carries the ticket id and
   the per-repo `(remote, branch, sha)` triples.

Destination Mac — pull, verify, claim, accept, resume:

1. Pull the board; find the offer addressed to this machine-id.
2. `fleet_handoff.verify_destination`: every repo resolves by remote URL,
   the offered SHAs are reachable from the remote, and the destination
   tree is clean. Dirty state refuses with the file list; the source row
   stays parked so the work is recoverable.
3. Claim the scope through the normal claim verb (overlap with the parked
   source annotates `overlaps-parked`, with provenance), post
   `handoff-accept`, then complete the resume checklist: board truth,
   code truth, context truth (re-read from synced stores), claim truth,
   and the written resume receipt. A resume without a receipt is
   incomplete; the doctor flags it.
4. The loop runs identically for every destination lane — no step reads
   the seat's client.

## Leave (retire a Mac)

1. Hand off or release every active row the Mac owns; park rows it may
   resume before the retirement date.
2. Mark `retired_at` on its `machines.json` entry and push the registry.
3. Re-pin its automations and runner tokens to a live Mac.
4. Rotate every secret the retired Mac could read (see
   `synthesis-fleet-secrets`), then wipe its `~/.synthesis/fleet/`
   identity. Retired identities never re-enroll; a returning Mac mints
   fresh.

## Workspace subscriptions

`~/.synthesis/fleet/subscriptions.json` maps each machine-id to the areas
it may commit. The commit gate refuses unsubscribed staged paths, naming
the machine and the needed subscription. Escape once per commit with an
explicit reason, logged on the board:

```bash
coordination.py check-staged --repository . --json \
  --override-subscription 'hotfix outside subscribed areas'
```

No registry means subscriptions are unenrolled and the gate passes; a
present registry with an unlisted machine, or paths outside every
subscribed area, fails closed.

## Doctor

`coordination.py fleet-doctor` runs the whole gate: synced-path
normalization, lease reachability, lease freshness, workset consistency,
parked coherence, sealed-artifact verification, and the workset
divergence scan. Any failure names its check and blocks with exit 1.

## Engine map

| Engine | Owns |
|---|---|
| `fleet_identity.py` | Machine-id minting, registry enrollment |
| `fleet_handoff.py` | Source gate, sealed offers, destination resume |
| `fleet_doctor.py` | Reachability, freshness, coherence, divergence |
| `fleet_subscriptions.py` | Workspace-subscription gate decisions |
| `fleet_bootstrap.py` | Idempotent new-Mac provisioning |
| `fleet_logical.py` | Repo-qualified overlap across checkout paths |
| `fleet_paths.py` | `~`-normalization primitives and the paths gate |

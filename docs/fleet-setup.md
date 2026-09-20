# Fleet setup: enroll a second Mac

Run a personal fleet of Macs as one system. Git remotes plus the leased
coordination board are the only transports: every shared write goes
through compare-and-swap, every Mac keeps its own machine identity, and
no file copy sits in any write path.

This guide enrolls a second Mac end to end. The protocol reference is
the `synthesis-machine-sync` skill; the bootstrap CLI below is
authoritative and every flag here exists in its implementation.

## Before you start

On the new Mac you need:

- A checkout of `synthesis-skills` (the bootstrap verifies it carries
  the component catalog, the machine-sync skill, and the hooks
  installer before it does anything).
- Network access to your git remotes and to the leased coordination
  board remote.
- A repos manifest: JSON naming what to clone, `~`-rooted paths
  expanded against the new Mac's home:

```json
{
  "schema_version": 1,
  "repos": [
    {"remote": "https://github.com/example/notes.git", "path": "~/workspaces/notes", "branch": "main"}
  ]
}
```

`branch` is optional. Paths may be `~`-rooted or absolute.

- For a secondary Mac: the synced copy of the fleet registry
  (`machines.json`) from the personal knowledge repo, already cloned
  onto the new Mac. A secondary enrolls against that synced copy and
  refuses to found a second fleet. A primary founds the registry and
  omits `--fleet-registry`.
- For secrets: the `op` CLI (see "Sign in on each Mac" below).

Clean-install path only: never copy one Mac's `~/.synthesis` state,
seats, spools, or transcript caches onto another. Per-machine state
stays per-machine; shared state arrives only through its remote.

## Enroll

Run the bootstrap on the new Mac itself:

```bash
python3 skills/synthesis-project-management/scripts/fleet_bootstrap.py \
  --home ~ --source-root ~/workspaces/example/synthesis-skills \
  --label my-new-mac --role secondary \
  --repos-manifest fleet-repos.json \
  --fleet-registry ~/workspaces/example/fleet/machines.json
```

| Flag | Meaning |
|---|---|
| `--home` | Home being provisioned (required; `~` in the manifest expands against this, never the invoking shell's home). |
| `--source-root` | `synthesis-skills` checkout to install from (required). |
| `--label` | Human name for this Mac, recorded in the registry (required). |
| `--role` | `primary` (founds the registry) or `secondary` (required). |
| `--repos-manifest` | Repos-manifest JSON (optional; no manifest means nothing to clone). |
| `--fleet-registry` | Synced `machines.json` from the personal knowledge repo (required for `secondary`). |

The bootstrap runs five steps in order and stops at the first failure:

1. `mint-identity` — mints this Mac's stable machine-id once
   (`~/.synthesis/fleet/machine-id`, mode 0600, never overwritten,
   never moved to another Mac).
2. `clone-repos` — clones subscribed repos; existing checkouts are
   verified against their subscribed remote, never clobbered.
3. `install-runtime` — installs the hooks runtime plus the skill set
   from `--source-root`.
4. `enroll-machine` — enrolls the minted identity in the fleet
   registry under `--label` and `--role`.
5. `verify-doctor` — runs the fleet doctor over the new Mac's board
   mirror and handoff artifacts; any finding fails the step.

## What each receipt means

Every step writes a receipt under `~/.synthesis/fleet/receipts/` named
`bootstrap-<step>.json`. Each receipt carries the step name, a status
(`done`, `noop`, or `fail`), a human-readable detail line, the receipt
path, the machine-id, and a timestamp. The CLI also prints one line per
step, for example:

```text
DONE bootstrap-mint-identity: minted machine-id: <machine-id>
  receipt: /Users/example/.synthesis/fleet/receipts/bootstrap-mint-identity.json
```

Read them in order when enrollment fails: the first receipt with
`fail` names the step and the reason, and later steps never ran.

## Rerun safety

The bootstrap is idempotent: rerunning it re-verifies current state
and reports `noop` instead of redoing work. Minting refuses to
overwrite an existing machine-id, cloning refuses to clobber a
directory that is not the subscribed checkout, installing is a no-op
when the same source root is already installed, enrollment is a no-op
when this machine is already enrolled under the same label and role,
and the doctor step re-verifies and reports `noop` while it keeps
passing. Fix the underlying problem and rerun the same command; exit
code is 0 only when every step is `done` or `noop`.

## Sign in on each Mac

Secrets ride the `synthesis-fleet-secrets` provider, never synced
files. Each Mac signs in independently:

1. Install the `op` CLI and sign in (`op signin`). The secrets
   manifest itself lives in the personal sphere and travels out of
   band — it is never committed to a shared repo.
2. Dry-run, then materialize, then run the doctor:

```bash
python3 scripts/materialize.py --manifest secrets-manifest.yaml --dry-run
python3 scripts/materialize.py --manifest secrets-manifest.yaml
python3 scripts/secrets_doctor.py --manifest secrets-manifest.yaml --scan-root ~/workspaces/example
```

`materialize.py` takes `--manifest` (required), `--home`, `--backend`,
`--dry-run`, and `--no-backup`; `secrets_doctor.py` takes `--manifest`
(required), `--home`, `--backend`, and repeatable `--scan-root`.
Every protective check fails closed: a missing or signed-out `op`, an
invalid manifest, loose permissions, or an unverifiable values-absent
scan is an error, never a silent pass.

Revoking a Mac means removing its vault access; it then fails closed
with "secret unavailable," never with stale cached values.

## Next steps

- [Move work between machines](fleet-handoff.md).
- [Daily fleet care](fleet-operations.md).

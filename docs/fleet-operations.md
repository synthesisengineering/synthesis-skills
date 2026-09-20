# Fleet operations: daily care

Keep every Mac healthy, keep checkouts united, keep secrets vaulted,
and retire machines cleanly. The protocol reference is the
`synthesis-machine-sync` skill; secrets ride
`synthesis-fleet-secrets`.

## Fleet doctor

`coordination.py fleet-doctor` runs the whole gate: synced-path
normalization plus six checks — lease reachability, lease freshness,
workset consistency, parked coherence, sealed-artifact verification,
and the workset divergence scan. Any failure names its check and
blocks with exit 1 (failures print to stderr).

```bash
coordination.py fleet-doctor
coordination.py fleet-doctor --repo ~/workspaces/example/notes --machine-id <machine-id>
```

| Flag | Meaning |
|---|---|
| `--synthesis-root` | `~/.synthesis` root to scan (default: the real one). |
| `--artifacts-dir` | Handoff artifacts directory (default: `<synthesis-root>/fleet/handoffs`). |
| `--repo` | Workset checkout to divergence-scan; repeatable (default: this machine's claimed workspaces). |
| `--machine-id` | Machine whose workspaces to scan (default: this Mac's enrolled id). |

Read the output line by line: each check reports `PASS` or `FAIL`
with its id and detail. `reachability` proves the lease remote
answers; `lease-freshness` proves the local board mirror matches the
leased tip byte for byte (refresh before any authority decision when
it differs); `workset-consistency` proves every live row names
parseable worksets and non-empty claims; `parked-coherence` proves
parked rows carry park records and every `overlaps-parked` annotation
references live rows on both ends; `artifact-sealed` proves every
sealed handoff artifact verifies (open, unsealed artifacts are listed,
never failed); `divergence-scan` proves no workset checkout has
diverged from its upstream.

## Divergence drill

When `divergence-scan` fails, it names the repo and how far it split
(for example, `2 ahead, 1 behind <upstream>`). Fetch first, reunite
the branches, and never force-push over the other side — the same
rule as handoff resume: a second checkout of the same scope is
re-validated, never overwritten. Rerun `fleet-doctor` until the scan
passes.

## Subscriptions

`~/.synthesis/fleet/subscriptions.json` maps each machine-id to the
areas it may commit. The commit gate refuses unsubscribed staged
paths, naming the machine and the needed subscription. Escape once
per commit with an explicit reason, logged on the board:

```bash
coordination.py check-staged --repository . --json \
  --override-subscription 'hotfix outside subscribed areas'
```

No registry means subscriptions are unenrolled and the gate passes; a
present registry with an unlisted machine, or paths outside every
subscribed area, fails closed.

## Secrets rotation

Issue new values in the vault, re-materialize on each Mac, verify
with the doctor:

```bash
python3 scripts/materialize.py --manifest secrets-manifest.yaml
python3 scripts/secrets_doctor.py --manifest secrets-manifest.yaml --scan-root ~/workspaces/example
```

Old plaintext (where it predates the vault) is rotated, not just
deleted: revoke the old credential after the new one verifies on
every Mac. Run the doctor's `--scan-root` over every synced store so
no value lingers in a synced file.

## Leaving the fleet

Retire a Mac in this order:

1. Hand off or release every active row the Mac owns
   (`coordination.py release --id <session>`; hand off per
   [fleet handoff](fleet-handoff.md) when the work continues
   elsewhere). Park rows it may resume before the retirement date
   (`coordination.py park --id <session> --basis operator`).
2. Mark `retired_at` on its `machines.json` entry and push the
   registry.
3. Re-pin its automations and runner tokens to a live Mac.
4. Rotate every secret the retired Mac could read, then wipe its
   `~/.synthesis/fleet/` identity. Retired identities never
   re-enroll; a returning Mac mints fresh.

## See also

- [Enroll a second Mac](fleet-setup.md).
- [Move work between machines](fleet-handoff.md).

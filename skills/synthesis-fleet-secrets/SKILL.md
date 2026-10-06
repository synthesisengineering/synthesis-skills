---
name: synthesis-fleet-secrets
description: "Provision machine secrets from a vault (1Password's op CLI) onto a Mac by hand, owner-only, with nothing in git. Use when asked to: fleet secrets, secrets manifest, materialize secrets, op backend, vault provisioning, check secrets, enroll a Mac's secrets, rotate secrets."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Fleet Secrets

Provision per-machine secrets from a vault by hand. A private secrets manifest
maps vault refs to file paths and permissions; you read each ref from the vault
at enrollment and write the value with owner-only permissions. Plaintext
values never touch git. v5 ships no secrets tooling: the four 1.0 scripts were
never used and were removed, and the commit check (R3.3) refuses credentials in
any commit.

## Binding rules

Rules 1 to 5 are the 1.0.0 Non-negotiables, applied by hand; rules 6 to 9 come from the enrollment, rotation and backend sections.

1. **The secrets manifest carries refs only, never values.** An entry with a `value:` key is a defect: delete the key and rotate that value.
2. **The real secrets manifest lives in the personal sphere** and is never committed to a shared repo. Only the schema and generic examples ship here.
3. **No secret value or vault item content appears in code, tests, fixtures, or commit messages.** Examples use fake refs (`op://ExampleVault/...`) only.
4. **Service-account tokens (headless hosts) live in the OS credential store,** scoped to a minimal per-role vault: never in flags, files, or manifests.
5. **Every check fails closed:** missing or signed-out `op`, an invalid manifest, loose permissions, or a values-absent scan that could not run is an error, never a silent pass.
6. **Enroll in order: list, then materialize, then check,** with the values-absent scan over every synced store.
7. **Revoking a Mac means removing its vault access.** It must then fail closed with "secret unavailable", never serve stale cached values.
8. **Rotate, don't just delete:** revoke the old credential only after the new one verifies.
9. **The age/SOPS backend is a ruled future design, not implemented.** Use 1Password.

## Contents

- [references/enrollment-age-sops.md](references/enrollment-age-sops.md): the ruled future design for an age/SOPS backend (Variant 2). Read it before building or enrolling with that backend.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text and each script change now lives.
- [references/preserved.md](references/preserved.md): the 2.0.0 text for the removed scripts, verbatim. Read only to review the change.
- Manifest schema, Materialize by hand, Check by hand, Enrollment (new Mac), Rotation: below.

## Manifest schema

YAML or JSON. Paths are `~`- (or `$HOME`-) rooted; modes are owner-only:

```yaml
schema_version: 1
backend: onepassword
entries:
  - ref: op://ExampleVault/ExampleItem/api-key
    path: ~/.synthesis/example-service/api-key
    mode: "0600"
```

Field rules:

| Field | Rule |
|---|---|
| `schema_version` | Exactly `1` |
| `backend` | `onepassword` or `age-sops` |
| `ref` | Non-empty; `op://...` for 1Password, `<file>#<key>` for age/SOPS |
| `path` | `~/...` or `$HOME/...`; no literal home paths, no `..` |
| `mode` | Exactly `"0600"` or `"0400"`, quoted |

Unknown keys are invalid. Two entries with one destination path are invalid. Read the manifest against this table before any write.

## Materialize by hand

First `op whoami`; if it fails, stop (rule 5). Then list what would be written: each entry's ref, path and mode, and whether the path exists. For each entry:

```bash
umask 077
dest="$HOME/.synthesis/example-service/api-key"
mkdir -p "$(dirname "$dest")"
[ -e "$dest" ] && cp -p "$dest" "$dest.bak.$(date +%Y%m%d%H%M%S)"   # back up before overwrite
op read 'op://ExampleVault/ExampleItem/api-key' > "$dest" && chmod 600 "$dest"
```

`op read` fails closed on a missing item or lost access; never paste a value into a command line, and never echo one.

## Check by hand

- `op whoami` succeeds.
- Each path exists with its mode: `stat -f '%Lp %N' "$dest"` (macOS) prints `600` or `400`.
- The manifest has no `value:` key: `grep -n 'value:' secrets-manifest.yaml` prints nothing.
- No value is in a git-tracked file of any synced store: `git -C <repo> grep -q -F -f "$dest"; echo $?` per value and repository. `1` means absent; `0` means a leak, so remove it, rotate the value and check history; any other exit means the scan did not run, which is a failure (rule 5). The value stays in its file; it never appears in the command or its output.

## Enrollment (new Mac)

1. Install the `op` CLI and sign in (`op signin`). Headless hosts use a
   service-account token from the OS credential store, never a file.
2. Place the personal secrets manifest on the Mac (out of band — it never
   travels through a shared repo).
3. List, then materialize, then check, with the values-absent scan over
   every synced store.
4. Revoking a Mac = removing its vault access. The removed Mac then fails
   closed with "secret unavailable," never with stale cached values.

## Rotation

Issue new values in the vault, re-materialize on each Mac, verify with the
checks above. Old plaintext (where it predates the vault) is rotated, not just
deleted: revoke the old credential after the new one verifies.

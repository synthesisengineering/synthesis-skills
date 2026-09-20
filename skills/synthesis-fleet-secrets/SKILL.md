---
name: synthesis-fleet-secrets
description: "Provision machine secrets from a vault-backed provider across a personal Mac fleet. Use when asked to: fleet secrets, secrets manifest, materialize secrets, op backend, vault provisioning, secrets doctor, enroll a Mac's secrets, rotate fleet secrets."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Fleet Secrets

Provision per-machine secrets from a vault-backed provider. The secrets
manifest maps backend refs to materialization paths and permissions; the
provider resolves each ref at enrollment (or on doctor demand) and writes the
value with owner-only permissions. Plaintext values never touch git.

This skill ships the 1Password (`op` CLI) backend tonight and the dual-mode
seam for a future age/SOPS backend (Variant 2), which exists as a documented
stub. See `references/enrollment-age-sops.md` for the ruled future design.

## Non-negotiables

- The secrets manifest carries refs only — never values. The parser rejects
  any `value:` key outright.
- The real secrets manifest lives in the personal sphere and is never
  committed to a shared repo. Only the schema and generic examples ship here.
- No secret value or vault item content appears in code, tests, fixtures, or
  commit messages. Fixtures use fake refs (`op://ExampleVault/...`) only.
- Service-account tokens (headless hosts) live in the OS credential store,
  scoped to a minimal per-role vault — never in flags, files, or manifests.
- Every protective check fails closed: missing `op`, signed-out `op`,
  invalid manifest, loose permissions, or an unverifiable values-absent scan
  is an error, never a silent pass.

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

Field rules (`scripts/secrets_manifest.py` is normative):

| Field | Rule |
|---|---|
| `schema_version` | Exactly `1` |
| `backend` | `onepassword` or `age-sops` |
| `ref` | Non-empty; `op://...` for 1Password, `<file>#<key>` for age/SOPS |
| `path` | `~/...` or `$HOME/...`; no literal home paths, no `..` |
| `mode` | Exactly `"0600"` or `"0400"`, quoted |

Unknown keys are rejected. Duplicate destination paths are rejected.

## Commands

All commands take `--manifest PATH` and resolve `~` against the real home
unless `--home DIR` overrides it (tests). `--backend` defaults to the
manifest's declared backend. `fake` selects a fixture backend for tests only.

Materialize (refs in, files out, existing files backed up before overwrite):

```bash
python3 scripts/materialize.py --manifest secrets-manifest.yaml --dry-run
python3 scripts/materialize.py --manifest secrets-manifest.yaml
```

Doctor (backend available, manifest valid, permissions correct, values
absent from the manifest and from git-tracked files under `--scan-root`):

```bash
python3 scripts/secrets_doctor.py --manifest secrets-manifest.yaml --scan-root ~/workspaces/example
```

Provider interface (see `scripts/secrets_provider.py`):

```python
from secrets_provider import OnePasswordBackend, SecretsProvider
provider = SecretsProvider(OnePasswordBackend())
value = provider.get("op://ExampleVault/ExampleItem/api-key")
report = provider.materialize(manifest)
```

## Enrollment (new Mac)

1. Install the `op` CLI and sign in (`op signin`). Headless hosts use a
   service-account token from the OS credential store, never a file.
2. Place the personal secrets manifest on the Mac (out of band — it never
   travels through a shared repo).
3. Dry-run, then materialize, then run the doctor with `--scan-root` over
   every synced store.
4. Revoking a Mac = removing its vault access. The removed Mac then fails
   closed with "secret unavailable," never with stale cached values.

## Rotation

Issue new values in the vault, re-materialize on each Mac, verify with the
doctor. Old plaintext (where it predates the vault) is rotated, not just
deleted: revoke the old credential after the new one verifies.

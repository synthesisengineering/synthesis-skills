# Fleet secrets: preserved text

Contents:
- Why this text was retired
- SKILL.md 2.0.0 (whole body)
- references/enrollment-age-sops.md 1.0.0 (whole file)

## Why this text was retired

The v5 code evaluation (`tool-scripts.md`, synthesis-fleet-secrets row) ruled the four
scripts CUT, never used: "`op` is not installed and no manifest exists outside test
fixtures; R3.3 covers secrets in commits." They were `secrets_manifest.py` (190 lines),
`secrets_provider.py` (194), `materialize.py` (330) and `secrets_doctor.py` (259), built
for the multi-Mac fleet design (#172, 2026-09-19). The rules they enforced are kept as a
manual procedure in SKILL.md: the manifest's field rules, refs only, owner-only modes,
backup before overwrite, fail closed when `op` is missing or signed out, and a
values-absent scan of every synced store. Everything below is verbatim.

## SKILL.md 2.0.0

### Fleet Secrets

Provision per-machine secrets from a vault-backed provider. The secrets
manifest maps backend refs to materialization paths and permissions; the
provider resolves each ref at enrollment (or on doctor demand) and writes the
value with owner-only permissions. Plaintext values never touch git.

This skill ships the 1Password (`op` CLI) backend tonight and the dual-mode
seam for a future age/SOPS backend (Variant 2), which exists as a documented
stub. See `references/enrollment-age-sops.md` for the ruled future design.

### Binding rules

Rules 1 to 5 are the 1.0.0 Non-negotiables, word for word; rules 6 to 9 come from the enrollment, rotation and backend sections.

1. The secrets manifest carries refs only — never values. The parser rejects
   any `value:` key outright.
2. The real secrets manifest lives in the personal sphere and is never
   committed to a shared repo. Only the schema and generic examples ship here.
3. No secret value or vault item content appears in code, tests, fixtures, or
   commit messages. Fixtures use fake refs (`op://ExampleVault/...`) only.
4. Service-account tokens (headless hosts) live in the OS credential store,
   scoped to a minimal per-role vault — never in flags, files, or manifests.
5. Every protective check fails closed: missing `op`, signed-out `op`,
   invalid manifest, loose permissions, or an unverifiable values-absent scan
   is an error, never a silent pass.
6. **Enroll in order: dry-run, then materialize, then run the doctor** with `--scan-root` over every synced store.
7. **Revoking a Mac means removing its vault access.** It must then fail closed with "secret unavailable", never serve stale cached values.
8. **Rotate, don't just delete:** revoke the old credential only after the new one verifies.
9. **The age/SOPS backend is a documented stub.** `AgeSopsBackend` raises `NotImplementedError`; use the 1Password backend.

### Contents

- [references/enrollment-age-sops.md](references/enrollment-age-sops.md): the ruled future design for the age/SOPS backend (Variant 2). Read it before building or enrolling with that backend.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives.
- Manifest schema, Commands, Enrollment (new Mac), Rotation: below.

### Manifest schema

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

### Commands

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

### Enrollment (new Mac)

1. Install the `op` CLI and sign in (`op signin`). Headless hosts use a
   service-account token from the OS credential store, never a file.
2. Place the personal secrets manifest on the Mac (out of band — it never
   travels through a shared repo).
3. Dry-run, then materialize, then run the doctor with `--scan-root` over
   every synced store.
4. Revoking a Mac = removing its vault access. The removed Mac then fails
   closed with "secret unavailable," never with stale cached values.

### Rotation

Issue new values in the vault, re-materialize on each Mac, verify with the
doctor. Old plaintext (where it predates the vault) is rotated, not just
deleted: revoke the old credential after the new one verifies.

## references/enrollment-age-sops.md 1.0.0

### age/SOPS Backend — Enrollment Design (Variant 2, ruled future)

The age/SOPS backend is not implemented. `AgeSopsBackend` in
`scripts/secrets_provider.py` is a stub raising `NotImplementedError`. This
document records the enrollment design so the dual-mode seam (the
`SecretsBackend` interface plus the manifest `backend` field) can grow the
second backend without changing callers.

### Layout

- Ciphertext lives in a DEDICATED secrets repo, never co-located with the
  bootstrap personal KB (the KB rides to every machine; ciphertext must not).
- Manifest refs for this backend look like `<file>#<key>`, e.g.
  `example.enc.yaml#/service/token`, so every value a Mac could decrypt is
  enumerable from the manifest.

### Enrollment ceremony (new Mac)

1. The new Mac generates its age keypair locally. The private key never
   leaves the Mac.
2. The owner adds the new Mac's public key as a SOPS recipient from an
   already-enrolled Mac and runs `sops updatekeys` on every encrypted file.
3. The new Mac clones the secrets repo, decrypts through the provider's
   `get(ref)`, and materializes exactly like the 1Password path (same
   permissions, backup, and doctor gates).

### Offboard / loss

1. Remove the Mac's recipient and run `sops updatekeys`.
2. Rotate every value the removed Mac could decrypt (enumerated from the
   secrets manifest) — rotation must cover value AND recipients, because old
   ciphertext in git history stays decryptable by old keys.
3. The removed Mac fails closed with "secret unavailable."

### Implementation checklist (when ruled)

- `AgeSopsBackend.get`: `sops --decrypt` the referenced file (or `sops exec`)
  and extract `<key>`; never log the value.
- `is_available`: `sops` + `age` present and the local keypair unlocks at
  least one recipient slot (probe without exposing values).
- Doctor and materialize paths are backend-agnostic already; add backend
  fixtures mirroring the `op` fakes, with fake refs only.

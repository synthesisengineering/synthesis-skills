# age/SOPS Backend — Enrollment Design (Variant 2, ruled future)

The age/SOPS backend is not implemented. `AgeSopsBackend` in
`scripts/secrets_provider.py` is a stub raising `NotImplementedError`. This
document records the enrollment design so the dual-mode seam (the
`SecretsBackend` interface plus the manifest `backend` field) can grow the
second backend without changing callers.

## Layout

- Ciphertext lives in a DEDICATED secrets repo, never co-located with the
  bootstrap personal KB (the KB rides to every machine; ciphertext must not).
- Manifest refs for this backend look like `<file>#<key>`, e.g.
  `example.enc.yaml#/service/token`, so every value a Mac could decrypt is
  enumerable from the manifest.

## Enrollment ceremony (new Mac)

1. The new Mac generates its age keypair locally. The private key never
   leaves the Mac.
2. The owner adds the new Mac's public key as a SOPS recipient from an
   already-enrolled Mac and runs `sops updatekeys` on every encrypted file.
3. The new Mac clones the secrets repo, decrypts through the provider's
   `get(ref)`, and materializes exactly like the 1Password path (same
   permissions, backup, and doctor gates).

## Offboard / loss

1. Remove the Mac's recipient and run `sops updatekeys`.
2. Rotate every value the removed Mac could decrypt (enumerated from the
   secrets manifest) — rotation must cover value AND recipients, because old
   ciphertext in git history stays decryptable by old keys.
3. The removed Mac fails closed with "secret unavailable."

## Implementation checklist (when ruled)

- `AgeSopsBackend.get`: `sops --decrypt` the referenced file (or `sops exec`)
  and extract `<key>`; never log the value.
- `is_available`: `sops` + `age` present and the local keypair unlocks at
  least one recipient slot (probe without exposing values).
- Doctor and materialize paths are backend-agnostic already; add backend
  fixtures mirroring the `op` fakes, with fake refs only.

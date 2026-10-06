# age/SOPS Backend — Enrollment Design (Variant 2, ruled future)

The age/SOPS backend is not implemented, and v5 ships no secrets scripts (the
1.0 stub went with them). This document records the enrollment design so the
manifest's `backend` field can name a second backend without changing the
manifest format or the materialize and check procedure.

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
3. The new Mac clones the secrets repo, decrypts each ref with
   `sops --decrypt`, and materializes exactly like the 1Password path (same
   permissions, backup, and check gates).

## Offboard / loss

1. Remove the Mac's recipient and run `sops updatekeys`.
2. Rotate every value the removed Mac could decrypt (enumerated from the
   secrets manifest) — rotation must cover value AND recipients, because old
   ciphertext in git history stays decryptable by old keys.
3. The removed Mac fails closed with "secret unavailable."

## Checklist (when ruled)

- Read a value: `sops --decrypt` the referenced file (or `sops exec`) and
  extract `<key>`; never log the value.
- Available means: `sops` and `age` are present and the local keypair unlocks
  at least one recipient slot (probe without exposing values).
- The materialize and check procedures in SKILL.md are backend-agnostic; any
  example uses fake refs only.

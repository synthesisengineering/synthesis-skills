# Signed portable observations

The existing `live_receipt.py` owner can issue, verify and admit a content-free
portable observation. Its `signed_receipt.py` dependency uses the maintained
OpenSSH Ed25519 SSHSIG implementation. It does not implement cryptography or
interpret a digest as a signature. `/usr/bin/ssh-keygen` must support `-Y sign`
and `-Y verify`; an unavailable or refusing helper fails closed. The helper has
a five-second deadline and a 16 KiB combined output limit. No network, SSH agent,
askpass, client configuration or key enrollment is used. Windows is unqualified.

## Exact schema and trust

The envelope has exactly six fields: `schema`, `key_id`, `payload`,
`signer_provenance_sha256`, `trust_generation`, and `signature`. Schema is
`synthesis-signed-observation/1`. OpenSSH signs canonical ASCII JSON containing
all five non-signature fields, sorted with compact separators and no non-finite
numbers. Its namespace is `synthesis-observation@synthesiswork.org`.

The payload has exactly these fields:

| Fields | Contract |
| --- | --- |
| `schema`, `event` | Same schema and `SessionStart` |
| `client` | `claude`, `codex`, `muse`, `cursor`, or `copilot` |
| `source_sha256`, `installation_sha256` | Exact source and installation generations |
| `session_id`, `event_id` | Canonical UUIDs for the observed event |
| `audience_sha256`, `challenge` | Exact recipient scope and current UUID challenge |
| `status` | `PASS`, `FAIL`, or `UNKNOWN`; signature verification never changes it |
| `observed_at`, `issued_at`, `expires_at` | Explicit UTC; observed ≤ issued ≤ now < expiry, at most 24 hours from observation |

The separately supplied local trust document has exactly `schema: 1`,
`generation` (UUID), `audience_sha256`, and `keys` (one to 32 entries). Each key
has `key_id` (SHA-256 of the Ed25519 wire key), `public_key` (exact key without
comments/options), `provenance_sha256`, `clients`, `sources`, `installations`,
`not_before`, `not_after`, and a Boolean `revoked`. Scope arrays contain one to
32 unique exact values. No wildcard, certificate, embedded-envelope key or
unrecognized signer grants trust. Observation lifetime must fit signer lifetime;
changed provenance, trust generation or revocation invalidates old observations.
A provenance hash binds the owner's enrollment evidence; it does not prove that
the evidence exists or that enrollment was authorized.

Current bindings are a separate exact seven-field object: `client`,
`source_sha256`, `installation_sha256`, `session_id`, `event_id`,
`audience_sha256`, `challenge`. The verifier must obtain them from its current
workflow, not copy them from an incoming envelope. All three input files are
bounded regular single-link files; trust and bindings require current ownership
and no group/other write permission. Inputs are rechecked at admission. The verifier binds a detached snapshot, checks
current lifetime again after OpenSSH returns, and refuses changed inputs. Owners
repeat that check after final evidence reads and before every registry creation.
Expiry or changed inputs after event creation keep the consumed record as
unresolved custody; they never permit replay or a successful admission response. The
64 KiB input bound, depth/path limits and finite helper budget are product
limits, independent of any evaluation allowance.

## Actual producer and consumer

`conformance.py signed-receipt-issue` requires `--signed-envelope` naming an
existing local schema-2 SessionStart receipt, `--signed-trust`,
`--signed-bindings`, `--signing-key`, `--source-root`, `--signing-plugin-root`,
`--signing-transcript-root`, and `--signing-expires-at`. It uses the current local
receipt transcript parser and native installation inventory owner, then rechecks
them before emitting the signed JSON to stdout. A missing/unbound transcript
produces `UNKNOWN`; conflicting or malformed transcript evidence produces
`FAIL`; a matching transcript and exact installation produce a signer-attested
`PASS`. Missing or changed installation/source evidence refuses issuance.
Only Claude, Codex and Muse have this local producer; Cursor/Copilot portable
verification does not establish native emission support. The supplied private
key must be a current-owner, single-link regular file with no group/other access.
It is never discovered from an account or copied into permanent product state.

`conformance.py signed-receipt` requires `--signed-envelope`, `--signed-trust`
and `--signed-bindings`. It is read-only unless `--signed-registry` explicitly
selects the existing local receipt registry owner. Admission stores one event
under its separate `signed-observations-v1/client/session/event.json` subtree.
Exclusive creation arbitrates concurrent admission. Re-signing or changing the
challenge cannot replay the same event. An interrupted partial record consumes
the event and requires owner reconciliation; it is never overwritten or treated
as success. Read-only verification can examine the same event repeatedly and
must not be called one-shot admission. `--local` refuses registry admission.

Signed results are a capability evidence plane. They cannot satisfy `hook-live`,
set onboarding live-load state, authenticate a disclosure reviewer, authorize an
action, or prove a client restart. Genuine native emission, signer enrollment and
live acceptance require their own observed evidence. A content-free payload
omits text, paths and credentials, but stable identifiers/hashes can still be
correlated; audience scoping is not permission to publish it.

## Source provenance

The OpenBSD [ssh-keygen manual](https://man.openbsd.org/ssh-keygen#SIGNATURES)
defines the signature namespace, allowed-signers verification and revocation
interfaces. This owner uses verification against its exact selected trusted key;
it does not use structural-only `check-novalidate`. The signature primitive was
qualified with disposable synthetic keys, including mutation, revocation,
replay, stale scope and interruption controls. No real client signer was enrolled
by those tests.

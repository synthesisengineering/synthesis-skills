# Coordination session identity

Schema v3 separates a session's identity from its claims. The canonical
identity is a full UUIDv7. Human operators get two exact aliases, while claims
remain the source-area paths attached to the session.

## Representations

| Representation | Shape | Bits | Purpose |
|---|---|---:|---|
| Canonical | `019fff79-5858-7993-a329-b301bccf5d62` | 128 | Durable machine identity, lease ownership, pointers |
| Compact | `s-6adk-06yc-yqb2` | 60 | Fast visual scanning and typing |
| Speakable v1 | `crater-sunset-alone-okay-23906` | 60 | Dictation, reading, and short-term recall |
| Legacy | `AX` | historical | Explicit lookup mapping for migrated v1/v2 boards |

Since schema v4 a row also carries a **client session ref** (for example
`ccd:local_<uuid>`), which is not an identity: it is the client-native
delivery address registered at claim time, resolvable through
`coordination.py resolve` but never a substitute for the UUID in pointers,
leases, or receipts. See the parallel-agent protocol's "Addressing a peer
session."

UUIDv7 follows RFC 9562: 48 milliseconds-of-Unix-time bits, required version
and variant fields, and 74 random bits. The alias token uses only the low 60
bits of `rand_b`; no timestamp, version, or variant bit enters either
human-facing identity.

The compact form encodes the token as 12 Crockford Base32 symbols and groups
them four at a time. Decoding accepts Crockford's case folding and the
`I`/`L`→`1`, `O`→`0` aliases; rendering uses lowercase and omits `I`, `L`, `O`,
and `U`.

The speakable v1 form splits the same token into four 11-bit word indexes and a
16-bit integer. Four indexes select entries from the fixed 2,048-entry English
list; the integer renders as `00000` through `65535`. It therefore carries the
same 60 bits as the compact form and round-trips exactly. This is an identifier
encoding, not a password, recovery phrase, or cryptographic secret.

The v1 vocabulary vendors the BIP-39 English word list because it is exactly
2,048 entries, uses lowercase ASCII, avoids similar words, and gives each word
a unique first-four-letter prefix. The exact decoded bytes are pinned to SHA-256
`2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`.
BIP-39 and its word list are MIT-licensed. Sources:

- RFC 9562, section 5.7: <https://www.rfc-editor.org/rfc/rfc9562.html#section-5.7>
- Crockford Base32: <https://www.crockford.com/base32.html>
- BIP-39 specification and license: <https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki>
- Canonical English word list: <https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt>

## Allocation and lookup

`coordination.py claim` allocates UUIDv7 plus both aliases inside the same
locked or lease-backed compare-and-swap transaction that publishes the row.
It checks every canonical and human selector for collisions and regenerates
before publication. This makes concurrent machines serialize allocation
against the accepted remote board rather than against stale local memory.

`claim`, `heartbeat`, `release`, active-project validation, SessionStart
summaries, and addressed messages accept or resolve the full UUID, compact
alias, speakable alias, or legacy mapping. New claims normally omit an ID:

```bash
python3 scripts/coordination.py claim \
  --agent "OpenAI Codex" --project example --mode interactive \
  --context-role owner --goal "Implement the checkpoint" \
  --workspace "/tmp/example @ feature/checkpoint" --area "repo/**"
```

The output returns all three current identities. Subsequent commands may use
the compact or speakable form:

```bash
python3 scripts/coordination.py heartbeat --session s-6adk-06yc-yqb2
python3 scripts/coordination.py release \
  --session crater-sunset-alone-okay-23906
```

`coordination.py migrate` upgrades the whole v1/v2 board atomically, assigns
each historical row a UUIDv7 and both aliases, and preserves its old letter in
`legacy id`. Messages and history are left intact. Once migrated, canonical
machine references use the UUID even when a human supplied a legacy selector.

## Collision boundary

The UUID remains authoritative even if a human alias collision were ever
encountered. Sixty random alias bits give about a 1-in-1.15-quintillion chance
for one specified pair; the birthday probability is roughly 4.3e-7 across one
million allocated sessions. The transactional collision check prevents a
duplicate from being published to one lease-backed board. Independent boards
may reuse a human alias without ambiguity because their lease/board scope is
part of the durable identity boundary.

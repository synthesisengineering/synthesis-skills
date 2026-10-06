# Decision packet: generate, file, record, and what a record authorizes

The commands, the filing and recording rules, the schema-2 record, provenance and action authority, and retiring a packet. Moved verbatim from the 1.8.0 SKILL.md; only link paths changed.

Contents:
- Use: the commands, filing with `--file-into`, recording with `record_rulings.py`, note whitespace, schema-2 records, idempotent imports
- Provenance and action authority: `--provenance`, `authorization.granted: false`, `--legacy-unbound`
- Retiring historical interfaces

## Use

```bash
python3 scripts/build_packet.py --schema              # the spec format
python3 scripts/build_packet.py spec.json -o packet.html --strict-reader
python3 scripts/build_packet.py spec.json --stdout    # to a pipe
python3 scripts/build_packet.py spec.json --strict-reader \
    --file-into PROJECT/resources/artifacts/         # + <date>-<slug>-spec.json, <date>-<slug>.html
python3 scripts/record_rulings.py paste.txt \
    --spec PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --file-into PROJECT/resources/artifacts/         # -> <date>-<slug>-rulings.json
```

Write a JSON spec, generate, file, hand over the file. It is self-contained: no build step, no
dependencies, no server. It opens from disk, over a local HTTP server, or published as an
artifact, in light or dark, on a phone or a laptop.

**File it, then hand it over.** `--file-into DIR` writes a dated copy of the spec and of the page
into DIR after a successful build. DIR is the owning project's `resources/artifacts/` and must
already exist: the generator refuses a missing directory rather than creating one where you did
not mean. `--date YYYY-MM-DD` sets the date in the names (default: today). Publish the page as
an artifact too if that is how the principal will open it; the filed copy is the one other
agents read.

**Record what came back.** Save the complete returned summary, including its final
binding line. Run `record_rulings.py paste.txt --spec CURRENT-SPEC --file-into DIR`.
The current spec is selected explicitly; omitting `--spec` works only when the
directory has one matching candidate. Multiple versions require an explicit choice.
The recorder refuses a changed spec, duplicate/missing/reordered rows, unknown
option values, mismatched displayed text and malformed bindings before writing.

Notes use LF line endings and omit trailing whitespace on each line, matching
common clipboard and editor behavior. Leading indentation inside the note, word
spacing and paragraph breaks remain significant. This tolerance applies only to
notes; decisions, row labels and the current-spec binding remain exact. A refused
paste names the affected row and field without repeating its note contents.

Schema-2 records retain `packet`, `ruled_on`, `decided`, `total`, and per-row
`id`, `label`, `choice_value`, `choice_label`, recommendation/bulk status and
`note`. They add the complete canonical spec SHA-256, actual filed-spec byte
digest, summary digest, claimed provenance and an explicit non-authorizing status.
Canonical bytes are UTF-8 JSON with sorted object keys, compact separators and one
final newline. Every field participates, including context, consequences and scope;
duplicate JSON keys and nonfinite numbers are refused. Whitespace in an input JSON
file does not change meaning; any change in its canonical content changes the binding.

Identical imports are idempotent. A changed response receives a distinct filename;
there is no destructive `--replace`. Preserve and commit the spec, page, original
response and recorded versions in the owning project. An explicit `--out` path also
preserves existing bytes; give a revised page a new path or use versioned filing.

## Provenance and action authority

The parser records a response; it does not authenticate a principal or authorize
an action. Every output has `authorization.granted: false` and
`authentication: unverified`, including a byte-perfect synthetic or forged paste.
This describes the tool's authority, not the validity of an existing user grant.

When the trusted conversation supplies attribution, pass `--provenance FILE` with
exactly five nonempty strings: `principal`, `source_ref`, `received_at` (an ISO
timestamp with timezone), `scope`, and `authority_ref`. The recorder preserves
these claims and the provenance-file digest as `claimed-unverified`; it cannot
verify an identity merely because a local file names one. Missing provenance stays
`unattributed-paste`, with unknown fields explicit. `ruled_on` is the supplied
record date, not proof of when the principal acted.

The existing action owner reads the authentic source and checks the principal,
current scope, exact target/payload, validity and restrictions before acting.
Put the concrete target, payload revision and decision boundary in the displayed
`scope` or row context. A technical selection or preference cannot authorize a
new deployment, disclosure, spend or other consequential effect.

Historical text remains readable with `--legacy-unbound --stdout`; historical
records remain untouched. This read does not produce a new bound filing. An old
record's lack of a schema-2 binding neither authenticates it nor erases authority
already supplied in a trusted user instruction. Resolve that authority through
its actual owner and source.

## Retiring historical interfaces

Read [artifact succession](../../synthesis-context-lifecycle/references/artifact-succession.md)
before retiring a packet or reconciling transferred decisions. `context_edit.py`
owns exact-byte custody and the existing multi-file transaction; the packet owner
refuses filing a retired exact spec or equivalent payload as a new live interface.
A rulings filename does not establish closure. Preserve actual answers and every
unanswered or unverified obligation; archive and transfer grant no new authority.

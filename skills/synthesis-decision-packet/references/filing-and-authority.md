# Decision packet: generate, file, record, carry forward, and what a record authorizes

The commands, the filing and recording rules, the schema-2 record, action authority, and carrying unanswered decisions forward when a packet is replaced. Moved from the 1.8.0 SKILL.md; the v5 script pass (M3) removed claimed provenance, input-file custody and legacy-summary parsing and added `carry_forward.py`. Every replaced line is kept in [preserved.md](preserved.md).

Contents:
- Use: the commands and what they print, filing with `--file-into`, recording with `record_rulings.py`, note whitespace, schema-2 records, idempotent imports
- Action authority: `authorization.granted: false`, summaries without a binding line
- Carrying unanswered decisions forward: `carry_forward.py --successor` and `--check`

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
python3 scripts/carry_forward.py PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --successor next-spec.json                       # the unanswered rows, ids unchanged
python3 scripts/carry_forward.py PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --check reconciliation.json                      # every id answered or carried, once
```

What they print: `build_packet.py` prints READER and NOTE findings to stderr, then the path and
size of each page or filed copy it wrote (`filed <path>`), or `will not build:` with the
reasons and exit status 2. `record_rulings.py` prints `filed <path>  (N of M decided; no
action authority granted)`, the record itself with `--stdout`, or `record_rulings: <reason>`
and exit status 2. `carry_forward.py` prints the ids it carried, or `reconciled N ids: ...`,
or `carry_forward: refused:` with one line per missing, extra, duplicate or unproven id and
exit status 2.

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
Each refusal quotes what it received (the line or value) beside what the spec
expects, so the mismatch can be found without diffing by hand.

Notes use LF line endings and omit trailing whitespace on each line, matching
common clipboard and editor behavior. Leading indentation inside the note, word
spacing and paragraph breaks remain significant. This tolerance applies only to
notes; decisions, row labels and the current-spec binding remain exact. A refused
paste names the affected row and field without repeating its note contents.

Schema-2 records retain `packet`, `ruled_on`, `decided`, `total`, and per-row
`id`, `label`, `choice_value`, `choice_label`, recommendation/bulk status and
`note`. They add the binding (`binding.spec_sha256`, the complete canonical spec
SHA-256), the filed spec's name (`spec_file`), whether the browser blocked storage
(`storage_blocked`) and an explicit non-authorizing status. A row about review
material keeps that material, its revision and delivery, and any prior position.
Canonical bytes are UTF-8 JSON with sorted object keys, compact separators and one
final newline. Every field participates, including context, consequences and scope;
duplicate JSON keys and nonfinite numbers are refused. Whitespace in an input JSON
file does not change meaning; any change in its canonical content changes the binding.

Identical imports are idempotent. A changed response receives a distinct filename;
there is no destructive `--replace`. Preserve and commit the spec, page, original
response and recorded versions in the owning project. The filed copies are the
record: `-o` writes a working copy and overwrites it on the next build, while
`--file-into` never replaces a filed file (a revision gets a digest suffix).

## Action authority

The parser records a response; it does not authenticate a principal or authorize
an action. Every output has `authorization.granted: false` and
`authentication: unverified`, including a byte-perfect synthetic or forged paste.
This describes the tool's authority, not the validity of an existing user grant.
The record does not say who pasted it or when; where that matters, the session
names the source in the project's own record. `ruled_on` is the supplied
record date, not proof of when the principal acted.

The existing action owner reads the authentic source and checks the principal,
current scope, exact target/payload, validity and restrictions before acting.
Put the concrete target, payload revision and decision boundary in the displayed
`scope` or row context. A technical selection or preference cannot authorize a
new deployment, disclosure, spend or other consequential effect.

A summary without the final binding line (from a packet built before the line
existed, or a paste cut short) cannot become a record; read it as text and
rebuild the packet from its spec to collect fresh rulings. An old
record's lack of a schema-2 binding neither authenticates it nor erases authority
already supplied in a trusted user instruction. Resolve that authority through
its actual owner and source.

## Carrying unanswered decisions forward

When a packet is replaced (a revised spec, a follow-up sitting, work moving to another
project), every decision the principal has not answered carries forward by its exact id.
The spec's ids, not labels, counts or a narrative total, define what must arrive.

- `carry_forward.py SPEC --successor NEXT.json [--title T]` writes a spec holding exactly the
  unanswered rows, ids and content unchanged, with `carried_from` naming SPEC. Build and file
  it with `build_packet.py` like any packet (`--allow-small` when fewer than five remain). It
  never overwrites an existing file, and when every row has a recorded ruling it writes
  nothing and says so.
- `carry_forward.py SPEC --check RECONCILIATION.json` verifies a declared accounting:
  `{"items": [{"id": ..., "status": "answered", "ruling": FILE}, {"id": ..., "status":
  "carried", "to": DESTINATION}]}`, paths relative to SPEC's folder. Every id of SPEC appears
  exactly once; missing, extra and duplicate ids are refused. A destination that is a spec
  file must hold a row with the same id.
- **Only a recorded ruling answers a decision:** a rulings file `record_rulings.py` wrote
  against this exact spec (same digest, rows and options) with a choice for that id. A
  narrative source that calls an item answered (meeting notes, a chat message, a context
  file) closes nothing; carry the item forward until its ruling is recorded. By default the
  script counts the `*-rulings.json` beside SPEC that bind to it; `--rulings FILE...` names
  them, and a named file that does not bind to SPEC is refused.

A rulings filename does not establish closure. Preserve actual answers and every
unanswered or unverified obligation; archive and transfer grant no new authority.
The check accounts for decisions only: it does not establish that any chosen work
happened, and it authorizes nothing.

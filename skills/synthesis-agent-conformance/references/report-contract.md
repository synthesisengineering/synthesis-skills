# Shared conformance report contract

The existing conformance producer and Console consumer use
`conformance-report-v1.schema.json` byte for byte. Schema version 1 names five
planes: source, installed, native, continuity, capability. The CLI's internal
historical live label is serialized as native. Unknown schemas, fields, planes,
duplicate check names or JSON keys, contradictory statuses and aggregates are
refused. JSON numeric fields use integer syntax; fractional or exponent forms
are not accepted. Reports are limited to 4 MiB in the actual producer encoding (two-space JSON
indentation, ASCII escaping, and a final newline) and 4,096 checks; a detail has at
most 16,384 characters. Refusal is visible and never produces acceptance.

PASS means all required checks in the named command scope passed. A partial
source audit does not certify another plane. An `all` report with an unobserved
plane is UNKNOWN. An `all` PASS requires required PASS evidence in every plane;
WARN or UNSUPPORTED alone cannot fill an unverified plane. Required failure is FAIL; missing required evidence is UNKNOWN;
optional warning or unsupported capability never supplies required success.

## Identity and freshness

The identity binds canonical source root, exact producer bytes, selected project
and repository, public/private profile, and a digest of the local hostname plus
canonical home. The source binding hashes five exact files in stable order:
both plugin manifests, the conformance producer, report-contract implementation
and schema. It does **not** assert a whole-tree audit or cryptographic signer.
This is a local unsigned evidence cache; authenticity and release authority remain
with the existing release and receipt owners.

A report expires exactly four hours after its UTC check time. Console rejects
expired evidence, a check more than five seconds in the future, or changed
machine, source, project or profile identity. A newly invoked audit must also
produce a new check time within its invocation window. Files are read with
single-link regular-file, byte, descriptor/path and ancestor checks; symbolic
links, special files and replacement races refuse. Installed bytes do not prove
a client loaded them or approved hooks. A native or capability PASS still needs
its existing actual evidence owner.

## Runtime and interface integration

The installed launcher's activation receipt includes the contract module and
schema. The modular support payload includes these same files without activating
new hooks. Console bundles the identical schema and tests actual Python-produced
reports against its TypeScript validator; any schema-byte mismatch refuses.
The report panel renders all five planes, the scope and status in text, semantic
table headings, and a plain-language evidence/trust boundary. Its audit control
remains focusable while busy and announces progress through a polite live region.
No report or accessibility fixture authorizes a service, migration or provider call.

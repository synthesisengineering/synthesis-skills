# Format versioning and the reader promise

This file states the interoperability promise once. It is addressed to
readers outside Rajiv's own products; it is never cited as a pro of any
internal change.

## R10: older format versions are conformant targets forever

Readers accept every older `format_version` forever. A reader never
requires the newest version: v1 projects remain fully readable without
migrating, and new classes appear on first use with no backfill.

## Downgrade

Downgrade is deletion of added files: move `archive/*` back, then delete
the files the migration marker names, and the v1 view is restored
byte-for-byte. Additions within a major are optional files and keys only,
so there is nothing else to remove.

## What this promise does not do

- It does not keep deprecated writers alive. Deprecations follow their
  windows; only the reader side is forever.
- It does not freeze the spec. The spec stays 0.x until its known-defect
  markers land; no golden fixture encodes a known defect.
- It does not argue for backward compatibility inside Rajiv's own
  products. That remains a non-goal; this promise exists because
  third-party readers cannot migrate on our schedule.

Basis: strategy rev 4 ruling S17 (2026-09-20), strategy §8.5/§10.

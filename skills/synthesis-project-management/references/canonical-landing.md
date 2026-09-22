# Canonical Checkout Landing

`scripts/canonical_landing.py` observes one literal `git push REMOTE
SOURCE:main` and fast-forwards the canonical checkout to the verified
remote commit — behind the explicit-push trigger only. Dynamic,
grouped, multi-ref, nested, and script-internal pushes are never
landed; neither are pushes with force, dry-run, deletion, or mirror
flags. Shell parsing comes from sibling
`scripts/publication_command.py`.

Entry points: `capture_before` records the pre-tool source at the
push boundary; `process_after` makes one bounded landing attempt
per call. Receipts distinguish observed remote state (`observed`,
`remote_published`), canonical state (`canonical`), and claim
cleanup (`claim_cleanup`).

Landing admits a board claim on the incoming paths, then re-verifies
checkout identity, cleanliness, remote stability, and claim authority
before the fast-forward, and restores only its own authority
afterward. It refuses: foreign same-checkout use, unclean or
diverged canonicals, non-main checkouts, in-progress Git operations,
submodules, unbounded checkout effects (filters, fsmonitor, hooks),
and contributor seats landing canonical context. A refused landing
is a maintenance finding in the receipt, never a partial write.

# Detection rules and private-key material

The credential boundary distinguishes an exact rule literal from key material.
It never exempts a file, path, repository class or every quoted string.

## Supported rule syntax

The configured exact bare strings for RSA, OpenSSH, EC, PGP, generic and encrypted
private keys are typed only within `tier_0_always.private_key_markers`. Arbitrary
regular expressions, entries in other groups, overlapping custom expressions and
team-mandatory expressions retain ordinary matching semantics.

For staged content, a YAML document must parse completely with the existing
strict config grammar. A complete `private_key_markers` sequence at document root,
or directly inside `tier_0_always`, must contain only exact supported bare-marker
scalars. Mixed body values, aliases, malformed syntax and unsupported nesting do
not establish a rule. A Python data-only module may contain raw-string
`private_key_marker` assignments with those exact values. Expressions, function
calls, concatenated material and arbitrary quotes are insufficient. Unknown
syntax keeps the conservative marker refusal; it does not become an exemption.

Other credential expressions scan all added bytes before rule classification.
The rest of the file and diff remain in the scan, so a valid rule cannot hide a
second credential, key block, or custom-policy finding. Tier-1 and mandatory-team
policy remain distinct. Optional commit-message settings affect exposure checks;
credentials remain mandatory even for a personal repository.

## Staged context and finite failure

The scanner captures index object IDs before acquiring the diff, reads changed
blobs by their immutable object IDs, verifies each blob hash and every added-line
binding, then checks the index again. Working-tree text cannot substitute for
staged bytes. Each changed file is inspected for key regions, including an old
header above a new body. Full, incomplete, header-only, indented and quoted or
ASCII-escaped material refuse without requiring cryptographic validity. A bare
END phrase is not an armored footer. A closed old block does not make unrelated
new lines sensitive.

One scan has a 60-second deadline, 256 MiB Git acquisition bound, and a cumulative
32 MiB / 1,024-file marker-context bound. Exceeded limits, missing objects, changed
index/blob/parser source, unsupported index modes and malformed evidence refuse.
The policy grammar is captured from the existing sibling `_load_config.py` as
bounded regular-file bytes, checked for identity changes and compiled directly;
a cached `.pyc` does not replace it. No extra installed module or global cache is
introduced. The loader, scanner and both shell consumers ship together, and the
existing installer/doctor covers that dependency closure.

## Explicit vocabulary ownership

The public template seeds only absent configuration. It lists generic and
encrypted PKCS#8 signatures in addition to RSA, OpenSSH, EC and PGP (whose armored
form includes `PRIVATE KEY BLOCK`). Existing settings are not silently rewritten.
A source-managed policy receives a separately reviewed marker-only source delta,
then its existing backed-up deployment owner applies it. Updating the engine or
template alone does not claim that an existing user policy has the new signatures.

## Verification boundary

Use actual staged Git and commit-message consumers with synthetic unusable key
bodies. Keep rule-positive cases, material/token refusals, unchanged-header/body,
custom-pattern overlap, index/worktree divergence, changed-source, parser custody,
footer, bounds and performance controls. Preserve original failures and fixture
hashes. Deterministic source tests do not establish installation, policy deployment,
real-account health or authority for a peer's next commit.

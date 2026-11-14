# Inbox cleanup: release notes, license and author

The version notes from 1.4.0 to 1.6.2, the license and the author line, moved verbatim from the 1.6.2 SKILL.md. The 1.6.0 note documents the impersonation scanner and the catch-all routing rule.

Contents:
- v2.0.0: v5 (the engine's stable path, the slim installer, the principal impersonation rule)
- v1.6.2: cross-platform runtime pointer replacement
- v1.6.0: impersonation scanning, and why a passing domain check is not a safety verdict
- v1.5.0: workspace scoping
- v1.4.0: the stable cross-client engine runtime
- License, Author

## v2.0.0 — v5: one stable engine path, and the principal rule

The engine is no longer copied into `~/.synthesis/inbox-cleanup/engine/`. The v5
runtime installs it at `~/.synthesis/v5/current/skills/synthesis-inbox-cleanup/scripts`,
which survives client plugin updates, so `scripts/install.sh` now only seeds the
private config and rules and reports what is missing (including a leftover 1.x
engine copy, which it never deletes). The pointer-replacement machinery of 1.4.0
to 1.6.2 left with the copy.

`scan_impersonation.py` gains the principal rule (IR-19, carried from the
unshipped 4.154.13 candidate): a display name equal to the account owner's name
or an alias, sent from any address not listed exactly, is flagged high. The
private `impersonation.yaml` must declare `principal.names` and
`principal.addresses` (shape in `templates/impersonation.example.yaml`);
without them the scan refuses (exit 2) before reading mail, because a scan that
silently lacks the rule looks clean. Address matching normalizes ASCII case and
IDNA domains without stripping plus tags or dots; name matching uses NFKC, case
folding, format-control removal and collapsed whitespace. A sender group that
claims the principal's name is flagged even when empty or listed, and encoded
names are parsed before display decoding so punctuation cannot change the
sender structure. `--check-config` validates the file without touching mail.
An allowed From address is not proof of authentication or safety.

## v1.6.2 — Cross-platform runtime pointer replacement

The runtime installer replaces its staged `engine/current` symlink with
Python's atomic `os.replace`. The previous repair used BSD `mv -h`, which works
on macOS but fails under GNU `mv` before the pointer can move. The regression
fixture now models that GNU refusal on every host while preserving the original
two-install, differing-digest acceptance path.

## v1.6.0 — Impersonation scanning: the taxonomy had no cell for *hostile*

`scripts/scan_impersonation.py` (read-only) adds the adversarial pass the
disposition taxonomy structurally lacked. Every existing class sorts mail by
DESIRABILITY — marketing, newsletter, transactional, keep — so a phishing message
is not merely misfiled by this engine, it is **invisible to it**: a sweep that only
files things tidily walks straight past an attack.

The detection is the one that catches live campaigns: **the sending domain is
authenticated; the display name is not.** SPF/DKIM/DMARC validate the envelope
domain and say nothing about the free-text name the mail client actually shows.
So the high-yield phish forges no domain at all — it sends through infrastructure
that passes every check (a survey platform, a form host) and puts the impersonated
brand in the display name. "The domain checks out" is therefore not a safety verdict.

Reports only; removal stays a human-reviewed step, because a false positive here is
a legitimate vendor notice. Brand→domain map in
`~/.synthesis/inbox-cleanup/impersonation.yaml`, seeded in-script.

**Also recorded here as a standing rule: a human sender is not the same as your
mail.** On a catch-all domain, misdirected business threads between real people
are still junk for the account owner. Route recipient-based purges by the `To:`
header (the private alias-purge path), not by whether a person wrote it.

## v1.5.0 — Workspace scoping: cleanup reach follows the seat that invokes it

New `scripts/resolve_scope.py` + `~/.synthesis/inbox-cleanup/scopes.yaml`
contract (see "Workspace scoping" below): a personal operations seat sweeps
every account; a client-workspace seat sweeps only its own. Unknown workspaces
are unverifiable (exit 2), never an empty sweep. Subprocess-tested.

## v1.4.0 — Stable cross-client engine runtime

v1.4.0 (2026-07-30) installs an immutable engine release under
`~/.synthesis/inbox-cleanup/engine/releases/` and atomically points
`engine/current` at it. Operational scripts use that stable path instead of a
Claude Code or Codex plugin cache. Updating either client can no longer remove
the engine path used by private workflows.

## License

Apache-2.0. The engine and scripts may be used, modified, and redistributed under the terms of `LICENSE-APACHE` at the root of the synthesis-skills repository.

## Author

[Rajiv Pant](https://rajiv.com). This skill packages the methodology that cleaned 10,000+ messages across 8 accounts and 3 tool stacks in production use.

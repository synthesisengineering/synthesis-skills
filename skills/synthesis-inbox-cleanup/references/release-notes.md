# Inbox cleanup: release notes, license and author

The version notes from 1.4.0 to 1.6.2, the license and the author line, moved verbatim from the 1.6.2 SKILL.md. The 1.6.0 note documents the impersonation scanner and the catch-all routing rule.

Contents:
- v1.6.2: cross-platform runtime pointer replacement
- v1.6.0: impersonation scanning, and why a passing domain check is not a safety verdict
- v1.5.0: workspace scoping
- v1.4.0: the stable cross-client engine runtime
- License, Author

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

# Inbox cleanup: architecture, workspace scoping and setup

Moved verbatim from the 1.6.2 SKILL.md; only link paths changed.

Contents:
- Architecture: public engine, private rules, and what lives under ~/.synthesis/inbox-cleanup/
- Workspace scoping: the scopes.yaml contract, resolve_scope.py and its exit codes
- Setup: install the plugin, run the installer, configure accounts and rules, store the IMAP password, sanity-check

## Architecture: public engine, private rules

```
<synthesis-inbox-cleanup-root>/             ← public (this skill)
  ├── SKILL.md                             ← methodology + rules
  ├── scripts/                             ← Python + AppleScript engine
  ├── templates/                           ← starter manifests
  ├── references/                          ← deeper docs
  └── tests/poisoned/                      ← adversarial fixtures

~/.synthesis/inbox-cleanup/                 ← private (per-user, not in git)
  ├── engine/
  │   ├── current → releases/<digest>/     ← stable client-neutral runtime
  │   └── releases/<digest>/               ← immutable verified engine
  ├── config.yaml                          ← account list, host, user candidates
  ├── rules.yaml                           ← sender rules, never_touch, subject_rules
  └── imap.secret                          ← optional credential fallback
```

The engine reads its rules from `~/.synthesis/inbox-cleanup/rules.yaml`. The contents of that file — which senders to trash, which domains to never touch, which family-domain subject keywords to spare — is private user data. It never reaches the public repo. The engine is generic; the rules are yours.

## Workspace scoping — inbox cleanup as a chief-of-staff duty (v1.5.0)

One person, many mailboxes, several working contexts. The morning ritual of a
**personal operations seat** should sweep every account the person owns; the
ritual of a **client-workspace seat** should touch only that workspace's
accounts — a client engagement's session has no business reading personal
mail, and the boundary should be mechanical, not remembered.

The contract lives in `~/.synthesis/inbox-cleanup/scopes.yaml`:

```yaml
version: 1
all_scope_workspaces: [personal]        # seats whose default is EVERYTHING
accounts:
  - address: you@example.com
    workspace: personal
    stack: icloud-imap
  - address: you@work.example.com
    workspace: acme
    stack: gmail
```

Resolution is by `scripts/resolve_scope.py --workspace <name>` (add `--json`
for rituals): an all-scope workspace resolves to every account; any other
workspace resolves to its own accounts only; `--all` overrides explicitly.
The caller **states its workspace** — rituals know where they run, and an
explicit argument beats environment sniffing that guesses wrong silently.

Guard contract: exit 0 resolved, 1 config defects, 2 unverifiable — and an
**unknown workspace is exit 2, never an empty list**, because a cleanup run
that resolves to zero accounts by typo must not look like a clean sweep.

Sweep results are reported per account against the resolved scope ("7 of 9
accounts in scope, 7 swept; 2 out of scope for this workspace"), so a partial
sweep is always distinguishable from a complete one.

## Setup

```bash
# 1. Install the native plugin in the client you use
codex plugin marketplace add synthesisengineering/synthesis-skills
codex plugin add synthesis-skills@synthesis-engineering

# Claude Code equivalent
claude plugin marketplace add synthesisengineering/synthesis-skills
claude plugin install synthesis-skills@synthesis-engineering

# 2. Run the installer — creates ~/.synthesis/inbox-cleanup/ with seed config + rules
<synthesis-inbox-cleanup-root>/scripts/install.sh

# 3. Edit ~/.synthesis/inbox-cleanup/config.yaml — add your account(s)
# 4. Edit ~/.synthesis/inbox-cleanup/rules.yaml — start with the never_touch list

# 5. Store the IMAP app-specific password in the macOS Keychain
security add-generic-password -s inbox-cleanup-imap -a "$USER" -w
# (paste the password when prompted; never in shell history)

# 6. Sanity-check from the stable runtime
cd ~/.synthesis/inbox-cleanup/engine/current
python3 icloud_census.py
```

For Gmail and M365 setup details, see [`references/three-tool-stacks.md`](three-tool-stacks.md).

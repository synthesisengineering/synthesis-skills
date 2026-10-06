# Inbox cleanup: preserved text

Lines replaced on 2026-10-05 when the engine moved to the v5 stable path and
`scripts/install.sh` was slimmed (v5 code verdict: SLIM, "the v5 plugin install
gives a stable path"). Each is verbatim from references/setup-and-scoping.md,
which had moved it verbatim from the 1.6.2 SKILL.md; the replacement sits at the
same place in that file.

## Architecture tree, the private folder

```
~/.synthesis/inbox-cleanup/                 ← private (per-user, not in git)
  ├── engine/
  │   ├── current → releases/<digest>/     ← stable client-neutral runtime
  │   └── releases/<digest>/               ← immutable verified engine
  ├── config.yaml                          ← account list, host, user candidates
  ├── rules.yaml                           ← sender rules, never_touch, subject_rules
  └── imap.secret                          ← optional credential fallback
```

## Setup, step 6

```bash
# 6. Sanity-check from the stable runtime
cd ~/.synthesis/inbox-cleanup/engine/current
python3 icloud_census.py
```

## The 1.6.2 installer's contract, from its header

Idempotent. Run multiple times safely. Creates ~/.synthesis/inbox-cleanup/,
installs an immutable engine release behind a stable `engine/current`
symlink, seeds config.yaml and rules.yaml from the bundled templates (only
if no existing files — does not overwrite), and prints next-step
instructions.

Why the engine copy existed, and why it is gone: plugin caches are versioned
and client-owned, so a private workflow that imported the engine from one broke
when a client update removed the folder (v1.4.0, 2026-07-30). The copy solved
that with digest-verified releases and an atomic pointer, and two pointer bugs
followed: BSD `mv` deposited the staged pointer inside the old release (seen in
production 2026-08-24, a stale runtime missing `resolve_scope.py`), and the
`mv -h` repair failed under GNU `mv` (1.6.2). v5 installs one runtime at
`~/.synthesis/v5/current` for every part of the plugin that runs outside a
session, so the inbox engine needs no copy of its own and the pointer bugs
cannot recur.

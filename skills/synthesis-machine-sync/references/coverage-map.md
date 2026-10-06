# Coverage map: synthesis-machine-sync 1.0.0 to 2.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in [preserved.md](preserved.md)
with the reason.

## Coverage check results

Run on 2026-10-05 from the v5 worktree against `origin/main`:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-machine-sync
synthesis-machine-sync: 123 old lines, 0 not found verbatim
```

The 1.0.0 SKILL.md is in [preserved.md](preserved.md) word for word.

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-machine-sync
description: "Enroll, sync, hand off, and retire Macs in a personal fleet with git plus the leased coordination board. Use when asked to: machine sync, enroll a Mac, fleet handoff, move work to another Mac, resume on another Mac, fleet doctor, bootstrap a new Mac, retire a Mac, workspace subscriptions."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

v5 changes: the description keeps move work to another Mac, resume on another Mac, machine sync,
bootstrap a new Mac, enroll a Mac and retire a Mac, and drops fleet handoff, fleet doctor and
workspace subscriptions with the machinery; `depends_on` names synthesis-mac-sync and
synthesis-daily-rituals; version 2.0.0; `format: v5`.

## SKILL.md sections

| 1.0.0 section | v5 home | How |
|---|---|---|
| Purpose (one system, git plus the board, no file replication in write paths) | Purpose paragraph | Reworded: git and the sync folder are the transports; the board is per Mac |
| Non-negotiables: machine-id, single primary, board row identity | [preserved.md](preserved.md) | Retired (CUT, REPLACE) |
| Non-negotiables: secrets never in synced files, board messages or receipts | Binding rule 5 | Kept; the provider is retired (never used) |
| Non-negotiables: resume is harness-neutral | Binding rule 4 | Kept |
| Enroll a new Mac (clean install only; one command; joins, narrates, resumes) | Binding rules 1 and 7; Procedure "A new Mac" | Kept as the setup script; enrollment and receipts retired |
| Enroll: robustness list (labels, relabel, concurrent enrollments, mint races, role contradictions) | [preserved.md](preserved.md) | Retired with machine identities; interrupted clones and reruns kept in Procedure step 1 |
| Sync: board mirror through the lease | [preserved.md](preserved.md) | Retired (board per Mac) |
| Sync: pull subscribed repos; divergence scan | Procedure "Arrive", step 2 | Kept (`repo_state.py --discover --fetch --ff`) |
| Sync: `~`-rooted synced configs | Binding rule 6 | Kept |
| Never copy `~/.synthesis` subtrees, seats, spools or transcript caches | Binding rule 1 | Kept |
| Handoff: work moves, processes do not | Purpose paragraph | Kept |
| Handoff source: quiesce (nothing dirty, unpushed or unpulled) | Binding rule 2; Procedure "Leave" | Kept with `synthesis handoff` and the strand scan |
| Handoff source: offer, park, seal | [preserved.md](preserved.md) | Retired (SLIM verdict) |
| Handoff destination: pull, verify, refuse dirty with the file list, claim, resume checklist | Binding rule 3; Procedure "Arrive" | Kept: board truth, code truth, context truth (`synthesis brief`), claim truth (`synthesis claim`); the resume receipt retired |
| Leave (retire a Mac), steps 1 to 4 | Procedure "Retire a Mac" | Kept, minus machine identities |
| Workspace subscriptions | [preserved.md](preserved.md) | Retired (CUT, never enabled) |
| Doctor (`coordination.py fleet-doctor`) | `synthesis doctor`; the strand scan | Replaced |
| Engine map | [preserved.md](preserved.md) | Retired; each engine's verdict listed |

## Scripts and tests

machine-sync had no scripts of its own; its engines lived in synthesis-project-management
(`fleet_*.py`, owned by that skill's rewrite). The behaviors it keeps are tested where they now
live: the strand scan and arrive-without-overwriting in synthesis-daily-rituals
(`tests/test_repo_state.py`), handoff in the core (`tests/test_handoff.py`), resume warnings in
the core (`tests/test_resume.py`).

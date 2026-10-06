# Coverage map: synthesis-mac-sync 2.1.0 to 3.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in [preserved.md](preserved.md)
with the reason. "Verbatim" means the old lines appear unchanged in the named file.

## Coverage check results

Run on 2026-10-05 from the v5 worktree against `origin/main`:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-mac-sync
synthesis-mac-sync: 601 old lines, 0 not found verbatim
```

Every old line is in a v5 file; the reworded ones are also in [preserved.md](preserved.md) word
for word.

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-mac-sync
description: "Multi-Mac configuration sync via iCloud with bidirectional config file sync, git repository sync, machine inventory, and one-time action system. Use when asked to: mac sync, sync config, sync repos, sync with GitHub, push config to iCloud, pull config from iCloud, run mac-sync, repo status."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

v5 changes: the description keeps the triggers (mac sync, run my mac-sync, sync config, push or
pull config to iCloud, sync repos, repo status) and adds leaving this Mac; `depends_on` names
synthesis-daily-rituals (its `repo_state.py` is the strand scan; synthesis-machine-sync, which
shares the leave and arrive steps, depends on this skill rather than the other way round, so
there is no cycle); version 3.0.0; `format: v5`.

## SKILL.md sections

| 2.1.0 section | v5 home | How |
|---|---|---|
| Title and opening paragraphs (protocol versus config file) | SKILL.md purpose paragraph | Reworded |
| Configuration table | [icloud-config-sync.md](icloud-config-sync.md) | Verbatim |
| Architecture | [icloud-config-sync.md](icloud-config-sync.md) | Verbatim |
| Agent configuration ownership | [icloud-config-sync.md](icloud-config-sync.md); Binding rule 7 | Verbatim except `synthesis doctor` replaces conformance |
| Setup 1 to 3 | [icloud-config-sync.md](icloud-config-sync.md) | Verbatim |
| New-machine bootstrap — protection layer first | [machines-and-symlinks.md](machines-and-symlinks.md) | Steps rewritten for `setup.py` and `synthesis doctor`; ordering rationale verbatim |
| Sync Modes: Full, Config-Only, Git-Only | SKILL.md Procedure | Reworded |
| Push Policy (v1.3.0) | [repo-sync.md](repo-sync.md); Binding rule 5 | Verbatim |
| Local session end and remote handoff; Remote-handoff mode; source-machine gate | [leaving-and-arriving.md](leaving-and-arriving.md) | Rewritten for `synthesis handoff` (retired text in [preserved.md](preserved.md)) |
| Performance: config sync in one bash call | [icloud-config-sync.md](icloud-config-sync.md); Binding rule 8 | Verbatim (one comment line names `synthesis doctor`) |
| Performance: Codex configuration overlay | [icloud-config-sync.md](icloud-config-sync.md) | Verbatim except `synthesis doctor` |
| Performance: git repo sync in two or three calls | [repo-sync.md](repo-sync.md) | Verbatim |
| iCloud Propagation Verification (all subsections) | [icloud-config-sync.md](icloud-config-sync.md); Binding rule 2 | Verbatim except cross-Mac handoff steps 1 and 3 |
| Config File Sync Protocol (bidirectional, pull, push, templates, safety rules 1 to 7) | [icloud-config-sync.md](icloud-config-sync.md); Binding rules 1, 2, 9 | Verbatim |
| Per-Workspace Repo Manifests (v1.6.0) | [repo-sync.md](repo-sync.md); Binding rule 6 | Verbatim except the consumers line |
| Git Repository Sync Protocol (discovery, per-repo procedure, safety rules 1 to 12) | [repo-sync.md](repo-sync.md); Binding rules 3, 4 | Verbatim except safety rule 3 |
| Git Remote Sync Protocol | [repo-sync.md](repo-sync.md) | Verbatim |
| Manifest Merge Protocol | [repo-sync.md](repo-sync.md); Binding rule 6 | Verbatim |
| Automation Policy | [repo-sync.md](repo-sync.md) | Verbatim |
| Machine Inventory | [machines-and-symlinks.md](machines-and-symlinks.md) | Verbatim |
| One-Time Actions | [machines-and-symlinks.md](machines-and-symlinks.md); Procedure step 6 | Verbatim |
| Workspace Config Symlinks (v1.4.0) | [machines-and-symlinks.md](machines-and-symlinks.md); Procedure step 4 | Verbatim |
| Summary Format | [repo-sync.md](repo-sync.md); Procedure | Verbatim |
| Config File Format | [icloud-config-sync.md](icloud-config-sync.md) (sync manifests), [repo-sync.md](repo-sync.md) (git-repos.yaml), [machines-and-symlinks.md](machines-and-symlinks.md) (inventory, one-time actions) | Verbatim |
| Adding New Files to Sync | [icloud-config-sync.md](icloud-config-sync.md) | Verbatim |

## Scripts and tests

mac-sync had no scripts and no tests, and gains none. The repository strand scan it uses is
synthesis-daily-rituals' `repo_state.py --discover` (tested there: `test_discover_finds_every_repo_and_reports_a_detached_head`,
`test_uncommitted_changes_are_listed_and_never_pulled_over`). The handoff edge cases (claims
only, foreign staged files left staged, no `--no-verify`, fast-forward only, index locks left
alone, NUL-separated paths) belong to `synthesis handoff` and its core tests.

## One word changed for the public-repo scanner

Commit-message rule 5 (in repo-sync.md and in preserved.md) said history "can leak" a word this public repository's disclosure scanner refuses; it now says "private information", the same meaning and strength.

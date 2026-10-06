---
name: synthesis-onboarding
description: "Install synthesis on a Mac for Claude Code, Codex and Muse, bring a workspace's repositories onto a new Mac from repos.yaml, enroll an organization's config, update or uninstall, then verify with synthesis doctor. Use to onboard, install, set up, update, repair or diagnose synthesis."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "3.0.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Onboarding

One script, `scripts/setup.py`, sets synthesis up on a Mac: the plugin in each harness
with that harness's own commands, Codex's settings, the stable runtime, and optionally a
workspace's repositories or an organization's configuration. `synthesis doctor` then
proves each part.

## Binding rules

1. **The native plugin, installed with each harness's own commands, is the only install path.** Never copy skills into a harness cache; the private layer installs on top without editing public files.
2. **Every step is safe to rerun.** Finished work is reported, not redone; an interrupted run resumes when run again.
3. **Never overwrite what a person wrote.** A workspace `AGENTS.md`/`CLAUDE.md` setup did not create, an edited skill copy, a checkout with local work or another origin: keep it and name it. Replacing instructions needs `--adopt-workspace-instructions`, which archives first.
4. **Touch only the config keys setup owns, after a backup.** An explicit Codex `hooks = false` stays, with a warning that no guard runs there.
5. **Hook trust belongs to the person.** Never approve Codex `/hooks` or Muse hooks; say what is waiting.
6. **Organization repositories are data only.** No code from them runs; unknown manifest keys fail; only HTTPS or SSH URLs without credentials.
7. **Ask through the terminal, even under `curl | sh`.** With no terminal, name the flag to pass instead of waiting.
8. **Installed is not loaded.** Finish with `synthesis doctor` and tell the person to restart each harness.
9. **What a colleague sees carries no private path or name.**

## Contents

- **Procedure** (below): new install, new Mac, organization member, update, uninstall.
- [references/harness-install.md](references/harness-install.md): each harness's commands and edge cases, Codex settings, runtime, commit check, first config, hook trust, uninstall. Read before installing or when a harness line fails.
- [references/new-mac.md](references/new-mac.md): cloning a workspace from `repos.yaml`, what is skipped and why, workspace instructions, the 2026-09-20 lesson. Read when bringing a workspace onto a Mac.
- [references/org-manifest.md](references/org-manifest.md): the schema-2 manifest, migration from schema 1, checking a manifest, enrollment, repository and instruction rules. Read for any organization.
- [references/kernel.example.md](references/kernel.example.md): the public instruction baseline setup writes first into an organization workspace's `AGENTS.md`. Read when changing it.
- [references/first-useful-task.md](references/first-useful-task.md): helping a new user get one useful result after install. Read after a first install.
- [references/coverage-map.md](references/coverage-map.md): where every section of 2.10.4 went (ruling D8).
- [references/preserved.md](references/preserved.md), [references/preserved-org-manifest.md](references/preserved-org-manifest.md), [references/preserved-kernel.md](references/preserved-kernel.md), [references/preserved-declared-maintenance.md](references/preserved-declared-maintenance.md), [references/preserved-first-run-journeys.md](references/preserved-first-run-journeys.md), [references/preserved-message-guard-onboarding.md](references/preserved-message-guard-onboarding.md), [references/preserved-modular-lifecycle.md](references/preserved-modular-lifecycle.md), [references/preserved-platform-ownership.md](references/preserved-platform-ownership.md), [references/preserved-web-distribution-contract.md](references/preserved-web-distribution-contract.md): the 2.10.4 text verbatim. Read only to review what was cut.

## Procedure

Get the source once, to a durable place (never a temporary folder):

```bash
git clone --branch stable https://github.com/synthesisengineering/synthesis-skills.git ~/.synthesis/v5/source
S=~/.synthesis/v5/source/skills/synthesis-onboarding/scripts/setup.py
```

### New install

`python3 "$S"` installs the plugin in every harness found, sets Codex's keys, installs
the runtime, asks about the commit check (`--git-hooks`) and a first config, and offers
to bring a workspace. `--day-end [auto|codex|claude]` also links the day-end launcher and
schedules the weekday nudge. Read each line: `<harness>: installed …`, `… not found; skipped`,
`codex config: …`, `synthesis runtime <hash> at …`, then the restart sentence. Then run
`synthesis doctor` and relay anything waiting for the person's hook approval. A person
with no knowledge repository yet starts one with `python3 "$S" workspace --new NAME`
(add `--kb URL` for its remote); it needs a git identity and commits only the seeds it
wrote. For a newcomer, follow with [first-useful-task.md](references/first-useful-task.md).

### New Mac for an existing user

`python3 "$S" workspace` (or `--kb URL --workspace NAME`). It finds the knowledge
repository through `gh`, clones it and every repository in its `.agents/repos.yaml`,
and prints `[i/N] repo: cloned | updated | current | skipped: <reason>`. Rerun the same
command after any interruption.

### Organization member

`python3 "$S" --org-repo URL` for a new install (clients and release come from the
manifest), or `python3 "$S" org --org-repo URL` on an existing one. Add
`--personal-source PATH` for a private instruction layer. A repository line marked
`needs action` shows the organization's sign-in help; fix access and rerun.

### Update

Rerun `onboard.sh` with `plugin`:
`curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- plugin`
(`| SYNTHESIS_REF=vX.Y.Z sh -s -- plugin` takes another source ref). It fetches the release
into `~/.synthesis/v5/source` and leaves that checkout detached, so `git pull` there fails;
rerunning `onboard.sh` is the update. An install following a channel keeps it; `--ref vX.Y.Z`
pins one. `synthesis doctor --latest` says whether a newer release exists.

### Uninstall

`python3 "$S" uninstall --dry-run` shows what would go; without `--dry-run` it removes
the plugin from each harness, restores `core.hooksPath`, removes unedited runtime files,
and keeps config and the board.

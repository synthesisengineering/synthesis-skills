# Source update protocol (NON-NEGOTIABLE)

## Contents

- [In v5](#in-v5)
- [The protocol (verbatim from 2.9.3)](#the-protocol-verbatim-from-293): the sequence, what you must not do, and why (the 2026-04-29 incident)

## In v5

The rule is unchanged: source is the only edit point, push happens before install, the
canonical installer runs, and a verify step proves the installed copy equals source.
Two mechanics changed:

- **Public skills** ship as the `synthesis-skills` plugin. Steps 6 and 7 below are
  `release.py` (see [release.md](release.md)): it installs into Claude Code, Codex and
  Muse with each harness's own commands and verifies the installed bytes against the
  tag, which is the `diff -q` proof done for every file.
- **Private and shared skills** still deploy with their repository's own installer to
  `~/.claude/skills/` and `~/.agents/skills/` (never `~/.codex/skills/`, which Codex
  owns), and step 7's `diff -q` loop is still the proof.

## The protocol (verbatim from 2.9.3)

When updating any skill — whether one file or several — follow this exact sequence. Do not deviate. **Manual file copies to install targets are NOT installation.** They create drift between what is committed, what is pushed, and what is locally active. The protocol below exists because that drift has happened before and must not happen again.

### The sequence

1. **Edit the skill in its source repo.** Public skill paths are
   `<source-repo>/skills/<skill-name>/SKILL.md`; private/shared repositories use
   their declared source layout. Never edit plugin caches or installed copies
   under `~/.claude/skills/`, `~/.agents/skills/`, or client caches.

2. **Verify the source repo state.** `git status` to confirm only the intended files changed. `git diff` to review the actual content of every change.

3. **Commit with a generic message** per public-repo commit hygiene. "Update skills" or similar. No skill names, no version arc, no rationale that exposes the work that motivated the edit.

4. **Identify all configured push remotes.** `git remote -v`. The skills repos may have multiple push remotes; the source-of-truth state is "the union of all configured push remotes is up to date."

5. **Push to EVERY configured push remote**, not just `origin`. Loop over the remote names from step 4. Single-remote repos still use this step — it just iterates once.

6. **Refresh deployments using the source’s canonical path.** For public
   skills, update/reinstall the `synthesis-skills` plugin in Claude and Codex.
   For private/shared skills, run the repository installer, which deploys to
   `~/.claude/skills/` and `~/.agents/skills/` (plus declared project/Cursor
   targets), writes provenance, and reports whole-directory drift.

7. **Verify zero drift.** After `install.sh` completes, `diff -q` each installed copy against the source. They must be byte-identical:
   ```bash
   for target in ~/.claude/skills ~/.agents/skills ~/.cursor/skills; do
     for skill in <changed-skill-names>; do
       diff -q "<source-repo>/$skill/SKILL.md" "$target/$skill/SKILL.md"
     done
   done
   ```
   Any output from `diff -q` is a failure. Investigate and re-run `install.sh update`.

### What you must NOT do

- **DO NOT** manually `cp` SKILL.md files from the source repo to install targets. The install targets are managed by `install.sh`, which writes `.source.json` provenance and runs drift detection. Manual `cp` skips both and produces files that look installed but are not canonically so.
- **DO NOT** edit plugin caches or installed copies under
  `~/.claude/skills/`, `~/.agents/skills/`, or client caches directly.
- **DO NOT** skip the push step before reinstalling. `install.sh` pulls from the configured remote; if you have not pushed, the install will refresh from a stale remote state and silently revert your local edits.
- **DO NOT** skip the verify step. "I ran install.sh" is not the same as "the install matches the source." The drift check (`diff -q`) is the proof.
- **DO NOT** ask for permission to push as if push were optional. Push is part of the install workflow, not a separate decision. If you have permission to update a skill, you have permission to push the source repo. Pausing between commit and push is the failure pattern that produced the 2026-04-29 incident — it leaves three different states of the truth (working tree, remote, installs) and the agent in the middle.

### Why these rules are non-negotiable

The 2026-04-29 incident: an agent edited four skill files in source, manually copied them to install targets to "install" them, then waited at the wrong gate before pushing. The result was three different states of the truth — source repo working tree (had the changes), GitHub (did not have the changes), install targets (had locally-copied files that drifted from what `install.sh update` would have produced). When `install.sh update` was finally run, it detected and overwrote the manually-copied drift. That detection-and-overwrite happened to be safe in that case, but it was luck, not design — the manual copies could just as easily have included an in-flight edit that the agent had not yet propagated to the source.

The protocol above eliminates the asymmetry. Source is the only edit point. Push happens before install. Install runs the canonical script. The verify step proves the canonical state. There is no place for three-states-of-truth to sit.

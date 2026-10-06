---
name: synthesis-skills-manager
description: "Release the synthesis-skills plugin and keep skill installs true to source: one releaser at a time, push, install in Claude Code, Codex and Muse, verify installed bytes. Use to release, publish, install or update skills, check drift or provenance, or synthesis-merge a skill."
license: "CC0-1.0"
depends_on: ["synthesis-onboarding"]
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Skills Manager

Skills are executable methodology kept in three source repositories (public, personal,
team-shared). This skill releases the public plugin and keeps every installed copy equal
to its source, resolving drift by synthesis merge in source rather than by overwriting.

## Binding rules

1. **Source is the only edit point.** Never edit an installed copy or a harness cache; edit, commit, push every configured remote, then install. Edits made anywhere else leave three states of the truth (2026-04-29).
2. **Push is part of the update, not a separate decision.** Permission to update a skill is permission to push its source; pausing between commit and push is the failure pattern.
3. **A release is done only when each harness's installed bytes equal the tag.** Pushing is publishing, harness installs do not follow the remote, and version labels lie (2026-08-24).
4. **One releaser at a time.** Claim the release train before authoring the version bump and hold it through the release; two sessions overtook each other five times on 2026-09-01.
5. **CI on the pull request is the only test gate.** Never release a commit CI has not passed, and never bypass a hook with `--no-verify`.
6. **Reference stable paths, never a version folder.** Pinned version paths go stale on the next release.
7. **Resolve drift in source with a synthesis merge.** Keep both sides' legitimate changes; ask the user only when both changed the same instruction differently.
8. **Hook trust is the person's decision.** Report Codex `/hooks` and Muse approvals that a release needs; never approve them.

## Contents

- **Procedure** (below): release, update one skill, private and shared skills.
- [references/release.md](references/release.md): why release is a script, every refusal and why, each harness's commands, why self-reports are not evidence, the release train and stable-path history. Read before any release.
- [references/source-update-protocol.md](references/source-update-protocol.md): the non-negotiable edit-commit-push-install-verify sequence, the must-nots, and the 2026-04-29 incident. Read before editing any skill.
- [references/skills-and-provenance.md](references/skills-and-provenance.md): the three repositories, deployment targets, `.source.json` provenance, dependency hierarchy, configuration separation, the install/update/status/drift/merge commands and worked examples. Read when installing private or shared skills or resolving drift.
- [references/coverage-map.md](references/coverage-map.md): where every section of 2.9.3 went (ruling D8).
- [references/preserved.md](references/preserved.md) and [references/preserved-release-protocol.md](references/preserved-release-protocol.md): the 2.9.3 SKILL.md and release protocol verbatim. Read only to review what was cut.

## Procedure

### Release the public plugin

1. Claim the train: `synthesis claim <main checkout>/CHANGELOG.md --goal "release vX.Y.Z"`.
2. In a pull request, bump the three plugin manifests together and add the CHANGELOG
   entry for that version. Merge once CI passes.
3. From a clean checkout of the merged default branch, run

   ```bash
   python3 skills/synthesis-skills-manager/scripts/release.py --dry-run
   python3 skills/synthesis-skills-manager/scripts/release.py
   ```

   It prints a line per stage: preflight, the push read back from each remote, then per
   harness `verified, the installed files at <folder> equal vX.Y.Z` or `NOT verified:`
   with each missing, differing or extra file, then `synthesis doctor`, and finally
   `release complete: vX.Y.Z` (exit 0) or `release NOT complete` (exit 1).
4. On `NOT verified`, fix the cause and run `release.py --install-only`, which reinstalls
   and re-verifies the tag HEAD carries without publishing again (also the new-Mac path).
5. Relay doctor's hook-trust lines to the person if a hook definition changed, and tell
   them to restart each harness so it loads the new skills and hooks.
6. The script releases the train on success; on failure it stays claimed by this
   session until the release completes or the person frees it.

### Update one skill

Follow [references/source-update-protocol.md](references/source-update-protocol.md):
edit in the source repository, review `git status` and `git diff`, commit with a generic
message, push to every remote in `git remote -v`, then install (the release above for
public skills; the repository's installer for private and shared ones) and prove zero
drift.

### Private and shared skills

Use [references/skills-and-provenance.md](references/skills-and-provenance.md): the
repository's own installer copies to `~/.claude/skills/` and `~/.agents/skills/`, never
`~/.codex/skills/`; check the dependency hierarchy (public depends only on public); and
resolve drift by the synthesis merge protocol in source.

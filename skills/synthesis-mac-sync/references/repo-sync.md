# Repository sync across Macs

Read before a git sync across Macs, a repo scan, or any change to a repo manifest.

Contents: Push policy · Git repo sync in two or three bash calls · Per-workspace repo manifests ·
Git repository sync protocol · Git remote sync protocol · Manifest merge protocol · Automation
policy · Summary format · Git repository manifest format.

### Push Policy (v1.3.0)

Each repo in the manifest may have a `push_policy` field. When set, the sync protocol MUST respect it — refusing to push to any remote that violates the policy.

| `push_policy` | Meaning |
|---------------|---------|
| unset (default) | Push to all remotes configured in the repo |
| `owner-only` | Only push to `origin` when origin points to the owner's personal GitHub account. Never push to a client org, another GitHub org, or a third-party Git host. Used for `ai-knowledge-*-private` repos that carry Type 3 (personal-client) content. |
| `pr-required` | Never auto-push; user must review and open a PR |

For `owner-only` repos:
- Before any `git push`, verify `git remote -v` shows ONLY the owner's personal-GitHub URLs
- If any non-owner remote exists, abort with an error and alert the user
- These repos exist per ADR-013 (workspace-private repos); the `-private` suffix is also a discovery protocol filter (ADR-014)


### Git repo sync — TWO to THREE bash calls maximum

1. **Discovery + fetch all** (ONE call): `find` repos, then loop through all of them running `git fetch origin` in a single script.
2. **Status + auto-actions** (ONE call): Loop through all repos checking branch, ahead/behind, uncommitted changes, stashes. In the SAME script, automatically `git pull` repos that are behind and `git push` repos that are ahead with clean working trees. Collect all output into a structured summary.
3. **Follow-up actions** (ONE call, only if needed): Handle any repos that need individual attention (diverged, conflicts).

Example pattern for step 2:
```bash
REPOS=(
  "/path/to/repo1"
  "/path/to/repo2"
  # ...
)
for repo in "${REPOS[@]}"; do
  name=$(basename "$repo")
  branch=$(git -C "$repo" branch --show-current 2>/dev/null)
  if [ -z "$branch" ]; then echo "DETACHED: $name"; continue; fi
  counts=$(git -C "$repo" rev-list --left-right --count "origin/$branch...$branch" 2>/dev/null)
  behind=$(echo "$counts" | awk '{print $1}')
  ahead=$(echo "$counts" | awk '{print $2}')
  dirty=$(git -C "$repo" status --porcelain 2>/dev/null | head -5)
  if [ "$behind" -gt 0 ]; then git -C "$repo" pull origin "$branch" 2>&1 | sed "s/^/PULLED $name: /"; fi
  if [ "$ahead" -gt 0 ] && [ -z "$dirty" ]; then git -C "$repo" push origin "$branch" 2>&1 | sed "s/^/PUSHED $name: /"; fi
  [ -n "$dirty" ] && echo "DIRTY $name: $(echo "$dirty" | wc -l | tr -d ' ') files"
done
```

**Do NOT run individual tool calls per repo.** The whole point of mac-sync is automation without interaction.

## Per-Workspace Repo Manifests (v1.6.0) — the decentralized inventory

As of v1.6.0 (2026-07-08), the repo inventory is decentralized: each workspace owns its own list, and only a thin router stays central.

**Canonical file:** `<workspace-private-repo>/.agents/repos.yaml`, symlinked to `<workspace>/.agents/repos.yaml` (plus `.claude/` and `.codex/` back-compat) by the Workspace Config Symlinks layer (v1.4.0). A personal workspace without a `-private` repo carries it in the personal ai-knowledge repo. Cross-machine propagation is git (the context repo pushes/pulls, with its usual history, diffs, and conflict detection) — not iCloud.

**Schema — facts vs policy.** Fact fields (`path`, `remotes`, `default_branches`) are refreshed by scans. Policy fields (workspace-level `status: active | dormant`, per-repo `ritual_sync`, `push_policy`, `category`, `notes`) are declared by the user or their agent and are NEVER changed by a scan.

**Scan behavior per workspace (replaces the central-yaml scan for repo entries):**

- Refresh fact fields from `git remote -v` and local branch listings.
- Repo on disk but not in the manifest → PROPOSE adding it (facts pre-filled); the user confirms the policy fields.
- Repo in the manifest but not on disk → a clone decision, not an auto-clone (see Clone semantics).
- NEVER remove an entry, and NEVER delete a local clone. **Retention rule:** leaving a client, or a client shutting down, retires a workspace to `status: dormant` — retained on disk, sync paused, nothing deleted. Deletion is a rare, explicit, manual act outside every sync flow.
- Dead remotes (org deleted, Git host sunset): report once, keep the clone indefinitely — the local clone is the durable record.

**Clone semantics (selective-cloning rule):**

- The manifest records CHOSEN clones. Never enumerate a remote org (GitHub/Bitbucket) to clone or list everything the user can access.
- New-machine bootstrap (an explicit "set this machine up" act): read `machines.yaml` for the machine's subscribed workspaces, clone each workspace's context repo, read its `repos.yaml`, clone the curated list (minus any `exclude:` entries).
- Ongoing: a repo listed in a workspace manifest but missing locally is surfaced as a decision; a machine subscription may set `auto_clone: true` to mirror automatically (default: false).

**Router file — `machines.yaml`** (same folder as the legacy central yaml): machine inventory, per-machine `workspaces:` subscriptions (`all` or an explicit list — supports restricted machines such as client-issued hardware that must never hold other clients' names), optional `auto_clone` and `exclude:`, and the workspace → context-repo bootstrap map. This is the only repo-related state that stays centralized.

**Transition:** while the legacy `repositories:` section of `git-repos.yaml` still exists, each sync cross-checks it against the per-workspace manifests and REPORTS any drift — no silent divergence. After a drift-free window (at least two clean daily-ritual code-syncs plus one clean mac-sync), archive that section to a dated file; the Manifest Merge Protocol below then applies only to `machines.yaml` and any remaining central state.

**Consumers:** synthesis-daily-rituals enumerates day-start/day-end source-code sync from `ritual_sync: yes` entries (`repo_state.py --workspace-root`); this skill reads the same files for repo and remote reconciliation; the strand scan (`repo_state.py --discover`) scans disk independently of any manifest.

---

## Git Repository Sync Protocol

### Repository Discovery

Scan a configured directory (e.g., `~/workspaces/`) recursively:

```bash
find ~/workspaces -maxdepth 3 -name ".git" -type d 2>/dev/null
```

Maintain a **manifest file** (`git-repos.yaml`) that caches discovered repos, their categories, and their remote configurations for quick status checks and cross-machine remote sync. **Update using the merge protocol** on each sync — never overwrite the yaml from scratch. See **Git Remote Sync Protocol** and **Manifest Merge Protocol**.

**v1.6.0:** repo entries now live per workspace in `<workspace>/.agents/repos.yaml` (see Per-Workspace Repo Manifests above); the central `repositories:` section is transitional and the scan's write target is the workspace manifest's fact fields.

### Per-Repo Sync Procedure

**IMPORTANT:** All steps below must be executed as batched shell scripts, NOT individual tool calls per repo. See the **Performance — Minimize Tool Calls** section above.

**Step 1: Fetch all** — loop through every discovered repo and `git fetch origin` in a single script.

**Step 2: Status + auto-actions** — in a single script, loop through all repos:
- Get current branch, ahead/behind counts, uncommitted changes, stashes
- Pull if behind (automatic)
- Push if ahead and clean working tree (check push policy first — `pr-required` repos are reported, not pushed)
- If push fails (non-fast-forward), report but do not force push

**Step 3: Handle repos with uncommitted changes** — show the user what's uncommitted (file list per repo) and ask whether to commit and push each dirty repo. Present a suggested commit message for each. Do NOT silently skip — uncommitted changes are unsynced state.

### Safety Rules

1. **ALWAYS fetch first** — run `git fetch origin` before checking any status
2. **NEVER force push** — always use regular `git push`
3. **Never sweep uncommitted work** — ordinary sync reports dirty files. When leaving a Mac or at day-end, commit only the paths inside this session's claims, through `synthesis handoff` for project records and by explicit path for source work. Paths you cannot attribute, paths inside another session's claim, or paths a policy gates keep the move blocked, and the report says so.
4. **NEVER bypass hooks without explicit permission** — if a pre-commit hook blocks a commit, STOP and ask the user. Never use `--no-verify` on your own. If the user approves bypassing for a specific commit, that approval does not extend to other commits
5. **Sanitize ALL commit messages** — never include people's names, company names, project codenames, article titles, or meeting topics in commit messages. Use generic descriptions like "Add meeting transcript", "Update context", "Add new blog post". Git history is persistent and can leak private information
6. **Push automatically if ahead** — if working tree is clean and repo is ahead, push without asking
7. **Pull automatically if behind** — pull new commits without asking
8. **Skip repos with no remote** — report them but don't fail
9. **Skip repos with conflicts** — report and let user resolve manually
10. **Skip repos mid-rebase/merge** — report the state, don't interfere
11. **One branch only** — only sync the current branch, don't switch branches
12. **Prompt only for diverged repos** — when both ahead and behind, ask for merge strategy

---

## Git Remote Sync Protocol

Remote configurations (name + URL pairs) are per-machine state stored in each repo's `.git/config`. Without explicit sync, a remote added on one Mac won't exist on the other.

**v1.6.0:** the reconciliation source for a repo's remotes is its workspace `repos.yaml` `remotes:` map (fact fields), not the central yaml.

### Capture (during scan/refresh)

When refreshing `git-repos.yaml`, capture all remotes per repo:

```bash
# For each discovered repo:
git -C "$repo_path" remote -v | grep '(fetch)' | awk '{print $1, $2}'
```

**CRITICAL: Use the Manifest Merge Protocol (below) to update git-repos.yaml. NEVER generate a fresh yaml from scratch and overwrite the existing file.** The existing yaml may contain repos, remotes, categories, notes, and metadata contributed by other machines that this machine doesn't have locally. A destructive overwrite causes data loss.

This runs as part of the single batched scan script — not as separate tool calls.

### Reconcile (during pull/sync)

When syncing to a Mac, reconcile local remotes against the manifest:

```bash
# For each repo in git-repos.yaml, for each remote in the manifest:
existing_url=$(git -C "$repo_path" remote get-url "$remote_name" 2>/dev/null)
if [ -z "$existing_url" ]; then
  git -C "$repo_path" remote add "$remote_name" "$manifest_url"
  echo "ADDED $repo_name: $remote_name → $manifest_url"
elif [ "$existing_url" != "$manifest_url" ]; then
  git -C "$repo_path" remote set-url "$remote_name" "$manifest_url"
  echo "UPDATED $repo_name: $remote_name → $manifest_url (was: $existing_url)"
fi
```

Execute this as a SINGLE batched script across all repos — not individual tool calls.

### Safety Rules

1. **Never auto-remove remotes** — if a local remote exists but isn't in the manifest, flag it in the summary but do not delete. The manifest captures the last scan from one machine; the local remote may be intentionally machine-specific.
2. **Never overwrite origin with empty** — if the manifest has no `remotes:` field for a repo, skip reconciliation for that repo.
3. **Report all changes** — every add/update goes in the sync summary.
4. **Credentials in URLs are expected** — some remotes include usernames (e.g., `user@bitbucket.org`). These are not secrets (the password is in the credential helper, not the URL). Do not strip or redact them.

### Relationship to setup-git-remotes.sh

If you maintain a `setup-git-remotes.sh` bootstrap script, it serves as a fallback for initial machine setup (before repos are cloned and before the first mac-sync). Once `git-repos.yaml` captures remotes, the yaml is the authoritative source of truth. Keep the bootstrap script consistent with the yaml, or auto-generate it from the yaml during push.

---

## Manifest Merge Protocol

**v1.6.0 scope note:** with per-workspace `repos.yaml` files live, this protocol applies to `machines.yaml` and the transitional central yaml only — per-workspace manifests merge via git in their context repos.

**CRITICAL SAFETY RULE: git-repos.yaml must NEVER be generated from scratch and overwritten.** The yaml is a shared manifest across multiple machines. Each machine may have repos, remotes, or metadata that other machines don't. A destructive overwrite from one machine's scan silently destroys data contributed by other machines.

### The merge procedure

When refreshing git-repos.yaml on any machine:

1. **Read the existing yaml first.** Parse all entries, their paths, categories, notes, remotes, and any other fields.

2. **Scan the local machine** for repos (`find ~/workspaces -maxdepth 3 -name ".git"`). For each discovered repo, capture its remotes.

3. **Merge — additive updates only:**
   - **Repo exists in yaml AND locally:** Update remotes from local scan (add new remotes, update changed URLs). Preserve all existing fields (category, notes, etc.) unless the local scan has a reason to change them.
   - **Repo exists locally but NOT in yaml:** Add it as a new entry.
   - **Repo exists in yaml but NOT locally:** **Keep it.** This machine may not have it cloned. Do NOT remove it.
   - **Remote exists in yaml but NOT locally:** **Keep it.** Another machine may have added it. Do NOT remove it.

4. **Update metadata:** Refresh the header comment (date, machine name). Recount total_repos as the number of entries in the merged yaml (not the local scan count).

5. **Write the merged result.**

### What this prevents

- Repo discovered on Machine A doesn't disappear when Machine B runs a scan
- Remotes configured on Machine A survive Machine B's refresh
- Categories, notes, and other metadata contributed by any machine persist
- A machine running an older version of the skill that doesn't know about `remotes:` doesn't strip the field

### Never generate yaml from local scan alone

The correct mental model: the yaml is a **multi-machine document** that each machine **contributes to**. It is not a point-in-time capture of any single machine's state.

---

## Automation Policy

Mac-sync is designed to run fully automated. The assistant should complete the entire sync without prompting, except in specific situations.

### Automated (never prompt)

- Config files identical → skip silently
- Config file changed on one side only → copy the changed version
- Git fetch → always do
- Git pull when behind → always do (fast-forward only)
- Git push when ahead, clean working tree → always do
- Clean repos → skip silently
- Repos with no remote → skip, note in summary
- Manifest update → always refresh
- One-time actions for a different machine → skip silently

### Must prompt (show details + ask for action)

1. **Repos with uncommitted changes** → show file list per repo, suggest commit message, ask whether to commit+push. Uncommitted local changes won't reach the other Mac — treating them as informational breaks the sync guarantee
2. **Config file conflict** — both sides changed, can't determine winner from timestamps
3. **Git repo diverged** — both ahead of AND behind remote
4. **Git merge conflict during pull** — automatic merge failed
5. **Repo in unexpected state** — mid-rebase, mid-merge, or detached HEAD
6. **Auth failure across multiple repos** — stop and alert
7. **Destructive action needed** — force push, hard reset, or branch deletion

### Report but take no action (never prompt)

- Repos with stashes → note in summary
- Non-fast-forward push failures → report, move on
- Repos with `push_policy: pr-required` → report unpushed commits

## Summary Format

Present a summary after sync completes:

```
## Mac Sync Complete

### Actions Taken
- Pulled X repos (list with commit counts)
- Pushed X repos (list with commit counts)
- Synced X config files from iCloud/to iCloud

### Needs Attention (prompt user for these)
- Repos with uncommitted changes: [file list per repo + suggested commit message] — ask whether to commit+push
- Diverged repos: [list] — need merge strategy decision
- Merge conflicts: [list] — need manual resolution
- Repos in unexpected state: [list] — mid-rebase/merge/detached HEAD

### Informational (no action needed)
- Repos with stashes: [list]
- Push failures (non-fast-forward): [list]
- Repos with no remote: [list]
- Clean repos: X repos
```

Only prompt for items in "Needs Attention." Everything else is informational.


### Git Repository Manifest (git-repos.yaml)

```yaml
scan_root: ~/workspaces
max_depth: 3
total_repos: 12

repositories:
  - path: ~/workspaces/personal/my-app
    category: personal
    remotes:
      origin: https://github.com/user/my-app.git

  - path: ~/workspaces/work/app
    category: work
    push_policy: pr-required
    remotes:
      origin: https://github.com/org/app.git
      mirror: https://github.com/other-org/app.git

excluded:
  # - ~/workspaces/personal/some-fork  # Reason: upstream only
```

The `remotes` field captures all configured git remotes per repo. This is the source of truth for remote topology across machines — when mac-sync runs on a second Mac, it reconciles local remotes against this manifest. See **Git Remote Sync Protocol** below.


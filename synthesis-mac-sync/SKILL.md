---
name: synthesis-mac-sync
description: "Multi-Mac configuration sync via iCloud with bidirectional config file sync, git repository sync, machine inventory, and one-time action system. Use when asked to: mac sync, sync config, sync repos, sync with GitHub, push config to iCloud, pull config from iCloud, run mac-sync, repo status."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.5.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Mac Sync

A methodology for keeping multiple Macs in sync using iCloud for configuration files and Git for repositories. Designed to run fully automated via an AI coding assistant — the user says "run my mac-sync" and the assistant handles everything.

This skill provides the **protocol** — the sync methodology, safety rules, conflict resolution, and manifest format. Your personal **config file** (a README or manifest in your iCloud sync folder) provides the specifics: which files, which machines, which repos.

## Configuration

These values are user-specific. Update them for your environment.

| Setting | Value | Description |
|---------|-------|-------------|
| `icloud_sync_folder` | `~/Library/Mobile Documents/com~apple~CloudDocs/workspaces/[username]/mac-sync/` | iCloud Drive folder for synced config files |
| `git_scan_root` | `~/workspaces/` | Root directory for git repository discovery |
| `git_scan_max_depth` | `3` | Maximum depth for recursive `.git` directory search |
| `git_repos_manifest` | `git-repos.yaml` | Manifest file caching discovered repos |

---

## Architecture

```
synthesis-mac-sync (this skill)
  = the HOW — sync protocol, safety rules, conflict resolution, manifest format

Your config file (in your iCloud sync folder)
  = the WHAT — your specific file list, machine inventory, repo paths
```

The skill is invoked by the AI assistant. The assistant reads both this skill (for methodology) and your config file (for specifics), then executes the sync.

---

## Setup

### 1. Create a sync folder in iCloud

Create a folder in iCloud Drive to hold your synced configuration files. Example path:

```
~/Library/Mobile Documents/com~apple~CloudDocs/workspaces/[username]/mac-sync/
```

### 2. Create a config file (README.md)

Your config file lives in the sync folder. It contains:

- **Sync manifest** — which files to sync and where they map locally
- **Machine inventory** — your Mac hostnames and details
- **Git repo configuration** — optional repo sync settings
- **One-time actions** — machine-specific tasks to run once

See the **Config File Format** section below for the template.

### 3. Copy your config files into the sync folder

Mirror the directory structure. For example:
```
mac-sync/
  .gitconfig          → syncs to ~/.gitconfig
  .zshrc              → syncs to ~/.zshrc
  .config/app/keys.yaml → syncs to ~/.config/app/keys.yaml
```

---

## Sync Modes

### Full Sync ("run my mac-sync")

Performs these operations in order:
1. **Pre-pull iCloud download check** — `brctl download "$ICLOUD_BASE"` followed by polling for `.icloud` placeholder files until none remain (with 5-minute timeout), per the iCloud Propagation Verification section. Ensures any pulls operate on materialized data.
2. **Config file sync** — bidirectional, based on modification timestamps
3. **Post-push iCloud upload check** — `brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"`, per the iCloud Propagation Verification section. Ensures local-newer pushes have reached Apple's servers before reporting completion.
4. **Workspace config symlinks** — idempotent reconciliation against each workspace-private repo's `.agents/` canonical (see Workspace Config Symlinks section below)
5. **Git repo sync** — fetch, pull if behind, push if ahead
6. **One-time actions** — execute any pending machine-specific actions

### Config-Only Sync

- **Pull from iCloud:** "sync my Mac config files from iCloud"
- **Push to iCloud:** "push my Mac config files to iCloud"

### Git-Only Sync

- **Full:** "sync my repos with GitHub"
- **Status only:** "show me the status of my repos"

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

### Session-End Check

Every AI coding session should end with all repos committed and pushed. Use `synthesis-repo-guard` to verify — and, since its v2.0.0, to self-heal: `checkpoint_sync.py` auto-commits+pushes the configured private context-repo class at workflow events (agent turn end, console writes), so mac-sync's day-boundary sweep normally finds those repos already clean.

- If repo-guard reports clean: session can end safely.
- If repo-guard reports dirty: the detail is in `~/.synthesis/repo-guard/last-report.txt` and the synthesis-console `/sync` page (audible/banner alerts are deliberately generic — counts only, never repo or client names). Commit and push per the report, or run a full mac-sync.

Configure repo-guard hooks per the `synthesis-repo-guard` skill (Claude Code, Codex, Cursor, synthesis-console). Mac-sync remains the full multi-machine operation and the sweep for out-of-class repos (source code, public repos) that checkpoint automation deliberately never touches.

---

## Performance — Minimize Tool Calls

**CRITICAL:** Mac-sync must run with minimal interactive tool calls. The user should NOT face dozens of approval prompts.

### Config file sync — ONE bash call

Write a single bash script that loops through ALL files in the manifest, compares them with `diff`, checks timestamps with `stat -f %m` if different, copies the newer version, and applies `chmod 600` to sensitive files. Execute this entire script in ONE `Bash` tool call. Do NOT run separate `diff`, `stat`, or `cp` commands for each file.

Example pattern:
```bash
ICLOUD_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/workspaces/[username]/mac-sync"

sync_file() {
  local icloud="$1" local_path="$2" sensitive="$3"
  if [ ! -f "$icloud" ] && [ ! -f "$local_path" ]; then echo "SKIP (neither exists): $local_path"; return; fi
  if [ ! -f "$icloud" ]; then echo "COPY local→iCloud: $local_path"; cp "$local_path" "$icloud"; return; fi
  if [ ! -f "$local_path" ]; then echo "COPY iCloud→local: $local_path"; mkdir -p "$(dirname "$local_path")"; cp "$icloud" "$local_path"; [ "$sensitive" = "yes" ] && chmod 600 "$local_path"; return; fi
  if diff -q "$icloud" "$local_path" > /dev/null 2>&1; then echo "IDENTICAL: $local_path"; return; fi
  local icloud_ts=$(stat -f %m "$icloud") local_ts=$(stat -f %m "$local_path")
  if [ "$icloud_ts" -gt "$local_ts" ]; then echo "SYNC iCloud→local (newer): $local_path"; cp "$icloud" "$local_path"; [ "$sensitive" = "yes" ] && chmod 600 "$local_path"
  else echo "SYNC local→iCloud (newer): $local_path"; cp "$local_path" "$icloud"; fi
}

sync_file "$ICLOUD_BASE/.claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md" "no"
sync_file "$ICLOUD_BASE/.codex/AGENTS.md" "$HOME/.codex/AGENTS.md" "no"
sync_file "$ICLOUD_BASE/AGENTS.md" "$HOME/AGENTS.md" "no"
sync_file "$ICLOUD_BASE/.codex/config.toml" "$HOME/.codex/config.toml" "no"
sync_file "$ICLOUD_BASE/.codex/hooks.json" "$HOME/.codex/hooks.json" "no"
# ... one line per manifest entry ...
```

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

---

## iCloud Propagation Verification (CRITICAL — added v1.5.0)

iCloud sync between Macs is **two-stage** and both stages take time:

1. **Upload:** source Mac's local file → Apple's iCloud servers (handled by `bird` / `cloudd`).
2. **Download:** Apple's iCloud servers → destination Mac's local file (also `bird` / `cloudd`).

The receiving Mac CANNOT pull data that has not completed stage 1. Verifying the receiving side's download state without first verifying the source side's upload state misses the more fundamental question and can result in: stale iCloud content overwriting good local copies, new files silently skipped because they haven't propagated yet, and false "sync complete" reports when actual state diverges.

### After every push to iCloud — wait for upload (MANDATORY)

After completing config-file sync (including the bidirectional sync's local-newer cases), the assistant MUST run:

```bash
brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"
```

This blocks for up to 5 minutes until iCloud confirms `Stopping the query because all items are now uploaded`. Do NOT report sync complete — and especially do NOT draft cross-Mac handoff instructions — until this returns successfully.

If the command times out without confirming upload, alert the user. Network issues or Apple-side queue backlog may be at play. Do not proceed with handoff instructions in that case.

### Before every pull from iCloud — verify download materialization (MANDATORY)

Before pulling iCloud → local (especially in cross-Mac handoff scenarios where another Mac just pushed), the assistant MUST verify all items have been downloaded from iCloud to the local Mac.

**macOS `brctl monitor` only supports `--wait-uploaded` — it has NO `--wait-downloaded` flag.** The correct download verification is **trigger-then-poll**:

```bash
# 1. Trigger materialization of all items in the sync folder.
#    Idempotent — no-op if everything is already local.
brctl download "$ICLOUD_BASE"

# 2. Poll for .icloud placeholder files until none remain (with timeout).
DEADLINE=$(($(date +%s) + 300))
while true; do
  PLACEHOLDERS=$(find "$ICLOUD_BASE" -type f \( -name "*.icloud" -o -name ".*.icloud" \) 2>/dev/null)
  if [ -z "$PLACEHOLDERS" ]; then echo "All items materialized."; break; fi
  if [ $(date +%s) -ge $DEADLINE ]; then
    echo "TIMEOUT: still pending downloads after 5 minutes:"; echo "$PLACEHOLDERS"
    break
  fi
  sleep 5
done
```

Only proceed with the pull operation when the placeholder list is empty. If the loop times out, alert the user — there may be a network or iCloud-queue issue.

**Why `.icloud` placeholders work as the signal:** when iCloud has a file but the local Mac hasn't downloaded its content yet, macOS represents it as a hidden zero-byte placeholder file with a `.<filename>.icloud` extension instead of the real file. Once iCloud finishes downloading, the placeholder is replaced with the actual file. So an empty placeholder set means full materialization.

### Cross-Mac handoff (one-time actions involving another Mac)

When drafting a one-time action that involves running mac-sync on a different Mac (e.g., "the second Mac should now pull what the first Mac just pushed"):

1. **On the source Mac, BEFORE drafting the handoff prompt:** run `brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"` and confirm upload complete. Only then is it safe to send the prompt.
2. **In the handoff prompt itself:** include the download trigger + placeholder poll above as the FIRST step on the destination Mac, before any pull operation.

These two together close the two-stage gap.

### Pre-response self-check

Before sending any message that includes a cross-Mac handoff prompt, the assistant must ask itself: *"have I verified iCloud upload is complete on this Mac?"* If no, run the check first.

This is the same discipline as the cache-vs-truth rule (verify state has reached the system that will be read), applied to iCloud propagation.

### Full bidirectional sync — when to run which check

| Scenario | Before pulling local from iCloud | After pushing local to iCloud |
|----------|----------------------------------|-------------------------------|
| Single-Mac everyday sync | `brctl download` + placeholder poll (cheap no-op if already current) | `brctl monitor --wait-uploaded` (cheap no-op if no new content) |
| Cross-Mac handoff (other Mac just pushed) | `brctl download` + placeholder poll (REQUIRED — waits for propagation) | `brctl monitor --wait-uploaded` (REQUIRED if drafting reverse handoff) |
| Pull-only sync ("from iCloud") | `brctl download` + placeholder poll (REQUIRED) | N/A (no push) |
| Push-only sync ("to iCloud") | N/A (no pull) | `brctl monitor --wait-uploaded` (REQUIRED) |

In the everyday single-Mac case the checks are cheap — they return almost immediately when iCloud is current. The cost of always running them is small; the cost of skipping them in a cross-Mac case is data loss.

---

## Config File Sync Protocol

### Bidirectional Sync (default)

For each file in the sync manifest (executed as a SINGLE batched script per the Performance section above):

1. Compare iCloud version with local version using `diff`
2. **If identical** → skip silently
3. **If different** → compare modification timestamps using `stat -f %m` (macOS)
4. **Copy the newer file over the older one** automatically
5. For sensitive files, ensure `chmod 600` after copying
6. Report what was synced in the summary

### Pull from iCloud

When user explicitly asks to pull:
1. Compare each iCloud file with its local counterpart
2. If different, copy iCloud → local automatically
3. Preserve permissions (chmod 600 for sensitive files)

### Push to iCloud

When user explicitly asks to push:
1. Compare each local file with its iCloud counterpart
2. If different, copy local → iCloud automatically

### Template File Expansion

For config files containing machine-specific paths, use template files with placeholders:
- **When pulling:** Replace `{{HOME}}` with `$HOME` and `{{USERNAME}}` with `$USER`
- **When pushing:** Replace current `$HOME` value with `{{HOME}}` and `$USER` value with `{{USERNAME}}`

### Safety Rules

1. **Automatic for one-sided changes** — if only one side changed, copy automatically
2. **Prompt only for conflicts** — if both sides changed and timestamps can't resolve, show diff and ask which to keep
3. **Preserve permissions** — sensitive files must be `chmod 600`
4. **Quote all paths** — iCloud paths contain spaces ("Mobile Documents")
5. **Never overwrite with empty** — if either file is empty or missing, do not overwrite the non-empty version
6. **Skip machine-specific path differences** — if the only differences are username-specific paths (e.g., `/Users/alice/` vs `/Users/bob/`), skip and note in summary
7. **Verify iCloud propagation** — run `brctl monitor --wait-uploaded` after push and `brctl download` + `.icloud` placeholder polling before pull, per the iCloud Propagation Verification section above. Mandatory for cross-Mac handoff scenarios.

---

## Git Repository Sync Protocol

### Repository Discovery

Scan a configured directory (e.g., `~/workspaces/`) recursively:

```bash
find ~/workspaces -maxdepth 3 -name ".git" -type d 2>/dev/null
```

Maintain a **manifest file** (`git-repos.yaml`) that caches discovered repos, their categories, and their remote configurations for quick status checks and cross-machine remote sync. **Update using the merge protocol** on each sync — never overwrite the yaml from scratch. See **Git Remote Sync Protocol** and **Manifest Merge Protocol**.

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
3. **NEVER silently auto-commit** — always show uncommitted files and ask before committing. Uncommitted changes are unsynced state; ignoring them defeats the purpose of the sync. Group files into separate commits by topic — never bundle unrelated files
4. **NEVER bypass hooks without explicit permission** — if a pre-commit hook blocks a commit, STOP and ask the user. Never use `--no-verify` on your own. If the user approves bypassing for a specific commit, that approval does not extend to other commits
5. **Sanitize ALL commit messages** — never include people's names, company names, project codenames, article titles, or meeting topics in commit messages. Use generic descriptions like "Add meeting transcript", "Update context", "Add new blog post". Git history is persistent and can leak confidential information
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

---

## Machine Inventory

Use `LocalHostName` as the unique machine identifier:

```bash
scutil --get LocalHostName
```

Why LocalHostName:
- Set explicitly per machine in System Settings → Sharing → Local hostname
- Won't accidentally collide (unlike usernames)
- Persists across OS updates
- Easy to check

### Machine Inventory Table Format

```markdown
| LocalHostName | Model | Username | Notes |
|---------------|-------|----------|-------|
| my-mac-mini | Mac mini M2 Pro | alice | Primary development |
| my-macbook | MacBook Pro M4 | alice | Secondary laptop |
```

---

## One-Time Actions

Machine-specific tasks that should run once per machine.

### Safety Protocol

1. **Detect current machine:** `scutil --get LocalHostName`
2. **Check eligibility:** Each action has a `Target:` field — `machine-name`, `ALL`, or `ALL EXCEPT machine-name`
3. **Execute or skip** based on match
4. **Update status** after execution: `machine-name [COMPLETED 2026-01-15]`
5. **Delete action** only when ALL targeted machines show `[COMPLETED]`

### Template

```markdown
### YYYY-MM-DD: Brief Description

**Target:** [LocalHostName(s) or ALL or ALL EXCEPT LocalHostName]
**Status:** [LocalHostName] [PENDING]

**Background:** Why this action is needed

**Action Required:**
\`\`\`bash
# Commands to run
\`\`\`

**Verification:** How to confirm it worked
```

---

## Workspace Config Symlinks (v1.4.0)

For workspace-scoped agent configs that should be **identical across all your Macs** AND **available to any agent tool** (Claude Code, Codex, Cursor, etc.), the canonical source lives in the workspace-private repo at `<workspace>/<workspace-private>/.agents/`. mac-sync ensures the expected symlinks exist at the workspace level (and known repos) on every invocation.

### Why this layer (vs iCloud-based config sync)

iCloud-based sync is the right pattern for global personal configs (`.gitconfig`, `.zshrc`, `.codex/config.toml`). Workspace-scoped agent configs are different:

- They're already in a git repo (the workspace-private repo) that pushes to GitHub — so cross-machine sync is "free" via git
- They're agent-tool-agnostic — `.agents/` is the convention multiple tools should read from, not `.claude/`
- They're version-controlled with diff history per change (which iCloud sync isn't)

So: keep iCloud sync for global personal files; use git + symlinks for workspace agent configs.

### Discovery

For each workspace under `~/workspaces/<workspace>/`:

1. Check if a workspace-private repo exists at `~/workspaces/<workspace>/ai-knowledge-<workspace>-<owner>-private/.agents/`
2. If yes, list all `*.yaml` and `*.json` files in that `.agents/` directory (skip `README.md` and any non-config files)
3. For each canonical file: ensure the symlinks below exist

### Symlinks to create per canonical file

| Symlink path | Target (relative) | Purpose |
|--------------|-------------------|---------|
| `<workspace>/.agents/<file>` | `../<workspace-private>/.agents/<file>` | Agent-agnostic location (preferred) |
| `<workspace>/.claude/<file>` | `../<workspace-private>/.agents/<file>` | Back-compat for tools that look in `.claude/` |
| `<workspace>/.codex/<file>` | `../<workspace-private>/.agents/<file>` | Back-compat for Codex |

All paths use **relative** symlinks so they work on any Mac regardless of `~/<username>`.

### Per-repo symlinks (conservative)

A canonical config may also need to appear inside a specific repo (e.g., a skill that walks up from CWD looking for `.claude/<file>.yaml` in the current repo first). The skill handles this **conservatively** — it does NOT auto-create per-repo symlinks for arbitrary repos. Instead:

- If a repo already has `.claude/<file>.yaml` (or `.agents/<file>.yaml`) AS A REGULAR FILE, AND its content matches the canonical exactly: replace with a symlink to canonical.
- If a repo already has `.claude/<file>.yaml` AS A SYMLINK pointing to canonical: leave alone (already correct).
- If a repo already has `.claude/<file>.yaml` AS A SYMLINK pointing somewhere else, OR as a regular file with different content: WARN. Do not overwrite — manual decision.
- If neither exists in the repo: do nothing. Per-repo symlinks for "new" repos are an explicit setup step, not auto-created.

### Idempotence rules (apply to every symlink action)

| Current state at symlink path | Action |
|-------------------------------|--------|
| Symlink exists, points correctly | Skip silently |
| Symlink exists, points wrong | Replace with `ln -sf` |
| Regular file exists, content matches canonical | `rm` then create symlink |
| Regular file exists, content differs from canonical | **WARN** — do not overwrite |
| Nothing exists at the path | Create symlink |
| Parent directory doesn't exist | `mkdir -p` parent, then create symlink |

The skill must report what it did per file, not silently overwrite anything that diverged from canonical.

### Bootstrap script (single batched bash call, per the Performance section)

Run this with `bash -c '...'` (not `zsh`) so `shopt -s nullglob` is available — that makes empty globs expand to nothing instead of throwing or expanding to the literal pattern.

```bash
shopt -s nullglob 2>/dev/null  # or: [ -n "$ZSH_VERSION" ] && setopt NULL_GLOB

ensure_symlink() {
  local link_path="$1" target_relative="$2"
  local link_dir=$(dirname "$link_path")
  mkdir -p "$link_dir"
  if [ -L "$link_path" ]; then
    local current_target=$(readlink "$link_path")
    if [ "$current_target" = "$target_relative" ]; then
      echo "OK (symlink correct): $link_path"
      return
    fi
    echo "FIX (symlink wrong target): $link_path → $target_relative (was: $current_target)"
    ln -sf "$target_relative" "$link_path"
    return
  fi
  if [ -f "$link_path" ]; then
    local canonical_abs="$link_dir/$target_relative"
    if diff -q "$link_path" "$canonical_abs" > /dev/null 2>&1; then
      echo "MIGRATE (file matches canonical, replacing with symlink): $link_path"
      rm "$link_path"
      ln -s "$target_relative" "$link_path"
      return
    fi
    echo "WARN (regular file differs from canonical, NOT touching): $link_path"
    return
  fi
  echo "CREATE: $link_path → $target_relative"
  ln -s "$target_relative" "$link_path"
}

# Discover workspace-private repos and process each canonical file
for workspace_dir in "$HOME"/workspaces/*/; do
  workspace=$(basename "$workspace_dir")
  # Look for any ai-knowledge-<workspace>-*-private repo (the -private suffix marks it)
  for private_repo in "$workspace_dir"ai-knowledge-"$workspace"-*-private/; do
    [ -d "$private_repo/.agents" ] || continue
    for canonical in "$private_repo".agents/*; do
      [ -f "$canonical" ] || continue
      filename=$(basename "$canonical")
      # Skip README and other non-config files
      case "$filename" in README.md|*.md) continue ;; esac
      private_repo_name=$(basename "${private_repo%/}")
      # Workspace-level: .agents/ + .claude/ + .codex/ (back-compat)
      ensure_symlink "$workspace_dir.agents/$filename" "../$private_repo_name/.agents/$filename"
      ensure_symlink "$workspace_dir.claude/$filename" "../$private_repo_name/.agents/$filename"
      ensure_symlink "$workspace_dir.codex/$filename" "../$private_repo_name/.agents/$filename"
    done
  done
done
```

This script is fully idempotent: run it 100 times, every line reports `OK` after the first successful run. Run it on a fresh Mac (after cloning the workspace-private repo): every line reports `CREATE`. Run it after manually editing a config to a different value: report `WARN` and don't clobber.

### When the skill runs this

Workspace symlink reconciliation runs as part of every full mac-sync, AFTER config-file iCloud sync and BEFORE git-repo sync. This ordering matters:

- After iCloud sync: ensures any iCloud-synced files are up to date before checking workspace-level symlinks (in case an old workflow had a config in both iCloud and workspace-private)
- Before git-repo sync: any new symlinks being committed (none today, but theoretically) get included in the next git status check

Report symlink results in the summary under "Workspace Symlinks":
```
### Workspace Symlinks
- Reconciled: 5 symlinks across 1 workspace
- Warnings: 0 regular-file divergences
```

### Migration: moving a config from iCloud-synced to workspace-private

When a workspace-scoped config moves from iCloud-based sync to workspace-private + symlink:

1. Delete the entry from your mac-sync config's "Sync Manifest — Direct Copy Files" table
2. Add a one-time action with `Target: ALL` to delete the iCloud copy on every Mac (so it doesn't get re-synced from any Mac that still has it)
3. Add the canonical to `<workspace-private>/.agents/<file>`, commit, push
4. The next mac-sync invocation creates the symlinks on every Mac via the bootstrap above

---

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

---

## Config File Format

Your config file (README.md in the sync folder) should include these sections. Adapt to your needs:

### Sync Manifest — Direct Copy Files

```markdown
| iCloud Path (relative) | Local Path | Purpose | Sensitive? |
|------------------------|------------|---------|------------|
| `.gitconfig` | `~/.gitconfig` | Git identity | No |
| `.zshrc` | `~/.zshrc` | Shell config | No |
| `.config/app/keys.yaml` | `~/.config/app/keys.yaml` | API keys | **Yes** |
```

### Sync Manifest — Template Files

```markdown
| iCloud Path (relative) | Local Path | Placeholders | Sensitive? |
|------------------------|------------|-------------|------------|
| `.ssh/config.template` | `~/.ssh/config` | `{{HOME}}`, `{{USERNAME}}` | No |
```

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

### Machine Inventory

Document your machines with the table format above.

### One-Time Actions

Use the template above for machine-specific tasks.

---

## Adding New Files to Sync

### Direct copy file
1. Copy it to the sync folder (maintaining directory structure)
2. Add it to the sync manifest table
3. Note if it contains secrets (for permissions)

### Template file (contains machine-specific paths)
1. Create a `.template` version with `{{HOME}}` and `{{USERNAME}}` placeholders
2. Add it to the template files table
3. Document which placeholders are used

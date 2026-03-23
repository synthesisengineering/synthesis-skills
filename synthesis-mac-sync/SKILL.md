---
name: synthesis-mac-sync
description: "Multi-Mac configuration sync via iCloud with bidirectional config file sync, git repository sync, machine inventory, and one-time action system. Use when asked to: mac sync, sync config, sync repos, sync with GitHub, push config to iCloud, pull config from iCloud, run mac-sync, repo status."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
  source_type: "public"
---

# Synthesis Mac Sync

A methodology for keeping multiple Macs in sync using iCloud for configuration files and Git for repositories. Designed to run fully automated via an AI coding assistant — the user says "run my mac-sync" and the assistant handles everything.

This skill provides the **protocol** — the sync methodology, safety rules, conflict resolution, and manifest format. Your personal **config file** (a README or manifest in your iCloud sync folder) provides the specifics: which files, which machines, which repos.

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

Performs all three operations:
1. **Config file sync** — bidirectional, based on modification timestamps
2. **Git repo sync** — fetch, pull if behind, push if ahead
3. **One-time actions** — execute any pending machine-specific actions

### Config-Only Sync

- **Pull from iCloud:** "sync my Mac config files from iCloud"
- **Push to iCloud:** "push my Mac config files to iCloud"

### Git-Only Sync

- **Full:** "sync my repos with GitHub"
- **Status only:** "show me the status of my repos"

---

## Config File Sync Protocol

### Bidirectional Sync (default)

For each file in the sync manifest:

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

---

## Git Repository Sync Protocol

### Repository Discovery

Scan a configured directory (e.g., `~/projects/`) recursively:

```bash
find ~/projects -maxdepth 4 -name ".git" -type d 2>/dev/null
```

Maintain a **manifest file** (`git-repos.yaml`) that caches discovered repos for quick status checks. Refresh on each sync.

### Per-Repo Sync Procedure

**Step 1: Fetch (always do this first)**
```bash
git -C "$repo_path" fetch origin
```

**Step 2: Check status**
```bash
branch=$(git -C "$repo_path" branch --show-current)
git -C "$repo_path" rev-list --left-right --count "origin/$branch...$branch"
```

**Step 3: Pull if behind** — automatic, no prompt needed
```bash
git -C "$repo_path" pull origin "$branch"
```

**Step 4: Push if ahead** (clean working tree) — check push policy first:
- **Default:** Push directly. If push fails (non-fast-forward), report but do not force push.
- **`pr-required`:** Do NOT push. Report unpushed commits in summary.

**Step 5: Report repos with uncommitted changes** — list in summary, do NOT auto-commit.

### Safety Rules

1. **ALWAYS fetch first** — run `git fetch origin` before checking any status
2. **NEVER force push** — always use regular `git push`
3. **NEVER auto-commit** — never stage and commit uncommitted changes
4. **Push automatically if ahead** — if working tree is clean and repo is ahead, push without asking
5. **Pull automatically if behind** — pull new commits without asking
6. **Skip repos with no remote** — report them but don't fail
7. **Skip repos with conflicts** — report and let user resolve manually
8. **Skip repos mid-rebase/merge** — report the state, don't interfere
9. **One branch only** — only sync the current branch, don't switch branches
10. **Prompt only for diverged repos** — when both ahead and behind, ask for merge strategy

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

### Report but take no action (never prompt)

- Repos with uncommitted changes → list so user is aware
- Repos with stashes → note in summary
- Non-fast-forward push failures → report, move on
- Repos with `push_policy: pr-required` → report unpushed commits

### Must prompt (only these situations)

1. **Config file conflict** — both sides changed, can't determine winner from timestamps
2. **Git repo diverged** — both ahead of AND behind remote
3. **Git merge conflict during pull** — automatic merge failed
4. **Repo in unexpected state** — mid-rebase, mid-merge, or detached HEAD
5. **Auth failure across multiple repos** — stop and alert
6. **Destructive action needed** — force push, hard reset, or branch deletion

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

## Summary Format

Present a summary after sync completes:

```
## Mac Sync Complete

### Actions Taken
- Pulled X repos (list with commit counts)
- Pushed X repos (list with commit counts)
- Synced X config files from iCloud/to iCloud

### Needs Attention (prompt user for these)
- Diverged repos: [list] — need merge strategy decision
- Merge conflicts: [list] — need manual resolution
- Repos in unexpected state: [list] — mid-rebase/merge/detached HEAD

### Informational (no action needed)
- Repos with uncommitted changes: [list with file counts]
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
scan_root: ~/projects
max_depth: 4

repositories:
  - path: ~/projects/my-app
    remote: https://github.com/user/my-app.git
    category: personal

  - path: ~/projects/work/app
    remote: https://github.com/org/app.git
    category: work
    push_policy: pr-required

excluded:
  # - ~/projects/forks/some-repo  # Reason: upstream only
```

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

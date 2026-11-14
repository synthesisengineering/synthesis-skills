# Machines, one-time actions and workspace config symlinks

Read when adding a Mac to the inventory, writing or running a one-time action, setting up a new
Mac, or reconciling workspace config symlinks.

Contents: New-machine bootstrap · Machine inventory · One-time actions · Workspace config
symlinks · Config file format: machine inventory and one-time actions.

## New-machine bootstrap — protection layer first

On any new Mac (or after a macOS / Xcode CLT update, which can replace interpreters and wipe user site-packages), bring up the protection layer BEFORE the first commit, not after:

1. Run the onboarding setup script: `python3 <synthesis-onboarding>/scripts/setup.py`. It installs the native plugin in each harness, the runtime and its hooks, and the global git hooks, and clones the workspace repositories `repos.yaml` declares; it asks its questions through the terminal, so it works when piped from `curl`.
2. Pull the synced config through this skill's config-file sync (credentials and private config arrive this way, sensitive files `chmod 600`) BEFORE running repos sync — the commit guard reads its policy on every commit.
3. Install the private layer on top (private skills and config), without editing public files.
4. Run `synthesis doctor` and require a healthy first line before the first commit.
5. Only then run the git-repos sync and begin work.

Ordering rationale: a fresh machine is exactly where the old failure mode lived — interpreters differ, site-packages are empty, and the first commits of a migration are often bulk imports with the highest leak surface. The v2 engine needs no third-party packages (any python3 works), so step 1 has no pip prerequisite on a fresh macOS with CLT installed.

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

### Machine Inventory

Document your machines with the table format above.

### One-Time Actions

Use the template above for machine-specific tasks.

---


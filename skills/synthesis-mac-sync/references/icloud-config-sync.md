# iCloud config sync

Read before syncing config files through iCloud, adding a file to the sync, or changing a
client's configuration on more than one Mac. `<ICLOUD_BASE>` is the sync folder.

Contents: Configuration · Architecture · Agent configuration ownership · Setup · Config file sync
in one bash call · Codex configuration overlay · iCloud propagation verification · Config file
sync protocol · Config file format · Adding new files to sync.

## Configuration

These values are user-specific. Update them for your environment.

| Setting | Value | Description |
|---------|-------|-------------|
| `icloud_sync_folder` | `~/Library/Mobile Documents/com~apple~CloudDocs/workspaces/[username]/mac-sync/` | iCloud Drive folder for synced config files |
| `git_scan_root` | `~/workspaces/` | Root directory for git repository discovery |
| `git_scan_max_depth` | `3` | Maximum depth for recursive `.git` directory search |
| `git_repos_manifest` | `git-repos.yaml` | Legacy central manifest (transitional; see v1.6.0 section) |
| `workspace_repo_manifest` | `<workspace>/.agents/repos.yaml` | Per-workspace repo manifest (v1.6.0; canonical for repo entries) |

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

## Agent configuration ownership

Agent instructions, lifecycle hooks, and the stable subset of client
configuration use version-controlled sources plus native adapters:

- Public reusable behavior lives in the `synthesis-skills` plugin.
- Personal rules, private skills, hook policy, and owned config overlays live in
  the private personal source repository.
- Repository instructions live in tracked `AGENTS.md`; `CLAUDE.md` imports it.
- Runtime-owned auth, trust databases, marketplace timestamps, caches, and
  machine-specific paths stay local to each client.

Do not synchronize an entire client configuration file when the client also
writes volatile state into it. Install or merge only the keys owned by the
synthesis configuration source, then run `synthesis doctor`.

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

# Direct timestamp sync is appropriate for user-owned static files.
sync_file "$ICLOUD_BASE/.gitconfig" "$HOME/.gitconfig" "no"

# Agent instructions, hooks, plugins, and client config use their
# version-controlled installer + `synthesis doctor` instead of sync_file.
# Runtime auth may remain an explicit encrypted/sensitive manifest item when
# the user has deliberately chosen cross-machine credential synchronization.
```

### Codex configuration overlay

Codex `config.toml` contains both declarative preferences and runtime-owned
state. The personal agent-config installer must merge only its declared keys,
such as model role, feature toggles, sandbox policy, and MCP definitions. It
must preserve plugin install state, marketplace update timestamps, hook trust,
project trust, and unknown keys. After the merge:

```bash
codex doctor --json
synthesis doctor
```

Treat the source overlay and merged runtime file as separate truth layers.


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

1. **On the source Mac:** run the leave procedure in
   [leaving-and-arriving.md](leaving-and-arriving.md): `synthesis handoff` for every project
   being transferred, then the strand scan, until nothing claimed is dirty or unpushed.
2. **Before drafting the handoff prompt:** run `brctl monitor --wait-uploaded -t 300 "$ICLOUD_BASE"` and confirm upload complete.
3. **In the handoff prompt itself:** include the download trigger and
   placeholder poll as the first destination step, then the arrive procedure
   (fetch, fast-forward only over clean trees, `synthesis brief`) before project work resumes.

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

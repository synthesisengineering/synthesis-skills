---
name: synthesis-skills-manager
description: "Agent-native skill installer and manager for the synthesis skills ecosystem. Handles installation, drift detection, synthesis merge for conflicts, provenance tracking, and cross-repo coordination. Use when asked to: install skills, update skills, check skill drift, manage skills, skill status, skill inventory, sync skills."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
  source_type: "public"
---

# Synthesis Skills Manager

You are an AI agent managing synthesis skills across a three-repo architecture. Skills are executable methodology for AI agents — not configuration files, not packages. This distinction matters for how you handle drift and conflicts.

## Architecture

Three skill repositories, each with a different access level:

| Repo | Type | Access | Purpose |
|------|------|--------|---------|
| `synthesis-skills` | public | Open source | General-purpose methodology skills |
| `synthesis-skills-rajiv` (or user's private repo) | private | Owner only | Personal and proprietary skills |
| `synthesis-skills-mcclatchy` (or team shared repo) | shared | Team members | Cross-project team skills |

**Installation targets** (in priority order):
1. `~/.claude/skills/` — Claude Code
2. `~/.agents/skills/` — Cross-platform convention
3. `~/.cursor/skills/` — Cursor (if present)
4. `/path/to/project/.claude/skills/` — Project-level (shared repo only)

## Provenance Tracking

Every installed skill has a `.source.json` file (gitignored in source repos):

```json
{
  "source_repo": "github.com/rajivpant/synthesis-skills",
  "source_type": "public",
  "source_path": "synthesis-thinking-framework/SKILL.md",
  "source_commit": "abc123...",
  "installed_at": "2026-03-23T14:30:00Z",
  "installed_by": "synthesis-skills-manager"
}
```

## Commands

When the user asks you to manage skills, execute the appropriate command:

### `install [repo] [skill-name]`

Install a skill from a source repo to the target location.

1. Read the skill's SKILL.md from the source repo
2. Check if a skill with the same name already exists at the target
3. If it exists:
   a. Compare checksums (SHA-256 of SKILL.md content)
   b. If identical, skip (already up to date)
   c. If different, perform drift resolution (see below)
4. Copy the skill directory to the target
5. Write `.source.json` with current commit hash and timestamp
6. Check dependencies (read `depends_on` from frontmatter, verify each is installed)
7. Report result

### `update [repo]`

Update all skills from a source repo.

1. For each skill in the source repo, run the install flow
2. Report: updated, skipped (unchanged), merged (drift resolved)

### `status`

Show the state of all installed skills.

1. Scan all target directories for skill directories (contain SKILL.md)
2. Group by source_repo (from .source.json)
3. For each skill:
   - Read `.source.json` for provenance
   - Compare installed SKILL.md checksum against source (if source repo is available locally)
   - Report: OK, DRIFT (local changes), MISSING (in source but not installed), ORPHAN (installed but not in any known source)
4. Check all dependencies
5. Validate access hierarchy

### `drift [skill-name]`

Show what changed between installed and source versions.

1. Read both SKILL.md files
2. Show a diff summary (sections added, removed, modified)
3. Recommend: accept source, keep local, or merge

### `merge [skill-name]`

Perform synthesis merge when drift is detected.

This is the key differentiator from package managers. Skills are methodology — when the installed copy and source both have legitimate changes, the right answer is synthesis merge, not "pick a version."

**Merge protocol:**

1. Read the source version (from repo)
2. Read the installed version (from target)
3. Read `.source.json` to find the common ancestor commit
4. Identify what changed in each:
   - Source changes: new sections, updated instructions, bug fixes
   - Local changes: customizations, environment-specific tweaks, improvements
5. Synthesize:
   - Keep all source structural changes (new sections, reordered steps)
   - Keep all local customizations that don't conflict with source intent
   - For true conflicts (both changed the same instruction differently), present both versions and ask the user
6. Write the merged result to the installed location
7. Update `.source.json` with new commit hash

**What makes this different from git merge:** Git merges text. This merges methodology. An AI agent understands that moving a step from section 3 to section 2 is not a conflict with adding a new substep to section 3 — even though a text-based merge would flag it.

## Dependency Access Hierarchy

Strict rules — enforced on every install and status check:

| Skill Type | Can Depend On |
|------------|---------------|
| public | public only |
| private | public + private |
| shared | public + shared |

**No cross-collection private dependencies.** If a private skill needs functionality from a shared skill (or vice versa), the dependency must be promoted to public first.

### Checking Dependencies

Read `depends_on` from SKILL.md frontmatter:

```yaml
depends_on: ["synthesis-thinking-framework", "synthesis-content-quality"]
```

For each dependency:
1. Check if it's installed in the target directory
2. Read its `.source.json` to get its `source_type`
3. Validate against the hierarchy table
4. Report warnings (missing) or violations (hierarchy breach)

## Configuration Separation

Skills with user-specific values have a `## Configuration` section with a table:

```markdown
## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| `daily_plans_path` | `ai-knowledge-rajiv/projects/_daily-plans/` | Where to save daily plans |
```

When installing a skill that has a Configuration section:
1. Note the configuration table to the user
2. If the user has previously configured values for this skill (in a prior installation), preserve them
3. Never overwrite Configuration values during update — merge them

## Workflow Examples

### First-time setup

```
User: "Install all my synthesis skills"

1. Clone/update synthesis-skills (public) → install 22 skills to ~/.claude/skills/
2. Clone/update synthesis-skills-rajiv (private) → install 13 skills to ~/.claude/skills/
3. For project-level: install synthesis-skills-mcclatchy skills to project .claude/skills/
4. Write .source.json for each
5. Check all dependencies
6. Report summary
```

### Drift detected during update

```
User: "Update my skills"

1. Pull latest from each repo
2. For synthesis-daily-rituals: installed checksum ≠ source checksum
3. Read both versions
4. Installed has: added clickable link instruction (local improvement)
5. Source has: no changes since last install
6. Decision: local is ahead of source → keep local, update .source.json timestamp
7. Report: "synthesis-daily-rituals: local changes preserved (source unchanged)"
```

### Both sides changed

```
User: "Update my skills"

1. Pull latest from each repo
2. For synthesis-article-writing: installed checksum ≠ source checksum
3. Source has: new Phase 3 critical review section
4. Installed has: custom anonymization examples added
5. Decision: synthesis merge needed
6. Merge: keep new Phase 3 from source + keep custom examples from local
7. Report: "synthesis-article-writing: merged (source added Phase 3, kept local customizations)"
```

## Error Handling

- **Source repo not available locally:** Report which repo is missing, suggest cloning it
- **Circular dependencies:** Detect and report (should never happen with the hierarchy)
- **Corrupted .source.json:** Regenerate from SKILL.md frontmatter (source_repo, source_type) and current state
- **Skill with no frontmatter:** Warn — skill doesn't follow the standard. Install anyway but flag for review.

## Implementation Notes

This skill is designed to be executed by an AI agent (Claude Code, Cursor, etc.), not as a shell script. The agent reads files, compares content, understands methodology structure, and makes merge decisions that a text-based tool cannot.

The `install.sh` scripts in each repo serve as bootstrap/fallback installers for environments without an AI agent. They handle the mechanical parts (copy, provenance, checksums) but cannot do synthesis merge — they overwrite on conflict with a drift warning.

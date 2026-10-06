# Quick answers: the pattern and its setup

What the companion is, how it is configured, and how to stand it up in a workspace.

## The Pattern

A **quick-answers companion**: one `ongoing`-status project inside the user's own personal knowledge workspace (per `synthesis-project-management`, at `~/workspaces/{workspace}/ai-knowledge-{workspace}/` — the same location `synthesis-onboarding` scaffolds), used from a session on a routine-tier model, whose entire mandate is answering lookups by reading everything else in the workspace and writing almost nothing back.

It is deliberately **not** a "seat" in the operations sense (compare an `<org>-operations`-style project, which *owns* rituals, syncs, and triage). It owns no workflow. It is a read path across every other project, plus the workspace's knowledge base — and its value depends on staying that narrow. The moment it starts drafting, deciding, or sending, it has become a second copy of the work it exists to protect other sessions from absorbing.

**"Automatic" is a file, not a habit.** The routing line lives in the workspace's Git-tracked `.agents/workspace-AGENTS.md`. The onboarding engine exposes that one source to both clients through the workspace-root `AGENTS.md` and `CLAUDE.md` entry points. A companion without the routing line still has to be invoked by hand, which is the friction this pattern exists to remove.

### Configuration

| Setting | Value | Description |
|---|---|---|
| `ai_knowledge_workspace` | `~/workspaces/{workspace}/ai-knowledge-{workspace}/` | Same location `synthesis-project-management` and `synthesis-onboarding` already use — never a substitute folder |
| `project_id` | `{workspace}-quick-answers` | e.g. `acme-quick-answers` — noun name, `ongoing` status, mirrors the workspace's own ops-seat naming |
| `faq_log` | `projects/{project_id}/resources/FAQ.md` | Append-only log of answered questions — see "The FAQ log" below |
| `model_tier` | `routine` (per `synthesis-model-tiers`) | Set by the user per client (`/model` in Claude Code, the equivalent in Codex) — an agent cannot switch its own model, so state the recommendation and wait rather than attempting it |

### Setup

This pattern needs a personal knowledge workspace — the same `ai-knowledge-{workspace}` repo `synthesis-project-management` and `synthesis-onboarding` already use, at `~/workspaces/{workspace}/ai-knowledge-{workspace}/`. Don't invent a substitute location (a loose folder somewhere else, a name that doesn't match): a companion that lives outside the convention every other project already follows is a second, incompatible system, not a lighter version of the same one.

1. **Ensure the personal knowledge workspace exists.** Run `python3 <synthesis-onboarding>/scripts/setup.py workspace --new {name}` (add `--kb URL` for its remote). It safely scaffolds `~/workspaces/{name}/ai-knowledge-{name}/`, including a seeded `projects/index.yaml`, a Git-tracked `.agents/workspace-AGENTS.md`, a tracked `.agents/knowledge-base.yaml` declaring the `source/` bundle, and collision-safe workspace entry points for both clients: the workspace folder's `AGENTS.md` links to the tracked source, with a `CLAUDE.md` importing it, and an entry point someone else wrote is kept. It is idempotent when the workspace already exists, and it leaves every seeded file alone once you have edited it. It needs a git identity, and commits only the seeds it wrote. With no checkout of the plugin at hand, run the same command through the stable bootstrap: `curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- workspace --new {name}`. A shared organization workspace is a sibling, not a substitute; this pattern's project files belong in the personal repository.
2. Create the project the normal way (`synthesis-project-management`): `status: ongoing`, `bounded: false`, noun-first id (e.g. `{workspace}-quick-answers`). Give it a thin `CONTEXT.md` and, if the workspace has enough standing routing knowledge to be worth writing down (which sources answer which question shapes), a short `REFERENCE.md`.
3. Register it in `projects/index.yaml` under its own initiative if the workspace doesn't already have a natural home for "standing non-ops infrastructure" — don't force it under an operations initiative that implies it owns rituals.
4. **Add one routing line to the tracked source** at `~/workspaces/{name}/ai-knowledge-{name}/.agents/workspace-AGENTS.md`. Never edit the workspace-root entry points: the onboarding engine owns those and both clients resolve the tracked source through them. Commit the source change in the personal knowledge repository so a new machine receives it.
5. Tell the user which model tier to select for the session (see Configuration), and that this is a one-time-per-session setting they make, not something this skill can do for them.
6. Seed `resources/FAQ.md` with a header; leave it empty otherwise. It fills from use.

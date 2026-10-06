# Cross-Agent Conformance Architecture

## Contents

1. Ownership
2. Instruction discovery
3. Skill and plugin deployment
4. Lifecycle controls
5. Durable project handoff
6. Cross-machine synchronization
7. Conformance contract

The 1.14.1 text is in [preserved-architecture.md](preserved-architecture.md); this is
its v5 form.

## 1. Ownership

| Behavior | Canonical owner | Deployment examples |
|----------|-----------------|---------------------|
| Public methodology and scripts | public skill repository | Claude/Codex plugin caches |
| Personal behavior and machine policy | private skill/config repository | user instructions, hooks, private skill directories |
| Project status and history | appropriate AI-knowledge repository | local clone on each machine |
| Repo operating instructions | tracked `AGENTS.md` | Claude import adapter and Codex native discovery |
| Runtime credentials and volatile state | client runtime | local auth/database/cache files |

Generated or installed files must name their source. Do not edit them directly.

Muse is the third harness: it installs the same plugin from a local bundle and reads the
same skills; its hooks run through `.muse-plugin/hooks/`.

## 2. Instruction discovery

Use `AGENTS.md` as the tracked, agent-neutral repository source. Claude Code
supports imports in `CLAUDE.md`; the adapter is:

```text
@AGENTS.md
```

At user scope, keep one authored instruction file and make each runtime read it where it
actually looks (Codex reads `~/.codex/AGENTS.md`; Claude Code reads `~/.claude/CLAUDE.md`).
Codex concatenates the user file and one instruction file per folder from the repository
root to the working folder, and truncates at `project_doc_max_bytes`; `synthesis doctor`
measures that chain against the limit minus a 4 KiB reserve.

## 3. Skill and plugin deployment

The public repository is a three-runtime plugin:

```text
.codex-plugin/plugin.json
.claude-plugin/plugin.json
.muse-plugin/plugin.json
skills/<skill>/SKILL.md
hooks/hooks.json
synthesis/            (the runtime the hooks run, installed to ~/.synthesis/v5/current)
```

Install it through each client’s marketplace (Muse: a local bundle). Private skills
remain user skills because they are not a public package:

- Claude: `~/.claude/skills`
- Codex and the Agent Skills convention: `~/.agents/skills`

Codex’s product-owned `.system` skills may remain under `~/.codex/skills`.
Source-managed public/private skills must not also be copied there.

## 4. Lifecycle controls

Share the behavior-producing code; adapt the hook configuration to each
runtime’s events and output schema. In v5 every hook calls one stable path,
`~/.synthesis/v5/bin/synthesis-hook <event>`, whose text never changes between
releases, so a harness's approval of a hook definition survives upgrades and a deleted
plugin version folder never breaks a running task.

Required properties:

- protective hooks fail closed when their dependencies cannot load;
- every hook source is version-controlled;
- health commands report source, installed state, live delivery, continuity,
  and capability as separate planes;
- plugin-relative paths replace absolute references to a project checkout;
- SessionStart establishes verified time and project state;
- post-compaction recovery reloads the active plan where supported;
- Stop/SessionEnd checks durable state without silently mutating unrelated repos.

Codex hook definitions outside managed policy require human hash review; Codex runs a
changed hook only after the person approves it in `/hooks`. Doctor reproduces Codex's
trust hash for each synthesis hook (pinned to hashes Codex itself stored) and reports
untrusted, modified or disabled hooks; it never writes Codex's trust state. Muse holds
the same decision behind `muse plugins approve`. A simulated hook event verifies a
script contract, not client delivery: doctor's self-test runs the real stable hook, and
a fresh session in each harness shows that SessionStart actually fired.

## 5. Durable project handoff

Tool-native memory is a cache. The portable record is:

```text
CONTEXT.md
REFERENCE.md
sessions/YYYY-MM.md
resources/artifacts/<active-plan>.md
projects/index.yaml
```

Each session's active project is in its own board file (`synthesis use <project>`);
there is no global active-project pointer. A receiving agent reads the project's
directive and current-state block (SessionStart injects them, and again after
compaction), verifies project path and git history, reads the current context and
plan, and resumes the recorded next action.

Concurrent root sessions add two invariants:

- every writing session owns non-overlapping resources (`synthesis claim`), in an
  isolated worktree when it changes code; and
- one session owns canonical project context while same-project contributors
  write separate reconciliation artifacts.

Session identity comes from the harness (`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`,
Muse's session id); the board gives each a six-character short name for addressing.
Resource claims stay separate from identity.

Tool-native threads remain views of the work. The synthesis project files and
verified git history remain the record.

## 6. Cross-machine synchronization

Synchronize canonical sources and stable declarative adapters. Do not use
timestamp-winner whole-file synchronization for client configuration that also
contains volatile marketplace data, trust hashes, caches, or machine-specific
paths. Apply an owned-key overlay and validate the merged runtime state (onboarding's
`setup.py` does this for Codex's `config.toml`).

Git provides durable cross-machine handoff: `synthesis handoff` commits and pushes the
records inside this session's claims, and the other Mac resumes from them. The board is
per Mac; it is not synchronized. Synced config writes home paths as `~`, never literally
(doctor checks).

## 7. Conformance contract

The ecosystem passes only when:

- instructions are discoverable without personal fallback filenames;
- each public skill appears once per client;
- private installed copies match source;
- every harness's plugin bytes equal the installed runtime, every hook is wired to
  the stable hook, every Codex hook is trusted and every Muse hook approved;
- instruction files retain budget headroom;
- Codex's full resolved catalog fits its model-dependent 2% budget through an
  implicit core, explicit specialists, and a natural-language routing skill;
- configured and authenticated connector states are named separately;
- the same project phase, status, plan, and next action are recovered in every
  client;
- active sessions have non-overlapping claims and isolated git state, with no
  more than one context owner per project;
- cross-machine setup reproduces canonical source and all required
  adapters without overwriting runtime-owned state.

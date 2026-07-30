# Cross-Agent Conformance Architecture

## Contents

1. Ownership
2. Instruction discovery
3. Skill and plugin deployment
4. Lifecycle controls
5. Durable project handoff
6. Cross-machine synchronization
7. Conformance contract

## 1. Ownership

| Behavior | Canonical owner | Deployment examples |
|----------|-----------------|---------------------|
| Public methodology and scripts | public skill repository | Claude/Codex plugin caches |
| Personal behavior and machine policy | private skill/config repository | user instructions, hooks, private skill directories |
| Project status and history | appropriate AI-knowledge repository | local clone on each machine |
| Repo operating instructions | tracked `AGENTS.md` | Claude import adapter and Codex native discovery |
| Runtime credentials and volatile state | client runtime | local auth/database/cache files |

Generated or installed files must name their source. Do not edit them directly.

## 2. Instruction discovery

Use `AGENTS.md` as the tracked, agent-neutral repository source. Claude Code
supports imports in `CLAUDE.md`; the adapter is:

```text
@AGENTS.md
```

At user scope, render the private canonical source into the locations each
runtime actually discovers. Generated files may differ where platform-specific
sections are intentional.

## 3. Skill and plugin deployment

The public repository is a dual-runtime plugin:

```text
.codex-plugin/plugin.json
.claude-plugin/plugin.json
skills/<skill>/SKILL.md
hooks/hooks.json
```

Install it through each client’s marketplace. Private skills remain user skills
because they are not a public package:

- Claude: `~/.claude/skills`
- Codex and the Agent Skills convention: `~/.agents/skills`

Codex’s product-owned `.system` skills may remain under `~/.codex/skills`.
Source-managed public/private skills must not also be copied there.

## 4. Lifecycle controls

Share the behavior-producing script; adapt the hook configuration to each
runtime’s events and output schema.

Required properties:

- protective hooks fail closed when their dependencies cannot load;
- every hook source is version-controlled;
- a health command verifies config, source, trust, and a simulated event;
- plugin-relative paths replace absolute references to a project checkout;
- SessionStart establishes verified time and project state;
- post-compaction recovery reloads the active plan where supported;
- Stop/SessionEnd checks durable state without silently mutating unrelated repos.

## 5. Durable project handoff

Tool-native memory is a cache. The portable record is:

```text
CONTEXT.md
REFERENCE.md
sessions/YYYY-MM.md
resources/artifacts/<active-plan>.md
projects/index.yaml
```

An active-project pointer may accelerate discovery, but it never overrides
those files. A receiving agent must verify the project path and git history,
read the current context and plan, and resume the recorded next action.

Concurrent root sessions add two invariants:

- every writing session owns non-overlapping resources in an isolated
  worktree/branch; and
- one session owns canonical project context while same-project contributors
  write separate reconciliation artifacts.

Tool-native threads remain views of the work. The synthesis project files and
verified git history remain the record.

## 6. Cross-machine synchronization

Synchronize canonical sources and stable declarative adapters. Do not use
timestamp-winner whole-file synchronization for client configuration that also
contains volatile marketplace data, trust hashes, caches, or machine-specific
paths. Apply an owned-key overlay and validate the merged runtime state.

Git provides durable cross-machine handoff. The default live coordination board
uses an OS file lock and is authoritative only for processes sharing that
filesystem. File synchronization does not provide distributed mutual
exclusion; simultaneous cross-machine writes to the same resources require a
separately verified compare-and-swap coordination backend.

## 7. Conformance contract

The ecosystem passes only when:

- instructions are discoverable without personal fallback filenames;
- each public skill appears once per client;
- private installed copies match source;
- hook health checks and simulated events pass;
- configured and authenticated connector states are named separately;
- the same project phase, status, plan, and next action are recovered in both
  clients;
- active sessions have non-overlapping claims and isolated git state, with no
  more than one context owner per project;
- cross-machine bootstrap reproduces the canonical plane and all required
  adapters without overwriting runtime-owned state.

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
- health commands report source, installed state, live delivery, continuity,
  and capability as separate planes;
- plugin-relative paths replace absolute references to a project checkout;
- SessionStart establishes verified time and project state;
- post-compaction recovery reloads the active plan where supported;
- Stop/SessionEnd checks durable state without silently mutating unrelated repos.

Codex hook definitions outside managed policy require human hash review. Query
the client-owned `hooks/list` response for the normalized current hash and trust
reason; do not duplicate its private hashing algorithm or write its trust file.
A simulated hook event verifies a script contract, not client delivery. Live
delivery requires a receipt from a real event payload and a matching
client-owned transcript. Claude Code may create the transcript after its
SessionStart hook returns, so receipt creation and transcript binding are a
two-phase assertion; conformance accepts it only after both are true. Claude
root-session evidence additionally requires the canonical
`projects/<encoded-cwd>/<session-id>.jsonl` shape because subagent transcripts
also carry their parent session UUID.

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
those files. It records the owning coordination session and lease URL,
worktree, branch, and source commit. A receiving agent must compare those fields
with disk, verify project path and git history, read the current context and
plan, and resume the recorded next action.

Concurrent root sessions add two invariants:

- every writing session owns non-overlapping resources in an isolated
  worktree/branch; and
- one session owns canonical project context while same-project contributors
  write separate reconciliation artifacts.

Coordination session identity is provider-neutral. The lease-backed board uses
a full UUIDv7 for durable ownership and stores compact Crockford Base32 plus
speakable word-number aliases derived from the same 60 random bits. Claude,
Codex, and other adapters accept any exact representation, resolve it to the
UUID, and keep resource claims separate from identity. Pre-v3 letters remain
explicit migration aliases only.

Tool-native threads remain views of the work. The synthesis project files and
verified git history remain the record.

## 6. Cross-machine synchronization

Synchronize canonical sources and stable declarative adapters. Do not use
timestamp-winner whole-file synchronization for client configuration that also
contains volatile marketplace data, trust hashes, caches, or machine-specific
paths. Apply an owned-key overlay and validate the merged runtime state.

Git provides durable cross-machine handoff. The coordination board is
lease-backed by a dedicated private repository ref and mutations use
compare-and-swap semantics. Local file locking protects same-machine writers;
the remote lease protects cross-machine writers. Mutations fail closed when the
remote is configured but unreachable. File synchronization alone is never a
distributed lock.

## 7. Conformance contract

The ecosystem passes only when:

- instructions are discoverable without personal fallback filenames;
- each public skill appears once per client;
- private installed copies match source;
- hook definitions pass, every enabled Codex hook is managed or human-trusted,
  and required clients have genuine live-event receipts;
- instruction files retain budget headroom and a verified tail sentinel;
- source and installed skill catalogs agree within their description budget;
- Codex's full resolved catalog fits its model-dependent 2% budget through an
  implicit core, explicit specialists, and a natural-language routing skill;
- configured and authenticated connector states are named separately;
- the same project phase, status, plan, and next action are recovered in both
  clients;
- active sessions have non-overlapping claims and isolated git state, with no
  more than one context owner per project;
- cross-machine bootstrap reproduces canonical source and all required
  adapters without overwriting runtime-owned state.

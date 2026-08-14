# Runtime integration contract

This document defines what a first-class synthesis runtime must expose and what
evidence an adapter must produce. It applies to Claude Code, ChatGPT Codex, and
other agent systems that support filesystem-backed work.

## Five evidence planes

Every check belongs to one plane. Reports must not turn an untested plane into
a pass.

| Plane | Question | Example evidence |
|---|---|---|
| Source | Is the canonical implementation internally valid? | manifests, schemas, unit tests, license and metadata checks |
| Installed | Did the intended version reach this client? | native plugin listing, immutable cache version, source-to-install hashes |
| Live | Did the client execute the behavior in a real session? | fresh client-specific hook receipt, actual skill registry response |
| Continuity | Can another session recover the work safely? | local edit manifests and receipts, durable project files, active pointer, lease ownership, remote publication receipts |
| Capability | Can the runtime perform the authenticated operation? | read-only connector handshake with timestamp and explicit status |

Statuses are `PASS`, `FAIL`, `UNKNOWN`, or `UNSUPPORTED`. `UNKNOWN` means the
probe could not establish the result. `UNSUPPORTED` means the product surface
does not provide the capability. Neither means pass.

## Skill discovery

The canonical skill is the `SKILL.md` tree. Client adapters may add discovery
metadata without changing the shared method.

- Follow the [Agent Skills specification](https://agentskills.io).
- Preserve precise trigger descriptions for clients that use them directly.
- Use `agents/openai.yaml` for Codex catalog presentation and implicit-invocation
  policy.
- Keep foundational execution and routing skills implicit. Keep specialists
  explicit when a full catalog would consume excessive model context.
- Report both discoverable and prompt-visible counts.
- Treat catalog truncation or description shortening as observable runtime
  state.

## Hooks and session lifecycle

Each adapter maps the shared intent to the client's native lifecycle. Exact
event names and envelopes may differ.

- Session start supplies current time, coordination state, active project,
  controlling plan, and integrity state without duplicating private context.
- Pre-tool guards make deny/allow decisions before mutation.
- Stop and session-end work stays within the client's documented timing and
  retry contract.
- Hook trust remains a human decision when the client requires review of
  executable hashes.
- A live receipt records client, event, plugin version, timestamp, and contract
  fields. One client's receipt cannot stand in for another's.
- Versioned plugin caches are updated at an explicit session boundary. An
  update must not replace hook commands under an active session.

Reference contracts:

- [OpenAI Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [OpenAI Codex plugins](https://learn.chatgpt.com/docs/plugins)
- [Anthropic Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Anthropic Claude Code plugins](https://code.claude.com/docs/en/plugins)

## Durable project continuity

A runtime integration reads and writes the same filesystem-backed project structure:

```text
projects/<slug>/
├── CONTEXT.md
├── REFERENCE.md
├── sessions/YYYY-MM.md
└── resources/artifacts/
```

The active-project pointer is a cache backed by a valid lease. Before accepting
it, verify the owning session, heartbeat, exact worktree, branch, commit, and
upstream freshness. Symlinks and unexpected archive roots fail closed.

Two sessions may work at once when they use different worktrees and
non-overlapping source claims. The coordination board is an advisory interface
backed by an atomic remote lease, not an invitation to edit the Markdown file
directly.

Continuity has two independently reported states. `LOCAL_READY` means the
project record and attributed working-tree edits are recoverable by another
client on the same filesystem; Stop must not commit or use the network.
`LOCAL_RECOVERABLE` means a successful edit manifest survived an interrupted
task even though no Stop receipt exists. `REMOTE_READY` additionally requires
source repositories and exact-path project-context commits to be clean and
equal to fetched upstreams, with no pending manifests. Day-end and explicit
remote-handoff sync create that state; a local pass may never be presented as a
cross-machine pass.

## Capability probes

Capability parity is about outcomes, not identical tool names. A probe should
answer whether the client can read a repository, recover a project, inspect a
workspace, or authenticate to an approved connector.

- Prefer read-only handshakes.
- Never send a message, create an event, or mutate external state as a health
  check.
- Record the product surface separately: desktop app, CLI, and IDE are not
  interchangeable.
- Identify authentication failures separately from missing product support.
- Sanitize connector output before saving shared evidence.

## Onboarding and updates

A compatible runtime should support an idempotent installation path and a
doctor path that does not mutate an existing plugin cache.

1. `install` converges missing configuration without replacing a live cache.
2. `doctor` reads source, installed state, and live evidence separately.
3. `update` is explicit. Close active sessions, checkpoint work, update through
   each client's native command, and start new sessions afterward.
4. Installed copies are never edited as source.
5. Local modifications are archived recoverably before replacement.

## Adding another runtime

An adapter for Hermes Agent, Cursor, or another capable client should provide:

1. native skill discovery or a documented Agent Skills bridge;
2. lifecycle mapping for session context and pre-mutation guards;
3. source-to-installed version evidence;
4. live receipts that cannot be synthesized by static tests;
5. durable-project and lease support;
6. read-only capability probes;
7. an explicit supported-surface table;
8. regression fixtures for offline, stale-cache, bad-authentication, timeout,
   and destructive-target failures.

The adapter earns first-class status when all required planes pass on a fresh
normal session. Product documentation or a successful source test alone is not
enough.

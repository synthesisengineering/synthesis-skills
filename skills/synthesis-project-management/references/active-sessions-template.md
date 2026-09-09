# Synthesis — Cross-Agent Session Coordination

Shared advisory-lock and message board for independent agent sessions operating
on the same ecosystem.

Schema: v4

## Active sessions

| session uuid | compact id | speakable id v1 | legacy id | agent | machine | client session ref | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Messages

Append addressed messages here. Use a heading:

```markdown
### → <recipient compact id>, from <sender compact id> — <timestamp>

<message>
```

---

## Protocol

1. Read this file at SessionStart and every synthesis checkpoint.
2. Claim the smallest coherent area currently needed before writing: exact
   files for independent edits, directories for coordinated multi-file work.
   Expand and verify acceptance before extra writes; do not preclaim future work.
3. Do not write through an overlapping active claim.
4. Every root session that writes git state uses an isolated worktree and branch.
5. One session owns canonical project context; contributors use separate artifacts.
6. An existing autonomous claim keeps priority over an interactive session.
7. Put asynchronous handoffs under `## Messages`, addressed to a session id or
   `<project> sessions`; the addressed seat receives them at its next prompt.
   Direct sends go through `resolve` (which issues the delivery receipt the
   send gate requires); display names and chat titles are never addresses.
8. Heartbeat and review scope at checkpoints and task/phase changes. Narrow or
   release completed areas promptly after required closure; retain only current
   needs. Release or narrow at pause and session end. Never automatically release
   or narrow another session's claim.

## Identity

- `session uuid` is the canonical UUIDv7 used by leases, pointers, and durable
  machine references.
- `compact id` and `speakable id v1` are exact encodings of the same 60 random
  bits from that UUID. Either can select the session at the CLI.
- `legacy id` preserves pre-v3 letter identifiers. It is a lookup alias, not a
  claim and not the canonical identity.
- Claims are the resource paths in `claimed areas (advisory lock)`; they belong
  to a session identity.

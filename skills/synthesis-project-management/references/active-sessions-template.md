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
2. Claim source-area globs before writing.
3. Do not write through an overlapping active claim.
4. Every root session that writes git state uses an isolated worktree and branch.
5. One session owns canonical project context; contributors use separate artifacts.
6. An existing autonomous claim keeps priority over an interactive session.
7. Put asynchronous handoffs under `## Messages`, addressed to a session id or
   `<project> sessions`; the addressed seat receives them at its next prompt.
   Direct sends go through `resolve` (which issues the delivery receipt the
   send gate requires); display names and chat titles are never addresses.
8. Heartbeat at checkpoints; release or narrow claims at pause and session end.

## Identity

- `session uuid` is the canonical UUIDv7 used by leases, pointers, and durable
  machine references.
- `compact id` and `speakable id v1` are exact encodings of the same 60 random
  bits from that UUID. Either can select the session at the CLI.
- `legacy id` preserves pre-v3 letter identifiers. It is a lookup alias, not a
  claim and not the canonical identity.
- Claims are the resource paths in `claimed areas (advisory lock)`; they belong
  to a session identity.

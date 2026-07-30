# Synthesis — Cross-Agent Session Coordination

Shared advisory-lock and message board for independent agent sessions operating
on the same ecosystem.

Schema: v2

## Active sessions

| id | agent | machine | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |
|---|---|---|---|---|---|---|---|---|---|---|---|

## Messages

Append addressed messages here. Use a heading:

```markdown
### → <recipient session>, from <sender session> — <timestamp>

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
7. Put asynchronous handoffs under `## Messages`.
8. Heartbeat at checkpoints; release or narrow claims at pause and session end.

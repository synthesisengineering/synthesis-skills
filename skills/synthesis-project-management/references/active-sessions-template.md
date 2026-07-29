# Synthesis — Cross-Agent Session Coordination

Shared advisory-lock and message board for independent agent sessions operating
on the same ecosystem.

## Active sessions

| id | agent | started | mode | goal | claimed areas (advisory lock) | status |
|----|-------|---------|------|------|--------------------------------|--------|

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
4. An existing autonomous claim keeps priority over an interactive session.
5. Put asynchronous handoffs under `## Messages`.
6. Release or narrow claims at pause and session end.

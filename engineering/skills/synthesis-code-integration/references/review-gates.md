# Code integration: review gates

What every contribution must pass before integration, and the checks that keep standards from drifting.

## Quality Gates

Every contribution must pass these gates before integration.

### Meta-Principle: Zero Accepted Failures

Every test must pass. Every lint error must be clean. No exceptions for "pre-existing" or "known" failures.

When you encounter a failing test you didn't cause, fix it — right then, in the same branch. The distinction between "my failure" and "someone else's failure" is irrelevant; the only question is whether the suite is green when you're done.

**Why:** A test suite with accepted failures is a broken smoke detector. It cannot tell you whether your change is safe. Every "known failure" you walk past teaches the next engineer that failing tests are normal. This is how test suites die — not in one catastrophic event, but through gradual normalization of red.

**The cost argument:** Fixing a pre-existing failure while you're already in the code costs minutes. Coming back later after context is lost costs hours. The cheapest time to fix is always now.

**The campsite rule for code:** Leave the test suite greener than you found it. If you touched the codebase, you own its health when you leave.

### Gate 1: Completeness

- Feature is fully implemented (not half-frontend, half-backend)
- No dead code, no references to methods that do not exist
- No dependency on unreleased or unmerged work
- Tests exist for new backend logic

### Gate 2: Security

- Privileged operations produce audit log entries
- Auth tokens handled correctly (claims propagated through refresh, appropriate expiry)
- Rate limiting on sensitive endpoints
- No credentials or secrets hardcoded in code
- Input validation at system boundaries
- User data exposure reviewed (no unnecessary information leakage)

### Gate 3: Architecture

- One feature per branch (no bundled unrelated changes)
- Follows existing codebase patterns (component structure, API client usage, error handling)
- Uses framework features properly (not fighting the framework with workarounds)
- No regression of existing functionality
- No unnecessary complexity

### Gate 4: Project-Specific Standards

These vary by project. The contributor guide should document these. If a standard is not documented and a contributor violates it, that is the lead's responsibility to document — not the contributor's fault.

---

## Convention Review Checklist

Contributors using AI coding tools produce code that is functionally correct but drifts from project-specific conventions.

### Standard Items (Every Project)

1. **Correctness** — edge cases, race conditions, error paths
2. **Existing pattern adherence** — matches codebase conventions
3. **Test coverage** — new backend logic has tests; existing tests still pass
4. **Security** — audit logging, auth handling, input validation

### Project-Specific Items (Define Per Project)

These are the conventions that AI tools miss because they do not exist in training data:
- Brand terminology compliance
- AI messaging rules
- CSS/UI framework conventions
- Role-based access patterns

Add this checklist to the project's contributor guide. Make it a formal gate, not an optional pass.

---

## Critical Config Regression Guards

When a configuration value is deliberately upgraded (e.g., thinking effort from "high" to "max", or token budgets from 16K to 24K), add a test that asserts the new value and will fail if it's reverted.

### Why This Exists

Cherry-picks from older branches carry the old config values. A merge conflict in a config file can resolve to the older value. A contributor who copies a config pattern from their older branch silently downgrades the value. None of these trigger test failures because the old value is "valid" — it just produces worse results.

### The Pattern

```python
def test_thinking_effort_is_max(self):
    """Content generation MUST use max thinking effort.

    Downgrading to 'high' causes thinking-phase exhaustion on complex
    articles. See incident 2026-03-30.
    """
    assert THINKING_CONFIG["content"]["output_config"]["effort"] == "max", (
        "CRITICAL: Content thinking effort was downgraded from 'max'. "
        "If intentional, update this test with justification."
    )
```

### When to Add Config Guards

Add a guard test whenever you:
- Upgrade a thinking/reasoning effort level
- Raise token budgets or context limits
- Change a model selection (e.g., from Sonnet to Opus for a task)
- Enable a feature flag that affects output quality
- Change a retry count, timeout, or resilience parameter

The test comment must explain WHY the value matters, not just WHAT it is. A future developer encountering a failing guard test needs to understand the consequences of the old value before deciding to change it.

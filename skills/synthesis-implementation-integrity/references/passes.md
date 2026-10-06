# The seven integrity passes and the quick check

The risk catalog, as written in 1.4.1: what each pass catches, how to run it, and its challenge question, then the five-minute check for smaller changes.

Contents:
- Pass 1: Chain Completeness (origin to presentation)
- Pass 2: Placeholder and Deferral Detection (code markers, language signals, hardcoded values)
- Pass 3: Test Honesty (steps 1 to 6, including separating skipped from passed)
- Pass 4: Environment Parity
- Pass 5: Diminishing Attention Audit
- Pass 6: Companion Change Completeness
- Pass 7: Boundary Verification
- Quick Integrity Check (5 minutes)

## The Seven Integrity Passes

These passes are a risk catalog. Apply the relevant ones to the complete changed
behavior; do not turn every invocation into seven new reports.

### Pass 1: Chain Completeness

**Catches:** Missing links in data flows, values computed but never stored, fields added at one layer but missing at another, state changes that don't propagate to every consumer.

Every piece of data in a software system flows through a chain of layers. The specific layers vary by architecture, but the principle is universal: **if you add or modify data at any layer, every downstream layer must also handle it.**

Trace every new or modified data element through its full lifecycle:

| Link | Question | How to verify |
|------|----------|---------------|
| **Origin** | Where is the value first created or received? | Read the function that produces it |
| **Transport** | How does it move between layers? | Check return values, payloads, events, props, context |
| **Validation** | Is it validated where it enters the system? | Check entry points for validation logic |
| **Transformation** | Is it transformed correctly at each boundary? | Check serializers, mappers, adapters, formatters |
| **Storage** | Is it persisted correctly? | Check the schema, model, AND the migration |
| **Retrieval** | Can it be read back accurately? | Check queries, selectors, fetchers include the field |
| **Presentation** | Does it reach the end user or consumer? | Check UI components, API responses, reports, exports |

**The critical test:** Search for the new field or function name across the entire codebase. Every layer that handles the entity should reference it. A layer that doesn't is a broken link — even if everything else works.

**Challenge question:** "For every new data element I introduced, can I name every file that touches it and confirm each one handles it correctly?" If you can't name them from memory, search for them. If you find fewer references than expected, something is missing.

### Pass 2: Placeholder and Deferral Detection

**Catches:** TODO comments, stub implementations, "for now" compromises, hardcoded values, temporary workarounds that become permanent.

Search all changed files for these patterns:

**Code markers:**
```
TODO, FIXME, HACK, XXX, TEMP, TEMPORARY
NotImplementedError, raise NotImplementedError
pass  (as sole function body)
unimplemented!(), todo!()  (Rust)
throw new Error("not implemented")
// stub, # stub, /* stub */
```

**Natural language signals in comments:**
- "for now" — a known compromise the author planned to revisit
- "temporary" or "quick fix" — intent to replace that almost never happens
- "should be" or "ought to" — awareness of the right approach that wasn't taken
- "works but" — acknowledged limitations
- "revisit" or "come back to" — explicitly deferred work

**Hardcoded values that should be configuration:**
- Magic numbers without named constants
- URLs, endpoints, or email addresses in source code
- Credentials or tokens in source (should be environment variables)
- Feature flags set to literal `true`/`false`

**For each finding:** Is this an intentional scope boundary or an accidental omission? Intentional boundaries should have documentation explaining the decision. A bare `TODO` is not documentation — it's a placeholder for documentation.

**Challenge question:** "If a senior engineer reviewed this code with no context, would any line make them ask 'is this finished?' or 'why is this hardcoded?'" If yes, address it now or document why it's intentional.

### Pass 3: Test Honesty

**Catches:** Tests that exist but don't verify the change, tests that pass because they mock the critical parts, false confidence from green suites.

**Core question:** Do the tests that "cover" this change actually execute the code path that could fail in production?

**Step 1: Identify the risky code path.** The path most likely to fail in production. Usually involves database commits, external API calls, file system operations, or environment-specific configuration.

**Step 2: Read the tests that cover this path.** For each test, ask:
- Does it use the real implementation, or mock the critical dependency?
- Does it commit to a real database, or roll back before the commit that would expose schema mismatches?
- If it mocks a dependency, does the mock faithfully reproduce production behavior — including error cases?
- Does it test only the success path, or both success and failure?

**Step 3: Check for the mock gap.** If the service layer is mocked in route tests, those tests cannot verify that the service and route interact correctly. This is where integration tests matter — and where they're most often absent.

**Step 4: Check test naming vs. test behavior.** A test named `test_create_output_with_timing` that never asserts on a timing value is a false signal. The name implies coverage that doesn't exist.

**Step 5: Check discrimination.** Determine whether existing assertions would
catch the relevant defect in the changed path. Unchanged tests can provide valid
coverage, including a regression test that fails before the fix and passes after
it. Test-file changes are neither necessary nor sufficient evidence. Add or
repair assertions only where coverage is missing or dishonest.

**Step 6: Separate skipped from passed.** "X passed, Y skipped, 0 failed" is not the same claim as "tests pass" — it's "the tests that ran didn't fail, and some tests didn't run at all." A skip is an absence of information, not a green light. Read what was actually skipped, not just the aggregate count, and ask specifically: could the skipped set contain the one test that validates the exact property this decision depends on? For a cosmetic or environment-gated test, a skip is usually neutral. For a security, data-integrity, or irreversibility claim, it isn't — if the answer isn't a confident no, go run the skipped test before treating the suite as passing.

*Field case:* a suite reporting "911 passed, 29 skipped, 0 failed" read as green. The 29 skips were exactly the tests gated behind a live database connection — including the one test that validated a workspace-isolation security control. When that test finally ran, it failed: the isolation was silently a no-op, because the connecting database role carried a built-in bypass for the exact policy meant to enforce it. Nothing in the aggregate summary surfaced this — the one test that would have caught it was simply never executed.

**Challenge question:** "If I deleted the implementation I just wrote but left the tests, would any test fail?" If no test would fail, the tests don't actually cover the change. And separately: "Of everything that was skipped, could any of it have been the test that mattered?"

### Pass 4: Environment Parity

**Catches:** "Works on my machine" failures caused by differences between dev, test, staging, and production.

| Gap | What breaks | How to check |
|-----|-------------|--------------|
| Test DB is fresh, prod DB is persistent | Missing migrations, missing columns | Verify ALTER TABLE/migration for every schema change |
| Test uses SQLite, prod uses PostgreSQL | Type differences, dialect issues | Check for DB-specific syntax or behavior |
| Dev has local filesystem, prod has cloud storage | Path errors, permission failures | Check for hardcoded paths or local-only assumptions |
| Dev has all env vars, CI/CD may not | Missing configuration | Verify deployment config includes new variables |
| Dev runs one instance, prod runs multiple | Race conditions, shared state | Check for in-memory state that should be in a shared store |
| Dev has current code, CDN serves cached assets | Stale JS/CSS after deploy | Check cache-busting for changed static assets |
| Dev logs to console, prod logs to aggregator | Missing structured fields | Verify log format matches prod expectations |

**The key question:** What assumptions does this code make about its runtime environment, and do those assumptions hold in every environment where it will run?

**Challenge question:** "If I deployed this to a brand-new environment right now, what would break before a user could successfully use this feature?" Walk through the first request mentally — from DNS to response.

### Pass 5: Diminishing Attention Audit

**Catches:** Errors in the last item of a series, copy-paste mistakes, incomplete implementations hidden by confidence from earlier successes.

When the same pattern is implemented across multiple components (three services, four endpoints, five models), cognitive attention follows a predictable curve:

- **First implementation:** High attention, careful work
- **Middle implementations:** Moderate attention, pattern-following
- **Last implementation:** Low attention, false confidence from earlier successes

This is not a character flaw — it's a documented cognitive pattern. Experienced engineers and AI agents both exhibit it.

**The protocol:**

1. Identify the last component that was implemented in the series
2. Verify it with FIRST-item diligence — read line by line, don't pattern-match
3. Check that names, types, and references are correct for THIS component, not a previous one (copy-paste errors leave the previous component's identifiers in place)
4. If the last item touches fewer files than the first, ask why — fewer files may mean skipped steps, not simpler requirements
5. Count the layers completed for the last item against the first — every layer the first item has, the last item should also have

**The heuristic:** The Nth implementation in a series of N is the most likely to have a bug. Give it more scrutiny, not less.

**Challenge question:** "Am I confident about the last implementation because I verified it, or because the first two worked?" If the answer is the latter, that confidence is borrowed, not earned.

### Pass 6: Companion Change Completeness

**Catches:** Backend changes without frontend updates, code changes without config updates, feature additions without documentation or monitoring.

Most non-trivial changes require companion changes elsewhere in the system:

| Primary change | Expected companion |
|---------------|-------------------|
| New API endpoint | Client code, API docs, auth configuration |
| New database field | Migration, serialization, UI display, API response |
| New environment variable | Deployment config, CI/CD config, documentation |
| Backend logic change | Updated error messages, updated UI states |
| New feature | Feature flag config, monitoring, alerting |
| Dependency upgrade | Lock file update, compatibility checks |
| API contract change | Client library update, versioning |
| New error type | Error handling in callers, user-facing message |

**Verification:** For each file changed, ask: "What other files would a fully complete implementation of this change require?" Then check whether those files were also changed. If not, determine whether they were unchanged because they didn't need changing, or because the change was forgotten.

**Challenge question:** "If I handed the list of changed files to another engineer and asked 'is anything missing?', would they spot a gap I missed?" Mentally role-play the conversation.

### Pass 7: Boundary Verification

**Catches:** Invalid assumptions where your code meets external systems, user input, or other services.

System boundaries are where controlled internal code meets uncontrolled external reality. Verify every boundary the change touches:

- **User input:** Validated before use? Error messages helpful without leaking internals?
- **Outbound APIs:** What happens when the external service is slow, returns unexpected data, or is unavailable?
- **Inbound APIs:** New endpoints authenticated? Request format validated?
- **Database:** Queries parameterized? Transactions used where atomicity is required?
- **File system:** Paths validated? Behavior defined for missing files?
- **Configuration:** Behavior defined for missing values? Sensible defaults or clear errors?

**Challenge question:** "What is the worst thing an external system could send me, and does my code handle it without crashing, leaking data, or corrupting state?"

## Quick Integrity Check (5 minutes)

For smaller changes that don't warrant all seven passes, run this condensed version:

1. **Grep the new field/function name** across the full codebase — is it referenced in every layer it should be?
2. **Search changed files** for `TODO`, `FIXME`, `for now`, `temporary`, `stub`
3. **Read the most critical test** — does it exercise the actual code path, mock it away, or was it skipped entirely? A skip is not a pass.
4. **Ask:** "If I deploy this to a fresh environment, what would I need to configure for it to work?"
5. **If this is the Nth implementation in a series:** re-read the Nth one as carefully as the first

If a check exposes a gap, run the passes and consumer checks that resolve that gap. Broaden when its cause affects more of the system; do not automatically restart every pass.

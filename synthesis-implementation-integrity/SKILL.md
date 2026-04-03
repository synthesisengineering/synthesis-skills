---
name: synthesis-implementation-integrity
description: "Post-implementation verification protocol that catches incomplete work, hidden shortcuts, and gaps between 'tests pass' and 'production works.' Systematically traces data chains, detects placeholders, audits test honesty, and verifies environment parity. Use when asked to: verify implementation, check completeness, implementation review, is this done, built properly, no shortcuts, verify work, completion check, integrity check, self-review, pre-PR check, ship check."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
  source_type: "public"
---

# Synthesis Implementation Integrity

The most dangerous moment in software development is when you believe you're done. That belief shuts down scrutiny exactly when scrutiny matters most.

This skill is an adversarial self-review protocol. It challenges you — human or AI agent — to systematically prove your implementation is complete rather than assuming it is. The discipline: look for evidence that the work is WRONG, not confirmation that it's right. Confirmation bias is the default mode; this protocol overrides it.

"Tests pass" is not proof of correctness. Tests create their own world — fresh databases, mocked dependencies, controlled inputs. Production is a different world with persistent state, real external services, cached assets, and environment configurations that no test suite reproduces. The gap between "tests pass" and "production works" is where the worst failures live, because everyone has stopped looking.

This protocol exists to keep looking.

---

## When to Invoke

Run this protocol:

- **After completing any non-trivial implementation** — before declaring it done
- **After adding a field, column, or property** that flows through multiple system layers
- **After implementing the same pattern across multiple components** — the last one gets the least attention
- **After all tests pass on a schema, config, or deployment change** — for these change types, "all tests pass" should trigger deeper scrutiny, not signal that verification is over
- **When someone (human or AI) says "it's done"** — use this to give an evidence-based answer

Skip for trivial changes (typo fixes, comment updates, single-line config edits).

---

## Where This Fits — Three Verification Scopes

Three complementary skills cover verification at different scopes. Each has a distinct purpose and cadence:

| Skill | Scope | Cadence | Core question |
|-------|-------|---------|---------------|
| **synthesis-implementation-integrity** (this one) | A single change | After every non-trivial implementation | "Is this change genuinely complete?" |
| **synthesis-pr-review** | A change proposed for merge | Every pull request | "Should this change enter the codebase?" |
| **synthesis-codebase-review** | The entire system | Periodic or at milestones | "Is this system healthy?" |

**The natural flow:** Implement → self-verify (this skill) → peer review (pr-review) → periodic health check (codebase-review).

**When to use both this skill and codebase-review:** After a major feature that touches many system layers. Run this skill to verify the feature itself is complete. Then run relevant sections of codebase-review (security, architecture, testing) to verify the feature doesn't degrade overall system health.

**The critical difference:** Codebase-review evaluates the system as-is. This skill evaluates the delta between what was and what should now be. Codebase-review might give the system a clean bill of health while this skill reveals that the specific change you just made has a missing link. They catch different classes of problems.

---

## The Adversarial Mindset

Before running the seven passes, answer this honestly:

**Would you stake your professional reputation on this implementation? Would you deploy it at 5 PM on a Friday, confident nothing will page you at 2 AM?**

If the answer is "yes, but I haven't actually checked X" — that's not confidence, it's hope. This protocol replaces hope with evidence.

The discipline: **you are not verifying that the work is correct. You are trying to prove it is wrong.** If a genuine adversarial search finds nothing, that's meaningful. A casual glance that finds nothing is just confirmation bias.

Five rules for honest self-review:

1. **Distrust your memory of what you did.** Read the actual files. Your recollection of "I added that column" is not evidence the column exists. Open the file and check.

2. **Distrust passing tests.** Ask what the tests actually exercise. A test that mocks the layer where the real risk lives is not evidence of correctness for that layer.

3. **Distrust the last implementation in a series.** Cognitive fatigue makes the Nth item the most error-prone. It gets the least scrutiny and deserves the most.

4. **Distrust "it compiles."** Compilation proves syntax. It does not prove that data flows to the right place, that schemas are migrated, that configuration is complete, or that the production environment matches your assumptions.

5. **Distrust your own confidence.** The feeling of "this is obviously fine" is a signal to look harder, not to stop looking. Obvious failures don't survive to production — it's the non-obvious ones that do.

---

## The Seven Integrity Passes

Work through each pass in order. Each targets a specific, well-documented failure mode. Read the description before deciding to skip — the most dangerous gaps are the ones that seem irrelevant.

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

**Step 5: Apply the suspicion rule.** If all tests pass without any test modifications after a change that affects data storage, external integrations, or system boundaries, the tests almost certainly don't cover the change. A change that's genuinely tested usually requires at least one new assertion.

**Challenge question:** "If I deleted the implementation I just wrote but left the tests, would any test fail?" If no test would fail, the tests don't actually cover the change.

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

---

## Quick Integrity Check (5 minutes)

For smaller changes that don't warrant all seven passes, run this condensed version:

1. **Grep the new field/function name** across the full codebase — is it referenced in every layer it should be?
2. **Search changed files** for `TODO`, `FIXME`, `for now`, `temporary`, `stub`
3. **Read the most critical test** — does it exercise the actual code path, or mock it away?
4. **Ask:** "If I deploy this to a fresh environment, what would I need to configure for it to work?"
5. **If this is the Nth implementation in a series:** re-read the Nth one as carefully as the first

If any of these raises a question, run the full seven passes.

---

## Domain-Specific Checks

Apply the relevant section based on what the change involves.

### Database / ORM

The most common "tests pass, production breaks" pattern: test databases are created fresh from model definitions. Production databases have persistent schemas. A new column that appears automatically in test databases requires an explicit migration in production. No migration means no column means production crash — with a green test suite.

- [ ] Every new column exists on the model AND has a migration for existing tables
- [ ] Column types match between model definition and migration
- [ ] Nullable vs. non-nullable is intentional; non-nullable columns have a default or data migration
- [ ] Indexes exist for columns used in WHERE, ORDER BY, or JOIN clauses
- [ ] Migration is idempotent (safe to run more than once)
- [ ] Rollback path exists or the change is explicitly forward-only
- [ ] If all tests pass without test modifications after adding a column, ask why — tests probably don't exercise the write path

### API

- [ ] New endpoints have authentication and authorization checks
- [ ] Request validation exists for all user-supplied input
- [ ] Response format is consistent with existing endpoints
- [ ] Error responses follow established patterns
- [ ] Rate limiting applies if the endpoint is externally accessible
- [ ] API documentation is updated

### Frontend / UI

- [ ] Loading state exists (not just the "data loaded" state)
- [ ] Error state exists (not just the happy path)
- [ ] Empty state exists (what shows when there's no data?)
- [ ] Responsive behavior works if the project requires it
- [ ] Interactive elements are keyboard-accessible
- [ ] Static asset changes have cache-busting in place

### Configuration & Deployment

- [ ] New environment variables are documented with expected values
- [ ] Deployment configuration includes new variables
- [ ] Secrets use the project's secret management, not config files
- [ ] Feature flags have defined defaults for all environments
- [ ] Infrastructure-as-code is updated if infrastructure changed

---

## The Integrity Report

After running the passes, produce this report:

```
## Implementation Integrity Report

**Change:** [One-line description]
**Date:** YYYY-MM-DD

### Verdict: PASS / ISSUES FOUND / INCOMPLETE

### Passes Completed
- [x] Chain Completeness
- [x] Placeholder Detection
- [x] Test Honesty
- [x] Environment Parity
- [ ] Diminishing Attention (single implementation — not applicable)
- [x] Companion Changes
- [x] Boundary Verification

### Findings

| # | Pass | Finding | Severity | Action |
|---|------|---------|----------|--------|
| 1 | Chain | `timing_seconds` not on OutputModel | Critical | Add column to model |
| 2 | Environment | No migration for existing output table | Critical | Add idempotent ALTER TABLE |
| 3 | Test Honesty | No test asserts on timing value | Medium | Add assertion |

### Verdict Notes
[Brief explanation of verdict and any caveats]
```

**Severity:**
- **Critical** — production will break or data will be lost
- **High** — production may break under specific, realistic conditions
- **Medium** — functionality degraded but not broken
- **Low** — quality or maintainability concern, not a runtime issue

---

## Anti-Patterns This Protocol Prevents

### "Tests Pass, Ship It"
Treating a green test suite as proof of production-readiness. Tests verify test scenarios. They cannot catch environment gaps, missing migrations, or code paths they don't exercise. A green suite after a schema change with zero test modifications is a warning, not a clearance.

### "I Did the First Two Right, So the Third Is Fine"
Cognitive attention degrades with repetition. The last implementation in a series inherits confidence from earlier successes without inheriting the diligence. The diminishing attention audit catches what familiarity breeds.

### "I'll Come Back to This"
TODO comments and "for now" compromises have an expected lifespan of forever. Code ships with the deferral, the deferral becomes the implementation, and nobody comes back. If it's not acceptable as permanent code, it's not acceptable to ship.

### "The Pattern Is the Same, I Just Copy It"
Copy-paste across components introduces component-specific errors — wrong table names, wrong field types, references to the previous component. The pattern may be identical, but every proper noun changes.

### "It Compiles, Therefore It Works"
Compilation checks syntax and type safety. It does not check that the right data flows to the right place, that migrations exist, that configuration is complete, or that the production environment matches the assumptions the code makes.

---

## Relationship to Other Skills

This skill forms a verification trio with two others. Together they cover all three scopes of code quality:

| Skill | Scope | Who runs it | Analogy |
|-------|-------|-------------|---------|
| **implementation-integrity** (this) | Single change | The implementer, on their own work | A pilot's pre-flight checklist |
| **synthesis-pr-review** | Change proposed for merge | A peer reviewer | An inspector's acceptance test |
| **synthesis-codebase-review** | Entire system | An auditor or lead | An annual structural inspection |

**The handoff:** Run this skill before creating a PR. It catches the issues you'd be embarrassed to have a peer find. Then pr-review catches what you missed from an external perspective. Codebase-review catches systemic patterns that no single change reveals.

Other related skills:

| Skill | Relationship |
|-------|-------------|
| **synthesis-code-planning** | Plans the approach before implementation; this skill verifies the result after |
| **synthesis-code-integration** | Verifies the merge is safe; this skill verifies the implementation is complete before merge |

This skill is the bridge between "I wrote the code" and "I'd stake my reputation on it." Run it before the code leaves your hands.

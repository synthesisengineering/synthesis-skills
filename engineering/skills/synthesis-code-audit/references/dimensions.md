# Code audit: the ten dimensions

What to check under each dimension. Grade each one PASS, WARNING, FAIL or UNKNOWN using the scale in SKILL.md.

### 1. Project Convention Compliance

Read the project's convention documentation (style guides, architectural decision records, contribution guidelines). Check every changed file against the conventions that apply to it. Flag violations with a reference to the specific convention.

If the project has no documented conventions, skip this dimension and note it as N/A.

### 2. Code Reuse — Existing Before New

When the diff introduces a new component, utility, hook, or abstraction, search the codebase for existing implementations that serve the same purpose. If one exists, flag the new code and recommend using the existing implementation.

When the diff introduces a behavioral pattern (overlay management, keyboard navigation, positioning logic, state machine, API wrapper, error handling), search the broader codebase for functionally similar implementations — different code serving the same purpose is still duplication.

When multiple implementations of the same pattern are found, recommend extracting a shared primitive and migrating callers.

For any shared primitive — existing, introduced in this diff, or recommended for extraction — check whether the project's conventions document it. Undocumented shared primitives will be re-implemented by contributors who do not know they exist.

### 3. Consistency with Existing Patterns

Read 2-3 neighboring files in the same directory or module as each changed file. Note their naming conventions, file structure, export style, error handling approach, and architectural patterns.

Compare the diff against those observed patterns. Flag divergences that are not justified by the change's purpose.

### 4. Security

- Auth checks on all new endpoints
- No injection vectors (SQL injection, XSS, command injection)
- Input validation at system boundaries
- No secrets, credentials, or sensitive data in code, logs, or error messages
- ORM queries preferred over raw SQL (unless justified)

### 5. Scalability & Enterprise Readiness

- Efficient database queries (proper indexes, no N+1, pagination)
- Async patterns used correctly
- Proper logging for observability
- Resource cleanup (connections, file handles, subscriptions)

### 6. Future-Proofing (Without Over-Engineering)

- Extensible where extension is likely
- Migration-safe database changes
- Clean interfaces that do not leak implementation details
- No abstractions for hypothetical requirements

### 7. Code Quality

- DRY — no literal code duplication (copy-pasted blocks, repeated logic). Semantic duplication (different code serving the same purpose) belongs to Dimension 2.
- Single responsibility
- Readable and self-documenting
- Proper error handling at boundaries
- Type safety

### 8. Test Coverage

- New behavior has corresponding test additions or updates (or a clear reason why not)
- Existing test files were not removed or gutted without replacement
- Edge cases and error paths have test coverage

### 9. Documentation & Comments

- No project-management artifacts in code comments (plan phases, ticket numbers, sprint references)
- No stale comments from refactoring
- Complex logic has a "why" comment

### 10. Cleanup

- No dead code, unused imports, or leftover debug statements
- No TODO comments without context
- No commented-out code blocks
- Consistent formatting

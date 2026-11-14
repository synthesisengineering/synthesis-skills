# Domain-specific checks

Checklists for database and ORM, API, frontend and UI, and configuration and deployment changes, as written in 1.4.1.

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
- [ ] Existing or new tests exercise the changed write/read path and migration against persistent state; inspect assertions and execution, not whether test files changed

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

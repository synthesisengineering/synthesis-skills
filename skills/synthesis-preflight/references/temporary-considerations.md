# Preflight: the temporary considerations pattern

How to track workarounds so that dimension 5 can check them.

## The Temporary Considerations Pattern

This pattern is worth explaining because most projects do not formalize it, and workarounds accumulate silently as a result.

### What to Track

- Workarounds for known bugs in dependencies or infrastructure
- Feature flags that were meant to be temporary
- Hardcoded values that should come from configuration after a specific migration
- Compatibility shims for deprecated APIs
- Any code with an implicit expiration date

### Entry Format

Each tracked consideration should include:

- **Description** — what the workaround does and why it exists
- **Reason it is temporary** — what event or change will make it unnecessary
- **Resolution verification** — a concrete, checkable condition (a file is deleted, a config key exists, a dependency version is above X, a feature flag is removed)
- **Proposed exclusions** — identify the affected requirement, its decision owner and any applicable grant. Record failures once without suppressing their blocking consequence. No exclusion arises merely from being listed here.

### Why Preflight Checks This

Workarounds that are not tracked and not checked tend to become permanent. Preflight auto-cleaning resolved entries prevents accumulation. The developer who resolves the underlying issue may not remember every workaround it affects — preflight remembers for them.

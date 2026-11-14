# Preplan: background

Why the skill exists and where it sits among its sibling skills, as written in 1.1.0.

## Why decisions come first

The skill exists because the hard part of planning is **deciding what to build**, not breaking the build into commits. Once architectural decisions are locked, the commit-by-commit plan is mechanical. This skill makes the decision-locking explicit so your planner inherits a clear, reviewable input instead of designing inside its own output.

### Where this sits

This skill runs **before** any code exists, on the architectural layer: which base branch, what's in and out of scope, and the design questions a competent engineer could answer more than one way. Two siblings sit next to it:

- `synthesis-code-planning` evaluates **code-level** approaches once the architecture is settled — competing implementations of a decision this skill has already locked. Reach for it inside a commit; reach for this skill before the commit list exists.
- `synthesis-preflight` is the **pre-merge** gate at the other end of the arc. The plan this skill hands off ends in that gate.

The full lifecycle: preplan → code-planning → implementation-integrity → code-audit → preflight → pr-review.

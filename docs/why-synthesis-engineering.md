# Why synthesis engineering exists

AI coding products keep getting better. That makes synthesis engineering more
useful, not less.

Claude Code, Codex, Muse and other agent harnesses are powerful working
environments. Each has its own tools, security model, plugins, session lifecycle,
and strengths. None should be reduced to a replaceable model endpoint. At the
same time, a user's projects, methods, knowledge, decisions, and safety rules
should not be trapped inside one client or one chat.

Synthesis engineering supplies that missing layer.

## The problem it solves

Long-running work breaks when important state exists only in conversation
history. It also breaks when a skill works in one client because of a private
path, an undocumented hook, or a stale cache. Teams then face several recurring
problems:

- another agent cannot reconstruct the current project;
- a model upgrade changes routing or context injection without evidence;
- two simultaneous sessions edit the same source;
- installed skills drift from their repositories;
- a passing static test is reported as proof of live behavior;
- business users inherit setup steps designed only for tool builders;
- safety policy varies with the client that happened to open the task.

These are systems problems. A stronger model can reason around one of them in a
single session, but it cannot make the operating system durable by itself.

## What the ecosystem provides

Synthesis engineering combines six public capabilities:

1. **Portable methods.** Skills follow the [Agent Skills](https://agentskills.io)
   standard, in one format that every supported harness reads whole, and keep
   provider-specific metadata in adapters.
2. **Durable project state.** `CONTEXT.md`, `REFERENCE.md`, session logs, and
   committed plans let a different agent or machine recover the work from
   version control, and the session-start hook re-injects a project's directive
   and current state, including after compaction.
3. **Concurrent-work coordination.** Sessions claim the paths they will write on
   a shared board, one small file per session. Claims make simultaneous work
   visible, and the optional commit check refuses a commit inside another live
   session's claim, so overlapping writes are not left to social convention.
4. **Safety controls.** Hooks hold sends and deploys for the person's approval of
   the exact call and refuse destructive commands, the same way in every
   harness; the commit check adds credential and disclosure scanning.
5. **Verification.** One test command covers the core and every skill, and
   `synthesis doctor` checks what is actually installed in each harness, whether
   its hooks are wired, and whether the person has trusted them.
6. **Progressive onboarding.** One setup script serves a person on one Mac, a
   workspace moving to a new Mac, and an organization whose members share
   configuration from a data-only repository.

The same architecture supports synthesis coding, synthesis writing, project
management, knowledge work, and operational workflows. The artifact changes;
the continuity and verification problem does not.

## What it is not

Synthesis engineering is not a replacement client and does not proxy every
model through one lowest-common-denominator interface. Native harnesses retain
their own execution, permissions, user experience, and integrations. The
ecosystem provides a shared contract beneath them and adapters at their edges.

It is also not a prompt collection. Skills include activation metadata,
scripts with tests, references, and coverage maps that record where each rule
lives; the runtime adds hooks that enforce the safety rules instead of asking
the model to remember them.

## Why vendors should care

An agent vendor benefits when users can trust upgrades, move substantial work
into the product, and diagnose failures without guesswork. Synthesis engineering
offers reusable tests for hook registration and latency, skill-format budgets
matched to how harnesses truncate and re-attach skills, and doctor checks for
installed plugin bytes and hook trust. Those checks can expose integration
defects before users experience them as lost work.

The project does not ask vendors to standardize their products into sameness.
It asks for enough observable interfaces that users can prove what each product
did. The plugin and hook contracts of Claude Code and Codex already provide most
of what the runtime needs. Another harness can meet the same
[runtime contract](runtime-integration.md) without copying either product.

## Why contributors should care

This is a place to work on agent engineering beyond benchmark scores: durable
state, human authority, interoperability, failure semantics, onboarding,
writing systems, and the operating practices that make agents useful over
months. Contributions can be a skill, a harness adapter, a guard, a safer
installer, an accessibility improvement, or a documented workflow from a field
that agent tooling usually overlooks.

The governing question is direct: can a person begin meaningful work in one
capable agent, continue in another, and verify that neither client silently
changed the result?

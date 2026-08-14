# Why synthesis engineering exists

AI coding products keep getting better. That makes synthesis engineering more
useful, not less.

Claude Code, ChatGPT Codex, and other agent runtimes are powerful working
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
   standard and keep provider-specific metadata in adapters.
2. **Durable project state.** `CONTEXT.md`, `REFERENCE.md`, session logs, and
   committed plans let a different agent or machine recover the work from
   version control.
3. **Concurrent-work coordination.** Lease-backed claims make simultaneous
   sessions visible and prevent overlapping writes from being treated as a
   social convention.
4. **Safety controls.** Hooks, guards, and explicit authority gates make
   destructive or outward-facing actions reviewable.
5. **Runtime evidence.** Conformance separates source correctness, installed
   state, live delivery, continuity, and authenticated capability.
6. **Progressive onboarding.** One engine supports an individual power user,
   an engineering team, and an organization with shared configuration.

The same architecture supports synthesis coding, synthesis writing, project
management, knowledge work, and operational workflows. The artifact changes;
the continuity and verification problem does not.

## What it is not

Synthesis engineering is not a replacement client and does not proxy every
model through one lowest-common-denominator interface. Native harnesses retain
their own execution, permissions, user experience, and integrations. The
ecosystem provides a shared contract beneath them and adapters at their edges.

It is also not a prompt collection. Skills include activation metadata,
scripts, references, tests, installation, lifecycle rules, and evidence about
the runtime in which they execute.

## Why vendors should care

An agent vendor benefits when users can trust upgrades, move substantial work
into the product, and diagnose failures without guesswork. Synthesis engineering
offers reusable fixtures for plugin discovery, hook delivery, context budgets,
session continuity, and authenticated capability. Those fixtures can expose
integration defects before users experience them as lost work.

The project does not ask vendors to standardize their products into sameness.
It asks for enough observable interfaces that users can prove what each product
did. OpenAI's app-server interfaces and Anthropic's plugin and hook contracts
already provide much of that substrate. Other runtimes can implement the same
five-plane evidence contract without copying either product.

## Why contributors should care

This is a place to work on agent engineering beyond benchmark scores: durable
state, human authority, interoperability, failure semantics, onboarding,
writing systems, and the operating practices that make agents useful over
months. Contributions can be a skill, a runtime fixture, a connector probe, a
safer installer, an accessibility improvement, or a documented workflow from a
field that agent tooling usually overlooks.

The governing question is direct: can a person begin meaningful work in one
capable agent, continue in another, and verify that neither client silently
changed the result?

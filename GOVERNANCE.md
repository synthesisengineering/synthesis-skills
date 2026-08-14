# Governance

Synthesis Skills is maintained as public infrastructure for portable agent
work. Governance favors evidence, clear ownership, contributor credit, and
decisions that keep the public layer useful across vendors.

## Roles

- **Maintainers** merge releases, protect security and disclosure boundaries,
  and decide public interfaces.
- **Contributors** submit code, skills, tests, documentation, research, or
  runtime evidence through pull requests.
- **Runtime stewards** maintain an adapter and its live acceptance fixtures for
  a specific agent product.

A contributor can become a runtime steward through sustained ownership of an
adapter, responsive review, and passing live evidence. Maintainer access is
granted case by case based on the same demonstrated care.

## Decision model

Routine fixes are decided in pull-request review. Changes to the portable
project format, safety boundaries, evidence statuses, plugin packaging, or
first-class runtime criteria require a written decision record in the pull
request or repository documentation.

Maintainers seek input from the people who operate the affected runtime. The
maintainer responsible for the release makes the final decision and records
the reasoning. Vendor preference is not a deciding criterion; user continuity,
safety, observable behavior, and maintainability are.

## Compatibility

Claude Code and ChatGPT Codex are first-class runtimes. A shared change must
preserve both verified contracts. Client-specific differences belong in
adapters and tests, not in divergent copies of the method.

Another runtime becomes first-class when it satisfies
[the runtime integration contract](docs/runtime-integration.md) with fresh
normal-session evidence. Unsupported capabilities remain explicit.

## Releases

- Source is versioned and tested before native plugin caches are refreshed.
- Release notes credit substantive contributions and name the user-visible
  behavior.
- Installed state and live acceptance are verified independently after a
  release.
- A failing required evidence plane blocks a first-class conformance claim.

## Public and private boundaries

The public repository contains generic methods, fixtures, and examples.
Personal, client, and organization configuration belongs in separate private
layers. A useful private pattern should be generalized before it enters this
repository; private names and paths do not come with it.

## Conduct

Be direct about technical disagreement and respectful toward the people doing
the work. Review the change, explain the failure mode, and give credit publicly.
Security or disclosure concerns should be raised privately with maintainers
before details are posted in an issue.

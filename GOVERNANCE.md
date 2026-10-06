# Governance

Synthesis Skills is maintained as public infrastructure for portable agent
work. Governance favors evidence, clear ownership, contributor credit, and
decisions that keep the public layer useful across vendors.

## Roles

- **Maintainers** merge and release, protect security and disclosure
  boundaries, and decide public interfaces.
- **Contributors** submit code, skills, tests, documentation or research
  through pull requests.
- **Harness stewards** maintain one harness's adapter: its install commands in
  the onboarding setup, its hook wiring, its `synthesis doctor` checks, and the
  tests for all three.

A contributor can become a harness steward through sustained ownership of an
adapter and responsive review. Maintainer access is granted case by case on the
same demonstrated care.

## Contribution lanes and appointments

Documentation, methodology, guards and their tests, harness adapters,
accessibility, compatibility, translations and research are separate
contribution lanes, and each is credited on its own terms.

Repeat contributors, harness stewards and maintainers each hold an explicit
scope and a named backup. An appointment and its scope are recorded in a pull
request. When someone steps down, the change closes that appointment and keeps
their credit in the repository history. Neither a generated proposal nor a
passing test grants repository membership.

## Decision model

Routine fixes are decided in pull-request review. Changes to the project record
format, the hook contract, safety boundaries, plugin packaging, or the criteria
for a supported harness require a written decision record in the pull request
or the repository documentation.

Maintainers seek input from the people who use the affected harness. The
maintainer responsible for the release makes the final decision and records the
reasoning. Vendor preference is not a deciding criterion; user continuity,
safety, observable behavior, and maintainability are.

## Supported harnesses

Claude Code, Codex and Muse are the supported harnesses. Each installs the
native plugin with its own commands, runs the four hooks through the stable
hook path, and is checked by `synthesis doctor`. A shared change must keep all
three working. Harness-specific differences belong in adapters and tests, not
in divergent copies of a skill.

Another harness joins the list when it meets
[the runtime contract](docs/runtime-integration.md), its install and doctor
checks are in the repository with tests, and a fresh session in that harness
shows the SessionStart brief. Anything the harness cannot do is stated, not
hidden.

## Releases

- Continuous integration is the only gate: `python3 -m pytest -q tests/ skills/`
  must pass on the pull request before it merges.
- The release script runs from a clean checkout of the merged default branch.
  It tags, pushes, installs into each harness with that harness's own commands,
  verifies each harness's installed files equal the tag, and runs
  `synthesis doctor`. A release is not complete until it exits 0.
- Release notes in [CHANGELOG.md](CHANGELOG.md) name the user-visible behavior
  and credit substantive contributions.

[AGENTS.md](AGENTS.md) has the exact commands.

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

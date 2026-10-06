# Contributing to Synthesis Skills

Synthesis Skills is a provider-neutral layer for durable project state,
portable skills, and safety controls. Contributions should improve that shared
layer while respecting the native strengths of each agent harness.

## Choose a contribution lane

- **Report a bug.** Use the bug template and include the harness and its
  version, the plugin version (`synthesis version`), the `synthesis doctor`
  output, and whether you saw the problem in a live session or only in a test.
- **Improve an existing skill.** Explain the user problem and add a regression
  test when scripts or routing behavior change.
- **Add a skill.** Start with the skill-proposal template. State who needs it,
  what phrase should activate it, and why an existing skill cannot own the
  workflow.
- **Add or improve a harness adapter.** Follow
  [docs/runtime-integration.md](docs/runtime-integration.md). An adapter must
  state what the harness cannot do rather than report it as working.
- **Improve onboarding or documentation.** Test the instructions as a new user
  on the path you are changing.

Documentation fixes, test fixtures, accessibility improvements, and examples
from non-coding work are all useful contributions.

## Before opening a pull request

1. Search existing issues, skills, and repository history.
2. Create a feature branch. Keep one user-visible concern per pull request.
3. Preserve the public/private boundary. Do not include names, local paths,
   credentials, client data, or organization-specific procedures.
   This repository accepts mechanisms strangers can configure: detectors,
   guards, parsers, and capabilities, opt-in behind configuration, with the
   personal surface audited out and its absence tested. A person's opinions and
   rule texts, instruction kernels, disclosure ledgers, personal adapters and
   secrets stay in private layers. Code moved here from a private layer ships
   inert until configured and is maintained under the community posture in
   [SUPPORT.md](SUPPORT.md).
4. Run the same check CI runs:

   ```bash
   python3 -m pytest -q tests/ skills/
   ```

   It covers the core, every skill's tests, the skill format, the budgets and
   hook latency, and the source lint (manifests agree, the CHANGELOG's newest
   entry is the manifest version, every skill has a license and Codex
   metadata, no personal paths). Code must also run on Python 3.9, the version
   macOS ships as `/usr/bin/python3`.
5. If you changed install or hook wiring, run `synthesis doctor` on a machine
   with the plugin installed and start a fresh session in each affected
   harness. Say in the pull request what you saw. A test that runs the hook
   script directly is not proof that a harness delivered the event.
6. Complete the pull request template.

## Skill structure

Every skill follows [docs/skill-format.md](docs/skill-format.md):

```text
skills/skill-name/
├── SKILL.md            # frontmatter, purpose, binding rules, contents, procedure
├── agents/openai.yaml  # Codex display text and invocation policy
├── references/         # material for one step or situation, listed in Contents
├── scripts/            # executable parts, when needed
├── tests/              # tests for those scripts, collected by CI
└── assets/             # templates or examples, when needed
```

### SKILL.md requirements

- Frontmatter has `name`, `description`, `license`, `depends_on` and
  `metadata`, with `metadata.format: v5` and the skill's own
  `metadata.version`. The SPDX license identifier selects the
  repository-level `LICENSE-CC0` or `LICENSE-APACHE` terms.
- The description says when to use the skill, in at most 300 characters.
- `SKILL.md` stays under 8,000 bytes. It opens with one short paragraph, then
  `## Binding rules`, then `## Contents`, then the procedure.
- Every file in `references/` is listed in Contents with a line saying when to
  read it. Each is at most 1,500 lines; one over 150 lines opens with its own
  contents list.
- A rewrite carries `references/coverage-map.md`, listing every rule of the old
  text and where it now lives, and puts anything not kept in
  `references/preserved.md` with the reason.
- Show every script the skill uses with its exact command line and what it
  prints.
- Keep the skill standalone. Public skills cannot depend on personal agent
  instructions or private configuration.

### Codex metadata requirements

`agents/openai.yaml` is part of the skill interface, not decoration.

- `interface.short_description` must stay concise and distinct in the catalog.
- `policy.allow_implicit_invocation` follows the catalog architecture:
  foundational routing and execution skills may be implicit; specialists stay
  explicitly invocable through the router.
- The explicit invocation prompt must name the skill with `$skill-name`.
- Do not weaken Claude Code trigger descriptions to fit a Codex catalog budget.
  Harness-specific metadata is the adapter layer.

## Quality standard

A contribution is ready when:

- the user-visible behavior is complete;
- tests cover failure paths, not only the happy path;
- destructive targets are resolved and validated before mutation;
- protection fails closed when its dependencies cannot run;
- what the source does, what is installed, and what a live session showed are
  reported separately;
- Claude Code, Codex and Muse behavior is preserved, or the harness-specific
  difference is documented and tested;
- documentation matches the commands and current product surfaces;
- no generated or installed cache was edited as the source of truth.

## Contributor credit and decisions

Substantive contributors are credited in release notes and repository history.
Maintainers explain decisions in the pull request when an architectural choice
affects portability, safety, or a public interface. See
[GOVERNANCE.md](GOVERNANCE.md) for the decision and release model.

## License

By contributing, you agree that your contribution is licensed under the
repository's existing dual-license structure: CC0 for methodology content and
Apache 2.0 for executable scripts. Within a skill folder, the license declared
in that skill's `SKILL.md` frontmatter applies. The core outside `skills/` (the
`synthesis/` runtime, `hooks/`, `install.sh`, `onboard.sh` and the tests) is
Apache 2.0.

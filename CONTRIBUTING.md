# Contributing to Synthesis Skills

Synthesis Skills is a provider-neutral layer for durable project state,
portable skills, safety controls, and runtime evidence. Contributions should
improve that shared layer while respecting the native strengths of each agent
client.

## Choose a contribution lane

- **Report a runtime gap.** Use the bug template and include the client,
  surface, plugin version, command output, and whether the evidence came from
  source, installed files, or a live session.
- **Improve an existing skill.** Explain the user problem and add a regression
  test when scripts or routing behavior change.
- **Add a skill.** Start with the skill-proposal template. State who needs it,
  what phrase should activate it, and why an existing skill cannot own the
  workflow.
- **Add a runtime adapter.** Follow the five-plane integration contract in
  [docs/runtime-integration.md](docs/runtime-integration.md). A new adapter
  must report unsupported and unverifiable capabilities explicitly.
- **Improve onboarding or documentation.** Test the instructions as a new user
  on the audience path you are changing.

Documentation fixes, runtime fixtures, accessibility improvements, connector
probes, and examples from non-coding work are all useful contributions.

## Before opening a pull request

1. Search existing issues, skills, and repository history.
2. Create a feature branch. Keep one user-visible concern per pull request.
3. Preserve the public/private boundary. Do not include names, local paths,
   credentials, client data, or organization-specific procedures.
4. Run the source conformance check:

   ```bash
   python3 skills/synthesis-agent-conformance/scripts/conformance.py source --source-root .
   ```

5. Run the tests closest to the change. If you changed a runtime adapter, also
   supply installed and live evidence or identify the exact human/runtime gate.
6. Complete the pull request template. A static contract probe is not live
   acceptance evidence.

## Skill structure

Every skill includes:

```text
skills/skill-name/
├── SKILL.md            # Agent Skills instructions and frontmatter
├── agents/openai.yaml  # Codex discovery and invocation policy
├── references/         # Supporting material, when needed
├── scripts/            # Executable implementation, when needed
├── assets/             # Templates or examples, when needed
└── LICENSE             # CC0 or Apache 2.0
```

### SKILL.md requirements

- Use valid YAML frontmatter with `name`, `description`, `license`, and
  `metadata`.
- Make the description specific enough to route real user requests.
- Keep the body under 500 lines. Move detailed material to `references/`.
- Write instructions in imperative form.
- Include examples when they clarify a decision or failure mode.
- Keep the skill standalone. Public skills cannot depend on personal agent
  instructions or private configuration.
- If the skill covers writing or style, include standalone defaults in
  `references/voice-defaults.md`.

### Codex metadata requirements

`agents/openai.yaml` is part of the skill interface, not decoration.

- `interface.short_description` must stay concise and distinct in the catalog.
- `policy.allow_implicit_invocation` follows the catalog architecture:
  foundational routing and execution skills may be implicit; specialists stay
  explicitly invocable through the router.
- The explicit invocation prompt must name the skill with `$skill-name`.
- Do not weaken Claude Code trigger descriptions to fit a Codex catalog budget.
  Client-specific metadata is the adapter layer.

## Quality standard

A contribution is ready when:

- the user-visible behavior is complete;
- tests cover failure paths, not only the happy path;
- destructive targets are resolved and validated before mutation;
- protection fails closed when its dependencies cannot run;
- source, installed state, and live runtime are not conflated;
- Claude Code and Codex behavior are both preserved or the client-specific
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
Apache 2.0 for executable scripts.

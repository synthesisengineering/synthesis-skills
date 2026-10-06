# Repository Instructions: Synthesis Skills

## Purpose

This public repository is the canonical source for portable synthesis
engineering skills. It is packaged as one native plugin for Claude Code, OpenAI
Codex and Muse while remaining compatible with the Agent Skills standard.

## Canonical Sources

- `skills/` owns every public skill, script, reference, asset, license, and
  Codex interface.
- `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json` and
  `.muse-plugin/plugin.json` own the three client manifests. Their versions must
  match.
- `.agents/plugins/marketplace.json` and
  `.claude-plugin/marketplace.json` own marketplace discovery.
- `hooks/hooks.json` owns shared lifecycle-hook registration.
- `skills/synthesis-onboarding/scripts/setup.py` installs the native plugin in
  each harness; native plugins are the only installation path.

Never edit installed plugin caches or user-level skill copies. Make the change
here, verify it, merge it to `main`, then update the installed plugins.

## Implementation Rules

1. Search the existing skills and scripts before adding behavior.
2. Keep shared behavior agent-neutral. Put client-specific metadata and event
   translation in the corresponding adapter.
3. Give each skill one canonical directory under `skills/`.
4. Keep `SKILL.md` under 8,000 bytes in the v5 format (`docs/skill-format.md`); move
   detailed material into `references/`.
5. Keep executable behavior in version-controlled scripts with deterministic
   tests.
6. Protective checks fail closed when required state or dependencies cannot be
   verified.
7. Do not add compatibility shims unless the task explicitly requires them.
8. Do not include credentials, private organization names, personal paths, or
   client-confidential examples in this public repository.

## Cross-Client Contract

- Every public skill requires `SKILL.md` with an SPDX license identifier in
  frontmatter and `agents/openai.yaml`. The repository-level
  `LICENSE-APACHE` and `LICENSE-CC0` files carry the corresponding terms.
- Claude Code and Codex must load the same skill source and shared scripts.
- `AGENTS.md` is the tracked repository instruction source.
- `CLAUDE.md` is only the Claude Code import adapter: `@AGENTS.md`.
- Plugin-relative paths are required; absolute paths to a local checkout are
  forbidden.
- Runtime conformance must verify enabled plugin state, duplicate direct
  copies, hooks, and project handoff behavior.

## Verification

CI runs exactly what you run locally, and it is the only gate (R7.3):

```bash
python3 -m pytest -q tests/ skills/
```

That covers the v5 core (`synthesis/`), every skill's own tests wherever they live
(beside its scripts, at its root or in `tests/`), the format check for
v5 skills (`tests/test_skill_format.py`), the budgets and hook latency
(`tests/test_budgets.py`), and the source lint (`tests/test_source_lint.py`): the three
plugin manifests agree, the CHANGELOG's newest entry is that version, skill names are
unique, every `depends_on` resolves, every skill has an SPDX license and
`agents/openai.yaml`, Muse's manifest lists every skill, Codex's skill catalog fits its
budget, no personal path appears anywhere, and every config a skill documents as
fail-closed ships an example. The lint also fails if any `test_*.py` under `skills/`
would not be collected by that command (a folder pytest skips, or a file name shared with
another test module outside a package). Code must also run on Apple's `/usr/bin/python3` (3.9);
CI runs a 3.9 job.

On a machine with the plugin installed, `synthesis doctor` checks the installed side:
the stable runtime, each harness's plugin bytes against it, hook wiring and trust,
Codex's settings and catalog, instruction adapters and durable storage.

## Releases

- Use semantic versioning; bump all three plugin manifests together and add the
  CHANGELOG entry for that version in the same pull request.
- Use a feature branch and a pull request; merge only after CI passes.
- Ship with the release script from a clean checkout of the merged default branch:

  ```bash
  python3 skills/synthesis-skills-manager/scripts/release.py --dry-run   # check and print the plan
  python3 skills/synthesis-skills-manager/scripts/release.py
  ```

  It refuses unless the tree is clean on the default branch, the manifests and
  CHANGELOG agree, and CI passed for HEAD. It holds the release train (a board claim
  on the main checkout's `CHANGELOG.md`; another live session holding it means
  another release is under way, and the script names it), tags, pushes `main`,
  `stable` and the tag atomically to every push remote and reads them back with
  `git ls-remote`, installs into Claude Code, Codex and Muse with each harness's
  own commands, verifies each harness's installed files equal the tag at the folder
  it reports loading, then updates the stable runtime and runs `synthesis doctor`.
  A release is not complete until the script exits 0.
- `release.py --install-only` installs and verifies the tag HEAD carries, for a new
  Mac or after drift.

See `CONTRIBUTING.md` for contribution structure and licensing.

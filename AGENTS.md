# Repository Instructions: Synthesis Skills

## Purpose

This public repository is the canonical source for portable synthesis
engineering skills. It is packaged as one native plugin for OpenAI Codex and
Claude Code while remaining compatible with the Agent Skills standard.

## Canonical Sources

- `skills/` owns every public skill, script, reference, asset, license, and
  Codex interface.
- `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json` own the two
  client manifests. Their versions must match.
- `.agents/plugins/marketplace.json` and
  `.claude-plugin/marketplace.json` own marketplace discovery.
- `hooks/hooks.json` owns shared lifecycle-hook registration.
- `install.sh` supports direct-copy fallbacks and the transition to native
  plugins. Native plugins are the primary installation path.

Never edit installed plugin caches or user-level skill copies. Make the change
here, verify it, merge it to `main`, then update the installed plugins.

## Implementation Rules

1. Search the existing skills and scripts before adding behavior.
2. Keep shared behavior agent-neutral. Put client-specific metadata and event
   translation in the corresponding adapter.
3. Give each skill one canonical directory under `skills/`.
4. Keep `SKILL.md` below 500 lines; move detailed material into `references/`.
5. Keep executable behavior in version-controlled scripts with deterministic
   tests.
6. Protective checks fail closed when required state or dependencies cannot be
   verified.
7. Do not add compatibility shims unless the task explicitly requires them.
8. Do not include credentials, private organization names, personal paths, or
   client-confidential examples in this public repository.

## Cross-Client Contract

- Every public skill requires `SKILL.md`, `LICENSE`, and
  `agents/openai.yaml`.
- Claude Code and Codex must load the same skill source and shared scripts.
- `AGENTS.md` is the tracked repository instruction source.
- `CLAUDE.md` is only the Claude Code import adapter: `@AGENTS.md`.
- Plugin-relative paths are required; absolute paths to a local checkout are
  forbidden.
- Runtime conformance must verify enabled plugin state, duplicate direct
  copies, hooks, and project handoff behavior.

## Verification

Run the same checks required by CI:

```bash
python3 skills/synthesis-agent-conformance/scripts/conformance.py source
python3 skills/synthesis-agent-conformance/scripts/conformance.py instructions --repo-root .
python3 -m pytest skills/synthesis-agent-conformance/scripts/test_*.py -q
python3 -m pytest skills/synthesis-project-management/scripts/test_coordination.py -q
python3 -m pytest skills/synthesis-kb-edit/scripts/test_*.py skills/synthesis-okf/scripts/test_*.py -q
python3 -m pytest skills/synthesis-daily-rituals/scripts/test_*.py skills/synthesis-message-guard/scripts/test_*.py skills/synthesis-git-hooks/scripts/test_*.py -q
python3 -m pytest skills/synthesis-onboarding/scripts/test_onboard.py -q
python3 skills/synthesis-meeting-transcripts/test_verify_transcripts.py
sh -n install.sh onboard.sh tests/test_installer.sh
./tests/test_installer.sh
python3 -m compileall -q skills
python3 skills/synthesis-inbox-cleanup/tests/run_poisoned.py
python3 skills/synthesis-inbox-cleanup/tests/run_resolver.py
sh skills/synthesis-inbox-cleanup/tests/test_runtime_installer.sh
```

For a cross-client release, also run:

```bash
python3 skills/synthesis-agent-conformance/scripts/conformance.py runtime
python3 skills/synthesis-agent-conformance/scripts/conformance.py coordination
```

## Releases

- Use semantic versioning and keep both plugin manifests in parity.
- Record user-visible changes in `CHANGELOG.md`.
- Update the concise release note in `README.md`.
- Use a feature branch and a review request for non-trivial changes.
- Merge only after every required check passes.
- Update both installed marketplaces from committed `main` and rerun runtime
  conformance.

See `CONTRIBUTING.md` for contribution structure and licensing.

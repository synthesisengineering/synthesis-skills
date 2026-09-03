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

Run the same checks required by CI:

```bash
python3 skills/synthesis-agent-conformance/scripts/conformance.py source
python3 skills/synthesis-agent-conformance/scripts/conformance.py instructions --repo-root .
python3 -m pytest skills/synthesis-agent-conformance/scripts/test_*.py -q
python3 -m pytest skills/synthesis-project-management/scripts/ -q
python3 -m pytest skills/synthesis-promotion-gate/scripts/ -q
python3 -m pytest skills/synthesis-context-lifecycle/scripts/ skills/synthesis-implementation-integrity/scripts/ -q
python3 -m pytest skills/synthesis-kb-edit/scripts/test_*.py skills/synthesis-okf/scripts/test_*.py -q
python3 -m pytest skills/synthesis-daily-rituals/scripts/test_*.py skills/synthesis-message-guard/scripts/test_*.py skills/synthesis-git-hooks/scripts/test_*.py skills/synthesis-slack-sync/scripts/test_*.py skills/synthesis-chief-of-staff/scripts/test_*.py -q
python3 -m pytest skills/synthesis-onboarding/scripts/ -q
python3 skills/synthesis-onboarding/scripts/check_scaffolds.py .
python3 skills/synthesis-onboarding/scripts/check_capabilities.py .
python3 -m pytest skills/synthesis-skills-manager/scripts/test_release.py -q
python3 skills/synthesis-meeting-transcripts/test_verify_transcripts.py
python3 skills/synthesis-meeting-transcripts/test_transcript_primary.py
sh -n install.sh onboard.sh tests/test_installer.sh
./tests/test_installer.sh
python3 -m compileall -q skills
python3 skills/synthesis-inbox-cleanup/tests/run_poisoned.py
python3 skills/synthesis-inbox-cleanup/tests/run_resolver.py
sh skills/synthesis-inbox-cleanup/tests/test_runtime_installer.sh
```

This fenced list and the `conformance` job in
`.github/workflows/validate.yml` are held equal (modulo the CI-only
`pip install` and env-bound acceptance steps) by
`test_release.py::test_agents_verification_list_matches_ci_workflow` —
change them together, or CI fails.

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
- On a machine with a synthesis coordination board, hold the release train
  (`coordination.py claim ... --area release-train:synthesis-skills`) from
  version authoring through the gated release; `release.py` preflight
  refuses otherwise. Release the claim right after shipping.
- **Ship with the gated release script**, which runs the required checks,
  publishes to every push remote, installs into both clients using each
  client's own commands, and verifies each client twice — its CLI report and
  the manifest at the path it loads:

  ```bash
  python3 skills/synthesis-skills-manager/scripts/release.py --repo-root .
  ```

  A release is not complete until both clients are confirmed current; the
  script exits non-zero otherwise. Use `--install-only` to recover drift or
  provision a new machine. Publishing by hand is still possible, but then the
  install step is yours to remember — which is the gap the script closes.

See `CONTRIBUTING.md` for contribution structure and licensing.

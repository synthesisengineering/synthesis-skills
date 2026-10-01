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
python3 skills/synthesis-skills-manager/scripts/release.py --repo-root . --source-checks-only
```

CI and local verification execute the same exhaustive `REQUIRED_CHECKS` catalog
in `release.py`. Two independent checks run concurrently by default (maximum four), each with its
own retained temporary directory and bounded process group. Source identity is
checked before and after execution. Failure stops further admission and drains
running checks; missing checks never count as success. `--check-workers 1`
provides a measured sequential comparison without changing the catalog.

Hosted acceptance runs concurrently in its separate job. Its exact-candidate
result is verified again at publication; installation and live health checks
remain fresh. Do not manually repeat the catalog after a verified hosted pass.

Executable consumers still require native macOS isolation or bubblewrap on
Linux, and complete-page acceptance requires a verified Chromium executable.
Missing required capability fails; no test or protection is skipped.

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
- **Ship with the gated release script**, which verifies authenticated complete tests for the exact candidate,
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

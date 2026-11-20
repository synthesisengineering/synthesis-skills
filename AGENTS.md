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
- `skills/synthesis-skills-manager/assets/collections.json` lists the five
  collections, plugins that each release builds from `skills/` and publishes as the
  `collections` branch, and that setup's `--collections` installs; the core carries the
  whole set's guard, its hooks and their runtime, so no collection installs without it.
  Each skill names its own in its frontmatter (`metadata.category`). That branch is a
  build output: never edit it by hand.

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

It runs this command in six jobs for each system and Python, the core's tests in four
parts by file name and the skills' in two by the skill's name, so that no job nears its
ten-minute limit even on a slow runner; a lint test holds that together they run each test
file once.

That covers the v5 core (`synthesis/`), every skill's own tests wherever they live
(beside its scripts, at its root or in `tests/`), the format check for
v5 skills (`tests/test_skill_format.py`), the budgets and hook latency
(`tests/test_budgets.py`), and the source lint (`tests/test_source_lint.py`): the three
plugin manifests agree, the CHANGELOG's newest entry is that version, skill names are
unique, every `depends_on` resolves, every skill is in exactly one collection and depends
only on its own or the core, every skill has an SPDX license and
`agents/openai.yaml`, Muse's manifest lists every skill, Codex's skill catalog fits its
budget, no personal path appears anywhere, and every config a skill documents as
fail-closed ships an example. The lint also fails if any `test_*.py` under `skills/`
would not be collected by that command (a folder pytest skips, or a file name shared with
another test module outside a package). Code must also run on Apple's `/usr/bin/python3` (3.9);
CI runs a 3.9 job.

The browser tests drive Chrome's headless shell. Install it once where they look for it,
or set `SYNTHESIS_TEST_CHROMIUM` to one; without it they skip locally, and CI requires it
(`SYNTHESIS_REQUIRE_CHROMIUM=1`):

```bash
npx --yes @puppeteer/browsers install chrome-headless-shell@stable --path ~/.cache/synthesis/browsers
```

On a machine with the plugin installed, `synthesis doctor` checks the installed side:
the stable runtime, each harness's plugin bytes against it, hook wiring and trust,
Codex's settings and catalog, instruction adapters and durable storage.

## CI on a self-hosted Mac

The macOS jobs of a run that someone the repository variable `SELF_HOSTED_MAC_ACTORS` names
started, on a branch of this repository, run on a self-hosted Mac; every other job runs on
GitHub's machines. That routing in `.github/workflows/ci.yml` is no control: a pull request
can rewrite it. So, with any login that can act on this repository:

- never approve a fork's workflow run without reading every change it makes under `.github/`;
- never push another person's unreviewed commits to a branch of this repository;
- never add a `pull_request_target` or `workflow_run` workflow that checks out pull request
  code, a job that asks for more than `contents: read`, or a secret a CI job could read.

## Releases

- Use semantic versioning; bump all three plugin manifests together and add the
  CHANGELOG entry for that version in the same pull request.
- Use a feature branch and a pull request; merge only after CI passes. GitHub enforces it: `main` and `stable`
  require the `ci` check (branch protection, admins included), and with auto-merge allowed,
  `gh pr merge --auto --merge` merges a pull request when its checks pass.
- Ship with the release launcher the installed runtime carries, from a clean checkout of the merged
  default branch, alone on the line, with absolute paths:

  ```bash
  ~/.synthesis/v5/bin/synthesis-release --repo-root <absolute path of the checkout> --dry-run   # the plan
  ~/.synthesis/v5/bin/synthesis-release --repo-root <absolute path of the checkout>
  ```

  The launcher runs the release tool from the installed runtime with the interpreter pinned at install (owned by
  root with every folder above it, writable by neither this user nor its groups), isolated (`-I -S`) and with only
  named environment variables. Run so, the guard asks no code: it lets exactly that launcher run, with only the options
  the tool documents, `--session` only as the asking session's own id, on the canonical checkout (origin and every
  remote the synthesis-skills repository on GitHub, on `main`, its own git config running no program), and grants it
  one install of that tag, which the runtime's install spends for the tool's fresh clone of the tag alone, its HEAD the
  commit GitHub's tag names; a wrapped `<shell> -c '<line>'` counts only for the system's own shell. A release
  from a checkout's copy, or the tool run any other way, waits for the principal's code. The checkout only says what is
  released: the tool refuses unless the tree is clean, the manifests and CHANGELOG agree, HEAD is the tip of GitHub's
  `main` (read with git's own config left out; a tag of the version GitHub already has must name HEAD), the version is
  no older than the running runtime or GitHub's highest version tag, and CI passed for HEAD there. It then makes a fresh clone of the
  repository from GitHub at that commit in the protected releases folder, and everything after comes from that clone.
  It holds the release train (a board claim on the main checkout's `CHANGELOG.md`; another live session holding it
  means another release is under way, and the script names it), builds and checks the five collections from the
  clone's commit with the clone's own `build_collections.py --tree`, in a process of its own, tags, pushes `main`,
  `stable`, the tag and the collections, as the `collections` branch, atomically from the clone and reads them back
  with `git ls-remote`, creates the GitHub release for the tag (its CHANGELOG entry as the notes, read back as latest),
  opens the Homebrew tap's pull request that points the `synthesis` formula at the tag's archive (it merges itself
  when the tap's install tests pass), installs into Claude Code, Codex and Muse with each harness's own commands (Muse
  from the clone), verifies each harness's installed files equal the clone's tag at the folder it reports loading,
  installs the stable runtime from the clone (its staged copy must hold the tag's listing before `current` moves) and
  runs `synthesis doctor`, then waits for the tap's pull request to merge and reads the formula back from the tap's
  `main`. A GitHub server error runs its stage again, up to three times, since each stage reads what is already
  published first, and a tap job GitHub never gave a runner is run again. A release is not complete until the script
  exits 0; a hook approval only the person can give in a harness (Codex asks again after every release) is named as
  waiting, not counted.
- `~/.synthesis/v5/bin/synthesis-release --install-only --tag v<version>` installs a released tag from a fresh clone of
  it, after drift: GitHub must serve the tag on its `main` with CI passed, and nothing older than the running runtime or
  GitHub's highest version tag installs. On a new Mac, where no runtime is installed yet, the checkout's copy runs it
  (`python3 skills/synthesis-skills-manager/scripts/release.py --install-only --tag v<version>`).
- Releasing 5.31.0, the first version whose release tool builds the collections with its fresh clone's own
  `build_collections.py`, starts with `synthesis install <merged checkout>`, which waits for the principal's code:
  every release tool installed before it builds the collections with its own older script and refuses. Later
  releases need no such step.

See `CONTRIBUTING.md` for contribution structure and licensing.

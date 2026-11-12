# The directory package: method skills without hooks

How the hook-free package for OpenAI's plugin directory is defined, built and checked,
and what a submission needs that this repository cannot supply. Read it before building
or submitting the package, and when its check fails.

Contents:
- What it is, and what it is not
- What it holds
- Build it, check it, and see what changed
- What fails the check
- A skill that fails leaves the list
- What a submission asks of the owner
- What is not yet established

## What it is, and what it is not

OpenAI's public plugin directory does not list a plugin that registers lifecycle hooks
(the programs a harness runs at session start, before a tool call and at the end of a
turn). The synthesis plugin registers four, and its guards, its board, its session brief
and its approvals all hang on them, so the plugin as it ships cannot be listed there.

The directory package is a second package, built for that directory: the method skills
that need nothing from the runtime, each file copied byte for byte, with a manifest that
registers no hook, as one ZIP. It is cut from the same commit as a plugin release and
has no release train of its own.

It is not the synthesis system, and it adds nothing to it: the plugin holds every skill
in the package, so a person installs one or the other. An install without hooks has no
guard: nothing checks a send, a deploy, a commit, a calendar write or a destructive
command, and no approval code exists. It has no session brief, no reply check and no
`synthesis` command, and so no board, claims, doctor or handoff. The package's name and
description say so. A skill that promised a guard, in a package that has none, would
leave its reader trusting a protection that is not there; the check below exists to keep
such a line out.

Building the package submits nothing. The upload is the owner's step: the owner is the
person who publishes this plugin and makes the policy attestations a submission asks for.

## What it holds

- **The skills on the list.** [assets/directory-package.json](../assets/directory-package.json)
  names them under `skills`: the writing, review, planning and thinking methods. Each
  is whole but for its tests: every tracked file that is not in a `tests/` folder and
  is not named `test_*`. A test is the repository's check on a skill, not part of it,
  and one of them imports the synthesis core, which the package does not carry.
- **One manifest,** `.codex-plugin/plugin.json`: the list's `manifest` object with the
  repository's current version added. It carries the package's own name and its
  description, and has no `hooks` entry.
- **Nothing else.** No `hooks/` folder, no `synthesis/` core, no second manifest and no
  license text: the manifest names both licenses and links the repository, where
  `LICENSE-APACHE` and `LICENSE-CC0` are.

A listed skill may still name a skill outside the package as related reading: grounding
discipline links four, and others name pull-request review, implementation integrity or
the daily rituals. In this package those names lead nowhere; the description's link to
the full system is where they point.

Under `left_out` the list records each method skill that failed the check, with the
reason. At the first build that is `synthesis-skill-router`: its routing table names the
repository guard, the git hooks and the message guard as routes. The cost is discovery in
Codex.
Most listed skills set `allow_implicit_invocation: false` in their `agents/openai.yaml`,
the setting this repository gives a skill that is reached through the router, so without
the router a person invokes them by name (`$synthesis-writing-craft`). Code planning,
grounding discipline and the thinking framework leave the setting out and stay available
without being named.

## Build it, check it, and see what changed

All three commands run from a source checkout, need git and Python 3.9 or newer, and
print one line.

```bash
python3 skills/synthesis-skills-manager/scripts/build_directory_package.py OUT.zip
```

writes the ZIP and prints `built OUT.zip: 32 skills, 234 files, 845393 bytes, version
5.8.0` (exit 0). It writes nothing unless every check passes. It also refuses while the
list or a file it would carry differs from the last commit, because a package is cut
from committed files: build it from a clean checkout of the release's tag. A build is
repeatable: entries in name order, one fixed date, the executable bit as git records it.

```bash
python3 skills/synthesis-skills-manager/scripts/build_directory_package.py --check
```

runs the same checks on the same bytes and writes nothing: `ok: 32 skills, 234 files,
845393 bytes, version 5.8.0; nothing written` (exit 0). On a defect either command
prints `refused: 2 problems; nothing written`, then one line for each problem, and exits
1. CI makes the same checks on every pull request, in
[tests/test_skills_manager_directory_package.py](../tests/test_skills_manager_directory_package.py).

```bash
python3 skills/synthesis-skills-manager/scripts/build_directory_package.py --changed-since v5.7.0
```

says whether a release needs a new submission: `unchanged since v5.7.0: no new
submission is due` (exit 0), or `changed since v5.7.0: the list, synthesis-preplan; a
new submission is due` (exit 1). It names each listed skill with a packaged file that
differs from the tag, and `the list` when the list file differs: its skills, or the
manifest's name and description. The version changes with every release and is not
counted.

When the script cannot tell, it prints `cannot continue: <why>` and exits 2: the list or
a manifest cannot be read, the tag does not exist, the folder is not a git checkout, a
listed skill holds a symbolic link (followed, one could carry a file from outside its
skill), or the ZIP cannot be written.

## What fails the check

The checks read the ZIP that was built, not the folders it came from. It fails when:

1. it holds a `hooks` folder or a `hooks.json`, or its manifest has a `hooks` entry;
2. it holds a file that is neither the manifest nor a file of a listed skill, or a test;
3. a listed name is not a skill in this checkout;
4. a listed skill names, in `depends_on`, a skill that is not listed (the rule holds for
   every listed skill, so the whole chain of dependencies stays inside the list);
5. a packaged file differs from its source;
6. the manifest's version is not the repository's;
7. a line of a packaged file claims a hook, a guard or an approval code, or needs the
   runtime.

Rule 7 is a set of phrases, decided from what the skills outside the list say; the test
file names every one. They are: the lifecycle hooks and the git hooks by name
(`PreToolUse`, `Stop hook`, `git hooks`, `the commit check`); a guard by name, spaced or
hyphenated, so the name of a guard skill counts (`send guard`,
`synthesis-message-guard`), and `the guard`; `hook` or `guard` before a verb of
enforcement (`the hook refuses`, `each guard blocks`); `approve <code>`, `approval code`
and `waits for the code`; and the runtime itself: the `synthesis` command in backticks,
`~/.synthesis/v5`, an import of the core. The same words in their ordinary senses pass,
and the tests pin those too: a writer's opening hook, a guard clause, a pull request
someone approved, a review checklist's line about a project's own pre-commit hooks.

## A skill that fails leaves the list

A listed skill that gains a line under rule 7 fails the check in CI, on the pull request
that adds the line. It then leaves the list in that pull request: its name moves from
`skills` to `left_out`, with the reason, where a reader of the diff sees it.

The skill's text is never edited so that it passes, and no phrase is loosened to let one
skill through. A phrase that matches what it was never meant to, an ordinary sense of a
word, is corrected as its own change, with a line under `SPARED` in the tests that shows
the ordinary sense. A skill under `left_out` whose text stops failing is named by a
test, and may return. Adding a skill is the same edit in the other direction: put its
name under `skills`, run `--check`, and read what it reports.

## What a submission asks of the owner

From OpenAI's two pages, developers.openai.com/plugins/build/plugins and
developers.openai.com/plugins/deploy/submission, as read on 2026-11-10:

- A ZIP uploaded at platform.openai.com/plugins by an organization owner, or a member
  with Apps Management Write, from a verified publisher. Automated checks run, then a
  review with policy attestations. The upload and the attestations are the owner's.
- One review at a time for a plugin. A change to a skill or to the metadata needs a new
  ZIP, so every release that touches a listed skill is a new submission;
  `--changed-since` says which releases those are.
- A skills-only plugin is allowed. A remote MCP server is allowed only over HTTPS, one
  for a plugin, and not with API-key authentication. This package has none.
- A ZIP with lifecycle hooks or with app references (`.app.json`) cannot be submitted.
  This package has neither.

The package's name (`Synthesis Skills: methods`), its short description and its
paragraph are the owner's to choose. They are in the list file, and changing them
changes nothing else.

## What is not yet established

To find out before any upload:

- whether the owner's OpenAI organization is already a verified publisher, and what
  verification asks for;
- how long a review takes;
- whether the directory accepts skills that carry scripts. Four listed skills do:
  bitbucket, clean-text, content-quality and local-model-runtime.

The submission page was read again on 2026-11-11, with its last part, a reference of
manifest fields. It was read through a tool that summarizes a page, so confirm each
point on the page itself. As read:

- **Scripts.** A skill scan must pass before a submission, and the page does not say
  what the scan checks, so the question above stays open.
- **Icons.** A package in the Codex format needs two, `interface.logo` and
  `interface.composerIcon`: square, at least 48 by 48 pixels, PNG, JPEG, WebP or SVG, at
  most 5 MiB each, named by `./` paths and included in the ZIP. This repository holds no
  image and the package carries none. Until the owner supplies the two icons, and the
  list and the build carry them, expect the directory's validation to refuse the ZIP.
- **Lengths.** `displayName` and `shortDescription` at most 30 characters each (the
  list's are 25 and 28); `description` and `longDescription` at most 4,000; `name` at
  most 64, in lowercase letters, digits and single hyphens.
- **Links.** A website, support, privacy-policy and terms link are required of a plugin
  with an MCP server, and not of a skills-only one.

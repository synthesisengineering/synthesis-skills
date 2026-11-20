# The collections: the skills in five plugins, the guard in the core

How the five collections are defined, built, checked and published, and what installing
one gives a person. Read it before changing a skill's collection, the collections file or
the build, and when the build or the release's collections stage refuses.

Contents:
- What they are, and what they are not
- The guard rides in the core (ruling C8)
- What decides a skill's collection
- A collection's scripts, paths and links (review round 1)
- What a collection's folder holds
- Build it, check it
- What fails the check
- How a release publishes them
- Installing one
- What is not yet established

## What they are, and what they are not

The owner ruled on 2026-11-14: publish five collections, the fifth named chief-of-staff.
The whole set, `synthesis-skills` (every skill, the hooks and the runtime), stays the
default and is listed first. A collection is for someone who wants one discipline: core,
project management, engineering, writing and chief of staff, each a plugin of its own
(`synthesis-skills-<name>`). The core is what the other four build on. The source stays
one flat `skills/` folder, the only layout every harness reads: a collection is a build
output, never a second copy kept by hand.

## The guard rides in the core (ruling C8)

The principal ruled on 2026-11-20: someone may want only the writing skills, and the core
skills and the guards those need are installed with them; adding another collection later
is easy. So the core carries the whole set's guard as well as its own skills, and every
collection installs with the core: Claude Code installs it as each collection's declared
dependency, and the Codex and Muse lines, and setup, install it first. No collection is
installed without the guard.

What the core carries for the guard, every byte the whole set's, links and all:

- `hooks/hooks.json`, which Claude Code and Codex read by its place;
- the hooks the whole set's Muse manifest registers, in the core's Muse manifest, and the
  `.muse-plugin/hooks/` scripts they run;
- the runtime those hooks run, as the runtime's own install takes it (`install.takes`
  over what `synthesis/install.py` names in `STABLE_SKILL_SCRIPTS`): the `synthesis/`
  package, the scripts of each skill the runtime keeps at a stable path (other
  collections' among them, under `skills/<name>/` with no `SKILL.md`, so no harness reads
  them as a skill), and the CHANGELOG.

So the core's runtime hashes as the whole set's (`install.package_hash`): the doctor holds
a collections install's core to the installed runtime as it holds the whole set, and a
first session start installs the runtime from the core's own folder where none is there.
The other four hold no hook. Each description says the core carries the guard, and names
the whole set. Setup's `--collections` builds these folders from its checkout and installs
the ones a person picks (onboarding's `references/harness-install.md`).

## What decides a skill's collection

Each skill names its collection in its frontmatter, as `metadata.category`. The
collections file, [assets/collections.json](../assets/collections.json), lists the
collections, their plugin names and their words. A SKILL.md with no room left under
8,000 bytes for that line keeps its words (a skill is never trimmed to fit): the file
names its collection under `awaiting_room` until a reorganization makes room. A test then
fails and says so, and the line moves into the frontmatter. At 5.22.0 five skills wait:
git hooks, the knowledge-base distribution, the message guard, Slack sync and waiting.

The rules, which `tests/test_source_lint.py` and the build both hold:

1. Every skill is in exactly one collection that the file lists.
2. A skill depends (`depends_on`) only on skills in its own collection or in the core.
3. A dependency a skill's scripts name is in its own collection, since the core is
   installed in a folder of its own and a path from one plugin into another leads
   nowhere. The action sheet loads the decision packet's engine, the release loads
   onboarding's `setup.py`, and onboarding seeds a new workspace's sharing policy from
   knowledge-base editing's template, so each pair shares a collection (all are in the
   core).

A skill is placed by what it does. Where that was not obvious: the decision packet and
the action sheet are in the core, because work in every collection brings the principal
decisions and remaining actions; agent guardrails is in the core, because its guards span
every collection's work; knowledge-base editing and the Open Knowledge Format are in the
core, because onboarding loads knowledge-base editing's template (rule 3), which depends
on the format, while capturing knowledge and distributing a knowledge base stay in
project management; adversarial review is in project management, with autopilot,
which runs its rounds and which it links into; the machines (Mac sync, machine sync,
fleet secrets and the repo guard) are in chief of staff, beside the daily rituals that
Mac sync and machine sync depend on; executive communication is writing; concise
messaging is with quick answers, which depends on it, in chief of staff. Autopilot
declares as dependencies only what it always uses: the fact-checking and writing-craft
skills apply when its task is writing, as its references say, so they are no longer in
its `depends_on`.

## A collection's scripts, paths and links (review round 1)

5.22.0's first review found three ways a collection's files failed where it is installed,
and the build now holds each:

- **Scripts that import the runtime (R1-3).** Of 34 collected scripts that imported the
  synthesis runtime, 23 read only its YAML reader, which uses the standard library alone
  and keeps no state. A collection whose scripts read it carries `synthesis/__init__.py`
  and `synthesis/yamlish.py`, byte for byte, where the whole set holds them, so those
  scripts find them as they do there. The core carries the whole runtime with the guard,
  so every core script runs in its folder. The other seven need the runtime itself (its
  board, the rituals' records) and are not in the core: the collections file names each
  under `needs_the_whole_set` with why, and each says so in one line; a skill runs the
  runtime's own copy of them, which the guard installs. The
  build reads every collected script's imports from its syntax, through the modules beside
  it, and refuses one that cannot start in its collection unless it is named, one that
  imports the runtime inside a function with nothing to catch the absence, a name that no
  longer fits, and a carried module that imports the rest of the runtime. A test runs every
  collected entry point with `--help` from a built folder on a Mac with no runtime.
- **A path into another skill's folder (R1-20).** Every string of a collected script's
  code, docstrings aside, that names another skill's folder is read: that skill must be in
  the script's collection, or the script must need the whole set, or `optional_loads` must
  name the load with what the script does without it. The rituals' pull-request scan reaches
  the Bitbucket skill's helper, and reports a Bitbucket repository unscanned without it. A
  core script may reach a skill whose scripts the guard carries, since they are beside it.
- **Links (R1-21).** In the built copy alone, a relative link that resolves in the whole set
  and would lead out of the folder points at the repository's file, or folder, at the
  release's tag; every other byte stays the source's, and a link that leads nowhere in the
  whole set too is left as it is. The build names any link that still leads out.

## What a collection's folder holds

- Every tracked file of its skills that is not a test, byte for byte, but for links that
  would lead out of the folder (above).
- In the core, the guard (above), byte for byte. Elsewhere, where its scripts read
  settings, the runtime's `synthesis/__init__.py` and `synthesis/yamlish.py`, and nothing
  else of the runtime.
- The repository's `LICENSE-APACHE` and `LICENSE-CC0`, the terms its skills' SPDX
  identifiers name.
- Its own `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` and
  `.muse-plugin/plugin.json`, at the repository's version; only the core's Muse manifest
  registers hooks, the whole set's. Each takes the whole set's author, homepage,
  repository and license; its description is the collection's own sentence, then
  `with_core` (all but the core), then `guard`, then `whole_set`. Every
  Claude Code manifest but the core's declares `synthesis-skills-core` as a dependency;
  Codex and Muse resolve none, so their install lines name both plugins. The Muse
  manifest lists exactly the folder's skills.

Two marketplace files sit at the top of the branch, beside the five folders:
`.claude-plugin/marketplace.json` (which Muse reads too) and
`.agents/plugins/marketplace.json`, each listing the five, the core first, from
`./<name>`, under the marketplace name `synthesis-collections`, apart from the whole
set's `synthesis-engineering`. Each Claude Code entry carries the same description as
the manifests: Claude Code shows the entry, not the manifest, before an install.

## Build it, check it

```bash
python3 skills/synthesis-skills-manager/scripts/build_collections.py --check
python3 skills/synthesis-skills-manager/scripts/build_collections.py OUT_DIR
```

`--check` builds from the checkout's files and writes nothing: `ok: 5 collections, 73
skills, 753 files, version 5.22.0; nothing written` (exit 0). With a folder that does not
exist yet, it builds from the last commit and writes the branch's tree there, whole or
not at all: `built OUT_DIR: ...` (exit 0); it refuses while a file it reads differs from
that commit. A defect prints `refused: N problems; nothing written`, then each problem,
and exits 1; what cannot be read prints `cannot continue: <why>` and exits 2. It reads
files with `build_directory_package.py`'s code and runs on Python 3.9. CI runs the same
checks on every pull request, in
[tests/test_skills_manager_collections.py](../tests/test_skills_manager_collections.py).

## What fails the check

The check reads the folders that were built. It fails on a skill in no collection, in
more than one, or in one the file does not list; on a dependency outside a skill's own
collection and the core, or one its scripts load from outside its own folder; on a file
that is no manifest, license, file of the collection's skills or of the core's guard, or a
test; a file that differs from its source; a guard file the core lacks, or a core Muse
manifest that registers other hooks than the whole set's; a hook folder, a `hooks.json`,
or a manifest with a `hooks` entry that holds anything, outside the core; a skill or
license missing; a manifest that names another
plugin or version, or declares other dependencies; a Muse manifest that does not list
exactly the folder's skills; a file in no collection's folder; and a marketplace file
that does not list exactly the collections, each from its folder.

## How a release publishes them

`release.py` builds the collections from the commit it releases and checks them before it
tags anything: collections that fail a check, or a collections file it cannot read, stop
the release with nothing published, a dry run included. It writes the folders into git as
a tree (`build_collections.tree`) and, for each push remote, commits that tree on top of
the remote's `collections` head, so no release rewrites the branch a harness installs
from; a run again after a server error finds the head already holding the tree and
reuses it. The commit takes the release commit's identity and time, unsigned, and names
the commit it was built from, so every remote that shares a head gets the same commit, on
this run or a run again (R1-22: each remote had got its own). The commit goes in the same
atomic push as `main`, `stable` and the tag, and each ref is read back with `git ls-remote`. The commit is made with git's own plumbing
from files the release's commit already holds, so no commit hook runs on it. The branch
must stay writable by the release: a protection rule that requires pull requests on
`collections` would stop every release at its push.

## Installing one

Setup is the way: `setup.py plugin --collections writing` builds the five folders from its
checkout, installs the runtime, then the core and the collection in each harness, and a
later `--collections engineering` adds another (onboarding's
`references/harness-install.md`, "Pick your collections"). The README's "Pick your
collections" also gives each harness's own lines for the branch: Claude Code adds the
repository at `@collections` and installs a collection, which brings the core; Codex adds
it with `--ref collections` and adds the core and the collection; Muse adds
`https://github.com/synthesisengineering/synthesis-skills.git#collections` and installs
both. On 2026-11-14 each line was run in isolated harness homes (Claude Code 2.1.316,
Codex 0.167.0-alpha.4.1, Muse 1.4.20) against a local copy of the branch served over
HTTP, with the real installs' files unchanged before and after: each installed only its
folder's files and listed only its skills; then no collection carried a hook. On
2026-11-20, with the guard in the core, Claude Code 2.1.316 added a folder of the build as
a marketplace, installed a collection with the core as its dependency and listed the
core's four hooks, and Codex 0.169.1 added the same folder as a local marketplace and
installed from it, each in an empty home.

## What is not yet established

- Which skills a signed-in session loads, and how it names them: the isolated homes have
  no sign-in. Each harness's own listing showed only the collection's skills, under the
  plugin's name (`synthesis-skills-engineering:synthesis-code-planning` in Codex).
- Muse with the guard in the core: its launcher updates itself and signs in first, so it
  was not run on 2026-11-20; setup's Muse lines are those it runs for the whole set.
- The branch on GitHub carries the guard in its core from the first release built with
  ruling C8; until then its core has no hooks (its head was `Collections of v5.28.1` on
  2026-11-20).
- In Muse 1.4.20, `muse plugins update` did not move a plugin installed from a marketplace
  to the marketplace's newer snapshot; removing it and installing it again did.

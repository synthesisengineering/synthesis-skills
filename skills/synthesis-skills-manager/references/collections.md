# The collections: the skills in five plugins without hooks

How the five collections are defined, built, checked and published, and what installing
one gives a person. Read it before changing a skill's collection, the collections file or
the build, and when the build or the release's collections stage refuses.

Contents:
- What they are, and what they are not
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
default and is listed first. A collection is for someone who wants one discipline and no
hooks: core, project management, engineering, writing and chief of staff, each a plugin
of its own (`synthesis-skills-<name>`). The core is what the other four build on.

A collection registers no hook and runs no synthesis runtime, so installing one asks for no
approval and changes nothing else on a Mac. It has no guards, no board, no approval codes
and none of the rituals' state; a skill in it that describes those describes the whole
set, and each collection's description says so and names the whole set. The source stays
one flat `skills/` folder, the only layout every harness reads: a collection is a build
output, never a second copy kept by hand.

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
  scripts find them as they do there. The other eleven need the runtime itself (its board,
  approvals, the rituals' records, installing or releasing the whole set): the collections
  file names each under `needs_the_whole_set` with why, and each says so in one line. The
  build reads every collected script's imports from its syntax, through the modules beside
  it, and refuses one that cannot start in its collection unless it is named, one that
  imports the runtime inside a function with nothing to catch the absence, a name that no
  longer fits, and a carried module that imports the rest of the runtime. A test runs every
  collected entry point with `--help` from a built folder on a Mac with no runtime.
- **A path into another skill's folder (R1-20).** Every string of a collected script's
  code, docstrings aside, that names another skill's folder is read: that skill must be in
  the script's collection, or the script must need the whole set, or `optional_loads` must
  name the load with what the script does without it. The rituals' pull-request scan reaches
  the Bitbucket skill's helper, and reports a Bitbucket repository unscanned without it.
- **Links (R1-21).** In the built copy alone, a relative link that resolves in the whole set
  and would lead out of the folder points at the repository's file, or folder, at the
  release's tag; every other byte stays the source's, and a link that leads nowhere in the
  whole set too is left as it is. The build names any link that still leads out.

## What a collection's folder holds

- Every tracked file of its skills that is not a test, byte for byte, but for links that
  would lead out of the folder (above).
- Where its scripts read settings, the runtime's `synthesis/__init__.py` and
  `synthesis/yamlish.py`, and nothing else of the runtime.
- The repository's `LICENSE-APACHE` and `LICENSE-CC0`, the terms its skills' SPDX
  identifiers name.
- Its own `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` and
  `.muse-plugin/plugin.json`, at the repository's version, none registering a hook. Each
  takes the whole set's author, homepage, repository and license; its description is the
  collection's own sentence, then `with_core` (all but the core), then `without`. Every
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
that is no manifest, license or file of the collection's skills, or a test; a file that
differs from its source; a hook folder, a `hooks.json`, or a manifest with a `hooks`
entry that holds anything; a skill or license missing; a manifest that names another
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

The README's "One collection, without the hooks" and onboarding's
`references/harness-install.md` give each harness's lines: Claude Code adds the
repository at `@collections` and installs a collection, which brings the core; Codex adds
it with `--ref collections` and adds the core and the collection; Muse adds
`https://github.com/synthesisengineering/synthesis-skills.git#collections` and installs
both. On 2026-11-14 each line was run in isolated harness homes (Claude Code 2.1.316,
Codex 0.167.0-alpha.4.1, Muse 1.4.20) against a local copy of the branch served over
HTTP, with the real installs' files unchanged before and after: each installed only its
folder's files, listed only its skills, registered no hook and needed no approval. The
same form of each line read this repository's `stable` branch from GitHub.

## What is not yet established

- Which skills a signed-in session loads, and how it names them: the isolated homes have
  no sign-in. Each harness's own listing showed only the collection's skills, under the
  plugin's name (`synthesis-skills-engineering:synthesis-code-planning` in Codex).
- The branch on GitHub itself: the first release with the collections stage creates it.
- In Muse 1.4.20, `muse plugins update` did not move a plugin installed from a marketplace
  to the marketplace's newer snapshot; removing it and installing it again did.

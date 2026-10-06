# A workspace on a new Mac

## Contents

- [Why this is one command with no required flags](#why-this-is-one-command-with-no-required-flags)
- [What it does](#what-it-does)
- [What it never does](#what-it-never-does)
- [Starting a workspace from nothing](#starting-a-workspace-from-nothing)
- [Workspace instructions](#workspace-instructions)

## Why this is one command with no required flags

Enrolling the second Mac by terminal paste on 2026-09-20 failed four ways in an hour,
including a clone that ran silently long enough to look hung (lesson 2026-09-20, fleet
onboarding must be flag-free). So the command finds what it can, asks once for what it
cannot, prints a line per repository as it lands, and resumes after any interruption.

```bash
python3 <checkout>/skills/synthesis-onboarding/scripts/setup.py workspace
python3 <checkout>/skills/synthesis-onboarding/scripts/setup.py workspace --kb URL-or-path [--workspace NAME]
```

The full `setup.py` run offers the same step ("Bring a workspace's repositories onto this
Mac?").

## What it does

1. **Finds the knowledge repository.** With no `--kb`, it asks `gh repo list` for
   repositories named `ai-knowledge-*`. If `gh` needs a sign-in, it starts
   `gh auth login` on the terminal. One match is used; several are offered as a
   numbered choice; none means one question, with a hint of what the URL looks like.
2. **Derives the workspace** from the repository name (`ai-knowledge-<name>`), or asks.
3. **Clones the knowledge repository** to `~/workspaces/<name>/ai-knowledge-<name>`.
4. **Reads `.agents/repos.yaml`** from it (the workspace's repository manifest) with the
   YAML subset reader, and for each listed repository at `~/workspaces/<name>/<path>`:
   - absent: clones it beside the target and renames it into place, so an interrupted
     clone never leaves half a checkout; adds its other remotes (`upstream`, …);
   - present and clean: fetches and fast-forwards to its upstream;
   - present with uncommitted changes, unpushed commits, a diverged branch or no
     upstream: skips it and says so by name;
   - `status: dormant` (or archived): not cloned, and listed.
   Progress prints as `[3/12] repo ...` then `[3/12] repo: cloned`.
5. **Links the workspace** to its knowledge repository: `.agents/repos.yaml`, and
   `AGENTS.md` to `.agents/workspace-AGENTS.md` with `CLAUDE.md` as `@AGENTS.md`.

Ctrl-C prints "run the same command again to resume; finished steps are kept", and a
rerun skips what is done (finished repositories report `current`).

## What it never does

- Repoint a checkout whose `origin` differs from the manifest: it stops and says so.
  For the knowledge repository this stops the whole run, since nothing else can be read.
- Overwrite a folder that is not a git checkout.
- Pull over uncommitted work, or merge a diverged branch.
- Clone repositories the manifest does not list (curated clones only).

## Starting a workspace from nothing

`setup.py workspace --new NAME [--kb URL]` creates `~/workspaces/NAME/ai-knowledge-NAME`
from `assets/workspace/`: `AGENTS.md` with `CLAUDE.md` importing it, `projects/index.yaml`,
`lessons/`, a `source/` bundle declared in `.agents/knowledge-base.yaml` (which the
knowledge-base skills read before editing), `.agents/workspace-AGENTS.md` and a
`.agents/repos.yaml` listing the repository itself. Every seed is the person's from the
moment it exists and is never rewritten. It checks for a git identity before creating
anything, commits exactly the files it wrote (a refused commit is reported with git's own
reason), adds `origin` when `--kb` names one, and links the workspace as below.

## Workspace instructions

If the workspace already has an `AGENTS.md` or `CLAUDE.md` that setup did not create,
it is kept and named. `--adopt-workspace-instructions` replaces them, after moving both
to `~/.synthesis/v5/archive/<timestamp>/`. Edit the tracked source in the knowledge
repository, never the workspace entry points.

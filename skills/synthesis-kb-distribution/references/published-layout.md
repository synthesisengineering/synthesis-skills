# The published tree and the publishing step

Contents:

1. Why one published tree
2. The tree
3. A published knowledge file
4. What the build checks
5. The CI publishing step
6. Giving the plugin to the organization

## 1. Why one published tree

The knowledge base lives as OKF markdown (each file with YAML front matter holding at least
`type`, usually `title`, `description` and a date field) in its own repository, under `source/`.
A build step turns it into one published tree in a separate, private repository. Two channels read
that tree and nothing else:

- the **organization plugin**, which Claude and ChatGPT workspace administrators make available to
  people inside the organization;
- the **connector** (references/connector.md), which serves the same files to people outside those
  workspaces.

Because both read the same commit of the same tree, an answer given through either one can be
traced to the same source commit, and a file left out of the build is left out of both.

## 2. The tree

```text
.claude-plugin/marketplace.json           the marketplace both products read
.agents/plugins/marketplace.json          the same plugin in OpenAI's native marketplace format
README.md                                 what the repository is and that it is generated
plugins/<plugin>/
  .claude-plugin/plugin.json              name, version, description, author
  .codex-plugin/plugin.json               the same, plus "skills": "./skills/" and display text
  plugin.json                             the same manifest at the plugin root
  skills/<plugin>/SKILL.md                the index: front matter, then every file by section
  skills/<plugin>/references/<path>.md    one file per knowledge-base file, at its path under source/
```

- `<plugin>` is the plugin's name, used for both folders; the skill's `name` in `SKILL.md` must
  equal its folder's name.
- `.claude-plugin/marketplace.json` names the marketplace and its owner, then lists the plugin
  with `"source": "./plugins/<plugin>"`, its description and version.
- `.agents/plugins/marketplace.json` lists the same plugin with
  `"source": {"source": "local", "path": "./plugins/<plugin>"}` and an installation and
  authentication policy.
- The version can encode the source commit's date and time, for example `1.<YYYYMMDD>.<HHMM>`, so
  every publication sorts after the one before it.
- `SKILL.md` is the index a model reads first. Its description says what the knowledge base covers
  and when to use it. Its body lists each file as a link (`references/<path>.md`) with its title,
  last-updated date and description, grouped into sections by folder.

The connector needs only `plugins/<plugin>/skills/<plugin>/references/`. When the tree holds more
than one plugin, `KB_REFERENCES_PATH` names the folder to serve.

## 3. A published knowledge file

Each `references/<path>.md` is the source file's front matter, unchanged, then a provenance stamp
as the first line after it, then the source body:

```markdown
---
type: Decision
title: Pricing decision for 2027
description: The decision to move plans to per-seat pricing in 2027.
timestamp: 2026-10-12
---

> Published from `source/datasets/active/pricing-decision.md` in <org>/<kb-repo> at commit `abc1234` (2026-11-01).

# Pricing decision for 2027
...
```

The stamp's exact form is
``> Published from `source/<rel>` in <repo> at commit `<sha7>` (<date>).``, where `<rel>` is the
file's path under `source/`, `<sha7>` the short source commit and `<date>` that commit's date. The
connector parses it into `source_path`, `source_repository`, `source_commit` and `published` in
`fetch`'s metadata, and `KB_DOCUMENT_URL_TEMPLATE` can build a citation address from
`{source_path}` and `{commit}`. A file without the stamp is still served, with those fields empty.

## 4. What the build checks

A build that publishes to every assistant in the organization should stop, rather than publish,
when any of these fail:

- **Front matter.** Every included file has front matter with a non-empty `type` (OKF's hard rule;
  `synthesis-okf`'s validator checks the whole bundle).
- **Exclusions.** An exclusion list of globs relative to `source/` keeps drafts, private notes and
  anything not meant for every reader out of the tree; the build prints each file it left out and
  the glob that matched. `README.md` and hidden paths are never published.
- **Text addressed to an assistant.** Knowledge files describe the organization. A line that
  addresses an AI assistant instead (for example "ignore previous instructions", "you are an AI
  assistant", "system prompt", "do not tell the user") would be read by every assistant that loads
  the plugin or calls the connector, so the build stops and a person decides.
- **Size.** The plugin stays inside the products' current limits on file count, total size and the
  skill description's length; check each product's documentation for the current numbers.
- **Output folder.** The build writes only to a dedicated output folder and refuses to clear any
  folder that is not a previous build's output.
- **Placeholders.** Templates for `SKILL.md` and `README.md` leave no placeholder unfilled.

## 5. The CI publishing step

1. On every merge to the knowledge base's default branch, CI runs the build from a clean checkout of
   that commit, with the commit passed in so every stamp names it.
2. CI pushes the built tree to the private published repository as one commit whose message names
   the source commit. It authenticates with a deploy key that has write access to the published
   repository only, stored in the CI system's secrets.
3. The connector, holding a different, read-only deploy key, sees the new head within
   `KB_REFRESH_SECONDS` and serves it once it loads. Its `/health` shows the served commit.
4. The organization plugin updates when each product syncs the published repository.

Keep the published repository private: it holds every published file in plain text.

## 6. Giving the plugin to the organization

The organization's Claude and ChatGPT administrators add the published repository as an
organization plugin marketplace and make the plugin available to the groups that should have it.
The products' admin consoles change; follow each product's current administrator documentation for
the exact steps and for how the repository is authorized. People outside those workspaces use the
connector instead.

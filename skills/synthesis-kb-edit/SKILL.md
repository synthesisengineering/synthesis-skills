---
name: synthesis-kb-edit
description: >
  Edit, validate, and ship Markdown knowledge-base changes through a repository's
  config-driven workflow. Reads .agents/knowledge-base.yaml for the editable
  bundle, generated/refused paths, topic routing, frontmatter schema,
  confidentiality control, Git host, branching, and review policy. Use when a
  user asks to update a knowledge base, edit KB content, fix a durable fact,
  add a concept, ship an existing KB edit, open a knowledge-base review
  request, or synchronize a local knowledge-base checkout after publication.
license: Apache-2.0
depends_on:
  - synthesis-okf
metadata:
  author: Rajiv Pant
  version: "1.0.0"
---

# Synthesis Knowledge-Base Editing

Run a complete knowledge-base edit in plain language while enforcing the
repository's declared policy. The generic workflow lives here; repository
specifics live only in `.agents/knowledge-base.yaml`.

## Configuration gate

Before interpreting or changing the repository:

1. Locate the Git root and read `.agents/knowledge-base.yaml`.
2. Run:

   ```bash
   python3 <skill-root>/scripts/kb_config.py <repo-root> --check-paths
   ```

3. Stop if the config is absent or invalid. Never infer a bundle, editable
   scope, generated output, confidentiality filter, Git host, or publishing
   policy.
4. Read `notes` and any configured `review.setup_guide`.

The complete contract is in
[`references/knowledge-base-config-v1.md`](references/knowledge-base-config-v1.md).

## Route by intent

- **Edit and ship:** understand the requested change, find its owning concept,
  edit, validate, and follow the configured ship flow.
- **Ship an existing edit:** preserve the user's existing edits, validate their
  exact paths and contents, then follow the configured ship flow.
- **Synchronize after publication:** verify the review request is published,
  fast-forward the configured default branch, and remove the working branch
  only when Git confirms it is merged.

If intent is unclear, ask one plain-language question. Do not make a
non-technical editor choose paths, branches, or Git commands.

## Plain-language interaction

Translate a technical term the first time it matters:

- branch: a separate workspace copy
- commit: save the change as one labeled step
- push: upload the saved change
- pull request: a request to review and publish the change
- default branch: the shared published version
- frontmatter: the settings block at the top of a document

Narrate a state-changing action before it runs and report the outcome without
dumping command output. Follow the current session's authorization rules; this
skill does not widen authority.

## Edit and ship workflow

### 1. Preflight

1. Verify the Git root, configured remote, and configured host.
2. Check the working tree and index. Identify every existing edit and whether
   it belongs to this request. Never discard or silently absorb unrelated work.
3. Verify the configured confidentiality control exists and is operational.
   A protective control that cannot run blocks shipping.
4. Fetch the configured remote so the workspace starts from current remote
   state.

For `git_host: bitbucket`, use `synthesis-bitbucket` or the applicable private
companion skill. For `git_host: github`, use the available GitHub CLI or
connector. Host mechanics do not belong in this skill.

### 2. Find the owning concept

Use `topic_routing` to select likely directories, then search the configured
bundle for every existing mention of the affected entity or fact. Present
candidate concepts by title. Do not create a second concept when an existing
one owns the fact.

For durable facts learned during the current session, compose with
`synthesis-knowledge-capture`: scan every mention, reconcile conflicts, and
preserve provenance before entering this ship workflow.

Classify every candidate path before writing:

```bash
python3 <skill-root>/scripts/kb_config.py <repo-root> --resolve <repo-relative-path>
```

Write only when the result is `editable`. Treat `generated` and `refused` as
hard stops. Capture a request outside editable scope as a reviewer note rather
than changing the file.

### 3. Isolate the work

For `ship: pr`, create one short-lived branch from the fetched remote default
branch using the configured `branch_prefix`. Never commit the edit on the
default branch. Carry pre-existing intended edits onto that branch without
moving unrelated work.

For `ship: direct`, use the repository's declared branching rules. Direct
shipping still requires the authority granted by the user and surrounding
instructions.

### 4. Edit with the declared schema

- Match the concept's established voice and structure.
- Keep one concept per file.
- Use only frontmatter fields declared by `frontmatter.required` and
  `frontmatter.house`, plus fields already allowed by the repository's
  taxonomy.
- Use `frontmatter.date_field` as the only last-update field. Do not add an
  alias such as `last_updated` when the config declares `timestamp`.
- Read `taxonomy_path` before selecting `type`, `tags`, status, or placement.
  Never invent a controlled value.
- Never hand-edit a configured generated artifact.

### 5. Validate before saving

Run all three layers:

```bash
python3 <skill-root>/scripts/kb_config.py <repo-root> --check-paths
python3 <synthesis-okf-root>/scripts/okf_validate.py <bundle-path> --summary --check-links
python3 <synthesis-okf-root>/scripts/okf_consistency.py <repo-root> <touched-path>...
```

The consistency check enforces the configured frontmatter schema and detects
duplicate or conflicting inline metadata, invalid taxonomy values,
title/heading drift, and naming or placement problems. Resolve every
`CONFLICT` and `DUPLICATE`; review every `WARN`.

Then run the configured confidentiality scanner against the exact staged added
lines. Read its pattern source at runtime; never copy its terms into this
public skill. If the scanner or hook cannot run, stop. Never bypass a match or
use `--no-verify`.

### 6. Review and save exactly the intended files

Show:

- what changed, concept by concept;
- which configured schema and taxonomy were applied;
- the conformance, consistency, link, and confidentiality results;
- any reviewer notes for requests outside editable scope.

Stage only the listed editable files. Before committing, inspect both
`git status --short` and `git diff --cached --name-only`; the index must contain
exactly this change. Use a generic commit message when repository policy
requires it.

### 7. Ship through the declared policy

- **`ship: pr`:** push only the working branch and open a review request against
  `default_branch`. Use `review.default_reviewers` when configured. Never merge
  the editor's own request. Report the request number, URL, responsible
  publisher from `review.who_merges`, and what automation runs after merge.
- **`ship: direct`:** push only when current authority and repository rules
  permit it. Verify the remote branch afterward.

Use repository-relative paths in outward-facing text. Do not expose local
absolute paths, secrets, scanner patterns, or AI attribution unless
the user explicitly requests attribution.

## Synchronize after publication

1. Verify the review request or branch is actually published.
2. Ensure the working tree is clean or isolate unrelated work.
3. Switch to `default_branch` and fast-forward from its configured remote.
4. Delete the local work branch only after Git confirms it is merged. Delete a
   remote branch only when repository policy and current authority permit it.
5. Re-run the config and OKF validators on the synchronized tree.

If fast-forwarding fails, stop and surface the divergence. Never force-push or
rewrite shared history.

## Hard invariants

- Config decides; prose recollection does not.
- Claim the repository area on the synthesis coordination board before
  writing when concurrent root sessions are active.
- Editable/refused/generated path rules are mechanical gates.
- One configured date field; no aliases.
- Frontmatter and taxonomy are single sources of truth; remove conflicting
  body copies.
- Never bypass hooks, scanners, reviews, or branch protections.
- Never merge a `ship: pr` edit from the editor workflow.
- Never stage sibling-session work.

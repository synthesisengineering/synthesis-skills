---
name: synthesis-kb-edit
description: "Edit, validate and ship Markdown knowledge-base changes through the repository's .agents/knowledge-base.yaml workflow. Use to update a knowledge base, edit KB content, fix a durable fact, add a concept, ship a KB edit, open a KB review request, or sync a KB checkout after publication."
license: Apache-2.0
depends_on:
  - synthesis-okf
metadata:
  author: Rajiv Pant
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Knowledge-Base Editing

Run a complete knowledge-base edit in plain language while enforcing the
repository's declared policy. The generic workflow lives here; repository
specifics live only in `.agents/knowledge-base.yaml`.

## Binding rules

1. **Config decides; prose recollection does not.** Pass the configuration gate below before anything else; a missing or invalid config stops the work, because every other rule reads it.
2. **Editable/refused/generated path rules are mechanical gates.** Write only where `kb_config.py --resolve` says `editable`; `generated` and `refused` are hard stops, and a request outside editable scope becomes a reviewer note.
3. **One owning concept per fact.** Search every existing mention before writing and never create a second concept for a fact an existing one owns.
4. **One configured date field; no aliases.** Frontmatter and taxonomy are single sources of truth: use only declared fields and controlled values, and remove conflicting body copies.
5. **Validate before saving:** the config check, the OKF validator, the consistency check and the configured confidentiality scanner. A protective control that cannot run blocks shipping.
6. **Never bypass hooks, scanners, reviews, or branch protections,** and never use `--no-verify`. A bypassed control protects nothing.
7. **The index holds exactly this change.** Never stage sibling-session work, and never discard or silently absorb unrelated edits.
8. **Never merge a `ship: pr` edit from the editor workflow,** and never commit it on the default branch; publishing belongs to the reviewer named in `review.who_merges`.
9. **Claim the repository area on the synthesis coordination board before writing** when concurrent root sessions are active.
10. **Never force-push or rewrite shared history.** A failed fast-forward stops and is surfaced.
11. **This skill does not widen authority.** Follow the current session's authorization rules for every commit, push and merge.

## Contents

- [references/edit-and-ship.md](references/edit-and-ship.md): the seven-step edit and ship workflow (preflight, find the owning concept, isolate, edit, validate with the exact commands, review and stage, ship) and the 1.0.0 hard invariants as written. Read it before any edit, and before shipping an existing edit.
- [references/knowledge-base-config-v1.md](references/knowledge-base-config-v1.md): the complete `.agents/knowledge-base.yaml` contract. Read it when the config check fails or a key's meaning is unclear.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives.
- Configuration gate, Route by intent, Plain-language interaction, Synchronize after publication: below.

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

## Synchronize after publication

1. Verify the review request or branch is actually published.
2. Ensure the working tree is clean or isolate unrelated work.
3. Switch to `default_branch` and fast-forward from its configured remote.
4. Delete the local work branch only after Git confirms it is merged. Delete a
   remote branch only when repository policy and current authority permit it.
5. Re-run the config and OKF validators on the synchronized tree.

If fast-forwarding fails, stop and surface the divergence. Never force-push or
rewrite shared history.

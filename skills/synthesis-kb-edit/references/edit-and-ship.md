# Edit and ship workflow

The full procedure for the "edit and ship" and "ship an existing edit" intents, step by step, followed by the 1.0.0 hard invariants as written.

Contents:
- Edit and ship workflow: 1. Preflight, 2. Find the owning concept, 3. Isolate the work, 4. Edit with the declared schema, 5. Validate before saving, 6. Review and save exactly the intended files, 7. Ship through the declared policy
- Hard invariants

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

To import a document, extract: take its information, not its text; put each
fact in the concept that owns it, updated in place, and cite the document.
Convert the whole document only when its full text is the reference. When the
contract names a sharing policy, judge each fact by the policy's test and
classes ([sharing-standard.md](sharing-standard.md)) and count what you leave
out, by class, for the review request.

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

When the contract names a sharing policy (`confidentiality.sharing_policy`),
run its phrase scan over the same staged lines:

```bash
python3 <skill-root>/scripts/sharing_scan.py <repo-root> --staged
```

It prints each hit as where it is (a file and line, a file's name) and the
phrase, and nothing else of the line, and holds any file it cannot read as
text. Read each held line against the policy: a fact in a class comes
out; a line that is right as it stands goes to the reviewer, with the phrase
narrowed or dropped in the contract in the same request. Never reword a line
only to get past the scan. A scan that cannot run (exit 2: no phrases, no
policy or one still the template as written, a bundle git tracks no file
under, an invalid contract) blocks shipping like any protective control.

### 6. Review and save exactly the intended files

Show:

- what changed, concept by concept;
- which configured schema and taxonomy were applied;
- the conformance, consistency, link, and confidentiality results;
- for an import, what was left out, by class and count, never the facts;
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
- **An import's review request** says in its description what was left out,
  by class and count ("Left out: 4 facts (personal and customer data 3,
  negotiated terms 1)"), and never the facts themselves or enough to infer
  them. With `ship: direct`, the same list goes in the report to the user.

Use repository-relative paths in outward-facing text. Do not expose local
absolute paths, secrets, scanner patterns, or AI attribution unless
the user explicitly requests attribution.

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

# Article writing: publication-package review

Phase 4 of the workflow: the title, description, slug, routes and batch an article ships with.

Contents:
- 4.1 Title-only stranger test; 4.2 Newcomer entry lens; 4.3 Title/description/body truth contract
- 4.4 Batch headline monotony review and batch-shape budget; 4.5 Positive reader-value row
- 4.6 Slug and metadata closure invariant (unpublished articles)

## Phase 4: Publication-Package Review (Title, Metadata, and Batch Gates)

Phase 3 reviews the draft. Phase 4 reviews the *package* — title, description, slug, routes, and the batch the article ships with. A body-perfect article can still fail here, and the failure is invisible to any body-focused review. Detailed worked fixtures: [references/publication-review-fixtures.md](publication-review-fixtures.md).

### 4.1 Title-only stranger test (executable obligation)

For every article, the reviewer records six fields. The first four are recorded **before seeing the description or body**; promise match is completed after the body read; the action ruling comes last:

- **subject:** what is this about?
- **stake:** why should the intended reader care now?
- **specificity:** what concrete object, decision, incident, or result anchors the promise?
- **jargon debt:** which word requires project or ecosystem context to parse?
- **promise match:** does the body deliver exactly what the title claims? (filled after the body read)
- **action:** keep, tune, or replace.

A blank or project-internal answer fails the row. **A description cannot repair a failed title-only row** — many surfaces show the title alone. After the title-only pass, run a second title-plus-description pass, because many cards show both. A reviewer that checks bodies but emits no per-article title disposition table cannot sign publication readiness; for a batch, the deliverable is the full N-row table.

### 4.2 Newcomer entry lens

For public work about a named methodology, add one audience fixture: a technically literate reader who has never heard the methodology's name. The title must state a problem or payoff that reader already owns before asking them to care about the category. The methodology name may stay in the title; it must not be the only reason offered to open the piece. **The forbidden repair is hype.** The acceptable repair is clearer subject, stakes, and evidence.

### 4.3 Title/description/body truth contract

Schema validation checks type and length, not truth. Publication review compares four claims for alignment:

- the title's claim;
- the description's claim;
- the lede's claim;
- the body's actual conclusion.

A carefully scoped body with a broadened title or description fails, even when every individual sentence is accurate. **Section headings are metadata too:** a heading that asserts a conclusion its own section never argues fails truth alignment at the same severity as a broadened frontmatter description. The defect is one class at three levels — title against body, heading against section, sentence-level universals — and a check scoped to frontmatter sees only the first.

### 4.4 Batch headline monotony review and batch-shape budget

For a staged batch, classify each title's mechanism (confession/reversal, negation, question, coined principle, numbered result, why/what/how, internal label) and report concentration and adjacent repetition. A high count is not automatically a defect; the reviewer decides whether each instance earns its shape.

**Measure the replacement set on the same axes as the diagnosis.** A proposed cure that reduces the diagnosed formula while raising a different one above threshold fails — a cure measured only against the disease it names is not measured.

Default batch-shape budget (per ~30 titles, tune per corpus):

- no two-word opening repeated more than twice;
- a domain token (such as "AI") only where the title is otherwise ambiguous about its subject;
- no more than one-third of the batch in the imperative or second person.

Mechanical support: the corpus-level checker in `synthesis-content-quality` (`scripts/corpus_repetition.py`) computes opening repetition, token concentration, and register share; the judgment about what earns its shape stays with the reviewer.

### 4.5 Positive reader-value row

For each artifact, state in one sentence what the reader can do, decide, notice, or explain after reading that they could not before. "No slop markers" and "no paragraph fails the deletion test" are negative evidence; they do not establish that the article is worth a stranger's time. A package without a reader-value row is not publication-ready.

### 4.6 Slug and metadata closure invariant (unpublished articles)

For an unpublished article, changing or selecting the final headline **invalidates the URL and metadata plane** until all of the following close together:

1. derive the default slug deterministically from the final selected title;
2. keep a nonmatching slug only through a specific recorded exception — "unchanged" is not an adjudication;
3. migrate every metadata surface together: source path, staged path, frontmatter slug, canonical URL, specialty and dated routes, category/config keys, preview links, and any transaction manifests;
4. search every current body and metadata input for retired internal-link targets; the built preview must contain zero retired routes (historical evidence files that preserve old URLs as records are not current inputs and must not be counted as failures);
5. synchronize source frontmatter and every regenerator so a rebuild cannot restore stale metadata;
6. before publication approval, produce a closed-world per-article table of title / slug / canonical / route;
7. already-published articles are a different regime: their route-preservation-or-redirect decision is publishing policy, never permission to keep stale slugs on unpublished work.

A clean build does not prove editorial correctness of routes: internally consistent stale routes build green.

# Coverage map: reader briefing 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description (588 characters) | Shortened to 291 characters; it keeps the precondition, insider context collapse, series dependency, and the trigger words write article, plan article, brief audience, pre-writing, who is this for and prerequisite |
| Frontmatter metadata | `metadata.version` 2.0.0 and `metadata.format: v5` added; `depends_on`, `source_repo` and `source_type` kept because the onboarding installer (`modular.py`) and agent-conformance read them |
| Title and the two opening paragraphs | SKILL.md (verbatim) |
| Why this skill exists | references/background.md (verbatim) |
| When to apply, When NOT to apply | SKILL.md (verbatim) |
| The four core questions (universal) | SKILL.md (verbatim); distilled into Binding rule 2 |
| How the answers shift by genre (four worked examples) | references/genres.md (verbatim); distilled into Binding rule 3 |
| The series-dependency contract | references/series-dependency.md (verbatim); distilled into Binding rule 4 |
| The audit discipline | references/audit-and-precondition.md (verbatim); distilled into Binding rule 5 |
| The hard precondition | references/audit-and-precondition.md (verbatim); distilled into Binding rule 1 |
| Output format | SKILL.md (verbatim) |
| Related and the closing line | references/background.md (verbatim, except the links below) |
| Binding rules, Contents | New in 2.0.0; each binding rule restates rules already in the sections it names |

## Lines reworded

| Line | Change and reason |
|---|---|
| The five Related entries (`synthesis-thinking-framework`, `synthesis-content-quality`, `synthesis-content-framing`, `synthesis-article-writing`, `synthesis-fact-checking`) | Each link now starts `../../` instead of `../`, because the list moved one directory deeper into references/. The words are unchanged. |

One output path that named the author's own private repository became the placeholder `<your knowledge repo>/projects/<project>/drafts/`: the public plugin must not carry personal paths.

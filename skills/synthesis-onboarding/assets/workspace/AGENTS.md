# ai-knowledge-{workspace}

Personal knowledge base for the `{workspace}` workspace, managed with synthesis
project management (three-tier context: CONTEXT.md / REFERENCE.md /
sessions/ per project).

## Structure

```
ai-knowledge-{workspace}/
|-- projects/            # one folder per project + index.yaml registry
|   `-- index.yaml
`-- lessons/             # cross-project lessons, YYYY-MM-DD-slug.md
```

## Rules

- Active projects are listed in `projects/index.yaml` (status lives there,
  not in folder names).
- Each project keeps working memory in `CONTEXT.md` (<=150 lines), stable
  facts in `REFERENCE.md`, history in `sessions/YYYY-MM.md`.
- Lessons are date-prefixed files in `lessons/` — grep them at session start.

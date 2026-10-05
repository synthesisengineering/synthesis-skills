# Skill format (v5)

Every skill is written so a current model (Opus 5.5, Sonnet 5.5, GPT-6 class)
reads all of it that matters and applies it, even when the skill is long and
even after the harness compacts its context. `tests/test_skill_format.py`
enforces the checkable parts on every skill marked `format: v5`.

## Why these rules

- Codex cuts a plugin's SKILL.md at 8,000 bytes (in its source, not its docs),
  Claude Code re-attaches only the first 5,000 tokens of each loaded skill after
  compaction, and a single file read stops at 25,000 tokens. So SKILL.md stays
  under 8,000 bytes, and no linked file outgrows one read.
- Skill descriptions share a budget of about 1% of the context window, so a
  description says when to use the skill in one or two sentences.
- Models follow structure they can see. A table of contents near the top tells
  the model what exists and when to open it, so linked files actually get read.

## Rules

1. **Frontmatter:** `name`, `description` (at most 300 characters, saying when
   to use the skill), `license`, and `metadata.format: v5`.
2. **Order of SKILL.md:**
   1. One short paragraph: what the skill is for.
   2. `## Binding rules`: numbered, one or two lines each, with the reason.
      These are the rules that must hold every time.
   3. `## Contents`: every section below and every linked file, each with one
      line saying what it holds and when to read it.
   4. The procedure and the rest.
3. **Size:** SKILL.md at most 8,000 bytes (Codex truncates beyond that), so
   the purpose, binding rules and contents always arrive whole. Each linked file at most 1,500
   lines; a linked file over 150 lines opens with its own short contents list.
4. **Split by when it's needed.** Material needed only for one step, one
   situation or one reader goes in `references/<topic>.md`, linked from
   Contents with a "read when" line. Nothing is linked from nowhere: every file
   in `references/` appears in Contents.
5. **No loss (ruling D8).** A skill rewritten into this format carries a
   coverage map, `references/coverage-map.md`, listing every rule of the old
   text and where it now lives. Anything not kept goes to
   `references/preserved.md` with the reason.
6. **Plain words.** Define any term of art in the sentence that first uses it.
   Prefer telling the model why over shouting ALWAYS or NEVER.
7. **Scripts:** every script the skill uses is shown with the exact command
   line and what it prints.

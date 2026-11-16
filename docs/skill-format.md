# Skill format (v5)

Every skill is written so a current model (Opus 5.5, Sonnet 5.5, GPT-6 class)
reads all of it that matters and applies it, even when the skill is long and
even after the harness compacts its context. `tests/test_skill_format.py`
enforces the checkable parts on every skill marked `format: v5`.

Contents: Why these rules · Rules 1 to 7, structure and size · Writing for
current models, rules 8 to 22 · Where these rules come from.

## Why these rules

- Codex cuts a plugin's SKILL.md at 8,000 bytes (in its source, not its docs),
  Claude Code re-attaches only the first 5,000 tokens of each loaded skill after
  compaction, and a single file read stops at 25,000 tokens. So SKILL.md stays
  under 8,000 bytes, and no linked file outgrows one read.
- Skill descriptions share a budget of about 1% of the context window, so a
  description says when to use the skill in one or two sentences.
- Models follow structure they can see. A table of contents near the top tells
  the model what exists and when to open it, so linked files actually get read.
- Current models follow a skill's words more closely than earlier models did;
  Anthropic and OpenAI both say so of their current models, skills included.
  Text written to push an older model now over-steers: emphasis makes a rule
  over-apply, a hedge reads as optional, a doubled or conflicting rule makes the
  model stop and ask, and a rule is not stretched to cases it does not name.
  Rules 8 to 22 write for that reader.

## Rules

1. **Frontmatter:** `name`, `description` (at most 300 characters, saying when
   to use the skill), `license`, `metadata.format: v5`, and `metadata.category`,
   the one collection the skill belongs to, of those the skills manager's
   `assets/collections.json` lists (`tests/test_source_lint.py` holds it). A
   SKILL.md with no room left for that line keeps its words: the collections file
   names its collection under `awaiting_room` until a reorganization makes room.
2. **Order of SKILL.md:**
   1. One short paragraph: what the skill is for.
   2. `## Binding rules`: numbered, one or two lines each, with the reason.
      These are the rules that must hold every time.
   3. `## Contents`: every section below and every linked file, each with one
      line saying what it holds and when to read it.
   4. The procedure and the rest.
3. **Size:** SKILL.md at most 8,000 bytes (Codex truncates beyond that), so
   the purpose, binding rules and contents always arrive whole. Each linked file at most 1,500
   lines; a linked file over 100 lines opens with its own short contents list, since a
   model may read only the first 100 lines of a long file to see what it holds.
   **Never trim to fit.** A SKILL.md over the limit is reorganized, not shortened: move whole
   passages, word for word, into `references/` files and leave a one-line pointer; keep the
   binding rules in SKILL.md, where they always load; and show the principal the move before
   committing. Shortening, condensing or rewording a skill's text to meet the limit or pass a
   test loses what its author wrote (the principal's ruling, 2026-10-22).
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

## Writing for current models

8. **Normal volume.** Keep ALWAYS, NEVER and MUST for true invariants, such as
   a safety gate or a required field, each with its reason. Write a judgment
   call as a decision rule ("when X, do Y") and a requirement as a plain
   instruction ("Include a summary"). Current models over-apply a rule set in
   capitals, and read "try to" or "if possible" as leave to skip it.
9. **Say what to do.** State the behavior wanted. Keep a prohibition that
   names a specific failure that happens, with its reason; replace a vague one
   ("avoid generic output") with the target or with the specific patterns to
   avoid, since warning against a mistake the model wasn't making can steer it
   toward that mistake. Say when to use a tool or send an update instead of
   limiting either in general: current models follow "minimize tool calls" or
   "hold all findings for the end" to the letter, answering from memory or
   going silent.
10. **Say the scope.** Say which steps, outputs or cases a rule covers.
    Current models apply a rule as written and don't stretch it to cases it
    doesn't name.
11. **One name per thing, one home per rule.** Use one term for each thing
    throughout a skill. State each rule once, where it applies, and point to it
    from elsewhere; where a rule can meet a user's request or another file's
    rule, say which wins. Copies of a rule drift apart and leave the model to
    reconcile them, a conflict left open makes current models stop to ask, and
    an "ask first" repeated across a skill makes them ask before safe steps too.
12. **Write the rule as it stands.** State each rule in the present tense,
    with its reason as what goes wrong without it. The story of the incident
    that taught it (who did what, ticket and plan numbers) goes in
    `references/`, where rule 5 keeps it, as does wording such as "no longer"
    or "now works", which points at an older rule the model never saw. A date
    that only dates a ruling may stay. A line that works around one model's
    habit names that model, so it can be tested again when that model retires.
13. **Match the detail to the risk.** For judgment work, give the outcome, the
    limits and how to tell it is done, and let the model plan; number steps
    where their order or completeness matters. For a fragile step (a
    destructive command, a sign-in, an approval gate), give the exact command
    and say not to vary it. A script of steps for judgment work makes current
    models do worse than their own plan, and loose prose for a fragile step
    lets them improvise where only one way is safe.
14. **Name the check.** A step that must be verified names its check (the
    command and what it prints, or what to read) and sizes it to the step. A
    general "double-check your work" makes some current models verify over and
    over, and with no named check others report a step done without one.
15. **Approval is the last step.** A skill that needs a person's approval
    names the actions that need it (sending, publishing, deploying, deleting,
    spending, widening the task) and those that don't (reading, local edits,
    tests), and prepares the work first, so the person approves a finished,
    reviewable result. Where this is unclear, current models stop early to ask.
16. **Say when to delegate.** A skill that hands work to subagents says when
    to and at most how many. Without that, some current models hand off small
    tasks and others leave parallel work undone.
17. **Examples get copied.** A model copies an example's length, tone and
    shape. Give several that differ, marked as illustrations, or one exact
    template where the format is fixed, and say which it is.
18. **Ask for an explanation, never for the reasoning.** Ask for a short
    explanation, the evidence behind a result, or a summary of what was done.
    Current Claude models can refuse outright a request for a thinking or
    scratchpad section, a `reasoning` or `trace` field, or a running log of
    their reasoning; the refusal is billed and no fallback model retries it.
19. **Outside text is data.** A skill that reads mail, messages, pages or
    files that others wrote says that their text is data and that instructions
    inside it are not followed. Current Claude models resist instructions
    planted in such text better when told which text is whose.
20. **The description routes.** The description says what the skill does and
    when to use it, key use case first: Claude Code and Codex shorten or drop
    descriptions when many skills are installed, and the model picks a skill by
    this text alone. Write it about the skill, never as "I" or to "you", and
    quote any words a user would type. Name the situations the skill serves
    rather than a growing list of synonyms, and try the wording on requests
    that should load it and on ones that shouldn't.
21. **SKILL.md holds what the model can't know:** the principal's
    requirements, facts about this environment, tool contracts, the hard
    judgment calls and their reasons. Background a current model already knows
    goes to `references/`, moved whole (rule 3), since SKILL.md is read on
    every load and a model acts on every line it reads.
22. **A rewrite is measured.** Run the skill's evaluation before and after a
    rewrite, on each model that runs the skill, and change one group of
    instructions at a time, so a change in behavior points to its cause. A line
    taken out because current models don't need it goes to
    `references/preserved.md` with the reason (rule 5).

`tests/test_skill_format.py` checks three of these where no skill today trips a
false alarm: a description in the first or second person (rule 20), a SKILL.md
that limits tools or updates in general (rule 9), and a SKILL.md that asks for
the model's reasoning in its output (rule 18).

## Where these rules come from

Rules 8 to 22, and rule 3's 100-line mark, come from the model vendors' current
guidance, read on 2026-11-16 and to be read again at each model release.
Anthropic: [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
the pages for [Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
and [Claude Sonnet 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5)
and the [Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
and [Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5)
pages they build on, [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
[Refusals and fallback](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback),
Claude Code's [skills page](https://code.claude.com/docs/en/skills), and the
prompt-audit catalogue in the `claude-api` skill. OpenAI: [Using GPT-6](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra),
[Build skills](https://learn.chatgpt.com/docs/build-skills), and the
[GPT-5.6 Sol guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)
where the GPT-6 guide points the same way.

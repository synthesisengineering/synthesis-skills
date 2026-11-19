# Rewriting a skill (the D8 standard)

How a skill already in the v5 format is rewritten to the current prompting guidance without losing
anything it says, and how the rewrite ships. [skill-format.md](skill-format.md) says what a skill must
be (rules 1 to 22); this file says how a rewrite gets there. Ruling D8 governs every rewrite: restructure
rather than cut, map every rule to its new place, and keep removed text word for word in the skill's
preserved file. A rewrite ships only when the skill's evaluation shows it at least as good as the version
it replaces. A new skill's text follows the same writing rules (W1 to W19).

The first skill rewritten to this standard is `synthesis-meeting-transcripts` 1.3.0; its coverage map and
preserved file show the method on a real skill.

Contents: What a model reads, and in what order (W1 to W4) · Binding rules (W5 to W8) · Emphasis and
absolutes (W9 to W11) · Positive and negative instructions (W12, W13) · Scope, and where a rule stops
(W14 to W16) · Examples (W17) · Order and length (W18, W19) · Writing for both vendors' models · The
rewrite, step by step · Where this comes from.

## What a model reads, and in what order

1. **The description**, in a listing every installed skill shares. Claude Code budgets the listing at
   1% of the context window, drops the descriptions of the skills used least when it overflows, and caps
   each entry at 1,536 characters. Codex budgets 2% and shortens descriptions first, then leaves skills
   out. The model chooses a skill from this text alone.
2. **SKILL.md**, once the skill is chosen. Claude Code adds it to the conversation once and does not read
   it again; after compaction it re-attaches only the first 5,000 tokens. Codex's documentation says it
   loads the whole file; its source cuts a plugin's SKILL.md at 8,000 bytes.
3. **A reference**, only when a Contents line says when to open it. A model may preview a long file's
   first 100 lines rather than read it whole, and a reference reached through another reference is the
   one most often read in part.
4. **The user's own material**: pasted lines, files, tool output. The skill's rules meet it there, and
   a rule written about the skill's own steps can reach it unless the rule says what it covers.

**W1. Write the description for a listing that may cut it.** Put the key use case and the words a user
would type first (format rule 20). Change a description only with a trigger test: requests that should
load the skill and requests that should not. The evaluation harness puts SKILL.md straight into the
prompt, so it cannot see whether a model would have chosen the skill.

**W2. Make each binding rule complete on its own.** SKILL.md may be all a model reads, and its binding
rules may be all that survives a compaction, so a binding rule never depends on a reference for its
trigger, its scope or its exception. A reference expands a rule; it never narrows or widens it.

**W3. Word what applies throughout a task as a standing rule:** "after every save, verify the saved
file", not "then verify". The model reads the skill once, at the start.

**W4. Keep references one level deep.** Every reference is linked from SKILL.md's Contents with a line
saying when to read it (format rule 4). A reference may point to another for background, never for a
rule the model needs to act.

## Binding rules

**W5. Write each binding rule in this order:** the action, in the imperative, as the bold head; the scope:
the step, input or output it governs, named as the model will meet it; the reason, as what goes wrong
without it; and, when an evaluation has found one, where the rule stops and what to do there instead.

```markdown
N. **<Do this.>** <When, or to which input or output.> <Why: what goes wrong otherwise.> <Where it stops, when known.>
```

The head states the rule by itself; the sentences after it give its scope, its reason and its stop. One
or two sentences after the head; three when the rule has a known stop.

**W6. Keep the numbers.** A rewrite keeps each rule's number. A new rule takes the next free number, and
a retired rule's number is not reused. Evaluation cases, coverage maps and other skills cite rules by
number, so a renumbered rule silently changes what each of them measures.

**W7. Give every stop a narrow trigger.** A rule that makes the model stop, ask, confirm or refuse names
its trigger as the model will see it (the output of a named script, a call that failed, a request to
publish) and says what goes ahead without asking. Current models of both vendors take such rules
seriously enough to stop for them in cases the rule never named: Claude Sonnet 5.5 at low and medium
effort sometimes stops to confirm a plan or asks what it could have answered itself, and OpenAI's GPT-6
guide warns that its models are more sensitive to skill instructions, asks that the user approve a
concrete result rather than each step, and has the model name the skill when a skill makes it stop. In
the pilot, binding rule 9's "a scanned commitment" read as any commitment, and a model asked the user to
confirm one it had read directly from transcript lines the user pasted; the rewrite names the scanner.

**W8. Say which rules hold against a contrary request.** One line at the top of the binding rules says
whether they hold when a request asks otherwise, and how to answer such a request: say which rule
applies and why, then do what it allows. OpenAI's GPT-6 guide recommends stating the priority outright,
and its sample prompt puts the user's instructions ahead of a skill's guidelines; a skill whose rules
protect a record or a gate says that they hold (format rule 11).

## Emphasis and absolutes

**W9. Keep capitals and absolutes for true invariants.** ALWAYS, NEVER, MUST, "critical", "mandatory",
"non-negotiable" and "not optional" mark only a rule that must hold every time (format rule 8), once per
rule and with its reason. Alarm emoji and capitalized headings come out of instruction text. A marker the
skill writes into its output, such as a warning stamp in a saved file, is output format and stays exactly
as specified. Anthropic's guidance says capitalized commands written to make earlier models use a tool
now make current models over-use it, and recommends ordinary wording in their place; OpenAI's GPT-5.6
guidance keeps absolutes for invariants and warns that conflicting rules destabilize more than missing
ones.

**W10. When a rule is missed, make it concrete before making it louder.** First make its trigger concrete (W14), then
move it where it is read (into SKILL.md, or earlier in it). Stronger wording comes last, and only with
the near-miss cases run again, since stronger wording spreads to cases the rule does not cover.
Anthropic's skill-authoring page suggests stronger wording for a rule a model skipped, and its prompting
guide warns that such wording over-triggers; the evaluation decides between them.

**W11. Check by program what must hold every time.** When a rule can be checked by a program (a
pre-commit hook, a guard, a script that refuses), the skill names that check and what it prints, and the
check enforces the rule; the text explains it. Claude Code's skills page advises moving a rule that must
hold every time into a hook, since a hook runs every time its event occurs, whether or not the model is
following the skill.

## Positive and negative instructions

**W12. Say what to do, then the one failure to avoid.** Lead with the behavior wanted. Follow it with a
prohibition only for a failure that has happened, naming its specific form, as the pilot's rule 5 does:
"record that ID; position or a regular expression only guesses, so neither selects". Replace a vague
prohibition with its target (format rule 9). Anthropic
recommends telling Claude what to do instead of what not to do; its Sonnet 5 page finds positive examples
work better than prohibitions, and its Opus 5.5 page finds that a general instruction to avoid something
swaps one default for another, while a list of the specific patterns to avoid works.

**W13. Write in the register the output should have.** Plain sentences and short lists, with bold kept
for rule heads and list labels, and no emoji. A model mirrors the formatting of its prompt (Anthropic: match the prompt's style to the output
wanted), so a skill dense with bold, capitals and emoji produces answers that look the same.

## Scope, and where a rule stops

**W14. Name what a rule governs as the model meets it:** the output of a named script, a tool summary,
a file in a named folder, lines the user pasted. "A commitment" reaches every commitment; "lines the
commitment scanner (`extract_commitments.py`) flags" reaches only those. Claude Sonnet 5 reads
instructions literally and does not carry a rule from one item to another, so a broad rule must say it
is broad; OpenAI's GPT-6 models act on skill text more readily than earlier ones, so a narrow rule must
say it is narrow (format rule 10).

**W15. Add a near-miss sentence when an evaluation finds one.** When a case or a reported answer shows a
rule firing where it should not, add one sentence saying what to do there ("when a line names the
actor, attribute directly"). Do not write near-miss sentences for cases nobody has seen: a warning
against a mistake the model was not making can steer it toward that mistake (format rule 9).

**W16. Say whose text a rule covers.** Material the user brings and text a tool returns are data (format
rule 19). A rule about the skill's own steps or tools does not reach the user's material unless it says
so; when it does, it says so (the pilot's rule 8 applies to transcript lines "fetched or pasted by the
user"). Claude Opus 5.5 resists instructions inside pasted text better when told which text is the
user's own and which was pasted.

## Examples

**W17. Keep an example only where it changes behavior:** a fixed format, marked as the exact template,
or a boundary the rule's words leave unclear, best shown as a pair (one case the rule covers, one it does
not). Mark illustrations as illustrations, vary them in length and shape, and use synthetic names. Put
examples in references unless the format is fixed and short (format rule 17). Anthropic recommends three
to five relevant, varied examples set off from the instructions; OpenAI's GPT-5.6 guidance says to trim
examples that do not change behavior. An example that changes behavior meets both.

## Order and length

**W18. Route after Contents.** Format rule 2 fixes the order: purpose, binding rules, Contents, then the
procedure. A skill that serves more than one kind of request opens its procedure with a short "which
path" list sending each kind to its steps, so a request of one kind does not run another's procedure.
OpenAI's skills post recommends a root document that routes to supporting files; Anthropic's
skill-authoring page shows the same pattern for workflows with decision points.

**W19. Leave room.** A rewritten SKILL.md stays at least 400 bytes under the 8,000-byte limit, so the
next fix fits without a reorganization. Every sentence in it is an instruction, a fact the model cannot
know, or a pointer (format rule 21); history and background move to references whole.

## Writing for both vendors' models

| | Anthropic: Claude Opus 5.5 and Sonnet 5.5 | OpenAI: the GPT-6 family (GPT-6.1 Sol) and GPT-6.2 | What a skill does |
|---|---|---|---|
| Reading | Precise instruction following; Sonnet reads literally, more so at low effort, and does not generalize a rule | GPT-6 is more sensitive to instructions in skills and `AGENTS.md`; its guide asks for an audit of them | States each rule's scope both ways (W14, W15) |
| Stopping to ask | Sonnet 5.5 may stop to confirm or to ask what it could answer; Opus 5.5 follows a list of the stops wanted and not wanted | Finish authorized work before asking; approval on a concrete result; GPT-6.2 asks only on a real change of scope or a block | Names each stop's trigger and what proceeds (W7); approval last (format rule 15) |
| Reasons | Explaining why lets Claude generalize; Claude Code asks skills to say what to do rather than narrate | Describe the destination and decision rules, not every step | One-clause reason per rule; history to references (format rule 12) |
| Precedence | Pasted text's instructions are followed only where the user's own message asks, when the paste is marked | State the priority; the guide's sample prompt puts the user's instructions ahead of a skill's guidelines | Says which rules hold against a request (W8) |
| Emphasis | Aggressive wording written for older models now over-triggers | Absolutes only for invariants; conflicting rules destabilize | W9, W10 |
| Examples | Three to five relevant, varied examples, set apart | Trim examples that change nothing | W17 |
| Checks | Opus checks its own work, and generic check instructions cause over-checking; Sonnet 5.5 at low effort can skip a real check | GPT-6 Astra tests on its own; GPT-6.2 asks for a check that the requested work is complete | Names the one check a step needs, with its command (format rule 14) |
| Reasoning in output | A request for it can be refused (`reasoning_extraction`), is billed, and has no fallback | GPT-6.2's final answer should not copy its reasoning | Asks for an explanation or the evidence (format rule 18) |
| What survives | SKILL.md read once; first 5,000 tokens re-attached after compaction | Descriptions shortened first; SKILL.md cut at 8,000 bytes in Codex's source | Binding rules first and complete on their own (W2) |
| Delegation | Opus delegates readily; cap it | GPT-6's sample prompt delegates whenever work can run in parallel | Says when to delegate and how many (format rule 16) |

**How one skill serves both.** The vendors agree on nearly everything a skill controls: plain volume,
scope stated outright, outcomes for judgment work and exact commands for fragile steps, approval after
the work is ready, and a short description that leads with its use. Where they differ, a skill takes the
form both accept. A one-clause reason is enough for Claude to generalize from and short enough for
OpenAI's destination-first style. An example that changes behavior satisfies Anthropic's advice to use
examples and OpenAI's advice to trim the rest. A named check prevents Opus's over-checking and Sonnet's
skipped check, and gives GPT-6.2 its completion check. A line saying which rules hold against a request
gives OpenAI's models the priority their guide asks for and costs Claude nothing. A line that works
around one model's habit names that model (format rule 12), so it can come out when the model retires.
A repository's skills guide every contributor's agent, whatever model it runs (OpenAI's skills post), so
a rewrite is evaluated on each model that runs the skill (format rule 22).

## The rewrite, step by step

1. **Read before writing:** the whole skill (SKILL.md, every reference, its scripts' usage, its tests),
   its evaluation cases, and the latest gate report for it, with every finding it made about this skill.
2. **Inventory the rules.** List every rule and requirement of the current text, file by file and in
   order, with where each sits (file, section, rule number). The list is the coverage map's first column.
3. **Decide what moves.** What a model needs on every load stays in SKILL.md (format rule 21). A
   procedure for one kind of request moves to its own reference. History and incident stories go to the
   release notes. A file kept only as a record stays as written.
4. **Write the new text** to W1 to W19: SKILL.md and every reference a model follows while it works.
   Records (release notes, version history, earlier coverage maps, preserved text) are not rewritten.
5. **Fix the evaluation's findings** for this skill, each in the rule it concerns, and name each fix in
   the release note.
6. **Map and preserve.** The coverage map gives every inventoried item its new place and how it got
   there: kept, moved word for word, reworded, or merged. Every reworded or removed passage goes word for
   word into `references/preserved.md` with its reason; a passage moved word for word is recorded in the
   map, not copied.
7. **Version.** Bump `metadata.version` the way the repository does: scripts that print the skill's
   version move with it, and the release notes gain the entry. A rewrite that keeps every rule and every
   script interface takes the next minor version; one that retires a rule or changes an interface takes
   the next major.
8. **Test:** `tests/test_skill_format.py`, `tests/test_source_lint.py`, `tests/test_budgets.py` and the
   skill's own tests, then the CI command, `python3 -m pytest -q tests/ skills/`.
9. **Commit in groups:** SKILL.md; the references; the records and the version. Each group passes the
   tests on its own, so a dip at the gate can be traced to one group (format rule 22).
10. **Pass the gate.** The skill's evaluation runs on each model that runs the skill, against the frozen
    answers of the version it replaces. The rewrite ships only when all three hold: the coverage map
    places every rule of the old text; no rule's pass rate falls below the old version's by more than the
    measured noise; and in blind pairwise comparison the rewrite wins or ties more often than it loses,
    and wins outright on at least one rule. A rule that falls is fixed and the evaluation runs again.

## Where this comes from

Read on 2026-11-18, and to be read again at each model release. The standard paraphrases; follow the
links for the vendors' own words.

Anthropic:
- [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices):
  clear and direct instructions, reasons that let Claude generalize, examples, saying what to do,
  matching the prompt's style to the output, softening aggressive wording, self-checks.
- [Prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5):
  naming the stops wanted and not wanted, marking pasted text, specific patterns over general
  prohibitions, reasoning-extraction refusals.
- [Prompting Claude Sonnet 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5):
  initiative and scope, check-ins at low effort, real checks before "done", removing tool-limiting
  wording, genuine user text misread as injection.
- [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
  and [Prompting Claude Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5),
  which the 5.5 pages build on: over-verification, task scope, delegation, literal instruction following,
  positive examples.
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):
  conciseness, degrees of freedom, references one level deep, contents for files over 100 lines,
  consistent terms, templates and examples, evaluations first, testing on every model.
- [Refusals and fallback](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback#keep-reasoning-in-thinking-blocks):
  what a skill must not ask for in a response, and what it can ask for instead.
- Claude Code, [Extend Claude with skills](https://code.claude.com/docs/en/skills): the listing budget,
  the 1,536-character cap, the 5,000 tokens kept after compaction, standing instructions, hooks for rules
  that must always hold.

OpenAI:
- [Using GPT-6](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra), the guide the
  GPT-6.1 Sol model page points to: sensitivity to skills and `AGENTS.md`, stated priority (in its
  words, "The user's instructions take precedence over guidelines provided in a skill"), approval on a
  reviewable result, naming the skill behind a stop, finishing authorized work before asking.
- [Using GPT-6.2](https://developers.openai.com/api/docs/guides/latest-model), the model Codex now
  recommends starting with: outcomes for unsupervised work, when to stop and ask, completion checks,
  final answers that do not copy reasoning.
- [Prompting guidance for GPT-5.6 Sol](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6),
  the generation before GPT-6, used where the GPT-6 guides agree or say nothing: destinations over steps,
  absolutes for invariants, contradictions, examples, repeated "ask first" wording.
- [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra):
  short descriptions, a routing root document, outcomes over recipes, "ask first" wording that stops a
  model early, skills read by several models.
- [Build skills](https://learn.chatgpt.com/docs/build-skills) and Codex
  [Best practices](https://learn.chatgpt.com/guides/best-practices): the listing budget and shortened
  descriptions, front-loaded use cases and trigger words, when a skill should not trigger, one job per
  skill, testing prompts against the description.

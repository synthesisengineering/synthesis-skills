# Anti-shortcuts: when the skill applies, and the scanner

Read it when unsure whether a task calls for this skill, or to run the scanner with its flags. The binding rules in SKILL.md govern: they state each rule's scope whole, and where a wording here differs, the binding rule applies.

## When to Apply

- Before generating any non-trivial implementation plan, design recommendation, or multi-option analysis
- Before accepting a sub-agent's report — especially when the sub-agent self-flags a tradeoff
- Before committing prose to public-facing artifacts where reputation is at stake (READMEs, blog posts, marketing copy, OSS docs)
- Before responding when the user has explicitly stated "complete this, no shortcuts," "best solution," or equivalent
- As part of a pre-response self-check on any draft that touches code, content, or strategy

## When NOT to Apply

- Trivial single-line changes where the implementation is obvious
- Genuine constraint-neutral decisions where the user's input is actually required (e.g., product direction, scheduling, stakeholder facts the agent cannot know)
- Discussions where the agent is teaching about shortcuts, not committing one (the skill recognizes quoted and discussion-mode usage)

## The scanner

`python3 scripts/scan_output.py draft.md` (or text on stdin) prints each hit by category: line and column, the matched phrase, why it is a shortcut, a rewrite framing and a `see:` case. Exit 0 clean, 1 detections, 2 error. Flags: `--json`, `--quiet` (exit code only, for hooks), `--context 120`, `--category <name>`, `--catalog <file>` (JSON or YAML). It reads `costume-catalog.json`, the one public catalog, and skips phrases quoted or in code, since those are being discussed. The v5 Stop hook checks every reply against a short built-in subset of the same catalog.

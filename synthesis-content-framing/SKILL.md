---
name: synthesis-content-framing
description: "Content framing methodology for synthesis engineering articles. Covers topic selection, sophistication standards, engagement patterns, quality gates, and operational rules for publishing technical thought leadership. Use when writing synthesis engineering content, framing technical articles, checking content quality gates, or publishing thought leadership."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Synthesis Engineering"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Content Framing

A methodology for writing and publishing synthesis engineering and synthesis coding thought leadership. This skill covers topic selection, sophistication standards, engagement patterns, quality gates, and operational rules.

**Document structure:**
- **Public Principles** — Core concepts suitable for explanation and public content
- **Quality Gates Summary** — Overview of blocking gates every article must pass
- **Operational Rules** — Mechanics of content creation

For detailed gate criteria and checklists, see: `references/quality-gates.md`

---

# Public Principles

---

## Core Principle

Synthesis coding and synthesis engineering describe **how expert humans direct AI agents** to build software. The human is the leader, decision-maker, and ultimately responsible party. The AI is like a team of tireless, multi-domain expert programmers with vast knowledge — but the human is the boss.

Think of it like managing a team of superpowered beings: a skilled leader knows how to tap into each team member's expertise, learn from their knowledge, delegate effectively, and course-correct when needed — while remaining in charge and accountable.

**The dynamic:**
- Human: Expert leader with deep technical knowledge who makes final decisions
- AI: Tireless, knowledgeable team that executes, suggests, and sometimes errs
- Collaboration: Human directs, AI executes; human verifies, AI iterates

The human isn't a passive recipient of AI output — the human is actively directing, verifying, and learning.

---

## The Expert Operator's Toolkit

Beyond directing and verifying, the expert human uses sophisticated techniques to extract maximum value from AI collaboration:

### Intelligent Questioning

The human asks probing questions to arrive at better answers:
- "What assumptions are you making here?"
- "What could go wrong with this approach?"
- "How confident are you in this recommendation?"
- "What would you need to know to give a better answer?"

### Challenging for Alternatives

The human pushes AI beyond first-pass solutions:
- "What are three different approaches to this problem?"
- "What's the unconventional solution you'd hesitate to suggest?"
- "If we had unlimited time, what would the ideal solution look like?"
- "What would a senior engineer at a top tech company do here?"

### Demanding Options with Tradeoffs

The human requests structured decision support:
- "Present the top three options with pros and cons for each"
- "What are the tradeoffs between approach A and approach B?"
- "Which option optimizes for maintainability vs speed vs simplicity?"
- "What would you recommend and why?"

### Research and Transfer Learning

The human leverages AI's broad knowledge:
- "How have others solved this problem?"
- "What are the industry best practices here?"
- "Are there patterns from [adjacent domain] that apply?"
- "What does the documentation/RFC/specification say about this?"
- "Find examples of how production systems handle this edge case"

### Socratic Exploration

The human uses dialogue to refine understanding:
- "Walk me through your reasoning"
- "Why did you choose X over Y?"
- "What's the mental model I should use here?"
- "Teach me this concept as if I'm a senior engineer who hasn't seen it before"

### Meta-Collaboration

The human optimizes the collaboration itself:
- "How should I prompt you to get better results on this type of task?"
- "What context would help you give a better answer?"
- "What am I not asking that I should be asking?"
- "If this fails, what should we try next?"

**The pattern:** The expert human doesn't just accept AI output — they interrogate it, challenge it, and use the AI's vast knowledge as a resource for better decision-making. The AI becomes a thinking partner, not just an executor.

---

## The Direction Dynamic

The human directs; the AI executes.

**The pattern:**
- "I asked Claude to..." (human initiates)
- "Claude [did X]..." (AI executes)
- "I noticed/caught/identified..." (human verifies)
- "I then directed Claude to..." (human corrects)

**Key distinctions:**

| Action | Who Initiates | Who Executes |
|--------|---------------|--------------|
| Strategy decisions | Human | — |
| Implementation | Human (direction) | AI |
| Verification | Human | — |
| Error detection | Human | — |
| Correction | Human (direction) | AI |

**The human's unique contributions:**
- Setting objectives and constraints
- Providing domain context AI lacks
- Verifying correctness against real-world requirements
- Catching errors before they compound
- Recognizing patterns across multiple sessions
- Systematizing lessons into reusable practices

**The AI's unique contributions:**
- Tireless execution capacity
- Broad knowledge across domains
- Speed of implementation
- Consistency in applying established patterns
- Surfacing options the human might not consider

Both contribute. But the human leads.

---

## The Five Pillars

Synthesis engineering rests on five foundational pillars. They form a mutually-reinforcing loop — not a checklist — in which each pillar depends on the others to function and each one strengthens the others when practiced well.

### Pillar 1: Human Architectural Authority

The human owns the decisions that are hardest to reverse — module boundaries, data flow, where state lives, the security model, how the system fails. AI helps with research, brainstorming, surfacing trade-offs, and stress-testing assumptions, but the final commitment is human.

Architectural vision must persist across months and years; AI operates one conversation at a time. The human is the only continuous mind in the loop, and architectural decisions get more expensive to change the longer a project runs.

When architectural authority remains human, codebases stay comprehensible, multiple engineers can collaborate effectively, and technical debt doesn't accumulate from inconsistent AI-generated patterns.

### Pillar 2: Systematic Quality Standards

AI-generated code is held to the same standards as human-written code. In practice the bar should be higher, because AI produces more code faster, and the cost of letting bad code through scales with volume. The same "I'll fix it later" reflex that produced one shaky function now produces twenty.

Review, testing, security analysis, and performance validation don't get a discount because AI was involved. What changes is that AI is also a tool for meeting these standards more systematically — catching what tired humans miss, writing the tests a human would have written if they had time, flagging the security pattern that looks correct but isn't.

Quality standards are the audit trail that proves Pillar 3 (Active System Understanding) is real and not performed.

### Pillar 3: Active System Understanding

The human stays close to the code — not at the level of "I approved this PR" but at the level of "I could explain what this module does, why it talks to that one, and what fails first when load doubles." The bar is what you would expect from a lead engineering manager who is also expected to read and reason about the code their team ships.

This is the pillar most often eroded in AI-assisted teams, because AI removes the friction that used to force engineers to read carefully. Without that friction, reading becomes a choice. The 2 AM test is the operational version: if the system breaks in production and you cannot debug it, either you have lost touch with the system or the system has grown too complex for the team to hold. Both are problems worth fixing now rather than later.

### Pillar 4: Self-Improving System

Both the project and the practice are evolving systems. Improvement compounds along four threads that run together:

- **Context.** Every session adds to the project's accumulated memory. Decisions made, paths considered and rejected, conventions established. `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `REFERENCE.md`, and session archives capture this so it survives across conversations, across AI tools, and across the people who pick up the project later. Project memory belongs to the project, not to any single AI tool.
- **Skills.** When you find a better way to do something, you codify it. Patterns get named and packaged so the AI applies them next time without being re-taught. The skills library grows from a few personal tricks into a serious system of reusable practices.
- **Instructions.** The files that tell each AI tool how to work in this project get refined every time the AI does something wrong. If the AI keeps making the same mistake, the instruction is the bug, not the AI.
- **Practice.** The discipline of synthesis coding itself improves through everything above, plus what gets shared with other practitioners. Improvement happens at four scales at once: the current project, the team's shared playbook, the practitioner's craft, and the discipline as a whole.

Iterative context building is one element of this pillar. The earlier framing of synthesis coding called out context building specifically; the broader framing recognizes that context is one of four threads, not the whole story.

### Pillar 5: Transferable Knowledge

Knowledge in synthesis coding is built to travel along multiple axes at once, and a piece of work is only as good as the weakest axis:

- **Across people.** Code, documentation, and project memory are written for engineers who were not present when they were created. A new contributor should be able to pick up the project with or without AI assistance.
- **Across AI tools.** The same project memory works in Claude Code, Codex, Cursor, Copilot, and whatever ships next month. Instructions live in files the project owns, not in any one tool's private memory.
- **Across the synthesis crafts.** What is learned in synthesis coding transfers to synthesis writing, and the other direction. Both crafts share the same underlying pattern.
- **Across time.** Your six-months-from-now self is effectively a different person. Project memory is the gift you leave for that person.
- **Across organizations.** The synthesis terminology, the methodology, and the skills library are CC0 public domain. A discipline any team can adopt without negotiation is a discipline that improves in a thousand places at once.

---

## What Synthesis Engineering Is NOT

**Not prompt engineering.** Prompt engineering is a skill within synthesis coding, but synthesis engineering encompasses organizational practices, quality frameworks, lesson capture systems, and more.

**Not AI-assisted work.** Using Grammarly to check spelling is AI-assisted writing. That's fine, but it's not synthesis. Synthesis requires the AI to contribute substantively to the creative or technical work itself.

**Not agentic AI without human oversight.** Autonomous agents running without human review aren't practicing synthesis engineering. The human in the loop is essential, not optional.

**Not "vibe coding."** Vibe coding — casual, exploratory AI use — is great for prototypes, learning, and quick experiments. Synthesis coding is what you graduate to for production work. Different tools for different contexts.

---

## Synthesis Coding vs Other Approaches

| Approach | Best For | Human Role | AI Role |
|----------|----------|------------|---------|
| **Traditional coding** | Full control needed | Writes all code | None |
| **AI-assisted coding** | Speed on known patterns | Writes code, accepts suggestions | Autocomplete, suggestions |
| **Vibe coding** | Exploration, prototypes, learning | Describes intent casually | Generates, human accepts/rejects |
| **Synthesis coding** | Production software | Directs, verifies, decides | Executes, suggests, iterates |

Synthesis coding is the professional discipline for when quality, maintainability, and correctness matter.

---

# Quality Gates Summary

Every article must pass four blocking gates before publication. If any gate fails, stop and fix before proceeding.

1. **Gate 1: Topic Gate** — Is this article about building software? Not content editing, not publishing workflows. The output of the work must be software/code.

2. **Gate 2: Sophistication Gate** — Is the example impressive enough to justify AI collaboration? Minimum scale thresholds apply (10K+ lines, 50+ files, 3+ services). Would this impress engineers at top AI labs or Fortune 500 CTOs?

3. **Gate 3: Engagement Gate** — Is this compelling reading? Does it open with narrative tension, contain earned insights, include vivid specificity, and pass the share/memory/feeling tests?

4. **Gate 4: Confidentiality Gate** — Does this protect all private information? No client names, no business strategy, no internal positioning language.

Beyond gates, articles must also pass safety rules (incident confirmation, confession detection), quality standards (content value, example ethics), and operational checks (attribution, voice, cross-linking).

For full gate criteria, checklists, and examples, see: `references/quality-gates.md`

---

# Operational Rules

---

## Identify the Collaborators

**Wrong:** "I built a content pipeline..."
**Right:** "I built a content pipeline working with Claude Code..."

**Wrong:** "I made a mistake..."
**Right (if AI made the error):** "Claude made a mistake..." or "My AI assistant made a mistake..."
**Right (if human made the error):** "I made a mistake..." (only if truly human error)

**Test:** For every "I" statement describing an action, ask: "Did the human do this, or did the AI do this while the human directed?"

---

## Attribute Errors Correctly

When describing failures or lessons learned:

| Who Actually Erred | How to Write It |
|-------------------|-----------------|
| AI made the error | "Claude assumed..." / "The AI suggested..." / "My assistant removed..." |
| Human made the error | "I decided..." / "I chose..." / "I overlooked..." |
| Both contributed | "Neither of us checked..." / "We both missed..." |
| Human accepted AI error | "I accepted Claude's suggestion without verifying..." |

**Key insight:** In synthesis coding, the human's error is often *accepting* AI output without verification, not *producing* the flawed output.

---

## No Fake Human Collaborators

**Wrong:** "A colleague challenged my approach..." (when it was actually the AI or yourself)
**Right:** "Reviewing the design, I challenged myself..." or "Claude pushed back on my initial approach..."

**Test:** Is every human mentioned in the article a real person? If not, reframe.

---

## Scope Appropriateness

| Topic | Belongs On |
|-------|-----------|
| Hands-on coding practices with AI | synthesiscoding.org |
| Organizational/leadership frameworks | synthesisengineering.org |
| Human team communication | NOT synthesis coding |
| Project management for AI workflows | synthesisengineering.org |

**Test:** Does the article describe working with AI agents on software or software project management? If it describes AI-assisted writing or content creation, it doesn't belong in public synthesis content.

---

## Open Source Authenticity

Name and link to open source projects. Real, verifiable examples build credibility.

**Pattern:**
- When discussing lessons from building tools, name them explicitly
- Link to GitHub repos
- Use real code examples from public repos when helpful
- This adds authenticity and allows readers to verify/explore

**Wrong:** "When building a personal RAG system..."
**Right:** "When building [project-name](https://github.com/username/project-name), my open source RAG system..."

---

## Confidentiality Boundaries

**Must anonymize:**
- Client names (use "a client" or generic descriptions)
- Advisory relationships
- Company names that reveal business relationships
- Project names that could identify clients

**Can discuss freely:**
- Architecture patterns (without client context)
- Technical lessons learned (anonymized)
- Open source project details

---

## Perception Management

**Avoid framing that could be misinterpreted as:**
- "AI replacing human judgment"
- "AI generating journalism/content"
- "AI making decisions autonomously"

**Safe framing:**
- "AI helping build tools that [professionals] use"
- "AI assisting with software development"
- "Human-directed AI collaboration"

The distinction matters for public perception.

---

## Audience Targeting

Each article should have a clear primary audience.

| Audience | What They Care About | Article Focus |
|----------|---------------------|---------------|
| CEO/Business Leader | ROI, competitive advantage, risk | Productivity multipliers, quality outcomes, team scaling |
| CTO | Architecture, tooling, team adoption | Technical patterns, infrastructure, organizational change |
| CPO | Product velocity, quality, user impact | Faster iteration, better outcomes, reduced defects |
| Engineering Lead | Team practices, code quality, process | Workflow patterns, review processes, team coordination |
| Individual Engineer | Daily workflow, skill development | Hands-on techniques, tool usage, career relevance |

**synthesiscoding.org** — Primarily engineers and engineering leads
**synthesisengineering.org** — Primarily CTOs, CPOs, and business leaders

---

## Cross-Linking and Pattern Vocabulary

**Requirements:**
- Name patterns explicitly (Foundation-First, Direction Dynamic, etc.)
- Link to other articles that expand on referenced patterns
- Build vocabulary that becomes industry standard
- Each article should reference at least one other article in the series

**Pattern naming convention:**
- Use title case for named patterns: "Foundation-First Pattern", "Direction Dynamic"
- Be consistent across articles
- Create a growing vocabulary readers can reference

---

## Terminology Consistency

**Lowercase in prose:**
- synthesis coding
- synthesis engineering
- synthesis project management

**Title case in headlines/titles:**
- "The Foundation-First Pattern"
- "Synthesis Engineering Best Practices"

**Never:**
- synthesis-coding (no hyphen)
- Synthesis Coding (mid-sentence)

---

## Theory and Practice Balance

Each article should include:
- **Concrete example** — A real (or composite) incident that illustrates the pattern
- **Pattern extraction** — The generalizable lesson
- **Practical application** — How readers can apply this

Avoid pure theory without examples. Avoid pure anecdotes without extracting patterns.

---

## External Validation

When external sources validate synthesis engineering concepts, reference them. This builds credibility and shows the ideas are independently emerging.

**Pattern:**
- "This pattern was independently validated by [source]..."
- Add an "Update" note to existing articles when relevant external validation emerges

External validation from respected sources strengthens the framework's credibility without relying solely on personal experience.

---

## Update Notes for Evolving Articles

When adding significant new content to published articles, use update notes.

**Format:**
```markdown
*Updated [Date]: [Brief description of what was added and why]*
```

**Placement:** After the TL;DR or introduction, before the main content.

Readers trust content that's transparently maintained. Updates show the discipline is actively evolving based on new evidence.

---

## Audience Declaration

State the primary audience in the opening paragraphs or as part of the article's setup.

**Good examples:**
- "I wrote this blog post for software engineers, architects, and technical leads."
- "This article is for CTOs, VP of Engineering, or Engineering Directors evaluating synthesis coding..."

**Pattern:** First or second paragraph should clarify who the article is for.

---

## Series Integration

Each article should acknowledge its place in the broader synthesis engineering/coding series.

**Patterns:**
- Link to synthesiscoding.org or synthesisengineering.org as the series home
- Reference "the synthesis engineering series" or "the synthesis coding series"
- Include a closing note like: "This article is part of the synthesis engineering series."
- Cross-link to related articles for deeper dives on specific topics

---

## CC0 Public Domain Notice

When appropriate, include the public domain release for terminology and concepts.

**Use when:**
- Introducing the synthesis engineering/coding terms to new audiences
- In foundational articles explaining the discipline
- When inviting others to use the terms

**Standard language:**

> *Synthesis engineering is an open methodology. The terminology and concepts are released to the public domain (CC0). Build on them, adapt them, share them.*

or:

> These terms -- synthesis engineering for the discipline, synthesis coding for the craft -- are offered to the community without restriction. They're released under CC0 1.0 Universal (public domain) for anyone to use, modify, or build upon.

## Related

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.

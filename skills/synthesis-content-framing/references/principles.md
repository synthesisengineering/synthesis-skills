# Public Principles

The core concepts of synthesis engineering and synthesis coding, suitable for explanation and public content.

Contents:
- Core Principle: the human leads; the AI is a tireless expert team
- The Expert Operator's Toolkit: intelligent questioning, challenging for alternatives, options with tradeoffs, research and transfer learning, Socratic exploration, meta-collaboration
- The Direction Dynamic: who initiates and who executes, and each side's contributions
- The Five Pillars: human architectural authority, systematic quality standards, active system understanding, a self-improving system, transferable knowledge
- What Synthesis Engineering Is NOT
- Synthesis Coding vs Other Approaches

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

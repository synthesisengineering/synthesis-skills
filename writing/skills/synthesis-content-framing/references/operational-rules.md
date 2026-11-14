# Operational Rules

The mechanics of creating synthesis engineering content: how to attribute work, what to keep private, and how an article fits the series.

Contents:
- Identify the Collaborators
- Attribute Errors Correctly
- No Fake Human Collaborators
- Scope Appropriateness: which site a topic belongs on
- Open Source Authenticity
- Confidentiality Boundaries
- Perception Management
- Audience Targeting
- Cross-Linking and Pattern Vocabulary
- Terminology Consistency
- Theory and Practice Balance
- External Validation
- Update Notes for Evolving Articles
- Audience Declaration
- Series Integration
- CC0 Public Domain Notice, with the standard language

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
- Link by dependency, not by quota: the reader-briefing's series-dependency contract (`synthesis-reader-briefing`) decides whether an article is `standalone`, `standalone after compact context`, or a `true prerequisite` case. A true prerequisite requires a link plus a one-sentence reason to read it first; a standalone article carries no obligatory series link. A blanket at-least-one-cross-reference quota produces formulaic over-context and is retired.

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

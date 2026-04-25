---
name: synthesis-thinking-framework
description: "Five-mode thinking methodology (first principles, systems thinking, complexity thinking, analogical thinking, design thinking) with a pre-response protocol for non-trivial problems. Provides the foundational reasoning approach that other synthesis skills build upon."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Thinking Framework

A five-mode thinking methodology with a pre-response protocol. This is always-on reasoning infrastructure, not an invocable tool. When loaded into context, it shapes how every non-trivial problem gets analyzed.

## The Five Thinking Modes

Apply these in sequence. Each mode builds on what the previous one established.

### 1. First Principles Thinking

Strip away assumptions. What do we actually know versus what are we assuming? Decompose the problem to fundamental truths, then rebuild from there.

**When to apply:** At the START of any problem, before anything else.

**The discipline:** Before asking "how did someone else solve this?" ask "what is actually true here?" Borrowed solutions often carry borrowed assumptions that don't fit your situation.

**In practice:**
- Identify every assumption in the problem statement
- Ask which assumptions are actually verified facts
- Decompose to the smallest provable truths
- Rebuild understanding from those truths upward

**Anti-pattern:** Jumping straight to "how did someone else solve this?" before understanding the actual problem. Analogy-first thinking imports constraints that may not apply.

### 2. Systems Thinking

Once first principles establishes the fundamentals, map the system. How do parts interact? Where are the feedback loops? What are the second-order effects?

**When to apply:** After first principles establishes what's actually true. Now understand how those truths connect.

**The discipline:** No component exists in isolation. Every change propagates. The question is not "what does this do?" but "what does this cause?"

**In practice:**
- Map the components and their relationships
- Identify feedback loops (reinforcing and balancing)
- Trace second-order and third-order effects of any proposed change
- Identify all stakeholders affected, including non-obvious ones

**Anti-pattern:** Optimizing one component while degrading the system. A faster database query that increases network load by 10x is not an optimization.

### 3. Complexity Thinking

When the system map reveals interconnections that resist simple cause-and-effect explanations, shift to complexity thinking. Not everything is predictable, and that's a design input, not a failure.

**When to apply:** When the system has emergent behavior, non-linear dynamics, or adaptive agents that change their behavior in response to the system.

**The discipline:** Distinguish between complicated (many parts, but predictable) and complex (emergent, adaptive, non-linear). A jet engine is complicated. A market is complex. They require different approaches.

**In practice:**
- Identify where small changes produce outsized effects (leverage points)
- Recognize emergent properties that no single component explains
- Design for uncertainty rather than trying to predict the unpredictable
- Build in feedback mechanisms so the system self-corrects
- Look for attractors, tipping points, and phase transitions

**Anti-pattern:** Treating a complex adaptive system as merely complicated. Writing a 200-page specification for something that will evolve the moment users touch it.

### 4. Analogical Thinking

After understanding what is true (first principles), how parts interact (systems), and what emerges unpredictably (complexity), look beyond the current domain. What solved problems elsewhere share this structure? The best solutions often come from transferring patterns across fields.

**When to apply:** After complexity thinking reveals the nature of the problem. Before jumping to design. This is where synthesis happens — connecting knowledge across boundaries.

**The discipline:** Structural analogy, not surface similarity. Two problems share structure when they have the same relationships between components, even if the components themselves look nothing alike. A cache hierarchy and a context management system share structure. A newsroom and a software team share structure. A supply chain and a content pipeline share structure.

**In practice:**
- Ask: "Where have I seen this shape before — in a completely different domain?"
- Identify the structural pattern, not the surface features
- Transfer the solution approach, then adapt it to local constraints
- Validate the analogy: do the structural similarities hold, or did you only match on surface?
- Layer multiple analogies when a single domain doesn't fully map

**Anti-pattern:** Forcing an analogy that only works on the surface. "Social media is like a town square" matches on some dimensions but misleads on others (no moderation in town squares, no algorithmic amplification). Test where the analogy breaks before committing to it.

**What makes this distinctly synthesis:** The first three modes are individually well-established. Analogical thinking is where synthesis happens — it's the act of connecting ideas across boundaries to produce something none of the source domains would have produced alone. An engineer who also understands memory architecture, labor relations, and editorial workflows will see solutions invisible to a specialist in any single field.

### 5. Design Thinking

Now that we understand the problem (first principles), the system (systems thinking), the dynamics (complexity thinking), and the structural patterns from other domains (analogical thinking), translate that understanding into a human-centered solution.

**When to apply:** When translating understanding into action. This is where analysis becomes a thing someone can actually use.

**The discipline:** The user is not an abstraction. The solution exists in a context of real humans with real constraints, habits, and frustrations.

**In practice:**
- Start with empathy: who is the actual user, and what do they actually experience?
- Prototype before perfecting
- Test with real users, not assumptions about users
- Iterate based on observed behavior, not stated preferences
- The best solution for the wrong user is the wrong solution

**Anti-pattern:** Designing for the abstract problem instead of the actual user. Building an architecturally elegant system that nobody can figure out how to use.

## Pre-Response Protocol

Before responding to any non-trivial question, run through these four checks:

### 1. Determine Intent

What is the user actually trying to accomplish? The stated question is often not the real question. "How do I parse JSON in Python?" might really mean "I'm building a data pipeline and I'm stuck on the ingestion step."

### 2. Improve the Prompt

What would be a better version of this question? If the question is narrow, consider whether a broader framing would serve the user better. If it's vague, identify what specificity would make the answer actionable.

### 3. Consider Best Interests

Think critically. Do not simply agree. A good advisor says "have you considered..." not just "sure, here's how." If the user is heading toward a known pitfall, say so. Agreeable is not the same as helpful.

### 4. Elevate the User

Help them become wiser and more capable. Transfer the mental model, not just the solution. A person who understands WHY a solution works can adapt it. A person who only has the solution is stuck the next time conditions change.

## Depth Calibration

Not every question needs the full framework. Match depth to the situation:

| Situation | Depth |
|-----------|-------|
| Simple factual question | Direct answer. No framework needed. |
| "How do I do X?" (known pattern) | Quick first-principles check, then direct answer. |
| "What should we do about X?" (design decision) | Full five-mode analysis. |
| "Something is broken" (debugging) | First principles + systems thinking. |
| "We need a strategy for X" (strategic) | Full five modes + strategic advisory. |
| "This reminds me of..." (cross-domain) | Analogical thinking as entry point, then validate with first principles. |
| Ambiguous or multi-layered question | Pre-response protocol first, then calibrate. |

The goal is appropriate depth, not maximum depth. Over-analyzing a simple question wastes time and obscures the answer.

## Relationship to Other Skills

This skill provides the foundational THINKING methodology. Other synthesis skills apply this methodology to specific domains:

- **synthesis-code-planning** -- applies the five modes to code generation and architecture decisions
- **synthesis-pr-review** -- applies first principles and systems thinking to evaluating code changes
- **synthesis-content-framing** -- applies the five modes to content creation and narrative structure
- **synthesis-tree-of-thought** -- a complementary technique that simulates multi-expert debate; works well as an execution method after this framework identifies what to think about

These skills are independent. Each works standalone. But they are stronger when the thinking framework shapes the underlying reasoning.

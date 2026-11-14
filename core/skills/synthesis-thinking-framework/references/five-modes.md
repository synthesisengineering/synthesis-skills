# Thinking framework: the five modes

The five thinking modes in full: when to apply each, its discipline, how it looks in practice, and its anti-pattern.

Contents:
- How to use the modes
- 1. First Principles Thinking
- 2. Systems Thinking
- 3. Complexity Thinking
- 4. Analogical Thinking
- 5. Design Thinking

## The Five Thinking Modes

Start with what is known and the applicable constraints. Then use the modes that answer the unresolved questions. For a strategic or unfamiliar problem, the sequence below helps expose interactions and test alternatives. For a diagnosed defect or an already-decided change, use the relevant modes and proceed to execution. A skipped mode needs no ceremony; an unexamined material risk needs investigation.

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

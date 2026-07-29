# Quality Gates and Operational Rules

Detailed blocking gates, safety rules, and quality standards for synthesis engineering content. Every article must pass all gates before publication.

---

# BLOCKING GATES

These gates are evaluated FIRST. If any fails, STOP. Do not proceed to other checks.

---

## Gate 1: Topic Gate (BLOCKING)

Before ANY other evaluation, ask the fundamental question:

### Is this article about WRITING SOFTWARE?

**PASS if the work described is:**
- Building applications, services, APIs, tools
- Writing code (functions, classes, modules, tests)
- Refactoring codebases
- Debugging software
- Designing system architecture
- Implementing features
- Building deployment pipelines
- Creating development tooling

**FAIL if the work described is:**
- Editing articles, blog posts, or content
- Content pipelines (fetching, converting, publishing text)
- Formatting or styling documents
- Managing content across sites
- Any work where the OUTPUT is text/content, not software

**The test:** Replace "Claude" with "a human developer" in the article. Does it still describe software engineering work? If the work is "editing articles" or "updating content" -- it's not software engineering.

### Examples

**PASS:** "Working with Claude Code, I was migrating a Node.js codebase from callbacks to async/await."

**FAIL:** "Working with Claude Code, I was updating articles across a site -- changing URLs, fixing formatting."

**PASS:** "I built a data processing pipeline: an ingestion service that parsed logs, a transformation service that normalized data."

**FAIL:** "I built a content pipeline: fetch from WordPress, convert to markdown, preview locally."

---

## Gate 2: Sophistication Gate (BLOCKING)

### Audience Sophistication Standards

**For Engineers (Primary audience: AI/ML engineers, senior software engineers)**

**The bar:** Would this impress and engage engineers at top AI labs?

**Requirements:**
- Technical depth that assumes familiarity with distributed systems, ML pipelines, or complex architectures
- Examples involving scale (millions of records, thousands of files, global distribution)
- Patterns that solve problems these engineers actually face
- Novel insights they haven't seen in standard literature
- Code examples that demonstrate sophisticated techniques, not basic patterns

**Engagement requirement:** The article should make them want to try the technique immediately, share with their team, or argue about the approach.

**Automatic rejection if:**
- The example could be solved in under an hour by a competent engineer
- The pattern is covered in any "intro to X" tutorial
- The scale is embarrassingly small (single files, simple scripts, "a few pages")
- The insight is something any senior engineer already knows

**For Engineering Leaders (CTOs, VPs of Engineering, Directors)**

**The bar:** Would this impress a CTO at a Fortune 500 company or a unicorn startup?

**Requirements:**
- Strategic implications, not just tactical patterns
- Organizational scaling challenges
- ROI and productivity multiplier evidence
- Risk management at enterprise scale
- Patterns for leading teams of engineers using AI

**Engagement requirement:** The article should make them want to share with their leadership team, reference in a strategy document, or use as the basis for a team initiative.

**Automatic rejection if:**
- The example is individual productivity, not team/org scale
- The insight doesn't translate to organizational strategy
- A competent engineering manager already knows this

**For Product Leaders (CPOs, VP Product, Product Directors)**

**The bar:** Would this impress a CPO at a top-tier tech company?

**Requirements:**
- Product velocity implications
- Quality/speed tradeoff resolution
- User impact and experience considerations
- Feature delivery acceleration patterns
- Cross-functional collaboration models

**Engagement requirement:** The article should make them want to discuss with their peers, share with their product org, or pilot a new approach.

**Automatic rejection if:**
- Purely technical without product implications
- Doesn't address product delivery challenges
- No clear user or business impact

**For Business Leaders (CEOs, Board members, Investors)**

**The bar:** Would this be credible in a strategic discussion?

**Requirements:**
- Business outcome focus (speed, cost, quality, competitive advantage)
- Risk and governance considerations
- Market positioning implications
- Clear ROI narrative

**Engagement requirement:** The article should be reference-worthy for strategic planning.

**Automatic rejection if:**
- Too technical without business translation
- No clear strategic or financial implications
- Sounds like engineering advocacy without business grounding

### Scale and Complexity Requirements

**Minimum scale thresholds:**

| Dimension | Minimum for Articles | Why |
|-----------|---------------------|-----|
| Codebase size | 10,000+ lines or 50+ files | Smaller codebases don't need AI assistance |
| Data volume | Thousands of records or millions in production | Toy data doesn't demonstrate scale benefits |
| System complexity | 3+ interacting services/components | Single-service examples are too simple |
| User impact | Thousands of users or significant business process | Personal tools don't impress |
| Time saved | Days or weeks of human effort | Hours don't justify the methodology |

**Acceptable scope indicators:**
- "across 47 microservices"
- "2 million lines of legacy code"
- "processing 50M events daily"
- "12 different API versions"
- "serving 100K concurrent users"

**Unacceptable scope indicators:**
- "a few files"
- "my personal project"
- "a simple script"
- "updating some pages"
- "a basic refactoring"

**The principle:** If the example doesn't sound like it needs agentic AI, it undermines the article's thesis.

### Sophistication Tests

**Test 1: Sophistication Test**

**Ask:** "Is this example sophisticated enough to justify AI collaboration?"

**Automatic rejection if:**
- A competent engineer could do this without AI in under an hour
- The complexity doesn't require multi-step reasoning or large-scale analysis
- The example is "toy scale" (single file, simple script, basic refactoring)
- The work described is something juniors do as learning exercises

**What passes:**
- Work that would take days or weeks for a human alone
- Complexity that benefits from AI's ability to hold large contexts
- Multi-system reasoning that requires synthesizing information across codebases
- Scale that makes manual work impractical

**Test 2: "Why AI?" Test**

**Ask:** "Why did this require agentic AI? What would have been different without it?"

**Automatic rejection if:**
- The article never explains why AI collaboration mattered
- The work could have been done just as easily by a human
- The AI's contribution is trivial (autocomplete-level assistance)
- There's no moment where AI capability was essential

**What passes:**
- Clear "AI unlocked this" moments
- Explicit comparison to how long/difficult this would be without AI
- Examples where AI's breadth of knowledge or tireless execution was essential
- Patterns that only emerge from AI-scale collaboration

---

## Gate 3: Engagement Gate (BLOCKING)

**The goal:** Every article should be something readers want to share, discuss, and return to.

### The Engagement Tests

**Test 1: The Share Test**
- Would a reader screenshot a passage and share it on Twitter/LinkedIn?
- Would they send it to a colleague with "you need to read this"?
- Would they bookmark it for future reference?

**Test 2: The Conversation Test**
- Would this spark discussion in an engineering team's Slack?
- Would it come up in a 1:1 between an engineer and their manager?
- Would people argue about it (in a productive way)?

**Test 3: The Memory Test**
- A week later, would the reader remember a specific insight or story?
- Would they be able to retell the key example to someone else?
- Does it have a "sticky" moment that lodges in memory?

**Test 4: The Feeling Test**
- Does the reader feel energized after reading?
- Do they feel like they learned something valuable?
- Do they feel motivated to try something new?

### What Makes Content Engaging

**Narrative tension:**
- Open with a problem, mystery, or surprising situation
- "This worked perfectly. Until it didn't."
- "The dashboard showed impossible patterns."
- Create stakes -- something was at risk, something mattered

**Vivid specificity:**
- Not "the system failed" but "at 2:47 AM, the monitoring alert triggered for the third time that week"
- Not "many files" but "2,847 files across 12 repositories"
- Concrete details make abstract concepts real

**Earned insight:**
- The reader should feel they discovered something alongside the author
- Build to the insight -- don't just state it upfront
- The "aha" moment should feel satisfying

**Human moments:**
- Frustration, surprise, satisfaction -- show the emotional arc
- "I stared at the logs for ten minutes before I saw it"
- "The fix was embarrassingly simple"
- Readers connect with human experience, not just technical facts

**Memorable framing:**
- Give concepts names that stick: "The Foundation-First Pattern"
- Use metaphors that illuminate: "like hiring a senior engineer on their first day"
- Create mental models readers can reuse

**Pacing and rhythm:**
- Vary sentence length and structure
- Short punchy sentences for emphasis. Longer ones for complex ideas that need room to breathe and develop.
- Strategic white space -- not walls of text

### What Kills Engagement

**Abstract generalities:**
- "Systems can fail in various ways" -- who cares?
- "Best practices are important" -- obviously

**Predictable structure:**
- Setup, three bullet points, conclusion -- boring
- Every section the same length -- monotonous

**Missing stakes:**
- Why should the reader care?
- What was at risk? What mattered?

**Dry recitation:**
- "First we did X, then Y, then Z" -- tedious
- No narrative arc, just chronology

**Hedged conclusions:**
- "This might help in some situations"
- Readers want conviction, not disclaimers

### Examples of Engagement Patterns

**Strong opening (narrative hook):**
> "The query 'what's in my biography' failed to find the biography file. 'Show me my biography' worked fine. That apostrophe broke everything."

vs. weak opening:
> "In this article, we'll explore how punctuation affects search queries in RAG systems."

**Strong insight reveal:**
> "The fix was embarrassingly simple. I directed Claude to add normalization: `query = query.replace("what's", "what is")`"

vs. weak conclusion:
> "Therefore, text normalization is an important consideration for search systems."

**Strong emotional moment:**
> "I stared at the dashboard showing impossible patterns -- aggregations grouped by nonsensical time buckets. The data corruption had been happening for days before I noticed."

vs. flat description:
> "The aggregations were incorrect due to the timestamp mismatch."

---

# SAFETY RULES

---

## Incident Confirmation Gate (CRITICAL)

Some lessons are only valuable internally. Publishing them externally confirms things better left unconfirmed.

### AUTOMATIC REJECTION if an article:

1. **Confirms a real security or confidentiality incident occurred**
   - "The sequence of events is real"
   - "I experienced this recently"
   - "Names are sanitized but this happened"

2. **Describes failure patterns that could invite investigation**
   - Details about what was leaked
   - Details about where it was leaked
   - Details about how it was discovered
   - Anything that makes readers think "I wonder what was actually leaked"

3. **Draws attention to attack surfaces where past leaks might be discovered**
   - Git history
   - Commit messages
   - Archive services

4. **Provides enough detail that the incident could be traced**
   - Even with "sanitized" names
   - Even with "hypothetical" framing
   - If it happened to you and you're describing it, it can potentially be traced

### What's acceptable:

- **Hypothetical scenarios** -- "Imagine this happened..." with no confirmation it did
- **Industry examples** -- Other people's public incidents
- **Generic patterns** -- Without confirming personal experience
- **Lessons from completely anonymized contexts** -- Where nothing can be traced

### The Meta-Test for Incident Articles:

**Ask:** "Does publishing this article CAUSE the harm it describes?"

If the article warns about how publicizing incidents draws attention to them, and you're publishing it to describe an incident... you're causing the harm.

---

## Confession Detection (CRITICAL)

### AUTOMATIC REJECTION if an article:

1. **Uses "lessons learned from mistakes" framing about security/privacy**
   - "I've learned these lessons through incidents I'd rather not have experienced"
   - "From incidents I've seen, these patterns commonly reveal things"
   - Any implication that the author has had security or privacy incidents

2. **Provides a checklist for preventing YOUR OWN past mistakes**
   - If the article reads like "here's what I do now to prevent the problems I used to have"
   - If the advice is suspiciously specific to your actual workflow

3. **Describes patterns that match your internal practices**
   - Grep patterns that match your actual sensitive terms
   - Workflow descriptions that match your actual workflows
   - Configuration patterns that match your actual configs

4. **Implies repeated incidents**
   - "incidents" (plural)
   - "these patterns commonly reveal"
   - "I've seen this happen"

### The meta-test:

**Could a reader use this article to investigate YOU?**

If the article describes what patterns to grep for, what configuration reveals, what commit messages expose -- and those patterns match YOUR actual practices, you've just published a guide to investigating yourself.

### What's acceptable:

- Generic security advice that doesn't reveal your specific practices
- Industry-standard checklists that don't match your specific workflow
- Advice framed as proactive best practices, not lessons from incidents

---

## Deployment Verification (CRITICAL)

Deleting source files is not the same as deleting deployed content. For static sites with build steps, deletion requires:

### For Static Site Content Deletion:

1. **Delete from source** (content/posts/)
2. **Rebuild the site** (`npm run build` or equivalent)
3. **Verify deleted from output** (check output directory)
4. **Commit and push** the updated build output
5. **Wait for deployment** (check deployment status)
6. **Verify live URL returns 404** -- not 200, not redirect
7. **Only then report completion**

### The Verification Requirement

**"Deleted" means nothing until the live site returns 404.**

- GitHub showing file deleted? Not enough.
- CMS showing draft? Not enough.
- Build output clean? Not enough.
- Deployment triggered? Not enough.

**The only verification that counts: `curl -o /dev/null -w "%{http_code}" "URL"` returns 404.**

### CDN Caching

If the live site still returns 200 but the deployment preview returns 404:
- The deployment is correct
- The CDN is serving cached content
- Note this explicitly: "Deployment shows 404, main domain cached for X minutes"
- Consider cache purge if content is critically harmful

### Never Report Partial Completion

Wrong: "I deleted the source and pushed. The article should be gone soon."

Right: "Deleted source, rebuilt, pushed. Deployment preview returns 404. Main domain still cached (age: 217s, expires in ~56m)."

---

# QUALITY STANDARDS

---

## Content Value Gate

**This rule applies at TWO levels:**
1. **Article level** -- The whole article must pass
2. **Section level** -- Every section, paragraph, and sentence must earn its place

If a section doesn't pass these tests, cut it. Filler dilutes value and wastes reader time.

### Test 1: Novel Value Test

**Ask:** "What does this article give readers that they couldn't get elsewhere?"

**Automatic rejection if:**
- The main lesson is "verify AI output" or "check your work" -- everyone knows this
- The article restates common knowledge without new framing or application
- A senior engineer would read this and think "I already knew all of this"
- The article could be summarized in a tweet with no loss of value

**What passes:**
- Introduces a named pattern that readers can reference and use
- Provides a framework that changes how readers think about the problem
- Shares specific, actionable techniques that readers can apply immediately
- Connects ideas in ways readers haven't seen before

### Test 2: So What Test

**Ask:** "If someone reads this, so what? What changes for them?"

**Automatic rejection if:**
- The article describes what happened without extracting transferable lessons
- The takeaway is vague ("be more careful", "think things through")
- Readers couldn't explain what to do differently after reading

**What passes:**
- Clear, specific actions readers can take
- Named patterns they can reference in their work
- Frameworks they can apply to their own situations

### Test 3: Expertise Demonstration Test

**Ask:** "Does this make readers MORE likely to trust the author's expertise?"

**Automatic rejection if:**
- The article shows fumbling with basics
- The scale of problems is embarrassingly small
- The "expertise" is discovering what everyone already knows

**What passes:**
- Demonstrates pattern recognition that requires experience
- Shows sophisticated thinking about complex problems
- Positions the author as someone who systematizes solutions

### Test 4: Alignment Test

**Ask:** "Does this actively promote synthesis engineering as the right approach?"

**Automatic rejection if:**
- The article could work just as well without mentioning synthesis engineering
- Synthesis engineering is mentioned but not central to the value
- The article doesn't strengthen the case for the discipline

**What passes:**
- The article demonstrates synthesis engineering principles in action
- Readers understand synthesis engineering better after reading
- The value of the article IS the synthesis engineering insight

### Section-Level Audit

**For EVERY section, paragraph, and sentence, ask:**

1. **Does this earn its place?** If removed, would the article lose value?
2. **Is this filler?** Generic statements, throat-clearing, padding?
3. **Does this repeat something already said?** Redundancy wastes reader time.
4. **Is this necessary setup, or just delay?** Get to the point.
5. **Would a busy CTO skip this?** If yes, cut it.

**Common filler patterns to eliminate:**
- "In this article, we will explore..." -- Just start exploring
- "It's important to note that..." -- If it's important, just say it
- "As we discussed earlier..." -- Don't remind, just reference
- Paragraphs that summarize what you're about to say before saying it
- Conclusions that just restate the introduction
- Transitions that don't add information ("Now let's turn to...")

### What This Rule Does NOT Mean

**This rule is about cutting bullshit, not killing voice.**

Good storytelling, personal anecdotes, and human authenticity are NOT filler. They serve real purposes:

**Keep these -- they earn their place:**
- **Personal anecdotes** that make abstract concepts concrete
- **Asides that build trust** ("I'll admit -- my first instinct was to blame Claude. But reviewing the logs...")
- **Conversational pacing** that helps readers absorb complex ideas
- **Specific details** that make stories believable and memorable
- **Humor and personality** that keep readers engaged
- **Rhetorical questions** that guide reader thinking
- **Narrative tension** ("This worked perfectly. Until it didn't.")

**Cut these -- they're filler:**
- Generic statements that could appear in any article
- Corporate-speak that says nothing ("leveraging synergies")
- Padding to hit a word count
- Restating what you just said in different words
- Obvious observations ("AI is changing how we work")
- Hedging that weakens claims without adding nuance

**The distinction:** Personal voice and storytelling CREATE value by making ideas memorable and building reader trust. Filler DILUTES value by wasting reader time on nothing.

**The test:** "Does this make the article more engaging AND more valuable?" Good anecdotes do both. Filler does neither.

**The standard:** Every sentence should either teach something new, provide evidence, move the argument forward, OR make the reading experience more engaging and human. Generic filler does none of these.

---

## Example Ethics -- Impressive Educational Storytelling

**The Goal:** Educate through sophisticated storytelling that showcases why agentic AI matters. Examples must be impressive, plausible, and unfalsifiable -- not constrained by what literally happened.

**The bar:** Would this example make an engineer at a top AI lab think "that's a sophisticated use of agentic coding"?

**Examples must be:**

1. **Impressive** -- Demonstrate work that would be genuinely difficult, time-consuming, or tedious without agentic AI assistance
2. **Sophisticated** -- Show complexity that justifies AI collaboration (not tasks a human could do in 5 minutes)
3. **Educational** -- Teach patterns that readers can apply to their own sophisticated work
4. **Engaging** -- Tell a compelling story with narrative tension, stakes, and earned insights
5. **Plausible** -- Realistic scenarios that practitioners would recognize as valid
6. **Unfalsifiable** -- Cannot be proven wrong; no specific dates, systems, or verifiable details that could be checked

**Creative latitude:**
- Examples can be invented, composite, or heavily modified
- The constraint is plausibility and educational value, not "did this happen"
- If an impressive example teaches the lesson better than a mundane real one, use the impressive example

**Scale and complexity requirements:**
- Multi-service architectures, not single scripts
- Thousands of files or millions of records, not "a few pages"
- Cross-system reasoning, not single-file edits
- Production-grade challenges, not learning exercises

**Examples of WEAK vs STRONG:**

| WEAK (fails bar) | STRONG (passes bar) |
|------------------|---------------------|
| "Migrating callbacks to async/await in a Node.js codebase" | "Migrating a distributed payment processing system across 47 microservices while maintaining zero-downtime compatibility with three different API versions" |
| "Timestamp format mismatch between two services" | "Reconciling event ordering across a globally distributed system where clock skew, network partitions, and eventual consistency created silent data corruption detectable only through statistical anomalies" |
| "Refactoring authentication code" | "Redesigning an authentication system to support federated identity across acquired companies while maintaining session continuity for 12M active users" |
| "Adding a feature to a CLI tool" | "Building an AI-assisted code migration system that analyzes dependency graphs, identifies breaking changes, and generates migration paths across a 2M-line polyrepo" |

**The test:** After reading the example, would someone think:
- "I should try synthesis coding for my complex work" -- yes
- "I could have done that in an afternoon" -- no

**Not acceptable:**
- Examples that misrepresent how AI actually behaves
- Stories so implausible that practitioners would reject them
- Fabrications that contradict known facts about tools or systems
- Toy-scale examples that don't justify AI collaboration

---

# PRE-PUBLISH CHECKLIST

Before publishing, verify:

### BLOCKING GATES (Must Pass First -- Stop if Any Fails)

**Gate 1: Topic gate**
- [ ] The WORK described is building software, not editing content
- [ ] Replace "Claude" with "human developer" -- is it still software engineering?
- [ ] The OUTPUT of the work is software/code, not articles/content
- [ ] This is not about content pipelines, publishing workflows, or document editing

**If topic gate fails, STOP. This article does not belong on synthesis coding or synthesis engineering sites.**

---

**Gate 2: Sophistication gate**
- [ ] Example involves substantial scale (10K+ lines, 50+ files, 3+ services, or equivalent complexity)
- [ ] Work described would take days/weeks without AI, not hours
- [ ] Complexity justifies AI collaboration (not autocomplete-level assistance)
- [ ] For engineer audience: Would impress engineers at top AI labs
- [ ] For leadership audience: Would impress Fortune 500 CTOs or unicorn VPs
- [ ] Clear "why AI mattered" explanation present in the article
- [ ] No "toy scale" examples (single files, simple scripts, basic patterns)
- [ ] Example makes reader think "I should try synthesis coding" not "I could do that easily"

**If sophistication gate fails, STOP. Rewrite with more impressive examples before proceeding.**

---

**Gate 3: Engagement gate**
- [ ] Opens with narrative tension, mystery, or surprising situation
- [ ] Has at least one "aha" moment that feels earned (not stated upfront)
- [ ] Contains vivid, specific details (not abstract generalities)
- [ ] Shows human moments (frustration, surprise, satisfaction)
- [ ] Has memorable framing or metaphors readers can reuse
- [ ] Varies pacing (not monotonous structure)
- [ ] Share test: Would readers share this with colleagues?
- [ ] Memory test: Would readers remember a specific insight a week later?
- [ ] Feeling test: Does the reader feel energized/motivated after reading?

**If engagement gate fails, STOP. Rewrite for compelling narrative before proceeding.**

---

**Gate 4: Confidentiality gate**
- [ ] Content does NOT reveal business strategy or professional positioning goals
- [ ] Content does NOT mention client names or specific relationships
- [ ] Content does NOT reveal that articles are strategically positioned
- [ ] Commit message does NOT reveal article topic, content strategy, or editing intent

**If ANY confidentiality check fails, STOP. Fix the violation first.**

---

### CRITICAL SAFETY RULES

**Confession detection (MUST PASS):**
- [ ] Article does NOT imply the author has had security or privacy incidents
- [ ] Article does NOT use "lessons learned from mistakes" framing about security
- [ ] Article does NOT provide a checklist that matches the author's actual practices
- [ ] Article does NOT describe patterns a reader could use to investigate the author
- [ ] Grep patterns, configuration examples, etc. are generic, NOT the author's actual terms
- [ ] Could NOT be read as "here's what I do to prevent the problems I've had"

**If confession detection fails, STOP. This article confirms incidents that should remain private.**

---

**Incident confirmation gate (MUST PASS):**
- [ ] Article does NOT confirm a real security or confidentiality incident occurred
- [ ] Article does NOT use phrases like "this happened to me" or "the sequence is real"
- [ ] Article does NOT describe failure patterns that could invite investigation
- [ ] Article does NOT draw attention to attack surfaces (git history, commit messages)
- [ ] Publishing this article does NOT cause the harm it describes
- [ ] Meta-test: If this warns about publicizing incidents, am I publicizing an incident?

---

### QUALITY STANDARDS

**Content value gate (MUST PASS ALL):**
- [ ] Novel Value: Article provides something readers couldn't get elsewhere
- [ ] Novel Value: Main lesson is NOT just "verify AI output" or common knowledge
- [ ] So What: Readers can explain what to do differently after reading
- [ ] So What: Takeaways are specific and actionable, not vague ("be careful")
- [ ] Expertise: Demonstrates pattern recognition requiring experience
- [ ] Alignment: Article actively promotes synthesis engineering as the approach
- [ ] Alignment: Value of article IS the synthesis engineering insight
- [ ] Section audit: Every section earns its place (no generic filler, no padding, no redundancy)
- [ ] Section audit: No throat-clearing intros, no restating-the-intro conclusions
- [ ] Section audit: Every sentence teaches, provides evidence, advances argument, OR adds engaging human voice
- [ ] Section audit: Personal anecdotes and storytelling preserved (these are NOT filler)

---

### OPERATIONAL CHECKS

**Collaboration framing:**
- [ ] Article explicitly mentions working with AI (Claude Code, Codex, etc.)
- [ ] Human is positioned as the director/leader throughout
- [ ] AI is positioned as capable executor who sometimes errs
- [ ] The direction dynamic is clear (human initiates, AI executes)
- [ ] Where applicable, shows sophisticated collaboration (questioning, challenging, research)

**Attribution accuracy:**
- [ ] Every error attributed to correct party (human, AI, or both)
- [ ] Human errors framed as "didn't verify" or "accepted without checking"
- [ ] AI errors framed within context of human's direction
- [ ] No fake human collaborators ("a colleague suggested...")

**Scope and audience:**
- [ ] Topic fits synthesis coding or synthesis engineering scope
- [ ] The "I" in personal anecdotes refers to human author, not AI
- [ ] Primary audience is clear

**Authenticity and confidentiality:**
- [ ] Open source projects named and linked where relevant
- [ ] Client names and relationships anonymized
- [ ] No content that could be misinterpreted (AI generating journalism, etc.)
- [ ] Examples are real patterns (even if composite/modified)

**Cross-linking and vocabulary:**
- [ ] At least one cross-reference to another article in the series
- [ ] Named patterns use consistent terminology
- [ ] Terminology follows capitalization rules

**Series integration and metadata:**
- [ ] Series acknowledgment in footer or body
- [ ] CC0 notice included where appropriate (foundational articles)
- [ ] Audience declared in opening paragraphs
- [ ] Update notes added if article was modified after publication

**General writing quality:**
- [ ] Active voice throughout
- [ ] No AI patterns (generic phrasing, excessive hedging, etc.)
- [ ] Sentence case headings

---

## Examples of Correct Framing

### Deployment Errors (Attribution + Direction)

**Wrong:**
> Error four: removed content without asking. During a template update, I removed a line from the footer.

**Right:**
> Error four: removed content without asking. During a template update, Claude removed a line from the footer -- "The logo was hand-crafted by a human artist." -- because it seemed like a placeholder. It wasn't. I wanted it there.

### Learning from AI (No Fake Collaborators)

**Wrong:**
> A colleague challenged: would it be bad to implement all four?

**Right:**
> Reviewing the design, I challenged myself: would it be bad to implement all four?

### Expert Framing (Authority + Authenticity)

**Wrong:**
> I made a rookie mistake and didn't check Claude's output. I finally learned to verify everything.

**Right:**
> This incident revealed a gap in my verification workflow. I'd been accepting Claude's output for routine tasks without the same scrutiny I applied to complex ones. The pattern: routine confidence breeds unverified acceptance. I've since added explicit checkpoints even for "obvious" operations.

### Direction Dynamic (Human Leads)

**Wrong:**
> Claude decided to refactor the authentication module using a different pattern.

**Right:**
> When I asked Claude to clean up the authentication code, Claude proposed a refactor using a different pattern. I evaluated the tradeoffs, approved the direction, and directed Claude to proceed with the migration.

### Error Attribution (Human's Role)

**Wrong:**
> The deployment failed because Claude used the wrong command.

**Right:**
> The deployment failed because Claude used `wrangler pages project create` expecting Git-connected auto-deploy. I should have verified the command before executing -- checking `--help` would have taken seconds.

### Open Source Authenticity

**Wrong:**
> When building a personal RAG system, I learned that contractions break search.

**Right:**
> When building [project-name](https://github.com/username/project-name) with Claude Code, I learned that contractions break search. The query "what's in my biography" failed because MiniLM embeddings treat "what's" differently than "what is".

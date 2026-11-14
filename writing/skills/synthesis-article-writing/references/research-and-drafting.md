# Article writing: research and drafting

Phases 1 and 2 of the workflow. Phase 0, the reader briefing, comes first and lives in SKILL.md.

Contents:
- Phase 1, Research & Validation: mission, critical research principles, research deliverables A to E, research output format
- Phase 2, Writing the Article: mission, critical writing principles, content architecture, voice and tone, hyperlink strategy, images and alt text, ethical storytelling and anonymization, output deliverables, author bios, success criteria

## Phase 1: Research & Validation

### Mission

Conduct thorough research and provide verified, cited information before writing begins. **Accuracy is paramount** — every claim, quote, and reference must be verifiable.

### Critical Research Principles

1. **Cite Everything**: Provide URLs, page numbers, or specific sources for all information
2. **Flag Uncertainty**: If you cannot verify something, explicitly state "Cannot verify" or "Paraphrased concept - not direct quote"
3. **Distinguish Direct Quotes from Summaries**: Make clear what is verbatim vs. interpretation
4. **Confidence Levels**: Rate each piece of information:
   - Verified: Found direct source
   - Likely accurate: Found multiple corroborating sources
   - Uncertain: Found reference but could not verify
   - Cannot verify: No source found

### Research Deliverables

#### A. Source Material Research

If exploring a book, article, or specific source:

- Direct quotes with page numbers or citations
- Core concepts and how they are explained
- Key examples or case studies used
- Related frameworks or principles
- Public discourse and reception
- Notable critiques or limitations

#### B. Author's Writing Archive Analysis

Search existing content for:

- Relevant past posts (title, URL, date, key themes)
- Established voice patterns and frameworks
- Recurring terminology and characteristic examples
- Career experiences already written about publicly
- Topics where established expertise exists

#### C. Integration Opportunities

- Natural connections between source material and the author's expertise
- Where the author's perspective adds unique value
- Contrast opportunities (where nuance or respectful disagreement applies)
- 8-10 specific past posts to hyperlink with rationale for each

#### D. Anecdote Development Guidelines

**Safe territory for illustrative stories:**
- Generic patterns true to experience without naming specific employers
- Engineering/product/leadership challenges
- Implementation lessons
- Cross-functional dynamics

**Handle carefully:**
- Specific company cultures or politics
- Individual colleagues or executives
- An employer's or client's internal systems or strategies

#### E. Competitive Landscape

- Recent thought leadership on this topic
- What angle seems underexplored
- Where genuinely new thinking can be added

### Research Output Format

1. Executive Summary (2-3 paragraphs on findings)
2. Each deliverable section above
3. Red Flags section (anything that could not be verified)
4. Recommended Next Steps before proceeding to writing

---

## Phase 2: Writing the Article

### Mission

Craft an authentic, insightful article that:

1. Explores the topic with depth and nuance
2. Connects it to the author's expertise and experience
3. Establishes peer-level thinking, not just application of others' ideas
4. Feels genuinely written by the author
5. Is accurate and verifiable in every factual claim

### Critical Writing Principles

**Accuracy First**
- Use ONLY information from the research phase
- Only use Verified and Likely accurate items
- If additional information is needed, ask rather than inventing it

**Authentic Voice**
- Study voice patterns from past posts
- Write like explaining to a smart colleague over coffee
- Use characteristic terminology and examples
- Reference actual experiences and body of work

**Strategic Positioning**
- Position the author as someone who independently thinks deeply about these topics
- Show how expertise creates unique insights
- Make content valuable beyond any specific context (evergreen)

### Content Architecture

#### 1. Opening Hook (Personal Experience)
- Start with a specific, visceral moment from career experience
- Make it real and human, with stakes
- Link to one relevant past post naturally

#### 2. Core Concept Exploration
- Unique interpretation of the topic
- How domain expertise informs the perspective
- Why this matters now

#### 3. Industry Application
- Why specific industries struggle or succeed with this
- Concrete but anonymized examples
- Pattern recognition across career experience

#### 4. Unique Value-Add
- Where the article goes beyond the source material
- Where technical/domain expertise creates insights
- The bridge between theory and practice

#### 5. The Nuance
- Show critical thinking, not blind acceptance
- Add crucial nuance
- Demonstrate wisdom, not just intelligence

#### 6. Forward-Looking Implications
- Where this leads
- Practical call to action
- Ongoing commitment (subtle)

### Voice and Tone

**Characteristics:**
- Conversational but substantive
- Confident without arrogance
- Specific over abstract
- Intellectually generous (credit others, build on ideas)

**Sentence structure:**
- Vary length for rhythm
- Use occasional fragments for emphasis
- Ask rhetorical questions
- Include "you" to make it conversational

**Avoid:**
- Corporate jargon or buzzwords
- Excessive qualifiers (very, really, quite)
- Passive voice
- AI-typical phrases ("delve into," "it's important to note," "in conclusion")
- Words like "honored," "humbled," "excited," "thrilled," "privileged"

### Hyperlink Strategy

**Target**: 6-8 hyperlinks to past posts.

**Integration principles:**
- Weave links naturally into sentences
- Each link should add depth, not distract
- No "see also" sections — embed in narrative
- Distribute throughout the post

**Example:**
- Good: "As I wrote when introducing [project], the key to useful AI assistants is..."
- Bad: "To learn more about AI assistants, see this post."

### Images and Alt Text

**Write alt text the moment you place an image — never leave it for later.** Captionless images (`![](image.png)`) are the single largest source of accessibility debt in a migrated or fast-drafted archive; the cheapest time to describe an image is when you add it and know what it shows.

For every image:

- **Content image** (carries information — a diagram, screenshot, chart, photo of a person or place, a book cover, a tweet screenshot): write specific, descriptive alt text. Describe what the image *shows* and what a reader who can't see it needs to know. For a screenshot of text (tweet, chat, slide), include the key text in the alt.
- **Decorative image** (a pure visual flourish with no informational content): use explicit empty alt, `![]( )` → `![](image.png)` is acceptable ONLY when the image is genuinely decorative. Prefer to state intent so a later reader doesn't mistake it for missing alt.
- **A caption is not a substitute for alt text, and alt text is not a substitute for a caption.** If a visible caption already conveys the description, the alt can be shorter, but it should still exist.

Markdown patterns:
- Plain image: `![Diagram of the three-tier context architecture](./architecture.png)`
- Linked image: `[![Book cover of "Leadership BS" by Jeffrey Pfeffer](./cover.jpg)](https://publisher.example/book)`

**Do not infer an image's content from its filename or the article's topic alone.** A file named `tony_ridder.jpg` in an article about Tony Ridder may be a portrait — or a scan of a letter he wrote. View the image (or rely on a caption you can verify) before describing it.

### Ethical Storytelling and Anonymization

**CRITICAL: Name removal is NOT anonymization.** Removing company names while keeping the scenario, specific numbers, stakeholder dynamics, vocabulary, and industry context creates a fingerprint that names are the least important part of. The scenario IS the identifier.

**Before using any real example, apply all four tests:**

1. **Outsider test:** A stranger reads this. Could they narrow it to a small set of companies or situations?
2. **Insider test:** Someone who knows your work reads this. Does the example confirm something they suspected but couldn't prove? Does it reveal an internal decision that was meant to stay internal?
3. **Adversary test:** A reporter or competitor reads this. Could this become evidence or ammunition?
4. **Irony test:** Does publishing this example undermine the very thing the example describes protecting?

If ANY test fails, the example cannot be used regardless of whether names are removed.

**Especially dangerous: Operational decisions as teaching material.** If a decision was made to manage risk (changing terminology, restructuring a team, pivoting a strategy), describing it publicly re-creates the risk. An article about careful language choices that reveals you made those choices is self-defeating.

**Safe example sources:**
- The author's personal methodology and tools (already public)
- Publicly known examples from other companies (with attribution)
- Genuinely universal patterns that don't map to specific companies
- Fictional scenarios clearly marked as illustrative
- Examples where the specifics have been transformed, not just redacted (change the industry, the stakeholder type, the numbers, and the vocabulary simultaneously)

**Not safe, even without names:**
- Internal product strategy decisions with specific numbers
- Risk mitigation choices where the risk itself is sensitive
- Stakeholder dynamics that fingerprint a specific situation
- Vocabulary changes that map to known products

**Never permitted regardless of anonymization** (restored pre-migration prohibitions — these are fabrication and attribution bans, not identifiability tests):
- Attributing quotes to real individuals without verification
- Inventing technical achievements
- Creating scenarios inconsistent with the author's public record

### Output Deliverables

1. **5-7 Title Options** with brief rationale
2. **Full Article Draft** with all hyperlinks embedded
3. **Meta Description** (150-160 characters)
4. **LinkedIn Sharing Post**
5. **Pull Quotes** (3-4 tweetable excerpts)
6. **Verification Notes** (choices to double-check)

### Author Bios: Rendered by Layout, Not Markdown

On sites that render posts through a component-based layout (such as Astro with an `AuthorBio` component), **do NOT include an inline author bio at the end of the markdown**. The layout adds a visually-separated bio box automatically, pulling from a single source of truth in site config. Writing an inline bio will produce duplicates and defeat the single-source-of-truth design.

For sites without a layout-level bio component — external publications, guest posts, platforms that render raw markdown — include a bio at the end of the draft. If the author maintains a writer-specific bio skill that provides variants for different audiences (Standard, Short, Technical, Executive), pull the appropriate variant from there.

**Co-authored posts with layout-rendered bios** should put co-author bios in front matter (e.g., a `coauthors` array) rather than inline in the body. The layout component renders the primary author's current bio plus each co-author's bio in the same visual treatment. Check the site's front matter schema for supported fields.

**Testimonials and recommendations** (posts written about the site owner by others) should not have the site owner's bio rendered. The layout typically detects these via category (e.g., `Recommendations`) and suppresses the bio component. The testimonial writer's own bio goes at the end of the markdown as usual.

### Success Criteria

The article succeeds if:

- It sounds unmistakably like the author
- Every factual claim is verified and sourced
- It advances thinking beyond summarizing sources
- It positions the author as a thought leader
- Multiple hyperlinks prove authenticity
- It is useful to any leader thinking about this topic
- The author would be proud to have their name on it

---
name: synthesis-content-distribution
description: >
  Strategically promote and distribute content across social media platforms to build thought leadership,
  spark discussion, and create professional connections. Provides platform-specific guidelines,
  engagement strategies, cross-platform coordination, and quick-start templates for blog promotion
  and event/topic posts.
  Use when asked to: promote content, content distribution, social media strategy, share article,
  social media post, write tweet, LinkedIn post, Instagram post, promote blog, blog promotion,
  post about event, content marketing, distribute post, promote article, social media promotion.
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Content Distribution

Strategically promote content across social media platforms to build genuine thought leadership, spark meaningful discussion, and create valuable professional connections.

## Initial Analysis Phase

When given a content URL, produce a strategic brief before writing any posts:

**Content Analysis**
- Core insight or argument
- Primary value proposition for different audiences
- Natural discussion hooks and controversy points
- Connection to current industry conversations
- Unique angles or perspectives presented

**Audience Mapping**
- Who benefits most from this content
- What specific problems it solves or questions it answers
- Which professional communities find it most relevant
- Potential objections or counterarguments to anticipate

**Platform Strategy Recommendation**
- Which platforms are optimal for this content (and why)
- Suggested posting sequence and timing
- Platform-specific angles to emphasize
- Communities or groups to target
- Risks or sensitivities to navigate

**Voice and Positioning**
- How this content advances thought leadership
- What authority or expertise it demonstrates (implicitly)
- Connections to other work or ongoing themes
- How to frame without sounding promotional

Present this analysis and get feedback before writing posts.

## Content Information Template

Gather this information:

- **Content URL**
- **Content Type**: Blog post, published article, research/analysis, opinion piece, tutorial/guide, case study, or other
- **Primary Goal**: Establish expertise, generate discussion, drive qualified traffic, create speaking/advising opportunities, test ideas with peers, build relationships, or other
- **Timing Considerations**: Current events ties, relevant industry discussions, upcoming events, time-sensitive elements
- **Constraints or Sensitivities**: Topics to avoid, relationships to navigate, competitive sensitivities

## Strategic Context and Voice

Voice and tone for posts come from the user's active voice profile, not from this skill. Apply whatever voice profile is loaded in the current environment — typically a private skill (e.g., `<workspace>-private-writing-voice`), a `CLAUDE.md` / `AGENTS.md` instruction block, or both. This skill is methodology-agnostic about voice; it does not embed sample voice traits, sample forbidden language, or persona text.

Areas the active voice profile should cover for content distribution to work well:

- **Professional positioning** — domain expertise, current role, what distinguishes the writer's perspective.
- **Authentic voice characteristics** — direct vs academic, formal vs conversational, contrarian vs consensus-leaning, etc.
- **Forbidden language** — words and patterns the writer never uses.
- **Strategic subtlety** — how expertise should surface (through analysis quality, storytelling, evidence) rather than be claimed directly.

If no voice profile is active, ask the user to load one (or to describe their voice in conversation) before generating posts. Defaults applied without user input produce generic posts that read as machine-generated.

## Social register vs article register

Articles and social posts have different reader expectations. The same writer's voice should sound different in the two modes — same person, different register.

| Dimension | Article | Social post |
|---|---|---|
| Time investment | Hours to days | One sitting |
| Editing passes | Multiple | One or two |
| Reader expectation | Reference, deep dive | Update, share, react |
| Polish level | High | Medium-low (intentional) |
| Voice register | Considered, can be more formal | Conversational, casual-professional |
| Engagement goal | Click-through, share | Comment, react, repost |
| AI-detectability tolerance | Lower | Much lower |

**The expectation gap.** Readers expect articles to be edited; they expect social posts to be conversational. Over-polished social posts read as AI-generated and get skipped, even when a human wrote them. A few rough edges (a fragment, a casual word, a slight digression) signal authenticity.

### Common AI-cadence failures specific to social posts

These patterns are tolerable in articles and flag immediately in social:

1. **Article structure imported wholesale.** Topic sentences, transitions, "the principle" / "the takeaway" / "first / second / finally" labels read as essay scaffolding in social register.
2. **Imported spec language uppercase.** Formal severity labels (CRITICAL, HIGH, MEDIUM) lifted from technical specs read as press-release register in a conversational post. Translate to conversational equivalents.
3. **Third-person narration of first-person experience.** Using "the site", "the audit", "the fix" instead of "my site", "my audit", "my fix" reads as third-party reporting. First-person throughout for personal-experience posts.
4. **Long sentences (>25 words) without compression.** Essay register. Break them.
5. **Over-smoothed prose with no rhythmic variation.** When every sentence is grammatically tidy and every paragraph the same shape, the post reads as machine-edited.
6. **Closing the loop instead of inviting response.** Conversational posts invite a reply (question, observation, "tell me what you've seen"). Posts that wrap up cleanly are essay-shaped, not conversation-shaped.
7. **Em dashes.** Em dashes in articles are tolerable in moderation (the general rule against overuse from `synthesis-content-quality` A3-SS-001 still applies, per-family weighted; HIGH for Claude and pre-GPT-5.1 ChatGPT, LOW for newer GPT and Llama). In social posts the threshold drops to zero (A3-SR-005). Fast-scrolling readers register any em dash as the AI-typical polished-prose signal. Use commas, parentheses, colons, or sentence breaks instead.

### Pre-publish register check

Read the post aloud. If it sounds like prepared remarks instead of conversation, rewrite. The author's voice in social must be the author's actual voice, in less-polished form.

For voice-specific rules tailored to a particular author, layer the author's voice profile on top — generate one with [`synthesis-voice-profiler`](../synthesis-voice-profiler/SKILL.md) if needed. For AI-pattern detection across both registers, see [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md), which catalogs social-register failures (criteria 38-41) on top of the general pattern catalog.

## Sidecar File Convention

Promotion content for a published article should live as a **sidecar markdown file alongside the article itself**, not in a separate project folder.

**Convention:** the sidecar is named `social.md` and lives in the same directory as the article's main markdown file.

For static-site generators that store articles in slug-named folders (e.g., Astro, Hugo, Eleventy):
```
content/posts/YYYY/MM/DD-slug/
├── index.md          ← the article (or post.md, depending on your SSG)
├── social.md         ← the sidecar
└── [images]
```

For flat-layout blogs (one .md per post):
```
content/posts/
├── post-slug.md
├── post-slug.social.md
└── ...
```

**Why sidecar:** the promotion content travels with the article. When the article moves between repos (drafts → destination), promotion content moves with it. Co-location reduces drift, makes the file findable when working on the post, and survives directory moves intact.

**Safety:** standard SSG content collection globs (`**/index.md`, `**/post.md`, etc.) won't match `social.md`, so the sidecar is safe from accidental publishing. Verify against your specific glob if uncertain.

**Sidecar file structure:** one `## Platform Name` section per platform, each containing the post text ready to copy-paste, plus optional notes (timing, tagging, alt-text). Top of file: the article URL used in posts, the canonical URL (if different), and the generation date.

**Skeleton:**

```markdown
# Social posts: <article title>

**Article URL (for posts):** <URL>
**Canonical URL (for SEO reference):** <URL, often same>
**Generated:** YYYY-MM-DD

---

## Platform selection

[One-line rationale per platform — why include or skip]

---

## LinkedIn

[Post text, ready to copy-paste]

**Notes:** [...]

---

## Twitter/X

[Tweets, one per paragraph]

---

## [Other platforms]
```

Configuration of which platforms to include, which URL to use (some sites maintain a separate display URL distinct from the SEO canonical), and platform-specific engagement patterns are user-specific. A private/personal skill layer should encode those choices.

## Platform-Specific Guidelines

### LinkedIn

**Purpose**: Thought leadership, professional relationships, advisory/board positioning.

**Format**: 300-600 words with natural paragraph breaks.

**Structure**:
- Open with an observation or question that creates immediate relevance
- Develop one core insight with supporting context
- Connect to broader industry implications
- End with an invitation to engage (question, alternative perspective, call to discussion)
- URL placement should feel natural, not promotional

**Do**: Connect technical insights to business outcomes. Share lessons from real experience. Provide frameworks or mental models. Challenge conventional wisdom thoughtfully.

**Avoid**: Resume recitation. Promotional language. Asking for likes/shares. More than two hashtags.

**Tagging**: Only tag people genuinely relevant to the discussion. Tag at end, not in main text.

### Twitter/X

**Purpose**: Industry conversations, quick insights, peer relationships.

**Format**: Thread of 2-5 tweets (280 characters each).

**Structure**:
- First tweet is the hook
- Each subsequent tweet develops one idea
- Final tweet includes URL and optional discussion invitation
- Each tweet should work standalone (people quote-tweet individual thoughts)

**Do**: Counterintuitive observations. Specific examples or data points. Questions that spark debate. Timely reactions to industry news.

**Avoid**: Thread announcements ("Thread: 1/5"). Engagement farming. Excessive emoji. Multiple hashtags. "Like and retweet if you agree."

### Hacker News

**Purpose**: Share technical insights with startup/tech community.

**Format**: Title and optional comment.

**Tone**: Technical and substantive. This audience values depth and dislikes promotion.

**Do**: Use factual, specific titles (not clickbait). Add technical context if commenting on own submission. Be transparent about authorship. Engage substantively with comments.

**Avoid**: Any promotional language. Business/marketing angles. Defensive responses. Talking about metrics.

### Reddit

**Purpose**: Engage specific communities, get substantive feedback.

**Strategy**:
- Identify 1-2 highly relevant subreddits (quality over quantity)
- Review recent posts to understand community norms
- Title should match subreddit style
- Include context explaining relevance to the community
- Be transparent about authorship
- Engage meaningfully with comments

**Avoid**: Cross-posting to many subreddits. Generic promotional language. Ignoring community rules. Arguing with skeptics. Deleting underperforming posts.

### BlueSky

**Purpose**: Build presence with early adopter community.

**Format**: Similar to Twitter (300 character limit). Slightly more informal.

**Strategy**: Good for testing ideas before wider distribution. Engage with others' content. Use as complement to Twitter.

### Other Platforms

- **Threads**: Similar to Twitter/X approach; broader, less technical audience
- **Instagram**: Only if content has strong visual component; carousel posts for text-heavy content
- **Facebook**: Personal network, use sparingly; share to specific groups if highly relevant

## Content Creation Process

### Step 1: Strategic Brief

Present analysis: what makes this content valuable, platform recommendations with rationale, suggested emphasis per platform, timing/sequencing, risks or sensitivities. Wait for feedback.

### Step 2: Content Creation

For each approved platform, provide:
- **Platform** name
- **Strategic Approach**: One paragraph explaining strategy
- **Post Content**: Actual text, formatted for the platform
- **Engagement Hook**: What will spark discussion
- **Success Indicators**: What good engagement looks like
- **Follow-up Strategy**: How to engage with responses

### Step 3: Cross-Platform Coordination

**Posting Sequence**: Which platform first and why. Spacing between platforms. Timing considerations.

**Cross-Pollination**: When to reference discussion from one platform on another. How to synthesize feedback. Opportunities for follow-up content.

## The Human Polish Pass

AI-drafted posts are 85%-finished drafts. The remaining 15% is the human's contribution — texture, personality, and engagement-stance reframing that signal authentic authorship. Treat the AI output as a strong starting point, not a finished post. A draft that feels DONE discourages the edit pass; the post goes out as-is and reads as machine-shaped. A draft that feels like a strong starting point gets polished and reads as the writer's own.

### What AI does reliably (the 85%)

- Substantive structure (hook, develop, URL placement, call to action).
- Voice-rule compliance (forbidden language, sentence variety, no diminishers, no concierge tone).
- Platform format (length, sequence, hashtag/mention discipline).
- Strategic brief alignment (right insight emphasized for the right audience).
- Cross-platform coordination (which platform first, what to vary across them).

### What the human adds (the 15%)

These are texture moves the AI should NOT try to fake — they only work when they come from the actual writer:

- **Personality moments** — an inside joke, a callback to a recent post, a parenthetical aside, a mid-paragraph "ok, back to the subject..." — anything that signals "this was written by a real person, not generated." Generic personality (peppered emoji, "haha", "btw") is worse than no personality.
- **Specific callbacks** — references to recent posts, prior conversations, ongoing themes the writer's audience tracks. AI does not know which callbacks land for the writer's specific followers.
- **The unique-to-this-moment edit** — small adjustments that reflect what the writer is currently learning, currently noticing, currently revising in their thinking. AI cannot anticipate these.

### What the AI CAN apply as polish defaults (codifiable patterns)

These four patterns belong in the first draft, not added by the human in review:

1. **Closing questions in peer-stance, not expert-stance.** Default to invitation framing, not quiz framing.
   - Avoid: "Where have you hit this? What did you change?"
   - Prefer: "Have you run into this? If yes, where? What did you change in response?"
   - The first reads as a teacher quizzing students. The second reads as a peer asking colleagues. The peer-stance form invites contributions; the expert-stance form filters for confident responders only.

2. **Add a learner-stance closing for emerging topics.** When the post is about a new or evolving domain, end with the writer's explicit still-learning position. This is humility used correctly — not self-deprecation, but acknowledgment that the topic is moving and the writer is exploring it. Example: "I'm still learning this new world of [domain]." The peer-relationship signal it sends drives more substantive engagement than a confident close.

3. **Build the comments hook into LinkedIn drafts.** When the URL is in the first comment (LinkedIn pattern that boosts reach), the post body must signal this — otherwise readers may not realize the URL exists. A line like "I'll share more in the comments" or "Continued in the comments" pairs the body with the comment-thread layer where additional value lives. This also drives the comment-engagement signal that LinkedIn's algorithm rewards.

4. **Restrained verbs, no hyperbole.** Avoid "hit hard," "completely changed," "fundamentally," "absolutely," "transformed" when describing the writer's own experience. Use measured equivalents — "hit," "changed," "I noticed." The human will likely strip hyperbolic verbs on review anyway; the AI should not include them in the first place. Hyperbole reads as forced enthusiasm; restraint reads as considered judgment.

### What AI should NOT do

- Do not insert generic personality placeholders trying to mimic the human polish pass. Inserted "haha" or "btw" or random emoji read as machine-attempting-human and are worse than a clean draft.
- Do not invent callbacks to posts that may not exist. If the writer has been working on a theme, they will reference it themselves.
- Do not over-edit conversational irregularity. Slight roughness — a parenthetical aside, an "ok let me get back to..." — is human texture. AI tends to smooth these out, producing the perfectly-polished tell.
- Do not claim emotional states ("I'm so excited") or expertise positions ("As someone who has been doing this for years") that belong to the writer to claim or not claim.

### Workflow implication

When generating posts, present them as drafts ready for the human polish pass, not as final-form posts. The user's edit-and-then-publish step is part of the workflow, not an exception. Drafts that include the four codifiable polish patterns (peer-stance closing, learner-stance for emerging topics, comments hook, restrained verbs) reach the human in better shape; the human's polish pass adds personality and timing-specific texture on top of an already-substantive draft.

---

## Engagement Management

### Responding to Comments

**Prioritize**: Thoughtful questions that advance discussion. Constructive disagreement. Comments from people worth building relationships with. Questions that add context.

**Strategy**: Add value in every response (not just "thanks"). Use questions to deepen discussion. Acknowledge good points from dissenters. Share additional resources when relevant.

**Avoid**: Defensive responses. Arguing with trolls. Over-responding. Generic "thanks for reading."

### Watch For

- Emerging themes suggesting follow-up content
- Connections to people with aligned interests
- Misconceptions needing clarification in future writing
- Questions revealing audience needs

## Success Metrics

**Quantitative**: Engagement rate (not just volume). Quality of commenters. Inbound connections or opportunities. Click-through rate. Secondary sharing by influential accounts.

**Qualitative**: Depth of discussion. New relationships formed. Ideas or opportunities that emerge. Position in relevant conversations.

**Red Flags**: High engagement with low substance. Negative discussion without understanding. Engagement from outside target audience. Backlash from poor framing.

## Failure Modes and Recovery

**Low traction**: Evaluate timing and framing. Look at who did engage. Mine comments for positioning insights. Do not over-analyze.

**Negative discussion**: Do not respond defensively. Acknowledge valid criticisms. Clarify misunderstandings once, then move on. Take heated discussion private.

**Missed the mark**: Acknowledge openly if wrong. Use as learning opportunity. Do not over-apologize. Improve framing next time.

## Continuous Improvement

After each campaign: Which platforms drove best engagement? What framing worked? What relationships emerged? What follow-up content does this suggest?

**Pattern Recognition**: Which topics consistently resonate? Which platforms work for which content types? How is the network evolving? What themes emerge in discussions?

## Special Situations

- **Time-Sensitive Content**: Prioritize fast-engagement platforms (Twitter, HN). Post at optimal times. Be ready for active engagement in first hours.
- **Controversial Topics**: Anticipate objections in framing. Be precise with tone. Consider which platforms handle nuance well.
- **Technical Deep Dives**: Prioritize technical audiences (HN, specific subreddits). Expect slower but higher-quality engagement.
- **Strategic/Business Content**: LinkedIn becomes primary. Frame in terms of decisions and tradeoffs.

## Quick Start: Blog Article Promotion

When asked to promote a blog post or article, follow this condensed workflow:

1. **Read the article** at the provided URL. Identify the single most compelling insight.
2. **Note the URL** to include in posts.
3. **Write posts for three platforms:**

**Twitter/X** (thread of 2-4 tweets):
- First tweet: the hook — a counterintuitive observation or specific insight from the article
- Middle tweets: develop one idea each, each tweet works standalone
- Final tweet: URL + optional discussion question
- No thread announcements, no engagement farming, no excessive emoji or hashtags

**Instagram** (caption for image/carousel post):
- Lead with a strong opening line that stops the scroll
- Share the key insight in accessible language
- End with a call to discussion or reflection
- 3-5 relevant hashtags maximum

**LinkedIn** (300-600 words):
- Open with an observation or question that creates relevance
- Develop the core insight with supporting context
- Connect to broader implications
- End with a discussion invitation
- Place URL naturally, not promotionally

**How to write:** Direct, substantive, confident from experience. Demonstrate expertise through insight, not credentials. Challenge conventional wisdom where warranted.

**How NOT to write:** No "honored/humbled/excited/thrilled." No business platitudes. No promotional language. No humble bragging or credential listing. No "like and retweet."

## Quick Start: Event or Topic Post

When asked to write social media posts about an event, experience, location, or topic, follow this workflow:

1. **Gather information** (ask if not provided):
   - What is the event, experience, or topic?
   - Where and when? (location, date, context)
   - What is the key insight, tip, or takeaway to share?
   - Who is the audience? (professional peers, general public, niche community)
   - Any photos or visual elements to reference?
   - Any people or organizations to mention or tag?

2. **Write posts for three platforms:**

**Twitter/X** (1-3 tweets):
- Lead with the most interesting or useful observation
- Include specific details (names, places, concrete tips) rather than generalities
- Tag relevant accounts sparingly and only when genuinely relevant

**Instagram** (caption):
- Open with a vivid or specific detail that sets the scene
- Share what made this notable or what you learned
- Keep it conversational and authentic
- 3-5 relevant hashtags

**LinkedIn** (200-400 words):
- Frame around a professional insight or lesson drawn from the experience
- Connect the specific event to a broader theme your audience cares about
- Include practical takeaway or reflection
- Tag people or organizations only if genuinely relevant to the post

**Tone across all platforms:** Authentic, specific, grounded in real experience. Avoid generic "what an amazing event" language. Share what you actually observed, learned, or found useful.

## Related

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.

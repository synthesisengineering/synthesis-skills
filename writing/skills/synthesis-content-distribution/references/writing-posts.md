# Content distribution: writing the posts

How social posts differ from articles, what each platform expects, and what the AI drafts versus what the human adds.

Contents:
- Social register vs article register: the expectation gap, common AI-cadence failures, the pre-publish register check
- Platform-Specific Guidelines: LinkedIn, Twitter/X, Hacker News, Reddit, BlueSky, other platforms
- The Human Polish Pass: what AI does reliably, what the human adds, the four polish defaults, what AI should not do, the workflow implication

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

For voice-specific rules tailored to a particular author, layer the author's voice profile on top — generate one with [`synthesis-voice-profiler`](../../synthesis-voice-profiler/SKILL.md) if needed. For AI-pattern detection across both registers, see [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md), which catalogs social-register failures (criteria 38-41) on top of the general pattern catalog.

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

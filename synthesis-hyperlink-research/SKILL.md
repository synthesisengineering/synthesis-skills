---
name: synthesis-hyperlink-research
description: "Find authoritative hyperlinks for people, organizations, and entities mentioned in content. Use when asked to: find links, hyperlink, research links, find URLs, gather references, look up websites for people or organizations."
license: "CC0-1.0"
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
---

# Hyperlink Research

## Purpose

Gather accurate, authoritative hyperlinks for people, organizations, and entities mentioned in blog posts, articles, presentations, or any content that references external entities.

## How to Use

This skill works in two modes:

1. **Interactive mode:** If the user does not specify entities, ask which people and organizations need links.
2. **Directed mode:** If the user provides names and entities, research them directly.

---

## People to Research

If no people are specified, ask the user which people need links. Otherwise, research the people listed.

For each person, provide context such as: role, affiliation, or why they are mentioned.

## Organizations and Entities

If no organizations are specified, ask the user which organizations need links. Otherwise, research the organizations listed.

For each organization, provide context such as: what they do, where they are based, or why they are relevant.

---

## Link Prioritization

### For People

Prioritize links in this order:
1. Personal or professional website
2. Institutional or company profile page
3. LinkedIn profile
4. Other professional social media (Twitter/X, etc.)

### For Organizations

Prioritize links in this order:
1. Official website
2. Primary social media presence (if no website exists)
3. Authoritative third-party profile (Wikipedia, Bloomberg, etc.) if no official presence exists

---

## Required Output Format

Provide results in HTML format for easy copy-paste:

```html
<!-- People -->
<a href="URL">Person Name</a>
<a href="URL">Another Person</a>

<!-- Organizations -->
<a href="URL">Organization Name</a>
<a href="URL">Another Organization</a>
```

If a link cannot be found for a specific entity, note that and suggest alternatives. For example: "Could not find official page for X, consider linking to their LinkedIn profile or recent interview at [URL]."

For common names or ambiguous entities, confirm the context matches before providing final links.

---

## Tips for Best Results

1. **Add context for ambiguous names.** For people with common names, include distinguishing details like their company, field of expertise, or location to ensure correct identification.
2. **Specify link recency.** If particularly current links are needed, explicitly request the most recent official websites.
3. **Request verification.** For important links, provide a brief confirmation that the link is still active and matches the entity.
4. **Group related entities.** When writing about a specific industry or event, group requests by category to improve context.
5. **Regional preferences.** If region-specific versions of websites are needed, mention this requirement explicitly.

---

## Example Use Cases

### Technology Conference Recap
- Speakers: keynote speakers from various tech companies
- Organizations: conference host, sponsoring companies, featured startups

### Industry Analysis
- People: key industry leaders, analysts, and innovators
- Organizations: major companies, regulatory bodies, research institutions

### Personal Research
- People: authors, researchers, or experts in a field of interest
- Organizations: universities, research centers, journals, or industry associations

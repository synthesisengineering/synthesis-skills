# Content distribution: the sidecar file

Where a published article's promotion posts are saved, and the file's shape.

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

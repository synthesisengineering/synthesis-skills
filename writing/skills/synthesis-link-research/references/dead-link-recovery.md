# Link research: dead-link recovery

How to replace a URL that was once valid and no longer resolves, and the tools that make bulk checks reliable.

## Dead-Link Recovery (Archive/Cleanup Mode)

When auditing an existing archive for link rot — the URL was once valid but no longer resolves — substitute in priority order. Don't take "the domain name matches a known entity" as evidence; verify.

### Priority Order for Dead-URL Substitution

1. **archive.org Wayback Machine archived copy of the original URL.**
   The safest first choice. Preserves what readers would have seen at the original page. For personal-history URLs (someone's old site, a defunct consulting practice, a discontinued product page), Wayback is almost always the right answer.

2. **Current canonical URL of the SAME entity** (only when continuity is verifiable).
   Examples: `mysql.org` → `mysql.com` (same software, post-acquisition). Verify same-entity via Wayback archived content, the candidate canonical's own About page, or third-party confirmation. Do not assume "similar-looking domain" means same entity.

3. **Wikipedia article** for the general concept/entity (not personal/private sites).
   Example: a specific Yahoo Pipes URL whose pipe ID is dead → link to the Wikipedia article on Yahoo! Pipes.

4. **Strip the link, keep visible text + "(no longer online)" note.**
   Default when none of the above apply.

### Wayback Machine API — Rate-Limit and Fallback

The `https://archive.org/wayback/available?url=...` API has aggressive rate-limiting that silently returns an empty archived-captures result for URLs that DO have captures when queried in parallel. Three-pass approach:

1. First pass — sequential queries with 1.2-second pacing
2. Second pass on the "no archive" remainder — 2-3.5-second pacing
3. Third pass — URL-form fallback for URLs the API still claims have no archive

URL-form fallback (always works if an archive exists):

```bash
curl -sS -L --max-time 15 -A "Mozilla/5.0" -o /dev/null \
  -w "%{url_effective}" "https://web.archive.org/web/2010/$ORIGINAL_URL"
```

If Wayback has any archive, this URL redirects to a specific timestamped archive URL matching `^/web/\d{14}/`. If no archive exists, the URL stays in the unresolved `/web/2010/...` form. Use this to distinguish "no archive" from "API rate-limited."

### LinkedIn-Specific Recovery

LinkedIn returns HTTP 999 to ALL unauthenticated automated requests, both for legacy `/pub/` URLs and modern `/in/` vanity URLs. Direct verification via WebFetch or curl is impossible.

**Don't waste sub-agent budget on direct LinkedIn WebFetch.** Use one of:

1. **Google site-search** (`site:linkedin.com "person name" employer`) — surfaces the canonical LinkedIn URL in the result set if it exists.
2. **Authenticated browser session** (Claude in Chrome or similar) — the user logs in once; the agent navigates and reads page content. Reliably verifies 1st-degree connection, current employer, etc.
3. **Hash-suffix migration pattern** — for legacy `/pub/firstname-lastname/0/abc/def` URLs, the modern vanity URL is often `/in/firstname-lastname-defabc` (the last two hex groups concatenate in reverse order). Pattern held for ~70% of cases in the 2026 rajiv-com-cleanup project; the rest used user-chosen clean vanity URLs (`/in/firstname-lastname`).

### Browser Automation Has a Domain Allow-List

Claude in Chrome's browser session is gated per-domain. Reddit, NYT, Microsoft, GNU, SmugMug, and many other common domains return `"Navigation to this domain is not allowed"` until the user grants per-domain permission. For bulk URL verification across many domains, fall back to:

- `curl` with full browser headers (User-Agent + Accept + Accept-Language) using GET method. Bypasses HEAD-method anti-bot discrimination on most real sites.
- `WebSearch` for "does X site exist" or "what's the canonical URL for entity Y" — often answers without rendering the page.

### URL Extraction Regex for Archive Scans

When extracting URLs from markdown/prose to feed a scan, exclude code-block / template metacharacters:

```python
url_pattern = re.compile(r'https?://[^\s)\]\'"`<\$]+')
```

The `\$` excludes shell/template interpolations like `http://$server_name`. The backtick excludes URLs at the end of inline-code spans. The `<` excludes URLs immediately followed by HTML fragments. Without these exclusions, scans surface ~10-15% false-positive URLs from code blocks that aren't real URLs.

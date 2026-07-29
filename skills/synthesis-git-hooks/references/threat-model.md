# Threat model

Why two tiers, and what each tier protects against.

## Tier 0 — credentials

A credential in a git history is a credential that has leaked. Even if the repo is private today, three failure modes turn a private credential into a public one:

1. **The repo flips to public.** GitHub's "Make public" button is one click. Many repos that started private end up public after a project is open-sourced, a team decides to share examples, or someone forks for a demo.
2. **The repo is forked into a different visibility scope.** A private fork that someone else makes public exposes everything in the history. The original repo owner has no control.
3. **The credential is harvested from a clone.** Anyone with read access can clone, and a clone on a compromised laptop is a leak vector.

Defense in depth: credentials never go in git, regardless of repo visibility. The hook enforces this at the commit boundary because the alternative — discovering the leak after the fact and rotating — is more expensive and incomplete (you can't un-leak a key that's been cloned).

Patterns in Tier 0 are LITERAL credential signatures: AWS access key prefix `AKIA…`, OpenAI's `sk-…T3BlbkFJ`, Anthropic's `sk-ant-api…`, Google's `AIza…`, GitHub's `ghp_…`, GitLab's `glpat-…`, Slack's `xoxb-…` / `xoxp-…`, and the standard private-key BEGIN markers (RSA, OpenSSH, EC, PGP). These are designed by the issuers to be regex-detectable — finding them is unambiguous.

## Tier 1 — exposure-sensitive

These patterns matter when SOMEONE OTHER THAN THE COMMITTER will read the repo. Categories:

### Financial signals

Words like `salary`, `bonus`, `compensation`, `$NK` (where N is a number). These appear LEGITIMATELY in personal notes (the whole point of journaling is to track such things) and in HR/finance team channels — but they leak embarrassing or competitive information into public repos and into work repos shared with broader audiences.

### HR / employment signals

`contract renewal`, `not renewing`, `job search`, `leadership criticism`, `my boss`. Similar exposure model: fine in personal notes; harmful if a colleague, manager, or recruiter reads them in a work-shared context.

### Confidentiality markers

`confidential`, `NDA`, `proprietary`. Explicit signals for outward-facing artifacts. A blog post with `confidential` in the body is almost certainly mistaken (either the content shouldn't be public, or the word shouldn't be there).

### Confidential client / company names

The names of your clients (or your own org's name, when committing in a client's workspace) shouldn't leak across workspace boundaries. An "example-client" name appearing in a public open-source commit, or in another client's workspace, breaks the trust boundary you've established by keeping work products in dedicated workspaces.

### Private skill names

Skills in your own private skill repos shouldn't be referenced by name in public docs. The skill catalog is itself sensitive — someone reading a public repo shouldn't learn the names of skills that exist privately.

### Internal URLs

GitHub orgs, bitbucket workspaces, internal domains, paths to private knowledge bases. Any URL that wouldn't be linkable in a public README belongs in Tier 1.

## When Tier 1 is OK to skip

When the repo classifies as `personal` — i.e., every push remote points to your personal namespace (e.g., `github.com:rajivpant/...`), AND no other human can push to or pull from the repo. In this state:

- "bonus" is a journal entry, not a leak target
- A client name is your own working notes
- A private skill name is a reference for yourself

Personal-private repos are where Tier 1 false positives would otherwise dominate. Skipping Tier 1 there eliminates the false-positive flow that erodes discipline via `--no-verify` bypasses.

## What this doesn't protect against

- **History rewriting attacks.** If you committed a credential and pushed, the leak happened. The hook can't help retroactively. Use `git secret-scan` (or equivalent) on push, or rotate credentials.
- **Steganographic leaks.** Someone hand-crafting an obfuscated leak past the regex will succeed. The threat model assumes good-faith engineers making mistakes, not adversaries.
- **Side-channel leaks via tool output.** A leaked `process.env.OPENAI_API_KEY` value in a log file would be caught; a leaked value in a comment that decomposes the key letter-by-letter would not. Again: good-faith assumption.

The hook is a developer-side first line. CI/CD-side secret scanning is the second line, and credential rotation policies are the third. The three are complementary; none are sufficient alone.

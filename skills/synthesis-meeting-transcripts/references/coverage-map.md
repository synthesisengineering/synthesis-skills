# Coverage map: meeting transcripts 0.14.0, restructured to the v5 format

Every part of the earlier 0.14.0 SKILL.md and where it lives now. Nothing was removed. No script, test, fixture, `acceptance-suite.yaml` or `optional-workspace-mcp/` file changed.

## Why the version stays 0.14.0

The v5 brief asks for a major version bump, but this skill's scripts pin the skill version. `verify_transcripts.py`, `transcript_primary.py` and `extract_commitments.py` each carry `SCRIPT_VERSION = "0.14.0"`, and three tests require SKILL.md's `metadata.version` to equal it: `test_version_parity.py`, `test_transcript_primary.py::test_component_versions_match_skill_metadata`, and `test_verify_transcripts.py` (run directly by the release checks), which also requires the exact line `  version: "0.14.0"`. Scripts and tests are outside this restructuring, so the frontmatter keeps `version: "0.14.0"` and gains only `format: v5`. A future version bump has to move the three `SCRIPT_VERSION` constants and the frontmatter together.

| 0.14.0 section | Now |
|---|---|
| Frontmatter description (336 characters) | Shortened to 275 characters, keeping fetch notes and full transcripts into local markdown, primary-source verification before attribution, tool-agnostic Gmail/Drive MCPs or local exports, and every trigger verb: fetch, pull, sync, download, import, classify, verify. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `version`, `source_repo`, `source_type` | Kept unchanged; `version` for the reason above |
| Opening notes for 0.14.0 and 0.13.0 | references/release-notes.md (verbatim); Binding rules 2, 3 and 5 carry their live rules |
| "The earlier release notes and rationale are retained in... Before a declared-window sweep, read the mandatory acquisition evidence contract..." | SKILL.md (verbatim), after the opening paragraph |
| v0.5.3, v0.5.2, v0.5.1, v0.3.0, v0.2.0 | references/release-notes.md (verbatim, original order). The v0.5.2 note's "this file's frontmatter `version`" means SKILL.md's |
| v0.5.0: fail-closed enforcement, with the pre-commit hook script | references/transcript-primary-and-commit-gate.md (verbatim); Binding rules 4, 7 and 11 |
| v0.4.0: transcript-primary sourcing | references/transcript-primary-and-commit-gate.md (verbatim, placed first); Binding rules 4 and 8 |
| Title | SKILL.md (verbatim) |
| Opening paragraph ("A protocol for fetching AI-generated meeting transcripts...") | SKILL.md (verbatim) |
| Protocol versus config paragraph, and the tool-agnostic list | references/setup.md (verbatim), under a new "Protocol and config" heading |
| Configuration | references/setup.md (verbatim) |
| Prerequisites | references/setup.md (verbatim) |
| Protocol, Step 0: Declared-window sweep | SKILL.md (verbatim, whole); Binding rule 1. It stays because synthesis-daily-rituals `test_sync_watermark.py` reads the heading `### Step 0: Declared-window sweep` and the phrases "does not get a vote", "after fetching", "Enumerate the declared set", "unclosed gap" and "Account for every member" from this SKILL.md |
| Steps 1, 2, 3, the email warning, Steps 4, 4.5, 4.6, 4.7, 4.8, 5, 6 | references/protocol-steps.md (verbatim); Binding rules 4 to 9 and 11. A one-line pointer after Step 0 in SKILL.md names the file |
| When Multi-Account Matters | references/setup.md (verbatim) |
| Date Verification | references/protocol-steps.md (verbatim); Binding rule 10 |
| Integration With synthesis-daily-rituals | references/protocol-steps.md (verbatim) |
| Why Tool-Agnostic Matters | references/setup.md (verbatim) |
| references/earlier-version-history.md | Unchanged (119 lines, so no contents list was needed) |

## Pointers from scripts

The scripts are unchanged, and two of their messages point at SKILL.md:

- `optional-workspace-mcp/fetch-meeting.py` says "See synthesis-meeting-transcripts/SKILL.md for the schema" when no config is found or a pre-v0.2.0 key is used. The schema is now in references/setup.md; SKILL.md's Contents entry for that file names the four required keys and says to read it when a config is missing or refused, so the pointer still leads to the schema in one step.
- A comment in `verify_transcripts.py` asks for "a matching entry to SKILL.md's changelog" when output changes. The release notes now live in references/release-notes.md and references/earlier-version-history.md.

## Lines the coverage check reports

`v5-skill-coverage-check.py` reports no lines: every non-blank line of the 0.14.0 Markdown appears verbatim in SKILL.md or a reference file. None of the moved text had a relative link, so no link paths changed.

## The earlier 0.14.0 frontmatter

Kept whole, so the old description stays on record.

```yaml
---
name: synthesis-meeting-transcripts
description: "Fetch AI-generated meeting notes and full transcripts into local markdown files, and verify that an artifact is primary before it supports attribution-bearing claims. Tool-agnostic: works with Gmail/Drive MCPs and local transcript exports. Use when asked to fetch, pull, sync, download, import, classify, or verify a meeting transcript."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "0.14.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

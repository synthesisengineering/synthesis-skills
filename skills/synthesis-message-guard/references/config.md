# Send-guard configuration

The guard reads `~/.synthesis/v5/config.json`, the principal's private file. An
unreadable or malformed file blocks every send (R3.5); a missing file means the defaults
below. The public starting point is
[config.example.json](../config.example.json), which the tests load in CI, where there is
no `~/.synthesis`.

## Keys

| Key | Meaning |
|---|---|
| `send_tools` | Extra tool-name globs to guard, beside the built-in Slack, Gmail, email, chat and draft patterns (`mcp__*slack*send_message*`, `mcp__*send_gmail_message*`, `mcp__*create_draft*`, `mcp__*__reply`, ...). |
| `forbidden_phrases` | The register scan: `[{"name", "pattern", "why", "case_sensitive"}]`. Patterns are Python regexes, matched case-insensitively unless `case_sensitive` is true. |
| `message_format.allow_line_breaks_in_paragraphs` | Default false. True only for content whose line structure matters (an address block, poetry). Changes formatting only. |
| `message_format.default_email_format` | Default `html`. `plain` lets every transport send plain text (still with whole paragraphs). |
| `message_format.plain_email_tools` | Tool-name globs of transports that can only send plain text (for example `mcp__apple-mail__*`). |
| `signature.markers` | Strings that mark a persona signature (for example the persona's emoji). |
| `signature.domains` | Persona domains that must appear only inside a link on a link-capable channel. |
| `signature.plain_url_tools` | Tool globs whose channel cannot render links, where the visible domain is the right form. |

None of these keys can grant a send: approval is always the principal's, and overrides
change formatting only. Grounding, register, recipient, branding, threading, approval and
disclosure requirements stay in force.

## Calibration

The pattern set must PASS the principal's real sent messages and BLOCK the incident
drafts. Re-run calibration whenever patterns change; a guard that blocks the principal's
own voice is miscalibrated, not strict.

- A rule against a miscased brand is case-sensitive (`"case_sensitive": true`): on
  2026-08-03 a retired-branding pattern compiled to ignore case blocked every correctly
  signed send.
- The positive controls are tests, run in CI: a real signed agent message, in Slack
  wire form, reaches the approval step; a known-bad message (an apology for delay,
  self-abandonment) is blocked by name
  (`tests/test_send_guard.py::test_positive_controls_a_real_signed_message_passes_and_a_known_bad_one_blocks`,
  `tests/test_signed_message.py`). A principal's private config adds its own canonical
  messages as tests in the private layer, so a pattern change that blocks real traffic
  fails there before it reaches a session.

## Wiring and health

The plugin's hooks file registers the PreToolUse hook for every harness, matching shell
tools and every MCP tool whose name holds send, draft, reply, forward or schedule (plus
the calendar and sharing verbs the account guard needs), and `synthesis doctor` proves
each harness actually calls it. A tool added through `send_tools` must also match that
matcher, or it never reaches the guard. There is no per-client patterns file and no
enrollment step.

## From the 1.x patterns file

| 1.x `patterns.json` | v5 |
|---|---|
| `gated_tool_patterns` (regexes) | built-in globs plus `send_tools` |
| `exempt_tool_patterns` | not needed: session-to-session tools are never guarded |
| `block_patterns` `{name, regex}` | `forbidden_phrases` `{name, pattern, why, case_sensitive}` |
| `warn_patterns` | dropped: a warning the model never sees changes nothing |
| `ledger_max_age_minutes` | approvals expire after 15 minutes |
| `text_field_candidates` | every string in the call is scanned |
| `doctor_clean_controls` | tests (above) |
| `currency_claim_patterns`, `currency_claim_max_age_minutes` | binding rule 2: re-read within 30 minutes |
| `email_policy`, `paragraph_policy` | `message_format` |
| `signature_link_enforcement` | `signature`, plus the HTML email rule for every email |
| `peer_send_resolution` | board messages (`synthesis msg`) resolve their target |

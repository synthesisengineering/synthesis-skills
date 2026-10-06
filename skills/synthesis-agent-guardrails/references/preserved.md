# Preserved: synthesis-agent-guardrails 1.0.3

What 2.0.0 did not carry, and why; the retired scripts' own notes on the incidents behind
them, verbatim; and the 1.0.3 SKILL.md verbatim. Nothing here is an instruction. Read only
to review the cut.

## Contents

- What was not kept, and why
- What moves to synthesis-anti-shortcuts
- Notes of the retired scripts, verbatim
- The 1.0.3 SKILL.md, verbatim

## What was not kept, and why

- **`guards/account_routing_guard.py`** (KEEP by the code evaluation): already ported into
  `synthesis/guards.py` (`check_account`) with its tests, so the standalone copy, its
  `--doctor` controls and its config file went. Its incident and narrowing history are in
  account-routing.md.
- **`guards/publish_guard.py`** (SLIM): ported into `synthesis/guards.py` (`check_deploy`,
  `check_dates`) at about a sixth of its size. Cut: the approval ledger file and
  `--approve` (approvals now come only from the principal's prompt), the deployment-binding
  transactions, the team constraint, the inline test suite, `principal_name`, and the
  refusal of anything it could not parse, which blocked read-only commands.
- **`guards/installed_artifact_guard.py`** and **`hooks/codex/installed_skill_edit_guard.py`**:
  edits to installed copies are found by `synthesis doctor` comparing installed bytes with
  the plugin; generated instruction files are gone (AGENTS.md is authored).
- **`hooks/_settings.py`**: per-hook enable flags; the plugin's hooks file decides what runs.
- **The anti-shortcut hooks** (`_anti_shortcut_catalog.py`, the three
  `lazy_shortcut_detector.py`, `sub_agent_brief_scanner.py`, `_transcript_state.py`):
  replaced by the reply check (built-in phrases plus `shortcut_phrases`) and by the
  anti-shortcuts skill's self-check, which the next section feeds.
- **`quote_provenance_checker.py`** (Claude and Codex): slimmed to
  `scripts/provenance_scan.py`, run on demand and at day-end over what the day wrote,
  because a per-turn check of the whole transcript was the wrong moment.
- **`bare_filename_detector.py`** (Claude and Codex): slimmed to the file-link rule in the
  reply check, which reaches the model; the logging and the disk search for slugs went.
- **`long_session_detector.py`, `pre_tool_temporal_reminder.py`**: replaced by R1.2's
  re-injection carrying today's date (see reply-and-provenance.md for its status); both
  wrote per-session state or printed to stderr the model likely never saw.
- **`hooks/codex/repo_guard_stop.py`, `hooks/codex/session_end_checkpoint.py`**: served the
  retired checkpoint machinery; nothing read their snapshot.
- **`schemas/`**: the config contracts are the tables in config.md.
- **The fourteen 1.0.3 test files**: replaced by `tests/test_account_routing.py`,
  `tests/test_deploy_rules.py`, `tests/test_shell_classification.py`, `tests/test_guards.py`,
  `tests/test_reply_check.py` and this skill's `tests/test_provenance_scan.py`. The
  absence test for principal identity in this skill's tree is replaced by the plugin-wide
  source lint for personal paths and the planned CI scan for ledger names.

## What moves to synthesis-anti-shortcuts

These are content, not code, and belong in the anti-shortcuts skill (its owner moves them):

- The principal's phrase catalog, `~/.synthesis/anti-shortcut-catalog.yaml` (private; its
  phrases, categories, severities, rewrite hints, acknowledgment signals and escalation
  threshold), as the skill's costume vocabulary and, for phrases the reply check should
  send back, as `shortcut_phrases` in the private config.
- The escalation policy of the 1.x detector: a loud warning at the first violation in a
  session, an explicit acknowledgment demanded at the third, and the count reset by that
  acknowledgment. In v5 the reply check sends each violating reply back once; the
  escalation becomes the skill's self-check guidance.
- The sub-agent brief rules: scan a dispatch brief (its `prompt`, `instructions`,
  `message`, `task` or `description`) for costume vocabulary before dispatch; if found,
  revise it to specify the completeness required, not the minimization of effort; the
  block reason lists each phrase with its category, severity and rewrite hint. The 19
  briefs the scanner blocked since 2026-05-13 (`~/.claude/anti-shortcut-brief-block-log.jsonl`)
  are calibration examples. Blocking a dispatch is not a harm-class action under R3.5, so
  this is skill prose, not a hook.
- The detection log, `~/.claude/lazy-shortcut-log.jsonl` (449 rows), salvaged once as
  examples for the skill.

## Notes of the retired scripts, verbatim

### guards/account_routing_guard.py

```text
account_routing_guard — fail-closed PreToolUse gate on cross-account artifact creation.

THE INCIDENT (2026-09-11). A short calendar invitation to two client colleagues was
created through the personal-account calendar connector. It dispatched with a personal
address as organizer. Deleting the event does not unsend an invitation, and
suppressing the cancellation leaves a stale invite with no explanation. The cost is
reputational, it lands on the principal rather than the agent, and it cannot be
undone after the fact.

WHY A GATE AND NOT A RULE. The routing rule was written into the workspace instructions the same
day. That is necessary and demonstrably insufficient: three separate violations that week were of
rules already sitting on disk, unread at the moment of acting. The message guard exists for the
same reason on the send boundary. This is that boundary for calendar and mail artifacts, one
account layer up.

WHAT IT DOES. When the session's working directory is inside a client workspace, a tool call that
creates or mutates an outward-facing artifact through a connector NOT bound to that workspace's
account is blocked. Account-bound tools carry an explicit account parameter; personal connectors
do not. The absence of that parameter on a mutating call is the signal.

WHY THE BOUNDARY IS NARROW, AND THE TWO TIMES IT WAS DRAWN TOO WIDE. This gate is about GOOGLE
ACCOUNT IDENTITY. Every widening of it past that has been a false positive, twice within an hour
of being written:

  1. The first draft matched tool-name SUFFIXES, so `slack_send_message` matched `send_message`
     and every Slack send from a client workspace would have been blocked — the sanctioned
     agent-send lane included, which carries no Google account parameter and never will.
  2. The second draft matched terminal names exactly but kept a bare `send_message`, so
     one agent-messaging server's send_message — one agent session messaging another,
     nothing outward, no account at all — was blocked on its first live call.

A guard that blocks approved paths trains its own bypass, and that is a worse outcome than the
incident it was built for. So: names that are distinctively Google are gated unconditionally;
`send_message`, which three different servers use for three different things, is gated only when
its payload carries an addressee (the Gmail and Chat shapes). Slack's boundary is
synthesis-message-guard. Session-to-session messaging has no account boundary to cross.

DESIGN, inherited from synthesis-git-hooks v2 and synthesis-message-guard:
  1. FAIL CLOSED on its own errors. An unreadable config blocks; it does not wave through.
  2. ZERO DEPENDENCIES. Stdlib only.
  3. READ-ONLY CALLS ARE NEVER BLOCKED. Reading the personal calendar from a client workspace is
     legitimate and common (conflict checks). Only mutation is gated.
  4. SELF-DIAGNOSING. --doctor runs positive and negative controls.
  5. EMPTY AUTHORITY UNTIL CONFIGURED. With no workspaces configured the gate
     allows (it must not brick routine tool use) and --doctor reports
     UNHEALTHY with a setup pointer.

CONFIG. Workspaces live in ~/.synthesis/account-routing/workspaces.json
(ACCOUNT_ROUTING_CONFIG overrides the path), shaped
{"workspaces": {"<root>": {"account": "<email>", "label": "<name>",
"tool_hint": "<optional tool suggestion>"}}}.

Exit 0 allow, exit 2 block.
```

### guards/publish_guard.py

```text
publish_guard.py — fail-closed pre-publish gate for live-site deployments.

The intent this enforces (2026-08-20, restating the intent behind the
original 2026-03-23 `disable-model-invocation` flags): **no change reaches a
live site without the principal previewing it and giving explicit in-chat
approval.** The old flag gated skill *loading*, which was always a proxy —
the dangerous act is the push/deploy itself, reachable with or without any
skill loaded. This guard gates the act.

Gated commands (PreToolUse on Bash / exec):
  * any `wrangler pages deploy` (manual-deploy sites, e.g. a personal site)
  * any `git push` that targets a configured AUTO-DEPLOY site repository
    (Cloudflare Pages publishes these on push to main)

A gated command passes only when a FRESH, SINGLE-USE approval ledger exists,
bound to the repository and its current HEAD:

    ~/.synthesis/publish-guard/approval.json
    { "repo": "<abs path>", "head_sha": "<rev-parse HEAD at approval>",
      "created_at": "<ISO-8601 UTC>", "summary": "<what the principal approved>",
      "approved_via": "in-chat" }

The composing agent writes the ledger ONLY after showing the principal the
change (preview, diff, or built output) and receiving their yes for THIS
publish — permission never carries forward. `--approve <repo> --summary
"..."` writes it correctly (it snapshots HEAD itself). The gate consumes
the ledger on use; HEAD moving after approval invalidates it.

CONFIG. ~/.synthesis/publish-guard/config.json (PUBLISH_GUARD_CONFIG
overrides the path):
{"auto_deploy_repos": ["<abs repo>", ...],
 "principal_name": "<optional; messages use 'the principal' when empty>",
 "sites": {"<abs repo>": {"label": "<name>",
   "principal_name": "<optional per-site override>",
   "content_layout": "nested-date | flat",
   "content_roots": ["<repo-relative dir>", ...]}}}.
Repos without a sites entry use the default descriptor (both historical
article layouts). The installing principal's identity lives ONLY in this
file, never in the guard.

Design principles (inherited from synthesis-message-guard / git-hooks v2):
  1. FAIL CLOSED. Unparseable command, unreadable config, missing repo,
     failed rev-parse: the gated class blocks. Non-gated commands still pass
     when config is broken — a dead config must not brick every shell call,
     only publishing.
  2. ZERO DEPENDENCIES. Stdlib only.
  3. SELF-DIAGNOSING. --doctor runs positive and negative controls; --test
     is a hermetic behavioral suite.

Modes:
  --gate     (default) PreToolUse hook: read tool-call JSON on stdin,
             allow (exit 0) or block (exit 2, reason on stderr).
  --approve REPO --summary TEXT   write the approval ledger for REPO.
  --doctor   self-check; exit 0 HEALTHY / 2 UNHEALTHY.
  --test     behavioral suite; exit 0 all pass / 2 failures.

Environment overrides (used by --test):
  PUBLISH_GUARD_CONFIG     path to config JSON
                           (default ~/.synthesis/publish-guard/config.json)
  PUBLISH_GUARD_STATE_DIR  ledger dir (default ~/.synthesis/publish-guard)
```

### hooks/claude/lazy_shortcut_detector.py

```text
Stop hook that scans the last assistant message for lazy-shortcut phrases.

Reads detections from the shared catalog via the _anti_shortcut_catalog
loader. Logs every detection to ~/.claude/lazy-shortcut-log.jsonl with full
structure (phrase_id, category, severity, excerpt, suggested rewrite hint,
lesson link, skill reference).

Implements an escalation policy: tracks per-session violation counts in
~/.claude/lazy-shortcut-session-counts.json. On the FIRST violation in a session,
emits a loud stderr warning. On the Nth violation (block_threshold from the
catalog, default 3), emits an escalation message telling the agent to
acknowledge the antipattern explicitly. If the agent's message contains an
explicit acknowledgment (detected via _anti_shortcut_catalog.is_acknowledgment),
the session count resets.

Does NOT block — Stop hooks fire after the message has been sent. This hook
is the SAFETY NET behind the pre-response self-check and the constraint-first
protocol in the project instructions (full catalog: the
synthesis-anti-shortcuts skill), alongside the PreToolUse hook on
sub-agent dispatch (sub_agent_brief_scanner.py). The user is the final
enforcer; this hook makes violations visible and tracks trends.

Invoked by Claude Code's Stop hook mechanism. Receives JSON on stdin with:
  - session_id
  - transcript_path (JSONL of all session events)
  - cwd

Exit 0 always.
```

### hooks/claude/_anti_shortcut_catalog.py

```text
Shared loader for the anti-shortcut catalog.

Reads `~/.synthesis/anti-shortcut-catalog.yaml` (or `$ANTI_SHORTCUT_CATALOG_PATH`)
once at module import time. Compiles every phrase's regex and every exempt_when
regex upfront. All matcher calls operate on the pre-compiled catalog.

Failure mode: a missing or malformed catalog is logged once to stderr and
replaced with an empty catalog. Hooks importing this module continue to work
as no-ops rather than crashing. This is the artifact-grade choice: a Stop hook
that silently breaks on a corrupted YAML would be worse than one that simply
detects nothing until the catalog is fixed.

Used by the lazy-shortcut detectors (Stop-hook backstops) and the
sub-agent brief scanner (PreToolUse on dispatch) across clients.

Rules live in the catalog file, never in this loader: phrases,
categories, escalation, acknowledgment signals, and per-category
rewrite hints are all principal-supplied content. An absent catalog
loads empty (hooks pass, doctors report unconfigured).
```

### hooks/claude/sub_agent_brief_scanner.py

```text
PreToolUse hook that blocks sub-agent dispatches with lazy-shortcut framings.

Triggered before the `Agent` tool fires (the dispatch tool for sub-agents in
Claude Code). Scans the brief that would be passed to the sub-agent for
costume vocabulary from the anti-shortcut catalog. If detected, blocks the
dispatch and tells the orchestrating agent to revise the brief.

This is the highest-leverage hook in the anti-shortcut system. Bad framing in
sub-agent briefs propagates through entire sub-agent runs — by the time the
sub-agent reports back with "I left X as a follow-up" (the costume), the
half-applied work is already done. Catching the costume in the BRIEF before
dispatch prevents the cascade.

Receives JSON on stdin per Claude Code's PreToolUse hook protocol:
  - tool_name
  - tool_input  (the parameters being passed to the tool)
  - session_id
  - cwd

Decision protocol:
  - For tool_name == "Agent" (the sub-agent dispatch tool): scan tool_input.prompt
    for catalog phrases; if detected, emit JSON to stdout with
    {"decision": "block", "reason": "<reason>"} and exit 0. The reason lists
    the detected phrases and concrete rewrite suggestions.
  - For any other tool_name: exit 0 silently with no stdout output (does not
    affect tool execution).

Logs blocked dispatches to ~/.claude/anti-shortcut-brief-block-log.jsonl for
the audit trail.

This hook complements (does not replace) the Stop-hook backstop at
lazy-shortcut-detector.py, which catches phrases that survived to the
final assistant message.
```

### hooks/claude/quote_provenance_checker.py

```text
Stop hook: detect fabricated Slack TSes in transcript / daily-plan / context writes.

Scans the current session's conversation transcript for Slack TS-shaped values
(NNNNNNNNNN.NNNNNN floats or /pNNNNNNNNNNNNNNNN permalink suffixes) that were
written into transcripts/, daily-plans/, or project context files (CONTEXT.md,
REFERENCE.md, sessions/) but did NOT appear anywhere ELSE in the session — no
MCP slack_read_* result, no Read of a transcript file, no user message containing
the TS, no other tool input.

A TS that appears only inside a Write/Edit/MultiEdit and nowhere else is a
candidate for fabrication: the agent constructed the TS from imagination
rather than reading it from MCP, a synced transcript, or the user.

Logs candidates to ~/.claude/quote-provenance-log.jsonl. Does NOT block.

This is the backstop for the "Quote provenance" posture in the project
instructions. A prose rule fails when narrative coherence overrides factual
rigor; the hook makes the violation visible after the fact.

The motivating incident: an agent fabricated a chat message by tweaking the
millisecond suffix of a real message TS. The fake TS appeared in
transcript/sessions/CONTEXT writes but in no chat-read result. The hook
flags exactly this pattern.

Invoked by Claude Code's Stop hook mechanism. Stdin JSON:
  - session_id
  - transcript_path  (JSONL of all session events)
  - cwd

Exit 0 always. The user is the enforcer; this tool just makes violations visible.
```

### hooks/claude/bare_filename_detector.py

```text
Stop hook: catch filenames mentioned in a response that are not clickable links.

The project instructions carry the rule as ABSOLUTE — "every file referenced in a chat
response is a markdown link with the full absolute path" — and the rule still failed
repeatedly when responses named bare strings that the principal could not resolve. The
principal's demand is the specification for this hook: make every file mentioned in a
response a hyperlink, permanently, with no excuses about why that is not possible.

A prose rule the agent must remember is a rule the agent forgets under load. This is the
safety net, built on the same Stop-hook shape as lazy_shortcut_detector.py.

WHAT COUNTS AS A VIOLATION
  A token that looks like a filename or a path segment and is NOT already inside a markdown
  link target. Bare `foo.md`, `resources/scripts/bar.py`, or a distinctive slug that matches
  a real file on disk.

WHAT DOES NOT
  - anything inside `[text](path)` — that is the correct form
  - inline code spans and fenced blocks, which are quoting shell or source, not referencing
  - a filename the user themselves just used in their own message (echoing their words back
    is not the failure; introducing an unresolvable name is)

Exit 0 always. Stop hooks fire after the message is sent, so this makes the violation
visible and logged rather than blocking it.
```

### hooks/claude/long_session_detector.py

```text
long_session_detector.py — Claude Code Stop hook.

Detects when a Claude Code session has been running long enough that the
agent's in-context sense of "today" is likely drifting from reality. Emits
a stderr reminder to re-anchor date and project state via the checkpoint
protocol.

Threshold: 4 hours of wall-clock time since session start. Sessions that
span a midnight boundary will cross this threshold by definition. The
4-hour figure is conservative — token-cheap and catches the
day-spans-overnight case.

Tracks per-session "first seen" timestamp in ~/.claude/session-start-times.json
keyed by session_id. The Stop hook fires after every assistant message, so
state needs to persist across invocations. If the session_id is unknown, this
hook treats the current invocation as session start.

Hook input (stdin, JSON, per Claude Code Stop spec):
    {
        "session_id": "...",
        "transcript_path": "...",
        "cwd": "...",
        "stop_hook_active": true | false
    }

Output: emits a stderr reminder when threshold is crossed; silent otherwise.
Stop hooks fire after the assistant message has been sent, so this is a
safety-net reminder, not a blocker. Exit 0 always.

Related: the checkpoint protocol (the recommended re-anchor procedure).
```

### hooks/claude/pre_tool_temporal_reminder.py

```text
pre_tool_temporal_reminder.py — Claude Code PreToolUse hook.

Fires before Edit/Write/NotebookEdit tool calls. If the target file path
looks date-sensitive (session logs, daily plans, CONTEXT.md, MEMORY.md, any
file under a sessions/ directory), emits a stderr reminder of today's
verified date and the cache-vs-truth rule.

This is the reinforcement layer for the cache-vs-truth output gate in the
project instructions and the mid-session refresh protocol. It catches the
case where the agent is about to write a session-log entry or update
CONTEXT.md with a possibly-cached date.

Hook input (stdin, JSON, per Claude Code PreToolUse spec):
    {
        "session_id": "...",
        "tool_name": "Edit" | "Write" | "NotebookEdit",
        "tool_input": {
            "file_path": "...",
            ...
        },
        "cwd": "..."
    }

Output: emits a stderr reminder when target path matches the date-sensitive
patterns; silent otherwise. Exit 0 always (warn, never block). The user is
the final enforcer.

Matcher in settings.json: this hook registers under matcher "Edit|Write|
NotebookEdit". The path-pattern filtering happens inside this script so
the matcher itself stays simple.

Related: the mid-session refresh protocol; the checkpoint protocol; the
cache-vs-truth output gate in the project instructions.
```

### hooks/codex/session_end_checkpoint.py

```text
Write a bounded, atomic Codex SessionEnd repository checkpoint.

Codex caps SessionEnd commands at three seconds. Workspace-wide repository
scans therefore belong to Synthesis Console and day-end, where they are
observable and can take the time they need. This hook records fast local
evidence for the ending session so the lifecycle event is not lost.
```

### hooks/codex/repo_guard_stop.py

```text
Codex Stop hook that records local handoff state and verifies guard health.

Routine dirty or ahead state is LOCAL_READY on the same machine and is reported
for the explicit remote-handoff/day-end sync. An unavailable guard or malformed
session checkpoint remains a protection failure and blocks continuation.
```

## The 1.0.3 SKILL.md, verbatim

# Synthesis Agent Guardrails

## The Problem

Agent harnesses act through the principal's accounts: calendar invites go out
as someone, drafts send from somewhere. A routing rule written in the
workspace instructions is necessary and demonstrably insufficient — rules
sitting on disk go unread at the moment of acting, and an invitation cannot
be unsent. The controls that prevent cross-account mistakes have to sit
*before* the tool call, not after it.

## The Guards

### Account routing gate (`guards/account_routing_guard.py`)

A fail-closed PreToolUse gate on cross-account artifact creation. When the
session's working directory is inside a configured workspace, a tool call
that creates or mutates an outward-facing artifact through a connector NOT
bound to that workspace's account is blocked (exit 2 with an explanation);
everything else passes (exit 0).

Gated surface, matched on the tool name's terminal segment exactly:

- Google-mutating terminals unconditionally (`create_event`, `send_email`,
  `reply`, sharing verbs, and the rest — see `MUTATING_TOOLS`).
- Shared terminals (`send_message`) only when the payload proves the call
  addresses a mailbox or Chat space. Bare agent-to-agent messaging and
  Slack sends are never this guard's boundary.
- Read-only calls are never blocked.

Account binding is proven by an explicit account parameter
(`user_google_email` first, then `from_email`, `account`, `user_email`,
`sender`). A mutating call with no account parameter inside a client
workspace authenticates as the personal account, so it blocks.

### Configuration

Workspaces live in `~/.synthesis/account-routing/workspaces.json`
(`ACCOUNT_ROUTING_CONFIG` overrides the path):

```json
{
  "workspaces": {
    "/path/to/client-workspace": {
      "account": "person@client.example.com",
      "label": "Client",
      "tool_hint": "calendar-mcp: manage_event"
    }
  }
}
```

`account` is required; `label` defaults to the root path; `tool_hint` is an
optional suggestion appended to block messages. The machine-readable
contract is `schemas/workspaces.schema.json`. Longest-prefix match wins, so
a nested workspace overrides its parent.

`--doctor` runs 9 positive/negative controls against the longest
configured workspace and exits 0 only when all pass.

### Publication authority gate (`guards/publish_guard.py`)

A fail-closed PreToolUse gate on live-site publication. A `git push` into
a configured auto-deploy repository or a `wrangler pages deploy` passes
only with a fresh single-use approval ledger bound to the repo and its
current HEAD (exit 2 with the remedy otherwise); everything else passes.

Three invariant layers sit above the ledger and no approval can waive
them: future-dated content never goes live before its stated date,
already-published dates are immutable, and a second publish inside the
rapid-redeploy window needs explicit quoted approval (the rushed
follow-up fix is the highest-risk publish there is).

Repo targeting resolves explicit `cd`/`git -C` references first, the
ambient cwd last, so a command that names its repo is attributed to that
repo wherever the shell sits.

### Configuration

Sites live in `~/.synthesis/publish-guard/config.json`
(`PUBLISH_GUARD_CONFIG` overrides the path; `PUBLISH_GUARD_STATE_DIR`
overrides the ledger directory):

```json
{
  "auto_deploy_repos": ["/path/to/site-repo"],
  "principal_name": "Dana Example",
  "sites": {
    "/path/to/site-repo": {
      "label": "Personal site",
      "content_layout": "nested-date",
      "content_roots": ["content/posts"]
    }
  }
}
```

`auto_deploy_repos` is required. `principal_name` is interpolated into
block messages (per-site `principal_name` overrides it); empty means the
messages address "the principal". Repos without a `sites` entry use the
default descriptor, which scans both historical article layouts. The
machine-readable contract is `schemas/sites.schema.json`.
`--approve <repo> --summary "..."` writes the ledger after the principal
previews the change and says yes for that publish; `--doctor` runs the
positive/negative controls plus the hermetic `--test` suite.

### Defaults-off

Every guard ships inert without principal configuration: with no
workspaces configured the routing gate allows (it must not brick routine
tool use) and `--doctor` reports UNHEALTHY with a setup pointer. The
publication gate has no authority until its config names repos — with no
config it blocks only publish-shaped commands (fail closed on the gated
class) and allows everything else. An unreadable config fails closed
(blocks); a workspace with no account fails closed (raises, and the
doctor control reports the failure).

## Hooks

`hooks/{claude,codex,muse}/` carries the per-client hook suite: filename,
shortcut, provenance, brief, temporal, session, and install-guard
detectors. Every hook ships inert and is enabled per-hook in
`~/.synthesis/agent-guardrails/hooks.json`:

```json
{
  "hooks": {
    "lazy_shortcut_detector": {"enabled": true},
    "bare_filename_detector": {"enabled": true}
  }
}
```

With no config file every hook exits 0 silently; `--doctor` on any hook
reports `UNCONFIGURED` plus its own state (log path, catalog size,
thresholds). `GUARDRAILS_HOOKS_CONFIG` overrides the config path. The
shortcut detectors read their phrase catalog from
`~/.synthesis/anti-shortcut-catalog.yaml`
(`ANTI_SHORTCUT_CATALOG_PATH` overrides); an absent catalog means zero
detections, never a crash.

## Layout and Roadmap

- `guards/` — executable gates (both promotions).
- `hooks/{claude,codex,muse}/` — per-client hook wiring (this promotion).
- `schemas/` — config contracts.
- `tests/` — gate regressions plus committed absence tests proving the
  promoted tree carries no principal identity.

Both promotions have landed — the publication authority guard and
the output detectors — each with the same defaults-off contract.

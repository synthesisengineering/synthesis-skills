---
name: synthesis-agent-guardrails
description: "Fail-closed session and tool guards for agent harnesses: cross-account artifact routing today; publication authority and output detectors landing next. Every guard ships inert until its principal configures it."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

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

### Defaults-off

Every guard ships inert without principal configuration: with no
workspaces configured the routing gate allows (it must not brick routine
tool use) and `--doctor` reports UNHEALTHY with a setup pointer. An
unreadable config fails closed (blocks); a workspace with no account fails
closed (raises, and the doctor control reports the failure).

`--doctor` runs 9 positive/negative controls against the longest
configured workspace and exits 0 only when all pass.

## Layout and Roadmap

- `guards/` — executable gates (this promotion).
- `hooks/{claude,codex,muse}/` — per-client hook wiring (lands with the
  detector promotion).
- `schemas/` — config contracts.
- `tests/` — gate regressions plus committed absence tests proving the
  promoted tree carries no principal identity.

Next: the publication authority guard (fail-closed deploy/publish approval
with per-site layout descriptors), then the output detectors (shortcut,
provenance, and brief scans over principal-supplied rule catalogs). Each
lands with the same defaults-off contract.

---
name: synthesis-agent-guardrails
description: "Fail-closed session and tool guards for agent harnesses: cross-account artifact routing and publication authority today; output detectors landing next. Every guard ships inert until its principal configures it."
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

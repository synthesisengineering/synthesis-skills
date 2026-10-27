---
name: synthesis-agent-guardrails
description: "Pre-tool guards beyond sends: the account a calendar or mail call acts as, a browser call's Chrome profile, deploys and their date rules, destructive commands; the reply check and day-end provenance scan. Use to configure them, or when a deploy, delete, calendar or browser call is blocked."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.2.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Agent Guardrails

Agent harnesses act through the principal's accounts and shells: calendar invites go out
as someone, a push publishes a site, a delete removes a home folder. A rule written in the
instructions is necessary and demonstrably insufficient, because rules on disk go unread
at the moment of acting. These guards sit before the tool call, in the v5 PreToolUse hook
(`synthesis/guards.py`), and two checks sit at the end of a turn and of a day.

## Binding rules

1. **A calendar, mail or sharing call acts as the account of the workspace it runs in.** An invitation cannot be unsent (2026-09-11). Reads and Slack sends are never routed; session-to-session messages have no account to cross.
2. **A production deploy needs the principal's approval of that exact command,** typed by them as `approve <code>`, bound to the commit HEAD is at, used once, within 15 minutes. A deploy is a build deploy (`wrangler pages deploy` and the like) or any push into a repository that deploys on push, however the push names it (2025-12-22, 2026-08-30).
3. **No page goes live before its stated date, and no published date changes,** even with approval, in both content layouts (2026-08-29, 2026-08-31).
4. **A second deploy of a site within 45 minutes is a rapid redeploy:** put the options to the principal first; only their explicit rapid-redeploy approval lets it through (2026-08-29).
5. **Recursive deletes of protected roots** (home, the workspaces folder, each workspace, any repository root) **and force pushes to a default branch are refused.**
6. **A command is judged by what it runs, not by the words in it.** Quoted text and arguments are data; wrappers, `bash -c`, substitutions, eval and scripts fed to a shell run. Text the guard can't read is judged on its raw words, and is never blocked when no guarded word is in it.
7. **The shell, send, account and browser guards fail closed** when the config can't be read; every other check advises.
8. **A reply is sent back once,** never twice in a row, when it defers work, quotes words no tool returned this session, or (when enabled) names a file without a clickable absolute-path link.
9. **At day-end, run the provenance scan** over the records written that day; a timestamp or quote that appears in no source is named, not trusted.
10. **A browser call acts in the Chrome profile of the workspace its session started in.** The extension is shared: a call passes only when this session made the latest selection, to its workspace's browser, and that selection reported success (2026-10-21).

## Contents

- **Procedure** (below): configure, and what to do when each guard blocks.
- [references/config.md](references/config.md): every config key these guards read, with examples, and how the 1.x config files map onto them. Read when setting up or changing a guard.
- [references/deploys.md](references/deploys.md): what counts as a deploy, approvals, the date and rapid-redeploy rules, how the shell is read, and the tests that pin each. Read when a deploy or shell command is blocked, or before changing the shell reader.
- [references/account-routing.md](references/account-routing.md): the routing rule, its incident, and why its boundary is narrow; the browser-profile rule and its limits. Read when a calendar, mail or browser call is blocked.
- [references/reply-and-provenance.md](references/reply-and-provenance.md): the turn-end reply check and the provenance scan, with commands and output. Read when a reply is sent back, or at day-end.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.0.3 and its scripts went (ruling D8), and what moves to the anti-shortcuts skill.
- [references/preserved.md](references/preserved.md): what was not kept and why, with the 1.0.3 text and the retired scripts' incident notes verbatim. Read only to review the cut.

## Procedure

1. **Configure** in `~/.synthesis/v5/config.json` (references/config.md): `account_routing`, `browser_routing`, `push_deploys`, `deploy_patterns`, `deploy_content`, `sheet_hosts`, `protected_roots`, `shortcut_phrases`, `reply_file_links`. Every guard runs with safe defaults when its key is absent: no routing, the built-in deploy commands, home and workspace roots protected.
2. **A deploy is blocked for approval:** show the principal the exact command and what it publishes (a preview, the diff, or the built output), and the code. When they type `approve <code>`, run the identical command once. A changed command or a moved HEAD needs a new approval. A date-rule refusal is never approvable: fix the date or hold the deploy.
3. **A rapid redeploy is blocked:** stop and put the options to the principal (wait, revert, or deploy now); ask for the rapid code only if they want it now.
4. **A calendar or mail call is blocked for its account:** use the tool that takes the workspace's account and pass it (for example `user_google_email`); afterwards, check the organizer or sender.
5. **A delete or force push is refused:** name a narrower target; never route around the guard.
6. **A reply is sent back:** revise exactly what it names, then end the turn.
7. **Day-end:** `python3 <synthesis-agent-guardrails>/scripts/provenance_scan.py --since <today> <records or folders written today>`; resolve every line it prints against its source before the records are handed off.
8. **A browser call is blocked:** call `list_connected_browsers`, then `select_browser` with the deviceId the message names, and wait for its result before the next browser call. Never select another workspace's browser to get past it.

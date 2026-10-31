"""R8: budgets that make machinery regrowth a failing build, and hook latency."""

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ceilings at the measured size once every verdict was applied and duplication removed (2026-10-06):
# set first at 5,000 and 20,000 before the code evaluation measured what carries real value.
# Raised to 5,170 and 20,320 for the approval-provenance layer that closed the M5 self-approval
# defect (2026-10-06), after removing every duplicate found; then by 20 and 17 lines for one-line
# flow collections in the YAML reader (the inbox rules use them), which let every skill drop PyYAML
# while the skills' own scripts shrank by as much as they grew. The plugin rose 10 more in 5.0.2: setup's
# recognition of unedited 4.x-installed organization skills, and release reporting what it matched,
# after pyflakes found nothing left to remove. 5.0.3 adds 41 to both for three things Rajiv asked for on
# 2026-10-06: the once-per-release upgrade note (25), calendar writes that email no one (9) and a repository
# naming itself (7). 5.0.4 adds 18 to both so a session still on an older plugin can no longer switch the
# stable runtime back (a defect found live that day), after the three version parsers became one.
# 5.0.5 adds 10 to the core (the doctor reaps each harness CLI's whole process group) and 55 to the plugin:
# those 10, a bytecode guard ahead of the first local import in 35 scripts (38; Muse refuses a bundle with
# stray __pycache__), the repo guard's atomic report (2) and autopilot's JSON status (5).
# 5.0.7 adds 50 to both for fixes other sessions reported from 2026-10-07 to 10-13: board delivery that marks
# read only what it shows and can re-show a cut message (22), the upgrade note for sessions recorded before
# versions were kept (11), a write guard that tells a read from a write (9), HTML link targets counting as
# branding in the send guard (4) and a doctor that says "cannot tell" for a CLI or trust state it cannot read
# (4). A scan for unreferenced definitions and repeated blocks across the core found nothing to remove.
# 5.0.8 adds 146 to the plugin: the decision packet's reading path Rajiv asked for on 2026-10-08 (153: changes
# against a reviewed baseline, HTML messages as their words, material shown once, a handled list, reading-burden
# checks), the message reader's three gaps (56) and the meeting window's in-progress hold (5, after two shared
# helpers recovered 5), less the reader's unused sandbox runner (73), the meeting config's April migration
# hint (8) and two unreferenced definitions (4). A plugin-wide scan found nothing else unreferenced. Then 18 more
# so saved meeting transcripts never keep a Docs image's access key (reported the same day).
# 5.0.9 adds 320 to both for Rajiv's 2026-10-13 rulings: approval on every channel, recognized by what a call does,
# and send windows (synthesis/sends.py 220, guard wiring 61, `synthesis sends` 29, the window note in the hooks 8),
# and the Docs image key as a built-in credential (2). The preferred-names check came in at zero net.
# 5.0.10 adds 3 so a read-only script may import the window and approval code; writing calls stay refused.
# 5.0.11 adds 44 so `synthesis sends open` itself refuses an agent without the principal's granted code (a
# global option before `sends` slipped past the guard alone), whatever order its options take; help needs no code.
# 5.0.12 adds 40 for four defects a project session reported: the register scan reads the message (and $(cat
# file) bodies), not file names; approvals bind where a command runs; untaken codes are named; parsed redirects.
# 5.0.14 adds 144 for defects reported 10-13 and 10-14: a Python script judged by what it writes, not what it
# quotes (about 50); file-edit tools kept out of approvals and windows; heredoc, JSON and rewritten bodies read
# right; global options and help in posting commands.
# 5.0.15 adds 331 to the core (338 to the plugin) after a project session's data-loss incident on 2026-10-20: the
# shared-checkout journal and claims log (synthesis/checkout.py, about 230), release and claim checks, journal and
# index commands in the CLI (about 60), claims checked when a file is written (about 40), and wiring.
# 5.1.0 adds 45 to the core and 960 to the plugin. The plugin's share is the action sheet Rajiv asked for on
# 2026-10-19 (build_sheet.py 510 and record_actions.py 401, importing the packet's engine rather than copying
# it). The core's: declared mailboxes left unread past their cadence counted at every session start (31; an
# audit found one workspace's account ten days unread with nothing reporting it), worktree retirement after a
# squash merge the team edited further and past pytest's cache (10), approval codes read only in the issued shape and never inside a
# harness block (3), and the doctor checking action sheets (1).
# 5.1.1 adds 95 to the plugin (the core is unchanged): dry runs that write nothing in onboarding (workspace.py 37,
# setup.py 9), the message reader's stale-store check and Recently Deleted attribution (47), and wrapped list items
# in the packet's Markdown view (2). A search for unreferenced definitions and repeated bodies found nothing.
# 5.1.3 adds 59 to the plugin (the core's two edits change no line count): sends to an existing iMessage or SMS chat,
# group included, named by exactly its members, under the same approval (messages_send.py 47, members resolution
# and the shared send path), and watched chats in the reader (12), for a trip group the principal asked agents to
# post logistics to and monitor.
# 5.1.4 adds 118 to the core and 178 to the plugin for five defects other sessions reported from 10-20 to 10-22.
# The core's: browser calls held to the Chrome profile of the session's workspace, after that session's own
# confirmed selection (guards.py 96 net, after account routing's workspace lookup became shared; a public post had
# gone out from the wrong profile); a folder claimed by name alone covering its files, and handoff's READY reading
# every claimed file again (board.py 15, project.py 6; READY had been printed over nine staged files); and the Docs
# image key's second host in the commit check (1). The plugin's beyond that: the Slack thread checker reading the
# listed transcript layout and refusing one it cannot read (46), a watermark target checked as one id (11), and the
# second image host in the meeting verifier (3).
# 5.1.5 adds 157 to both (guards.py only) so a send made by computer use or in a browser waits for the code, after a
# WhatsApp photo went out on 10-22 with none asked for and 45 days of transcripts showed 11 unguarded browser sends:
# the section's comment and tables (messaging apps by bundle id with their line-break key, app names, tool and key
# sets, the sending-summary pattern) 34; recognizing the tools on any server, browsers included, 12; reading each
# call's clicks, keys, typed text and menu paths, browser steps and form values included, 29; the `messaging_apps`
# key 9; app names and each session's recorded grants 10; Return and send shortcuts per app 12; the check itself
# (register scan, window, approval and the hold's instructions) 47; wiring in check(), guarded() and the signature
# rule 4. The click names were listed once instead of twice.
# 5.1.6 adds 153 to the plugin (the core is unchanged), from the principal's ruling of 2026-10-22: iMessage and SMS
# photos sent under the same approval, bound to the photo's hash, with the transport's size and change-time check
# and a caption that fails after its photo reported as uncertain (messages_send.py 51), and the WhatsApp prefill that
# opens an existing chat with the approved text for the principal to send, found by number or linked id (102).
# 5.1.7 adds 4 to both: an RSVP's comment fields left out of the signature-link check, since they render as plain
# text (the field set and its comment 3, the joined text it reads 1); the browser refusal's wording changes no count.
# 5.1.8 adds 19 to the core and 189 to the plugin, from the principal's rulings of 2026-10-22: a private host for
# action sheets on Cloudflare Pages behind Access, whose uploads by the sheet's own script need no code, and a sheet
# that keeps working with no hosting account at all. The core's: the publish script recognized as a deploy, and its
# path (2); the `sheet_hosts` check that frees only that script's upload to a listed project (16) and its use among
# the deploy targets (1); a versioned interpreter such as python3.12 counting as its interpreter changes no count.
# The plugin's beyond that, publish_sheet.py 170: usage 18, imports and the engine's path 18, constants and the
# no-index, no-cache, no-referrer headers 9, its three outcomes 12, the gate probe that never follows a redirect,
# with the system CA retry, 24, the gate test 11, the page rebuilt from the filed spec 12, the upload 23, the order
# of the checks 19, the command line 24.
# 5.1.9 adds 94 to the core and 96 to the plugin. The core's (guards.py): a browser page on a messaging site counts as
# that messaging app, after a session found on 2026-10-22 that Return in a Google Chat compose box went out with no
# code. The transcript's tail read once and shared with the browser guard, a file gone mid-read counting as
# unreadable (19, less 5 in `_last_selection`); the sites with their line-break keys, and the tab-list pattern, 15; a
# page's site 14; the newest tab list a browser call printed, its call found by id so a shell printing a transcript
# cannot move the page, 24; the pages a call acts on, navigate steps included, 17; their use in the send check 1. And
# doctor.py 9: filed pages found by their generator's marker as well as by name, since sheets are named from their
# titles and no filed sheet had been checked. The plugin's 2 more: the sheet host's gate probe names its user agent (the constant and why), since Cloudflare answered
# 403 to urllib's on the first upload.
# 5.1.11 adds 3 to both (guards.py): every RSVP waits for the code again, after an accepted RSVP with notifications
# off went out unasked on 2026-10-23 through the quiet-calendar exemption (the RSVP test 1, the joined condition 1,
# the docstring's reason 1).
# 5.1.12 adds 77 to the plugin (the core is unchanged), for three gaps other sessions reported on 2026-10-26:
# thread_checker.py 24, listing every message in a section of threads read, at any indent, linked or bare, and never
# a table row; sync_watermark.py 33, a local message store's watermark needing its reader's coverage and stopping at
# its through; local_messaging.py 20, a quit WhatsApp counting as stale at once.
# 5.1.13 adds 3 to the plugin (local_messaging.py), after a session found on 2026-10-27 that a followed WhatsApp
# Channel's posts held every window as gaps: a community read as a group 1; a row's chat known before attribution, so
# exclusion runs first 0 (the old exclusion moved up); the Channel rule and its reason 2.
# 5.1.14 adds 17 to the core and 19 to the plugin, after an action sheet on 2026-10-27 asked the principal to run the
# rituals of a workspace the ritual config already marked as worked occasionally (`quiet_after_days`, his 09-02
# ruling), because the session line counted it as owing a weekly review and nothing read that setting. rituals.py:
# the setting checked as a whole number of days 2; such a workspace owes no weekly review 3; `quiet`, its days
# without a ritual record once past the limit, 9; the session line counting it among the other workspaces, with
# how many are quiet too long, 3. ritual_state.py 2: the summary's quiet days, in its record and its text.
# And 2 more to the plugin (build_packet.py): raw HTML told from a shell placeholder, the tag names on their own
# line 1 and the comment saying what counts 1, after a calibration packet could not be built on 2026-10-27.
# And 8 more, after the principal found that packet's page confusing and asked why it went out as a claude.ai
# artifact: build_packet.py 4, a blind row refused with a recommendation 3 and an all-blind packet built
# without one 1; publish_sheet.py 4, the packet engine imported 1, a packet rebuilt by it 1, and the
# docstring's reason 2.
# 5.1.15 adds 43 to both, for three board reports of 2026-10-27. sends.py 30: a window's planned sends (the limit and
# its reason 2, read from the command 1, kept in the request 1, required 2, spent and settled, the last closing it, 13,
# a window without them covering none 1, the count left in its description 2); shared-document edits held for the
# code, after an agenda line went out with none (the reason 2, the tools 5, their channel 1). guards.py 12: a register
# rule scoped to channels, after a line fit only for scheduling went out on Jira answers (the scope 2, the channels
# passed in 3), a document's own line breaks 0 (in the same line); each window send settles the window 3; a window the
# command would refuse is refused before the principal is asked for a code 4. cli.py 1: `--sends`.
# 5.1.16 adds 54 to both, after a series moved to a new hour on 2026-10-27 revived a meeting canceled at the old
# hour, double-booked on an accepted one, and nobody read the day back. guards.py 14: a call that deletes an event or
# sets its time or recurrence asks, in its approval text, for the occurrences from today through the next three (the
# text 4 and its reason 1, the test 4, its use 1, spacing 4). reply_check.py 40: a calendar write this turn that no
# calendar read followed sends the reply back once (the write and read patterns 2, the turn read from the
# transcript's tail with what each call did 33, the reply naming the writes 4, json imported 1).
# 5.1.17 adds 1 to both (checkout.py): the reason `synthesis index set` commits as "Update docs", after a session
# found on 2026-10-27 that its message named the project and field, against the principal's commit-message rule.
# 5.1.18 adds 130 to the core and 204 to the plugin, for two board reports. Codex sessions could neither claim nor
# post, because Codex's sandbox could not write the state folder, which also holds approvals and send windows; the
# principal chose on 2026-10-30 to give the board its own folder and let the sandbox write only that. paths.py 14:
# the board's folder and its reason 4, the names it took from state/ 1, those left behind found 3, spacing 6.
# install.py 43: every install merges what an older release left in state/ (the call, and a failure printed rather
# than blocking a session start, 4); the merge, because the older release's own session-start hook can switch to
# this one without moving anything (its reason 6, the walk 9), free names moved 4, folders entry by entry 5, logs
# appended 3, a session in both places keeping both copies' claims 6, the rest archived, never deleted, 2, spacing
# 4. hook.py 7: the first hook that finds the board in the old place merges it (the check costs seven lstat calls).
# doctor.py 53: a Codex config that does not grant the board fails, and so does a grant over the state folder (the
# check 16; the folders the config grants, from the older writable roots while `sandbox_mode` is set, else from the
# permissions profile in use through `extends`, 17; a TOML array's strings read 4); the board still in the old place
# warns 7; the checks run 1; spacing 8. guards.py 10: the board is written only through the CLI, since a session file edited by
# hand can drop another session's claims (the roots' docstring 1, the refusal naming the CLI 2 and its reason 1,
# spacing 2, the file-tool and shell refusals 4). And a wildcard claim, after a session found twice (2026-10-28 and
# 29) that `meeting-preps/2026-11-02-*` covered none of the files inside the folders it matched while handoff printed
# READY: board.py 2, a claim covering everything beneath what it names unless that is an existing file (the docstrings
# 2; the rule changed in its one line); project.py 1, git asked about the folder above a pattern held with "/**".
# The plugin's 74 more (setup.py): Codex's config granting the board (the line finder 11; the overlay's step 7;
# through the permissions profile in use, which Codex 0.166 reads unless `sandbox_mode` is set, 28, and that
# profile's name 1; through the older writable roots while it is set 17; the marker 1; the docstring 1; spacing 6),
# and the board's folder made first, since the sandbox may write inside it but never create it, 2.
# 5.1.19 adds 2 to both (install.py), after the 5.1.18 move on 2026-10-30 blanked a session's project, folder and
# briefing: the release script's own claim had written a fresh record first, and the newer copy won whole. The newer
# copy now wins field by field, never with an empty value, 1; a session's start is the earlier of the two, 1.
# 5.2.0 adds 592 to the core and 616 to the plugin, for the principal's request on 2026-10-30 to keep every agent
# conversation, with its models, in synthesis, portable across harnesses: Claude Code had been deleting its transcripts
# after 30 days, Codex keeps its own format and Muse an event log. sessions.py 501: its reason 11 and imports 11; the
# limits, the injected-text prefixes, the rows to skip and the project line, with their reasons, 19; masking secrets
# with the commit check's patterns 12, applied to every field 8, injected text told apart 2, the workspace from the
# folder 9, times in one form 8, the archive's folder 2; a session's export state 117 (the class 2, its state read
# 9, text kept once 9, text and media from a message 18, media once by hash 14, long text once per workspace 10, each
# record with its project, times and blobs 22, segments and the offset saved 26, spacing 7); the three harnesses'
# formats: Claude Code 47, Codex 41, Muse 29 (its prompts are accepted intents), the table 1; a session's identity 7
# and folder 19; the export 29, the transcripts to read 7, every one 17; reading: the catalog 6, records with their
# full text 19, the recent conversation 12, search 5, a readable line 10;
# spacing 54. cli.py 40: `synthesis sessions` 25 and its arguments 13, spacing 2. project.py 16: resume shows the
# project's latest prompts and replies from any harness, 13, its call 1, spacing 2. doctor.py 17: Claude Code
# transcripts kept a year or more, 14, its use 1, spacing 2. guards.py 13: only the exporter writes the archive (the
# root 2, the reason 2, the refusal shared with the board's 9). paths.py 5: the archive's folder. The plugin's 24 more
# (setup.py): Claude Code keeps transcripts 3,650 days unless the person set a period, 20, its call 2, spacing 2.
# 5.3.0 adds 216 to both, for the principal's ten rulings of 2026-10-30 on keeping agent conversations (R10.1 to
# R10.5). sessions.py 163: the reason in the docstring 3 and the subprocess import 1; the kinds that leave the Mac,
# with their reason, 3; the injected prefixes measured that day 3 and another session's message 1; a prompt told
# apart from a brief or a reviewer's copy, 7; the Claude Code and Codex adapters using it 6 (Codex's child threads
# named 4, the sub-agent flag 2); workspace folders listed once 7, so the folder lookup shrinks by 5, and a Claude
# Code project folder matched to its workspace 9; placement following a sub-agent's parent 8, its working folder kept
# 1; workflow journals skipped 1; Codex's archived sessions read too (139 had been missed) 1; the archive moved aside
# for a rebuild 8; the catalog reading other Macs' synced
# sessions 7; a cited record with its neighbors 3; the sync: the configured repos 5, git 2, sync 8, a workspace's
# commits, pull and push 33, a session's synced files rewritten whole 28; the section heading 1; spacing 22. cli.py
# 17: `sync`, `--rebuild`, `--seq` and `--json` 13, their arguments 4. doctor.py 29: each sessions repo cloned, synced
# within two days and under 3 GB, 24, its call 2, the datetime import 1, spacing 2. project.py 7: handoff syncs the
# conversations and is not ready while one is behind.
# 5.3.1 adds 79 to both, 16 of them (sessions.py) from reading 5.3.0's output on 2026-10-30: `show d20ab7c4` matched 274
# sessions, because a sub-agent's id starts with its parent's, so every citation of a session with sub-agents was
# ambiguous; the id resolved to the exact or main session 10 (its reason 3, the lookup 5, spacing 2); a Claude Code
# sub-agent's role and parent 2; and a project read only from the session-start hook's own text, after a test
# fixture's line named a project this session never worked on: the hook's sources and why 3, the check 1. It adds
# 12 more, after an export from one session and a rebuild ran into the archive at once that day: one export at a
# time on a Mac (sessions.py 15: the lock beside the archive and why 3, taking it 4, a busy archive read as it is by
# a resume 2, the rebuild inside it 2, the export's body apart from the lock 3, the fcntl import 1), the CLI reading
# the move from the export -3. And 35 more (sessions.py), after `synthesis resume` run inside Codex's sandbox on
# 2026-10-30 showed only what other sessions had exported, and the new lock would have shown nothing: a read-only
# view of what each harness recorded since the last export 27 (its reason 2, reading without writing 18, a line
# still being written or unreadable 5, spacing 2), recent adding it when the export could not run 6, the lock that
# cannot be opened reported instead of raised 2. And 16 more (sessions.py) so two sessions handing off or closing
# the day together take turns instead of colliding in a sessions repo's index: one writer lock as its own context
# 17 and its reason 3, sync holding it 3, the export's own copy of the lock removed -10, the contextlib import 1,
# spacing 2.
# 5.3.2 adds 13 to both (sessions.py), from the first sync of history on 2026-10-30, which the commit check refused
# for two workspaces: masking with exactly what the check refuses, the principal's tier-0 list loaded as the check
# loads it 5 and a private key's header with its body in JSON text 1, the reason 3; each month committed alone and a
# refused month unstaged 2, after a refused month's files were swept into the next month's commit; the sessions in
# a commit counted from what git staged 2.
# 5.3.3 adds 16 to both (doctor.py), after a Mac with only the Claude desktop app had nothing to install into on
# 2026-10-30: the app's own Claude Code as a known location 2, the reason in the finder's comment 2, a location
# pattern expanded with the newest version folder first 10 (the function and its docstring 2, a plain location 2,
# the version order 4, spacing 2), the glob import 1, the finder reading patterns 1. And 2 more to the plugin
# (setup.py): each harness named before its plugin install, which prints nothing for up to a minute, after a first
# install that looked hung.
# Code may grow past these only with an itemized reason here (Rajiv, 2026-10-20: raise the ceiling, itemized, rather
# consolidate first).
CORE_BUDGET = 7794
PLUGIN_BUDGET = 24795


def _lines(files):
    return sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)


def test_core_stays_within_its_budget():
    assert _lines((ROOT / "synthesis").glob("*.py")) <= CORE_BUDGET


def test_whole_plugin_stays_within_its_budget():
    code = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts and not p.name.startswith("test_")]
    assert _lines(code) <= PLUGIN_BUDGET


def test_bash_guard_hook_is_fast(tmp_path):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la && git status"}})
    env = {**os.environ, "SYNTHESIS_HOME": str(tmp_path)}
    times = []
    for _ in range(15):
        start = time.perf_counter()
        subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "pre-tool-use"],
                       input=payload, capture_output=True, text=True, env=env, check=True)
        times.append(time.perf_counter() - start)
    # 50 ms is the target on the principal's Mac; shared CI runners get headroom.
    assert statistics.median(times) < 0.15

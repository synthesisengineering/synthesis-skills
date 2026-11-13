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
# install that looked hung. And 11 more (setup.py), at Rajiv's direction that day that anyone can install without
# running into problems: with no harness on the Mac, setup stops before changing anything and says which app to
# install (the message naming the harnesses asked for 6, spacing 2, the stop in main 3).
# 5.3.4 adds 70 to both (guards.py), after an unapproved site deploy and an early Homebrew tap merge on 2026-10-30:
# a shell script a command runs, read and followed three deep so a deploy inside it waits for approval 44 (the file
# reader 25, the follower 11, its limits 2, spacing 6); a push or merge to a repository listed in deploy_remotes 15
# (the remote match 5 and its spacing 2, the merge and push checks in _targets 8); the Claude desktop app's terminal
# tab guarded like Bash 8 (the shell-tool test 4, its spacing 2, the tab's own folder 2); a --dry-run publishes
# nothing 3.
# 5.3.5 adds 216 to both (commit_check.py), after four README screenshots in one commit on 2026-10-30 each needed an
# approval code for a match in their compressed pixels, and the same patterns matched 1,743 of the 8,982 images
# tracked in the principal's repositories (51 of 80 HEIC photos): PNG, JPEG, GIF, WebP, HEIC and AVIF read by their
# structure, so everything but the pixel data is scanned and compressed text is inflated. The section's comment, the
# format and scan-end patterns and the coded HEIF item types 10; the reader that follows concatenated images and
# keeps what comes after them 13; PNG chunks 20 (the zTXt, iCCP and iTXt text inflated 7); JPEG segments and each
# scan's coded data 21; GIF blocks 14, sub-blocks 5 and palettes 3; WebP 6 and its RIFF chunks, animation frames
# included, 13; HEIC and AVIF 13, their boxes 12, the item types 8 and the item locations 23; inflation within the
# 32 MiB bound 8; spacing 28. images() 12, an image's added lines replaced by the text its HEAD version did not
# carry, and its spacing 2; the key rule reading that text in scan() 2; the call in problems() 1; the zlib import 1;
# the docstring's sentence 1.
# 5.3.6 adds 26 to both (guards.py), after the Ownwords release and npm publish on 2026-10-30, run from the
# synthesis-skills checkout, counted as two deploys of synthesis-skills: a publish identified by what it publishes, the
# function 21 (its docstring 4, the release's repository 4, the npm package path 11, the folder otherwise 1, def 1),
# npm's options that take a value 1, spacing 4. And 118 more to the plugin (synthesis-daily-rituals'
# stop_reprompts.py), the weekly count of Stop-hook send-backs Rajiv asked for that night: the module's docstring and
# shebang 15, imports 8, the hook's labels 7, the archive's location 2, the hook's words read from its blocking-error
# report 5, each send-back in the window found by its file's last write 27, the count by check, harness and repeated
# item 14, the command line and its report 25, the entry point 2, spacing 13. And 48 more to the plugin
# (synthesis-onboarding), a compaction brief in every synthesis workspace's instructions at Rajiv's direction on
# 2026-10-31, for every user rather than him alone: in workspace.py, add_brief 24 (its docstring 2), with_brief 8,
# the section's comment 3, the markers 1, the glob import 1, the new workspace's seed 1, spacing 5; in setup.py, the
# --compact-brief flag 2 and its call 3.
# 5.3.7 adds 6 to the plugin (decay_sweep.py), after a second mid-day run's record was never swept: its name 1, the
# match that reads it 0, its place after the first mid-day and before the day-end 5.
# 5.3.8 adds 1 to both (reply_check.py), the Stop hook's two phrases for an external wait handed back to the
# principal (2026-11-02). And 104 more to the plugin (synthesis-daily-rituals' stray_lessons.py), day-end's check for
# lessons written into project records instead of the lessons folder, after the principal asked that day for every
# lesson in the usual place: the module's shebang and docstring 16, imports 8, the heading and label markers 2, the git
# helper 3, a line's marker test 2, the section a marker covers 13, the markers added since the date and unlinked 23,
# the command line and its report 22, the entry point 2, spacing 13.
# 5.3.9 adds 1 to both (guards.py): the docstring line saying a `--help` publishes nothing and why `-h` stays held.
# And 33 more to the plugin (synthesis-skills-manager's release.py), a GitHub release for each version at Rajiv's yes
# of 2026-11-02, since GitHub's release list still showed a 4.x release as latest: the stage's docstring line 1, the
# GitHub remote pattern 1, the CHANGELOG entry reader 4, github_release 22 (def 1, docstring 2, the tag and the
# GitHub remotes 2, no remote or a dry run 4, the loop 2, create unless it exists and refuse on failure 5, read back
# as latest 4, the line and its return 2), its call in main 1, spacing 4.
# 5.3.11 adds 13 to both (doctor.py), the hook self-test at background priority, after the Synthesis Console, a launchd
# Background job, kept showing the warning 5.3.10 meant to clear: background_priority 7 (def 1, docstring 2, the
# priority read on Linux 2 and on macOS 2), spacing 2, the self-test's docstring line 1, the time reported rather than
# judged 3.
# 5.3.12 adds 163 to the plugin. 48 in synthesis-slack-sync's thread_checker.py, after it listed a thread under a
# channel whose heading came 566 lines earlier and listed the thread's replies as parents (2026-11-03): the pattern
# for a heading naming one channel and its comment 4, the colon-less `(TS n)` stamp's comment 1, the reply-link
# pattern and its comment 2, the heading levels' comment 2, a channel id written on a line and the link targets it
# skips 2, stamps_in's reply links 3, line_channel 12 (def 1, docstring 4, the ids outside links 3, the nearest one
# before a TS 2, spacing 2), and in extract_threads the evidence rank in place of the thread list 0, the scope of
# enclosing channel headings 1, the heading block 7 (17 lines in place of 10: its level and the channels it ends, a
# heading that names one channel or writes one id, a heading carrying a TS never a section of threads read), each
# TS's channel by where it is listed 4, the best reading of a TS kept 10. And 115 in synthesis-skills-manager's
# release.py, the Homebrew formula moved to each release's tag at Rajiv's approval of 2026-11-03, after it had stayed
# at 5.0.3 through eleven releases: the docstring 3, imports 2, the canonical repository, the tap, the formula and the
# failed check states 4, archive 2, archive_sha256 12, tap_formula 7, serves 2, homebrew_formula 44, homebrew_merged
# 19, their spacing 12, the calls in main 8.
# 5.3.13 adds 27 to the plugin (synthesis-skills-manager's release.py), after the 5.3.12 release took three runs by
# hand for GitHub's 502s (Rajiv's yes, 2026-11-05): the docstring line 1, the server-error pattern and its comment 4,
# retrying 14 (def 1, docstring 3, the loop and the stage 3, a server error or the last attempt 3, the notice and the
# wait 2, spacing 2), ci_state's second read 4 (the loop 1, the check and the break 2, the wait 1),
# the tap branch gone after the merge 4 (comment 1, the call 1, its answer 1, the line when it stays 1).
# 5.3.14 adds 31 to the core and 51 to the plugin (Rajiv's yes, 2026-11-05), after an idle compaction applied a summary
# whose in-flight items were 2 h 22 min old with nothing saying so, and a tap job with no runner stopped a release: in
# hook.py 30, the docstring 1, the pause threshold and its spacing 3, _away_note 20 (def 1, docstring 4, the end and
# the time 2, the threshold 2, the span 4, the end's time 2, the note 3, spacing 2), the Stop hook recording the
# turn's end 6; in board.py the session's `ended` 1; in release.py 20, no_runner 7 (def 1, docstring 2, the check 2,
# spacing 2) and homebrew_merged 13 (docstring 1, the rerun count 1, the failing checks 1, their runs 4, a run
# running again 2, the rerun and its notice 4).
# 5.3.15 adds 59 to the core and 66 to the plugin (Rajiv's yes, 2026-11-05), after Codex ran none of synthesis's
# hooks while doctor reported them trusted: in doctor.py 59, imports 2, codex_plugin_hash 25 (def 1, docstring 4,
# the walk 18, spacing 2), codex_trust_baseline 8 (def 1, docstring 2, the key 2, the path 1, spacing 2),
# check_codex_trust 17 (signature 1, docstring 1, the fingerprint 5, the baseline 5, a stale approval 5), APPROVALS
# and report 9 (the names 1, report 4, spacing 4), main 2 fewer; in release.py 7, the docstring 1 and the doctor
# stage 6 (the checks and their report 3, the approvals waiting 3).
# The knowledge-base distribution skill adds 857 to the plugin (the core is unchanged; Rajiv's yes, 2026-11-09): its
# read-only MCP connector,
# which serves an organization's published knowledge base to people its Claude and ChatGPT workspaces cannot reach.
# server.py 224: FastMCP's Google provider with the access list at sign-in and on every token, the tool-call check,
# the OAuth store (memory, or Firestore encrypted and prefixed), search and fetch in the shapes ChatGPT expects,
# /health and the start. source.py 192: the shallow git clone with a private copy of the deploy key and strict host
# keys, the remote-head check, snapshot swap and removal, the last good copy kept on any failure, and the refresh
# thread. corpus.py 131: documents from the published references folder, never through a symbolic link, front
# matter through synthesis/yamlish.py (reused, not copied) and the provenance stamp. search.py 124: BM25F ranking,
# word folding and snippets with the standard library. config.py 112: every environment variable checked at once.
# access.py 61: the access list, verified addresses and hosted domains. The package docstring and entry point 13.
# The connector runs in its own image, so nothing in the core could be reused beyond the YAML reader.
# The same skill's build_plugin.py adds 436 more to the plugin (the core is unchanged; Rajiv's yes, 2026-11-09): the
# plugin build an organization kept as its own script, made general, every organization value now coming from its config, exclusion list and
# templates. Each count includes the two blank lines before it. The shebang and docstring 19; imports and the
# plugin-root path 18 (synthesis/yamlish.py and the connector's front-matter split, reused, not copied); constants 37
# (the default lint patterns 10, the config schema 14, the limits 2, names, versions and placeholders 11);
# check_shape 20 and load_config 49 (every config problem reported at once, then the defaults); glob_to_regex 16;
# read_excludes 8; git 7; collect 21 (exclusions, hidden paths, links never followed); one_line 4; build_index 19;
# fill 17; guard_output 13; dump 4; resolve_commit 16 (the UTC version, {count} refused on a shallow clone);
# uncommitted 8 (what is read must be the commit the stamps name); read_knowledge 30 (the lint, OKF front matter and
# the stamp); render_skill 17; manifests 22; main 82; the entry point 4. Its publish_plugin.sh is shell, outside the
# count.
# The same skill adds 335 more to the plugin (the core is unchanged; Rajiv's yes, 2026-11-11), so an organization's
# IT team manages who reads its knowledge base and a Gemini notebook can read it too. 141 for access by Google group:
# groups.py 110, the roster of each allowed group's members from the Cloud Identity Groups API (the docstring 9,
# imports 7, constants 4; google_reader 17, a GET as the service's own account with the read-only groups scope;
# GroupRoster 73: the class and its docstring 3, __init__ 9, people_in 19 following nested groups once each,
# refresh 16 keeping the last good roster for at most three intervals, current 4, contains 4, start 11 with its
# refresh thread, stop 3, health 4). server.py 11 (the roster started before serving and stopped on any failure,
# its state in /health, fetch serving the plugin's guide), access.py 10 (a group member passes; an unreadable roster
# refuses with a reason a person can act on), config.py 6 (KB_ALLOWED_GROUPS and KB_GROUP_REFRESH_SECONDS, either
# list enough), corpus.py 4 (the guide beside references/ kept apart from search). 194 for publish_drive.py, the copy
# a CI step keeps current in a Drive folder, signing in through workload identity federation so no key is stored:
# the shebang and docstring 26, imports 14, constants 4, Refused 4, call 19 (a refusal names the status, never the
# token), access_token 28 (the token given, or the step's OIDC token exchanged at Google's Security Token Service
# for a service account's), published_files 18, drive_files 19 (every page, duplicate names refused), upload 11
# (replaced in place or added), sync 29 (unchanged files left alone by MD5, dropped ones to the trash, the notebook's
# manual steps named), main 18, the entry point 4. Each count includes the two blank lines before it.
# 5.5.0 adds 453 to the core and 880 to the plugin (Rajiv's go on the plan, 2026-11-11), after three things that
# happened in one week: a deadline that could not be undone lapsed as one row among many, an agent staged a meeting
# into the same day three days running, and a repository whose rule was "pull requests only" turned out to have
# taken 61 direct pushes. Five review rounds by a second model shaped the two guards, and every finding has a test
# that failed first.
# In guards.py 400. The same-day rule 157: _invited_today 43 (the rule's setting, the principal's own addresses,
# each event of a call judged by itself, its zone, its guests, a move that names no guest list), _falls 19 (today
# as written, on this clock, in the event's zone, or not knowable), _invitees 15 (guests in whatever shape a
# connector gives them, removals and rooms left out), _own_hold 15 and HOLDS_READER 4 (the holds ledger's own
# reader says which holds are in force today), _starts 11, _events 9, _keys 8, _today 4, the start keys and their
# comment 5, the address, month and written-date patterns 3, the guest and calendar-write patterns and the address
# keys 5, check_send's approval of its own 11, _sends 2 (a quiet move to today is not quiet), spacing 2, an import 1.
# The shell reader 16: _simple 5, _commands 7 and _parse 4 report the `&&` chain each command stands in, so a
# branch switch counts only for a push that runs only if the switch succeeded.
# The pull-request gate 227: _gated_push 68 (where a push can go, every branch at once, routing config, the default
# branch or the lack of a record of it, what earlier commands left current, each refspec's destination),
# check_pr_gate 58 (the line's pushes, what rerouted a push or moved the branch before it, the approval for one
# exact push), _push_options 32 (options as git reads them), _push 28 (a push through aliases and leading options),
# _switched_to 13, _repo_names and the section's comment 6, the git commands that are never aliases 4, the push
# options 5 and their short forms 2, the routing prefixes 3, the two refusal phrases 4, the rebase options that
# take a value 1, spacing 2, the dispatch line 1.
# In doctor.py 50: check_pr_gate 46 (commits on a gated default branch that came through no pull request, a
# checkout that records no default branch, a repository with no checkout here), its call 2, spacing 2. In
# install.py 2: the chief of staff's scripts in the runtime 1, the docstring's line on hook approvals 1. In
# sends.py 1: a moved event is a calendar write.
# And 427 more to the plugin. slot_check.py 224, the verdict that goes with every proposed meeting time: judge 108
# (the same day, protected hours, working hours, the deep-work block, the meeting load, placement beside existing
# meetings, an existing touchpoint with the same people, the requester's deadline), main 31, the docstring 19,
# moment 13, free_blocks 12, imports 10, the entry point and its spacing 10, part 5, stop 4, hm 4, clock 4, the
# verdict order 2, the beside window 1, the address pattern 1. decay_sweep.py 143, critical deadlines reported
# apart from the rest: critical_row 26, collect 20, alert_today 17 (three days out, one day out, the day, past
# due, moved off a day the workspace does not work), main 17, critical_lines 15, alert 15, declared 9, the
# docstring 6, parse_plan 6, imports 4, the path to the core and the lead and alert days 7, the keyword net 1.
# ritual_state.py 43, a ritual record refused over a past-due critical deadline: critical_deadlines 27, the
# docstring 5, today 4, cmd_record 3, the sweep's import and its spacing 3, the clean outcomes 1.
# build_packet.py 4: a row tagged critical is refused. sync_watermark.py 13, after two workers advancing one
# store at once lost 27 of 632 advances (reported 2026-11-11): held 12 (the store read, changed and written back
# under a lock), its imports 2, spacing 2, and one line fewer in each of begin, advance and defer.
# 5.6.0 adds 284 to the plugin, 49 of them in the core (Rajiv's go on the plan, 2026-11-11). linkedin_messages.py 216,
# LinkedIn's two inboxes as a ritual surface, after a principal found messages there that no ritual had shown him:
# main 40 (the two commands, the day a plan counts from, the inbox's name, an empty inbox, a conversation open
# during the read named), parse 40 (each conversation from the list's text, a sign-in or security page above the
# list, an inbox the reader says is empty, the coverage, the opened count and the line with its inbox), entry 32
# (who, when shown twice or once, who spoke last, unread counts, LinkedIn's own reply nudge, InMail, the account on
# either side of the closing sentence), the docstring 27, plan 27 (the declaration, each inbox's address in the
# new-message view and the day it is scrolled back to, an inbox with no address refused), when 17 (a clock time
# for today, a day before it, a date from last year), imports 8, stop 5, the path to the core and no bytecode 4,
# the entry point 4, the list's patterns 12 (the closing sentence 2; the clock, the day, the months, the unread
# count, the nudge, the status line, the wall, the view's address, each inbox's address and a first read's reach
# 1 each). sync_watermark.py 3: `linkedin` among
# the stores that move only with their reader's coverage 2, the docstring's line 1. decay_sweep.py 16, after nine
# drafts and a ledger carried deadlines the sweep never read: collect 12 (a declared folder of other records, each
# file read as of the date in its name or of today, a plan outranking a record), main 2 (the flag and its roots),
# the record-name pattern 1, declared 1. In the core, approvals.py 43 and hook.py 6, after a principal typed nine
# codes after one "approve" and eight were passed over without a word (2026-11-11), and after a second model's two
# reviews of the reader: typed_text 19 (what a harness wraps into a prompt, from a name's first opening tag to its
# last closing tag, taken out in one pass over the tags where the old pattern took seconds on a long prompt, a mark
# where each block was so no list runs across it), the patterns 10 (the list after the word, with a negation before
# it as part of the match, and its comment 5; one code's shape, a space inside a line, the negation, the mark 1
# each; a tag and its comment 2; less the old block pattern), mentioned 6 (every code-shaped word in the message),
# _prompt 4 (each block of a record read by itself, one marked as not the principal's left out), typed_codes 3,
# the module docstring 1; in hook.py, user_prompt_submit 6 (a pending code that is in the message and was not
# approved is said aloud).
# 5.7.0 adds 735 to the plugin, 322 of them in the core (the request came from the principal through his operations
# seat on 2026-11-11, with two additions the same afternoon; he gave the release its go that day). travel_check.py
# 285, after an evening 28 miles from a principal's home sat on his calendar for six days with no travel time, route
# or fare: judge 112 (each in-person event of the days asked for: an exact address, the event's travel line, a block
# on each side with every line a traveler needs, whose a block is, an arrival early enough, and the four cases only
# the principal settles), main 34, the docstring 23, place 19 (no place, the principal's base, anywhere else; a
# street address is a place whatever else the location says), days 15 (the days an entry covers, so one under way
# counts), the entry point 13 (a read it cannot make sense of exits 2), exact 11 and street 6 (what an address is:
# a venue's number, a room and a time of day are not one), lines 10 (a block's labeled lines, read through HTML, a
# placeholder counting as none), form 6 (a travel line is one of its three forms), tidy 5, stop 4, imports 11, the
# patterns, constants and the path to the slot check 16. slot_check.py 45: judge 25 (the trip there and back as
# taken time, an in-person slot refused without its minutes, when the principal is home, and what the night
# leaves), morning_after 9 and span 5 (the next morning's first commitment, shared with the travel check), the
# docstring 3, main 3. ritual_state.py 82: travel 33 (where a workspace checks travel, no record without today's
# result, with one that does not agree with itself, or while an event lacks its travel), choices 28 (no record
# while the plan puts a choice with no recommendation, or with no word on its cost where it commits the principal's
# time: a bare accept-or-decline had got a yes), the docstring 7, the seven patterns 9, cmd_record 3, an import 1,
# main 1. build_packet.py 1 (validate: every row that is not blind recommends). In the core, guards.py 314 and
# paths.py 8, after two review rounds by a second model and seven replays of 30 days of recorded commands:
# check_travel 35 and _place 8 (a calendar write at a place carries its travel line in one of its three forms; what
# a place is comes from the chief of staff's own check and the principal's policy; a place is read under any of its
# field names), _self_grant 60 less the 18 it took over from check_self_grant (each reading of a command judged:
# every write looked at whether or not a protected folder is spelled out, a link made and written through at once,
# a path handed to a program not known to only read it, a script judged by its own code and by what reaches it,
# and only a readable command where no session has reason to stand), _landing 38 (where a utility lands what it
# writes: -t, both ends of a move, dd, install -d, compressors, sort -o, uniq, an awk program, find, sed and perl
# without their script, a reference file only read), _python_writes 30 with OS_WRITES 2 and OPENERS 3 (a Python
# program read by its syntax, since a pattern stopped at the first closing parenthesis: whether it writes into a
# protected path, whether it writes at all, and a path spelled through a name, a join or an f-string), _resolved
# 28 and _put 16 (every reading of a command with its variables put where they are used: assignments, +=, a loop's
# list, the environment, a default, a trimmed end), _ran 19 (the script an interpreter runs is its first operand
# past its own options, so a program handed the hook's file is not running it), _awk_writes 13 with its token
# pattern and names 2 (an awk program's redirect, pipe or system call; a printed bar and a comparison are none),
# _named 11 and _changes 11 (the paths a command hands an unknown program, and whether a command find runs changes
# its files), READERS with its reason 9, _memory 8 and _material 8 (a project's memory notes and a saved tool
# result are the agent's own), _bare 5 and _commands 2 (the files xargs hands a command are marked, and env -C runs
# its command in the folder it names), SCRIPTED_WRITE 2 (node's fs methods and perl's open), the thirteen patterns
# and constants 13 (the Drive publisher among the deploy patterns), imports 2, spacing 4, check_destructive 1,
# _shell_writes 1 and check 1 (the destructive guard and the claim check read the same readings); in paths.py,
# spelled 4, inside 3 and an import 1 (a path compared as a Mac's file system finds it).
# After a third review round, three more replays and probes of its own, guards.py 263 more: _python_writes 182 with
# six constants 6 (an inline Python program read alone and by its syntax: a call known by the module it comes from
# however it was imported or renamed, arguments by keyword, a target the program spells judged where it leads, a name
# followed through assignments, loops, `with`, defaults, the program's own functions, lists and attributes, the words
# after the program and the variables of the environment placed where it reads them, what a file holds kept apart
# from where it is, a link judged at both ends, a helper's one caller, a folder the program changes into; 30 days of
# recorded commands held 23 such programs refused for writes they never made), _program 23 less the 11 it took over
# from _ran and the 4 from _python_source (how Python is handed a program: -Bc, -cPROGRAM, an option that takes a
# value), _awk_writes 20 and _string_writes 8 (a division is not a pattern, a comparison in parentheses is no
# redirect, a command given as one plain string is read as a command), _self_grant 13 (each command with its own
# stdin, the variables the command sets, a relative link read from its own folder), _commands 11 and _parse 2 (each
# command's own stdin; cd -, pushd and popd), _own 9 less the 6 of _memory it replaces (a session's saved workflow
# scripts are the agent's own), check_travel 6 (the policy read only for a call that names a place; a title that
# starts with the block word itself), _bare 2 (env --chdir= and sudo -D), spacing 2. slot_check.py 18: hour 8 (a
# policy hour that is no time of day stops the check), morning_after 4 and first_thing 3 (the morning begins at the
# policy's hour, entry or none), judge 1, spacing 2. ritual_state.py 27: _items 23 (a plan's choices under a heading
# of their own or as entries of a list, fenced blocks left out first), two patterns 2, travel 1 and choices 1 (an
# event's start is a whole date and time).
# After a fourth review round, guards.py 44 more: _python_writes 26 (the path an open call opens and the name of the
# file it hands back, a loop's rows as each name's values, a helper's default and its call of itself, a folder change
# under another name, a copy that keeps links, fileinput told to edit, os.open only reading, a file given as
# filename=), _commands 5 (a wrapper inside a wrapper; the folder stack turned by number), _self_grant 7 (a copy onto
# a note or a script lands on it, not inside it; a link made and then moved is that link at its new place), VALUED 2
# and _landing 2 (a mode, an owner, a size or a date is not a file), _awk_writes 1 and _string_writes 1 (a file name
# in two strings cannot be read; a command given whole keeps its folder and its unknown programs). slot_check.py 12:
# morning_after 8 and first_thing 5 less 1 in judge (a return after the morning has begun leaves no night).
# travel_check.py 1 less (the night is said by the slot check). ritual_state.py 10: _items 6 (the list's next entry
# begins another choice), _day 3 and travel 1 (each event's start and end is a whole date and time within the
# result's days).
# After a fifth review round, which found the fourth's fixes holding and ten refusals of ordinary work, guards.py 26
# more: _python_writes 24 (a command the program spells whole is judged as the shell guard judges a command, a file
# it found standing in for one word of it, reading flags are read however they are spelled, a name built with % or
# format keeps its folder, the last part of a path names no folder, a helper's keyword-only parameters are bound, an
# archive's member is unpacked where the call says, two files already open are judged where each is opened) and
# _self_grant 2 (a copy into a memory folder is judged by the note it makes there). ritual_state.py 1: a pattern (a
# recommendation on a choice's title line counts).
# After a sixth review round, which found two ways through the rule the fifth had added and two refusals of ordinary
# work, guards.py 22 more: _python_writes 18 (a command a program starts is judged in each folder the program may
# have changed into, with the program's configuration, the variables it sets, a list handed to the shell and a script
# fed on its input; a reading flag is known by its name in os; a name that walks a list of plain values is one of
# them), _landing 2 (the folders find searches are its operands before the expression: a pattern or a type letter is
# no file) and _self_grant 2 (a program that starts a refused command is told which rule refused it).
# After a seventh review round, which found four ways through what a command a program starts is given, one choice read
# as an example and one refusal of ordinary work, and after the same question was then put to the shell guard and to a
# folder that holds a protected one, guards.py 191 more. _python_writes 123: the folder each call is made in, followed
# in the order the program's statements run and a function's too, a descriptor standing for the folder it was opened
# on, 38; the variables a program keeps for a command however the mapping is kept, and a script written down a pipe,
# 39; a started command judged as the program it really runs, with the words after a shell's script, asyncio's and
# pty's ways to start one, and from the part of a folder that can be read, 13; a target judged from each folder the
# call may be made in, 11; what a walk or a pattern finds under a folder that holds a protected one, 13; a file named
# beside a descriptor and a tree removed, moved or copied over whole, 5; sys.executable, a walk's folder apart from its
# names and what a helper's one caller hands it, 4. _placed 21 with POSITIONAL, REBOUND, _shell_input 2 and _program 1
# (the words after a shell's script are put where the script uses them; sh -s reads its script on stdin). _reaches 10,
# _self_grant 5, _landing 3, _protected_roots 2 and WHOLE (a target outside a protected folder that changes it: a
# folder changed throughout that holds it, a pattern that reaches in). _find 7, _commands 3 and _changes 3 (each
# command find runs is a command of its own, a shell it runs read by its script). _string_writes 4 and _named 1 (a word
# handed to a program the guard does not know is read as a command line). WALKS, STARTS and PLACED, one line each.
# ritual_state.py 18: _shown 15, _items 2 and ENTRY (an example is what Markdown shows as code, so options indented
# under a list entry are read). slot_check.py 27: judge 20, clock 5 and the docstring 2 (the meeting load counts only
# events someone else is on; protected windows stand beside prose; 24:00 ends a day).
# travel_check.py 10: judge 8, BESIDE and TRIP (an entry beside an event that is titled like a trip is named as its
# travel in another form, not reported as no block).
# After an eighth review round, which found twelve more of the same kinds (a command another command runs, a value a
# program keeps before it moves, a pipe, a variable, an example read as a choice, a time that cannot be judged), and
# after the guard's own probes of a folder it cannot read, guards.py 103 more. _python_writes 39: a relative path made
# whole (abspath, realpath, resolve, absolute, getcwd, cwd) judged from where the program stood at that call, in a
# target and in a started command, 11; a pipe judged with the process it belongs to, by the name the process is kept
# under, and what is written down it piece after piece read as one script, 10; the names' fixed point as a function,
# run again once the folders the program may stand in are known, 9; with_suffix, with_name and with_stem spelled, 4; a
# walk or a pattern from a relative folder, glob's root_dir and a folder reached through a link, 2; a protected path
# kept in any mapping beside a variable the started command leaves to its environment, 2; a tree removed or moved away
# apart from one copied over, 1. _commands 21, Quoted 6, MESSAGE 3, STARTERS 2 and PROMPTED 1 (a word handed to a
# program the guard does not know is read as a command line only where it starts as a command, the value of a message
# option is words for a reader, and a command read that way is judged for what it writes, runs and starts; find's
# -execdir runs in the folder of what it found). _led 17 (a cd into the folder of a spelled path, a fresh temporary
# folder or the folder it is in is followed; any other substitution is a folder the guard cannot read). _self_grant 7
# (a relative write in a folder the guard cannot read, in a command that names a protected folder; the approved
# lines' folder removed or moved away whole). _placed 5 (quoting starts over inside a substitution). _find 5 (-execdir,
# -okdir and BSD's -f). _landing 2 and VALUED 1 (xxd's second operand is its output), GONE and OVER in place of WHOLE 1,
# less 4 in _string_writes, 2 in _deploys (the publisher is found past the interpreter's options by _program) and 1 in
# _named. slot_check.py 4: judge (a personal marker is a tag matched as a whole word; a plain word stops the check).
# travel_check.py 2: judge (an event at a place with no start it can read stops the check and is named).
# ritual_state.py 7: _when 3, _day 1, travel 1, QUOTE and _shown 2 (a quoted example is an example; an event that ends
# before it starts is refused).
# Before the ninth review round, after 254 plain commands and programs of this project's own were put to the eighth
# round's answer, guards.py 84 more. _python_writes 41: what names no folder (a path taken relative to a folder that
# holds it, one part of a path, a path flattened into a name, a digest, a length), and that relative path itself when
# both ends are spelled, 26; a word of a list built round a path the program found keeps that path, and a script it
# cannot read is refused, 5; a fresh temporary folder is a folder somewhere else, also when `with` names it, 4; what
# is written to os.popen is the command's input, 3; the standard library's own writers (a log file, a download, a
# temporary file made in a folder it is told), 3. _own_text 16 (a keyword argument or a statement of a program handed
# to another interpreter is not a variable the command sets). _commands 8 ($PWD and $OLDPWD are the folder each
# command is in and the one before, in its own words and targets and not in a script it hands a shell; what printf
# prints into a shell is its format with its words put in). _self_grant 6 (a command find -execdir runs is judged at
# the top of the search and in each protected folder under it). _led 5 (any word that starts with a substitution the
# guard can read: a temporary file, the top of the repository). _put 2, PLACE and DEEP (the folder a command is in).
# LIBRARY_WRITES 2. OPAQUE and _named 2 (a program for an interpreter the guard cannot read is held for each path it
# names).
# After a ninth review round (eleven findings at the edges of the eighth round's answer) and the probes that followed,
# guards.py 56 more. _python_writes 47: the folder a call is made in is followed through a `with`, a `try`, a branch,
# a loop and the program's main block, each in the order its statements run (a branch may not be taken, a loop may
# run no times or leave at any point, a handler and a finally may start from any point of the try, the body of
# `with contextlib.chdir` runs in that folder, and a change passed over by `suppress` may not have happened), 34; a
# descriptor stands for its folder as it stood when it was opened, 5; a process kept under a second name is the same
# process, 5; the parent of a path and `dirname`, 3. _commands 2, WORDS 2 and _named 1 (a handed command line starts
# as a command with any program the guard has a rule for, a reader included since it may redirect, and not with a
# shell's own word or a word a sentence starts with; a message attached to its option, `--body=...`, is words for a
# reader). _landing 2 (an operand that is `-` is the input, so the operand after it is still the output). _bare 2
# (what `trap` keeps to run when the shell ends). travel_check.py 11: is_block 10 and STEP (a travel block is known
# by the form of its title or by its lines, so an event whose title only begins with the block's word is an event).
# ritual_state.py 2: FENCE (a fence left open and an HTML comment are not the plan's own text).
# After a tenth review round (twelve findings) and this project's own probes of its answer (452 commands and
# programs and 36 plan shapes), guards.py 394 more. The probes showed one cause behind the needless refusals each
# round had met a case or two of: a name was read only when it was given one value, once, in one place (30 of the
# first hundred everyday programs run from inside a transcript folder were refused for it, 19 of the second).
# _python_writes 382. A program is read through every value a name may hold: its body 123 (what the program gives
# each name, each field of its own object and each entry of its own table: its assignments, a class's constants and
# fields, a data class's and a named tuple's, a parser's defaults, setattr; which functions' callers are all seen
# (not wrapped, not given another value, map) and what each hands back; the rule for a call named as a writer),
# gather 24 (what each function is handed, what each loop visits, each name where it is read), elements 25 and
# columns 18 (what a loop visits: a list, its rows, zip, enumerate, a table's values, what a walk or a pattern
# finds), spellings 18, values_of 14 and outer 5 (a target read once for each value; one of two values), key_of 11,
# entry_of 10 and table 14 (a field, an entry by its key or by a key held in a name, a place in a list, the
# environment with its default), spelled 20 (those readings, a template filled, a list joined, Path.home()),
# given_to 3. Each function by its own names: scope 16 and nodes_of 7. Each name where it is read, in the order the
# program runs: gives 16 (what an assignment gives, a pair unpacked, mkstemp's) and order 7. A call of the
# program's own function read by what that call hands it: answers 15, hands 10 (taken out of settle, kept between
# settlings) and asked 5 (a method is told from a function of the same name; a class reaches its __init__).
# folders 7 (a descriptor opened beside another), descriptor 4 (a number, and what os.open or mkstemp hands back,
# is no path), home 3 (the home a command or a program gives itself), elsewhere 3 and inward 2 (what a walk found
# from where the program stands only goes further into a folder named before it), named 3 (that, and the
# environment the program sets), settle 1, less 2 in leads. BY_NAME 4 and PATH_KEYS 2 (a call named as a writer in
# any library is judged where its path lands). check_self_grant 3 (a command that gives HOME its own value).
# _bare 1 (`trap --`), _own_text 1 (a program handed in double quotes), _named 1 (a message value given apart from
# its option).
# slot_check.py 22: morning_day 9 (a morning's outing is judged against the next night), judge 9 (an event is taken
# time on each day it covers; a slot on top of another event says so), morning_after 3 and first_thing 1 (a
# commitment begun before the return leaves no night). travel_check.py 2: judge (a block-titled entry with no clock
# times is an event; the outing's own way there and back is no commitment of the next morning).
# ritual_state.py 23: _items 12 (the entry an explanation stands in; a deeper heading or a bold line is a title),
# choices 3 (a closing line closes when it says what was decided; a recommendation marked on the option), ITEM 2,
# OPTION 2, FENCE 2, OPEN 1 and HEAD 1 (a quote inside a list entry, a heading or a row of a table as an option, a
# sentence that begins with the word, a fence longer than the one it holds).
# The eleventh review round, and the probes and the replay after it, add 389 to the plugin, 345 of them in
# guards.py (the bar the principal set on 2026-11-11: a round with no ordinary way through and no ordinary work
# refused). The round's eight findings in the Python reader were one gap, a field or a key read as one set of
# values whatever carried it, so a member is now read by the thing that holds it. In _python_writes: its own body
# 100 (a table or a row spelled out once and only read, handed as `f(**table)` or `f(*row)`, written out; each
# class's lineage, the __init__ that builds it, its kin and the function each node is written in; an argument
# parser's defaults; a class that keeps its keywords as its fields; the census of what each thing is given after
# it is made; where a writer by its name takes its path), part 42 (what one member of one thing holds: a table's
# entry, a list's place, an object's field, the environment's variable, and what it was given since, the last
# plain gift along one path standing for those before it; a thing that holds itself read once), resolve 10 and
# follow 30 (each thing an expression may be, as the place that makes it; a finished reading kept, one that runs
# away cut short, after the replay met two recorded commands that did not come back), built 27 (what an object's
# field holds as it is made: what the __init__ that runs gives it from what that call hands it, a base's through
# super().__init__, a field handed by place or by name, the class's constants and properties), under 19 (a value
# read with what one call hands the function and the object it is called on; a name the function gives another
# value is either, which a function that rebinds what it is handed had slipped past since the tenth round),
# sel_of 17 and path_of 6 (a member read or store, and the path it is reached by), named 15 (a member is built
# from what it holds, the program's own function from what it hands back, a comprehension from what it makes
# each one of; one member followed once), order 14 and flat 2 (the last plain gift before each read; a main block
# in line), members 11 (with its default; kept between settlings), asked 10 (`cls(...)`, `super().__init__(...)`,
# a method by the class of what it is called on, and a call on a file or a string is no call of the program's own
# method), stringy 9 (what reads as a path and not as an object or an open file), selves 7, read_as 7, is_member
# 6, spelled 5, key_at 5, handed_field 4, settle 4, gifts 3, keep 3, one 2, lineage 2, gives 2 (a pair unpacked
# from anything is its first and its second), elements 2, builds 2, outer 2, held 1; less table 14, answers 8,
# entry_of 8, key_of 4 and gather 2, which the member model replaces. BY_NAME 4, STRINGS 3, FOREIGN 2,
# OBJECT_FIRST 1, PATH_FIRST 1 and OPENED 1 (a writer in another library takes its path first, second or either;
# a library's own way to open a file).
# slot_check.py 27: judge 16 and whole_days 11 (an all-day block the principal marked, or one that says it is busy,
# takes its day; a night before an all-day commitment is not called enough; of several events at a slot's own
# hours one is the slot). travel_check.py 5: judge (the same night, said in the event's own lacks).
# ritual_state.py 12: _items 9 (a heading or a bold title after a choice's options begins another; a sentence
# between a title and its options), OPEN 2 (a recommendation or a decision that only puts the answer off), LED 1
# (a line led by a pictograph).
# The twelfth review round adds 56, 52 of them in guards.py (the principal's ruling of 2026-11-12: fix its twelve
# findings with tests first, show nothing got worse, and release). In _python_writes: census 37, less 13 from the
# body and 3 from keep, which it takes in (what each thing is given is gathered until it settles: rows added to a
# list and then copied into a table were missed in one pass), inlined 12 (what a function hands back, written with
# what this call hands it, so a factory called twice makes two objects), rowed 9 (a table filled from rows keeps
# each row's key with its value), part 4 (a table made from pairs or from another table; the round's one write
# let through), follow 3 (a union of two tables), spelled 2 (a template kept in a name), built 1 (a default made
# by a function written in place). slot_check.py 1 and travel_check.py 2 (an all-day hold; a trip into a day
# blocked whole; an all-day commitment at the principal's own place), decay_sweep.py 1 (a fence on a list mark's
# line).
# 5.8.0 adds 886 to the core and 1,070 to the plugin.
# wait.py 253, new (waiting for an expected event is a task): main 59, its usage 29, attempt 23 (a try in a session
# of its own, stopped with all it started; a program that cannot be started refuses), _watch 18, live 14, wake 11,
# _signal 10, _stop 10, _alive 8, span 7, record 7, sent_by 6, watching 6, said 3, unread 3, _folder 2, four
# constants, and the lines between them.
# reply_check.py 259 (the turn-end check reads a wait): the forms a wait takes 66 (WAITS and the patterns it is
# built from); the principal's own move 68 (THEIRS, YOURS, _theirs and their parts; a staged message, an approval
# code and a request hand them the turn); what announces nothing 43 (a wait as its sentence's subject, a label, a
# heading, a rule); held_by_harness 43 with its constants (background work the harness holds, read from the
# transcript's tail: of 815 recorded replies read as a wait, 586 were of this kind); unarmed_wait 22, check 8,
# quoted text 5, _probe 2, the module's note 2.
# guards.py 214: _unread_files 82 with _standard_base64 10, _sha256 12, HASH_SECONDS 3, check_upload 7 and the
# constants that say which tools read a local file and which names mark secrets 19 (a send's attachments are read
# as the connector reads them, before the approval, and the approval binds their bytes); temporary_addresses 20
# with TUNNELS 5, HOSTNAME, LOCAL and their parts 6, and message_problems 12 (an address that can change is refused
# before any approval); check_tunnel 13, _tunnels 13 and their two constants (a quick tunnel's start waits for a
# code); check_send 4, _python_writes 3 (a parsed program's own warnings are not the hook's to print),
# _protected 2, check 1.
# doctor.py 90: check_outbox 41, started_with 13 and connector_files 10 (the outbox is there, and the running
# connector was started to read it); check_temporary_addresses 10; check_wait_check 8; run_checks 3,
# check_shell_name 2, RELEASE_MANIFEST 2, check_codex_board 1.
# cli.py 22 (cmd_msg 10: what will deliver a message; cmd_who 6: a waiting seat; parser 3, main 3), board.py 22
# (waiting 6, Session 5, _describe 5, _held 4, _read_marker 2, ClaimConflict 1, less inbox 1), approvals.py 13
# (backed 11: a grant of a thing, held and not spent; 2 beside it), paths.py 6 (outbox 4, BOARD_FILES 2), hook.py 4
# (the mail hint at a session's start), project.py 3 (resume names a waiting seat).
# Outside the core 184: relied_on.py 94, new (main 48, its note 29, answer 17: the health of what other people rely
# on, each check put to the guard first); the knowledge-base connector 54 (config.py 40: load 18, temporary 10,
# TEMPORARY_HOSTS 6 and 6 beside them; server.py 10; access.py 4: the operator-only test mode); provenance_scan.py
# 33 (scan 9, main 9, its note 8, records 7: the folders a workspace keeps its plan in); setup.py 2 and
# autopilot_cli.py 1.
# 5.8.0, review round 3 (2026-11-12): core 342, plugin 431. A second model's 42 findings in the pieces above, and what
# the fixes' own probes found beside them, each with a failing test first.
# guards.py 201: _unread_files 65 (a url the connector reads from its own disk, does not fetch, or fetches nothing
# from for its host; an entry it would skip or rename; a source that cannot be parsed; a link of another name),
# _sha256 21 (the read runs in a thread the guard stops waiting for at its limit), CONTROL, CONTENT_ID and
# check_upload 3; _only_here 29, _carried 15, _here 7, temporary_addresses 7 and LOCAL, FILED, NAMED, _HOST, NEAR and
# TUNNELS 8 less _NAME and _NET 2 (a host is read whole: IPv6 literals, any scheme, a file's name with its line, a
# range, a wildcard-DNS name, a service's own host with a port); _tunnels 23, _reverse_host 17, check_tunnel 2 and
# NGROK, CLOUDFLARED, CARRIERS, LOOPHOLE and SSH_VALUED 7 less RUNNERS 1 (the launch forms that started unheld, and
# a named tunnel that was held).
# reply_check.py 89: held_by_harness 9 (only the harness's own entries start and end work; nothing raises); _asked 9
# with OTHERS 3 and _PLAIN 4 (a request is one put to the principal); _offered 6 with SPENT 3, USED 2 and _CODE 1 (a
# spent code offers nothing); _GETS 8 and _EVENT 1 (the session's own next step is no event); WOKEN 7 and _SEAT 4
# (the stated wake limitation passes); unarmed_wait 7, RULE 4, COUNTED 4, TABLED 3, STAGED 3 and SENT 2 (a
# first-person wait is read in a heading, a table and before a colon; a block is set aside); _NAMED 4 and WAITS 1
# (standing by for a named thing); HANDED 3 (the next clause hands the thing over); _ONCE 1, the module's note 1,
# less THEIRS 1.
# doctor.py 24: _procargs 15 and started_with 9 (the connector's environment read from the process record, whole).
# project.py 9 (_peers 13 and _recent_conversation 2, less resume 6: resume names a waiting seat when already
# bound); paths.py 9 (config 7, Unreadable 2) and cli.py 8 (main 5, _main 3): a config that is no object is
# unreadable, and a command that reads one says so in one line; wait.py 2 (attempt: a folder found on PATH).
# Outside the core 89: the knowledge-base connector 79 (config.py 65: load 22, _beyond_origin 15, _ip 11,
# old_spelling 8, temporary 2 and 7 lines of constants and notes; server.py 14: a refresh refused in the test mode;
# together its owner's five rulings and the review's three findings); relied_on.py 10 (a checker or a check that
# cannot run says so).
# 5.8.1 (2026-11-12): core and plugin 13. install.py: _compile 10 and install 3 (the runtime is compiled once at
# install, so a hook does not compile the guards from source on every call: 72 ms to 33 ms for a shell command's check).
# Code may grow past these only with an itemized reason here (Rajiv, 2026-10-20: raise the ceiling, itemized, rather
# consolidate first).
CORE_BUDGET = 11856
PLUGIN_BUDGET = 32613


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

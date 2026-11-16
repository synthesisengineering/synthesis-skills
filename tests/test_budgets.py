"""R8: budgets that make machinery regrowth a failing build, and hook latency."""

import json
from pathlib import Path

import pytest

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
# 5.8.1 (2026-11-13): core 34, plugin 61. install.py: _compile 18, _compiled 12 and install 4 (the runtime is compiled
# once at install, so a hook does not compile the guards from source on every call: 72 ms to 33 ms for a shell command's
# check; and, from the release's review, a session start compiles a runtime that an older release's installer switched
# to, a compiled file is held to its source's hash and not its date, and compiling cannot fail an install).
# conftest.py at the root 27, new: under an interpreter that keeps compiled code in one folder of the person's own
# (Apple's Python), a test run keeps its compiled code in a temporary folder, in this process and in each it starts.
# 5.8.2 (2026-11-13): core 3, plugin 294. doctor.py: _reap 3 (the doctor closes the three pipes it opened to a harness
# CLI when it stops it; they were left to the collector, which Python 3.13 reports at every such query).
# build_directory_package.py 291, new (the package of method skills for a plugin directory that lists no plugin with
# hooks; it left 5.8.0 for a passage since moved): verify 48 (the nine things that fail a built ZIP), its header,
# imports and constants' notes 47, main 45 (build, --check, --changed-since), carried 23 (what a package carries,
# read from the last commit itself for a ZIP that is written), CLAIMS 20, ACTS 6, COMMANDS 2 and BY 1 (the phrases of
# a text that claims a guard, a hook or an approval code at work, sends its reader to the board or needs the
# runtime), build 17, claimed 16 (a file read a paragraph at a time, so a claim that wrapping splits is caught),
# read_list 8, depends_on 7, git 7, read_json 7, committed 7, differing 7, claims 5, Unreadable 4, is_test 4,
# count 4, and 6 lines of constants (REPO, LIST, IMAGES, ICONS, MANIFEST).
# 5.9.0 (2026-11-13): core 444, plugin 583. What the principal typed reaches a record, and the archive is copied on
# a schedule. sessions.py 288: _Session 46 (held and flush: a line torn by a cut write is finished as a whole record,
# and a copy cut before its state was saved repeats none), uncited 43 (the prompts no record cites: which files are
# read, what is passed over, and what stops the listing with its name) and _text 11 (a string that carries an escape
# is read as the text it holds), worded 7 (a prompt's first words for the listing's line, every number set apart
# from its `#`) and named 5 (the sessions a citation's id names), _export 36 and lost 35 (the stamp every export
# leaves: what it could not copy, what is gone, the schedule's own mark; a loss only the principal clears), behind 20
# (the listing stops while a transcript that may hold the day's prompts is not copied), prompts 19, natives 17 (a
# folder or a transcript the search cannot look at is named), short 13, _codex 9 (a turn is read by how it says it
# began, and a mirrored copy is one prompt), CITED 6, STRING 3 and RECORDS 1, _rebuild 4, _shift 4, catalog 2,
# find 2, _prompt 1 and 4 lines of imports. cli.py 74: cmd_sessions 56 (the prompts action, which names a prompt by
# what opens it and says where it looked; --lost; the export's exit status; `show` begins each line with its
# session), parser 10 and _main 6 (a name a command may leave out is read after an option too: `show --json <id>`
# was refused), imports 2. doctor.py 46: check_sessions_export 41, run_checks 3, check_board 2. install.py 35:
# scheduled 24 and runs_only 9 (what the loaded schedule runs, read from its own command line), _git_global 2.
# project.py 1 (_recent_conversation).
# Outside the core 139: ritual_state.py 87 (prompts 66 and _is_day 8, each with the two blank lines after it: the
# day-end record runs the listing itself and refuses a clean close over an open prompt, a folder written from no
# fixed place is refused, and a day is one written YYYY-MM-DD; cmd_record 4; 9 lines of the module's note and
# imports) and setup.py 52 (register_sessions_export 27, unregister_sessions_export 11, main 5, _homes 4,
# _export_plist 4, EXPORT_LABEL 3, workspace_archive 2, HOMES 1 and a note 1, less 6 in _points_at).
# 5.10.0 (2026-11-13): core 200, plugin 455. commit_check.py 152, the check on an entry's own time, off unless the
# config has `record_times`: record_times 57 (which lines of a staged diff are an entry's stamp, and the two
# refusals), _stamped 34 (a stamp placed by its own day in its own zone, and whether a span had begun), AHEAD with
# the note of what was measured 14, _around 14 (for each line of a file, its code fence and the dated heading above
# it, in one pass), problems 8 (a commit that brings older lines is not judged: a merge, a squash merge, a
# cherry-pick, a stopped rebase), 6 lines of imports (zoneinfo where there is one), and the patterns 19 (_SPAN 5 and
# _DONE 5, the zones and the words each a closed list after a second review, _DAY 2, STAMPS 2, and one each for
# _MARKS, _CLOCK, ENTRY, BOX and REGIONS). doctor.py 48: check_teardown 46 (it reads a list that is only appended
# to, whatever else the file holds) and the two blank lines after it.
# Outside the core 255: teardown.py 114, new (a test's teardown list: main 52, its header and imports 30, read 17,
# said 6, plain 5, listed 4), 140 for the shape in which 27 scripts import the runtime (five lines each, ten in
# autopilot_cli.py, which imports it twice): one line that says the runtime is not there, where a traceback was;
# and 1 in the knowledge-base connector's server.py, whose start line in the test mode asks for the teardown list.
# 5.11.0 (2026-11-13): core 279, plugin 279. guards.py 126: 125 for the rule that a message naming a clock time goes on a
# fresh calendar read, off unless the config has `fresh_calendar`: _time_without_calendar 33 (the setting, the times
# in the words, the age of the read, the hold's words for this harness and for one whose record is not read),
# _calendar_read 29 (the calls, then the results that name one of them, each line looked at once), check_send 14 and
# check_outgoing 15 (asked before any code and again at the approved call, a code of its own, and either code
# spending the other), to_a_person 11 (what a message to a person is, for this rule and the next), CLOCK with the
# note of what was measured 10, _reads_calendar 9, one each for CALENDAR_READ and CALENDARS, and two blank lines;
# and 1 in check, which drops the record's kept lines, so that each call reads the record anew (a rewrite in place
# can keep a file's size and its time stamp, and a Linux run then judged the lines kept from the call before).
# reply_check.py 125, the question after a message to a person, off unless the config has `reply_watch`:
# unwatched_sends 47, _result 26 (whether a call went, by its error mark and by the guard's own words for a hold,
# and when), 14 for the turn's reader now shared with the calendar read-back (_turn 21, unread_calendar_writes 7
# fewer), _stated 21 (the statement's line on the board), check 11, HELD 3, TIMERS 1 and two imports. wait.py 17: the
# statement that no answer is awaited (main 14, its usage line, its sentence and one import). approvals.py 11: void
# 9 (a grant and a waiting request of one subject dropped unused) and two blank lines.
# 5.12.0 (2026-11-13): core 421, plugin 421. commit_check.py 119. Of them 111 are a status table held to its own header, off unless
# the config has `status_evidence`: status_evidence 46 (a row against its table's Status column, its columns for
# evidence and its softer ones, the refusal and the note), _tables 20 (each table's first row, found in one pass of the
# file: quotes, fences, indented code and list items), ROW with the note of what was measured 10, _record 6 (which
# files are records, shared with the time check), _name 6 (a header's words under its marks), problems 5 (the call
# beside the time check, and the note's line), _cells 4, _BLANK 3, _WORKS 2, and one each for RULE, _QUOTE, _ITEM,
# _CODE, _STATUS, _EVIDENCE, _SOFT, _NOT and _POINTS; and 8 are the fourth place an entry gives its own time, a line
# that opens with what was done and then the time (STAMPS 5, _stamped 2 for a weekday that is not today's, and a
# line of the note above them). guards.py 226. Of them 210 are the account a site shows in a
# workspace's browser profile, on only where `browser_routing` names sites under `accounts`: _account_hold 35 (which
# steps put something into a page, a page the record does not show, one reading for a site, and the words of the
# holds), _account_shown 34 (the newest read of the site that settles its account, a line read as JSON only when it
# holds one of the principal's addresses, and a batch only when nothing after its read can move a tab),
# named_sites 15 (the map's shape), _where 14 and _on_site 8 (an address as a browser reads it, against a site and
# its page; _web_app is 5 fewer for it), accounts_misrouted 13 (the same reading at the turn's end), _note_account
# 12 and _account 9 (what a read showed, written down once and one writer at a time), _misrouted 12 (firm where
# the key names the account's page, a condition where it names the site alone), _everyone 10 and _principal 6 (the
# principal's addresses; the same-day rule is 2 fewer for it), _browser_workspace 9 (the session's workspace, for
# the guard and the reply check), _puts 9 (a key that only moves puts nothing), _steps 8 (the steps of a browser
# call and the page each acts on, shared with the messaging pages), _said 4 (a result's text; _tabs and
# _last_selection are 2 fewer each), _browser_call 2, PUTS and its neighbors with the rule's note 14, check_browser
# 1, and six blank lines. The other 16 are the second review of 5.11.0's two rules: check_send 4 and _judged_send
# 3 (one send judged at a time), to_a_person 2, _time_without_calendar 2 (a sub-agent's record, and the session's
# found by its id), and one each for PERSON, CARRIES, _reads_calendar, _calendar_read and check_outgoing. doctor.py
# 27: check_browser_accounts 24, its call 1 and two blank lines. reply_check.py 30: misrouted_accounts 12, _sender 6
# (the texts' own sender, run and not read), check 4, _result 2, unwatched_sends 2, FAILED 1, one import and two
# blank lines. approvals.py 14: alone 11 (one decision at a time for a thing that can go on either of two codes),
# one import and two blank lines. wait.py 5: past 1 MB the file of statements keeps its last 64 KB.
# 5.12.1 (2026-11-13): plugin 25, all in the knowledge-base connector's server.py, so that a client whose ID is a URL
# (ChatGPT, Codex) can be stored on Firestore: hashed_firestore_keys 23 (its def 1, an 8-line docstring that says why
# every key is hashed, two imports with the blank line between them and the one after them 4, the strategy class
# with sanitize and validate, the blank line between them and the one after the class 7, its return 1, and the two
# blank lines after the function) and oauth_storage 2 (the key and collection strategies passed to FirestoreStore).
# 5.12.2, core 30 more, all in doctor.py: json_in 12 (a listing read past the words a command prints before it, from a
# brace or bracket that opens a line, each tried until one parses; the installer's own reader is 5 fewer for it),
# harness_checks 8 (Codex is asked for the plugin's own marketplace, for which it fetches no remote catalog, and
# the whole listing before the plugin is called not installed, with what lets its fetch finish), _version_ok 3 and
# find_client 1 (a command that gave no answer in time is the Codex on the machine where no other install answers),
# LISTINGS 2, MARKETPLACE, CODEX_WHOLE and PROBE_TIMEOUT 3, and codex_entry 1 (a listing with no version names no
# folder). The plugin 12 more beside those, in the installer: plugin_entry 12 (the marketplace first, absent said
# only from the whole listing, a listing past its limit stops the install), install_plugin 3 (no second copy beside
# one from another marketplace), LIST_TIMEOUT 1, _uninstall 1 (the copy that is there), and _json 5 fewer.
# 5.13.0, core 125 more. sessions.py 121: what the principal typed is filed as a prompt in every shape a Claude Code
# transcript holds it, and a session is tagged with the projects it wrote into. _Session 39 (wrote 36 with the blank
# line after it: the projects a tool call's written files lie in, by the guard's own readers, with arguments kept as
# JSON text read as the object they are, the working directory a call names or the row's kept for a relative
# target, a project taken as a folder that holds its CONTEXT.md, and a reading that cannot be made counted; its
# call 2, and the working directory kept 1), _typed 24 (one text block as its records: a prompt, a slash command as
# it was typed with the words beside it, a reminder and then the typed words, and a system record for a row the
# principal cannot have typed), _queued 18 (a prompt typed while a turn runs, which the harness keeps as a queued
# command: its mode, its origin, and no tag of the harness's at its head where no origin is given), _reminded 13
# (the reminders a block opens with; one that holds the tag's own closing text ends at its last one), _claude 9
# (the two routed through _typed, a queued prompt filed at its own time, and the working directory), _machine 8
# (the approval reader's own test of a row the principal cannot have typed), SLASH 5 with its note, _codex 2 (the
# working directory), and one each for INJECTED (what the harness keeps of its bash mode), REMINDED and OWN_TAGS;
# _reminded, _typed, _queued and _claude are each counted with the two blank lines before them. guards.py 4:
# _shell_writes 3 (the readings it could not make, handed to a caller that counts them) and _file_targets 1 (Codex's
# own hook gives a patch under `command`).
# 5.14.0, core 198 more: what the doctor saw of each harness's hooks is written down, a hook that runs strikes
# itself from it, and the doctor says where the day's prompt check is on. doctor.py 70: _note_waits 27 (for each
# harness the run looked at, the hooks its check's own line names and the line itself; a harness not looked at keeps
# its entry, another release's entry goes where the run found no line of that harness, and a hook that ran after the
# run began stays struck), check_prompt_check 26 (each workspace's setting read as its day-end reads it, the
# defaults' own for a workspace the config does not list, a refused one a warning; with two blank lines), main 10
# (--waiting: the count whose guard has not been seen to run, or that nothing looked since the release changed) and
# run_checks 7 (when the run began, the rituals' config read for the prompt check's line, the note written last).
# hook.py 49: _unguarded_note 23 (the hooks not running when the doctor looked and not seen since, with the doctor's
# line, for each harness, and a harness seen under another release; with two blank lines), _ran 21 (a hook that
# runs strikes its own event, where its transcript is a file in its harness's own folder of them and the entry is
# this release's), main 2 and HARNESSES 3 with its two blank lines. paths.py 50: _waits 18 (the entries that say anything: sound in shape and
# in time, a day old at most unless another release wrote them), note_wait 18 (one entry changed under the note's
# lock from what the file holds then, the other left), waits 10, WAITS and HOOK_APPROVALS 2, and two blank lines.
# rituals.py 29: prompt_check 18 (the one reader of that setting for the day-end and the doctor: off, on with its
# folders and first day, or refused with which fault), is_day 7 (moved from the record script, which reads it here),
# config 2 (a workspace that is a string, a number or a list of things refused in words) and two blank lines. The
# plugin 53 more beside those: the context doctor 55 (cited_entries 44 with two blank lines, a citation counted where
# it names a session whose folder holds its meta.json, in the archive here or a cloned sessions repo, and the count
# kept when the config cannot be read; main 6, its call with two roots of one name told apart; render 4, its line
# and the one where no archive is here; CITE_DAYS 1) and the record script 2 fewer (prompts 3 more, the setting read
# where the doctor reads it; its day test 5 fewer, moved to the core).
# 5.14.1 (2026-11-13): plugin 5, in the knowledge-base connector. config.py 4: the collection prefix read once into
# its own name and refused when it begins with H_ or S_ (the name 1, the check 1, its message 2; the line that read
# it inside Settings stays one line). server.py 1: hashed_firestore_keys's docstring, which now says the library
# raised on the lookup, is one line longer.
# 5.15.0, core 62 more, in the note of hook approvals as its third review left it and in the doctor's reading of
# Codex's model cache. doctor.py 36: _note_waits 16 (a look that could not tell written down as that, with the line
# that says why, in place of what another release saw; a harness with no plugin dropped; a harness not found said
# for a day; the clock read under the note's lock), _model_cache 15 with two blank lines (the cache read by its
# first whole value, and known as unreadable where it holds none), check_codex_catalog 4 (a budget that cannot be
# told is a warning) and harness_checks 1 (Muse's own code for a plugin that is not there). hook.py 13:
# _unguarded_note 6 (what the doctor could not tell, no empty bracket, whose the approval is), _ran 4 (when it
# strikes, and that it does not wait), main 2 (the strike after the handler) and session_start 1 (its own event
# struck before the note is read). paths.py 13: write_json 6 (a temporary file of the call's own, removed when the
# write fails), note_wait 6 (a writer that will not wait, and that a change must not call it) and waits 1. The
# plugin 319 more beside those. The deadline sweep 253: collect 52 (the newest plan's commitments, the dated items
# with no ID, a date that passed unannounced on any copy, a ledger's rows and its view, the plan's day apart from
# the day what is closed is judged by, and a reader that fails on one file a gap for that file), commitments 47 (the
# entries and a table's rows under a heading that places commitments, a row's status under the header that names one
# or in its last cell, a row with a clock time), ledger_rows 38, main 25 (the text report's lines for each new list,
# and the evening job's count of passed dates), _status 14, CLOSED_ENTRY 10 with its note, _cells 9, COMMIT 8 with
# its note, passed 8 (the banner for dates that passed), parse_plan 7 (the day each Lapsed mark speaks of, and one
# dated ahead), _holds 7, _closing_line 6, UNFINISHED 4, _tool 3 (a banner's tool found on the PATH and run), two
# each for STATUS_CELL, UNDONE, LEDGER_CLOSED and declared (the records folders), one each for DONE, STATUS_HEAD,
# RELEASED, OTHER, FINISHED, PARKED, TICK and OWED_DAYS, and alert 1 fewer. The record script 58: commitments 43
# (the check a workspace turns on, its refusal with each kind's remedy, its line), cmd_record 10 (one read of the
# plans for a record of today, by the plan's day) and critical_deadlines 5 (the refusal names each source not taken
# in full). The repository's conftest 9 (no test reads a rituals folder named in the shell). The context doctor 1
# fewer (cited_entries: a folder is a session's where it holds its meta.json).
# 5.15.1, plugin 6 more: the connector's GOOGLE_AUTHORIZE_PARAMS 5 (the setting and its four-line note) and
# build_auth 1 (the argument that passes it), so Google shows its account chooser at every sign-in.
# 5.16.0 (2026-11-13): plugin 1,077 more, all in the daily rituals' scripts; the core is as it was. lapse.py 592, new
# (a lapse written in one step: the register's row, then the mark at the item): _run 129, its opening words and
# imports 75, came 42 (what came of a lapse, and which lapse, asked where the rows are more than one item's or the
# line holds another), standing 42 (the row a lapse already has, asked about and not guessed, a copy's in another
# plan included), locate 35 (the item read again by the sweep's own reader; a plan whose lines are counted otherwise
# refused), prepare 34 (the marked plan written beside the plan and read back before it is put in place, taken away
# on an interrupt), find 26, held_by 16 (a row still held by the item at its line), in_table 15, occupant 15 (what a
# line holds now), append_row 15, main 14 (a stop the system asks for taken as an interrupt), sweep_reads 11, lead
# 9, place 9, title_of 8, where_cell 8, pick 8, _gone 8, _title 7, day_of 7, _at 7, bears 7 (which gaps stand in a
# lapse's way), link 6, file_of 6, read_back 6, _cell 5, listed 5, Refused 4, and 13 for its ten constants and the
# runtime it names. lapse_review.py 221, new (the register read for a review): main 53, read_register 46, its opening
# words and imports 44, register_path 18, lapses 11, place 11, patterns 9, row_id 6, plain 6, lapse_key 6, Unread 4,
# and 7 for its five constants. plate.py 190, new (everything open for a seat in one list): build 75, its opening
# words and imports 39, main 28, within 20 (a folder by what the file system takes for it), merge 19 (the copies of
# one item), newest 4, and 5 for its three constants. The deadline sweep 36: collect 22 (a link that hides nothing,
# of the same kind, is listed and is no gap; a declared folder's gap says how many files it holds that the sweep
# could read; a ledger's unread rows are counted by ledger; two gaps say whose they are; the dated items ahead say
# their plan's day), gap 5 (whose line a gap is on), item_blocks 5 (a field written as a list entry is its item's
# only beneath it) and parse_plan 4 (a gap on an item's own lines). The record script 38, in the reader of a plan's
# choices, which now says the line each choice opens on: _plan_lines 20 (each line it reads, by the plan's own line
# past its fenced blocks), _located 54 with _items 44 fewer (the reader under a name that also gives the line,
# _items its wrapper), and open_choices with the lines about it 8.
# 5.17.0 (2026-11-13): core and plugin 219 more, in the session archive, so a record's number names the same record
# for good. sessions.py 213: in _Session, seed 44 (a Mac with no archive of a session begins it from a synced copy:
# the copy in this Mac's workspace and month, its numbers kept, its own numbered past the other Mac's next, and read
# without writing for peek), read_again 17 (a session read again from its start, passing over what is held as today's
# reader would write it, numbered past the archive's last line), held 5 (a number written as words counts for
# nothing), flush 2 and __init__ 2 (the next number in meta.json, and the copy's gaps), emit 1; then _as_today 19 (a
# held record as today's reader would write it), _pulled 17 (a sync's pull, before it writes and before it pushes, and
# a failed rebase undone), in_time 16 (records in the order said), no_record 12 and given_here 11 (what show --seq says
# of a number given on another Mac, and of one given here), _blobbed 11 (a long text kept as emit keeps it, shared with
# _as_today), _when 11 (a time read whatever its fraction), _same 10 (what a record is, its source included),
# export_file 10 (a reading again where the archive is ahead of its state or the transcript was rewritten smaller),
# _moment 9 (recent's order), _write_synced 9 (a copy another Mac numbered or extended is not written over),
# _sync_workspace 8 (a refusal for one session, the pull first), Diverged 4, around 4, export 2, peek 2 and mask 1 (a
# named policy that cannot be read refuses), with _rebuild 14 fewer (nothing is moved aside). cli.py 6: the sessions
# command 5 (show says a number this Mac gave as that, and one that names nothing, with why) and the parser 1.
# 5.18.0 (2026-11-13): core 55 more and plugin 62, so the desktop app's local agent-mode sessions are archived and
# guarded. paths.py 31: desktop_agent_roots 25 (their projects folders, read level by level, a folder that cannot be
# listed said) and desktop_dir 6. sessions.py 13: natives 8 (those roots, and what of them could not be listed) and
# _identity 5 (a desktop session named with its own folder). guards.py 11: _claude_parts 12 (a path's parts below the
# CLI's projects folder or a desktop session's, by its words alone) and _protected_roots 1, with _own and _material one
# fewer each. The repository's conftest 7 (no test reads this Mac's desktop sessions).
# 5.19.0 (2026-11-13): core 356 more and plugin 356 (plan item 13.5, parts 1 to 3, with the 23 findings of its first
# review round), so a record no commit holds yet leaves this Mac with something. checkout.py 150: snapshot 38 (the
# claim's own untracked files first, every one of them not kept named, a file holding a credential left out),
# _tree_commit 28 (one commit through a temporary index for every snapshot; a file git refuses is left out and the rest
# kept), _staged_commit 17 (what the index held, as the snapshot's last parent), _holds 12, the module's constants 10,
# _changes 9 (git that cannot read is said; Finder's files are no record), _append 9 (a lock, and the journal's lines go
# with their snapshots), _stamp 8 and _commit 6 (no identity needed, the present time), _run 8 with _git 3 fewer (bytes,
# no newline translation), Unreadable 4, snapshot_paths 3 and dirty_under 1 (a repository inside a claim). doctor.py
# 119: unsaved 46 (every branch, names as written, a folder removed whole), check_fetch 31, check_unsaved 16,
# unsaved_hours 10, main 10 (--unsaved) and run_checks 6. sessions.py 46: fetch 26 and _fetch_one 20 (no FETCH_HEAD,
# git's own reason, nothing asked). credentials.py 37: the commit check's patterns moved word for word (commit_check.py
# 15 fewer) and held 9. cli.py 18: release 6 (refused when git cannot read), journal 6 (byte for byte; what was not
# kept), claim 4 and sessions 2. hook.py 1.
# 5.20.0 (2026-11-13): core 311 more and plugin 327 (plan item 13.5, parts 4 and 5, through two review rounds, and the
# unsaved count narrowed to what is actionable). board.py 94: carried 37 (a project's inbox read as records: a regular
# file of at most 64 KB named as a message, never through a link, its header checked), undelivered 22 (no other session
# here has read it, not carried before), carried_text 12, carried_ids 11 (names alone, for each prompt), mark_carried 8
# and constants 4. project.py 64: _carry_out 46 (each project named when it cannot be carried; never stops a handoff),
# carried_note 9, _mark_carried_out 8 (counted once its file is committed) and handoff 1. rituals.py 64: _machine 13,
# host 13 (a name two Macs never share), read 13 (every host's file, safely), hosts_folders 10, _moment 8 (a real moment
# across time zones) and is_record 7. sessions.py 39: _ritual_history 38 (a host's file, whole, committed alone; never
# holding the push) and _sync_workspace 1. hook.py 24: _carried_since 19 (told once at a prompt) and the starts 5.
# doctor.py 14: _unsaved_repo 32 and live_claims 7, with unsaved 25 fewer (read side by side). cli.py 12: inbox 12 (the
# words quoted, twenty at a time). ritual_state.py 16: carried_by 12 and imports 4 (plugin only).
# 5.20.1 (2026-11-13): core 62 more and plugin 70, so the deploy guard holds neither a syntax check nor too little (a
# seat's report, and its fix's review). guards.py 59: _no_exec 21 (a shell's options read in order up to its script:
# -n and -o noexec on, +n and +o noexec off, an unknown option reads the script), _alias_deploys 12 (an alias read for
# what it runs), _script_file 9 (`.`, `source`, `builtin source` and `--` read; one too large to read said so), _bound
# 8 (what an approval binds to, said in the hold), the option lists and the too-large mark 5, _script_deploys 3 and
# check_deploy 1. The repository's conftest 8 (no test reads this Mac's synthesis home, whose sessions repos hold its
# ritual history since 5.20.0). wait.py 3 and cli.py 1: who watches is read before a message is sent (a race CI met).
# 5.21.0 (unreleased): core 105 more and plugin 233, so one approval in Codex lasts through releases where the person
# chooses that (plan item 13.7, part 2: setup.py plugin --codex-user-hooks). doctor.py 100: check_codex_trust 25 (the
# user-level hooks judged by their own keys, the plugin's switched-off copies taken as intended; a copy left on, a
# declaration unlike the plugin's and a hooks.json Codex would not read named), codex_user_entries 20 (the hooks of
# Codex's own hooks.json that run the stable hook, by Codex's key), codex_hooks_problem 19 and CODEX_HANDLERS 1 (what
# Codex reads of a hooks.json, which is all of it or none), read_toml 10 (a strict reading that names the first line it
# cannot place), codex_user_declaration 7, calls_stable_hook 4 (shared with check_hooks_wired, one fewer) and _declared
# 3, and spacing 12. paths.py 5: codex_home 3 and spacing 2. The plugin's 128 more (setup.py): codex_user_hooks 60
# (declare, keep in step, take out; a file that cannot be parsed refused before anything is written), _switches 22 (a
# marked line per key in that key's own table), _replace 15 (a harness file written whole after its backup, with
# configure_codex 8 and configure_claude 7 fewer), _state_tables 10, _setup_wrote 5 (setup's own groups by their text),
# install_plugin 5 (every Codex install keeps the declaration in step), _uninstall 4, main 3 (the flag), the two marks
# 2, configured_ref one fewer (paths.codex_home), and spacing with the section's comment 18.
# 5.21.0 (2026-11-14): guards.py 4, Messenger inside facebook.com (its page and the pop-ups on every page) and
# Instagram in the browser's messaging sites: a comment line and three lines of five entries.
# 5.21.0, the release's own count: doctor.py 8, waits_on_person 6 (signature, a docstring of three lines, the test)
# and ASKS 1 with a blank line: an approval line that names a fault of setup no longer reads as waiting on the person.
# 5.21.0, a guard that cannot answer holds the call in Claude Code (the PreToolUse handler's "onFailure": "block"): core
# 30 more and plugin 38. doctor.py 30: check_claude_fail_closed 15 (the plugin's guard without the setting fails, a
# Claude Code older than 2.1.295 or one that names no version warns), claude_version 8 (`claude --version`, bounded),
# CLAUDE_ON_FAILURE 1, harness_checks 0 (the hooks file read once for both lines, one line fewer, and the new line) and
# spacing 6. setup.py 8: _hashes 3 and spacing 2 (Codex's hashes of setup's own groups, before and after), the note that
# an approval stays 3, and the event filed under it 0 (one line changed).
# 5.21.0, review round 1 (2026-11-14), the doctor: core 104 more and plugin 104. doctor.py 98: check_codex_trust 23 (hook
# state held inline named; an event covered in part judged as the plugin's, with advice by setup's record; an event
# declared twice; setup's switch with nothing covering its event, and an unreadable hooks.json while the option is on,
# as faults), codex_switch_lines 16 (setup's switch found by its table, key, value and mark, however spaced), _assign 9
# and read_toml 5 (the strict reading refuses a key set twice and any table or key inside a value or another header's
# table; lines end at line feeds alone), check_codex_hooks_file 7 (the person's own unreadable file, a warning of its
# own), calls_stable_hook 7 (the stable hook as the program a command runs, never a mention), _text 5, codex_covers 5,
# codex_hooks_key 4, check_hooks_wired 2 (its own looser test of the plugin's files, back), the shlex import 1,
# SETUP_MARK 1 and harness_checks 1, and spacing 12. paths.py 6: codex_hooks_record 4 and spacing 2.
# 5.21.0, review round 1, setup: plugin 112 more. setup.py 110: codex_user_hooks 16 (setup's own known by its record;
# a narrower declaration of the person's keeps the plugin's copy on; the edit read back before it is written; on,
# hooks.json first and off, config.toml first), _write_all 14 (a write that fails midway puts back what was written),
# _replace 13 (through a symlink to its target, the file's mode kept, no temporary file left, a file changed meanwhile
# refused), _codex_state 12 (hook state held inline refused), _switches 12 (setup's own lines alone go, found however
# spaced; a quoted `enabled` found), _toml_problem 12 (the strict reader, and tomllib where Python has it), _step 8 and
# setup_plugins 2 (the option's step apart from the install: off needs no network, a refusal hides nothing),
# _restore 7, codex_user_hooks_on 6 (the option on by a switch or the record, never by the mark's words),
# configure_codex 3 (nothing written into a file that does not parse), _uninstall 1 (the declaration out first, or
# nothing removed and exit 1), the stat import 1 and _UNREAD 1, with _setup_wrote 5 and install_plugin 5 fewer, and
# spacing 12. release.py 2: install_and_verify keeps the option in step with the folder it verified.
# The two merged (2026-11-14): the fail-closed work's 8 setup.py lines sit in round 1's rewrite of codex_user_hooks as
# _hashes 3 with spacing 2, its note 2 and the event filed under it 1; the ceilings are the sum of both counts.
# 5.21.0, a guard that cannot start or crashes holds the call in Codex and Muse too: core 4 more and plugin 6. doctor.py 4:
# codex_user_declaration 2 (the plugin's own command kept where it runs the stable hook, so the user-level guard carries
# the failure tail; its docstring one line longer) and check_claude_fail_closed's docstring 2 (what holds in Codex and
# Muse now). setup.py 2: the note that asks once again for the approval of a declaration whose hash changed.
# 5.21.0, after the release's first review round: guards.py 27 more. PUBLISHES 5 with its two lines of comment (a click
# on Post, Comment, Reply, Repost, Share, Publish or Submit on a messaging site waits, unless its summary says it only
# opens a box); WEB_MESSAGING 7 (a site is its host and every host under it, the short hosts that land on one, the new
# addresses of Teams and Outlook, X's chat and pages, Messenger's channel on every facebook.com host, every other page of
# the four sites marked, and every Gmail page holding Return as Google Chat's pop-ups do, on a line of its own); _web_app 1 (its docstring, the match now _on_site's); _steps 2 (with `keep`, which only the
# send guard passes, a navigate that names no host keeps a messaging site's page; the account check still takes it as
# unknown); _pages 1 (whether a box on every page may be a search); check_desktop 11 (10 for the
# words of a call that only types on those pages, which go on the principal's code, and 1 for the pages read beside apps).
# 5.22.0 (unreleased): plugin 248 more and the core as it was, for the sharing standard (plan item 14.1), which ships
# no phrase list (the principal's ruling of 2026-11-14). sharing_scan.py 162, new (the policy's backstop scan): main 37
# (one way of choosing lines, a refusal with its reason and exit 2, a held line named by file, line and phrase only,
# the summary), its opening words 17 (the shebang and the docstring with its three commands), read_contract 17 (the
# contract checked whole, then no policy, a policy that is not there and no phrases, each refused with what to do),
# added 19 (the lines a range or the index adds under the bundle, by their new numbers; a move read as a deletion and an
# addition, so a file moved in is judged whole; a binary file marked), whole 14 (every line of the named files and of
# the files in the named folders, a file holding a NUL byte marked, .git passed over), unjudged 7 (the policy, the
# contract, a path outside the bundle and a file that is not text), imports 6, matcher 5 (a phrase where a word starts,
# in any case, with any run of spaces between its words; one of five characters or fewer a whole word), git 5 (git's
# own message when it fails), the bytecode guard, the path beside it and kb_config 3, SHORT and HUNK 2, Refused 2,
# count 2, the entry point 2, and 24 blank lines between them. kb_config.py 81: adopt_sharing_policy 46 and the two
# blank lines after it (the policy named with the phrases given or with those the contract lists, never with neither;
# the template written where the contract says and never over a file that exists; the keys the contract lacks added
# after its confidentiality line at its first key's indent, every other line kept; the result read back and validated
# before anything is written, so no policy is left named with no phrases; a contract it cannot change safely refused,
# with the lines to add by hand), validate_config 11 (any other key refused at every level 4; the phrase list a list of
# phrases, and at least one while a policy is named, the error naming both ways out, 7; the policy's path read in the
# loop that reads the other two paths), main 10 (adopt-sharing-policy read first, with its repeatable --phrase, its
# lines and its exit), KEYS 7 with its two-line note (every key the contract names, by the mapping that holds it),
# POLICY and TEMPLATE 2, check_paths 2 (a named policy must be there) and the re import 1. workspace.py 5: the policy's
# template seeded from synthesis-kb-edit's, not a copy, 2, and the line saying it is not adopted and how to adopt it 3.
# 5.22.0 (unreleased): plugin 344 more, the core as it was (plan item 12.1, ruled 2026-11-14: five collections, each a
# plugin without hooks, beside the whole set). build_collections.py 299, new (each collection built from the flat folder
# into a folder of its own, and the branch the release publishes them on): verify 51 (what fails a built folder: a skill
# in no collection or in several, a dependency out of bounds, a file that is no manifest, license or file of the
# collection's skills, one that differs from its source, a hook, a skill or license missing, a manifest's name, version
# or dependency, the Muse list, a file in no folder, the two marketplaces), its header and imports 41 (the docstring 30;
# the imports 11, with the bytecode guard, its own folder on the path and the directory package's code), main 39
# (--check, a folder written whole from the commit or not at all, its one line), manifests 17, bounds 15 (a dependency
# outside a skill's own collection and the core, or outside its own folder where its scripts load it), marketplaces 15,
# tree 15 (the folders as a git tree, through an index of its own), build 14, homes 13 (each skill's one collection, from
# its frontmatter or awaiting_room), read_spec 11, category 6, the constants 6, hooked 5, described 5 (one description
# for the manifests and the marketplace entry), sources 4, order 3, text 2, the entry point 2, and spacing 35. release.py
# 41: collections_head 17 (the commit the branch moves to on a remote: its head when that holds the folders, else a
# commit on top), collections 14 (built and checked before the tag), publish 4 (the branch in the atomic push and its
# read-back), the import 1, the docstring 1, spacing 4. build_directory_package.py 4: tracked 14 (a package's files,
# now read for the collections too), with carried 12 fewer, and spacing 2.
# 5.22.0 (unreleased; 2026-11-14): plugin 769 more, all in the new skill synthesis-message-exports; the core is as it
# was. import_messages.py 769, new (a message export the principal authorized, read whole and checked before anything
# is written, into one private transcript per conversation; standard library only): main 57 (the arguments, the
# refusals made before anything is read, the writes and the report); read_export 57 (each file's kind, every
# conversation read before any write, what is unknown kept for the listing, two ids that would share a file name
# refused); Zip 43 (read in place: an entry that could lead outside, a link entry, a name given twice or a member over
# the limit refuses the archive); plan 40 (new, extended or unchanged, reading only the transcripts this export would
# write; a secure-storage id that now names other people is not merged); parse_transcript 37 (an earlier transcript
# read back by its fences, an edited one left alone); Folder 35 (walked without following links, refused if it holds
# one); classify 35 (a file's kind by its place in each layout); its constants 35 (the sections, layouts, media kinds,
# limits, known fields and the characters that hide themselves); secure_conversation 26 (the secure-storage shape,
# its timestamp unit decided per file); message_block 24; keyed 23 (a message named by its time and a digest of what
# it says, so a re-import adds only new messages); dyi_message 21; render 21; dyi_conversation 19; listing 19 (file
# names and sizes, never text); write 18 (whole or not at all); its docstring 15 and imports 14; read_transcript,
# secure_message, since_of and uris 12 each; messages_root and safe 11 each; open_export 10; inline, reactions_of and
# repair 9 each (repair: the Latin-1 escape quirk undone only where it round-trips); Refused and Unknown 8 each;
# checked_times, code, duration, fence (more backticks than the text holds), in_time_order, load, text_of and visible
# (hidden characters shown) 7 each; Unreadable 6; day_heading, kind_of, participants_line, shown and tally 5 each;
# moment, stamp, too_large and whole 4 each; the __main__ guard 2 and the opening two lines 2.
# 5.22.0 review round 1 (2026-11-14): plugin 157 more, all in the message exports' import_messages.py; the core is as
# it was. R1-10 4: keyed 2 (the key leaves out the sender's name and an attachment's folders) and parse_transcript 2 (a
# transcript of an earlier format left alone). R1-11 43: plan 18 (a secure-storage conversation goes to the transcript
# holding its messages; one in two transcripts, or two for one transcript, skipped), holders 17 (each secure-storage
# transcript in --out read back), read_export 4 (named by display name and first message, never by index) and slug 4.
# R1-12 27: fixer 11 (the repair decided once for a whole file), strings_of 9, as_written 4, and the repair passed to
# the readers 3 (dyi_message, dyi_conversation and secure_conversation 1 each). R1-13 25: Zip 10 (vet: method and
# ratio from the archive's directory), read_export 9 (count, total and each file's size before the first read), Folder
# 3 and the three bounds 3. R1-23 16: the hidden and kept characters 6, visible 5, hidden 4 and unicodedata 1. R1-24
# 11: within (each existing ancestor compared by its identity on disk). R1-26 31: redacted 15 (each name replaced by a
# token keyed for one run), listing 6 (the caution), main 3 (--listing-redacted), the redaction key and the names a
# listing keeps 4, hmac and secrets 2, shown 1.
# Merged into release 5.22.0 on 5.21.0 (2026-11-14): the ceilings are 5.21.0's (core 14924, plugin 38171) and what
# each 5.22.0 paragraph above adds over 5.20.1's: plugin 248 for the sharing standard, 344 for the collections and 769
# for the message exports.
# 5.21.1: guards.py 1, the comment's third line: a click on a control that publishes waits on every page, since a
# public review went out on a site that is no messaging site through a click on Submit rating.
# 5.21.1, after the second review of 5.21.0: guards.py 76 more. The summary rules 38: PUBLISHES with effect-first verbs,
# any form of a click verb and a word or three before the label, and Tweet and Done (3, as before), OPENS 3, POSTS 1,
# ROUTINE 2 and MESSAGE_WORDS 1 (a click that only opens or closes a box, a sign-in or a search, passes), the page-script
# patterns 8 (WRITES, SCRIPT_ACTS, SCRIPT_SENDS, SCRIPT_ROUTINE and their comment), the comment 5, _publishes 9 and
# _submits 12 (Return, or Space or Return after Tab), less the 6 lines of 5.21.1's pattern. _released 15 (the words the
# typed-words code released, shown in the next send's hold from that page). check_desktop 12 (the key rule, page scripts,
# a register hit on a page that is no messaging site going on the send's code, typed words kept out of the record).
# _browser_item 8 and _desktop_actions 2 fewer (a form fill and a page script alone reach the guard), BROWSER_STEPS 1,
# WEB_MESSAGING 3 (Gmail, Outlook and Google Voice by the hosts typed), and _pages 1 (a local app's page).
# Then 2 more, NAMES_POST and its comment, for Rajiv's ruling of 2026-11-14 ("Skip typed text that names no post"): off a
# messaging site, typed words then a key that submits wait only when the call names a message, comment, review, post,
# reply or tweet.
# 5.21.1, review round 2 of 5.21.0, setup and core: core 94 more and plugin 129. doctor.py 48: stable_rest 14 and
# STABLE_SPELLINGS 2 with their spacing 4 (the stable hook as the program a command runs, spelled as sh finds it: a
# quoted ~ or a single-quoted $HOME names no hook), calls_stable_hook 6 fewer (it asks stable_rest), _runs_as 9 with
# spacing 2 (a user-level group covers the plugin's only as its own invocation, the guard's with its fail-closed
# tail), claude_installs 11 and oldest_claude 4 with their spacing 4 (every Claude Code on the Mac, the oldest judged),
# check_claude_fail_closed 1 (the oldest one's path where there are several) and harness_checks 3. hook.py 29:
# GUARD_SECONDS 1, _Late 2 and _late 2 with their spacing 6, and pre_tool_use 18: its docstring 4, the deadline set 4
# (signal's import with its blank, the handler and the timer) before the guards load, the try 1, the held answer past
# the deadline 3, the timer cancelled and the handler put back 3, and an unreadable config's answer 3 more (kept, not
# returned, so it prints once the timer is cancelled). install.py 13: InUse 2 with spacing 2, and uninstall 9 (the
# runtime stays while Codex's own hooks.json runs it: its docstring 3, the check 3 and the refusal 3). cli.py 4:
# cmd_uninstall says the refusal and exits 1. setup.py 35: codex_user_hooks 14 (declares only where the stable hook is
# in place 4; each event left running twice named, with what two guards do to an approved call: its lists 1, the event
# filed 1, the words 2, the narrower declaration's note 1 longer and two notes of 2 each; a CRLF hooks.json kept CRLF 1),
# main 2 (the runtime installed before any plugin), _persons_calls 6 with spacing 2, and _uninstall 11 (the person's
# own declarations keep the runtime, nothing removed and exit 1, 6; a declaration made meanwhile, 5).
# The coordinator's ruling on review round 2 (protective automation fails closed): a user-level guard covers only with
# the fail-closed tail. _runs_as's condition and docstring change in place: no line more.
# 5.22.0, the guard's time: guards.py 2 in _placed (the script's rebinding searched once, not for each character;
# a 1,700-character heredoc of substitutions had taken the guard 13 s, past the hook's 5).
# each 5.22.0 paragraph above adds over 5.20.1's: plugin 248 for the sharing standard, 344 for the collections, 769
# for the message exports and 157 for their review round 1.
# 5.22.0's review round 1, the sharing standard's findings (2026-11-14): plugin 252 more, the core 1 of them.
# kb_config.py 63:
# adopt_sharing_policy 20 more (the template written first and the policy named only once it says who reads it, a
# folder at the policy's path refused, a key left null or empty replaced in its place, the contract's own line ending
# kept, the key the read-back found otherwise named, and the configuration gate run on the result), spelled 15 with its
# two blank lines (each part of a path as the disk spells it), check_paths 11 (a path spelled otherwise on disk; a
# named policy still the template as written), validate_config 5 (an unknown key's way out, with a close match; the
# unread_allowed globs), UNFILLED 4 with its two-line note, unfilled 4 with its two blank lines, the three imports 3
# and KEYS 1. sharing_scan.py 188 more (350 now): main 42 more (79: --message, the range read from the revisions
# it names with its commit messages, the index and HEAD for staged scans, the configuration gate before a whole-file
# scan, links listed, the phrases a change takes out named), rules 27 (the stricter of the contract under review and
# the one before it: both phrase lists and bundles, only the exemptions both grant; read_contract's 17 gone), hits 23
# (a phrase in a judged line or wrapped onto it, forms made only for the lines judged), judge 22 (a file's new name,
# its lines, the contract's values, or a hold for a file that is not text), walked 20 (links never followed, .git
# passed over; whole's 14 gone), changed 14 (each file a change adds or alters, read as it now is, with --text; added's
# 19 gone), values 13 (the contract's keys and strings, the phrase list left out), ready 10 (a named policy there
# and filled in), canon 9 (NFKC, no format characters, one apostrophe and hyphen, separators and CamelCase read as
# words), text_of 8 (UTF-8, or UTF-16 with its mark), tracked 8 (a bundle git tracks files under), contract_at 7,
# matchers 6 (matcher's 5 gone), message 5, blob 4, the constants 6, the docstring 3 more, three imports 3,
# unjudged 2 fewer, count's 2 gone, and 18 more blank and comment lines between them. The core's 1, install.py:
# STABLE_SKILL_SCRIPTS carries synthesis-kb-edit, so the hooks the standard prints find the scan in the stable runtime.
# 5.22.0's review, round 1 (2026-11-14): plugin 191 more, the core as it was (findings R1-3, R1-20, R1-21 and R1-22, the
# collections). build_collections.py 173: verify 37 (a script that cannot start in its collection unless named, an import
# inside a function with nothing to catch its absence, a stale name, a carried module that imports the rest of the
# runtime, a carried file missing, out of place or changed, a path into another collection's skill unless named, and a
# link left leading out of the folder), runtime_imports 21 (the runtime modules a file imports as it starts and inside a
# function, read from its syntax), needs 12 (through the modules beside it), impure 11, relink 10 (a link that would
# leave the folder pointed at the file at the tag), reaches 9 (a path into another skill's folder in a string of the
# code), leaving 8, guards 6, build 5 (the carried runtime files and the links), docstrings 5, imported 5, sources 4 (the
# runtime's files and every tracked path), ancestors 3, carry 3, catches 3, the constants CARRIABLE, CAUGHT, PRESENT and
# LINK 4, the imports of ast and posixpath 2, and spacing and a comment line 25. release.py 8: collections_head 8 (the
# commit takes the release commit's identity and time, unsigned, names it, and is made once for each head).
# context_doctor.py 6: repo_state 3 and cited_entries 3 (without the runtime's claims log or session archive, each says
# what it cannot tell). local_messaging.py 4: _close 4 (without the runtime's approvals nothing is closed, in one line).
# 5.22.1 (2026-11-14): core 209 more and plugin 209, after a review wrote the principal's prompt into a transcript and
# the grant into the state with one line of Perl's File::Copy, which the guard's list of writing calls did not know, and
# opened a send window from a faked terminal. guards.py 210: the section's comment 7 and its constants 8 (UNREAD 2, the
# interpreters the guard does not read; EDITORS 1; AWK_SAFE 1, the awk options that write nothing; CANDIDATE 1, a path
# in code; SPELLINGS 1, each folder's spellings compiled once; 2 blank lines), Unproven 5, _code_of 11 (a script file's
# text, never a program's bytes), _sed_scripts 18 (each -e, else the first operand; none read from -f), _sed_writes 26
# (w, W, e and an s flag that writes or runs, past addresses, the parts of s and y, text, labels and file names),
# _unread 35 (which programs run text the guard cannot read, and the script file each runs: Python left to its reader,
# synthesis's own module and json.tool given one file passed, a shell's script on the line passed, awk and sed by their
# options and scripts, an interpreter, an editor, a program run by its path), PROOF_LIMIT 3 and _proven 11 (a Python script file of 16 KB or less, proven by the reader and never
# refused on that reading), _spells 48 (a folder named in any spelling: its path in any case, its path below the home
# folder however joined, a variable that holds it, a folder above it or a place inside it, a path through `..` or a
# link, a folder above it handed whole), check_self_grant 20 more (every reading's refusal first, then the hold: the
# code filed and spent for exactly that command and folder, or the reason as a refusal for a command a Python program
# starts), _self_grant 9 (the files the line writes 2, the program, its script and what it names, standing in the state,
# the board or the archive included, 4, a script file that makes a grant or opens a window 1, the hold's reason 2),
# BUILT_CALLS 2 and its check in _python_writes 4 (a call reached by a name the program builds, through a module's own
# table or `__dict__`, handed on, or into C; an object's own `__dict__` is read as before), and check_outgoing 3
# (every window request in a line collected 1, a code asked for each that waits 2). cli.py 1 fewer: the own-terminal
# shortcut's condition is gone and its comment says why in as many lines.
# 5.22.1's review, round 2 (2026-11-14): core 20 more and plugin 21. guards.py 21: a git read a Python program spells
# whole is a read wherever it is pointed 5 (its words, git's own options and the value -C takes 2, the read subcommand
# with no option that writes or runs 2, the pass 1); EXTRACTS 3, the archive tools and the word that says each unpacks;
# _spellings 6 (the spellings and the folders above each protected one, kept apart from _spells so the handed-path
# rule reads the same folders: its signature and docstring 3, the return 1, 2 blank lines); an archive tool unpacking
# where it stands in such a folder or a protected one 3; a folder above a protected one handed to a program the guard
# does not know 4. sessions.py 1 fewer: the lost-transcript gate's own-terminal shortcut is gone, its docstring
# rewritten in as many lines. provenance_scan.py 1: its git helper's five lines become five that spell each read whole,
# and the docstring gains a line saying why.
# Review round 1 of 5.22.1 (2026-11-14): core 210 more and plugin 210, for its nineteen findings and the coordinator's
# rulings (a command that names a protected folder passes only when its program is a known reader; brace lists and
# every redirect form; programs judged by their text, failing closed; Python isolated from the agent's modules; the hold
# on time and bound to the scripts it runs). guards.py 203, each with the blank lines after it: _braces 26 (brace lists
# as bash and zsh expand them, nested, with sequences, under a cap), _sed_writes 25 more (a sed program read with
# certainty: bracket expressions as BSD sed reads them, any command or flag it does not know taken to write), _regular
# 21 (a regular file read without waiting, bounded), _shipped 18 (the installed plugin's own scripts: the guard's
# folder, the synthesis home, or a harness's plugin folder whose guard is this one byte for byte), _awk_reads 17 (an awk
# program with no redirect, pipe or system), _proven 13 more (each script proved once a call under a cap and the call's
# deadline, and no planted module beside it), _git_reads 13 (git's read subcommands without options that write or run),
# _python_writes 10 more (a writer handed on rather than called, sys.modules, a started command's wait carried, a
# refusal preferred), _unread 8 more (every program not known to only read is named; open runs what it opens), _self_grant
# 8 more (each command's words judged for what they name, a script file outside the plugin using synthesis's code, a
# line it cannot read), _piped 8 (what cat pipes into a shell, and what another program pipes, which waits), _isolated 6,
# _commands 5 more (a file on a program's input read as its script; what printed into a shell), check_self_grant 3 more
# (its deadline, its caches, the scripts the code binds), _lex 3 and _bare 3 more (quoted braces kept whole; env -S read
# as env's own words), SYNTHESIS_IMPORT 3, _simple 2, _code_of 2, READER_WRITES 2, check 1, _spells 1, _spellings 1, and
# one line each for _CALL, UNREAD_INPUT, SHIELD, OUTPUTS, GIT_RUNS, GIT_FIRST, ABSOLUTE and the operator list, less
# _script_file's 4 (it opens its file through _regular). approvals.py 6: transcript reads the path the prompt hook recorded
# (and only one that is there), remember records it. hook.py 1: the prompt hook records it.
# The coordinator's ruling on the plugin's own scripts (2026-11-14): core 3 more and plugin 3. guards.py 3: _shipped 1
# more (only the release the guard runs from, or a script and the modules beside it that it imports byte for byte that
# release's copy, in place of the synthesis home and a plugin cache's guard match), _protected_roots 1 (the runtime's
# releases, current and bin), and a script file outside the release that imports synthesis's code waits apart from the
# approval-call refusal 1.
# What the 30-day replay of recorded commands showed the round-1 code misread (2026-11-14): core 5 more and plugin 5.
# guards.py 5: _lex 5 (arithmetic, whose own substitutions alone run, and an array's values, kept in its word; the
# substitution branch and the `$` branch step past `$((` in place); _dquote's arithmetic, the empty word no longer read
# as a reader's writing option and the import check for synthesis's code each change one line in place.
# The coordinator's ruling on Python without -I (2026-11-14): core 18 more and plugin 18. guards.py 18: _stand_in 11 with
# its two blank lines (a module a program imports or runs with -m that a file where it starts could stand in for),
# PYTHON_ENV 3 with its blank line (the variables that move Python's module path, set on the line), _unread 1 (the -m
# exemptions under the same rule), and _self_grant 3 (why only isolation is missing, and a hold that says -I or a clean
# folder needs no code). And 1 more to both: the refusal of a program that imports synthesis's code and that its reader
# cannot follow says that, not that it runs the approval code (its words take a second line).
# The coordinator's ruling on Python script files (2026-11-14, after the 30-day replay held about 3,700 such runs a month
# for want of a full proof): core 138 more and plugin 138. guards.py 138: _python_files 47 (the script and each module
# of its own it imports, read whole: a file or package in the folder Python looks in first named like no module found
# elsewhere, or one a package names relative to itself, and theirs in turn, with the packages that hold a module run
# with -m; a file there named like a module found elsewhere stands in; past TEXT_LIMIT, OWN_MODULES or the call's time
# it waits), _shows 30 in place of _proven's 22 (judged by what the text shows: no write or run the reader recognizes,
# or each placed outside the protected folders, a module of its own by any write it holds; once a call, under the
# cap), _imports 18 (each import a program's syntax holds), _module_file 16 (the file `python -m` runs when the folder
# it starts from holds it; one found elsewhere keeps the full rule), _found_elsewhere 9, _python_writes 15 (a member
# read inside its own reading, where the reader recursed without end, leaves the writes it reaches unplaced and no
# member followed after it, a file argparse opens to write is a write, and the call's deadline it stops at), _self_grant 10 (each script read with its
# own modules, the import check for synthesis's code over all of them, the text check in place of the proof), _unread 2
# (a module run with -m from the folder that holds it), the block's comment and blank lines 13, and TEXT_LIMIT with
# OWN_MODULES 1 in place of PROOF_LIMIT 1; df on the readers' list, _code_of reading to TEXT_LIMIT and the call's
# module cache change lines in place.
# The coordinator's ruling on programs that use synthesis's own code (2026-11-14: waiting on every import stopped every
# probe, review script and skill script outside the runtime that reads through it): core 119 more and plugin 119.
# guards.py 119: _synthesis_reach 78 (what a program does with synthesis's code: names one of its writers under any
# name it is imported by, reaches it in a way the reader cannot follow, or reaches a protected folder through its own
# paths, each such call spelled out as the folder it returns), _synthesis_own 14 (whether a module makes a name itself
# or only imports it), SYNTHESIS_WRITES 13 (synthesis's writers, which a test reads from the source), _self_grant 5 (the
# check over a script and its own modules and over Python on the line, and where its paths lead counted as named),
# SYNTHESIS_PLACES 2, _shows 2 (a program read with its paths spelled out, and a write where they lead unspelled taken
# to land there), SYNTHESIS_DEFS 1 and 4 blank lines.
# What the replay of that rule showed it misread (2026-11-14): core 17 more and plugin 17. guards.py 17:
# _synthesis_reach 10 (a module printed or shown as text is no module handed on; a call inside an f-string, or one
# whose place cannot be read with certainty or whose spelled-out text does not parse, is not spelled out), _ancestors 7
# with its 2 blank lines (the nodes that hold a node), less _synthesis_own's 2 (only a name a module imports leads
# elsewhere, so a value it makes by a tuple, a dunder or a name it no longer has does not).
# 5.23.0, the Messenger surface and a chat saved from its page (2026-11-14): plugin 602 more, the core as it was.
# messenger_messages.py 274 (synthesis-daily-rituals): parse 56 (rows to chats, the owed and nudged ones, unread marks
# and the coverage line; a wall, another inbox's grid, an empty list without --empty and --end off the list's bottom
# refused), main 50 (plan, extractor and parse, and the text report), the docstring and imports 41, entry 32 (one row's
# lines; its age dated the latest it allows, its words checked against it), the extractor 27 (the named grid's rows,
# the address, dialogs and whether the list is at its bottom, as JSON; it only reads), plan 26 (the declaration, each
# inbox's way in and its day from the watermark), loaded 12, address 6, stop 5 and the constants 19, each with the
# blank lines after it. chat_page.py 273 (synthesis-message-exports): read_chat 54 (walls, the chat's address, name
# and zone, each message from its two labels; notices, messages without text and labels that disagree counted, not
# written), place 42 (the transcript holding the chat's page reads, else its messages with the same people, else
# --into, else a new name), the docstring and imports 37, save 36 (pairing with an export's blocks, the write and the
# coverage line), main 24, instant 18 (the minute in UTC, the hour the clocks went back, a time never shown), the
# extractor 17, loaded 13, label_of 9, people 6, Refused 4 and the patterns 13. import_messages.py 54: page_blocks,
# sender_of, pairs and read_from_page 37 (a block read from the page pairs with a message of its digest inside its
# minute, and draws a conversation only with the same people), plan 9 (both downloads find a transcript holding their
# page-read messages, each such message counts as present, and its docstring 2), the page mark and the minute 5, and
# message_block 3 (the page line). sync_watermark.py 1: messenger joins the stores that move only with their reader's
# coverage, and its help line wraps.
# 5.23.0, after the Messenger extractors' first live reads (2026-11-14): plugin 9 more. messenger_messages.py 1: the
# extractor looks for the list's scroll containers from its first row up, inside the grid or around it, and says the
# list is at its end only when it finds one and each is at its end. chat_page.py 8: read_chat 6 (the encryption notice,
# known by its sender and words before any time is read, and a label dated before 2004-02-04 held for a person),
# EARLIEST 1 and the held count in the coverage line 1.
# 5.23.0, review round 1 of the Messenger surface (2026-11-14, 21 findings): plugin 221 more, the core 3 of them.
# guards.py 3: MOVES 1 (a location assignment, assign, replace or window.open held on a messaging site), SCRIPT_ACTS 1
# (now on two lines to take it) and its comment 1. messenger_messages.py 66: read_time 22 (the read's own clock and zone,
# --read-at held to within five minutes of it), parse 21 (the --since moment, the reach from the last row in the list's
# order, rows above newer ones, pop-ups, the empty-list words, dialogs by their heading, no watermark without --since),
# the docstring and imports 10, shown 5 (names and previews on one line, separators shown), the extractor 4 (its clock,
# zone, pop-ups and dialog headings), entry 2 (`You` only in the page's forms, each row's span), CLOCK_SLACK 1, UNTRUSTED
# 1 and plan 1 (each inbox's own watermark), less main 1. linkedin_messages.py 17: reach_of 7 (an entry's latest moment),
# parse 7 (moments, and no watermark without --since), the docstring and import 4 and plan 1, less main 2.
# sync_watermark.py 18: since_moment 15 (the first moment a --since names; a day that is no day refused) and _store_reach
# 3 (a coverage moves only the inbox it names). chat_page.py 42: read_chat 13 (the labeled notice only, held items, reads
# joined only where they share two messages, twins), save 12 (pairing with what is held, the day reached only from before
# it, the held and passed-over lines), label_of 6 (the sender by the name the log gives), the docstring 5, HELD 5, paged
# 5, place 4 (evidence about the chat) and the extractor 2, less people 6, EARLIEST 2, LABELS 1 and FIELDS 1.
# import_messages.py 75: block_text 16, transcript_text 13, loose 11, page_holds 11 (evidence about the chat), plan 7 (a
# conversation split with a page read imported, partial pairs held, a page read's header kept), mine 6, text_digest 6,
# exact_blocks 6, main 5 (the held and split lines), holders 5, near 4 and page_blocks 2, less read_from_page 9 and
# read_transcript 8.
# Spelling across words (the coordinator, 2026-11-15: a skill script's path in the plugin cache and a project page's
# path were read together as naming the transcripts): core 43 more and plugin 43. guards.py 43: _statements 18 (a
# program's text cut into its statements, outside quotes and brackets, comments left out), _joined 18 (the parts one
# statement spells: from its code and pieces of a path, with at most one path written whole, and such a path alone
# only where they stand one after another), LITERAL 1, 6 blank lines; _spells judging each text and each word apart
# and expanding a word's variables, and the naming line handing it each word apart, change lines in place.
# 5.23.0, round 3 of the batch review, finding 8, and that fix's own review round 1 (2026-11-15: words typed into a
# Messenger box with the browser tool, then Return pressed through osascript, and the Playwright plugin's browser tools,
# sent with no code; the review found 15 more ways through and 16 false holds): core 611 more and plugin 611. guards.py
# 609. Keys, clicks and other apps from the shell, 409: _acts_outside 77 (a command read through the scripts, programs,
# runners, task recipes and shell files it runs, a program the shell names, a file the line writes), _osa_code 73 (an
# AppleScript or JavaScript script with comments and strings out: a member a string names written as it runs, a
# template's code kept, a pattern passed over, `¬` and `|name|` read, a string never closed found), _program_acts 54 (an
# input library or module it uses, or a command it starts, from its calls, command spans and strings, an AppleScript kept
# in a variable of a program that runs osascript), _osa_judge 36 (the apps a script names and the verbs it uses, System
# Events by its UI verbs, words the shell fills in), _osa_source 25 (its -e lines, its file with $HOME filled in, its
# input, or the line's heredocs), _recipe 17 (a make target's recipe or a package script), _acts_in_line 18 (every
# reading of the line's variables, the line as its caller parsed it, a line the parser cannot read), osa_send 8,
# _code_only 5, _app_name 4, _unquoted 4, _home 2, the tables and patterns 51 (ACTORS, INPUT_PROGRAMS, INPUT_WORDS,
# HS_ACTS, the three descriptions, UI_SCRIPTING, ACTING_APPS, SENDING_APPS, OSA_KEYS, SE_VERBS, OSA_OTHER, OSA_UNREAD,
# OSA_CALLED, OBJC_SAFE, AUTOMATION_URL, TERMINALS, INPUT_LIBS, INPUT_MODULES, IMPORTED, SPAWNS, QUOTED_RUN, CALLED_WITH,
# LOOKS_OSA, PROGRAM_STRINGS), the comment 9 and 26 blank lines. Browser tools from any server, 173: _driven_steps 39
# (a tool's steps as a browser batch reads them, on its page: a click by the control the current page's snapshot names for
# its target or ref with the agent's words, a line-break key, a dialog, dropped text, an unknown tool as a step that may
# send), _line_events 25 (a call or a result from a Claude Code record or a Codex rollout), driven_tool 16 (Playwright's
# names, any other server's by its words), check_driven 14 (run_code from a file or starting a command, the code bound to
# the call), _driver_events 13, _driver_page 13 (the page its results or its own last navigate show), _driver_ref 9,
# _caller 6, DRIVERS, DRIVEN, READ_WORDS, UNKNOWN_PAGE, PAGE_LINE and PAGE_MARKS 13, the comment 7 and 18 blank lines.
# Elsewhere 27: check_outgoing 9 (the line's keys and apps, and a hold that says what they do), _bare 7 (`script` and
# `launchctl asuser` run the command they are given), _program 5 (node's --eval and -p, perl's -E, php's -r, deno eval
# and run), the dispatch 4 (a driven tool is read before the connectors), DRIVES and PRESSES_ENTER 3 (a browser server's
# own code acts through its page and keyboard), _web_app 2 (a page nothing shows), less _browser_call 3 (its search moved
# to _caller). sends.py 2: command_send reads an osascript by the guard's reading of its script, across its lines, in
# place of the one-line pattern. A reuse of the reader of a Python program's writes to spell the commands it starts was
# tried and dropped: over two days of records it took 168 ms a program on average and 4 s at worst.
# 5.23.1: core and plugin each 10 more, all in guards.py: _real 7 (where a path leads, asked once a call: the recorded
# heredoc shape asked 11,746 times over 102 paths and took 1.11 s on CI's macOS runner under Apple's Python 3.9, 0.31 s
# on this Mac; with it, 123 times and 0.105 s) and its 3 blank lines. The per-call reset and the 29 places that ask
# change in place.
# Then core and plugin each 64 more, all in approvals.py, so a grant is read before it is spent and finding the
# principal's prompt reads only the approval window (a Codex record of 1.9 GB took 4.6 s to read from its start, past the
# hook's 4 s, after the grants had been deleted): _lines_back 16 (a record's lines from its end), _spend 13 (a grant taken
# once, the bytes it held returned), _stamps 10 (every time a line carries), typed 9 more (read from the end; a run of
# lines older than the window ends it), consume 6 more (read, check, then spend; a grant changed during the check is
# never used), STAMP and the run's two constants 2, and the new functions' 8 blank lines.
# Then each 46 more, from that fix's review round 1 (a compaction block of older lines after the prompt ended the search
# before it; a long line was read in time proportional to its length squared; a deadline later in the same call lost a
# grant spent earlier): approvals.py 42 (give_back 13 and SPENT 1, with 4 blank lines: a call that is held gives back the
# grants it used; _lines_back 9 more, a long line kept as its pieces and read back only to a position; grant_from_prompt
# 5 more, the record's size when he typed; typed 3 more, read back to that position; consume 3 more, what it used noted;
# _stamps 2 more, a number read by its length; MARGIN 1; backed 1 more), hook.py 4 (pre_tool_use: the list cleared, and
# the grants given back when the call is held).
# Then each 101 more, from that fix's review round 2 (a deploy, a send, a send window's count and a voided grant stayed
# recorded when a later check of the same call held it, so the retry was refused; a grant given back could be found half
# written; a prompt line longer than the margin was cut): the hook is now the boundary, writing a call's records only
# when it lets the call through. guards.py 45: settle 10 (each record written if the call is let through, undone in
# reverse if it is held, the grants kept spent or given back), _after 4 and _void 4 (a record queued; a grant voided at
# once and put back if the call is held), EFFECTS and UNDER_HOOK 2, with 8 blank lines; check 15 more (its body moved to
# _check, the records settled here for a direct caller, also when the check raises); _record_deploys 6 with 2 blank lines
# (the deploy brake's record, written at settle), less check_deploy 3 and check_outgoing 3 (their records queued in
# place). approvals.py 33: put_back 21 with 2 blank lines (a grant written beside its place and linked in, so it appears
# whole or not at all; a write that takes only part), less give_back 7 (it calls put_back); void 7 more (it returns what
# it removed); _lines_back 10 more (the line holding the read's first byte read whole). sends.py 17: undo 8 with 2 blank
# lines (a window's send counted at once and undone if its call is held), log 4 more (an id per send, its mark
# returned), ledger 3 more (an undone send left out). hook.py 6: BEGAN 1 with its blank line (the deadline counts from
# the process's start), pre_tool_use 4 more (the guard's records settled when it answers; an answer later than a harness
# waits keeps them).
# Then each 49 more, from review round 3 (a sender that runs check_send itself left no record of an approved send; a
# record that could not be written ended the hook with no answer, so Claude Code ran a held call; two window sends counted
# at once lost a planned send when the second was held; an agent's program could call the guard's new writers):
# guards.py 30: _entry 23 with 2 blank lines (the first check a caller enters starts the call's records and settles them
# unless the hook answers; check, check_send, check_deploy, check_desktop, check_driven and check_outgoing are entries,
# their 6 decorator lines), _DEPTH 1, settle 6 more (each record its own, the first failure raised after the rest),
# check_desktop 1 more (the window decision under the send lock), the guard's writers in SYNTHESIS_WRITES 1, less check
# 10 (its wrapper is _entry). sends.py 16: _note 7 and _rows 3, with 4 blank lines (a line about a send, "undone" or
# "settled"; a day's lines), settle 4 more and spent 3 more (the window closes once its last planned send has gone, so
# one still being judged keeps it open), less undo 4 and ledger 1. hook.py 3: pre_tool_use 3 more (a record that cannot
# be written holds the call, and the answer still goes out).
# Then each 51 more, from review round 4 (two threads would share a call's records; an interrupt left the hook's flag
# on; a call held because its record failed kept its grants spent and the records before it; the send lock taken inside
# itself waited for ever): guards.py 34: _record_deploys 10 more (the deploy record put back as it was if a later record
# fails), _logged 6 with 2 blank lines (a send's line, undone the same way), _entry 8 more (one thread judges at a time;
# the first entered puts the depth back however it ends), _JUDGING 1 and `import _thread` 1, settle 6 more (a call whose
# record fails is held: every record undone and its grants given back). approvals.py 15: alone 12 more (taken again
# inside itself in one process, it does not lock again), _ALONE 1 with 2 blank lines. hook.py 2: pre_tool_use 2 more
# (the hook's flag put back however the check ended).
# Then each 37 more, from review round 5 and CI on b458c09f (refusing a second thread broke two identical calls at once,
# which the send lock serializes; the hook settled another thread's records; the send lock's count was the process's; an
# interrupt just after the guard was taken left it taken; putting back a deploy record erased another call's; an alarm
# as the deadline was taken down escaped the hook with no answer): guards.py 32: answered 7 and hook_answers 3, with 4
# blank lines (the hook settles only the call its own check judged, in the thread it answers for), _PENDING 1, _swap 6
# with 2 blank lines (a file replaced whole), _entry 4 more (a second thread waits its turn; the lock taken and freed
# inside the try; the hook's call's records kept for its answer), settle 4 more (the records given, or the current
# check's), _record_deploys 1 more (a deploy recorded meanwhile stays). hook.py 10: pre_tool_use 3 more (an alarm as the
# deadline is taken down still holds; an interrupt settles as held), _answer 5 with 2 blank lines. approvals.py 5 fewer:
# alone 2 more (the thread that holds the lock) and `import _thread` 1, less give_back 6 and its 2 blank lines (settle
# puts back the grants it is given).
# Then each 21 more, all in guards.py, from review round 6 (a commit that entered the guard while it settled waited for
# ever; the alarm in a check's own finally left the hook's call unsettled; a thread inside the send lock entering a check
# could wait on a thread waiting for the lock): answered 9 more (a check cut short in its own finally: what it left is
# settled and the guard freed), _entry 8 more (no entry while this thread settles or holds the send lock; the hook's
# call marked as entered; the depth and the lock put back last), hook_answers 3 more (records an unanswered call left
# stand), _SETTLING 1.
# Then each 5 more, all in guards.py: answered 5 more, from review round 7 (an interrupt after the check handed its
# records over and before it freed the guard left the lock taken): the guard freed whichever records the check left, and
# no check entered while the answer settles them.
# 5.23.1, round 4 of the batch approval's review, findings 1 (its plain form) and 3, both on 5.23.0 (2026-11-15: the
# navigate tool alone was never judged and a `javascript:` address was read as written; on a messaging site's page a
# script clicked Send by a name built as it ran): core 101 more and plugin 101, all in guards.py: _refused_scripts 20 (on a
# messaging site's page, or a page a driven browser's record does not show, only the shipped readers' scripts run; a
# javascript: address is such a script), _tabs 20 (each browser's own newest list: the pane's `tab-N` ids, its own
# tabs_context and its navigate's result), _read_only_scripts 17 (the extractors as their commands print them, read from
# the release), _script_address 6 and _url_read 5 (an address as a URL parser reads it, and the code a javascript: one
# runs), _browser_item 4 (a javascript: navigate is a script step), check_desktop 3, _steps 2 (a navigate read as a
# parser reads it; a javascript: one runs on the page it is on), _driven_steps 2 (a driven browser's javascript:
# navigate), _puts 1, BROWSER_STEPS 1 (the navigate tool), desktop_tool 1, PAGE_READERS 1, the comments 8 (the rule and
# the 60 days it was decided by; the pane's ids) and 10 blank lines.
# The coordinator's ruling on round 4's measurement (2026-11-15): on a messaging site's page a script the guard cannot
# read is refused, one that acts waits, a read passes, in place of refusing every script but the plugin's own: core 30
# more and plugin 30, all in guards.py. _unread_script 7 (a call by a name built as it runs, code in a string the page
# runs, text never closed), _script_acts 5 (the acts rule over the code too, and its new spellings), _refused_scripts 2
# (a javascript: address refused there whatever it runs), UNREAD_SCRIPT 2, SCRIPT_ACTS_MORE 2, PAGE_CODE 1, the comment
# 5 and 6 blank lines.
# Review round 1 of that rule (2026-11-15): core 60 more and plugin 60, all in guards.py. _writes_by_fetch 15 (a fetch,
# Request or XHR writes unless its method is a literal GET or HEAD, in any spelling), _unread_script 8 (the form named in
# fixed words; code only where it reaches a sink), _script_code 7 (an optional call read as a call, X.call( as a call of
# a dotted X), _record 6 (a sub-agent's own record), UNREAD_FORMS 4, _script_acts 4 (PAGE_ACTS for a page's script; a
# GET by XHR reads), CODE_SINKS 3, SCRIPT_ACTS_MORE 3 (optional, bare and destructured calls; other parts of the
# address), _steps 3 (a page no list shows is unknown; the pane's first page), PAGE_ACTS 2, _driver_events 2 (a call a
# hook refused left out), _refused_scripts 1, HANDLERS 1, SERVER_CODE 1, _osa_code 1 (`/` after `++` or `--` divides),
# _driver_page 1 (a javascript: navigate is no page), _driven_steps 1 and 6 blank lines; less PAGE_CODE 1,
# UNREAD_SCRIPT 2 and 6 lines of comment.
# Review round 2 of that rule (2026-11-15): core 69 more and plugin 69, all in guards.py. _writes_by_fetch 37 (method
# and body read in the init of fetch or Request alone, or in the object a variable given there holds and what is set
# on it; an init the reader cannot follow is a write), _tabs 9 (preview_start's answer places the pane; one that names
# no address changes no page), check_desktop 9 (a call that sends only if a page no result shows is a messaging site's
# is told to read the page first, with no code asked, in a browser whose reads show its page), _defined_names 8 (a name
# the script defines is no page's send), SHOWS_PAGE 1, BARE_SENDS 1, _script_code 1 (`[].x.call(` is a call of x),
# _script_acts 1 and 2 blank lines.
# Review round 3 of that rule (2026-11-15): core 83 more and plugin 83, all in guards.py. _shared_tabs 26 (Claude in
# Chrome's tab at the newest list that names it across the session's record and its sub-agents'), _writes_by_fetch 14
# (an init the reader cannot follow is read by a method or a body anywhere in the script, so a read through a fetch
# wrapper passes; keyed by a name built as it runs, it waits), _listed 12 (each record's newest list, read once per
# version of the file), _when 6 (a list's line's time), _script_acts 6 (a call by a method the script defines, on `this`
# or an object it defines, is no page's send), _defined_names 4 (an object's or a class's method, a property or a field
# given a function), MEMBER_SENDS 2, _tab_list 8 less _tabs 6 (the list's time, split as on the batch), _LISTS 1 and 10
# blank lines.
# Review round 4 of that rule (2026-11-15): core 22 more and plugin 22, all in guards.py. _bracketed 8 (a balanced group,
# for the init reader and the IIFE rule), _writes_by_fetch 5 (U1: an init not followed is read by a method or a body in
# what the script passes to a call, not in what a callback returns or names), _shared_tabs 4 (a sub-agent record whose
# last 8 MB name no tab list is not parsed: a busy session's 70 records), _script_acts 3 (U4: the object an IIFE of the
# script's own returns) and 2 blank lines.
# Merged with main's 5.23.1 (2026-11-15): main's ceilings above, plus this branch's notes since: core 101, 30, 60,
# 69, 83 and 22 more, plugin the same (the path note's 10 was main's already).
# Review round 5 of the page rule (2026-11-15): core and plugin 5 more, all in guards.py: _writes_by_fetch 5 (W4: an init
# the reader cannot follow is read by a method named anywhere in the script again, as before round 4).
# Review round 6 of the page rule (2026-11-15): core and plugin 5 more, all in guards.py: _writes_by_fetch 5 (a method
# read only as an object key, a shorthand by its const's one literal, or a member assignment: a parameter or a property
# read named method held a read through a wrapper).
# Code may grow past these only with an itemized reason here (Rajiv, 2026-10-20: raise the ceiling, itemized, rather
# than consolidate first).
CORE_BUDGET = 17256
PLUGIN_BUDGET = 43328


def _lines(files):
    return sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)


def test_core_stays_within_its_budget():
    assert _lines((ROOT / "synthesis").glob("*.py")) <= CORE_BUDGET


def test_whole_plugin_stays_within_its_budget():
    code = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts and not p.name.startswith("test_")]
    assert _lines(code) <= PLUGIN_BUDGET


# What the modules a pre-tool-use call for a shell command loads import as they load, by the module that asks.
HOOK_NEEDS = ("json", "os", "re", "signal", "sys", "time",                        # hook.py (signal: its deadline)
              "__future__", "_thread", "datetime", "fnmatch", "itertools", "math", "shlex",  # guards.py (_thread: loaded at start)
              "hashlib", "pathlib", "unicodedata",                                # approvals.py and paths.py
              "base64", "contextlib", "dataclasses",                              # board.py
              "urllib.parse")                                                     # sends.py


def test_bash_guard_hook_is_fast(compiled_runtime, tmp_path, hook_budget):
    """What a session pays on every shell command: a new process that runs the installed runtime, compiled as the
    installer leaves it. On the principal's Mac the modules named above load in 27 ms, so twice that is 54 ms,
    beside the 50 ms the doctor's self-test holds there. The hook took 1.3 times when this was written (35 ms), and
    2.7 times with its own code compiled on every call (73 ms: the fault 5.8.1 fixed, which a fixed 150 ms had let
    pass)."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la && git status"}})
    hook_budget([str(compiled_runtime / "synthesis" / "hook.py"), "pre-tool-use"], HOOK_NEEDS,
                input=payload, cwd=str(tmp_path))


def test_the_hook_budget_fails_an_unnamed_import_a_name_nothing_imports_and_a_slow_call(compiled_runtime, tmp_path, hook_budget):
    """The budget is a test's only word on a hook's cost, so each way it can refuse is shown to refuse."""
    hook = [str(compiled_runtime / "synthesis" / "hook.py"), "pre-tool-use"]
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    with pytest.raises(AssertionError, match=r"synthesis\.sends imports urllib\.parse while the call runs: every call pays for it"):
        hook_budget(hook, tuple(name for name in HOOK_NEEDS if name != "urllib.parse"), input=payload, cwd=str(tmp_path))
    with pytest.raises(AssertionError, match="asyncio is named as a need and nothing of the call's own imports it"):
        hook_budget(hook, HOOK_NEEDS + ("asyncio",), input=payload, cwd=str(tmp_path))
    inside = "import time\n\ndef later():\n    import shlex\n\nlater()"  # inside a function, and the function runs
    with pytest.raises(AssertionError, match="the caller imports shlex while the call runs"):
        hook_budget(["-c", inside], ("time",))
    slow = "import time\nif not time:\n    import asyncio\ntime.sleep(0.25)"  # an import that never runs is no need
    with pytest.raises(AssertionError, match=r"the call took \d+ ms; its standard-library modules alone load in \d+ ms here"):
        hook_budget(["-c", slow], ("time",), rounds=3)


def test_a_call_that_met_a_busy_machine_is_timed_again_before_it_is_called_slow(tmp_path, hook_budget):
    """2026-11-13: on a shared runner whose whole job ran at half its usual speed, the guard hook's fastest of fifteen
    runs read 92 ms beside 45 for its modules, and the release waited on a hook that had not changed. Other work on
    a machine stretches the longer run more, so one block of rounds can leave the call without a single quiet run.
    A call over its allowance is timed for more rounds, all of them counted, before it is called slow; one that is
    slow in every round still fails (the test above)."""
    runs = tmp_path / "runs"
    runs.mkdir()
    busy = ("import os, time\n"
            f"n = len(os.listdir({str(runs)!r}))\n"
            f"os.mkdir(os.path.join({str(runs)!r}, str(n)))\n"  # a folder for each run: opening a file loads a module more on 3.9
            "time.sleep(0.3 if n <= 3 else 0)")  # the first look at it and its first three rounds meet a busy machine
    hook_budget(["-c", busy], ("os", "time"), rounds=3)
    assert len(list(runs.iterdir())) == 7  # one look, three rounds over, three more that settle it


def test_the_hook_budget_fails_a_runtime_that_is_not_compiled(compiled_runtime, tmp_path, hook_budget, monkeypatch):
    """What 5.8.1 fixed is what the budget has to catch, on any machine: it looks at the runtime, since by time alone
    an uncompiled one passed where starting a process costs more than compiling does. A process that may write
    bytecode compiles the runtime at its first call, which is how CI runs the suite; a session's hooks are told to
    write none, so the budget's own runs are told the same and leave the runtime as they found it (both found by a
    review before 5.8.1 was released)."""
    from importlib.util import cache_from_source
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)  # as CI runs the suite
    compiled = [Path(cache_from_source(str(source))) for source in (compiled_runtime / "synthesis").glob("*.py")]
    for file in compiled:
        file.unlink()
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la && git status"}})
    with pytest.raises(AssertionError, match="the runtime is not compiled for this interpreter, so every call compiles it"):
        hook_budget([str(compiled_runtime / "synthesis" / "hook.py"), "pre-tool-use"], HOOK_NEEDS,
                    input=payload, cwd=str(tmp_path))
    assert not [file for file in compiled if file.exists()]  # and the budget's own run of the call wrote none

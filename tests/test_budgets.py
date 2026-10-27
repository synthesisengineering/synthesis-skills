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
# Code may grow past these only with an itemized reason here (Rajiv, 2026-10-20: raise the ceiling, itemized, rather
# consolidate first).
CORE_BUDGET = 6631
PLUGIN_BUDGET = 23520


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

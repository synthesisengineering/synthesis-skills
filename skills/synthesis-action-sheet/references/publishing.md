# Action sheet: handing it over

The chat contract, how each harness puts the page in front of the principal, an optional shared
private host, and why the codes line can go stale. Read it when handing a sheet over.

Contents:
- The core: one filed file
- The chat contract: three lines
- Codes expire
- Adapters by harness: Claude Code, Codex, Muse and others
- An optional shared private host (not implemented)

## The core: one filed file

The sheet is one self-contained HTML file with no build step, dependency, server or network
call, filed in the owning project's `resources/artifacts/` by `build_sheet.py --file-into`. Any
harness can build it and open it; every agent on the project can read it, and the next session
finds it after this one is gone. Publishing is an adapter on top of that file. No harness
feature is the foundation: the paste-back works in every harness, so the loop closes even where
nothing else does.

## The chat contract: three lines

After a packet's rulings are carried out, or whenever a sheet is handed over, the chat reply is
exactly three lines (binding rule 3):

```text
Done for you: 7 (3 emails sent, 2 calendar holds, 2 records filed), folded at the top of the sheet.
Your sheet: <the published link, or the filed page's absolute path>
approve <code> approve <code>
```

- Line 1 counts what was done, by kind, and points to where the list lives. No items in chat.
- Line 2 is the page to open: the published URL where there is one, else the filed page's path.
- Line 3 is every staged send's code, on one copyable line, in the order of the Approve section.
  The principal types or pastes that line as their own message; the prompt hook grants every
  pending code a prompt carries, and the guard then lets each identical call through once. With
  no staged sends, line 3 says so ("No codes: nothing waits for approval").

Write each code exactly as the guard gave it, and nowhere else: not in the spec, the page, a
note, a record or the plan (binding rule 2). Everything else the principal needs is on the
sheet; if you are tempted to add a fourth line, it belongs on the sheet.

## Codes expire

The message guard drops an approval request 15 minutes after filing it. If the principal opens
the sheet later, the codes in line 3 may be gone: make each blocked call again (a retry inside
the window keeps its code; after it, the guard files a new one) and post a fresh codes line. The
sheet does not change, because it never held a code. A row the principal marked "Don't send it"
or "Not now" gets no code at all.

## Adapters by harness

**Claude Code: a private claude.ai Artifact.** Publish the filed page with the Artifact tool
(publish, with `file_path` set to the filed `.html`); artifacts start private. The principal can
open it on a phone or a laptop. Inside the viewer, `https://` links (WhatsApp, LinkedIn, web
tasks) open normally, while Messages, phone and mail links may do nothing; the page shows the
number and Copy works there ([channels-and-links.md](channels-and-links.md)). Marks are saved in
the viewer's own browser, per device, so marks made on the phone stay on the phone; the
paste-back carries them to the agent either way. To update a published sheet, rebuild from the
spec and publish the new filed page; never edit the published copy. A later adapter could give
the artifact a shared store so taps reach the agent without a paste; it is not built, and the
paste-back stays the return path.

**Codex, Muse and other harnesses: the local file.** Open the filed page in the principal's
browser (`open <path>` on macOS, `xdg-open <path>` on Linux) and put its absolute path in line 2.
A page opened from disk has no viewer sandbox, so `sms:`, `tel:` and `mailto:` go to the
operating system's handlers. It is not reachable from a phone; for that, use a host below or
the Claude Code adapter.

## An optional shared private host (not implemented)

One place any harness can publish to and the principal can open on a phone, behind their own
sign-in: for example a static site on a hosting service with an access gate limited to the
principal's account. It is an option for the principal to set up, not part of this skill. If
one is set up:

- It serves only the filed pages, privately, and never anything public. Sheets name people and
  carry message text.
- The page already holds no codes and needs no server: the paste-back still closes the loop.
- The deploy guard holds deploys and pushes to sites that deploy on push. A sheet host either
  takes a code for each upload like any deploy, or gets its own entry in the guard's
  configuration, which is the principal's setting to make, never an agent's.
- Pages on a normal host have no viewer sandbox, so the Messages, phone and mail links work there
  as on a local file.

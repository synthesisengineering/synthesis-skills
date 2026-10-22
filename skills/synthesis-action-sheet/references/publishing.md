# Action sheet: handing it over

The chat contract, how each harness puts the page in front of the principal, the optional
private host, and why the codes line can go stale. Read it when handing a sheet over or setting
up the host.

Contents:
- The core: one filed file
- The chat contract: three lines
- Codes expire
- Adapters by harness: Claude Code, Codex, Muse and others
- The optional private host: Cloudflare Pages behind Access

## The core: one filed file

The sheet is one self-contained HTML file with no build step, dependency, server or network
call, filed in the owning project's `resources/artifacts/` by `build_sheet.py --file-into`. Any
harness can build it and open it; every agent on the project can read it, and the next session
finds it after this one is gone. Publishing is an adapter on top of that file. No harness
feature is the foundation: the paste-back works in every harness, so the loop closes even where
nothing else does.

No hosting account is needed, and none is assumed. Building, filing and recording make no
network call and read nothing from the home folder; a test runs all three with the network
refused, an empty home folder and nothing on the path.

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
operating system's handlers. It is not reachable from a phone. A principal with Claude Code
reaches it there through the Artifact above, and one with the private host below through the
host; for a principal with neither, the sheet opens only on the computer it was filed on.

## The optional private host: Cloudflare Pages behind Access

One place any harness can publish to and the principal can open on a phone, behind their own
sign-in. It is the principal's to set up; the skill works the same without it.

**Setting it up, once:**

1. A Cloudflare Pages project that serves sheets and nothing else, for example
   `wrangler pages project create <name> --production-branch main`. Sheets name people and carry
   message text, so the project never serves anything public.
2. One self-hosted Access application whose destinations are `<name>.pages.dev` and
   `*.<name>.pages.dev`, with an allow policy naming only the principal's email address. The
   wildcard matters: every deployment and every branch gets its own subdomain. Access's one-time
   code, emailed to that address, is enough to sign in; no identity provider is needed.
3. In the principal's synthesis config, `"sheet_hosts": ["<name>"]`. The deploy guard then lets
   the script's uploads to that project through without an approval code; a direct
   `wrangler pages deploy` to it, or an upload to any other project, still waits for one. Listing
   a host is the principal's setting, never an agent's. Without it, every upload takes a code like
   any deploy, and a second one within 45 minutes is a rapid redeploy.

**Publishing:** `python3 scripts/publish_sheet.py <filed page> --project <name>` (or the filed
`-spec.json`). It prints `published <deployment address>`, which goes on line 2 of the chat
contract, and `latest <host address>`, which always shows the newest sheet and is worth a
bookmark on the phone. What it does, in order:

- **Rebuilds the page from the filed spec** and uploads that, never the file on disk, so a page
  edited by hand cannot reach the host. The rebuild embeds the filed spec, whose keys are sorted,
  so its integrity marker differs from the filed page's; its binding digest is the same, so the
  paste-back records against the filed spec as usual.
- **Checks the gate before uploading.** A request with no sign-in to `https://<name>.pages.dev/`
  and to a fresh random subdomain must be redirected to a sign-in on a `*.cloudflareaccess.com`
  address. Anything else (an answer, a 404, a redirect elsewhere) prints `will not publish:` and
  exits 2 with nothing uploaded.
- **Uploads with wrangler**, which uses its own sign-in; the script reads no credential. The
  upload carries headers for no indexing, no caching and no referrer, so links on the sheet do
  not pass its address on.
- **Checks the new deployment's own address the same way.** If it does not ask for a sign-in, the
  script exits 3 with `UPLOADED, BUT NOT BEHIND THE SIGN-IN` and says to delete that deployment.
  A failed or unfinished upload prints `upload failed:` and exits 4.

Notes:

- Marks are saved per address: the deployment address and the host address keep separate marks,
  as a phone and a laptop do. The paste-back carries them either way.
- Pages on the host have no viewer sandbox, so the Messages, phone and mail links work there as on
  a local file.
- The page holds no codes and needs no server: the paste-back still closes the loop.

---
name: synthesis-action-sheet
description: "One page of what the principal must still do after agents act: done items folded, staged sends awaiting approval codes, their own messages and tasks with exact text, Copy, open-in-app links, marks, Me or Agent, and a paste-back. Use after a decision packet or daily plan."
license: "Apache-2.0"
depends_on: ["synthesis-decision-packet"]
metadata:
  author: "Rajiv Pant"
  version: "1.1.1"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Action Sheet

After agents carry out the principal's rulings, what remains is theirs: sends that wait for an
approval code, and messages and tasks only they can do. A chat reply that mixes those with what
is already done leaves the principal unable to tell what was done, what to approve, what to type
and what to send. An action sheet is one self-contained page that answers each, built on the
page engine of [synthesis-decision-packet](../synthesis-decision-packet/SKILL.md). A decision
closes when it is made; an action closes when it is done and confirmed, and it can carry forward,
so the two are separate pages.

## Binding rules

1. **One page per sitting.** Everything the principal must act on goes on one sheet: done for you (folded), approve, do. Two pages split the attention the sheet exists to hold.
2. **Approval codes never go on the page or in a file.** The generator refuses any value holding `approve` and a code of the guard's shape (a digit, then five hex characters) and any field named for a code, since a pasted summary holding one would grant a send nobody chose. Codes go in chat, on one line.
3. **The chat after a packet or sheet is exactly three lines:** what was done (count and link), the page to open, and the codes line. No lists of items in chat; the sheet holds them.
4. **Generate from a spec; never hand-author or hand-edit the page.** Links are built and tested in the generator, and the page carries the packet's integrity marker.
5. **Open every generated sheet before handing it over.** The packet's permanent defects were found by loading the page, not by reading its source.
6. **A click is a claim, not proof.** After the principal marks a message done, confirm it from the source (Messages `chat.db`, WhatsApp `ChatStorage.sqlite`, LinkedIn in the browser, sent mail) before logging it under the daily plan's "On your behalf". Log a row with no readable trace as "principal reports done".
7. **Choosing Agent permits exactly that text to exactly that recipient on that channel, once.** Use a guarded send tool where one exists, else computer use or the browser. The send guard holds those sends too and asks the principal for their code; the sheet's choice does not replace it. Stop on any difference from the row, and verify afterward from the source.
8. **Money, security, credentials and identity rows, and rows without exact text, are `agent: never`,** and their links are never prefilled. The generator refuses a spec that says otherwise.
9. **The paste-back returns marks, Me or Agent and notes; `record_actions.py` files them.** "Not now" and unmarked rows carry forward by exact id (`--successor`). A row handed to the agent closes only on the agent's confirmation from the source.
10. **File in the owning project's `resources/artifacts/`,** never only as a chat artifact. Publishing is an adapter per harness, never the foundation. No hosting account is needed: without one the sheet is the filed page, and in Claude Code also a private Artifact a phone can open.
11. **Feeds:** a decision packet's recorded rulings and the daily plan's items only the principal can do become rows. [authoring.md](references/authoring.md) shows the mapping.
12. **An optional private host takes only `publish_sheet.py`'s uploads:** the generator's page rebuilt from the filed spec, uploaded only while the host and a fresh subdomain send a request with no sign-in to a Cloudflare Access sign-in. Listing the host in `sheet_hosts` is the principal's setting, never an agent's; without it each upload waits for a code.

## Contents

- [references/authoring.md](references/authoring.md): the sections, every row field, who does it, risk rows, the feeds from packet rulings and the daily plan, and the example spec. Read it before writing any spec.
- [references/channels-and-links.md](references/channels-and-links.md): each channel's link, what it was verified against, the claude.ai viewer's limit on custom-scheme links, Copy. Read it when a link misbehaves or before adding a channel.
- [references/publishing.md](references/publishing.md): the three-line chat contract, the adapter for each harness, the optional private host on Cloudflare Pages behind Access, and code expiry. Read it when handing a sheet over or setting up the host.
- [references/filing-and-records.md](references/filing-and-records.md): the commands and what they print, the actions record, confirming marks, acting on rows handed to the agent, carrying forward. Read it when the paste comes back.
- [references/background.md](references/background.md): the origin, why a separate skill, related skills, changelog. Read it when choosing between this skill and a neighbor.
- Use: below.

## Use

```bash
python3 scripts/build_sheet.py --schema                  # the spec format
python3 scripts/build_sheet.py spec.json -o sheet.html   # a working copy
python3 scripts/build_sheet.py spec.json \
    --file-into PROJECT/resources/artifacts/            # + <date>-<slug>-spec.json, <date>-<slug>.html
python3 scripts/record_actions.py paste.txt \
    --spec PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --file-into PROJECT/resources/artifacts/            # -> <date>-<slug>-actions.json
python3 scripts/record_actions.py --successor next-spec.json \
    --actions PROJECT/resources/artifacts/<date>-<slug>-actions.json \
    [--agent-done ID ...] [--not-found ID ...] [--title "..."]
python3 scripts/publish_sheet.py PROJECT/resources/artifacts/<date>-<slug>.html \
    --project NAME                                      # optional private host (rule 12)
```

Output: the generator prints `filed <path>` for each filed copy (`wrote <path>  (N bytes; ...)` for `-o`), or `will not build:` with one line per problem and exit status 2. The recorder prints `filed <path>  (N rows: ...)` and the rows handed to the agent; `--successor` prints the ids it carried. Refusals exit 2 and never repeat a note or a code. The publisher prints `published <deployment address>` and `latest <host address>`; `will not publish:` (exit 2) means nothing was uploaded. Template, schema text and an example spec: `assets/`.

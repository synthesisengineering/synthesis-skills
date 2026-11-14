# Action sheet: channels and links

Each channel's Open link, how the generator builds it, what it was checked against and what was
not, the claude.ai viewer's limit on custom-scheme links, and how Copy works. Read it when a
link misbehaves, before relying on a link on a new device, or before adding a channel.

Contents:
- What the generator emits and refuses
- Each channel: the link, its source, its limits
- Inside the claude.ai viewer
- Copy
- Adding a channel

## What the generator emits and refuses

Links are built in `build_sheet.py` (`open_link`) from the row's address and exact text, never
taken from the author, except a LinkedIn conversation and the page of a web or task row. Only
four schemes are ever emitted: `https`, `sms`, `mailto` and `tel`; the generator raises rather
than write anything else. An author's `href` must be `https://` with a host and no user name,
password or port other than 443; `javascript:`, `data:`, `http:`, scheme-relative (`//host`)
and other schemes are refused. A done item's `href` may also be a relative path, for a filed
record beside the page. A money, security, credentials or identity row gets no text in its link,
and its `href` may carry no query or fragment.

## Each channel

**WhatsApp** (`whatsapp`): `https://wa.me/<digits>?text=<percent-encoded text>`. Checked
2026-10-20 against WhatsApp's Help Center page "How to use click to chat"
(faq.whatsapp.com/general/chats/how-to-use-click-to-chat, rendered in a headless browser because
the page builds itself in script). It gives that form: the full number in international format
with no plus, leading zeros, brackets or dashes, and the message URL-encoded in `text`; it says
click to chat works on the phone and in WhatsApp Web. The generator drops the plus from the
E.164 number (which has no zeros or punctuation by definition) and encodes the whole text as
UTF-8 with nothing left raw (space `%20`, line break `%0A`, `&` `%26`, `#` `%23`). On a Mac the
link opens the default browser (Launch Services, checked read-only on 2026-10-20), and WhatsApp's
page hands off to the desktop app or WhatsApp Web. Not tested: opening a real chat (it needs a
real contact) and very long texts.

**iMessage and SMS** (`imessage`, `sms`): `sms:<E.164>&body=<percent-encoded text>`, a custom
scheme. Apple's archived "SMS Links" reference (iPhone URL Scheme Reference, updated 2017-09-19)
documents only `sms:<phone>`, says the URL must carry no message text, and says SMS links are
iOS-only. The `&body=` form is undocumented: it is the form iPhones are reported to read, with
mixed results across iOS versions (an Apple developer forum thread from the iOS 11 years reports
the body arriving only when Messages was already open). RFC 5724 specifies `?body=`, which
Android follows. On a Mac, Launch Services hands `sms:` to Messages (checked read-only on
2026-10-20); whether Messages on macOS fills in the body was **not tested**, because testing it
opens the principal's own Messages app. So the row shows the number as selectable text, says
Copy works, and Copy is the dependable path. An iMessage contact known only by an email handle
goes as a `task` row with the text.

**LinkedIn** (`linkedin`): LinkedIn documents no link that fills in a message. The Open link is
the conversation's URL from `href` (refused unless its host is `linkedin.com` or
`www.linkedin.com`), else `https://www.linkedin.com/messaging/`, the inbox. Copy the
conversation URL from the principal's browser while the conversation is open; it looks like
`https://www.linkedin.com/messaging/thread/<id>/`. Not verified here: the thread form, which
needs a signed-in account.

**Email** (`email`): `mailto:<addresses>?subject=...&body=...` per RFC 6068: addresses separated
by commas, subject and body percent-encoded, line breaks as `%0D%0A`. A fallback only: the agent
sends email itself through the guarded tool, so most email belongs under `approve`. Launch
Services hands `mailto:` to the default mail app.

**Call** (`call`): `tel:<E.164>`, the global-number form of RFC 3966. On a Mac, Launch Services
hands `tel:` to the Phone app (checked read-only on 2026-10-20); on a phone it dials. The row's
text, if any, is talking points with Copy.

**Web and task** (`web`, `task`): the `https://` page as given, opened in a new tab, labeled with
its host ("Open bank.example.test") so the principal sees where it goes. Nothing is filled in.
A task without a page has no link.

## Inside the claude.ai viewer

The claude.ai Artifact page contract (the Artifact tool's design guidance) says links to other
websites (`https://`) open in a new tab, but `mailto:`, `tel:`, `sms:` and other custom schemes
are unreliable inside an artifact: for many viewers following one does nothing, and the page
cannot tell. So on a published sheet the WhatsApp and LinkedIn links work, while Messages, phone
and mail links may do nothing. The page answers that by design: the number or address is shown
as selectable text, the row says Copy works, and nothing on the page claims a message was sent
because a link was tapped. The same contract says the viewer answers `confirm()` with false, so
"Clear marks" asks on the page itself. A page opened from a local file or a normal private host
has no such sandbox: custom schemes go to the operating system's handlers.

## Copy

Copy follows the decision packet's order, which is load-bearing: select the exact text first, so
a manual copy always works; say something at once; then a copy event that writes the exact text
through `document.execCommand("copy")` (which works in sandboxed frames); then
`navigator.clipboard.writeText`, bounded by a two-second timer; and finally an honest message that
the text is selected for Cmd+C, Ctrl+C or the phone's Copy. The status never stays empty. The
browser test asserts the immediate status and the exact selection; whether the system clipboard
received the text depends on the browser's permissions and cannot be observed headless.

## Adding a channel

Add it to `CHANNELS` and to the right section in `SECTION_CHANNELS` in `build_sheet.py`, build its
link in `open_link()` with a scheme from `SCHEMES` (add a scheme only with a reason recorded here),
say what the link was checked against in this file, and add a link test to
`tests/test_sheet_build.py`.

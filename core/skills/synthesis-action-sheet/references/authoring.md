# Action sheet: writing the spec

What goes on a sheet, how each row is written, who may do it, and where rows come from. Read it
before writing any spec. The full field list is `python3 scripts/build_sheet.py --schema`
(`assets/spec-schema.txt`); a complete synthetic spec is `assets/example-spec.json`.

Contents:
- The three sections, and what never goes on a sheet
- Writing a row: name, why, exact text, address
- Who does it: `agent: can` and `agent: never`
- Risk rows: money, security, credentials and identity
- Feeds: rows from a decision packet's rulings and from the daily plan
- Before you build

## The three sections

A sheet answers the principal's five questions in order: what was done, what to approve, what to
type, what to send, what to do. The page opens with counts, then:

1. **Done for you** (`done`): what agents finished for this sitting, each `{kind, label, href}`.
   The page folds it and shows only the counts by kind ("3 emails sent · 2 calendar holds"), so
   it is never a list to read through. Write `kind` as a short lowercase plural ("emails sent",
   "records filed"); link each item to its trace (the sent message, the event, the filed record).
2. **Approve** (`approve`): each staged send that waits for the principal's approval code: the
   exact text, the recipient and address, the channel and why. Stage the send first (the guard
   files a code when the call is blocked), then list it. The page says it waits for a code and
   offers "Don't send it" and "Not now" with a note; the codes themselves go in chat.
3. **Do** (`do`): the principal's own actions: messages on channels the agent cannot or should
   not send on (WhatsApp, iMessage, LinkedIn), calls, web tasks and offline tasks. Each row shows
   who, channel, why, the exact text with Copy, the link that opens the conversation or the
   place, Mark done / Skip / Not now, and a note.

Order rows by what is most urgent first; the page keeps your order. Ids must be unique across
the whole sheet and stable: they key saved marks, the paste-back and carry-forward. Use the
same id when a row carries to the next sheet (the successor does this for you).

Never on a sheet: an approval code, a password or one-time code, card or account numbers, or
anything the principal asked to keep out of files. A decision is not an action: if the
principal still has to choose, that belongs in a decision packet, and its ruling becomes a row.

## Writing a row

- **Name.** Message and call rows are named "<Channel> to <who>" unless you give a `label`;
  web and task rows need a `label` that says what to do ("Pay the venue deposit"). Names are one
  line with no edge spaces, because the paste-back prints `id  name` on one line.
- **Why.** One or two sentences in the principal's terms: why it matters now, and the deadline
  if there is one ("He leaves town tomorrow"). This is what lets them order their own sitting.
- **Exact text.** Every message row carries the words that go out, exactly as they will be
  sent: no placeholders, no "[your name]". Copy copies these bytes, the WhatsApp and Messages
  links carry them, and a row handed to the agent is bound to them by digest. If you are not
  sure of the words, the row is not ready: draft and ground it first (the correspondence skills
  apply), or ask in chat.
- **Address.** WhatsApp, iMessage, SMS and call rows need an E.164 number (`+15555550123`:
  plus, country code, digits, nothing else); the generator refuses any other form, because the
  links are built from it. An iMessage contact you only know by an email handle goes as a
  `task` row with the text, so Copy still works. Email rows need the address. LinkedIn rows take
  the conversation's URL in `href` when you have it (from the principal's browser), else the
  inbox opens. Web rows need the `https://` page where the task is done.
- **Approve rows** show the address as text, so the principal checks the recipient before typing
  the code; give the `subject` for email and calendar sends.

## Who does it

Every Do row declares `agent`:

- `"can"`: the page offers **Who does it: Me / Agent**. The principal can do it themselves
  (quick, and it saves an agent's time and tokens) or hand it to an agent harness that has a
  browser or computer use. Choosing Agent is the principal's permission for exactly that text to
  exactly that recipient on that channel, once; [filing-and-records.md](filing-and-records.md)
  has the protocol the agent follows. The Agent button says what it permits ("Sends exactly
  this text to Sam Placeholder on WhatsApp"), and while it is chosen, Mark done is disabled.
- `"never"`: only the principal does it. Required, and enforced, for money, security,
  credentials and identity tasks; for calls (a conversation, not exact text); for email (the
  agent sends email itself through the guarded tool, so stage it under `approve` instead); and
  for any row without exact text.

Neither choice is preselected: a page that opens decided cannot tell "I chose" from "I never
looked". Unchosen rows stay the principal's.

## Risk rows

Mark a row `"risk": "money" | "security" | "credentials" | "identity"` when it moves money,
changes a security setting, involves a password or code, or acts as the principal's legal
identity (signing, filing). The generator then requires `agent: never`, never puts the text in
the link (a WhatsApp link opens the chat empty), and refuses a query string or fragment on the
row's `href`: the link opens the place, never a filled-in form. Show the details the principal
needs in `why` or `text` (the amount, the payee), and nothing they would not want filed.

## Feeds

**From a decision packet's recorded rulings** (`<date>-<slug>-rulings.json`). Read each ruling
with its row in the packet spec, and place what it leads to:

| The ruling leads to | Where it goes |
|---|---|
| A send the agent makes through a guarded tool (email, Slack, an approved iMessage) | Stage the send, then an `approve` row with its exact text |
| A message the principal sends on a channel the agent does not send on (WhatsApp, LinkedIn, personal iMessage) | A `do` row with the exact text; `agent: can` when an agent may send it by computer use |
| A task only the principal can do (pay, sign, call, confirm in person) | A `do` row, `agent: never`, with `risk` where it applies |
| Work the agent finished | A `done` item linked to its trace |
| "Not now" or a note that changes the work | Nothing yet: act on the note, or carry the decision in the packet |

A ruling is a decision, not an authorization to send (the packet records `authorization.granted:
false`): the approve row and its code, or the principal's Agent choice, is what lets a message go.

**From the daily plan.** The items only the principal can do become rows the same way: drafts
under "Drafts — Ready to Send" that the agent will send become `approve` rows once staged;
drafts the principal must send themselves become `do` rows with the draft's exact text; tasks
the principal owns under "Priority Tasks" become `do` rows (`agent: never` unless the task is a
message with exact text); what was sent or completed today becomes `done` items. The sheet does
not replace the plan: the plan stays the day's record, and the sheet is the principal's page for
one sitting.

**From the previous sheet.** `record_actions.py --successor` writes the rows still open or put
off, by exact id and unchanged; add today's new rows and `done` items to that spec before you
build it, and give it today's `--title`.

## Before you build

- Every message row has its exact, grounded text, and every number is E.164.
- Every send under `approve` is staged and waiting for a code right now (codes expire; see
  [publishing.md](publishing.md)).
- `agent: can` appears only on rows an agent could do from exact text, with nothing at risk.
- Nothing on the sheet is a decision in disguise, and nothing holds a code or a secret.
- Then build, file, open the page and read it as the principal will (binding rule 5).

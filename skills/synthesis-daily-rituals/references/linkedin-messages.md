# LinkedIn messages as a declared surface

Read before a sync in a workspace that declares `.agents/linkedin-sync.yaml`. `<rituals>` is this skill's folder;
`<W>` is the workspace.

## Why it is a surface of its own

LinkedIn reaches a mailbox only as notification emails, which often hide the text and never cover InMail or the
messages LinkedIn chooses not to email about. A principal found messages there that no ritual had shown him. The
conversation list itself shows what a ritual needs without opening anything: who, the day, who spoke last, the whole
last message, unread counts and LinkedIn's own "Reply?" nudge.

## The declaration

```yaml
# .agents/linkedin-sync.yaml
workspace: personal
parking_thread: "2-ABCdef123xyz=="   # a dormant conversation whose opening changes nothing
inboxes: [focused]                   # the list views to read
```

`parking_thread` is required. **Never load `https://www.linkedin.com/messaging/` itself:** it opens the newest
conversation by itself, and when that one is unread the read marks it read. A thread's own address shows the same
list and opens only that thread, so the read opens a conversation chosen because nothing in it changes (an old
exchange, a note to self). Its id is the part of its address after `/messaging/thread/`.

## The read

1. `python3 <rituals>/scripts/linkedin_messages.py plan --config .agents/linkedin-sync.yaml` prints the address to
   open and, per inbox, the day the last read reached:

   ```text
   open  https://www.linkedin.com/messaging/thread/2-ABCdef123xyz==/  (the parking thread; never the bare messaging page)
   read  focused: read through 2026-11-10; scroll back to that day and pass --since 2026-11-10
   ```

2. Open that address in the browser profile where the principal is signed in to LinkedIn. Scroll the conversation
   list (the left pane, not the page) until its oldest entry is on or before the day `plan` named: the list loads
   as it scrolls. Click no conversation.
3. Save the list's text to a file: the list element's text where the browser tool can run a page script, or the
   whole page's text where it returns that. Note the time of the read.
4. `python3 <rituals>/scripts/linkedin_messages.py parse --text <file> --read-at <ISO time> --since <day>` prints
   the coverage line and the conversations that end with someone else:

   ```text
   LinkedIn messages: 8 conversations read from the list, back to 2026-11-05; 5 end with someone else (3 unread, LinkedIn asks for a reply on 1); none opened
     2026-11-10 Cy Castillo: Cy: We met years ago. Would you have thirty minutes to talk about a product role?
     2026-11-09 Eli Edwards: Eli: 👍  [LinkedIn asks for a reply]
     2026-11-06 Flo Fischer: InMail • Advisory project: how it works  [InMail, 1 unread]
   ```

   Exit 0: the read is complete. Exit 1: it stopped short of `--since` or could not read an entry; scroll further
   or look at the entry, and read again. Exit 2: the text holds no conversation list, or shows a sign-in page or a
   security check. **At a sign-in page, a security check or any warning from LinkedIn, stop and tell the principal.**
   `--json` gives every conversation (`who`, `last`, `from_me`, `speaker`, `kind`, `unread`, `nudge`, `preview`)
   and the coverage.
5. Record the read: `python3 <rituals>/scripts/sync_watermark.py advance --workspace <W> --surface linkedin --target
   <inbox> --through <read time> --coverage <the --json output>`. The watermark moves only with a complete read's
   coverage, as a local message store's does.
6. The coverage line goes in the plan's sync state, word for word. It names no one.

## What is owed

The candidates are the conversations that end with someone else. From each preview:

- A thank-you or a reaction to the principal's own message is closed. Say so in one line; it needs nothing.
- Anything that asks, offers or invites goes to the plan with its day and the whole last message.
- An unread count, an InMail and LinkedIn's "Reply?" nudge are reasons to look, not verdicts.
- Open a thread only when the preview cannot show whether something is owed. Opening marks it read, so name each
  opened conversation in the plan and pass their number as `--opened`.

A reply is a send like any other: it goes through the correspondence skill, in the lane and with the signature rule
the principal has set for that site, and the send guard holds it for the principal's code (LinkedIn messaging is on
its list of messaging sites). The ritual itself sends nothing.

## What the list does not give

- **The minute.** Today's entries carry a clock time; older ones carry only the day. `--since` is a day, and a
  read overlaps the last one by a day on purpose.
- **A thread id.** List entries carry no link. A conversation is known by its participants' names, and the
  watermark is per inbox, not per conversation.
- **Everything at once.** The list is virtual: only what has been scrolled into view is in the text.
- **Other list views.** Declare each view to read under `inboxes`; a view not declared is not read, and the plan
  says which were.

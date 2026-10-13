# Preferred names

What to call the people a message greets or names, where a preferred name comes from,
what stays as the platform requires, how the principal's map is kept, and what the send
guard checks. Binding rule 12 in SKILL.md is the short form.

Contents:
- The rule, and why it matters more for agents
- Where a preferred name comes from, in order
- What stays as the platform requires
- Keeping the principal's map
- The editor pass
- What the send guard checks

## The rule, and why it matters more for agents

Address a person by their preferred name in prose and greetings wherever one is known.
Someone who goes by Bob is "Bob" in the greeting, in the body and in the thanks at the end,
not "Robert".

Systems carry official names: the directory, the HR record, an email header's display
name, a calendar invitation, a CRM. People answer to the names they go by. An agent drafts
from system data far more often than a person does, so it reaches for the official name
by default, and a greeting with the wrong name tells the reader the message came from
something that does not know them. That is the one impression an agent-assisted message
must not give. On 2026-10-13 an agent message addressed someone by the official first
name a directory showed; the principal then told her the agent's editor phase would change to
use preferred names where one exists.

## Where a preferred name comes from, in order

1. **A preferred-names map the principal keeps.** The principal knows what their people
   go by, and the map records it with its source. It wins over every other source.
2. **The person's chat display name, when it differs from their real name.** A display
   name of "Bob Example" over a directory name of "Robert Example" is the person telling
   everyone what to call them.
3. **The name they sign or use in their own messages.** A sign-off ("Bob"), or how they
   refer to themselves.

With no known preference, use the name the person uses in their own messages. When a
person has never written and no source gives a preference, the official first name is
the fallback, and a source found later replaces it.

A document whose purpose is the legal name (a contract, an HR or legal record, a form)
keeps the legal name. That is a record, not correspondence.

## What stays as the platform requires

- **Mention syntax** is whatever the platform needs: Slack `<@U0EXAMPLE>`, Jira
  `[~accountid:...]`, an email address. Only the words around it change. A Slack mention
  renders as the person's display name, so it already shows the name they chose.
- **Address fields** (`to`, `cc`, `bcc` and their display names) are addresses, not
  greetings.
- **Quoted text** stays as written: never edit what someone else said.

## Keeping the principal's map

- One entry per person: the official first name, the preferred name, the identifiers
  that name them on each channel the principal uses (email addresses, a chat user id, the
  principal's DM channel id with them, a ticketing account id), and the source of each:
  where the preference was seen, and where each identifier was read.
- Add an entry when a preference is learned: the person signs with another name, corrects
  someone, shows a display name that differs from their directory name, or the principal
  says so. Record the source in the same change.
- Group the entries by workspace or organization, so an entry can leave with the
  relationship it belongs to.
- The map is private: it names real people and their identifiers. Public skills and
  examples carry only `example.test` entries.
- Mirror each entry into the send guard's `preferred_names` config so a slip is caught
  before approval (below).

## The editor pass

At the compose-time gate and again at the send-time gate (references/gates-and-sending.md),
list every person the draft greets or names and check each name against the sources
above. Look hardest at names that came from system data: a directory lookup, a calendar
attendee list, an email header, a meeting tool's speaker label. Those carry official
names.

## What the send guard checks

`synthesis-message-guard` reads the principal's `preferred_names` entries
(`{"official", "preferred", "identifiers"}`). When the call carries one of an entry's
identifiers anywhere (a recipient, the channel, mention syntax in the text), the official
first name, as a whole word and case-sensitively, is refused outside the address fields
with:

```text
this message involves someone who goes by Bob; write Bob, not Robert
```

A message to someone else who shares the official first name is never blocked, because
none of that entry's identifiers is in the call. The guard catches only the people the map
lists, and only when the call identifies them; the editor pass covers everyone else. The
key and its matching rules are in the message guard's
[config reference](../../synthesis-message-guard/references/config.md#preferred-names).

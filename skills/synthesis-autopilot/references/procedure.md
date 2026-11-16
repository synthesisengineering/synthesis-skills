# Procedure: engagement to close

The six steps of a run. They moved word for word from SKILL.md's Procedure section
in 4.2.0, to make room there for binding rule 14. Helpers run as
`python3 -S "$AP" <command>`, with `$AP` as SKILL.md's Procedure section sets it.

1. **Engage.** Tell the user in one line: mode plus plan path. Anchor with synthesis-checkpoint, read the board and inbox, and claim what the run will write.
2. **Plan.** Write the plan in the project from the template, then `engage --plan <path>`. If the horizon passes this turn, set up and record the continuation and backstop now, and put the plan path and next item in CONTEXT.md's current-state block so compaction brings them back.
3. **Phase loop.** Re-read the plan and board; work with anti-shortcut discipline; decide by class; dispatch by the fan-out rules; record the wake with `cycle --advanced` or `--waiting-on`; update the plan; move cited scratch into the project; refresh CONTEXT.md and the session log.
4. **Wait or block honestly.** Nothing ready: `Status: waiting` with `Waiting on:`. Only the principal can unblock: record the blocker (with a probe for any missing capability), run `alert --kind blocked --count N`, note the outcome on the blocker, set `Status: blocked`, and keep the report in the plan.
5. **Verify.** Run synthesis-implementation-integrity or the domain's equivalent and fix what it finds.
6. **Close.** Delete every scheduled job and read the deletion back; `close --done`, or `--incomplete "<reason>"`; release claims; write the completion report; `alert --kind done`.

## When the count stops the run

`cycle --advanced` refuses to record an advance when the run's own items outran
the principal's ([plan-file.md](plan-file.md#origins-and-the-count)), and the
turn-end check asks for the same thing instead of the next item. Start nothing
new until the principal answers: the stop holds the whole run, the one exception
to rule 8, and a wake that finds it does no work. Bring the principal the one line
`cycle` printed, as it printed it, and record it under `## Blockers` with its
alert (`alert --kind blocked --count 1`); set `Status: blocked`. If anything was
added or closed after that alert, the turn-end check names it: tell the principal
what was done, alert them again, and add the new alert to the blocker.

When the principal answers, write their reply on the `Principal answer:` line, in
quotes and word for word, then where they gave it and when; check the blocker
with their words, and set `Status: running`. Quote the reply from the word
continue, narrow or stop that they used ("Yes, continue, but skip X" becomes
"continue, but skip X"), keep their whole reply on the checked blocker, and ask
again only when the reply holds none of the three words. Never write the line from
your own judgement: the count's question is a checkpoint the principal reserved.
The count reads the quote's first word:

- **continue**: go on with the next open item.
- **narrow**: first narrow the plan as they said: take the items they dropped off
  the checklist and record them, with their words, in the decisions log. Then go on.
- **stop**: close the run with their words as the reason
  (`close --incomplete "<reason>"` or `--cancelled "<reason>"`), or, if they asked
  to pause, set `Status: paused — <who asked and when>`.

An answer of continue or narrow holds for 24 hours from the time it was given.
After that the count asks again if the run's own work still outruns the
principal's.

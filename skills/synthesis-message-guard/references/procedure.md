# Message guard: the procedure

The six steps from composing a message to recording its send. Moved here word for word from SKILL.md in 2.11.0, to make room for binding rules 16 and 17; "binding rule" means a rule of SKILL.md, and a file it names is linked from this folder.

1. **Research, then compose** (binding rule 2). Write email as HTML paragraphs: `htmlBody` on the Gmail connector (its `body` is the plain-text alternative, also whole paragraphs), `body` with `body_format: "html"` on the workspace connector.
2. **Freeze the complete call:** recipients, subject, thread fields, every body part, attachments. Then make the call once. If the text breaks a rule, the guard answers `This message can't go out as written: <reasons>.` and files nothing; fix it and call again.
3. **Ask for approval.** A clean message is blocked with `Sending needs the principal's approval of this exact message ... type approve followed by the code <code>`. Show the principal the exact text and recipients, in full, and the code. `synthesis approvals` lists what is waiting.
4. **When they type `approve <code>`** (several codes may follow the word on its line), make each identical call again. A changed call needs a new code; an approval unused after 15 minutes is gone, and so is one the harness declined after the guard let it through ([references/composing.md](composing.md)).
5. **Verify** (binding rule 8): fetch the draft or sent message and compare recipients, subject and paragraphs with what was approved.
6. **Record** the send where the correspondence skills say (transcript, plan), with its message id.

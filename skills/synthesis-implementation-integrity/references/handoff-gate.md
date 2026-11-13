# The handoff gate: before another person is given something to use

The moment a person other than the principal relies on something, it is production,
whatever it was built as. This gate runs before anything is handed to such a person: a
service, a connector, a link to a tool, a shared sheet that a script fills, an automation
that acts for them. A miss on any line blocks the handoff. The principal's own test needs
no gate, and stays the principal's own.

## Where it came from

A connector was proved on the principal's laptop: a process in a terminal tab, a free
quick tunnel for its public address, sign-ins kept in memory. It was approved as a test.
The same day its address was given to two colleagues, with one warning, to keep the laptop
open until the meeting ended. One of them kept using it for real work. A day and a half
later the laptop's app restarted, the process and the tunnel stopped, and the address was
gone for good. Two scheduled check-ins ran without looking at it. Nobody had decided that
a test should carry someone's work, and nothing in the handoff asked.

## The five lines

Each line needs evidence that was read this session, not remembered. Write the evidence
beside the line in the handoff record.

| Line | What must be true | Evidence that counts | What fails it |
|---|---|---|---|
| Where it runs | On infrastructure that outlives the principal's machine and session, under the organization's own accounts | The deployed service's own description: its project or account, region and revision, read from the platform | A laptop, a terminal tab, a session-bound process, a temporary folder, a personal cloud account |
| Its address | Permanent: a name the organization controls, which stays the same across restarts and redeploys | The address resolved now, and the record that shows who owns the name | A quick tunnel's host, a local name, a private or loopback address, a port on someone's machine, a preview address that changes with each build |
| Its state | Survives a restart: sign-ins, tokens, queues and data are kept outside the process | A restart done on purpose, after which a signed-in user is still signed in and the data is still there | Anything kept in memory or in a temporary folder; "they sign in again" as the plan |
| Who watches it | A health check that runs without anyone remembering to run it, and an alert that reaches a person when it fails | The check's definition and one alert seen arriving (a failure made on purpose in a test) | A check someone runs by hand; an alert nobody receives; a dashboard nobody opens |
| Who owns it | A named person who is told when it fails and can fix it, and a second way to reach it when they are away | The owner's name in the service's own record and in the handoff note | "The agent", "this session", nobody |

## Each recipient

The five lines are about the thing. This one is about each person it is handed to, and it
is checked per person: one recipient having access proves nothing about the next.

- They can reach it: they are a member of the workspace or group it lives in (read the
  members and the pending invitations where an administrator sees them), and the feature
  is turned on for them.
- The route they are told to take has passed an end-to-end test. A route that was never
  tested is not offered.
- When a check fails, the fix is prepared and brought with the finding, in the order it
  must run: the invitation, the access change, the corrected note. A problem reported
  without its fix hands the principal work that could have been done.
- A note revised and filed again is checked again. A change of wording does not carry the
  earlier check with it.

## When a line fails

Do not hand it over. Say which line failed and what would make it pass, and either deploy
it properly first or keep it the principal's own test.

If the principal decides a demonstration on test ground cannot wait, that is their
decision to make with the facts in front of them. The handoff note then opens with one
plain sentence that says what the demonstration depends on and when it stops. The person's
access is removed when the demonstration ends, unless the principal decides otherwise.
The address of a test is never written into a message to anyone but the principal: the
send guard refuses a message that carries one (the `temporary_addresses` setting), and
starting a quick tunnel waits for the principal's code.

## After the handoff

- What another person relies on is declared where the check-ins look (the daily rituals'
  `relied_on` setting), so its health is checked at every check-in and at every wake of
  an autopilot run, and a failure, or a check that did not run, is the first thing reported.
- An outage, a restart or a sign-out that touches someone else's setup is an incident.
  The principal is told first, in the same turn, with who is affected and what the fix
  is. The affected people are told on the principal's approval.
- Every outside dependency of the thing is listed with its owner and where its notices
  arrive (a permission request, an expiry warning, a deprecation), and each of those
  places is read at every check-in. Where the state can be asked directly, it is asked. A
  pending item reaches the principal first in the reply, with what it is, a
  recommendation, and the step staged for their approval.
- A ruling of the principal's that conflicts with something already handed out is said
  the same turn: "that address has already reached them".
- A claim to anyone that something works for a person says how durable it is, or is not
  made.

## What this gate is not

It does not judge whether the thing is good, finished or secure; the integrity passes and
the domain checks do that. It asks only whether a person can rely on it tomorrow without
the principal's machine being awake.

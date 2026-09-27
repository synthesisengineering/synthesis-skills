# Earlier release notes

## v0.11.0 — Confirmed commitments carry their owning workspace

v0.11.0 (2026-09-20) wires §3 ownership into filing: new Step 4.8 stamps
each principal-confirmed commitment `owner:`/`owner_rule:` via
`extract_commitments.py --stamp`, routed by the daily-rituals ownership
rules. Other seats record nothing — not even a pointer.

## v0.10.0 — Saved transcripts get read for obligations

v0.10.0 (2026-09-18) closes the §5b gap: verification proved fidelity
while nothing asked whether anything was owed — Rajiv's "Oh of course"
to Paul Smurl's celebration of life sat in a filed transcript no one
read for obligations. New Step 4.7 runs `extract_commitments.py` over
the saved
file and presents every timestamped candidate for principal
confirmation in the same turn. Candidates only; nothing auto-creates.

## v0.9.0 — The declared set gets an execution path

v0.9.0 (2026-08-29) closes the gap an external adversarial review found in
v0.8.0: the policy said "declared means fetched" while the operative protocol
only resolved one user-named meeting. Step 0 now defines the declared-window
sweep — enumerate the declared set for the window, fetch every member, and
account for every member in the report with unclosed gaps recorded
machine-readably. Frontmatter version also catches up; v0.8.0 shipped with
stale skill metadata.

## v0.8.0 — Declared means fetched: no judgment gate before fetching

v0.8.0 (2026-08-27) removes agent judgment from the decision of *which* declared
transcripts to fetch.

**The defect.** The sweep enumerated documents and recorded their ids, but
fetching was gated on the agent deciding what looked worth fetching. That
judgment deprioritised several meetings as routine standups. One held a live
action item for the principal; another carried a launch date contradicting the
one recorded everywhere else, so the corpus held two incompatible dates and
nothing surfaced the conflict.

**The rule.** If a transcript is declared in scope for the window, it is
fetched. The agent does not get a vote on which declared items are interesting.
Relevance is judged *after* fetching, when the content is visible — never
before, from a title.

**Why this shape is already settled here.** The workspace retired this exact
failure once before, when "sync when active" gating was removed from the repo
list after a repository drifted for six weeks behind a judgment that it looked
inactive. Titles and activity heuristics are not evidence about content. A
declared set exists precisely so that no per-item judgment stands between the
list and the fetch; re-introducing one at a lower level rebuilds the failure the
declared set was meant to prevent.

A run that cannot fetch a declared item records it as an unclosed gap rather
than silently omitting it.

## v0.7.0 — Source grade is now executable

The standing kernel rule already says that a verbatim transcript is the only
primary source for attribution-bearing meeting claims. v0.7.0 adds the missing
mechanical boundary: `transcript_primary.py` rejects a structured summary even
when its filename or heading says “primary transcript,” classifies artifacts
from complete raw provider-message records that pair an identifier with
bounded message content, and requires an exact record-bound message location
before issuing an attribution receipt. Loose or conflicting identifiers fail
closed.

Both executable components now report the same 0.7.0 version as this skill's
metadata. The acceptance suite executes that parity instead of leaving the
existing “must match” banner as an unchecked claim.

The motivating fixture preserves the structure, not the private content, of a
real 128-line summarizer that had been labelled a primary transcript. Its
summary bullets and inline times cannot establish raw-message provenance. The
positive fixture uses synthetic `message_ts`, `thread_ts`, and Slack permalink
records. Classification is explicitly diagnostic. Only
`authorize-attribution` is an enforced gate, and its receipt binds the input
hash and the exact permalink or `message_ts`; a thread id alone is not
quote-granular. Every result names the unverified remainder.

## v0.6.1 — The heartbeat distinguishes absence from invisibility

v0.6.1 makes the doctor classify restricted LaunchAgent visibility as
unverifiable, separates curl transport failure from HTTP status, and prevents a
double-`000` response from being accepted as health.

## v0.6.0 — The optional auto-start service gets a heartbeat

v0.6.0 (2026-08-12) adds `optional-workspace-mcp/doctor.sh`. The bundle shipped an
installer for a supervised background service and no way to ask whether that service
was still alive — the one fail-open control in a stack whose other guards all ship a
health check.

The failure it exists to catch: `install-autostart.sh` records an **absolute** path to
`start.sh` into the launchd/systemd unit at install time. Move the checkout, rename a
parent directory, or restructure the repo, and the unit still points at the old path.
launchd exits `78` (`EX_CONFIG`), `KeepAlive` retries every 30 seconds indefinitely, and
the log fills with thousands of identical lines. Nothing surfaces. The only symptom is
that the MCP tools are quietly absent — and since the natural reading of "my tools are
missing" is a client problem, the investigation starts in the wrong place. Restarting
the client cannot help: the client never owned the process.

Observed 2026-08-12 against a checkout that had gained a `skills/` directory level. The
unit had been failing for an unknown period.

`doctor.sh` checks the unit exists, that its recorded start-script path still exists and
is executable, that the supervisor has it loaded and with what exit status (`78` gets a
targeted hint), that the client secret is present, that the port is listening, and that
the endpoint answers. Exit codes follow the guard contract — `0` healthy, `1` defects,
`2` a check could not run, because a check that cannot run must never be reported as a
check that passed. It also flags the case where the unit runs a *different* checkout
than the one you are editing.

The remedy is always to re-run `install-autostart.sh`, never to hand-edit the unit: the
installer derives the path from its own location and is correct by construction. The
defect was never in the generator — only in the absence of anything that noticed the
generated artifact had gone stale.


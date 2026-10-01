# First useful task and consented local studies

Start with the result the user wants. `synthesis journey catalog` exposes five
product journeys and seven audience types from the release capability catalog.
The default journey is **Portable project**. Audience labels help explain the
work; they do not create separate installers or infer the user's occupation.

| Journey | First task | Existing owners |
|---|---|---|
| Portable project | Save a project plan and checkpointed handoff | Project management, context lifecycle, checkpoint, conformance |
| Engineering | Save a source-grounded implementation plan | Portable project plus code planning, preflight, integrity, review, repository guards |
| Writing | Save a review or revision of a supplied draft | Portable project plus article writing, link research, craft, quality, voice profiling |
| Work management | Save a daily plan from supplied priorities | Portable project plus rituals, catch-up, inbox, absence, chief-of-staff methods |
| Organization | Save a plan grounded in a supplied organization manifest | Portable project plus onboarding, knowledge management, disclosure and guardrails |

The seven audiences are software engineer, product manager, technical leader,
writer, workload manager, AI power user and runtime/tool author. A nondeveloper
can choose any journey. Ask only for the intended result and the actual clients
needed for it. Use plain language before explaining repository or profile terms.

## Agent and terminal path

The same commands serve interactive users and agents. `--json` produces stable
structured output; ordinary output preserves the complete reviewable record.

1. Read the catalog, confirm the local client, then run
   `synthesis journey plan --journey portable-project --clients codex --json`.
   Repeat clients with the existing comma-separated vocabulary, such as
   `--clients claude,codex`. `--no-dormant-core` declines optional staged bytes.
   The modular owner currently binds Claude and Codex. An unsupported client is
   refused instead of being presented as installed or trusted.
2. Show the exact visible skills, support components, required/optional bytes,
   source identity, write scope, first-task instructions and native loading
   boundary. The plan writes only its local receipt. It expires after one hour;
   `--ttl` accepts 1 through 86,400 seconds. A new plan is required after source,
   selected state, machine identity or trust-input drift.
3. Obtain consent for that exact plan. Run
   `synthesis journey apply --id ID --consent PLAN_DIGEST --json`.
   Never infer consent from an unanswered question or from a study consent.
   Modular installation uses its existing transaction and recovery owner.
   Existing full/catalog installations are inspected through the existing doctor;
   they are not replaced, deactivated or reinitialized by a journey.
4. Load the selected skill in the actual client and perform one supplied task.
   Use the project's resolver, claims, checkpoint and publication owners when the
   task belongs to a managed project. The journey does not write a project or
   invent one. Missing integrations remain explicit; do not invent a principal
   profile, meeting history, private voice or organization configuration.
5. Save the useful artifact and show it to the user. After the user confirms its
   usefulness, run `synthesis journey verify --id ID --artifact /absolute/result.md
   --sha256 REVIEWED_SHA256 --confirmed-useful --json`. The release-owned
   `first-use-artifact-check` verifier checks exact bounded UTF-8 file custody.
   Empty, changed, linked, special and oversized files are refused.
6. `synthesis journey status --id ID --json` rechecks the source, installation,
   selected generation and artifact. It reports stale evidence instead of reusing
   a previous green receipt. Use the existing repair/update owners for drift.

A first-value receipt distinguishes **verified artifact bytes**,
**user-attested usefulness**, and **quality not independently evaluated**.
It does not establish a native model call, live loading, client trust, or a
cross-client handoff. The existing `outcome verify` command still requires its
live-loaded selected-generation prerequisite before recording the outcome plane.
Doctor findings remain separate, including genuine unknown or failed planes.

Organization enrollment, private policy, credentials, hook approval, inbox
access, external messages, publishing and scheduling retain their own gates.
Dormant core is staged data; selecting a journey does not activate its hooks,
plugins, services or unselected skill entrypoints.

## Recovery and bounds

The first-run record binds the exact modular transaction before its first file
mutation. A crash before completion uses the same transaction owner's recovery.
A crash after commit reattaches that exact receipt without replaying installation,
including after the plan expires. Uncommitted expired work does not gain renewed
consent. Another owner's pending transaction is refused. Foreign files and
changed bindings remain untouched.

The local record owner uses descriptor-based path traversal, single-link regular
files, a ten-second lock budget, atomic writes and directory fsync. The shared
onboarding state lock refuses after thirty seconds while preserving its owner.
Records are capped at 512 KiB, artifacts at 1 MiB, and the first-run directory at
256 records plus its lock. Limits stop admission; they do not silently prune or
turn an incomplete record into success.

## Local study protocol

`synthesis study protocol --json` presents the versioned protocol and its digest.
Plan a technical Mac cohort and a nondeveloper AI power-user cohort. Additional
Linux/WSL cohorts use the actual supported contract; do not claim native Windows
support. Consent and recruitment are human actions. This implementation performs
no recruitment, enrollment with a provider, audio/video capture, or telemetry.

Before recording any participant observation, explain the purpose, fields,
retention deadline, withdrawal behavior and separately retained witness material.
Create the exact proposed selection before asking for consent:

```sh
synthesis study plan --sample participant --audience ai-power-user \
  --journey portable-project --retention-days 7 --json
```

Save that JSON locally as `/absolute/study-plan.json`. The plan binds the protocol,
sample, audience, journey, retention period, machine identity, local receipt-owner digest and a single-use ID;
it expires after one hour. Present these terms, obtain explicit consent to this
selection, then record the attestation using the plan's exact `digest`:

```sh
synthesis study begin --plan /absolute/study-plan.json --consent PLAN_DIGEST --json
```

A generic protocol digest cannot authorize capture. Repeating the same approved
plan returns its existing record without renewing consent or retention; a
withdrawn or expired study requires a fresh plan and fresh consent. Planning
performs no participant capture. The consent plan contains no home pathname.

Use `--sample synthetic` for rehearsals and fixtures. Synthetic records cannot
be labeled participant evidence. The command records an attestation that consent
was obtained; a flag does not prove consent happened. Do not provide names, email,
raw commands, prompts, paths, credentials, project contents or screenshots.

Record understanding time, first useful artifact time, each copied command,
unexplained terms, permission/trust hesitation, failed-install recovery, update
and uncoached cross-client handoff. Each observation is a separate record passed
to `synthesis study observe --id ID --input /absolute/observation.json --json`:

```json
{
  "event_id": "32lowercasehexcharactersfromuuid4",
  "step": "trust",
  "event": "hesitation",
  "elapsed_ms": 700,
  "observed_at": 1790000000,
  "provenance": "direct-observation",
  "witness_sha256": "64lowercasehexcharactersofconsentedlocalwitness",
  "outcome": "observed",
  "term": null,
  "command": null,
  "command_sha256": null,
  "coaching": "none"
}
```

The placeholders above must be replaced by actual UUID/digest/time values.
`observed_at` is Unix seconds within the consent period. Elapsed time is a
nonnegative integer up to 86,400,000 milliseconds. Events use `started`,
`completed`, `failure`, `hesitation`, `unexplained-term`, or `command-copied`.
Steps are `understand`, `trust`, `install`, `first-value`, `update`, `recovery`
and `handoff`. Outcomes are `observed`, `pass`, `fail`, or `unknown`; coaching is
`none`, `provided`, or `unknown`. Provenance is `direct-observation`,
`participant-report`, or `synthetic-fixture`, matching the sample kind.

For a copied command, use a declared command kind and the digest of its exact
bytes, never the raw command. For an unexplained term, use the bounded vocabulary
shown by the recorder's source/protocol. Use `other` plus the consented witness
digest when a term or command is not in that vocabulary. The recorder stores no
witness content or path; witnesses stay with their separately authorized owner.
It validates receipt shape and provenance binding, not whether a human event is
true. Record an unknown rather than inventing an observation.

At most 200 events and 30 retention days are admitted. Identical event-ID replay
is idempotent; a different observation under that ID is refused. An expired or
withdrawn consent rejects capture. A changed protocol requires new consent.
`synthesis study status --id ID --json` reports counts and missing observations;
it never equates a recorded hesitation, installation or fixture with successful
human adoption. Turn findings into a fixture, documentation change or explicit
product decision under the relevant project owner, preserving provenance.

`study withdraw --id ID` immediately replaces captured observations with an owned
tombstone and erases verified crash preparations for that record. Interrupted
withdrawal can be repeated. After expiry, status hides observations and reports
retention due; `study expire --id ID` performs the same scoped erasure. Logical
file erasure is not a claim of secure deletion from filesystem snapshots or
backups. External witnesses have separate custody and require their own consented
retention action. No unrelated file, installation receipt or project is removed.

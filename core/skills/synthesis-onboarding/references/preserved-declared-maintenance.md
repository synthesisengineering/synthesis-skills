# Preserved: `skills/synthesis-onboarding/references/declared-maintenance.md` before v5 (verbatim)

Retired: machine review, receipt-owned repair and upgrade campaigns were cut (machine_review.py, upgrade_campaigns.py: no incident behind them; release notes and doctor cover upgrades).

## Contents of the preserved text

- Declare the review boundary
- Repair only derived state that the existing receipt owns
- Versioned campaigns on real native events
- Selected project upgrades

---

# Declared machine review, repair and upgrade campaigns

Use the installed `synthesis` CLI. Review is separate from repair, and a campaign
notice is separate from action authority. These routes do not install a scheduler,
wake idle sessions, acquire provider credentials, change account limits or grant
ownership of a project. Unknown coverage remains visible.

## Declare the review boundary

`machine review --inventory <file> --json` reads a schema-1 JSON inventory:

```json
{
  "schema": 1,
  "components": [
    {"id": "installation", "kind": "installation"},
    {"id": "git-guards", "kind": "runtime", "component": "git-hooks"},
    {"id": "message-guard", "kind": "runtime", "component": "message-guard"},
    {"id": "kernel", "kind": "runtime", "component": "kernel"},
    {"id": "day-end", "kind": "runtime", "component": "day-end"},
    {"id": "declared-record", "kind": "file", "path": "/absolute/operator-selected/file", "sha256": null}
  ],
  "registries": [{"id": "workspace", "path": "/absolute/operator-selected/projects/index.yaml"}]
}
```

Paths in the example are placeholders to replace with selected local paths.
Inventories contain 1–512 declared components/registries. Registries accept the
existing list or `projects` mapping shape and at most 256 distinct project IDs
per registry. Duplicate YAML/JSON keys and duplicate IDs refuse rather than
silently choosing one. Each declared unsupported component or unreadable project
is reported UNKNOWN. Unlisted resources are explicitly UNSCANNED. This is a
machine review within the declared scope, not discovery of every possible file.

The installation row observes desired/resolved/installed/source-provenance/
live-loaded/outcome-verified evidence from the existing installation owner.
Saved receipts are not fresh live execution proof. Registry rows use the causal
resolver without fetch, fast-forward, board refresh or checkpoint writes; format
observation is not project-health certification. File comparisons prove only the
declared bytes; a null expected hash observes a file without certifying it.
Review never invokes convergence, repair, native/model/provider work or services.
It creates no installation lock, directory, receipt or acknowledgement.

Each ordinary input and runtime payload is a no-follow, single-link regular file
capped at 8 MiB; selected runtime source payloads are capped at 32 MiB total;
JSON plans are capped at 1 MiB. Review has a cooperative 30-second admission
budget: a member not started within it is explicitly unscanned. Existing release
and Git owners retain their own bounded calls. This is not a promise that an
individual OS read or nested release check can be preempted at exactly 30 seconds.

## Repair only derived state that the existing receipt owns

`machine plan --inventory <file> --select <id> [--select <id> ...] --json`
returns an exact one-hour preview digest. Only the existing runtime components
above are repairable through this route. Generic files, project prose, source
checkouts, personal configuration, claims, native permissions and provider state
are never repair targets. The prior receipt must own every selected target by
component, source path, commit, content hash and mode. Missing owned outputs can
be restored; unexplained changed bytes are preserved. A matching released file
without the original ownership receipt is insufficient authority.

`machine apply --inventory <file> --plan <saved-preview> --approve <digest>`
requires consent to that exact preview. Add `--dry-run` to revalidate without
writing. It repeats the release, receipt and target checks under the existing
engine lock. Freshness is rechecked after lock acquisition and again after input
derivation, immediately before admitting the owner operation. Waiting cannot
extend the consent lifetime. A stale preview refuses before a target effect. Re-preview after a
completed repair produces the ordinary verified no-op when no work remains.
The engine lock waits at most five seconds by default; a held lock is not stolen.

Mutation, backups, write intent, readback and recovery use `runtime_payload` and
its existing `EnrollmentJournal`. No second repair state engine exists.
`machine recover --approve-recovery` reconciles only that owner's pending
runtime transactions against re-derived allowed targets. It grants no new repair
selection. Later foreign bytes remain untouched, including when rollback cannot
finish. Preserve the original journal and failure evidence; do not delete a
journal or release another session to obtain a clean diagnostic.

## Versioned campaigns on real native events

The operator may declare an inert `campaigns.json` in the existing synthesis
configuration directory. Its schema is:

```json
{
  "schema": 1,
  "campaigns": [{
    "id": "review-installed-records",
    "version": 1,
    "not_before": "2026-01-01T00:00:00+00:00",
    "expires_at": "2027-01-01T00:00:00+00:00",
    "clients": ["codex", "claude", "muse"],
    "minimum_release": "4.0.0",
    "maximum_release": "5.0.0",
    "projects": [],
    "notice": "Review the selected project and report concrete findings.",
    "action": "refresh-and-report",
    "mode": "report-only"
  }]
}
```

This example does not activate a campaign. There are at most 64 campaigns in
128 KiB, one declared version per ID. Version, time range, client, exact release
range (minimum inclusive, maximum exclusive), and optional project IDs determine
applicability. An unknown release or unproven native project is UNKNOWN, not a
match. Project identity comes only from the existing exact native coordination
seat. The supported action vocabulary is `refresh-and-report`, `review-machine`
and `review-project-migration`; no command text is executable policy.

`campaign status --client <client> --release <X.Y.Z> [--project <id>] --json`
is a nonmutating applicability report. Its explicit arguments do not prove native
execution. Actual bound SessionStart receipts can carry selected notices; pending
transcripts and static probes cannot acknowledge them. The hook emits at most
4 KiB of campaign notices and explicitly counts omitted eligible notices. It
uses each client's existing native receipt owner; dormant sessions remain
NOT_NOTIFIED. Selection for a notice is not proof a person or agent read it.

`campaign report --event <original-native-event> --native-payload <payload>
--id <campaign> --version <integer> --outcome <outcome> --detail <text>` records
one immutable response to that exact native event and campaign digest. Outcomes
are `acknowledged`, `blocked`, `reported-complete`, and `not-applicable`.
The original event, exact native transcript identity and current applicability
must still agree. Notices also recheck current applicability and content before
emission; expired or replaced campaign selections are not replayed. Identical repeat reports are no-ops; a conflicting report at
the same identity refuses. Reports are kept beneath that native receipt's
`campaign-reports` directory, with the event hash and campaign digest. They do
not replace project records or certify acceptance. Reporting completion remains
reported evidence; the binding identifies the retained native event and does
not prove that the reporting process is a presently running native agent. Native
receipt serialization has a five-second wait, with no stolen locks. No report
runs an action, approves effects, changes native
trust, or establishes a successful installation.

Campaign files, report details, migration previews and inventories can contain
private project metadata. Keep them in the appropriate private local/project
custody. Public fixtures and documentation use synthetic examples only.

## Selected project upgrades

Follow the [project migration protocol](../../synthesis-project-management/references/project-migration.md).
An ecosystem release version never substitutes for a project format version.

A malformed or unreadable optional catalog refuses campaign selection/reporting.
It does not erase an otherwise genuine native delivery receipt: that receipt
retains a bounded `campaign_notice_error` with `REFUSED` and no execution authority.
The hook emits an explicit unavailable notice, including when catalog corruption
is detected after selection. Core native provenance and protective gates are
unchanged; catalog refusal is never recorded as campaign acknowledgement or success.

The same optional boundary contains a missing or broken campaign module and
records its refusal without erasing base delivery evidence. Mandatory native
identity, base receipt persistence and protective owner failures still propagate;
this containment never converts those failures into a successful receipt.

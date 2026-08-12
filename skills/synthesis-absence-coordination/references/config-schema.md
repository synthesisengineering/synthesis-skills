# Config schema reference

Field reference for `~/.synthesis/absence-coordination/config.yaml`. A fully commented
starting point is [`../example-config.yaml`](../example-config.yaml); validate any config
with `python3 validate_config.py <path>`.

Exit codes: `0` valid · `1` defects · `2` could not establish ground truth.

---

## `principal`

| Field | Type | Notes |
|---|---|---|
| `name` | string | Used in drafts. |
| `timezone` | IANA string | Home time zone; the baseline for continuity-tier offsets. |
| `travel_verified_address` | email | **The address verified on your travel service.** Must equal `integrations.travel_service.must_send_from` — the validator fails on mismatch, because the failure it causes is silent. |

## `absence_types`

Map of type name → spec. Four are conventional (`vacation`, `conference`, `family_visit`,
`quiet`); add your own freely.

| Field | Type | Notes |
|---|---|---|
| `lead_time_days` | int | Deadline for the full announcement. |
| `notify_on_commit` | bool | Fire the immediate cohort as soon as the plan is real, independent of lead time. This is what prevents conflicts — it lands before conflicting things get scheduled. |
| `visibility` | `standard` \| `minimal` | `minimal` suppresses group posts and wide announcements. |
| `travel` | bool | Enables itinerary forwarding and the continuity tier. |

`notify_on_commit_tiers` (top level) lists which tiers hear on commit. Keep it small.

**At least one type should be `minimal`.** The validator warns otherwise: a system that
can only broadcast is abandoned exactly when discretion matters most.

## `recipient_tiers`

List of tiers. Order in the file is not execution order — gates and tier semantics are.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique. Referenced by `cc`, `notify_on_commit_tiers`, `coverage.required_before`. |
| `channel` | `email` \| `chat` | `chat` tiers are gated behind principals. |
| `send_mode` | `draft_only` \| `agent_send_after_approval` | The `principals` tier **must** be `draft_only`. |
| `members` | list[email] | Explicit recipients. **Not a distribution alias** — the validator warns on alias-shaped addresses. |
| `targets` | list[string] | Chat channels, for `channel: chat`. |
| `cc` | string | Supports `tier:<id>` to cc an entire tier. The ordering fix is `cc: tier:exec_assistants` on `principals`. |
| `content` | policy | See below. |
| `gate` | `after_principals` | Required on chat tiers. |
| `research` | map | `lodging_facilities: true` on the continuity tier. |
| `cadence` | string | e.g. `daily` — drives per-day slot proposals. |

### Content policies

Disclosure is mechanical, set per tier, so it is never re-decided under time pressure.
When in doubt, the narrower policy wins.

| Policy | Includes |
|---|---|
| `dates_only` | When. Nothing else. |
| `dates_city` | When and where. |
| `dates_city_coverage` | Adds who decides in your absence. |
| `dates_city_coverage_reach` | Adds how to reach you. Fullest policy. |
| `dates_coverage_reach` | Coverage and reachability without location. |
| `dates_child_logistics` | Co-parenting specifics. |
| `dates_timezone_facilities` | Continuity tier: **time zone** (not city), lodging, researched facilities. |

## `calendars`

| Field | Notes |
|---|---|
| `personal`, `work_ooo`, `family_visible` | Primary calendars. |
| `also_check` | Every additional calendar swept for conflicts. |
| `outside_mirror` | Calendars **not** covered by a cross-calendar blocking tool. These block nothing elsewhere and are invisible exactly when you check for conflicts. List them or they will be missed. |
| `shared` | Team/leadership vacation calendars. `status: unknown` until the URL is known; the validator warns. |

## `integrations`

`travel_service` — `enabled`, `forward_to`, `must_send_from`, `verify_trip_created`.
Most services silently discard mail from unverified senders: no bounce, no trip, no
symptom. Always verify the trip was created.

`out_of_office` — `enabled`, `set_on_departure`, `clear_on_return`. Set the clear.

## `coverage`

| Field | Notes |
|---|---|
| `source` | `external` (supplied by whoever owns the org context — the skill will not invent coverage) or `inline`. |
| `required_before` | Tiers that must not be notified until a coverage statement exists. |

## `gates`

Enforced, not advisory. A failing gate blocks the step. The five core gates:

- `no_group_post_before_principals_notified`
- `no_send_before_conflict_check_all_calendars`
- `no_send_before_coverage_statement_present`
- `principal_tier_is_draft_only`
- `amendments_update_existing_rows_never_repost`

## `ledger`

`path` — where notification rows are written. Reuse an existing drafts ledger if the
workspace has one rather than creating a parallel mechanism.

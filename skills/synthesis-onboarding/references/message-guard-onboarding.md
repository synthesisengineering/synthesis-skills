# Reviewed correspondence setup

A full profile selects correspondence protection. Fresh setup requires explicit transport capabilities and an attributed review of the effective configuration. Skills-only and modular profiles do not acquire this requirement unless they select that layer. Missing inputs make the full profile **NOT_CONFIGURED / needs owner input**. Setup preserves existing configuration, engines, hooks and pending evidence; it never makes an unconfigured guard appear healthy.

## Agent-driven owner workflow

1. Inspect the selected clients' actual tool descriptors. For each correspondence tool that will be configured, record its exact name, channel and body/format mapping. A name or read-only hint cannot establish a capability. Record catalog authentication or pagination gaps; this finite setup does not establish a complete native inventory or authorize broad dispatch.
2. Put those declarations under `message_guard.capabilities` in the ordinary onboarding answers. Keep the HTML default and no intra-paragraph breaks. A deliberate owner policy override belongs in `message_guard.email_policy`; it is never inferred from a transport's limitations.
3. Run the installed owner's read-only plan: `python3 /absolute/selected-release/skills/synthesis-onboarding/scripts/onboard.py message-guard-plan --answers /absolute/answers.json`. This creates no home state. Inspect `effective_configuration`, `unsupported_transports`, and the exact `configuration_sha256`.
4. After the actual owner review, set `message_guard.reviewed_configuration_sha256` to that digest and `message_guard.owner_review` to an attributed `source` and a timezone-aware, nonfuture `reviewed_at`. Do not invent a human approval or silently carry a review across changed configuration bytes. The attribution documents the review; it is not an authenticated assertion that a human read it.
5. Run normal `synthesis setup --profile full --answers /absolute/answers.json` for the selected clients. The owner validates the complete effective policy, creates private config and the existing digest-bound activation record exclusively, rechecks them, installs the engine and merges only its hook. No old grounding ledger is translated into a new approval.
6. Run `synthesis doctor` and inspect per-layer readiness. A stored declaration is not actual tool loading, provider access, successful delivery, hook trust, or a client restart. Those require their own acceptance evidence.

A declaration for a schema that really exposes `body` and `body_format` may look like this; substitute the exact observed tool name, not a guessed transport name:

```json
{
  "message_guard": {
    "capabilities": [{
      "tool_names": ["mcp__observed_server__observed_email_tool"],
      "channel": "email",
      "body_field": "body",
      "format_field": "body_format",
      "html_value": "html",
      "plain_value": "plain"
    }]
  }
}
```

The example is incomplete review input and cannot activate a guard. A fixed-plain tool instead requires its true `fixed_format: "plain"` declaration and no format selector. Under the HTML default it stays explicitly unavailable; other correctly mapped HTML transports remain usable. Changing the global default just to make one transport pass is not part of setup.

## Retained state, restart and recovery

Existing configuration always goes through `--migration-plan` / `--migration-preflight` under its owner. Fresh setup refuses a nonempty state directory or existing message hooks rather than adopting them. Configuration and activation-record creation are separate durable exclusive writes, not a claim of a multi-file atomic transaction. If interrupted between them, the retained config stays unactivated; the next attempt refuses and the owner inspects exact state, prepares the actual migration record, and resumes. No retry deletes, overwrites or adopts the interrupted evidence.

A successful repeat preserves the reviewed config and activation record. Changed pending custody during an engine migration requires a new owner record; unchanged configuration cannot justify migrating stale approvals. Desired state retains the explicit selection so repair can recover the input, but current owner config and its migration gate retain authority. Standalone installation uses the same owner plan/preflight before wiring. Copying the example template alone is never a completed installation.

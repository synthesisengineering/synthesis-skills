# Constructing a grounding envelope

Use the existing message guard's `--build-ledger` mode with JSON containing
`tool_name`, complete `tool_input` and `grounding`. The builder computes the same
canonical cross-field digest as the actual send guard, preserving HTML/plaintext
parts, recipients, attachments and tool identity. It supplies the timestamp;
do not construct an independent hash or assert every check passed by default.

Grounding names channel, recipient, reply status, claims or an explicit no-factual-
claims flag, voice/precision/address/branding checks and the actual thread/history
attestations required by the selected route. Explicit false values stay false.
The builder refuses invented hash/time fields and malformed booleans. Its output
is a proposed envelope, not approval or proof that sources were read.

After actually completing the required checks, pass the envelope to the existing
`--write-ledger` owner. Its input validation, file boundary, fresh single-use claim,
pre-send validation and effect approval still apply. Building an envelope neither
writes the ledger nor sends anything. Route email composition through the existing
complete multipart contract and capability-aware inventory; no transport name is
itself proof that a tool is read-only or supports a required field.

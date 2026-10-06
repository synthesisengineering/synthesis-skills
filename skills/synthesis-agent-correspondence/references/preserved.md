# Preserved: sentences replaced in 4.0.1

4.0.1 (2026-10-05) replaced the sentences below because they named send-guard machinery
that v5 removed: the grounding ledger the composing agent wrote about itself, capability
enrollment, `--message-sha` binding, and the `--build-text` and `--verify-text-readback`
commands. In v5 `synthesis-message-guard` scans the text and then requires the principal's
approval of the exact call; the research the ledger attested is the composing agent's own
duty (message-guard binding rule 2). Each rule these sentences served is kept in the new
wording: [coverage-map.md](coverage-map.md#changed-in-401) says where. Nothing here is
current procedure.

## SKILL.md, binding rule 11

```text
11. **Bind and verify every send.** Load `synthesis-message-guard` for construction and the ledger, and verify the actual raw readback after an authorized draft or send.
```

## references/gates-and-sending.md

Three gates, opening paragraph (its last sentence changed):

```text
The lanes say *what* to disclose. These gates protect the *work* underneath the disclosure — a message can be honestly labeled and still be wrong, stale, or off-voice. All three are substance, not enforcement; `synthesis-message-guard` (below) is what makes them mechanical instead of optional.
```

Email construction and verification, second paragraph:

```text
Load `synthesis-message-guard` for construction, capability enrollment and the
complete tool-input ledger. Ground every populated alternate part; bind the
final recipients, subject, body, thread fields and tool name with `--message-sha`.
After an authorized draft/send, verify its actual raw readback and preserve the
message ID and provenance. Do not call a synthetic MIME roundtrip a native send,
a filed draft or delivery confirmation. Route catalog changes to the existing
configuration owner, preserving unrelated hooks and non-email workflows.
```

Other human-readable posts:

```text
Other human-readable correspondence follows the same overridable default for
paragraphs. Use `--build-text` for literal prose and `--verify-text-readback`
after an authorized post. Intentional code, poetry and address blocks require
an owner-approved paragraph-policy override; never normalize significant
whitespace. Retain post IDs, retrieval evidence and any missing-readback gap.
```

Related, the message-guard entry:

```text
- [`synthesis-message-guard`](../../synthesis-message-guard/SKILL.md) — the mechanical enforcement layer: a fail-closed pre-send hook that blocks a send unless a fresh grounding ledger attests the gates above actually ran. This skill states the conventions; message-guard is what makes them impossible to skip.
```

## references/personas-and-adoption.md, adoption step 5

```text
5. **Wire the three gates to your own voice/style skill(s)**, and to `synthesis-message-guard` if you want fail-closed enforcement rather than a convention that depends on being remembered. If your guard has brand-integrity patterns, make them lane-aware: block each persona's emoji when its own branding is absent, rather than banning an emoji outright.
```

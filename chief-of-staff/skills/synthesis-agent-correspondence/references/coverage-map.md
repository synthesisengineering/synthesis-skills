# Coverage map: agent correspondence 3.1.2 to 4.0.0

Every part of the 3.1.2 SKILL.md and where it lives now. Nothing was removed. `scripts/test_signature_channels.py` is unchanged and still passes: every phrase it reads is in SKILL.md, because the section it pins stays there whole.

| 3.1.2 section | Now |
|---|---|
| Frontmatter description (605 characters) | Shortened to 297 characters, keeping the three lanes, the voice axis, review depth, personas, disclosure signatures, the send gates and the triggers "sending on a principal's behalf", "message signatures", "persona registries", "agent voice". The full text is quoted below |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on` (synthesis-chief-of-staff and synthesis-absence-coordination depend on this skill), and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title | SKILL.md (verbatim) |
| The core principle | references/lanes-and-voice.md (verbatim). Its closing blockquote ("Disclosure should answer...") is also quoted in SKILL.md, under a new one-sentence purpose line |
| The two questions, and the three lanes, with the lane table and legend | references/lanes-and-voice.md (verbatim); Binding rule 1 |
| The assistant lane requires exact-text ownership | references/lanes-and-voice.md (verbatim); Binding rule 2 |
| The bot lane spans direction depths | references/lanes-and-voice.md (verbatim) |
| The voice axis (v3.0.0), with the bot-voice composition rules | references/lanes-and-voice.md (verbatim); Binding rules 3 and 4 |
| Review depth, the hard content limits and the two routing rules | references/lanes-and-voice.md (verbatim); Binding rules 5 and 6 |
| Persona registry, with the schema and field list | references/personas-and-adoption.md (verbatim apart from one link path, below); Binding rule 7 |
| Archetype is binding, with the example signatures | references/personas-and-adoption.md (verbatim) |
| Channel disclosure is a fact, not a preference | references/gates-and-sending.md (verbatim); Binding rule 8 |
| Signature links render natively per channel (v3.1.0), with the v3.1.1 send-path paragraph | SKILL.md (verbatim, whole); Binding rule 9. It stays because `test_signature_channels.py` reads it from SKILL.md |
| Three gates, 1 to 3 | references/gates-and-sending.md (verbatim); Binding rule 10 |
| Adopting this for yourself | references/personas-and-adoption.md (verbatim). Its step 4 says "the hard limits above"; those limits are in references/lanes-and-voice.md, under Review depth |
| Migrating from earlier versions of this skill | references/personas-and-adoption.md (verbatim) |
| Related, and the private-companion paragraph | references/gates-and-sending.md (verbatim apart from link paths, below), placed after the gates so the gates' "`synthesis-message-guard` (below)" still points down the same file |
| Email construction and verification, and the paragraph on other human-readable correspondence | references/gates-and-sending.md (verbatim); Binding rule 11 |
| references/persona-registry.example.yaml | Unchanged; now listed in Contents |

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports five lines. All five are text moved into `references/` whose relative links gained one level so they still resolve; the wording is unchanged:

- Persona registry: "A fuller, commented template is in [`references/persona-registry.example.yaml`]..." The link target became `persona-registry.example.yaml`, since the file now sits beside it.
- Related: the four bullets for synthesis-message-guard, synthesis-content-quality with synthesis-writing-pitfalls, synthesis-writing-craft, and synthesis-disclosure-policy. Each `../synthesis-x/SKILL.md` target became `../../synthesis-x/SKILL.md`.

## The 3.1.2 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-agent-correspondence
description: >
  Compose and send honest agent correspondence across Slack, email, and other channels. Defines
  principal-direct, assistant, and bot lanes; the voice axis (chief-of-staff personas speak as
  the principal, executive-assistant personas speak as themselves); review-depth governance;
  persona configuration; disclosure signatures; and compose/send gates. Use for agent
  correspondence, sending on a principal's behalf, message signatures, disclosure lanes, persona
  registries, agent branding, agent voice, third-person agent messages, standing-direction
  sends, ghostwriting disclosure, or outbound-message gates.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "3.1.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## Changed in 4.0.1

The final v5 sweep (2026-10-05) replaced six passages that told an agent to use send-guard
machinery v5 removed (the grounding ledger, capability enrollment, `--message-sha`,
`--build-text`, `--verify-text-readback`). Each old passage is verbatim in
[preserved.md](preserved.md). The rule each served is kept:

| Where | Old | Now | Rule kept |
|---|---|---|---|
| SKILL.md binding rule 11 | "Bind and verify every send": construction and the ledger, raw readback | "Get the exact call approved, then verify it": construction and the principal's approval of the exact call, readback through the transport | Every send is bound to what was reviewed and read back after it goes |
| gates-and-sending.md, Three gates, opening | message-guard "makes them mechanical instead of optional" | message-guard enforces the scan and the exact-call approval; the gates stay the composing agent's job, because no approval shows whether the thread was read | The gates are substance and must run every time |
| gates-and-sending.md, Email construction, paragraph 2 | capability enrollment, tool-input ledger, `--message-sha` binding, raw readback, catalog changes | freeze the complete call before approval (any change needs a new one), read back through the transport, route `send_tools` changes to the config owner | Ground every alternate part; bind the exact recipients, subject, body and thread fields; keep message ID and provenance; never call a synthetic roundtrip a send; preserve unrelated hooks |
| gates-and-sending.md, other posts | `--build-text`, `--verify-text-readback`, paragraph-policy override for code, poetry and address blocks | the guard's chat paragraph rule; fenced code keeps its lines; read each post back; `message_format.allow_line_breaks_in_paragraphs` for poetry and address blocks | Whole paragraphs by default, an owner-approved override for line structure, never normalize significant whitespace, retain post IDs and readback gaps |
| gates-and-sending.md, Related | "a fresh grounding ledger attests the gates above actually ran" | "blocks a send until the text passes the register and format scan and the principal approves that exact call" | message-guard is the mechanical layer under these conventions |
| personas-and-adoption.md, adoption step 5 | wire the gates "to `synthesis-message-guard`"; "your guard has brand-integrity patterns" | configure message-guard's register patterns; "your register patterns include brand-integrity rules" | Fail-closed enforcement over convention; lane-aware brand-integrity rules |

SKILL.md also lists [preserved.md](preserved.md) in Contents; version 4.0.0 became 4.0.1.

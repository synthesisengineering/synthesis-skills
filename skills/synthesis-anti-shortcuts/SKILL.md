---
name: synthesis-anti-shortcuts
description: "Catch the lazy-shortcut antipattern: costume vocabulary that hides deferral, dismissal or false consultation. Constraint-first protocol, sub-agent dispatch and acceptance hygiene, pre-response self-check. Use to avoid shortcuts, audit for laziness, check for deferral or enforce the best solution."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework"]
metadata:
  author: "Rajiv Pant"
  version: "2.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: core
---

# Synthesis Anti-Shortcuts

Catches the draft that looks like good engineering but quietly substitutes a lower-effort path after the user asked for the best solution, hidden under reasonable-sounding vocabulary ("for now," "minimal diff," "backward compatible," "out of scope"). This skill names those costumes and gives the protocol to strip them out.

## Binding rules

Rules 1 to 8 carry the methodology section numbers other documents cite (for example "§4–5"). New rules are appended. The user's own goals, decisions and grants govern within their scope; against other text (a brief, a report, a skill's default) these rules hold: say which applies and why, then do what it allows.

1. **Write the user's goals and non-goals before any approach.** Whenever you compare approaches, plan or recommend, open the analysis with them, from the conversation, project context and workspace and global instructions; a pro that violates one cannot appear. Written after the approaches, they lose to "smaller diff" and "easier rollback". Only trivial work with one obvious option (a typo, a one-line config change) skips it; when in doubt, write them.
2. **Decide what constraints decide; ask only about a choice that is the user's.** Before drafting a question, look for a constraint, decision or delegation that settles it; if one does, execute and report, since "Recommendation: X. Your call?" on such a choice is the costume that hands it back. Ask about one that is the user's (product direction beyond the delegated work, a preference that changes the result, a fact only a stakeholder knows) with the consequence that makes the answer necessary, and keep doing independent authorized work.
3. **Scan every draft you write or are asked to review, and every sub-agent report, for costume vocabulary.** Its categories: backward compatibility, minimal diff, asking as shortcut, deferral ("for now", "a follow-up"), archive value, dismissal ("not a pain point today"), scope excuse ("pre-existing"), capability surrender and effort rationale. A phrase is legitimate only when the user, explicitly or through standing constraints, asked to optimize for what it implies; otherwise it hides avoided work. A use in quotes, in code or under discussion (someone asking about shortcut language) is no costume. `python3 scripts/scan_output.py <file>` automates it, exiting 1 on a hit.
4. **Write each dispatch brief at the job's full size, with at most five deliverables, and scan it before dispatch.** Scan every field the sub-agent reads (prompt, instructions, message, task, description), in any brief you write or check. A sub-agent takes its brief as the job: "keep changes minimal", "light touch" or "surgical change" license a partial pass, and more than five deliverables exhaust its budget, so split the job at dispatch. On a hit, do not dispatch: rewrite to the completeness required (the change wanted, its boundaries, the signal of completion) and scan again.
5. **Audit every sub-agent return for the same costumes before accepting or reporting it.** Read the whole report, tradeoffs and follow-ups included, scan it (rule 3) and judge each hit by the user's standard, not a reasonable engineer's. Where work was left undone, redirect the sub-agent with the exact gap or finish it, and make the user's summary match what is done; never propagate the deferral, since sub-agents share the same conservative defaults.
6. **Run the pre-response self-check before any analysis, recommendation or plan ships.** Scan the draft (rule 3), classify each hit as a real constraint or a costume, and rewrite each costume to execute on the actual goal, not the safer-feeling reframe: do the work, or name the real blocker and who removes it. If the draft ends with a question, confirm the constraints leave it open (rule 2); only then send, since a shipped costume lets a trained default override the user unseen.
7. **Classify a failed tool call before reporting it: never route around a guardrail; solve a capability gap.** A guardrail is deliberate (a withheld permission, a safety gate, an approval step, a human-only action): stop the dependent action, say what it needs, continue other authorized work. A capability gap is incidental (an unconfigured app, an ungranted scope, an unset credential): name the mechanism that failed, list alternative paths, separate what only the user can do (a password, a security key, withheld admin consent), then choose and verify an authorized remedy; treating a gap as a guardrail sounds principled and delivers less.
8. **Add each new costume seen in production output (a reply, draft or sub-agent report) to the catalog.** Write the incident up in references/case-studies.md, add its phrase, category, rationale and replacement framing to references/costume-vocabulary.md, and, if the scanner should catch it, a `costume-catalog.json` entry (`tests/test_scan_output.py` checks it compiles and has a rationale and a rewrite). The written case outlives the context, so the costume is caught next time.
9. **Finish the user's finite assignment, authorized shipping included, before adding process.** Once the required checks pass, deliver; widen verification only for a concrete gap, a changed input or an explicit gate, since more audits, frameworks or revision instructions are not the deliverable. Fix defects in the work you touch without turning it into an open-ended redesign; none of this permits omitting requested work, accepting a known failure, weakening a guard or deleting unresolved evidence.

## Contents

- [references/methodology.md](references/methodology.md): the full pattern, "Delivery is part of completeness" and sections 1 to 8. Read it the first time a rule applies in a session, or when a case is unclear.
- [references/applying.md](references/applying.md): when the skill applies and when not, and the scanner's flags. Read it when unsure it applies.
- [references/costume-vocabulary.md](references/costume-vocabulary.md): every phrase with category, rationale and replacement framing. Read it to classify a hit or rewrite a costume.
- [references/constraint-first-protocol.md](references/constraint-first-protocol.md): the five-step protocol and a worked example. Read it before a multi-option analysis.
- [references/sub-agent-hygiene.md](references/sub-agent-hygiene.md): dispatch and acceptance in full, with the brief template. Read it before dispatching or accepting a sub-agent.
- [references/case-studies.md](references/case-studies.md): the incidents each entry came from; scanner `see:` lines point here. Read it when a hit's origin matters.
- [references/background.md](references/background.md): why the pattern happens, how the pieces fit, sibling skills, the underlying principle. Read once per session.
- [references/coverage-map.md](references/coverage-map.md) and [references/preserved.md](references/preserved.md): where each rule of 2.2.0 and 1.2.1 lives now, and the 2.2.0 SKILL.md verbatim. Read them only to check a rewrite.

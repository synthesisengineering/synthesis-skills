---
name: synthesis-skill-router
description: Route a request to the correct synthesis engineering, coding, writing, project-management, knowledge, operations, or agent-governance skill while keeping specialist metadata out of Codex's bounded prompt. Use when a task appears to match a synthesis workflow but the user did not name the exact skill.
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.4.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Skill Router

Choose the narrowest matching workflow, then read its sibling `SKILL.md` completely before acting. Resolve every path relative to this skill's directory. Load multiple skills when the request crosses categories; their `depends_on` declarations remain authoritative.

## Route by outcome

### Projects, context, and agent ecosystems

- Create, find, resume, or manage a project: `../synthesis-project-management/SKILL.md`
- Compact, archive, or repair project context: `../synthesis-context-lifecycle/SKILL.md`
- Refresh state during a long session: `../synthesis-checkpoint/SKILL.md`
- Execute explicit end-to-end delegation: `../synthesis-autopilot/SKILL.md`
- Install or upgrade the ecosystem: `../synthesis-onboarding/SKILL.md`, `../synthesis-skills-manager/SKILL.md`
- Audit Claude, Codex, hooks, plugins, catalogs, or capability parity: `../synthesis-agent-conformance/SKILL.md`
- Configure an LLM workspace or agent: `../synthesis-llm-setup/SKILL.md`, `../synthesis-technical-advisor/SKILL.md`
- Sync machines or protect repository state: `../synthesis-mac-sync/SKILL.md`, `../synthesis-repo-guard/SKILL.md`
- Select model roles: `../synthesis-model-tiers/SKILL.md`

### Software engineering and review

- AGENT HEURISTIC — Conduct a bounded adversarial review, rotate differently shaped
  reviewers, or maintain a finding ledger: `../synthesis-adversarial-review/SKILL.md`
- Plan implementation: `../synthesis-code-planning/SKILL.md`; for unresolved architecture choices also load `../synthesis-preplan/SKILL.md`
- Audit code or a codebase: `../synthesis-code-audit/SKILL.md`, `../synthesis-codebase-review/SKILL.md`
- Integrate multi-contributor work: `../synthesis-code-integration/SKILL.md`
- Review, prioritize, or merge a change request: `../synthesis-pr-review/SKILL.md`, `../synthesis-review-triage/SKILL.md`, `../synthesis-bitbucket/SKILL.md` as applicable
- Run merge-readiness gates: `../synthesis-preflight/SKILL.md`, `../synthesis-implementation-integrity/SKILL.md`
- Install or diagnose repository policy hooks: `../synthesis-git-hooks/SKILL.md`

### Writing, research, and publishing

- AGENT HEURISTIC — Configure or run a rendered-output publication boundary,
  publishable-range contract, or promotion receipt: `../synthesis-promotion-gate/SKILL.md`
- Write or refresh an article: `../synthesis-article-writing/SKILL.md`, `../synthesis-article-refresh/SKILL.md`
- Frame a topic or brief its readers: `../synthesis-content-framing/SKILL.md`, `../synthesis-reader-briefing/SKILL.md`
- Check quality and revise prose: `../synthesis-content-quality/SKILL.md`, `../synthesis-writing-pitfalls/SKILL.md`, `../synthesis-writing-craft/SKILL.md`
- Fact-check or research links: `../synthesis-fact-checking/SKILL.md`, `../synthesis-link-research/SKILL.md`
- Distribute content: `../synthesis-content-distribution/SKILL.md`
- Write executive or very concise communication: `../synthesis-executive-communication/SKILL.md`, `../synthesis-concise-messaging/SKILL.md`
- Profile a voice or coach creative writing: `../synthesis-voice-profiler/SKILL.md`, `../synthesis-creative-writer/SKILL.md`
- Remove text artifacts: `../synthesis-clean-text/SKILL.md`
- Record text integrity, lineage, generation receipts, or provenance without making authorship or watermark-absence claims: `../synthesis-text-provenance/SKILL.md`

### Knowledge and information operations

- Edit and ship a configured knowledge base: `../synthesis-kb-edit/SKILL.md`
- Preserve session facts: `../synthesis-knowledge-capture/SKILL.md`
- Author or validate Open Knowledge Format: `../synthesis-okf/SKILL.md`
- Sync or derive meeting records: `../synthesis-meeting-transcripts/SKILL.md`
- Sync Slack records: `../synthesis-slack-sync/SKILL.md`
- Clean inboxes: `../synthesis-inbox-cleanup/SKILL.md`
- Merge several model responses: `../synthesis-response-merger/SKILL.md`

### Workload, coordination, and communication

- Run day-start, day-end, or gap recovery: `../synthesis-daily-rituals/SKILL.md`, `../synthesis-catchup-ledger/SKILL.md`
- Coordinate an absence: `../synthesis-absence-coordination/SKILL.md`
- Act as chief of staff: `../synthesis-chief-of-staff/SKILL.md`
- Compose or send agent correspondence: `../synthesis-agent-correspondence/SKILL.md`
- Enforce outbound-message safety: `../synthesis-message-guard/SKILL.md`
- Govern disclosure: `../synthesis-disclosure-policy/SKILL.md`

### Reasoning and execution quality

- Structure a non-trivial decision: `../synthesis-thinking-framework/SKILL.md`
- Explore independent expert branches: `../synthesis-tree-of-thought/SKILL.md`
- Detect shortcut reasoning: `../synthesis-anti-shortcuts/SKILL.md`; the effort side, where output does less than the work requires
- Verify a claim, check quote provenance, or prove an absence: `../synthesis-grounding-discipline/SKILL.md`; the truth side, where output claims more than the evidence supports

Do not substitute this routing summary for the selected skill's instructions.

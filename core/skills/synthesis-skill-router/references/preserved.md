# Preserved: the route replaced in 2.0.1

2.0.1 (2026-10-05) replaced the promotion-gate route because it described the gate by
machinery v5 removed: the publishable-range contract and the promotion receipt. The v5
gate scans a built site for configured internal markers before an approved deploy
(`scripts/promotion_gate.py <dist> --config markers.json`), so the route now says that. The
route still points at the same skill, which `synthesis-promotion-gate`'s
`test_prompt_hidden_skill_is_reachable_through_router` checks. Nothing here is current
procedure.

The 2.0.0 route, verbatim (unchanged from 1.5.0):

```text
- AGENT HEURISTIC — Configure or run a rendered-output publication boundary,
  publishable-range contract, or promotion receipt: `../synthesis-promotion-gate/SKILL.md`
```

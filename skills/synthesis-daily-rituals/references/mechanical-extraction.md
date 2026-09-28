# Mechanical ritual owners

Run these through the verified public runtime. They report evidence in their
own bounded domains; interpretation and effect approvals remain with the agent
and existing state owners. Do not copy native credentials into prompts.

| Package | Current owner | Required result |
|---|---|---|
| P1 meeting transcript acquisition | synthesis-meeting-transcripts fetch/export, document tabs and commitment extraction | Declared source IDs, exact full saved transcript/header/body, explicit missing-half and unavailable-source reasons; verbatim primary evidence remains separate from summaries. |
| P2 channel acquisition | synthesis-slack-sync preflight and thread_checker.acquire_channel | Current declared IDs, in-window roots and replies, exact saved files and coverage gaps; no automatic expansion into private conversations. |
| P3 sync arithmetic | synthesis-daily-rituals sync_watermark | Existing begin/window/advance/status owner, exact declared universe, evidence-bound advance, clock zone explicit and unknown coverage blocking. |
| P4 repository status | synthesis-daily-rituals repo_state.py | All declared repositories and branches, cached versus freshly fetched status, ahead/behind counts, BLIND/UNREACHABLE/DECISION/EXCLUDED with a denominator. |
| P5 grounding envelope | synthesis-message-guard message_guard.py --build-ledger | Canonical complete tool-input digest and truthful supplied attestations, checked by the existing single-use write/consume owner. |

For P4, use `synthesis exec-public synthesis-daily-rituals/scripts/repo_state.py
--workspace <absolute-root> --fetch` when this ritual is authorized to fetch.
Without --fetch the result is cached and cannot prove current remote state.
The helper performs no merge, rebase or fast-forward. The existing branch owner
handles a permitted fast-forward after rechecking claims and current state.
Do not overwrite an active seat's checkout. Every fetch is bounded; source and
branch identities are rechecked. An upstream-less branch stays BLIND.

Interpret raw reports without inflating their evidence plane. Test the chosen
package with causal negatives and a legitimate positive case before release,
verify its installed dependencies in each selected client, and retain actual
elapsed/resource measurements. Unknown model-token or energy costs remain
unknown. Script extraction does not prove that a model read every source or
that all future prompts will follow the protocol.

# Durable project delivery

A plain project bus message (`--to <project>`) reaches the sessions of
its time only: seats that claim later never see it in `inbox` (the
claim floor). A **durable** project message additionally reaches any
future owner/contributor seat for the project, however old — the
mode for handoffs that must survive seat turnover.

```bash
ROOT=<synthesis-project-management-root>/scripts/coordination.py
# Post: project addresses only; --durable with a seat handle or
# --free-address is refused.
python3 $ROOT message --from s-6adk-06yc-yqb2 \
  --to synthesis-ecosystem-engineering --durable \
  --text "Defect 4 fixed on main; re-run the drill before release."
# Retire by key prefix once done; only a live owner/contributor seat
# on the message's project may resolve it. The bus stays append-only:
# the resolution is recorded alongside the inbox watermarks.
python3 $ROOT message --from s-6adk-06yc-yqb2 --resolve 9f2c41ab
```

Semantics:

- Delivery is per-seat: each owner/contributor seat sees each
  unresolved durable message once (watermarked like the rest of the
  inbox). Seats with any other role, and seats on other projects,
  never match.
- Resolution is audited: `inbox/resolved.json` records the message
  key plus who retired it and when. Unknown or ambiguous key
  prefixes fail closed.
- The SessionStart/UserPromptSubmit inbox hook reads the same path,
  so durable items surface in the normal session-start board read
  with no protocol change.

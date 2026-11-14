# Knowledge capture: the configuration contract

Read when the config is missing, when setting up a new knowledge base, or when the capture config and a repository's `.agents/knowledge-base.yaml` disagree.

## The configuration contract

All routing specifics live in a PRIVATE config the skill reads at load time:

```
~/.synthesis/knowledge-capture/config.json
```

It maps knowledge **domains** to a target repo, a confidentiality **tier**, and
the OKF bundle path inside that repo; it names the **confidential terms** that
must never reach a public repo; and it records each repo's **push posture**
(auto, or hold-for-approval). This skill is generic and publishable; the config
is neither. If the config is missing, STOP and say so — routing a fact without
the routing table is guessing, and guessing about confidentiality is how a
private fact ends up in a shared corpus.

Run `synthesis-onboarding init` to author the file from the personal workspace
you select, or copy `config.example.json` and validate it with the onboarding
doctor. The public example contains no real repository or confidentiality data.

Each target repository must also carry `.agents/knowledge-base.yaml`. The
private capture config answers **which repository receives the fact**; the
repository contract answers **what may be edited there, which schema applies,
and how the change ships**. Stop if either layer is missing or they disagree on
the bundle path.

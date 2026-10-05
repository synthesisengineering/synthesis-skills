# Executive communication: the kill-list and translation patterns

The six categories to scan for, then worked translations.

## The kill-list

Six categories that read as normal to the writer and as noise (or worse) to the executive reader. Scan for all six before anything ships upward or sideways to a non-technical audience.

### 1. Unexplained codenames and internal project names

Your project's codename is insider vocabulary the reader never agreed to learn. If the reader would ask "what is that?", the name is doing anti-work. Say what the thing does. If the codename must appear because the reader will hear it in other rooms, gloss it inline on first use — once.

### 2. Workflow and tooling vocabulary

Pull requests, merges, branches, repos, staging, CI, QA environments, framework names, cloud vendor names, API mechanics. None of it carries meaning for this reader. Translate to the business action: *finished review and accepted*, *on the internal test site*, *ships on the next scheduled release* — and reserve *live* and *shipped* for work that is actually in front of users.

### 3. Insider praise

Quoting your own team praising your own team's work — or your own in-meeting reaction to it — is not evidence to an outside reader; it reads as manufactured applause. Cut every instance. Show reception through facts an outsider can verify: what shipped, who outside the team adopted it, what happened next because of it.

### 4. Defect and error counts

"Fixed 37 bugs this sprint," "eliminated a recurring class of nightly failures," "caught the issue before launch" — operational exhaust. To the executive it communicates nothing except that things break. If reliability genuinely matters to this reader, state the consequence: what used to go wrong now cannot, and what protects it from recurring. Usually one sentence; often zero.

### 5. Engineering-culture credentials

Open-source contributions, test coverage, tooling choices, methodology names. These signal craft to peers and nothing to this reader — unless the item changes something the reader owns (cost, risk, speed, talent). If it does, state that change; if it does not, cut it.

### 6. Mechanism where consequence belongs

The default sentence describes what changed for the business. Mechanism appears only when the reader must act on it or fund it. "We rewrote the retry logic in the payments worker" is mechanism; "the payment failures customers hit last quarter cannot recur" is consequence. The reader funds consequences.

## Translation patterns

All examples below are invented. Note what the honest ones have in common: several right-column cells use knowledge the left-column sentence does not carry. That is the point — a faithful consequence-translation pulls the consequence from what you know to be true about the work. It never invents one. If you cannot state the business consequence truthfully, the sentence was not ready for this reader.

| The draft says | What the executive reads | Write instead |
|---|---|---|
| Merged 14 pull requests this week | *(nothing)* | This week's changes finished review and are queued for Thursday's release |
| Deployed the new checkout to staging | *(nothing)* | The new checkout is on the internal test site; customers see it after Thursday's release |
| The dedupe job is idempotent | *(nothing)* | The duplicate-detection step gives the same answer every time it runs, so its results can be trusted and audited |
| Project LANTERN cleared its last blocker | What is LANTERN? | The new customer-data feed cleared its last blocker |
| Fixed 37 bugs this sprint | Things break a lot | *(usually: cut. If reliability matters to this reader:)* The checkout failures customers hit last month cannot recur; monitoring now catches that class before customers do |
| Kicked off the API-contract workshop | A meeting about contracts? | The billing and CRM teams met to agree on how their systems share customer data |
| Shipped SSO | *(nothing)* | People sign in with the company account they already have |
| Refactored the invoicing service | *(nothing)* | We reorganized the invoicing code so future billing changes ship in days instead of weeks; nothing customers see changed |

The pattern behind every row: name the actor the reader knows, the action in plain verbs, and the consequence the business feels — truthfully, including the unflattering parts.

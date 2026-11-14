# Sharing policy

What goes into this knowledge base, what stays out, and how information gets in. It follows the synthesis sharing
standard (synthesis-kb-edit, `references/sharing-standard.md`), which explains each part. The parts marked **Yours**
are this organization's own: fill them in. A default is narrowed only in a part marked **Yours**, saying so.

## 1. Who reads it

Every fact here has two audiences, and goes in only when both may read it.

- **The repository's readers.** **Yours:** who they are.
- **The readers of the copy it publishes.** **Yours:** who they are, and what the copy is (an assistant that answers
  from it, a plugin built from it, an export).

## 2. How information goes in

By extraction. Read the source and take its information, not its text; put each fact in the concept that owns it,
updating in place; cite the source of each fact. Convert a whole document only when its full text is the reference
and every part of it passes the test below. Every import's review request says what was left out, by class and
count, and never the facts themselves.

## 3. The test for each fact

Could this fact cause real harm if it left the organization: to a person's privacy, a customer, a contract or a
negotiation, a legal position, the organization's own protected work, or a decision not yet announced?

- **If yes,** leave the detail out, or describe the work generically.
- **If no,** it goes in.
- **If you cannot tell,** it waits: leave it out, count it as "not yet judged", and ask the person the source came
  from.

## 4. What stays out

| Class | Stays out | Still goes in |
|---|---|---|
| 1. Personal and customer data | A person's private contact details, identifiers, health, family and finances; a customer's account records and anything that identifies its data | Names, roles, teams and work contact details already shared across the organization; aggregate figures with no individual in them |
| 2. Individual pay and personnel matters | A named person's pay, rating, review, discipline, health or leave, and the reasons for a departure | That a role exists, who holds it and whom it reports to; an arrival or a departure once announced |
| 3. Job changes before they are announced | Hires, departures, promotions, moves and reorganizations not yet announced to the repository's readers | The change as announced, once it is; the team's work in the meantime |
| 4. Transactions before they are announced | Acquisitions, sales, investments, partnerships and the launches tied to them, not yet announced | The transaction as announced, once it is; that work in an area is under way, described generically |
| 5. Negotiated terms | Prices, discounts, rates, volumes, service levels and other terms agreed with a customer, vendor or partner, and the positions taken while negotiating | That an agreement exists and what it lets the organization do, where that is known across the organization; prices the organization publishes |
| 6. Security details | Credentials, keys, internal addresses and layouts that would help an attacker, open vulnerabilities, and the specifics of an incident under investigation | That a control exists and who owns it; a closed incident's lessons, written so they cannot be used against the organization |
| 7. Legal matters | Disputes, claims, investigations, regulatory inquiries, and advice from counsel or anything else privileged | That legal review is a step in a process, and whom to ask; an outcome once it is public |
| 8. Work held under professional confidentiality or embargo | Work the organization holds under a professional duty or an embargo, until it is released: an audit in progress, unpublished findings, a source's identity, an embargoed announcement | The work once released, as released; that the work exists, where saying so breaks no duty |
| 9. Material another organization shared in confidence | Another organization's plans, figures, documents and terms, shared under an agreement or in trust | That the relationship exists, where that is known across the organization; what the other organization has published |

**Yours:** the classes this organization adds, and any default it narrows, each with what still goes in.

- (none yet)

## 5. Figures

| Where the figure was shared | In the knowledge base |
|---|---|
| Published outside the organization: a public filing, a press release, the public website | Goes in, with its source |
| Shared with everyone in the organization: an all-company meeting or memo | Goes in when both audiences are inside the organization, cited to where it was shared; otherwise it stays out |
| Shared with a group narrower than the repository's readers: a leadership team, a department, a project | Stays out; the work it measures goes in without it ("the project's budget was approved") |
| Shared with a few named people, or in a negotiation | Stays out, with any range, rounding or comparison that would let it be inferred |
| About one identifiable person | Stays out at every level (classes 1 and 2), unless that person published it |

## 6. A project with an element that stays out

The project is still recorded: its purpose, owner, team, systems and progress go in. The element, and anything that
lets it be inferred (a counterparty, a date, a count, a code name that points at it), stays out. When the project's
existence is itself the element, the project waits until it is announced, and its work is described generically in
the meantime.

## 7. How it is enforced

1. The editor applies the test and the classes to each fact while extracting it.
2. The review request lists what was left out, by class and count.
3. The reviewer reads the change against this policy, and the count against the source.
4. The phrase scan (synthesis-kb-edit's `scripts/sharing_scan.py`) is a backstop that cannot see meaning: it holds a
   line that contains a listed phrase, for a person to read against this policy, and misses a fact told in other
   words.
5. The source systems keep what stays out. The knowledge base may say where to ask, never what is there.

**Yours:** where the material in each class lives: the system a person asks instead.

- (none yet)

**Yours:** the phrases the scan looks for. They live in `.agents/knowledge-base.yaml`, under
`confidentiality.backstop_phrases`, not here, so the scan reads one list. They are named when this policy is adopted
(synthesis-kb-edit's `kb_config.py adopt-sharing-policy`, one `--phrase` for each), since a contract that names this
policy with no phrases holds every edit. Everyone who can read the repository can read the list, so it never holds the
very thing it guards.

## Rulings

**Yours:** this organization's rulings on this policy, newest first, each with its date and who made it. A ruling
names a class or a kind of fact, never a fact that stays out.

- (none yet)

## Examples

**Yours:** examples from this organization's own work: a fact that went in; a fact that stayed out, described by its
class and shape, never the fact itself (as a review request counts what it left out), with why; and a project recorded
without its element. Everyone with access to the repository reads this file, and the phrase scan judges it.

- (none yet)

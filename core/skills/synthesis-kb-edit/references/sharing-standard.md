# The sharing standard: what goes into a shared knowledge base

An organization's knowledge base is worth reading only when what its people know goes into it, and safe to keep only
when what could do harm stays out. This standard is the general part of that judgment, the same for every
organization. What is an organization's own (who reads its knowledge base, its rulings, its examples, the classes it
adds or narrows, and the phrases its scan looks for) lives in its repository: a policy file made from
[the template](../assets/sharing-policy.template.md), and two keys of its contract, `.agents/knowledge-base.yaml`.
This text names no organization, and the plugin ships no phrase list.

Contents:
- Two audiences
- How information goes in: by extraction
- One test for each fact
- The classes that stay out, and what still goes in
- Figures, by the level at which they were shared
- A project with an element that stays out
- Enforcement in layers
- The policy file and the contract
- The phrase scan
- Calling the scan from a commit hook and a pipeline
- Adopting the standard

## Two audiences

Every fact in the knowledge base has two audiences:

1. **The repository's readers:** everyone with access to the repository. The contract names them in
   `confidentiality.visible_to`.
2. **The readers of the copy it publishes:** whoever reads the compiled or distributed copy (an assistant that
   answers from it, a plugin built from it, an export). This audience is often wider than the first, and it reads
   without the repository's history or its reviewers.

A fact goes in only when both audiences may read it. The policy names both audiences by who they are.

## How information goes in: by extraction

1. Read the source and take its information, not its text.
2. Put each fact in the concept that owns it (a person's entry, a product's page, a process), updating in place.
3. Cite the source of each fact, in the corpus's citation style.
4. Convert a whole document only when its full text is the reference, such as a policy the organization adopted in
   those words, and only when every part of it passes the test below.
5. In the review request, say what was left out, by class and count: "Left out: 4 facts (personal and customer
   data 3, negotiated terms 1)." Never the facts themselves, and never enough to infer them.

Why: a converted document carries everything in it, including what the test keeps out, and a reviewer cannot see
what was never said. Extraction sends each fact past the test on its own, and the count shows the reviewer what the
editor held back.

## One test for each fact

Could this fact cause real harm if it left the organization: to a person's privacy, a customer, a contract or a
negotiation, a legal position, the organization's own protected work, or a decision not yet announced?

- **If yes,** leave the detail out, or describe the work generically ("a project to combine two billing systems is
  under way").
- **If no,** it goes in.
- **If you cannot tell** (you do not know the level at which it was shared, or whether it has been announced), it
  waits: leave it out, count it as "not yet judged", and ask the person the source came from.

The test is about the fact. Where it was learned does not decide it: a fact heard in a large meeting can still fall
in a class below, and a fact from a small conversation can be harmless.

## The classes that stay out, and what still goes in

The default classes. An organization's policy may add a class or narrow one, and says so in its own part.

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

## Figures, by the level at which they were shared

A figure (a number, a total, a rate, or a date that is itself the news) goes in at the level its audience was given
it, and no wider.

| Where the figure was shared | In the knowledge base |
|---|---|
| Published outside the organization: a public filing, a press release, the public website | Goes in, with its source |
| Shared with everyone in the organization: an all-company meeting or memo | Goes in when both audiences are inside the organization, cited to where it was shared; otherwise it stays out |
| Shared with a group narrower than the repository's readers: a leadership team, a department, a project | Stays out; the work it measures goes in without it ("the project's budget was approved") |
| Shared with a few named people, or in a negotiation | Stays out, with any range, rounding or comparison that would let it be inferred |
| About one identifiable person | Stays out at every level (classes 1 and 2), unless that person published it |

## A project with an element that stays out

A project is still recorded when one element of it stays out. Its purpose, owner, team, systems and progress go in;
the element, and anything that lets it be inferred (a counterparty, a date, a count, a code name that points at it),
stays out. When the project's existence is itself the element, such as a transaction not yet announced, the project
waits until it is announced, and its work is described generically in the meantime.

## Enforcement in layers

No single layer is enough, so there are five, each catching what the one before it can miss:

1. **The editor** applies the test and the classes to each fact while extracting it.
2. **The review request** lists what was left out, by class and count.
3. **The reviewer** reads the change against the policy, and the count against the source.
4. **The phrase scan** is a backstop. It finds the organization's own phrases in what a change adds (its lines, its
   file and folder names, its commit messages), so a name, a code name or a term the editor missed is caught before it
   is published, and it holds for a person any file it cannot read. It cannot see meaning: a fact told in
   other words passes it, and a harmless line that holds a phrase is held for a person to read. A person reads each
   held line against the policy: a fact in a class comes out; a line that is right as it stands stays, and the
   phrase is narrowed or dropped in the contract, in the same review request, so the reviewer sees that too. Never
   reword a line only to get past the scan: that hides a fact from the backstop without deciding it.
5. **The source system keeps what stays out.** Material in a class stays in the system where it lives, with that
   system's own access controls, and the policy names those systems. The knowledge base may say where to ask, never
   what is there.

## The policy file and the contract

The contract names the policy and holds the phrases:

```yaml
confidentiality:
  visible_to: "Everyone in the organization"
  sharing_policy: ".agents/sharing-policy.md"   # the policy file, made from the template
  backstop_phrases:                             # this organization's own; the plugin ships none
    - "zephyr ledger"
```

The policy file is the template with the organization's parts filled in: its audiences by name, its rulings with
their dates, its examples, the classes it adds or narrows, and where the material that stays out lives. Keep it under
`.agents/`, which the editor workflow refuses, so a change to the policy goes through the repository's maintainers
rather than through an edit. The phrases live in the contract, not in the policy file, so the scan reads one list.
Everyone with access to the repository reads the policy, and the scan judges it: its examples and rulings describe
what stays out by its class and shape, never the fact itself, as a review request counts what it left out. The
contract is judged too, all of it but the phrase list, so a fact written into its `notes` is held like any other.

Files only people read, such as images or signed PDFs the organization keeps in the bundle, may be listed by name in
`confidentiality.unread_allowed` (repository-relative globs). The scan holds every other file it cannot read, and a
change cannot exempt its own files: an exemption counts only when the contract before the change grants it too.

Choose phrases that are specific to what stays out in this organization: the terms its people use for material in
each class, and the code names of its work. A phrase so common that most pages use it holds harmless lines until
people stop reading what it holds. Everyone who can read the repository can read the list, so it never holds the very
thing it guards. A contract that names a policy lists at least one phrase: the configuration gate holds every edit
while it names a policy with none, and the scan refuses to run without them, so adopting takes the phrases in
the same step.

## The phrase scan

`scripts/sharing_scan.py` judges what a change adds under the bundle (`bundle_path`): each added line, each added file's
name and folders, and, for a range, each commit message. It judges the policy file too, and the contract's keys and
values, all but the phrase list itself.

```bash
# what a review request adds, and its commit messages (BASE...HEAD: from where HEAD's branch left BASE)
python3 <skill-root>/scripts/sharing_scan.py <repo-root> --range origin/main...HEAD

# what this commit adds, as staged (a pre-commit hook), and its message (a commit-msg hook)
python3 <skill-root>/scripts/sharing_scan.py <repo-root> --staged
python3 <skill-root>/scripts/sharing_scan.py <repo-root> --message .git/COMMIT_EDITMSG

# every line and name of these files, and of every file under these folders (a first pass over a knowledge base)
python3 <skill-root>/scripts/sharing_scan.py <repo-root> source/reference/team.md source/projects
```

**What governs a scan.** The contract under review must be valid, and the one before it governs too: a range is
judged by its base's contract and its head's, a staged scan or a message by HEAD's and the index's, never by the working
tree. The phrases of both are judged, and the bundles of both, so a change cannot take out the phrase that would hold
it, or point the policy at the file that leaks; the scan names any phrase a change takes out of the list. A whole-file
scan reads the working tree's contract and runs the configuration gate first.

It prints one line for each phrase it finds, and a summary, and never more of a line than the phrase:

```
source/reference/plans.md:12: "zephyr ledger"
source/projects/zephyr-ledger.md: name: "zephyr ledger"
.agents/knowledge-base.yaml: notes: "zephyr ledger"
commit 3f2a9c1e4b7d:3: "zephyr ledger"
source/reference/terms.pdf: held, not text: a person must read it
sharing scan: 5 lines held in 3 files read; read each against .agents/sharing-policy.md
```

A file it cannot read as text (neither UTF-8 nor UTF-16 with its byte-order mark: a PDF, an image, a file in another
encoding) is held, unless `unread_allowed` lists it. A named file outside the bundle is listed as not judged. A link is
listed and never followed: it is judged by where it points, as git stores it. Exit status is `0` when nothing is held,
`1` when something is held, and `2` when it cannot run: no contract or an invalid one, a bundle git tracks no file
under (renamed away, or spelled in another letter case, which a disk that ignores case accepts and git does not), no
policy, one that is not there or is still the template as written, no phrases, or a git error, whose own message it
prints.

How a phrase matches: as words, starting where a word starts, in any letter case. Text and phrase are compared alike:
composed (NFKC), with invisible format characters such as soft hyphens and zero-width spaces dropped, typographic
apostrophes and hyphens read as plain ones, and `-`, `_`, `.`, `/` and `\` read as spaces, so a slug, a path or a
snake_case identifier holds a phrase; a capital inside a word starts a new word, so CamelCase does too; and the words of
a phrase may run together (`violetharbor`). A phrase of five characters or fewer must also end where a word ends
("opal" never holds "opalescent"); a longer one may run on ("zephyr ledger" holds "zephyr ledgers"), so list each form
of a short phrase you mean. A phrase wrapped across two lines is held at the line the change adds, also when the other
line is one it leaves as it was.

It needs the Python standard library and the checkout's own `synthesis/yamlish.py`, through `kb_config.py` beside it,
and nothing installed: run it by path from a checkout of synthesis-skills pinned to a release tag.

## Calling the scan from a commit hook and a pipeline

The plugin installs no hook in a knowledge base. The repository's own hook and its pipeline call the scan, so it runs
the same way on every machine and in review.

**Commit hooks.** Two files in the knowledge base's `.githooks/`, named in the contract as `confidentiality.hook_path:
".githooks"`: `pre-commit` judges what the commit adds, and `commit-msg` judges its message. Where synthesis's commit
check is installed, it runs both after its own checks (`synthesis-git-hooks`); add `.githooks/required` so that a
missing `pre-commit` blocks the commit. Elsewhere, point git at the folder once in each clone:
`git config core.hooksPath .githooks`. Both run the scan from the stable runtime synthesis installs
(`~/.synthesis/v5/current`, or `$SYNTHESIS_HOME/current`), which carries kb-edit's scripts; `SYNTHESIS_SKILLS`, when
set, names a checkout of synthesis-skills to run instead, as a machine without synthesis needs.

```sh
#!/bin/sh
# .githooks/pre-commit: the sharing scan over what this commit adds.
scan="${SYNTHESIS_SKILLS:-${SYNTHESIS_HOME:-$HOME/.synthesis/v5}/current}/skills/synthesis-kb-edit/scripts/sharing_scan.py"
if [ ! -f "$scan" ]; then
  echo "pre-commit: no sharing scan at $scan: install synthesis, or set SYNTHESIS_SKILLS to a checkout of synthesis-skills" >&2
  exit 1
fi
exec python3 "$scan" "$(git rev-parse --show-toplevel)" --staged
```

```sh
#!/bin/sh
# .githooks/commit-msg: the sharing scan over this commit's message.
scan="${SYNTHESIS_SKILLS:-${SYNTHESIS_HOME:-$HOME/.synthesis/v5}/current}/skills/synthesis-kb-edit/scripts/sharing_scan.py"
if [ ! -f "$scan" ]; then
  echo "commit-msg: no sharing scan at $scan: install synthesis, or set SYNTHESIS_SKILLS to a checkout of synthesis-skills" >&2
  exit 1
fi
exec python3 "$scan" "$(git rev-parse --show-toplevel)" --message "$1"
```

**Pipeline.** On every review request, check out synthesis-skills at the release tag the organization adopted (one
that has this scan), and scan the range the request adds, its commit messages included. The knowledge base's own
checkout needs the base branch's history, so the range can find where the two parted:

```sh
git fetch --quiet origin main
git clone --quiet --depth 1 --branch "$SYNTHESIS_TAG" https://github.com/synthesisengineering/synthesis-skills.git ../synthesis-skills
python3 ../synthesis-skills/skills/synthesis-kb-edit/scripts/sharing_scan.py . --range origin/main...HEAD
```

A held line fails the step, and so does a scan that cannot run: a backstop that did not run protected nothing.

## Adopting the standard

Adopting is deliberate. Until a knowledge base adopts the standard, its contract names no policy, the phrase scan does
not run, and edits ship as they always have. Naming the policy also switches knowledge capture to sharing by default
(its rule 6), so the contract names a policy only once the policy says who reads the knowledge base.

- **A new knowledge base** made by synthesis-onboarding (`setup.py workspace --new NAME`) starts with the template at
  `.agents/sharing-policy.md`, committed with its other seeds, and a contract that does not name it.
- **Any knowledge base**, new or existing, adopts it with the organization's own phrases:

  ```bash
  python3 <skill-root>/scripts/kb_config.py adopt-sharing-policy <repo-root> --phrase "zephyr ledger" --phrase "violet harbor"
  ```

  With no policy file where `confidentiality.sharing_policy` says (`.agents/sharing-policy.md` when it names no path),
  it writes the template there and stops: fill in the parts marked as the organization's own, at least who reads it,
  and run it again. It never writes over a file that is there, and refuses one that is still the template as written,
  or a folder in its place. It then names the policy and lists the phrases in the contract, in place, keeping every
  line and line ending the contract has, replacing a key left null or empty rather than adding a second, and writes
  the contract only when the result passes the configuration gate. Given no `--phrase` while the contract lists none,
  it writes nothing: a policy named with no phrases would hold every edit. A list the contract already has is changed
  in the contract itself. It refuses a contract that is invalid, or whose `confidentiality` is not a block mapping (it
  prints the lines to add by hand there), and commits nothing: the person reviews and ships the change. It exits `0`
  when the contract names the policy, and `1` otherwise, saying what it wrote, if anything, and what is next.

The order that works: fill in the policy's parts marked as the organization's own and choose the phrases, adopt, run
the scan once over the whole bundle (`sharing_scan.py <repo-root> <bundle_path>`) and settle what it holds, then wire
the hooks and the pipeline.

# What the commit check reads, and how

Each rule names the test that pins it (`tests/test_commit_policy.py`,
`tests/test_commit_check.py`, `tests/test_commit_chaining.py`, `tests/test_line_approvals.py`).

## Contents

- [The hooks and their order](#the-hooks-and-their-order)
- [The staged diff, byte for byte](#the-staged-diff-byte-for-byte)
- [Images](#images)
- [Credentials](#credentials)
- [Private keys](#private-keys)
- [Credential file names](#credential-file-names)
- [Disclosures, and moved text](#disclosures-and-moved-text)
- [Approved lines](#approved-lines)
- [Commit messages](#commit-messages)
- [An entry's own time](#an-entrys-own-time)
- [Claims](#claims)
- [Repository hooks](#repository-hooks)
- [Failing closed](#failing-closed)

## The hooks and their order

`install.py --git-hooks` writes three wrappers into `~/.synthesis/v5/git-hooks/`, each
calling `synthesis/commit_check.py` with its own name in `SYNTHESIS_GIT_HOOK`:

- `pre-commit`: the staged diff, credential file names and claims.
- `pre-merge-commit`: the same, for a clean automatic merge commit, which git otherwise
  commits without running pre-commit. A merge finished with `git commit` after a
  conflict runs pre-commit; a fast-forward creates no commit and runs neither.
- `commit-msg`: the message (git gives pre-commit no reliable access to it).

Its own checks run first; the repository's hooks run only after they pass
(`test_the_synthesis_checks_run_before_any_repository_hook`).

## The staged diff, byte for byte

- Read as bytes from `git diff --cached --no-ext-diff --no-textconv --text --no-renames
  -U0`, so binary attributes, text conversion and external diff drivers can't hide bytes.
- Hunk lengths are followed, so an added line that looks like a diff header stays content;
  a truncated or mismatched hunk refuses (`test_the_diff_parser_follows_hunk_counts_and_quoted_paths`).
- Git-quoted paths (spaces, quotes, tabs, newlines, non-ASCII) are decoded to their bytes
  and never reach a shell (`test_unusual_file_names_cannot_hide_a_credential`).
- A line with invalid UTF-8 is matched through a replacement-character view; it can
  never earn an allowlist exemption, and a path with invalid UTF-8 or a newline never
  earns a path exclusion (`test_invalid_utf8_cannot_hide_a_match_or_earn_an_allowlist_exemption`,
  `test_catalog_paths_skip_exposure_patterns_but_never_credentials`).
- Bounds: 60 seconds for the whole check, 256 MiB of diff (and of each version of an image
  read whole), 1 MiB of message, 32 MiB of staged file read for the key rule. Reaching one
  refuses the commit; staged files are never changed (`test_git_output_is_bounded_in_size_and_time`).

## Images

An image's pixels are compressed bytes, not text: read as lines, they matched short
protected names at random, and four screenshots in one commit needed four approval codes
(2026-10-30). So a path with an added line that isn't UTF-8 text is read whole, the staged
file and its HEAD version, and a PNG, JPEG, GIF, WebP, HEIC or AVIF file is read by its
structure:

- Everything but the pixel data is scanned: PNG chunks other than `IDAT`, `fdAT` and
  `PLTE`; JPEG comments, `APPn` segments (EXIF, XMP, ICC, IPTC) and unknown segments, but
  not the frame, table and scan headers or a scan's coded data; GIF extensions (comments,
  plain text, application data such as XMP) as stored, but not the header, palettes or
  pixels; WebP chunks other than `VP8 `, `VP8L` and `ALPH`, in animation frames too; in HEIC
  and AVIF, every byte but the extents the item table (`iinf`, `iloc`) places for coded
  image items (`hvc1`, `av01` and the other coded types), so EXIF and XMP items, stored
  beside the coded tiles, are scanned. An image sequence (a `moov` box) is read byte for byte.
  Whatever follows the image is scanned as stored, and an image there is read the same way.
- Compressed text is inflated first (PNG `zTXt`, compressed `iTXt` and `iCCP` profiles), so
  its words are read, which the byte scan never could. `tEXt` and `zTXt` are read as
  Latin-1. More than 32 MiB of inflated text in one file reads as malformed.
- The image's added lines are the lines of that text its HEAD version did not carry,
  numbered within the text, and a finding names that line. Credentials, the key rule (which
  reads the same text), exposure patterns, moved text and approvals apply to them as to any
  line.
- A file that doesn't parse exactly (a chunk, segment, block or box that doesn't fit, an
  extent outside the file), and every other format, is scanned byte for byte.

(`test_an_images_pixels_and_coding_tables_are_not_read_as_text`,
`test_the_text_an_image_carries_is_scanned_compressed_or_not`,
`test_an_image_that_does_not_parse_exactly_is_read_byte_for_byte`,
`test_credentials_and_keys_in_an_images_text_block_in_every_repository`,
`test_an_edited_image_is_checked_for_the_text_its_last_commit_did_not_carry`,
`test_image_text_inflates_within_its_bound_and_follows_concatenated_images`.)

## Credentials

Built in: AWS access keys, GitHub tokens (classic and fine-grained), GitLab tokens, Slack
tokens, Anthropic and OpenAI keys, Google API keys, and the access key on a Docs image link
(`googleusercontent.com/...?key=` or `docs.google.com/docs-images-rt/...?key=`, 16 or more characters;
`key=REDACTED` passes), which opens the image to anyone holding the URL. The second host was added after
14 such keys were committed past the first pattern (2026-10-20). The policy's `tier_0_always` adds to them. Every added line in every path is scanned, before path exclusions and allowlist
lines, in every repository class (`test_without_a_policy_credentials_still_block_and_nothing_else_does`).
No credential is ever approvable. The one exception is a vendor's published example key,
passed by its exact value, whole: AWS's documented access key ID and secret access key from
the IAM User Guide, so documentation and tests can show what a key looks like. Any other
value a credential pattern matches, including the example with one character changed, still blocks
(`test_the_published_aws_example_keys_pass_and_a_real_looking_key_blocks`). A test that needs
a value the rules must refuse generates it when it runs (`synthetic_key` in
`tests/test_line_approvals.py`): written into the test file, it would block that file's own
commit, and nothing can approve it.

## Private keys

A private-key header (`BEGIN ... PRIVATE KEY`, any family) blocks only when key body
lines follow it: base64 lines of 40 or more characters, after at most a few blank or
`Name: value` lines (legacy encrypted PEM). A header alone, as in a detection rule, a
policy file or a doc example, passes. The rule reads the staged file, so an unchanged
header with a newly added body still blocks, and an escaped key inside one JSON string
(`-----BEGIN ... KEY-----\nMIIE...`) blocks too. A file name, quoting or a policy-looking
path grants no exemption. A key header is left to this rule whatever the policy's
`tier_0_always` lists for it (`private_key_markers` in any spelling, with or without the
dashes), and the header may name two words (`SSH2 ENCRYPTED`) (`test_a_key_header_alone_is_a_rule_not_a_key`,
`test_a_bare_key_header_passes_whatever_marker_the_policy_lists_and_a_key_blocks`,
`test_a_key_header_followed_by_key_body_lines_blocks`,
`test_an_unchanged_header_with_a_new_body_blocks`,
`test_an_inline_escaped_key_and_a_key_in_a_message_block`).

## Credential file names

Adding, copying or renaming into a file named `.env` or `.env.<anything>` (but not
`.env.example`, `.sample`, `.template`, `.dist` or `.defaults`), `id_rsa`, `id_dsa`,
`id_ecdsa`, `id_ed25519` (not `.pub`), `*.pem`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`,
`.netrc`, `.pgpass` or `.aws/credentials` is refused whatever it holds. A public
certificate can be committed as `.crt`
(`test_credential_file_names_are_refused_whatever_they_hold`). `*.key` is left out:
Keynote documents use it.

## Disclosures, and moved text

Tier-1 patterns for the repository's class (see [policy-file.md](policy-file.md)) are
matched against added lines outside excluded paths and allowlisted lines. A matching line
that already exists, whole, somewhere in HEAD of the same repository is moved or copied
text, not a new disclosure, and passes: splitting a reference file into parts, or copying
an instruction file to its adapter (CLAUDE.md to AGENTS.md), adds no exposure. One
bounded `git grep -F` over the flagged lines decides it. A new line with the same words
blocks, and a credential blocks wherever it moves
(`test_a_line_already_in_head_moves_without_counting_as_a_new_disclosure`,
`test_a_moved_credential_still_blocks`, `test_an_exact_copy_is_not_rescanned_but_an_edited_rename_is`).
Any other hit goes to [Approved lines](#approved-lines).

## Approved lines

No word list can tell a leak from a legitimate mention, and rewording, splitting or
assembling a term at run time to get past the check weakens the text and defeats the
check (the principal's ruling, 2026-10-06). So a hit that is not moved text blocks with a
code, and the principal decides:

1. The block names each line and its code: `ask the principal to type approve followed by
   the code <code>`. It never prints the phrase itself, so no tool output can carry it.
2. The agent shows the principal the line. If it belongs, the principal types approve and
   the code in their own prompt; the prompt hook records the grant.
3. The agent commits again, unchanged. The check spends the grant only if the harness's
   transcript of the session shows the principal typing that code after the block (the
   same proof as an approved send: `synthesis/approvals.py`). A `git commit` run from the
   agent's shell finds the session by the id its shell carries: `SYNTHESIS_SESSION` if
   set, else `CLAUDE_CODE_SESSION_ID` (Claude Code), `CODEX_THREAD_ID` (Codex) or
   `MUSE_SESSION_ID` (Muse; not yet confirmed in its shells, so a Muse agent may need to
   set `SYNTHESIS_SESSION` to its session id). With no transcript the grant is spent
   unused and the commit blocks with the reason
   (`test_a_grant_without_the_principals_prompt_in_the_transcript_does_not_count`).
4. The approved line is recorded and passes from then on: a later commit of the identical
   line in the same file of the same repository needs nothing. An edited line, the same
   line in another file, and the same line in another repository each ask again
   (`test_an_approved_line_passes_later_and_an_edit_or_a_new_place_asks_again`,
   `test_the_same_line_in_another_repository_asks_again_but_another_clone_of_the_same_one_does_not`).

What an approval binds: a SHA-256 over the repository, the path (or `commit message`) and
the line's exact bytes. The repository is its push remotes, normalized (scheme, user,
`.git` and case dropped, sorted), so every clone and worktree on every Mac agrees, and
adding a remote, which changes who reads the repository, asks again. A repository with no
remote is its git folder, written with `~` for the home directory.

The store is a JSON file, `{"lines": {"<sha256>": "<date approved>"}}`: hashes and
dates, never a term or a line (`test_the_store_holds_only_hashes_and_dates`). It is the
file `line_allowances` names in `config.json`, else `line-allowances.json` beside the
commit policy. The check writes it atomically. It is a catalog the scan skips when it
lives in the repository being committed, as the policy and ledger are. A shell command
that writes it is refused by the shell guard; an edit through a file-edit tool is not
guarded (docs/runtime-integration.md, What remains open).

A line that leaks is removed: what it discloses, not only the flagged word. Reviewed
`allowlist_lines` and the ledger stay the principal's tools for whole classes of lines.

## Commit messages

In strict and public-surface repositories the message gets the strict tier-1 set, never
reduced by the ledger: a message names the nature of an edit, which no published
precedent covers, and site commit logs stay generic. Credentials and keys in a message
block in every class. Git's `#` comment lines are not scanned. A message line is
approved the same way as a file line, bound to the repository and the line
(`test_messages_are_scanned_in_strict_and_public_surface_repos_without_ledger_allowances`,
`test_a_credential_in_a_message_blocks_in_every_class`, `test_a_commit_message_hit_is_approved_the_same_way`).

## An entry's own time

Off unless the config has `record_times` (`{}` turns it on; see the guardrails'
[config reference](https://github.com/synthesisengineering/synthesis-skills/blob/v5.22.0/skills/synthesis-agent-guardrails/references/config.md)). In a Markdown
file (`.md`, `.markdown`) outside a folder of transcripts and outside what the setting's
`skip` list names, the check reads the time an added entry gives for itself. An entry
states one in four places:

| Place | Example |
|---|---|
| The line opens with the day and a time, behind a list mark, a ticked box, a heading, emphasis or a bracket. A line with no mark counts where it begins a paragraph | `- **2026-11-12 19:30, the release is out.**`, `### 2026-11-12 14:40 CDT`, `- [2026-11-12 6:54 pm]` |
| A parenthesis opens with the day and a time, or with one of the words below, each saying what was done then | `(11-12 18:54: approved in the dialog)`, `(added 11-12 18:46, ...)`, `(Updated: 11-12 18:46)` |
| In a file under a `sessions/` folder, a list item or a heading opens with a time, and the nearest dated heading above it, outside a code fence, names today | `- 18:54 ET: pushed the branch` |
| The line opens, behind the same marks, with one of the words below and then the time, with a weekday or a day between them or neither. A weekday with no day is read only where it is today's | `**Revised Fri 07:15 ET:**`, `Written 18:52:`, `### Built 2026-11-12 18:47`, `- Released about 18:40` |

**The words,** in any case, with or without a colon: `as of`, `current to`, `added`,
`answered`, `approved`, `asked`, `begun`, `built`, `checked`, `closed`, `completed`,
`corrected`, `counted`, `created`, `decided`, `deleted`, `deployed`, `done`, `extended`,
`filed`, `finished`, `fixed`, `found`, `held`, `installed`, `kept`, `left`, `made`,
`measured`, `merged`, `modified`, `noted`, `opened`, `posted`, `probed`, `proven`,
`published`, `pushed`, `read`, `received`, `recorded`, `refreshed`, `released`, `removed`,
`renamed`, `replied`, `returned`, `reviewed`, `revised`, `ruled`, `run`, `said`, `searched`,
`sent`, `shown`, `started`, `stopped`, `synced`, `tested`, `told`, `updated`, `verified`,
`written`. A parenthesis or a line that opens with any other word names an event, and its
time is the event's: `(scheduled 11-12 18:55)`, `(call 11-12 19:00)`, `(due 2026-11-12
18:55)`, `Standup 18:45`, `Thu 18:45 review`.

The fourth place was added on 2026-11-13, the morning the check first ran for a principal:
a seat committed `**Revised Fri 07:1x ET:** ...` at 07:11 and no stamp was read, since the
line opens with a word and a weekday. Counted over thirty days of commits, 110 added lines
open with one of these words and then a time, and 28 of them round the time or stand a
few minutes after their commit.

The commit is refused when such a stamp is:

1. **1 to 30 minutes after now.** A range is read by its later end, and a 12-hour clock
   by its mark (`pm`, `PM`, `p.m.`). A zone the stamp names is honored: `UTC`, `GMT`, `Z`,
   an offset (`UTC+1`, `-05:00`), and the four regions of the United States by any of
   their labels (`ET`, `EST`, `EDT`, and the same for `C`, `M` and `P`). A winter or
   summer label names its region's clock on that day, since people keep one label all
   year: `10:25 EST` in July is 10:25 on the eastern clock. Labels are read in capitals. A
   time with no label is taken to be this machine's. The stamp is placed by its own day in
   its own zone, so `2026-11-13T00:05Z` written at 18:40 eastern on the twelfth is 25
   minutes ahead.
2. **a rounding of the present:** `18:3x`, `about 18:35`, `c. 18:35`, `~18:40`, `18:40ish`
   or `18:35 (approx.)`, for a moment from 15 minutes back to 30 ahead. The clock could be
   read.

**The half hour is the rule.** Counted over thirty days of real commits while the check
had no bound, every stamp that was later than its commit stood at most 30 minutes ahead
(41 stamps: 18 by 1 to 5 minutes, 18 by 6 to 15, 5 by 16 to 30): a mistaken stamp is a
near miss. A time farther ahead is something else (a deadline, a schedule, a time read in
the wrong zone), and it passes.

It also passes:

- an exact time at or before now, and a rounded time for a moment more than 15 minutes
  old, which may be all the writer knows;
- every time that is not an entry's own stamp: a time inside the text, and a parenthesis
  that opens with a word that is not on the list;
- outside a session log, an exact span that had begun: `### 2026-11-12 18:30–19:00 Weekly
  sync` in the notes written while the meeting runs. In a session log a span is the
  entry's own hours, and its later end is when the entry was written;
- the time an unchecked box opens with (`- [ ] 18:54 call the owner`): a plan, whose time
  is when it is to be done. A stamp in a parenthesis inside one is still read;
- a code fence, where a pasted log keeps its own clock;
- a line with no mark that continues a paragraph: the wrapped rest of the sentence above;
- transcripts (any folder whose name ends in `transcripts`), whose lines carry other
  people's times;
- a zone the check names and does not place (`IST`, `BST`, `CET`, `EET`, `WET`, `JST`,
  `KST`, `HKT`, `SGT`, `AEST`, `ACST`, `AWST`, `NZST`, `AKST`, `HST`, `MSK`, and their
  summer forms), and a region's label on a machine with no zone data;
- a commit that brings lines written before: a merge, a squash merge, a cherry-pick, a
  revert, a rebase that stopped. Their lines were judged when they were first committed,
  by the clock of the machine that wrote them.

No approval clears a refusal: the line states a time that has not come, or rounds one the
clock gives. Read the clock in the command that writes the entry (`date "+%H:%M"`), and
name the zone when the time is in another one. A time that is not when the entry is
written (an event's, a meeting that has not begun, a moment a few minutes back that nobody
timed) goes after the words that say what it is, not at the head of the line or of a
parenthesis: `- the build broke at about 18:30`. The refusal of a rounding says both.

**What it does not see.** A time that is wrong and earlier than the commit (17:40 written
for 17:36, committed at 17:45). A present rounded to a neat quarter hour with no mark of
rounding. A time behind a label (`**Last updated:** 2026-11-12 18:54`). A time in a
parenthesis with no day (`(as of 18:54)`). A day written with a month's name or with
slashes. A zone outside the two lists above, which is not taken for a zone: the time is
read as this machine's. Only reading the clock in the command that writes the time
prevents those.

It was measured before it was built, on thirty days of commits to twenty-seven knowledge
repositories: a time inside an entry's text is later than its commit three times in ten,
and rightly, so only an entry's own stamp is judged. Replayed over thirty days of commits
(1,111) as it stands, it refuses 213 lines in 149 commits (46 later, 167 rounding the
present). Its first form also refused five wrapped lines that began with a
time by chance; its second, before a review, refused deadlines and schedules hours ahead;
its third took any word in -ed at a parenthesis's head for a stamp and any capital word
ending in T for a zone, neither of which those commits bear out
(`tests/test_record_times.py`).

## A status and its evidence

Off unless the config has `status_evidence` (`{}` turns it on; see the guardrails'
[config reference](https://github.com/synthesisengineering/synthesis-skills/blob/v5.22.0/skills/synthesis-agent-guardrails/references/config.md)). On 2026-11-12
obligation statuses said colleagues could use a tool "now" when none of them could: the
status had been written from an assumption, and nothing asked what it rested on. That a
line claims a thing works is meaning, which the check does not read. That a table has a
column headed Status and a column for evidence is the table's own statement, and the
table is held to it.

In a Markdown file the check reads (the same files as for an entry's time: not a folder of
transcripts, not what the setting's `skip` names), for each table row a commit adds:

1. **Refused:** the row's table has a Status column and a column for evidence, and the row
   says something in its status cell and nothing in any column for evidence or any
   column of the second list below. The word `unverified` anywhere in the row is an
   answer. The refusal names the row: say where it was checked (a link, a command, a
   record), or write `unverified`. No approval clears it, so a wrong refusal stops a
   commit with no way through, and few headers can refuse.
2. **Noted, never refused:** the table has a Status column and no column for evidence; the
   row's status says a thing works or is done (`works`, `live`, `done`, `ready`,
   `available`, `shipped`, `released`, `deployed`, `complete`, `enabled`, `passing`,
   `fixed`, `resolved`, `installed`, `running`, a check mark) and does not negate it; no
   cell of the second list is filled; and the row holds no link, no code span and not
   the word `unverified`. A word is negated by `not`, `never`, `no longer`, `cannot` or a
   word ending in `n't`, with at most two words and only spaces between (`not done`,
   `won't be ready`, `isn't live`, `never shipped`, `no longer working`). The commit
   goes through and prints one line for the file: how many such rows, and that the table
   can take a column for evidence. This part reads a list of words, so it only informs.

**The header.** A header cell is read with its emphasis marks, a link's brackets and target
(`[Status](x.md)` reads as `Status`), and a closing colon or parenthesis (`Status:`,
`Status (today)`) taken off. The Status column is the first one headed `Status`, in any
case, alone or after one word (`Current status`, `Deploy status`); a column headed
`State`, or `Status` after two words, is none. Two lists name the other columns, by a word
the header says:

- **a column for evidence**, which can refuse: `evidence`, `proof` or `proofs`,
  `verified`, `how we know`;
- **the second list**, which never refuses: `source` or `sources`, `checked`, `basis`. A
  table whose only such columns are from it is never refused; a row that fills one
  points somewhere and gets no note.

The Status column is never also a column for evidence: in `| Item | Verified status |
Evidence |` the Evidence cell is the one that answers. A review of 2026-11-13 found a lead's
`Source`, a task's `Checked` and a US `State` column refused; none of them can refuse now.

**A cell that says nothing** is empty or holds only spaces, dashes, emphasis marks, `n/a`,
`none`, `tbd`, question marks, a line break (`<br>`, `<br/>`), `&nbsp;`, an ellipsis
(`...`, `…`) or a zero-width character. A status cell that says nothing owes no evidence.

**Which rows are read.** A row is a line with a pipe at each end, read inside any block
quote's marks (`> | a | b |`). Its table is the run of such lines it stands in, at the
same depth of quote, read from the file as staged, once a file, with CRLF line endings
read as LF; the run's first line is the header when the next is a delimiter row: a pipe at
each end and, in each cell, dashes alone, a colon allowed at either end (`|---|`, `|-|`,
`|:-:|`). Not read:

- a table written without its outer pipes (`Item | Status`), or a row missing either one;
- a table in a code fence, or in an indented code block: four spaces or a tab, with no
  list item above it since the last blank line (a table indented under a list item, with
  no blank line between, is read);
- a header with no delimiter row under it, and a header and its delimiter row themselves;
- a row cut off from its header, by a blank line or any line that is no row;
- a status written in prose;
- a commit that brings lines written before, as for an entry's time: a merge, a squash
  merge, a cherry-pick, a revert, a rebase that stopped.

The check cannot know that the evidence is evidence: a cell that says `checked` is filled.
What it changes is that the reader of the record sees what was written there, where
before nothing was asked.

Replayed as it stands over thirty days of real commits (1,110): 12 rows refused in 6
commits, and 11 rows noted in 7. Where a table has a column for evidence it is nearly
always filled: 919 of 931 added rows (`tests/test_status_evidence.py`).

## Claims

Every staged path, both sides of a rename and deletions included, is checked against the
coordination board: a path inside another live session's claim is refused, naming the
holder, its project and goal. The committer is the harness session the shell belongs to
(`SYNTHESIS_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`, `MUSE_SESSION_ID`),
never an id copied from text. With no session identity, unclaimed paths pass and a
claimed path is refused with how to identify. No board on the machine: the commit passes
with a note. A board entry that can't be read: the commit blocks
(`tests/test_commit_check.py`).

## Repository hooks

A global `core.hooksPath` makes git skip every repository's own hooks, so the check runs
them after its own: `.githooks/<hook>`, then `.git/hooks/<hook>`, each once, never itself,
with `SYNTHESIS_REPO_CLASS` set. A repository that declares `.githooks/required` (present
in the working tree, or still listed in the index) blocks when its `.githooks/pre-commit`
is missing, not a regular file or not executable, and names the remedy; withdrawing the
declaration takes a staged `git rm`. An undeclared delegate that is not executable is
skipped aloud (`tests/test_commit_chaining.py`).

## Failing closed

These block the commit with the reason: an unreadable `config.json`; a named policy that
is missing, outside the YAML subset, below `config_version` 2, without tier-0 patterns or
with an invalid pattern; a configured ledger that is missing or malformed, or an entry
without evidence, with an unapproved register or claiming a non-identity pattern (public
surfaces only); approved lines that exist but can't be read, in any repository where
exposure patterns apply (`test_a_store_that_cannot_be_read_blocks`); a malformed diff; a
bound reached; git failing; an unreadable board.
Success is git's exit status; nothing prints a success-looking line on refusal.

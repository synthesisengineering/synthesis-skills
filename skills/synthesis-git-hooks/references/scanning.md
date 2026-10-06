# What the commit check reads, and how

Each rule names the test that pins it (`tests/test_commit_policy.py`,
`tests/test_commit_check.py`, `tests/test_commit_chaining.py`, `tests/test_line_approvals.py`).

## Contents

- [The hooks and their order](#the-hooks-and-their-order)
- [The staged diff, byte for byte](#the-staged-diff-byte-for-byte)
- [Credentials](#credentials)
- [Private keys](#private-keys)
- [Credential file names](#credential-file-names)
- [Disclosures, and moved text](#disclosures-and-moved-text)
- [Approved lines](#approved-lines)
- [Commit messages](#commit-messages)
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
- Bounds: 60 seconds for the whole check, 256 MiB of diff, 1 MiB of message, 32 MiB of
  staged file read for the key rule. Reaching one refuses the commit; staged files are
  never changed (`test_git_output_is_bounded_in_size_and_time`).

## Credentials

Built in: AWS access keys, GitHub tokens (classic and fine-grained), GitLab tokens, Slack
tokens, Anthropic and OpenAI keys, Google API keys. The policy's `tier_0_always` adds to
them. Every added line in every path is scanned, before path exclusions and allowlist
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

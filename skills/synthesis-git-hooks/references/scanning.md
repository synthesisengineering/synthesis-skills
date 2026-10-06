# What the commit check reads, and how

Each rule names the test that pins it (`tests/test_commit_policy.py`,
`tests/test_commit_check.py`, `tests/test_commit_chaining.py`).

## Contents

- [The hooks and their order](#the-hooks-and-their-order)
- [The staged diff, byte for byte](#the-staged-diff-byte-for-byte)
- [Credentials](#credentials)
- [Private keys](#private-keys)
- [Credential file names](#credential-file-names)
- [Disclosures, and moved text](#disclosures-and-moved-text)
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

## Private keys

A private-key header (`BEGIN ... PRIVATE KEY`, any family) blocks only when key body
lines follow it: base64 lines of 40 or more characters, after at most a few blank or
`Name: value` lines (legacy encrypted PEM). A header alone, as in a detection rule, a
policy file or a doc example, passes. The rule reads the staged file, so an unchanged
header with a newly added body still blocks, and an escaped key inside one JSON string
(`-----BEGIN ... KEY-----\nMIIE...`) blocks too. A file name, quoting or a policy-looking
path grants no exemption (`test_a_key_header_alone_is_a_rule_not_a_key`,
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

## Commit messages

In strict and public-surface repositories the message gets the strict tier-1 set, never
reduced by the ledger: a message names the nature of an edit, which no published
precedent covers, and site commit logs stay generic. Credentials and keys in a message
block in every class. Git's `#` comment lines are not scanned
(`test_messages_are_scanned_in_strict_and_public_surface_repos_without_ledger_allowances`,
`test_a_credential_in_a_message_blocks_in_every_class`).

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
surfaces only); a malformed diff; a bound reached; git failing; an unreadable board.
Success is git's exit status; nothing prints a success-looking line on refusal.

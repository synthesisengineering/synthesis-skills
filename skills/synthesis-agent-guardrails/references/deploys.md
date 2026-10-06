# Deploys, destruction, and how the shell is read

The intent (2026-08-20, restating the 2026-03-23 intent behind the old skill-loading
flags): **no change reaches a live site without the principal previewing it and giving
explicit in-chat approval.** The old flag gated skill loading, which was always a proxy;
the dangerous act is the push or deploy itself, reachable with or without any skill
loaded. This guard gates the act.

## Contents

- [What counts as a deploy](#what-counts-as-a-deploy)
- [Approval](#approval)
- [The date rules](#the-date-rules)
- [The rapid-redeploy brake](#the-rapid-redeploy-brake)
- [Destruction](#destruction)
- [How the shell is read](#how-the-shell-is-read)
- [Tests](#tests)

## What counts as a deploy

- A build deploy: a command that starts with a deploy pattern (config.md), after
  wrappers, or the script an interpreter runs (`npx wrangler pages deploy`,
  `python3 -m twine upload`, `node release.mjs deploy` with a matching pattern).
- A push into a repository listed in `push_deploys`, judged by the directory the push
  acts on: `git -C <site> push` from anywhere (2026-08-30, the bypass), `cd <site> &&
  git push`, a subshell, a linked worktree of the site. A plain `git push` to main of
  such a repository is a deploy exactly like `wrangler pages deploy`.
- A push whose repository is named by a variable (`git -C $r push` in a loop,
  `cd $DIR && git push`) while any push-deploy repository is configured: the guard can't
  tell which repository it is, so it asks.
- Not a deploy: `git commit -m "fix site push"` (2026-08-29 false block), `git log` with
  push in its arguments, `echo` or `grep` of deploy words, a heredoc written to a file.

## Approval

A blocked deploy files a request whose code the principal types as `approve <code>`. The
approval binds the exact command text and, for pushes, the commit each target's HEAD is
at: HEAD moving before the run voids it. It lets one run through within 15 minutes. A
command that deploys the same site twice (`git push && git push`) is refused outright:
one approval covers one publish. `synthesis approvals` lists
what is waiting. There is no command to approve: only the principal's own prompt grants.

## The date rules

These hold even for an approved deploy: an approval covers a publish, not a break in the
site's own timeline.

- **No page goes live before its stated date.** A content file whose first `date:`,
  `pubDate:` or `publishDate:` line is more than 15 minutes in the future refuses the
  deploy (a few minutes is clock skew). Dates without a zone are local time; a date-only
  value means midnight. On 2026-08-29 a post dated the next afternoon went live the
  evening before.
- **Published dates never change.** A deploy that changes the date of a page already on
  the published branch (origin's main) refuses, naming both dates. To move a page to a
  new date, take it down in one deploy and republish it at that date in another. If the
  published branch can't be found, the guard asks for `git fetch` rather than guessing.
- **Both layouts:** `content/posts/**/index.md` (nested by date) and
  `**/src/content/articles/*.md` (flat). On 2026-08-31 the flat-layout site was found to
  have escaped the date scans entirely: a guard covers what it reaches, not what it reads.
  A push checks the committed tree at HEAD; a build deploy checks the working tree,
  untracked files included.

## The rapid-redeploy brake

A second deploy of the same site (a linked worktree counts as its main checkout) within
45 minutes of the last approved one is a rapid redeploy. On 2026-08-29 a page went live
early, was re-dated, and was republished 28 minutes later: the rushed follow-up fix is the
riskiest publish there is. The guard refuses with the time of the last deploy and asks
the agent to put the options to the principal first; only an explicit rapid-redeploy
approval lets it through, and it still counts if the window closes before the rerun.

## Destruction

- `rm` with a recursive flag whose target resolves to `/`, home, `~/workspaces`, a folder
  directly in it, a configured protected root, or any directory holding a `.git` is
  refused. A build folder inside a repository is not protected.
- `git push --force`, `-f` or a `+ref` to `main` or `master` is refused; a force push to a
  feature branch is not.
- `git worktree remove` of an ordinary worktree is allowed (the 1.x guard refused it only
  to protect its own manifests).

## How the shell is read

`guards._commands` reads a shell line without running or expanding anything:

- Quotes: single quotes and quoted heredoc tags are literal; `$'...'` has its escapes
  decoded (`$'g\x69t'` is `git`); double quotes and unquoted heredocs still run their
  `$(...)` and backtick substitutions.
- Wrappers and keywords are skipped to find the command that runs: `env` (with its
  assignments, `-u`, `-C`), `command` (but `command -v` is a lookup), `exec`, `nohup`,
  `time`, `nice`, `timeout` and its duration, `sudo`, `xargs`, `npx`, `bunx`, `pnpx`,
  `caffeinate`, `if`/`then`/`do`/`while`/`{`/`!`, and leading `NAME=value` words.
- Code inside code is read as commands: `bash -c '...'`, `eval '...'`, `env -S '...'`,
  `$(...)` and backticks anywhere outside single quotes, and whatever a shell reads from
  its stdin: a heredoc, a here-string, `/dev/stdin`, or a pipe (`printf '...' | sh`).
- `cd` and `pushd` move the working directory for the commands after them; a subshell's
  `cd` ends with it. `#` starts a comment only at the start of a word.
- Text that can't be read (unbalanced quotes, nesting more than six levels deep) is split
  on its separators and judged on its raw words: a deploy word anywhere makes it a deploy
  needing approval; anything else runs. The 1.x guard refused every command it could not
  classify, and blocked a read-only `diff <(...) <(...)` that way during the code
  evaluation.

The Bash hook stays under 50 ms (about 31 ms median measured on the principal's Mac,
2026-10-05).

## Tests

`tests/test_shell_classification.py` (every wrapper, substitution, heredoc and data case,
the unreadable cases, nesting depth, speed), `tests/test_deploy_rules.py` (incident shapes
of a site push, attribution by directory, worktrees, both date rules in both layouts,
approval bound to HEAD, the rapid brake), `tests/test_guards.py` (approvals, protected
roots, force pushes, every harness's shell tool, fail-closed config).

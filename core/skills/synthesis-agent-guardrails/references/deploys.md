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
- [The pull-request gate](#the-pull-request-gate)
- [How the shell is read](#how-the-shell-is-read)
- [Tests](#tests)

## What counts as a deploy

- A build deploy: a command that starts with a deploy pattern (config.md), after
  wrappers, or the script an interpreter runs (`npx wrangler pages deploy`,
  `python3 -m twine upload`, `node release.mjs deploy` with a matching pattern). A versioned
  interpreter (`python3.12`) counts as its interpreter.
- A push into a repository listed in `push_deploys`, judged by the directory the push
  acts on: `git -C <site> push` from anywhere (2026-08-30, the bypass), `cd <site> &&
  git push`, a subshell, a linked worktree of the site. A plain `git push` to main of
  such a repository is a deploy exactly like `wrangler pages deploy`.
- An action sheet's upload by `publish_sheet.py`, unless it is the plugin's own script naming
  exactly one `--project` listed in `sheet_hosts` (config.md; 2026-10-22). That script uploads only
  the generator's page and only behind a verified Cloudflare Access sign-in, so the principal's
  listing stands in for a code. A script of that name anywhere else, or an upload to an unlisted
  project, is a deploy like any other.
- The knowledge base's Drive copy, written by `publish_drive.py` (synthesis-kb-distribution). An edit to a
  Drive file's contents is published in the principal's name, and the guard cannot see what a script sends,
  so the script is named (2026-11-11: it wrote 36 files with no hold). `--dry-run` passes. A script of the
  principal's own that writes to Drive is not seen.
- A shell script a command runs from a file (`bash publish-site.sh`, `./publish-site.sh`, `sh -e wrapper.sh`),
  read up to 256 KB and three scripts deep, when anything in it is a deploy (2026-10-30: `bash
  scripts/publish-site.sh` published a site, because the `wrangler` call inside the script never reached the
  guard). A command named by its path is read only when its first line is a shell's `#!`. A shell whose options,
  read in order up to its script, leave it running nothing (`-n`, `-o noexec`, not undone by a later `+n`,
  `+o noexec` or zsh's `-o exec`) deploys nothing (5.20.1: a syntax check of two scripts was held, and its approval
  armed the rapid-redeploy brake); an option the guard does not know, or an `-n` that is another option's value
  (`--rcfile -n`), reads the script. A script sourced with `.`, `source` or `builtin source` is read whole, as a run
  one is, so a deploy anywhere in it is held, in a function it only defines too: what runs when cannot be told for
  sure from the text. An alias is read for what its value runs, and a script past the 256 KB the guard reads is held,
  since what it runs cannot be told.
- A push to, or a `gh pr merge` on, a GitHub repository listed in `deploy_remotes`, matched against the
  checkout's remotes or `-R owner/repo` (2026-10-30: a merge on the Homebrew tap published a formula before
  its release archive existed).
- A push whose repository is named by a variable (`git -C $r push` in a loop,
  `cd $DIR && git push`) while any push-deploy repository is configured: the guard can't
  tell which repository it is, so it asks.
- Not a deploy: `git commit -m "fix site push"` (2026-08-29 false block), `git log` with
  push in its arguments, `echo` or `grep` of deploy words, a heredoc written to a file, and any
  command with `--dry-run` (`wrangler deploy --dry-run` in a build script publishes nothing).

Every tool that runs a command line is read this way: Bash and its peers in Codex and Muse, and the Claude
desktop app's terminal tab (`mcp__terminal__run_in_terminal`, judged in the folder its `cwd` names), whose
commands passed every shell guard until 2026-10-30.

## Approval

A blocked deploy files a request under a random code, which the principal types as
`approve <code>`; the block message says "approve followed by the code", never the two
together. The approval binds the exact command text and the commit the HEAD of each checkout it deploys is at: HEAD
moving before the run voids it. Since 5.20.1 the hold says so, naming each checkout and its HEAD, so the same command
after a commit, or from a checkout at another commit, meeting a new code is not a surprise. A build deploy's target is what it
publishes: `gh release create -R owner/repo` that repository, `npm publish <path>` that package, anything
else the folder it runs in. Until 2026-10-30 it was always the folder, so a release run from an unrelated
checkout bound that checkout's HEAD and set off its rapid-redeploy brake. It lets one run through within
15 minutes. A command that deploys the same site twice (`git push && git push`) is
refused outright: one approval covers one publish. `synthesis approvals` lists what is
waiting. There is no command to approve: only the principal's own prompt grants, and the
grant is used only when the harness's transcript shows that prompt (M5, 2026-10-05: an
agent once granted its own send by piping a made-up prompt into the hook). The shell
guard refuses a command that carries a pending code, runs the synthesis hook by hand, or
writes into the synthesis state folder or a harness's transcripts; what stays open is in
the plugin's `docs/runtime-integration.md` (Approvals). The approval is spent when the
guard lets the command through, so if the harness then declines it, the next identical
run asks again.

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

## The pull-request gate

A repository can have the rule "changes land through a pull request" and no way to hold it: a
hosting plan without branch protection, or an agent whose instructions say "push every remote".
One private skills repository took 61 commits pushed straight to `main` in six weeks, beside 35
merged pull requests (found 2026-11-09). `pr_gated` lists such repositories by `owner/repo`.

- **The rule:** from a checkout (or linked worktree) with a remote on a listed repository, a
  `git push` goes through only when it provably leaves that repository's default branch
  alone. The guard does not work out what a push would change. Two reviews of earlier
  versions found every hole where it predicted git (a commit made earlier on the same line,
  a branch that tracks the default branch, a configured refspec, a level branch that a lease
  could rewind), so a push that names the default branch is held even when nothing is ahead,
  and a level push is a no-op to lose. The default branch is the one the rule names
  (`"branch": "develop"`), else the remote's `HEAD` as the checkout records it. When neither
  names it, nothing can be shown to leave it alone, so every branch push from that checkout
  is held until the rule names it or `git remote set-head origin --auto` records it; the
  doctor warns of such a checkout.
- **Passes:** a push that names a branch other than the default (`git push -u origin feature`,
  `feature:feature`, `HEAD:refs/heads/feature`); a bare `git push`, `git push origin` or
  `git push origin HEAD` while the current branch is not the default; a push whose
  destination is a tag (`--tags`, `tag <name>`, `refs/tags/...`); a dry run; a push to a
  remote on another repository. Whatever ran earlier on the line does not matter for these
  (`npm test && git push -u origin feature`, `git rebase origin/main && git push`,
  `git config --get ... && git push`), except as below.
- **Held:** a push whose destination is the default branch (`git push origin main`,
  `HEAD:main`, `feature:main`, `refs/heads/main`, `refs/tags/v1:refs/heads/main`, `:main`,
  `--delete main`, a bare `git push` on the default branch), with the route in the refusal: push a branch, open the pull
  request, let its checks pass, merge it, install from the merged branch.
- **Held because it cannot be read:** every branch at once (`--all`, `--mirror`, `--branches`,
  `:`, any wildcard refspec, a remote configured as a mirror); a branch or remote named
  through a variable or a substitution; an option git would not know; routing config on the
  line (`git -c remote.x.url=...`, `-c remote.origin.push=...`, `-c push.default=...`,
  `-c alias.x=...`, `--config-env`) or in its environment (`GIT_CONFIG_*`, `GIT_DIR`,
  `GIT_WORK_TREE`); a bare push, or a branch named without its destination, when the
  checkout has a configured `remote.<name>.push` refspec or a `push.default` other than
  `simple` or `current`; a `git config` or `git remote` that writes earlier on the same
  line; a push in a folder that does not exist yet (a clone or a worktree made earlier on the
  line: none of its remotes or branches can be read beforehand; run the push by itself
  afterwards); a shell alias that pushes; and a command with an unclosed quote.
- **Read the way git reads it:** a remote is judged by every URL it pushes to (`pushurl`);
  `--repo` names the repository when the line names none; options are taken as git takes
  them (any unambiguous start of a long option, `--no-` to turn one off, the last of a pair,
  short options run together, so `--mir` is a mirror and `-qn` a dry run); a git alias is
  followed through other aliases and through options it puts first; and `git switch`,
  `git checkout -b` and their kin earlier on the line set the branch a later `git push` or
  `HEAD` refers to (`git switch main && git push origin HEAD` is held; `git checkout -b topic
  && git push -u origin HEAD` passes). A switch settles the branch only for a push that
  stands in its own `&&` chain, in the same shell, and so runs only if the switch ran and
  succeeded (a newline after `&&` continues the chain). After `;`, `||`, `|`, `&`, a
  newline, a `!`, a subshell or a nested `sh -c`, the push is judged against the branch
  before the line as well. A `git rebase <upstream> <branch>` checks `<branch>` out, so that
  name is judged too. When the branch cannot be read (`git checkout -`, a variable,
  `git branch -m`, a `git symbolic-ref` that writes, `git stash branch`, `git bisect`, a
  detached `HEAD`), a push that depends on it is held.
- **One exact push with the principal's code:** the refusal carries a code; when the
  principal types it, the identical command runs once. There are no exceptions by path or
  kind of change: a list of exceptions is where a gate erodes. A forced push to a default
  branch is refused outright, as before, and no code admits it.
- **What it cannot see:** a push made inside a script file, a branch switched by a program
  other than git earlier on the line, a ref moved through the host's API, and any push from
  a machine or tool without the hook. The doctor's check below is what catches those.
- **The doctor:** `pr gate` reads each listed repository's checkout under the workspace
  folders and lists commits on its default branch since `since` that are neither merge
  commits nor GitHub squash merges (subject ending `(#N)`) nor in `direct_ok`. A push made
  where the guard cannot see it (another machine, a script, a harness without the hook) shows
  there at the next day-start. A repository with no checkout on this machine, or whose
  history cannot be read, is a warning, never a pass.
- Where the host offers it, turn on branch protection as well: it covers every machine and
  every tool, and the guard and the doctor then never fire.

Tests: `tests/test_pr_gate.py`.

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
approval bound to HEAD, the rapid brake, a sheet upload free only to a listed host), `tests/test_guards.py` (approvals, protected
roots, force pushes, every harness's shell tool, fail-closed config).

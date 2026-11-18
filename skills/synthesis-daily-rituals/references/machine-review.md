# The machine review: `synthesis review`

What is wrong on this Mac, read in one pass, and the exact steps that would fix it. The doctor checks the installed
side, the strand scan reads every repository and the context doctor reads each project's records, each as its own
command and none proposing a repair. The review joins them with the board's claims and the schedules synthesis keeps
in launchd, and ends in a numbered plan. It repairs nothing: every step runs only on the principal's word (BACKLOG C3,
roadmap FUTURE-01, which the principal ruled to build on 2026-11-18).

Contents: Where it runs, and why there · What it reads · How it stays read-only · The findings and the plan.

```bash
synthesis review            # findings by severity, then the numbered repair plan
synthesis review --json     # the same, as one JSON object
synthesis review --fetch    # first fetch every repository, and read the stable release's version
```

Exit 0 when nothing fails and nothing is unknown (warnings may remain), 1 when something fails, 2 when something could
not be told, which is never read as fine.

## Where it runs, and why there

It is a command of the core CLI, `synthesis/review.py`, beside `synthesis doctor`, not a skill's script:

- **How its pieces load.** It reads the doctor, the board, the installer's schedule reader and paths, all in the core,
  and two scripts in two collections: the strand scan (`synthesis-daily-rituals/scripts/repo_state.py`, chief of
  staff) and the context doctor (`synthesis-context-lifecycle/scripts/context_doctor.py`, core). A skill's script names
  another skill's folder only inside its own collection (rule 3 of the collections, held by `tests/test_source_lint.py`),
  so no skill's script could load both. The runtime carries both beside `synthesis/` (`install.STABLE_SKILL_SCRIPTS`),
  so the core loads each from its own release, in every install.
- **The guard's trust.** The guard runs the runtime's own CLI as the release holds it. Onboarding's scripts, the other
  home the role suggests, are the release kit, which the guard judges as any other script.
- **The budgets.** Its lines count against the core's budget as well as the plugin's, each itemized in
  `tests/test_budgets.py`. No hook imports it: the CLI loads it only for `review`, so no guarded call pays for it.

## What it reads

- **Installed side:** every doctor check that only reads (the runtime and its launchers, the pinned interpreter, the
  config, the board's and the approvals' layout, the sessions repos, the outbox, the teardown list, decision packets,
  the prompt check, browser accounts, the PR gate and temporary addresses where configured, machine security, the
  sandbox files, and Codex's and Claude Code's own config files); what the doctor last wrote down of each harness's
  hook approval (`paths.waits`, as `synthesis doctor --waiting` reads it); with `--fetch`, the stable release's version.
- **Schedules:** the hourly export of session transcripts and its fetch (the doctor's checks), and every other
  `com.synthesis.*` launch agent: loaded, and running programs that are there. macOS only.
- **Workspaces:** every folder `workspace_roots` names (default `~/workspaces/*`), its `.agents/repos.yaml`, the
  workspaces the rituals' config lists, instruction adapters and work under temporary folders.
- **Repositories:** every clone one or two folders inside a workspace folder, each read by the strand scan's own check
  on its checked-out branch (as `--discover` reads it), and every repository a workspace declares, not dormant, that has
  no clone here.
- **Claims:** each session quiet past eight hours that still holds claims and holds no live wait (a seat inside a
  wait is quiet, not gone), and each live seat whose claim covers a repository's uncommitted files, or, where it has
  none, the repository: in a repository many seats share, the seat whose work it is is the one whose claim covers it.
- **Projects:** every knowledge root (`knowledge_roots`, default `~/workspaces/*/ai-knowledge-*`), audited by the
  context doctor's own `audit_root`. A project with defects is one finding; a root's warnings are one finding.

## How it stays read-only

- **It writes no file.** `review.py` calls none of synthesis's writers, which `tests/test_unproven_programs.py` finds in
  the source, and a test holds it to none. A test runs it as installed over a synthetic machine and finds every file
  and folder there as it was, size and modification time alike, the repositories' indexes included.
- **Git cannot rewrite an index or run a planted program.** Git runs with `GIT_OPTIONAL_LOCKS=0`, so `git status` never
  refreshes an index. Before git runs in a repository, the guard's own reader (`guards._git_programs`) is asked whether
  that repository's own configuration names a program git would run for the subcommands the guard lists for the scanner
  (`guards.GIT_SCANNERS`): `core.fsmonitor`, a filter, a hook. Where one does, git never runs there, and the repository
  is reported unknown, for the principal to look at. The user's system and global git configuration is run as git runs
  it for every command on the Mac.
- **It starts no harness's program and not the hook.** A harness's own listing writes its housekeeping (on 2026-11-18,
  `claude plugin list` rewrote marker files in Claude Code's plugin cache), and the guard holds a shell that starts a
  harness's program. So the doctor's checks that start a harness's program, run the hook, try writes or ask a model are
  not run, and the review says so in its header: each harness's plugin, package, hooks and their approval, Claude
  Code's version, Codex's skill catalog and instruction chain, the hook's self-test and shell names, the turn-end wait
  check, the plan judge and the seal. `synthesis doctor` runs them.
- **No bytecode.** The two scripts load with bytecode writing off, so nothing is compiled beside them in the release.
- **It fetches nothing unless `--fetch` is given.** With it, `git fetch --all --prune` writes git's own remote-tracking
  refs and `FETCH_HEAD` in each repository, as the strand scan's `--fetch` does, and the stable release's manifest is
  read from GitHub. Nothing else is written.

## The findings and the plan

Each finding has an id (`F1`, `F2`, ...), a severity, an area, a subject (a path, a doctor check, a session) and what
is wrong. Findings print grouped by severity, worst first, then by area in the order above:

- **fail:** broken now, or work that can be lost: a part of the guard's install that is down, a branch with no
  upstream or a detached HEAD, a declared repository missing here, a record defect.
- **unknown:** a piece that could not run or could not tell, never read as fine.
- **warn:** drifting: uncommitted or unpushed work, a branch behind its upstream, a stale claim, a doctor warning, a
  root's record warnings.

The plan numbers each step in the order it runs: the steps for failures first, a stale claim taken over before the
work under it is committed, a commit before its push. Each step names:

- **do:** the exact command; for a record, the remedies the context doctor's `--project` command lists.
- **who:** `agent` (the agent, with no code), `agent-with-code` (the agent, once the principal types the code the guard
  shows: the onboarding setup, and anything else that changes what the guard trusts) or `principal` (the principal's
  own hands: macOS settings, `sudo`, an approval inside a harness, a choice only the principal can make).
- **fixes:** the findings it addresses.

A quiet seat's claims still block a claim over them, so their step is `synthesis claim <paths> --take`; the board tells
that seat what was taken and keeps it on its record. Work under a live seat's claim gets one step, a board message to
that seat, and nothing else: the work is the seat's. No step runs. Once the principal says go, the steps run in order,
and `synthesis review` again shows what remains.

`--json` prints one object: `healthy`, `exit`, `fetched`, `ms`, `counts` (fail, unknown, warn), `read` (what was read,
counted), `not_run`, `findings` (`id`, `severity`, `area`, `subject`, `detail`) and `plan` (`step`, `who`, `do`,
`fixes`).

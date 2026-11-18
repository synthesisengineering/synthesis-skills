"""`synthesis review`: what is wrong on this Mac, and the exact steps that would fix it (BACKLOG C3, roadmap FUTURE-01,
built on the principal's ruling of 2026-11-18). One read of every workspace's repositories (the rituals' strand scan),
every knowledge root's project records (the context doctor), the board's claims, the schedules synthesis keeps in launchd
and the installed side (each doctor check that only reads), ending in a numbered repair plan. Each step names its exact
command and who may run it; none runs. It writes nothing, and fetches nothing unless --fetch is given: the rituals'
references/machine-review.md says how.

    main(["--json"])   # argv without the program name; returns the exit code
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from synthesis import __version__, board, doctor, install, paths

SEVERITY = ("fail", "unknown", "warn")  # worst first: broken now or work that can be lost, cannot be told, drifting
AREAS = ("installed", "schedules", "workspaces", "claims", "repositories", "projects")  # the order findings print in
WHO = {"agent": "agent", "agent-with-code": "agent, with the principal's code", "principal": "principal"}
READ = {"workspaces": "workspace", "repositories": "repository", "projects": "project", "sessions": "session",
        "schedules": "schedule", "doctor checks": "doctor check"}  # what was read, counted, each with its one's name
SKILLS = Path(__file__).resolve().parents[1] / "skills"  # this release's own: the runtime carries both scripts read there
EXPORT, NUDGE, CONNECTOR = "com.synthesis.sessions-export", "com.synthesis.day-end-nudge", "com.synthesis.workspace-mcp"
DORMANT = {"dormant", "archived", "retired"}  # a declared repository the onboarding's workspace step does not clone
COMMIT = "Commit work left uncommitted"
LIVE ="Your claim covers {}, which holds uncommitted or unpushed work: commit and push it, or reply with what it is."
APPROVE = {"codex": "approve the synthesis hooks inside Codex: run `/hooks` there and trust each one",
           "muse": f"run `muse plugins approve {doctor.PLUGIN}`, then approve each hook Muse names"}
AGENT_FIXES = {"instruction adapters": "give each folder one set of instructions, `AGENTS.md` with a `CLAUDE.md` of the one "
               "line `@AGENTS.md`: ", "decision packets": "rebuild each page with its own generator (build_packet.py or "
               "build_sheet.py): ", "teardown": "", "prompt check": "mend the rituals' config as the line says: "}
NOT_RUN = {  # each doctor check this review does not run, and why; a test holds every check to here or to a call below
    **dict.fromkeys(("check_plugin", "check_package", "check_hooks_wired", "check_codex_trust", "check_muse_approval",
                     "check_codex_managed_hooks", "check_codex_catalog", "check_claude_fail_closed", "check_versions"),
                    "it reads what a harness's own program answers, and starting one writes the harness's housekeeping"),
    **dict.fromkeys(("check_self_test", "check_shell_name"), "it runs the hook, which writes what it saw"),
    "check_wait_check": "the turn-end check it runs writes that turn's record",
    "check_seal": "it tries the writes the sandbox must refuse",
    "check_plan_judge": "it asks a model to judge a plan",
    "check_unsaved": "the repositories' own states say what is uncommitted or unpushed, claimed or not",
    "check_codex_instructions": "it is about the folder one session runs in",
    "check_git_hooks_path": "it only reports, and never fails or warns",
}
NOT_SAID = ("Not run here, since each starts a harness's own program or the hook, tries a write or asks a model: each harness's "
            "plugin, package, hooks and their approval, Claude Code's version, Codex's skill catalog and instruction chain, the "
            "hook's self-test and shell names, the turn-end wait check, the plan judge and the seal. `synthesis doctor` runs them.")


class _Report:
    """What the review finds, in the order it reads it, each finding with the steps that fix it; `done` orders both."""

    def __init__(self):
        self.findings, self.steps, self.read = [], [], dict.fromkeys(READ, 0)

    def add(self, severity: str, area: str, subject: str, detail: str, *steps: tuple) -> None:
        self.findings.append({"severity": severity, "area": area, "subject": subject, "detail": detail})
        self.steps += [(len(self.findings) - 1, who, do) for who, do in steps]

    def doctor(self, check, area: str, subject: str = "") -> None:
        """A doctor line as a finding, with the step that fixes it; a line that is well, or only reports, is none. A line
        that could not tell is unknown, never fine."""
        self.read["doctor checks"] += 1
        if check.status in ("fail", "warn"):
            unknown = check.detail.startswith(("cannot tell", "could not read"))
            self.add("unknown" if unknown else check.status, area, subject or check.name, check.detail, _fix(check))

    def done(self, fetched: bool, began: float) -> dict:
        """Findings by severity, then area, then the order they were read; the plan in the order of what each step fixes,
        a step that one command makes said once, with every finding it fixes."""
        rank = {i: (SEVERITY.index(f["severity"]), AREAS.index(f["area"]), i) for i, f in enumerate(self.findings)}
        order = sorted(rank, key=rank.get)
        ids = {i: f"F{n}" for n, i in enumerate(order, 1)}
        plan, said = [], {}
        for _, (i, who, do) in sorted(enumerate(self.steps), key=lambda step: (rank[step[1][0]], step[0])):
            if do not in said:
                said[do] = {"step": len(plan) + 1, "who": who, "do": do, "fixes": []}
                plan.append(said[do])
            said[do]["fixes"] += [ids[i]] * (ids[i] not in said[do]["fixes"])
        counts = {s: sum(f["severity"] == s for f in self.findings) for s in SEVERITY}
        code = 2 if counts["unknown"] else 1 if counts["fail"] else 0
        return {"healthy": code == 0, "exit": code, "fetched": fetched, "ms": round((time.time() - began) * 1000), "counts": counts,
                "read": self.read, "not_run": NOT_SAID, "findings": [{"id": ids[i], **self.findings[i]} for i in order], "plan": plan}


# ---- how a step names a path, a script and the runtime's own install ------------------------------------------------

def _arg(path) -> str:
    """A path as a command line takes it: `~` for the home folder where the rest needs no quotes, else quoted whole."""
    text, home = str(path), str(Path.home())
    rest = text[len(home):] if text == home or text.startswith(home + os.sep) else None
    return "~" + rest if rest is not None and re.fullmatch(r"[\w./+@%:,=-]*", rest) else shlex.quote(text)


def _runtime(skill: str, *parts: str) -> str:
    """A command for a script the runtime carries, as every skill runs one: the runtime's copy, Python with -s."""
    path = paths.home() / "current" / "skills" / skill / Path(*parts)
    return ("python3 -s " if path.suffix == ".py" else "bash ") + _arg(path)


def _version(home: Path) -> str:
    return ".".join(map(str, install.version(home / "current"))) or __version__


def _reinstall(home: Path) -> tuple:
    """The install of the runtime's own release, which the guard lets the release launcher make with no code."""
    return "agent", f"{_arg(home / 'bin' / 'synthesis-release')} --install-only --tag v{_version(home)}"


def _fix(check) -> tuple:
    """(who, do) for a doctor line. The runtime's own parts: the install of its release. The export's schedule and a
    harness's settings: the onboarding setup, which waits for the principal's code. A sessions repo to sync, transcripts
    to copy, a list to work through: the agent. Anything else touches macOS, the sealed config or a choice that is the
    principal's: their own hands, in the line's own words."""
    name, detail, home = check.name, check.detail, paths.home()
    setup = _runtime("synthesis-onboarding", "scripts", "setup.py")
    newer = re.search(r"is (\d+\.\d+\.\d+); behind", detail) if name == "latest release" else None
    if name in ("runtime", "hook script") or check.status == "warn" and name in ("config", "board", "approvals"):
        return _reinstall(home)
    if newer:
        return "agent", f"{_arg(home / 'bin' / 'synthesis-release')} --install-only --tag v{newer[1]}"
    if name == "sessions export" and "could not be copied" in detail:
        return "agent", "synthesis sessions export --all"
    if name == "sessions export" or name == "scheduled fetch" and "not fetched:" not in detail:
        return "agent-with-code", f"{setup} plugin --sessions-export"
    if name in ("codex hooks feature", "codex instruction bytes", "codex board access", "claude transcripts"):
        return "agent-with-code", f"{setup} plugin --clients {name.split()[0]}"
    if name.startswith("sessions repo ") and "not cloned" not in detail and " GB" not in detail:
        return "agent", "synthesis sessions sync"
    if name in AGENT_FIXES:
        return "agent", AGENT_FIXES[name] + detail
    return "principal", detail


# ---- what is read, and how without a write -------------------------------------------------------------------------

def _load(skill: str, script: str):
    """A script this release carries, loaded as a module, with nothing compiled beside it in the release."""
    sys.dont_write_bytecode = True
    path = SKILLS / skill / "scripts" / script
    spec = importlib.util.spec_from_file_location(f"synthesis_review_{path.stem}", path)
    module = sys.modules[spec.name] = importlib.util.module_from_spec(spec)  # a dataclass finds its module there
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


def _programs(repo: Path, subs: tuple) -> list:
    """What, in this repository's own configuration (its config, its worktree's, its submodules'), names a program git
    would run there for these subcommands, read by the guard's own reader: [] for none. The user's system and global
    files are git's for every command on this Mac, and the guard judges a program they name as a command."""
    from synthesis import guards
    return sorted({what for sub in subs for what, _, _, scope in guards._git_programs(["git", "-C", str(repo), sub], str(repo), "")
                   if scope == "repo"})


def _present(harness: str) -> bool:
    """Whether this Mac has the harness's command line where the doctor looks for one: found, never run."""
    given = os.environ.get(doctor.CLIENT_ENV[harness])
    places = [given] if given else [shutil.which(harness) or ""] + [p for c in paths.INSTALLS[harness] for p in paths.expand_install(c)]
    return any(p and os.path.isfile(os.path.expanduser(p)) and os.access(os.path.expanduser(p), os.X_OK) for p in places)


def _covers(claims: list, real: str, found: dict) -> bool:
    """Whether these claims cover a repository's uncommitted files (the first twenty the scan lists), or, with none, any
    part of it: in a repository many seats share, the seat whose work it is is the one whose claim covers it."""
    files = [os.path.join(real, line[3:].split(" -> ")[-1].strip('"')) for line in found.get("dirty", []) if not line.startswith("... ")]
    spots = [f + "**" if f.endswith("/") else f for f in files] or [real + "/**"]  # an untracked folder: what is beneath it
    return any(board.overlaps(c, spot) for c in claims for spot in spots)


def _claimed(claim: str) -> str:
    """A claim as `synthesis claim` takes it again: a folder by its path, since a claim covers what is beneath it."""
    folder = claim[:-3] if claim.endswith("/**") else ""
    return _arg(folder if folder and os.path.isdir(folder) else claim)


# ---- the installed side and the schedules ----------------------------------------------------------------------------

def installed(report, config, home: Path, fetch: bool) -> None:
    """Each doctor check that only reads; what the doctor last saw of each harness's hook approval; with fetch, the
    stable release's version."""
    from synthesis import project, rituals, sessions
    checks = [doctor.check_runtime(home), doctor.check_config(home), doctor.check_board(home), doctor.check_approvals_layout(home)]
    if (home / "bin" / "synthesis-hook").is_file():  # when it is missing, the runtime's line says so
        checks += [doctor.check_hook_script(home), doctor.check_interpreter(home)]
    checks += [doctor.check_home_paths([home / "config.json"]), doctor.check_outbox(paths.outbox(), *doctor.connector_files()),
               doctor.check_teardown(home / "teardown.jsonl"), doctor.check_sandbox([h for h in doctor.HARNESSES if _present(h)])]
    checks += doctor.check_security(paths.account_home())
    try:
        checks.append(doctor.check_prompt_check(rituals.config()))
    except (OSError, ValueError) as exc:
        checks.append(doctor.check_prompt_check(None, str(exc)[:120]))
    if config is not None:
        checks += doctor.check_sessions_repos(sessions.repos(), home / "sessions" / ".state") + [doctor.check_packets(project.roots()),
                   doctor.check_browser_accounts(config, paths.read_json(paths.approvals() / "browser-accounts.json"))]
        checks += [doctor.check_pr_gate(config["pr_gated"], doctor.workspace_repos(config))] if config.get("pr_gated") is not None else []
        checks += [doctor.check_temporary_addresses(config)] if "temporary_addresses" in config else []
    if _present("codex"):  # its own config file, read as the doctor reads it
        codex = paths.codex_home()
        try:
            toml = doctor.read_toml((codex / "config.toml").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            toml = {}
        checks += [doctor.check_codex_features(toml), doctor.check_codex_doc_bytes(toml), doctor.check_codex_board(
            toml, home / "board", home / "approvals", home / "outbox"), doctor.check_codex_hooks_file(codex), doctor.check_codex_nested_hooks(codex)]
    if _present("claude"):
        checks.append(doctor.check_claude_retention(paths.transcript_roots()["claude-code"].parent / "settings.json"))
    if fetch:
        checks.append(doctor.check_latest({"runtime": _version(home)}, "stable"))
    for check in (c for c in checks if c):  # a check with nothing to say answers None
        report.doctor(check, "installed")
    _approvals(report)


def _approvals(report) -> None:
    """What the doctor last wrote down of each harness's hook approval here (`paths.waits`, as `synthesis doctor --waiting`
    reads it): a guard it saw not running fails; a harness it has not looked at in a day or in this release, or could not
    tell, is unknown until it looks again."""
    seen = paths.waits()
    for name, harness in paths.HOOK_APPROVALS.items():
        entry, label = seen.get(name), harness.capitalize()
        if not _present(harness):
            continue
        if entry and entry["version"] == __version__ and not entry["untold"]:
            if entry["waiting"]:
                at = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["at"]))
                report.add("fail", "installed", name, f"{', '.join(entry['waiting'])} not running in {label} when the doctor looked "
                           f"at {at}: {entry['said']}", ("principal", APPROVE[harness]))
            continue
        why = ("the doctor has not looked in a day" if entry is None else f"the doctor last looked under release {entry['version']}"
               if entry["version"] != __version__ else entry["said"])
        report.add("unknown", "installed", name, f"whether {label} runs the synthesis hooks is not known here: {why}",
                   ("agent", "synthesis doctor"))


def schedules(report, home: Path, config, run, platform: str) -> None:
    """The launch agents synthesis keeps: the hourly export and the fetch it makes (the doctor's checks), and every other
    `com.synthesis.*` one, which must be loaded and run programs that are there. launchd is macOS's; elsewhere no schedule
    is kept."""
    if platform != "darwin":
        return
    folder, state, setup = Path.home() / "Library" / "LaunchAgents", home / "sessions" / ".state", _runtime(
        "synthesis-onboarding", "scripts", "setup.py")
    plists = sorted(folder.glob("com.synthesis.*.plist")) if folder.is_dir() else []
    report.read["schedules"] = len(plists)
    report.doctor(doctor.check_sessions_export(folder / f"{EXPORT}.plist", state / "export.json", run=run, command=home / "bin" / "synthesis"),
                  "schedules", EXPORT)
    report.doctor(doctor.check_fetch(state / "fetch.json", config or {}), "schedules")
    for plist in (p for p in plists if p.stem != EXPORT):
        programs = install.scheduled(plist)
        gone = [p for p in programs if os.path.isabs(p) and not (os.path.isfile(p) and os.access(p, os.X_OK))]
        loaded = run(["launchctl", "print", f"gui/{os.getuid()}/{plist.stem}"], capture_output=True, text=True).returncode == 0
        said = ("cannot be read as a schedule, or runs no command" if not programs else f"runs {', '.join(gone)}, which is not there"
                if gone else "" if loaded else "is not loaded, so launchd never runs it")
        step = {NUDGE: ("agent-with-code", f"{setup} plugin --day-end"), CONNECTOR: ("agent-with-code", _runtime(
            "synthesis-meeting-transcripts", "optional-workspace-mcp", "install-autostart.sh"))}.get(plist.stem, (
                "principal", "load or mend it with the setup that wrote it: no public setup of synthesis writes one of that name"))
        if said:
            report.add("fail", "schedules", plist.stem, f"{doctor._short(plist)} {said}", step)


# ---- workspaces, repositories and claims -----------------------------------------------------------------------------

def workspaces(report, scan, config: dict, sessions: list) -> list:
    """Each workspace folder, with its clones and what its .agents/repos.yaml declares (never what is dormant); each
    workspace the rituals' config lists with no folder here; and the doctor's two checks over the workspaces' clones."""
    from synthesis import rituals
    from synthesis import sessions as archive
    from synthesis.yamlish import load
    spaces = []
    for folder in sorted(archive._workspaces()):
        declared, manifest = [], folder / ".agents" / "repos.yaml"
        if scan and os.path.lexists(manifest):  # a link into a knowledge repository that is not here cannot be read
            try:
                rows, status = scan.declared(folder), str((load(manifest.read_text(encoding="utf-8")) or {}).get("status") or "")
                declared = [r for r in rows if not {status.lower(), str(r.get("status") or "").lower()} & DORMANT]
            except (OSError, ValueError) as exc:
                report.add("unknown", "workspaces", doctor._short(manifest), f"cannot be read ({exc}), so what the workspace declares "
                           "is not known", ("principal", f"mend {doctor._short(manifest)}: its repos are a list, each with its own name"))
        spaces.append((folder, scan.discovered(folder) if scan else [], declared))
    report.read["workspaces"] = len(spaces)
    try:
        listed = sorted(set(rituals.config()["workspaces"]) - {folder.name for folder, _, _ in spaces})
    except (OSError, ValueError):
        listed = []  # the prompt check's line says why the rituals' config cannot be read
    for name in listed:
        report.add("warn", "workspaces", name, "the rituals' config lists this workspace, and it has no folder here", (
            "principal", f"bring it onto this Mac (`{_runtime('synthesis-onboarding', 'scripts', 'setup.py')} workspace --kb <its "
            f"knowledge repository's URL> --workspace {shlex.quote(name)}`), or take it out of {doctor._short(rituals.state_dir() / 'config.json')}"))
    repos = doctor.workspace_repos(config)
    for check in (doctor.check_instruction_adapters(repos), doctor.check_temporary_work(repos, [s.cwd for s in sessions if not s.stale])):
        report.doctor(check, "workspaces")
    return spaces


def repositories(report, scan, spaces: list, sessions: list, fetch: bool) -> list:
    """Every clone in each workspace folder, read by the strand scan's own check on its checked-out branch (as --discover
    reads it), and each repository a workspace declares with no clone here. Git runs only where the repository's own
    configuration names no program. Returns (path, what the scan found) for each clone read."""
    from synthesis import guards
    entries = {}
    for _, found, declared in spaces:  # a declared clone, read as a found one is, wherever it lies
        for row in found + [{**r, "excluded": False, "branches": None} for r in declared]:
            entries.setdefault(os.path.realpath(row["path"]), row)
    order, subs = sorted(entries), tuple(guards.GIT_SCANNERS["repo_state.py"]) + ("fetch",) * fetch

    def read(real: str):
        row = entries[real]
        if not os.path.exists(Path(row["path"]) / ".git"):
            return None  # declared, with no clone here
        try:
            named = _programs(Path(row["path"]), subs)
            return {"programs": named} if named else scan.check(row, fetch, False)
        except Exception as exc:  # what cannot be read is never read as fine
            return {"error": str(exc) or type(exc).__name__}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read, order))
    own = paths.session_id()  # this session's own claims hold its own work, which it repairs itself
    live, quiet = [s for s in sessions if s.claims and not s.stale and s.session != own], [s for s in sessions if s.claims and s.stale]
    for real, found in zip(order, results):
        _repository(report, scan, entries[real], found, live, quiet, fetch)
    report.read["repositories"] = len(order)
    return [(real, found) for real, found in zip(order, results) if found is not None]


def _repository(report, scan, row: dict, found, live: list, quiet: list, fetch: bool) -> None:
    """One repository's finding, with its steps in the order they run: back on a branch, the commit, then the upstream or
    the integration. Work under a live seat's claim is that seat's: one message to it is the only step."""
    path = Path(row["path"])
    where, short = _arg(path), doctor._short(path)
    if found is None:
        origin = str((row.get("remotes") or {}).get("origin") or "")
        report.add("fail" if row.get("ritual_sync") is True else "warn", "repositories", short, "declared in .agents/repos.yaml, with "
                   "no clone here", ("agent", f"git clone {_arg(origin)} {where}") if origin else ("principal", f"clone it to {where}: "
                                                                                                    "its workspace declares no origin for it"))
        return
    if "programs" in found or "error" in found:
        named = found.get("programs") or []
        show = f" (`git -C {where} config --show-origin --get-all {named[0]}` shows it)" if named and re.fullmatch(r"[\w.-]+", named[0]) else ""
        report.add("unknown", "repositories", short, f"its own git configuration names a program git would run here ({', '.join(named)}), "
                   "so the review ran no git in it" if named else f"whether git may run here cannot be told ({found['error']})",
                   ("principal", f"look at what {named[0]} names and take it out unless the principal put it there{show}" if named else
                    f"look at {short}'s git configuration by hand"))
        return
    state, items, said, steps = found["state"], found["branches"], [], []
    if state in ("CURRENT", "CACHED", "EXCLUDED"):
        return
    dirty = found.get("dirty", [])
    files = sum(1 for line in dirty if not line.startswith("... ")) + sum(int(n) for line in dirty for n in re.findall(r"^\.\.\. (\d+) more$", line))
    if state == "UNREACHABLE":
        said.append(f"git cannot read it: {found.get('reason', '')}")
        steps.append(("principal", f"`git -C {where} fetch --all --prune` fails ({found.get('reason', '')}): restore its remote's sign-in "
                      "or the network, then run it again" if fetch else f"`git -C {where} status` fails ({found.get('reason', '')}): mend "
                      "the repository by hand"))
    elif state == "BLIND" and not items:
        said.append("HEAD is detached: commits made here are on no branch")
        steps.append(_onto_branch(scan, path, where))
    if files:
        said.append(f"{files} uncommitted file{'s' * (files != 1)} (" + ", ".join(line.strip() for line in dirty[:3] if not line.startswith(
            "... ")) + (", ..." if files > 3 else "") + ")")
        steps.append(("agent", f"git -C {where} add -A && git -C {where} commit -m {shlex.quote(COMMIT)}"))
    for item in items:
        branch, upstream = item["branch"], item.get("upstream", "")
        if item["state"] == "BLIND":
            said.append(f"branch {branch} has no upstream: nothing tells whether its commits reached a remote")
            steps.append(_upstream(scan, path, where, branch))
            continue
        ahead, behind = item.get("ahead", 0), item.get("behind", 0)
        said += [f"{branch} and {upstream} have diverged: {ahead} commit{'s' * (ahead != 1)} here, {behind} there"] if ahead and behind else [
            f"{branch} is {n} commit{'s' * (n != 1)} {how} {upstream}" for n, how in ((ahead, "ahead of"), (behind, "behind")) if n]
        ahead += bool(files)  # the commit above is one more for its upstream
        steps += [("principal", f"rebase onto {upstream} (`git -C {where} pull --rebase`) or merge it (`git -C {where} pull --no-rebase`), "
                   f"then `git -C {where} push`")] if ahead and behind else [("agent", f"git -C {where} push")] if ahead else [
            ("agent", f"git -C {where} merge --ff-only {shlex.quote(upstream)}")] if behind else []
    real = os.path.realpath(path)
    holders, resting = [s for s in live if _covers(s.claims, real, found)], [s for s in quiet if _covers(s.claims, real, found)]
    said += [f"live session {s.short} claims it" for s in holders] + [
        f"under the claim of session {s.short}, quiet {int((time.time() - s.seen) / 3600)} h" for s in resting]
    if holders:
        steps = [("agent", f"synthesis msg {shlex.quote(s.session)} {shlex.quote(LIVE.format(short))}") for s in holders]
    report.add("fail" if state in ("UNREACHABLE", "BLIND") else "warn", "repositories", short, "; ".join(said), *steps)


def _onto_branch(scan, path: Path, where: str) -> tuple:
    """A detached HEAD's step: back onto the one branch that already holds it, else the principal's choice."""
    try:
        named = scan.git(path, "for-each-ref", "--points-at", "HEAD", "--format=%(refname:short)", "refs/heads").split()
    except (RuntimeError, OSError, subprocess.SubprocessError):
        named = []
    if len(named) == 1:
        return "agent", f"git -C {where} switch {shlex.quote(named[0])}"
    return "principal", (f"put HEAD back on a branch: `git -C {where} switch -c <a new branch>` keeps what was committed while detached; "
                         f"`git -C {where} branch --contains HEAD` names the branches that already hold it")


def _upstream(scan, path: Path, where: str, branch: str) -> tuple:
    """A branch's step to an upstream: the remote's branch of that name where it has one, else a first push, else the
    principal's remote."""
    try:
        listed = scan.git(path, "config", "--get-regexp", r"^remote\..*\.url$").splitlines()
    except (RuntimeError, OSError, subprocess.SubprocessError):
        listed = []
    remotes = [m[1] for m in (re.match(r"remote\.(.+)\.url\s", line) for line in listed) if m]
    remote = "origin" if "origin" in remotes else (remotes or [""])[0]
    if not remote:
        return "principal", (f"give it a remote: `git -C {where} remote add origin <its URL>`, then `git -C {where} push -u origin "
                             f"{shlex.quote(branch)}`")
    try:
        scan.git(path, "rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}")
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return "agent", f"git -C {where} push -u {shlex.quote(remote)} {shlex.quote(branch)}"
    return "agent", f"git -C {where} branch --set-upstream-to={shlex.quote(f'{remote}/{branch}')} {shlex.quote(branch)}"


def claims(report, sessions: list, scanned: list) -> None:
    """Each seat quiet past eight hours that still holds claims and no live wait: a seat inside a wait is quiet, not
    gone, and no one takes it over before its wait ends (the day-start's stale-claim review). Its claims still block a
    claim over them, so the step takes them over; the board tells the seat what was taken, and keeps it on its record."""
    from synthesis import wait
    now = time.time()
    for s in sorted(sessions, key=lambda s: s.session):
        if not (s.stale and s.claims) or wait.held(s.session):
            continue
        under, n = [doctor._short(p) for p, found in scanned if found.get("dirty") and _covers(s.claims, p, found)], len(s.claims)
        report.add("warn", "claims", s.session, f"session {s.short} ({s.harness or 'harness not recorded'}, project {s.project or '-'}) "
                   f"has been quiet {int((now - s.seen) / 3600)} h and holds {n} claim{'s' * (n != 1)}: {doctor._short(s.claims[0])}"
                   + (f" and {n - 1} more" if n > 1 else "") + (f"; uncommitted work under {'it' if n == 1 else 'them'} in "
                                                               f"{', '.join(under)}" if under else ""),
                   ("agent", f"synthesis claim {' '.join(_claimed(c) for c in s.claims)} --take"))


# ---- project records -----------------------------------------------------------------------------------------------

def projects(report, config: dict, scanned: list) -> None:
    """Every knowledge root's project records, audited by the context doctor's own `audit_root`: a project with defects is
    one finding, a root's projects with warnings only one more, and a root whose records cannot be read is unknown. What
    the repositories' own states say of a root's repository read with them is not said twice."""
    from synthesis import guards
    script = SKILLS / "synthesis-context-lifecycle" / "scripts" / "context_doctor.py"
    try:
        cd = _load("synthesis-context-lifecycle", "context_doctor.py")
    except (Exception, SystemExit) as exc:  # a script that cannot load is never read as one that found nothing
        report.add("unknown", "projects", "context doctor", f"{doctor._short(script)} cannot be loaded ({exc}), so no project's "
                   "records were read", _reinstall(paths.home()))
        return
    try:
        roots = cd.knowledge_roots()
    except cd.CannotTell as exc:
        report.add("unknown", "projects", "knowledge roots", f"{exc}, so no project's records were read", ("principal", str(exc)))
        return
    command, today, subs = _runtime("synthesis-context-lifecycle", "scripts", "context_doctor.py"), date.today(), tuple(
        guards.GIT_SCANNERS["context_doctor.py"])

    def audit(root: Path) -> tuple:
        if not (root / "projects").is_dir():
            return "absent", None
        try:
            named = _programs(root / "projects", subs)
            return ("programs", f"its repository's own git configuration names a program git would run there ({', '.join(named)})"
                    ) if named else ("read", cd.audit_root(root, today, named=False))
        except Exception as exc:  # the doctor's own CannotTell among them
            return "cannot", str(exc) or type(exc).__name__
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(audit, roots))
    held = [real for real, _ in scanned]
    for root, (kind, value) in zip(roots, results):
        short = doctor._short(root)
        if kind == "absent":  # a root found by the default pattern always has one: only a configured root can lack it
            if config.get("knowledge_roots"):
                report.add("warn", "projects", short, "the config names this knowledge root, and it has no projects/ folder here", (
                    "principal", f"bring its workspace onto this Mac, or take it out of knowledge_roots in "
                    f"{doctor._short(paths.config_file())} (`synthesis config apply <file>` takes the principal's code)"))
            continue
        if kind != "read":
            report.add("unknown", "projects", short, f"{value}, so its records were not read", ("principal", f"look at {short}'s git "
                                                                                                "repository by hand"))
            continue
        audits, source = value
        report.read["projects"] += len(audits)
        for audit_ in audits:
            defects = [f for f in audit_.findings if f.severity == "defect"]
            if defects:
                checks = ", ".join(sorted({f.check for f in defects}))
                report.add("fail", "projects", doctor._short(audit_.path), f"{len(defects)} defect{'s' * (len(defects) != 1)} ({checks}): "
                           f"{defects[0].message}", ("agent", f"make the remedies `{command} --project {_arg(audit_.path)}` lists ({checks})"))
        warned = [f for a in audits if not any(f.severity == "defect" for f in a.findings) for f in a.findings]
        if warned:
            kinds, many = Counter(f.check for f in warned), len({f.project for f in warned})
            report.add("warn", "projects", short, f"{many} project{'s' * (many != 1)} with warnings only, {len(warned)} in all: " + ", ".join(
                f"{k} {n}" for k, n in sorted(kinds.items())), ("agent", f"make the remedies `{command} --root {_arg(root)}` lists for them"))
        mine = any(paths.inside(os.path.realpath(root), real) for real in held)  # its repository's state is said with the rest
        for f in (f for f in source if not (mine and f.check in ("unpushed-context", "uncommitted-context"))):
            report.add("fail" if f.severity == "defect" else "warn", "projects", short, f"{f.project}: {f.message}", (
                "agent", f"synthesis index set {shlex.quote(f.project)} status archived") if f.check == "context-present" else ("agent", f.remedy))


# ---- the whole review ----------------------------------------------------------------------------------------------

def review(fetch: bool = False, run=subprocess.run, platform: str = sys.platform) -> dict:
    """What is wrong on this Mac, by severity, and the repair plan; nothing is written. `run` asks launchd, and only that."""
    began, home, report = time.time(), paths.home(), _Report()
    try:
        config = paths.config()
    except paths.Unreadable as exc:
        config = None
        report.add("unknown", "workspaces", doctor._short(paths.config_file()), f"cannot be read ({exc}), so the workspaces, knowledge "
                   "roots and sessions repos it names are not known, and none was read", ("principal", f"make {doctor._short(paths.config_file())} "
                   "one JSON object of settings again (it is sealed: `synthesis config apply <file>` takes the principal's code)"))
    installed(report, config, home, fetch)
    sessions = board.sessions()
    report.read["sessions"] = len(sessions)
    schedules(report, home, config, run, platform)
    scanned = []
    if config is not None:
        try:
            scan = _load("synthesis-daily-rituals", "repo_state.py")
        except (Exception, SystemExit) as exc:  # a script that cannot load is never read as one that found nothing
            scan = None
            report.add("unknown", "repositories", "strand scan", f"{doctor._short(SKILLS / 'synthesis-daily-rituals' / 'scripts' / 'repo_state.py')} "
                       f"cannot be loaded ({exc}), so no repository was read", _reinstall(home))
        spaces = workspaces(report, scan, config, sessions)
        scanned = repositories(report, scan, spaces, sessions, fetch) if scan else []
        projects(report, config, scanned)
    claims(report, sessions, scanned)
    return report.done(fetch, began)


def render(report: dict) -> str:
    """The text form: a line that counts, what this review does not run, the findings by severity, then the plan."""
    read = ", ".join(f"{n} {name if n != 1 else READ[name]}" for name, n in report["read"].items())
    head = ", ".join(f"{report['counts'][s]} {s}" for s in SEVERITY) if report["findings"] else "nothing to repair"
    out = [f"synthesis review: {head}; read {read} in {report['ms'] / 1000:.1f} s" + (", after fetching" if report["fetched"] else "")
           + "; nothing was changed", report["not_run"]]
    for severity in SEVERITY:
        found = [f for f in report["findings"] if f["severity"] == severity]
        if found:
            out += ["", severity.upper()] + [f"  {f['id']:<4} {f['area']:<13} {f['subject']}: {f['detail']}" for f in found]
    if report["plan"]:
        n = len(report["plan"])
        out += ["", f"Repair plan, {n} step{'s' * (n != 1)}: none has run, and each waits for the principal's word"]
        out += [f"  {s['step']}. [{WHO[s['who']]}] {s['do']}  ({', '.join(s['fixes'])})" for s in report["plan"]]
        out.append("Once they have run, `synthesis review` shows what remains.")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="synthesis review", description="What is wrong on this Mac, every workspace's repositories, "
                                     "project records, claims, schedules and install, with the exact steps that would fix it. It "
                                     "changes nothing, and no step runs.")
    parser.add_argument("--json", action="store_true", help="print the review as one JSON object")
    parser.add_argument("--fetch", action="store_true", help="first fetch every repository (git writes its remote-tracking refs) "
                        "and read the stable release's version from GitHub; network")
    args = parser.parse_args(list(argv or []))
    sys.dont_write_bytecode = True  # nothing compiled into the release beside a script it loads
    report = review(fetch=args.fetch)
    print(json.dumps(report, indent=1) if args.json else render(report))
    return report["exit"]

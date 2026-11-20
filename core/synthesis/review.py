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
import contextlib
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
NAMED = 100  # the most paths one commit in the plan names; past it, what is work there is the principal's to decide
LIVE = "Your claim covers {}, which holds uncommitted or unpushed work: commit and push it, or reply with what it is."
APPROVE = {"codex": "approve the synthesis hooks inside Codex: run `/hooks` there and trust each one",
           "muse": f"run `muse plugins approve {doctor.PLUGIN}` (`{doctor.CORE}` where collections are installed), then "
                   "approve each hook Muse names"}
AGENT_FIXES = {"instruction adapters": "give each folder one set of instructions, `AGENTS.md` with a `CLAUDE.md` of the one "
               "line `@AGENTS.md`: ", "decision packets": "rebuild each page with its own generator (build_packet.py or "
               "build_sheet.py): ", "teardown": "", "prompt check": "mend the rituals' config as the line says: "}
NOT_RUN = {  # each doctor check this review does not run, and why; a test holds every check to here or to a call below
    **dict.fromkeys(("check_plugin", "check_package", "check_hooks_wired", "check_codex_trust", "check_muse_approval", "check_hooks_on",
                     "check_codex_managed_hooks", "check_codex_catalog", "check_claude_fail_closed", "check_versions"),
                    "it reads what a harness's own program answers, and starting one writes the harness's housekeeping"),
    **dict.fromkeys(("check_self_test", "check_shell_name", "check_home_self_test"), "it runs the hook, which writes what it saw"),
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
        """A doctor line as a finding, with the step that fixes it, by the doctor's own status: a line that is well, or only
        reports, is none, and one that could not tell is unknown, never fine."""
        self.read["doctor checks"] += 1
        if check.status in SEVERITY:
            self.add(check.status, area, subject or check.name, check.detail, _fix(check))

    def guard(self, area: str, subject: str, read, default=None):
        """What read() answers, or, where it raises, an unknown finding for its area: a part that cannot run is never read
        as fine, and never ends the rest of the review."""
        try:
            return read()
        except Exception as exc:
            self.add("unknown", area, subject, f"the review could not read it ({type(exc).__name__}: {exc})", (
                "principal", f"look at {subject} by hand: what stopped the review there is named above"))
            return default

    def done(self, fetched: bool, began: float, config) -> dict:
        """Findings by severity, then area, then the order they were read; the plan in the order of what each step fixes,
        a step that one command makes said once, with every finding it fixes, and each git step classed by the guard."""
        rank = {i: (SEVERITY.index(f["severity"]), AREAS.index(f["area"]), i) for i, f in enumerate(self.findings)}
        order = sorted(rank, key=rank.get)
        ids = {i: f"F{n}" for n, i in enumerate(order, 1)}
        plan, said = [], {}
        with _offline():
            steps = [(i, "agent-with-code" if who == "agent" and do.startswith("git ") and _held(do, config) else who, do)
                     for i, who, do in self.steps]
        for _, (i, who, do) in sorted(enumerate(steps), key=lambda step: (rank[step[1][0]], step[0])):
            if do not in said:
                said[do] = {"step": len(plan) + 1, "who": who, "do": do, "fixes": []}
                plan.append(said[do])
            said[do]["fixes"] += [ids[i]] * (ids[i] not in said[do]["fixes"])
        counts = {s: sum(f["severity"] == s for f in self.findings) for s in SEVERITY}
        code = 2 if counts["unknown"] else 1 if counts["fail"] else 0
        return {"healthy": code == 0, "exit": code, "fetched": fetched, "ms": round((time.time() - began) * 1000), "counts": counts,
                "read": self.read, "not_run": NOT_SAID, "findings": [{"id": ids[i], **self.findings[i]} for i in order], "plan": plan}


# ---- how a step names a path, a script and the runtime's own install, and whom the guard asks for a code ---------------

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


def _held(do: str, config: dict) -> bool:
    """Whether the guard holds this git step for the principal's code, asked of its own deciders, which record no request:
    a deploy it makes (a repository that publishes on push: push_deploys, deploy_remotes, deploy_patterns), or a push that
    may move a gated repository's default branch (pr_gated), a setting the guard cannot read holding every push."""
    from synthesis import guards
    cwd, gated = str(Path.home()), config.get("pr_gated")
    if guards._targets(do, config, cwd):
        return True
    commands, readable = guards._parse(do, cwd)
    pushes = [(found, where) for words, at in commands for where in [guards._git(words, at)[1]] for found in [guards._push(words, where)]
              if found]
    if not pushes or gated is None:
        return False
    if not isinstance(gated, dict) or not all(isinstance(k, str) and "/" in k for k in gated):
        return True
    rules = {k.lower(): rule for k, rule in gated.items()}
    return any(guards._gated_push(found[0], where, rules, readable and found[1], None, do, {where}) for found, where in pushes)


@contextlib.contextmanager
def _offline():
    """No git started inside reaches another repository, one at a local path included: nothing is fetched without --fetch,
    and a transport runs what the repository's own configuration names (`remote.<name>.uploadpack`), which the screen for
    the scanner's subcommands does not read. The push decider may ask a remote which version tags it holds; one it cannot
    ask holds the push, which the plan then says. The environment comes back whole, as it was."""
    before = os.environ.copy()
    os.environ.update(GIT_ALLOW_PROTOCOL="none")  # a list of no protocol git has: `file`, a local path's, refused with the rest
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(before)


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


def _gitdir(dot: Path) -> str:
    """'' for a `.git` git can read: a folder, or a file naming a folder that is there (a worktree's); else why not."""
    if dot.is_dir():
        return ""
    if dot.is_symlink() and not dot.exists():
        return f"it is a link to {os.readlink(dot)}, which is not there"
    if not dot.is_file():  # a pipe, never opened: it waits for a writer
        return "it is neither a folder nor a file"
    try:
        named = re.match(r"gitdir:\s*(.+)", dot.read_text(encoding="utf-8", errors="replace").strip())
    except OSError as exc:
        return f"it cannot be read ({exc.strerror})"
    if not named:
        return "it is a file that names no git folder"
    return "" if (dot.parent / named[1].strip()).is_dir() else f"it names {named[1].strip()}, which is not there"


def _discovered(folder: Path) -> list:
    """A row for each folder one or two inside a workspace folder that holds a `.git` of any kind, as the strand scan's
    discovery makes one: a worktree's file, and a dangling link, which a glob for `.git` itself finds or not by the Python
    running it, and whose repository's one read says it is unknown."""
    return [{"name": str(spot.relative_to(folder)), "path": spot, "excluded": False, "branches": None} for spot in sorted(
        p for depth in ("*", "*/*") for p in folder.glob(depth) if os.path.lexists(p / ".git"))]


def _split(claim: str) -> tuple:
    """A claim as the board holds it (normalized when its session was read), split once, as `board._parts` splits one."""
    subtree = claim.endswith("/**")
    return Path(claim[:-3] if subtree else claim).parts, subtree


def _covered(claims: list, real: str, files: list) -> list:
    """The paths of a repository at `real` these split claims cover, an untracked folder ("dir/") as all beneath it; with
    no path, [""] where one covers any part of it. A claim outside the repository is compared with none of its paths."""
    near = [c for c in claims if board.split_overlap(c, (Path(real).parts, True))]
    if not near or not files:
        return [""] if near else []
    return [f for f in files if any(board.split_overlap(c, (Path(real, f).parts, f.endswith("/"))) for c in near)]


def _claimed(claim: str) -> str:
    """A claim as `synthesis claim` takes it again: a folder by its path, since a claim covers what is beneath it."""
    folder = claim[:-3] if claim.endswith("/**") else ""
    return _arg(folder if folder and os.path.isdir(folder) else claim)


def _sessions(report) -> list:
    """The board's sessions, each file read on its own: one that cannot be opened or parsed is counted and reported, and
    costs only itself (board.sessions() passes over one it cannot parse, and stops at one it cannot open)."""
    folder, found, dropped = paths.board() / "sessions", [], []
    for file in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            found.append(board._session(json.loads(file.read_text(encoding="utf-8"))))
        except Exception as exc:
            dropped.append(f"{file.name} ({type(exc).__name__})")
    report.read["sessions"] = len(found) + len(dropped)
    if dropped:
        report.add("unknown", "claims", "board", f"{len(dropped)} session file{'s' * (len(dropped) != 1)} cannot be read, so the "
                   f"claims {'it holds are' if len(dropped) == 1 else 'they hold are'} not known, and a step below may touch work "
                   f"claimed there: {', '.join(dropped[:5])}", ("principal", f"mend or archive each in {doctor._short(folder)}: a "
                                                                             "session file is one JSON object the board wrote"))
    return found


# ---- the installed side and the schedules ----------------------------------------------------------------------------

def installed(report, config, home: Path, fetch: bool) -> None:
    """Each doctor check that only reads, one at a time, so one that raises costs only its own line; what the doctor last
    saw of each harness's hook approval; with fetch, the stable release's version."""
    from synthesis import project, rituals, sessions

    def prompts():
        try:
            return doctor.check_prompt_check(rituals.config())
        except (OSError, ValueError) as exc:
            return doctor.check_prompt_check(None, str(exc)[:120])

    def codex():  # its own config file, read as the doctor reads it
        try:
            toml = doctor.read_toml((paths.codex_home() / "config.toml").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            toml = {}
        return [doctor.check_codex_features(toml), doctor.check_codex_doc_bytes(toml), doctor.check_codex_board(toml, home / "board",
                home / "approvals", home / "outbox"), doctor.check_codex_hooks_file(paths.codex_home()), doctor.check_codex_nested_hooks(paths.codex_home())]
    checks = [("runtime", lambda: doctor.check_runtime(home)), ("config", lambda: doctor.check_config(home)),
              ("board", lambda: doctor.check_board(home)), ("approvals", lambda: doctor.check_approvals_layout(home))]
    if (home / "bin" / "synthesis-hook").is_file():  # when it is missing, the runtime's line says so
        checks += [("hook script", lambda: doctor.check_hook_script(home)), ("hook interpreter", lambda: doctor.check_interpreter(home))]
    checks += [("home paths", lambda: doctor.check_home_paths([home / "config.json", *rituals.workspace_files()])), ("outbox", lambda: doctor.check_outbox(
        paths.outbox(), *doctor.connector_files())), ("teardown", lambda: doctor.check_teardown(home / "teardown.jsonl")), (
        "sandbox", lambda: doctor.check_sandbox([h for h in doctor.HARNESSES if _present(h)])), ("machine security", lambda: doctor.check_security(
            paths.account_home())), ("prompt check", prompts)]
    if config is not None:
        checks += [("sessions repos", lambda: doctor.check_sessions_repos(sessions.repos(), home / "sessions" / ".state")), (
            "decision packets", lambda: doctor.check_packets(project.roots())), ("browser accounts", lambda: doctor.check_browser_accounts(
                config, paths.read_json(paths.approvals() / "browser-accounts.json")))]
        checks += [("pr gate", lambda: doctor.check_pr_gate(config["pr_gated"], doctor.workspace_repos(config), run=_screened))] if config.get(
            "pr_gated") is not None else []
        checks += [("temporary addresses", lambda: doctor.check_temporary_addresses(config))] if "temporary_addresses" in config else []
    checks += [("codex", codex)] * _present("codex") + [("claude transcripts", lambda c=c, n=n: doctor.check_claude_retention(
        c / "settings.json", doctor._short(c) if n else "")) for n, c in enumerate(paths.claude_dirs(config))] * _present("claude")  # each Claude home's (C2)
    checks += [("latest release", lambda: doctor.check_latest({"runtime": _version(home)}, "stable"))] if fetch else []
    for name, read in checks:
        found = report.guard("installed", name, read, [])
        for check in (c for c in (found if isinstance(found, list) else [found]) if c):  # a check with nothing to say answers None
            report.doctor(check, "installed")
    _approvals(report)


def _screened(argv: list, **how):
    """The PR-gate check's git, run only where the repository's own configuration names no program git would run for it
    (gpg.program, with log.showSignature, runs under `git log`); elsewhere it is not run, and the check cannot read there."""
    if _programs(Path(argv[argv.index("-C") + 1]), ("log", "symbolic-ref")):
        raise subprocess.SubprocessError("its own git configuration names a program")
    return subprocess.run(argv, **how)


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
    """Each workspace folder, with its checkouts and what its .agents/repos.yaml declares (never what is dormant); each
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
            except Exception as exc:  # a declaration of another shape too: what cannot be read is never an empty list
                report.add("unknown", "workspaces", doctor._short(manifest), f"cannot be read ({type(exc).__name__}: {exc}), so what "
                           "the workspace declares is not known", ("principal", f"mend {doctor._short(manifest)}: its repos are a list "
                                                                                "of repositories, each with its own name"))
        spaces.append((folder, report.guard("workspaces", doctor._short(folder), lambda folder=folder: _discovered(folder), []), declared))
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
    """Every checkout in each workspace folder, read by the strand scan's own check on its checked-out branch (as --discover
    reads it), with every uncommitted file listed, each `.git` git cannot read, and each repository a workspace declares
    with no clone here. Git runs only where the repository's own configuration names no program. Returns (path, what was
    read) for each checkout read."""
    from synthesis import guards
    entries = {}
    for _, found, declared in spaces:  # a declared clone, read as a found one is, wherever it lies
        for row in found + [{**r, "excluded": False, "branches": None} for r in declared]:
            entries.setdefault(os.path.realpath(row["path"]), row)
    order, subs = sorted(entries), tuple(guards.GIT_SCANNERS["repo_state.py"]) + ("fetch",) * fetch

    def read(real: str):
        row = entries[real]
        if not os.path.lexists(Path(row["path"]) / ".git"):
            return None  # declared, with no clone here
        why = _gitdir(Path(row["path"]) / ".git")
        if why:  # found or declared, said once, and never cloned over
            return {"unread": why}
        try:
            named = _programs(Path(row["path"]), subs)
            found = {"programs": named} if named else scan.check(row, fetch, False)
            if found.get("dirty"):  # the scan lists twenty: every path by its own name, an untracked folder as one
                listed = scan.git(Path(row["path"]), "status", "--porcelain=v1", "-z", "--untracked-files=normal", "--no-renames")
                found["files"] = [entry[3:] for entry in listed.split("\0") if len(entry) > 3]
            return found
        except Exception as exc:  # what cannot be read is never read as fine
            return {"error": str(exc) or type(exc).__name__}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read, order))
    own = paths.session_id()  # this session's own claims hold its own work, which it repairs itself
    live = [(s, [_split(c) for c in s.claims]) for s in sessions if s.claims and not s.stale and s.session != own]
    quiet = [(s, [_split(c) for c in s.claims]) for s in sessions if s.claims and s.stale]
    landed = [kept for real, found in zip(order, results) for kept in [report.guard("repositories", doctor._short(real), lambda
              real=real, found=found: _repository(report, scan, entries[real], found, live, quiet, fetch))] if kept]
    if landed:  # one line for them all, and no step: what a worktree whose work merged needs is the principal's tidying
        report.add("warn", "repositories", f"{len(landed)} checkout{'s' * (len(landed) != 1)}", "each on a branch with no upstream, or "
                   "a detached HEAD, whose commits a remote already holds, so nothing in them is at risk; one whose work is done "
                   "can be removed: "
                   + ", ".join(f"{short} ({branch})" for short, branch in landed[:5]) + (", ..." if len(landed) > 5 else ""))
    report.read["repositories"] = len(order)
    return [(real, found) for real, found in zip(order, results) if found is not None]


def _repository(report, scan, row: dict, found, live: list, quiet: list, fetch: bool):
    """One repository's finding, with its steps in the order they run: back on a branch, the commit of the paths no live
    claim covers (past NAMED of them, the principal's choice of what is work), then the upstream or the integration. A
    live seat whose claim covers work here is asked about it, and with a seat asked nothing more than the commit is
    planned: the push is that seat's, after its own commit. A checkout whose one condition is a branch with no upstream
    whose commits a remote already holds is no finding of its own: it returns (path, branch) for the area's one line."""
    path = Path(row["path"])
    where, short, real = _arg(path), doctor._short(path), os.path.realpath(path)
    if found is None:
        origin = str((row.get("remotes") or {}).get("origin") or "")
        report.add("fail" if row.get("ritual_sync") is True else "warn", "repositories", short, "declared in .agents/repos.yaml, with "
                   "no clone here", ("agent", f"git clone {_arg(origin)} {where}") if origin else ("principal", f"clone it to {where}: "
                                                                                                    "its workspace declares no origin for it"))
        return
    if "unread" in found:
        report.add("unknown", "repositories", short, f"its .git is no git folder git can read: {found['unread']}", (
            "principal", f"look at {doctor._short(path / '.git')}: restore what it names, or move the folder away"))
        return
    if "programs" in found or "error" in found:
        named = found.get("programs") or []
        show = f" (`git -C {where} config --show-origin --get-all {named[0]}` shows it)" if named and re.fullmatch(r"[\w.-]+", named[0]) else ""
        report.add("unknown", "repositories", short, f"its own git configuration names a program git would run here ({', '.join(named)}), "
                   "so the review ran no git in it" if named else f"the review could not read it ({found['error']})",
                   ("principal", f"look at what {named[0]} names and take it out unless the principal put it there{show}" if named else
                    f"look at {short}'s git repository by hand"))
        return
    state, items, said, steps, landed = found["state"], found["branches"], [], [], []
    if state in ("CURRENT", "CACHED", "EXCLUDED"):
        return
    files = found.get("files", [])
    asked = [(s, mine) for s, claims in live for mine in [_covered(claims, real, files)] if mine]
    taken = {f for _, mine in asked for f in mine}
    unclaimed = [f for f in files if f not in taken]
    if state == "UNREACHABLE":
        said.append(f"git cannot read it: {found.get('reason', '')}")
        steps.append(("principal", f"`git -C {where} fetch --all --prune` fails ({found.get('reason', '')}): restore its remote's sign-in "
                      "or the network, then run it again" if fetch else f"`git -C {where} status` fails ({found.get('reason', '')}): mend "
                      "the repository by hand"))
    elif state == "BLIND" and not items:
        held = _holder(scan, path, "HEAD")
        said.append(f"HEAD is detached at a commit {held} holds" if held else "HEAD is detached: commits made here are on no branch")
        landed += [f"detached, on {held}"] if held else []
        steps += [] if held else [_onto_branch(scan, path, where)]
    if files:
        folders = sum(f.endswith("/") for f in files)
        counts = [f"{n} {what}{'s' * (n != 1)}" for n, what in ((len(files) - folders, "uncommitted file"), (folders, "untracked folder")) if n]
        said.append(" and ".join(counts) + " (" + ", ".join(files[:3]) + (", ..." if len(files) > 3 else "") + ")")
    commit = [("agent", f"git -C {where} add -- {' '.join(map(shlex.quote, unclaimed))} && git -C {where} commit -m {shlex.quote(COMMIT)} "
               f"-- {' '.join(map(shlex.quote, unclaimed))}")] if 0 < len(unclaimed) <= NAMED else []
    sort = [("principal", f"decide which of the {len(unclaimed)} uncommitted paths in {short} are work, and commit those (`git -C {where} "
             f"status` lists them): more than the {NAMED} one step of this plan names")] if len(unclaimed) > NAMED else []
    steps += commit + sort
    lost = state == "UNREACHABLE" or (state == "BLIND" and not items and not landed)
    for item in items:
        branch, upstream = item["branch"], item.get("upstream", "")
        held = _holder(scan, path, f"refs/heads/{branch}") if item["state"] == "BLIND" else ""
        if held:  # a worktree whose work merged, or a branch pushed under another name: nothing in it is at risk
            said.append(f"branch {branch} has no upstream; {held} holds its commits")
            landed.append(f"{branch}, on {held}")
            continue
        if item["state"] == "BLIND":
            said.append(f"branch {branch} has no upstream, and no remote this checkout knows holds its commits")
            steps.append(_upstream(scan, path, where, branch))
            lost = True
            continue
        ahead, behind = item.get("ahead", 0), item.get("behind", 0)
        said += [f"{branch} and {upstream} have diverged: {ahead} commit{'s' * (ahead != 1)} here, {behind} there"] if ahead and behind else [
            f"{branch} is {n} commit{'s' * (n != 1)} {how} {upstream}" for n, how in ((ahead, "ahead of"), (behind, "behind")) if n]
        ahead += bool(commit)  # the commit above is one more for its upstream
        steps += [("principal", f"rebase onto {upstream} (`git -C {where} pull --rebase`) or merge it (`git -C {where} pull --no-rebase`), "
                   f"then `git -C {where} push`")] if ahead and behind else [("agent", f"git -C {where} push")] if ahead else [
            ("agent", f"git -C {where} merge --ff-only {shlex.quote(upstream)}")] if behind else []
    said += [f"live session {s.short} claims " + (f"{len(mine)} of them" if mine != [""] else "it") for s, mine in asked] + [
        f"under the claim of session {s.short}, quiet {int((time.time() - s.seen) / 3600)} h" for s, claims in quiet if _covered(claims, real, files)]
    if asked:
        steps = commit + sort + [("agent", f"synthesis msg {shlex.quote(s.session)} {shlex.quote(LIVE.format(short))}") for s, _ in asked]
    if landed and len(said) == len(landed) and not steps:
        return short, landed[0]
    report.add("fail" if lost else "warn", "repositories", short, "; ".join(said), *steps)
    return None


def _holder(scan, path: Path, ref: str) -> str:
    """The first remote-tracking branch that holds every commit of `ref` (a branch's ref, or HEAD), a remote's HEAD left
    out; '' where none does, or git cannot tell."""
    try:
        listed = scan.git(path, "for-each-ref", "--contains", ref, "--count=8", "--format=%(refname:short)",
                          "refs/remotes").split()
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return ""
    return next((ref for ref in listed if not ref.endswith("/HEAD") and "/" in ref), "")


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
        split = [_split(c) for c in s.claims]
        under, n = [doctor._short(p) for p, found in scanned if found.get("files") and _covered(split, p, found["files"])], len(s.claims)
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
        report.guard("projects", doctor._short(root), lambda root=root, kind=kind, value=value: _root(report, config, held, command, root,
                                                                                                    kind, value))


def _root(report, config: dict, held: list, command: str, root: Path, kind: str, value) -> None:
    """One knowledge root's findings, from what its audit found."""
    short = doctor._short(root)
    if kind == "absent":  # a root found by the default pattern always has one: only a configured root can lack it
        if config.get("knowledge_roots"):
            report.add("warn", "projects", short, "the config names this knowledge root, and it has no projects/ folder here", (
                "principal", f"bring its workspace onto this Mac, or take it out of knowledge_roots in "
                f"{doctor._short(paths.config_file())} (`synthesis config apply <file>` takes the principal's code)"))
        return
    if kind != "read":
        report.add("unknown", "projects", short, f"{value}, so its records were not read", ("principal", f"look at {short}'s git "
                                                                                            "repository by hand"))
        return
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
    """What is wrong on this Mac, by severity, and the repair plan; nothing is written. `run` asks launchd, and only that.
    Each area runs guarded: what raises in one is an unknown finding for it, and the rest is still read."""
    began, home, report = time.time(), paths.home(), _Report()
    try:
        config = paths.config()
    except paths.Unreadable as exc:
        config = None
        report.add("unknown", "workspaces", doctor._short(paths.config_file()), f"cannot be read ({exc}), so the workspaces, knowledge "
                   "roots and sessions repos it names are not known, and none was read", ("principal", f"make {doctor._short(paths.config_file())} "
                   "one JSON object of settings again (it is sealed: `synthesis config apply <file>` takes the principal's code)"))
    report.guard("installed", "installed side", lambda: installed(report, config, home, fetch))
    sessions = report.guard("claims", "board", lambda: _sessions(report), [])
    report.guard("schedules", "schedules", lambda: schedules(report, home, config, run, platform))
    scanned = []
    if config is not None:
        try:
            scan = _load("synthesis-daily-rituals", "repo_state.py")
        except (Exception, SystemExit) as exc:  # a script that cannot load is never read as one that found nothing
            scan = None
            report.add("unknown", "repositories", "strand scan", f"{doctor._short(SKILLS / 'synthesis-daily-rituals' / 'scripts' / 'repo_state.py')} "
                       f"cannot be loaded ({exc}), so no repository was read", _reinstall(home))
        spaces = report.guard("workspaces", "workspaces", lambda: workspaces(report, scan, config, sessions), [])
        scanned = report.guard("repositories", "repositories", lambda: repositories(report, scan, spaces, sessions, fetch), []) if scan else []
        report.guard("projects", "projects", lambda: projects(report, config, scanned))
    report.guard("claims", "claims", lambda: claims(report, sessions, scanned))
    return report.done(fetch, began, config or {})


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
    parser.add_argument("--fetch", action="store_true", help="first fetch every repository (git writes what it brings and its "
                        "remote-tracking refs) and read the stable release's version from GitHub; network")
    args = parser.parse_args(list(argv or []))
    sys.dont_write_bytecode = True  # nothing compiled into the release beside a script it loads
    try:
        report = review(fetch=args.fetch)
    except Exception as exc:  # the last resort: a review that could not finish is never read as one that found nothing
        print(f"synthesis review could not finish ({type(exc).__name__}: {exc}), so nothing is known of this Mac", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=1) if args.json else render(report))
    return report["exit"]

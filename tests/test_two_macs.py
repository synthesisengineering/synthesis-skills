"""Two Macs, end to end (BACKLOG D5; the plan's Q32): what the principal checks on a second Mac, run on two homes of one
machine that share a bare remote for the workspace's knowledge repository and one for its sessions repository.

Each Mac starts as an empty home and is brought up as his steps bring a new Mac up: `setup.py all --git-hooks --kb`
from the checkout (the runtime and its launchers, the commit check in git's global config, the workspace's
repositories from its repos.yaml), with a stand-in Claude Code as the only harness; then the config his private layer
copies in, the same file on both Macs. Every command after that runs as its own process through the launchers the
install wrote, as it runs on a Mac:

- check A: a durable message to a project and `synthesis handoff` on Mac A; on Mac B the arrive step's pull, then
  `synthesis resume` names one carried message and `synthesis inbox` shows it quoted, once;
- check B: a day-end recorded on each Mac and each Mac's hourly job, run as its LaunchAgent runs it; then
  `ritual_state.py query summary` on either Mac counts both closes.

One machine stands in for two, so each Mac names its ritual file with SYNTHESIS_HOST (a Mac's own name and platform
id do that on two machines). What no test here can show is iCloud's own sync, a second harness's sign-in and GitHub's
authentication: the remotes are bare repositories on this disk, and the config arrives as a copy.
"""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills" / "synthesis-onboarding" / "scripts" / "setup.py"
WORKSPACE, OTHER = "demo", "client"
# What a test process carries that a Mac's own shell does not: the suite's homes and a harness's session.
NOT_A_MACS = ("SYNTHESIS_HOME", "GIT_CONFIG_GLOBAL", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
              "XDG_STATE_HOME", "XDG_CACHE_HOME", "SYNTHESIS_CLAUDE_DESKTOP_DIR", "SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID",
              "CLAUDECODE", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "MUSE_PLUGIN_ROOT", "RITUAL_STATE_DIR", "SYNTHESIS_HOST")

FAKE_CLAUDE = '''#!{python}
"""Claude Code as setup asks it: its plugin listing, a marketplace and an install, each logged."""
import json, os, sys
args = sys.argv[1:]
with open({log!r}, "a") as out:
    out.write(" ".join(args) + "\\n")
if args[:2] == ["plugin", "list"]:
    print(json.dumps([{{"id": "synthesis-skills@synthesis-engineering", "version": "5", "enabled": True, "installPath": {root!r}}}]
                     if os.path.exists({state!r}) else []))
elif args[:2] == ["plugin", "install"]:
    open({state!r}, "w").close()
'''


def run(argv: list, env: dict, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run([str(a) for a in argv], env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    assert not check or done.returncode == 0, f"{argv[:4]} exited {done.returncode}:\n{done.stdout}\n{done.stderr}"
    return done


def git(*args, env: dict | None = None) -> str:
    return run(["git", *args], env or dict(os.environ)).stdout.strip()


class Mac:
    """One Mac: an empty home of its own, its own git identity in that home, and its own Claude Code."""

    def __init__(self, name: str, folder: Path):
        self.name, self.home = name, folder / "home"
        self.home.mkdir(parents=True)
        (self.home / ".gitconfig").write_text("[user]\n\temail = test@example.com\n\tname = test\n[init]\n\tdefaultBranch = main\n",
                                              encoding="utf-8")
        self.synthesis_home = self.home / ".synthesis" / "v5"
        self.workspace = self.home / "workspaces" / WORKSPACE
        self.kb, self.sessions_repo = self.workspace / f"ai-knowledge-{WORKSPACE}", self.workspace / f"ai-sessions-{WORKSPACE}"
        self.claude_log, claude = folder / "claude.log", folder / "bin" / "claude"
        claude.parent.mkdir()
        claude.write_text(FAKE_CLAUDE.format(python=sys.executable, log=str(self.claude_log), root=str(ROOT),
                                             state=str(folder / "claude-installed")), encoding="utf-8")
        claude.chmod(0o755)
        self.claude = claude

    def env(self, session: str = "") -> dict:
        env = {k: v for k, v in os.environ.items() if k not in NOT_A_MACS}
        env.update(HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1", SYNTHESIS_HOST=f"Mac {self.name}",
                   SYNTHESIS_CLAUDE_BIN=str(self.claude), SYNTHESIS_CODEX_BIN="", SYNTHESIS_MUSE_BIN="")
        return {**env, "SYNTHESIS_SESSION": session} if session else env

    def setup(self, *args: str) -> str:
        return run([sys.executable, SETUP, *args, "--no-input"], self.env()).stdout

    def synthesis(self, *args: str, session: str = "", check: bool = True) -> subprocess.CompletedProcess:
        return run([self.synthesis_home / "bin" / "synthesis", *args], self.env(session), check)

    def script(self, skill: str, name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """A skill's script as the rituals run it: the runtime's copy, with the user's site folder left out."""
        return run([sys.executable, "-s", self.synthesis_home / "current" / "skills" / skill / "scripts" / name, *args],
                   self.env(), check)

    def private_layer(self, config: dict, rituals: dict) -> None:
        """The principal's config as his private layer copies it in, and his ritual config: one file for every Mac."""
        (self.synthesis_home / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (self.synthesis_home / "rituals").mkdir(exist_ok=True)
        (self.synthesis_home / "rituals" / "config.json").write_text(json.dumps(rituals), encoding="utf-8")

    def hourly(self) -> subprocess.CompletedProcess:
        """The hourly LaunchAgent's own command line, in an environment as bare as launchd gives a job."""
        job = plistlib.loads((self.home / "Library" / "LaunchAgents" / "com.synthesis.sessions-export.plist").read_bytes())
        env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "SHELL": "/bin/bash", "GIT_CONFIG_NOSYSTEM": "1",
               "SYNTHESIS_HOST": f"Mac {self.name}", **{k: os.environ[k] for k in ("USER", "LOGNAME", "TMPDIR") if k in os.environ}}
        return run(job["ProgramArguments"], env)


@pytest.fixture
def remotes(tmp_path):
    """The workspace's knowledge repository, with its repos.yaml and one project, and its sessions repository, each
    published to a bare remote."""
    def publish(name: str, files: dict) -> Path:
        work, bare = tmp_path / "authoring" / name, tmp_path / "remotes" / f"{name}.git"
        for rel, text in files.items():
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_text(text, encoding="utf-8")
        git("init", "-q", "-b", "main", str(work))
        git("-C", str(work), "add", "-A")
        git("-C", str(work), "commit", "-qm", "start")
        git("clone", "-q", "--bare", str(work), str(bare))
        return bare
    sessions = publish(f"ai-sessions-{WORKSPACE}", {"README.md": "Agent conversations, written by synthesis sessions sync.\n"})
    other = publish(f"ai-sessions-{OTHER}", {"README.md": "Another workspace's conversations.\n"})
    kb = tmp_path / "remotes" / f"ai-knowledge-{WORKSPACE}.git"
    publish(f"ai-knowledge-{WORKSPACE}", {
        ".agents/repos.yaml": (f"workspace: {WORKSPACE}\nrepos:\n"
                               f"  - name: ai-knowledge-{WORKSPACE}\n    path: ai-knowledge-{WORKSPACE}/\n    remotes:\n      origin: {kb}\n"
                               f"  - name: ai-sessions-{WORKSPACE}\n    path: ai-sessions-{WORKSPACE}/\n    remotes:\n      origin: {sessions}\n"),
        ".agents/workspace-AGENTS.md": "# The demo workspace\n",
        "projects/alpha/CONTEXT.md": ("# Alpha\n\n<!-- synthesis-current-state:start -->\n**Phase:** two Macs\n**Status:** active\n"
                                      "<!-- synthesis-current-state:end -->\n\n## What's Next\n\n1. [ ] Read the second Mac's report\n"),
    })
    return {"kb": kb, "sessions": sessions, "other": other}


# One config for every Mac, as the principal keeps his: it names the sessions repo of a workspace that only Mac A
# holds, as his names client workspaces a second Mac need not hold.
CONFIG = {"knowledge_roots": [f"~/workspaces/{WORKSPACE}/ai-knowledge-{WORKSPACE}"],
          "sessions_repos": {WORKSPACE: f"~/workspaces/{WORKSPACE}/ai-sessions-{WORKSPACE}",
                             OTHER: f"~/workspaces/{OTHER}/ai-sessions-{OTHER}"}}
RITUALS = {"workspaces": {WORKSPACE: {"streak": "expected-days", "plans_dirs": []}}}


@pytest.fixture
def macs(tmp_path, remotes):
    """Mac A and Mac B, each brought up from an empty home by setup, with the hourly job written as launchd would load
    it, and given the principal's config; Mac A also holds the other workspace's sessions repo."""
    a, b = Mac("A", tmp_path / "mac-a"), Mac("B", tmp_path / "mac-b")
    for mac in (a, b):
        mac.said = mac.setup("all", "--git-hooks", "--sessions-export", "--no-launchctl", "--kb", str(remotes["kb"]))
        mac.private_layer(CONFIG, RITUALS)
    git("clone", "-q", str(remotes["other"]), str(a.home / "workspaces" / OTHER / f"ai-sessions-{OTHER}"), env=a.env())
    return a, b


def test_a_second_mac_comes_up_from_an_empty_home_with_the_runtime_the_commit_check_and_the_workspace(macs, remotes):
    _, b = macs
    assert "synthesis runtime" in b.said and f"core.hooksPath -> {b.synthesis_home / 'git-hooks'}" in b.said, b.said
    assert git("config", "--global", "core.hooksPath", env=b.env()) == str(b.synthesis_home / "git-hooks")
    assert os.access(b.synthesis_home / "bin" / "synthesis", os.X_OK) and (b.synthesis_home / "current" / "synthesis").is_dir()
    assert "plugin marketplace add synthesisengineering/synthesis-skills@stable" in b.claude_log.read_text(encoding="utf-8")
    assert f"ai-knowledge-{WORKSPACE}: cloned" in b.said and f"ai-sessions-{WORKSPACE}: cloned" in b.said, b.said
    for repo, remote in ((b.kb, remotes["kb"]), (b.sessions_repo, remotes["sessions"])):
        assert git("-C", str(repo), "remote", "get-url", "origin", env=b.env()) == str(remote)
        assert git("-C", str(repo), "status", "--porcelain", env=b.env()) == ""  # nothing setup wrote is left uncommitted there
        assert git("-C", str(repo), "rev-parse", "--abbrev-ref", "@{upstream}", env=b.env()) == "origin/main"
    assert os.readlink(b.workspace / "AGENTS.md") == f"ai-knowledge-{WORKSPACE}/.agents/workspace-AGENTS.md"
    assert (b.workspace / ".agents" / "repos.yaml").is_file()
    job = plistlib.loads((b.home / "Library" / "LaunchAgents" / "com.synthesis.sessions-export.plist").read_bytes())
    assert job["StartInterval"] == 3600 and job["ProgramArguments"][-1] == (
        f'"{b.synthesis_home / "bin" / "synthesis"}" sessions export --all --scheduled; '
        f'"{b.synthesis_home / "bin" / "synthesis"}" sessions sync')  # this home's own command, and no other home's
    assert b.synthesis("version").stdout.strip()  # the installed command runs, on the interpreter the install pinned
    scratch = b.workspace / "scratch"  # the commit check runs on this Mac's commits, from its own home: a key file's name
    git("init", "-q", str(scratch), env=b.env())  # is refused in every repository
    (scratch / "id_ed25519").write_text("not a key\n", encoding="utf-8")
    git("-C", str(scratch), "add", "id_ed25519", env=b.env())
    refused = run(["git", "-C", str(scratch), "commit", "-qm", "note"], b.env(), check=False)
    assert refused.returncode != 0 and "a credential file name" in refused.stdout + refused.stderr, refused


def test_a_durable_message_handed_off_on_one_mac_is_read_quoted_once_on_the_other(macs):
    a, b = macs
    text = "Second Mac: read this once, then tell the principal it arrived"
    a.synthesis("claim", str(a.kb / "projects" / "alpha"), "--project", "alpha", "--goal", "the two-Mac check", session="S-A")
    assert "kept for every session that works on alpha" in a.synthesis("msg", "project:alpha", "--durable", text, session="S-A").stdout
    handed = a.synthesis("handoff", "-m", "Carry a message to the other Mac", session="S-A").stdout
    assert "project alpha: carried 1 durable message(s)" in handed and handed.rstrip().splitlines()[-1].startswith("READY"), handed

    early = b.synthesis("resume", "alpha").stdout  # resume reads local git and never fetches: nothing has arrived yet
    assert "Phase: two Macs" in early and "carried" not in early, early
    pulled = b.script("synthesis-daily-rituals", "repo_state.py", "--discover", str(b.home / "workspaces"), "--fetch", "--ff")
    assert f"ai-knowledge-{WORKSPACE}" in pulled.stdout, pulled.stdout

    told = b.synthesis("resume", "alpha", session="S-B").stdout
    assert "1 message(s) carried in this project's records that this Mac has not shown: `synthesis inbox`" in told, told
    assert text not in told  # named, never quoted, by resume
    shown = b.synthesis("inbox", session="S-B").stdout.splitlines()
    assert shown[0].startswith("--- carried in alpha's records (inbox/") and "from S-A by its own header" in shown[0], shown
    assert shown[1:] == [f"    > {text}"], shown
    assert b.synthesis("inbox", session="S-B").stdout == ""  # shown once on this Mac


def test_each_macs_day_end_is_counted_on_both_once_each_has_synced_after_it(macs, remotes):
    a, b = macs
    today = date.today().isoformat()

    def close(mac: Mac, session: str) -> None:  # the day-end's record step, as day-end.md has it run
        said = mac.script("synthesis-daily-rituals", "ritual_state.py", "record", "--direction", "day-end", "--workspace", WORKSPACE,
                          "--date", today, "--session", session).stdout
        assert f"recorded day-end {WORKSPACE} {today} (clean)" in said and "`synthesis sessions sync` carries it to" in said, said

    def hourly(mac: Mac) -> str:
        said = mac.hourly().stdout
        assert "FAILED" not in said and f"{WORKSPACE}: ai-sessions-{WORKSPACE} up to date" in said, said
        return said

    def closes(mac: Mac) -> tuple:  # this Mac's name, and each Mac's newest close of the workspace, as its summary reads them
        view = json.loads(mac.script("synthesis-daily-rituals", "ritual_state.py", "query", "summary", "--json").stdout)
        assert view["workspaces"][WORKSPACE]["last_day_end"]["date"] == today
        return view["host"], view["workspaces"][WORKSPACE]["last_day_end_by_host"]

    close(a, "S-A")
    assert f"{WORKSPACE}: ritual history: 1 record(s) of this Mac committed" in hourly(a)
    close(b, "S-B")
    said = hourly(b)  # it pulls Mac A's file before it writes its own
    assert f"{WORKSPACE}: ritual history: 1 record(s) of this Mac committed" in said
    assert f"{OTHER}: " in said and "holds none of its sessions or ritual records" in said, said  # not this Mac's workspace
    b.synthesis("claim", str(b.kb / "projects" / "alpha"), "--project", "alpha", "--goal", "close the day", session="S-B")
    (b.kb / "projects" / "alpha" / "sessions").mkdir()
    (b.kb / "projects" / "alpha" / "sessions" / "2026-11.md").write_text("# November\n\n### 2026-11-18: closed on Mac B\n",
                                                                         encoding="utf-8")
    handed = b.synthesis("handoff", "-m", "Close the day", session="S-B").stdout  # the day-end's last step on this Mac
    assert handed.rstrip().splitlines()[-1].startswith("READY"), handed
    (host_a, seen_a), (host_b, seen_b) = closes(a), closes(b)
    assert host_a != host_b
    assert seen_b == {host_a: today, host_b: today}  # the Mac whose sync ran last counts both closes
    assert seen_a == {host_a: today}  # and the other counts its own until its next sync
    hourly(a)
    assert closes(a) == (host_a, {host_a: today, host_b: today})
    assert sorted(git("-C", str(remotes["sessions"]), "ls-tree", "--name-only", "main", "rituals/").splitlines()) == sorted(
        [f"rituals/{host_a}.jsonl", f"rituals/{host_b}.jsonl"])  # each Mac wrote its own file, and only its own
    shown = a.script("synthesis-daily-rituals", "ritual_state.py", "query", "summary").stdout  # what the principal reads
    assert f"closes by host: {host_a} {today} (this Mac), {host_b} {today}" in shown, shown

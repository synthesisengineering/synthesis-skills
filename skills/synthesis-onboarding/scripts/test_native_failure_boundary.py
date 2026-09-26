"""Exercise native acquisition failures through the real bootstrap and CLI.

Only client executables are stand-ins. Source materialization, policy selection,
transaction locking, the engine, and explicit direct copies run unchanged in a
disposable home. Network acquisition and service activation are refused.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

import pytest

import onboard
from test_onboard import REPO_ROOT, Sandbox, snapshot_current_source


def communicate_with_copy_progress(process, completed_copies, *, clock=time.monotonic):
    """Allow real bulk copying, while keeping a 60-second no-progress bound.

    A full catalog copy is materially more work than a native failure probe.
    Only newly completed, source-bound receipts count as progress; repeated
    subprocess activity cannot extend the wait. The entire copy remains capped.

    The idle bound was 25 seconds until CI evidence showed a loaded
    macos-latest runner still in setup preamble — plugin-list probes
    advancing, zero receipts yet — at 25.0 seconds (4.138.0, 4.139.0).
    Sixty seconds absorbs preamble variance on shared runners while
    still catching a true hang well under the total cap.
    """
    started = clock()
    idle_deadline = started + 60
    total_deadline = started + 120
    high_watermark = 0
    while True:
        remaining = min(idle_deadline, total_deadline) - clock()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, clock() - started)
        try:
            return process.communicate(timeout=min(1, remaining))
        except subprocess.TimeoutExpired:
            completed = completed_copies()
            if completed > high_watermark:
                high_watermark = completed
                idle_deadline = clock() + 60


def completed_copy_receipts(home, source_info, client):
    source, _, commit = source_info
    selected = ".claude" if client == "claude" else ".agents"
    completed = 0
    for skill in (source / "skills").glob("*/SKILL.md"):
        receipt = home / selected / "skills" / skill.parent.name / ".source.json"
        try:
            record = json.loads(receipt.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and all(record.get(key) == value for key, value in {
            "source_repo": "github.com/synthesisengineering/synthesis-skills",
            "source_type": "public", "source_commit": commit,
            "source_path": "skills/" + skill.parent.name + "/SKILL.md",
        }.items()):
            completed += 1
    return completed


class CopyClock:
    """Deterministic process clock for the fixture watchdog's time boundaries."""

    def __init__(self, completes_at=None):
        self.now = 0
        self.completes_at = completes_at
        self.args = ["fixture-copy"]

    def communicate(self, timeout):
        self.now += timeout
        if self.completes_at is not None and self.now >= self.completes_at:
            return "completed", ""
        raise subprocess.TimeoutExpired(self.args, timeout)


def test_copy_watchdog_allows_slow_completed_work_without_relaxing_stall_limit():
    process = CopyClock(completes_at=60)
    result = communicate_with_copy_progress(
        process, lambda: int(process.now // 10), clock=lambda: process.now,
    )
    assert result == ("completed", "")
    assert process.now == 60


def test_copy_watchdog_keeps_the_sixty_second_stall_boundary():
    process = CopyClock()
    with pytest.raises(subprocess.TimeoutExpired):
        communicate_with_copy_progress(
            process, lambda: int(process.now >= 10), clock=lambda: process.now,
        )
    assert process.now == 70


def test_copy_watchdog_has_an_absolute_ceiling_even_with_progress():
    process = CopyClock()
    with pytest.raises(subprocess.TimeoutExpired):
        communicate_with_copy_progress(
            process, lambda: int(process.now // 10), clock=lambda: process.now,
        )
    assert process.now == 120


def test_copy_watchdog_does_not_count_rewritten_receipts_as_new_progress():
    process = CopyClock()
    with pytest.raises(subprocess.TimeoutExpired):
        communicate_with_copy_progress(
            process, lambda: 1, clock=lambda: process.now,
        )
    assert process.now == 61


def test_copy_progress_counts_only_completed_selected_source_receipts(tmp_path):
    source = tmp_path / "source"
    skill = source / "skills/synthesis-fixture/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Fixture source\n")
    home = tmp_path / "home"
    commit = "a" * 40
    info = (source, "1.2.3", commit)
    receipt = home / ".claude/skills/synthesis-fixture/.source.json"
    receipt.parent.mkdir(parents=True)
    record = {
        "source_repo": "github.com/synthesisengineering/synthesis-skills",
        "source_type": "public", "source_commit": commit,
        "source_path": "skills/synthesis-fixture/SKILL.md",
    }
    for incomplete in ('{', '[]', 'null'):
        receipt.write_text(incomplete)
        assert completed_copy_receipts(home, info, "claude") == 0
    for key in record:
        receipt.write_text(json.dumps({**record, key: "unreviewed"}))
        assert completed_copy_receipts(home, info, "claude") == 0
    receipt.write_text(json.dumps(record))
    assert completed_copy_receipts(home, info, "claude") == 1
    assert completed_copy_receipts(home, info, "codex") == 0
    unknown = receipt.parent.parent / "foreign-skill/.source.json"
    unknown.parent.mkdir()
    unknown.write_text(json.dumps(record))
    assert completed_copy_receipts(home, info, "claude") == 1


def fixture_git(root, *args, env):
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        env=env, text=True, stderr=subprocess.PIPE,
    ).strip()


@pytest.fixture(scope="module")
def reviewed_source(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-failure-source")
    environment = {
        "PATH": os.environ["PATH"], "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_COUNT": "0",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_COMMITTER_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    source = snapshot_current_source(REPO_ROOT, root / "reviewed", environment)
    version = json.loads((source / ".codex-plugin/plugin.json").read_text())["version"]
    commit = fixture_git(source, "rev-parse", "HEAD", env=environment)
    fixture_git(source, "tag", "v" + version, env=environment)
    fixture_git(source, "branch", "stable", commit, env=environment)
    fixture_git(source, "update-ref", "refs/remotes/origin/stable", commit, env=environment)
    return source, version, commit


AUDIT_HOOK = r'''
import json, os, sys
from pathlib import Path
def record(value):
    with Path(os.environ["FAILURE_AUDIT_LOG"]).open("a") as stream:
        stream.write(json.dumps(value, default=str) + "\n")
record({"event": "python-start", "argv": sys.argv})
def audit(event, args):
    if event == "subprocess.Popen":
        command = args[1]
        record({"event": event, "command": command})
        tokens = list(command) if isinstance(command, (list, tuple)) else [str(command)]
        if tokens and Path(str(tokens[0])).name in {"launchctl", "systemctl", "security", "curl", "wget"}:
            record({"event": "refused-command", "command": command})
            raise PermissionError("Fixture refuses external command")
    if event in {"socket.connect", "socket.getaddrinfo"}:
        record({"event": "refused-network", "detail": event})
        raise PermissionError("Fixture refuses network")
sys.addaudithook(audit)
'''


FAKE_CLIENT = r'''
import json, os, sys
from pathlib import Path
root = Path(os.environ["FAILURE_CASE_ROOT"])
client = Path(sys.argv[0]).name
path = root / (client + "-state.json")
state = json.loads(path.read_text()) if path.exists() else {}
args = sys.argv[1:]
with (root / "native-commands.jsonl").open("a") as stream:
    stream.write(json.dumps({"client": client, "args": args}) + "\n")
if args[:2] == ["plugin", "list"]:
    installed = ([{"pluginId": "synthesis-skills@synthesis-engineering",
                   "name": "synthesis-skills", "version": state["version"], "enabled": True}]
                 if state.get("installed") else [])
    print(json.dumps({"installed": installed}))
elif args[:3] == ["plugin", "marketplace", "add"]:
    ref = args[3].rsplit("@", 1)[1] if client == "claude" else args[args.index("--ref") + 1]
    state["ref"] = ref
    path.write_text(json.dumps(state))
elif args[:2] in (["plugin", "install"], ["plugin", "add"]):
    if os.environ["FAILURE_NATIVE_MODE"] == "fail":
        print("Fixture native acquisition failure", file=sys.stderr)
        raise SystemExit(1)
    if os.environ["FAILURE_NATIVE_MODE"] != "unverified":
        state.update(installed=True, version=os.environ["FAILURE_REVIEWED_VERSION"])
        path.write_text(json.dumps(state))
'''


def run_isolated(source_info, tmp_path, profile, client, *, entry="bootstrap",
                 mode="fail", explicit_copy=False):
    source, version, _ = source_info
    box = Sandbox()
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    (helpers / "sitecustomize.py").write_text(AUDIT_HOOK)
    binary = helpers / client
    binary.write_text("#!" + sys.executable + "\n" + FAKE_CLIENT)
    binary.chmod(0o755)
    (helpers / "git").write_text(
        "#!/bin/sh\nfor arg in \"$@\"; do\n"
        " case \"$arg\" in fetch|clone|pull|push|ls-remote) "
        "printf '%s\\n' \"$*\" >> \"$FAILURE_GIT_NETWORK_LOG\"; exit 97;; esac\ndone\n"
        "exec /usr/bin/git \"$@\"\n"
    )
    (helpers / "git").chmod(0o755)
    environment = {key: os.environ[key] for key in ("LANG", "LC_ALL", "TMPDIR", "TZ") if key in os.environ}
    environment.update(box.env_overrides())
    environment.update({
        "SYNTHESIS_HOME": str(box.home), "SYNTHESIS_ONBOARD_SOURCE_DIR": str(source),
        "SYNTHESIS_INSTALL_BIN_DIR": str(box.home / ".local/bin"),
        "SYNTHESIS_CLAUDE_BIN": str(binary) if client == "claude" else "",
        "SYNTHESIS_CODEX_BIN": str(binary) if client == "codex" else "",
        "CODEX_HOME": str(box.home / ".codex"), "CLAUDE_CONFIG_DIR": str(box.home / ".claude"),
        "XDG_CACHE_HOME": str(box.home / ".cache"),
        "PATH": str(helpers) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        "PYTHONPATH": str(helpers), "PYTHONDONTWRITEBYTECODE": "1",
        "FAILURE_CASE_ROOT": str(box.root), "FAILURE_REVIEWED_VERSION": version,
        "FAILURE_NATIVE_MODE": mode, "FAILURE_AUDIT_LOG": str(tmp_path / "audit.jsonl"),
        "FAILURE_GIT_NETWORK_LOG": str(tmp_path / "network.txt"),
        "HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1",
        "ALL_PROXY": "http://127.0.0.1:1", "NO_PROXY": "",
    })
    if explicit_copy:
        environment["SYNTHESIS_ONBOARD_NO_PLUGIN_CLI"] = "1"
        # Ambient direct-copy overrides may not redirect the selected source or
        # expand the selected client set when the engine invokes its capability.
        environment.update({
            "SYNTHESIS_SKILLS_SOURCE_DIR": str(tmp_path / "unreviewed-source"),
            "SYNTHESIS_SKILLS_TARGETS": str(tmp_path / "unselected-target"),
            "SYNTHESIS_SKILLS_SOURCE_REPO": "https://example.invalid/unreviewed.git",
            "SYNTHESIS_SKILLS_SOURCE_TYPE": "organization",
        })
    bootstrap = ["sh", str(source / "onboard.sh")]
    if entry == "cli":
        # Materialize the stable command without installing any client payload.
        prepared = subprocess.run(
            bootstrap + ["status", "--json"], cwd=tmp_path,
            env={**environment, "SYNTHESIS_ONBOARD_VERSION_PIN": version},
            capture_output=True, text=True, timeout=30,
        )
        assert (box.home / ".local/bin/synthesis").is_file(), prepared.stdout + prepared.stderr
        (tmp_path / "audit.jsonl").write_text("")
    prefix = bootstrap if entry == "bootstrap" else [str(box.home / ".local/bin/synthesis")]
    command = prefix + ["setup", "--profile", profile, "--clients", client,
                        "--answers", str(box.answers(git_identity=("Fixture", "fixture@example.invalid"))),
                        "--no-services", "--pin", version, "--json"]
    proc = subprocess.Popen(command, env=environment, cwd=tmp_path, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    started = time.monotonic()
    timed_out = False
    try:
        if explicit_copy:
            stdout, stderr = communicate_with_copy_progress(
                proc, lambda: completed_copy_receipts(box.home, source_info, client),
            )
        else:
            stdout, stderr = proc.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=10)
    def json_file(relative):
        path = box.home / relative
        return json.loads(path.read_text()) if path.exists() else None
    result = {
        "returncode": proc.returncode, "timed_out": timed_out, "stdout": stdout, "stderr": stderr,
        "elapsed_seconds": time.monotonic() - started,
        "completed_copy_receipts": completed_copy_receipts(box.home, source_info, client),
        "active": json_file(".local/state/synthesis/active-release.json"),
        "desired": json_file(".config/synthesis/system-state.json"),
        "observations": json_file(".local/state/synthesis/observations.json"),
        "events": [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()],
        "network_attempts": (tmp_path / "network.txt").read_text() if (tmp_path / "network.txt").exists() else "",
    }
    (tmp_path / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result, box


@pytest.mark.parametrize("entry", ["bootstrap", "cli"])
@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("profile", ["skills-only", "full"])
def test_native_failure_preserves_reviewed_release_and_terminates(reviewed_source, tmp_path, profile, client, entry):
    result, box = run_isolated(reviewed_source, tmp_path, profile, client, entry=entry)
    assert not result["timed_out"], "Native failure reentered the active transaction; see result.json"
    assert result["returncode"] == 1, result["stdout"] + result["stderr"]
    assert result["active"]["channel"] == "pin"
    assert result["active"]["ref"] == "v" + reviewed_source[1]
    assert result["active"]["commit"] == reviewed_source[2]
    assert result["desired"] is None
    assert result["observations"]["transactions"][-1]["state"] == "aborted"
    assert not result["network_attempts"]
    assert not [event for event in result["events"] if event["event"].startswith("refused-")]
    starts = [event for event in result["events"] if event["event"] == "python-start"
              and event["argv"][0].endswith("/bootstrap.py")]
    assert len(starts) == (1 if entry == "bootstrap" else 0)
    assert "Fixture native acquisition failure" in result["stdout"] + result["stderr"]
    assert not list(box.home.glob(".claude/skills/*/SKILL.md"))
    assert not list(box.home.glob(".agents/skills/*/SKILL.md"))
    assert not list((box.home / "workspaces").glob("*"))


@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("profile", ["skills-only", "full"])
def test_native_success_retains_selected_profile_and_client(reviewed_source, tmp_path, profile, client):
    result, _ = run_isolated(reviewed_source, tmp_path, profile, client, mode="success")
    assert not result["timed_out"]
    assert result["returncode"] == 0, result["stdout"] + result["stderr"]
    assert result["active"]["channel"] == "pin"
    assert result["active"]["commit"] == reviewed_source[2]
    assert result["desired"]["profile"] == profile
    assert result["desired"]["clients"] == [client]
    assert result["desired"]["release"]["version_pin"] == reviewed_source[1]
    latest = result["observations"]["transactions"][-1]
    assert latest["state"] == "committed"
    assert latest["live-loaded"]["status"] == "restart-required"
    assert latest["outcome-verified"]["status"] == "not-requested"
    assert not result["network_attempts"]
    assert not [event for event in result["events"] if event["event"].startswith("refused-")]


@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("profile", ["skills-only", "full"])
def test_explicit_copy_is_bound_and_does_not_claim_native_readiness(reviewed_source, tmp_path, profile, client):
    result, box = run_isolated(reviewed_source, tmp_path, profile, client, explicit_copy=True)
    assert not result["timed_out"], json.dumps({
        "elapsed_seconds": result["elapsed_seconds"],
        "completed_copy_receipts": result["completed_copy_receipts"],
        "last_events": result["events"][-6:], "stderr": result["stderr"],
    }, indent=2)
    assert result["returncode"] == 1, result["stdout"] + result["stderr"]
    assert result["active"]["channel"] == "pin"
    assert result["active"]["commit"] == reviewed_source[2]
    assert result["desired"] is None
    assert result["observations"]["transactions"][-1]["state"] == "aborted"
    assert not result["network_attempts"]
    assert not [event for event in result["events"] if event["event"].startswith("refused-")]
    selected = ".claude" if client == "claude" else ".agents"
    unselected = ".agents" if client == "claude" else ".claude"
    copies = list(box.home.glob(selected + "/skills/*/SKILL.md"))
    assert copies, result["stdout"] + result["stderr"]
    assert not list(box.home.glob(unselected + "/skills/*/SKILL.md"))
    assert not (tmp_path / "unselected-target").exists()
    for skill in copies:
        assert skill.read_bytes() == (reviewed_source[0] / "skills" / skill.parent.name / "SKILL.md").read_bytes()
        provenance = json.loads((skill.parent / ".source.json").read_text())
        assert provenance["source_type"] == "public"
        assert provenance["source_repo"] == "github.com/synthesisengineering/synthesis-skills"
    engine_report = json.loads(result["stderr"])
    assert any(step.get("layer") == "session-context" and step.get("layer_state") == "missing"
               for step in engine_report["steps"]), engine_report


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_successful_native_command_without_verified_installation_fails_closed(monkeypatch, client):
    report = onboard.Report(as_json=True)
    monkeypatch.setattr(onboard, "plugin_record", lambda *_: (False, None))
    monkeypatch.setattr(onboard, "install_plugin", lambda *_: (True, "client returned success"))
    monkeypatch.setattr(onboard, "expected_policy_version", lambda *_: ("1.2.3", "fixture"))
    calls = []
    monkeypatch.setattr(onboard, "run", lambda command, **_: (calls.append(command) or (0, "", "")))
    onboard.phase_ecosystem(report, {client: client}, False, False,
                            {"channel": "stable", "version_pin": "1.2.3"})
    assert report.exit_code() == 1
    assert not calls, "A failed installation verification must not invoke a copy installer"
    assert "could not be verified" in report.steps[-1]["detail"]


def test_copy_dry_run_does_not_enter_any_installer(monkeypatch, tmp_path):
    report = onboard.Report(dry_run=True, as_json=True)
    monkeypatch.setattr(onboard, "HOME", tmp_path)
    monkeypatch.setattr(onboard, "plugin_record", lambda *_: (False, None))
    calls = []
    monkeypatch.setattr(onboard, "run", lambda command, **_: (calls.append(command) or (0, "", "")))
    onboard.phase_ecosystem(report, {"claude": "claude"}, True, True,
                            {"channel": "stable", "version_pin": "1.2.3"})
    assert report.exit_code() == 0
    assert not calls


def test_copy_refuses_ambiguous_target_without_running_shell(monkeypatch, tmp_path):
    report = onboard.Report(as_json=True)
    monkeypatch.setattr(onboard, "HOME", tmp_path / "home with spaces")
    calls = []
    monkeypatch.setattr(onboard, "run", lambda command, **_: (calls.append(command) or (0, "", "")))
    onboard.phase_explicit_skill_copies(report, ["claude"], False)
    assert report.exit_code() == 1
    assert not calls
    assert "whitespace" in report.steps[-1]["detail"]


@pytest.fixture
def copy_boundary(tmp_path, monkeypatch):
    source = tmp_path / "source"
    scripts = source / "skills/synthesis-onboarding/scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("direct_copy.sh"), scripts / "direct_copy.sh")
    discovery = source / "skills/synthesis-agent-conformance/scripts"
    discovery.mkdir(parents=True)
    shutil.copy2(Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts/client_binaries.py", discovery / "client_binaries.py")
    skill = source / "skills/synthesis-fixture"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Reviewed fixture\n")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "source_root", lambda: source)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("SYNTHESIS_CLAUDE_BIN", "")
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", "")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return source, home


@pytest.mark.parametrize("selected", ["claude", "codex"])
def test_copy_preserves_unselected_native_client_copies(copy_boundary, tmp_path, monkeypatch, selected):
    _, home = copy_boundary
    other = "codex" if selected == "claude" else "claude"
    other_root = ".agents" if other == "codex" else ".claude"
    retained = home / other_root / "skills/synthesis-fixture/SKILL.md"
    retained.parent.mkdir(parents=True)
    retained.write_text("Retained unselected work\n")
    binary = tmp_path / other
    binary.write_text("#!/bin/sh\nprintf '%s\\n' '{\"installed\":[{\"id\":\"synthesis-skills@test\",\"name\":\"synthesis-skills\",\"enabled\":true}]}'\n")
    binary.chmod(0o755)
    monkeypatch.setenv("SYNTHESIS_" + other.upper() + "_BIN", str(binary))
    report = onboard.Report(as_json=True)
    onboard.phase_explicit_skill_copies(report, [selected], False)
    assert report.exit_code() == 0, report.steps
    assert retained.is_file(), "Unselected native client retirement deleted retained work"
    assert retained.read_text() == "Retained unselected work\n"


@pytest.mark.parametrize("location", ["target", "target-parent", "source", "source-parent", "source-skill", "installed-skill"])
def test_copy_refuses_symlink_boundaries_before_invoking_script(copy_boundary, tmp_path, monkeypatch, location):
    source, home = copy_boundary
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "retained.txt"
    sentinel.write_text("Retained outside work\n")
    target = home / ".claude/skills"
    if location in {"target", "target-parent", "installed-skill"}:
        boundary = {"target": target, "target-parent": home / ".claude",
                    "installed-skill": target / "synthesis-fixture"}[location]
        boundary.parent.mkdir(parents=True, exist_ok=True)
        boundary.symlink_to(outside, target_is_directory=True)
    elif location in {"source", "source-parent"}:
        alias = tmp_path / "source-link"
        alias.symlink_to(source if location == "source" else source.parent, target_is_directory=True)
        monkeypatch.setattr(onboard, "source_root", lambda: alias if location == "source" else alias / source.name)
    else:
        (source / "skills/synthesis-linked").symlink_to(outside, target_is_directory=True)
    calls = []
    actual_run = onboard.run
    monkeypatch.setattr(onboard, "run", lambda *args, **kwargs: (calls.append(args[0]) or actual_run(*args, **kwargs)))
    report = onboard.Report(as_json=True)
    onboard.phase_explicit_skill_copies(report, ["claude"], False)
    assert report.exit_code() == 1, report.steps
    assert not calls, "Unsafe ancestry must be rejected before status or install"
    assert sentinel.read_text() == "Retained outside work\n"
    assert sorted(p.name for p in outside.iterdir()) == ["retained.txt"]


@pytest.mark.parametrize("character", ["*", "?", "[a]"])
def test_copy_refuses_shell_path_expansion(copy_boundary, tmp_path, monkeypatch, character):
    _, home = copy_boundary
    home = tmp_path / ("home" + character)
    home.mkdir()
    monkeypatch.setattr(onboard, "HOME", home)
    calls = []
    monkeypatch.setattr(onboard, "run", lambda command, **_: (calls.append(command) or (0, "", "")))
    report = onboard.Report(as_json=True)
    onboard.phase_explicit_skill_copies(report, ["claude"], False)
    assert report.exit_code() == 1
    assert not calls


def test_explicit_custom_destination_does_not_retire_default_client_roots(copy_boundary, tmp_path, monkeypatch):
    source, home = copy_boundary
    retained = []
    for client_root in (".claude", ".agents", ".codex"):
        path = home / client_root / "skills/synthesis-fixture/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("Retained " + client_root + "\n")
        retained.append((path, path.read_bytes()))
    client = tmp_path / "native-client"
    client.write_text("#!/bin/sh\nprintf '%s\\n' '{\"installed\":[{\"id\":\"synthesis-skills@test\",\"name\":\"synthesis-skills\",\"enabled\":true}]}'\n")
    client.chmod(0o755)
    target = tmp_path / "custom-root/skills"
    environment = {**os.environ, "SYNTHESIS_SKILLS_HOME": str(home),
                   "SYNTHESIS_SKILLS_SOURCE_DIR": str(source), "SYNTHESIS_SKILLS_TARGETS": str(target),
                   "SYNTHESIS_CLAUDE_BIN": str(client), "SYNTHESIS_CODEX_BIN": str(client)}
    script = Path(__file__).with_name("direct_copy.sh")
    for action in ("install", "status"):
        result = subprocess.run(["sh", str(script), action], env=environment,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        for path, content in retained:
            assert path.is_file(), "Custom destination retired an unselected default root"
            assert path.read_bytes() == content
    assert (target / "synthesis-fixture/SKILL.md").read_bytes() == (source / "skills/synthesis-fixture/SKILL.md").read_bytes()


@pytest.mark.parametrize("location", ["target", "target-parent", "source", "backup", "source-trailing", "target-trailing"])
@pytest.mark.parametrize("action", ["status", "install"])
def test_direct_copy_entrypoint_refuses_symlink_scope(copy_boundary, tmp_path, location, action):
    source, home = copy_boundary
    target = home / ".claude/skills"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "retained.txt").write_text("Retained outside work\n")
    if location.startswith("source"):
        alias = tmp_path / "source-link"
        alias.symlink_to(source, target_is_directory=True)
        source = alias
    else:
        boundary = {"target": target, "target-trailing": target, "target-parent": target.parent,
                    "backup": tmp_path / "cache/synthesis-skills-backups"}[location]
        boundary.parent.mkdir(parents=True, exist_ok=True)
        boundary.symlink_to(outside, target_is_directory=True)
    environment = {**os.environ, "SYNTHESIS_SKILLS_HOME": str(home),
                   "SYNTHESIS_SKILLS_SOURCE_DIR": str(source) + ("///" if location == "source-trailing" else ""),
                   "SYNTHESIS_SKILLS_TARGETS": str(target) + ("///" if location == "target-trailing" else "")}
    result = subprocess.run(["sh", str(Path(__file__).with_name("direct_copy.sh")), action],
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "symbolic-link" in result.stdout + result.stderr
    assert sorted(path.name for path in outside.iterdir()) == ["retained.txt"]


@pytest.mark.parametrize("entry", ["engine", "script"])
def test_copy_refuses_source_inside_prunable_backups(copy_boundary, tmp_path, monkeypatch, entry):
    source, home = copy_boundary
    backup = tmp_path / "cache/synthesis-skills-backups"
    backup.mkdir(parents=True)
    relocated = backup / "000-reviewed-source"
    shutil.move(str(source), relocated)
    for index in range(11):
        (backup / ("100-retained-%02d" % index)).mkdir()
    monkeypatch.setattr(onboard, "source_root", lambda: relocated)
    if entry == "engine":
        calls = []
        actual_run = onboard.run
        monkeypatch.setattr(onboard, "run", lambda *args, **kwargs: (calls.append(args[0]) or actual_run(*args, **kwargs)))
        report = onboard.Report(as_json=True)
        onboard.phase_explicit_skill_copies(report, ["claude"], False)
        result_code = report.exit_code()
        assert not calls, "Pruning overlap must be rejected before script execution"
    else:
        environment = {**os.environ, "SYNTHESIS_SKILLS_HOME": str(home),
                       "SYNTHESIS_SKILLS_SOURCE_DIR": str(relocated),
                       "SYNTHESIS_SKILLS_TARGETS": str(home / ".claude/skills")}
        result = subprocess.run(["sh", str(Path(__file__).with_name("direct_copy.sh")), "install"],
                                env=environment, capture_output=True, text=True, timeout=30)
        result_code = result.returncode
    assert result_code != 0
    assert (relocated / "skills/synthesis-fixture/SKILL.md").read_text() == "# Reviewed fixture\n"

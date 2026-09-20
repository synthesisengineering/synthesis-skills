"""One-command fleet join: derive everything, clone once, resume safely."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fleet_join as FJ


def git(*arguments, cwd):
    completed = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def seed_kb_worktree(path: Path, workspace: str = "demo") -> Path:
    subprocess.run(
        ["git", "init", "-b", "main", "--quiet", str(path)],
        check=True,
        capture_output=True,
    )
    git("config", "user.name", "Test", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    (path / "fleet").mkdir(parents=True)
    (path / "fleet" / f"repos.{workspace}.json").write_text(
        json.dumps({"schema_version": 1, "repos": []}), encoding="utf-8"
    )
    now = "2026-09-19T12:00:00+00:00"
    (path / "fleet" / "machines.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "machines": {
                    str(uuid.uuid4()): {
                        "label": "mac-a",
                        "enrolled_at": now,
                        "last_seen": now,
                        "role": "primary",
                        "environments": ["default"],
                        "retired_at": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    git("add", "fleet", cwd=path)
    git("commit", "--quiet", "-m", "seed kb", cwd=path)
    return path


def seed_kb_origin(path: Path, workspace: str = "demo") -> str:
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(path)],
        check=True,
        capture_output=True,
    )
    work = seed_kb_worktree(path.parent / f"seed-work-{path.stem}", workspace)
    git("remote", "add", "origin", str(path), cwd=work)
    git("push", "--quiet", "origin", "main", cwd=work)
    subprocess.run(
        ["git", "--git-dir", str(path), "symbolic-ref", "HEAD",
         "refs/heads/main"],
        check=True,
        capture_output=True,
    )
    return str(path)


def stub_engine(captured: dict, report: dict | None = None):
    def parse_repos_manifest(manifest, home):
        captured["manifest"] = str(manifest)
        return [{"remote": "r", "path": "p", "branch": ""}]

    def preflight(home, role, registry):
        captured["preflight"] = (str(home), role, str(registry))
        return []

    def bootstrap(**kwargs):
        captured["bootstrap"] = kwargs
        return report or {
            "machine_id": "machine-1",
            "steps": [
                {"step": "mint-identity", "status": "done",
                 "detail": "minted", "receipt": "/tmp/r.json"},
            ],
            "ok": True,
        }

    return SimpleNamespace(
        parse_repos_manifest=parse_repos_manifest,
        preflight=preflight,
        bootstrap=bootstrap,
        EXIT_INTERRUPTED=130,
    )


def join_args(kb=None, **overrides):
    values = {
        "kb": kb, "label": None, "role": None, "workspace": None,
        "json": False, "verbose": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_remote_detection_and_normalization(tmp_path):
    assert FJ.looks_like_remote("https://github.com/u/kb.git")
    assert FJ.looks_like_remote("git@github.com:u/kb.git")
    assert FJ.looks_like_remote("github.com:u/kb.git")
    assert FJ.looks_like_remote("kb.git")
    target = tmp_path / "plain"
    target.mkdir()
    assert not FJ.looks_like_remote(str(target))
    assert not FJ.looks_like_remote(str(tmp_path / "no-colon-here"))
    assert FJ.normalize_remote("https://h/u/kb.git/") == "https://h/u/kb"
    assert FJ.normalize_remote("https://h/u/kb") == "https://h/u/kb"


def test_workspace_derivation():
    assert FJ.workspace_from_remote(
        "https://github.com/u/ai-knowledge-acme.git") == "acme"
    assert FJ.workspace_from_remote("git@h:u/ai-knowledge-vik") == "vik"
    assert FJ.workspace_from_remote("https://h/u/other.git") is None
    assert FJ.workspace_from_kb_path(
        Path("/h/workspaces/demo/ai-knowledge-demo")) == "demo"
    assert FJ.workspace_from_kb_path(Path("/x/ai-knowledge-vik")) == "vik"
    assert FJ.workspace_from_kb_path(Path("/x/plain")) is None
    assert FJ.clone_target_for(
        Path("/h"), "demo", "https://h/u/ai-knowledge-demo.git"
    ) == Path("/h/workspaces/demo/ai-knowledge-demo")


def test_discover_manifest(tmp_path):
    kb = seed_kb_worktree(tmp_path / "kb", "demo")
    manifest, workspace = FJ.discover_manifest(kb, None)
    assert manifest == kb / "fleet" / "repos.demo.json"
    assert workspace == "demo"
    manifest, _ = FJ.discover_manifest(kb, "demo")
    assert manifest.name == "repos.demo.json"
    with pytest.raises(FJ.FleetJoinError, match="available"):
        FJ.discover_manifest(kb, "missing")
    (kb / "fleet" / "repos.other.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FJ.FleetJoinError, match="--workspace"):
        FJ.discover_manifest(kb, None)
    empty = tmp_path / "empty"
    (empty / "fleet").mkdir(parents=True)
    with pytest.raises(FJ.FleetJoinError, match="no repos manifest"):
        FJ.discover_manifest(empty, None)


def test_ensure_existing_checkout_verifies_origin(tmp_path):
    origin = seed_kb_origin(tmp_path / "kb.git")
    kb = tmp_path / "kb"
    subprocess.run(
        ["git", "clone", "--quiet", origin, str(kb)],
        check=True, capture_output=True,
    )
    lines: list[str] = []
    target, workspace = FJ.ensure_kb_checkout(
        origin, tmp_path / "home", "demo", progress=lines.append
    )
    assert target == tmp_path / "home" / "workspaces" / "demo" / "kb"
    assert workspace == "demo"
    assert lines[0].startswith("cloning ")
    assert lines[-1] == f"cloned {target}"

    rerun: list[str] = []
    target2, _ = FJ.ensure_kb_checkout(
        origin, tmp_path / "home", "demo", progress=rerun.append
    )
    assert target2 == target
    assert rerun == [f"verified {target} (already cloned)"]

    with pytest.raises(FJ.FleetJoinError, match="does not match"):
        FJ.ensure_kb_checkout(f"file://{origin}", tmp_path / "home", "demo")


def test_ensure_local_path_must_be_a_checkout(tmp_path):
    kb = seed_kb_worktree(tmp_path / "kb")
    target, _ = FJ.ensure_kb_checkout(str(kb), tmp_path, None)
    assert target == kb
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(FJ.FleetJoinError, match="not a git checkout"):
        FJ.ensure_kb_checkout(str(plain), tmp_path, None)
    with pytest.raises(FJ.FleetJoinError, match="--workspace"):
        FJ.ensure_kb_checkout("https://h/u/custom-name.git", tmp_path, None)


def test_join_derives_everything_from_a_path(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    kb = seed_kb_worktree(tmp_path / "kb")
    captured: dict = {}
    monkeypatch.setattr(FJ, "default_label", lambda: "test-mac")
    code = FJ.join(
        join_args(str(kb)), release_root=tmp_path / "release",
        home=home, bootstrap=stub_engine(captured),
    )
    assert code == 0
    assert captured["manifest"] == str(kb / "fleet" / "repos.demo.json")
    call = captured["bootstrap"]
    assert call["home"] == home
    assert call["source_root"] == tmp_path / "release"
    assert call["label"] == "test-mac"
    assert call["role"] == "secondary"
    assert call["fleet_registry"] == kb / "fleet" / "machines.json"
    assert call["kb_repo"] == kb
    out = capsys.readouterr().out
    assert "DONE bootstrap-mint-identity: minted" in out


def test_join_clones_a_remote_and_derives_the_workspace(tmp_path, capsys):
    home = tmp_path / "home"
    origin = seed_kb_origin(tmp_path / "ai-knowledge-demo.git", "demo")
    captured: dict = {}
    code = FJ.join(
        join_args(f"file://{origin}"), release_root=tmp_path / "release",
        home=home, bootstrap=stub_engine(captured),
    )
    assert code == 0
    expected = home / "workspaces" / "demo" / "ai-knowledge-demo"
    assert captured["bootstrap"]["kb_repo"] == expected
    assert captured["manifest"] == str(
        expected / "fleet" / "repos.demo.json"
    )
    out = capsys.readouterr().out
    assert "cloning file://" in out


def test_join_json_mode_and_failures(tmp_path, capsys, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    kb = seed_kb_worktree(tmp_path / "kb")
    monkeypatch.setattr(FJ, "default_label", lambda: "test-mac")

    captured: dict = {}
    code = FJ.join(
        join_args(str(kb), json=True), release_root=tmp_path / "release",
        home=home, bootstrap=stub_engine(captured),
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["machine_id"] == "machine-1"

    def failing_preflight(home_dir, role, registry):
        return ["git is not on PATH"]

    engine = stub_engine({})
    engine.preflight = failing_preflight
    with pytest.raises(FJ.FleetJoinError, match="not on PATH"):
        FJ.join(
            join_args(str(kb)), release_root=tmp_path / "release",
            home=home, bootstrap=engine,
        )

    def raising_bootstrap(**kwargs):
        raise KeyboardInterrupt

    engine = stub_engine({})
    engine.bootstrap = raising_bootstrap
    code = FJ.join(
        join_args(str(kb)), release_root=tmp_path / "release",
        home=home, bootstrap=engine,
    )
    assert code == 130
    assert "INTERRUPTED fleet join" in capsys.readouterr().err


def test_load_bootstrap_refuses_a_release_without_the_engine(tmp_path):
    with pytest.raises(FJ.FleetJoinError, match="synthesis update"):
        FJ.load_bootstrap(tmp_path / "empty-release")


def test_cli_registers_fleet_join():
    import synthesis_cli

    assert "fleet join" in synthesis_cli.CLI_COMMANDS
    parser = synthesis_cli.build_parser()
    args = parser.parse_args(["fleet", "join", "--kb", "kb"])
    assert args.command == "fleet"
    assert args.fleet_command == "join"
    assert args.role is None
    bare = parser.parse_args(["fleet", "join"])
    assert bare.kb is None and bare.role is None
    assert "fleet" in parser.format_help()


def gh_stub(*, urls=None, returncode=0, stdout=None, error=None):
    def run(argv):
        assert argv[:2] == ["repo", "list"]
        if error is not None:
            raise error
        if stdout is not None:
            out = stdout
        else:
            out = json.dumps([{"url": url} for url in (urls or [])])
        return SimpleNamespace(returncode=returncode, stdout=out, stderr="")

    return run


def test_github_discovery_statuses():
    status, remotes = FJ.gh_kb_remotes(
        gh_runner=gh_stub(urls=[
            "https://h/u/ai-knowledge-demo.git",
            "https://h/u/other.git",
        ])
    )
    assert (status, remotes) == (
        "ok", ["https://h/u/ai-knowledge-demo.git"]
    )
    assert FJ.gh_kb_remotes(
        gh_runner=gh_stub(returncode=1)
    ) == ("auth-needed", [])
    assert FJ.gh_kb_remotes(
        gh_runner=gh_stub(error=FileNotFoundError())
    ) == ("no-gh", [])
    assert FJ.gh_kb_remotes(
        gh_runner=gh_stub(stdout="not json")
    ) == ("ok", [])
    assert FJ.gh_auth_login(
        auth_runner=lambda: SimpleNamespace(returncode=0)
    ) is True
    assert FJ.gh_auth_login(
        auth_runner=lambda: SimpleNamespace(returncode=1)
    ) is False
    assert FJ.gh_auth_login(
        auth_runner=lambda: (_ for _ in ()).throw(FileNotFoundError())
    ) is False


def test_resolve_role_follows_shared_state(tmp_path, capsys):
    assert FJ.resolve_role("primary", tmp_path / "absent.json") == "primary"
    kb = seed_kb_worktree(tmp_path / "kb")
    announced: list[str] = []
    assert FJ.resolve_role(
        None, kb / "fleet" / "machines.json", announce=announced.append
    ) == "secondary"
    assert announced == ["found a fleet of 1 machine(s); joining as secondary"]
    announced.clear()
    assert FJ.resolve_role(
        None, tmp_path / "empty" / "machines.json",
        announce=announced.append,
    ) == "primary"
    assert announced == [
        "no fleet found in this knowledge repo; founding one as primary"
    ]
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not json", encoding="utf-8")
    assert FJ.resolve_role(None, corrupt) == "secondary"


def test_prompts_validate_and_name_the_flag(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "  answer  ")
    assert FJ.prompt_text("Q", "--kb <u>", can_prompt=True) == "answer"
    monkeypatch.setattr("builtins.input", lambda *a: "2")
    assert FJ.prompt_choice("Q", ["a", "b"], "--w <n>", can_prompt=True) == "b"
    monkeypatch.setattr("builtins.input", lambda *a: "9")
    with pytest.raises(FJ.FleetJoinError, match="choice must be"):
        FJ.prompt_choice("Q", ["a", "b"], "--w <n>", can_prompt=True)
    monkeypatch.setattr("builtins.input", lambda *a: "   ")
    with pytest.raises(FJ.FleetJoinError, match="required"):
        FJ.prompt_text("Q", "--kb <u>", can_prompt=True)

    def eof(*args):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    with pytest.raises(FJ.FleetJoinError, match="no answer"):
        FJ.prompt_text("Q", "--kb <u>", can_prompt=True)
    with pytest.raises(FJ.FleetJoinError, match="not interactive"):
        FJ.prompt_text("Q", "--kb <u>", can_prompt=False)


def test_resolve_kb_prefers_discovery_then_asks(tmp_path, monkeypatch):
    announced: list[str] = []
    remote, workspace = FJ.resolve_kb_interactive(
        None,
        gh_runner=gh_stub(
            urls=["https://h/u/ai-knowledge-demo.git"]
        ),
        announce=announced.append,
    )
    assert remote == "https://h/u/ai-knowledge-demo.git"
    assert workspace == "demo"
    assert announced == [f"found knowledge repo {remote}"]

    monkeypatch.setattr("builtins.input", lambda *a: "2")
    remote, _ = FJ.resolve_kb_interactive(
        None,
        gh_runner=gh_stub(urls=["https://h/u/ai-knowledge-a.git",
                                "https://h/u/ai-knowledge-b.git"]),
        announce=announced.append,
    )
    assert remote == "https://h/u/ai-knowledge-b.git"

    calls: list[str] = []

    def login():
        calls.append("login")
        return SimpleNamespace(returncode=0)

    attempts = iter([
        SimpleNamespace(returncode=1, stdout="", stderr="auth"),
        SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [{"url": "https://h/u/ai-knowledge-demo.git"}]
            ),
            stderr="",
        ),
    ])
    remote, _ = FJ.resolve_kb_interactive(
        None, gh_runner=lambda argv: next(attempts), auth_runner=login,
        announce=announced.append,
    )
    assert calls == ["login"]
    assert remote == "https://h/u/ai-knowledge-demo.git"

    monkeypatch.setattr(
        "builtins.input", lambda *a: "https://h/u/ai-knowledge-x.git"
    )
    remote, workspace = FJ.resolve_kb_interactive(
        None, gh_runner=gh_stub(error=FileNotFoundError()),
        announce=announced.append,
    )
    assert (remote, workspace) == ("https://h/u/ai-knowledge-x.git", "x")

    with pytest.raises(FJ.FleetJoinError, match="--kb"):
        FJ.resolve_kb_interactive(
            None, gh_runner=gh_stub(error=FileNotFoundError()),
            can_prompt=False,
        )


def test_discover_manifest_empty_and_choice(tmp_path):
    kb = tmp_path / "kb"
    (kb / "fleet").mkdir(parents=True)
    assert FJ.discover_manifest(kb, "demo", allow_empty=True) == (None, "demo")
    assert FJ.discover_manifest(kb, None, allow_empty=True) == (None, None)
    with pytest.raises(FJ.FleetJoinError, match="no repos manifest"):
        FJ.discover_manifest(kb, None)

    kb = seed_kb_worktree(tmp_path / "kb2", "demo")
    (kb / "fleet" / "repos.other.json").write_text("{}", encoding="utf-8")
    manifest, workspace = FJ.discover_manifest(
        kb, None, choose=lambda names: "repos.other.json"
    )
    assert (manifest.name, workspace) == ("repos.other.json", "other")


def test_join_without_kb_discovers_and_runs(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    origin = seed_kb_origin(tmp_path / "ai-knowledge-demo.git", "demo")
    captured: dict = {}
    monkeypatch.setattr(FJ, "default_label", lambda: "test-mac")
    code = FJ.join(
        join_args(), release_root=tmp_path / "release", home=home,
        bootstrap=stub_engine(captured),
        gh_runner=gh_stub(urls=[f"file://{origin}"]),
    )
    assert code == 0
    expected = home / "workspaces" / "demo" / "ai-knowledge-demo"
    call = captured["bootstrap"]
    assert call["kb_repo"] == expected
    assert call["role"] == "secondary"
    assert call["label"] == "test-mac"
    out = capsys.readouterr().out
    assert "joining as test-mac (secondary)" in out


def test_join_founding_skips_clones(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    kb = tmp_path / "kb"
    subprocess.run(
        ["git", "init", "-b", "main", "--quiet", str(kb)],
        check=True, capture_output=True,
    )
    git("config", "user.name", "Test", cwd=kb)
    git("config", "user.email", "test@example.com", cwd=kb)
    (kb / "README.md").write_text("fresh\n", encoding="utf-8")
    git("add", "README.md", cwd=kb)
    git("commit", "--quiet", "-m", "seed", cwd=kb)
    captured: dict = {}
    parsed: dict = {}

    def parse_repos_manifest(manifest, home_dir):
        parsed["called"] = True
        raise AssertionError("founding must not parse a manifest")

    engine = stub_engine(captured)
    engine.parse_repos_manifest = parse_repos_manifest
    monkeypatch.setattr(FJ, "default_label", lambda: "test-mac")
    code = FJ.join(
        join_args(str(kb)), release_root=tmp_path / "release", home=home,
        bootstrap=engine,
    )
    assert code == 0
    assert parsed == {}
    assert captured["bootstrap"]["role"] == "primary"
    assert captured["bootstrap"]["repos"] == []
    out = capsys.readouterr().out
    assert "founding one as primary" in out
    assert "skipping clones" in out

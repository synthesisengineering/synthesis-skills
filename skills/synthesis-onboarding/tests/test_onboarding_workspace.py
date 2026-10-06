"""workspace.py: a new Mac's workspace from repos.yaml, and an organization's data-only configuration."""

import json
import os
import subprocess
from pathlib import Path

import pytest

import setup
import workspace


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def remote(tmp_path, name, files=None):
    """A bare repository with one commit, standing in for a hosted remote."""
    work = tmp_path / "src" / name
    work.mkdir(parents=True)
    for rel, text in (files or {"README.md": name}).items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text)
    git("init", "-q", str(work))
    git("-C", str(work), "add", ".")
    git("-C", str(work), "commit", "-qm", "init")
    bare = tmp_path / "remotes" / f"{name}.git"
    git("clone", "-q", "--bare", str(work), str(bare))
    return str(bare), work


def push_change(work, bare, text="more"):
    (work / "CHANGE.md").write_text(text)
    git("-C", str(work), "add", ".")
    git("-C", str(work), "commit", "-qm", "change")
    git("-C", str(work), "push", "-q", bare, "HEAD:main")


def knowledge_repo(tmp_path, repos_yaml):
    return remote(tmp_path, "ai-knowledge-demo", {".agents/repos.yaml": repos_yaml,
                                                  ".agents/workspace-AGENTS.md": "# Demo workspace\n"})


# ---- one repository -----------------------------------------------------------

def test_clone_then_fast_forward_then_skip_by_name(tmp_path):
    bare, work = remote(tmp_path, "tool")
    target = tmp_path / "ws" / "tool"
    assert workspace.clone_or_update(bare, target) == "cloned"
    assert workspace.clone_or_update(bare, target) == "current"
    push_change(work, bare)
    assert workspace.clone_or_update(bare, target) == "updated" and (target / "CHANGE.md").is_file()
    (target / "README.md").write_text("local edit")
    assert workspace.clone_or_update(bare, target) == "skipped: uncommitted changes"
    git("-C", str(target), "commit", "-qam", "local")
    push_change(work, bare, "upstream")
    assert workspace.clone_or_update(bare, target) == "skipped: diverged from its upstream"


def test_a_checkout_with_another_origin_is_refused_and_not_repointed(tmp_path):
    bare, _ = remote(tmp_path, "tool")
    other, _ = remote(tmp_path, "other")
    target = tmp_path / "ws" / "tool"
    workspace.clone_or_update(other, target)
    with pytest.raises(setup.SetupError, match="refusing to repoint"):
        workspace.clone_or_update(bare, target)
    assert git("-C", str(target), "remote", "get-url", "origin") == other


def test_an_interrupted_clone_leaves_nothing_at_the_target_and_a_rerun_finishes(tmp_path):
    bare, _ = remote(tmp_path, "tool")
    target = tmp_path / "ws" / "tool"
    leftover = target.with_name("tool.partial-99999")
    leftover.mkdir(parents=True)
    (leftover / "half").write_text("x")
    assert workspace.clone_or_update(bare, target) == "cloned"
    assert not leftover.exists() and (target / "README.md").is_file()


def test_a_plain_folder_in_the_way_is_never_overwritten(tmp_path):
    bare, _ = remote(tmp_path, "tool")
    target = tmp_path / "ws" / "tool"
    target.mkdir(parents=True)
    with pytest.raises(setup.SetupError, match="not a git checkout"):
        workspace.clone_or_update(bare, target)


# ---- a workspace from repos.yaml -------------------------------------------------

def test_new_mac_clones_every_listed_repository_with_progress(tmp_path):
    tool, _ = remote(tmp_path, "tool")
    up, _ = remote(tmp_path, "upstream-tool")
    kb, _ = knowledge_repo(tmp_path, f"""workspace: demo
repos:
  - name: ai-knowledge-demo
    path: ai-knowledge-demo/
    remotes:
      origin: {tmp_path}/remotes/ai-knowledge-demo.git
  - name: tool
    path: tool/
    remotes:
      origin: {tool}
      upstream: {up}
    default_branches: [main]
  - name: old
    path: old/
    status: dormant
    remotes:
      origin: {tool}
""")
    seen = []
    lines = workspace.bring_workspace(kb, "demo", seen.append)
    ws = Path.home() / "workspaces" / "demo"
    assert (ws / "tool" / "README.md").is_file() and not (ws / "old").exists()
    assert git("-C", str(ws / "tool"), "remote", "get-url", "upstream") == up
    assert "[1/1] tool: cloned" in seen and "old: dormant; not cloned" in lines
    assert os.readlink(ws / "AGENTS.md") == "ai-knowledge-demo/.agents/workspace-AGENTS.md"
    assert (ws / "CLAUDE.md").read_text() == "@AGENTS.md\n" and (ws / ".agents" / "repos.yaml").is_file()
    again = workspace.bring_workspace(kb, "demo", seen.append)
    assert "tool: current" in again and any("already links" in line for line in again)


def test_existing_workspace_instructions_are_kept_unless_adopted_and_then_archived(tmp_path):
    kb, _ = knowledge_repo(tmp_path, "repos: []\n")
    ws = Path.home() / "workspaces" / "demo"
    ws.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("my own rules\n")
    lines = workspace.bring_workspace(kb, "demo", lambda line: None)
    assert (ws / "AGENTS.md").read_text() == "my own rules\n" and any("kept as it is" in line for line in lines)
    lines = workspace.bring_workspace(kb, "demo", lambda line: None, adopt=True)
    archived = list((setup.install._home() / "archive").glob("*/AGENTS.md"))
    assert archived and archived[0].read_text() == "my own rules\n"
    assert (ws / "AGENTS.md").is_symlink()


def test_the_knowledge_repository_with_a_wrong_origin_stops_everything(tmp_path):
    kb, _ = knowledge_repo(tmp_path, "repos: []\n")
    other, _ = remote(tmp_path, "other")
    workspace.clone_or_update(other, Path.home() / "workspaces" / "demo" / "ai-knowledge-demo")
    with pytest.raises(setup.SetupError, match="refusing to repoint"):
        workspace.bring_workspace(kb, "demo", lambda line: None)


def test_discovery_uses_the_one_knowledge_repo_gh_lists(monkeypatch):
    listing = json.dumps([{"url": "https://example.test/me/site"}, {"url": "https://example.test/me/ai-knowledge-me"}])
    monkeypatch.setattr(setup, "run", lambda argv, *a, **k: subprocess.CompletedProcess(argv, 0, listing, ""))
    assert workspace.discover_kb(interactive=False) == "https://example.test/me/ai-knowledge-me"
    assert workspace.workspace_from("https://example.test/me/ai-knowledge-me.git") == "me"


def test_discovery_without_a_terminal_names_the_flag(monkeypatch):
    two = json.dumps([{"url": "https://e.test/a/ai-knowledge-a"}, {"url": "https://e.test/b/ai-knowledge-b"}])
    monkeypatch.setattr(setup, "run", lambda argv, *a, **k: subprocess.CompletedProcess(argv, 0, two, ""))
    with pytest.raises(setup.SetupError, match="pass --kb URL"):
        workspace.discover_kb(interactive=False)


# ---- an organization ----------------------------------------------------------

MANIFEST = """version: 2
org:
  id: example-team
  name: Example Team
  workspace: example-team
ecosystem:
  clients: [claude, codex]
  channel: stable
skills_repos:
  - name: team-skills
    repository: {skills}
    capability: skills-install
knowledge_bases:
  - name: ai-knowledge-example-team
    repository: {kb}
    default_branch: main
    local_hooks: true
instruction_sources:
  - path: .agents/workspace-instructions.md
    required: true
auth_help: |
  Ask the team for read access, then rerun.
welcome:
  title: Your workspace is ready
  try_asking:
    - "What projects are active?"
"""


@pytest.fixture
def local_git(monkeypatch):
    """Organization git normally allows only https and ssh; these tests use local bare repositories."""
    monkeypatch.setattr(workspace, "ORG_GIT", [])
    monkeypatch.setattr(workspace, "validate_repository_url", lambda url: url)
    monkeypatch.setattr(workspace, "org_git_env", lambda: dict(os.environ))


def org_repo(tmp_path, manifest=None):
    skills, _ = remote(tmp_path, "team-skills", {"skills/team-review/SKILL.md": "---\nname: team-review\n---\n"})
    kb, _ = remote(tmp_path, "ai-knowledge-example-team")
    text = manifest or MANIFEST.format(skills=skills, kb=kb)
    org, _ = remote(tmp_path, "team-config", {".agents/onboarding.yaml": text,
                                              ".agents/workspace-instructions.md": "Team rules.\n"})
    return org


def test_enrollment_clones_installs_skills_and_writes_the_instruction_pair(tmp_path, local_git):
    lines = workspace.enroll(org_repo(tmp_path), lambda line: None, adopt=False)
    ws = Path.home() / "workspaces" / "example-team"
    assert (ws / "ai-knowledge-example-team" / "README.md").is_file()
    for root in (".claude/skills", ".agents/skills"):
        assert (Path.home() / root / "team-review" / "SKILL.md").is_file()
    assert not (Path.home() / ".codex" / "skills").exists()
    agents = (ws / "AGENTS.md").read_text()
    assert agents.startswith(workspace.ARCHIVE_NOTE) and "## Organization\n\nTeam rules." in agents
    assert (ws / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert "Your workspace is ready" in lines and "  try: What projects are active?" in lines


def test_reenrollment_keeps_an_edited_skill_copy_and_regenerates_its_own_file(tmp_path, local_git):
    org = org_repo(tmp_path)
    workspace.enroll(org, lambda line: None)
    edited = Path.home() / ".claude" / "skills" / "team-review" / "SKILL.md"
    edited.write_text("my edit\n")
    personal = tmp_path / "mine.md"
    personal.write_text("My own rules.\n")
    lines = workspace.enroll(org, lambda line: None, personal_source=str(personal))
    assert edited.read_text() == "my edit\n" and any("kept (changed since setup" in line for line in lines)
    assert "## Personal\n\nMy own rules." in (Path.home() / "workspaces" / "example-team" / "AGENTS.md").read_text()


def test_a_clone_failure_shows_the_organizations_auth_help(tmp_path, local_git):
    manifest = MANIFEST.format(skills=str(tmp_path / "missing-skills.git"), kb=str(tmp_path / "missing-kb.git"))
    lines = workspace.enroll(org_repo(tmp_path, manifest), lambda line: None)
    failed = [line for line in lines if "needs action" in line]
    assert len(failed) == 2 and all("Ask the team for read access" in line for line in failed)


def test_a_dirty_organization_clone_is_refused(tmp_path, local_git):
    org = org_repo(tmp_path)
    root, _ = workspace.acquire_org(org)
    (root / ".agents" / "onboarding.yaml").write_text("tampered\n")
    with pytest.raises(setup.SetupError, match="local changes"):
        workspace.acquire_org(org)


def test_same_repository_name_in_two_organizations_gets_two_folders():
    a = workspace.org_root("https://example.test/one/config.git")
    b = workspace.org_root("https://example.test/two/config.git")
    assert a != b and a.parent == b.parent and a.name.startswith("config-")


@pytest.mark.parametrize("url", ["file:///tmp/x", "git://example.test/x", "https://user:pw@example.test/x",
                                 "https://token@example.test/x", "/local/path", "https://example.test/x?y=1"])
def test_only_authenticated_https_and_ssh_urls_are_accepted(url):
    with pytest.raises(setup.SetupError):
        workspace.validate_repository_url(url)


def test_good_urls_pass():
    for url in ("https://example.test/org/repo.git", "ssh://git@example.test/org/repo.git", "git@example.test:org/repo.git"):
        assert workspace.validate_repository_url(url) == url


def test_organization_git_runs_with_only_https_and_ssh_and_no_injected_config(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.file:///.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'core.sshCommand'='evil'")
    env = workspace.org_git_env()
    assert env["GIT_ALLOW_PROTOCOL"] == "https:ssh" and env["GIT_PROTOCOL_FROM_USER"] == "0"
    assert not {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_PARAMETERS"} & set(env)
    assert "protocol.file.allow=never" in workspace.ORG_GIT


def _manifest(**changes):
    from yaml_subset import load
    data = load(MANIFEST.format(skills="https://example.test/s.git", kb="https://example.test/k.git"))
    data.update(changes)
    return data


def test_manifest_validation_accepts_schema_2_and_refuses_unknown_keys():
    assert workspace.validate_org_manifest(_manifest())["org"]["id"] == "example-team"
    with pytest.raises(setup.SetupError, match="unknown keys: installer_hook"):
        workspace.validate_org_manifest(_manifest(installer_hook="sh evil.sh"))


def test_schema_1_manifests_are_refused_naming_the_migration():
    for legacy in ({"version": 1}, {"skills_repos": [{"name": "x", "primary": "https://e.test/x.git"}]}):
        with pytest.raises(setup.SetupError, match="migrating-from-schema-1"):
            workspace.validate_org_manifest(_manifest(**legacy))


@pytest.mark.parametrize("change, message", [
    ({"instruction_sources": []}, "exactly one"),
    ({"instruction_sources": [{"path": "../outside.md"}]}, "relative path inside"),
    ({"org": {"id": "../x", "workspace": "w"}}, "org.id"),
    ({"ecosystem": {"clients": ["claude", "cursor"]}}, "may name only"),
    ({"skills_repos": [{"name": "s", "repository": "https://e.test/s.git", "capability": "run-script"}]},
     "skills-install"),
])
def test_manifest_validation_failures(change, message):
    with pytest.raises(setup.SetupError, match=message):
        workspace.validate_org_manifest(_manifest(**change))


def test_org_preferences_turn_the_release_policy_into_a_marketplace_ref(tmp_path, local_git):
    assert workspace.org_preferences(org_repo(tmp_path)) == (["claude", "codex"], "stable")


def test_a_rerun_keeps_the_personal_layer_until_cleared(tmp_path, local_git):
    org = org_repo(tmp_path)
    personal = tmp_path / "mine.md"
    personal.write_text("My own rules.\n")
    agents = Path.home() / "workspaces" / "example-team" / "AGENTS.md"
    workspace.enroll(org, lambda line: None, personal_source=str(personal))
    workspace.enroll(org, lambda line: None)
    assert "My own rules." in agents.read_text()
    workspace.enroll(org, lambda line: None, personal_source="none")
    assert "## Personal" not in agents.read_text()


def test_manifest_check_command_exits_2_on_unknown_keys(tmp_path):
    import sys
    script = Path(workspace.__file__)
    good = tmp_path / "good.yaml"
    good.write_text(MANIFEST.format(skills="https://example.test/s.git", kb="https://example.test/k.git"))
    bad = tmp_path / "bad.yaml"
    bad.write_text(good.read_text() + "installer: ./setup.sh\n")
    run = lambda path: subprocess.run([sys.executable, str(script), "check", str(path)], capture_output=True, text=True)
    assert run(good).returncode == 0 and "valid schema-2 manifest for example-team" in run(good).stdout
    out = run(bad)
    assert out.returncode == 2 and "migrating-from-schema-1" in out.stdout


# ---- a brand-new knowledge repository ----------------------------------------

def test_a_new_workspace_gets_a_committed_knowledge_repository_and_links(tmp_path):
    lines = workspace.new_workspace("demo", "https://example.test/me/ai-knowledge-demo.git")
    repo = Path.home() / "workspaces" / "demo" / "ai-knowledge-demo"
    assert (repo / ".agents" / "knowledge-base.yaml").is_file() and (repo / "projects" / "index.yaml").is_file()
    assert "{workspace}" not in (repo / "AGENTS.md").read_text() and (repo / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert git("-C", str(repo), "status", "--porcelain") == "" and git("-C", str(repo), "log", "--oneline")
    from yaml_subset import load
    manifest = load((repo / ".agents" / "repos.yaml").read_text())
    assert manifest["repos"][0]["remotes"]["origin"] == "https://example.test/me/ai-knowledge-demo.git"
    assert os.readlink(repo.parent / "AGENTS.md") == "ai-knowledge-demo/.agents/workspace-AGENTS.md"
    (repo / "projects" / "index.yaml").write_text("projects: [mine]\n")
    git("-C", str(repo), "commit", "-qam", "mine")
    assert workspace.new_workspace("demo") [0] == "ai-knowledge-demo: already set up"
    assert (repo / "projects" / "index.yaml").read_text() == "projects: [mine]\n"


def test_a_new_workspace_without_a_git_identity_changes_nothing(tmp_path, monkeypatch):
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("HOME", str(tmp_path / "bare-home"))
    with pytest.raises(setup.SetupError, match="no identity"):
        workspace.new_workspace("demo")
    assert not (tmp_path / "bare-home" / "workspaces").exists()


def test_a_malformed_repos_manifest_stops_with_its_line_not_a_traceback(tmp_path, capsys):
    kb, _ = knowledge_repo(tmp_path, "repos:\n  - name: x\n    path: y\nnot a key\n")
    assert setup.main(["workspace", "--kb", kb, "--workspace", "demo", "--no-input"]) == 1
    out = capsys.readouterr().out
    assert "stopped: " in out and ".agents/repos.yaml:" in out

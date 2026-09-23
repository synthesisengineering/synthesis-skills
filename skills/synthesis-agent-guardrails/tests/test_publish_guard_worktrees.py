#!/usr/bin/env python3
"""Real-Git counterexamples for the deployment approval boundary.

All Git repositories, guard configuration, approvals, and execution sentinels
are test-owned. Git plumbing creates synthetic fixture history; no production
repository hook is disabled and no actual push/deploy is executed. A push
double is used only by the unsafe-shell-continuation regression.
"""
from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest


SCRIPT = Path(__file__).resolve().parent.parent / "guards" / "publish_guard.py"
SPEC = importlib.util.spec_from_file_location("publish_guard_worktrees_subject", SCRIPT)
pg = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pg)
PUSH = "p" + "ush"


@pytest.fixture(scope="module", autouse=True)
def _parser_runtime():
    """Bind the same-repo shell parser eagerly (fails fast on layout drift)."""
    pg._ensure_shell_parser()
    assert pg.inspect_command is not None
    yield


@pytest.fixture
def real_repos(tmp_path, monkeypatch):
    """Construct actual .git/common-dir identity, not pretend .git files."""
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(isolated_home / "config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(isolated_home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                 "PUBLISH_GUARD_ALLOW_FUTURE_DATES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Fixture Author")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "fixture@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Fixture Author")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "fixture@example.com")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-01-01T12:00:00+00:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-01-01T12:00:00+00:00")

    def git(repo, *args, input=None):
        result = subprocess.run(
            ["git", *args], cwd=repo, input=input, text=True,
            capture_output=True, check=True, env=os.environ.copy(), timeout=20,
        )
        return result.stdout.strip()

    def init(repo):
        repo.mkdir(parents=True)
        git(repo, "init", "--initial-branch=main", "--quiet")
        tree = git(repo, "mktree", input="")
        first = git(repo, "commit-tree", tree, input="Synthetic baseline\n")
        git(repo, "update-ref", "refs/heads/main", first)
        git(repo, "update-ref", "refs/remotes/origin/main", first)
        git(repo, "remote", "add", "origin", "https://example.com/ordinary/repo.git")
        return first

    canonical = tmp_path / "repositories" / "public-site"
    first = init(canonical)
    site_url = "https://example.com/sites/public-site.git"
    git(canonical, "remote", "set-url", "origin", site_url)
    linked = tmp_path / "worktrees" / "release-candidate"
    linked.parent.mkdir()
    git(canonical, "worktree", "add", "--quiet", "-b", "candidate", str(linked), first)
    spaced = tmp_path / "worktrees" / "release candidate with spaces"
    git(canonical, "worktree", "add", "--quiet", "-b", "quoted-candidate", str(spaced), first)
    unrelated = tmp_path / "different-owner" / "public-site"
    init(unrelated)
    tree = git(linked, "rev-parse", "HEAD^{tree}")
    second = git(linked, "commit-tree", tree, "-p", first, input="Synthetic candidate\n")
    git(linked, "update-ref", "refs/heads/candidate", second, first)
    git(spaced, "update-ref", "refs/heads/quoted-candidate", second, first)
    assert (canonical / ".git").is_dir()
    assert (linked / ".git").is_file()
    assert first != second
    assert git(linked, "rev-parse", "--path-format=absolute", "--git-common-dir") == str(canonical / ".git")
    assert git(unrelated, "rev-parse", "--path-format=absolute", "--git-common-dir") != str(canonical / ".git")
    state = tmp_path / "guard-state"
    config = tmp_path / "guard-config.json"
    config.write_text(json.dumps({"auto_deploy_repos": [str(canonical)]}))
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(config))
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(state))
    return {
        "root": tmp_path, "canonical": canonical, "linked": linked,
        "spaced": spaced, "unrelated": unrelated, "first": first,
        "second": second, "git": git, "state": state, "site_url": site_url,
    }


def gated(monkeypatch, command, cwd, *, tool="Bash", field="command"):
    payload = {"tool_name": tool, "cwd": str(cwd), "tool_input": {field: command}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return pg.gate()


def command_for(repo):
    return f"cd {shlex.quote(str(repo))} && git {PUSH} origin HEAD:main"


def test_canonical_no_approval_blocks_positive_control(real_repos, monkeypatch):
    assert gated(monkeypatch, command_for(real_repos["canonical"]), real_repos["root"]) == 2


def test_canonical_approval_authorizes_matching_candidate_positive_control(real_repos, monkeypatch):
    canonical = real_repos["canonical"]
    assert pg.approve(str(canonical), "Synthetic matching approval") == 0
    assert gated(monkeypatch, command_for(canonical), real_repos["root"]) == 0
    assert not Path(pg.ledger_path()).exists()


def test_unrelated_same_basename_passes_negative_control(real_repos, monkeypatch):
    assert gated(monkeypatch, command_for(real_repos["unrelated"]), real_repos["canonical"]) == 0


def test_real_linked_worktree_without_approval_blocks(real_repos, monkeypatch):
    assert gated(monkeypatch, command_for(real_repos["linked"]), real_repos["root"]) == 2


def test_bare_push_from_linked_worktree_without_approval_blocks(real_repos, monkeypatch):
    assert gated(monkeypatch, f"git {PUSH} origin HEAD:main", real_repos["linked"]) == 2


def test_approve_real_linked_worktree_then_consume_once(real_repos, monkeypatch):
    linked = real_repos["linked"]
    assert pg.approve(str(linked), "Synthetic candidate approval") == 0
    command = command_for(linked)
    assert gated(monkeypatch, command, real_repos["root"]) == 0
    assert gated(monkeypatch, command, real_repos["root"]) == 2


def test_canonical_approval_does_not_authorize_different_worktree_head(real_repos, monkeypatch):
    assert pg.approve(str(real_repos["canonical"]), "Synthetic baseline approval") == 0
    assert gated(monkeypatch, command_for(real_repos["linked"]), real_repos["root"]) == 2


def test_other_clone_approval_does_not_authorize_site(real_repos, monkeypatch):
    assert pg.approve(str(real_repos["unrelated"]), "Synthetic unrelated approval") == 0
    assert gated(monkeypatch, command_for(real_repos["linked"]), real_repos["root"]) == 2


@pytest.mark.parametrize("form", ["cd", "git-c", "relative-c", "git-dir", "work-tree"])
def test_shell_target_forms_keep_linked_worktree_guarded(real_repos, monkeypatch, form):
    linked = real_repos["linked"]
    git_dir = real_repos["git"](linked, "rev-parse", "--absolute-git-dir")
    commands = {
        "cd": command_for(linked),
        "git-c": f"git -C {linked} {PUSH} origin HEAD:main",
        "relative-c": f"git -C {linked.parent} -C {linked.name} {PUSH} origin HEAD:main",
        "git-dir": f"git --git-dir={git_dir} {PUSH} origin HEAD:main",
        "work-tree": f"git --git-dir {git_dir} --work-tree {linked} {PUSH} origin HEAD:main",
    }
    assert gated(monkeypatch, commands[form], real_repos["unrelated"]) == 2


@pytest.mark.parametrize("form", ["cd", "git-c"])
def test_quoted_spaces_resolve_actual_worktree(real_repos, monkeypatch, form):
    linked = real_repos["spaced"]
    command = (command_for(linked) if form == "cd" else
               f"git -C {shlex.quote(str(linked))} {PUSH} origin HEAD:main")
    assert gated(monkeypatch, command, real_repos["unrelated"]) == 2


def test_explicit_git_c_overrides_preceding_site_cd(real_repos, monkeypatch):
    command = (f"cd {real_repos['canonical']} && "
               f"git -C {real_repos['unrelated']} {PUSH} origin HEAD:main")
    assert gated(monkeypatch, command, real_repos["canonical"]) == 0


def test_push_explicit_site_remote_is_gated_from_unrelated_checkout(real_repos, monkeypatch):
    command = (f"cd {real_repos['unrelated']} && "
               f"git {PUSH} {real_repos['site_url']} HEAD:main")
    assert gated(monkeypatch, command, real_repos["root"]) == 2


def test_approved_head_does_not_authorize_different_pushed_ref(real_repos, monkeypatch):
    canonical = real_repos["canonical"]
    assert pg.approve(str(canonical), "Synthetic baseline approval") == 0
    command = f"cd {canonical} && git {PUSH} origin candidate:main"
    assert gated(monkeypatch, command, real_repos["root"]) == 2


def test_one_approval_cannot_authorize_two_pushes_in_one_shell(real_repos, monkeypatch):
    canonical = real_repos["canonical"]
    assert pg.approve(str(canonical), "Synthetic one-operation approval") == 0
    command = f"{command_for(canonical)} && git {PUSH} origin HEAD:main"
    assert gated(monkeypatch, command, real_repos["root"]) == 2


def test_unknown_variable_target_fails_closed(real_repos, monkeypatch):
    command = f'cd "$UNRESOLVED_SITE" && git {PUSH} origin HEAD:main'
    assert gated(monkeypatch, command, real_repos["root"]) == 2


def test_codex_exec_cmd_payload_cannot_skip_guard(real_repos, monkeypatch):
    assert gated(monkeypatch, command_for(real_repos["canonical"]),
                 real_repos["root"], tool="exec_command", field="cmd") == 2


def test_failed_approval_newline_cannot_reach_push_consumer(real_repos, monkeypatch):
    """The observed failed-approve/newline incident, with a fake push sink."""
    marker = real_repos["root"] / "push-consumer-reached"
    bin_dir = real_repos["root"] / "bin"
    bin_dir.mkdir()
    real_git = shutil.which("git")
    assert real_git
    shim = bin_dir / "git"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        f"if sys.argv[1:2] == [{PUSH!r}]:\n"
        f"    pathlib.Path({str(marker)!r}).write_text('synthetic sink reached')\n"
        "    raise SystemExit(0)\n"
        f"os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n"
    )
    shim.chmod(0o700)
    # This must fail even after linked-worktree approvals are repaired.
    nonexistent = real_repos["root"] / "missing-repository"
    command = (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(SCRIPT))} "
        f"--approve {shlex.quote(str(nonexistent))} --summary synthetic\n"
        f"{command_for(real_repos['linked'])}"
    )
    verdict = gated(monkeypatch, command, real_repos["root"])
    if verdict == 0:
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])
        subprocess.run(["/bin/sh", "-c", command], cwd=real_repos["root"],
                       env=env, text=True, capture_output=True, check=False, timeout=20)
    assert not marker.exists(), "Failed approval followed by newline reached the state-changing sink"
    assert verdict == 2


@pytest.mark.parametrize("prefix", ["export", "assign"])
def test_prior_shell_environment_cannot_redirect_unguarded_push(real_repos, monkeypatch, prefix):
    canonical = real_repos["canonical"]
    setup = f"GIT_DIR={canonical / '.git'} GIT_WORK_TREE={canonical}"
    if prefix == "export":
        setup = "export " + setup
    command = f"{setup}; git {PUSH} origin HEAD:main"
    assert gated(monkeypatch, command, real_repos["unrelated"]) == 2


@pytest.mark.parametrize("prefix", ["false &&", "(", "skipped-or", "failed-cd"])
def test_shell_control_flow_cannot_replace_actual_parent_cwd(real_repos, monkeypatch, prefix):
    unrelated = real_repos["unrelated"]
    if prefix == "(":
        command = f"(cd {unrelated}); git {PUSH} origin HEAD:main"
    elif prefix == "skipped-or":
        command = f"cd {real_repos['canonical']} || cd {unrelated}; git {PUSH} origin HEAD:main"
    elif prefix == "failed-cd":
        command = f"cd {real_repos['root'] / 'missing-directory'} && cd {unrelated}; git {PUSH} origin HEAD:main"
    else:
        command = f"false && cd {unrelated}; git {PUSH} origin HEAD:main"
    assert gated(monkeypatch, command, real_repos["canonical"]) == 2


@pytest.mark.parametrize("program", ["/bin/sh", "/bin/bash", "/bin/zsh"])
def test_nested_shell_publication_cannot_escape_detection(real_repos, monkeypatch, program):
    command = f"{program} -c {shlex.quote(command_for(real_repos['linked']))}"
    assert gated(monkeypatch, command, real_repos["unrelated"]) == 2


def test_nested_shell_worker_publication_cannot_escape_detection(real_repos, monkeypatch):
    command = "/bin/sh -c 'wrangler deploy index.js'"
    assert gated(monkeypatch, command, real_repos["canonical"]) == 2


@pytest.mark.parametrize("prefix", ["--config worker.toml", "--cwd ."])
def test_raw_worker_global_options_before_command_stay_guarded(real_repos, monkeypatch, prefix):
    command = f"wrangler {prefix} deploy index.js"
    assert gated(monkeypatch, command, real_repos["canonical"]) == 2


@pytest.mark.parametrize("tool", ["wrangler", "/fixture/wrangler/bin/wrangler.js"])
def test_raw_worker_direct_invocation_is_rejected(real_repos, monkeypatch, tool):
    command = ("node " if tool.endswith(".js") else "") + tool + " deploy index.js"
    assert gated(monkeypatch, command, real_repos["canonical"]) == 2


def test_raw_worker_dry_run_positive_control(real_repos, monkeypatch):
    assert gated(monkeypatch, "wrangler deploy index.js --dry-run", real_repos["canonical"]) == 0


@pytest.mark.parametrize("ending", ["--dry-run=false", "--no-dry-run", "--dryRun=false"])
def test_later_false_dry_run_option_cannot_enable_publication(real_repos, monkeypatch, ending):
    # Wrangler declares dry-run boolean; its yargs parser resolves this pair
    # to false. The presence of an earlier bare flag is not proof of dry-run.
    command = "wrangler deploy index.js --dry-run " + ending
    assert gated(monkeypatch, command, real_repos["canonical"]) == 2


def test_inherited_git_environment_cannot_change_approval_identity(real_repos, monkeypatch):
    canonical, unrelated = real_repos["canonical"], real_repos["unrelated"]
    monkeypatch.setenv("GIT_DIR", str(unrelated / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(unrelated))
    result = pg.approve(str(canonical), "Synthetic requested site approval")
    if result == 0:
        ledger = json.loads(Path(pg.ledger_path()).read_text())
        assert ledger["repo"] == str(canonical), "Approval silently rebound to inherited Git environment"
    else:
        assert result == 2


def test_regular_approval_concurrent_consumers_have_one_winner(real_repos):
    linked = real_repos["linked"]
    assert pg.approve(str(linked), "Synthetic one-use approval") == 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: pg.consume_ledger(str(linked))[0], range(2)))
    assert sorted(results) == [False, True]


def test_regular_approval_io_failure_burns_attempt(real_repos, monkeypatch):
    linked = real_repos["linked"]
    assert pg.approve(str(linked), "Synthetic crash-burn approval") == 0
    def disk_failure(*args):
        raise OSError("Synthetic persistence failure")
    monkeypatch.setattr(pg, "record_publish", disk_failure)
    assert pg.consume_ledger(str(linked))[0] is False
    assert not Path(pg.ledger_path()).exists()
    assert pg.consume_ledger(str(linked))[0] is False


def test_rapid_approval_check_cannot_authorize_replacement_plain_ledger(real_repos, monkeypatch):
    linked = str(real_repos["linked"])
    pg.record_publish(linked, "Synthetic recent publish")
    assert pg.approve(linked, "Synthetic rapid approval", True, "Approve this rapid fixture.") == 0
    original_consume = pg.consume_ledger
    def replace_before_consume(repo):
        # A concurrent ordinary approval is legal to record, but cannot use
        # the earlier ledger's rapid permission at the consumption boundary.
        assert pg.approve(linked, "Synthetic replacement without rapid approval") == 0
        return original_consume(repo)
    monkeypatch.setattr(pg, "consume_ledger", replace_before_consume)
    assert gated(monkeypatch, command_for(linked), real_repos["root"]) == 2


def artifact_binding(real_repos):
    root = real_repos["root"]
    consumer = root / "consumer.mjs"
    consumer.write_text("// non-executable fixture\n")
    digest = hashlib.sha256(consumer.read_bytes()).hexdigest()
    linked = real_repos["linked"]
    binding = {
        "schema": 1, "transaction_id": str(uuid4()), "surface": "worker",
        "repo": str(linked), "head_sha": real_repos["second"],
        "tree_sha": real_repos["git"](linked, "rev-parse", "HEAD^{tree}"),
        "consumer_path": str(consumer), "consumer_sha256": digest,
        "bound_files": [{"path": str(consumer), "sha256": digest}],
        "artifact_manifest_sha256": digest,
        "plan": {"surface": "worker", "target": "fixture-only"},
    }
    path = root / "binding.json"
    path.write_text(json.dumps(binding))
    return path, binding


def test_artifact_consumption_rename_failure_keeps_unspent_approval(real_repos, monkeypatch):
    path, _ = artifact_binding(real_repos)
    assert pg.approve_deployment(str(path), "Synthetic approved fixture", "Approve this fixture.") == 0
    def rename_failure(*args):
        raise OSError("Synthetic failure before one-way commit")
    monkeypatch.setattr(pg.os, "rename", rename_failure)
    assert pg.consume_deployment(str(path)) == 2
    assert len(list(real_repos["state"].glob("deployments/*/approval.json"))) == 1
    assert not list(real_repos["state"].glob("deployments/*/consumed.json"))


def test_artifact_consumption_failure_after_rename_burns_approval(real_repos, monkeypatch):
    path, _ = artifact_binding(real_repos)
    assert pg.approve_deployment(str(path), "Synthetic approved fixture", "Approve this fixture.") == 0
    def record_failure(*args):
        raise OSError("Synthetic failure after one-way commit")
    monkeypatch.setattr(pg, "record_publish", record_failure)
    assert pg.consume_deployment(str(path)) == 2
    assert not list(real_repos["state"].glob("deployments/*/approval.json"))
    assert len(list(real_repos["state"].glob("deployments/*/consumed.json"))) == 1
    assert pg.consume_deployment(str(path)) == 2


def test_artifact_peek_does_not_spend_approval(real_repos):
    path, _ = artifact_binding(real_repos)
    assert pg.approve_deployment(str(path), "Synthetic approved fixture", "Approve this fixture.") == 0
    assert pg.consume_deployment(str(path), peek=True) == 0
    assert len(list(real_repos["state"].glob("deployments/*/approval.json"))) == 1
    assert not list(real_repos["state"].glob("deployments/*/consumed.json"))
    assert pg.consume_deployment(str(path)) == 0


def test_artifact_symlink_ancestor_refuses_without_write(real_repos, monkeypatch):
    path, _ = artifact_binding(real_repos)
    destination = real_repos["root"] / "destination"
    destination.mkdir()
    link = real_repos["root"] / "linked-state"
    link.symlink_to(destination, target_is_directory=True)
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(link / "guard"))
    assert pg.approve_deployment(str(path), "Synthetic approved fixture", "Approve this fixture.") == 2
    assert list(destination.iterdir()) == []


def test_doctor_does_not_overwrite_symlink_target(real_repos, monkeypatch):
    state = real_repos["state"]
    state.mkdir()
    victim = real_repos["root"] / "unrelated-state.txt"
    victim.write_text("Original independent bytes\n")
    probe = state / ".doctor-probe"
    probe.symlink_to(victim)
    real_run = pg.subprocess.run
    def controlled_self_checks(args, **kwargs):
        if len(args) >= 3 and Path(args[1]) == SCRIPT:
            if args[2] == "--test":
                return subprocess.CompletedProcess(args, 0, "Hermetic controls passed\n", "")
            if args[2] == "--gate":
                payload = json.loads(kwargs["input"])
                command = payload["tool_input"]["command"]
                return subprocess.CompletedProcess(args, 2 if PUSH in command else 0, "", "")
        return real_run(args, **kwargs)
    monkeypatch.setattr(pg.subprocess, "run", controlled_self_checks)
    assert pg.run_doctor() in (0, 2)
    assert victim.read_text() == "Original independent bytes\n"
    assert probe.is_symlink(), "Doctor must not remove an unrelated existing path"


def node_wrapper_fixture(real_repos, surface="worker"):
    _, binding = artifact_binding(real_repos)
    consumer = real_repos["root"] / "fixture-release-gate.mjs"
    consumer.write_text("// Non-executable wrapper fixture\n")
    digest = hashlib.sha256(consumer.read_bytes()).hexdigest()
    binding["consumer_path"] = str(consumer)
    binding["consumer_sha256"] = digest
    binding["bound_files"] = [{"path": str(consumer), "sha256": digest}]
    binding["surface"] = surface
    binding["plan"]["surface"] = surface
    if surface == "database":
        migration = real_repos["root"] / "migration.sql"
        migration.write_text("CREATE TABLE fixture_cursor (task TEXT PRIMARY KEY);\n")
        binding["bound_files"].append({"path": str(migration), "sha256": hashlib.sha256(migration.read_bytes()).hexdigest()})
    transaction = real_repos["root"] / "transaction"
    transaction.mkdir()
    path = transaction / f"{surface}.binding.json"
    path.write_text(json.dumps(binding))
    receipt = real_repos["root"] / "acceptance.json"
    receipt.write_text(json.dumps({"snapshot": {"root": str(transaction / "inputs"),
                                                "source_head": binding["head_sha"]}}))
    command = f"node {consumer} deploy-{surface} {binding['head_sha']} {receipt}"
    return path, binding, command


@pytest.mark.parametrize("surface", ["worker", "database"])
def test_exact_node_wrapper_hook_peeks_without_spending(real_repos, monkeypatch, surface):
    path, _, command = node_wrapper_fixture(real_repos, surface)
    assert pg.approve_deployment(str(path), "Synthetic wrapper approval", "Approve this fixture.") == 0
    assert gated(monkeypatch, command, real_repos["root"], tool="exec_command", field="cmd") == 0
    assert len(list(real_repos["state"].glob("deployments/*/approval.json"))) == 1
    assert not list(real_repos["state"].glob("deployments/*/consumed.json"))
    assert pg.consume_deployment(str(path)) == 0
    assert gated(monkeypatch, command, real_repos["root"], tool="exec_command", field="cmd") == 2


@pytest.mark.parametrize("problem", ["missing-approval", "changed-consumer", "wrong-head", "wrong-executable"])
@pytest.mark.parametrize("surface", ["worker", "database"])
def test_node_wrapper_hook_refuses_unapproved_or_changed_invocation(real_repos, monkeypatch, problem, surface):
    path, binding, command = node_wrapper_fixture(real_repos, surface)
    if problem != "missing-approval":
        assert pg.approve_deployment(str(path), "Synthetic wrapper approval", "Approve this fixture.") == 0
    if problem == "changed-consumer":
        Path(binding["consumer_path"]).write_text("// Changed consumer\n")
    if problem == "wrong-head":
        command = command.replace(binding["head_sha"], real_repos["first"])
    if problem == "wrong-executable":
        command = "python3 " + command[len("node "):]
    assert gated(monkeypatch, command, real_repos["root"], tool="exec_command", field="cmd") == 2
    assert not list(real_repos["state"].glob("deployments/*/consumed.json"))


@pytest.mark.parametrize("command", [
    "wrangler d1 execute fixture --file fixture.sql --remote --json",
    "node /fixture/wrangler/bin/wrangler.js d1 execute fixture --file fixture.sql --remote --json",
    "wrangler d1 execute fixture --file fixture.sql --remote=true --json",
    "/bin/sh -c 'wrangler d1 execute fixture --file fixture.sql --remote --json'",
])
def test_raw_remote_database_mutation_requires_exact_consumer(real_repos, monkeypatch, command):
    assert gated(monkeypatch, command, real_repos["canonical"]) == 2


def test_changed_database_sql_refuses_private_consumption(real_repos, monkeypatch):
    path, _, command = node_wrapper_fixture(real_repos, "database")
    assert pg.approve_deployment(str(path), "Synthetic database approval", "Approve this fixture.") == 0
    (real_repos["root"] / "migration.sql").write_text("DROP TABLE fixture_cursor;\n")
    assert gated(monkeypatch, command, real_repos["root"], tool="exec_command", field="cmd") == 2
    assert pg.consume_deployment(str(path)) == 2
    assert not list(real_repos["state"].glob("deployments/*/consumed.json"))

"""publish_plugin.sh: build, then push to the published repository, here a local bare one."""

import os
import shutil
import subprocess

import pytest

from kb_plugin_fixture import SCRIPTS, VERSION, build, commit, files_under, git, make_repo

SCRIPT = SCRIPTS / "publish_plugin.sh"
SHELLS = sorted({"sh", *(name for name in ("dash", "bash") if shutil.which(name))})  # POSIX sh in every shell here
BOT = "kb-publish[bot] <kb-publish@users.noreply.invalid>"
HOST_LINE = "git.example.invalid ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleOnlyNotARealHostKey0000000000000000"


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "published.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(bare)], check=True)
    return bare


def publish(repo, tmp_path, env=None, *args, shell="sh"):
    """Run the script as CI would; its temporary folder lives in tmp_path/tmp so the test can see it cleaned."""
    (tmp_path / "tmp").mkdir(exist_ok=True)
    command = ["bash", "--posix"] if shell == "bash" else [shell]
    command += [str(SCRIPT), "--config", str(repo / "distribution" / "kb-plugin.json"), "--source",
                str(repo / "source"), *args]
    return subprocess.run(command, capture_output=True, text=True, cwd=tmp_path,
                          env={**os.environ, "TMPDIR": str(tmp_path / "tmp"), **(env or {})})


def tree(remote, ref="main") -> dict:
    """Every file on the published branch with its content."""
    names = git(remote, "ls-tree", "-r", "--name-only", ref).splitlines()
    return {name: git(remote, "show", f"{ref}:{name}") for name in names}


@pytest.mark.parametrize("shell", SHELLS)
def test_the_first_run_pushes_the_build_and_the_second_finds_nothing_to_change(repo, remote, tmp_path, shell):
    url = f"file://{remote}"
    first = publish(repo, tmp_path, {"KB_PUBLISH_REPO": url}, shell=shell)
    assert first.returncode == 0, first.stderr
    assert first.stdout.splitlines()[-1] == f"Published example-knowledge {VERSION} to {url} (main)."
    sha7 = git(repo, "rev-parse", "--short=7", "HEAD")
    assert git(remote, "log", "--format=%an <%ae>%n%s", "main") == \
        f"{BOT}\nPublish example-knowledge {VERSION} from {sha7}"
    direct = tmp_path / "direct"
    assert build(repo, direct).returncode == 0
    assert tree(remote) == {name: (direct / name).read_text(encoding="utf-8").rstrip("\n")
                            for name in files_under(direct)}
    second = publish(repo, tmp_path, {"KB_PUBLISH_REPO": url}, shell=shell)
    assert second.returncode == 0, second.stderr
    assert second.stdout.splitlines()[-1] == "The published copy already matches this build; nothing to push."
    assert git(remote, "rev-list", "--count", "main") == "1"
    assert list((tmp_path / "tmp").iterdir()) == []  # the temporary folder went with each run


def test_a_publication_replaces_everything_but_git(repo, remote, tmp_path):
    url = f"file://{remote}"
    assert publish(repo, tmp_path, {"KB_PUBLISH_REPO": url}).returncode == 0
    clone = tmp_path / "hand-edit"
    subprocess.run(["git", "clone", "--quiet", url, str(clone)], check=True)
    (clone / "stray.md").write_text("edited by hand in the published copy\n", encoding="utf-8")
    commit(clone, "A hand edit")
    git(clone, "push", "--quiet", "origin", "main")
    (repo / "source/datasets/reference/glossary.md").unlink()
    roadmap = repo / "source/datasets/active/roadmap.md"
    roadmap.write_text(roadmap.read_text(encoding="utf-8") + "\nReporting slips to the third quarter.\n",
                       encoding="utf-8")
    commit(repo, "Roadmap update", when="2026-11-02T14:05:00+00:00")
    third = publish(repo, tmp_path, {"KB_PUBLISH_REPO": url})
    assert third.returncode == 0, third.stderr
    assert third.stdout.splitlines()[-1] == f"Published example-knowledge 1.20261102.1405 to {url} (main)."
    published = tree(remote)
    references = "plugins/example-knowledge/skills/example-knowledge/references"
    assert "stray.md" not in published and f"{references}/datasets/reference/glossary.md" not in published
    assert published[f"{references}/datasets/active/roadmap.md"].endswith("Reporting slips to the third quarter.")
    assert git(remote, "rev-list", "--count", "main") == "3"


def test_the_branch_comes_from_the_environment(repo, remote, tmp_path):
    result = publish(repo, tmp_path, {"KB_PUBLISH_REPO": str(remote), "KB_PUBLISH_BRANCH": "published",
                                      "KB_PUBLISH_BOT_NAME": "ci-bot", "KB_PUBLISH_BOT_EMAIL": "ci@example.com"})
    assert result.returncode == 0, result.stderr
    assert git(remote, "for-each-ref", "--format=%(refname)") == "refs/heads/published"
    assert git(remote, "log", "--format=%an <%ae>", "published") == "ci-bot <ci@example.com>"


def test_a_refused_build_pushes_nothing(repo, remote, tmp_path):
    (repo / "source/notes/onboarding.md").write_text("No front matter.\n", encoding="utf-8")
    commit(repo)
    result = publish(repo, tmp_path, {"KB_PUBLISH_REPO": f"file://{remote}"})
    assert result.returncode == 1 and "no front matter" in result.stderr
    assert git(remote, "for-each-ref") == ""


@pytest.mark.parametrize("url", ["git@git.example.invalid:example/kb-plugin.git",
                                 "ssh://git@git.example.invalid/example/kb-plugin.git"])
def test_an_ssh_push_needs_pinned_host_keys_before_anything_runs(repo, tmp_path, url):
    result = publish(repo, tmp_path, {"KB_PUBLISH_REPO": url, "KB_PUBLISH_KNOWN_HOSTS": ""})
    assert result.returncode == 1 and "KB_PUBLISH_KNOWN_HOSTS is not set" in result.stderr
    assert result.stdout == ""  # refused before the build


def test_an_ssh_push_trusts_only_the_pinned_host_keys(repo, tmp_path):
    record = tmp_path / "ssh-call"
    fake_ssh = tmp_path / "fake-ssh"
    fake_ssh.write_text("\n".join([  # records its arguments and the known_hosts file it was given, then fails
        "#!/bin/sh", 'printf "%s\\n" "$@" > "$RECORD"', 'for arg in "$@"; do',
        '  case $arg in UserKnownHostsFile=*) cat "${arg#UserKnownHostsFile=}" > "$RECORD.hosts" ;; esac', "done",
        'echo "ssh: connect to host git.example.invalid: refused" >&2', "exit 255", ""]), encoding="utf-8")
    fake_ssh.chmod(0o755)
    key = tmp_path / "deploy_key"
    key.write_text("not a real key\n", encoding="utf-8")
    result = publish(repo, tmp_path, {
        "KB_PUBLISH_REPO": "git@git.example.invalid:example/kb-plugin.git", "KB_PUBLISH_KNOWN_HOSTS": HOST_LINE,
        "KB_PUBLISH_SSH_KEY_FILE": str(key), "GIT_SSH_COMMAND": str(fake_ssh), "RECORD": str(record)})
    assert result.returncode == 1
    assert "cannot reach git@git.example.invalid:example/kb-plugin.git" in result.stderr
    arguments = record.read_text(encoding="utf-8").splitlines()
    for option in ("GlobalKnownHostsFile=/dev/null", "StrictHostKeyChecking=yes", "IdentitiesOnly=yes", str(key)):
        assert option in arguments
    assert (tmp_path / "ssh-call.hosts").read_text(encoding="utf-8") == HOST_LINE + "\n"


def test_a_credential_in_the_url_is_never_printed(repo, tmp_path):
    result = publish(repo, tmp_path, {"KB_PUBLISH_REPO": "https://bot:s3cret-token@127.0.0.1:9/example/kb.git"})
    assert result.returncode == 1 and "cannot reach https://127.0.0.1:9/example/kb.git" in result.stderr
    assert "s3cret" not in result.stdout + result.stderr


def test_usage_and_settings_are_checked_first(repo, tmp_path):
    assert publish(repo, tmp_path, {}, "--commit").returncode == 2
    missing = publish(repo, tmp_path, {"KB_PUBLISH_REPO": ""})
    assert missing.returncode == 1 and "KB_PUBLISH_REPO is not set" in missing.stderr
    branch = publish(repo, tmp_path, {"KB_PUBLISH_REPO": "/nowhere.git", "KB_PUBLISH_BRANCH": "bad..name"})
    assert branch.returncode == 1 and "is not a branch name" in branch.stderr
    unreachable = publish(repo, tmp_path, {"KB_PUBLISH_REPO": str(tmp_path / "missing.git")})
    assert unreachable.returncode == 1 and "cannot reach" in unreachable.stderr
    assert os.access(SCRIPT, os.X_OK)

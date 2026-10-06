"""prep_init.py: profiles live only in the owning workspace's private repository (E73, IR-72).

Carried from scripts/test_prep_init.py and the ownership half of
scripts/test_profile_workspace.py; the migration and shared-pack tests left
with the code they tested.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prep_init.py"
sys.path.insert(0, str(SCRIPT.parent))

import prep_init as prep  # noqa: E402


def repo(tmp_path, name="one"):
    path = tmp_path / name
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True, timeout=10)
    top = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return Path(top)  # the physical path git reports (macOS tmp folders sit behind /var -> /private/var)


def cli(tmp_path, *args, cwd=None):
    home = tmp_path / "synthetic-home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True,
                          text=True, timeout=30, cwd=cwd or tmp_path)


def test_init_creates_principal_and_template(tmp_path):
    root = repo(tmp_path)
    result = prep.init_principal(root, "Ada", "CTO", "Acme", ["ship v2"], workspace="synthetic")
    principal = json.loads(Path(result["principal"]).read_text(encoding="utf-8"))
    assert principal["name"] == "Ada" and principal["role"] == "CTO"
    assert principal["goals_professional"] == ["ship v2"] and "authority" in principal
    assert Path(result["template"]).read_text(encoding="utf-8").startswith("# ")
    profiles = root / "profiles/meeting-prep"
    assert json.loads((profiles / ".owner.json").read_text()) == {"schema": 1, "workspace": "synthetic"}
    assert (profiles / "principal.json").stat().st_mode & 0o777 == 0o600
    assert profiles.stat().st_mode & 0o777 == 0o700


def test_init_refuses_overwrite(tmp_path):
    root = repo(tmp_path)
    prep.init_principal(root, "Ada", "CTO", "Acme", [], workspace="synthetic")
    with pytest.raises(FileExistsError):
        prep.init_principal(root, "Bob", "CFO", "Acme", [], workspace="synthetic")
    assert json.loads((root / "profiles/meeting-prep/principal.json").read_text())["name"] == "Ada"


def test_add_reader_writes_profile_and_refuses_overwrite(tmp_path):
    root = repo(tmp_path)
    body = Path(prep.add_reader(root, "rivera", "Dana Rivera", "peer", workspace="synthetic")["reader"]).read_text()
    assert body.startswith("# Dana Rivera") and "relationship: peer" in body
    with pytest.raises(FileExistsError):
        prep.add_reader(root, "rivera", "Someone Else", "boss", workspace="synthetic")


@pytest.mark.parametrize("reader_id, relationship, message", [
    ("x", "nemesis", "relationship must be"), ("../evil", "peer", "alphanumeric")])
def test_add_reader_rejects_bad_input(tmp_path, reader_id, relationship, message):
    with pytest.raises(ValueError, match=message):
        prep.add_reader(tmp_path / "prep", reader_id, "X", relationship, workspace="synthetic")


def test_cli_without_owner_refuses_before_writing(tmp_path):
    result = cli(tmp_path, "init", "--name", "Ada", "--role", "Engineer", "--org", "Synthetic")
    assert result.returncode == 2
    assert not (tmp_path / "synthetic-home/.synthesis").exists()


def test_never_selects_home_or_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ValueError, match="explicit"):
        prep.owner_root(None, "one")
    with pytest.raises(ValueError):
        prep.owner_root(tmp_path, "one")  # the home folder is never an owner


def test_cli_init_end_to_end_and_second_init_refuses(tmp_path):
    root = repo(tmp_path)
    args = ("init", "--name", "Ada", "--role", "CTO", "--org", "Acme", "--goals", "a;b",
            "--context-repo", str(root), "--workspace", "synthetic")
    first = cli(tmp_path, *args)
    assert first.returncode == 0, first.stderr
    assert json.loads((root / "profiles/meeting-prep/principal.json").read_text())["goals_professional"] == ["a", "b"]
    assert cli(tmp_path, *args).returncode == 2


def test_workspace_profiles_are_separate_by_explicit_owner(tmp_path):  # E73
    one, two = repo(tmp_path), repo(tmp_path, "two")
    for owner, workspace in ((one, "one"), (two, "two")):
        result = cli(tmp_path, "init", "--context-repo", str(owner), "--workspace", workspace,
                     "--name", "Ada", "--role", "Engineer", "--org", "Synthetic")
        assert result.returncode == 0, result.stderr
        assert (owner / "profiles/meeting-prep/principal.json").is_file()
    assert prep.owner_root(one, "one") != prep.owner_root(two, "two")
    assert not (tmp_path / "synthetic-home/.synthesis").exists()


def test_explicit_owner_resolves_independently_of_cwd(tmp_path):
    owner = repo(tmp_path)
    nested = tmp_path / "elsewhere"
    nested.mkdir()
    first = cli(tmp_path, "resolve", "--context-repo", str(owner), "--workspace", "one")
    second = cli(tmp_path, "resolve", "--context-repo", str(owner), "--workspace", "one", cwd=nested)
    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout) == json.loads(second.stdout)
    assert not (owner / "profiles").exists()  # resolve creates nothing


@pytest.mark.parametrize("kind", ["wrong-workspace", "missing-workspace", "not-repo", "subdir",
                                  "relative", "traversal", "symlink", "unbound-profiles"])
def test_owner_resolution_refuses_ambiguous_or_unsafe_owner(tmp_path, kind):
    owner = repo(tmp_path)
    prep.init_principal(owner, "Ada", "Engineer", "Synthetic", [], workspace="one")
    path, workspace = owner, "one"
    if kind == "wrong-workspace":
        workspace = "two"
    elif kind == "missing-workspace":
        workspace = None
    elif kind == "not-repo":
        path = tmp_path
    elif kind == "subdir":
        path = owner / "profiles"
    elif kind == "relative":
        path = Path("one")
    elif kind == "traversal":
        path = owner / ".." / owner.name
    elif kind == "symlink":
        path = tmp_path / "alias"
        path.symlink_to(owner, target_is_directory=True)
    else:
        (owner / "profiles/meeting-prep/.owner.json").unlink()
    with pytest.raises(ValueError):
        prep.owner_root(path, workspace)


@pytest.mark.parametrize("kind", ["principal-symlink", "reader-parent-symlink", "principal-hardlink",
                                  "owner-hardlink", "owner-symlink"])
def test_existing_special_paths_refuse_without_overwrite(tmp_path, kind):
    owner = repo(tmp_path)
    root = owner / "profiles/meeting-prep"
    prep.add_reader(owner, "safe", "Safe", "peer", workspace="one")
    foreign = tmp_path / "foreign"
    foreign.write_text("UNCHANGED")
    if kind == "principal-symlink":
        (root / "principal.json").symlink_to(foreign)
    elif kind == "principal-hardlink":
        os.link(foreign, root / "principal.json")
    elif kind == "owner-hardlink":
        os.link(root / ".owner.json", tmp_path / "owner-link")
    elif kind == "owner-symlink":
        (root / ".owner.json").rename(tmp_path / "saved-owner")
        (root / ".owner.json").symlink_to(tmp_path / "saved-owner")
    else:
        (root / "readers").rename(root / "saved-readers")
        (root / "readers").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        prep.init_principal(owner, "Ada", "Engineer", "Synthetic", [], workspace="one")
    assert foreign.read_text() == "UNCHANGED"


def test_owner_marker_boolean_schema_refuses(tmp_path):
    owner = repo(tmp_path)
    prep.add_reader(owner, "safe", "Synthetic", "peer", workspace="one")
    (owner / "profiles/meeting-prep/.owner.json").write_text('{"schema":true,"workspace":"one"}')
    with pytest.raises(ValueError, match="ambiguous owner"):
        prep.owner_root(owner, "one")


def test_size_bound_precedes_owner_creation(tmp_path):
    owner = repo(tmp_path)
    with pytest.raises(ValueError, match="8 MiB"):
        prep.init_principal(owner, "x" * prep.MAX_FILE_BYTES, "Role", "Synthetic", [], workspace="one")
    assert not (owner / "profiles").exists()


def test_concurrent_same_reader_creation_never_overwrites(tmp_path):
    owner = repo(tmp_path)
    command = [sys.executable, str(SCRIPT), "add-reader", "--context-repo", str(owner),
               "--workspace", "one", "--id", "shared", "--name", "Synthetic", "--relationship", "peer"]
    workers = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        outputs = [p.communicate(timeout=20) for p in workers]
    finally:
        for p in workers:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=3)
    assert sorted(p.returncode for p in workers) == [0, 2], outputs
    shared = owner / "profiles/meeting-prep/readers/shared.md"
    assert shared.read_text().startswith("# Synthetic\n") and shared.stat().st_nlink == 1

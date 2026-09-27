from __future__ import annotations
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from repository_binding import BindingError, validate_argv, COMMANDS


@pytest.mark.parametrize("argv", [
    ["bkt", "pr", "ls", "--repo", "fixture"],
    ["bkt", "pr", "comment", "1", "--repo=fixture", "--text", "--repo"],
    ["bkt", "pr", "create", "--repo", "fixture", "--reviewer", "user", "--draft"],
    ["bkt", "api", "/repositories/team/fixture/pullrequests"],
    ["bkt", "api", "/rest/api/1.0/projects/TEAM/repos/fixture/pull-requests"],
])
def test_repo_bound_positive(argv):
    assert validate_argv(argv)["repo"] == "fixture"


@pytest.mark.parametrize("argv", [
    ["bkt", "pr", "comment", "1", "--text", "--repo", "fixture"],
    ["bkt", "pr", "list", "--repo", "fixture", "--repo=foreign"],
    ["bkt", "pr", "list", "--repo", "$UNKNOWN"],
    ["bkt", "pr", "list", "--repo", "../other"],
    ["bkt", "api", "/repositories/team/fixture/../foreign"],
    ["bkt", "api", "/repositories/team/fixture/%2e%2e/foreign"],
    ["bkt", "api", "https://example.invalid/repositories/team/fixture"],
    ["bkt", "api", "/user", "--method", "POST"],
    ["bkt", "api", "/user", "--input", "{}"],
    ["bkt", "mcp", "serve"],
    ["bkt", "pr", "unknown", "--repo", "fixture"],
    ["bkt", "pr", "list", "--repo", "fixture", "--new-flag"],
])
def test_ambiguous_or_foreign_target_refused(argv):
    with pytest.raises(BindingError):
        validate_argv(argv)


def test_every_repo_command_requires_and_accepts_exact_binding():
    for path, profile in COMMANDS.items():
        if "--repo" not in profile["flags"]:
            continue
        # Group-only commands are intentionally not admitted as an operation.
        if any(key.startswith(path + " ") for key in COMMANDS):
            continue
        if path.startswith("context "):
            continue  # Configuration changes do not read/write a repository.
        words=["bkt", *path.split()]
        with pytest.raises(BindingError):
            validate_argv(words)
        assert validate_argv([*words,"--repo","fixture"])["repo"] == "fixture", path


def test_short_repo_alias_is_an_explicit_binding():
    assert validate_argv(["bkt", "variable", "list", "-R", "synthetic-repo"])["repo"] == "synthetic-repo"
    assert validate_argv(["bkt", "variable", "ls", "-R=synthetic-repo"])["repo"] == "synthetic-repo"
    for args in [
        ["bkt", "variable", "list", "-R", "synthetic-repo", "--repo", "other"],
        ["bkt", "variable", "list", "-R", "$UNKNOWN"],
        ["bkt", "variable", "list", "-R", "synthetic-repo", "-R", "synthetic-repo"],
    ]:
        with pytest.raises(BindingError):
            validate_argv(args)

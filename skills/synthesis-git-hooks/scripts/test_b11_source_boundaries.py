"""Independent fixed controls for the frozen B11 package; synthetic inputs only."""

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import pytest

PUBLIC = Path(__file__).resolve().parents[3]
for skill in [
    "synthesis-project-management",
    "synthesis-git-hooks",
    "synthesis-daily-rituals",
]:
    sys.path.insert(0, str(PUBLIC / "skills" / skill / "scripts"))
import team_contract as tc  # noqa: E402 - exact source owner bound above
from test_team_contract import contract  # noqa: E402 - exact source owner bound above
import _load_config as policy  # noqa: E402 - exact source owner bound above


def test_contract_regular_digest_positive(tmp_path):
    p = tmp_path / "team.json"
    p.write_text(json.dumps(contract()))
    assert (
        tc.load(p, expected_digest=hashlib.sha256(p.read_bytes()).hexdigest())
        == contract()
    )


def test_contract_ancestor_alias_created_during_read_refuses(tmp_path, monkeypatch):
    parent = tmp_path / "enrolled"
    parent.mkdir()
    p = parent / "team.json"
    p.write_text(json.dumps(contract()))
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    moved = tmp_path / "moved"
    original_read = tc.os.read
    changed = []

    def raced(fd, count):
        data = original_read(fd, count)
        if data and not changed:
            parent.rename(moved)
            parent.symlink_to(moved, target_is_directory=True)
            changed.append(True)
        return data

    monkeypatch.setattr(tc.os, "read", raced)
    with pytest.raises(tc.TeamContractError):
        tc.load(p, expected_digest=digest)
    assert changed


def team_config(tmp_path):
    p = tmp_path / "policy.json"
    p.write_text(
        json.dumps(
            {
                "schema": 1,
                "organization": "synthetic-team",
                "repository_prefixes": ["https://git.example/team/"],
                "mandatory_patterns": ["SYNTHETIC_CONFIDENTIAL"],
            }
        )
    )
    return {
        "team_policy_files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()},
        "tier_0_always": ["SECRET_VALUE"],
        "tier_1_strict_only": ["BASE_PRIVATE"],
        "allowlist_lines": [".*"],
        "diff_exclude_paths": [".*"],
        "personal_remote_patterns": ["git.example"],
    }


@pytest.mark.parametrize(
    "remote",
    [
        "https://git.example/team/repo.git",
        "git@git.example:team/repo.git",
        "ssh://git@git.example/team/repo.git",
        "not-a-remote",
    ],
)
def test_team_policy_same_repository_or_unresolvable_cannot_drop_restriction(
    tmp_path, remote
):
    try:
        result = policy.apply_team_policy(team_config(tmp_path), [remote])
    except policy.ConfigError:
        return  # safe refusal is permitted for unsupported source identity
    assert result["_team_mandatory_regex"] == "SYNTHETIC_CONFIDENTIAL"


def test_other_organization_positive(tmp_path):
    result = policy.apply_team_policy(
        team_config(tmp_path), ["https://other.example/team/repo.git"]
    )
    assert result["_team_mandatory_regex"] == ""


def test_precommit_same_repository_transport_cannot_skip_enrolled_mandatory_rule(
    tmp_path,
):
    # Actual staged-content consumer; no remote, network or user repository access.
    from test_pre_commit import repository, HOOK

    repo, env = repository(tmp_path)
    c = team_config(tmp_path)
    source, digest = next(iter(c["team_policy_files"].items()))
    Path(env["SYNTHESIS_GIT_HOOK_CONFIG"]).write_text(
        "config_version: 2\npersonal_remote_patterns:\n  - git.example\ntier_0_always:\n  - SECRET_VALUE\ntier_1_strict_only:\n  - BASE_PRIVATE\nallowlist_lines:\n  - .*\ndiff_exclude_paths:\n  - .*\ncheck_commit_message: false\nteam_policy_files:\n  "
        + source
        + ": "
        + digest
        + "\n"
    )
    p = repo / "new.txt"
    p.write_text("SYNTHETIC_CONFIDENTIAL\n")
    subprocess.run(
        ["git", "add", "new.txt"], cwd=repo, check=True, capture_output=True, timeout=10
    )
    observations = []
    for remote in [
        "https://git.example/team/repo.git",
        "git@git.example:team/repo.git",
    ]:
        subprocess.run(
            ["git", "remote", "set-url", "origin", remote],
            cwd=repo,
            check=True,
            capture_output=True,
            timeout=10,
        )
        result = subprocess.run(
            [str(HOOK)], cwd=repo, env=env, text=True, capture_output=True, timeout=20
        )
        observations.append(
            {
                "remote": remote,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    (tmp_path / "observations.json").write_text(json.dumps(observations, indent=2))
    assert (
        observations[0]["returncode"] == 1
    )  # positive control proves policy was enrolled
    assert observations[1]["returncode"] != 0, observations


@pytest.mark.parametrize(
    "remote",
    [
        "https://git.example/elsewhere/repo",
        "https://git.example/Team/repo",
        "https://other.example/team/repo",
    ],
)
def test_explicit_distinct_scope_is_not_reassigned(tmp_path, remote):
    assert (
        policy.apply_team_policy(team_config(tmp_path), [remote])[
            "_team_mandatory_regex"
        ]
        == ""
    )


@pytest.mark.parametrize(
    "remote",
    [
        "https://git.example:8443/team/repo",
        "ssh://git@git.example:2222/team/repo",
        "https://git.example/team/%2e%2e/elsewhere",
        "https://user:secret@git.example/team/repo",
    ],
)
def test_ambiguous_service_or_encoding_keeps_restrictions(tmp_path, remote):
    assert (
        policy.apply_team_policy(team_config(tmp_path), [remote])[
            "_team_mandatory_regex"
        ]
        == "SYNTHETIC_CONFIDENTIAL"
    )


def test_clean_ssh_content_remains_usable_with_mandatory_layer(tmp_path):
    from test_pre_commit import repository, HOOK

    repo, env = repository(tmp_path)
    c = team_config(tmp_path)
    source, digest = next(iter(c["team_policy_files"].items()))
    Path(env["SYNTHESIS_GIT_HOOK_CONFIG"]).write_text(
        "config_version: 2\npersonal_remote_patterns:\n  - git.example\ntier_0_always:\n  - SECRET_VALUE\ntier_1_strict_only:\n  - BASE_PRIVATE\ncheck_commit_message: false\nteam_policy_files:\n  "
        + source
        + ": "
        + digest
        + "\n"
    )
    (repo / "clean.txt").write_text("ordinary synthetic content\n")
    subprocess.run(
        ["git", "add", "clean.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
        timeout=10,
    )
    subprocess.run(
        ["git", "remote", "set-url", "origin", "git@git.example:team/repo.git"],
        cwd=repo,
        check=True,
        capture_output=True,
        timeout=10,
    )
    r = subprocess.run(
        [str(HOOK)], cwd=repo, env=env, capture_output=True, text=True, timeout=20
    )
    assert r.returncode == 0, r.stdout + r.stderr

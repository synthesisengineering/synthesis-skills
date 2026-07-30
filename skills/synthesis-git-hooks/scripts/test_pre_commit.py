from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HOOK = SCRIPT_DIR / "pre-commit"


def run(repository: Path, *command: str, env: dict[str, str] | None = None):
    return subprocess.run(
        command,
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def policy(path: Path) -> None:
    path.write_text(
        """\
config_version: 1
personal_remote_patterns:
  - '[:/]never-matches/'
tier_0_always:
  credentials:
    - 'AKIA[0-9A-Z]{16}'
tier_1_strict_only:
  confidentiality:
    - 'confidential'
check_commit_message: false
""",
        encoding="utf-8",
    )


def repository(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "repo"
    root.mkdir()
    assert run(root, "git", "init").returncode == 0
    assert run(root, "git", "config", "user.name", "Test").returncode == 0
    assert run(root, "git", "config", "user.email", "test@example.com").returncode == 0
    assert (
        run(
            root,
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/example/public-repo.git",
        ).returncode
        == 0
    )
    (root / "CLAUDE.md").write_text(
        "# Rules\n\nDo not add confidential material.\n",
        encoding="utf-8",
    )
    assert run(root, "git", "add", "CLAUDE.md").returncode == 0
    assert (
        run(
            root,
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            "Initial",
        ).returncode
        == 0
    )
    config = tmp_path / "policy.yaml"
    policy(config)
    environment = dict(os.environ)
    environment["SYNTHESIS_GIT_HOOK_CONFIG"] = str(config)
    return root, environment


def test_exact_instruction_copy_is_not_rescanned(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    (root / "AGENTS.md").write_bytes((root / "CLAUDE.md").read_bytes())
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    assert run(root, "git", "add", "AGENTS.md", "CLAUDE.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_genuinely_new_sensitive_line_still_blocks(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    (root / "NEW.md").write_text("New confidential material.\n", encoding="utf-8")
    assert run(root, "git", "add", "NEW.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout

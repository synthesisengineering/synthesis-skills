from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "handoff.py"


def run_cli(
    project: Path, *args: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    env.pop("SYNTHESIS_HANDOFF_SELF", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--project-root", str(project)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def write_prompt(project: Path, text: str = "do the next round\n") -> Path:
    prompt = project / "prompt.md"
    prompt.write_text(text, encoding="utf-8")
    return prompt


def test_write_read_done_flow(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    written = run_cli(
        tmp_path,
        "write",
        "--to",
        "codex",
        "--from",
        "claude",
        "--file",
        str(prompt),
        "--round",
        "3",
        "--summary",
        "round three",
    )
    assert written.returncode == 0, written.stdout + written.stderr
    assert "handoff h-" in written.stdout
    handoff_id = written.stdout.split()[1]

    queue = json.loads(
        (tmp_path / "resources" / "handoffs" / "queue.json").read_text()
    )
    assert queue[0]["state"] == "pending"
    assert queue[0]["to"] == "codex"
    assert queue[0]["from"] == "claude"
    assert queue[0]["round"] == 3

    read = run_cli(tmp_path, "read", "--as", "codex")
    assert read.returncode == 0, read.stdout + read.stderr
    assert "do the next round" in read.stdout

    queue = json.loads(
        (tmp_path / "resources" / "handoffs" / "queue.json").read_text()
    )
    assert queue[0]["state"] == "claimed"

    done = run_cli(tmp_path, "done", "--id", handoff_id)
    assert done.returncode == 0
    queue = json.loads(
        (tmp_path / "resources" / "handoffs" / "queue.json").read_text()
    )
    assert queue[0]["state"] == "done"


def test_read_refuses_without_identity(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    run_cli(tmp_path, "write", "--to", "codex", "--file", str(prompt))
    read = run_cli(tmp_path, "read")
    assert read.returncode == 2
    assert "identity is required" in read.stdout


def test_read_uses_env_identity(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    run_cli(tmp_path, "write", "--to", "codex", "--file", str(prompt))
    read = run_cli(
        tmp_path, "read", env_extra={"SYNTHESIS_HANDOFF_SELF": "codex"}
    )
    assert read.returncode == 0, read.stdout + read.stderr


def test_read_refuses_tampered_payload(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    written = run_cli(tmp_path, "write", "--to", "codex", "--file", str(prompt))
    assert written.returncode == 0
    stored = next((tmp_path / "resources" / "handoffs").glob("to-codex-*.md"))
    stored.write_text("tampered\n", encoding="utf-8")

    read = run_cli(tmp_path, "read", "--as", "codex")
    assert read.returncode == 2
    assert "has changed since it was handed off" in read.stdout
    queue = json.loads(
        (tmp_path / "resources" / "handoffs" / "queue.json").read_text()
    )
    assert queue[0]["state"] == "pending"


def test_read_with_empty_queue_exits_one(tmp_path: Path) -> None:
    read = run_cli(tmp_path, "read", "--as", "claude")
    assert read.returncode == 1
    assert "no pending handoff" in read.stdout


def test_write_refuses_bad_agent_label(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    written = run_cli(tmp_path, "write", "--to", "Not A Slug", "--file", str(prompt))
    assert written.returncode == 2
    assert "lowercase agent slug" in written.stdout


def test_done_refuses_unknown_id(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "done", "--id", "h-missing")
    assert done.returncode == 2
    assert "no handoff with id" in done.stdout


def test_round_is_optional(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    written = run_cli(tmp_path, "write", "--to", "claude", "--file", str(prompt))
    assert written.returncode == 0
    queue = json.loads(
        (tmp_path / "resources" / "handoffs" / "queue.json").read_text()
    )
    assert queue[0]["round"] is None
    read = run_cli(tmp_path, "read", "--as", "claude")
    assert read.returncode == 0


SKILLS_ROOT = SCRIPT.parents[2]


def test_pm_skill_documents_the_handoff_queue() -> None:
    text = (SCRIPT.parent.parent / "SKILL.md").read_text(encoding="utf-8")
    assert "### The Handoff Queue" in text
    assert "scripts/handoff.py" in text
    assert "Nothing self-triggers" in text


def test_autopilot_wires_packet_and_handoff() -> None:
    text = (SKILLS_ROOT / "synthesis-autopilot" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "synthesis-decision-packet" in text
    assert "build_packet.py" in text
    assert "handoff.py" in text
    assert "never reimplemented inline" in text


def test_decision_packet_names_concrete_handoff_path() -> None:
    text = (SKILLS_ROOT / "synthesis-decision-packet" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "synthesis-project-management/scripts/handoff.py" in text

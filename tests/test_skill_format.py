"""R4: every skill marked `format: v5` follows docs/skill-format.md."""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return match.group(1) if match else ""


def v5_skills():
    return sorted(p for p in SKILLS.glob("*/SKILL.md")
                  if re.search(r"^\s*format:\s*v5\s*$", _frontmatter(p.read_text(encoding="utf-8")), re.M))


def _check(skill_md: Path) -> list[str]:
    text = skill_md.read_text(encoding="utf-8")
    front = _frontmatter(text)
    problems = []
    description = re.search(r'^description:\s*"?(.*?)"?\s*$', front, re.M)
    if not description or len(description.group(1)) > 300:
        problems.append("description missing or over 300 characters")
    for field in ("name", "license"):
        if not re.search(rf"^{field}:", front, re.M):
            problems.append(f"frontmatter lacks {field}")
    lines = text.splitlines()
    size = len(text.encode("utf-8"))
    if size > 8000:
        problems.append(f"SKILL.md is {size} bytes (Codex truncates past 8,000): reorganize it, moving whole passages "
                        "word for word into references/; never trim it (docs/skill-format.md, rule 3)")
    headings = [line for line in lines if line.startswith("## ")]
    if headings[:2] != ["## Binding rules", "## Contents"]:
        problems.append(f"first sections must be Binding rules then Contents, found {headings[:2]}")
    contents = text.split("## Contents", 1)[-1].split("\n## ", 1)[0]
    for ref in sorted((skill_md.parent / "references").glob("*.md")):
        if f"references/{ref.name}" not in contents:
            problems.append(f"references/{ref.name} is not listed in Contents")
        ref_lines = ref.read_text(encoding="utf-8").splitlines()
        if len(ref_lines) > 1500:
            problems.append(f"references/{ref.name} is {len(ref_lines)} lines (limit 1500)")
    return problems


V5_SKILLS = v5_skills()


@pytest.mark.parametrize("skill_md", V5_SKILLS, ids=[p.parent.name for p in V5_SKILLS])
def test_v5_skill_follows_the_format(skill_md):
    assert _check(skill_md) == []


def test_checker_catches_each_rule(tmp_path):
    skill = tmp_path / "demo"
    (skill / "references").mkdir(parents=True)
    (skill / "references" / "orphan.md").write_text("x\n")
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: " + "x" * 301 +
                                    "\nmetadata:\n  format: v5\n---\n\n## Procedure\n")
    found = " | ".join(_check(skill / "SKILL.md"))
    for expected in ("over 300", "lacks license", "Binding rules then Contents", "orphan.md is not listed"):
        assert expected in found


def _demo_skill(root: Path, description: str, procedure: str) -> Path:
    skill = root / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        f"---\nname: demo\ndescription: {description}\nlicense: CC0-1.0\nmetadata:\n  format: v5\n---\n\n"
        "What the demo is for.\n\n## Binding rules\n\n1. **One rule,** with its reason.\n\n"
        f"## Contents\n\n- Procedure: the steps.\n\n## Procedure\n\n{procedure}\n", encoding="utf-8")
    return skill / "SKILL.md"


def test_checker_catches_the_wording_rules(tmp_path):
    """The parts of rules 9, 18 and 20 a test can check without a false alarm on any skill today."""
    found = " | ".join(_check(_demo_skill(
        tmp_path, "You can use this to sync files.",
        "Minimize tool calls, and hold all findings for the final report.\n"
        'Write your reasoning in <thinking> tags, then return {"reasoning": "..."}.')))
    for expected in ("first or second person", "limits tools or updates in general", "asks for the model's reasoning"):
        assert expected in found


def test_quoted_phrases_and_explanations_pass(tmp_path):
    """Words quoted as a user would type them, or as text not to write, are not the skill's own voice."""
    skill_md = _demo_skill(
        tmp_path,
        "Arm a watcher before a turn ends. Use when a reply would say 'I'll pick it up once' or \"you can stop\".",
        'Use a search when a fact may have changed since training, not "minimize tool calls".\n'
        "Ask for a short explanation of the result and the evidence behind it.")
    assert _check(skill_md) == []

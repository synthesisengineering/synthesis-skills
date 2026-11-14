from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path



MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kb_config.py"
TEMPLATE = MODULE_PATH.parents[1] / "assets" / "sharing-policy.template.md"
SPEC = importlib.util.spec_from_file_location("kb_config", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_config() -> dict:
    return {
        "bundle_path": "source",
        "git_host": "github",
        "default_branch": "main",
        "branch_prefix": "kb/",
        "ship": "pr",
        "review": {
            "who_merges": "A maintainer other than the editor",
            "default_reviewers": [],
            "setup_guide": None,
        },
        "editable": ["source/**"],
        "refuse": [".agents/**", "compiled/**"],
        "generated_artifacts": ["compiled/**", "all-knowledge.md"],
        "topic_routing": {"reference": "source/reference"},
        "taxonomy_path": "source/taxonomy.md",
        "frontmatter": {
            "required": ["type"],
            "house": ["title", "tags", "timestamp", "status"],
            "date_field": "timestamp",
            "reserved_files": ["index.md", "log.md"],
        },
        "confidentiality": {
            "forbidden_words_source": None,
            "hook_path": None,
            "visible_to": "Repository readers",
        },
        "notes": "",
    }


def write_repo(tmp_path: Path, config: dict | None = None) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / "source" / "reference").mkdir(parents=True)
    (repo / "source" / "taxonomy.md").write_text("# Taxonomy\n", encoding="utf-8")
    (repo / ".agents" / "knowledge-base.yaml").write_text(
        json.dumps(config or valid_config()),
        encoding="utf-8",
    )
    return repo


def test_valid_contract_and_paths(tmp_path: Path) -> None:
    repo = write_repo(tmp_path)
    _, config = MODULE.load_config(repo, None)
    assert MODULE.validate_config(config) == []
    assert MODULE.check_paths(repo.resolve(), config) == []


def test_classification_precedence() -> None:
    config = valid_config()
    config["editable"] = ["source/**", "compiled/**"]
    assert MODULE.classify("source/reference/item.md", config) == "editable"
    assert MODULE.classify("compiled/bundle.md", config) == "generated"
    assert MODULE.classify(".agents/knowledge-base.yaml", config) == "refused"
    assert MODULE.classify("README.md", config) == "outside"


def test_rejects_frontmatter_date_alias_drift() -> None:
    config = valid_config()
    config["frontmatter"]["date_field"] = "last_updated"
    errors = MODULE.validate_config(config)
    assert any("frontmatter.date_field" in error for error in errors)


def test_rejects_path_escape() -> None:
    config = valid_config()
    config["bundle_path"] = "../outside"
    errors = MODULE.validate_config(config)
    assert any("bundle_path" in error for error in errors)


def test_symlinked_contract_path_that_leaves_the_repo_is_refused(tmp_path: Path) -> None:  # E93
    repo = write_repo(tmp_path)
    outside = tmp_path / "outside-bundle"
    outside.mkdir()
    (repo / "linked").symlink_to(outside, target_is_directory=True)
    config = valid_config()
    config["bundle_path"] = "linked"
    try:
        errors = MODULE.check_paths(repo, config)
    except ValueError as exc:
        errors = [str(exc)]
    assert any("escapes" in error for error in errors), errors


def test_a_key_the_contract_does_not_name_is_refused_at_every_level() -> None:
    """A misspelled optional key would otherwise switch off what it configures in silence: `sharing_polcy` would leave
    a knowledge base with no sharing policy while the configuration gate said VALID."""
    for section in ("", "review", "frontmatter", "confidentiality"):
        config = valid_config()
        (config[section] if section else config)["sharing_polcy"] = ".agents/sharing-policy.md"
        field = f"{section}.sharing_polcy" if section else "sharing_polcy"
        errors = MODULE.validate_config(config)
        assert any(error.startswith(f"{field}: unknown key") for error in errors), (section, errors)


def test_the_sharing_policy_and_its_phrases_validate_and_a_named_policy_must_be_there(tmp_path: Path) -> None:
    """The organization's own phrases: the plugin ships none, so an empty list is a valid contract (the scan, not the
    contract, refuses to run on it), and anything but a list of phrases is refused."""
    config = valid_config()
    config["confidentiality"].update(sharing_policy=".agents/sharing-policy.md", backstop_phrases=["zephyr ledger", "opal"])
    assert MODULE.validate_config(config) == []
    repo = write_repo(tmp_path, config)
    assert any(error.startswith("confidentiality.sharing_policy: configured file does not exist")
               for error in MODULE.check_paths(repo.resolve(), config))
    (repo / ".agents" / "sharing-policy.md").write_text("# Sharing policy\n", encoding="utf-8")
    assert MODULE.check_paths(repo.resolve(), config) == []
    config["confidentiality"]["backstop_phrases"] = []
    assert MODULE.validate_config(config) == []
    for broken in ({"sharing_policy": "../outside.md"}, {"sharing_policy": "/srv/policy.md"},
                   {"backstop_phrases": "zephyr ledger"}, {"backstop_phrases": ["zephyr ledger", " "]},
                   {"backstop_phrases": {"add": ["zephyr ledger"]}}, {"backstop_phrases": None}):
        changed = valid_config()
        changed["confidentiality"].update(broken)
        field = next(iter(broken))
        assert any(error.startswith(f"confidentiality.{field}: ") for error in MODULE.validate_config(changed)), broken


# ---- adopting the sharing standard in an existing knowledge base ------------------

BLOCK_CONTRACT = """\
# The knowledge base's contract.
bundle_path: "source"
git_host: "github"
default_branch: "main"
branch_prefix: "kb/"
ship: "pr"

review:
  who_merges: "A maintainer other than the editor"
  default_reviewers: []
  setup_guide: null

editable:
  - "source/**"
refuse:
  - ".agents/**"
generated_artifacts: []

topic_routing:
  "reference": "source/reference"

taxonomy_path: null

frontmatter:
  required:
    - "type"
  house:
    - "title"
    - "timestamp"
  date_field: "timestamp"
  reserved_files:
    - "index.md"
    - "log.md"

confidentiality:   # who may read what
  forbidden_words_source: null
  hook_path: null
  visible_to: "Everyone in the organization"

notes: >
  Kept as written.
"""


def block_repo(tmp_path: Path, contract: str = BLOCK_CONTRACT) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / "source" / "reference").mkdir(parents=True)
    (repo / ".agents" / "knowledge-base.yaml").write_text(contract, encoding="utf-8")
    return repo


def adopt(repo: Path):
    done = subprocess.run([sys.executable, str(MODULE_PATH), "adopt-sharing-policy", str(repo)],
                          capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def test_adopting_writes_the_template_and_adds_the_two_keys_keeping_every_line(tmp_path: Path) -> None:
    repo = block_repo(tmp_path)
    code, out = adopt(repo)
    assert code == 0, out
    assert (repo / ".agents" / "sharing-policy.md").read_text(encoding="utf-8") == TEMPLATE.read_text(encoding="utf-8")
    lines, before = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8").splitlines(), BLOCK_CONTRACT.splitlines()
    assert [line for line in lines if line not in before] == ['  sharing_policy: ".agents/sharing-policy.md"',
                                                              "  backstop_phrases: []"]
    assert [line for line in lines if line in before] == before  # every line kept, comments included, in order
    _, config = MODULE.load_config(repo, None)
    assert MODULE.validate_config(config) == [] and MODULE.check_paths(repo.resolve(), config) == []
    assert config["confidentiality"]["sharing_policy"] == ".agents/sharing-policy.md"
    assert config["confidentiality"]["backstop_phrases"] == []
    assert "confidentiality.backstop_phrases" in out  # the next step: the scan refuses to run until a phrase is named


def test_adopting_never_writes_over_a_policy_that_exists_and_a_second_run_changes_nothing(tmp_path: Path) -> None:
    repo = block_repo(tmp_path)
    (repo / ".agents" / "sharing-policy.md").write_text("# Our policy, as we wrote it\n", encoding="utf-8")
    assert adopt(repo)[0] == 0
    assert (repo / ".agents" / "sharing-policy.md").read_text(encoding="utf-8") == "# Our policy, as we wrote it\n"
    contract = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8")
    code, out = adopt(repo)
    assert code == 0 and "kept as it is" in out
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == contract


def test_adopting_writes_where_the_contract_says_and_adds_only_the_key_it_lacks(tmp_path: Path) -> None:
    contract = BLOCK_CONTRACT.replace('  visible_to: "Everyone in the organization"\n',
                                      '  visible_to: "Everyone in the organization"\n'
                                      '  sharing_policy: "source/reference/sharing.md"\n')
    repo = block_repo(tmp_path, contract)
    assert adopt(repo)[0] == 0
    assert (repo / "source" / "reference" / "sharing.md").read_text(encoding="utf-8") == TEMPLATE.read_text(encoding="utf-8")
    assert not (repo / ".agents" / "sharing-policy.md").exists()
    lines = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line not in contract.splitlines()] == ["  backstop_phrases: []"]


def test_adopting_refuses_a_contract_it_cannot_safely_change_and_writes_nothing(tmp_path: Path) -> None:
    for number, (contract, said) in enumerate(((BLOCK_CONTRACT.replace("notes: >", "note: >"), "unknown key"),
                                               (json.dumps(valid_config()), "by hand"))):  # a flow mapping
        repo = block_repo(tmp_path / str(number), contract)
        code, out = adopt(repo)
        assert code == 1 and said in out, out
        assert not (repo / ".agents" / "sharing-policy.md").exists()
        assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == contract
    bare = tmp_path / "bare"
    (bare / ".git").mkdir(parents=True)
    assert adopt(bare)[0] == 2  # no contract at all


def test_the_template_carries_the_standards_classes_figures_and_test_word_for_word() -> None:
    """The template is copied into an organization's repository and must stand alone, so it repeats the standard's
    defaults; this keeps the two copies from drifting apart."""
    standard = (MODULE_PATH.parents[1] / "references" / "sharing-standard.md").read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    rows = [line for line in standard.splitlines() if line.startswith("| ")]
    assert len(rows) == 16 and [row for row in rows if row not in template.splitlines()] == []
    question = ("Could this fact cause real harm if it left the organization: to a person's privacy, a customer, a "
                "contract or a negotiation, a legal position, the organization's own protected work, or a decision not "
                "yet announced?")
    assert question in " ".join(standard.split()) and question in " ".join(template.split())

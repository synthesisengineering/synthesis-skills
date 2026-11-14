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
    """The organization's own phrases (the plugin ships none) are a list of phrases, and a named policy's file must be
    there. With no policy named, an empty list holds nothing."""
    config = valid_config()
    config["confidentiality"].update(sharing_policy=".agents/sharing-policy.md", backstop_phrases=["zephyr ledger", "opal"])
    assert MODULE.validate_config(config) == []
    repo = write_repo(tmp_path, config)
    assert any(error.startswith("confidentiality.sharing_policy: configured file does not exist")
               for error in MODULE.check_paths(repo.resolve(), config))
    (repo / ".agents" / "sharing-policy.md").write_text("# Sharing policy\n", encoding="utf-8")
    assert MODULE.check_paths(repo.resolve(), config) == []
    del config["confidentiality"]["sharing_policy"]
    config["confidentiality"]["backstop_phrases"] = []
    assert MODULE.validate_config(config) == []
    for broken in ({"sharing_policy": "../outside.md"}, {"sharing_policy": "/srv/policy.md"},
                   {"backstop_phrases": "zephyr ledger"}, {"backstop_phrases": ["zephyr ledger", " "]},
                   {"backstop_phrases": {"add": ["zephyr ledger"]}}, {"backstop_phrases": None}):
        changed = valid_config()
        changed["confidentiality"].update(broken)
        field = next(iter(broken))
        assert any(error.startswith(f"confidentiality.{field}: ") for error in MODULE.validate_config(changed)), broken


def test_a_contract_that_names_a_policy_with_no_phrases_is_held_and_says_how_to_fix_it() -> None:
    """A named policy runs the phrase scan on every edit, and the scan refuses to run without phrases, so such a contract
    fails the configuration gate at once, naming both ways out, instead of when an edit is ready to ship."""
    for listed in (True, False):  # an empty list, and no list at all
        config = valid_config()
        config["confidentiality"]["sharing_policy"] = ".agents/sharing-policy.md"
        if listed:
            config["confidentiality"]["backstop_phrases"] = []
        held = [error for error in MODULE.validate_config(config) if error.startswith("confidentiality.backstop_phrases: ")]
        assert len(held) == 1 and "every edit is held" in held[0], held
        assert "list at least one" in held[0] and "remove confidentiality.sharing_policy" in held[0]


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


def filled(repo: Path, relative: str = ".agents/sharing-policy.md") -> str:
    """The template with its audience parts filled in, as an organization leaves it before adopting."""
    text = TEMPLATE.read_text(encoding="utf-8").replace("**Yours:** who they are.", "Everyone in the organization.")
    text = text.replace("**Yours:** who they are, and what the copy is", "Our assistant's users; the copy is")
    (repo / relative).parent.mkdir(parents=True, exist_ok=True)
    (repo / relative).write_text(text, encoding="utf-8")
    return text


def adopt(repo: Path, *phrases: str):
    done = subprocess.run([sys.executable, str(MODULE_PATH), "adopt-sharing-policy", str(repo),
                           *(part for phrase in phrases for part in ("--phrase", phrase))], capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def test_adopting_names_the_policy_with_the_phrases_given_keeping_every_line(tmp_path: Path) -> None:
    repo = block_repo(tmp_path)
    policy = filled(repo)
    code, out = adopt(repo, "zephyr ledger", "opal")
    assert code == 0, out
    assert (repo / ".agents" / "sharing-policy.md").read_text(encoding="utf-8") == policy
    lines, before = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8").splitlines(), BLOCK_CONTRACT.splitlines()
    assert [line for line in lines if line not in before] == ['  sharing_policy: ".agents/sharing-policy.md"',
                                                              "  backstop_phrases:", '    - "zephyr ledger"', '    - "opal"']
    assert [line for line in lines if line in before] == before  # every line kept, comments included, in order
    _, config = MODULE.load_config(repo, None)
    assert MODULE.validate_config(config) == [] and MODULE.check_paths(repo.resolve(), config) == []
    assert config["confidentiality"]["sharing_policy"] == ".agents/sharing-policy.md"
    assert config["confidentiality"]["backstop_phrases"] == ["zephyr ledger", "opal"]


def test_adopting_with_no_phrases_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """A policy named with no phrases would hold every edit, so adopting takes the phrases in the same step."""
    repo = block_repo(tmp_path)
    code, out = adopt(repo)
    assert code == 1 and "--phrase" in out, out
    assert not (repo / ".agents" / "sharing-policy.md").exists()
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == BLOCK_CONTRACT


def test_adopting_never_writes_over_a_policy_that_exists_and_a_second_run_changes_nothing(tmp_path: Path) -> None:
    repo = block_repo(tmp_path)
    (repo / ".agents" / "sharing-policy.md").write_text("# Our policy, as we wrote it\n", encoding="utf-8")
    assert adopt(repo, "zephyr ledger")[0] == 0
    assert (repo / ".agents" / "sharing-policy.md").read_text(encoding="utf-8") == "# Our policy, as we wrote it\n"
    contract = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8")
    code, out = adopt(repo)
    assert code == 0 and "kept as it is" in out
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == contract
    code, out = adopt(repo, "violet harbor")  # a list that exists is changed in the contract, not by adopting again
    assert code == 1 and "lists phrases already" in out, out
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == contract


def test_adopting_writes_where_the_contract_says_and_adds_only_what_it_lacks(tmp_path: Path) -> None:
    contract = BLOCK_CONTRACT.replace('  visible_to: "Everyone in the organization"\n',
                                      '  visible_to: "Everyone in the organization"\n'
                                      '  sharing_policy: "source/reference/sharing.md"\n')
    repo = block_repo(tmp_path, contract)
    code, out = adopt(repo, "violet harbor")  # the template first, where the contract says
    assert code == 1 and "fill in" in out, out
    assert (repo / "source" / "reference" / "sharing.md").read_text(encoding="utf-8") == TEMPLATE.read_text(encoding="utf-8")
    assert not (repo / ".agents" / "sharing-policy.md").exists()
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == contract
    filled(repo, "source/reference/sharing.md")
    code, out = adopt(repo, "violet harbor")
    assert code == 0, out
    lines = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line not in contract.splitlines()] == ["  backstop_phrases:", '    - "violet harbor"']


def test_adopting_refuses_a_contract_it_cannot_safely_change_and_writes_nothing(tmp_path: Path) -> None:
    for number, (contract, said) in enumerate(((BLOCK_CONTRACT.replace("notes: >", "note: >"), "unknown key"),
                                               (json.dumps(valid_config()), "by hand"))):  # a flow mapping
        repo = block_repo(tmp_path / str(number), contract)
        code, out = adopt(repo, "zephyr ledger")
        assert code == 1 and said in out, out
        assert not (repo / ".agents" / "sharing-policy.md").exists()
        assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == contract
    bare = tmp_path / "bare"
    (bare / ".git").mkdir(parents=True)
    assert adopt(bare, "zephyr ledger")[0] == 2  # no contract at all


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


# ---- review round 1: the contract's gate and adoption -----------------------------------------------------------

def test_the_gate_reads_letter_case_as_git_does(tmp_path: Path) -> None:
    """R1-1: a Mac's disk finds `Source` for `source`; git does not, and the scan reads nothing there."""
    config = valid_config()
    config["bundle_path"] = "Source"
    repo = write_repo(tmp_path, config)
    errors = MODULE.check_paths(repo.resolve(), config)
    assert any(error.startswith("bundle_path: ") for error in errors), errors


def test_an_unknown_key_says_how_to_fix_it() -> None:
    """R1-17: a contract valid under 5.21.0 stops at the gate under 5.22.0, so the error names the way out."""
    config = valid_config()
    config["confidentiality"]["sharing_polcy"] = ".agents/sharing-policy.md"
    config["version"] = 1
    errors = MODULE.validate_config(config)
    assert any(error.startswith("confidentiality.sharing_polcy: unknown key") and "did you mean sharing_policy" in error
               for error in errors), errors
    assert any(error.startswith("version: unknown key") and "move it into notes" in error for error in errors), errors


def test_adopting_replaces_a_null_policy_or_an_empty_list_in_place(tmp_path: Path) -> None:
    """R1-14: the documented schema allows both; a second key of the same name is a duplicate key."""
    for number, line in enumerate(("  sharing_policy: null", "  backstop_phrases: []")):
        contract = BLOCK_CONTRACT.replace('  visible_to: "Everyone in the organization"\n',
                                          f'  visible_to: "Everyone in the organization"\n{line}\n')
        repo = block_repo(tmp_path / str(number), contract)
        filled(repo)
        code, out = adopt(repo, "zephyr ledger")
        assert code == 0, out
        lines = (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8").splitlines()
        assert line not in lines and sum(entry.strip().startswith(line.strip().split(":")[0] + ":") for entry in lines) == 1
        _, config = MODULE.load_config(repo, None)
        assert MODULE.validate_config(config) == [] and config["confidentiality"]["backstop_phrases"] == ["zephyr ledger"]


def test_adopting_a_crlf_contract_keeps_its_line_endings(tmp_path: Path) -> None:
    """R1-15: "keeping every line" holds for the bytes too, so the review shows only the lines added."""
    contract = BLOCK_CONTRACT.replace("\n", "\r\n")
    repo = block_repo(tmp_path)
    (repo / ".agents" / "knowledge-base.yaml").write_bytes(contract.encode("utf-8"))
    filled(repo)
    assert adopt(repo, "zephyr ledger")[0] == 0
    data = (repo / ".agents" / "knowledge-base.yaml").read_bytes()
    assert data.count(b"\r\n") == data.count(b"\n") == contract.count("\n") + 3, data[:200]


def test_adopting_over_a_folder_at_the_policys_path_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """R1-16: a folder exists, but it is no policy, and naming it would hold every edit."""
    repo = block_repo(tmp_path)
    (repo / ".agents" / "sharing-policy.md").mkdir()
    code, out = adopt(repo, "zephyr ledger")
    assert code == 1 and "not a file" in out, out
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == BLOCK_CONTRACT


def test_adopting_writes_the_template_first_and_names_it_once_it_says_who_reads_it(tmp_path: Path) -> None:
    """R1-18: naming the policy switches knowledge capture to sharing by default, so a policy that names no audience
    is never named; adoption writes the template, and names it on a later run, once its audiences are filled in."""
    repo = block_repo(tmp_path)
    code, out = adopt(repo, "zephyr ledger")
    assert code == 1 and "fill in" in out, out
    assert (repo / ".agents" / "sharing-policy.md").read_text(encoding="utf-8") == TEMPLATE.read_text(encoding="utf-8")
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == BLOCK_CONTRACT
    code, out = adopt(repo, "zephyr ledger")  # still the template as written
    assert code == 1 and "who reads it" in out, out
    assert (repo / ".agents" / "knowledge-base.yaml").read_text(encoding="utf-8") == BLOCK_CONTRACT
    filled(repo)
    code, out = adopt(repo, "zephyr ledger")
    assert code == 0, out
    assert MODULE.load_config(repo, None)[1]["confidentiality"]["sharing_policy"] == ".agents/sharing-policy.md"


def test_the_gate_refuses_a_named_policy_still_the_template_as_written(tmp_path: Path) -> None:
    config = valid_config()
    config["confidentiality"].update(sharing_policy=".agents/sharing-policy.md", backstop_phrases=["zephyr ledger"])
    repo = write_repo(tmp_path, config)
    (repo / ".agents" / "sharing-policy.md").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    errors = MODULE.check_paths(repo.resolve(), config)
    assert any(error.startswith("confidentiality.sharing_policy: ") and "fill in who reads it" in error
               for error in errors), errors
    filled(repo)
    assert MODULE.check_paths(repo.resolve(), config) == []


def test_the_templates_examples_ask_for_the_shape_of_what_stayed_out_never_the_fact() -> None:
    """R1-27: the policy file is read by everyone with access to the repository."""
    text = " ".join(TEMPLATE.read_text(encoding="utf-8").split())
    assert "never the fact itself" in text and "by its class and shape" in text

"""Regressions for the Google Chat preflight.

Derived from a real miss: on 2026-09-01 a surface-level watermark on the
gchat surface recorded coverage no per-space read backed, and a colleague's
four DMs went unsurfaced through two syncs and a day-end. The enumeration
behind this surface returns text, ignores its own type filter, pages at 100
with no cursor, orders undocumented, and labels every DM "Unnamed Space" —
so the declared set is an explicit, labeled config core plus a client-side
filtered, explicitly bounded enumeration, and the gate names the bound.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gchat_preflight.py"
SPEC = importlib.util.spec_from_file_location("gchat_preflight", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SKILLS_ROOT = Path(__file__).resolve().parents[2]
WATERMARK = Path(__file__).resolve().parents[1] / "scripts" / "sync_watermark.py"

CONFIG = """
workspace: example-workspace
scope:
  direct_messages: all
  group_chats: all
  named_spaces: all
  meeting_chat_spaces: all
targets:
  - space: spaces/AAAAdm000001
    label: Jane Doe (DM)
    type: DIRECT_MESSAGE
  - space: spaces/AAAAgrp00001
    label: Project Alpha (group)
    type: GROUP_CHAT
"""

ENUMERATION = """Found 4 Chat spaces (type: DIRECT_MESSAGE):
- Unnamed Space (ID: spaces/AAAAdm000001, Type: DIRECT_MESSAGE)
- Unnamed Space (ID: spaces/AAAAdm000002, Type: DIRECT_MESSAGE)
- Engineering (ID: spaces/AAAAsp000001, Type: SPACE)
- Project Alpha (ID: spaces/AAAAgrp00001, Type: GROUP_CHAT)
"""


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True)


# --- the config core is explicit and labeled ----------------------------------------------------


def test_config_targets_are_the_labeled_core(tmp_path: Path) -> None:
    core = MODULE.config_targets(MODULE._load_yaml(write(tmp_path, "c.yaml", CONFIG)))

    assert [(t.space, t.label, t.kind) for t in core] == [
        ("spaces/AAAAdm000001", "Jane Doe (DM)", "DIRECT_MESSAGE"),
        ("spaces/AAAAgrp00001", "Project Alpha (group)", "GROUP_CHAT"),
    ]


def test_a_person_id_is_never_a_read_target(tmp_path: Path) -> None:
    config = CONFIG.replace("space: spaces/AAAAgrp00001", "space: users/107000000000000000000")
    core = MODULE.config_targets(MODULE._load_yaml(write(tmp_path, "c.yaml", config)))

    bad = core[1]
    assert bad.resolved is False
    assert "is a person" in bad.reason
    assert "users/" not in json.dumps(MODULE.declared_set(core))


# --- the enumeration is parsed as text, filtered client-side, and bounded honestly ---------------


def test_enumeration_is_parsed_from_the_wrappers_text() -> None:
    records, claimed = MODULE.parse_enumeration(ENUMERATION)

    assert claimed == 4
    assert [(t.space, t.label, t.kind) for t in records][:2] == [
        ("spaces/AAAAdm000001", "Unnamed Space", "DIRECT_MESSAGE"),
        ("spaces/AAAAdm000002", "Unnamed Space", "DIRECT_MESSAGE"),
    ]


def test_the_wrappers_type_filter_is_not_trusted_scope_filters_client_side(tmp_path: Path) -> None:
    """The header says DIRECT_MESSAGE while the body mixes SPACE and GROUP_CHAT
    records; the config's scope decides, not the header."""
    config = CONFIG.replace("named_spaces: all", "named_spaces: none")
    cfg = MODULE._load_yaml(write(tmp_path, "c.yaml", config))
    records, _ = MODULE.parse_enumeration(ENUMERATION)

    kept = [t for t in records if MODULE.in_scope(t.kind, cfg["scope"])]

    assert [t.space for t in kept] == ["spaces/AAAAdm000001", "spaces/AAAAdm000002", "spaces/AAAAgrp00001"]


def test_short_page_and_page_cap_mark_the_set_bounded() -> None:
    records, claimed = MODULE.parse_enumeration(ENUMERATION.replace("Found 4", "Found 443"))
    assert "443" in MODULE.bound(records, claimed)

    capped = "Found 443 Chat spaces (type: SPACE):\n" + "".join(
        f"- Space {i} (ID: spaces/AAAAcap{i:05d}, Type: SPACE)\n" for i in range(MODULE.PAGE_CAP)
    )
    records, claimed = MODULE.parse_enumeration(capped)
    assert "full page" in MODULE.bound(records, claimed)

    records, claimed = MODULE.parse_enumeration(ENUMERATION)
    assert MODULE.bound(records, claimed) is None


def test_a_page_shorter_than_the_requested_size_is_complete() -> None:
    """2026-10-06: page_size 1000 returned 546 records with a header of 546, and the fixed cap of 100 called it
    bounded; page_size 500 returning exactly 500 is the truncated case."""
    page = lambda n: f"Found {n} Chat spaces (type: SPACE):\n" + "".join(  # noqa: E731
        f"- Space {i} (ID: spaces/AAAAcap{i:05d}, Type: SPACE)\n" for i in range(n))
    records, claimed = MODULE.parse_enumeration(page(546))
    assert MODULE.bound(records, claimed, page_size=1000) is None
    records, claimed = MODULE.parse_enumeration(page(500))
    assert "full page" in MODULE.bound(records, claimed, page_size=500)


def test_merge_keeps_config_labels_and_adds_enumerated_spaces(tmp_path: Path) -> None:
    core = MODULE.config_targets(MODULE._load_yaml(write(tmp_path, "c.yaml", CONFIG)))
    records, _ = MODULE.parse_enumeration(ENUMERATION)

    merged = MODULE.merge(core, records)

    assert [t.space for t in merged] == [
        "spaces/AAAAdm000001", "spaces/AAAAgrp00001", "spaces/AAAAdm000002", "spaces/AAAAsp000001",
    ]
    assert merged[0].label == "Jane Doe (DM)"  # the config label wins over "Unnamed Space"
    assert MODULE.census(merged) == "census: 2 DIRECT_MESSAGE / 1 GROUP_CHAT / 1 SPACE / 0 unresolved"


# --- the CLI feeds the gate and fails closed ----------------------------------------------------


def test_cli_writes_the_declared_set_the_gate_consumes(tmp_path: Path) -> None:
    out = tmp_path / "declared.json"
    done = run_cli("--config", str(write(tmp_path, "c.yaml", CONFIG)),
                   "--spaces", str(write(tmp_path, "spaces.txt", ENUMERATION)), "--out", str(out))

    assert done.returncode == 0, done.stderr
    assert "census: 2 DIRECT_MESSAGE / 1 GROUP_CHAT / 1 SPACE / 0 unresolved" in done.stdout
    assert "enumeration: complete" in done.stdout
    declared = json.loads(out.read_text(encoding="utf-8"))
    assert declared == {"gchat": ["spaces/AAAAdm000001", "spaces/AAAAgrp00001",
                                  "spaces/AAAAdm000002", "spaces/AAAAsp000001"]}
    spec = importlib.util.spec_from_file_location("sync_watermark", WATERMARK)
    watermark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watermark)
    assert watermark.parse_targets([], str(out)) == declared


def test_cli_exits_one_and_names_the_bound_when_the_enumeration_is_capped(tmp_path: Path) -> None:
    done = run_cli("--config", str(write(tmp_path, "c.yaml", CONFIG)),
                   "--spaces", str(write(tmp_path, "spaces.txt", ENUMERATION.replace("Found 4", "Found 443"))))

    assert done.returncode == 1
    assert "BOUNDED" in done.stdout
    assert "443" in done.stderr


def test_cli_without_an_enumeration_is_the_config_core_only_and_partial(tmp_path: Path) -> None:
    done = run_cli("--config", str(write(tmp_path, "c.yaml", CONFIG)), "--json")

    assert done.returncode == 1
    payload = json.loads(done.stdout)
    assert payload["declared"] == {"gchat": ["spaces/AAAAdm000001", "spaces/AAAAgrp00001"]}
    assert payload["enumeration"].startswith("enumeration: none supplied") and payload["bound"] is None
    assert "config core only" in done.stderr


TABLE = """# Google Chat preflight — workspace example-workspace

| type | space | label | source | status |
|---|---|---|---|---|
| DIRECT_MESSAGE | spaces/AAAAdm000001 | Jane Doe (DM) | config | resolved |
| GROUP_CHAT | — | Project Alpha (group) | config | UNRESOLVED — users/107000000000000000000 is a person, not a space |
| DIRECT_MESSAGE | spaces/AAAAdm000002 | Unnamed Space | enumeration | resolved |
| SPACE | spaces/AAAAsp000001 | Engineering | enumeration | resolved |
| GROUP_CHAT | spaces/AAAAgrp00001 | Project Alpha | enumeration | resolved |

census: 2 DIRECT_MESSAGE / 1 GROUP_CHAT / 1 SPACE / 1 unresolved
enumeration: complete (header count matches the records parsed, below the page cap)
"""


def test_json_carries_the_census_and_enumeration_lines_the_table_prints(tmp_path: Path) -> None:
    """2026-10-07: --json printed only the declared set, so a ritual told to quote the census and the
    enumeration line had to rerun table mode on the same inputs. Both modes now carry the same lines."""
    config = str(write(tmp_path, "c.yaml", CONFIG.replace("space: spaces/AAAAgrp00001", "space: users/107000000000000000000")))
    complete = str(write(tmp_path, "complete.txt", ENUMERATION))
    bounded = str(write(tmp_path, "bounded.txt", ENUMERATION.replace("Found 4", "Found 443")))
    assert run_cli("--config", config, "--spaces", complete).stdout == TABLE  # table mode as it always printed
    for spaces, opening in ((complete, "enumeration: complete ("), (bounded, "BOUNDED: header claimed 443"),
                            (None, "enumeration: none supplied")):
        argv = ["--config", config, *(["--spaces", spaces] if spaces else [])]
        table, out = run_cli(*argv), tmp_path / "declared.json"
        done = run_cli(*argv, "--json", "--out", str(out))
        payload = json.loads(done.stdout)
        assert done.returncode == table.returncode == 1  # the person id stays unresolved
        assert table.stdout.splitlines()[-2:] == [payload["census"], payload["enumeration"]]
        assert payload["census"].endswith("/ 1 unresolved") and payload["enumeration"].startswith(opening)
        assert (payload["bound"] is not None) == (spaces == bounded)
        rows = [f"| {r['type']} | {r['space'] or '—'} | {r['label']} | {r['source']} | {r['status']} |"
                for r in payload["targets"]]
        assert rows == [line for line in table.stdout.splitlines()[4:] if line.startswith("| ")]
        assert payload["declared"] == json.loads(out.read_text(encoding="utf-8"))
        assert "users/" not in json.dumps(payload["declared"])


def test_cli_refuses_an_empty_set_and_a_malformed_config(tmp_path: Path) -> None:
    empty = run_cli("--config", str(write(tmp_path, "e.yaml", "workspace: w\nscope: {}\n")))
    assert empty.returncode == 2
    assert "refused" in empty.stderr

    malformed = run_cli("--config", str(write(tmp_path, "m.yaml", "targets:\n  - just-a-string\n")))
    assert malformed.returncode == 2
    assert "must be a mapping" in malformed.stderr


# --- the documented rules the mechanism depends on ----------------------------------------------


def test_rituals_run_the_gchat_preflight_per_target() -> None:
    text = skill_prose(SKILLS_ROOT / "synthesis-daily-rituals")
    assert "gchat_preflight.py --config" in text
    assert "advance --surface gchat --target" in text
    assert "surface-level advance is refused" in text


def test_reference_documents_gchat_targets_and_the_refusal() -> None:
    text = (SKILLS_ROOT / "synthesis-daily-rituals" / "references" / "sync-watermarks.md").read_text(encoding="utf-8")
    assert "## Google Chat targets" in text
    assert "--surface-level" in text


def skill_prose(folder: Path) -> str:
    """SKILL.md and the living references (v5 moved the checklists out of SKILL.md)."""
    files = [folder / "SKILL.md", *sorted((folder / "references").glob("*.md"))]
    return "\n".join(f.read_text(encoding="utf-8") for f in files
                     if not f.name.startswith(("preserved", "version-history", "coverage-map")))

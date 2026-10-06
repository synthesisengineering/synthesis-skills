"""R5.3 exact-id carry-forward: when a packet is replaced, every unanswered decision carries
forward by its exact id, a reconciliation with missing, extra or duplicate ids is refused,
and an item called answered closes only with a ruling recorded against the exact spec.
Ported from the succession checks of the context-lifecycle skill.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_packet as bp  # noqa: E402
import carry_forward as cf  # noqa: E402
import record_rulings as rr  # noqa: E402


def spec(n=6):
    return {
        "title": "Synthetic backlog pass", "audience": "Fixture principal",
        "options": [{"value": "build", "label": "Build it this month"},
                    {"value": "drop", "label": "Drop it from the backlog"}],
        "rows": [{"id": f"B-{i}", "label": f"Synthetic idea {i}", "context": f"Fixture idea {i}.",
                  "impact": {"accept": "It gets built.", "decline": "It leaves the backlog."},
                  "recommendation": "build"} for i in range(1, n + 1)],
    }


@pytest.fixture
def packet(tmp_path):
    """A filed packet whose principal answered B-1 and B-2 (B-2 with a note) and left the rest."""
    artifacts = tmp_path / "resources" / "artifacts"
    artifacts.mkdir(parents=True)
    current = spec()
    spec_path, _ = bp.file_packet(current, bp.build(current), artifacts, "2026-09-20")
    paste = rr.compose_summary(current, {"B-1": {"choice": "build"}, "B-2": {"choice": "drop", "note": "Not now."}})
    (tmp_path / "paste.txt").write_text(paste, encoding="utf-8")
    recorded = subprocess.run([sys.executable, str(SCRIPTS / "record_rulings.py"), str(tmp_path / "paste.txt"),
                               "--spec", str(spec_path), "--file-into", str(artifacts), "--date", "2026-09-21"],
                              capture_output=True, text=True)
    assert recorded.returncode == 0, recorded.stderr
    return current, spec_path, artifacts / "2026-09-21-synthetic-backlog-pass-rulings.json"


def carry(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "carry_forward.py"), *map(str, args)],
                          capture_output=True, text=True)


def reconcile(tmp_path, items):
    path = tmp_path / "reconciliation.json"
    path.write_text(json.dumps({"items": items}), encoding="utf-8")
    return path


def full(rulings_name, to="next-spec.json"):
    return ([{"id": "B-1", "status": "answered", "ruling": rulings_name},
             {"id": "B-2", "status": "answered", "ruling": rulings_name}]
            + [{"id": f"B-{i}", "status": "carried", "to": to} for i in range(3, 7)])


def test_r53_successor_holds_exactly_the_unanswered_rows_with_ids_unchanged(packet, tmp_path):
    current, spec_path, _ = packet
    out = tmp_path / "next-spec.json"
    result = carry(spec_path, "--successor", out, "--title", "Synthetic backlog pass, continued")
    assert result.returncode == 0, result.stderr
    assert "carried 4 of 6 decisions forward by exact id: B-3, B-4, B-5, B-6" in result.stdout
    nxt = json.loads(out.read_text(encoding="utf-8"))
    assert nxt["rows"] == current["rows"][2:]
    assert nxt["carried_from"] == spec_path.name and nxt["title"] == "Synthetic backlog pass, continued"
    assert nxt["options"] == current["options"]
    built = subprocess.run([sys.executable, str(SCRIPTS / "build_packet.py"), str(out), "--strict-reader",
                            "--allow-small", "--file-into", str(spec_path.parent), "--date", "2026-09-22"],
                           capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    assert (spec_path.parent / "2026-09-22-synthetic-backlog-pass-continued-spec.json").is_file()
    again = carry(spec_path, "--successor", out)
    assert again.returncode == 2 and out.read_text(encoding="utf-8") == json.dumps(nxt, indent=2,
                                                                                    ensure_ascii=False) + "\n"


def test_r53_a_packet_with_every_decision_recorded_carries_nothing(tmp_path):
    artifacts = tmp_path / "a"
    artifacts.mkdir()
    current = spec(n=5)
    spec_path, _ = bp.file_packet(current, bp.build(current), artifacts, "2026-09-20")
    record = rr.parse_summary(rr.compose_summary(current, {r["id"]: {"choice": "drop"} for r in current["rows"]}),
                              current)
    (artifacts / "2026-09-20-x-rulings.json").write_text(json.dumps(record), encoding="utf-8")
    result = carry(spec_path, "--successor", tmp_path / "next.json")
    assert result.returncode == 0 and "nothing to carry forward" in result.stdout
    assert not (tmp_path / "next.json").exists()


@pytest.mark.parametrize("damage, expected", [
    (lambda items: items.pop(), "missing ids: 'B-6'"),
    (lambda items: items.append({"id": "B-9", "status": "carried", "to": "elsewhere"}), "extra ids: 'B-9'"),
    (lambda items: items.append(dict(items[3])), "duplicate ids: 'B-4'"),
    (lambda items: items[3].update(status="done"), "use 'answered' or 'carried'"),
    (lambda items: items[3].pop("to"), "no destination is named"),
])
def test_r53_a_reconciliation_with_missing_extra_or_duplicate_ids_is_refused(packet, tmp_path, damage, expected):
    _, spec_path, rulings = packet
    items = full(rulings.name, to="CONTEXT.md open decisions")
    assert carry(spec_path, "--check", reconcile(tmp_path, items)).returncode == 0
    damage(items)
    result = carry(spec_path, "--check", reconcile(tmp_path, items))
    assert result.returncode == 2 and expected in result.stderr, result.stderr


def test_r53_a_narrative_answer_without_a_recorded_ruling_is_refused(packet, tmp_path):
    """Meeting notes or a chat message calling an item answered close nothing."""
    _, spec_path, rulings = packet
    narrative = spec_path.parent / "answers.md"
    narrative.write_text("# Notes\n\nB-3: the principal said build it.\n", encoding="utf-8")
    items = full(rulings.name, to="CONTEXT.md open decisions")
    items[2] = {"id": "B-3", "status": "answered", "ruling": narrative.name}
    result = carry(spec_path, "--check", reconcile(tmp_path, items))
    assert result.returncode == 2 and "'B-3' is called answered, but answers.md is not a ruling" in result.stderr
    items[2] = {"id": "B-3", "status": "answered", "ruling": rulings.name}  # recorded, but B-3 undecided
    result = carry(spec_path, "--check", reconcile(tmp_path, items))
    assert result.returncode == 2 and "records no choice for it; carry it forward" in result.stderr
    items[2] = {"id": "B-3", "status": "answered"}
    result = carry(spec_path, "--check", reconcile(tmp_path, items))
    assert result.returncode == 2 and "without the rulings file" in result.stderr


def test_r53_a_ruling_recorded_against_another_spec_version_answers_nothing(packet, tmp_path):
    current, spec_path, rulings = packet
    revised = copy.deepcopy(current)
    revised["options"][0]["consequence"] = "A different meaning."
    revised_spec, _ = bp.file_packet(revised, bp.build(revised), spec_path.parent, "2026-09-23")
    assert cf.answered(revised, revised_spec, None) == {}  # the old rulings bind the old spec
    with pytest.raises(cf.CarryError, match="not a ruling recorded against this exact spec"):
        cf.recorded_choices(revised, rulings)
    result = carry(revised_spec, "--rulings", rulings, "--successor", tmp_path / "n.json")
    assert result.returncode == 2 and not (tmp_path / "n.json").exists()


def test_r53_a_tampered_ruling_is_refused(packet):
    current, _, rulings = packet
    data = json.loads(rulings.read_text(encoding="utf-8"))
    data["rulings"][3]["choice_value"] = "build"  # a choice the paste never carried
    rulings.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(cf.CarryError, match="does not match"):
        cf.recorded_choices(current, rulings)


def test_r53_carried_ids_must_arrive_in_a_successor_spec_destination(packet, tmp_path):
    _, spec_path, rulings = packet
    out = spec_path.parent / "next-spec.json"
    assert carry(spec_path, "--successor", out).returncode == 0
    ok = carry(spec_path, "--check", reconcile(tmp_path, full(rulings.name, to=out.name)))
    assert ok.returncode == 0, ok.stderr
    assert "reconciled 6 ids: 2 answered with recorded rulings, 4 carried forward" in ok.stdout
    nxt = json.loads(out.read_text(encoding="utf-8"))
    nxt["rows"] = nxt["rows"][1:]
    out.write_text(json.dumps(nxt), encoding="utf-8")
    lost = carry(spec_path, "--check", reconcile(tmp_path, full(rulings.name, to=out.name)))
    assert lost.returncode == 2 and "'B-3' is carried to next-spec.json, which holds no row" in lost.stderr


def test_r53_rulings_filed_before_note_whitespace_normalization_still_count(packet):
    current, _, rulings = packet
    data = json.loads(rulings.read_text(encoding="utf-8"))
    data["rulings"][1]["note"] = "Not now.  "
    rulings.write_text(json.dumps(data), encoding="utf-8")
    assert cf.recorded_choices(current, rulings) == {"B-1": "build", "B-2": "drop"}

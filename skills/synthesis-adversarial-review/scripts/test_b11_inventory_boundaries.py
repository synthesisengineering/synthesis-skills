"""Independent source-contract closure controls: unchanged after initial red."""

from pathlib import Path
import hashlib
import os
import sys
import pytest

PUBLIC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PUBLIC / "skills/synthesis-adversarial-review/scripts"))
import review_contract as rc  # noqa: E402 - exact source owner bound above


def make(root):
    rows = []
    for name in ("a.py", "b.py"):
        p = root / name
        p.write_text("# retained synthetic instrument\n")
        rows.append(
            {
                "path": name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "role": "fixture",
                "terminal": "not-run",
            }
        )
    return rows


def test_inventory_closed_positive(tmp_path):
    rows = make(tmp_path)
    assert len(rc.instrument_inventory(tmp_path, rows)) == 2


def test_inventory_added_instrument_during_hash_refuses(tmp_path, monkeypatch):
    rows = make(tmp_path)
    original = rc.read_bytes
    changed = []

    def read(root, path, **kw):
        raw = original(root, path, **kw)
        if not changed:
            (tmp_path / "undeclared.sh").write_text("# synthetic new instrument\n")
            changed.append(True)
        return raw

    monkeypatch.setattr(rc, "read_bytes", read)
    with pytest.raises(rc.ReviewContractError):
        rc.instrument_inventory(tmp_path, rows)
    assert changed


def test_inventory_earlier_source_changed_during_later_read_refuses(
    tmp_path, monkeypatch
):
    rows = make(tmp_path)
    original = rc.read_bytes
    changed = []

    def read(root, path, **kw):
        raw = original(root, path, **kw)
        if path == "b.py" and not changed:
            (tmp_path / "a.py").write_text("# changed after initial source read\n")
            changed.append(True)
        return raw

    monkeypatch.setattr(rc, "read_bytes", read)
    with pytest.raises(rc.ReviewContractError):
        rc.instrument_inventory(tmp_path, rows)
    assert changed


def test_inventory_aggregate_read_budget_is_enforced(tmp_path, monkeypatch):
    rows = make(tmp_path)
    monkeypatch.setattr(rc, "MAX_TOTAL_BYTES", 40)
    with pytest.raises(rc.ReviewContractError, match="budget"):
        rc.instrument_inventory(tmp_path, rows)


def test_inventory_shared_deadline_reaches_hashing(tmp_path, monkeypatch):
    rows = make(tmp_path)
    clock = [0.0]
    original = rc.read_bytes
    monkeypatch.setattr(rc.time, "monotonic", lambda: clock[0])

    def read(root, path, **kw):
        value = original(root, path, **kw)
        clock[0] = rc.MAX_SECONDS + 1
        return value

    monkeypatch.setattr(rc, "read_bytes", read)
    with pytest.raises(rc.ReviewContractError, match="budget"):
        rc.instrument_inventory(tmp_path, rows)


def test_inventory_no_alias_root_and_distinct_regular_files(tmp_path):
    root = tmp_path / "real"
    root.mkdir()
    rows = make(root)
    link = tmp_path / "alias"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(rc.ReviewContractError):
        rc.instrument_inventory(link, rows)
    os.link(root / "a.py", root / "copy.py")
    rows.append(
        {
            "path": "copy.py",
            "sha256": rows[0]["sha256"],
            "role": "fixture",
            "terminal": "not-run",
        }
    )
    with pytest.raises(rc.ReviewContractError):
        rc.instrument_inventory(root, rows)

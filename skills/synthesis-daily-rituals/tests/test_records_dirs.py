"""A deadline that lives only in a draft or a ledger is swept too.

A seat found nine draft files and a ledger that carried their own `**Decays:**` lines; the sweep read only dated
plans and the three ritual artifact names, so each was listed as excluded and never read (2026-11-11). A workspace
can now declare `records_dirs`: folders of other Markdown records whose items the sweep reads. A plan outranks a
record: once a plan or ritual artifact carries an item (the same Decay ID), the plans decide it. Committed before
the code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SWEEP = SCRIPTS / "decay_sweep.py"
AS_OF = "2026-11-11"


def write(folder: Path, name: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(body, encoding="utf-8")
    return path


def sweep(tmp_path: Path, *extra, plans=True):
    plans_dir = tmp_path / "plans"
    if plans and not plans_dir.exists():
        write(plans_dir, "2026-11-10.md", "# Plan\n\n1. **Nothing dated here.**\n")
    proc = subprocess.run([sys.executable, str(SWEEP), "--as-of", AS_OF, "--plans-dir", str(plans_dir), "--records-dir",
                           str(tmp_path / "drafts"), "--json", *extra], capture_output=True, text=True,
                          env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "home")})
    assert proc.stdout, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


def item(title="Reply to the vendor", due="2026-11-05", ident="", extra=""):
    lines = [f"### {title}", f"**Decays:** {due} (their quote expires)"] + ([f"**Decay ID:** {ident}"] if ident else [])
    return "\n".join(lines + ([extra] if extra else [])) + "\n\n"


def test_an_open_item_in_a_draft_is_due_like_any_other(tmp_path):
    draft = write(tmp_path / "drafts", "2026-10-28-reply-to-the-vendor.md", "# Draft\n\n" + item())
    code, got = sweep(tmp_path)
    due = got["due"]
    assert [d["title"] for d in due] == ["Reply to the vendor"] and due[0]["path"] == str(draft) and due[0]["due_date"] == "2026-11-05"
    assert got["status"] == "REVIEW" and str(draft) in got["scanned"] and not got["gaps"]


def test_an_item_closed_where_it_sits_is_not_due(tmp_path):
    write(tmp_path / "drafts", "2026-10-28-reply.md", item(extra="**Sent:** 2026-11-04"))
    _, got = sweep(tmp_path)
    assert got["due"] == [] and got["status"] == "CLEAR"


def test_a_file_with_no_date_in_its_name_is_read_as_of_today(tmp_path):
    ledger = write(tmp_path / "drafts", "_LEDGER.md", "# Ledger\n\n" + item("Send the renewal", "2026-11-09") + item("Later one", "2026-12-01"))
    _, got = sweep(tmp_path)
    assert [d["title"] for d in got["due"]] == ["Send the renewal"] and got["due"][0]["path"] == str(ledger)


def test_a_plan_that_carries_the_item_decides_it(tmp_path):
    """The record still shows it open; the plan closed it. And the other way round."""
    write(tmp_path / "drafts", "2026-10-28-reply.md", item(ident="vendor-reply") + item("Call the landlord", "2026-11-03", "landlord", "**Sent:** 2026-11-02"))
    write(tmp_path / "plans", "2026-11-10.md", "# Plan\n\n" + item(ident="vendor-reply", extra="**Resolved:** 2026-11-09 — sent by hand")
          + item("Call the landlord", "2026-11-08", "landlord"))
    _, got = sweep(tmp_path)
    assert [(d["identity"], d["due_date"]) for d in got["due"]] == [("id:landlord", "2026-11-08")]
    assert got["due"][0]["path"].endswith("2026-11-10.md")


def test_a_critical_item_in_a_record_leads_like_any_critical_item(tmp_path):
    write(tmp_path / "drafts", "2026-11-01-benefits.md", "### Open enrollment closes\n**Critical:** benefits enrollment\n"
          "**Decays:** 2026-11-13 (the window closes)\n**Decay ID:** enroll\n**Calendar:** event 4f2a\n")
    _, got = sweep(tmp_path)
    assert [row["identity"] for row in got["critical"]["open"]] == ["id:enroll"] and got["due"] == []


def test_a_record_dated_after_today_is_not_read_and_an_empty_folder_is_no_gap(tmp_path):
    future = write(tmp_path / "drafts", "2026-11-20-next-week.md", item(due="2026-11-21"))
    _, got = sweep(tmp_path)
    assert got["future_files"] == [str(future)] and got["due"] == [] and not got["gaps"]
    future.unlink()
    _, got = sweep(tmp_path)
    assert not got["gaps"] and got["status"] == "CLEAR"


def test_only_markdown_is_read_and_a_folder_that_is_missing_is_a_gap(tmp_path):
    write(tmp_path / "drafts", "notes.txt", item())
    write(tmp_path / "drafts" / "nested", "2026-10-30-inner.md", item("Inner item", "2026-11-02"))
    _, got = sweep(tmp_path)
    assert [d["title"] for d in got["due"]] == ["Inner item"]
    proc = subprocess.run([sys.executable, str(SWEEP), "--as-of", AS_OF, "--plans-dir", str(tmp_path / "plans"), "--records-dir",
                           str(tmp_path / "absent"), "--json"], capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "home")})
    assert any("missing" in g["reason"] for g in json.loads(proc.stdout)["gaps"])


def test_a_workspace_declares_its_records_folders(tmp_path):
    home = tmp_path / "home"
    (home / "rituals").mkdir(parents=True)
    write(tmp_path / "plans", "2026-11-10.md", "# Plan\n\n1. **Nothing dated here.**\n")
    draft = write(tmp_path / "drafts", "2026-10-28-reply.md", item())
    (home / "rituals" / "config.json").write_text(json.dumps({"workspaces": {"desk": {
        "plans_dirs": [str(tmp_path / "plans")], "records_dirs": [str(tmp_path / "drafts")]}}}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SWEEP), "--as-of", AS_OF, "--workspace", "desk", "--json"], capture_output=True, text=True,
                          env={**os.environ, "SYNTHESIS_HOME": str(home)})
    got = json.loads(proc.stdout)
    assert [d["path"] for d in got["due"]] == [str(draft)]
    assert {"path": str(tmp_path / "drafts"), "kind": "records"} in got["declared_roots"]

"""A status carries its evidence, or says it is unverified.

2026-11-12: obligation statuses said colleagues could use a tool "now" when none of them could. The status had been
written from an assumption, and nothing asked what it rested on. That a line claims a thing works is meaning, which
no check reads; that a table has a column headed Status and a column for evidence is the table's own statement. So
a table is held to its own header: a row that gives a status and leaves the evidence empty is refused. A table with
a Status column and no column for evidence gets a note when a row says a thing works and points at nothing, and a
note is all a list of words may do.

Measured before it was built (2026-11-13), on thirty days of commits to twenty-seven knowledge repositories: 1,520
rows were added to tables with a Status column, 931 of them to tables that also have a column for evidence.
Replayed as built over the same 1,032 commits: 11 rows refused in 5 commits, and 12 rows noted in 10.
"""

import os
import time

import pytest

from synthesis import commit_check as cc

RECORD = "projects/alpha/CONTEXT.md"
HEAD = ("| Item | Status | Evidence |", "|---|---|---|")
BARE = ("| Item | Status |", "|---|---|")


def said(path, *lines, settings=None, before=HEAD):
    """(refusals, notes) for these lines added to one file; `before` stands above them in the file."""
    whole = [*before, *lines]
    added = [(path.encode(), len(before) + number, line.encode()) for number, line in enumerate(lines, 1)]
    return cc.status_evidence(added, {} if settings is None else settings, lambda name: "\n".join(whole))


def test_a_row_that_gives_a_status_and_no_evidence_is_refused_where_the_table_has_a_column_for_it():
    found, notes = said(RECORD, "| The connector | live for the whole team | |")
    assert len(found) == 1 and found[0].startswith(f"{RECORD}:3: ") and notes == []
    assert "evidence" in found[0] and "unverified" in found[0] and "where it was checked" in found[0]


@pytest.mark.parametrize("row", [
    "| The connector | live | [health check](https://example.com/health), 200 at 09:14 |",
    "| The connector | live | `curl -s https://example.com/health` answered ok |",
    "| The connector | live | checked by signing in as a member on 11-13 |",
    "| The connector | live, unverified | |",
    "| The connector | live | unverified |",
    "| The connector (unverified) | live | |",
])
def test_a_row_with_its_evidence_or_the_word_unverified_passes(row):
    assert said(RECORD, row) == ([], [])


@pytest.mark.parametrize("status", ["", " ", "-", "—", "n/a", "N/A", "tbd", "?", "**"])
def test_a_row_that_gives_no_status_owes_no_evidence(status):
    assert said(RECORD, f"| The connector | {status} | |") == ([], [])


@pytest.mark.parametrize("evidence", ["", "  ", "-", "—", "n/a", "N/A", "none", "TBD", "?", "**", "_-_"])
def test_a_dash_or_a_placeholder_is_no_evidence(evidence):
    assert len(said(RECORD, f"| The connector | live | {evidence} |")[0]) == 1


@pytest.mark.parametrize("head", [
    "| Thing | **Status** | Proof |", "| Thing | Current status | How we know |", "| Thing | status | Verified (how) |",
    "| Evidence | Thing | Status |", "| Thing | [Status](x.md) | Proofs |", "| Thing | Status (today) | Evidence |",
    "| Thing | Status: | _Evidence_ |", "| Thing | Deploy status | Evidence | Source |", "| Thing | Verified status | Evidence |",
])
def test_a_tables_own_header_says_which_columns_are_the_status_and_the_evidence(head):
    cells = [c.strip() for c in head.strip("|").split("|")]
    row = "| " + " | ".join("live" if "status" in c.lower() else "" if any(w in c.lower() for w in ("proof", "know", "source", "verified", "evidence"))
                            else "x" for c in cells) + " |"
    before = (head, "|" + "---|" * len(cells))
    assert len(said(RECORD, row, before=before)[0]) == 1
    filled = row.replace("|  |", "| seen in the console |", 1)
    assert said(RECORD, filled, before=before) == ([], [])


@pytest.mark.parametrize("head", [
    "| Name | State | Source |", "| Item | State | Evidence |", "| Item | Current deploy status | Evidence |", "| Item | Status / notes | Evidence |",
])
def test_a_column_headed_state_or_status_after_more_than_one_word_is_no_status_column(head):
    assert said(RECORD, "| A | live | |", before=(head, "|---|---|---|")) == ([], [])


@pytest.mark.parametrize("head", [
    "| Lead | Status | Source |", "| Task | Status | Checked |", "| Item | Status | Basis |", "| Item | Status | Sources | Checked |",
])
def test_a_source_checked_or_basis_column_never_refuses_and_a_filled_one_keeps_its_row_from_the_note(head):
    before = (head, "|" + "---|" * (head.count("|") - 1))
    assert said(RECORD, "| A | contacted | |", before=before) == ([], [])                 # a status that claims nothing: nothing
    found, notes = said(RECORD, "| A | done | |", before=before)
    assert found == [] and len(notes) == 1                                                 # a claim that points at nothing: a note
    assert said(RECORD, "| A | done | the deploy log |", before=before) == ([], [])        # a filled cell points somewhere
    assert said(RECORD, "| A | done, see [the log](x.md) | |", before=before) == ([], [])  # and so does a link


def test_the_status_column_is_never_its_own_evidence():
    assert len(said(RECORD, "| A | live | |", before=("| Item | Verified status | Evidence |", "|---|---|---|"))[0]) == 1
    found, notes = said(RECORD, "| A | live | |", before=("| Item | Verified status | Notes |", "|---|---|---|"))
    assert found == [] and len(notes) == 1


def test_one_filled_column_of_several_for_evidence_is_enough_and_a_short_row_has_none():
    before = ("| Item | Status | Evidence | Proof | Source |", "|---|---|---|---|---|")
    assert said(RECORD, "| A | done | | 11-13 by hand | |", before=before) == ([], [])
    assert said(RECORD, "| A | done | | | the deploy log |", before=before) == ([], [])
    assert len(said(RECORD, "| A | done | | | |", before=before)[0]) == 1
    assert len(said(RECORD, "| A | done |", before=before)[0]) == 1                     # the row stops before its evidence
    assert said(RECORD, "| A | done \\| released | see the log |", before=("| Item | Status | Evidence |", "|---|---|---|")) == ([], [])


@pytest.mark.parametrize("status", ["works", "working", "Live", "done", "ready", "available to everyone", "shipped", "deployed", "✅", "is live in production"])
def test_a_table_with_no_column_for_evidence_gets_a_note_and_never_a_refusal(status):
    found, notes = said(RECORD, f"| The connector | {status} |", "| The key | revoked |", before=BARE)
    assert found == [] and len(notes) == 1
    assert notes[0].startswith(f"{RECORD}: 1 row ") and "column for evidence" in notes[0] and "unverified" in notes[0]


@pytest.mark.parametrize("row", [
    "| The connector | works, see [the health check](https://example.com/health) |",
    "| The connector | works (`curl` answered) |",
    "| The connector | works, unverified |",
    "| The connector | blocked on the key |",
    "| The connector | in review |",
])
def test_no_note_for_a_row_that_points_somewhere_or_claims_nothing(row):
    assert said(RECORD, row, before=BARE) == ([], [])


def test_the_note_counts_the_rows_of_one_file_and_each_file_has_its_own():
    found, notes = said(RECORD, "| A | done |", "| B | live |", "| C | waiting |", before=BARE)
    assert found == [] and len(notes) == 1 and notes[0].startswith(f"{RECORD}: 2 rows ")


def test_what_is_no_row_of_a_status_table_is_not_read():
    assert said(RECORD, "| Item | Owner |", "|---|---|", "| A | live |", before=()) == ([], [])                  # no Status column
    assert said(RECORD, *HEAD, before=()) == ([], [])                                                              # the header and its rule
    assert said(RECORD, "| A | live | |", before=()) == ([], [])                                                   # a row with no table above it
    assert said(RECORD, "| A | live | |", before=("| Item | Status | Evidence |", "", "Some text.")) == ([], [])   # nor one cut off from its header
    assert said(RECORD, "The status is live.", "Status: live", before=()) == ([], [])                              # prose states no column
    fenced = ("```", *HEAD)
    assert said(RECORD, "| A | live | |", "```", before=fenced) == ([], [])                                        # a code fence is not read


def test_only_markdown_records_are_read_and_transcripts_and_skipped_folders_are_not():
    row = "| A | live | |"
    assert len(said("notes/status.markdown", row)[0]) == 1
    assert said("notes/status.txt", row) == ([], [])
    assert said("projects/alpha/transcripts/2026-11-13.md", row) == ([], [])
    assert said("daily-plans/2026-11-13.md", row, settings={"skip": ["daily-plans"]}) == ([], [])
    assert said("x/drafts/a.md", row, settings={"skip": ["*/drafts/*"]}) == ([], [])
    assert len(said("daily-plans/2026-11-13.md", row, settings={"skip": ["projects"]})[0]) == 1


def test_the_check_runs_only_where_the_config_turns_it_on_and_a_setting_of_another_shape_is_refused():
    row = [(RECORD.encode(), 3, b"| A | live | |")]
    read = lambda name: "\n".join([*HEAD, "| A | live | |"])  # noqa: E731
    assert cc.status_evidence(row, False, read) == ([], [])
    assert len(cc.status_evidence(row, {}, read)[0]) == 1
    for wrong in (None, True, 0, "on", [], {"skip": "daily-plans"}, {"skip": [7]}, {"enabled": False}):
        with pytest.raises(cc.Refused, match="status_evidence"):
            cc.status_evidence(row, wrong, read)


def test_each_file_is_read_once():
    reads = []

    def read(name):
        reads.append(name)
        return "\n".join([*HEAD, *("| A | live | |" for _ in range(40))])
    added = [(RECORD.encode(), number, b"| A | live | |") for number in range(3, 43)]
    assert len(cc.status_evidence(added, {}, read)[0]) == 40 and reads == [RECORD]


@pytest.mark.parametrize("head", [HEAD, ("| Name | Kind |", "|---|---|")], ids=["status", "no-status"])
def test_a_table_of_forty_thousand_added_rows_is_judged_in_one_pass(head, pace):
    # A review of 2026-11-13: each added row walked back to its table's top, so 10,000 rows took 6.1 s and a commit
    # of a 40,000-row table with no Status column took 86 s, and was then refused for running out of time.
    rows = [f"| item-{k} | live | the deploy log |" for k in range(40_000)]
    whole = "\n".join([*head, *rows])
    added = [(RECORD.encode(), number, row.encode()) for number, row in enumerate(rows, len(head) + 1)]
    began = time.perf_counter()
    assert cc.status_evidence(added, {}, lambda name: whole) == ([], [])
    assert time.perf_counter() - began < 0.5 * pace


def test_a_commit_is_refused_for_a_status_with_no_evidence_and_passes_with_it(tmp_path, monkeypatch):
    import subprocess
    repo = tmp_path / "kb"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)

    def git(*words):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *words], check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    (repo / "STATUS.md").write_text("\n".join(HEAD) + "\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-q", "-m", "one")
    (repo / "STATUS.md").write_text("\n".join([*HEAD, "| The connector | live | |"]) + "\n", encoding="utf-8")
    git("add", "-A")
    assert cc.problems({}, "S1", str(repo))[0] == []                                   # off unless the config turns it on
    found, notes, _ = cc.problems({"status_evidence": {}}, "S1", str(repo))
    assert len(found) == 1 and "STATUS.md:3" in found[0]
    (repo / "STATUS.md").write_text("\n".join([*HEAD, "| The connector | live | the health check answered at 09:14 |"]) + "\n", encoding="utf-8")
    git("add", "-A")
    assert cc.problems({"status_evidence": {}}, "S1", str(repo))[0] == []
    (repo / "PLAIN.md").write_text("\n".join([*BARE, "| The connector | live |"]) + "\n", encoding="utf-8")
    git("add", "-A")
    found, notes, _ = cc.problems({"status_evidence": {}}, "S1", str(repo))
    assert found == [] and any(note.startswith("PLAIN.md: 1 row ") for note in notes)
    with pytest.raises(cc.Refused, match="status_evidence"):
        cc.problems({"status_evidence": None}, "S1", str(repo))

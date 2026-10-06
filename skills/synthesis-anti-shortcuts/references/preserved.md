# Anti-shortcuts: preserved text

Sentences replaced on 2026-10-05 when the phrase catalog moved out of
`scripts/scan_output.py` into `costume-catalog.json` (v5 code verdict: SLIM, "move
the catalog to a data file and make it the one catalog"). Each is kept verbatim
with the file it came from; the replacement sits at the same place in that file.

## references/background.md, "Why this exists"

This skill is the methodology. The operational catalog in `scripts/scan_output.py` is the extract — a phrase scanner that any agent or pipeline can run against draft output. The detailed catalog with rationale, the constraint-first protocol with a worked example, the sub-agent dispatch and acceptance rules, and the anonymized case studies all live in `references/` and load on demand.

## references/background.md, "How the Pieces Fit"

```
   |-- scripts/scan_output.py                Standalone scanner (Python 3, stdlib + pyyaml)
```

## references/methodology.md

The full per-phrase catalog with category, rationale, and replacement framings lives in [`references/costume-vocabulary.md`](costume-vocabulary.md). The operational extract is in `scripts/scan_output.py`.

4. Update `scripts/scan_output.py` if the embedded catalog should detect the phrase.

## references/costume-vocabulary.md, "How the Catalog Maintains Itself"

3. Add the phrase to the scanner's embedded catalog in [`../scripts/scan_output.py`](../scripts/scan_output.py) if it should fire automatically.

## SKILL.md, "The scanner"

`python3 scripts/scan_output.py draft.md` (or text on stdin) prints each hit by category: line and column, the matched phrase, why it is a shortcut, a rewrite framing and a `see:` case. Exit 0 clean, 1 detections, 2 error. Flags: `--json`, `--quiet` (exit code only, for hooks), `--context 120`, `--catalog <file.yaml>` (needs PyYAML).

## scripts/scan_output.py docstring (the parts that changed)

Zero required external dependencies — Python 3.8+ stdlib is sufficient. The
optional --catalog flag accepts a YAML file (requires PyYAML); without it,
the scanner uses an embedded baseline catalog.

  # Use a custom catalog (requires PyYAML)
  ./scan_output.py --catalog ~/.synthesis/anti-shortcut-catalog.yaml draft.md

The embedded catalog's header said: "Mirrors the phrase set in the public
anti-shortcut catalog. Public references point at case-studies.md within this
skill rather than at incident-specific lesson files. The catalog can be
overridden by passing --catalog <yaml>." The phrase set is unchanged in
`costume-catalog.json`, with the additions listed in the coverage map.

#!/usr/bin/env python3
"""Cross-article repetition and batch title-shape checker.

Per-artifact review cannot see repetition that only exists when a body of work
is read together: thirty articles staged as one wave shared constructions that
every individual review passed. This tool reads a corpus and reports:

1. Body repetition: maximal word n-gram runs shared across documents,
   filtered so ordinary English (function-word runs, short overlaps) does not
   drown the report, with high-document-frequency runs classified separately
   as boilerplate candidates (deliberate series footers look different from
   accidentally shared constructions).
2. Title shape: mechanical batch-shape measurements against the default
   budget (repeated two-word openings, watch-token concentration,
   imperative/second-person share).

The tool is a measurement instrument, not a judge. A finding is an item for a
reviewer to adjudicate: quotes, deliberate refrains, and legal boilerplate are
legitimate repetition. Mechanism classification of titles (reversal, negation,
question, coined principle...) is reviewer judgment and out of scope here.
Nothing this tool reports establishes authorship.

Input contract:
  corpus_repetition.py PATH [PATH ...]      # .md files, or directories
                                            # searched recursively for *.md
  corpus_repetition.py --titles-file FILE   # one title per line (e.g. a
                                            # proposed replacement set)
Options:
  --min-n N          minimum shared-run length in words (default 5)
  --max-n N          maximum run length probed (default 12)
  --min-content K    minimum distinct non-function words a run needs (default 2)
  --boilerplate-df F fraction of documents at/above which a run is classified
                     boilerplate-candidate instead of a finding (default 0.5)
  --watch-token T    title token to report concentration for (repeatable;
                     default: AI)
  --basis N          batch-size basis for title budgets (default: title count)
  --ignore-file F    file of literal phrases to ignore (one per line)
  --json             machine-readable output
  --max-findings N   cap on reported body findings (default 200)
  --strict           also exit 1 while boilerplate candidates await a
                     reviewer's confirmation (default: candidates report but
                     do not fail, so series footers don't wedge pipelines)

Files whose body text duplicates an earlier file (mirrored trees) are counted
once and reported under skipped_content_duplicates.

Exit codes: 0 nothing over threshold; 1 findings to adjudicate; 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

# Function words (small, deliberately conservative): runs made almost only of
# these are ordinary English plumbing, not shared constructions.
FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "for",
    "of", "in", "on", "at", "to", "from", "by", "with", "without", "as",
    "into", "onto", "over", "under", "about", "after", "before", "between",
    "through", "during", "against", "within", "across", "around", "toward",
    "towards", "up", "down", "out", "off", "than", "then",
    "is", "are", "was", "were", "be", "been", "being", "am",
    "do", "does", "did", "done", "doing",
    "have", "has", "had", "having",
    "will", "would", "shall", "should", "can", "could", "may", "might",
    "must", "ought",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "mine", "yours",
    "this", "that", "these", "those", "there", "here",
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "not", "no", "nor", "n't",
    "if", "because", "while", "although", "though", "since", "unless",
    "one", "two", "all", "any", "some", "each", "every", "both", "few",
    "more", "most", "other", "such", "only", "own", "same", "very", "just",
    "also", "too", "even", "still", "again", "once", "now",
}

# Leading verbs treated as imperative openers for the register share metric.
IMPERATIVE_OPENERS = {
    "add", "ask", "avoid", "build", "check", "choose", "consider", "create",
    "cut", "define", "delete", "design", "do", "don't", "find", "fix", "get",
    "give", "keep", "know", "learn", "let", "make", "measure", "meet",
    "never", "plan", "prepare", "put", "read", "remember", "remove", "run",
    "save", "say", "see", "ship", "start", "stop", "take", "teach", "tell",
    "test", "think", "treat", "try", "turn", "use", "watch", "write",
}

FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.S)
TITLE_RE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
WORD_RE = re.compile(r"[a-z0-9']+")


def read_document(path: Path) -> tuple[str | None, list[str]]:
    """Return (title-or-None, body words) for one markdown file."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = None
    fm = FRONTMATTER_RE.match(raw)
    body = raw
    if fm:
        m = TITLE_RE.search(fm.group(0))
        if m:
            title = m.group(1).strip()
        body = raw[fm.end():]
    body = CODE_FENCE_RE.sub(" ", body)
    body = INLINE_CODE_RE.sub(" ", body)
    body = LINK_RE.sub(r"\1", body)
    words = WORD_RE.findall(body.lower())
    return title, words


def collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(p)
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(f)
    return unique


def ngram_positions(words: list[str], n: int) -> set[str]:
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def content_word_count(gram: str) -> int:
    return len({w for w in gram.split() if w not in FUNCTION_WORDS})


def _contains_words(longer: str, shorter: str) -> bool:
    """Word-boundary containment: shorter's word sequence appears in longer's."""
    lw, sw = longer.split(), shorter.split()
    n = len(sw)
    return any(lw[i:i + n] == sw for i in range(len(lw) - n + 1))


def find_shared_runs(
    docs: dict[str, list[str]],
    min_n: int,
    max_n: int,
    min_content: int,
    ignore: set[str],
) -> list[dict]:
    """Maximal cross-document n-gram runs with document lists."""
    grams_by_doc: dict[int, dict[str, set[str]]] = {}
    for n in range(min_n, max_n + 1):
        grams_by_doc[n] = {name: ngram_positions(ws, n) for name, ws in docs.items()}

    results: list[dict] = []
    # A shorter run is suppressed only when it is a word-boundary sub-run of
    # an already-reported longer run AND its document set adds nothing new -
    # a genuine repetition between a different pair of documents is its own
    # finding even when its words happen to sit inside a longer run
    # elsewhere. Ignored phrases suppress their word-boundary sub-runs in any
    # document (ignoring a maximal run silences its fragments), while a run
    # extending beyond an ignored phrase still reports.
    claimed: list[tuple[str, frozenset[str]]] = []
    for n in range(max_n, min_n - 1, -1):
        counts: dict[str, list[str]] = {}
        for name, grams in grams_by_doc[n].items():
            for g in grams:
                counts.setdefault(g, []).append(name)
        for gram, names in counts.items():
            if len(names) < 2:
                continue
            if gram in ignore:
                continue
            if content_word_count(gram) < min_content:
                continue
            if any(_contains_words(ig, gram) for ig in ignore):
                continue
            docset = frozenset(names)
            if any(_contains_words(longer, gram) and docset <= ldocs
                   for longer, ldocs in claimed):
                continue
            claimed.append((gram, docset))
            results.append({"run": gram, "n": n, "documents": sorted(names)})
    results.sort(key=lambda r: (-r["n"], -len(r["documents"]), r["run"]))
    return results


def analyze_titles(
    titles: list[str],
    watch_tokens: list[str],
    basis: int | None,
) -> dict:
    """Mechanical batch-shape measurements for a title set."""
    n_titles = len(titles)
    basis = basis or n_titles
    # thresholds scale with the declared basis (defaults follow the 30-title
    # budget: openings repeated more than twice, one-third register share)
    opening_threshold = max(2, math.ceil(basis / 15))
    register_threshold = basis / 3

    openings: dict[str, list[str]] = {}
    watch_hits: dict[str, int] = {t.lower(): 0 for t in watch_tokens}
    imperative_or_second = 0
    for t in titles:
        words = WORD_RE.findall(t.lower())
        if len(words) >= 2:
            openings.setdefault(" ".join(words[:2]), []).append(t)
        lowered = set(words)
        for tok in watch_hits:
            if tok in lowered:
                watch_hits[tok] += 1
        if words and (
            words[0] in IMPERATIVE_OPENERS or "you" in lowered or "your" in lowered
        ):
            imperative_or_second += 1

    repeated_openings = {
        k: v for k, v in openings.items() if len(v) > opening_threshold
    }
    flags: list[str] = []
    for opening, members in sorted(repeated_openings.items()):
        flags.append(
            f"two-word opening '{opening}' repeated {len(members)}x "
            f"(budget: {opening_threshold} per {basis})"
        )
    for tok, hits in watch_hits.items():
        if n_titles and hits / n_titles > 1 / 3:
            flags.append(
                f"watch token '{tok}' appears in {hits}/{n_titles} titles "
                f"({hits / n_titles:.0%}); budget expects it only where the "
                "title is otherwise ambiguous"
            )
    if imperative_or_second > register_threshold:
        flags.append(
            f"imperative/second-person register in {imperative_or_second}/"
            f"{n_titles} titles (budget: at most one third of {basis})"
        )
    return {
        "title_count": n_titles,
        "basis": basis,
        "repeated_openings": {k: v for k, v in sorted(repeated_openings.items())},
        "watch_token_counts": watch_hits,
        "imperative_or_second_person": imperative_or_second,
        "flags": flags,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-article repetition and batch title-shape checker."
    )
    parser.add_argument("paths", nargs="*", help="Markdown files or directories")
    parser.add_argument("--titles-file", help="Plain file of titles, one per line")
    parser.add_argument("--min-n", type=int, default=5)
    parser.add_argument("--max-n", type=int, default=12)
    parser.add_argument("--min-content", type=int, default=2)
    parser.add_argument("--boilerplate-df", type=float, default=0.5)
    parser.add_argument("--watch-token", action="append", default=None)
    parser.add_argument("--basis", type=int, default=None)
    parser.add_argument("--ignore-file", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-findings", type=int, default=200)
    parser.add_argument("--strict", action="store_true",
                        help="also exit 1 when boilerplate candidates exist "
                             "(they still need a reviewer confirmation)")
    args = parser.parse_args(argv)

    if not args.paths and not args.titles_file:
        parser.print_usage(sys.stderr)
        print("error: provide corpus paths and/or --titles-file", file=sys.stderr)
        return 2
    if args.min_n < 3:
        print("error: --min-n below 3 drowns the report in ordinary English",
              file=sys.stderr)
        return 2

    ignore: set[str] = set()
    if args.ignore_file:
        for line in Path(args.ignore_file).read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line:
                ignore.add(line)

    docs: dict[str, list[str]] = {}
    titles: list[str] = []
    duplicates: list[str] = []
    if args.paths:
        try:
            files = collect_files(args.paths)
        except FileNotFoundError as exc:
            print(f"error: no such path: {exc}", file=sys.stderr)
            return 2
        if not files:
            print("error: no .md files found under the given paths", file=sys.stderr)
            return 2
        seen_bodies: dict[str, str] = {}
        for f in files:
            title, words = read_document(f)
            body_key = " ".join(words)
            if words and body_key in seen_bodies:
                # mirrored trees would otherwise count one document twice and
                # silently double every measurement it participates in
                duplicates.append(f"{f} (duplicate of {seen_bodies[body_key]})")
                continue
            if words:
                seen_bodies[body_key] = str(f)
            docs[str(f)] = words
            if title:
                titles.append(title)
    if args.titles_file:
        titles = [
            line.strip()
            for line in Path(args.titles_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    report: dict = {"documents": len(docs)}
    if args.paths and duplicates:
        report["skipped_content_duplicates"] = duplicates
    findings_present = False

    if len(docs) >= 2:
        runs = find_shared_runs(docs, args.min_n, args.max_n, args.min_content, ignore)
        n_docs = len(docs)
        # Boilerplate classification needs a corpus big enough for document
        # frequency to mean anything; with 2-3 documents every shared run
        # would hit the fraction, so everything stays a finding there.
        def is_boilerplate(r: dict) -> bool:
            # fraction alone misfires at small corpus sizes (2 of 4 documents
            # is a shared construction, not series boilerplate), so demand at
            # least three sharing documents as well
            return (n_docs >= 4 and len(r["documents"]) >= 3
                    and len(r["documents"]) / n_docs >= args.boilerplate_df)

        boilerplate = [r for r in runs if is_boilerplate(r)]
        shared = [r for r in runs if not is_boilerplate(r)]
        report["shared_runs"] = shared[: args.max_findings]
        report["shared_run_total"] = len(shared)
        report["boilerplate_candidates"] = boilerplate[: args.max_findings]
        if shared:
            findings_present = True
        if boilerplate and args.strict:
            findings_present = True
    elif docs:
        report["shared_runs"] = []
        report["note"] = "corpus repetition needs at least two documents"

    if titles:
        title_report = analyze_titles(
            titles, args.watch_token or ["AI"], args.basis
        )
        report["titles"] = title_report
        if title_report["flags"]:
            findings_present = True

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if "shared_runs" in report:
            total = report.get("shared_run_total", 0)
            print(f"Cross-document shared runs (>= {args.min_n} words, "
                  f"{report['documents']} documents): {total}")
            for r in report["shared_runs"]:
                print(f"  {r['n']}-gram in {len(r['documents'])} docs: {r['run']}")
                for d in r["documents"]:
                    print(f"      - {d}")
            bp = report.get("boilerplate_candidates", [])
            if bp:
                print(f"Boilerplate candidates (in >= {args.boilerplate_df:.0%} "
                      f"of documents) - likely deliberate; confirm, don't flag:")
                for r in bp:
                    print(f"  {r['n']}-gram in {len(r['documents'])} docs: {r['run']}")
        if "titles" in report:
            t = report["titles"]
            print(f"Title shape ({t['title_count']} titles, basis {t['basis']}):")
            print(f"  imperative/second-person: {t['imperative_or_second_person']}")
            for tok, hits in t["watch_token_counts"].items():
                print(f"  watch token '{tok}': {hits}")
            for flag in t["flags"]:
                print(f"  FLAG: {flag}")
            if not t["flags"]:
                print("  within budget")
        print()
        print("Findings are adjudication items, not verdicts. Quotes, refrains,")
        print("and deliberate boilerplate are legitimate; a reviewer decides.")
        print("Nothing here establishes authorship.")

    return 1 if findings_present else 0


if __name__ == "__main__":
    sys.exit(main())

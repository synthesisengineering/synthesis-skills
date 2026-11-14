# Promotion gate: the marker config

Read when writing or changing `.agents/promotion-markers.json`, or wiring the
scan into a site's build.

Contents:
- The config file
- The four views
- Canonical marker policy
- Wiring it into build.sh

## The config file

Copy `templates/promotion-markers.example.json` to `.agents/promotion-markers.json`
in the site repository and replace its examples with the markers your pipeline
actually leaves. It is JSON, read with the standard library:

- `markers`: a non-empty list. Each marker has a unique `id`, a `rationale`
  (the threat, in one line), a `pattern` (a regular expression, matched
  case-insensitively and per line for `^` and `$`), `in` (the views to check;
  default `text`, `comments` and `source`), and `positive` and `negative`
  example strings.
- `file_globs` (optional): which built files to read, relative to the output
  folder. The default is `**/*.html`, `**/*.htm`, `**/*.xml`, `**/*.txt` and
  `**/*.json`, so feeds and search indexes are scanned as well as pages.

Every built file matching the globs is scanned, so a page nobody declared is
still read. Symlinked files are not followed, and the scan never reads outside
the output folder. An output folder with no matching file refuses (exit 2):
an empty scan is not a clean one.

## The four views

- `text`: the displayed prose. Comments, `script`, `style`, `template`,
  `noscript`, `pre` and `code` are removed; inline tags (`a`, `b`, `em`,
  `span` and the like) join their neighbours, so `Public<a>ation</a>` reads
  "Publication", while block tags separate words; entities are decoded, so
  `&lt;DATE&gt;` reads `<DATE>`; whitespace is collapsed.
- `headings`: the text of each `h1` to `h6`, one per line, read the same way.
  A heading runs to its closing tag, the next heading, or the end of the file,
  because browsers repair a missing close.
- `comments`: each HTML comment's body, one per line.
- `source`: the raw file. A source hit reports its line number.

Do not label `text` as all browser-visible or accessible text: it leaves out
attributes (`alt`, `title`, `aria-*`), code, non-displayed containers, CSS and
anything a script changes in the browser. The destination's own parser is the
arbiter of what a reader sees; the reader in `promotion_gate.py` is held to a
corpus generated with it (`tests/test_promotion_gate.py`, `CORPUS`). When a
page reads differently in the destination, add the page and the destination's
reading to the corpus first, then fix the reader. When a destination needs
another channel (accessible attributes, feed fields, search documents), add a
view and its motivating fixture before relying on it.

## Canonical marker policy

Each marker identity appears once with its threat rationale and positive and
negative examples. The loader runs the examples: the pattern must match at
least one positive example and reject every negative one, or the config is
refused. A schema-valid but behaviorally empty pattern is an invalid policy.
Choosing views per marker lets a heading-only marker refuse an internal
section ("Publication Notes" as a heading) while ordinary prose with the same
words stays valid.

The policy is a bounded vocabulary, not a semantic disclosure model. It does
not decide whether ordinary prose is appropriate to disclose; that stays with
the disclosure policy and the principal. Keep patterns tied to observed
pipeline scaffolding. If a proposed pattern matches ordinary language, repair
its view or remove it; approval fatigue is not safety.

## Wiring it into build.sh

Run the scan after the build writes its output folder and before the deploy
command, and stop on any non-zero exit:

```bash
python3 <synthesis-promotion-gate-root>/scripts/promotion_gate.py dist --config .agents/promotion-markers.json || exit 1
```

The deploy command after it is still a production deploy: the v5 deploy guard
holds it until the principal approves that exact command, and the approval is
single-use. A clean scan is not that approval, and the approval is not a clean
scan; both are needed. Rebuild after any fix and scan again, because the scan
judges the bytes that will ship, not the source.

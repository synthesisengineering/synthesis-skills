---
name: synthesis-promotion-gate
description: "Scan a built site for configured internal markers (draft notes, placeholders, private comments) before an approved deploy, and refuse on any hit. Use for publication gates, rendered-output inspection, pre-deploy marker scans or build.sh deploy checks."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-implementation-integrity"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Promotion Gate

Reads the built site the way a reader will see it, before the deploy command may publish it, and stops the deploy when a configured internal marker survived the build.

## Binding rules

1. **A successful build is not a publication-safety signal.** A build shows a renderer accepted its inputs; promotion needs a second judgment over the outgoing files.
2. **The gate is evidence, not permission.** The deploy still needs the principal's approval of that exact command (the v5 deploy guard, R3.2), and a clean scan covers only the markers configured.
3. **Refuse, never warn:** a hit (exit 1), an unusable config, a missing folder or a scan that found no files (exit 2) stops the deploy.
4. **Name the view judged:** `text` (what a reader sees), `headings`, `comments` or `source`. `text` is not all browser-visible text: attributes, code, scripts and styles are left out.
5. **The destination's parser is the arbiter of what a reader sees.** The gate's small HTML reader is held to a corpus that parser produced; when they disagree, add the case to the corpus and fix the reader. The `source` view catches a marker however the page parses.
6. **One canonical identity per marker,** whose pattern matches at least one positive example and no negative one; a pattern that matches nothing protects nothing.
7. **Keep patterns tied to observed pipeline scaffolding.** A pattern that matches ordinary language is repaired or removed: approval fatigue is not safety.
8. **The unverified remainder is never none.** The scan sees only built files matching its globs: not consumers served from elsewhere, remote bytes after the deploy, or client-side changes.
9. **A failing fixture comes before the repair** for a changed view or a new kind of marker.

## Contents

- [references/configuration.md](references/configuration.md): the marker config, the four views and what each leaves out, the marker policy, and wiring the scan into `build.sh`. Read it when writing or changing the config.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text and each script change now lives (ruling D8).
- [references/preserved.md](references/preserved.md): the 2.0.0 text for the retired engine (isolated build, routes, receipts, `check` and `enforce`), verbatim. Read only to review the change.
- Run it, Tests: below.

## Run it

In the site repository's `build.sh`, between the build and the deploy:

```bash
python3 <synthesis-promotion-gate-root>/scripts/promotion_gate.py dist --config .agents/promotion-markers.json || exit 1
```

It prints one line per hit, `<file>[:line]: <marker id> in <view> (<rationale>)`, then a summary such as `42 file(s) scanned, 3 marker(s), 0 hit(s): clean`. Exit 0 clean; 1 hits found, so do not deploy; 2 the config, the folder or an empty scan made the result meaningless. The matched text itself is not printed; open the file at the reported place.

## Tests

`python3 -m pytest -q skills/synthesis-promotion-gate/tests` runs the rendered-view corpus (inline adjacency, entities, repaired headings, attribute, code and hidden-container exclusions), the five round-two defects behind a successful build, and the policy refusals.

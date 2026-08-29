#!/usr/bin/env python3
"""Build a self-contained decision-packet HTML file from a JSON spec.

A decision packet is a single HTML file that collects many parallel decisions from a
principal in one sitting and emits a paste-able record of them. It exists because the
alternatives do not scale: one question per turn costs N round-trips, and a prose report
or a chat table makes the principal supply the structure the agent needs.

The origin run: 26 rounds of per-item conversation produced 0 of 30 decisions. One packet
produced 30 of 30, in one pass, in one paste.

    python3 build_packet.py spec.json -o packet.html
    python3 build_packet.py spec.json --stdout > packet.html
    python3 build_packet.py --schema          # print the spec schema and exit

Stdlib only. No build step, no dependencies, no server: the emitted file opens from disk,
from a local HTTP server, or as a published artifact.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys

SCHEMA = """\
Decision-packet spec (JSON)
===========================

{
  "title":       "Code review — CSA content pipeline",     REQUIRED
  "subtitle":    "12 findings from an adversarial pass",    optional
  "intro":       "Markdown-free prose shown under the title.",  optional
  "storage_key": "csa-review-2026-09",   optional; defaults to a slug of the title.
                                         Change it to reset everyone's saved state.
  "summary_intro": "Paste this back to the agent.",  optional
  "audience":    "One sentence: who reads this and what they already know.",
                                          optional in the format, REQUIRED by the
                                          reader contract in SKILL.md - it is the
                                          audience you must write every row for.
  "glossary": [                           optional - one-clause meanings for every
    {"term": "holdout",                   term of art any row still needs after
     "meaning": "test material set aside  plain-language rewriting. Rendered as a
      in advance so a rule is judged on   collapsible band under the intro.
      text it was not tuned on"}
  ],

  "options": [                            REQUIRED — the default choice set for every row
    {"value": "fix-now",  "label": "Fix now",  "tone": "danger"},
    {"value": "fix-later","label": "Fix later","tone": "warn"},
    {"value": "waive",    "label": "Waive",    "tone": "muted"}
  ],
  tone ∈ {danger, warn, ok, muted, info} — colours the selected button only.

  "filters": [                            optional; name these from the CONTENT
    {"id": "needs-fix", "label": "Needs a fix", "tags": ["correctness"]},
    {"id": "disputed",  "label": "We disagreed", "disagreement": true},
    {"id": "undecided", "label": "Not yet decided", "undecided": true}
  ],
  A filter matches if ANY of its declared criteria match. "undecided" is computed live
  from saved state; "disagreement" matches rows carrying a disagreement block.

  "rows": [                               REQUIRED
    {
      "id":    "F-01",                    REQUIRED — stable; it keys localStorage
      "label": "Unbounded retry loop in the publish worker",   REQUIRED
      "context":  "What the reader needs to judge it.",        optional
      "reasoning":"Why the agent recommends what it does.",    optional
      "impact": {                          optional in the format, REQUIRED by the
        "accept": "What actually happens   reader contract: the consequences of
                   if they take your       agreeing and of not agreeing, stated in
                   recommendation.",       outcomes the principal cares about -
        "decline": "What happens if they   never in internal treatment vocabulary.
                   do not."
      },
      "recommendation": "fix-now",        optional but STRONGLY expected — MARKS
                                          a button (never pre-selects it: a packet
                                          that opens decided records nobody's
                                          judgment). No recommendation on any row
                                          means the packet is a questionnaire; see the
                                          anti-trigger in SKILL.md.
      "severity": "high",                 optional ∈ {high, medium, low, none}
                                          — drives the coloured rail
      "tags":  ["correctness", "worker"], optional — drive filters and read as chips
      "links": [{"label": "worker.py:214", "href": "https://..."}],   optional
      "disagreement": {                   optional — surface it, never resolve it first
        "a": {"who": "Reviewer A", "view": "Ship it; the retry is bounded upstream."},
        "b": {"who": "Reviewer B", "view": "Upstream bound was removed in v0.91."}
      },
      "options": [...]                    optional per-row override of the choice set
    }
  ]
}
"""

TONES = {"danger", "warn", "ok", "muted", "info"}
SEVERITIES = {"high", "medium", "low", "none"}


# ---------------------------------------------------------------------------
# Validation — fail loudly at build time, never emit a broken packet
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "packet"


def validate(spec: dict) -> list[str]:
    """Return a list of problems; empty means the spec is buildable."""
    problems: list[str] = []

    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    if not spec.get("title"):
        problems.append("missing required field: title")

    opts = spec.get("options")
    if not isinstance(opts, list) or not opts:
        problems.append("missing required field: options (a non-empty list)")
        opts = []
    for i, o in enumerate(opts):
        if not isinstance(o, dict) or not o.get("value") or not o.get("label"):
            problems.append(f"options[{i}] needs both 'value' and 'label'")
        elif o.get("tone") and o["tone"] not in TONES:
            problems.append(f"options[{i}].tone {o['tone']!r} not in {sorted(TONES)}")

    rows = spec.get("rows")
    if not isinstance(rows, list) or not rows:
        problems.append("missing required field: rows (a non-empty list)")
        return problems

    if len(rows) < 5:
        # Not fatal — but the skill's anti-trigger says this shape is the wrong tool.
        problems.append(
            f"NOTE: only {len(rows)} rows. Below about five parallel decisions, just ask "
            "in chat — see the anti-trigger in SKILL.md. Pass --allow-small to build anyway."
        )

    seen: set[str] = set()
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            problems.append(f"rows[{i}] must be an object")
            continue
        rid = r.get("id")
        if not rid:
            problems.append(f"rows[{i}] missing required field: id")
        elif not isinstance(rid, str) or not rid.strip():
            # Ids key localStorage and DOM datasets, which coerce every value
            # to a string: JSON 1 and "1" become the same browser key, so two
            # JSON-distinct ids can silently share saved state. Only non-empty
            # strings are ids.
            problems.append(
                f"rows[{i}] id {rid!r} must be a non-empty string — browser "
                "storage coerces ids to strings, so non-string ids can "
                "collide after coercion"
            )
        elif rid.strip() in seen:
            problems.append(f"rows[{i}] duplicate id {rid.strip()!r} — ids key localStorage and must be unique")
        else:
            seen.add(rid.strip())
        if not r.get("label"):
            problems.append(f"rows[{i}] ({rid}) missing required field: label")
        sev = r.get("severity")
        if sev and sev not in SEVERITIES:
            problems.append(f"rows[{i}] ({rid}) severity {sev!r} not in {sorted(SEVERITIES)}")
        row_opts = r.get("options") or opts
        values = {o.get("value") for o in row_opts if isinstance(o, dict)}
        rec = r.get("recommendation")
        if rec and rec not in values:
            problems.append(
                f"rows[{i}] ({rid}) recommendation {rec!r} is not one of its options {sorted(v for v in values if v)}"
            )
        dis = r.get("disagreement")
        if dis is not None:
            if not isinstance(dis, dict) or not dis.get("a") or not dis.get("b"):
                problems.append(f"rows[{i}] ({rid}) disagreement needs both 'a' and 'b'")
        imp = r.get("impact")
        if imp is not None and (not isinstance(imp, dict)
                                or not imp.get("accept") or not imp.get("decline")):
            problems.append(f"rows[{i}] ({rid}) impact needs both 'accept' and 'decline'")

    gl = spec.get("glossary")
    if gl is not None:
        if not isinstance(gl, list):
            problems.append("glossary must be a list of {term, meaning}")
        else:
            for gi, g in enumerate(gl):
                if not isinstance(g, dict) or not g.get("term") or not g.get("meaning"):
                    problems.append(f"glossary[{gi}] needs both 'term' and 'meaning'")

    # Reader contract (see SKILL.md): a packet is a stranger-read document.
    # These are READER-class findings - warnings by default, fatal under
    # --strict-reader, which SKILL.md requires for packets handed to a
    # principal. Measured origin: a 15-row packet written in project-internal
    # language collected 0 decisions from the same principal whose plain-
    # language packets ran 30/30.
    if not spec.get("audience"):
        problems.append("READER: no 'audience' - name who reads this and what they already know, then write every row for that reader")
    missing_impact = [str(r.get("id")) for r in rows
                      if isinstance(r, dict) and not r.get("impact")]
    if missing_impact:
        problems.append(
            "READER: rows without an 'impact' block (what happens if they accept / decline, in the principal's terms): "
            + ", ".join(missing_impact))

    recommended = sum(1 for r in rows if isinstance(r, dict) and r.get("recommendation"))
    if recommended == 0:
        problems.append(
            "no row carries a recommendation. A packet without recommendations is a "
            "questionnaire, which means the analysis is not finished — see SKILL.md."
        )
    return problems


# ---------------------------------------------------------------------------
# The template
# ---------------------------------------------------------------------------
# `<meta charset>` sits in the first bytes deliberately. Without it, typographic
# punctuation in the rows renders as mojibake when the file is served over a plain
# local HTTP server. That defect reached a real packet; test_build_packet.py fixes it
# in place.

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --bg: #ffffff; --panel: #f7f8fa; --panel-2: #eef1f5; --ink: #14181f; --ink-2: #4a5568;
  --ink-3: #6b7688; --line: #d8dee7; --line-2: #c3ccd8; --accent: #12395f;
  --danger: #b3261e; --warn: #9a6400; --ok: #1c6b3f; --info: #1c4f8f; --muted: #5b6472;
  --sel-fg: #ffffff; --chip: #e6ebf2; --focus: #2d6cdf;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #10131a; --panel: #171b24; --panel-2: #1e2430; --ink: #e8ecf2; --ink-2: #b3bccb;
    --ink-3: #8b95a6; --line: #2a3140; --line-2: #3a4356; --accent: #7fb0e8;
    --danger: #ff8a80; --warn: #e8b04b; --ok: #6fcf97; --info: #7fb0e8; --muted: #9aa4b4;
    --sel-fg: #10131a; --chip: #232a37; --focus: #7fb0e8;
  }
}
:root[data-theme="dark"] {
  --bg: #10131a; --panel: #171b24; --panel-2: #1e2430; --ink: #e8ecf2; --ink-2: #b3bccb;
  --ink-3: #8b95a6; --line: #2a3140; --line-2: #3a4356; --accent: #7fb0e8;
  --danger: #ff8a80; --warn: #e8b04b; --ok: #6fcf97; --info: #7fb0e8; --muted: #9aa4b4;
  --sel-fg: #10131a; --chip: #232a37; --focus: #7fb0e8;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
  font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 28px 20px 96px; }
header h1 { font-size: 25px; line-height: 1.2; margin: 0 0 6px; letter-spacing: -0.01em; }
header .sub { color: var(--ink-2); margin: 0 0 14px; }
header .intro { color: var(--ink-2); max-width: 74ch; margin: 0 0 20px; }
header .aud { color: var(--ink-3); font-size: 13px; margin: -10px 0 16px; }
details.gloss { margin: 0 0 20px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
details.gloss summary { cursor: pointer; padding: 8px 12px; font-size: 13px; color: var(--ink-2); }
details.gloss dl { margin: 0; padding: 4px 14px 12px; font-size: 13px; }
details.gloss dt { font-weight: 600; margin-top: 6px; }
details.gloss dd { margin: 0; color: var(--ink-2); }
.impact { border-left: 3px solid var(--line); padding: 6px 10px; margin: 8px 0; font-size: 13.5px; }
.impact b { color: var(--ink-2); }
.counts { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }
.count {
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 12px; min-width: 92px;
}
.count b { display: block; font-size: 20px; font-variant-numeric: tabular-nums; line-height: 1.15; }
.count span { font-size: 12px; color: var(--ink-3); }
.filters { display: flex; flex-wrap: wrap; gap: 7px; margin: 0 0 22px; }
.filters button {
  font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
  background: var(--chip); color: var(--ink-2); border: 1px solid transparent;
}
.filters button[aria-pressed="true"] { background: var(--accent); color: var(--sel-fg); }
.filters button:focus-visible, .opts button:focus-visible, .bar button:focus-visible {
  outline: 2px solid var(--focus); outline-offset: 2px;
}
.row {
  position: relative; background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 15px 17px 15px 21px; margin: 0 0 12px; overflow: hidden;
}
.row::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--line-2);
}
.row[data-sev="high"]::before   { background: var(--danger); }
.row[data-sev="medium"]::before { background: var(--warn); }
.row[data-sev="low"]::before    { background: var(--ok); }
.row[data-decided="yes"] { border-color: var(--line-2); }
.row[hidden] { display: none; }
.rid { font-family: var(--mono); font-size: 12px; color: var(--ink-3); }
.rlabel { font-weight: 650; margin: 2px 0 7px; font-size: 16.5px; line-height: 1.35; }
.rtext { color: var(--ink-2); margin: 0 0 9px; max-width: 82ch; }
.rtext.reason::before {
  content: "Recommendation "; font-weight: 650; color: var(--ink); letter-spacing: .01em;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 9px; }
.chip {
  font-size: 11.5px; font-family: var(--mono); background: var(--chip); color: var(--ink-3);
  padding: 2px 8px; border-radius: 999px;
}
.links { margin: 0 0 9px; font-size: 13.5px; }
.links a { color: var(--info); }
.dis {
  background: var(--panel-2); border-left: 3px solid var(--warn); border-radius: 0 7px 7px 0;
  padding: 9px 13px; margin: 0 0 11px; font-size: 14px;
}
.dis .h { font-weight: 650; font-size: 12px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--warn); margin-bottom: 5px; }
.dis p { margin: 3px 0; color: var(--ink-2); }
.dis b { color: var(--ink); }
.opts { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin: 11px 0 0; }
.opts button {
  font: inherit; font-size: 13.5px; padding: 7px 14px; border-radius: 7px; cursor: pointer;
  background: var(--bg); color: var(--ink-2); border: 1px solid var(--line-2);
}
.opts button[aria-pressed="true"] { color: var(--sel-fg); border-color: transparent; font-weight: 600; }
.opts button[aria-pressed="true"][data-tone="danger"] { background: var(--danger); }
.opts button[aria-pressed="true"][data-tone="warn"]   { background: var(--warn); }
.opts button[aria-pressed="true"][data-tone="ok"]     { background: var(--ok); }
.opts button[aria-pressed="true"][data-tone="info"]   { background: var(--info); }
.opts button[aria-pressed="true"][data-tone="muted"]  { background: var(--muted); }
/* The recommendation is marked ON the control, so the eye lands on it and agreeing is
   one click. It is deliberately NOT pre-selected: a packet that starts fully decided
   cannot tell "I agreed" from "I never looked", and the summary would then report
   decisions nobody made. */
.opts button[data-recommended="true"] {
  border-color: var(--accent); border-width: 1.5px; font-weight: 600; color: var(--ink);
}
.opts button[data-recommended="true"]::before {
  content: "★ "; color: var(--accent); font-size: 11px; vertical-align: 1px;
}
.opts button[aria-pressed="true"][data-recommended="true"]::before { color: var(--sel-fg); }
.rec { font-size: 12px; color: var(--ink-3); margin-left: 2px; }
.note { margin-top: 9px; }
.note textarea {
  width: 100%; min-height: 38px; font: inherit; font-size: 14px; padding: 8px 10px;
  border-radius: 7px; border: 1px solid var(--line-2); background: var(--bg); color: var(--ink);
  resize: vertical;
}
.note textarea::placeholder { color: var(--ink-3); }
.bar {
  position: sticky; bottom: 0; margin-top: 26px; background: var(--panel);
  border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
}
.barhead { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.barhead > b { font-size: 15px; font-variant-numeric: tabular-nums; }
.bar .hint { margin: 12px 0 8px; color: var(--ink-2); font-size: 14px; }
.bar textarea {
  width: 100%; min-height: 130px; font-family: var(--mono); font-size: 12.5px; padding: 10px;
  border-radius: 7px; border: 1px solid var(--line-2); background: var(--bg); color: var(--ink);
}
.bar .actions { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; }
#summarywrap[hidden] { display: none; }
.bar button {
  font: inherit; font-size: 14px; font-weight: 600; padding: 9px 16px; border-radius: 7px;
  cursor: pointer; background: var(--accent); color: var(--sel-fg); border: none;
}
.bar button.secondary { background: var(--chip); color: var(--ink-2); font-weight: 500; }
#copystatus { font-size: 13px; color: var(--ink-2); }
@media (max-width: 620px) {
  .wrap { padding: 18px 13px 80px; }
  header h1 { font-size: 21px; }
  header .intro { font-size: 14px; }
  .count { min-width: 0; flex: 1 1 88px; padding: 7px 9px; }
  .count b { font-size: 17px; }
  /* Keep the sticky bar to one compact strip; on a phone it otherwise eats a third
     of the viewport and hides the row being decided. */
  .bar { padding: 9px 11px; }
  .barhead { flex-wrap: nowrap; gap: 8px; }
  .barhead > b { font-size: 13px; white-space: nowrap; }
  .bar .actions { gap: 6px; flex-wrap: nowrap; }
  .bar button { padding: 7px 10px; font-size: 13px; }
  #copystatus { flex-basis: 100%; font-size: 12px; }
}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>__TITLE__</h1>
  __SUBTITLE__
  __INTRO__
  __AUDIENCE__
  __GLOSSARY__
</header>

<div class="counts" id="counts"></div>
<div class="filters" id="filters"></div>
<main id="rows"></main>

<section class="bar">
  <div class="barhead">
    <b id="progress">Your decisions</b>
    <div class="actions">
      <button id="copy" type="button">Copy summary</button>
      <button id="bulk" type="button" class="secondary" hidden>Take all remaining</button>
      <button id="toggle" type="button" class="secondary" aria-expanded="false" aria-controls="summarywrap">Show text</button>
      <button id="reset" type="button" class="secondary">Clear</button>
      <span id="copystatus" role="status" aria-live="polite"></span>
    </div>
  </div>
  <div id="summarywrap" hidden>
    <p class="hint">__SUMMARY_INTRO__</p>
    <textarea id="summary" readonly aria-label="Decision summary"></textarea>
  </div>
</section>
</div>

<script type="application/json" id="spec">__SPEC_JSON__</script>
<script>
(function () {
  "use strict";
  var SPEC = JSON.parse(document.getElementById("spec").textContent);
  var KEY = "decision-packet:" + SPEC.storage_key;
  var rowsEl = document.getElementById("rows");

  // ---- state -------------------------------------------------------------
  // localStorage can throw outright (private mode, blocked site data), so every
  // access is guarded and the packet stays fully usable with no persistence.
  var state = {};
  var persists = true;
  try {
    state = JSON.parse(localStorage.getItem(KEY) || "{}") || {};
  } catch (e) { state = {}; persists = false; }

  function save() {
    if (!persists) return;
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) { persists = false; }
  }
  function get(id) { return state[id] || {}; }
  function set(id, patch) {
    state[id] = Object.assign({}, get(id), patch);
    save(); render();
  }

  function optionsFor(row) { return row.options || SPEC.options; }
  function labelFor(row, value) {
    var o = optionsFor(row).filter(function (x) { return x.value === value; })[0];
    return o ? o.label : value;
  }
  function decisionOf(row) {
    var s = get(row.id);
    return s.choice !== undefined ? s.choice : null;
  }

  // ---- filters -----------------------------------------------------------
  var active = "all";
  function matches(row) {
    if (active === "all") return true;
    var f = (SPEC.filters || []).filter(function (x) { return x.id === active; })[0];
    if (!f) return true;
    if (f.undecided && decisionOf(row) === null) return true;
    if (f.decided && decisionOf(row) !== null) return true;
    if (f.disagreement && row.disagreement) return true;
    if (f.tags && (row.tags || []).some(function (t) { return f.tags.indexOf(t) >= 0; })) return true;
    if (f.severity && f.severity.indexOf(row.severity) >= 0) return true;
    return false;
  }

  function renderFilters() {
    var host = document.getElementById("filters");
    if (host.childElementCount) return;
    var all = [{ id: "all", label: "All " + SPEC.rows.length }].concat(SPEC.filters || []);
    all.forEach(function (f) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = f.label;
      b.setAttribute("aria-pressed", String(f.id === active));
      b.addEventListener("click", function () { active = f.id; render(); });
      host.appendChild(b);
    });
  }
  function syncFilters() {
    var all = [{ id: "all" }].concat(SPEC.filters || []);
    Array.prototype.forEach.call(document.querySelectorAll("#filters button"), function (b, i) {
      b.setAttribute("aria-pressed", String(all[i].id === active));
    });
  }

  // ---- counts ------------------------------------------------------------
  function renderCounts() {
    var decided = SPEC.rows.filter(function (r) { return decisionOf(r) !== null; }).length;
    var noted = SPEC.rows.filter(function (r) { return (get(r.id).note || "").trim(); }).length;
    var agreed = SPEC.rows.filter(function (r) {
      return r.recommendation && decisionOf(r) === r.recommendation;
    }).length;
    var overridden = SPEC.rows.filter(function (r) {
      var d = decisionOf(r);
      return d !== null && r.recommendation && d !== r.recommendation;
    }).length;
    var cards = [
      ["Items", SPEC.rows.length],
      ["Decided", decided],
      ["Remaining", SPEC.rows.length - decided],
      ["Took the recommendation", agreed],
      ["Overrode it", overridden],
      ["With a note", noted]
    ];
    if (SPEC.rows.some(function (r) { return r.disagreement; })) {
      cards.push(["Disputed", SPEC.rows.filter(function (r) { return r.disagreement; }).length]);
    }
    document.getElementById("counts").innerHTML = cards.map(function (c) {
      return '<div class="count"><b>' + c[1] + "</b><span>" + c[0] + "</span></div>";
    }).join("");
  }

  // ---- rows --------------------------------------------------------------
  function buildRow(row) {
    var el = document.createElement("article");
    el.className = "row";
    el.dataset.sev = row.severity || "none";
    el.dataset.id = row.id;

    var head = '<div class="rid">' + esc(row.id) + "</div>" +
               '<div class="rlabel">' + esc(row.label) + "</div>";
    if (row.context)   head += '<p class="rtext">' + esc(row.context) + "</p>";
    if ((row.tags || []).length) {
      head += '<div class="chips">' + row.tags.map(function (t) {
        return '<span class="chip">' + esc(t) + "</span>";
      }).join("") + "</div>";
    }
    if ((row.links || []).length) {
      head += '<div class="links">' + row.links.map(function (l) {
        return '<a href="' + esc(l.href) + '" target="_blank" rel="noopener">' + esc(l.label) + "</a>";
      }).join(" · ") + "</div>";
    }
    if (row.impact) {
      head += '<div class="impact"><b>If you take the recommendation:</b> ' + esc(row.impact.accept) +
              '<br><b>If you don\u2019t:</b> ' + esc(row.impact.decline) + "</div>";
    }
    if (row.disagreement) {
      var d = row.disagreement;
      head += '<div class="dis"><div class="h">Unresolved disagreement — your call</div>' +
        "<p><b>" + esc(d.a.who) + ":</b> " + esc(d.a.view) + "</p>" +
        "<p><b>" + esc(d.b.who) + ":</b> " + esc(d.b.view) + "</p></div>";
    }
    if (row.reasoning) head += '<p class="rtext reason">' + esc(row.reasoning) + "</p>";
    el.innerHTML = head;

    var opts = document.createElement("div");
    opts.className = "opts";
    optionsFor(row).forEach(function (o) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = o.label;
      b.dataset.tone = o.tone || "info";
      b.dataset.value = o.value;
      if (row.recommendation === o.value) {
        b.dataset.recommended = "true";
        b.title = "The agent recommends this";
      }
      b.addEventListener("click", function () {
        // An individual click always clears the bulk flag: touching a row IS
        // considering it, and the record must not keep calling it a bulk accept.
        set(row.id, {
          choice: decisionOf(row) === o.value ? undefined : o.value,
          bulk: false
        });
      });
      opts.appendChild(b);
    });
    if (row.recommendation) {
      var hint = document.createElement("span");
      hint.className = "rec";
      hint.textContent = "recommended: " + labelFor(row, row.recommendation);
      opts.appendChild(hint);
    }
    el.appendChild(opts);

    var note = document.createElement("div");
    note.className = "note";
    var ta = document.createElement("textarea");
    ta.rows = 1;
    ta.placeholder = "Anything the buttons cannot say…";
    ta.value = get(row.id).note || "";
    ta.setAttribute("aria-label", "Note on " + row.id);
    ta.addEventListener("input", function () {
      state[row.id] = Object.assign({}, get(row.id), { note: ta.value });
      save(); renderCounts(); renderSummary();
    });
    note.appendChild(ta);
    el.appendChild(note);
    return el;
  }

  function render() {
    renderFilters(); syncFilters(); renderCounts();
    if (!rowsEl.childElementCount) {
      SPEC.rows.forEach(function (r) { rowsEl.appendChild(buildRow(r)); });
    }
    SPEC.rows.forEach(function (r) {
      var el = rowsEl.querySelector('[data-id="' + cssEsc(r.id) + '"]');
      if (!el) return;
      el.hidden = !matches(r);
      var d = decisionOf(r);
      el.dataset.decided = d === null ? "no" : "yes";
      Array.prototype.forEach.call(el.querySelectorAll(".opts button"), function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.value === d));
      });
    });
    renderSummary();
  }

  // ---- summary -----------------------------------------------------------
  function renderSummary() {
    var lines = [SPEC.title, "=".repeat(SPEC.title.length), ""];
    var decided = 0;
    SPEC.rows.forEach(function (r) {
      var s = get(r.id), d = s.choice !== undefined ? s.choice : null;
      if (d !== null) decided++;
      var mark = d === null ? "— not yet decided" : labelFor(r, d);
      if (d !== null && r.recommendation) {
        if (d !== r.recommendation) {
          mark += "  (OVERRODE: recommended " + labelFor(r, r.recommendation) + ")";
        } else {
          // A bulk acceptance is a different fact from an individual one, and the
          // agent reading this paste must not read the first as the second.
          mark += s.bulk ? "  (accepted in bulk)" : "  (took the recommendation)";
        }
      }
      lines.push(r.id + "  " + r.label);
      lines.push("    -> " + mark);
      if ((s.note || "").trim()) lines.push("    note: " + s.note.trim());
      lines.push("");
    });
    lines.push("Decided " + decided + " of " + SPEC.rows.length + ".");
    var bulk = SPEC.rows.filter(function (r) { return get(r.id).bulk; }).length;
    if (bulk) {
      lines.push(bulk + " of those were accepted in bulk rather than considered one by one — " +
                 "weight them accordingly.");
    }
    if (!persists) lines.push("(This browser blocked local storage, so nothing was saved between sittings.)");
    document.getElementById("summary").value = lines.join("\\n");
    document.getElementById("progress").textContent =
      decided + " of " + SPEC.rows.length + " decided";

    // The bulk control exists so that a genuinely routine set (forty patch bumps) does
    // not cost forty considered clicks. It is deliberately NOT a default state: an
    // affirmative, labelled gesture leaves an honest record, whereas a pre-selected
    // recommendation would make "I agreed" indistinguishable from "I never looked".
    var remaining = SPEC.rows.filter(function (r) {
      return r.recommendation && decisionOf(r) === null;
    }).length;
    var bulkBtn = document.getElementById("bulk");
    bulkBtn.hidden = remaining === 0;
    bulkBtn.textContent = "Take all remaining (" + remaining + ")";
  }

  function revealSummary() {
    var wrap = document.getElementById("summarywrap");
    var btn = document.getElementById("toggle");
    wrap.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    btn.textContent = "Hide text";
  }

  // ---- copy --------------------------------------------------------------
  // Order matters and is load-bearing. Selecting FIRST guarantees a manual
  // Cmd/Ctrl+C always works, even when both programmatic paths are blocked —
  // as they are inside a sandboxed artifact iframe with no clipboard-write
  // permission. A copy control that fails silently is a bug; this one always
  // says which path it took.
  function copySummary() {
    var ta = document.getElementById("summary");
    var status = document.getElementById("copystatus");
    // A hidden textarea cannot be selected, and selection is the fallback that always
    // works — so reveal before doing anything else.
    revealSummary();
    ta.removeAttribute("readonly");
    ta.focus(); ta.select();
    try { ta.setSelectionRange(0, ta.value.length); } catch (e) {}
    ta.setAttribute("readonly", "");

    // Say something SYNCHRONOUSLY. The async clipboard path below may resolve late or
    // never, and an empty status in the meantime is exactly the silent failure this
    // control exists to avoid. Every later branch overwrites this line.
    status.textContent = "Selected — copying…";

    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    if (ok) { status.textContent = "Copied. Paste it back in one message."; return; }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(ta.value).then(function () {
        status.textContent = "Copied. Paste it back in one message.";
      }, function () {
        status.textContent = "This browser blocked copying — the text is selected, so press " +
          (navigator.platform.indexOf("Mac") >= 0 ? "Cmd+C" : "Ctrl+C") + ".";
      });
      return;
    }
    status.textContent = "This browser blocked copying — the text is selected, so press " +
      (navigator.platform.indexOf("Mac") >= 0 ? "Cmd+C" : "Ctrl+C") + ".";
  }

  document.getElementById("copy").addEventListener("click", copySummary);
  document.getElementById("bulk").addEventListener("click", function () {
    var pending = SPEC.rows.filter(function (r) {
      return r.recommendation && decisionOf(r) === null;
    });
    if (!pending.length) return;
    if (!window.confirm(
      "Accept the recommendation on " + pending.length + " remaining item" +
      (pending.length === 1 ? "" : "s") + " without deciding them individually?\\n\\n" +
      "They will be marked as accepted in bulk in the summary, so the difference stays visible."
    )) return;
    pending.forEach(function (r) {
      state[r.id] = Object.assign({}, get(r.id), { choice: r.recommendation, bulk: true });
    });
    save(); render();
    document.getElementById("copystatus").textContent =
      pending.length + " accepted in bulk.";
  });

  document.getElementById("toggle").addEventListener("click", function () {
    var wrap = document.getElementById("summarywrap");
    if (wrap.hidden) { revealSummary(); return; }
    wrap.hidden = true;
    this.setAttribute("aria-expanded", "false");
    this.textContent = "Show text";
  });
  document.getElementById("reset").addEventListener("click", function () {
    if (!window.confirm("Clear every saved answer in this packet?")) return;
    state = {};
    try { localStorage.removeItem(KEY); } catch (e) {}
    rowsEl.innerHTML = "";
    document.getElementById("copystatus").textContent = "Cleared.";
    render();
  });

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function cssEsc(s) { return String(s).replace(/["\\\\]/g, "\\\\$&"); }

  render();
})();
</script>
</body>
</html>
"""


def build(spec: dict) -> str:
    title = str(spec["title"])
    sub = spec.get("subtitle")
    intro = spec.get("intro")
    spec = dict(spec)
    spec.setdefault("storage_key", slugify(title))
    spec.setdefault("filters", [])

    payload = json.dumps(spec, ensure_ascii=False)
    # A literal "</script>" inside the JSON would close the host block early.
    payload = payload.replace("</", "<\\/")

    out = TEMPLATE
    out = out.replace("__TITLE__", html.escape(title))
    out = out.replace("__SUBTITLE__", f'<p class="sub">{html.escape(str(sub))}</p>' if sub else "")
    out = out.replace("__INTRO__", f'<p class="intro">{html.escape(str(intro))}</p>' if intro else "")
    aud = spec.get("audience")
    out = out.replace("__AUDIENCE__",
                      f'<p class="aud">Written for: {html.escape(str(aud))}</p>' if aud else "")
    gl = spec.get("glossary") or []
    if gl:
        items = "".join(
            f"<dt>{html.escape(str(g['term']))}</dt><dd>{html.escape(str(g['meaning']))}</dd>"
            for g in gl if isinstance(g, dict))
        out = out.replace(
            "__GLOSSARY__",
            f'<details class="gloss"><summary>Terms used below ({len(gl)})</summary><dl>{items}</dl></details>')
    else:
        out = out.replace("__GLOSSARY__", "")
    out = out.replace(
        "__SUMMARY_INTRO__",
        html.escape(str(spec.get("summary_intro")
                        or "Work through the rows, then copy this and paste it back in one message.")),
    )
    out = out.replace("__SPEC_JSON__", payload)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="path to the JSON spec ('-' for stdin)")
    ap.add_argument("-o", "--out", help="output .html path")
    ap.add_argument("--stdout", action="store_true", help="write the HTML to stdout")
    ap.add_argument("--schema", action="store_true", help="print the spec schema and exit")
    ap.add_argument("--allow-small", action="store_true",
                    help="build even with fewer than five rows (see the anti-trigger)")
    ap.add_argument("--strict-reader", action="store_true",
                    help="make reader-contract findings (missing audience/impact) fatal; "
                         "SKILL.md requires this for packets handed to a principal")
    args = ap.parse_args()

    if args.schema:
        print(SCHEMA)
        return 0
    if not args.spec:
        ap.error("a spec path is required (or --schema)")

    raw = sys.stdin.read() if args.spec == "-" else pathlib.Path(args.spec).read_text(encoding="utf-8")
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"spec is not valid JSON: {exc}", file=sys.stderr)
        return 2

    problems = validate(spec)
    hard = [p for p in problems if not p.startswith(("NOTE:", "READER:"))]
    soft = [p for p in problems if p.startswith("NOTE:")]
    reader = [p for p in problems if p.startswith("READER:")]
    for p in soft + reader:
        print(p, file=sys.stderr)
    if soft and not args.allow_small:
        hard.append("refusing to build a sub-five-row packet without --allow-small")
    if reader and args.strict_reader:
        hard.append("reader contract unmet (--strict-reader): see READER findings above")
    if hard:
        print("\nwill not build:", file=sys.stderr)
        for p in hard:
            print("  - " + p, file=sys.stderr)
        return 2

    out = build(spec)
    if args.stdout or not args.out:
        sys.stdout.write(out)
    else:
        dest = pathlib.Path(args.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out, encoding="utf-8")
        print(f"{dest}  ({len(out):,} bytes, {len(spec['rows'])} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

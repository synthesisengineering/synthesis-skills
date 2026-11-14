#!/usr/bin/env python3
"""Build a self-contained action-sheet page from a JSON spec.

An action sheet is one page of what the principal still has to do after the agents did
their part: what was done for them (folded away), the staged sends that wait for their
approval code, and the actions only they can take. Each action carries its exact text,
Copy, a link that opens the conversation or the place, Mark done / Skip / Not now, a
note and, where an agent may do it, a choice of who does it. The page writes a summary
the principal pastes back; record_actions.py files it.

    python3 build_sheet.py --schema                     # print the spec format
    python3 build_sheet.py spec.json -o sheet.html      # a working copy
    python3 build_sheet.py spec.json --stdout > sheet.html
    python3 build_sheet.py spec.json --file-into PROJECT/resources/artifacts/ [--date YYYY-MM-DD]

The page engine is the decision packet's: strict spec reading, the canonical digest that
keys saved marks and binds the paste, filing and the integrity marker come from
../../synthesis-decision-packet/scripts/build_packet.py. Links are built here from the
address and the exact text; only https, sms, mailto and tel links are ever emitted.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import pathlib
import re
import sys
import urllib.parse

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
ENGINE = pathlib.Path(__file__).resolve().parents[2] / "synthesis-decision-packet" / "scripts"
sys.path.insert(0, str(ENGINE))
try:
    from build_packet import (canonical_spec_bytes, file_packet, parse_iso_date, slugify,  # noqa: F401
                              spec_digest, strict_json, write_preserved)
except ImportError as exc:  # the sheet has no engine of its own: fail closed, naming what is missing
    raise SystemExit(f"synthesis-action-sheet needs synthesis-decision-packet beside it "
                     f"({ENGINE / 'build_packet.py'}): {exc}")

ASSETS = pathlib.Path(__file__).resolve().parents[1] / "assets"
MAX_SPEC_BYTES = MAX_HTML_BYTES = 8_388_608
MAX_TEXT_BYTES = 32_768
# Approval codes stay in chat. The prompt hook grants every pending code a prompt carries, so a
# page or summary holding one would approve a send when the principal pastes the summary back.
APPROVAL_CODE = re.compile(r"(?i)\bapprove\s+\d[0-9a-f]{5}\b")  # the shape the guard issues; "approve budget" is prose
CODE_FIELD = re.compile(r"(?i)codes?$")
E164 = re.compile(r"\+[1-9][0-9]{6,14}")
EMAIL = re.compile(r"[^@\s,;:<>()\[\]\"]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
CHANNELS = {"whatsapp": "WhatsApp", "imessage": "iMessage", "sms": "SMS", "linkedin": "LinkedIn",
            "email": "Email", "call": "Phone call", "web": "Web", "task": "Task", "slack": "Slack",
            "teams": "Teams", "github": "GitHub", "calendar": "Calendar invite"}
MESSAGE = {"whatsapp", "imessage", "sms", "linkedin", "email"}
PHONE = {"whatsapp", "imessage", "sms", "call"}
SECTION_CHANNELS = {"approve": MESSAGE | {"slack", "teams", "github", "calendar"},
                    "do": MESSAGE | {"call", "web", "task"}}
RISKS = {"money", "security", "credentials", "identity"}
SCHEMES = {"https", "sms", "mailto", "tel"}
LINKEDIN_HOSTS = {"www.linkedin.com", "linkedin.com"}
FIELDS = {"spec": {"title", "date", "intro", "audience", "storage_key", "summary_intro", "carried_from",
                   "done", "approve", "do"},
          "done": {"kind", "label", "href"},
          "approve": {"id", "channel", "who", "label", "address", "subject", "why", "text"},
          "do": {"id", "channel", "who", "label", "address", "subject", "why", "text", "href", "agent", "risk"}}
LINE_BREAKS = "\r\n\x0b\x0c\x85\u2028\u2029"
# Every word of the pasted summary, in one place: the page reads it from its embedded spec,
# and record_actions.py rebuilds the paste from it, so the two cannot drift apart.
SUMMARY = {
    "headings": {"approve": "To approve", "do": "To do"},
    "status_prefix": "    -> ", "note_prefix": "    note: ",
    "approve": {"open": "waiting for your code", "skipped": "do not send", "not-now": "not now"},
    "do": {"open": "open", "me": "open, you do it", "agent": "the agent does it", "done": "done",
           "skipped": "skipped", "not-now": "not now"},
    "counts": {"approve": [[["open"], "waiting for your code"], [["skipped"], "not to send"], [["not-now"], "not now"]],
               "do": [[["done"], "done"], [["agent"], "for the agent"], [["me", "open"], "open"],
                      [["not-now"], "not now"], [["skipped"], "skipped"]]},
    "storage": "(This browser blocked local storage, so nothing was saved between sittings.)",
    "binding": "Action sheet binding v1: ",
}


def _one_line(value, limit=512) -> bool:
    """One line with no edge whitespace: the summary prints these fields whole on one line."""
    return (isinstance(value, str) and bool(value) and value == value.strip() and len(value.encode("utf-8")) <= limit
            and not any(ord(c) < 32 or ord(c) == 127 or c in LINE_BREAKS for c in value))


def _prose(value, limit=4096) -> bool:
    return (isinstance(value, str) and bool(value.strip()) and len(value.encode("utf-8")) <= limit
            and not any((ord(c) < 32 and c not in "\n\r\t") or ord(c) == 127 for c in value))


def _code_problems(value, where="spec") -> list:
    """No field named for a code and no value shaped like one, anywhere in the spec."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            named = not isinstance(key, str) or CODE_FIELD.search(key) or APPROVAL_CODE.search(key)
            if named:
                found.append(f"{where} has a field named for an approval code")
            found += _code_problems(item, f"{where}.<that field>" if named else f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += _code_problems(item, f"{where}[{index}]")
    elif isinstance(value, str) and APPROVAL_CODE.search(value):
        found.append(f"{where} holds text shaped like an approval code (approve, then a digit and five hex characters)")
    return found


def link_problem(href, *, relative=False, hosts=None, plain=False) -> str:
    """Why an author's link is refused ("" when it is accepted): https only, or a relative path."""
    if not _one_line(href, 2048) or any(c.isspace() or c == "\\" for c in href):
        return "must be one line with no spaces or backslashes"
    try:
        url = urllib.parse.urlsplit(href)
        port = url.port
    except ValueError:
        return "is not a valid link"
    if relative and not url.scheme and not url.netloc:
        return ""
    if url.scheme != "https" or not url.hostname or url.username or url.password or port not in (None, 443):
        return "must be an https:// link" + (" or a relative path" if relative else "")
    if hosts and url.hostname.lower() not in hosts:
        return "must point at " + " or ".join(sorted(hosts))
    if plain and (url.query or url.fragment):
        return "of a money, security, credentials or identity task opens the place, never a filled-in form: drop its query and fragment"
    return ""


def _address_problem(row: dict, section: str) -> str:
    channel, address = row["channel"], row.get("address")
    if channel in PHONE:
        if not (isinstance(address, str) and E164.fullmatch(address)):
            return ("needs 'address' as an E.164 number such as +15555550123: a plus, the country code, then the "
                    "digits, with no spaces or punctuation")
    elif channel == "email":
        if not (_one_line(address) and all(EMAIL.fullmatch(a.strip()) for a in address.split(","))):
            return "needs 'address': one email address, or several separated by commas"
    elif "address" in row and (section == "do" or not _one_line(address)):
        return ("takes no 'address': a LinkedIn row takes its conversation in 'href'" if channel == "linkedin" else
                "takes no 'address'" if section == "do" else "address must be a one-line string")
    return ""


def _row_problems(row, section: str, index: int) -> list:
    if not isinstance(row, dict):
        return [f"{section}[{index}] must be an object"]
    rid, channel = row.get("id"), row.get("channel")
    at = f"{section}[{index}] ({rid})" if isinstance(rid, str) else f"{section}[{index}]"
    problems = []
    if set(row) - FIELDS[section]:
        problems.append(f"{at} has unknown fields {sorted(set(row) - FIELDS[section])}; {section} rows take "
                        f"{sorted(FIELDS[section])}")
    if not _one_line(rid, 128) or "  " in rid:
        problems.append(f"{at} id must be a one-line string without leading, trailing or doubled spaces: it keys "
                        'saved marks, and the pasted summary prints "id  name" on one line')
    if not isinstance(channel, str) or channel not in SECTION_CHANNELS[section]:
        return problems + [f"{at} channel {channel!r} is not one of {sorted(SECTION_CHANNELS[section])}"]
    problems += [f"{at} {key} must be a non-empty one-line string" for key in ("who", "label", "subject")
                 if key in row and not _one_line(row[key])]
    if "who" not in row and (section == "approve" or channel in MESSAGE or channel == "call"):
        problems.append(f"{at} needs 'who': the person the {CHANNELS[channel]} goes to")
    if "label" not in row and channel in ("web", "task"):
        problems.append(f"{at} needs 'label': what to do, in one line")
    if not _prose(row.get("why")):
        problems.append(f"{at} needs 'why': a sentence or two on why it matters now")
    if "text" in row and not _prose(row["text"], MAX_TEXT_BYTES):
        problems.append(f"{at} text must be non-empty, at most {MAX_TEXT_BYTES:,} bytes, with no control characters")
    elif "text" not in row and (section == "approve" or channel in MESSAGE):
        problems.append(f"{at} is a message and needs its exact 'text', the words that go out")
    why = _address_problem(row, section)
    problems += [f"{at} {why}"] if why else []
    if section == "approve":
        return problems
    risk, agent = row.get("risk"), row.get("agent")
    if "risk" in row and not (isinstance(risk, str) and risk in RISKS):
        problems.append(f"{at} risk {risk!r} is not one of {sorted(RISKS)}")
    if "href" in row:
        if channel in PHONE or channel == "email":
            problems.append(f"{at} takes no 'href': its link is built from 'address' and 'text'")
        else:
            why = link_problem(row["href"], hosts=LINKEDIN_HOSTS if channel == "linkedin" else None, plain="risk" in row)
            problems += [f"{at} href {why}"] if why else []
    elif channel == "web":
        problems.append(f"{at} needs 'href': the https:// page where it is done")
    if agent not in ("can", "never"):
        problems.append(f"{at} agent must be 'can' or 'never': say whether an agent may do this row for the principal")
    elif agent == "can":
        problems += [f"{at} {why}" for ok, why in (
            ("risk" not in row, f"is a {risk} task, which an agent never does: set agent to 'never'"),
            ("text" in row, "has no exact text, and an agent does only what has exact text: add it or set agent to 'never'"),
            (channel != "call", "is a call, a conversation rather than exact text: set agent to 'never'"),
            (channel != "email", "is email, which the agent sends through the guard: stage it and list it under 'approve'"))
            if not ok]
    return problems


def validate(spec) -> list:
    """Every reason the spec cannot become a sheet; an empty list means it can."""
    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    codes = _code_problems(spec)
    if codes:  # nothing else is checked, so no message can repeat a code
        return codes + ["approval codes go in chat as one line; never put one in a spec, a page or a file"]
    problems = []
    try:
        canonical_spec_bytes(spec)
    except (TypeError, ValueError):  # includes an unpaired surrogate from a JSON escape
        problems.append("spec contains a value that is not valid JSON text")
    if set(spec) - FIELDS["spec"]:
        problems.append(f"unknown top-level fields {sorted(set(spec) - FIELDS['spec'])}; a sheet takes "
                        f"{sorted(FIELDS['spec'])}")
    if not _one_line(spec.get("title"), 200):
        problems.append("title must be a non-empty one-line string of at most 200 bytes")
    if "date" in spec and parse_iso_date(spec["date"]) is None:
        problems.append(f"date {spec['date']!r} is not a calendar date in YYYY-MM-DD form")
    problems += [f"{key} must be non-empty text" for key in ("intro", "audience", "summary_intro")
                 if key in spec and not _prose(spec[key])]
    problems += [f"{key} must be a one-line string" for key in ("storage_key", "carried_from")
                 if key in spec and not _one_line(spec[key])]
    done = spec.get("done", [])
    if not isinstance(done, list) or len(done) > 200:
        problems.append("done must be a list of at most 200 {kind, label, href} items")
        done = []
    for index, item in enumerate(done):
        if not (isinstance(item, dict) and set(item) <= FIELDS["done"] and _one_line(item.get("kind"), 64)
                and _one_line(item.get("label"))):
            problems.append(f"done[{index}] needs a one-line kind (such as 'emails sent') and label, and an optional href")
        elif "href" in item and link_problem(item["href"], relative=True):
            problems.append(f"done[{index}] href {link_problem(item['href'], relative=True)}")
    seen, rows = set(), 0
    for section in ("approve", "do"):
        listed = spec.get(section, [])
        if not isinstance(listed, list) or len(listed) > 100:
            problems.append(f"{section} must be a list of at most 100 rows")
            continue
        rows += len(listed)
        for index, row in enumerate(listed):
            problems += _row_problems(row, section, index)
            rid = row.get("id") if isinstance(row, dict) else None
            if isinstance(rid, str) and rid in seen:
                problems.append(f"{section}[{index}] duplicate id {rid!r}: ids key saved marks and must be unique "
                                "across the whole sheet")
            if isinstance(rid, str):
                seen.add(rid)
    if not rows:
        problems.append("nothing to approve or do: say what was done in chat instead of building a sheet")
    return problems


def row_name(row: dict) -> str:
    """The row's one-line name in the summary: its label, else "<Channel> to <who>"."""
    return row.get("label") or f"{CHANNELS[row['channel']]} to {row['who']}"


def _enc(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def open_link(row: dict):
    """The Open link a Do row shows, {"href", "label", "custom"}, or None when its channel has none.
    A money, security, credentials or identity row never gets its text in the link."""
    channel, plain = row["channel"], "risk" in row
    text = None if plain else row.get("text")
    if channel == "whatsapp":  # WhatsApp's click to chat: the number's digits, then the URL-encoded text
        href = "https://wa.me/" + row["address"][1:] + ("?text=" + _enc(text) if text else "")
        label = "Open WhatsApp with the text" if text else "Open the WhatsApp chat"
    elif channel in ("imessage", "sms"):  # the form iPhones read; Apple documents only sms:<number>
        href = "sms:" + row["address"] + ("&body=" + _enc(text) if text else "")
        label = "Open Messages with the text" if text else "Open Messages"
    elif channel == "linkedin":  # LinkedIn has no prefill: the conversation, else the inbox
        href = row.get("href") or "https://www.linkedin.com/messaging/"
        label = "Open the LinkedIn conversation" if "href" in row else "Open LinkedIn messages"
    elif channel == "email":  # a fallback: the agent sends email itself, through the guard
        body = text and re.sub(r"\r\n|\r|\n", "\r\n", text)
        query = [] if plain else [(k, v) for k, v in (("subject", row.get("subject")), ("body", body)) if v]
        href = ("mailto:" + ",".join(urllib.parse.quote(a.strip(), safe="@'+") for a in row["address"].split(","))
                + ("?" + "&".join(f"{k}={_enc(v)}" for k, v in query) if query else ""))
        label = "Open in Mail (fallback)"
    elif channel == "call":
        href, label = "tel:" + row["address"], "Call " + row["address"]
    elif "href" in row:  # web and task: the place itself, nothing filled in
        href, label = row["href"], "Open " + urllib.parse.urlsplit(row["href"]).hostname
    else:
        return None
    scheme = urllib.parse.urlsplit(href).scheme.lower()
    if scheme not in SCHEMES:  # defense in depth: the checks above admit nothing else
        raise ValueError(f"refusing to emit a {scheme or 'relative'} link for row {row['id']!r}")
    return {"href": href, "label": label, "custom": scheme != "https"}


def page_spec(spec: dict) -> dict:
    """The spec as the page embeds it: rows with their names and built links, and the summary's words."""
    page = dict(spec, storage_key=spec.get("storage_key") or slugify(spec["title"]), format=SUMMARY)
    page["approve"] = [dict(row, name=row_name(row)) for row in spec.get("approve", [])]
    page["do"] = [dict(row, name=row_name(row), open=open_link(row)) for row in spec.get("do", [])]
    return page


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _head(row: dict) -> str:
    meta = [("To", row["who"])] if row.get("label") and row.get("who") else []
    meta += [("Number" if row["channel"] in PHONE else "Address", row["address"])] if "address" in row else []
    meta += [("Subject", row["subject"])] if "subject" in row else []
    return (f'<div class="head"><h3>{_e(row.get("label") or row["who"])}</h3>'
            f'<span class="chip">{_e(CHANNELS[row["channel"]])}</span><span class="pill" aria-live="polite"></span>'
            f'<span class="rid">{_e(row["id"])}</span></div>'
            + ('<dl class="meta">' + "".join(f"<dt>{k}</dt><dd>{_e(v)}</dd>" for k, v in meta) + "</dl>" if meta else "")
            + f'<p class="why">{_e(row["why"])}</p>'
            + (f'<p class="text">{_e(row["text"])}</p>' if "text" in row else ""))


def _note(row: dict) -> str:
    return (f'<textarea class="note" rows="1" placeholder="Anything to tell the agent about this one" '
            f'aria-label="Note on {_e(row["id"])}"></textarea><p class="notewarn" hidden>Approval codes go in chat, '
            'not in a note: a note that holds one is refused when the summary is filed.</p>'
            '<p class="rowstatus" role="status" aria-live="polite"></p>')


def _approve_card(row: dict, index: int) -> str:
    return (f'<article class="card" data-row="{index}" data-section="approve">' + _head(row)
            + '<p class="waits">Waits for your approval code. The codes are in chat, on one line; this page never '
            'holds them.</p><div class="marks" role="group" aria-label="Mark this send">'
            '<button type="button" data-mark="skipped" aria-pressed="false">Don’t send it</button>'
            '<button type="button" data-mark="not-now" aria-pressed="false">Not now</button></div>'
            + _note(row) + "</article>")


def _hint(row: dict, link) -> str:
    hints = [f"Only you do this {row['risk']} task" + (", and its link opens the place with nothing filled in."
                                                         if link else ".")] if "risk" in row else []
    if row["channel"] == "linkedin":
        hints.append("LinkedIn cannot fill in a message: copy the text, open the conversation, paste and send.")
    elif row["channel"] == "email":
        hints.append("The agent normally sends email itself; this opens your mail app as a fallback.")
    elif link and link["custom"]:
        hints.append("If nothing opens (the claude.ai viewer can block Messages, phone and mail links), copy the "
                     + ("number above." if "text" not in row else "text and use the number above."))
    return " ".join(hints)


def _do_card(row: dict, index: int) -> str:
    link, tools = row["open"], []
    if link:
        target = "" if link["custom"] else ' target="_blank" rel="noopener noreferrer"'
        tools.append(f'<a class="btn primary" href="{_e(link["href"])}"{target}>{_e(link["label"])}</a>')
    if "text" in row:
        tools.append('<button type="button" class="btn" data-copy="text">Copy text</button>')
    who = ""
    if row["agent"] == "can":
        does = (f"Sends exactly this text to {row['who']} on {CHANNELS[row['channel']]}" if row["channel"] in MESSAGE
                else "Does exactly this, with this text")
        who = ('<div class="who" role="group" aria-label="Who does it"><span class="lab">Who does it</span>'
               '<button type="button" data-who="me" aria-pressed="false">Me</button><button type="button" '
               f'data-who="agent" aria-pressed="false">Agent<span class="conseq">{_e(does)}</span></button></div>')
    hint = _hint(row, link)
    return (f'<article class="card" data-row="{index}" data-section="do">' + _head(row)
            + (f'<div class="tools">{"".join(tools)}</div>' if tools else "")
            + (f'<p class="hint">{_e(hint)}</p>' if hint else "") + who
            + '<div class="marks" role="group" aria-label="Mark this row">'
            '<button type="button" data-mark="done" aria-pressed="false">Mark done</button>'
            '<button type="button" data-mark="skipped" aria-pressed="false">Skip</button>'
            '<button type="button" data-mark="not-now" aria-pressed="false">Not now</button></div>'
            + _note(row) + "</article>")


def _done(items: list) -> str:
    groups = {}
    for item in items:  # by kind, in the order the kinds first appear
        groups.setdefault(item["kind"], []).append(item)

    def entry(item):
        if "href" not in item:
            return _e(item["label"])
        external = ' target="_blank" rel="noopener noreferrer"' if item["href"].lower().startswith("https:") else ""
        return f'<a href="{_e(item["href"])}"{external}>{_e(item["label"])}</a>'
    kinds = " · ".join(f"{len(group)} {kind}" for kind, group in groups.items())
    body = "".join(f'<section><h3>{_e(kind)} <span class="n">{len(group)}</span></h3><ul>'
                   + "".join(f"<li>{entry(i)}</li>" for i in group) + "</ul></section>" for kind, group in groups.items())
    return (f'<details class="done" id="done"><summary><b>Done for you</b> <span class="n">{len(items)}</span> '
            f'<span class="kinds">{_e(kinds)}</span></summary><div class="done-body">{body}</div></details>')


def _section(key: str, title: str, lede: str, cards: list) -> str:
    return (f'<section class="group" id="{key}" aria-labelledby="{key}-h"><h2 id="{key}-h">{title} '
            f'<span class="n">{len(cards)}</span></h2><p class="lede">{lede}</p>{"".join(cards)}</section>')


def build(spec: dict) -> str:
    """The page for a valid spec, carrying the integrity marker (keep its exact form)."""
    problems = validate(spec)
    if problems:
        raise ValueError("invalid spec: " + "; ".join(problems))
    page_data = page_spec(spec)
    # Escaping every "<" keeps spec text such as "</script>" from ending the script block.
    payload = json.dumps(page_data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    approve, do, done = page_data["approve"], page_data["do"], spec.get("done", [])
    when = parse_iso_date(spec.get("date"))
    day = datetime.date.fromisoformat(when) if when else None
    counts = [("Done for you", len(done)), ("To approve", len(approve)), ("To do", len(do))]
    fields = {
        "__TITLE__": _e(spec["title"]), "__SPEC_JSON__": payload, "__CANONICAL_SPEC_SHA256__": spec_digest(spec),
        "__DATELINE__": f'<p class="date">{day:%A}, {day:%B} {day.day}, {day.year}</p>' if day else "",
        "__INTRO__": f'<p class="intro">{_e(spec["intro"])}</p>' if spec.get("intro") else "",
        "__AUDIENCE__": f'<p class="aud">Written for: {_e(spec["audience"])}</p>' if spec.get("audience") else "",
        "__COUNTS__": "".join(f'<div class="count"><b>{n}</b><span>{label}</span></div>' for label, n in counts),
        "__DONE__": _done(done) if done else "",
        "__APPROVE__": _section("approve", "Approve", "Each send below is staged and waits for your approval code. "
                                "Paste the codes line from chat to send them; mark any you want held.",
                                [_approve_card(row, i) for i, row in enumerate(approve)]) if approve else "",
        "__DO__": _section("do", "Do", "Yours to do. Copy the text, open the conversation, send it, then mark it done. "
                           "Where an agent may do it instead, choose Agent.",
                           [_do_card(row, len(approve) + i) for i, row in enumerate(do)]) if do else "",
        "__SUMMARY_INTRO__": _e(spec.get("summary_intro") or "When you are through, copy this and paste it back in "
                                "one message. Rows you did not mark come back on the next sheet."),
    }
    template = (ASSETS / "sheet-template.html").read_text(encoding="utf-8")
    empty = [re.escape(k) for k, v in fields.items() if not v]
    if empty:  # an empty placeholder takes its whole line with it
        template = re.sub(r"(?m)^[ \t]*(?:%s)\n" % "|".join(empty), "", template)
    # One substitution pass, so spec text that contains a placeholder stays text.
    page = re.sub("|".join(map(re.escape, fields)), lambda m: fields[m.group()], template)
    marker = f"<!-- synthesis-action-sheet spec-sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()} -->\n"
    head, sep, tail = page.partition("</title>\n")
    if not sep:
        raise RuntimeError("sheet template lost its </title> line")
    page = head + sep + marker + tail
    if len(page.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("generated sheet exceeds the 8 MiB page limit")
    return page


def file_sheet(spec: dict, page: str, directory: pathlib.Path, date: str) -> tuple:
    """File <date>-<slug>-spec.json and <date>-<slug>.html as the packet files its pages."""
    return file_packet(spec, page, directory, date)


def read_spec(source: str) -> dict:
    raw = sys.stdin.buffer.read(MAX_SPEC_BYTES + 1) if source == "-" else pathlib.Path(source).read_bytes()
    if len(raw) > MAX_SPEC_BYTES:
        raise ValueError("spec exceeds 8 MiB")
    return strict_json(raw.decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("spec", nargs="?", help="path to the JSON spec ('-' for stdin)")
    ap.add_argument("-o", "--out", help="write the page to this path (a working copy; it is overwritten)")
    ap.add_argument("--stdout", action="store_true", help="write the page to stdout")
    ap.add_argument("--schema", action="store_true", help="print the spec format and exit")
    ap.add_argument("--file-into", metavar="DIR", type=pathlib.Path,
                    help="file <date>-<slug>-spec.json and <date>-<slug>.html into DIR, the owning project's "
                         "existing resources/artifacts/ directory")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="the date in the filed names (default: today)")
    args = ap.parse_args()
    if args.schema:
        print((ASSETS / "spec-schema.txt").read_text(encoding="utf-8"), end="")
        return 0
    if not args.spec:
        ap.error("a spec path is required (or --schema)")
    if args.date and not args.file_into:
        ap.error("--date requires --file-into")
    if args.date and parse_iso_date(args.date) is None:
        ap.error(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
    if args.file_into and not args.file_into.is_dir():
        print(f"--file-into: {args.file_into} is not an existing directory - pass the owning project's "
              "resources/artifacts/ directory and create it first", file=sys.stderr)
        return 2
    try:
        spec = read_spec(args.spec)
    except (OSError, ValueError) as exc:
        print(f"cannot read valid spec JSON: {exc}", file=sys.stderr)
        return 2
    problems = validate(spec)
    if problems:
        print("will not build:\n" + "\n".join("  - " + p for p in problems), file=sys.stderr)
        return 2
    try:
        page, reports = build(spec), []
        shape = (f"{len(spec.get('approve', []))} to approve, {len(spec.get('do', []))} to do, "
                 f"{len(spec.get('done', []))} done for you")
        if args.out:
            dest = pathlib.Path(args.out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(page, encoding="utf-8")
            reports.append(f"wrote {dest}  ({len(page.encode('utf-8')):,} bytes; {shape})")
        if args.file_into:
            date = args.date or datetime.date.today().isoformat()
            reports += [f"filed {p}" for p in file_sheet(spec, page, args.file_into, date)]
    except (OSError, ValueError) as exc:
        print(f"sheet build refused: {exc}", file=sys.stderr)
        return 2
    if args.stdout or not (args.out or args.file_into):
        sys.stdout.write(page)
    for message in reports:
        print(message, file=sys.stderr if args.stdout else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

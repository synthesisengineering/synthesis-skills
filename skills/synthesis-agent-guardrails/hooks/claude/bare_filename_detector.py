#!/usr/bin/env python3
"""Stop hook: catch filenames mentioned in a response that are not clickable links.

The project instructions carry the rule as ABSOLUTE — "every file referenced in a chat
response is a markdown link with the full absolute path" — and the rule still failed
repeatedly when responses named bare strings that the principal could not resolve. The
principal's demand is the specification for this hook: make every file mentioned in a
response a hyperlink, permanently, with no excuses about why that is not possible.

A prose rule the agent must remember is a rule the agent forgets under load. This is the
safety net, built on the same Stop-hook shape as lazy_shortcut_detector.py.

WHAT COUNTS AS A VIOLATION
  A token that looks like a filename or a path segment and is NOT already inside a markdown
  link target. Bare `foo.md`, `resources/scripts/bar.py`, or a distinctive slug that matches
  a real file on disk.

WHAT DOES NOT
  - anything inside `[text](path)` — that is the correct form
  - inline code spans and fenced blocks, which are quoting shell or source, not referencing
  - a filename the user themselves just used in their own message (echoing their words back
    is not the failure; introducing an unresolvable name is)

Exit 0 always. Stop hooks fire after the message is sent, so this makes the violation
visible and logged rather than blocking it.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402
from _transcript_state import last_messages  # noqa: E402

HOOK_NAME = "bare_filename_detector"

LOG_FILE = Path.home() / ".claude" / "bare-filename-log.jsonl"

# Extensions worth flagging. Deliberately not exhaustive: a false negative costs nothing,
# a false positive trains the agent to ignore the hook.
EXTS = (
    "md", "py", "js", "ts", "tsx", "jsx", "mjs", "json", "yaml", "yml", "toml", "sh",
    "bash", "zsh", "html", "css", "astro", "txt", "csv", "sql", "rb", "go", "rs", "java",
)

FILENAME = re.compile(
    r"(?<![\w/.-])"                      # not mid-token
    r"([A-Za-z0-9._-]+/)*"               # optional path segments
    r"[A-Za-z0-9._-]+"
    r"\.(?:" + "|".join(EXTS) + r")"
    r"(?::\d+)?"                         # optional :line
    # Boundary must NOT reject a trailing sentence period. The first version used
    # (?![\w/.-]) and so missed every filename ending a sentence — "…in dupes.json." —
    # which is where filenames most often sit. Reject only a dot that starts another
    # extension-like token, not a full stop.
    r"(?![\w/-])(?!\.[A-Za-z0-9])"
)

# A slug-shaped token: at least two hyphen-joined parts, long enough to be distinctive.
SLUG = re.compile(r"(?<![\w/.-])(?=[a-z0-9-]{12,})[a-z0-9]+(?:-[a-z0-9]+){2,}(?![\w/.-])")

MD_LINK = re.compile(r"\[[^\]]*\]\([^)]*\)")
CODE_SPAN = re.compile(r"`[^`\n]*`")
CODE_FENCE = re.compile(r"```.*?```", re.S)
URL = re.compile(r"https?://\S+")


def get_last_assistant_text(transcript_path: str) -> str:
    return last_messages(transcript_path)[0]


def get_last_user_text(transcript_path: str) -> str:
    """The user's own words. Echoing a name they used is not the failure this catches."""
    return last_messages(transcript_path)[1]


def strip_linked_and_quoted(text: str) -> str:
    """Blank out the regions where a bare-looking name is legitimate."""
    for pat in (CODE_FENCE, MD_LINK, CODE_SPAN, URL):
        text = pat.sub(lambda m: " " * len(m.group(0)), text)
    return text


def find_violations(assistant_text: str, user_text: str, cwd: str) -> list[dict]:
    scannable = strip_linked_and_quoted(assistant_text)
    user_tokens = set(re.findall(r"[A-Za-z0-9._/-]+", user_text.lower()))

    hits, seen = [], set()

    for m in FILENAME.finditer(scannable):
        tok = m.group(0)
        if tok.lower() in user_tokens or tok in seen:
            continue
        seen.add(tok)
        hits.append({"token": tok, "kind": "filename"})

    # Slugs only count when they actually name something on disk — otherwise ordinary
    # hyphenated prose ("cost-effective-ish") would trip it.
    for m in SLUG.finditer(scannable):
        tok = m.group(0)
        if tok.lower() in user_tokens or tok in seen:
            continue
        found = resolve_on_disk(tok, cwd)
        if found:
            seen.add(tok)
            hits.append({"token": tok, "kind": "slug", "resolves_to": found})

    return hits


def resolve_on_disk(token: str, cwd: str) -> str:
    """Cheap bounded lookup: does this slug name a real file or directory nearby?"""
    roots = [cwd, str(Path.home() / "workspaces")]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            out = os.popen(
                f"find {root!r} -maxdepth 6 -name {token + '*'!r} "
                f"-not -path '*/.git/*' -print -quit 2>/dev/null"
            ).read().strip()
        except Exception:
            continue
        if out:
            return out
    return ""


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append(f"extensions_tracked={len(EXTS)}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--doctor" in argv:
        return doctor()
    if not hook_enabled(HOOK_NAME):
        return 0

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    transcript = data.get("transcript_path", "")
    cwd = data.get("cwd", "")
    if not transcript or not os.path.isfile(transcript):
        return 0

    assistant_text, user_text = last_messages(transcript)
    if not assistant_text:
        return 0

    hits = find_violations(assistant_text, user_text, cwd)
    if not hits:
        return 0

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": data.get("session_id", ""),
        "cwd": cwd,
        "violations": hits,
    }
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

    names = ", ".join(h["token"] for h in hits[:6])
    more = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
    print(
        "\n  UNLINKED FILENAMES IN YOUR RESPONSE — ABSOLUTE rule in project instructions\n"
        f"  Named without a clickable link: {names}{more}\n"
        "  Every file in a chat response is [name](/absolute/path).\n"
        "  The reader cannot click a bare string, and a relative path does not resolve.\n"
        "  Correct it in your next message.\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The published knowledge base as documents: front matter, provenance stamp and body.

A published tree holds `plugins/<plugin>/skills/<plugin>/references/<path>.md`, one file per
knowledge-base file, each opening with the source's front matter and then a provenance stamp:

    > Published from `source/<rel>` in <repo> at commit `<sha7>` (<date>).

A document's id is its path under `references/`. Front matter is read with the plugin's one YAML
reader (synthesis/yamlish.py); a block it cannot read leaves the document served with no fields,
never half-read.
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
# The folder holding synthesis/yamlish.py: the plugin root in a checkout, /app in the image.
_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "synthesis" / "yamlish.py").is_file()), None)
if _ROOT is not None and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    from synthesis import yamlish  # noqa: E402
except ImportError as exc:  # no runtime beside this copy or in this image; one that fails otherwise as it loads keeps its traceback
    print(f"{__file__} needs the synthesis runtime, which cannot be imported ({exc}), so nothing ran. Run it from the "
          "installed synthesis-skills plugin or a checkout of it, or in the image this connector's Dockerfile builds", file=sys.stderr)
    sys.exit(2)

LOG = logging.getLogger("kb_connector")
GUIDE = "SKILL.md"
FRONT = re.compile(r"---[ \t]*\n(.*?\n)?---[ \t]*(?:\n|\Z)", re.S)
STAMP = re.compile(r"^> Published from `(?P<source_path>[^`]+)` in (?P<source_repo>.+?) at commit "
                   r"`(?P<commit>[0-9a-fA-F]{4,64})` \((?P<published>[^)]*)\)\.\s*$")


class CorpusError(Exception):
    """The tree has no single references folder to serve."""


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    description: str
    body: str
    fields: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)


def split_front_matter(text: str):
    """(front matter text, body); the front matter is '' when the file has none."""
    match = FRONT.match(text)
    return (match.group(1) or "", text[match.end():]) if match else ("", text)


def read_fields(front: str, source: str) -> dict:
    if not front.strip():
        return {}
    try:
        return yamlish.load_mapping(front, source=source)
    except ValueError as error:
        LOG.warning("front matter of %s not read: %s", source, error)
        return {}


def provenance(body: str) -> dict:
    """The stamp on the first non-blank line after the front matter, whole and in parts."""
    first = next((line for line in body.splitlines() if line.strip()), "")
    match = STAMP.match(first.strip())
    if not match:
        return {}
    return {"stamp": first.strip(), **match.groupdict()}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def load_document(path: Path, doc_id: str) -> Document:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    front, body = split_front_matter(text)
    fields = read_fields(front, doc_id)
    heading = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
    title = _text(fields.get("title")) or heading or Path(doc_id).stem.replace("-", " ")
    return Document(id=doc_id, title=title, description=_text(fields.get("description")), body=body.strip("\n"),
                    fields=fields, provenance=provenance(body))


def find_references(root: Path, configured: str = "") -> Path:
    """The folder to serve: `configured` under root, else the one plugins/*/skills/*/references there."""
    root = root.resolve()
    if configured:
        folder = (root / configured).resolve()
        if root != folder and root not in folder.parents:
            raise CorpusError(f"KB_REFERENCES_PATH {configured!r} leaves the published tree")
        if not folder.is_dir():
            raise CorpusError(f"KB_REFERENCES_PATH {configured!r} is not a folder in the published tree")
        return folder
    found = sorted(p for p in root.glob("plugins/*/skills/*/references") if p.is_dir())
    if len(found) != 1:
        names = ", ".join(str(p.relative_to(root)) for p in found) or "none"
        raise CorpusError(f"expected one plugins/*/skills/*/references folder, found {names}; set KB_REFERENCES_PATH")
    return found[0]


class Corpus:
    """Every markdown file under the references folder, hidden paths left out, keyed by id."""

    def __init__(self, documents, guide=None):
        self.documents = {doc.id: doc for doc in documents}
        self.guide = guide  # the plugin's SKILL.md beside references/: fetch serves it, search leaves it out

    @classmethod
    def load(cls, root: Path, configured: str = "") -> "Corpus":
        """Symbolic links are never followed: one in the published tree could point at the deploy key."""
        folder = find_references(root, configured)
        docs = []
        for path in sorted(folder.rglob("*.md")):
            rel = path.relative_to(folder).as_posix()
            if any(part.startswith(".") for part in rel.split("/")) or path.is_symlink() or not path.is_file():
                continue
            if folder not in path.resolve().parents:
                LOG.warning("%s is reached through a link out of the references folder; not served", rel)
                continue
            docs.append(load_document(path, rel))
        if not docs:
            raise CorpusError(f"no markdown files under {folder.relative_to(root.resolve())}")
        guide = folder.parent / GUIDE  # read only when it is inside the tree and not a link
        return cls(docs, load_document(guide, GUIDE) if folder != root.resolve() and guide.is_file()
                   and not guide.is_symlink() else None)

    def __len__(self) -> int:
        return len(self.documents)

    def get(self, doc_id: str):
        return self.documents.get(doc_id) or (self.guide if doc_id == GUIDE else None)

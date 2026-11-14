"""BM25F ranking over title, description, path and body, with the standard library only.

Each field's term frequency is length-normalized against that field's average and weighted
(title 3, description 2, path 1.5, body 1) before BM25's saturation, so a term in a title counts
for more than the same term deep in a body. A query of two or more words that appears as a phrase
adds a bonus. Words are lowercased, stop words dropped and plurals and common suffixes folded the
same way in documents and queries, so "pricing" finds "priced".
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

WORD = re.compile(r"[^\W_]+", re.UNICODE)
STOP = frozenset("""a an and are as at be but by for from has have how i if in into is it its me my of on or
our so than that the their them then there these they this to was we were what when where which who why will
with you your""".split())
FIELDS = (("title", 3.0), ("description", 2.0), ("path", 1.5), ("body", 1.0))
K1, B = 1.2, 0.75
SNIPPET = 240


def stem(word: str) -> str:
    """A light suffix fold: plurals, then -ing or -ed, then a final e (price, prices, priced, pricing: pric)."""
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith(("sses", "xes", "zes", "ches", "shes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 3 else word


def tokens(text: str, drop_stop: bool = True) -> list:
    words = [w.lower() for w in WORD.findall(text or "")]
    return [stem(w) for w in words if not (drop_stop and w in STOP)]


def query_terms(query: str) -> list:
    """The query's distinct terms; a query of only stop words keeps them rather than finding nothing."""
    terms = tokens(query) or tokens(query, drop_stop=False)
    return list(dict.fromkeys(terms))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[#*_`>|]+", " ", text)).strip()


def snippet(body: str, terms: list, fallback: str = "") -> str:
    """About 240 characters around the body's first line with the most query terms."""
    lines = [line for line in body.splitlines() if line.strip() and not line.startswith("> Published from")]
    best, best_hits = "", 0
    for line in lines:
        hits = len(set(tokens(line)) & set(terms))
        if hits > best_hits:
            best, best_hits = line, hits
    text = _clean(best) if best else _clean(fallback or (lines[0] if lines else ""))
    if len(text) <= SNIPPET:
        return text
    lowered = text.lower()
    first = min((lowered.find(t) for t in terms if lowered.find(t) >= 0), default=0)
    start = max(0, min(first - SNIPPET // 3, len(text) - SNIPPET))
    return ("…" if start else "") + text[start:start + SNIPPET].strip() + ("…" if start + SNIPPET < len(text) else "")


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    snippet: str


class Index:
    def __init__(self, documents):
        self.docs = {doc.id: doc for doc in documents}
        self.freqs, self.lengths, self.phrases = {}, {}, {}
        df = Counter()
        for doc in self.docs.values():
            text = {"title": doc.title, "description": doc.description,
                    "path": doc.id.rsplit(".", 1)[0].replace("/", " "), "body": doc.body}
            self.freqs[doc.id] = {name: Counter(tokens(text[name])) for name, _ in FIELDS}
            self.lengths[doc.id] = {name: sum(self.freqs[doc.id][name].values()) for name, _ in FIELDS}
            self.phrases[doc.id] = {name: f" {' '.join(tokens(text[name], drop_stop=False))} " for name in ("title", "body")}
            df.update(set().union(*(self.freqs[doc.id][name] for name, _ in FIELDS)))
        count = max(len(self.docs), 1)
        self.average = {name: (sum(l[name] for l in self.lengths.values()) / count) or 1.0 for name, _ in FIELDS}
        self.idf = {term: math.log(1 + (count - n + 0.5) / (n + 0.5)) for term, n in df.items()}

    def _score(self, doc_id: str, terms: list) -> float:
        score = 0.0
        for term in terms:
            weighted = 0.0
            for name, weight in FIELDS:
                tf = self.freqs[doc_id][name].get(term, 0)
                if tf:
                    weighted += weight * tf / (1 - B + B * self.lengths[doc_id][name] / self.average[name])
            if weighted:
                score += self.idf.get(term, 0.0) * weighted / (K1 + weighted)
        return score

    def search(self, query: str, limit: int = 10) -> list:
        terms = query_terms(query)
        if not terms:
            return []
        phrase = f" {' '.join(tokens(query, drop_stop=False))} "
        hits = []
        for doc_id, doc in self.docs.items():
            score = self._score(doc_id, terms)
            if score <= 0:
                continue
            if len(phrase.split()) > 1:
                score *= 1.5 if phrase in self.phrases[doc_id]["title"] else 1.2 if phrase in self.phrases[doc_id]["body"] else 1.0
            hits.append(Hit(doc_id, round(score, 6), snippet(doc.body, terms, doc.description)))
        hits.sort(key=lambda hit: (-hit.score, hit.id))
        return hits[:max(1, limit)]

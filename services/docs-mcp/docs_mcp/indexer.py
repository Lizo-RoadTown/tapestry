"""In-memory search index for the Tapestry docs corpus.

Token-frequency ranking with a tiny inverted index. The corpus is small enough
(currently ~25 pages) that anything more sophisticated would be overkill. Swap
in BM25 + embeddings later if recall becomes inadequate.

Search returns ranked Doc records with snippet excerpts; the MCP tool layer
formats them for the client.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .corpus import Doc


_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


@dataclass(frozen=True)
class SearchHit:
    slug: str
    title: str
    score: float
    snippet: str


class Index:
    """Token-frequency index over the docs corpus.

    Construction is O(N tokens); search is O(query tokens * matching docs).
    Both are fine at corpus sizes well into the thousands of pages.
    """

    def __init__(self, docs: list[Doc]) -> None:
        self._docs: dict[str, Doc] = {d.slug: d for d in docs}
        # term -> {slug: count}
        self._postings: dict[str, dict[str, int]] = {}
        for doc in docs:
            haystack = " ".join([doc.title, doc.description, doc.body])
            counts = Counter(_tokenize(haystack))
            for term, count in counts.items():
                self._postings.setdefault(term, {})[doc.slug] = count

    @property
    def docs(self) -> list[Doc]:
        return list(self._docs.values())

    def get(self, slug: str) -> Doc | None:
        return self._docs.get(slug)

    def list_slugs(self, section: str | None = None) -> list[str]:
        if section is None:
            return sorted(self._docs.keys())
        return sorted(s for s, d in self._docs.items() if d.section == section)

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        """Return up to `limit` ranked SearchHits for `query`.

        Scoring: sum of (count_in_doc * idf) over query terms. Title hits
        get a 3x boost; description hits get 2x. Snippet is the first 200
        chars of the body containing any query term, falling back to the
        description.
        """
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        n_docs = max(1, len(self._docs))
        scores: dict[str, float] = {}
        for term in query_terms:
            postings = self._postings.get(term, {})
            if not postings:
                continue
            df = len(postings)
            idf = max(0.1, 1.0 + (n_docs / df))  # cheap idf; never zero
            for slug, count in postings.items():
                doc = self._docs[slug]
                term_score = count * idf
                if term in _tokenize(doc.title):
                    term_score *= 3.0
                elif term in _tokenize(doc.description):
                    term_score *= 2.0
                scores[slug] = scores.get(slug, 0.0) + term_score

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        hits: list[SearchHit] = []
        for slug, score in ranked:
            doc = self._docs[slug]
            hits.append(SearchHit(
                slug=slug,
                title=doc.title,
                score=round(score, 3),
                snippet=_snippet(doc, query_terms),
            ))
        return hits


def _snippet(doc: Doc, query_terms: list[str], length: int = 200) -> str:
    """Return a body excerpt around the first matching term; fall back to description."""
    body = doc.body.strip()
    lower = body.lower()
    for term in query_terms:
        idx = lower.find(term)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(body), idx + length - 60)
            excerpt = body[start:end].strip()
            if start > 0:
                excerpt = "…" + excerpt
            if end < len(body):
                excerpt = excerpt + "…"
            return excerpt
    return doc.description or body[:length]

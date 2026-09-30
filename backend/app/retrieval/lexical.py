"""
Lexical retrieval (Section 9 - the "keyword/lexical retrieval" half of
hybrid retrieval; NOT used alone as the matching mechanism).

Uses TF-IDF + cosine similarity over resume chunk text. TF-IDF is chosen
over a raw boolean keyword match because it naturally down-weights common
words and up-weights distinctive terms (a resume matching on "Kubernetes"
counts for more than matching on "team"), while remaining fully
deterministic, offline, and fast enough for interactive search even before
any embedding call happens -- this is what lets lexical retrieval run as a
genuinely independent signal from semantic retrieval rather than a
redundant approximation of it.
"""
from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class LexicalHit:
    doc_index: int
    score: float


def lexical_search(query: str, documents: list[str]) -> list[LexicalHit]:
    if not documents:
        return []

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=20000,
    )
    try:
        doc_matrix = vectorizer.fit_transform(documents)
        query_vec = vectorizer.transform([query])
    except ValueError:
        # e.g. vocabulary is empty after stop-word removal
        return [LexicalHit(doc_index=i, score=0.0) for i in range(len(documents))]

    sims = cosine_similarity(query_vec, doc_matrix)[0]
    return [LexicalHit(doc_index=i, score=float(s)) for i, s in enumerate(sims)]

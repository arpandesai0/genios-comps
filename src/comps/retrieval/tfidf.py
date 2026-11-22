"""TF-IDF cosine similarity on company descriptions: the first served ranker.

Settings (AGENTS.md §4, 2026-11-22): lower-case, English stop words, unigrams, sublinear TF and
L2-normalized rows, so the dot product of two rows is their cosine similarity. Any change to these
settings must come with an eval result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

NAME = "tfidf-description"
VERSION = "1"


@dataclass(frozen=True, eq=False)
class TfidfIndex:
    keys: tuple[str, ...]
    _matrix: csr_matrix  # one L2-normalized row per key
    _terms: np.ndarray  # column index -> term
    _row: Mapping[str, int]

    def similarities(self, target: str) -> dict[str, float]:
        scores = (self._matrix @ self._matrix[self._row[target]].T).toarray().ravel()
        return {k: _unit(float(scores[i])) for i, k in enumerate(self.keys) if k != target}

    def similarity(self, a: str, b: str) -> float:
        return _unit(float(self._matrix[self._row[a]].multiply(self._matrix[self._row[b]]).sum()))

    def shared_terms(self, a: str, b: str, n: int = 5) -> Sequence[str]:
        product = self._matrix[self._row[a]].multiply(self._matrix[self._row[b]]).tocoo()
        pairs = sorted(zip(product.data, product.col, strict=True), key=lambda p: (-p[0], self._terms[p[1]]))
        return [str(self._terms[col]) for weight, col in pairs[:n] if weight > 0]


def _unit(x: float) -> float:
    """Clamp float noise (e.g. 1.0000000000000002) into [0, 1]."""
    return min(1.0, max(0.0, x))


class TfidfRetriever:
    name = NAME
    version = VERSION

    def fit(self, documents: Mapping[str, str]) -> TfidfIndex:
        """Index every description that has at least one non-stop-word term.

        A description made only of stop words has no usable terms, so its key is left out of the index
        (and is reported as ``no_description``) instead of being ranked at similarity 0.
        """
        keys = sorted(documents)
        vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 1), sublinear_tf=True)
        try:
            matrix = csr_matrix(vectorizer.fit_transform([documents[k] for k in keys]))
            terms = vectorizer.get_feature_names_out()
        except ValueError:  # no description has a usable term
            matrix = csr_matrix((0, 0), dtype=np.float64)
            terms = np.array([], dtype=object)
            keys = []
        usable = [i for i in range(len(keys)) if matrix[i].nnz > 0]
        kept = tuple(keys[i] for i in usable)
        return TfidfIndex(
            keys=kept, _matrix=csr_matrix(matrix[usable]), _terms=terms, _row={k: i for i, k in enumerate(kept)}
        )

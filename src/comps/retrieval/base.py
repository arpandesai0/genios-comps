"""The retriever interface: the only part of retrieval meant to be swapped.

A ``Retriever`` is fitted once per snapshot on the companies' descriptions and returns an immutable
``Index``. Peer selection, the API and the evals only talk to these two protocols, so a different
ranker can be swapped without touching them. The served ranker is sentence embeddings
(``embedding.py``); TF-IDF (``tfidf.py``) is the earlier baseline.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class Index(Protocol):
    """A fitted, read-only similarity index over a fixed set of keys."""

    @property
    def keys(self) -> tuple[str, ...]:
        """The indexed keys: companies with a usable description."""
        ...

    def similarities(self, target: str) -> dict[str, float]:
        """Similarity of ``target`` to every other key, in [0, 1]. ``target`` must be in ``keys``."""
        ...

    def similarity(self, a: str, b: str) -> float:
        """Similarity of two keys, in [0, 1]."""
        ...


class Retriever(Protocol):
    name: str
    version: str

    def fit(self, documents: Mapping[str, str]) -> Index:
        """Fit on ``key -> description`` (descriptions already non-empty) and return the index."""
        ...

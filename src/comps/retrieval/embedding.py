"""Sentence-embedding cosine similarity on company descriptions.

One model per process, named by the ``EMBEDDING_MODEL`` setting and loaded once at snapshot build.
Rows are L2-normalized, so the dot product of two rows is their cosine similarity. The model is
required: if it can't be loaded (not downloaded, offline, unknown name) start-up fails. There is no
fallback ranker.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

NAME = "embedding-description"
VERSION = "1"

# Prompts a model card asks for. EmbeddingGemma is trained with task prompts; the symmetric
# "sentence similarity" task matches comparing two company descriptions.
PROMPTS = {"google/embeddinggemma-300m": "task: sentence similarity | query: "}  # keys lower-case


class ModelUnavailable(RuntimeError):
    """The configured embedding model could not be loaded."""


@dataclass(frozen=True, eq=False)
class EmbeddingIndex:
    keys: tuple[str, ...]
    _matrix: np.ndarray  # one L2-normalized row per key
    _row: Mapping[str, int]

    def similarities(self, target: str) -> dict[str, float]:
        scores = self._matrix @ self._matrix[self._row[target]]
        return {k: _unit(float(scores[i])) for i, k in enumerate(self.keys) if k != target}

    def similarity(self, a: str, b: str) -> float:
        return _unit(float(self._matrix[self._row[a]] @ self._matrix[self._row[b]]))


def _unit(x: float) -> float:
    """Clamp to [0, 1]: float noise above 1, and negative cosines (opposite meaning) count as 0."""
    return min(1.0, max(0.0, x))


class EmbeddingRetriever:
    name = NAME
    version = VERSION

    def __init__(
        self, model: str, *, cache_dir: Path | None = None, offline: bool = False, encoder: Any = None
    ) -> None:
        self.model = model
        if encoder is not None:  # tests pass a fake with an ``embed(texts)`` method
            self._encoder = encoder
            return
        from fastembed import TextEmbedding  # imported here so TF-IDF-only tests don't load onnxruntime

        try:
            self._encoder = TextEmbedding(
                model_name=model,
                cache_dir=str(cache_dir) if cache_dir else None,
                local_files_only=offline,
            )
        except Exception as exc:  # fastembed raises ValueError, OSError or hub errors
            where = f" from {cache_dir}" if cache_dir else ""
            mode = " (MODEL_OFFLINE is set, so it is never downloaded: is it in the cache?)" if offline else ""
            raise ModelUnavailable(f"cannot load embedding model {model!r}{where}{mode}: {exc}") from exc

    def fit(self, documents: Mapping[str, str]) -> EmbeddingIndex:
        keys = tuple(sorted(k for k, d in documents.items() if d.strip()))
        if not keys:
            return EmbeddingIndex(keys=(), _matrix=np.zeros((0, 0)), _row={})
        prompt = PROMPTS.get(self.model.lower(), "")
        vectors = np.asarray(list(self._encoder.embed([prompt + documents[k] for k in keys])), dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        matrix = vectors / np.where(norms == 0, 1.0, norms)
        return EmbeddingIndex(keys=keys, _matrix=matrix, _row={k: i for i, k in enumerate(keys)})


def download(model: str, cache_dir: Path | None = None) -> None:
    """Fetch ``model`` into the cache (used at image build). Raises ``ModelUnavailable`` on failure."""
    EmbeddingRetriever(model, cache_dir=cache_dir, offline=False)


if __name__ == "__main__":  # python -m comps.retrieval.embedding: download the configured model, fail hard
    from comps.config import load_settings

    cfg = load_settings().retrieval
    download(cfg.model, cfg.cache_dir)
    print(f"embedding model {cfg.model} is ready in {cfg.cache_dir or 'the default cache'}")

"""Settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestConfig:
    # A price older than this many days before the latest valid price_date in the dataset gets a "stale_price" warning.
    # (a warning only; stale companies are still served)
    stale_after_days: int = 90


# Served when EMBEDDING_MODEL / NEAR_DUPLICATE_THRESHOLD are not set. Chosen by the retrieval eval (docs/eval.md).
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_NEAR_DUPLICATE = 0.88


@dataclass(frozen=True)
class RetrievalConfig:
    model: str = DEFAULT_EMBEDDING_MODEL  # EMBEDDING_MODEL: one model per process, loaded at start-up
    cache_dir: Path | None = None  # MODEL_CACHE_DIR: where the model is downloaded to / loaded from
    offline: bool = False  # MODEL_OFFLINE=1: never download; fail if the model isn't in the cache
    # NEAR_DUPLICATE_THRESHOLD: similarity at or above which two companies are near-duplicates. 0.88 is the
    # lowest cut that flags no labelled non-duplicate on the pre-test data or the synthetic pairs (docs/eval.md).
    near_duplicate: float = DEFAULT_NEAR_DUPLICATE


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ingest: IngestConfig
    retrieval: RetrievalConfig = RetrievalConfig()


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    return Settings(
        data_dir=Path(env.get("DATA_DIR", "/data")).expanduser(),
        ingest=IngestConfig(
            stale_after_days=int(env.get("STALE_AFTER_DAYS", "90")),
        ),
        retrieval=RetrievalConfig(
            model=env.get("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
            cache_dir=Path(env["MODEL_CACHE_DIR"]).expanduser() if env.get("MODEL_CACHE_DIR") else None,
            offline=env.get("MODEL_OFFLINE", "") in ("1", "true", "yes"),
            near_duplicate=float(env.get("NEAR_DUPLICATE_THRESHOLD", str(DEFAULT_NEAR_DUPLICATE))),
        ),
    )

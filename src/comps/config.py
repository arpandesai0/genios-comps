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


# The embedding model served when EMBEDDING_MODEL is not set. Chosen by the retrieval eval (docs/eval.md).
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


@dataclass(frozen=True)
class RetrievalConfig:
    model: str = DEFAULT_EMBEDDING_MODEL  # EMBEDDING_MODEL: one model per process, loaded at start-up
    cache_dir: Path | None = None  # MODEL_CACHE_DIR: where the model is downloaded to / loaded from
    offline: bool = False  # MODEL_OFFLINE=1: never download; fail if the model isn't in the cache
    near_duplicate: float = 0.95  # NEAR_DUPLICATE_THRESHOLD: similarity at or above which two companies are duplicates


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
            near_duplicate=float(env.get("NEAR_DUPLICATE_THRESHOLD", "0.95")),
        ),
    )

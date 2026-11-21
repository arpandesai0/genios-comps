"""Settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class IngestConfig:
    # Freshness checks compare price dates with this date. If it is None, the latest valid
    # price_date in the dataset is used, so results stay reproducible regardless of when the
    # service runs.
    reference_date: date | None = None
    # A price older than this many days before the reference date gets a "stale_price" warning.
    # (a warning only; stale companies are still served)
    stale_after_days: int = 90


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ingest: IngestConfig


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    ref = env.get("REFERENCE_DATE")
    return Settings(
        data_dir=Path(env.get("DATA_DIR", "/data")).expanduser(),
        ingest=IngestConfig(
            reference_date=date.fromisoformat(ref) if ref else None,
            stale_after_days=int(env.get("STALE_AFTER_DAYS", "90")),
        ),
    )

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
    stale_after_days: int = 90
    # Any USD money value above this (USD millions; 1,000,000 = USD 1 trillion) is flagged
    # as a suspected unit/scale error. Values are flagged only, never rescaled.
    implausible_money_usd_m: float = 1_000_000.0


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
            implausible_money_usd_m=float(env.get("IMPLAUSIBLE_MONEY_USD_M", "1000000")),
        ),
    )

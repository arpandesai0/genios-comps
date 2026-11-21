"""Settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestConfig:
    # A price older than this many days before the reference date gets a "stale_price" warning.
    # (a warning only; stale companies are still served)
    stale_after_days: int = 90


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ingest: IngestConfig


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    return Settings(
        data_dir=Path(env.get("DATA_DIR", "/data")).expanduser(),
        ingest=IngestConfig(
            stale_after_days=int(env.get("STALE_AFTER_DAYS", "90")),
        ),
    )

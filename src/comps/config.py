"""Settings: defaults from the config file `settings.toml` (or CONFIG_FILE), overridden by environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILE = Path(__file__).with_name("settings.toml")


def read_config(path: Path = DEFAULT_CONFIG_FILE) -> dict[str, Any]:
    """The config file as a dict; a missing or malformed file raises ValueError, so start-up fails loudly."""
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ValueError(f"Cannot read the config file {path}: {e}") from None


# The shipped file's values, used as the dataclass defaults (e.g. in tests). The service reads its settings
# through load_settings(), which honours CONFIG_FILE and the environment.
_DEFAULTS = read_config()
# Served when EMBEDDING_MODEL is not set; its near-duplicate threshold comes from the same file.
DEFAULT_EMBEDDING_MODEL: str = _DEFAULTS["retrieval"]["embedding_model"]


@dataclass(frozen=True)
class IngestConfig:
    # A price older than this many days before the latest valid price_date in the dataset gets a "stale_price"
    # warning (a warning only; stale companies are still served).
    stale_after_days: int = _DEFAULTS["ingest"]["stale_after_days"]


@dataclass(frozen=True)
class RetrievalConfig:
    model: str = DEFAULT_EMBEDDING_MODEL  # EMBEDDING_MODEL: one model per process, loaded at start-up
    # MODEL_CACHE_DIR: where the model is downloaded to / loaded from (fastembed's own default is a temp
    # folder the OS may clear, so a persistent per-user folder is the default here; /models in the image).
    cache_dir: Path | None = None
    offline: bool = False  # MODEL_OFFLINE=1: never download; fail if the model isn't in the cache
    # Similarity at or above which two companies are near-duplicates: the model's value in the config file,
    # or NEAR_DUPLICATE_THRESHOLD.
    near_duplicate: float = field(
        default_factory=lambda: _DEFAULTS["retrieval"]["near_duplicate_threshold"][DEFAULT_EMBEDDING_MODEL]
    )


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ingest: IngestConfig
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)


DEFAULT_MODEL_CACHE = Path("~/.cache/comps-models")
_TRUE, _FALSE = ("1", "true", "yes", "on"), ("", "0", "false", "no", "off")


def _flag(name: str, value: str) -> bool:
    v = value.strip().lower()
    if v not in _TRUE + _FALSE:
        raise ValueError(f"{name} must be one of {', '.join(x for x in _TRUE + _FALSE if x)}; got {value!r}")
    return v in _TRUE


def _threshold(value: object, source: str) -> float:
    try:
        t = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{source} must be a number in (0, 1]; got {value!r}") from None
    if not 0 < t <= 1:
        raise ValueError(f"{source} must be in (0, 1]; got {t}")
    return t


def _days(value: object, source: str) -> int:
    if isinstance(value, bool | float):  # a TOML true or 90.5 is not silently truncated
        raise ValueError(f"{source} must be a whole number of days; got {value!r}")
    try:
        d = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        raise ValueError(f"{source} must be a whole number of days; got {value!r}") from None
    if d < 0:
        raise ValueError(f"{source} must not be negative; got {d}")
    return d


def _near_duplicate(env: dict[str, str], config: dict[str, Any], model: str, config_file: Path) -> float:
    if env.get("NEAR_DUPLICATE_THRESHOLD"):
        return _threshold(env["NEAR_DUPLICATE_THRESHOLD"], "NEAR_DUPLICATE_THRESHOLD")
    # Model names are matched ignoring case, as fastembed does.
    per_model = {k.lower(): v for k, v in config.get("retrieval", {}).get("near_duplicate_threshold", {}).items()}
    if model.lower() not in per_model:
        raise ValueError(
            f"No near-duplicate threshold for the embedding model {model!r}: each model needs its own tuned "
            f"value. Add it under [retrieval.near_duplicate_threshold] in {config_file}, or set "
            "NEAR_DUPLICATE_THRESHOLD."
        )
    return _threshold(per_model[model.lower()], f"near_duplicate_threshold for {model!r} in {config_file}")


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Read settings; a missing or malformed setting raises ValueError, so start-up fails loudly."""
    env = dict(os.environ if env is None else env)
    config_file = Path(env["CONFIG_FILE"]).expanduser() if env.get("CONFIG_FILE") else DEFAULT_CONFIG_FILE
    config = read_config(config_file)
    try:
        default_model = config["retrieval"]["embedding_model"]
        default_days = config["ingest"]["stale_after_days"]
    except KeyError as e:
        raise ValueError(f"{config_file} has no setting {e}") from None
    model = env.get("EMBEDDING_MODEL") or default_model
    return Settings(
        data_dir=Path(env.get("DATA_DIR", "/data")).expanduser(),
        ingest=IngestConfig(
            stale_after_days=_days(env["STALE_AFTER_DAYS"], "STALE_AFTER_DAYS")
            if env.get("STALE_AFTER_DAYS")
            else _days(default_days, f"stale_after_days in {config_file}"),
        ),
        retrieval=RetrievalConfig(
            model=model,
            cache_dir=Path(env.get("MODEL_CACHE_DIR") or DEFAULT_MODEL_CACHE).expanduser(),
            offline=_flag("MODEL_OFFLINE", env.get("MODEL_OFFLINE", "")),
            near_duplicate=_near_duplicate(env, config, model, config_file),
        ),
    )

"""Plain data types shared between pipeline stages.

This module is the contract between ingestion, finance, retrieval and the API.
It holds data only, with no behaviour that depends on another stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Mapping

Severity = Literal["error", "limitation", "warning", "info"]
FindingSource = Literal["validation", "derived"]
Origin = Literal["file", "manual"]

SEVERITIES: tuple[Severity, ...] = ("error", "limitation", "warning", "info")


@dataclass(frozen=True)
class Finding:
    """A structured data-quality observation. It never changes data by itself."""

    code: str
    severity: Severity
    message: str
    fields: tuple[str, ...] = ()
    affects: tuple[str, ...] = ()
    source: FindingSource = "validation"
    record_ids: tuple[str, ...] = ()
    entity_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class UsdValues:
    """Values normalized to USD. Money fields are in USD millions; price is USD per share.

    None means the value could not be computed (missing or invalid input). It never means zero.
    """

    price: float | None
    total_debt: float | None
    cash: float | None
    revenue: float | None
    ebitda: float | None
    net_income: float | None


@dataclass(frozen=True)
class Conversion:
    price_fx: float | None
    reporting_fx: float | None
    unit_factor: float | None


@dataclass(frozen=True)
class Observation:
    """One supplied record's point-in-time values, after validation and normalization."""

    record_id: str
    origin: Origin
    source_index: int                      # position in the input; used for deterministic tie-breaks
    price_date: date | None
    original: Mapping[str, Any]            # the record exactly as supplied
    shares_outstanding: float | None       # millions of shares (already in millions per the glossary)
    usd: UsdValues
    conversion: Conversion
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class TextVersion:
    """A value a text field held in one observation; kept as provenance."""

    field: str
    value: str | None
    record_id: str
    price_date: date | None


@dataclass(frozen=True)
class Entity:
    """A company identified by ``COUNTRY:TICKER``, with its observation history."""

    key: str
    ticker: str
    country: str
    name: str | None
    description: str | None
    sector: str | None
    industry: str | None
    sub_industry: str | None
    fiscal_year_end: str | None
    aliases: tuple[str, ...]
    observations: tuple[Observation, ...]  # oldest first; last one is the latest
    superseded: tuple[Observation, ...] = ()  # exact duplicates / same-date losers, kept as provenance
    text_history: tuple[TextVersion, ...] = ()
    findings: tuple[Finding, ...] = ()

    @property
    def latest(self) -> Observation:
        return self.observations[-1]

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(o.record_id for o in self.observations + self.superseded)


@dataclass(frozen=True)
class SourceFile:
    name: str
    sha256: str


@dataclass(frozen=True)
class Dataset:
    """The output of ingestion: an immutable, versioned view of the input."""

    version: str
    reference_date: date | None
    fx_rates: Mapping[str, float]          # USD per unit of currency, including USD itself
    files: tuple[SourceFile, ...]
    record_count: int
    entities: Mapping[str, Entity]         # key -> entity, ordered by key
    findings: tuple[Finding, ...]          # dataset-level findings (cross-record checks, fx issues)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def all_findings(self) -> list[Finding]:
        out = list(self.findings)
        for e in self.entities.values():
            out.extend(e.findings)
            for o in e.observations + e.superseded:
                out.extend(o.findings)
        return out

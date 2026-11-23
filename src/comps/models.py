"""Plain data types shared between pipeline stages.

This module is the contract between ingestion, finance, retrieval and the API.
It holds data only, with no behaviour that depends on another stage.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

Severity = Literal["error", "limitation", "warning", "info"]
FindingSource = Literal["validation", "derived"]

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
    source_index: int  # position in the input; used for deterministic tie-breaks
    price_date: date | None
    original: Mapping[str, Any]  # the record exactly as supplied
    shares_outstanding: float | None  # millions of shares (already in millions per the glossary)
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
    """A company identified by ``COUNTRY:TICKER``, with its observation history.

    After the share-class merge, an entity in ``Dataset.entities`` is an **issuer**: ``key`` is its
    shown key (its most valuable class), its own fields come from that class, and ``share_classes``
    lists every listing when there is more than one. A single listing has ``share_classes == ()``.
    """

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
    share_classes: tuple[ShareClass, ...] = ()  # shown class first; empty for a single listing
    # The description with the issuer's own names (name and aliases) replaced by "The company", set by ingestion.
    # Retrieval compares this, so invented names that look alike don't make unrelated companies similar; the
    # analyst always sees `description` as supplied.
    business_description: str | None = None

    @property
    def latest(self) -> Observation:
        return self.observations[-1]

    @property
    def classes(self) -> tuple[ShareClass, ...]:
        """Every listing of this issuer, shown class first. A single listing is its own only class."""
        return self.share_classes or (ShareClass(entity=self, counted=True),)

    @property
    def share_class_keys(self) -> tuple[str, ...]:
        return tuple(c.entity.key for c in self.classes)

    @property
    def record_ids(self) -> tuple[str, ...]:
        own = tuple(o.record_id for o in self.observations + self.superseded)
        return own + tuple(r for c in self.share_classes[1:] for r in c.entity.record_ids)


@dataclass(frozen=True)
class ShareClass:
    """One listing (``COUNTRY:TICKER``) of an issuer, as it was before the merge.

    ``counted`` is False when the listing has the same price, price currency and share count as an
    earlier class: the same shares listed twice, so they enter the issuer's market cap once.
    """

    entity: Entity
    counted: bool


@dataclass(frozen=True)
class SourceFile:
    name: str
    sha256: str


@dataclass(frozen=True)
class Dataset:
    """The output of ingestion: an immutable, versioned view of the input."""

    version: str
    reference_date: date | None
    fx_rates: Mapping[str, float]  # USD per unit of currency, including USD itself
    files: tuple[SourceFile, ...]
    record_count: int
    entities: Mapping[str, Entity]  # shown key -> issuer, ordered by key
    findings: tuple[Finding, ...]  # dataset-level findings (cross-record checks, fx issues)
    # Disjoint-set parent pointer of every listing key: its issuer's shown key (a shown key points to itself).
    parents: Mapping[str, str] = field(default_factory=dict)

    def all_findings(self) -> list[Finding]:
        out = list(self.findings)
        for issuer in self.entities.values():
            for e in (issuer, *(c.entity for c in issuer.share_classes[1:])):
                out.extend(e.findings)
                for o in e.observations + e.superseded:
                    out.extend(o.findings)
        return out


# --- Finance outputs -------------------------------------------------------------------------

MetricStatus = Literal["ok", "nm", "missing"]


@dataclass(frozen=True)
class MetricValue:
    """One computed metric.

    ``ok``: computed; ``nm``: zero or negative denominator (all inputs present);
    ``missing``: an input is unavailable (this takes precedence over ``nm``).
    ``value`` is rounded to 1 dp for display and ``raw`` is unrounded; both are None unless ``ok``.
    """

    status: MetricStatus
    value: float | None
    display: str | None
    raw: float | None
    missing_inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Metrics:
    market_cap_usd_m: MetricValue
    enterprise_value_usd_m: MetricValue
    ev_revenue: MetricValue
    ev_ebitda: MetricValue
    pe: MetricValue


@dataclass(frozen=True)
class StatDisplay:
    mean: str | None
    median: str | None
    high: str | None
    low: str | None


@dataclass(frozen=True)
class SummaryStat:
    """Peer-only statistics for one multiple, computed on unrounded values and rounded to 1 dp."""

    n: int
    n_nm: int
    n_missing: int
    mean: float | None
    median: float | None
    high: float | None
    low: float | None
    display: StatDisplay


@dataclass(frozen=True)
class Summary:
    ev_revenue: SummaryStat
    ev_ebitda: SummaryStat
    pe: SummaryStat

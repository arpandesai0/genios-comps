"""The served snapshot: an immutable view of the dataset plus each company's computed metrics.

The snapshot is built once at start-up and only read afterwards, so concurrent requests need no
locking. (Swapping in a new snapshot for manual additions comes later, with the ingest endpoints.)
Query logic for the read-only endpoints lives here, so the API layer stays an adapter.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from comps.config import Settings
from comps.finance import compute_metrics
from comps.ingest import load_dataset
from comps.models import SEVERITIES, Dataset, Entity, Finding, Metrics, Severity

Match = Literal["key", "ticker", "name_exact", "name_partial"]
_MATCH_ORDER: dict[Match, int] = {"key": 0, "ticker": 1, "name_exact": 2, "name_partial": 3}


@dataclass(frozen=True)
class CompanyView:
    entity: Entity
    metrics: Metrics
    findings: tuple[Finding, ...]  # what applies to the served values: company, latest observation, finance

    @property
    def finding_counts(self) -> dict[Severity, int]:
        counts = Counter(f.severity for f in self.findings)
        return {s: counts.get(s, 0) for s in SEVERITIES}


@dataclass(frozen=True)
class Snapshot:
    dataset: Dataset
    data_dir: Path
    companies: Mapping[str, CompanyView]  # key -> view, ordered by key
    findings: tuple[Finding, ...]  # every finding: dataset, all observations, companies, finance


def build_snapshot(settings: Settings) -> Snapshot:
    """Load and ingest ``settings.data_dir``. Raises ``DatasetError`` if the input is unusable."""
    dataset = load_dataset(settings.data_dir, settings.ingest)
    companies: dict[str, CompanyView] = {}
    finance_findings: list[Finding] = []
    for key, entity in dataset.entities.items():
        metrics, raised = compute_metrics(entity.latest)
        raised = tuple(replace(f, entity_keys=(key,)) for f in raised)
        finance_findings.extend(raised)
        companies[key] = CompanyView(
            entity=entity, metrics=metrics, findings=entity.findings + entity.latest.findings + raised
        )
    return Snapshot(
        dataset=dataset,
        data_dir=settings.data_dir,
        companies=companies,
        findings=tuple(dataset.all_findings()) + tuple(finance_findings),
    )


def search(snapshot: Snapshot, q: str | None) -> list[tuple[CompanyView, Match | None]]:
    """Companies matching ``q`` by key, ticker, exact name or partial name (names include aliases).

    Best match type first, then by key. Without ``q`` every company is returned with no match type.
    """
    if not q or not q.strip():
        return [(c, None) for c in snapshot.companies.values()]
    needle = q.strip().casefold()
    hits: list[tuple[CompanyView, Match]] = []
    for c in snapshot.companies.values():
        e = c.entity
        names = [n.casefold() for n in (e.name, *e.aliases) if n]
        match: Match | None
        if e.key.casefold() == needle:
            match = "key"
        elif e.ticker.casefold() == needle:
            match = "ticker"
        elif needle in names:
            match = "name_exact"
        elif any(needle in n for n in names):
            match = "name_partial"
        else:
            match = None
        if match:
            hits.append((c, match))
    hits.sort(key=lambda h: (_MATCH_ORDER[h[1]], h[0].entity.key))
    return [(c, m) for c, m in hits]

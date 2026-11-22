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
    entity: Entity  # an issuer: shown key plus every share class
    metrics: Metrics
    findings: tuple[Finding, ...]  # what applies to the served values: company, latest observations, finance

    @property
    def finding_counts(self) -> dict[Severity, int]:
        counts = Counter(f.severity for f in self.findings)
        return {s: counts.get(s, 0) for s in SEVERITIES}


@dataclass(frozen=True)
class Snapshot:
    dataset: Dataset
    data_dir: Path
    companies: Mapping[str, CompanyView]  # shown key -> view, ordered by key
    findings: tuple[Finding, ...]  # every finding: dataset, all observations, companies, finance

    def resolve(self, key: str) -> CompanyView | None:
        """The company a listing key belongs to (any share-class key resolves to its issuer). Exact case."""
        shown = self.dataset.parents.get(key, key)
        return self.companies.get(shown)


def build_snapshot(settings: Settings) -> Snapshot:
    """Load and ingest ``settings.data_dir``. Raises ``DatasetError`` if the input is unusable."""
    dataset = load_dataset(settings.data_dir, settings.ingest)
    companies: dict[str, CompanyView] = {}
    finance_findings: list[Finding] = []
    for key, entity in dataset.entities.items():
        listings = [c.entity.latest for c in entity.classes if c.counted]
        metrics, raised = compute_metrics(entity.latest, listings)
        raised = tuple(replace(f, entity_keys=(key,)) for f in raised)
        finance_findings.extend(raised)
        others = tuple(f for c in entity.share_classes[1:] for f in c.entity.findings + c.entity.latest.findings)
        companies[key] = CompanyView(
            entity=entity, metrics=metrics, findings=entity.findings + entity.latest.findings + others + raised
        )
    return Snapshot(
        dataset=dataset,
        data_dir=settings.data_dir,
        companies=companies,
        findings=tuple(dataset.all_findings()) + tuple(finance_findings),
    )


@dataclass(frozen=True)
class Hit:
    company: CompanyView
    match: Match | None
    matched_key: str | None = None  # the share class that matched, when it is not the shown key


def _match(e: Entity, needle: str) -> Match | None:
    names = [n.casefold() for n in (e.name, *e.aliases) if n]
    if e.key.casefold() == needle:
        return "key"
    if e.ticker.casefold() == needle:
        return "ticker"
    if needle in names:
        return "name_exact"
    if any(needle in n for n in names):
        return "name_partial"
    return None


def search(snapshot: Snapshot, q: str | None) -> list[Hit]:
    """Companies matching ``q`` by key, ticker, exact name or partial name (names include aliases).

    Every share class of an issuer is tried; the issuer appears once with its best match (the shown
    class wins a tie) and ``matched_key`` naming the class when it is not the shown one. Best match
    type first, then by key. Without ``q`` every company is returned with no match type.
    """
    if not q or not q.strip():
        return [Hit(c, None) for c in snapshot.companies.values()]
    needle = q.strip().casefold()
    hits: list[Hit] = []
    for c in snapshot.companies.values():
        found = [(m, cls.entity.key) for cls in c.entity.classes if (m := _match(cls.entity, needle))]
        if found:
            match, key = min(found, key=lambda f: _MATCH_ORDER[f[0]])
            hits.append(Hit(c, match, key if key != c.entity.key else None))
    hits.sort(key=lambda h: (_MATCH_ORDER[h.match] if h.match else 0, h.company.entity.key))
    return hits


# --- read-only queries (the API layer only parses parameters and serialises the results) ----------


def list_companies(
    snapshot: Snapshot,
    q: str | None = None,
    sector: str | None = None,
    has_findings: Severity | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[Hit]]:
    """Search, then filter by sector (case-insensitive) and by having a finding of a severity.

    Returns the total number of matches and the requested page.
    """
    rows = search(snapshot, q)
    if sector:
        rows = [h for h in rows if (h.company.entity.sector or "").casefold() == sector.casefold()]
    if has_findings:
        rows = [h for h in rows if h.company.finding_counts[has_findings] > 0]
    return len(rows), rows[offset : offset + limit]


def list_findings(
    snapshot: Snapshot,
    severity: Severity | None = None,
    code: str | None = None,
    entity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[Finding]]:
    """Filter findings. With ``entity``, it returns exactly that company's own findings (the same list as
    its company page). A share-class key resolves to its issuer."""
    if entity is not None:
        company = snapshot.resolve(entity)
        pool: tuple[Finding, ...] = company.findings if company else ()
    else:
        pool = snapshot.findings
    items = [f for f in pool if (severity is None or f.severity == severity) and (code is None or f.code == code)]
    return len(items), items[offset : offset + limit]


@dataclass(frozen=True)
class DatasetOverview:
    records: int
    entities: int
    manual_additions: int
    by_severity: dict[Severity, int]
    by_code: list[tuple[str, Severity, str, int]]  # (code, severity, source, count), most frequent first


def dataset_overview(snapshot: Snapshot) -> DatasetOverview:
    by_severity = Counter(f.severity for f in snapshot.findings)
    by_code = Counter((f.code, f.severity, f.source) for f in snapshot.findings)
    return DatasetOverview(
        records=snapshot.dataset.record_count,
        entities=len(snapshot.companies),
        manual_additions=int(snapshot.dataset.metadata.get("manual_records", 0)),
        by_severity={s: by_severity.get(s, 0) for s in SEVERITIES},
        by_code=[
            (code, sev, src, n) for (code, sev, src), n in sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0][0]))
        ],
    )

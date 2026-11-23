"""The served snapshot: an immutable view of the dataset plus each company's computed metrics.

The snapshot is built once at start-up (with the retrieval index) and only read afterwards, so
concurrent requests need no locking. Query logic for every endpoint lives here, so the API layer
stays an adapter.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from comps.config import Settings
from comps.finance import compute_metrics, round_places, summarize
from comps.ingest import load_dataset
from comps.models import SEVERITIES, Dataset, Entity, Finding, Metrics, Severity, Summary
from comps.retrieval import (
    Index,
    NearDuplicates,
    Retriever,
    Selection,
    Skip,
    normalize_description,
    select_peers,
)
from comps.retrieval.embedding import EmbeddingRetriever

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
    ranker: Index  # description similarity over companies with a usable description
    duplicates: NearDuplicates  # near-duplicate test on the same index
    method: tuple[str, str]  # (name, model or version) of the ranker; for logs, never served

    def resolve(self, key: str, ignore_case: bool = False) -> CompanyView | None:
        """The company a listing key belongs to: any share-class key resolves to its issuer.

        Exact case by default; ``ignore_case`` is for the single-company lookup endpoint only.
        """
        parents = self.dataset.parents
        if ignore_case:
            # Keys are built from upper-cased codes, so case-folded keys are unique.
            folded = {k.casefold(): v for k, v in parents.items()}
            shown = folded.get(key.casefold())
        else:
            shown = parents.get(key)
        return self.companies.get(shown) if shown else None


def _texts(texts: Mapping[str, str | None]) -> dict[str, str]:
    """Only the usable (non-blank) texts."""
    return {k: t for k, t in texts.items() if t and t.strip()}


def build_snapshot(settings: Settings, retriever: Retriever | None = None) -> Snapshot:
    """Load and ingest ``settings.data_dir`` and index the descriptions.

    ``retriever`` defaults to the configured embedding model (``settings.retrieval``); tests pass a
    lighter one. Raises ``DatasetError`` if the input is unusable and ``ModelUnavailable`` if the model
    can't be loaded.
    """
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
    # Ranking compares business descriptions (own names removed in ingestion, see ingest.business_description), so
    # look-alike invented names don't make unrelated companies similar. The near-duplicate test uses the
    # descriptions as supplied: two listings of one company usually share their name, and that is real evidence
    # that they are the same company. One model embeds both (owner decision 2026-11-23).
    business = _texts({k: e.business_description for k, e in dataset.entities.items()})
    supplied = _texts({k: e.description for k, e in dataset.entities.items()})
    cfg = settings.retrieval
    if retriever is None:
        retriever = EmbeddingRetriever(cfg.model, cache_dir=cfg.cache_dir, offline=cfg.offline)
    ranker = retriever.fit(business)
    duplicates = NearDuplicates(
        index=retriever.fit(supplied),
        normalized={k: normalize_description(d) for k, d in supplied.items()},
        threshold=cfg.near_duplicate,
    )
    return Snapshot(
        dataset=dataset,
        data_dir=settings.data_dir,
        companies=companies,
        findings=tuple(dataset.all_findings()) + tuple(finance_findings),
        ranker=ranker,
        duplicates=duplicates,
        method=(retriever.name, getattr(retriever, "model", retriever.version)),
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


# --- peers and comps -------------------------------------------------------------------------------


class UnknownTarget(LookupError):
    pass


class UnknownExclude(ValueError):
    def __init__(self, keys: list[str]):
        super().__init__(f"Unknown company key(s) in exclude: {', '.join(keys)}.")
        self.keys = keys


@dataclass(frozen=True)
class Evidence:
    similarity: float
    classification: dict[str, bool]
    country_match: bool
    revenue_ratio: float | None


@dataclass(frozen=True)
class PeerView:
    rank: int
    company: CompanyView
    evidence: Evidence


@dataclass(frozen=True)
class SkippedView:
    company: CompanyView
    skip: Skip


@dataclass(frozen=True)
class PeersResult:
    target: CompanyView
    selection: Selection
    peers: tuple[PeerView, ...]
    skipped: tuple[SkippedView, ...]


@dataclass(frozen=True)
class CompsResult:
    peers: PeersResult
    summary: Summary


_METRIC_NAMES = frozenset(Metrics.__dataclass_fields__)


def _evidence(target: Entity, peer: Entity, similarity: float) -> Evidence:
    t_rev, p_rev = target.latest.usd.revenue, peer.latest.usd.revenue
    raw = p_rev / t_rev if t_rev is not None and p_rev is not None and t_rev > 0 else None
    # A ratio too large to represent (a tiny target revenue) is blank, like any non-finite value.
    ratio = round_places(raw, 2) if raw is not None and math.isfinite(raw) else None
    return Evidence(
        similarity=round_places(similarity, 4),
        classification={
            level: getattr(target, level) is not None and getattr(target, level) == getattr(peer, level)
            for level in ("sector", "industry", "sub_industry")
        },
        country_match=target.country == peer.country and target.country not in ("", "*"),
        revenue_ratio=ratio,
    )


def limitations(company: CompanyView) -> tuple[str, ...]:
    """Distinct codes of findings that affect one of the company's metrics."""
    return tuple(sorted({f.code for f in company.findings if _METRIC_NAMES & set(f.affects)}))


def find_peers(snapshot: Snapshot, target: str, k: int, exclude: list[str] | tuple[str, ...] = ()) -> PeersResult:
    """Choose up to ``k`` peers for ``target`` (exact-case key; share-class keys resolve).

    Raises ``UnknownTarget`` or ``UnknownExclude``. Empty ``exclude`` items are ignored; repeats count once.
    """
    company = snapshot.resolve(target)
    if company is None:
        raise UnknownTarget(target)
    keys = [x.strip() for x in exclude if x.strip()]
    unknown = [x for x in dict.fromkeys(keys) if snapshot.resolve(x) is None]
    if unknown:
        raise UnknownExclude(unknown)
    excluded = {snapshot.dataset.parents[x] for x in keys}
    t = company.entity
    selection = select_peers(
        t.key, k, universe=snapshot.companies, ranker=snapshot.ranker, duplicates=snapshot.duplicates, exclude=excluded
    )
    peers = tuple(
        PeerView(p.rank, snapshot.companies[p.key], _evidence(t, snapshot.companies[p.key].entity, p.similarity))
        for p in selection.peers
    )
    skipped = tuple(SkippedView(snapshot.companies[s.key], s) for s in selection.skipped)
    return PeersResult(target=company, selection=selection, peers=peers, skipped=skipped)


def build_comps(snapshot: Snapshot, target: str, k: int, exclude: list[str] | tuple[str, ...] = ()) -> CompsResult:
    """The comps table: ``find_peers`` plus peer-only summary statistics (the target is never included)."""
    result = find_peers(snapshot, target, k, exclude)
    return CompsResult(peers=result, summary=summarize([p.company.metrics for p in result.peers]))

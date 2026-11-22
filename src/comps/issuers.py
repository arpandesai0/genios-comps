"""Share-class merge: listings of one issuer become one company.

Rule (AGENTS.md §4, 2026-11-22). Two listings belong to one issuer when they are in the same known
country (never ``*``), have different tickers, and their latest records agree on every issuer-level
field (``ISSUER_FIELDS``). Ticker, name, price, price currency and share count may differ, because
those belong to a share class, not to the issuer. A merge also needs a non-empty description and at
least one financial value, so two near-empty records never merge on missing data.

The grouping uses a **disjoint-set union** (union-find). Every listing key starts as its own parent;
each merge rule unions pairs of keys; afterwards every set is re-rooted at its shown key (the most
valuable class), so ``parents[key]`` resolves any listing key to its issuer in one step.

Like the rest of ingestion, this never changes a value: classes keep their own records, and every
merge is reported as a finding.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import replace
from typing import Generic, TypeVar

from comps.models import Entity, Finding, Observation, ShareClass

ISSUER_FIELDS = (
    "description",
    "sector",
    "industry",
    "sub_industry",
    "fiscal_year_end",
    "reporting_currency",
    "units",
    "price_date",
    "total_debt",
    "cash",
    "revenue",
    "ebitda",
    "net_income",
)
_FINANCIALS = ("total_debt", "cash", "revenue", "ebitda", "net_income")
_UNKNOWN_COUNTRY = "*"
_ALL_METRICS = ("market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe")

T = TypeVar("T", bound=Hashable)


class DisjointSet(Generic[T]):
    """Union-find with path halving and union by size.

    ``find`` returns a set's current root. ``reroot`` makes a chosen member the root of its set and
    points every member straight at it, which is the form the dataset stores (``Dataset.parents``).
    """

    def __init__(self, items: Iterable[T]) -> None:
        self.parent: dict[T, T] = {x: x for x in items}
        self._size: dict[T, int] = {x: 1 for x in self.parent}

    def find(self, x: T) -> T:
        parent = self.parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path halving
            x = parent[x]
        return x

    def union(self, a: T, b: T) -> T:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self._size[ra] += self._size[rb]
        return ra

    def groups(self) -> dict[T, list[T]]:
        """Root -> members, each list in insertion order."""
        out: dict[T, list[T]] = {}
        for x in self.parent:
            out.setdefault(self.find(x), []).append(x)
        return out

    def reroot(self, root: T) -> None:
        """Make ``root`` the parent of every member of its set, including itself."""
        old = self.find(root)
        members = [x for x in self.parent if self.find(x) == old]
        for x in members:
            self.parent[x] = root
        self._size[root] = len(members)


def issuer_signature(entity: Entity) -> str | None:
    """Hash of the issuer-level fields of the latest record, or None if the listing can't be merged."""
    if entity.country in ("", _UNKNOWN_COUNTRY):
        return None
    raw = entity.latest.original
    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        return None
    if all(raw.get(f) is None for f in _FINANCIALS):
        return None
    content = {"country": entity.country, **{f: raw.get(f) for f in ISSUER_FIELDS}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


def market_value(obs: Observation) -> float | None:
    """Price x shares of one listing, used only to order classes. None when it can't be computed."""
    if obs.usd.price is None or obs.shares_outstanding is None:
        return None
    v = obs.usd.price * obs.shares_outstanding
    return v if math.isfinite(v) else None


def _class_order(e: Entity) -> tuple[bool, float, str]:
    v = market_value(e.latest)
    return (v is None, -(v or 0.0), e.key)


def _listing_identity(obs: Observation) -> tuple | None:
    """What makes two classes the same shares listed twice; None when price or shares are unusable."""
    if obs.usd.price is None or obs.shares_outstanding is None:
        return None
    raw = obs.original
    return (raw.get("price"), raw.get("price_currency"), raw.get("shares_outstanding"))


def merge_share_classes(entities: Mapping[str, Entity]) -> tuple[dict[str, Entity], dict[str, str]]:
    """Merge share classes into issuers.

    Returns the issuers keyed by shown key (sorted by key) and the parent pointer of every listing key.
    """
    dsu: DisjointSet[str] = DisjointSet(entities)
    by_signature: dict[str, str] = {}
    for key, e in entities.items():
        sig = issuer_signature(e)
        if sig is None:
            continue
        if sig in by_signature:
            dsu.union(by_signature[sig], key)
        else:
            by_signature[sig] = key

    issuers: dict[str, Entity] = {}
    for members in dsu.groups().values():
        ordered = sorted((entities[k] for k in members), key=_class_order)
        shown = ordered[0]
        dsu.reroot(shown.key)
        issuers[shown.key] = shown if len(ordered) == 1 else _issuer(ordered)
    return dict(sorted(issuers.items())), dict(sorted(dsu.parent.items()))


def _issuer(ordered: list[Entity]) -> Entity:
    shown = ordered[0]
    keys = tuple(e.key for e in ordered)
    record_ids = tuple(e.latest.record_id for e in ordered)

    classes: list[ShareClass] = []
    seen: dict[tuple, str] = {}
    findings: list[Finding] = [
        Finding(
            code="share_classes_merged",
            severity="info",
            fields=("ticker", "name", "price", "shares_outstanding"),
            message=f"{', '.join(keys)} have identical issuer-level data (description, classification, "
            "financials and price date), so they are treated as share classes of one company, shown as "
            f"{shown.key} (the most valuable class). Market cap adds up every counted class; debt, cash "
            "and the financials are counted once.",
            affects=("identity", *_ALL_METRICS),
            record_ids=record_ids,
            entity_keys=keys,
        )
    ]
    for i, e in enumerate(ordered):
        identity = _listing_identity(e.latest)
        counted = identity is None or identity not in seen
        if not counted:
            assert identity is not None
            findings.append(
                Finding(
                    code="duplicate_share_listing",
                    severity="info",
                    fields=("price", "price_currency", "shares_outstanding"),
                    message=f"{e.key} has the same price, price currency and share count as {seen[identity]}, "
                    "so it is taken to be the same shares listed twice and counted once in market cap.",
                    affects=("market_cap_usd_m",),
                    record_ids=(e.latest.record_id,),
                    entity_keys=(shown.key, e.key),
                )
            )
        elif identity is not None:
            seen[identity] = e.key
        if i > 0 and identity is None:
            values = {"price": e.latest.usd.price, "shares_outstanding": e.latest.shares_outstanding}
            missing = [f for f, v in values.items() if v is None]
            findings.append(
                Finding(
                    code="share_class_incomplete",
                    severity="limitation",
                    fields=tuple(missing),
                    message=f"Share class {e.key} has no usable {' or '.join(missing)}, so the issuer's market cap "
                    "and everything computed from it are left blank rather than summed from the other classes.",
                    affects=_ALL_METRICS,
                    record_ids=(e.latest.record_id,),
                    entity_keys=(shown.key, e.key),
                )
            )
        classes.append(ShareClass(entity=shown if i == 0 else _relabel(e, shown.key), counted=counted))

    aliases = tuple(dict.fromkeys(a for e in ordered for a in e.aliases))
    return replace(
        shown,
        aliases=aliases,
        findings=shown.findings + tuple(findings),
        share_classes=tuple(classes),
    )


def _relabel(e: Entity, shown_key: str) -> Entity:
    """Name the issuer's shown key first in every finding of a non-shown class."""

    def fix(f: Finding) -> Finding:
        return replace(f, entity_keys=(shown_key, *(k for k in f.entity_keys if k != shown_key)))

    def fix_obs(o: Observation) -> Observation:
        return replace(o, findings=tuple(fix(f) for f in o.findings))

    return replace(
        e,
        findings=tuple(fix(f) for f in e.findings),
        observations=tuple(fix_obs(o) for o in e.observations),
        superseded=tuple(fix_obs(o) for o in e.superseded),
    )

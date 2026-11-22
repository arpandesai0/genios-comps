"""Cross-record data-quality checks that run once share classes are merged into issuers.

Each check only adds findings and never changes an entity's data.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from comps.config import IngestConfig
from comps.models import Entity, Finding

_PRICE_METRICS = ("market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe")


def cross_entity_findings(
    entities: Mapping[str, Entity], reference_date: date | None, config: IngestConfig
) -> dict[str, list[Finding]]:
    out: dict[str, list[Finding]] = {}
    for check in (
        _shared_names(entities),
        _freshness(entities, reference_date, config),
    ):
        for key, finding in check:
            out.setdefault(key, []).append(finding)
    return out


def _groups(entities: Mapping[str, Entity], keyfunc) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for key, e in entities.items():
        k = keyfunc(e)
        if k:
            groups.setdefault(k, []).append(key)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def _shared_names(entities):
    for group in _groups(entities, lambda e: (e.name or "").casefold() or None):
        for key in group:
            others = [k for k in group if k != key]
            yield (
                key,
                Finding(
                    code="shared_name",
                    severity="warning",
                    fields=("name",),
                    message=f"Name {entities[key].name!r} is also used by {', '.join(others)}; "
                    "search by name is ambiguous.",
                    affects=("search",),
                    entity_keys=tuple(group),
                ),
            )


def _freshness(entities, reference_date, config):
    if reference_date is None:
        return
    cutoff = reference_date - timedelta(days=config.stale_after_days)
    for key, e in entities.items():
        d = e.latest.price_date
        if d is None:
            continue
        if d < cutoff:
            yield (
                key,
                Finding(
                    code="stale_price",
                    severity="warning",
                    fields=("price_date",),
                    message=f"Latest price is from {d}, {(reference_date - d).days} days before the reference date "
                    f"{reference_date} (threshold {config.stale_after_days} days).",
                    affects=_PRICE_METRICS,
                    record_ids=(e.latest.record_id,),
                    entity_keys=(key,),
                ),
            )

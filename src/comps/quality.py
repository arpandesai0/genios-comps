"""Cross-record data-quality checks that run once entities are resolved.

Each check only adds findings and never changes an entity's data.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Mapping

from comps.config import IngestConfig
from comps.models import Entity, Finding

_PRICE_METRICS = ("market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe")


def cross_entity_findings(
    entities: Mapping[str, Entity], reference_date: date | None, config: IngestConfig
) -> dict[str, list[Finding]]:
    out: dict[str, list[Finding]] = {}
    for check in (_possible_same_issuer(entities), _shared_names(entities),
                  _freshness(entities, reference_date, config)):
        for key, finding in check:
            out.setdefault(key, []).append(finding)
    return out


def issuer_signature(entity: Entity) -> str:
    """Latest record content without id, ticker and name. Equal signatures under different keys
    suggest the same issuer listed twice (e.g. share classes)."""
    content = {k: v for k, v in entity.latest.original.items() if k not in ("id", "ticker", "name")}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


def _groups(entities: Mapping[str, Entity], keyfunc) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for key, e in entities.items():
        k = keyfunc(e)
        if k:
            groups.setdefault(k, []).append(key)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def _possible_same_issuer(entities):
    for group in _groups(entities, issuer_signature):
        for key in group:
            others = [k for k in group if k != key]
            yield key, Finding(
                code="possible_same_issuer", severity="warning",
                fields=("ticker", "name"),
                message=f"Identical description and financials to {', '.join(others)} under a different ticker "
                        "(possibly another share class or a duplicate listing). Not merged; they are kept out of "
                        "each other's peer lists.",
                affects=("peer_selection", "summary_statistics"),
                record_ids=tuple(r for k in group for r in entities[k].record_ids),
                entity_keys=tuple(group),
            )


def _shared_names(entities):
    same_issuer = {frozenset(g) for g in _groups(entities, issuer_signature)}
    for group in _groups(entities, lambda e: (e.name or "").casefold() or None):
        if frozenset(group) in same_issuer:
            continue  # already explained by possible_same_issuer
        for key in group:
            others = [k for k in group if k != key]
            yield key, Finding(
                code="shared_name", severity="warning", fields=("name",),
                message=f"Name {entities[key].name!r} is also used by {', '.join(others)}; search by name is ambiguous.",
                affects=("search",), entity_keys=tuple(group),
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
            yield key, Finding(
                code="stale_price", severity="warning", fields=("price_date",),
                message=f"Latest price is from {d}, {(reference_date - d).days} days before the reference date "
                        f"{reference_date} (threshold {config.stale_after_days} days).",
                affects=_PRICE_METRICS, record_ids=(e.latest.record_id,), entity_keys=(key,),
            )
        elif d > reference_date:
            yield key, Finding(
                code="future_price_date", severity="warning", fields=("price_date",),
                message=f"Price date {d} is after the reference date {reference_date}.",
                affects=("freshness",), record_ids=(e.latest.record_id,), entity_keys=(key,),
            )

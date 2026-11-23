"""Score captured pipeline output against golden labels. Never imports the pipeline.

Input is what ``run.py`` captured: the ``GET /api/peers`` response for every query, exactly as served.
Golden data is the fixture's ``labels.json`` (graded 0-3 relevance) or the dedup ``pairs.json``.

Retrieval metrics (docs/eval.md):

- nDCG@k (main): gain 2^rel - 1, log2 discount; the ideal ranking uses every labelled candidate.
- precision@k: share of the k slots holding a relevant peer (rel >= threshold); empty slots are misses.
  Reported with its ceiling, min(#relevant, k) / k.
- recall@k: relevant peers in the top k / all relevant candidates.
- per-tag means, how often a duplicate listing appeared and how often both copies of one company
  appeared in the same list (the real failure), and the geography lift (same-country share among
  irrelevant peers returned / that share among all irrelevant candidates).

Dedup metrics: each pair's score is the similarity of ``b`` in ``a``'s response (as a peer or as a
skipped near-duplicate); a pair whose ``b`` isn't in the response window scores ``None`` (below any
threshold). Reported: precision / recall at the served threshold, and the highest recall reachable
with no false duplicate (threshold just above the best-scoring non-duplicate).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

CUTOFFS = (5, 10)
TAGS = ("paraphrase", "cross_country", "mislabelled", "boilerplate", "geo_trap", "jargon")


def dcg(gains: Sequence[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at(ranked: Sequence[str], labels: Mapping[str, int], k: int) -> float:
    gains = [2 ** labels.get(key, 0) - 1 for key in ranked[:k]]
    ideal = sorted((2**rel - 1 for rel in labels.values()), reverse=True)[:k]
    best = dcg(ideal)
    return dcg(gains) / best if best > 0 else 0.0


def precision_at(ranked: Sequence[str], labels: Mapping[str, int], k: int, threshold: int) -> float:
    return sum(1 for key in ranked[:k] if labels.get(key, 0) >= threshold) / k


def recall_at(ranked: Sequence[str], labels: Mapping[str, int], k: int, threshold: int) -> float | None:
    relevant = sum(1 for rel in labels.values() if rel >= threshold)
    if relevant == 0:
        return None
    return sum(1 for key in ranked[:k] if labels.get(key, 0) >= threshold) / relevant


def _mean(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.fmean(vals), 4) if vals else None


def _ratio(a: float | None, b: float | None) -> float | None:
    return round(a / b, 4) if a is not None and b else None


def peer_keys(response: Mapping[str, Any]) -> list[str]:
    return [p["entity"]["key"] for p in response["peers"]]


def score_retrieval(
    responses: Mapping[str, Mapping[str, Any]],
    spec: Mapping[str, Any],
    countries: Mapping[str, str],
    split: str,
) -> dict[str, Any]:
    """Metrics for one split. ``countries`` maps every key to its country (from the fixture input)."""
    threshold = spec["relevant_threshold"]
    aliases: dict[str, str] = spec.get("aliases", {})
    k_max = max(CUTOFFS)
    rows = []
    geo = {"irrelevant_returned": 0, "same_country_returned": 0, "irrelevant_pool": 0, "same_country_pool": 0}
    for target in spec["splits"][split]:
        labels = dict(spec["labels"][target])
        returned = peer_keys(responses[target])
        ranked = list(dict.fromkeys(aliases.get(k, k) for k in returned if aliases.get(k, k) != target))
        country = countries[target]
        irrelevant_top = [k for k in ranked[:k_max] if labels.get(k, 0) == 0]
        pool = [k for k, rel in labels.items() if rel == 0]
        geo["irrelevant_returned"] += len(irrelevant_top)
        geo["same_country_returned"] += sum(countries[k] == country for k in irrelevant_top)
        geo["irrelevant_pool"] += len(pool)
        geo["same_country_pool"] += sum(countries[k] == country for k in pool)
        row: dict[str, Any] = {
            "target": target,
            "tags": spec["tags"][target],
            "returned": returned,
            "duplicate_returned": [k for k in returned if k in aliases],
            "both_copies_returned": [a for a, o in aliases.items() if a in returned and o in returned],
        }
        relevant = sum(1 for rel in labels.values() if rel >= threshold)
        for k in CUTOFFS:
            row[f"ndcg@{k}"] = round(ndcg_at(ranked, labels, k), 4)
            row[f"precision@{k}"] = round(precision_at(ranked, labels, k, threshold), 4)
            row[f"precision@{k}_ceiling"] = round(min(relevant, k) / k, 4)
            recall = recall_at(ranked, labels, k, threshold)
            row[f"recall@{k}"] = None if recall is None else round(recall, 4)
        rows.append(row)

    metrics = [m for k in CUTOFFS for m in (f"ndcg@{k}", f"precision@{k}", f"precision@{k}_ceiling", f"recall@{k}")]
    by_tag = {
        tag: {"targets": len(sel), "ndcg@10": _mean(r["ndcg@10"] for r in sel)}
        for tag in TAGS
        if (sel := [r for r in rows if tag in r["tags"]])
    }
    if untagged := [r for r in rows if not r["tags"]]:
        by_tag["(none)"] = {"targets": len(untagged), "ndcg@10": _mean(r["ndcg@10"] for r in untagged)}
    returned_share = _ratio(geo["same_country_returned"], geo["irrelevant_returned"])
    pool_share = _ratio(geo["same_country_pool"], geo["irrelevant_pool"])
    return {
        "split": split,
        "targets": len(rows),
        "overall": {m: _mean(r[m] for r in rows) for m in metrics},
        "by_tag": by_tag,
        # Times a second listing appeared among the peers (fine on its own: it stands in for its original).
        "duplicate_listing_returned": sum(len(r["duplicate_returned"]) for r in rows),
        # Times both listings of one company appeared in the same peer list: the failure dedup must prevent.
        "both_copies_returned": sum(len(r["both_copies_returned"]) for r in rows),
        "geography_lift": _ratio(returned_share, pool_share),
        "per_target": rows,
    }


def pair_score(response: Mapping[str, Any], other: str) -> float | None:
    """Similarity of ``other`` in a peers response (peer or skipped), or None if it isn't there."""
    for p in response["peers"]:
        if p["entity"]["key"] == other:
            return float(p["evidence"]["similarity"])
    for s in response["skipped"]:
        if s["entity"]["key"] == other and s["similarity"] is not None:
            return float(s["similarity"])
    return None


def score_dedup(
    scores: Sequence[tuple[float | None, bool, str]],
    served_threshold: float | None = None,
) -> dict[str, Any]:
    """``scores``: (score, is_duplicate, kind) per pair."""
    dups = [s for s, d, _ in scores if d]
    negs = [s for s, d, _ in scores if not d]
    top_negative = max((s for s in negs if s is not None), default=None)
    # Lowest threshold with no false duplicate: strictly above the best-scoring non-duplicate.
    caught = [s for s in dups if s is not None and (top_negative is None or s > top_negative)]
    out: dict[str, Any] = {
        "pairs": len(scores),
        "duplicates": len(dups),
        "top_non_duplicate_score": top_negative,
        "recall_at_zero_false_duplicates": round(len(caught) / len(dups), 4) if dups else None,
        "lowest_duplicate_score": min((s for s in dups if s is not None), default=None),
        "by_kind": {},
    }
    for kind in sorted({k for _, _, k in scores}):
        sel = [(s, d) for s, d, k in scores if k == kind]
        vals = [s for s, _ in sel if s is not None]
        out["by_kind"][kind] = {
            "pairs": len(sel),
            "duplicate": sel[0][1],
            "min": min(vals, default=None),
            "max": max(vals, default=None),
            "mean": _mean(vals),
        }
    if served_threshold is not None:
        flagged = [(s, d) for s, d, _ in scores if s is not None and s >= served_threshold]
        tp = sum(d for _, d in flagged)
        out["served_threshold"] = served_threshold
        out["precision_at_served"] = round(tp / len(flagged), 4) if flagged else None
        out["recall_at_served"] = round(tp / len(dups), 4) if dups else None
    return out

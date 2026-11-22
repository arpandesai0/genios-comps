"""Retrieval eval: score the served peer selection against graded synthetic labels.

It runs the real pipeline (files -> snapshot -> ``find_peers``), so it measures exactly what the API
serves. Metrics (AGENTS.md §4, 2026-11-22):

- nDCG@k (main): graded gain 2^rel - 1, log2 discount; the ideal ranking uses every labelled candidate.
- precision@k: share of the k slots holding a relevant peer (rel >= ``relevant_threshold``); an empty
  slot (fewer than k returned) counts as not relevant.
- recall@k: relevant peers returned in the top k / all relevant candidates.
- per-tag means (paraphrase, cross_country, mislabelled, boilerplate, geo_trap) and a geography-leak
  check: the share of top-k peers that are irrelevant (rel 0) but in the target's country.

Keys under ``aliases`` are second listings of the same company: a returned alias scores as its
original, and only the first of the two counts. The service should skip the duplicate as a
near-duplicate; ``duplicate_listing_returned`` counts the times it didn't.

``precision@k`` has a ceiling below 1 when a target has fewer than k relevant candidates; the ceiling
is reported next to it. The geography check compares the share of same-country companies among the
irrelevant peers returned with their share among all irrelevant candidates (a lift above 1 means
country words pull unrelated companies up).

Usage (repo root):

    .venv/bin/python eval/retrieval_eval.py --split dev [--out eval/results/retrieval_tfidf_v1_dev.json]

The held-out split is scored only when the owner calls a configuration final.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from comps.config import IngestConfig, Settings
from comps.service import Snapshot, build_snapshot, find_peers

FIXTURE = Path(__file__).parent / "fixtures" / "retrieval"
CUTOFFS = (5, 10)
TAGS = ("paraphrase", "cross_country", "mislabelled", "boilerplate", "geo_trap")


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


def _mean(values: Sequence[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.fmean(vals), 4) if vals else None


def _ratio(a: float | None, b: float | None) -> float | None:
    return round(a / b, 4) if a is not None and b else None


def evaluate(snapshot: Snapshot, spec: Mapping, split: str) -> dict:
    threshold = spec["relevant_threshold"]
    aliases: dict[str, str] = spec.get("aliases", {})
    k_max = max(CUTOFFS)
    per_target = []
    geo = {"irrelevant_returned": 0, "same_country_returned": 0, "irrelevant_pool": 0, "same_country_pool": 0}
    for target in spec["splits"][split]:
        labels = dict(spec["labels"][target])
        result = find_peers(snapshot, target, k_max)
        returned = [p.company.entity.key for p in result.peers]
        ranked = list(dict.fromkeys(aliases.get(k, k) for k in returned if aliases.get(k, k) != target))
        country = snapshot.companies[target].entity.country

        def same_country(key: str, country: str = country) -> bool:
            return snapshot.companies[key].entity.country == country

        irrelevant_top = [k for k in ranked[:10] if labels.get(k, 0) == 0]
        pool = [k for k, rel in labels.items() if rel == 0]
        geo["irrelevant_returned"] += len(irrelevant_top)
        geo["same_country_returned"] += sum(map(same_country, irrelevant_top))
        geo["irrelevant_pool"] += len(pool)
        geo["same_country_pool"] += sum(map(same_country, pool))
        row = {
            "target": target,
            "business": spec["business"][target],
            "tags": spec["tags"][target],
            "returned": returned,
            "duplicate_returned": [k for k in returned if k in aliases or aliases.get(target) == k],
            "note": result.selection.note,
        }
        for k in CUTOFFS:
            row[f"ndcg@{k}"] = round(ndcg_at(ranked, labels, k), 4)
            row[f"precision@{k}"] = round(precision_at(ranked, labels, k, threshold), 4)
            relevant = sum(1 for rel in labels.values() if rel >= threshold)
            row[f"precision@{k}_ceiling"] = round(min(relevant, k) / k, 4)
            recall = recall_at(ranked, labels, k, threshold)
            row[f"recall@{k}"] = None if recall is None else round(recall, 4)
        per_target.append(row)

    metric_names = [
        name for k in CUTOFFS for name in (f"ndcg@{k}", f"precision@{k}", f"precision@{k}_ceiling", f"recall@{k}")
    ]
    overall = {m: _mean([r[m] for r in per_target]) for m in metric_names}
    by_tag = {
        tag: {"targets": len(rows), **{m: _mean([r[m] for r in rows]) for m in ("ndcg@10", "precision@10")}}
        for tag in TAGS
        if (rows := [r for r in per_target if tag in r["tags"]])
    }
    untagged = [r for r in per_target if not r["tags"]]
    if untagged:
        by_tag["(none)"] = {
            "targets": len(untagged),
            **{m: _mean([r[m] for r in untagged]) for m in ("ndcg@10", "precision@10")},
        }
    return {
        "method": {"name": snapshot.method[0], "version": snapshot.method[1]},
        "dataset_version": snapshot.dataset.version,
        "split": split,
        "targets": len(per_target),
        "relevant_threshold": threshold,
        "overall": overall,
        "by_tag": by_tag,
        "duplicate_listing_returned": sum(len(r["duplicate_returned"]) for r in per_target),
        "geography": {
            **geo,
            "same_country_share_returned": _ratio(geo["same_country_returned"], geo["irrelevant_returned"]),
            "same_country_share_pool": _ratio(geo["same_country_pool"], geo["irrelevant_pool"]),
            "lift": _ratio(
                _ratio(geo["same_country_returned"], geo["irrelevant_returned"]),
                _ratio(geo["same_country_pool"], geo["irrelevant_pool"]),
            ),
        },
        "per_target": per_target,
    }


def load(fixture: Path = FIXTURE) -> tuple[Snapshot, dict]:
    snapshot = build_snapshot(Settings(data_dir=fixture, ingest=IngestConfig()))
    spec = json.loads((fixture / "labels.json").read_text())
    return snapshot, spec


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--split", choices=("dev", "held_out"), default="dev")
    parser.add_argument("--out", type=Path, help="write the full result as JSON here")
    args = parser.parse_args(argv)
    snapshot, spec = load()
    result = evaluate(snapshot, spec, args.split)
    keys = ("method", "split", "targets", "overall", "by_tag", "duplicate_listing_returned", "geography")
    summary = {k: result[k] for k in keys}
    print(json.dumps(summary, indent=2))
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

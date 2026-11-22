"""Peer selection: walk the ranking until k peers are chosen, skipping with reasons.

Rules (AGENTS.md §4, 2026-11-22):

- Candidates are every other company with a description, ranked by similarity (ties by key).
- A candidate is skipped when the analyst excluded it, when it is a near-duplicate of the target, or
  when it is a near-duplicate of a peer already chosen (the higher-ranked one stays).
- Near-duplicates: identical descriptions after normalizing case and whitespace, or a description
  TF-IDF cosine of at least ``NEAR_DUPLICATE_COSINE``.
- A company without a description is never ranked (``no_description``). A target without one gets
  no peers and a note.
- If the ranking runs out, fewer than k peers are returned with a note; the list is never padded.

This module only chooses keys. Metrics, evidence and serialisation happen elsewhere.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Literal

from comps.retrieval.base import Index

NEAR_DUPLICATE_COSINE = 0.95

SkipReason = Literal["near_duplicate_of_target", "near_duplicate_of_peer", "user_excluded", "no_description"]


@dataclass(frozen=True)
class Pick:
    key: str
    rank: int
    similarity: float


@dataclass(frozen=True)
class Skip:
    key: str
    reason: SkipReason
    detail: str
    similarity: float | None = None
    duplicate_of: str | None = None


@dataclass(frozen=True)
class Selection:
    target: str
    requested_k: int
    peers: tuple[Pick, ...]
    skipped: tuple[Skip, ...]
    note: str | None


def normalize_description(text: str) -> str:
    return " ".join(text.casefold().split())


@dataclass(frozen=True, eq=False)
class NearDuplicates:
    """The near-duplicate test. Its index must be TF-IDF with the served settings, so the test doesn't
    change when the ranker does; while the ranker is that same TF-IDF, the snapshot passes one index."""

    index: Index
    normalized: Mapping[str, str]  # key -> normalized description

    def check(self, a: str, b: str) -> float | None:
        """The cosine when ``a`` and ``b`` are near-duplicates (1.0 for identical text), else None."""
        if self.normalized[a] == self.normalized[b]:
            return 1.0
        cos = self.index.similarity(a, b)
        return cos if cos >= NEAR_DUPLICATE_COSINE else None


def select_peers(
    target: str,
    k: int,
    *,
    universe: Collection[str],
    ranker: Index,
    duplicates: NearDuplicates,
    exclude: Collection[str] = (),
) -> Selection:
    """Choose up to ``k`` peers for ``target``.

    ``universe`` is every company key; ``ranker`` and ``duplicates`` cover the ones with a description.
    ``exclude`` holds company keys the analyst removed (the target itself is ignored if present).
    """
    ranked_keys = set(ranker.keys)
    excluded = set(exclude) - {target}
    # A company appears in `skipped` once: an excluded company without a description is user_excluded.
    no_description = tuple(
        Skip(key, "no_description", f"{key} has no usable description, so it cannot be ranked.")
        for key in sorted(universe)
        if key not in ranked_keys and key != target and key not in excluded
    )
    if target not in ranked_keys:
        why = f"{target} has no usable description, so no peers can be ranked by similarity."
        excluded_skips = tuple(
            Skip(key, "user_excluded", f"{key} was removed by the analyst.") for key in sorted(excluded)
        )
        return Selection(target, k, (), excluded_skips + no_description, why)

    scores = ranker.similarities(target)
    ranking = sorted(scores, key=lambda key: (-scores[key], key))

    peers: list[Pick] = []
    skipped: list[Skip] = []
    for key in ranking:
        if len(peers) == k:
            break
        sim = scores[key]
        if key in excluded:
            skipped.append(Skip(key, "user_excluded", f"{key} was removed by the analyst.", sim))
            continue
        cos = duplicates.check(key, target)
        if cos is not None:
            detail = f"Near-duplicate of the target {target} (description cosine {cos:.2f})."
            skipped.append(Skip(key, "near_duplicate_of_target", detail, sim, target))
            continue
        twin = next(((p.key, c) for p in peers if (c := duplicates.check(key, p.key)) is not None), None)
        if twin is not None:
            detail = f"Near-duplicate of peer {twin[0]} (description cosine {twin[1]:.2f}), which ranks higher."
            skipped.append(Skip(key, "near_duplicate_of_peer", detail, sim, twin[0]))
            continue
        peers.append(Pick(key, len(peers) + 1, sim))

    met = {s.key for s in skipped}
    skipped += [Skip(key, "user_excluded", f"{key} was removed by the analyst.") for key in sorted(excluded - met)]

    note: str | None = None
    if len(peers) < k:
        note = f"Only {len(peers)} of the {k} requested peers: every company that could be ranked was used" + (
            f", after {len(met)} skipped." if met else "."
        )
    return Selection(target, k, tuple(peers), tuple(skipped) + no_description, note)

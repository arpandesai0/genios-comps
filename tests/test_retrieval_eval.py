"""The retrieval eval: metric arithmetic, fixture integrity, and that the committed result is current."""

import json
import math
import sys
from pathlib import Path

import pytest
from retrieval_eval import FIXTURE, evaluate, load, ndcg_at, precision_at, recall_at

ROOT = Path(__file__).parent.parent
RESULT = ROOT / "eval" / "results" / "retrieval_tfidf_v1_dev.json"


def test_ndcg_is_one_for_the_ideal_ranking_and_discounts_later_hits():
    labels = {"a": 3, "b": 2, "c": 0, "d": 1}
    assert ndcg_at(["a", "b", "d", "c"], labels, 4) == pytest.approx(1.0)
    swapped = ndcg_at(["b", "a"], labels, 2)
    ideal = 7 + 3 / math.log2(3)
    assert swapped == pytest.approx((3 + 7 / math.log2(3)) / ideal)
    assert ndcg_at([], labels, 5) == 0.0
    assert ndcg_at(["a"], {"a": 0}, 5) == 0.0  # nothing relevant: defined as 0


def test_precision_counts_empty_slots_and_recall_uses_all_relevant():
    labels = {"a": 3, "b": 3, "c": 2}
    assert precision_at(["a", "c"], labels, 5, threshold=3) == 0.2
    assert recall_at(["a", "c"], labels, 5, threshold=3) == 0.5
    assert recall_at(["a"], {"a": 1}, 5, threshold=3) is None


def test_fixture_is_in_sync_with_its_builder(tmp_path):
    sys.path.insert(0, str(FIXTURE))
    try:
        import build_fixture
    finally:
        sys.path.remove(str(FIXTURE))
    build_fixture.build(tmp_path)
    for name in ("companies.json", "fx_rates.json", "labels.json"):
        assert (tmp_path / name).read_text() == (FIXTURE / name).read_text(), f"{name}: rerun build_fixture.py"


def test_labels_cover_every_company_and_splits_are_disjoint_and_balanced():
    snapshot, spec = load()
    companies = set(snapshot.companies)
    labelled = set(spec["labels"])
    assert labelled | set(spec["aliases"]) == companies
    for target, row in spec["labels"].items():
        assert set(row) == labelled - {target} and set(row.values()) <= {0, 1, 2, 3}
    dev, held = set(spec["splits"]["dev"]), set(spec["splits"]["held_out"])
    assert not dev & held and dev | held == labelled and abs(len(dev) - len(held)) <= 3
    assert {spec["business"][k] for k in dev} == {spec["business"][k] for k in held}


def test_the_duplicate_listing_is_never_returned_as_a_peer():
    snapshot, spec = load()
    for split in ("dev", "held_out"):
        assert evaluate(snapshot, spec, split)["duplicate_listing_returned"] == 0


def test_committed_dev_result_matches_a_fresh_run():
    """Any change to what is served must come with an updated eval result (AGENTS.md): run `make eval`."""
    snapshot, spec = load()
    assert json.loads(RESULT.read_text()) == evaluate(snapshot, spec, "dev")

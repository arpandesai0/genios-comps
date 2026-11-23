"""The eval: metric arithmetic, fixture integrity, the black-box capture, and the experiment log.

The pipeline is only reached over HTTP (here through FastAPI's TestClient with the light TF-IDF
retriever, so no model download is needed). The committed experiments are checked by rescoring their
captured output, without running the pipeline.
"""

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import experiments
import pytest
import run
from fastapi.testclient import TestClient
from score import ndcg_at, pair_score, precision_at, recall_at, score_dedup, score_retrieval

from comps.api import create_app
from comps.config import IngestConfig, Settings
from comps.retrieval import TfidfRetriever
from comps.service import build_snapshot

ROOT = Path(__file__).parent.parent
FIXTURES = {f.name: f for f in run.FIXTURES}


# --- metrics ---------------------------------------------------------------------------------------


def test_ndcg_is_one_for_the_ideal_ranking_and_discounts_later_hits():
    labels = {"a": 3, "b": 2, "c": 0, "d": 1}
    assert ndcg_at(["a", "b", "d", "c"], labels, 4) == pytest.approx(1.0)
    swapped = ndcg_at(["b", "a"], labels, 2)
    ideal = 7 + 3 / math.log2(3)
    assert swapped == pytest.approx((3 + 7 / math.log2(3)) / ideal)
    assert ndcg_at(["b", "c", "a"], labels, 3) == pytest.approx(0.692, abs=5e-4)  # docs/eval.md example
    assert ndcg_at([], labels, 5) == 0.0
    assert ndcg_at(["a"], {"a": 0}, 5) == 0.0  # nothing relevant: defined as 0


def test_precision_counts_empty_slots_and_recall_uses_all_relevant():
    labels = {"a": 3, "b": 3, "c": 2}
    assert precision_at(["a", "c"], labels, 5, threshold=3) == 0.2
    assert recall_at(["a", "c"], labels, 5, threshold=3) == 0.5
    assert recall_at(["a"], {"a": 1}, 5, threshold=3) is None


def test_dedup_scoring_finds_the_strictest_cut_without_false_duplicates():
    rows = [
        (1.0, True, "x"),
        (0.9, True, "x"),
        (0.7, True, "y"),
        (None, True, "y"),
        (0.8, False, "z"),
        (None, False, "z"),
    ]
    out = score_dedup(rows, served_threshold=0.75)
    assert out["top_non_duplicate_score"] == 0.8
    assert out["recall_at_zero_false_duplicates"] == 0.5  # 1.0 and 0.9 are above 0.8
    assert (out["precision_at_served"], out["recall_at_served"]) == (round(2 / 3, 4), 0.5)
    assert out["by_kind"]["y"] == {"pairs": 2, "duplicate": True, "min": 0.7, "max": 0.7, "mean": 0.7}


def test_runner_ignores_service_settings_from_the_shell(monkeypatch, tmp_path):
    monkeypatch.setenv("EMBEDDING_MODEL", "leaked/model")
    monkeypatch.setenv("NEAR_DUPLICATE_THRESHOLD", "0.5")
    env = run.service_env(tmp_path, {"MODEL_CACHE_DIR": "/c"}, tmp_path / "data")
    assert "EMBEDDING_MODEL" not in env and "NEAR_DUPLICATE_THRESHOLD" not in env
    assert env["MODEL_CACHE_DIR"] == "/c" and env["DATA_DIR"] == str(tmp_path / "data")
    assert env["PYTHONPATH"] == str(tmp_path / "src")


def test_latency_stats_use_nearest_rank_percentiles():
    stats = run.latency_stats([float(x) for x in range(1, 21)])  # 1..20 ms
    assert stats == {"n": 20, "min": 1.0, "mean": 10.5, "p50": 10.0, "p95": 19.0, "max": 20.0}


def test_pair_score_reads_peers_and_skipped():
    response = {
        "peers": [{"entity": {"key": "B"}, "evidence": {"similarity": 0.5}}],
        "skipped": [{"entity": {"key": "C"}, "similarity": 0.97}, {"entity": {"key": "D"}, "similarity": None}],
    }
    assert (pair_score(response, "B"), pair_score(response, "C")) == (0.5, 0.97)
    assert pair_score(response, "D") is None and pair_score(response, "E") is None


# --- fixtures --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("folder", "script", "files"),
    [
        ("retrieval", "build_fixture", ("companies.json", "fx_rates.json", "labels.json")),
        ("independent", "build_fixture", ("companies.json", "fx_rates.json", "labels.json")),
        ("dedup", "build_pairs", ("pairs.json",)),
    ],
)
def test_fixtures_are_in_sync_with_their_builders(tmp_path, folder, script, files):
    path = ROOT / "eval" / "fixtures" / folder
    sys.path.insert(0, str(path))
    try:
        module = __import__(script)
        sys.modules.pop(script)
    finally:
        sys.path.remove(str(path))
    module.build(tmp_path)
    for name in files:
        assert (tmp_path / name).read_text() == (path / name).read_text(), f"{folder}/{name}: rerun {script}.py"


def _snapshot(data_dir: Path):
    return build_snapshot(Settings(data_dir=data_dir, ingest=IngestConfig()), TfidfRetriever())


@pytest.mark.parametrize("name", ["retrieval_v1", "independent"])
def test_retrieval_labels_cover_every_company_and_splits_are_disjoint(name):
    fixture = FIXTURES[name]
    spec = json.loads((fixture.path / "labels.json").read_text())
    companies = set(_snapshot(fixture.path).companies)  # nothing merged away
    labelled = set(spec["labels"])
    assert labelled | set(spec["aliases"]) == companies and not labelled & set(spec["aliases"])
    for target, row in spec["labels"].items():
        assert set(row) == labelled - {target} and set(row.values()) <= {0, 1, 2, 3}
    dev, held = set(spec["splits"]["dev"]), set(spec["splits"]["held_out"])
    assert not dev & held and dev | held == labelled and abs(len(dev) - len(held)) <= 3
    assert {spec["business"][k] for k in dev} == {spec["business"][k] for k in held}


def test_dedup_universe_keeps_every_text_as_its_own_company(tmp_path):
    fixture = FIXTURES["dedup"]
    data, queries, spec = run.prepare(fixture, tmp_path)
    pairs = spec["pairs"]
    assert len(_snapshot(data).companies) == 2 * len(pairs)  # the share-class merge folds none
    assert len(queries) == len(pairs) and {p["split"] for p in pairs} == {"dev", "held_out"}
    assert {d for p in pairs for d in [p["duplicate"]]} == {True, False}


# --- black-box capture -----------------------------------------------------------------------------


def test_capture_over_http_and_score(tmp_path):
    fixture = FIXTURES["retrieval_v1"]
    data, queries, spec = run.prepare(fixture, tmp_path)
    with TestClient(create_app(lambda: _snapshot(data))) as client:
        captured, latencies = run.capture(
            lambda path, params: client.get(path, params=params).json(), queries, fixture.k
        )
    assert set(captured) == set(queries) and len(latencies) == len(queries)
    stats = run.latency_stats(latencies)
    assert stats["n"] == len(queries) and stats["min"] <= stats["p50"] <= stats["p95"] <= stats["max"]
    result = run.score(fixture, captured, spec, ["dev", "held_out"])
    for split in ("dev", "held_out"):
        assert result[split]["duplicate_listing_returned"] == 0
        assert 0 < result[split]["overall"]["ndcg@10"] <= 1


# --- experiment log --------------------------------------------------------------------------------


def _entry(log, number, **kw):
    args = {
        "number": number,
        "description": "baseline",
        "commit": "a" * 40,
        "settings": {"EMBEDDING_MODEL": "m"},
        "inputs": {},
        "outputs": {},
        "runtime": {},
        "results": {"dedup": {"dev": {"recall_at_zero_false_duplicates": 0.5}}},
        "log": log,
    }
    return experiments.record(**{**args, **kw})


def test_experiment_log_numbers_runs_and_the_commit_is_not_a_key(tmp_path):
    log = tmp_path / "experiments.json"
    when = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    first = _entry(log, 1, now=when)
    assert log.read_text().startswith('[\n  {\n    "experiment": 1,')  # pretty-printed
    _entry(log, 2, settings={"EMBEDDING_MODEL": "other"})  # same commit, other settings: a new row
    assert [e["experiment"] for e in experiments.read(log)] == [1, 2]
    assert first["date"] == "2026-11-22T12:00:00+00:00" and first["schema"] == 2
    with pytest.raises(ValueError, match="not next"):
        _entry(log, 2)
    with pytest.raises(ValueError, match="description"):
        _entry(log, 3, description="  ")
    rows = experiments.table(experiments.read(log)).splitlines()
    assert "other" in rows[2] and rows[1].endswith("baseline")


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def test_committed_experiment_log_is_well_formed_and_reproducible_from_captured_output():
    """Numbered 1..n; every black-box run's captured output is committed, unchanged, and rescores to the log."""
    entries = experiments.read()
    assert [e["experiment"] for e in entries] == list(range(1, len(entries) + 1))
    for e in entries:
        assert e["description"]
        if e.get("schema", 1) < 2:
            continue
        for name, out in e["outputs"].items():
            path = ROOT / out["path"]
            assert run.sha(path.read_bytes()) == out["sha"], f"experiment {e['experiment']}: {path} changed"
            fixture = FIXTURES[name]
            assert run.sha(run.golden_path(fixture).read_bytes()) == e["inputs"][name]["golden"]
            captured = json.loads(path.read_text())["responses"]
            threshold = (e.get("effective") or {}).get("near_duplicate")
            rescored = run.score(fixture, captured, run.golden(fixture), list(e["results"][name]), threshold)
            # Metrics added after a run was logged may appear; every logged value must be reproduced.
            assert _contains(rescored, e["results"][name]), f"experiment {e['experiment']} {name}: rescore differs"


def test_score_retrieval_maps_aliases_to_their_original():
    spec = {
        "relevant_threshold": 3,
        "aliases": {"US:DUP": "US:B"},
        "splits": {"dev": ["US:A"]},
        "tags": {"US:A": []},
        "labels": {"US:A": {"US:B": 3, "US:C": 0}},
    }
    responses = {"US:A": {"peers": [{"entity": {"key": "US:DUP"}}, {"entity": {"key": "US:B"}}]}}
    countries = {"US:A": "US", "US:B": "US", "US:C": "CA", "US:DUP": "US"}
    out = score_retrieval(responses, spec, countries, "dev")
    assert out["overall"]["ndcg@5"] == 1.0 and out["duplicate_listing_returned"] == 1
    assert out["both_copies_returned"] == 1  # US:DUP and its original US:B in one list

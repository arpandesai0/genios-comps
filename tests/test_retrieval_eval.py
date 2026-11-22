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


def _result():
    snapshot, spec = load()
    return evaluate(snapshot, spec, "dev")


def test_experiment_log_appends_numbered_entries(tmp_path):
    from datetime import UTC, datetime

    from experiments import read, record, table

    result = _result()
    log = tmp_path / "experiments.jsonl"
    inputs = {"method": result["method"], "split": "dev"}
    when = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    first = record(result, description=" baseline ", eval_name="retrieval", inputs=inputs, log=log, now=when)
    log.write_text(log.read_text().rstrip("\n"))  # a hand-saved file without a final newline
    second = record(result, description="rerun", eval_name="retrieval", inputs=inputs, log=log)
    entries = read(log)
    assert [e["experiment"] for e in entries] == [1, 2] == [first["experiment"], second["experiment"]]
    assert first["date"] == "2026-11-22T12:00:00+00:00" and first["description"] == "baseline"
    assert first["results"]["overall"] == result["overall"] and first["inputs"]["split"] == "dev"
    assert first["result_file"] is None and first["result_sha"] is None
    lines = table(entries).splitlines()
    assert lines[1].startswith("1 ") and lines[1].endswith("baseline") and "0.697" in lines[1]
    with pytest.raises(ValueError):
        record(result, description="  ", eval_name="retrieval", inputs=inputs, log=log)
    assert len(read(log)) == 2


def test_git_info_reports_dirty_inputs_and_ignores_outputs(tmp_path):
    import subprocess

    from experiments import git_info

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    (tmp_path / "notes.txt").write_text("not an input\n")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    clean = git_info(tmp_path)
    assert clean["dirty"] is False and clean["branch"] == "main" and len(clean["commit"]) == 40

    (tmp_path / "notes.txt").write_text("changed, but not an input\n")
    (tmp_path / "src" / "out.json").write_text("{}\n")
    assert git_info(tmp_path, outputs=[tmp_path / "src" / "out.json"])["dirty"] is False

    git("mv", "src/a.py", "src/b.py")
    (tmp_path / "src" / "my file.py").write_text("y = 2\n")
    dirty = git_info(tmp_path, outputs=[tmp_path / "src" / "out.json"])
    assert dirty["dirty"] is True and dirty["dirty_paths"] == ["src/b.py", "src/my file.py"]

    git("checkout", "-q", "--detach")
    assert git_info(tmp_path)["branch"] is None


def test_git_info_is_unknown_outside_a_repository(tmp_path):
    from experiments import git_info

    info = git_info(tmp_path)
    assert info == {"commit": None, "branch": None, "dirty": None, "dirty_paths": None}


def test_main_with_log_writes_the_result_and_appends(tmp_path, monkeypatch, capsys):
    import experiments
    import retrieval_eval

    log, out = tmp_path / "experiments.jsonl", tmp_path / "result.json"
    monkeypatch.setattr(experiments, "LOG", log)
    assert retrieval_eval.main(["--split", "dev", "--out", str(out), "--log", "end to end"]) == 0
    (entry,) = experiments.read(log)
    assert entry["description"] == "end to end" and entry["inputs"]["fixture"] == "eval/fixtures/retrieval"
    assert entry["result_file"] == out.resolve().as_posix()  # outside the repo: absolute
    assert entry["result_sha"] == experiments.file_hash(out)
    assert json.loads(out.read_text())["overall"] == entry["results"]["overall"]


def test_main_rejects_a_blank_description_before_writing_anything(tmp_path):
    import retrieval_eval

    out = tmp_path / "result.json"
    with pytest.raises(SystemExit):
        retrieval_eval.main(["--out", str(out), "--log", "   "])
    assert not out.exists()


def test_committed_experiment_log_is_well_formed():
    """Numbered 1..n in order, each entry complete and run on a clean, committed tree."""
    from experiments import LOG, read

    entries = read(LOG)
    assert entries, "experiment 1 (the baseline) is committed"
    assert [e["experiment"] for e in entries] == list(range(1, len(entries) + 1))
    for e in entries:
        assert e["description"] and e["git"]["commit"] and e["results"]["overall"]
        assert e["git"]["dirty"] is False, f"experiment {e['experiment']} ran with uncommitted changes"

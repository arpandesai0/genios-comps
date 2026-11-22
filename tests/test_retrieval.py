"""Retrieval: the TF-IDF index, near-duplicates, the k-filling walk, and the peers/comps/CSV endpoints."""

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from comps.api import create_app
from comps.config import IngestConfig, Settings
from comps.retrieval import NearDuplicates, TfidfRetriever, normalize_description, select_peers
from comps.service import build_snapshot
from conftest import FX, make_record

# --- unit: index and selection ------------------------------------------------------------------

DOCS = {
    "US:BANKA": "Regional bank offering deposit accounts, mortgages and small business loans.",
    "US:BANKB": "Community bank providing mortgages, deposit accounts and commercial loans to small business.",
    "US:STEEL": "Steel mill producing rebar and structural beams from recycled scrap.",
    "US:SOFT": "Cloud software for payroll and human resources teams.",
    # Near-duplicate of BANKA: identical apart from punctuation.
    "US:TWIN": "Regional bank offering deposit accounts, mortgages and small business loans!",
}


def index_and_dups(docs=DOCS):
    index = TfidfRetriever().fit(docs)
    return index, NearDuplicates(index, {k: normalize_description(v) for k, v in docs.items()})


def test_similar_businesses_rank_first_and_terms_explain_why():
    index, _ = index_and_dups()
    scores = index.similarities("US:BANKA")
    assert "US:BANKA" not in scores
    assert max(scores, key=scores.get) == "US:TWIN"
    assert scores["US:BANKB"] > scores["US:STEEL"] and scores["US:BANKB"] > scores["US:SOFT"]
    terms = index.shared_terms("US:BANKA", "US:BANKB")
    assert 0 < len(terms) <= 5 and set(terms) <= {
        "bank",
        "deposit",
        "accounts",
        "mortgages",
        "small",
        "business",
        "loans",
    }
    assert index.shared_terms("US:STEEL", "US:SOFT") == []


def test_stop_word_only_descriptions_are_not_indexed():
    index = TfidfRetriever().fit({**DOCS, "US:EMPTY": "The and of it is."})
    assert "US:EMPTY" not in index.keys and "US:BANKA" in index.keys
    assert TfidfRetriever().fit({"US:A": "the of", "US:B": "and it"}).keys == ()


def test_walk_skips_near_duplicate_of_target_and_fills_k():
    index, dups = index_and_dups()
    sel = select_peers("US:BANKA", 2, universe=DOCS, ranker=index, duplicates=dups)
    assert [p.key for p in sel.peers] == ["US:BANKB", sel.peers[1].key]
    assert sel.peers[1].key in ("US:STEEL", "US:SOFT") and [p.rank for p in sel.peers] == [1, 2]
    (skip,) = sel.skipped
    assert (skip.key, skip.reason, skip.duplicate_of) == ("US:TWIN", "near_duplicate_of_target", "US:BANKA")
    assert sel.note is None


def test_near_duplicate_of_a_chosen_peer_is_skipped_and_the_higher_ranked_one_stays():
    index, dups = index_and_dups()
    sel = select_peers("US:BANKB", 3, universe=DOCS, ranker=index, duplicates=dups)
    chosen = [p.key for p in sel.peers]
    first_twin = next(k for k in chosen if k in ("US:BANKA", "US:TWIN"))
    assert sum(k in ("US:BANKA", "US:TWIN") for k in chosen) == 1
    (skip,) = [s for s in sel.skipped if s.reason == "near_duplicate_of_peer"]
    assert skip.duplicate_of == first_twin and skip.similarity is not None


def test_exclusions_are_always_listed_and_never_count_toward_k():
    index, dups = index_and_dups()
    exclude = {"US:BANKB", "US:STEEL", "US:BANKA"}
    sel = select_peers("US:BANKA", 1, universe=DOCS, ranker=index, duplicates=dups, exclude=exclude)
    # TWIN (near-duplicate) and BANKB (excluded) are skipped; SOFT and STEEL tie at 0, SOFT first by key.
    assert [p.key for p in sel.peers] == ["US:SOFT"]
    assert [(s.key, s.reason) for s in sel.skipped] == [
        ("US:TWIN", "near_duplicate_of_target"),
        ("US:BANKB", "user_excluded"),
        ("US:STEEL", "user_excluded"),  # never met in the walk: listed after it, without a similarity
    ]
    assert sel.skipped[-1].similarity is None
    assert all(s.key != "US:BANKA" for s in sel.skipped)  # the target in exclude is ignored


def test_fewer_peers_when_the_ranking_runs_out_and_never_padded():
    index, dups = index_and_dups()
    sel = select_peers("US:STEEL", 10, universe=[*DOCS, "US:NODESC"], ranker=index, duplicates=dups)
    keys = [p.key for p in sel.peers]
    assert len(keys) == 3 and "US:STEEL" not in keys and len(set(keys)) == 3  # BANKA/TWIN count once
    assert sel.note and "Only 3 of the 10" in sel.note
    assert sel.skipped[-1].key == "US:NODESC" and sel.skipped[-1].reason == "no_description"


def test_target_without_description_gets_no_peers_and_a_note():
    index, dups = index_and_dups()
    sel = select_peers("US:NODESC", 5, universe=[*DOCS, "US:NODESC", "US:ALSO"], ranker=index, duplicates=dups)
    assert sel.peers == () and "no usable description" in (sel.note or "")
    assert [(s.key, s.reason) for s in sel.skipped] == [("US:ALSO", "no_description")]


def test_ties_are_ordered_by_key():
    docs = {"US:T": "alpha beta", "US:B": "alpha gamma", "US:A": "alpha delta"}
    index = TfidfRetriever().fit(docs)
    dups = NearDuplicates(index, {k: normalize_description(v) for k, v in docs.items()})
    sel = select_peers("US:T", 2, universe=docs, ranker=index, duplicates=dups)
    assert [p.key for p in sel.peers] == ["US:A", "US:B"]


# --- API -----------------------------------------------------------------------------------------

UNIVERSE = [
    make_record(id="b1", ticker="BNKA", name="Alpha Bank", description=DOCS["US:BANKA"], revenue=1000.0),
    make_record(id="b2", ticker="BNKB", name="Beta Bank", description=DOCS["US:BANKB"], revenue=500.0, net_income=-5.0),
    make_record(id="b3", ticker="TWIN", name="Twin Bank", description=DOCS["US:TWIN"], revenue=900.0),
    make_record(id="s1", ticker="STL", name="Steel Co", description=DOCS["US:STEEL"], sector="Materials", country="CA"),
    make_record(id="w1", ticker="SOFT", name="Soft Co", description=DOCS["US:SOFT"], sector="Technology"),
    make_record(id="n1", ticker="NODE", name="No Desc Co", description=None, revenue=7.0),
    make_record(id="c1", ticker="CLS.A", name="Class A", description="Shipping containers leasing.", price=20.0),
    make_record(id="c2", ticker="CLS.B", name="Class B", description="Shipping containers leasing.", price=10.0),
]


@pytest.fixture
def api(tmp_path):
    (tmp_path / "companies.json").write_text(json.dumps(UNIVERSE))
    (tmp_path / "fx_rates.json").write_text(json.dumps(FX))
    settings = Settings(data_dir=tmp_path, ingest=IngestConfig())
    with TestClient(create_app(lambda: build_snapshot(settings))) as c:
        yield c


def test_peers_endpoint(api):
    body = api.get("/api/peers", params={"target": "US:BNKA", "k": 2}).json()
    assert body["method"] == {"name": "tfidf-description", "version": "1"}
    assert body["target"]["key"] == "US:BNKA"
    assert (body["requested_k"], body["returned_k"], body["note"]) == (2, 2, None)
    first = body["peers"][0]
    assert first["rank"] == 1 and first["entity"]["key"] == "US:BNKB"
    ev = first["evidence"]
    assert 0 < ev["similarity"] < 1 and ev["shared_terms"]
    assert ev["classification"] == {"sector": True, "industry": True, "sub_industry": True}
    assert ev["country_match"] is True and ev["revenue_ratio"] == 0.5
    assert "metrics" not in first
    reasons = {s["entity"]["key"]: s["reason"] for s in body["skipped"]}
    assert reasons["US:TWIN"] == "near_duplicate_of_target" and reasons["US:NODE"] == "no_description"


def test_share_class_target_and_exclude_resolve_to_the_issuer(api):
    body = api.get("/api/peers", params={"target": "US:CLS.B", "k": 50, "exclude": "US:CLS.A,US:SOFT,,US:SOFT"}).json()
    assert body["target"]["key"] == "US:CLS.A"  # the class key resolved; the target in exclude is ignored
    keys = [p["entity"]["key"] for p in body["peers"]]
    assert "US:CLS.A" not in keys and "US:CLS.B" not in keys and "US:SOFT" not in keys
    assert [s["reason"] for s in body["skipped"] if s["entity"]["key"] == "US:SOFT"] == ["user_excluded"]
    assert body["note"]  # fewer than 50 companies exist


def test_comps_endpoint_has_metrics_and_peer_only_summary(api):
    body = api.get("/api/comps", params={"target": "US:BNKA", "k": 3}).json()
    assert body["currency"] == "USD" and body["returned_k"] == 3
    assert body["target"]["metrics"]["pe"]["display"] == "25.0x"
    peer = next(p for p in body["peers"] if p["entity"]["key"] == "US:BNKB")
    assert peer["metrics"]["pe"]["display"] == "NM" and "nonpositive_denominator" in peer["evidence"]["limitations"]
    pe = body["summary"]["pe"]
    assert pe["n"] + pe["n_nm"] + pe["n_missing"] == 3 and pe["n_nm"] == 1


def test_comps_with_no_peers_has_empty_stats(api):
    body = api.get("/api/comps", params={"target": "US:NODE"}).json()
    assert body["peers"] == [] and body["returned_k"] == 0 and "no usable description" in body["note"]
    assert body["summary"]["pe"] == {
        "n": 0,
        "n_nm": 0,
        "n_missing": 0,
        "mean": None,
        "median": None,
        "high": None,
        "low": None,
        "display": {"mean": None, "median": None, "high": None, "low": None},
    }


def test_comps_csv(api):
    r = api.get("/api/comps.csv", params={"target": "US:BNKA", "k": 2})
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="comps_US_BNKA.csv"'
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == [
        "Row",
        "Rank",
        "Key",
        "Name",
        "Similarity",
        "Market cap (USD m)",
        "EV (USD m)",
        "EV/Revenue",
        "EV/EBITDA",
        "P/E",
    ]
    assert [row[0] for row in rows[1:]] == ["target", "peer", "peer", "mean", "median", "high", "low", "n"]
    assert rows[1][2] == "US:BNKA" and rows[1][5] == "2,000.0" and rows[1][4] == ""
    assert rows[2][1] == "1" and rows[2][2] == "US:BNKB" and rows[2][9] == "NM"
    assert rows[-1][7:] == ["2", "2", "1"]


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"target": "US:NOPE"}, 404),
        ({"target": "us:bnka"}, 404),  # exact case outside the single-company lookup
        ({}, 422),
        ({"target": "US:BNKA", "k": 0}, 422),
        ({"target": "US:BNKA", "k": 51}, 422),
        ({"target": "US:BNKA", "k": "ten"}, 422),
        ({"target": "US:BNKA", "exclude": "US:NOPE"}, 422),
    ],
)
@pytest.mark.parametrize("path", ["/api/peers", "/api/comps", "/api/comps.csv"])
def test_errors(api, path, params, status):
    r = api.get(path, params=params)
    assert r.status_code == status and "error" in r.json()


def test_peer_lists_never_contain_the_target_or_repeats(api):
    for target in ("US:BNKA", "US:BNKB", "US:TWIN", "CA:STL", "US:SOFT", "US:CLS.A"):
        body = api.get("/api/peers", params={"target": target, "k": 50}).json()
        keys = [p["entity"]["key"] for p in body["peers"]]
        assert target not in keys and len(keys) == len(set(keys))
        assert not ({"US:BNKA", "US:TWIN"} <= set(keys))  # near-duplicates never both appear


def test_excluded_company_without_description_is_listed_once():
    index, dups = index_and_dups()
    sel = select_peers(
        "US:BANKA", 2, universe=[*DOCS, "US:NODESC"], ranker=index, duplicates=dups, exclude={"US:NODESC"}
    )
    assert [(s.key, s.reason) for s in sel.skipped if s.key == "US:NODESC"] == [("US:NODESC", "user_excluded")]
    none = select_peers(
        "US:NODESC", 2, universe=[*DOCS, "US:NODESC", "US:X"], ranker=index, duplicates=dups, exclude={"US:X"}
    )
    assert [(s.key, s.reason) for s in none.skipped] == [("US:X", "user_excluded")]


def test_revenue_ratio_never_overflows_and_rounds_half_away(tmp_path):
    from comps.service import find_peers

    recs = [
        make_record(id="t", ticker="TINY", description="Container shipping and leasing services.", revenue=1e-300),
        make_record(id="p", ticker="HUGE", description="Container shipping and port leasing.", revenue=1e300),
        make_record(id="h", ticker="HALF", description="Container leasing for shipping lines.", revenue=0.125),
        make_record(id="o", ticker="ONE", description="Shipping container leasing company.", revenue=1.0),
    ]
    (tmp_path / "companies.json").write_text(json.dumps(recs))
    (tmp_path / "fx_rates.json").write_text(json.dumps(FX))
    s = build_snapshot(Settings(data_dir=tmp_path, ingest=IngestConfig()))
    ratios = {p.company.entity.key: p.evidence.revenue_ratio for p in find_peers(s, "US:TINY", 3).peers}
    assert ratios["US:HUGE"] is None  # 1e600 is not representable: blank, not a crash
    halves = {p.company.entity.key: p.evidence.revenue_ratio for p in find_peers(s, "US:ONE", 3).peers}
    assert halves["US:HALF"] == 0.13  # 0.125 rounds half away from zero

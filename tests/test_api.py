"""Read-only API on a small synthetic data folder (the full start-up path: files -> snapshot -> HTTP)."""

import json

import pytest
from fastapi.testclient import TestClient

from comps.api import create_app
from comps.config import IngestConfig, Settings
from comps.ingest import DatasetError
from comps.service import build_snapshot
from conftest import FX, make_record

RECORDS = [
    make_record(id="a1", ticker="ACME", price_date="2026-07-01", price=18.0),
    make_record(id="a2", ticker="ACME", price_date="2026-10-01"),
    make_record(id="b1", ticker="BOLT", name="Bolt Fasteners", description="Bolt makes fasteners.", total_debt=-5.0),
    make_record(
        id="c1", ticker="LOSS", name="Lossmaker Ltd", description="Loses money.", net_income=-40.0, cash=3000.0
    ),
    make_record(id="x1", ticker=None, name="Private Co"),
]


@pytest.fixture
def client(tmp_path):
    (tmp_path / "companies.json").write_text(json.dumps(RECORDS))
    (tmp_path / "fx_rates.json").write_text(json.dumps(FX))
    settings = Settings(data_dir=tmp_path, ingest=IngestConfig())
    with TestClient(create_app(lambda: build_snapshot(settings))) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert (body["entities"], body["records"], body["reference_date"]) == (3, 5, "2026-10-01")
    assert len(body["dataset_version"]) == 12


def test_company_list_and_search(client):
    body = client.get("/api/companies").json()
    assert body["total"] == 3
    assert [i["key"] for i in body["items"]] == ["US:ACME", "US:BOLT", "US:LOSS"]
    assert all(i["match"] is None for i in body["items"])

    assert client.get("/api/companies", params={"q": "us:acme"}).json()["items"][0]["match"] == "key"
    assert client.get("/api/companies", params={"q": "BOLT"}).json()["items"][0]["match"] == "ticker"
    assert client.get("/api/companies", params={"q": "lossmaker ltd"}).json()["items"][0]["match"] == "name_exact"
    partial = client.get("/api/companies", params={"q": "fasten"}).json()
    assert [(i["key"], i["match"]) for i in partial["items"]] == [("US:BOLT", "name_partial")]


def test_company_list_filters_and_paging(client):
    limited = client.get("/api/companies", params={"has_findings": "limitation"}).json()
    assert [i["key"] for i in limited["items"]] == ["US:BOLT"]  # invalid total_debt
    page = client.get("/api/companies", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 3 and [i["key"] for i in page["items"]] == ["US:BOLT"]


def test_company_detail_shows_history_usd_values_and_metrics(client):
    body = client.get("/api/companies/US%3AACME").json()
    assert [o["record_id"] for o in body["observations"]] == ["a1", "a2"]
    assert body["latest"]["record_id"] == "a2"
    assert body["latest"]["usd"]["price"] == 20.0
    assert body["latest"]["conversion"] == {"price_fx": 1.0, "reporting_fx": 1.0, "unit_factor": 1.0}
    assert body["latest"]["original"]["id"] == "a2"
    assert body["metrics"]["ev_ebitda"] == {
        "status": "ok",
        "value": 12.0,
        "display": "12.0x",
        "raw": 12.0,
        "missing_inputs": [],
    }


def test_company_detail_includes_ingestion_and_finance_findings(client):
    bolt = client.get("/api/companies/US%3ABOLT").json()
    assert bolt["metrics"]["enterprise_value_usd_m"]["missing_inputs"] == ["total_debt"]
    assert "invalid_value" in [f["code"] for f in bolt["findings"]]
    loss = client.get("/api/companies/US%3ALOSS").json()
    assert loss["metrics"]["pe"]["display"] == "NM"
    (ev,) = [f for f in loss["findings"] if f["code"] == "nonpositive_ev"]
    assert ev["entity_keys"] == ["US:LOSS"]
    assert loss["finding_counts"]["info"] >= 1


def test_unknown_company_is_404_in_contract_shape(client):
    r = client.get("/api/companies/US%3ANOPE")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_dataset_overview(client):
    body = client.get("/api/dataset").json()
    assert body["counts"] == {"records": 5, "entities": 3, "manual_additions": 0}
    assert [f["name"] for f in body["source"]["files"]] == ["companies.json", "fx_rates.json"]
    codes = {row["code"] for row in body["findings_by_code"]}
    assert {"unlisted_excluded", "invalid_value", "nonpositive_ev"} <= codes
    assert set(body["findings_by_severity"]) == {"error", "limitation", "warning", "info"}


def test_findings_filters(client):
    body = client.get("/api/dataset/findings", params={"code": "unlisted_excluded"}).json()
    assert body["total"] == 1 and body["items"][0]["record_ids"] == ["x1"]
    by_entity = client.get("/api/dataset/findings", params={"entity": "US:LOSS"}).json()
    assert "nonpositive_ev" in [f["code"] for f in by_entity["items"]]
    assert client.get("/api/dataset/findings", params={"limit": 1}).json()["items"].__len__() == 1


def test_invalid_parameters_are_422_in_contract_shape(client):
    for params in ({"limit": 0}, {"limit": 201}, {"has_findings": "bad"}):
        r = client.get("/api/companies", params=params)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_endpoints_not_built_yet_are_404(client):
    for path in ("/api/comps?target=US:ACME", "/api/comps.csv?target=US:ACME", "/api/ingest/records"):
        r = client.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


# --- richer universe: sectors, same ticker in two countries, aliases, a share-class pair ---------------

RICH = [
    make_record(id="r1", ticker="ACME", country="US", name="Acme Widgets Inc", sector="Industrials"),
    make_record(
        id="r2",
        ticker="ACME",
        country="GB",
        name="Acme Retail plc",
        sector="Consumer",
        description="Acme Retail runs shops.",
        price_currency="GBP",
        reporting_currency="GBP",
    ),
    make_record(
        id="r3",
        ticker="OLDN",
        name="Old Name Corp",
        description="Old name business.",
        price_date="2026-07-01",
        sector="Technology",
    ),
    make_record(
        id="r4",
        ticker="OLDN",
        name="New Name Corp",
        description="Old name business.",
        price_date="2026-10-01",
        sector="Technology",
    ),
    make_record(
        id="r5",
        ticker="BLT.A",
        name="Bolt Class A",
        description="Bolt makes fasteners.",
        sector="Industrials",
    ),
    make_record(
        id="r6",
        ticker="BLT.B",
        name="Bolt Class B",
        description="Bolt makes fasteners.",
        sector="Industrials",
    ),
]


@pytest.fixture
def rich(tmp_path):
    (tmp_path / "companies.json").write_text(json.dumps(RICH))
    (tmp_path / "fx_rates.json").write_text(json.dumps(FX))
    settings = Settings(data_dir=tmp_path, ingest=IngestConfig())
    with TestClient(create_app(lambda: build_snapshot(settings))) as c:
        yield c


def keys(body):
    return [i["key"] for i in body["items"]]


def test_same_ticker_in_two_countries_both_match_by_ticker(rich):
    body = rich.get("/api/companies", params={"q": "acme"}).json()
    assert [(i["key"], i["match"]) for i in body["items"]] == [("GB:ACME", "ticker"), ("US:ACME", "ticker")]


def test_search_precedence_key_before_ticker_before_names(rich):
    # "US:ACME" is a key match only; "acme retail plc" is an exact name; "acme" partial would be a ticker.
    assert rich.get("/api/companies", params={"q": "US:ACME"}).json()["items"][0]["match"] == "key"
    assert rich.get("/api/companies", params={"q": "acme retail plc"}).json()["items"][0]["match"] == "name_exact"
    partial = rich.get("/api/companies", params={"q": "bolt class"}).json()
    assert [(i["key"], i["match"]) for i in partial["items"]] == [
        ("US:BLT.A", "name_partial"),
        ("US:BLT.B", "name_partial"),
    ]  # ties ordered by key


def test_search_finds_a_company_by_an_old_name(rich):
    body = rich.get("/api/companies", params={"q": "old name corp"}).json()
    assert [(i["key"], i["match"], i["name"]) for i in body["items"]] == [("US:OLDN", "name_exact", "New Name Corp")]


def test_whitespace_query_lists_everything(rich):
    body = rich.get("/api/companies", params={"q": "   "}).json()
    assert body["total"] == 5 and all(i["match"] is None for i in body["items"])


def test_sector_filter_is_case_insensitive_and_combines_with_search(rich):
    assert keys(rich.get("/api/companies", params={"sector": "industrials"}).json()) == [
        "US:ACME",
        "US:BLT.A",
        "US:BLT.B",
    ]
    both = rich.get("/api/companies", params={"q": "acme", "sector": "Consumer"}).json()
    assert keys(both) == ["GB:ACME"]
    warn = rich.get("/api/companies", params={"q": "bolt", "has_findings": "warning"}).json()
    assert keys(warn) == ["US:BLT.A", "US:BLT.B"]  # possible_same_issuer


def test_offset_past_the_end_gives_an_empty_page_with_the_total(rich):
    body = rich.get("/api/companies", params={"offset": 99}).json()
    assert (body["total"], body["items"]) == (5, [])


def test_entity_findings_match_the_company_page(rich):
    # Each share class has its own possible_same_issuer finding naming both keys; the entity filter
    # returns only the company's own, so the counts agree with its page.
    page = rich.get("/api/companies/US%3ABLT.A").json()
    listed = rich.get("/api/dataset/findings", params={"entity": "US:BLT.A", "limit": 500}).json()
    assert listed["total"] == len(page["findings"]) == sum(page["finding_counts"].values())
    assert [f["code"] for f in listed["items"]].count("possible_same_issuer") == 1
    assert rich.get("/api/dataset/findings", params={"entity": "US:NOPE"}).json()["total"] == 0


def test_findings_severity_filter_and_offset(rich):
    warnings = rich.get("/api/dataset/findings", params={"severity": "warning", "limit": 500}).json()
    assert warnings["total"] >= 2 and all(f["severity"] == "warning" for f in warnings["items"])
    second = rich.get("/api/dataset/findings", params={"severity": "warning", "limit": 1, "offset": 1}).json()
    assert second["items"] == warnings["items"][1:2]


def test_unknown_path_and_wrong_method_use_the_error_shape(rich):
    r = rich.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = rich.post("/api/health")
    assert r.status_code == 405 and r.json()["error"]["code"] == "invalid_request"


def test_start_up_fails_clearly_on_an_unusable_data_folder(tmp_path):
    settings = Settings(data_dir=tmp_path, ingest=IngestConfig())  # empty folder: no files
    with pytest.raises(DatasetError, match="cannot read"), TestClient(create_app(lambda: build_snapshot(settings))):
        pass

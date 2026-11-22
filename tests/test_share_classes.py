"""Share-class merge: the disjoint-set union, the merge rule, the shown key and the issuer market cap."""

import pytest

from comps.finance import compute_metrics
from comps.ingest import build_dataset
from comps.issuers import DisjointSet
from conftest import make_record


def issuer_metrics(entity):
    listings = [c.entity.latest for c in entity.classes if c.counted]
    return compute_metrics(entity.latest, listings)[0]


def codes(findings):
    return [f.code for f in findings]


# --- disjoint-set union ------------------------------------------------------------------------


def test_every_item_starts_as_its_own_parent():
    dsu = DisjointSet(["a", "b", "c"])
    assert [dsu.find(x) for x in "abc"] == ["a", "b", "c"]
    assert dsu.groups() == {"a": ["a"], "b": ["b"], "c": ["c"]}


def test_union_is_transitive_and_reroot_points_every_member_at_the_new_root():
    dsu = DisjointSet(["a", "b", "c", "d"])
    dsu.union("a", "b")
    dsu.union("c", "b")
    assert dsu.find("a") == dsu.find("c") != dsu.find("d")
    dsu.reroot("c", dsu.groups()[dsu.find("c")])
    assert {x: dsu.parent[x] for x in "abcd"} == {"a": "c", "b": "c", "c": "c", "d": "d"}
    assert dsu.union("a", "c") == "c"  # already one set


# --- merge rule --------------------------------------------------------------------------------


def test_identical_issuer_data_with_different_prices_merges_and_sums_market_cap(fx):
    a = make_record(ticker="DUO.A", name="Duo Class A", price=20.0, shares_outstanding=100.0)
    b = make_record(ticker="DUO.B", name="Duo Class B", price=10.0, shares_outstanding=50.0)
    ds = build_dataset([b, a], fx)
    assert list(ds.entities) == ["US:DUO.A"]
    assert ds.parents == {"US:DUO.A": "US:DUO.A", "US:DUO.B": "US:DUO.A"}
    issuer = ds.entities["US:DUO.A"]
    assert issuer.share_class_keys == ("US:DUO.A", "US:DUO.B")
    assert [c.counted for c in issuer.classes] == [True, True]
    assert codes(issuer.findings) == ["share_classes_merged"]
    assert set(issuer.record_ids) == {a["id"], b["id"]}
    m = issuer_metrics(issuer)
    assert m.market_cap_usd_m.display == "2,500.0"  # 20 x 100 + 10 x 50
    assert m.enterprise_value_usd_m.display == "2,900.0"  # + 500 debt - 100 cash, counted once
    assert m.pe.display == "31.3x"  # 2,500 / 80 = 31.25, half away from zero


def test_shown_key_is_the_most_valuable_class(fx):
    small = make_record(ticker="AAA", price=1.0)
    big = make_record(ticker="ZZZ", price=50.0)
    ds = build_dataset([small, big], fx)
    assert list(ds.entities) == ["US:ZZZ"]
    assert ds.entities["US:ZZZ"].share_class_keys == ("US:ZZZ", "US:AAA")


def test_identical_price_and_shares_are_counted_once(fx):
    a = make_record(ticker="SAME.A", name="Same A")
    b = make_record(ticker="SAME.B", name="Same B")
    issuer = build_dataset([a, b], fx).entities["US:SAME.A"]
    assert [c.counted for c in issuer.classes] == [True, False]
    assert codes(issuer.findings) == ["share_classes_merged", "duplicate_share_listing"]
    assert issuer_metrics(issuer).market_cap_usd_m.display == "2,000.0"


def test_a_class_without_a_price_blanks_market_cap_instead_of_a_partial_sum(fx):
    a = make_record(ticker="INC.A", price=20.0)
    b = make_record(ticker="INC.B", price=None)
    ds = build_dataset([a, b], fx)
    issuer = ds.entities["US:INC.A"]  # a class without a value ranks last
    assert [c.counted for c in issuer.classes] == [True, True]
    (incomplete,) = [f for f in issuer.findings if f.code == "share_class_incomplete"]
    assert incomplete.entity_keys == ("US:INC.A", "US:INC.B") and incomplete.fields == ("price",)
    m = issuer_metrics(issuer)
    assert m.market_cap_usd_m.status == "missing" and m.market_cap_usd_m.missing_inputs == ("price",)
    assert m.pe.status == "missing"
    # The class's own finding names the issuer's shown key first.
    b_findings = issuer.classes[1].entity.latest.findings
    assert [(f.code, f.entity_keys) for f in b_findings] == [("missing_value", ("US:INC.A", "US:INC.B"))]


def test_three_classes_merge_transitively(fx):
    recs = [make_record(ticker=t, price=p) for t, p in (("T.C", 5.0), ("T.A", 30.0), ("T.B", 10.0))]
    ds = build_dataset(recs, fx)
    assert list(ds.entities) == ["US:T.A"]
    assert ds.entities["US:T.A"].share_class_keys == ("US:T.A", "US:T.B", "US:T.C")
    assert issuer_metrics(ds.entities["US:T.A"]).market_cap_usd_m.display == "4,500.0"


@pytest.mark.parametrize(
    ("other", "why"),
    [
        ({"revenue": 999.0}, "different financials"),
        ({"description": "Something else entirely."}, "different description"),
        ({"price_date": "2026-09-30"}, "different price date"),
        ({"sub_industry": "Robotics"}, "different classification"),
        ({"country": "CA"}, "same data in another country is another company"),
    ],
)
def test_listings_that_differ_on_issuer_data_stay_separate(fx, other, why):
    a = make_record(ticker="ABC.A")
    b = make_record(ticker="ABC.B", **other)
    ds = build_dataset([a, b], fx)
    assert len(ds.entities) == 2, why
    assert all(e.share_classes == () for e in ds.entities.values())


def test_name_price_and_shares_may_differ(fx):
    a = make_record(ticker="NM.A", name="Alpha Holdings", price=20.0, shares_outstanding=100.0)
    b = make_record(ticker="NM.B", name="Alpha Inc", price=7.0, shares_outstanding=3.0, price_currency="EUR")
    assert list(build_dataset([a, b], fx).entities) == ["US:NM.A"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"country": None},  # placeholder country "*": the exchange is unknown
        {"description": ""},
        {"description": None},
        {"total_debt": None, "cash": None, "revenue": None, "ebitda": None, "net_income": None},
    ],
)
def test_never_merges_on_missing_data(fx, overrides):
    a = make_record(ticker="EMP.A", **overrides)
    b = make_record(ticker="EMP.B", **overrides)
    assert len(build_dataset([a, b], fx).entities) == 2


def test_single_listing_is_its_own_class(fx):
    ds = build_dataset([make_record()], fx)
    e = ds.entities["US:ACME"]
    assert e.share_classes == () and e.share_class_keys == ("US:ACME",)
    assert ds.parents == {"US:ACME": "US:ACME"}


def test_cosmetic_differences_do_not_block_a_merge(fx):
    # Ingestion reads these the same way: currency codes are upper-cased, text is trimmed, 500 == 500.0.
    a = make_record(ticker="COS.A", price=20.0, total_debt=500.0, reporting_currency="USD", description="Makes X.")
    b = make_record(ticker="COS.B", price=10.0, total_debt=500, reporting_currency="usd", description="Makes X.  ")
    assert list(build_dataset([a, b], fx).entities) == ["US:COS.A"]


def test_price_currency_case_does_not_make_the_same_shares_count_twice(fx):
    a = make_record(ticker="CUR.A", price_currency="USD")
    b = make_record(ticker="CUR.B", price_currency="usd")
    issuer = build_dataset([a, b], fx).entities["US:CUR.A"]
    assert [c.counted for c in issuer.classes] == [True, False]
    assert issuer_metrics(issuer).market_cap_usd_m.display == "2,000.0"


def test_missing_inputs_list_price_causes_before_share_causes(fx):
    a = make_record(ticker="MIS.A", price=20.0, shares_outstanding=None)
    b = make_record(ticker="MIS.B", price=None, shares_outstanding=100.0)
    issuer = build_dataset([a, b], fx).entities["US:MIS.A"]
    assert issuer_metrics(issuer).market_cap_usd_m.missing_inputs == ("price", "shares_outstanding")

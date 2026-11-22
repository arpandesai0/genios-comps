"""Entity resolution by COUNTRY:TICKER, observation history, and cross-record checks."""

from datetime import date

from comps.ingest import build_dataset
from conftest import make_record


def codes(findings):
    return sorted(f.code for f in findings)


def test_same_ticker_in_different_countries_are_different_companies(fx):
    ds = build_dataset([make_record(country="US"), make_record(country="GB", price_currency="GBP")], fx)
    assert sorted(ds.entities) == ["GB:ACME", "US:ACME"]


def test_exact_duplicates_collapse_keeping_the_later_record(fx):
    a = make_record(id="a1")
    b = dict(a, id="b2")
    ds = build_dataset([a, b], fx)
    e = ds.entities["US:ACME"]
    assert [o.record_id for o in e.observations] == ["b2"]
    assert e.record_ids == ("b2", "a1")  # the dropped record is kept as provenance
    assert codes(e.findings) == ["exact_duplicate"]


def test_different_dates_form_a_time_series_and_latest_text_wins(fx):
    old = make_record(id="old", price_date="2026-04-01", price=10.0, name="Acme Old Name")
    new = make_record(id="new", price_date="2026-10-01", price=12.0, name="Acme New Name")
    ds = build_dataset([new, old], fx)  # input order must not matter here
    e = ds.entities["US:ACME"]
    assert [o.record_id for o in e.observations] == ["old", "new"]
    assert e.latest.usd.price == 12.0
    assert e.name == "Acme New Name"
    assert e.aliases == ("Acme Old Name", "Acme New Name")
    assert codes(e.findings) == ["text_updated"]
    assert {(t.value, t.record_id) for t in e.text_history} == {("Acme Old Name", "old"), ("Acme New Name", "new")}


def test_same_date_text_conflict_later_record_wins(fx):
    a = make_record(id="a", name="Acme Corp")
    b = make_record(id="b", name="Acme Holdings")
    e = build_dataset([a, b], fx).entities["US:ACME"]
    assert e.name == "Acme Holdings"
    assert [o.record_id for o in e.observations] == ["b"]
    assert codes(e.findings) == ["conflicting_attributes"]
    assert e.aliases == ("Acme Corp", "Acme Holdings")


def test_same_date_numeric_conflict_is_flagged_and_later_record_used(fx):
    a = make_record(id="a", revenue=1000.0)
    b = make_record(id="b", revenue=1200.0)
    e = build_dataset([a, b], fx).entities["US:ACME"]
    assert e.latest.usd.revenue == 1200.0
    (f,) = e.findings
    assert f.code == "conflicting_observation" and f.fields == ("revenue",)
    assert [o.record_id for o in e.superseded] == ["a"]


def test_numbers_are_never_mixed_across_dates(fx):
    old = make_record(id="old", price_date="2026-04-01", ebitda=300.0)
    new = make_record(id="new", price_date="2026-10-01", ebitda=None)
    e = build_dataset([old, new], fx).entities["US:ACME"]
    assert e.latest.record_id == "new"
    assert e.latest.usd.ebitda is None


def test_missing_latest_text_falls_back_to_older_value_with_finding(fx):
    old = make_record(id="old", price_date="2026-04-01", description="Makes widgets.")
    new = make_record(id="new", price_date="2026-10-01", description=None)
    e = build_dataset([old, new], fx).entities["US:ACME"]
    assert e.description == "Makes widgets."
    assert "text_from_older_record" in codes(e.findings)


def test_shared_name_with_different_content(fx):
    a = make_record(ticker="AAA", name="Same Name Co", revenue=10.0)
    b = make_record(ticker="BBB", name="same name co", revenue=99.0)
    ds = build_dataset([a, b], fx)
    assert codes(ds.entities["US:AAA"].findings) == ["shared_name"]


def test_stale_price_uses_latest_date_in_dataset_as_reference(fx):
    fresh = make_record(ticker="NEW", name="Fresh Co", price_date="2026-10-01", revenue=1.0)
    stale = make_record(ticker="OLD", name="Stale Co", price_date="2026-05-01", revenue=2.0)
    ds = build_dataset([fresh, stale], fx)
    assert ds.reference_date == date(2026, 10, 1)
    assert codes(ds.entities["US:OLD"].findings) == ["stale_price"]
    assert ds.entities["US:NEW"].findings == ()


def test_reused_record_id_is_not_a_conflict(fx):
    ds = build_dataset(
        [
            make_record(id="dup", ticker="AAA", name="A Co"),
            make_record(id="dup", ticker="BBB", name="B Co", revenue=5.0),
        ],
        fx,
    )
    assert sorted(ds.entities) == ["US:AAA", "US:BBB"]
    assert ds.findings == ()


def _view(ds):
    return {k: (e.name, e.latest.record_id, e.latest.usd, codes(e.findings)) for k, e in ds.entities.items()}


def test_ingestion_is_deterministic_and_order_independent_without_conflicts(fx):
    recs = [make_record(ticker=t, id=f"id{t}", name=f"Co {t}", revenue=float(i + 1)) for i, t in enumerate("ABCDE")]
    first = build_dataset(recs, fx)
    again = build_dataset(recs, fx)
    reordered = build_dataset(list(reversed(recs)), fx)
    assert first.version == again.version
    assert _view(first) == _view(again) == _view(reordered)
    assert list(first.entities) == sorted(first.entities)


def test_manual_records_change_the_version_and_are_marked(fx):
    base = [make_record(ticker="AAA")]
    ds = build_dataset(base, fx)
    added = build_dataset(base, fx, extra_records=[make_record(ticker="NEW", revenue=7.0)])
    assert added.version != ds.version
    assert added.entities["US:NEW"].latest.origin == "manual"
    assert added.metadata["manual_records"] == 1


def test_text_updated_message_says_which_value_is_used_after_a_fallback(fx):
    # The latest description is blank, so the older one is used; the message must not claim "latest".
    ds = build_dataset(
        [make_record(id="c1", price_date="2026-07-01"), make_record(id="c2", price_date="2026-10-01", description=" ")],
        fx,
    )
    (e,) = ds.entities.values()
    (updated,) = [f for f in e.findings if f.code == "text_updated"]
    assert "most recent non-empty value" in updated.message
    assert "using the latest value" not in updated.message

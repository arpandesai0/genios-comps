"""Record-level validation and USD normalization."""

import math

import pytest

from comps.ingest import DatasetError, build_dataset
from conftest import make_record


def ingest(records, fx, **kw):
    return build_dataset(records, fx, **kw)


def only(ds):
    (entity,) = ds.entities.values()
    return entity


def codes(findings):
    return sorted(f.code for f in findings)


def test_usd_record_passes_through_unchanged(fx):
    e = only(ingest([make_record()], fx))
    o = e.latest
    assert e.key == "US:ACME"
    assert o.usd.price == 20.0
    assert (o.usd.total_debt, o.usd.cash, o.usd.revenue, o.usd.ebitda, o.usd.net_income) == (500, 100, 1000, 200, 80)
    assert o.conversion.price_fx == 1.0 and o.conversion.unit_factor == 1.0
    assert o.findings == ()


def test_mixed_currencies_and_thousands_are_converted_independently(fx):
    # price in GBP, financials in EUR thousands: 2,000,000 thousand EUR = 2,000 m EUR = 2,200 m USD
    rec = make_record(price_currency="GBP", reporting_currency="EUR", units="thousands", price=148.0,
                      total_debt=1_000_000, cash=500_000, revenue=2_000_000, ebitda=-30_000, net_income=0)
    o = only(ingest([rec], fx)).latest
    assert o.usd.price == pytest.approx(185.0)              # 148 × 1.25
    assert o.usd.total_debt == pytest.approx(1100.0)        # 1,000,000 × 0.001 × 1.10
    assert o.usd.cash == pytest.approx(550.0)
    assert o.usd.revenue == pytest.approx(2200.0)
    assert o.usd.ebitda == pytest.approx(-33.0)
    assert o.usd.net_income == 0
    assert o.shares_outstanding == 100.0                    # always millions, never unit-scaled


def test_equivalent_representations_normalize_to_equal_values(fx):
    a = only(ingest([make_record(units="millions", revenue=1.5)], fx)).latest
    b = only(ingest([make_record(units="thousands", revenue=1500)], fx)).latest
    assert a.usd.revenue == pytest.approx(b.usd.revenue)


def test_original_record_is_preserved(fx):
    rec = make_record(price_currency=" gbp ")
    o = only(ingest([rec], fx)).latest
    assert o.original == rec
    assert o.conversion.price_fx == 1.25
    assert "normalized_value" in codes(o.findings)


def test_missing_value_is_none_not_zero_and_only_limits_dependent_metrics(fx):
    o = only(ingest([make_record(ebitda=None)], fx)).latest
    assert o.usd.ebitda is None
    assert o.usd.revenue == 1000 and o.usd.net_income == 80
    (f,) = o.findings
    assert (f.code, f.severity, f.fields, f.affects) == ("missing_value", "limitation", ("ebitda",), ("ev_ebitda",))
    assert f.entity_keys == ("US:ACME",) and f.record_ids == (o.record_id,)


def test_absent_field_is_reported(fx):
    rec = make_record()
    del rec["cash"]
    o = only(ingest([rec], fx)).latest
    assert o.usd.cash is None
    assert codes(o.findings) == ["missing_field"]


@pytest.mark.parametrize("field,value,code", [
    ("price", "20.0", "invalid_type"),
    ("price", True, "invalid_type"),
    ("price", 0, "invalid_value"),
    ("shares_outstanding", -5, "invalid_value"),
    ("total_debt", -1, "invalid_value"),
    ("cash", math.nan, "invalid_type"),
    ("revenue", math.inf, "invalid_type"),
])
def test_invalid_numbers_become_unavailable_with_a_finding(fx, field, value, code):
    o = only(ingest([make_record(**{field: value})], fx)).latest
    assert code in codes(o.findings)
    flat = {"price": o.usd.price, "shares_outstanding": o.shares_outstanding, "total_debt": o.usd.total_debt,
            "cash": o.usd.cash, "revenue": o.usd.revenue}
    assert flat[field] is None


def test_unknown_currency_blocks_only_values_in_that_currency(fx):
    o = only(ingest([make_record(reporting_currency="CHF")], fx)).latest
    assert o.usd.revenue is None and o.usd.total_debt is None
    assert o.usd.price == 20.0
    assert codes(o.findings) == ["unknown_currency"]


def test_invalid_units_blocks_money_fields_not_price(fx):
    o = only(ingest([make_record(units="billions")], fx)).latest
    assert o.usd.revenue is None and o.usd.price == 20.0
    assert codes(o.findings) == ["invalid_value"]


def test_nonpositive_denominators_are_kept_and_noted(fx):
    o = only(ingest([make_record(ebitda=-50.0, net_income=0)], fx)).latest
    assert o.usd.ebitda == -50.0 and o.usd.net_income == 0
    notes = [f for f in o.findings if f.code == "nonpositive_denominator"]
    assert sorted(f.affects for f in notes) == [("ev_ebitda",), ("pe",)]
    assert all(f.severity == "info" for f in notes)


def test_large_numbers_are_taken_as_given(fx):
    # Assumption: supplied numbers are the source of truth; no magnitude checks, no rescaling.
    o = only(ingest([make_record(revenue=3_000_000.0)], fx)).latest
    assert o.usd.revenue == 3_000_000.0
    assert o.findings == ()


def test_bad_dates_and_fiscal_year_end(fx):
    o = only(ingest([make_record(price_date="01/10/2026", fiscal_year_end="02-30")], fx)).latest
    assert o.price_date is None
    assert codes(o.findings) == ["invalid_value", "invalid_value"]


def test_unexpected_field_is_preserved_and_noted(fx):
    o = only(ingest([make_record(exchange="NYSE")], fx)).latest
    assert o.original["exchange"] == "NYSE"
    assert codes(o.findings) == ["unexpected_field"]


@pytest.mark.parametrize("country", ["US", None])
def test_record_without_ticker_is_treated_as_unlisted_and_excluded(fx, country):
    ds = ingest([make_record(), make_record(id="x1", ticker=None, country=country, name="No Ticker Co")], fx)
    assert list(ds.entities) == ["US:ACME"]
    (f,) = ds.findings
    assert (f.code, f.record_ids) == ("unlisted_excluded", ("x1",))


def test_only_unlisted_records_is_blocking(fx):
    with pytest.raises(DatasetError, match="no usable"):
        ingest([make_record(ticker=None)], fx)


def test_missing_country_uses_placeholder(fx):
    e = only(ingest([make_record(country=None)], fx))
    assert (e.key, e.country) == ("*:ACME", "")
    assert [f.code for f in e.latest.findings] == ["missing_value"]


def test_missing_id_is_not_a_finding(fx):
    rec = make_record()
    del rec["id"]
    o = only(ingest([rec], fx)).latest
    assert o.record_id == "#0" and o.findings == ()


def test_missing_description_limits_retrieval(fx):
    o = only(ingest([make_record(description="   ")], fx)).latest
    (f,) = o.findings
    assert f.code == "missing_value" and f.affects == ("retrieval",)

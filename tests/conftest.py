"""Synthetic test data. Every company here is invented for the tests."""

from __future__ import annotations

import itertools

import pytest

FX = {"base": "USD", "rates": {"EUR": 1.10, "GBP": 1.25, "JPY": 0.007}}

_ids = itertools.count(1)


def make_record(**overrides):
    """A valid record in the companies.json schema; override any field."""
    rec = {
        "id": f"t{next(_ids):04d}",
        "ticker": "ACME",
        "name": "Acme Widgets Inc",
        "description": "Acme Widgets Inc makes industrial widgets for factory automation customers.",
        "sector": "Industrials",
        "industry": "Machinery",
        "sub_industry": "Industrial Automation",
        "country": "US",
        "price_currency": "USD",
        "reporting_currency": "USD",
        "units": "millions",
        "fiscal_year_end": "12-31",
        "price": 20.0,
        "price_date": "2026-10-01",
        "shares_outstanding": 100.0,
        "total_debt": 500.0,
        "cash": 100.0,
        "revenue": 1000.0,
        "ebitda": 200.0,
        "net_income": 80.0,
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def fx():
    return {"base": "USD", "rates": dict(FX["rates"])}

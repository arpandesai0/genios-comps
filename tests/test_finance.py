"""Glossary formulas, metric states, rounding and peer summary statistics.

Every expected number is worked out by hand in a comment. The base record (conftest.make_record) is:
price 20 USD x 100m shares = market cap 2,000; EV = 2,000 + 500 - 100 = 2,400;
EV/Revenue = 2,400 / 1,000 = 2.4x; EV/EBITDA = 2,400 / 200 = 12.0x; P/E = 2,000 / 80 = 25.0x.
"""

import pytest

from comps.finance import (
    compute_metrics,
    format_money,
    format_multiple,
    round_1dp,
    summarize,
    summarize_metric,
)
from comps.ingest import build_dataset
from comps.models import MetricValue
from conftest import make_record


def observation(fx, **overrides):
    (entity,) = build_dataset([make_record(**overrides)], fx).entities.values()
    return entity.latest


def metrics(fx, **overrides):
    m, _ = compute_metrics(observation(fx, **overrides))
    return m


# --- formulas ---------------------------------------------------------------------------------


def test_base_record_matches_hand_calculation(fx):
    m = metrics(fx)
    assert (m.market_cap_usd_m.raw, m.enterprise_value_usd_m.raw) == (2000.0, 2400.0)
    assert (m.ev_revenue.raw, m.ev_ebitda.raw, m.pe.raw) == pytest.approx((2.4, 12.0, 25.0))
    assert m.market_cap_usd_m.display == "2,000.0"
    assert m.enterprise_value_usd_m.display == "2,400.0"
    assert (m.ev_revenue.display, m.ev_ebitda.display, m.pe.display) == ("2.4x", "12.0x", "25.0x")
    assert all(v.status == "ok" and v.missing_inputs == () for v in vars(m).values())


def test_currency_and_units_are_converted_before_computing(fx):
    # Price 1,000 JPY x 0.007 = 7 USD; x 50m shares = market cap 350.
    # EUR financials in thousands: debt 100,000k = 100m EUR x 1.10 = 110; cash 20,000k -> 22;
    # revenue 300,000k -> 330; EBITDA 60,000k -> 66; net income 25,000k -> 27.5.
    # EV = 350 + 110 - 22 = 438; EV/Rev = 438/330 = 1.327..; EV/EBITDA = 438/66 = 6.636..;
    # P/E = 350/27.5 = 12.727..
    m = metrics(
        fx,
        price=1000.0,
        price_currency="JPY",
        shares_outstanding=50.0,
        reporting_currency="EUR",
        units="thousands",
        total_debt=100_000.0,
        cash=20_000.0,
        revenue=300_000.0,
        ebitda=60_000.0,
        net_income=25_000.0,
    )
    assert m.market_cap_usd_m.raw == pytest.approx(350.0)
    assert m.enterprise_value_usd_m.raw == pytest.approx(438.0)
    assert (m.ev_revenue.display, m.ev_ebitda.display, m.pe.display) == ("1.3x", "6.6x", "12.7x")


# --- NM and missing ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, -50.0])
@pytest.mark.parametrize(
    ("field", "metric"), [("revenue", "ev_revenue"), ("ebitda", "ev_ebitda"), ("net_income", "pe")]
)
def test_zero_or_negative_denominator_is_nm(fx, field, metric, value):
    v = getattr(metrics(fx, **{field: value}), metric)
    assert (v.status, v.value, v.display, v.raw, v.missing_inputs) == ("nm", None, "NM", None, ())


@pytest.mark.parametrize(
    ("field", "blank"),
    [
        ("price", {"market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe"}),
        ("shares_outstanding", {"market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe"}),
        ("total_debt", {"enterprise_value_usd_m", "ev_revenue", "ev_ebitda"}),
        ("cash", {"enterprise_value_usd_m", "ev_revenue", "ev_ebitda"}),
        ("revenue", {"ev_revenue"}),
        ("ebitda", {"ev_ebitda"}),
        ("net_income", {"pe"}),
    ],
)
def test_missing_input_blanks_exactly_the_values_that_need_it(fx, field, blank):
    m = metrics(fx, **{field: None})
    for name, v in vars(m).items():
        if name in blank:
            assert (v.status, v.value, v.display, v.raw, v.missing_inputs) == ("missing", None, None, None, (field,))
        else:
            assert v.status == "ok", name


def test_missing_is_never_zero(fx):
    # Missing cash is not treated as 0: EV stays blank instead of becoming 2,000 + 500 = 2,500.
    m = metrics(fx, cash=None)
    assert m.enterprise_value_usd_m.raw is None


def test_missing_wins_over_nm(fx):
    # Owner decision: a missing input takes precedence over a zero or negative denominator.
    m = metrics(fx, total_debt=None, revenue=-10.0, net_income=0, price=None)
    assert m.ev_revenue.status == "missing"
    assert m.ev_revenue.missing_inputs == ("price", "total_debt")
    assert m.pe.status == "missing" and m.pe.missing_inputs == ("price",)
    # ...and the denominator alone being missing is also missing, not NM.
    assert metrics(fx, ebitda=None).ev_ebitda.missing_inputs == ("ebitda",)


def test_missing_inputs_list_every_cause_once(fx):
    m = metrics(fx, price=None, cash=None, revenue=None)
    assert m.ev_revenue.missing_inputs == ("price", "cash", "revenue")


def test_invalid_input_is_missing_not_nm(fx):
    # Ingestion rejects a negative debt (invalid_value) and stores None, so EV is missing.
    m = metrics(fx, total_debt=-5.0)
    assert m.enterprise_value_usd_m.missing_inputs == ("total_debt",)


def test_unknown_price_currency_names_the_root_cause(fx):
    m = metrics(fx, price_currency="XYZ")
    assert m.market_cap_usd_m.missing_inputs == ("price_currency",)
    assert m.pe.missing_inputs == ("price_currency",)


def test_unknown_reporting_currency_and_units_name_the_root_causes(fx):
    m = metrics(fx, reporting_currency="XYZ", units="billions")
    assert m.market_cap_usd_m.status == "ok"  # price side is unaffected
    assert m.enterprise_value_usd_m.missing_inputs == ("reporting_currency", "units")
    assert m.ev_revenue.missing_inputs == ("reporting_currency", "units")


def test_missing_inputs_follow_formula_order_field_before_its_conversion(fx):
    # Order: numerator causes, then denominator causes; within a field, the field then its conversion.
    # P/E: market cap is fine, so only net income is blamed: the field, then its currency.
    assert metrics(fx, net_income=None, reporting_currency="XYZ").pe.missing_inputs == (
        "net_income",
        "reporting_currency",
    )
    # EV/Revenue: the numerator EV already blames reporting_currency (via debt and cash), then revenue.
    assert metrics(fx, revenue=None, reporting_currency="XYZ").ev_revenue.missing_inputs == (
        "reporting_currency",
        "revenue",
    )


# --- negative EV ------------------------------------------------------------------------------


def test_negative_ev_is_used_as_given_with_an_info_finding(fx):
    # Cash 3,000 > market cap 2,000 + debt 500: EV = -500; EV/Rev = -0.5x; EV/EBITDA = -2.5x.
    m, findings = compute_metrics(observation(fx, cash=3000.0))
    assert m.enterprise_value_usd_m.display == "-500.0"
    assert (m.ev_revenue.status, m.ev_revenue.display) == ("ok", "-0.5x")
    assert (m.ev_ebitda.status, m.ev_ebitda.display) == ("ok", "-2.5x")
    assert m.pe.display == "25.0x"  # P/E does not use EV
    (f,) = findings
    assert (f.code, f.severity, f.source) == ("nonpositive_ev", "info", "validation")
    assert set(f.affects) == {"enterprise_value_usd_m", "ev_revenue", "ev_ebitda"}
    assert f.record_ids


def test_zero_ev_gives_zero_multiples_and_the_same_finding(fx):
    # Cash 2,500 = market cap 2,000 + debt 500, so EV = 0 and EV/Rev = 0.0x.
    m, findings = compute_metrics(observation(fx, cash=2500.0))
    assert (m.ev_revenue.status, m.ev_revenue.display) == ("ok", "0.0x")
    assert [f.code for f in findings] == ["nonpositive_ev"]


def test_ev_zero_is_judged_after_cleaning_float_noise(fx):
    # 0.1 x 30 = 3.0000000000000004 in floats; minus cash 3.0 gives 4e-16, not 0.
    # Cleaned at 9 dp, EV is exactly 0, so the finding fires and EV/Rev shows 0.0x.
    m, findings = compute_metrics(observation(fx, price=0.1, shares_outstanding=30.0, total_debt=0.0, cash=3.0))
    assert m.enterprise_value_usd_m.raw == 0.0
    assert m.ev_revenue.display == "0.0x"
    assert [f.code for f in findings] == ["nonpositive_ev"]


def test_positive_ev_raises_no_finding(fx):
    assert compute_metrics(observation(fx))[1] == ()


def test_ev_findings_need_a_computed_ev(fx):
    assert compute_metrics(observation(fx, cash=None))[1] == ()


# --- rounding and display ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        (12.25, 12.3),
        (-12.25, -12.3),
        (12.24, 12.2),
        (0.35, 0.4),  # binary 0.34999..; builtin round() gives 0.3
        (0.45, 0.5),  # binary 0.45000..1; builtin round() gives 0.5 too, but by luck
        (2.05 * 3, 6.2),  # arithmetic tie: 6.1499999999999995 is cleaned to 6.15 first
        (0.05, 0.1),
        (-0.04, 0.0),
        (1234.56, 1234.6),
    ],
)
def test_round_half_away_from_zero(x, expected):
    assert round_1dp(x) == expected


def test_display_formats():
    assert format_money(4512.25) == "4,512.3"
    assert format_money(-1234.5) == "-1,234.5"
    assert format_money(-0.04) == "0.0"  # never "-0.0"
    assert format_multiple(12.25) == "12.3x"
    assert format_multiple(-2.05) == "-2.1x"
    assert format_multiple(1234.5) == "1,234.5x"


def test_ok_value_is_rounded_and_raw_is_not(fx):
    # EV/EBITDA = 2,400 / 192 = 12.5 exactly; EV/Rev = 2,400 / 1,030 = 2.3300..
    m = metrics(fx, ebitda=192.0, revenue=1030.0)
    assert (m.ev_ebitda.value, m.ev_ebitda.display) == (12.5, "12.5x")
    assert m.ev_revenue.raw == pytest.approx(2.330097, rel=1e-6)
    assert m.ev_revenue.value == 2.3


# --- summary statistics -----------------------------------------------------------------------


def ok(raw):
    return MetricValue(status="ok", value=round_1dp(raw), display=format_multiple(raw), raw=raw)


NM = MetricValue(status="nm", value=None, display="NM", raw=None)
MISSING = MetricValue(status="missing", value=None, display=None, raw=None, missing_inputs=("ebitda",))


def test_summary_excludes_nm_and_missing_and_counts_them():
    # Valid values 4, 10, 1: mean 5.0, median 4.0, high 10.0, low 1.0.
    s = summarize_metric([ok(4.0), NM, ok(10.0), MISSING, ok(1.0), NM])
    assert (s.n, s.n_nm, s.n_missing) == (3, 2, 1)
    assert (s.mean, s.median, s.high, s.low) == (5.0, 4.0, 10.0, 1.0)
    assert (s.display.mean, s.display.median, s.display.high, s.display.low) == ("5.0x", "4.0x", "10.0x", "1.0x")


def test_even_count_median_averages_the_middle_two():
    # 2, 3, 8, 20 -> median (3 + 8) / 2 = 5.5
    assert summarize_metric([ok(20.0), ok(2.0), ok(8.0), ok(3.0)]).median == 5.5


def test_stats_use_unrounded_values():
    # Raw 1.24 x4 and 1.9: mean 6.86 / 5 = 1.372 -> 1.4.
    # On the displayed values 1.2 x4 and 1.9 the mean would be 6.7 / 5 = 1.34 -> 1.3.
    s = summarize_metric([ok(1.24)] * 4 + [ok(1.9)])
    assert s.mean == 1.4 and s.display.mean == "1.4x"


def test_single_peer_stats_all_equal_its_value():
    s = summarize_metric([ok(7.0)])
    assert (s.n, s.mean, s.median, s.high, s.low) == (1, 7.0, 7.0, 7.0, 7.0)


def test_negative_multiples_are_included():
    # -2, 4, 7: mean 3.0, low -2.0
    s = summarize_metric([ok(-2.0), ok(4.0), ok(7.0)])
    assert (s.mean, s.low, s.display.low) == (3.0, -2.0, "-2.0x")


def test_no_valid_values_gives_blank_stats():
    s = summarize_metric([NM, MISSING])
    assert (s.n, s.n_nm, s.n_missing) == (0, 1, 1)
    assert (s.mean, s.median, s.high, s.low) == (None, None, None, None)
    assert (s.display.mean, s.display.median, s.display.high, s.display.low) == (None, None, None, None)
    assert summarize_metric([]).n == 0


def test_summarize_covers_the_three_multiples_of_the_peers_passed(fx):
    # Peers: base (EV/Rev 2.4, EV/EBITDA 12.0, P/E 25.0) and one with net income 0 (P/E NM)
    # and revenue 600 (EV/Rev 2,400 / 600 = 4.0). The caller passes peers only.
    peers = [metrics(fx), metrics(fx, net_income=0, revenue=600.0)]
    s = summarize(peers)
    assert (s.ev_revenue.n, s.ev_revenue.mean) == (2, 3.2)
    assert (s.ev_ebitda.n, s.ev_ebitda.median) == (2, 12.0)
    assert (s.pe.n, s.pe.n_nm, s.pe.mean) == (1, 1, 25.0)


# --- overflow -----------------------------------------------------------------------------------


def test_overflowing_multiple_is_missing_with_a_warning(fx):
    # EV 2,400 / revenue 1e-320 overflows to inf: blank, excluded from stats, never a crash.
    m, findings = compute_metrics(observation(fx, revenue=1e-320))
    assert (m.ev_revenue.status, m.ev_revenue.display, m.ev_revenue.missing_inputs) == ("missing", None, ())
    assert m.ev_ebitda.status == "ok"
    (f,) = findings
    assert (f.code, f.severity, f.affects) == ("non_finite_result", "warning", ("ev_revenue",))
    assert summarize([m]).ev_revenue.n_missing == 1


def test_overflowing_market_cap_blanks_everything_built_on_it(fx):
    # 1e200 x 1e200 = inf, so market cap, EV and all three multiples are blank.
    m, findings = compute_metrics(observation(fx, price=1e200, shares_outstanding=1e200))
    assert all(v.status == "missing" for v in vars(m).values())
    (f,) = findings
    assert set(f.affects) == {"market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe"}


def test_huge_finite_values_still_round_and_display(fx):
    # 1e30 has more digits than decimal's default precision; it must not raise.
    m = metrics(fx, price=1e15, shares_outstanding=1e15)
    assert m.market_cap_usd_m.status == "ok"
    assert m.market_cap_usd_m.display == "1" + ",000" * 10 + ".0"


def test_invalid_field_and_failed_conversion_are_both_named(fx):
    # Owner rule: never serve a partial explanation. Debt -5 is invalid, and the reporting currency is
    # unknown, so both causes are listed (field first, then its conversion).
    m = metrics(fx, total_debt=-5.0, reporting_currency="XYZ")
    assert m.enterprise_value_usd_m.missing_inputs == ("total_debt", "reporting_currency")


def test_wrong_type_field_and_failed_conversion_are_both_named(fx):
    # P/E isolates one field: market cap is fine, net income is a string and units are invalid.
    m = metrics(fx, net_income="80", units="billions")
    assert m.pe.missing_inputs == ("net_income", "units")

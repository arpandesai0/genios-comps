"""Glossary formulas, metric states and peer summary statistics.

Pure functions: an ``Observation`` goes in, metric values come out. This module knows nothing
about where an observation came from or how peers were chosen.

Rules (GLOSSARY.md plus owner decisions in AGENTS.md):

- market cap = USD price x shares (millions); EV = market cap + debt - cash.
- EV/Revenue, EV/EBITDA and P/E. A zero or negative denominator gives NM.
- A missing input gives ``missing`` (blank), and this takes precedence over NM.
- A negative EV is used as given, and a zero or negative EV raises an info finding.
- Summary statistics use peers only (the caller passes only peers) and exclude NM and missing values.
- Everything is computed unrounded. Display values are rounded to 1 dp, with ties rounded
  half away from zero.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from decimal import ROUND_HALF_UP, Decimal

from comps.models import (
    Finding,
    Metrics,
    MetricValue,
    Observation,
    StatDisplay,
    Summary,
    SummaryStat,
)

_ONE_DP = Decimal("0.1")
_MONEY_FIELDS = ("total_debt", "cash", "revenue", "ebitda", "net_income")


# --- rounding and display ---------------------------------------------------------------------


def _quantize(x: float) -> Decimal:
    # repr() gives the shortest decimal that round-trips, so 2.675 rounds as 2.675 and not as its
    # binary approximation 2.67499... ROUND_HALF_UP in decimal rounds ties away from zero.
    d = Decimal(repr(x)).quantize(_ONE_DP, rounding=ROUND_HALF_UP)
    return d if d != 0 else Decimal("0.0")  # never show "-0.0"


def round_1dp(x: float) -> float:
    """Round to one decimal place, ties away from zero (12.25 -> 12.3, -12.25 -> -12.3)."""
    return float(_quantize(x))


def format_money(x: float) -> str:
    """USD millions for display: ``'4,512.3'``, ``'-1,234.5'``."""
    return f"{_quantize(x):,.1f}"


def format_multiple(x: float) -> str:
    """A multiple for display: ``'12.3x'``, ``'-2.1x'``, ``'1,234.5x'``."""
    return f"{_quantize(x):,.1f}x"


# --- metric values ----------------------------------------------------------------------------


def _ok(raw: float, fmt: Callable[[float], str]) -> MetricValue:
    return MetricValue(status="ok", value=round_1dp(raw), display=fmt(raw), raw=raw)


def _missing(inputs: Sequence[str]) -> MetricValue:
    return MetricValue(status="missing", value=None, display=None, raw=None, missing_inputs=_dedupe(inputs))


_NM = MetricValue(status="nm", value=None, display="NM", raw=None)


def _dedupe(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _causes(obs: Observation, name: str) -> list[str]:
    """The record fields to blame when the USD value of ``name`` is unavailable.

    If a currency or units conversion failed, those root fields are named. The field itself is named
    when it is absent or invalid in the record, or when no conversion failed.
    """
    c = obs.conversion
    if name == "price":
        conversion = ["price_currency"] if c.price_fx is None else []
    else:
        conversion = (["reporting_currency"] if c.reporting_fx is None else []) + (
            ["units"] if c.unit_factor is None else []
        )
    own = [name] if (obs.original.get(name) is None or not conversion) else []
    return own + conversion


def _value(obs: Observation, name: str) -> tuple[float | None, list[str]]:
    if name == "shares_outstanding":
        v = obs.shares_outstanding
        return v, ([] if v is not None else [name])
    v = getattr(obs.usd, name)
    return v, ([] if v is not None else _causes(obs, name))


def compute_metrics(obs: Observation) -> tuple[Metrics, tuple[Finding, ...]]:
    """Compute the comps-table metrics for one observation (normally an entity's latest).

    Returns the metrics and any findings raised while computing them (``nonpositive_ev``).
    The findings carry the record id. The caller adds entity keys if it needs them.
    """
    price, m_price = _value(obs, "price")
    shares, m_shares = _value(obs, "shares_outstanding")
    debt, m_debt = _value(obs, "total_debt")
    cash, m_cash = _value(obs, "cash")

    mc_missing = m_price + m_shares
    mc = price * shares if price is not None and shares is not None else None
    ev_missing = mc_missing + m_debt + m_cash
    ev = mc + debt - cash if mc is not None and debt is not None and cash is not None else None

    market_cap = _ok(mc, format_money) if mc is not None else _missing(mc_missing)
    enterprise_value = _ok(ev, format_money) if ev is not None else _missing(ev_missing)

    def multiple(numerator: float | None, num_missing: list[str], denom_name: str) -> MetricValue:
        denom, d_missing = _value(obs, denom_name)
        if numerator is None or denom is None:  # missing wins over NM
            return _missing(num_missing + d_missing)
        if denom <= 0:
            return _NM
        return _ok(numerator / denom, format_multiple)

    metrics = Metrics(
        market_cap_usd_m=market_cap,
        enterprise_value_usd_m=enterprise_value,
        ev_revenue=multiple(ev, ev_missing, "revenue"),
        ev_ebitda=multiple(ev, ev_missing, "ebitda"),
        pe=multiple(mc, mc_missing, "net_income"),
    )

    findings: list[Finding] = []
    if ev is not None and ev <= 0:
        findings.append(
            Finding(
                code="nonpositive_ev",
                severity="info",
                message=(
                    f"Enterprise value is {format_money(ev)} (USD m), which is zero or negative because cash "
                    "is at least market cap + debt. EV multiples are shown as computed."
                ),
                fields=("price", "shares_outstanding", "total_debt", "cash"),
                affects=("enterprise_value_usd_m", "ev_revenue", "ev_ebitda"),
                record_ids=(obs.record_id,),
            )
        )
    return metrics, tuple(findings)


# --- summary statistics -----------------------------------------------------------------------


def summarize_metric(values: Sequence[MetricValue]) -> SummaryStat:
    """Mean, median, high and low over the ``ok`` values, with counts of NM and missing values."""
    raws = [v.raw for v in values if v.status == "ok" and v.raw is not None]
    n_nm = sum(1 for v in values if v.status == "nm")
    n_missing = sum(1 for v in values if v.status == "missing")
    if not raws:
        return SummaryStat(
            n=0,
            n_nm=n_nm,
            n_missing=n_missing,
            mean=None,
            median=None,
            high=None,
            low=None,
            display=StatDisplay(mean=None, median=None, high=None, low=None),
        )
    stats = {
        "mean": statistics.fmean(raws),
        "median": statistics.median(raws),  # even n: average of the middle two
        "high": max(raws),
        "low": min(raws),
    }
    return SummaryStat(
        n=len(raws),
        n_nm=n_nm,
        n_missing=n_missing,
        **{k: round_1dp(v) for k, v in stats.items()},
        display=StatDisplay(**{k: format_multiple(v) for k, v in stats.items()}),
    )


def summarize(peers: Sequence[Metrics]) -> Summary:
    """Peer-only summary statistics for the three multiples.

    The caller must pass peers only, never the target company.
    """
    return Summary(
        ev_revenue=summarize_metric([p.ev_revenue for p in peers]),
        ev_ebitda=summarize_metric([p.ev_ebitda for p in peers]),
        pe=summarize_metric([p.pe for p in peers]),
    )

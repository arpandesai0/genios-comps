"""Ingestion: load → validate/normalize → resolve entities → dataset.

Ingestion knows nothing about retrieval or finance. It produces normalized USD values,
observation histories per company, and structured findings. It never imputes, rescales,
or rewrites data: anything doubtful becomes a finding.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from comps import quality
from comps.config import IngestConfig
from comps.models import (
    Conversion,
    Dataset,
    Entity,
    Finding,
    Observation,
    Origin,
    SourceFile,
    TextVersion,
    UsdValues,
)

COMPANIES_FILE = "companies.json"
FX_FILE = "fx_rates.json"

SCHEMA_FIELDS = (
    "id",
    "ticker",
    "name",
    "description",
    "sector",
    "industry",
    "sub_industry",
    "country",
    "price_currency",
    "reporting_currency",
    "units",
    "fiscal_year_end",
    "price",
    "price_date",
    "shares_outstanding",
    "total_debt",
    "cash",
    "revenue",
    "ebitda",
    "net_income",
)
TEXT_FIELDS = ("name", "description", "sector", "industry", "sub_industry", "fiscal_year_end")
MONEY_FIELDS = ("total_debt", "cash", "revenue", "ebitda", "net_income")
UNIT_FACTORS = {"millions": 1.0, "thousands": 0.001}
UNKNOWN_COUNTRY = "*"

_ALL_METRICS = ("market_cap_usd_m", "enterprise_value_usd_m", "ev_revenue", "ev_ebitda", "pe")
_EV_METRICS = ("enterprise_value_usd_m", "ev_revenue", "ev_ebitda")
AFFECTS: dict[str, tuple[str, ...]] = {
    "price": _ALL_METRICS,
    "shares_outstanding": _ALL_METRICS,
    "price_currency": _ALL_METRICS,
    "total_debt": _EV_METRICS,
    "cash": _EV_METRICS,
    "revenue": ("ev_revenue", "size_evidence"),
    "ebitda": ("ev_ebitda",),
    "net_income": ("pe",),
    "reporting_currency": _EV_METRICS + ("pe",),
    "units": _EV_METRICS + ("pe",),
    "description": ("retrieval",),
    "ticker": ("identity",),
    "country": ("identity", "geography_evidence"),
    "price_date": ("freshness", "observation_order"),
    "sector": ("classification_evidence",),
    "industry": ("classification_evidence",),
    "sub_industry": ("classification_evidence",),
    "name": ("search",),
    "fiscal_year_end": (),
}
# A missing value in one of these fields limits what the service can do; anything else is a warning.
_LIMITING_FIELDS = {f for f, a in AFFECTS.items() if a and not all(x.endswith("evidence") for x in a)}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_DAY = re.compile(r"^(\d{2})-(\d{2})$")


class DatasetError(Exception):
    """A blocking problem: the input cannot produce a usable dataset."""

    def __init__(self, message: str, findings: Sequence[Finding] = ()):
        super().__init__(message)
        self.findings = tuple(findings)


# --------------------------------------------------------------------------- loading


def load_dataset(
    data_dir: Path | str,
    config: IngestConfig | None = None,
    extra_records: Sequence[Mapping[str, Any]] = (),
) -> Dataset:
    """Read ``companies.json`` and ``fx_rates.json`` from ``data_dir`` and ingest them.

    ``extra_records`` are manual additions; they are ingested with ``origin="manual"``.
    """
    data_dir = Path(data_dir)
    raw_companies = _read_json(data_dir / COMPANIES_FILE)
    raw_fx = _read_json(data_dir / FX_FILE)
    files = tuple(
        SourceFile(name=name, sha256=hashlib.sha256(raw).hexdigest())
        for name, raw in ((COMPANIES_FILE, raw_companies[0]), (FX_FILE, raw_fx[0]))
    )
    return build_dataset(raw_companies[1], raw_fx[1], config=config, files=files, extra_records=extra_records)


def _read_json(path: Path) -> tuple[bytes, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise DatasetError(f"cannot read {path}: {exc.strerror or exc}") from exc
    try:
        return raw, json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetError(f"{path.name} is not valid JSON: {exc}") from exc


def build_dataset(
    companies: Any,
    fx: Any,
    *,
    config: IngestConfig | None = None,
    files: tuple[SourceFile, ...] = (),
    extra_records: Sequence[Mapping[str, Any]] = (),
) -> Dataset:
    """Pure ingestion of already-parsed JSON. Deterministic for a given input."""
    config = config or IngestConfig()
    rates, dataset_findings = parse_fx(fx)

    if not isinstance(companies, list):
        raise DatasetError(f"{COMPANIES_FILE} must contain a JSON list of records")

    inputs: list[tuple[Any, Origin]] = [(r, "file") for r in companies]
    inputs += [(r, "manual") for r in extra_records]

    normalized: list[_Normalized] = []
    for index, (raw, origin) in enumerate(inputs):
        if not isinstance(raw, Mapping):
            dataset_findings.append(
                Finding(
                    code="invalid_record",
                    severity="error",
                    message=f"Record #{index} is not a JSON object and was skipped.",
                    affects=("ingestion",),
                )
            )
            continue
        record = normalize_record(raw, index=index, origin=origin, rates=rates)
        if record.ticker is None:
            # Assumption: the universe is public companies, so a record without a ticker is treated
            # as not listed. There is no offline way to verify it, so it is excluded.
            dataset_findings.append(
                Finding(
                    code="unlisted_excluded",
                    severity="warning",
                    fields=("ticker",),
                    message=f"Record {record.observation.record_id} has no ticker, so it is treated as not listed "
                    "and excluded from the universe.",
                    affects=("universe",),
                    record_ids=(record.observation.record_id,),
                )
            )
            continue
        normalized.append(record)

    if not normalized:
        raise DatasetError("no usable company records", dataset_findings)
    entities = resolve_entities(normalized)

    reference_date = config.reference_date or max(
        (e.latest.price_date for e in entities.values() if e.latest.price_date), default=None
    )
    extra = quality.cross_entity_findings(entities, reference_date, config)
    entities = {
        key: replace(e, findings=e.findings + tuple(extra.get(key, ()))) if key in extra else e
        for key, e in entities.items()
    }

    return Dataset(
        version=_version(files, companies, fx, extra_records),
        reference_date=reference_date,
        fx_rates=rates,
        files=files,
        record_count=len(inputs),
        entities=entities,
        findings=tuple(dataset_findings),
        metadata={"manual_records": len(extra_records)},
    )


def _version(files, companies, fx, extra_records) -> str:
    h = hashlib.sha256()
    if files:
        for f in files:
            h.update(f.sha256.encode())
    else:
        h.update(json.dumps([companies, fx], sort_keys=True, default=str).encode())
    if extra_records:
        h.update(json.dumps(list(extra_records), sort_keys=True, default=str).encode())
    return h.hexdigest()[:12]


# --------------------------------------------------------------------------- fx


def parse_fx(fx: Any) -> tuple[dict[str, float], list[Finding]]:
    """Validate the FX file. USD is the base and is always 1.0."""
    if not isinstance(fx, Mapping) or not isinstance(fx.get("rates"), Mapping):
        raise DatasetError(f"{FX_FILE} must be an object with a 'rates' object")
    base = fx.get("base")
    if not isinstance(base, str) or base.strip().upper() != "USD":
        raise DatasetError(f"{FX_FILE} base must be 'USD' (rates are USD per unit), got {base!r}")

    findings: list[Finding] = []
    rates: dict[str, float] = {"USD": 1.0}
    for code, value in fx["rates"].items():
        ccy = str(code).strip().upper()
        if not _is_number(value) or value <= 0:
            findings.append(
                Finding(
                    code="invalid_fx_rate",
                    severity="limitation",
                    message=f"FX rate for {ccy} is {value!r}; values in {ccy} cannot be converted.",
                    fields=("fx_rates",),
                    affects=("currency_conversion",),
                )
            )
            continue
        if ccy == "USD" and float(value) != 1.0:
            raise DatasetError(f"{FX_FILE} lists USD at {value}, inconsistent with base USD")
        rates[ccy] = float(value)
    return rates, findings


# --------------------------------------------------------------------------- record normalization


@dataclass(frozen=True)
class _Normalized:
    key: str
    ticker: str | None
    country: str | None
    text: dict[str, str | None]
    observation: Observation
    content_signature: str  # everything except id: equal signatures = exact duplicate


def normalize_record(
    raw: Mapping[str, Any],
    *,
    index: int,
    origin: Origin,
    rates: Mapping[str, float],
) -> _Normalized:
    """Validate one record and normalize its values to USD. Never raises for bad values."""
    rid_raw = raw.get("id")
    record_id = rid_raw.strip() if isinstance(rid_raw, str) and rid_raw.strip() else f"#{index}"
    f = _FindingSink(record_id)

    for name in SCHEMA_FIELDS:
        if name not in raw and name != "id":  # ids are internal provenance only
            f.add("missing_field", _severity(name), (name,), f"Field '{name}' is absent.", AFFECTS.get(name, ()))
    for name in raw:
        if name not in SCHEMA_FIELDS:
            f.add("unexpected_field", "info", (name,), f"Unknown field '{name}' was preserved but not used.")

    ticker = _code(raw, "ticker", f)
    country = _code(raw, "country", f)
    text = {name: _text(raw, name, f) for name in TEXT_FIELDS}
    if text["fiscal_year_end"] is not None and not _valid_month_day(text["fiscal_year_end"]):
        f.add(
            "invalid_value",
            "warning",
            ("fiscal_year_end",),
            f"fiscal_year_end {text['fiscal_year_end']!r} is not a valid MM-DD.",
        )

    price_date = _date(raw, "price_date", f)
    price = _number(raw, "price", f, minimum=0.0, inclusive=False)
    shares = _number(raw, "shares_outstanding", f, minimum=0.0, inclusive=False)
    debt = _number(raw, "total_debt", f, minimum=0.0)
    cash = _number(raw, "cash", f, minimum=0.0)
    flows = {name: _number(raw, name, f) for name in ("revenue", "ebitda", "net_income")}
    for name, metric in (("revenue", "ev_revenue"), ("ebitda", "ev_ebitda"), ("net_income", "pe")):
        v = flows[name]
        if v is not None and v <= 0:
            f.add(
                "nonpositive_denominator",
                "info",
                (name,),
                f"{name} is {v:g} (zero or negative), so {metric} will be NM (not meaningful) "
                "unless another input it needs is missing.",
                (metric,),
            )

    price_ccy = _code(raw, "price_currency", f)
    report_ccy = _code(raw, "reporting_currency", f)
    price_fx = _rate(price_ccy, "price_currency", rates, f)
    report_fx = _rate(report_ccy, "reporting_currency", rates, f)
    unit_factor = _units(raw, f)

    money_scale = report_fx * unit_factor if report_fx is not None and unit_factor is not None else None
    raw_money = {"total_debt": debt, "cash": cash, **flows}
    usd_money = {
        k: (v * money_scale if v is not None and money_scale is not None else None) for k, v in raw_money.items()
    }
    usd = UsdValues(price=price * price_fx if price is not None and price_fx is not None else None, **usd_money)

    # A missing country gets the placeholder "*"; records without a ticker are dropped by the caller.
    key = f"{country or UNKNOWN_COUNTRY}:{ticker}"
    findings = tuple(replace(x, entity_keys=(key,)) for x in f.items)

    observation = Observation(
        record_id=record_id,
        origin=origin,
        source_index=index,
        price_date=price_date,
        original=dict(raw),
        shares_outstanding=shares,
        usd=usd,
        conversion=Conversion(price_fx=price_fx, reporting_fx=report_fx, unit_factor=unit_factor),
        findings=findings,
    )

    content = {k: v for k, v in raw.items() if k != "id"}
    return _Normalized(
        key=key,
        ticker=ticker,
        country=country,
        text=text,
        observation=observation,
        content_signature=_signature(content),
    )


class _FindingSink:
    def __init__(self, record_id: str):
        self.record_id = record_id
        self.items: list[Finding] = []

    def add(self, code, severity, fields, message, affects=()):
        self.items.append(
            Finding(
                code=code,
                severity=severity,
                message=message,
                fields=tuple(fields),
                affects=tuple(affects),
                record_ids=(self.record_id,),
            )
        )


def _severity(field: str) -> str:
    return "limitation" if field in _LIMITING_FIELDS else "warning"


def _present(raw: Mapping[str, Any], name: str, f: _FindingSink) -> Any:
    """Return the value, recording a finding if it is null (absent fields are reported once, earlier)."""
    if name not in raw:
        return None
    value = raw[name]
    if value is None:
        f.add("missing_value", _severity(name), (name,), f"{name} is null.", AFFECTS.get(name, ()))
    return value


def _text(raw, name, f) -> str | None:
    value = _present(raw, name, f)
    if value is None:
        return None
    if not isinstance(value, str):
        f.add(
            "invalid_type",
            _severity(name),
            (name,),
            f"{name} should be text, got {type(value).__name__}.",
            AFFECTS.get(name, ()),
        )
        return None
    value = value.strip()
    if not value:
        f.add("missing_value", _severity(name), (name,), f"{name} is empty.", AFFECTS.get(name, ()))
        return None
    return value


def _code(raw, name, f) -> str | None:
    """Short codes (ticker, country, currency) are trimmed and upper-cased; changes are recorded."""
    value = _text(raw, name, f)
    if value is None:
        return None
    upper = value.upper()
    if upper != raw[name]:
        f.add("normalized_value", "info", (name,), f"{name} {raw[name]!r} was read as {upper!r}.")
    return upper


def _number(raw, name, f, minimum: float | None = None, inclusive: bool = True) -> float | None:
    value = _present(raw, name, f)
    if value is None:
        return None
    if not _is_number(value):
        f.add("invalid_type", "limitation", (name,), f"{name} should be a number, got {value!r}.", AFFECTS[name])
        return None
    value = float(value)
    if minimum is not None and (value < minimum or (not inclusive and value == minimum)):
        rule = f"{'≥' if inclusive else '>'} {minimum:g}"
        f.add(
            "invalid_value",
            "limitation",
            (name,),
            f"{name} is {value:g}; it must be {rule}. Treated as unavailable.",
            AFFECTS[name],
        )
        return None
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _date(raw, name, f) -> date | None:
    value = _text(raw, name, f)
    if value is None:
        return None
    try:
        if not _ISO_DATE.match(value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        f.add("invalid_value", "limitation", (name,), f"{name} {value!r} is not a YYYY-MM-DD date.", AFFECTS[name])
        return None


def _valid_month_day(value: str) -> bool:
    m = _MONTH_DAY.match(value)
    if not m:
        return False
    try:
        date(2024, int(m.group(1)), int(m.group(2)))  # leap year, so 02-29 is accepted
        return True
    except ValueError:
        return False


def _rate(ccy: str | None, name: str, rates: Mapping[str, float], f) -> float | None:
    if ccy is None:
        return None
    if ccy not in rates:
        f.add(
            "unknown_currency",
            "limitation",
            (name,),
            f"No FX rate for {ccy}; values in it cannot be converted to USD.",
            AFFECTS[name],
        )
        return None
    return rates[ccy]


def _units(raw, f) -> float | None:
    value = _text(raw, "units", f)
    if value is None:
        return None
    lowered = value.lower()
    if lowered not in UNIT_FACTORS:
        f.add(
            "invalid_value",
            "limitation",
            ("units",),
            f"units {value!r} must be 'millions' or 'thousands'.",
            AFFECTS["units"],
        )
        return None
    if lowered != raw["units"]:
        f.add("normalized_value", "info", ("units",), f"units {raw['units']!r} was read as {lowered!r}.")
    return UNIT_FACTORS[lowered]


def _signature(obj: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


# --------------------------------------------------------------------------- entity resolution


def _order(r: _Normalized) -> tuple[date, int]:
    return (r.observation.price_date or date.min, r.observation.source_index)


def resolve_entities(records: Sequence[_Normalized]) -> dict[str, Entity]:
    """Group records by COUNTRY:TICKER and build each company's observation history.

    Rules (see AGENTS.md decision log):
    - identical content (ignoring id) collapses into one observation; the later record is kept;
    - one observation per price_date; on a same-date conflict the later record in the input wins;
    - text fields take the latest observation's value; changes are kept as provenance.
    """
    groups: dict[str, list[_Normalized]] = {}
    for r in records:
        groups.setdefault(r.key, []).append(r)
    return {key: _build_entity(key, sorted(groups[key], key=_order)) for key in sorted(groups)}


def _build_entity(key: str, group: list[_Normalized]) -> Entity:
    findings: list[Finding] = []

    # 1. exact duplicates: keep the later record (records are already in order)
    by_content: dict[str, _Normalized] = {}
    for r in group:
        prev = by_content.get(r.content_signature)
        if prev is not None:
            findings.append(
                Finding(
                    code="exact_duplicate",
                    severity="info",
                    fields=("id",),
                    message=f"Records {prev.observation.record_id} and {r.observation.record_id} are identical apart "
                    f"from their id; kept {r.observation.record_id}.",
                    affects=(),
                    record_ids=(prev.observation.record_id, r.observation.record_id),
                    entity_keys=(key,),
                )
            )
        by_content[r.content_signature] = r
    distinct = sorted(by_content.values(), key=_order)

    # 2. one observation per price_date; the later record wins a same-date conflict
    by_date: dict[date | None, list[_Normalized]] = {}
    for r in distinct:
        by_date.setdefault(r.observation.price_date, []).append(r)
    series: list[_Normalized] = []
    for d, same_day in by_date.items():
        winner = same_day[-1]
        series.append(winner)
        losers = same_day[:-1]
        numeric_conflict = [r for r in losers if _numbers(r) != _numbers(winner)]
        if numeric_conflict:
            ids = tuple(r.observation.record_id for r in numeric_conflict) + (winner.observation.record_id,)
            findings.append(
                Finding(
                    code="conflicting_observation",
                    severity="warning",
                    fields=_numeric_diff(numeric_conflict, winner),
                    message=f"{len(ids)} records for {key} share price_date {d} but report different numbers; "
                    f"using {winner.observation.record_id} (latest in the input).",
                    affects=_ALL_METRICS,
                    record_ids=ids,
                    entity_keys=(key,),
                )
            )
    series.sort(key=_order)
    latest = series[-1]
    in_series = {id(r) for r in series}
    superseded = tuple(r.observation for r in group if id(r) not in in_series)

    # 3. text fields: latest wins; differences are provenance or conflicts
    text: dict[str, str | None] = {}
    history: list[TextVersion] = []
    for name in TEXT_FIELDS:
        values = {r.text[name] for r in distinct}
        text[name] = latest.text[name]
        from_older = False
        if text[name] is None:
            older = [r for r in reversed(distinct) if r.text[name] is not None]
            if older:
                text[name] = older[0].text[name]
                from_older = True
                findings.append(
                    Finding(
                        code="text_from_older_record",
                        severity="info",
                        fields=(name,),
                        message=f"Latest record has no {name}; using the value from {older[0].observation.record_id}.",
                        record_ids=(latest.observation.record_id, older[0].observation.record_id),
                        entity_keys=(key,),
                    )
                )
        if len(values) <= 1:
            continue
        history.extend(
            TextVersion(name, r.text[name], r.observation.record_id, r.observation.price_date) for r in distinct
        )
        tied = {r.text[name] for r in distinct if r.observation.price_date == latest.observation.price_date}
        ids = tuple(r.observation.record_id for r in distinct)
        if len(tied) > 1:
            findings.append(
                Finding(
                    code="conflicting_attributes",
                    severity="warning",
                    fields=(name,),
                    message=f"Records with the same latest price_date disagree on {name}; using the later record's "
                    f"value {text[name]!r}.",
                    affects=AFFECTS.get(name, ()),
                    record_ids=ids,
                    entity_keys=(key,),
                )
            )
        else:
            findings.append(
                Finding(
                    code="text_updated",
                    severity="info",
                    fields=(name,),
                    message=(
                        f"{name} changed over time; using the most recent non-empty value. "
                        if from_older
                        else f"{name} changed over time; using the latest value. "
                    )
                    + "Earlier values are kept as provenance.",
                    record_ids=ids,
                    entity_keys=(key,),
                )
            )

    aliases = tuple(dict.fromkeys(r.text["name"] for r in distinct if r.text["name"]))
    return Entity(
        key=key,
        ticker=latest.ticker or "",
        country=latest.country or "",
        name=text["name"],
        description=text["description"],
        sector=text["sector"],
        industry=text["industry"],
        sub_industry=text["sub_industry"],
        fiscal_year_end=text["fiscal_year_end"],
        aliases=aliases,
        observations=tuple(r.observation for r in series),
        superseded=superseded,
        text_history=tuple(history),
        findings=tuple(findings),
    )


_NUMERIC_KEYS = ("price", "price_currency", "shares_outstanding", "reporting_currency", "units") + MONEY_FIELDS


def _numbers(r: _Normalized) -> tuple:
    return tuple(r.observation.original.get(k) for k in _NUMERIC_KEYS)


def _numeric_diff(losers: list[_Normalized], winner: _Normalized) -> tuple[str, ...]:
    return tuple(
        k
        for k in _NUMERIC_KEYS
        if any(r.observation.original.get(k) != winner.observation.original.get(k) for r in losers)
    )

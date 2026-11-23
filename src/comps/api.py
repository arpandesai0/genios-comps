"""FastAPI adapter for the read-only endpoints in docs/API.md.

Handlers only parse parameters, call the service and serialise. There's no business logic here.
Handlers are plain ``def``, so FastAPI runs them in its threadpool, and each request reads the
same immutable snapshot.

Peers and comps (``/api/peers``, ``/api/comps``, ``/api/comps.csv``) choose peers through the
service's retrieval; this module only serialises the result (JSON or CSV).
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date
from typing import Annotated, Any

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from comps.config import load_settings
from comps.finance import listing_value, round_places
from comps.models import Finding, Metrics, MetricValue, Observation, Severity, ShareClass
from comps.service import (
    CompanyView,
    CompsResult,
    PeersResult,
    Snapshot,
    UnknownExclude,
    UnknownTarget,
    build_comps,
    build_snapshot,
    dataset_overview,
    find_peers,
    limitations,
    list_companies,
    list_findings,
)

CURRENCY = "USD"  # ingestion normalizes every value to USD (it requires an fx_rates.json with base USD)
# Contract names (docs/API.md) are currency-neutral; internal names still carry "usd". This adapter maps them.
_METRIC_NAMES = {"market_cap_usd_m": "market_cap_m", "enterprise_value_usd_m": "enterprise_value_m"}


def _metric_name(name: str) -> str:
    return _METRIC_NAMES.get(name, name)


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def finding_json(f: Finding) -> dict[str, Any]:
    return {
        "code": f.code,
        "severity": f.severity,
        "message": f.message,
        "fields": list(f.fields),
        "affects": [_metric_name(a) for a in f.affects],
        "source": f.source,
        "record_ids": list(f.record_ids),
        "entity_keys": list(f.entity_keys),
    }


def metric_json(m: MetricValue) -> dict[str, Any]:
    return {**asdict(m), "missing_inputs": list(m.missing_inputs)}


def metrics_json(m: Metrics) -> dict[str, Any]:
    return {_metric_name(name): metric_json(getattr(m, name)) for name in m.__dataclass_fields__}


def observation_json(o: Observation) -> dict[str, Any]:
    return {
        "record_id": o.record_id,
        "price_date": _iso(o.price_date),
        "original": dict(o.original),
        "normalized": asdict(o.usd),
        "conversion": asdict(o.conversion),
    }


def summary_json(c: CompanyView) -> dict[str, Any]:
    e = c.entity
    return {
        "key": e.key,
        "ticker": e.ticker,
        "country": e.country,
        "name": e.name,
        "sector": e.sector,
        "industry": e.industry,
        "sub_industry": e.sub_industry,
        "latest_price_date": _iso(e.latest.price_date),
        "share_class_keys": list(e.share_class_keys),
        "finding_counts": c.finding_counts,
    }


def share_class_json(c: ShareClass) -> dict[str, Any]:
    e = c.entity
    value, missing = listing_value(e.latest)
    return {
        "key": e.key,
        "ticker": e.ticker,
        "name": e.name,
        "record_id": e.latest.record_id,
        "price_currency": e.latest.original.get("price_currency"),
        "price": e.latest.usd.price,
        "shares_outstanding": e.latest.shares_outstanding,
        "market_value_m": value,
        "missing_inputs": list(missing),
        "counted": c.counted,
    }


def detail_json(c: CompanyView) -> dict[str, Any]:
    e = c.entity
    return {
        **summary_json(c),
        "currency": CURRENCY,
        "description": e.description,
        "fiscal_year_end": e.fiscal_year_end,
        "aliases": list(e.aliases),
        "record_ids": list(e.record_ids),
        "share_classes": [share_class_json(sc) for sc in e.classes],
        "latest": observation_json(e.latest),
        "observations": [observation_json(o) for o in e.observations],
        "metrics": metrics_json(c.metrics),
        "findings": [finding_json(f) for f in c.findings],
    }


def evidence_json(r: PeersResult, i: int) -> dict[str, Any]:
    ev = r.peers[i].evidence
    return {
        "similarity": ev.similarity,
        "classification": dict(ev.classification),
        "country_match": ev.country_match,
        "revenue_ratio": ev.revenue_ratio,
    }


def _selection_json(r: PeersResult) -> dict[str, Any]:
    return {
        "requested_k": r.selection.requested_k,
        "returned_k": len(r.peers),
        "skipped": [
            {
                "entity": summary_json(sv.company),
                "reason": sv.skip.reason,
                "detail": sv.skip.detail,
                "similarity": None if sv.skip.similarity is None else round_places(sv.skip.similarity, 4),
                "duplicate_of": sv.skip.duplicate_of,
            }
            for sv in r.skipped
        ],
        "note": r.selection.note,
    }


def peers_json(s: Snapshot, r: PeersResult) -> dict[str, Any]:
    return {
        "dataset_version": s.dataset.version,
        "target": summary_json(r.target),
        **_selection_json(r),
        "peers": [
            {"rank": p.rank, "entity": summary_json(p.company), "evidence": evidence_json(r, i)}
            for i, p in enumerate(r.peers)
        ],
    }


def stat_json(stat: Any) -> dict[str, Any]:
    return asdict(stat)


def comps_json(s: Snapshot, c: CompsResult) -> dict[str, Any]:
    r = c.peers
    return {
        "dataset_version": s.dataset.version,
        "currency": CURRENCY,
        "target": {
            "entity": summary_json(r.target),
            "metrics": metrics_json(r.target.metrics),
            "findings": [finding_json(f) for f in r.target.findings],
        },
        **_selection_json(r),
        "peers": [
            {
                "rank": p.rank,
                "entity": summary_json(p.company),
                "metrics": metrics_json(p.company.metrics),
                "findings": [finding_json(f) for f in p.company.findings],
                "evidence": {**evidence_json(r, i), "limitations": list(limitations(p.company))},
            }
            for i, p in enumerate(r.peers)
        ],
        "summary": {name: stat_json(getattr(c.summary, name)) for name in ("ev_revenue", "ev_ebitda", "pe")},
    }


_MULTIPLES = ("ev_revenue", "ev_ebitda", "pe")


def comps_csv(c: CompsResult) -> str:
    """The CSV layout in docs/API.md: target, peers, then mean/median/high/low and n rows."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(
        ["Row", "Rank", "Key", "Name", "Similarity", f"Market cap ({CURRENCY} m)", f"EV ({CURRENCY} m)"]
        + ["EV/Revenue", "EV/EBITDA", "P/E"]
    )

    def metrics(v: CompanyView) -> list[str]:
        m = v.metrics
        values = [m.market_cap_usd_m, m.enterprise_value_usd_m, m.ev_revenue, m.ev_ebitda, m.pe]
        return [x.display or "" for x in values]

    r = c.peers
    t = r.target
    w.writerow(["target", "", t.entity.key, t.entity.name or "", "", *metrics(t)])
    for p in r.peers:
        w.writerow(
            ["peer", p.rank, p.company.entity.key, p.company.entity.name or "", f"{p.evidence.similarity:.4f}"]
            + metrics(p.company)
        )
    stats = [getattr(c.summary, name) for name in _MULTIPLES]
    for row in ("mean", "median", "high", "low"):
        w.writerow([row, "", "", "", "", "", "", *[getattr(st.display, row) or "" for st in stats]])
    w.writerow(["n", "", "", "", "", "", "", *[str(st.n) for st in stats]])
    return out.getvalue()


_ERROR_BODY = "Body: `{ error: { code, message, details } }`."
_NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": f"Not found. {_ERROR_BODY}"}}
_INVALID: dict[int | str, dict[str, Any]] = {422: {"description": f"Invalid query parameters. {_ERROR_BODY}"}}


def _error(status: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status, content=body)


def create_app(snapshot_factory: Callable[[], Snapshot] | None = None) -> FastAPI:
    """Build the app. By default the snapshot is loaded from ``DATA_DIR`` at start-up."""
    factory = snapshot_factory or (lambda: build_snapshot(load_settings()))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.snapshot = factory()  # a DatasetError here stops start-up with a clear message
        yield

    app = FastAPI(
        title="Comps service",
        version="0.1.0",
        description=(
            "Read-only access to the ingested dataset. Company identity is the key `COUNTRY:TICKER`. "
            "Similarity search is `GET /api/peers`; the comps table is `GET /api/comps` (JSON) and "
            "`GET /api/comps.csv`. "
            "The full contract is in `docs/API.md`."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(StarletteHTTPException)
    def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "invalid_request"
        message = str(exc.detail) if exc.status_code != 404 or exc.detail != "Not Found" else "Not found."
        return _error(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "invalid_request", "Invalid request parameters.", {"errors": exc.errors()})

    def snap(request: Request) -> Snapshot:
        snapshot: Snapshot = request.app.state.snapshot
        return snapshot

    @app.get(
        "/api/health",
        tags=["service"],
        summary="Service health",
        description="Liveness check, with the dataset version and the number of companies and records loaded.",
    )
    def health(request: Request) -> dict[str, Any]:
        s = snap(request)
        return {
            "status": "ok",
            "dataset_version": s.dataset.version,
            "currency": CURRENCY,
            "entities": len(s.companies),
            "records": s.dataset.record_count,
            "reference_date": _iso(s.dataset.reference_date),
        }

    @app.get(
        "/api/companies",
        tags=["companies"],
        summary="Find companies by key, ticker or name (text matching)",
        description=(
            "Text matching, **not** similarity search: it never returns peers or similar companies. "
            "With `q`, each company is matched by its best rule, ignoring case: `key` (`q` equals "
            "`COUNTRY:TICKER`), `ticker`, `name_exact` (current or old name) or `name_partial` "
            "(substring of a current or old name). Results are sorted by match type, then key. "
            "Every match is counted in `total` and paged by `limit`/`offset`; the caller chooses one. "
            "Without `q` it lists all companies. Share classes of one issuer are one company: any class's "
            "key, ticker or name matches it, and `matched_key` names the class when it is not the shown key. "
            "Use `GET /api/companies/{key}` for one company's full details."
        ),
        responses=_INVALID,
    )
    def companies(
        request: Request,
        q: Annotated[
            str | None, Query(description="Key, ticker, or full or partial company name.", examples=["IROV"])
        ] = None,
        sector: Annotated[
            str | None, Query(description="Only companies in this sector (whole name, ignoring case).")
        ] = None,
        has_findings: Annotated[
            Severity | None, Query(description="Only companies with a finding of this severity.")
        ] = None,
        limit: Annotated[int, Query(ge=1, le=200, description="Page size.")] = 20,
        offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    ) -> dict[str, Any]:
        s = snap(request)
        total, page = list_companies(s, q, sector, has_findings, limit, offset)
        return {
            "dataset_version": s.dataset.version,
            "total": total,
            "items": [{**summary_json(h.company), "match": h.match, "matched_key": h.matched_key} for h in page],
        }

    @app.get(
        "/api/companies/{key}",
        tags=["companies"],
        summary="Get one company by its exact key",
        description=(
            "Exact lookup by the company key `COUNTRY:TICKER`, e.g. `GB:ZRQA`, ignoring case (`gb:zrqa` works; "
            "the response carries the canonical key). A bare ticker (`IROV`) "
            "or a name is not a key and returns 404: find the key with `GET /api/companies?q=` first. "
            "A share-class key resolves to its issuer, and the response carries the issuer's shown key. "
            "Returns the company's details, observation history, metrics and findings."
        ),
        responses=_NOT_FOUND,
    )
    def company(
        request: Request,
        key: Annotated[str, Path(description="Company key `COUNTRY:TICKER`.", examples=["GB:ZRQA"])],
    ) -> Any:
        s = snap(request)  # read the snapshot once, so the company and the version always agree
        c = s.resolve(key, ignore_case=True)
        if c is None:
            return _error(404, "not_found", f"No company with key {key!r}.")
        return {"dataset_version": s.dataset.version, **detail_json(c)}

    @app.get(
        "/api/dataset",
        tags=["dataset"],
        summary="Dataset overview",
        description=(
            "Source files and their hashes, record and company counts, and finding counts by severity and code."
        ),
    )
    def dataset(request: Request) -> dict[str, Any]:
        s = snap(request)
        o = dataset_overview(s)
        return {
            "dataset_version": s.dataset.version,
            "currency": CURRENCY,
            "fx": {"base": CURRENCY},  # ingestion accepts only base USD
            "reference_date": _iso(s.dataset.reference_date),
            "source": {
                "data_dir": str(s.data_dir),
                "files": [{"name": f.name, "sha256": f.sha256} for f in s.dataset.files],
            },
            "counts": {"records": o.records, "entities": o.entities},
            "findings_by_severity": o.by_severity,
            "findings_by_code": [
                {"code": code, "severity": sev, "source": src, "count": n} for code, sev, src, n in o.by_code
            ],
        }

    @app.get(
        "/api/dataset/findings",
        tags=["dataset"],
        summary="List data-quality findings",
        description="Findings raised during ingestion, quality checks and finance, with optional filters.",
        responses=_INVALID,
    )
    def findings(
        request: Request,
        severity: Annotated[Severity | None, Query(description="Only findings of this severity.")] = None,
        code: Annotated[str | None, Query(description="Only findings with this code (exact).")] = None,
        entity: Annotated[
            str | None,
            Query(
                description="Only this company's own findings (exact, case-sensitive key; a share-class key "
                "resolves to its issuer; unknown key: no results)."
            ),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=500, description="Page size.")] = 50,
        offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    ) -> dict[str, Any]:
        s = snap(request)
        total, items = list_findings(s, severity, code, entity, limit, offset)
        return {"dataset_version": s.dataset.version, "total": total, "items": [finding_json(f) for f in items]}

    def _run(request: Request, target: str, k: int, exclude: list[str], fn: Callable[..., Any]) -> Any:
        s = snap(request)
        try:
            return s, fn(s, target, k, exclude)
        except UnknownTarget:
            return s, _error(404, "not_found", f"No company with key {target!r}.")
        except UnknownExclude as exc:
            return s, _error(422, "invalid_request", str(exc), {"unknown_keys": exc.keys})

    _SELECTION = (
        "Candidates are ranked by **description similarity** of the descriptions; size, geography and "
        "classification are evidence only, never ranking inputs, and valuation multiples are never used. "
        "The ranking is walked until `k` peers are chosen, skipping (with a reason) analyst exclusions, "
        "near-duplicates of the target and near-duplicates of a peer already chosen. Companies without a "
        "usable description are never ranked. If the ranking runs out, fewer peers are returned with a `note`."
    )

    @app.get(
        "/api/peers",
        tags=["peers"],
        summary="Find similar companies (peers) for a target",
        description="Similarity search: the `k` companies most similar to the target, each with evidence for why "
        "it was chosen, and every skipped candidate with its reason. No metrics. " + _SELECTION,
        responses={**_NOT_FOUND, **_INVALID},
    )
    def peers(
        request: Request,
        target: Annotated[
            str, Query(description="Company key `COUNTRY:TICKER` (exact case; share-class keys resolve).")
        ],
        k: Annotated[int, Query(ge=1, le=50, description="Number of peers requested.")] = 10,
        exclude: Annotated[str | None, Query(description="Comma-separated company keys the analyst removed.")] = None,
    ) -> Any:
        s, result = _run(request, target, k, (exclude or "").split(","), find_peers)
        return result if isinstance(result, JSONResponse) else peers_json(s, result)

    @app.get(
        "/api/comps",
        tags=["comps"],
        summary="Build the comps table for a target",
        description="The peers chosen exactly as `GET /api/peers` chooses them, with every company's market cap, "
        "EV, EV/Revenue, EV/EBITDA and P/E, and peer-only summary statistics (mean, median, high, low). "
        "`target` must be a key: resolve free text with `GET /api/companies?q=` first. " + _SELECTION,
        responses={**_NOT_FOUND, **_INVALID},
    )
    def comps(
        request: Request,
        target: Annotated[
            str, Query(description="Company key `COUNTRY:TICKER` (exact case; share-class keys resolve).")
        ],
        k: Annotated[int, Query(ge=1, le=50, description="Number of peers requested.")] = 10,
        exclude: Annotated[str | None, Query(description="Comma-separated company keys the analyst removed.")] = None,
    ) -> Any:
        s, result = _run(request, target, k, (exclude or "").split(","), build_comps)
        return result if isinstance(result, JSONResponse) else comps_json(s, result)

    @app.get(
        "/api/comps.csv",
        tags=["comps"],
        summary="Download the comps table as CSV",
        description="Same parameters and errors as `GET /api/comps`. Rows: the target, the peers in rank order, "
        "then mean, median, high, low and n for the three multiples. Values are the display strings "
        "(`NM` for not meaningful, blank for missing).",
        responses={**_NOT_FOUND, **_INVALID},
        response_class=Response,
    )
    def comps_csv_endpoint(
        request: Request,
        target: Annotated[
            str, Query(description="Company key `COUNTRY:TICKER` (exact case; share-class keys resolve).")
        ],
        k: Annotated[int, Query(ge=1, le=50, description="Number of peers requested.")] = 10,
        exclude: Annotated[str | None, Query(description="Comma-separated company keys the analyst removed.")] = None,
    ) -> Any:
        _, result = _run(request, target, k, (exclude or "").split(","), build_comps)
        if isinstance(result, JSONResponse):
            return result
        filename = f"comps_{result.peers.target.entity.key.replace(':', '_')}.csv"
        return Response(
            content=comps_csv(result),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


app = create_app()

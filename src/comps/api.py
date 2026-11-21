"""FastAPI adapter for the read-only endpoints in docs/API.md.

Handlers only parse parameters, call the service and serialise. There's no business logic here.
Handlers are plain ``def``, so FastAPI runs them in its threadpool, and each request reads the
same immutable snapshot.

Not served yet: ``/api/comps``, ``/api/comps.csv`` and ``/api/ingest/*``. Those paths return
404 in the contract's error shape.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date
from typing import Annotated, Any

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from comps.config import load_settings
from comps.models import Finding, Metrics, MetricValue, Observation, Severity
from comps.service import CompanyView, Snapshot, build_snapshot, dataset_overview, list_companies, list_findings


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def finding_json(f: Finding) -> dict[str, Any]:
    return {
        "code": f.code,
        "severity": f.severity,
        "message": f.message,
        "fields": list(f.fields),
        "affects": list(f.affects),
        "source": f.source,
        "record_ids": list(f.record_ids),
        "entity_keys": list(f.entity_keys),
    }


def metric_json(m: MetricValue) -> dict[str, Any]:
    return {**asdict(m), "missing_inputs": list(m.missing_inputs)}


def metrics_json(m: Metrics) -> dict[str, Any]:
    return {name: metric_json(getattr(m, name)) for name in m.__dataclass_fields__}


def observation_json(o: Observation) -> dict[str, Any]:
    return {
        "record_id": o.record_id,
        "origin": o.origin,
        "price_date": _iso(o.price_date),
        "original": dict(o.original),
        "usd": asdict(o.usd),
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
        "finding_counts": c.finding_counts,
    }


def detail_json(c: CompanyView) -> dict[str, Any]:
    e = c.entity
    return {
        **summary_json(c),
        "description": e.description,
        "fiscal_year_end": e.fiscal_year_end,
        "aliases": list(e.aliases),
        "record_ids": list(e.record_ids),
        "latest": observation_json(e.latest),
        "observations": [observation_json(o) for o in e.observations],
        "metrics": metrics_json(c.metrics),
        "findings": [finding_json(f) for f in c.findings],
    }


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
            "Similarity search (peers) and comps tables are not served yet. "
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
            "Without `q` it lists all companies. "
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
            "items": [{**summary_json(c), "match": m} for c, m in page],
        }

    @app.get(
        "/api/companies/{key}",
        tags=["companies"],
        summary="Get one company by its exact key",
        description=(
            "Exact lookup by the company key `COUNTRY:TICKER`, e.g. `GB:IROV`. Case-sensitive for now: write "
            "the key as shown in results (`gb:irov` returns 404). A bare ticker (`IROV`) "
            "or a name is not a key and returns 404: find the key with `GET /api/companies?q=` first. "
            "Returns the company's details, observation history, metrics and findings."
        ),
        responses=_NOT_FOUND,
    )
    def company(
        request: Request,
        key: Annotated[str, Path(description="Company key `COUNTRY:TICKER`.", examples=["GB:IROV"])],
    ) -> Any:
        s = snap(request)  # read the snapshot once, so the company and the version always agree
        c = s.companies.get(key)
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
            "reference_date": _iso(s.dataset.reference_date),
            "source": {
                "data_dir": str(s.data_dir),
                "files": [{"name": f.name, "sha256": f.sha256} for f in s.dataset.files],
            },
            "counts": {"records": o.records, "entities": o.entities, "manual_additions": o.manual_additions},
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
            Query(description="Only this company's own findings (exact, case-sensitive key; unknown key: no results)."),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=500, description="Page size.")] = 50,
        offset: Annotated[int, Query(ge=0, description="Number of results to skip.")] = 0,
    ) -> dict[str, Any]:
        s = snap(request)
        total, items = list_findings(s, severity, code, entity, limit, offset)
        return {"dataset_version": s.dataset.version, "total": total, "items": [finding_json(f) for f in items]}

    return app


app = create_app()

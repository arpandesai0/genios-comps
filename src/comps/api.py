"""FastAPI adapter for the read-only endpoints in docs/API.md.

Handlers only parse parameters, call the service and serialise. There's no business logic here.
Handlers are plain ``def``, so FastAPI runs them in its threadpool, and each request reads the
same immutable snapshot.

Not served yet: ``/api/comps``, ``/api/comps.csv`` and ``/api/ingest/*``. Those paths return
404 in the contract's error shape.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from comps.config import load_settings
from comps.models import SEVERITIES, Finding, Metrics, MetricValue, Observation, Severity
from comps.service import CompanyView, Snapshot, build_snapshot, search


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

    app = FastAPI(title="Comps service", version="0.1.0", lifespan=lifespan)

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

    @app.get("/api/health")
    def health(request: Request) -> dict[str, Any]:
        s = snap(request)
        return {
            "status": "ok",
            "dataset_version": s.dataset.version,
            "entities": len(s.companies),
            "records": s.dataset.record_count,
            "reference_date": _iso(s.dataset.reference_date),
        }

    @app.get("/api/companies")
    def companies(
        request: Request,
        q: str | None = None,
        sector: str | None = None,
        has_findings: Severity | None = None,
        limit: int = Query(20, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        s = snap(request)
        rows = search(s, q)
        if sector:
            rows = [(c, m) for c, m in rows if (c.entity.sector or "").casefold() == sector.casefold()]
        if has_findings:
            rows = [(c, m) for c, m in rows if c.finding_counts[has_findings] > 0]
        page = rows[offset : offset + limit]
        return {
            "dataset_version": s.dataset.version,
            "total": len(rows),
            "items": [{**summary_json(c), "match": m} for c, m in page],
        }

    @app.get("/api/companies/{key}")
    def company(request: Request, key: str) -> Any:
        c = snap(request).companies.get(key)
        if c is None:
            return _error(404, "not_found", f"No company with key {key!r}.")
        return {"dataset_version": snap(request).dataset.version, **detail_json(c)}

    @app.get("/api/dataset")
    def dataset(request: Request) -> dict[str, Any]:
        s = snap(request)
        by_severity = Counter(f.severity for f in s.findings)
        by_code = Counter((f.code, f.severity, f.source) for f in s.findings)
        return {
            "dataset_version": s.dataset.version,
            "reference_date": _iso(s.dataset.reference_date),
            "source": {
                "data_dir": str(s.data_dir),
                "files": [{"name": f.name, "sha256": f.sha256} for f in s.dataset.files],
            },
            "counts": {
                "records": s.dataset.record_count,
                "entities": len(s.companies),
                "manual_additions": int(s.dataset.metadata.get("manual_records", 0)),
            },
            "findings_by_severity": {sev: by_severity.get(sev, 0) for sev in SEVERITIES},
            "findings_by_code": [
                {"code": code, "severity": sev, "source": src, "count": n}
                for (code, sev, src), n in sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0][0]))
            ],
        }

    @app.get("/api/dataset/findings")
    def findings(
        request: Request,
        severity: Severity | None = None,
        code: str | None = None,
        entity: str | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        s = snap(request)
        items = [
            f
            for f in s.findings
            if (severity is None or f.severity == severity)
            and (code is None or f.code == code)
            and (entity is None or entity in f.entity_keys)
        ]
        return {
            "dataset_version": s.dataset.version,
            "total": len(items),
            "items": [finding_json(f) for f in items[offset : offset + limit]],
        }

    return app


app = create_app()

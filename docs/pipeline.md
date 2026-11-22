# Pipeline

How a request for a comps table flows through the service, stage by stage, and what exists today. **This is a living document:** update it in the same PR whenever a stage is added or changed.

## Stages

```
DATA_DIR/companies.json ─┐
DATA_DIR/fx_rates.json  ─┴─► 1. Ingestion ─► 2. Quality ─► Dataset ─► 3. Resolve ─► 4. Retrieve ─► 5. Finance ─► 6. Service ─► 7. API ─► 8. UI
```

Each stage talks to the next only through plain data types from `src/comps/models.py`. No stage reaches into another's internals, so a stage can be changed, or swapped in the case of retrievers, without touching the rest.

| # | Stage | Input → output | Status | Code | Docs |
|---|---|---|---|---|---|
| 1 | **Ingestion**: validate, normalize to USD, group by `COUNTRY:TICKER`, build time series | JSON files → `Dataset` of `Entity` + `Observation` + `Finding` | ✅ done | `ingest.py` | [ingestion.md](ingestion.md) |
| 2 | **Quality**: checks across companies (same issuer, shared names, freshness) | entities → extra findings | ✅ done | `quality.py` | [ingestion.md § 6](ingestion.md#6-checks-across-companies-qualitypy) |
| 3 | **Resolve**: turn an analyst's query (key, ticker, exact name or alias, partial name) into the matching companies, best match first; the analyst always chooses the target, and comps take a key | query → entity key(s) with match type | ✅ done | `service.search`, served by `GET /api/companies` | [API.md](API.md#get-apicompanies) |
| 4 | **Retrieve**: pick `k` peers by TF-IDF description similarity and explain each one | target + dataset → ranked peers with evidence | ⏳ planned | `retrieval/` | |
| 5 | **Finance**: glossary metrics (ok, NM or missing), rounding, peer summary stats | `Observation` → `Metrics`; peers' `Metrics` → `Summary` | ✅ done | `finance.py` | [finance.md](finance.md) |
| 6 | **Service**: build an immutable snapshot once at start-up, assemble comps responses | dataset → snapshot; request → comps response | 🟡 snapshot built at start-up and read-only queries (including stage 3's `search`); no comps yet | `service.py` | |
| 7 | **API**: FastAPI adapter, JSON and CSV, no business logic | HTTP ↔ service | 🟡 read-only endpoints (health, dataset, findings, companies); comps return 404 | `api.py` | [API.md](API.md) |
| 8 | **UI**: Next.js + shadcn/ui compare view and data-health view | HTTP only | 🟡 Data view wired to the real API (`make start`); Compare hidden until served | `web/` | |

## What each hand-off carries

| From → to | Data type | What the receiver can rely on |
|---|---|---|
| Ingestion → everything | `Dataset` | Immutable. Values are in USD, and `None` means unavailable, never zero. Each entity's `latest` is the only observation used for comps. Every doubtful value has a finding. `version` identifies the input files, but not settings such as `STALE_AFTER_DAYS`. |
| Dataset → Finance | `Observation` | `usd.*` in USD millions, `price` in USD per share, `shares_outstanding` in millions. `conversion` says which factor failed when a value is `None`. |
| Finance → Service | `Metrics`, `Summary`, findings | Every value is `ok`, `nm` or `missing`, with `raw` (unrounded apart from cleaning float noise at 9 dp) and `display` (final, 1 dp). Stats are computed over exactly the rows passed in. |

## Rules that hold across the whole pipeline

- **Serve no data rather than incorrect data.** A blank value, or a complete explanation, beats a guessed or partial one.
- **Never silently change data.** No imputing, rescaling, zero-filling or reclassifying. Every such case becomes a finding with a code, severity, fields and affected outputs.
- **Model-derived signals are labelled.** A finding produced by a model or heuristic has `source: "derived"` and is never presented as fact.
- **Valuation multiples never choose peers.** Retrieval doesn't see finance output, and finance doesn't know how peers were picked.
- **Display values are final.** Finance rounds once, and the API, CSV and UI never round again.
- **Reproducible.** The same input files give the same dataset version and the same results.

## Change history

| PR | Change to the pipeline |
|---|---|
| #1 | Scaffold, working rules, and the draft HTTP contract ([API.md](API.md)). |
| #2 | Stages 1–2: ingestion and quality checks. |
| #3 | Tooling: lint, type checks, tests with coverage, CI. |
| #4 | Process: the review loop, where agents never merge. |
| #5 | Stage 8 (partial): Compare and Data views built against synthetic mocks of [API.md](API.md). |
| #6 | Stage 5: finance (metrics, statuses, rounding, summary statistics). |
| #7 | Pipeline, ingestion and finance docs. |
| #8 | API contract: precise wording for `raw` and NM versus missing. |
| #9 | Accuracy fixes: `missing_inputs` names every cause; the `text_updated` message says which value is used. |
| #10 | Stages 6–7 (partial): read-only API on an immutable snapshot; `make start DIR=...` runs API + web with docker compose. |
| #11 | Tests: end-to-end planted-defects acceptance test for ingestion and finance (no behaviour change). |
| #13 | Stage 2: remove the `REFERENCE_DATE` setting and the `future_price_date` check; staleness is always measured from the latest `price_date` in the data. |
| this PR | Stage 3: marked done as it is. Resolution is `service.search` behind `GET /api/companies`; the separate `resolve.py` module is dropped from the plan (docs only, no behaviour change). |

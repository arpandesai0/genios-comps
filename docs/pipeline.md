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
| 2 | **Issuers and quality**: merge share classes into issuers (disjoint-set union), then checks across companies (shared names, freshness) | listings → issuers + extra findings | ✅ done | `issuers.py`, `quality.py` | [ingestion.md § 6](ingestion.md#6-merge-share-classes-issuerspy), [§ 7](ingestion.md#7-checks-across-companies-qualitypy) |
| 3 | **Resolve**: turn an analyst's query (key, ticker, exact name or alias, partial name) into the matching companies, best match first; the analyst always chooses the target, and comps take a key | query → entity key(s) with match type | ✅ done | `service.search`, served by `GET /api/companies` | [API.md](API.md#get-apicompanies) |
| 4 | **Retrieve**: pick `k` peers by description similarity (local MiniLM embeddings) and explain each one | target + dataset → ranked peers with evidence | ✅ done (MiniLM on business descriptions, experiment 13; nDCG@10 on the independent fixture 0.769 dev / 0.761 held-out, against TF-IDF's 0.459 / 0.428) | `retrieval/`, `eval/` | [retrieval.md](retrieval.md), [eval.md](eval.md) |
| 5 | **Finance**: glossary metrics (ok, NM or missing), rounding, peer summary stats | `Observation` → `Metrics`; peers' `Metrics` → `Summary` | ✅ done | `finance.py` | [finance.md](finance.md) |
| 6 | **Service**: build an immutable snapshot once at start-up, assemble comps responses | dataset → snapshot; request → comps response | ✅ snapshot (with the retrieval index) built at start-up; read-only queries, peers and comps | `service.py` | |
| 7 | **API**: FastAPI adapter, JSON and CSV, no business logic | HTTP ↔ service | ✅ read-only endpoints, `/api/peers`, `/api/comps`, `/api/comps.csv` | `api.py` | [API.md](API.md) |
| 8 | **UI**: Next.js + shadcn/ui compare view and data-health view | HTTP only | 🟡 Data view wired to the real API (`make start`); Compare still on mocks until wired to the new comps contract | `web/` | |

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
| #14 | Stage 3: marked done as it is. Resolution is `service.search` behind `GET /api/companies`; the separate `resolve.py` module is dropped from the plan (docs only, no behaviour change). |
| #19 | API contract: share classes are one company, shown under the most valuable class. |
| #20 | Manual additions dropped: the input files are the whole dataset, and the snapshot is never swapped. |
| #21 | Stage 2: share classes merged into issuers with a disjoint-set union; issuer market cap summed over classes. |
| #22 | API contract: `GET /api/peers`, the final `GET /api/comps` and the CSV layout. |
| #23 | Stage 4: TF-IDF retrieval, the k-filling peer walk with near-duplicate skips, and the peers, comps and CSV endpoints. |
| #24 | Stage 4 eval: synthetic universe with graded labels, nDCG / precision / recall, first result for TF-IDF v1 ([eval.md](eval.md)). |
| #29 | Eval: append-only experiment log (`eval/experiments.jsonl`) and [eval.md](eval.md). |
| #30 | Stage 4: local sentence embeddings (MiniLM-L6, required, baked into the image) replace TF-IDF; near-duplicate threshold 0.88; responses drop `method` and `shared_terms`; black-box eval runner, independent fixtures, experiments 2–7; `make start SERVICES=`. |
| #31 | Thresholds and defaults move to a config file (`src/comps/settings.toml`). |
| #32 | UI finished against the real API (Compare served); API names match the contract; `make start` prints URLs after start-up. |
| #33 | Stage 4: rank on business descriptions (distinctive name words removed in ingestion); look-alike-names fixture; experiments 9–13. |
| #34 | Cleanup: manual-addition remnants removed; `fx_rates.json` must have base USD. |
| #35 | Hand-in docs: `DESIGN.md`, `TIMELOG.md`, README AI usage and future work. |

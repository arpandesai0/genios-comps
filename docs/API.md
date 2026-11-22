# HTTP API contract (v0 draft)

This is the contract between the Python backend and the web UI. **Status:** the read-only endpoints (`/api/health`, `/api/companies`, `/api/companies/{key}`, `/api/dataset`, `/api/dataset/findings`) are implemented. `/api/comps` and `/api/comps.csv` are not yet: they return 404, and the UI keeps using mocks for them. There are **no write endpoints**: the input files are the whole dataset (owner decision 2026-11-22), so the former `/api/ingest/*` endpoints and the `origin` and `manual_additions` fields are removed from the contract (the code and UI drop them in a follow-up PR). If a field needs to change, change this file in its own PR first. The **share-class** fields and lookup rules below (`share_class_keys`, `share_classes`, `matched_key`, class keys resolving to their issuer) are agreed but not implemented yet; until they land, every key is its own issuer, and `docs/ingestion.md` still describes the current separate-entities behaviour.

## Conventions

- Base path: `/api`. JSON in and out, except the CSV export.
- **Company key**: `COUNTRY:TICKER`, e.g. `US:NOMA`. It identifies a listing: each country is assumed to have one exchange, so the same ticker in two countries is two different companies. Record `id`s are internal provenance only. URL-encode the key in paths (`US%3ANOMA`).
- **Issuers and share classes**: listings of one issuer (share classes, e.g. `US:ABC.A` and `US:ABC.B`) are merged into **one company**, with one row in every list and table. The company is shown under the key of its most valuable class (price × shares; ties go to the alphabetically first key), and `share_class_keys` lists every class. The merge and market-cap rules are recorded in AGENTS.md §4 (2026-11-22); the README gains a *Share classes* section when they are implemented.
  - **Resolving class keys.** Every parameter that takes a key accepts any class key and resolves it to the issuer: `GET /api/companies/{key}` (case-insensitive), and `/api/comps` `target` and `exclude` and `/api/dataset/findings?entity=` (exact case, like any key). Responses always carry the issuer's shown key. Excluding any class key excludes the whole issuer; several class keys of one issuer in `exclude` count as one exclusion; a class key of the target in `exclude` is ignored.
  - **`Finding.entity_keys`** names the shown key of each issuer the finding is about. A finding about one specific class (e.g. its price is missing) also names that class's key and its record in `record_ids`.
- Money values are in **millions of the dataset currency**, given as `currency` in every response that carries money. The dataset currency is **USD** whenever `fx_rates.json` provides a USD rate (always true when its `base` is USD). If the base is another currency and no valid USD rate is given, it is the base currency, and a `currency_not_usd` finding (severity `warning`, dataset-level: empty `entity_keys`, listed only by `/api/dataset` and `/api/dataset/findings`) says so. Ingestion decides the currency; no other stage converts anything. The conversion rule is defined in README Assumption 12 and, once implemented, in `docs/ingestion.md`.
- Metric names are currency-neutral everywhere, including `Finding.affects`: `market_cap_m`, `enterprise_value_m`, `ev_revenue`, `ev_ebitda`, `pe`.
- Multiples (EV/Revenue, EV/EBITDA, P/E) and the revenue ratio are plain ratios. They are the same in any currency.
- The backend rounds every value for display (one decimal place, as the glossary requires). The UI shows `display` as given and **never re-rounds**. `raw` is the value before display rounding (only float noise below 9 decimal places is cleaned), for calculation traces only.
- Errors look like `{"error": {"code": "not_found" | "invalid_request", "message": "...", "details": {}}}` and use HTTP status codes 404 or 422.
- Every response that depends on data includes `dataset_version`, a short hash of the input files.

## Shared types

```ts
type Severity = "error" | "limitation" | "warning" | "info";

interface Finding {
  code: string;               // e.g. "missing_value", "share_classes_merged", "stale_price"
  severity: Severity;
  message: string;            // human-readable
  fields: string[];           // affected record fields
  affects: string[];          // affected metrics/capabilities, e.g. ["ev_ebitda"], ["retrieval"]
  source: "validation" | "derived"; // "derived" = produced by a model/heuristic, not a fact
  record_ids: string[];
  entity_keys: string[];
}

type MetricStatus = "ok" | "nm" | "missing";   // NM = zero/negative denominator with all inputs present; missing = an input is unavailable (wins over NM), or the result overflowed (see non_finite_result)

interface MetricValue {
  status: MetricStatus;
  value: number | null;       // rounded to 1 dp; null unless status = "ok"
  display: string | null;     // "12.3x", "4,512.3", "NM", or null (show blank)
  raw: number | null;         // before display rounding (float noise cleaned at 9 dp)
  missing_inputs: string[];   // e.g. ["ebitda"] when status = "missing"; empty on overflow (a non_finite_result finding explains it). Always root record field names (e.g. "price", "price_currency"), never per-class names; when a share class other than the shown one causes it, that class's ShareClass.missing_inputs and a finding naming its key say which
}

interface Metrics {
  market_cap_m: MetricValue;            // millions of the dataset currency; sum over the issuer's counted share classes
  enterprise_value_m: MetricValue;      // millions of the dataset currency
  ev_revenue: MetricValue;
  ev_ebitda: MetricValue;
  pe: MetricValue;
}

interface EntitySummary {
  key: string;                // "US:NOMA"; for a merged issuer, its shown key
  share_class_keys: string[]; // every listing of this issuer, ["US:NOMA"] for most companies. Order: the shown key first, then by market value descending (classes without one last), ties by key alphabetically
  ticker: string;
  country: string;
  name: string;
  sector: string | null;
  industry: string | null;
  sub_industry: string | null;
  latest_price_date: string | null;   // ISO date
  finding_counts: Record<Severity, number>;
}

interface Observation {
  record_id: string;
  price_date: string | null;
  original: Record<string, unknown>;  // the record exactly as supplied
  normalized: {                        // in the dataset currency: price per share, other money values in millions; null when it can't be computed
    price: number | null;
    total_debt: number | null;
    cash: number | null;
    revenue: number | null;
    ebitda: number | null;
    net_income: number | null;
  };
  conversion: { price_fx: number | null; reporting_fx: number | null; unit_factor: number | null }; // factors into the dataset currency; null = conversion failed
}

interface ShareClass {
  key: string;
  ticker: string;
  name: string | null;
  record_id: string;                  // latest record of this class
  price_currency: string | null;      // as supplied
  price: number | null;               // per share, dataset currency
  shares_outstanding: number | null;  // millions
  market_value_m: number | null;      // price × shares, millions of the dataset currency; null if either is unusable
  missing_inputs: string[];           // root field names that make market_value_m null, as in MetricValue
  counted: boolean;                   // authoritative. false only when this class has the same price, price_currency and shares as an EARLIER class in share_classes (the same shares listed twice, counted once). A class with an unusable price or share count is always counted, so the issuer's market cap is missing rather than partial
}

interface EntityDetail extends EntitySummary {
  currency: string;                   // dataset currency of `metrics` and every `normalized` block
  description: string | null;
  fiscal_year_end: string | null;
  aliases: string[];                  // every name seen for this issuer, across its share classes
  record_ids: string[];               // every record of every share class
  share_classes: ShareClass[];        // same order as share_class_keys
  latest: Observation;                // latest observation of the shown key; the only one used for debt, cash and the financials. latest_price_date comes from it (merged classes share their latest price_date)
  observations: Observation[];        // full history of the CURRENT shown key only, oldest first. The shown key can change between dataset versions (it follows market value); `key` always says which class this is
  metrics: Metrics;                   // market cap from `share_classes`, everything else from `latest`
  findings: Finding[];
}

interface SummaryStat {
  n: number;                          // number of numeric peer values used
  n_nm: number;
  n_missing: number;
  mean: number | null; median: number | null; high: number | null; low: number | null; // rounded 1 dp
  display: { mean: string | null; median: string | null; high: string | null; low: string | null };
}
```

## Endpoints

### `GET /api/health`
Returns `{ "status": "ok", "dataset_version": string, "currency": string, "entities": number, "records": number, "reference_date": string | null }` (`reference_date` as in `/api/dataset`).

### `GET /api/companies`
Find companies by **text matching** on key, ticker or name. Used both for target search (with ambiguity) and for the data table. This is not similarity search: it never returns peers.

Query parameters: `q` (optional; case-insensitive, surrounding whitespace ignored, and a blank `q` counts as no query; matches the key `COUNTRY:TICKER`, the ticker, the current name or an old name exactly, or a substring of a current or old name; any share class's key, ticker or name matches its issuer), `sector`, `has_findings` (`error|limitation|warning|info`), `limit` (default 20, max 200), `offset`.

Returns `{ "dataset_version", "total": number, "items": (EntitySummary & { "match": "key" | "ticker" | "name_exact" | "name_partial" | null; "matched_key": string | null })[] }`. Each company (issuer) appears once, under its shown key, with its best match type over all of its share classes, and `matched_key` naming the class that matched when it is not the shown key (null otherwise, and with no query). `sector` and `has_findings` apply to the issuer: its sector (identical across merged classes) and its own findings. Items are sorted by match type (`key`, `ticker`, `name_exact`, `name_partial`), then by key. Without a query every company is listed with `match: null`. When a query matches several companies, return all of them (paged by `limit`/`offset`, with `total` giving the full count); the UI asks the analyst to choose. For example, a bare ticker listed in two countries gives two `ticker` matches.

### `GET /api/companies/{key}`
Exact lookup of one company by its key `COUNTRY:TICKER` (e.g. `GB:IROV`), ignoring case. Ignoring case applies to this endpoint only; other parameters that take a key match its case exactly (they still resolve class keys, see Conventions). The response always carries the canonical key, as in `GB:IROV`. A share-class key resolves to its issuer, so `GET /api/companies/US:ABC.B` returns the issuer with `key: "US:ABC.A"` when that is the shown key. Returns `EntityDetail`, or 404 if no company has that key. A bare ticker or a name is not a key: use `GET /api/companies?q=` to find one.

### `GET /api/comps`
Builds the comps table.

Query parameters: `target` (company key, required), `k` (number of peers requested, default 10, 1–50), `exclude` (comma-separated keys the analyst removed).

**Provisional.** Stage 4's contract PR finalises this section for the 2026-11-22 peer-selection rule (AGENTS.md §4): it will add `requested_k` and `returned_k`, a reason for each skipped candidate (target near-duplicate, near-duplicate of a chosen peer, analyst exclusion), and where the near-duplicate peer and score are reported.

To remove a peer, the UI calls the endpoint again with that key added to `exclude`. The server recomputes the summary statistics; the UI never computes them.

```ts
interface CompsResponse {
  dataset_version: string;
  currency: string;                          // dataset currency of market cap and EV
  method: { name: string; version: string };
  k: number;
  target: { entity: EntitySummary; metrics: Metrics; findings: Finding[] };
  peers: {
    rank: number;
    entity: EntitySummary;
    metrics: Metrics;
    findings: Finding[];
    evidence: {                              // why this peer was chosen (provisional shape)
      similarity: number;                    // description similarity score, 0–1; NOT a probability
      shared_terms: string[];                // description terms that drove the match
      classification: { sector: boolean; industry: boolean; sub_industry: boolean };
      country_match: boolean;
      revenue_ratio: number | null;          // peer revenue / target revenue (same currency); null if unavailable
      limitations: string[];                 // finding codes affecting this peer's metrics
    };
  }[];
  excluded: {
    entity: EntitySummary;
    reason: "near_duplicate" | "user_excluded";   // provisional; finalised in stage 4's contract PR
    detail: string;
  }[];
  summary: { ev_revenue: SummaryStat; ev_ebitda: SummaryStat; pe: SummaryStat }; // peers only
}
```

Errors: 404 for an unknown target, 422 for an invalid `k` or `exclude`.

### `GET /api/comps.csv`
Same parameters as `/api/comps`. Returns `text/csv` with the target row, the peer rows (key, name, rank, similarity, market cap, EV, EV/Revenue, EV/EBITDA, P/E using display values) and the summary rows.
The money columns are headed `Market cap (<currency> m)` and `EV (<currency> m)`, e.g. `Market cap (USD m)`. The summary rows use the same columns, with values only under the three multiples.

### `GET /api/dataset`
Data-health overview.

```ts
{
  dataset_version: string;
  currency: string;                          // dataset currency (see Conventions)
  fx: { base: string };                      // base currency as given in fx_rates.json
  reference_date: string | null;             // latest valid price_date in the data (stale-price checks measure from it); null if no record has a valid date
  source: { data_dir: string; files: { name: string; sha256: string }[] };
  counts: { records: number; entities: number };   // entities = issuers, share classes merged
  findings_by_severity: Record<Severity, number>;
  findings_by_code: { code: string; severity: Severity; source: "validation" | "derived"; count: number }[];
}
```

### `GET /api/dataset/findings`
Query parameters: `severity`, `code`, `entity` (key), `limit` (default 50, max 500), `offset`.
Returns `{ "dataset_version", "total": number, "items": Finding[] }`.

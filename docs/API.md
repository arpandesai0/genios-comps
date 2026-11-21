# HTTP API contract (v0 draft)

This is the contract between the Python backend and the web UI. **Status:** the read-only endpoints (`/api/health`, `/api/companies`, `/api/companies/{key}`, `/api/dataset`, `/api/dataset/findings`) are implemented. `/api/comps`, `/api/comps.csv` and `/api/ingest/*` are not yet: they return 404, and the UI keeps using mocks for them. If a field needs to change, change this file in its own PR first.

## Conventions

- Base path: `/api`. JSON in and out, except the CSV export.
- **Company key**: `COUNTRY:TICKER`, e.g. `US:NOMA`. This is the company's identity. Record `id`s are internal provenance only. URL-encode the key in paths (`US%3ANOMA`).
- Money values are in **USD millions**. Multiples are plain ratios.
- The backend rounds every value for display (one decimal place, as the glossary requires). The UI shows `display` as given and **never re-rounds**. `raw` is the value before display rounding (only float noise below 9 decimal places is cleaned), for calculation traces only.
- Errors look like `{"error": {"code": "not_found" | "invalid_request" | "rejected", "message": "...", "details": {}}}` and use HTTP status codes 404, 422 or 409.
- Every response that depends on data includes `dataset_version`, a short hash of the input files plus any in-memory additions.

## Shared types

```ts
type Severity = "error" | "limitation" | "warning" | "info";

interface Finding {
  code: string;               // e.g. "missing_value", "possible_same_issuer", "stale_price"
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
  missing_inputs: string[];   // e.g. ["ebitda"] when status = "missing"; empty on overflow (a non_finite_result finding explains it)
}

interface Metrics {
  market_cap_usd_m: MetricValue;
  enterprise_value_usd_m: MetricValue;
  ev_revenue: MetricValue;
  ev_ebitda: MetricValue;
  pe: MetricValue;
}

interface EntitySummary {
  key: string;                // "US:NOMA"
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
  origin: "file" | "manual";
  price_date: string | null;
  original: Record<string, unknown>;  // the record exactly as supplied
  usd: {                               // normalized; null when it can't be computed
    price: number | null;
    total_debt: number | null;
    cash: number | null;
    revenue: number | null;
    ebitda: number | null;
    net_income: number | null;
  };
  conversion: { price_fx: number | null; reporting_fx: number | null; unit_factor: number | null };
}

interface EntityDetail extends EntitySummary {
  description: string | null;
  fiscal_year_end: string | null;
  aliases: string[];                  // every name seen for this key
  record_ids: string[];
  latest: Observation;                // the only observation used in calculations
  observations: Observation[];        // full history, oldest first
  metrics: Metrics;                   // computed from `latest`
  findings: Finding[];
}

interface SummaryStat {
  n: number;                          // number of numeric peer values used
  n_nm: number;
  n_missing: number;
  mean: number | null; median: number | null; high: number | null; low: number | null; // rounded 1 dp
  display: { mean: string | null; median: string | null; high: string | null; low: string | null };
}

// A record in the original companies.json schema (all fields required; values may be null)
interface RawRecord {
  id: string; ticker: string; name: string; description: string;
  sector: string; industry: string; sub_industry: string; country: string;
  price_currency: string; reporting_currency: string; units: "millions" | "thousands";
  fiscal_year_end: string; price: number | null; price_date: string;
  shares_outstanding: number | null; total_debt: number | null; cash: number | null;
  revenue: number | null; ebitda: number | null; net_income: number | null;
}
```

## Endpoints

### `GET /api/health`
Returns `{ "status": "ok", "dataset_version": string, "entities": number, "records": number, "reference_date": string }`.

### `GET /api/companies`
Search and list companies. Used both for target search (with ambiguity) and for the data table.

Query parameters: `q` (key, ticker or name; optional), `sector`, `has_findings` (`error|limitation|warning|info`), `limit` (default 20, max 200), `offset`.

Returns `{ "dataset_version", "total": number, "items": (EntitySummary & { "match": "key" | "ticker" | "name_exact" | "name_partial" | null })[] }`. When a query matches several companies, return all of them; the UI asks the analyst to choose.

### `GET /api/companies/{key}`
Returns `EntityDetail`, or 404.

### `GET /api/comps`
Builds the comps table.

Query parameters: `target` (company key, required), `k` (number of peers, default 10, 1–50), `exclude` (comma-separated keys the analyst removed).

To remove a peer, the UI calls the endpoint again with that key added to `exclude`. The server recomputes the summary statistics; the UI never computes them.

```ts
interface CompsResponse {
  dataset_version: string;
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
      revenue_ratio: number | null;          // peer revenue / target revenue (USD); null if unavailable
      limitations: string[];                 // finding codes affecting this peer's metrics
    };
  }[];
  excluded: {
    entity: EntitySummary;
    reason: "possible_same_issuer" | "user_excluded";
    detail: string;
  }[];
  summary: { ev_revenue: SummaryStat; ev_ebitda: SummaryStat; pe: SummaryStat }; // peers only
}
```

Errors: 404 for an unknown target, 422 for an invalid `k` or `exclude`.

### `GET /api/comps.csv`
Same parameters as `/api/comps`. Returns `text/csv` with the target row, the peer rows (key, name, rank, similarity, market cap, EV, EV/Revenue, EV/EBITDA, P/E using display values) and the summary rows.

### `GET /api/dataset`
Data-health overview.

```ts
{
  dataset_version: string;
  reference_date: string;                    // date used for freshness checks
  source: { data_dir: string; files: { name: string; sha256: string }[] };
  counts: { records: number; entities: number; manual_additions: number };
  findings_by_severity: Record<Severity, number>;
  findings_by_code: { code: string; severity: Severity; source: "validation" | "derived"; count: number }[];
}
```

### `GET /api/dataset/findings`
Query parameters: `severity`, `code`, `entity` (key), `limit` (default 50, max 500), `offset`.
Returns `{ "dataset_version", "total": number, "items": Finding[] }`.

### `POST /api/ingest/preview`
Body: `RawRecord`. Runs the full ingestion pipeline against the current dataset **without saving**.

```ts
interface IngestResult {
  accepted: boolean;                         // false if a blocking error would reject it
  resolution: {
    key: string | null;
    action: "create" | "add_observation" | "update_text" | "duplicate" | "rejected";
  };
  entity: EntityDetail | null;               // the entity as it would look after saving
  findings: Finding[];                       // findings raised by this record
}
```

### `POST /api/ingest/records`
Body: `RawRecord`. Same pipeline as preview, then saves the record. Returns `IngestResult & { dataset_version: string }`, or 409 with the findings if it was rejected.

Additions are held **in memory only**: they are lost when the service restarts, and they never modify the input files.

### `GET /api/ingest/records`
Returns `{ "items": { record: RawRecord; key: string; added_at: string }[] }` for the additions made since the service started.

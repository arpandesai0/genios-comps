# HTTP API contract (v0 draft)

This is the contract between the Python backend and the web UI. **Status:** the read-only endpoints (`/api/health`, `/api/companies`, `/api/companies/{key}`, `/api/dataset`, `/api/dataset/findings`) are implemented. `/api/peers`, `/api/comps` and `/api/comps.csv` are implemented too, and the UI's Compare page uses them. There are **no write endpoints**: the input files are the whole dataset (owner decision 2026-11-22), so the former `/api/ingest/*` endpoints and the `origin` and `manual_additions` fields are removed from the contract (the code and UI drop them in a follow-up PR). If a field needs to change, change this file in its own PR first. The **share-class** fields and lookup rules (`share_class_keys`, `share_classes`, `matched_key`, class keys resolving to their issuer) are implemented for these endpoints.

## Conventions

- Base path: `/api`. JSON in and out, except the CSV export.
- **Company key**: `COUNTRY:TICKER`, e.g. `US:NOMA`. It identifies a listing: each country is assumed to have one exchange, so the same ticker in two countries is two different companies. Record `id`s are internal provenance only. URL-encode the key in paths (`US%3ANOMA`).
- **Issuers and share classes**: listings of one issuer (share classes, e.g. `US:ABC.A` and `US:ABC.B`) are merged into **one company**, with one row in every list and table. The company is shown under the key of its most valuable class (price × shares; ties go to the alphabetically first key), and `share_class_keys` lists every class. The merge and market-cap rules are recorded in AGENTS.md §4 (2026-11-22) and explained in the README (*Share classes*).
  - **Resolving class keys.** Every parameter that takes a key accepts any class key and resolves it to the issuer: `GET /api/companies/{key}` (case-insensitive), and `/api/peers` and `/api/comps` `target` and `exclude` and `/api/dataset/findings?entity=` (exact case, like any key). Responses always carry the issuer's shown key. Excluding any class key excludes the whole issuer; several class keys of one issuer in `exclude` count as one exclusion; a class key of the target in `exclude` is ignored.
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

### `GET /api/peers`
**Similarity search**: the `k` companies most similar to a target, with the reason each was chosen. This is retrieval only, with no metrics; `/api/comps` builds on the same selection.

Query parameters: `target` (company key, required; any share-class key resolves), `k` (number of peers requested, default 10, 1–50), `exclude` (comma-separated keys the analyst removed; class keys resolve to their issuer).

**How peers are chosen** (AGENTS.md §4, 2026-11-22):

- Candidates are ranked by **description similarity**. Size, geography and classification are shown as evidence and are never ranking inputs. Valuation multiples are never used. There is no similarity floor. Which model computes the similarity is a server setting and is not part of the response (see [retrieval.md](retrieval.md)).
- The ranking is walked from the top until `k` peers are chosen. A candidate is **skipped**, with a reason, when it is in `exclude` (`user_excluded`), a near-duplicate of the target (`near_duplicate_of_target`), or a near-duplicate of a peer already chosen (`near_duplicate_of_peer`; the higher-ranked one stays). When several apply, that order decides the reason. Skipped candidates never count toward `k`, and only chosen peers are checked for `near_duplicate_of_peer`.
- Two companies are **near-duplicates** when their descriptions are identical after normalizing case and whitespace, or their description similarity (unrounded) is at or above the server's near-duplicate threshold (0.88 by default). Neither can be the other's peer.
- A **usable description** is non-empty after trimming. A company without one cannot be ranked: as a candidate it is skipped with `no_description`; as the target, no peers are returned and `note` says why.
- If the ranking runs out first, fewer peers are returned and `note` says why. The list is never padded.
- Ties in similarity are ordered by key. `rank` is the position among the returned peers (1 … `returned_k`).
- `exclude`: empty items are ignored and repeats count once; a key of the target is ignored; an unknown key is a 422.

```ts
type SkipReason = "near_duplicate_of_target" | "near_duplicate_of_peer" | "user_excluded" | "no_description";

interface Evidence {                         // why this peer was chosen
  similarity: number;                        // description similarity to the target, 0–1, rounded to 4 dp; higher is closer; NOT a probability
  classification: { sector: boolean; industry: boolean; sub_industry: boolean };   // label equal to the target's (false if either is missing); evidence only
  country_match: boolean;                    // same country (false if either is the unknown "*"); evidence only
  revenue_ratio: number | null;              // peer revenue / target revenue (latest observation, dataset currency), rounded to 2 dp; may be ≤ 0 when the peer's revenue is; null if either is unavailable or the target's is ≤ 0
}

interface Skipped {
  entity: EntitySummary;
  reason: SkipReason;
  detail: string;                            // human-readable, e.g. "Near-duplicate of the target US:ABC: the descriptions are (almost) the same."
  similarity: number | null;                 // to the target (4 dp), even for near_duplicate_of_peer; null for no_description and for exclusions not met in the walk
  duplicate_of: string | null;               // the shown key it duplicates (target or chosen peer); null otherwise
}

interface PeersResponse {
  dataset_version: string;
  target: EntitySummary;
  requested_k: number;
  returned_k: number;
  peers: { rank: number; entity: EntitySummary; evidence: Evidence }[];   // rank 1 = most similar
  skipped: Skipped[];                        // in order: skips met while walking the ranking (ranking order); then every `exclude` key not met before the walk ended (by key); then every other no_description company (by key). A company appears at most once: an excluded company without a description is listed as `user_excluded`
  note: string | null;                       // non-null exactly when returned_k < requested_k (including a target with no description); display text only
}
```

Errors: 404 for an unknown `target` (exact case, like every key parameter except `GET /api/companies/{key}`); 422 for a missing `target`, a `k` that is not an integer in 1–50, or an unknown key in `exclude`.

### `GET /api/comps`
Builds the comps table: the peers chosen exactly as `/api/peers` chooses them, with every company's metrics and peer-only summary statistics. `target` must be a company key (any share-class key resolves). Free text goes through `GET /api/companies?q=` first: one match can go straight to comps; several let the analyst choose.

Query parameters: same as `/api/peers`.

To remove a peer, the UI calls the endpoint again with that key added to `exclude`. The server recomputes the summary statistics; the UI never computes them.

```ts
interface CompsResponse {
  dataset_version: string;
  currency: string;                          // dataset currency of market cap and EV
  requested_k: number;
  returned_k: number;
  target: { entity: EntitySummary; metrics: Metrics; findings: Finding[] };
  peers: {
    rank: number;
    entity: EntitySummary;
    metrics: Metrics;
    findings: Finding[];
    evidence: Evidence & { limitations: string[] };   // distinct codes of this peer's findings whose `affects` names one of its metrics, sorted; the findings themselves are in `findings`
  }[];
  skipped: Skipped[];
  note: string | null;
  summary: { ev_revenue: SummaryStat; ev_ebitda: SummaryStat; pe: SummaryStat }; // peers only; with no peers each has n = n_nm = n_missing = 0 and null values
}
```

Errors: as `/api/peers`.

### `GET /api/comps.csv`
Same parameters and errors (as JSON) as `/api/comps`. Returns `text/csv; charset=utf-8`, RFC 4180 quoting, with `Content-Disposition: attachment; filename="comps_<target key with : replaced by _>.csv"`.

Header: `Row,Rank,Key,Name,Similarity,Market cap (<currency> m),EV (<currency> m),EV/Revenue,EV/EBITDA,P/E`, e.g. `Market cap (USD m)`.

- One `target` row (blank `Rank` and `Similarity`), then one `peer` row per peer in rank order, then four summary rows `mean`, `median`, `high`, `low` (blank `Rank`, `Key`, `Name`, `Similarity` and money columns) and one `n` row giving the number of values used for each multiple.
- Values are the `display` strings: `NM` for not meaningful, blank for missing. Similarity uses 4 dp.
- With no peers (including a target without a usable description) the file has the target row and the summary rows, whose multiples are blank and whose `n` is 0.

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

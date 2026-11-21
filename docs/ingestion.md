# Ingestion

How the service turns `companies.json` and `fx_rates.json` into the in-memory dataset that every other stage reads. The code is in `src/comps/ingest.py` (loading, validation, normalization and entity resolution) and `src/comps/quality.py` (checks across companies).

**Ingestion's main rule: it never silently changes data.** It never imputes values, rescales them, turns a missing value into zero, or rewrites a classification. Anything doubtful becomes a structured **finding** and the value is left as it was, or set to "unavailable" (`None`).

All examples below use invented companies. The supplied data is never committed.

- [Inputs and settings](#inputs-and-settings)
- [Steps](#steps)
- [Output: what the dataset looks like](#output-what-the-dataset-looks-like)
- [Findings catalogue](#findings-catalogue)
- [Rounding](#rounding)
- [Assumptions](#assumptions)
- [Known gaps](#known-gaps)

## Inputs and settings

| Setting | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `/data` | Folder that holds `companies.json` and `fx_rates.json`. Point it at another folder to use a different data file of the same format. |
| `REFERENCE_DATE` | latest valid `price_date` in the data | The date that stale-price checks compare against. Set it (`YYYY-MM-DD`) to make the results reproducible. |
| `STALE_AFTER_DAYS` | `90` | A latest price older than this many days before the reference date gets a `stale_price` warning. |

Manual additions (records posted through the API) are passed in as `extra_records`. They go through exactly the same steps, with `origin="manual"`. They live in memory only and are never written to the input files.

## Steps

```
read files ─► parse FX ─► validate + normalize each record ─► drop unlisted ─► group by COUNTRY:TICKER
          ─► build each company's history ─► cross-company checks ─► Dataset (versioned)
```

### 1. Read the files

Both files are read as bytes and hashed with SHA-256, and the hashes go into the dataset version (step 8).

These problems **block** the whole dataset (`DatasetError`), and the service won't start on a broken input:

- a file can't be read, or isn't valid JSON;
- `companies.json` isn't a JSON list;
- after validation, no usable company is left.

### 2. Parse the FX rates

`fx_rates.json` must look like `{"base": "USD", "rates": {"EUR": 1.10, ...}}`. Each rate is the number of US dollars per one unit of the currency, as the glossary defines it.

| Input | Result |
|---|---|
| `base` is not USD (case-insensitive) | blocking error |
| `rates` missing or not an object | blocking error |
| Currency code `"jpy"` | read as `JPY` |
| Rate that is zero, negative or not a number, e.g. `"GBP": 0` | rate dropped, plus finding `invalid_fx_rate` (limitation). Values in GBP can't be converted. |
| `USD` listed at anything other than 1.0 | blocking error |
| `USD` not listed | added as 1.0 |

### 3. Validate and normalize each record

Each record is checked field by field. **A bad value never raises an error.** The value becomes `None` and a finding records why. The record itself is kept exactly as supplied in `Observation.original`.

**Schema.** All 20 glossary fields are expected. An absent field gives `missing_field`, except `id`, which is only used for provenance. An extra field gives `unexpected_field` (info): it is preserved but not used. A record that isn't a JSON object at all is skipped with `invalid_record` (error).

**Text fields** (`name`, `description`, `sector`, `industry`, `sub_industry`, `fiscal_year_end`):

- Leading and trailing whitespace is trimmed.
- `null` or an empty string gives `missing_value`.
- A non-string value gives `invalid_type`.
- `fiscal_year_end` must be a valid `MM-DD` (`02-29` is allowed), otherwise `invalid_value` (warning).

**Codes** (`ticker`, `country`, `price_currency`, `reporting_currency`) are trimmed and upper-cased. If that changed anything, a `normalized_value` (info) finding records it: `ticker 'zed' was read as 'ZED'`.

**Numbers.** These must be real JSON numbers. A string like `"20"` gives `invalid_type`, and NaN and infinity are rejected.

| Field | Rule | When the rule is broken |
|---|---|---|
| `price` | > 0 | `invalid_value`; treated as unavailable |
| `shares_outstanding` | > 0 | `invalid_value`; treated as unavailable |
| `total_debt`, `cash` | ≥ 0 | `invalid_value`; treated as unavailable |
| `revenue`, `ebitda`, `net_income` | any number | kept. If ≤ 0, an info finding `nonpositive_denominator` notes that the related multiple will be NM unless another input is missing. |

**Dates.** `price_date` must be `YYYY-MM-DD`, otherwise `invalid_value`.

**Conversion to USD.** This is done once, here, before anything is computed (glossary: *"convert everything to USD … before computing anything"*):

```
usd.price        = price × fx[price_currency]                         (USD per share)
usd.<money>      = value × fx[reporting_currency] × unit_factor       (USD millions)
unit_factor      = 1.0 for "millions", 0.001 for "thousands"
shares           = shares_outstanding (already in millions, so no conversion)
```

- `units` is case-insensitive, so `"Millions"` is read as `millions` with a `normalized_value` finding. Any other unit, such as `"billions"`, gives `invalid_value`, and every money field becomes unavailable.
- A currency missing from the FX file gives `unknown_currency`. Every value in that currency becomes unavailable. The price side and the financials side are independent, so an unknown reporting currency does not block the price.
- The factors actually used are kept in `Observation.conversion` (`price_fx`, `reporting_fx`, `unit_factor`). Later stages use them to explain *why* a value is missing.

*Example.* A Japanese-listed company that reports in EUR thousands:

| Field | Supplied | Factor | USD |
|---|---|---|---|
| price | 1,000 JPY | × 0.007 | 7.00 per share |
| shares_outstanding | 50 (m) | (none) | 50 m |
| total_debt | 100,000 (EUR k) | × 1.10 × 0.001 | 110.0 m |
| cash | 20,000 | same | 22.0 m |
| revenue | 300,000 | same | 330.0 m |
| ebitda | 60,000 | same | 66.0 m |
| net_income | 25,000 | same | 27.5 m |

### 4. Drop unlisted records and assign a key

- **No ticker**: the record is treated as *not listed* and excluded from the universe, with the dataset-level finding `unlisted_excluded` (warning). This applies whether or not the record has a country.
- **No country**: the placeholder `*` is used. A record with ticker `ZED` and no country becomes `*:ZED`, and it is still served.
- The company key is **`COUNTRY:TICKER`**, e.g. `US:ACME`. This is the company's identity. The record `id` is provenance only, so a repeated `id` is not a conflict.

### 5. Build each company's history

Records are grouped by key and sorted by (`price_date`, position in the input). Then, for each company:

**a. Exact duplicates collapse.** Records identical in everything except `id` count once. The later record is kept and the other goes to `superseded`, with finding `exact_duplicate` (info).

**b. One observation per `price_date`.** Numeric fields form a **time series**, one observation per date. If two records share a date, the later one in the input wins. When their numbers differ, a `conflicting_observation` finding (warning) lists the fields that differ. The loser is kept in `superseded`. Numbers are never mixed across dates or records.

**c. Text fields take the latest value.** Name, description, classification and fiscal year end come from the observation with the latest `price_date`.

- An older value that changed gives `text_updated` (info). All versions are kept in `text_history`.
- If two records on the **latest** date disagree, the later record in the input wins, with `conflicting_attributes` (warning).
- If the latest value is empty, the most recent non-empty value is used, with `text_from_older_record` (info). This handles append-style updates.

**d. Aliases.** Every distinct name seen for the key is kept, for search.

*Example.* Three records for `US:ACME`:

| id | price_date | price | description |
|---|---|---|---|
| r1 | 2026-07-01 | 18.00 | "…makes industrial widgets for factory automation customers." |
| r2 | 2026-10-01 | 20.00 | "…makes industrial widgets and sensors." |
| r3 | 2026-10-01 | 20.00 | "…makes industrial widgets and sensors." (identical to r2) |

The result is one company with `observations = [r1, r3]` and `superseded = [r2]`. Its description is the October one, and it has two findings: `exact_duplicate` (r2 and r3) and `text_updated` (description). Comps use **r3 only**, the latest observation.

### 6. Checks across companies (`quality.py`)

These run once all companies are built. They only **add findings** and never change data.

| Check | Rule | Finding |
|---|---|---|
| Possible same issuer | Two keys whose latest records are identical apart from `id`, `ticker` and `name`, e.g. `US:BLT.A` and `US:BLT.B`, two share classes | `possible_same_issuer` (warning) on both. They are **not merged**, and retrieval must keep them out of each other's peer lists. |
| Shared name | Two keys with the same name (case-insensitive) that the check above doesn't explain | `shared_name` (warning): searching by name is ambiguous |
| Stale price | Latest `price_date` more than `STALE_AFTER_DAYS` before the reference date | `stale_price` (warning). The company is still served. |
| Future price date | Latest `price_date` after the reference date (possible only when `REFERENCE_DATE` is set) | `future_price_date` (warning) |

### 7. Severity

| Severity | Meaning | Example |
|---|---|---|
| `error` | Something could not be ingested | a record that isn't a JSON object |
| `limitation` | A value the service needs is unavailable, so some outputs will be blank | null `revenue`, unknown currency |
| `warning` | Worth attention, but every output can still be produced | stale price, possible same issuer, a missing `sector` |
| `info` | Provenance or normalization; nothing is lost | upper-cased ticker, exact duplicate |

A missing field is a `limitation` when it feeds a metric or the company's identity, and a `warning` when it is only evidence, like `sector` or `industry`. Every finding also lists what it `affects`: a metric such as `ev_ebitda`, or a capability such as `retrieval`, `search` or `identity`.

### 8. Dataset version

`Dataset.version` is a 12-character hash of the two files' SHA-256 values plus any manual additions. Every API response that depends on the data carries it, so a result can be traced back to its exact input.

## Output: what the dataset looks like

Example input: eight invented records.

| id | ticker | country | What's special about it |
|---|---|---|---|
| r1, r2, r3 | ACME | US | time series, plus an exact duplicate (see step 5) |
| r4 | NIPP | JP | JPY price, EUR thousands financials |
| r5, r6 | BLT.A, BLT.B | US | identical apart from ticker and name |
| r7 | *(none)* | US | no ticker |
| r8 | zed | *(null)* | lower-case ticker, no country, `total_debt = -5`, price from 2026-05-01 |

Output, abridged. These are the real fields of `comps.models.Dataset`:

```jsonc
{
  "version": "49585f4f945f",
  "reference_date": "2026-10-01",          // latest valid price_date (REFERENCE_DATE not set)
  "record_count": 8,
  "fx_rates": {"USD": 1.0, "EUR": 1.10, "JPY": 0.007},
  "findings": [                            // dataset-level
    {"code": "unlisted_excluded", "severity": "warning", "record_ids": ["r7"],
     "message": "Record r7 has no ticker, so it is treated as not listed and excluded from the universe."}
  ],
  "entities": {                            // 5 companies from 8 records, ordered by key
    "*:ZED": {
      "observations": ["r8"],
      "latest": {
        "usd": {"price": 20.0, "total_debt": null, "cash": 100.0, "revenue": 1000.0,
                "ebitda": 200.0, "net_income": 80.0},
        "shares_outstanding": 100.0,
        "conversion": {"price_fx": 1.0, "reporting_fx": 1.0, "unit_factor": 1.0},
        "findings": [
          {"code": "normalized_value", "severity": "info",       "fields": ["ticker"]},
          {"code": "missing_value",    "severity": "limitation", "fields": ["country"],
           "affects": ["identity", "geography_evidence"]},
          {"code": "invalid_value",    "severity": "limitation", "fields": ["total_debt"],
           "affects": ["enterprise_value_usd_m", "ev_revenue", "ev_ebitda"],
           "message": "total_debt is -5; it must be ≥ 0. Treated as unavailable."}
        ]
      },
      "findings": [
        {"code": "stale_price", "severity": "warning",
         "message": "Latest price is from 2026-05-01, 153 days before the reference date 2026-10-01 (threshold 90 days)."}
      ]
    },
    "JP:NIPP": {
      "observations": ["r4"],
      "latest": {"usd": {"price": 7.0, "total_debt": 110.0, "cash": 22.0, "revenue": 330.0,
                         "ebitda": 66.0, "net_income": 27.5},
                 "conversion": {"price_fx": 0.007, "reporting_fx": 1.1, "unit_factor": 0.001}}
    },
    "US:ACME": {
      "observations": ["r1", "r3"], "superseded": ["r2"],
      "findings": [{"code": "exact_duplicate"}, {"code": "text_updated", "fields": ["description"]}]
    },
    "US:BLT.A": {"findings": [{"code": "possible_same_issuer", "entity_keys": ["US:BLT.A", "US:BLT.B"]}]},
    "US:BLT.B": {"findings": [{"code": "possible_same_issuer", "entity_keys": ["US:BLT.A", "US:BLT.B"]}]}
  }
}
```

Each entity also carries `key`, `ticker`, `country`, the resolved text fields, `aliases` and `text_history`. Each observation carries `record_id`, `origin`, `price_date` and `original`, which is the record exactly as supplied.

## Findings catalogue

| Code | Severity | Level | Raised when |
|---|---|---|---|
| `invalid_record` | error | dataset | a record is not a JSON object |
| `unlisted_excluded` | warning | dataset | a record has no ticker |
| `invalid_fx_rate` | limitation | dataset | an FX rate is zero, negative or not a number |
| `missing_field` | limitation / warning | record | a schema field is absent |
| `missing_value` | limitation / warning | record | a field is null or empty |
| `invalid_type` | limitation / warning | record | the wrong JSON type, e.g. `"20"` for a number |
| `invalid_value` | limitation / warning | record | a value breaks a rule, e.g. negative debt, a bad date or units |
| `unknown_currency` | limitation | record | a currency is not in the FX file |
| `normalized_value` | info | record | a code or units value was trimmed or had its case changed |
| `unexpected_field` | info | record | a field outside the schema |
| `nonpositive_denominator` | info | record | revenue, EBITDA or net income ≤ 0 |
| `exact_duplicate` | info | company | records identical apart from `id` |
| `conflicting_observation` | warning | company | same key and date, different numbers |
| `conflicting_attributes` | warning | company | same key and latest date, different text |
| `text_updated` | info | company | a text field changed over time |
| `text_from_older_record` | info | company | the latest text value was empty, so an older one is used |
| `possible_same_issuer` | warning | company | identical content under different keys |
| `shared_name` | warning | company | the same name under different keys |
| `stale_price` | warning | company | the latest price is older than the threshold |
| `future_price_date` | warning | company | the latest price date is after the reference date |

Finance adds `nonpositive_ev` and `non_finite_result`. See [finance.md](finance.md).

## Rounding

**Ingestion does no rounding.** USD values are kept at full floating-point precision, and every rounding rule lives in finance. See [finance.md § Rounding](finance.md#rounding-and-display).

## Assumptions

These were decided by the project owner where the brief was silent. They are logged in `AGENTS.md` §4.

1. **Identity is `COUNTRY:TICKER`.** The record `id` is provenance only, so a repeated `id` is not a conflict.
2. **No ticker means not listed**, so the record is excluded (`unlisted_excluded`). Nothing available offline can verify such a record.
3. **No country gives the placeholder `*`**, and the company is still served.
4. **Records with the same key are appends.** Numbers form a time series by `price_date`, and comps use the latest observation only. Text takes the latest value, falling back to the most recent non-empty one. Exact duplicates collapse.
5. **The later record in the input wins a same-date tie**, and a finding records it.
6. **Different keys with identical content are kept separate** and flagged `possible_same_issuer`, for example share classes.
7. **Supplied numbers are the source of truth.** There are no magnitude or unit-error checks, and nothing is ever rescaled.
8. **A stale price is a warning only.** It never blocks serving.

## Known gaps

- `text_from_older_record` also raises `text_updated`, whose message says "using the latest value" when the older value is the one used. This is a wording issue only, and the data is correct.
- The classification-conflict warning derived from description neighbours (AGENTS.md §4) is not built yet. It needs retrieval.

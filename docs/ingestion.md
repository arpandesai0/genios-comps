# Ingestion

How the service turns `companies.json` and `fx_rates.json` into the in-memory dataset that every other stage reads. The code is in `src/comps/ingest.py` (loading, validation, normalization and entity resolution), `src/comps/issuers.py` (merging share classes into issuers) and `src/comps/quality.py` (checks across companies).

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
| `STALE_AFTER_DAYS` | `90` (from [`src/comps/settings.toml`](../src/comps/settings.toml)) | A latest price older than this many days before the reference date (the latest valid `price_date` in the data) gets a `stale_price` warning. |

The input files are the whole dataset: there are no runtime additions (owner decision 2026-11-22).

## Steps

```
read files ─► parse FX ─► validate + normalize each record ─► drop unlisted ─► group by COUNTRY:TICKER
          ─► build each listing's history ─► merge share classes (DSU) ─► business descriptions
          ─► cross-company checks ─► Dataset (versioned)
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
| `USD` listed at a positive value other than 1.0 | blocking error (an unusable USD value is dropped as above, and USD stays 1.0) |
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
- If the latest value is empty, the most recent non-empty value is used, with `text_from_older_record` (info). This handles append-style updates. Because the empty value counts as a different value, the field also gets `text_updated` (info), whose message says the most recent non-empty value is used.

**d. Aliases.** Every distinct name seen for the key is kept, for search.

*Example.* Three records for `US:ACME`:

| id | price_date | price | description |
|---|---|---|---|
| r1 | 2026-07-01 | 18.00 | "…makes industrial widgets for factory automation customers." |
| r2 | 2026-10-01 | 20.00 | "…makes industrial widgets and sensors." |
| r3 | 2026-10-01 | 20.00 | "…makes industrial widgets and sensors." (identical to r2) |

The result is one company with `observations = [r1, r3]` and `superseded = [r2]`. Its description is the October one, and it has two findings: `exact_duplicate` (r2 and r3) and `text_updated` (description). Comps use **r3 only**, the latest observation.

### 6. Merge share classes (`issuers.py`)

A key `COUNTRY:TICKER` identifies a **listing**. Each country is assumed to have one exchange, so the same ticker in two countries is two companies. Share classes of one issuer (e.g. `US:BLT.A` and `US:BLT.B`) are merged into **one company**, with one row everywhere.

**When two listings merge.** They are in the same known country (never `*`), have different tickers, and their latest records agree on every issuer-level field: `description`, `sector`, `industry`, `sub_industry`, `fiscal_year_end`, `reporting_currency`, `units`, `price_date`, `total_debt`, `cash`, `revenue`, `ebitda` and `net_income`. Ticker, name, price, price currency and share count may differ, because they belong to the class. A merge also needs a non-empty description and at least one financial value, so two near-empty records never merge on missing data. Values are compared as ingestion reads them (text trimmed, currency codes upper-cased, units lower-cased, numbers by value, so `500` equals `500.0`), always from the latest record as supplied: a description carried over from an older record (step 5) does not count, so a latest record with an empty description never merges. Ticker look-alikes (`ABC.A` / `ABC.B`) whose financials differ are **not** merged: nothing tells us which numbers are right.

**How: a disjoint-set union.** Every listing key starts as its own parent. Listings with the same issuer signature (a hash of the fields above) are unioned. Each resulting set is re-rooted at its **shown key**, the class with the largest market value (price × shares; a class without one ranks last; ties go to the alphabetically first key). `Dataset.parents` keeps the parent pointer of every listing key, so any class key resolves to its issuer in one step, and `Dataset.entities` holds only issuers.

**What the issuer looks like.** Its own fields and history are the shown class's. `aliases` holds every class's names, and `share_classes` lists every listing (shown first, then by market value) with a `counted` flag. Each class keeps its own records and findings; a non-shown class's findings name the shown key first, then the class key.

**Market cap** (computed in finance) is the sum of price × shares over the **counted** classes. A class with the same price, price currency and share count as an earlier class is the same shares listed twice: it is not counted, and `duplicate_share_listing` (info) says so. If a counted class has no usable price or share count, market cap and everything built on it are **missing**, never a partial sum, and `share_class_incomplete` (limitation) names the class. Debt, cash, revenue, EBITDA and net income are counted once.

| Finding | Severity | Raised when |
|---|---|---|
| `share_classes_merged` | info | listings were merged; names every class key |
| `duplicate_share_listing` | info | a class repeats an earlier class's price, price currency and shares, so it is counted once |
| `share_class_incomplete` | limitation | a non-shown class has no usable price or share count, so market cap is missing |

Example: `US:DUAL.A` (price 20, 100 m shares) and `US:DUAL.B` (price 10, 50 m shares) with identical issuer data become one company shown as `US:DUAL.A`, with market cap 2,000 + 500 = 2,500. If `US:DUAL.B` had price 20 and 100 m shares too, it would be counted once (market cap 2,000).

### 6b. Business descriptions (owner decision 2026-11-23)

Descriptions usually open with the company's own invented name ("Irovaiva Air Group operates a regional flight network …"). An embedding model splits such names into sub-word pieces, so unrelated companies with look-alike names ("Irovaiva", "Irovaor", "Irixet") score as similar. In the supplied pre-test data this put a fibre broadband firm and a facilities firm above five of the six airlines for Irovaiva Air Group.

So, after the share-class merge, each issuer gets a derived **`business_description`**: its description without the **distinctive** words of its own names (current name and every alias, across share classes). A name word is distinctive when no other company's description contains it (case-insensitive), e.g. "Irovaiva". A removed word takes its possessive with it. Name words that other descriptions also use describe the business ("Air", "Offshore", "Drilling") and stay, as do legal suffixes. Removing whole names instead (experiments 11–12) also removed those business words and cost ranking quality. A description left with nothing but the name has no business text, and the company is treated as having no description for ranking.

- **Retrieval ranks on `business_description`.** The near-duplicate test keeps using the description as supplied, because two listings of one company usually share their name, and that is real evidence that they are the same company.
- **The analyst always sees the description as supplied** (`EntityDetail.description`). The derived text is not served.
- **No finding.** It applies to every company the same way and changes no supplied value.

### 7. Checks across companies (`quality.py`)

These run on issuers, after the merge. They only **add findings** and never change data.

| Check | Rule | Finding |
|---|---|---|
| Shared name | Two companies with the same name (case-insensitive) | `shared_name` (warning): searching by name is ambiguous |
| Stale price | Latest `price_date` more than `STALE_AFTER_DAYS` before the reference date (the latest valid `price_date` in the data) | `stale_price` (warning). The company is still served. |

### 8. Severity

| Severity | Meaning | Example |
|---|---|---|
| `error` | Something could not be ingested | a record that isn't a JSON object |
| `limitation` | A value the service needs is unavailable, so some outputs will be blank | null `revenue`, unknown currency |
| `warning` | Worth attention, but every output can still be produced | stale price, shared name, a missing `sector` |
| `info` | Provenance or normalization; nothing is lost | upper-cased ticker, exact duplicate |

A missing field is a `limitation` when it affects anything other than evidence: a metric, `identity` (ticker, country), `retrieval` (description), `search` (name) or `freshness` (price date). It is a `warning` when it affects only evidence, like `sector`, `industry` or `sub_industry`, or when it affects nothing, like `fiscal_year_end`. Every finding also lists what it `affects`: a metric such as `ev_ebitda`, or a capability such as `retrieval`, `search` or `identity`.

### 9. Dataset version

`Dataset.version` is a 12-character hash of the two files' SHA-256 values. Every API response that depends on the data carries it, so a result can be traced back to its input data. The version does **not** cover the settings: the same files with a different `STALE_AFTER_DAYS` give the same version but can give different `stale_price` findings.

## Output: what the dataset looks like

Example input: eight invented records.

| id | ticker | country | What's special about it |
|---|---|---|---|
| r1, r2, r3 | ACME | US | time series, plus an exact duplicate (see step 5) |
| r4 | NIPP | JP | JPY price, EUR thousands financials |
| r5, r6 | BLT.A, BLT.B | US | share classes: identical apart from ticker and name |
| r7 | *(none)* | US | no ticker |
| r8 | zed | *(null)* | lower-case ticker, no country, `total_debt = -5`, price from 2026-05-01 |

Output, abridged. These are the real fields of `comps.models.Dataset`:

```jsonc
{
  "version": "49585f4f945f",
  "reference_date": "2026-10-01",          // latest valid price_date in the data
  "record_count": 8,
  "fx_rates": {"USD": 1.0, "EUR": 1.10, "JPY": 0.007},
  "findings": [                            // dataset-level
    {"code": "unlisted_excluded", "severity": "warning", "record_ids": ["r7"],
     "message": "Record r7 has no ticker, so it is treated as not listed and excluded from the universe."}
  ],
  "entities": {                            // 4 companies from 8 records (BLT.A and BLT.B are one), ordered by key
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
    "US:BLT.A": {
      "share_classes": [{"key": "US:BLT.A", "counted": true}, {"key": "US:BLT.B", "counted": false}],
      "findings": [{"code": "share_classes_merged", "entity_keys": ["US:BLT.A", "US:BLT.B"]},
                   {"code": "duplicate_share_listing", "entity_keys": ["US:BLT.A", "US:BLT.B"]}]
    }
  },
  "parents": {"*:ZED": "*:ZED", "JP:NIPP": "JP:NIPP", "US:ACME": "US:ACME",
              "US:BLT.A": "US:BLT.A", "US:BLT.B": "US:BLT.A"}
}
```

Each entity also carries `key`, `ticker`, `country`, the resolved text fields, `aliases`, `text_history` and `share_classes` (empty for a single listing). Each observation carries `record_id`, `price_date` and `original` (and, until the follow-up code PR, `origin`, always `"file"`), which is the record exactly as supplied.

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
| `share_classes_merged` | info | company | listings with identical issuer data were merged into one company |
| `duplicate_share_listing` | info | company | a share class repeats another's price, price currency and shares (counted once) |
| `share_class_incomplete` | limitation | company | a share class has no usable price or shares, so market cap is missing |
| `shared_name` | warning | company | the same name under different keys |
| `stale_price` | warning | company | the latest price is older than the threshold |

Finance adds `nonpositive_ev` and `non_finite_result`. See [finance.md](finance.md).

**How the catalogue is tested.** Besides the unit tests for each rule, `tests/test_planted_defects.py` runs the whole pipeline, from the files through finance, on a synthetic universe in `tests/fixtures/planted_defects/` where each company carries one known defect. The test checks the result against `expected.json`, which was derived by hand from the rules on this page, and requires an exact match. Every planted defect must be caught with the right code, severity, fields, records and metric status, and no other finding may appear. A second check compares three lists of finding codes: the ones in this catalogue (the table plus the two finance codes named above it), the ones the source code can raise, and the planted ones. It fails if any code is missing from one of them.

## Rounding

**Ingestion does no rounding.** USD values are kept at full floating-point precision, and every rounding rule lives in finance. See [finance.md § Rounding](finance.md#rounding-and-display).

## Assumptions

These were decided by the project owner where the brief was silent. They are logged in `AGENTS.md` §4.

1. **Identity is `COUNTRY:TICKER`.** A key identifies one listing; one country has one exchange. The record `id` is provenance only, so a repeated `id` is not a conflict.
2. **No ticker means not listed**, so the record is excluded (`unlisted_excluded`). Nothing available offline can verify such a record.
3. **No country gives the placeholder `*`**, and the company is still served.
4. **Records with the same key are appends.** Numbers form a time series by `price_date`, and comps use the latest observation only. Text takes the latest value, falling back to the most recent non-empty one. Exact duplicates collapse.
5. **The later record in the input wins a same-date tie**, and a finding records it.
6. **Share classes are one company.** Listings in one country with identical issuer-level data are merged (step 6); market cap sums the counted classes.
7. **Supplied numbers are the source of truth.** There are no magnitude or unit-error checks, and nothing is ever rescaled.
8. **A stale price is a warning only.** It never blocks serving.

## Known gaps

- The classification-conflict warning derived from description neighbours (AGENTS.md §4) is not built yet. It needs retrieval.

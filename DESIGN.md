# Design

An offline comps-table service. An analyst names a company; the service picks its peers from a universe of about 500 public companies, computes valuation multiples, explains why each peer was chosen, and reports peer-only summary statistics. This document covers what is in scope, what a relevant peer is, the key decisions per stage with the alternatives considered, the data problems found and how each is handled, and how we know it works.

Detail lives in the stage docs: [ingestion](docs/ingestion.md), [finance](docs/finance.md), [retrieval](docs/retrieval.md), [evaluation](docs/eval.md), [API](docs/API.md), [pipeline](docs/pipeline.md). Every decision is dated in [AGENTS.md §4](AGENTS.md#4-decision-log).

## Scope

**In scope**
- Ingestion of `companies.json` and `fx_rates.json` from a folder named at start-up (`DATA_DIR`). It validates and normalizes every value to USD millions, resolves companies, and merges share classes.
- Glossary metrics: market cap, enterprise value, EV/Revenue, EV/EBITDA and P/E, each with an ok / NM / missing status. Also peer-only mean, median, high and low.
- Peer retrieval by business-description similarity, with a local embedding model, a reason for every peer and for every company skipped.
- An HTTP API (JSON and CSV) and a web UI with two pages: Compare (comps table) and Data (dataset health, findings, per-company provenance).
- A black-box retrieval eval on synthetic fixtures, with an append-only experiment log.
- One-command start (`make start DIR=...`), fully offline at runtime.

**Out of scope**
- Editing or adding companies at runtime. The input files are the whole dataset.
- Any network use at runtime: no web search, no hosted LLM.
- Using size, geography, labels or valuation to select peers. They are shown as evidence only.
- FX files with a base other than USD (rejected at start-up).
- Users, auth, persistence, scaling and hardening.

## What a relevant peer is

**A relevant peer is a company in the same business**: it sells similar products to similar customers, so an analyst would use its multiples to value the target. A company in the same industry but a different business (a regional bank vs a mortgage lender) is weaker. The same sector alone is weaker still.

Why description similarity, and not labels or size:
- **Descriptions say what a company does.** Sector, industry and sub-industry labels are coarse and can be wrong.
- **Size and geography don't make a business similar.** A small airline is still an airline, and a US and a UK airline are peers. Both are shown as evidence (revenue ratio, country match) so the analyst can filter.
- **Valuation multiples are never used to select peers.** That would be circular: the comps are meant to value the target.

The eval encodes this definition as graded labels: 3 same business, 2 same industry, 1 same sector, 0 different sector. Precision and recall count only grade 3.

## Problems and decisions, stage by stage

Each stage talks to the next only through plain data types (`src/comps/models.py`):

```
load → validate/normalize → resolve entities → merge share classes → snapshot (index) → retrieve → finance → API → UI
```

### 1. Load and validate (`ingest.py`)

| Problem | Decision | Alternatives considered |
|---|---|---|
| The grader runs a **different file of the same format** | Read from `DATA_DIR`; no rule or threshold calibrated on the supplied file alone (one exception: the near-duplicate threshold, see stage 5); synthetic fixtures cover cases the file lacks | Tuning on the supplied file (would overfit a pre-test) |
| Fields missing, null, of the wrong type (`"20"`), or invalid (negative debt, a bad date or units value) | The value becomes unavailable (`None`) and gets a structured finding. It is **never turned into zero, imputed or guessed** | Coercing strings or defaulting to 0 (silently wrong numbers) |
| A record with **no ticker** | Treated as not listed, excluded, finding `unlisted_excluded` | Keeping it under a made-up key |
| A record with **no country** | Placeholder `*` (key `*:TICKER`), still served | Dropping it |
| Unexpected fields, untidy codes (`" usd"`) | Ignored or normalized, with an info finding | Rejecting the record |

**General rule (owner decision):** serve no data rather than incorrect data. Every doubtful value becomes a finding with a code, the fields involved, a severity, a message and the metrics it affects.

### 2. Normalize currency and units (`ingest.py`)

| Problem | Decision | Alternatives considered |
|---|---|---|
| Prices and financials in different currencies, and financials in millions or thousands | Convert everything to **USD millions** in ingestion only; later stages are currency-agnostic | Converting in finance (two places to get wrong) |
| `fx_rates.json` has a `base` field | Must be USD (the glossary's definition); any other base is a blocking error | Accepting any base and converting through it (planned, then dropped as out of scope) |
| A rate that is zero, negative or not a number; a currency with no rate | The rate is dropped (`invalid_fx_rate`); values in that currency are blank (`unknown_currency`) | Assuming 1.0 |
| Implausibly large values (suspected unit errors) | **Used as given**, never rescaled: the supplied numbers are the source of truth | Heuristic rescaling (would rewrite data on a guess) |
| Stale prices | Warning `stale_price` (older than 90 days before the dataset's latest price date); still served | Blocking, or measuring from today (non-reproducible) |

### 3. Resolve companies (`ingest.py`)

| Problem | Decision | Alternatives considered |
|---|---|---|
| What identifies a company | **`COUNTRY:TICKER`**: each country is assumed to have one exchange, so the same ticker in two countries is two companies. Record `id`s may repeat and are provenance only | Record `id` (repeats in the data); ticker alone (collides across countries) |
| Several records with the same key | A **time series**: one observation per `price_date`, and comps use the latest only. Numbers are never mixed across dates | Averaging, or taking the last record in the file |
| Exact duplicates | Collapsed into one, finding `exact_duplicate` | Keeping both |
| Same key and date, different content | The later record in the file wins, finding `conflicting_observation` / `conflicting_attributes` | Dropping both |
| Text changed over time, or the latest text is empty | The latest value is used; if it is empty, the most recent non-empty one is used, with a finding | Blank text |
| Finding a company by name | `GET /api/companies?q=` returns **every** match (key, ticker, current or old name) and the analyst chooses. Comps take a key only | Automatic best-guess resolution (silently wrong target) |

### 4. Merge share classes (`issuers.py`)

| Problem | Decision | Alternatives considered |
|---|---|---|
| One issuer listed as several share classes (`ABC.A`, `ABC.B`) would appear as its own peer and be counted twice | Listings merge when they are in the same country, have different tickers and identical issuer-level data (description, labels, fiscal year, currencies, units, price date, debt, cash, revenue, EBITDA, net income). This is done with a **disjoint-set union**, re-rooted at the most valuable class | Flagging only ("possible same issuer"; tried first, then reversed); merging on ticker look-alikes (merges different companies) |
| Market cap of a merged issuer | Sum of price × shares over its classes. Identical classes (the same shares listed twice) are counted once. If any class lacks a price or share count, market cap is **missing, never a partial sum** | Using only the shown class (understates) |

### 5. Retrieve peers (`retrieval/`, `service.py`)

| Problem | Decision | Alternatives considered |
|---|---|---|
| How to rank | Cosine similarity of **local sentence embeddings** (MiniLM-L6, ONNX via fastembed) of business descriptions. It runs offline and is chosen by the eval: on the independent fixture, nDCG@10 rose from 0.46 to 0.73 over TF-IDF | TF-IDF (served first; misses paraphrases); bge-small and EmbeddingGemma (lower on the independent fixture; Gemma too slow to start); BM25 (lexical like TF-IDF); a hybrid (out of scope) |
| **Invented company names** dominate the text ("Zarqon Air Group" ≈ "Zarquel Fibre") | Ingestion derives a `business_description` without the distinctive name words (words no other description uses). Ranking uses it, and the analyst sees the original. Independent fixture 0.729 → 0.769; look-alike fixture 0.757 → 0.852 | Removing whole names (removed business words such as "Air", "Drilling"; −0.09); adding labels to the ranking (wrong labels would then move rankings) |
| **Duplicate listings** of one company (not share classes: different numbers, reworded text) | Near-duplicates (similarity ≥ 0.88 on the description as supplied, or identical text) are never each other's peers; the higher-ranked one stays. The threshold is the lowest cut that flags no labelled non-duplicate. A false duplicate (hiding a real peer) counts as worse than a missed one | 0.95 (inherited from TF-IDF; let 5 double listings through) |
| How many peers | The analyst picks `k` (1–50). The ranking is walked until `k` peers are found, skipping the target, near-duplicates, exclusions and companies without a description, each with a reason. No padding and no similarity floor: if it runs out, fewer are returned with a note | A fixed k; a similarity floor (would hide peers in thin universes) |
| Why each peer | Evidence per peer: similarity, label and country match, revenue ratio, limitations. The model internals are not shown to the analyst | Showing matched terms (TF-IDF only; removed with embeddings) |

### 6. Finance (`finance.py`)

| Problem | Decision | Alternatives considered |
|---|---|---|
| Glossary formulas with bad inputs | `ok`, `NM` (every input present and the denominator ≤ 0) or `missing` (an input unavailable; **wins over NM**), with the missing fields named | NM whenever a denominator is bad (hides that data is missing) |
| Zero or negative EV | Used as given, with an info finding; included in stats | Treating it as NM |
| Rounding | Everything is computed unrounded and rounded to 1 dp for display only, half away from zero. There is never a `-0.0` | Rounding before the stats (compounds error) |
| Summary statistics | Peers only (never the target), over the three multiples. NM and missing values are excluded and counted (`n`, `n_nm`, `n_missing`) | Including the target |
| Float overflow from extreme inputs | Becomes missing, with a `non_finite_result` warning | Crashing |

### 7. API and UI (`api.py`, `web/`)

| Problem | Decision |
|---|---|
| The UI must not depend on Python internals | A written contract ([docs/API.md](docs/API.md)) changed before the code; the API is an adapter only. The UI shows `display` strings and never re-rounds or computes stats |
| Analyst control | Remove a peer and the table is re-requested, so the server recomputes the stats; skipped companies show their reason and an Undo; CSV export |
| Trust | The Data page shows every company's records as supplied, the conversion factors, the normalized values, the unrounded metrics and the findings |

## Data problems found, and how each is handled

Found in the supplied pre-test file (485 records, 477 companies after merging) or planted in synthetic fixtures for cases a hidden file may contain:

| Problem | Stage | Handling | Finding |
|---|---|---|---|
| Share classes of one issuer listed separately | 4 | merged; identical classes counted once | `share_classes_merged`, `duplicate_share_listing` |
| Missing values (e.g. EBITDA, price) | 1 | blank, never zero; dependent metrics are missing | `missing_value` |
| Zero or negative revenue / EBITDA / net income | 6 | NM for that multiple | `nonpositive_denominator` |
| Stale prices | 2 | warning only | `stale_price` |
| Same key and date with different text | 3 | later record wins, flagged | `conflicting_attributes` |
| Exact duplicate records | 3 | collapsed | `exact_duplicate` |
| Invented names that look alike across unrelated businesses | 5 | distinctive name words removed before ranking | (derived text, no finding) |
| Name suffix differs between the name and the description ("Inc" vs "Corp") | 5 | handled by the word-level rule | none |
| Synthetic only: wrong types, unknown currencies, bad FX rates, no ticker, no country, units in thousands or an invalid unit such as billions, overflowing values, empty text | 1–6 | per the stage tables above | see the [findings catalogue](docs/ingestion.md#findings-catalogue) |

## How we know it works (acceptance criteria)

1. **Formulas match the glossary exactly.** Unit tests cover every metric, status and rounding tie (`tests/test_finance.py`).
2. **The pipeline matches hand-derived expectations end to end.** A synthetic universe has one planted defect per company, and `tests/test_planted_defects.py` must match `expected.json` exactly: every finding, every metric and every status.
3. **Retrieval quality is measured, not assumed.** The black-box eval runs a commit's API over HTTP on four synthetic fixtures with graded labels. Two of them were written by a different model that never saw the ranker. Dev and held-out targets are kept separate.
   - Served configuration (experiment 13): nDCG@10 is 0.769 dev / 0.761 held-out on the independent fixture, and 0.852 / 0.848 on look-alike names.
   - No company appears twice in a peer list.
   - Dedup precision is 1.0 at the served threshold.
4. **Spot-checked on the supplied data** (qualitative). 36 random companies at k = 5 had their peers graded by model judges reading the descriptions: 180 of 180 were graded the same business. The method and limits are in [eval/results/spotcheck_pretest_k5.md](eval/results/spotcheck_pretest_k5.md).
5. **The contract holds.** API tests assert the documented field names. Playwright tests cover the UI flows on mocks.
6. **It runs as the brief requires.** `make start DIR=<folder>` starts offline. This was checked by hand: the API image started with `docker run --network none -m 1g` and loaded the model baked into it (recorded in PR #30's review replies and PR #31's checks). Start-up fails loudly on a missing model, bad settings or unreadable files.
7. **One command runs every check:** `make check` (lint, types, 260+ tests). CI runs it on every PR.

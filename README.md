# genios-comps

An offline **comparable-companies (comps table) service**.

An analyst names the company they want to research. The service picks that company's peers from a universe of about 500 public companies and returns a comps table:

- each peer's market cap, enterprise value, EV/Revenue, EV/EBITDA and P/E, all in USD;
- **why each peer was chosen**, so the analyst can trust or adjust the list;
- summary statistics (mean, median, high, low) across the peers.

The service reads its data from a folder it is given at start-up. It runs fully offline and starts with a single command.

This project is under active development. Setup instructions, design notes and evaluation results will be added as each part lands.

## Setup and running

You need Docker (Engine 25+ with Compose 2.20.2+, for the start-up healthcheck interval). The service reads its data from a folder you name at start-up. The folder must contain `companies.json` and `fx_rates.json`.

```bash
make start DIR=/path/to/data                # builds and starts every service (API and web UI)
make start DIR=/path/to/data SERVICES=api   # only the named services, e.g. the API without the front end
make stop                                   # stops them
```

`SERVICES` takes a space-separated list of compose services (`api`, `web`); it defaults to all of them. An unknown name is an error.

The first build downloads the embedding model (`sentence-transformers/all-MiniLM-L6-v2`, about 90 MB) into the image; this is the only network use. At runtime the service is fully offline, and it refuses to start if the model is missing. Start-up embeds every company description once (a few seconds for a few hundred companies).

- UI: <http://localhost:3000>. It opens the **Data** view: dataset health, every company, and each company's observation history, normalized USD values, conversion factors, metrics and findings.
- API: <http://localhost:8000/api/health>. The endpoints are described in [`docs/API.md`](docs/API.md).
- **Using a different data file:** point `DIR` at another folder with the same two files. The data is mounted read-only and never copied into an image.

Once everything is healthy, `make start` prints the URLs between two `****` lines and then follows the logs; Ctrl+C stops the services.

- **Compare** (`/`): search a company, pick `k`, and get the comps table: peers ranked by description similarity with their metrics, the evidence for each peer, peer-only summary statistics, the companies skipped and why, CSV export. Removing a peer re-requests the table, and the statistics are recomputed by the server.

Status: the data endpoints, peer selection (`/api/peers`) and comps tables (`/api/comps`, `/api/comps.csv`) are served, and the UI uses all of them. The input files are the whole dataset: there is no way to add or edit companies at runtime.

## Assumptions

Where the brief is silent, the service assumes the following:

1. **Identity is `country:ticker`.** A key identifies one listing (see 13). Record `id`s are internal provenance only, so an `id` reused across records is not treated as a conflict.
2. **A record without a ticker is not a listed company.** The brief describes a universe of public companies, and nothing available offline (no web search or LLM) can verify such a record, so it is excluded and reported as `unlisted_excluded`. This applies whether or not the record has a country.
3. **A missing country becomes the placeholder `*`**, giving keys like `*:ACME`. The company is still served.
4. **Records with the same key are appends to one company.** Each `price_date` is one observation in a time series, and comps use the latest observation. Text fields (name, description, classification) take the latest value; if the latest value is empty, the most recent non-empty value is used and flagged. Numbers are never carried over from another date. Records that are identical apart from their `id` collapse into one.
5. **Supplied numbers are the source of truth.** Unusually large values are used as given. They are not flagged or rescaled. In production, values like these would go through human or automated review.
6. **Stale prices are a warning, not a blocker.** A price more than 90 days older than the latest `price_date` in the dataset is flagged, and the company is still served. Because the reference is the data's own latest date, not today's date, the same file always gives the same result. The trade-off: a single mistyped future date (e.g. 2099) would become the reference and mark every other company stale; since staleness is only a warning, no values change.
7. **Missing takes precedence over NM.** The glossary says both "a missing input gives blank, not NM" and "a zero or negative denominator gives NM". When both apply, the multiple is reported as missing (blank), with the missing fields listed. NM is used only when every input is present.
8. **A zero or negative enterprise value is used as given.** EV multiples are shown as computed, so they can be negative, and they are included in the summary statistics. An info finding (`nonpositive_ev`) flags it. The glossary defines NM only for denominators.
9. **Rounding.** Every value, including the summary statistics, is computed unrounded (apart from cleaning floating-point noise at 9 decimal places) and rounded to one decimal place only for display. A tie rounds half away from zero (12.25x → 12.3x).
10. **Summary statistics.** They cover the three multiples only. With an even number of peers, the median is the average of the two middle values. When no peer has a usable value, the statistics are blank.
11. **Extreme inputs never break a comps table.** If a value overflows (it is too large to represent), it is shown as blank, excluded from the statistics, and flagged with a `non_finite_result` warning.
12. **Money is in USD, and `fx_rates.json` must have base USD.** The glossary defines each rate as US dollars per one unit of the currency, so a file with any other `base` is rejected at start-up with a clear error. USD itself is 1.0: it is added if missing, a positive value other than 1.0 is an error, and an unusable USD value (zero, negative, not a number) is dropped like any bad rate, keeping 1.0. A rate that is zero, negative or not a number is dropped with an `invalid_fx_rate` finding. A currency with no usable rate is a data issue: values in it are blank, with an `unknown_currency` finding. Only ingestion converts currency.
13. **One company → one exchange → one country.** Each country is assumed to have a single stock exchange, and each listing trades on one exchange, so `country:ticker` identifies a listing. The same ticker in two countries (e.g. `US:ABC` and `CA:ABC`) is treated as two different companies.
14. **Share classes of one issuer are one company.** Listings in the same country whose issuer-level data is identical are merged; see [Share classes](#share-classes-disjoint-set-union).
15. **Peers are chosen by meaning, with one local embedding model.** Descriptions are compared without the invented words of the company's own name (name words no other description uses, e.g. "Irovaiva" in "Irovaiva Air Group"; "Air" stays): look-alike invented names ("Irovaiva Air", "Irovaor Fibre") would otherwise make unrelated companies similar. The near-duplicate test keeps the names, since two listings of one company share theirs. Descriptions are compared with `sentence-transformers/all-MiniLM-L6-v2`, run locally. It was chosen over TF-IDF and two other models by the retrieval eval ([eval/README.md](eval/README.md)). One model does both ranking and duplicate detection: a hybrid (for example, TF-IDF for duplicates) is out of scope for now. The model is a required part of the service, and there is no fallback.
16. **Two companies are near-duplicates at a description similarity of 0.88 or more** (or identical text), and are then never each other's peers. Hiding a genuine peer is treated as worse than showing a duplicate, so the cut is the lowest one that flags none of the labelled non-duplicates. These are the 40 most similar pairs in the supplied data (all genuine peers, the highest at 0.873) plus synthetic pairs. This threshold is the one rule tuned on the supplied pre-test data (an exception the owner made on 2026-11-22). Heavily reworded duplicate listings can still score below it and appear as peers.

## AI usage

**Every business and engineering decision was made by the human code owner.** That covers what counts as a peer, how duplicates and share classes are treated, which numbers feed the calculations, what is in or out of scope, which model is served and every threshold. The AI agents proposed options and recommendations, and the owner chose. Each decision is recorded with its date in [AGENTS.md §4](AGENTS.md#4-decision-log). The working rules the agents followed (ask, don't decide; small PRs; agents never merge) are in [AGENTS.md §2](AGENTS.md#2-how-to-work).

**Where AI tools helped**
- **Planning:** a first planning handoff (Codex) and stage-by-stage option lists with recommendations (Claude Code) for the owner to decide on.
- **Implementation:** Claude Code wrote most of the Python service (ingestion, share-class merge, finance, retrieval, API), the tests, the eval harness and the docs. Codex built the first version of the Next.js UI against mocks.
- **Independent test data:** the second ranking fixture, the look-alike-names fixture and the labelled near-duplicate pairs were written by a different model (Sonnet) that never saw the ranker or its scores. This keeps the eval from grading itself.
- **Review:** every PR got a review from a smaller model (Sonnet). The authoring agent answered each comment and fixed or declined it with a reason, and the owner reviewed and merged by hand.
- **Spot checks:** Sonnet sub-agents judged peer lists for 36 random companies in the supplied data by reading the descriptions.

**How the output was checked**
- **Tests on synthetic data only:** unit tests per rule, and an end-to-end acceptance fixture with one planted defect per company whose hand-derived `expected.json` must match exactly. `make check` (lint, types, tests) runs locally and in CI on every PR.
- **The glossary as ground truth:** every formula, status and rounding rule was checked against the brief's glossary, which overrides any AI-written doc.
- **Measurement, not claims:** each change to what is served came with a black-box eval run on fixed inputs, logged in an append-only experiment log ([eval/README.md](eval/README.md)). Regressions are reported next to gains, and estimates are never presented as measurements.
- **Running it:** the owner ran the service on the supplied data and inspected results in the UI. Two problems the AI had missed came from this: a broken Compare page against the real API, and look-alike company names skewing peers. Both were fixed and measured.

## Requesting a comps table

1. Find the company's key by text: `GET /api/companies?q=dorust` (key, ticker or name). Each result has a `key` such as `CA:DOLG`.
2. Build the table: `GET /api/comps?target=CA:DOLG&k=10`. Add `exclude=US:AAAA,US:BBBB` to remove peers; the summary statistics are recomputed.
3. Download it: `GET /api/comps.csv?target=CA:DOLG&k=10`.

`GET /api/peers?target=...` returns the same peers with the evidence for each (description similarity, classification and country match, revenue ratio) but no metrics. How peers are chosen is in [`docs/retrieval.md`](docs/retrieval.md).

## Share classes (disjoint-set union)

One issuer can list several share classes, e.g. `US:BLT.A` and `US:BLT.B`. A comps table needs **one row per issuer**, otherwise the same company shows up as its own peer and is counted twice in the statistics. So ingestion merges share classes into one company.

**Which listings merge.** Two listings are share classes of one issuer when they are in the same country (never the unknown-country placeholder `*`), have different tickers, and their latest records agree on every issuer-level field: description, sector, industry, sub-industry, fiscal year end, reporting currency, units, price date, total debt, cash, revenue, EBITDA and net income. Ticker, name, price, price currency and share count may differ, because they belong to the class. Two near-empty records never merge just because both are missing data, and tickers that merely look like classes (`ABC.A` / `ABC.B`) but report different financials stay separate.

**How: union-find.** `src/comps/issuers.py` implements a disjoint-set union (DSU):

```
start      every listing is its own parent      US:BLT.A → US:BLT.A    US:BLT.B → US:BLT.B    US:ACME → US:ACME
union      same issuer signature → one set      {US:BLT.A, US:BLT.B}   {US:ACME}
re-root    each set points at its shown key     US:BLT.A → US:BLT.A    US:BLT.B → US:BLT.A    US:ACME → US:ACME
```

- Each merge rule unions pairs of keys, so the grouping is always transitive and consistent, and a new rule can be added without touching the rest. Listings are bucketed by a hash of the issuer-level fields (compared as ingestion reads them: trimmed text, upper-case currency codes, numbers by value), so building and re-rooting the sets takes linear time, not a comparison of every pair.
- The **shown key** is the class with the largest market value (price × shares). A class without one ranks last, and ties go to the alphabetically first key.
- The parent pointer of every listing is kept (`Dataset.parents`), so any class key resolves to its issuer: `GET /api/companies/US:BLT.B` returns the issuer under `US:BLT.A`, and search reports which class matched (`matched_key`).

**Market cap** is the sum of price × shares over the issuer's classes, each converted to USD. Two classes with the same price, price currency and share count are taken to be the same shares listed twice and counted once. If any counted class has no usable price or share count, market cap and everything built on it are left blank rather than summed from the other classes. Debt, cash and the financials are counted once. Every merge, every class counted once and every incomplete class is reported as a finding.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
make install     # create .venv and install the package with dev tools
make check       # lint, typecheck and tests (the same checks CI runs)
make format      # apply ruff fixes and formatting
make model       # download the embedding model to MODEL_CACHE_DIR (first local run only)
DATA_DIR=/path/to/data .venv/bin/uvicorn comps.api:app --reload   # API only, without Docker
make experiment DESC="what it tests"   # retrieval eval: runs the pipeline at a commit, scores it, logs it
```

Settings: thresholds and defaults (stale-price days, embedding model, near-duplicate threshold per model) are in the config file [`src/comps/settings.toml`](src/comps/settings.toml). Environment variables override them (`STALE_AFTER_DAYS`, `EMBEDDING_MODEL`, `NEAR_DUPLICATE_THRESHOLD`), `CONFIG_FILE=<path>` points at another file, and `MODEL_CACHE_DIR` / `MODEL_OFFLINE` control the model cache; see [`docs/retrieval.md`](docs/retrieval.md). The tests use the light TF-IDF ranker, so they need no model download. The eval and its results are described in [`eval/README.md`](eval/README.md).

CI runs four workflows on every pull request and push to `main`: `lint`, `typecheck`, `tests` (Python 3.11 and 3.12, with a coverage report) and `repo-hygiene` (notebooks cleared, no supplied data or local state committed).

Optional: `pre-commit install` enables hooks that run ruff and strip notebook outputs on each commit (see `.pre-commit-config.yaml`).

## What I'd do with more time

Ranked by expected value for an analyst:

1. **Make retrieval more agentic and web-search driven.** Much of the remaining ambiguity is better settled by an agent with tools than by fixed rules: what a company really does, whether two listings are the same issuer, whether a label is wrong, which peers an analyst would accept. Small language models (SLMs) could run locally to keep the service offline-friendly, with web search used where policy allows. Model-derived signals would stay marked as such, never treated as fact.
2. **Reduce the geography leak.** When the ranker is wrong, the wrong peer shares the target's country more often than chance, because descriptions say "based in …". The fix would be stripping or down-weighting country phrases, measured on the eval's cross-country and geo-trap cases.
3. **Catch heavily reworded duplicate listings.** Copies reworded enough to score below the 0.88 near-duplicate threshold still appear as peers. A dedicated duplicate model, or an agent check, could catch them without lowering the threshold and hiding real peers.
4. **Harder evaluation on real-format data.** A random sample of the supplied data is easy, with about five near-identical companies per business. More planted hard cases are needed (mislabelled companies, boilerplate-heavy descriptions, thin universes), plus repeated runs to measure run-to-run variation.
5. **The derived label-conflict warning.** Flag a company whose description neighbours disagree with its sector label, marked as model-derived, without rewriting labels.


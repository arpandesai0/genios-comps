# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository. Read it fully before changing anything.

## 1. What this project is

An offline **comps-table service**. An analyst names a company; the service picks peers from a universe of ~500 companies, computes valuation multiples, explains why each peer was chosen, and reports summary statistics across the peers.

It is a take-home assignment with a **~6 hour budget**. Treat it as an **MVP**: a smaller scope done well and explained clearly beats a larger one half done.

### Sources of truth (in priority order)

1. **The assignment brief and glossary.** They live outside this repo at `~/Downloads/genios-takehome/` (`README.md`, `GLOSSARY.md`, `data/`). The glossary's formulas and rules must be applied exactly.
2. **The decision log in §4 of this file.** These decisions were made explicitly by the project owner.
3. **The original planning handoff.** It was written by a different agent (Codex). It is useful background, but where it conflicts with 1 or 2, those win.

**Never commit the brief, the glossary, or the supplied `data/`.** They are git-ignored. Tests use small synthetic fixtures written for this repo.

## 2. How to work

### Ask, don't decide

- **Do not make business or product decisions on your own.** That includes what counts as a peer, how duplicates are treated, which numbers feed the calculations, how many peers to return, what the UI shows, and what is in or out of scope. Ask the owner a concise question, give options, and mark the one you recommend.
- Purely technical choices that follow from an existing decision (naming, file layout inside a module, test structure) don't need a question. If a technical choice changes behaviour the analyst can see, it is a business decision.
- Record every answered decision in §4 with the date. Don't re-ask anything already recorded there.
- If the brief is silent and the owner is unavailable, pick the most conservative option, say so, and list it under **Assumptions** in the README.

### Engineering style: a simple MVP

- One Python service, synchronous, in-memory. No queues, workers, caches, vector databases, or microservices.
- FastAPI handlers are plain `def`, so they run in FastAPI's threadpool and requests are served concurrently. Every request reads one **immutable snapshot**, built once at start-up from the input files. There are no runtime writes.
- Prefer the standard library, plus numpy and scikit-learn for retrieval. Add a dependency only when it removes real complexity.
- No speculative abstractions. Add an interface only where a part is genuinely meant to be swapped (retrievers are; storage is not, yet).

### Keep steps abstract and loosely coupled

Each stage talks to the next only through plain data types. Nothing reaches into another stage's internals.

```
load → validate/normalize → resolve entities → snapshot(index) → retrieve → finance → API → UI
```

- **Ingestion** knows nothing about retrieval or finance.
- **Finance** takes a normalized observation and returns metric values. It doesn't know where they came from.
- **Retrieval** implements a small `Retriever` interface (fit on entities, score candidates for a target, explain a pair). Rankers can be swapped without touching ingestion, finance, or evaluation.
- **API** is an adapter only: no business logic in route handlers.
- **UI** depends on the HTTP contract only, never on Python internals.

### Measure, don't assume

- Evals and the served system evolve together, the way a researcher iterates. Only what is served gets evaluated, and every change to what is served comes with an updated eval result in `eval/results/` (machine-readable) plus a short interpretation: what improved, what got worse, and whether it is worth the complexity.
- Don't build or mention comparators, alternative rankers, or future variants ahead of time. The next step is decided by the owner after the current one has been evaluated.
- Never present estimates as measurements. Keep development and held-out evaluation targets separate.

### Data integrity rules

Never silently:

- turn missing values into zero;
- impute financials;
- rescale suspected unit errors;
- rewrite classifications;
- treat a model-derived signal as fact.

Every such case becomes a structured **finding** with a code, the affected fields, a severity, a message, and the metrics it affects.

### Parallelize

Wherever steps don't depend on each other, run them at the same time: independent tool calls in one turn, and parallel sub-agents or worktrees for independent modules. Once the shared data types (§5, `models.py`) are fixed, the following can proceed in parallel:

| Can run in parallel | Depends on |
|---|---|
| Finance calculations + tests | `models.py` |
| Ingestion validation and entity resolution + tests | `models.py` |
| Synthetic evaluation fixtures and relevance labels | the record schema only |
| Retriever implementation | `models.py` |
| Next.js UI against a mocked API | the agreed API contract (OpenAPI) |
| Docs (DESIGN, README sections, time log) | the decisions in §4 |

These steps run in sequence: the snapshot/service layer (needs ingestion, finance and retrieval), the evaluation run (needs retrievers and fixtures), and wiring the UI to the real API.

### Git and PRs

- Use small PRs, one per step, each with a clear description. Work on a branch, never directly on `main`.
- **Agents never merge PRs.** The owner reviews and merges every PR by hand. Agents must not run `gh pr merge`, enable auto-merge, add a PR to a merge queue, push to `main`, or merge one PR branch into another to get around this.
- Work that depends on an unmerged PR waits. Tell the owner what is blocked and stop, unless the owner explicitly says to stack the next branch on the unmerged one. Elsewhere in this file, "fixed" or "landed" means merged to `main`.
- Review loop for every PR:
  1. **Open.** The authoring agent opens the PR once the step is complete and `make check` passes. If the step changes what is served, the PR must also include the updated eval result in `eval/results/` and its interpretation (see "Measure, don't assume").
  2. **Review.** The authoring agent spawns a reviewer sub-agent on a smaller model than its own. The reviewer posts one GitHub review with event `COMMENT` (never `APPROVE` or `REQUEST_CHANGES`) and inline comments where possible. It never edits files, pushes or merges.
  3. **Address.** The authoring agent answers every comment *in its thread*: either it pushes a fix and says which commit fixed it, or it explains why no change is needed. It **resolves each thread it fixed**, and leaves declined threads open for the owner to judge. It reruns `make check` after the fixes. There is no second automated review unless the owner asks for one.
  4. **Hand off.** The authoring agent tells the owner the PR is ready, summarising what was fixed and what was declined, and stops. The owner reviews manually and merges.
- End every commit message with the trailer of the agent that actually wrote the change:
  - Claude: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  - Codex: `Co-authored-by: Codex <codex@openai.com>`
- Run the tests before every commit. Don't claim a PR, merge, or measurement that didn't happen.

## 3. Architecture

```
               DATA_DIR (companies.json, fx_rates.json)
                                  │
                        Ingestion pipeline
   raw → validate/normalize (USD, units) → group by country:ticker
       → share classes merged into one issuer (disjoint-set union)
       → issuers with observation history + findings
                                  ↓
          Immutable Snapshot (versioned by input-file hash)
     entities · findings · TF-IDF index · derived label-conflict warnings
                                  ↓
     Resolve (service.search): key / ticker / name → every match; the analyst chooses
                                  ↓
     Retriever: TF-IDF on descriptions
       walks the full ranking until k peers: skips the target, near-duplicates and
       analyst exclusions, with reasons; returns fewer (and says why) if it runs out;
       size and geography are shown as evidence only
                                  ↓
     Finance: latest observation → market cap, EV, EV/Revenue, EV/EBITDA, P/E
              (ok | NM | missing) → peer-only mean/median/high/low with n
                                  ↓
     FastAPI (JSON + CSV) ──► Next.js + shadcn/ui (compare view, data/ingestion view)
```

## 4. Decision log

| Date | Decision |
|---|---|
| 2026-11-21 | Repo lives in `~/Desktop/genios-finance`; the service reads the brief's data through `DATA_DIR`. |
| 2026-11-21 | **Identity = `country:ticker`.** Record `id` is internal provenance only. *(Narrowed 2026-11-22: the key identifies a listing; share classes of one issuer merge into one company.)* |
| 2026-11-21 | Same key with identical content → one entity (exact duplicates collapse). |
| 2026-11-21 | Same key with different content → text fields (name, description, labels) take the value with the latest `price_date`. A tie goes to the later record in the file and is logged as a conflict finding. A text-only change raises an info finding and keeps the previous value in provenance. |
| 2026-11-21 | Numeric fields are kept as a **time series** of observations keyed by `price_date`. Comps use the **latest observation only**; fields are never mixed across dates. |
| 2026-11-21 | ~~Different keys with identical content → separate entities flagged **possible same issuer** (e.g. share classes). They are excluded from each other's peer lists and the reason is shown.~~ **Reversed 2026-11-22:** share classes are merged into one issuer (see below). |
| 2026-11-21 | Supplied numbers are the source of truth: no magnitude or unit-error checks, never rescaled. |
| 2026-11-21 | No ticker → treated as **not listed** and excluded (finding `unlisted_excluded`). Missing country → placeholder `*` (key `*:TICKER`). |
| 2026-11-21 | Record `id`s may repeat; this is not a conflict. |
| 2026-11-21 | Latest text value is empty → use the most recent non-empty value, with a finding (an append-style update). |
| 2026-11-21 | Stale price (> 90 days before the dataset's latest price date) is a warning only; never blocks serving. |
| 2026-11-21 | The user picks `k`. There is **no similarity floor or abstention**. |
| 2026-11-21 | Retrieval = TF-IDF on descriptions. Size and geography are evidence, not ranking inputs. No hard industry filter. Valuation multiples are never used to select peers. |
| 2026-11-21 | A derived classification-conflict warning comes from description neighbours. It is marked model-derived, and labels are never rewritten. |
| 2026-11-21 | ~~Manual company additions are **in-memory only**. They never touch the input files.~~ **Reversed 2026-11-22:** no manual additions. |
| 2026-11-21 | UI = **Next.js + shadcn/ui** (data tables), served as a separate container in docker compose. |
| 2026-11-21 | GitHub: public repo `genios-comps`, one PR per step, merged in sequence **by the owner**. A PR is opened once its step is built (and, if it changes what is served, evaluated); the owner decides the next step after reviewing the results. |
| 2026-11-21 | Agents never merge. Each PR gets a smaller-model sub-agent review; the authoring agent addresses the comments; the owner reviews and merges by hand. |
| 2026-11-21 | After replying to review comments, the authoring agent resolves the threads it fixed. Declined threads stay open for the owner. |
| 2026-11-21 | ~~A zero or negative denominator gives NM even when another input is missing.~~ **Reversed the same day:** a missing input gives **missing** (blank) and takes precedence over NM, reading the glossary's "missing → blank, not NM" literally. NM only when every input is present and the denominator is ≤ 0. |
| 2026-11-21 | Only `~/Downloads/genios-takehome` is ground truth. Every repo doc (this file included) is generated and is checked against the glossary before being relied on. |
| 2026-11-21 | Zero or negative EV is used as given (multiples shown, included in stats) with an info finding `nonpositive_ev`. Extreme multiples are not flagged. |
| 2026-11-21 | Rounding: compute everything (summary stats included) on unrounded values; round to 1 dp only for display, ties **half away from zero** (12.25 → 12.3, −12.25 → −12.3). Never show `-0.0`. |
| 2026-11-21 | Display: money `4,512.3` / `-1,234.5`; multiples `12.3x` / `-2.1x` / `1,234.5x`; NM shows `NM`; missing shows blank (null). |
| 2026-11-21 | Summary stats only for the three multiples. Even-count median = average of the middle two. With no valid peer values, the stats are null (blank) and the n / n_nm / n_missing counts explain why. The caller passes peers only. |
| 2026-11-21 | `missing_inputs` names the root record field: `price_currency`, `reporting_currency` or `units` when a conversion failed, otherwise the numeric field itself. |
| 2026-11-21 | Float noise is cleaned at 9 dp (half away from zero) before the 1-dp display rounding and before the EV ≤ 0 check, so arithmetic ties such as 2.05 × 3 display as 6.2. `missing_inputs` is ordered numerator causes then denominator causes; within a field, the field then its conversion fields. |
| 2026-11-21 | A non-finite result (float overflow from extreme inputs) becomes **missing**, with a warning finding `non_finite_result` listing every value it blanked. It is excluded from stats and never crashes the response. |
| 2026-11-21 | **General rule: serve no data rather than incorrect data.** This includes partial explanations. So `missing_inputs` names an unusable field *and* its failed conversion (e.g. `["total_debt", "reporting_currency"]`), and finding messages must say which value is actually used. |
| 2026-11-21 | First backend slice is **read-only**: health, dataset, findings, company search/list/detail. Comps and ingest are not served yet (404). *(Ingest dropped 2026-11-22.)* |
| 2026-11-21 | `make start DIR=<folder>` runs **docker compose** (API + web). `DIR` is required and must contain `companies.json` and `fx_rates.json`; there is no default path. `make stop` stops it. |
| 2026-11-21 | Until comps exist, the UI in API mode hides the Compare page, and `/` redirects to `/data`. Mock mode still shows everything. *(The "Add company" form is removed, 2026-11-22.)* |
| 2026-11-21 | A company's findings (page, counts and `/api/dataset/findings?entity=KEY`) are its own: company-level, latest observation and finance. ~~A share-class sibling's mirror-image finding is not repeated.~~ (Moot since 2026-11-22: share classes are one issuer.) |
| 2026-11-21 | Keep Docker and compose conventional (e.g. ports `3000:3000`). No networking or security hardening, which is not the point of the assessment. |
| 2026-11-21 | **Priorities: data normalization (input) and retrieval (output) matter most.** The pipeline's outputs must match the expected results exactly. Findings are supporting statistics: keep them accurate, but don't spend effort polishing their granularity. |
| 2026-11-21 | An empty latest text value keeps raising both `text_from_older_record` and `text_updated` (current behaviour). Lower-case currency codes in `fx_rates.json` are upper-cased without a finding. |
| 2026-11-21 | **Currency.** `fx_rates.json` may have any `base`; each rate is read as base units per one unit of the currency. Values are converted to USD whenever the file gives a USD rate (glossary), otherwise to the base currency, with a dataset-level `currency_not_usd` finding and money labelled with the currency. A currency without a rate is a data issue (`unknown_currency`, values blank). Listed in README Assumptions. |
| 2026-11-21 | **Only ingestion handles currency.** It picks the dataset currency and normalizes every value into it; finance, retrieval, the API and the UI are currency-agnostic and only display the `currency` label. API names drop `usd` (`market_cap_m`, `enterprise_value_m`, `normalized`). |
| 2026-11-21 | Remove the `REFERENCE_DATE` setting and the `future_price_date` finding. Staleness is always measured from the dataset's latest valid `price_date`. |
| 2026-11-21 | **Resolve is done as it is.** Resolution stays in `service.search` behind `GET /api/companies`: every match is returned, the analyst always chooses, and `/api/comps?target=` takes a key only. No separate `resolve.py`, no automatic resolution. |
| 2026-11-21 | **Three distinct API roles.** (1) `GET /api/companies/{key}`: exact lookup by `COUNTRY:TICKER`, **case-insensitive**; record `id`s are not accepted. (2) `GET /api/companies?q=`: text matching on key, ticker and names, kept for picking a target and documented as not similarity. (3) A separate retrieval (peers) endpoint, company key → `k` similar companies with explanations, ships with stage 4. It is in addition to `/api/comps`, which remains the comps-table endpoint and does not replace it. Every endpoint gets a Swagger description. |
| 2026-11-21 | Sequencing: the Swagger descriptions and this contract wording land first. The peers endpoint is added to `API.md` (next to the existing `/api/comps` section) in stage 4's contract PR. Whether comps take a free-text query is decided separately. *(Decided 2026-11-22: key only.)* |
| 2026-11-22 | **The grader runs a hidden dataset of the same format.** The supplied `data/` is a pre-test only. No rule, threshold or "this never happens" claim is calibrated on it alone; cases it lacks are covered by synthetic fixtures. |
| 2026-11-22 | **One company → one exchange → one country.** Each country is assumed to have one stock exchange, so `country:ticker` identifies a listing. The same ticker in two countries means two different companies. Listed in README Assumptions. |
| 2026-11-22 | **Share classes are merged into one issuer in ingestion** (one entity, one comps row). Two keys merge when they are in the same country (never `*`), have different tickers, and their latest records agree on every issuer-level field: `description`, `sector`, `industry`, `sub_industry`, `fiscal_year_end`, `reporting_currency`, `units`, `price_date`, `total_debt`, `cash`, `revenue`, `ebitda`, `net_income`. Ticker, name, price, price currency and shares may differ. A merge needs a non-empty description and at least one financial value, so two near-empty records never merge on missing data. Ticker look-alikes (`ABC.A` / `ABC.B`) with different financials are not merged. |
| 2026-11-22 | **Merging uses a disjoint-set union (DSU).** Every key starts as its own parent; each merge rule unions pairs; after all unions each set is re-rooted at its shown key. Every key keeps a parent pointer, so looking up any class key resolves to its issuer. Documented in the README's *Share classes* section, added with the implementation. |
| 2026-11-22 | **Shown key** of a merged issuer = the class with the largest market value (price × shares); a class whose value can't be computed ranks last; ties go to the alphabetically first key. Text fields come from that class; every class name is an alias. |
| 2026-11-22 | **Issuer market cap = sum over share classes of price × shares** (each class converted to the dataset currency). Classes with identical price, price currency and shares are the same shares listed twice and are counted once, with a finding. If any counted class lacks a usable price or share count, market cap (and everything built on it) is missing, never a partial sum. Debt, cash, revenue, EBITDA and net income are counted once. |
| 2026-11-22 | **Near-duplicates (retrieval).** Two issuers whose descriptions are identical after normalizing case and whitespace, or whose description TF-IDF cosine is ≥ 0.95, are excluded from each other's peer lists with a finding naming the score. *(Clarified 2026-11-22: neither can be the other's peer; when both are candidates for one target, the higher-ranked one is kept. The "finding" is the request's `skipped` entry, whose `detail` names the score.)* |
| 2026-11-22 | **Peer selection walks the full ranking until it has k peers.** It skips the target, the target's near-duplicates, analyst exclusions, and any candidate that is a near-duplicate of a peer already chosen (the higher-ranked one is kept). Each skip carries a reason. If the ranking runs out, it returns fewer peers with `requested_k`, `returned_k` and the reasons; it never pads. |
| 2026-11-22 | Sequencing: the API contract for share classes lands first (this PR), then the ingestion/finance implementation with the README's DSU section and `docs/ingestion.md` update, then stage 4 (retrieval). |
| 2026-11-22 | **No runtime additions.** The input files (`companies.json`, `fx_rates.json`) are the whole dataset. The manual-addition feature (`/api/ingest/*`, the "Add company" form, `origin`, `manual_additions`) is dropped, so the snapshot is built once at start-up and never swapped. Contract first (this PR); code and UI removal follow. |
| 2026-11-22 | **Retrieval approach: TF-IDF cosine on descriptions is served first**, then measured. BM25 is not pursued separately (lexical like TF-IDF; little to gain on short, uniform descriptions). Local sentence embeddings are the next candidate, adopted only if the eval shows TF-IDF missing paraphrased peers. Retrievers stay swappable behind the `Retriever` interface. |
| 2026-11-22 | TF-IDF baseline: fitted at snapshot build on every issuer with a description; lower-case, English stop words, unigrams, sublinear TF, L2-normalized; cosine similarity; ties ordered by key. Any change to these settings comes with an eval result. |
| 2026-11-22 | **Country phrases stay in descriptions** ("based in the United States"). The eval includes cross-country peer pairs to check whether geography leaks into the ranking; nothing is stripped on the strength of the pre-test file's phrasing. |
| 2026-11-22 | **No usable description.** Target: no peers, with a `note` (no data rather than wrong data). Candidate: never ranked; listed in `skipped` as `no_description`. |
| 2026-11-22 | **`/api/comps` takes a company key only** (share-class keys resolve). Free text goes through `GET /api/companies?q=`: one match goes straight to comps, several let the analyst choose. `/api/peers` is the similarity endpoint (retrieval only); comps reuse its selection. |
| 2026-11-22 | **Retrieval eval uses ranking metrics**, not METEOR (which scores generated text): graded 0–3 relevance labels on synthetic fixtures, nDCG@k as the main metric, plus precision@k and recall@k, with separate dev and held-out targets. |
| 2026-11-22 | Stage 4: the owner allowed the implementation PR to be stacked on the unmerged contract PR. Owner wants to be asked at each stage before it is built. |
| 2026-11-22 | **Retrieval eval design.** Synthetic universe hand-written with planted hard cases (paraphrase, cross-country, mislabelled, boilerplate, geo trap, duplicate listing); each company's true business is fixed before any score is run and labels follow from it by the 0–3 rubric. Report nDCG@5/@10 (main), precision and recall at both cut-offs, per-tag breakdowns and a geography lift. Targets split 50/50 into dev and held-out; held-out is scored only when a configuration is final. Precision/recall count label 3 (same business) as relevant. |
| 2026-11-21 | **Updated:** UI headings and labels use Title Case (e.g. “Data & Integrity”, “Dataset Health”), superseding the earlier sentence-case choice. Preserve acronyms, company names and exact technical identifiers. |

## 5. Directory map

Items marked *(planned)* don't exist yet. Update this table when you add or remove a directory.

| Path | Purpose |
|---|---|
| `AGENTS.md` | This file: working rules, architecture, decisions. |
| `README.md` | Setup and running, how to point at another data file, how to request a comps table, assumptions, AI usage, ranked future work. |
| `DESIGN.md` *(planned)* | Scope, the definition of a relevant peer, key decisions and alternatives, data problems and how each was handled, acceptance criteria. |
| `TIMELOG.md` *(planned)* | Rough breakdown of the time actually spent. |
| `pyproject.toml` | Python package and pinned dependencies (`.[dev]` adds the test, lint and type-check tools; ruff and mypy are configured here). |
| `Makefile` | Developer shortcuts: `install`, `lint`, `format`, `typecheck`, `test`, `check`. |
| `.pre-commit-config.yaml` | Optional local hooks: ruff check, ruff format, and nbstripout for notebook outputs. |
| `.github/workflows/` | CI, one concern per workflow: `lint`, `typecheck`, `tests` (3.11 and 3.12, with coverage), `repo-hygiene`. |
| `src/comps/` | The Python service package. |
| `src/comps/config.py` | Settings from env vars: `DATA_DIR`, staleness threshold. |
| `src/comps/models.py` | Shared plain data types (entity, observation, finding, metric value). This is the contract between stages; change it with care. |
| `src/comps/ingest.py` | Load, validate, and normalize to USD; entity resolution by `country:ticker`; findings. |
| `src/comps/issuers.py` | Share-class merge: a disjoint-set union groups listings with identical issuer-level data into one issuer, re-rooted at the shown key; `Dataset.parents` maps every listing key to it. |
| `src/comps/quality.py` | Checks across companies, on issuers: shared names, stale price dates. (The derived label-conflict warning is planned; it needs retrieval.) |
| `src/comps/finance.py` | Glossary formulas, ok/NM/missing states, peer summary statistics, display rounding. |
| `src/comps/retrieval/` | `Retriever` / `Index` interface (`base.py`), the served TF-IDF ranker (`tfidf.py`), and the near-duplicate test and k-filling peer selection (`select.py`). |
| `docs/retrieval.md` | How peers are chosen: index, walk and skip reasons, evidence, example, known gaps. |
| `src/comps/service.py` | Builds the immutable snapshot (dataset, metrics, retrieval index) at start-up, and holds the query logic for every endpoint: search and resolution, findings, peers (selection + evidence) and comps (peers + metrics + peer-only summary). |
| `src/comps/api.py` | FastAPI adapter for `docs/API.md`. It serves the read-only endpoints, peers and comps (JSON and CSV); handlers only parse and serialise. |
| `docs/pipeline.md` | Living overview of the stages, their status, and the data passed between them. Update it whenever a stage changes. |
| `docs/ingestion.md` | Ingestion and quality steps, rules, findings catalogue, assumptions, with worked examples. |
| `docs/finance.md` | Formulas, ok/NM/missing statuses, rounding and display, summary statistics, with worked examples. |
| `docs/API.md` | HTTP contract shared by the backend and the UI. Change it in its own PR, before the code that depends on it. |
| `scripts/dev/` | Developer notebooks and scripts for exploring modules against a local `DATA_DIR`. Commit notebooks with outputs cleared, because outputs would contain the supplied data. |
| `web/` | Next.js + shadcn/ui front end, currently running on synthetic mocks. It talks to the API over HTTP only. |
| `tests/` | Pytest suite using synthetic data only (finance, ingestion, resolution, retrieval invariants, API). |
| `tests/fixtures/planted_defects/` | End-to-end acceptance fixture: a synthetic universe with one planted defect per company, and the hand-derived `expected.json` that `tests/test_planted_defects.py` must match exactly. |
| `eval/fixtures/retrieval/` | Synthetic retrieval universe, its builder (`build_fixture.py`) and graded relevance labels (0–3 rubric), split into dev and held-out targets. |
| `eval/retrieval_eval.py`, `eval/README.md` | The retrieval eval (nDCG@k, precision@k, recall@k, per-tag, geography lift) and how to run and read it. |
| `eval/results/` | Machine-readable results for each evaluated configuration, plus interpretations. `local_*` files (from the real data) are git-ignored. |
| `Dockerfile`, `docker-compose.yml`, `scripts/start.sh` | `make start DIR=...` validates the data folder and runs the API (port 8000) and web (port 3000) containers. Data is mounted read-only. |

## 6. Commands

```bash
uv venv -p 3.11 .venv && uv pip install -e '.[dev]'   # local setup
.venv/bin/pytest                                     # tests
make check                                           # lint, typecheck and tests (what CI runs)
make format                                          # apply ruff fixes and formatting
pre-commit install                                   # optional: ruff and nbstripout on each commit
uv pip install -e '.[notebook]'                      # dev notebooks (jupyterlab, pandas)
DATA_DIR=~/Downloads/genios-takehome/data .venv/bin/jupyter lab scripts/dev/ingestion.ipynb
make start DIR=~/Downloads/genios-takehome/data      # API + web via docker compose; make stop to stop
make eval                                            # retrieval eval (dev split) -> eval/results/
```

Update this section as the service, evaluation, and Docker commands land.

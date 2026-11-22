# Retrieval

How the service picks a target's peers. The code is in `src/comps/retrieval/` (the ranker, the near-duplicate test and the k-filling walk) and `src/comps/service.py` (evidence and comps assembly). The rules are owner decisions in AGENTS.md §4 (2026-11-22). The HTTP shape is in [API.md](API.md#get-apipeers).

## What a relevant peer is

A company in a **similar line of business**, judged from its description. Size, geography and the sector/industry labels are shown as **evidence** next to each peer, so the analyst can judge them, but they never move a company up or down the ranking. Valuation multiples are never used to choose peers, because that would bias the statistics the comps table exists to compute.

## Steps

```
start-up:  issuers' descriptions ─► embedding model (EMBEDDING_MODEL) ─► one normalized vector per company
request:   target key ─► resolve (share-class keys too) ─► rank every other company by cosine ─► walk until k peers
           ─► evidence per peer ─► (comps only) metrics + peer-only summary statistics
```

### 1. Index (`embedding.py`)

At start-up every issuer with a non-empty description is embedded with a **local sentence-embedding model** (ONNX Runtime via `fastembed`; no network at runtime). Vectors are L2-normalized, so the dot product of two vectors is their cosine similarity, clamped to 0–1.

| Setting | Default | Meaning |
|---|---|---|
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors, ~90 MB) | the one model loaded per process; chosen by the eval ([eval.md](eval.md)) |
| `NEAR_DUPLICATE_THRESHOLD` | `0.88` | similarity at or above which two companies are near-duplicates (§2); must be in (0, 1]. **Tuned for MiniLM:** another model needs its own threshold |
| `MODEL_CACHE_DIR` | `~/.cache/comps-models`; `/models` in the image | where the model is downloaded to and loaded from |
| `MODEL_OFFLINE` | off; `1` in the image | never download: fail if the model is not in the cache (`1`/`true`/`yes`/`on`, any case) |

A malformed setting (e.g. `MODEL_OFFLINE=maybe`, a threshold outside (0, 1]) stops start-up with an error.

**The model is required.** The Docker image downloads it at build time (a failed download fails the build) and runs with `MODEL_OFFLINE=1`. If the model can't be loaded, start-up fails with `ModelUnavailable`; there is no fallback ranker. `make model` downloads the configured model for local runs.

Only the description is embedded: names add brand noise, and labels can be wrong (they are evidence, not inputs). EmbeddingGemma, if configured, gets its documented sentence-similarity prompt; other models get the text as is.

The ranker sits behind a small `Retriever` / `Index` interface (`base.py`): `fit(descriptions) → Index`, then `similarities(target)` and `similarity(a, b)`. Selection, the API and the evals only use this interface. The earlier TF-IDF ranker (`tfidf.py`) still implements it; the tests use it as a light stand-in so they need no model download.

### 2. Rank and walk (`select.py`)

Every other indexed company is ranked by similarity to the target (ties by key). The walk takes them in order until `k` peers are chosen, skipping, in this order of precedence:

| Reason | When |
|---|---|
| `user_excluded` | the analyst removed it (`exclude`) |
| `near_duplicate_of_target` | its description is a near-duplicate of the target's |
| `near_duplicate_of_peer` | it is a near-duplicate of a peer already chosen (the higher-ranked one stays) |

**Near-duplicates** are two descriptions that are identical after normalizing case and whitespace, or whose embedding similarity is at least **0.88**. This catches the same company listed twice under unrelated tickers, which the share-class merge (ingestion § 6) does not, because their financials differ.

The threshold errs towards keeping peers (owner decision: hiding a genuine peer is worse than showing a duplicate). 0.88 is the lowest two-decimal cut above every labelled non-duplicate: the 40 most similar pairs in the supplied pre-test data (all genuine same-business peers, the highest at 0.8732) and the synthetic dedup pairs. The threshold is specific to MiniLM: other models score non-duplicates differently (bge-small's top synthetic non-duplicate is 0.837, EmbeddingGemma's 0.872), so switching `EMBEDDING_MODEL` means re-tuning it. At 0.88 it catches 87.5% of synthetic dev duplicates and 66% of held-out ones; the misses are heavy rewordings and copies padded with a generic corporate paragraph.

Skipped candidates never count toward `k`. Every `exclude` key is reported, even when the walk ended before reaching it. A company without a usable description is never ranked (`no_description`); a target without one gets no peers and a note. If the ranking runs out, fewer peers are returned and the `note` says so: the list is never padded with weak or invented matches.

### 3. Evidence (`service.py`)

| Field | Meaning |
|---|---|
| `similarity` | description similarity to the target, 0–1, 4 dp. Higher is closer; not a probability, and not comparable across models. |
| `classification` | whether sector, industry and sub-industry equal the target's |
| `country_match` | same country (never for the unknown `*`) |
| `revenue_ratio` | peer revenue ÷ target revenue, 2 dp; null if either is missing or the target's is ≤ 0 |
| `limitations` (comps) | codes of the peer's findings that affect its metrics |

Which model produced the similarity is a server setting, not part of the response (owner decision: the analyst doesn't see what runs underneath).

### 4. Comps

`/api/comps` uses exactly the same selection, adds each company's metrics ([finance.md](finance.md)) and summarizes the three multiples over the **peers only**.

## Example

Invented universe: three banks (`BANKA`, `BANKB`, and `TWIN`, whose description is `BANKA`'s with different punctuation), a steel mill and a software company. Peers for `BANKA` with `k = 2`:

| | Company | Why |
|---|---|---|
| skipped | `TWIN` | `near_duplicate_of_target`: the same text once case, spacing and punctuation are ignored |
| 1 | `BANKB` | highest similarity: another deposit-taking lender |
| 2 | the closer of `SOFT` / `STEEL` | unrelated businesses score low but are still ranked; there is no similarity floor |

With `k = 10`, three peers come back with the note "Only 3 of the 10 requested peers…".

## Cost

Measured on a laptop CPU (experiments 2–6, [eval.md](eval.md)): embedding 90 companies at start-up takes about 4–5 s with MiniLM (320 short texts about 9 s); a peers request takes about 1.5 ms (p95 under 2 ms), faster than TF-IDF's ~9 ms because the vectors are dense and small. The API process uses about 350–490 MB of memory (342–365 MB in experiment 6); the image is about 1 GB.

## How it is tested

`tests/test_retrieval.py` checks the index, each skip reason and its precedence, exclusions, running out, the no-description cases, ties, the endpoints (JSON and CSV), the errors, the settings, that a missing model stops start-up, and invariants (a target is never its own peer; no repeats; near-duplicates never both appear).

Ranking quality is measured by the eval ([eval.md](eval.md)), which runs the served pipeline as a black box over HTTP on synthetic fixtures and scores the output against graded labels.

## Known gaps

- **Geography leaks more than with TF-IDF.** When the ranker is wrong, the wrong peer shares the target's country more often than chance (lift about 2.4 vs 1.5 for TF-IDF), because descriptions say "based in …". Overall accuracy on those cases still rose (geo_trap nDCG@10 0.62 vs 0.31). Stripping country phrases is untested.
- **Reworded duplicate listings** below 0.88 are shown as peers (see §2).
- The derived label-conflict warning (a company whose description neighbours disagree with its label) is not built yet.

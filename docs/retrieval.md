# Retrieval

How the service picks a target's peers. The code is in `src/comps/retrieval/` (the ranker, the near-duplicate test and the k-filling walk) and `src/comps/service.py` (evidence and comps assembly). The rules are owner decisions in AGENTS.md §4 (2026-11-22). The HTTP shape is in [API.md](API.md#get-apipeers).

## What a relevant peer is

A company in a **similar line of business**, judged from its description. Size, geography and the sector/industry labels are shown as **evidence** next to each peer, so the analyst can judge them, but they never move a company up or down the ranking. Valuation multiples are never used to choose peers, because that would bias the statistics the comps table exists to compute.

## Steps

```
snapshot build:  issuers' descriptions ─► TF-IDF index (ranker) + near-duplicate test
request:         target key ─► resolve (share-class keys too) ─► rank every other company ─► walk until k peers
                 ─► evidence per peer ─► (comps only) metrics + peer-only summary statistics
```

### 1. Index (`tfidf.py`)

At snapshot build, every issuer with a description is indexed with TF-IDF: lower-case, English stop words removed, single words, sublinear term frequency, rows L2-normalized, so the dot product of two rows is their cosine similarity (0–1). A description made only of stop words has no usable term and is left out, like an empty one.

The ranker sits behind a small `Retriever` / `Index` interface (`base.py`): `fit(descriptions) → Index`, then `similarities(target)`, `similarity(a, b)` and `shared_terms(a, b)`. Selection, the API and the evals only use this interface, so another ranker (for example sentence embeddings) can be swapped in without touching them.

### 2. Rank and walk (`select.py`)

Every other indexed company is ranked by similarity to the target (ties by key). The walk takes them in order until `k` peers are chosen, skipping, in this order of precedence:

| Reason | When |
|---|---|
| `user_excluded` | the analyst removed it (`exclude`) |
| `near_duplicate_of_target` | its description is a near-duplicate of the target's |
| `near_duplicate_of_peer` | it is a near-duplicate of a peer already chosen (the higher-ranked one stays) |

**Near-duplicates** are two descriptions that are identical after normalizing case and whitespace, or whose TF-IDF cosine is at least 0.95. This catches the same company listed twice under unrelated tickers, which the share-class merge (ingestion § 6) does not, because their financials differ.

Skipped candidates never count toward `k`. Every `exclude` key is reported, even when the walk ended before reaching it. A company without a usable description is never ranked (`no_description`); a target without one gets no peers and a note. If the ranking runs out, fewer peers are returned and the `note` says so: the list is never padded with weak or invented matches.

### 3. Evidence (`service.py`)

| Field | Meaning |
|---|---|
| `similarity` | cosine to the target, 4 dp. Not a probability. |
| `shared_terms` | up to 5 terms in both descriptions, ranked by the product of their TF-IDF weights |
| `classification` | whether sector, industry and sub-industry equal the target's |
| `country_match` | same country (never for the unknown `*`) |
| `revenue_ratio` | peer revenue ÷ target revenue, 2 dp; null if either is missing or the target's is ≤ 0 |
| `limitations` (comps) | codes of the peer's findings that affect its metrics |

### 4. Comps

`/api/comps` uses exactly the same selection, adds each company's metrics ([finance.md](finance.md)) and summarizes the three multiples over the **peers only**.

## Example

Invented universe: three banks (`BANKA`, `BANKB`, and `TWIN`, whose description is `BANKA`'s with different punctuation), a steel mill and a software company. Peers for `BANKA` with `k = 2`:

| | Company | Why |
|---|---|---|
| skipped | `TWIN` | `near_duplicate_of_target` (description cosine 1.00: the same words, only the punctuation differs) |
| 1 | `BANKB` | highest cosine; shared terms such as `bank`, `deposit`, `mortgages`, `loans` |
| 2 | `SOFT` | cosine 0, like `STEEL`; ties are ordered by key |

With `k = 10`, three peers come back (`BANKB`, `SOFT`, `STEEL`) with the note "Only 3 of the 10 requested peers…".

## How it is tested

`tests/test_retrieval.py` checks the index, each skip reason and its precedence, exclusions, running out, the no-description cases, ties, the endpoints (JSON and CSV), the errors, and invariants (a target is never its own peer; no repeats; near-duplicates never both appear).

Ranking quality is measured separately by the retrieval eval ([eval/README.md](../eval/README.md)): graded relevance labels on a synthetic universe, nDCG@k, precision@k and recall@k. Current result (dev): nDCG@10 0.730; strong on plain, cross-country and mislabelled companies, weak on paraphrased (0.40) and boilerplate-heavy (0.28) descriptions. See [the interpretation](../eval/results/retrieval_tfidf_v1_dev.md).

## Known gaps

- The ranker sees only descriptions. Paraphrases that share no words are missed; whether this matters is what the eval will show (sentence embeddings are the next candidate).
- Country phrases in descriptions ("based in the United States") are kept; the eval checks whether they leak geography into the ranking.
- The derived label-conflict warning (a company whose description neighbours disagree with its label) is not built yet.

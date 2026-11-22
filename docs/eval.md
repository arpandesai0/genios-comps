# Evaluation

How the retrieval stage is measured, and how each measurement is recorded. The code is in `eval/`. The rules are owner decisions in AGENTS.md §4 (2026-11-22): measure what is served, use ranking metrics with graded labels, keep separate dev and held-out targets, and never present an estimate as a measurement.

## What is measured

The **served** peer selection: `comps.service.find_peers`, with k = 10. The eval builds a snapshot from the fixture files through the same ingestion, issuer merge and index as the API, so it measures exactly what `/api/peers` and `/api/comps` return, near-duplicate skips included.

```
eval/fixtures/retrieval/*.json ─► build_snapshot ─► find_peers(target, 10) for each target in a split
                               ─► score against labels.json ─► result JSON (results/) ─► experiment log line
```

**These are measurements on a synthetic universe, not on the hidden dataset.** The same agent wrote the universe and the ranker, so absolute numbers are optimistic. Comparisons between configurations, and between hard-case tags, are the useful part.

## Fixture

`eval/fixtures/retrieval/build_fixture.py` writes `companies.json`, `fx_rates.json` and `labels.json`. Every company is invented. A test fails if the committed files drift from the builder.

- **57 companies** in 13 businesses and 7 sectors, plus one duplicate listing (`US:WNDX`, a second listing of `US:WNDA`).
- Each company has a **true business**, fixed before any score was run. Relevance follows mechanically from it:

  | Label | Meaning |
  |---|---|
  | 3 | same business |
  | 2 | same industry, different business (e.g. regional bank vs mortgage lender) |
  | 1 | same sector, different industry |
  | 0 | different sector |

- The sector and industry labels in the records are what a data file would say. For companies tagged `mislabelled` they are deliberately wrong. Relevance never uses them.
- **Hard-case tags:**

  | Tag | What it tests |
  |---|---|
  | `paraphrase` | few words shared with true peers |
  | `cross_country` | true peers in other countries |
  | `mislabelled` | wrong dataset labels |
  | `boilerplate` | a long generic corporate paragraph |
  | `geo_trap` | the same country phrase as unrelated companies |

- **Aliases.** A returned alias scores as its original, and only the first of the two counts. The service should skip the duplicate as a near-duplicate, and `duplicate_listing_returned` counts the times it didn't.

### Splits

- **50/50, dev (29) / held-out (28).** Within each business the halves alternate, so both cover every business.
- **Ties are broken to spread the tags.** A tie goes to the half with fewer companies carrying the same hard-case tags, giving: paraphrase 7 / 6, boilerplate 4 / 2, geo_trap 5 / 3, mislabelled 2 / 2, cross_country 11 / 11.
- **Iterate on dev only.** Held-out is scored once, when the owner calls a configuration final.
- **Held-out is not independent of dev.** Both come from the same businesses, the same author and the same boilerplate paragraph. Held-out guards against tuning to individual dev companies, not against tuning to this universe's style.

## Metrics

For a target, `ranked` is the list of returned peers (aliases mapped to their original). `rel(c)` is the label of candidate `c`.

| Metric | Definition |
|---|---|
| **nDCG@k** (main) | DCG of the returned top k ÷ DCG of the ideal top k over all labelled candidates. Gain is `2^rel − 1`; the discount is `log2(rank + 1)`. 0 when nothing is relevant. |
| **precision@k** | Share of the k slots holding a same-business peer (`rel = 3`). An empty slot (fewer than k returned) counts as a miss. Reported with its **ceiling**, `min(#relevant, k) / k`, because a target has only 3–4 same-business companies. |
| **recall@k** | Same-business peers in the top k ÷ all same-business candidates. |
| **Per-tag** | Mean nDCG@10 and precision@10 over the targets carrying each tag. A target can carry several tags. |
| **Geography lift** | The same-country share among irrelevant (rel 0) peers returned, divided by the same-country share among all irrelevant candidates. Above 1 means country words pull unrelated companies up. |

Cutoffs are @5 and @10. All values are means over the split's targets, rounded to 4 dp.

**Worked example (nDCG@3).** Labels `{A: 3, B: 2, C: 0, D: 1}`, returned `[B, C, A]`.
- DCG = (2²−1)/log2 2 + 0/log2 3 + (2³−1)/log2 4 = 3 + 0 + 3.5 = 6.5.
- Ideal order `[A, B, D]`: 7/1 + 3/1.585 + 1/2 = 9.393.
- nDCG@3 = 6.5 / 9.393 = **0.692**.

## Running

```bash
make eval                                   # dev split -> eval/results/retrieval_tfidf_v1_dev.json
make experiment DESC="what this run tests"  # the same, plus one line in eval/experiments.jsonl
.venv/bin/python eval/experiments.py        # the experiment log as a table
PYTHONPATH=src .venv/bin/python eval/retrieval_eval.py --split held_out   # only once a configuration is final
```

## Experiment log

`eval/experiments.jsonl` holds one JSON line per logged run. It is append-only: lines are never edited or removed, and a wrong run is corrected by a later run whose description says so.

| Field | Content |
|---|---|
| `experiment` | Number, assigned automatically as last + 1. |
| `date` | UTC, to the second. |
| `description` | What the run tests. Required; a blank one is rejected before anything is written. |
| `eval` | Which eval (`retrieval`). |
| `git` | `commit`, `branch` (null when detached), `dirty` and `dirty_paths`. A path is dirty if it has uncommitted changes under `src/`, `eval/`, `pyproject.toml` or `requirements.lock`, not counting the log and the result file the run writes itself. All four are null when git can't answer, so "unknown" is never recorded as "clean". |
| `inputs` | Method name and version (the version pins the ranker settings: any settings change bumps it), split, fixture path, `dataset_version` (hash of `companies.json` and `fx_rates.json`), `labels_sha`, cutoffs, relevance threshold, near-duplicate cosine, and the Python, numpy and scikit-learn versions. |
| `results` | Targets, overall metrics, per-tag metrics, duplicate listings returned, geography lift. |
| `result_file`, `result_sha` | Where the full per-target result was written, and its hash. That file is overwritten by later runs; the hash tells whether it still holds this run. Any run can be reproduced from its commit. |

Workflow for a change to what is served:

1. Commit the change.
2. Run `make experiment DESC="..."` on that clean tree. The entry records the commit.
3. Commit the updated result file, its interpretation and the new log line in a follow-up commit in the same PR.

A test checks that the committed log is numbered 1..n and that every entry is complete and came from a clean tree. The table marks a dirty run `*` and an unknown git state `?`.

## Results

| # | Configuration | Split | nDCG@5 | nDCG@10 | P@10 (ceiling) | R@10 | Interpretation |
|---|---|---|---|---|---|---|---|
| 1 | `tfidf-description` v1 | dev | 0.657 | 0.697 | 0.269 (0.345) | 0.787 | [retrieval_tfidf_v1_dev.md](../eval/results/retrieval_tfidf_v1_dev.md) |

Highlights of experiment 1:
- **By tag (nDCG@10):** plain descriptions score 0.838 and mislabelled 0.814. The weak cases are paraphrase (0.614) and boilerplate (0.337).
- **Geography lift is 1.44.** Country words pull some unrelated companies up.
- **Duplicates:** the duplicate listing was never returned.
- **Open owner decisions:** whether and how to act on paraphrase, boilerplate and geography.

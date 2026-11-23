# Evaluation

**Served: `sentence-transformers/all-MiniLM-L6-v2` embeddings on business descriptions (each company's own names removed), near-duplicate threshold 0.88 on the descriptions as supplied** (experiment 11). Removing names lifted the look-alike-names fixture from 0.757 to 0.923 nDCG@10 on dev (0.782 to 0.884 held-out), with the other fixtures flat or better and no double listings; see [results/retrieval_business_descriptions.md](results/retrieval_business_descriptions.md). The table below is the earlier model choice; MiniLM replaced TF-IDF after these runs. nDCG@10 is the main metric (1.0 = every true peer, in the best order).

| # | Configuration | Vector size | nDCG@10 independent fixture (dev / held-out) | nDCG@10 own fixture (dev / held-out) | Dedup recall ceiling, dev (best cut with no false duplicate) | Both copies of a company in one list (independent dev) | Start-up, 90 cos. | Request latency mean / p95 / max | Memory |
|---|---|---|---|---|---|---|---|---|---|
| 2 / 7 | TF-IDF v1 (previous served) | sparse | 0.459 / 0.428 | 0.697 / 0.711 | 0.656 | 1 | 2.0 s | 9.1 / 10.1 / 10.4 ms | 155 MB |
| 3 | all-MiniLM-L6-v2, threshold 0.95 | 384 | 0.726 / – | 0.836 / – | 0.938 | 5 | 4.5 s | 1.5 / 1.8 / 2.7 ms | 487 MB |
| 4 | bge-small-en-v1.5, threshold 0.95 | 384 | 0.692 / – | 0.822 / – | **1.000** | 3 | 6.6 s | 1.5 / 1.8 / 3.0 ms | 523 MB |
| 5 | EmbeddingGemma-300M, threshold 0.95 | 768 | 0.682 / – | **0.847** / – | 0.656 | 5 | 23.8 s | 1.6 / 1.9 / 3.8 ms | 575 MB |
| **6** | **all-MiniLM-L6-v2, threshold 0.88 (served)** | **384** | **0.729 / 0.684** | 0.836 / 0.828 | 0.938 | **0** | 3.6 s | 1.3 / 2.2 / 3.4 ms | 365 MB |

- **Embeddings beat TF-IDF on every fixture and split.** On the independent fixture, written by a different model (Sonnet) that never saw the ranker, MiniLM scores +0.27 on dev and +0.26 on held-out. Its biggest gains are on paraphrased descriptions (0.47 → 0.78) and boilerplate-heavy ones (0.31 → 0.68).
- **MiniLM was chosen** because it is best on the independent fixture, which is the less biased one, and it's the smallest and fastest of the three. EmbeddingGemma wins on the fixture written by the same agent as the ranker, but takes about 82 s to embed 320 texts, too slow for the 60 s start-up budget at around 500 companies.
- **The dedup column is a ceiling**: the most duplicates any threshold could catch without a false one. At the served 0.88, MiniLM catches 87.5% of synthetic duplicates on dev and 66% on held-out, with no false duplicate in either (dev logged in experiment 8; held-out from rescoring experiment 6 at 0.88).
- **The 0.88 threshold** is the lowest two-decimal cut above every labelled non-duplicate in the supplied pre-test data (its 40 most similar pairs are all genuine peers, the highest at 0.8732) and in the synthetic pairs. It is tuned for MiniLM. At 0.88 MiniLM never put both copies of a company in one peer list (0 on dev and on held-out); at 0.95 it did so 5 times.
- **Held-out** was scored once, for the final configuration and for the TF-IDF reference (experiments 6 and 7).
- **Known cost: geography leaks more.** When an embedding model gets a peer wrong, the wrong peer is more often from the target's country (lift 2.4 vs TF-IDF 1.5 on the independent fixture). Accuracy on those targets still doubled (0.31 → 0.61).
- **Scope of these numbers.** They come from synthetic fixtures and are not measurements on the hidden dataset. Latency is measured over HTTP on a laptop CPU. The "both copies" column is computed by rescoring each run's committed output (`score.py`). The full interpretation is in [results/retrieval_embeddings.md](results/retrieval_embeddings.md), and the method is in [docs/eval.md](../docs/eval.md).

## How it works

The eval treats the pipeline as a black box. `run.py` checks out a commit in a temporary git worktree, starts that commit's API on a fixture's input files, calls `GET /api/peers` for every query, and saves the responses as served. `score.py` then scores them against the fixture's golden labels without importing the pipeline. Each run is appended to `experiments.json` under a new experiment number. The commit is only metadata, so one commit can be run with several settings.

```bash
make experiment DESC="what this run tests" [COMMIT=<sha>] [MODEL=<embedding model>] [HELD_OUT=1]
.venv/bin/python eval/experiments.py        # the experiment log as a table
make model                                  # download the configured embedding model
```

| Path | What |
|---|---|
| `run.py` | Runs the commit's pipeline over HTTP on each fixture, captures the output, scores it, logs the run. |
| `score.py` | Metrics on captured output: nDCG / precision / recall, per-tag, duplicates, geography lift, dedup recall. |
| `experiments.py`, `experiments.json` | The append-only experiment log (pretty-printed JSON) and its table view. Never edit past entries. |
| `runs/<NNN>/` | Captured `/api/peers` responses of each logged run, so any score can be recomputed without re-running. |
| `fixtures/retrieval/` | 57-company universe with 0–3 labels, written by the same agent as the ranker. |
| `fixtures/independent/` | 90-company universe, 18 businesses, written independently by a different model (Sonnet). |
| `fixtures/lookalike/` | 70-company universe whose unrelated companies share invented name stems ("Velorin Air", "Velorix Fibre"), written independently by Sonnet. |
| `fixtures/dedup/` | 160 labelled description pairs (64 duplicates) for the near-duplicate rule, also written by Sonnet. |
| `results/` | Interpretations; `local_*` files come from the supplied data and are git-ignored. |

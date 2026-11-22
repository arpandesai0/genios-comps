# Evaluation

`retrieval_eval.py` scores the **served** peer selection (`comps.service.find_peers`) against graded relevance labels on a synthetic universe. `experiments.py` keeps an append-only log of every logged run.

**Full description:** [docs/eval.md](../docs/eval.md). It covers the fixture, the labels rubric, the splits, the metric definitions, the experiment log fields and workflow, and the results.

```bash
make eval                                   # dev split -> results/retrieval_tfidf_v1_dev.json
make experiment DESC="what this run tests"  # the same, plus one line in experiments.jsonl
.venv/bin/python eval/experiments.py        # the experiment log as a table
PYTHONPATH=src .venv/bin/python eval/retrieval_eval.py --split held_out   # only once a configuration is final
```

| Path | What |
|---|---|
| `retrieval_eval.py` | Runs the eval: metrics, per-tag means, geography lift; `--out` writes the full result, `--log` appends to the log. |
| `experiments.py`, `experiments.jsonl` | The experiment log: writer, table view, and the log itself. Never edit past lines. |
| `fixtures/retrieval/` | `build_fixture.py` and the files it writes (`companies.json`, `fx_rates.json`, `labels.json`). Every company is invented. |
| `results/` | One JSON result and one interpretation per evaluated configuration. A test fails if the committed dev result is stale. `local_*` files (real data) are git-ignored. |

## Results

| # | Configuration | nDCG@10 (dev) | Interpretation |
|---|---|---|---|
| 1 | `tfidf-description` v1 | 0.697 | [retrieval_tfidf_v1_dev.md](results/retrieval_tfidf_v1_dev.md) |

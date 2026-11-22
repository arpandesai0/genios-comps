# Evaluation

## Retrieval

`retrieval_eval.py` scores the **served** peer selection (`comps.service.find_peers`) against graded relevance labels on a synthetic universe. It runs the full pipeline from the files, so it measures exactly what the API returns.

```bash
make eval                                                        # dev split -> eval/results/retrieval_tfidf_v1_dev.json
PYTHONPATH=src .venv/bin/python eval/retrieval_eval.py --split held_out   # only once a configuration is final
```

### Experiment log (`experiments.jsonl`)

Every eval run worth keeping is appended to `experiments.jsonl`, one JSON line per run. Lines are never edited or removed. A wrong run is corrected by a later run whose description says so.

```bash
make experiment DESC="what this run tests"   # dev split: writes the result file and appends to the log
.venv/bin/python eval/experiments.py         # the log as a table
```

Each entry records:

- `experiment`: assigned automatically, one more than the last entry
- `date`: UTC
- `description`
- `git`: commit, branch, and whether `src/`, `eval/`, `pyproject.toml` or `requirements.lock` had uncommitted changes (`dirty`, `dirty_paths`)
- `inputs`: method name and version, split, fixture, `dataset_version`, the labels file hash, cutoffs, the relevance threshold, the near-duplicate cosine, and the Python, numpy and scikit-learn versions
- `results`: overall metrics, per-tag metrics, duplicate listings returned, and the geography lift
- `result_file`: the full per-target result, if one was written

Commit the code first and then run the experiment, so `git.commit` names code that reproduces the result. Commit the new log line with the change it measures.

### Fixture (`fixtures/retrieval/`)

- `build_fixture.py` writes `companies.json`, `fx_rates.json` and `labels.json`. Every company is invented. A test fails if the committed files drift from the builder.
- 57 companies in 13 businesses, 7 sectors, plus one duplicate listing. Each company has a **true business**, fixed before any score was run. Relevance follows mechanically from it:

  | Label | Meaning |
  |---|---|
  | 3 | same business |
  | 2 | same industry, different business (e.g. regional bank vs mortgage lender) |
  | 1 | same sector, different industry |
  | 0 | different sector |

- The dataset labels in the records are what a data file would say. For companies tagged `mislabelled` they are deliberately wrong; relevance never uses them.
- Hard-case tags: `paraphrase` (few words shared with peers), `cross_country`, `mislabelled`, `boilerplate` (a long generic corporate paragraph), `geo_trap` (the same country phrase as unrelated companies). `aliases` maps the duplicate listing to its original; it must never be returned as a peer.
- Splits: 50/50 dev / held-out (29 / 28). Within each business the halves alternate, so both cover every business; ties go to the half with fewer companies of the same hard-case tags, so tags are spread evenly (paraphrase 7 / 6, boilerplate 4 / 2, geo_trap 5 / 3, mislabelled 2 / 2, cross_country 11 / 11). Iterate on dev only; score held-out once a configuration is final.
- **Held-out is not independent of dev.** Both halves come from the same 13 businesses, the same author and the same boilerplate paragraph. It guards against tuning to individual dev companies, not against tuning to this universe's style.

### Metrics

- **nDCG@5 and nDCG@10** (main): gain 2^rel − 1, log2 discount, ideal ranking over all labelled candidates.
- **precision@k**: share of the k slots holding a same-business peer (label 3); empty slots count as misses. Reported with its ceiling.
- **recall@k**: same-business peers in the top k / all same-business candidates.
- Per-tag nDCG@10 and precision@10, and a **geography lift**: the same-country share among irrelevant peers returned divided by that share among all irrelevant candidates (above 1 means country words pull unrelated companies up).

### Results

Each evaluated configuration has a JSON result and a short interpretation in `results/`. A test recomputes the dev result and fails if the committed file is stale, so any change to what is served must come with an updated result.

| Configuration | nDCG@10 (dev) | Interpretation |
|---|---|---|
| `tfidf-description` v1 | 0.697 | [retrieval_tfidf_v1_dev.md](results/retrieval_tfidf_v1_dev.md) |

# Evaluation

How retrieval is measured and how each measurement is recorded. The code is in `eval/`; the summary table is at the top of [eval/README.md](../eval/README.md). The rules are owner decisions in AGENTS.md §4 (2026-11-22):
- measure what is served, as a black box;
- use ranking metrics with graded labels;
- keep separate dev and held-out targets;
- never present an estimate as a measurement.

## What is measured

The **served** peer selection, exactly as `GET /api/peers` returns it, with k = 10 (k = 50 for dedup). The eval doesn't import the pipeline. For each run it:

1. checks out the commit under test in a temporary **git worktree**, so uncommitted changes can never leak into a result;
2. starts **that commit's API** with `DATA_DIR` pointing at a fixture's input files from the current checkout (the same input for every commit), plus the run's settings (e.g. `EMBEDDING_MODEL`);
3. calls `GET /api/peers` for every query and saves the responses as served (`eval/runs/<NNN>/<fixture>.json`), timing each request;
4. scores the captured output against the fixture's **golden labels** (`score.py`), and appends one entry to the experiment log.

```
commit ─► worktree ─► uvicorn comps.api:app (DATA_DIR = fixture input, settings) ─► GET /api/peers × queries
       ─► eval/runs/NNN/<fixture>.json ─► score.py + golden labels ─► eval/experiments.json (entry NNN)
```

So a run is reproducible two ways:
- rescore its committed output without running anything (a test does this for every run);
- re-run its commit with its settings.

**These are measurements on synthetic universes, not on the hidden dataset.**

## Fixtures

Every company and description is invented. Each fixture has a builder script that writes its JSON files, and a test fails if the committed files drift from the builder.

| Fixture | Size | Written by | Purpose |
|---|---|---|---|
| `retrieval/` | 57 companies, 13 businesses, 7 sectors, 1 duplicate listing | the same agent that wrote the ranker | first ranking fixture; kept so runs stay comparable with experiment 1 |
| `independent/` | 90 companies, 18 businesses, 9 sectors, 2 duplicate listings | a different model (Sonnet), never shown the ranker, its scores or the first fixture | **main ranking fixture**, the less biased one |
| `dedup/` | 160 description pairs, 64 duplicates | Sonnet, same rules | the near-duplicate rule |

### Ranking fixtures

- Each company has a **true business**, fixed before any score was run. Relevance follows mechanically from it:

  | Label | Meaning |
  |---|---|
  | 3 | same business |
  | 2 | same industry, different business (e.g. regional bank vs mortgage lender) |
  | 1 | same sector, different industry |
  | 0 | different sector |

- The sector and industry labels in the records are what a data file would say. For companies tagged `mislabelled` they are deliberately wrong, and relevance never uses them.
- **Hard-case tags:**

  | Tag | What it tests |
  |---|---|
  | `paraphrase` | few words shared with true peers |
  | `cross_country` | true peers in other countries |
  | `mislabelled` | wrong dataset labels |
  | `boilerplate` | a long generic corporate paragraph (one paragraph in `retrieval/`, five different ones in `independent/`) |
  | `geo_trap` | the same country phrase as unrelated companies |
  | `jargon` | heavy industry jargon (independent only) |

- **Aliases** are second listings of a company (another ticker, lightly reworded text, different numbers so the share-class merge leaves them apart). A returned alias scores as its original, and only the first of the two counts.
- **Splits: 50/50 dev / held-out**, alternating within each business so both halves cover every business, with tags spread evenly.
  - Iterate on dev. Held-out is scored once, when the owner calls a configuration final (done in experiments 6 and 7).
  - Within a fixture, held-out shares its author and style with dev. That's why the independent fixture exists.

### Dedup pairs

Each pair is two description texts, labelled duplicate (the same company) or not.

- **Duplicates:** case and spacing only, reworded, sentences reordered, truncated, a generic paragraph added, one fact updated.
- **Hard non-duplicates:** same-business peers with similar wording, a shared boilerplate paragraph, the same sentence template, related businesses in one group.

To run the pairs through the real pipeline, `run.py` turns them into a 320-company universe (distinct numbers per record, so nothing merges). It then asks for the peers of each pair's first text, and reads the second text's similarity from the response: from `peers`, or from `skipped` if it was dropped as a near-duplicate. A second text outside the 50-peer window scores below any threshold.

## Metrics

For a target, `ranked` is the list of returned peers, with aliases mapped to their original; `rel(c)` is candidate `c`'s label.

| Metric | Definition |
|---|---|
| **nDCG@k** (main) | DCG of the returned top k ÷ DCG of the ideal top k over all labelled candidates. Gain is `2^rel − 1`; the discount is `log2(rank + 1)`. 0 when nothing is relevant. |
| **precision@k** | Share of the k slots holding a same-business peer (`rel = 3`); an empty slot is a miss. Reported with its **ceiling**, `min(#relevant, k) / k`. |
| **recall@k** | Same-business peers in the top k ÷ all same-business candidates. |
| **Per-tag** | Mean nDCG@10 over the targets carrying each tag. |
| **Duplicates** | `both_copies_returned`: both listings of one company in the same peer list, the failure dedup must prevent. `duplicate_listing_returned`: a second listing appeared at all, which is harmless on its own. |
| **Geography lift** | Same-country share among irrelevant (rel 0) peers returned ÷ same-country share among all irrelevant candidates. 1 = country has no effect; above 1 = country words pull unrelated companies up. |
| **Dedup recall at zero false duplicates** | Share of duplicate pairs scoring strictly above the best-scoring non-duplicate: the most duplicates any threshold can catch without hiding a genuine peer. Also precision and recall at a given threshold. |
| **Cost** | Service start-up (including indexing), memory (RSS) after start-up, and `GET /api/peers` latency over HTTP: min, mean, p50, p95, max (nearest-rank). |

Cutoffs are @5 and @10, and values are means over the split's targets, rounded to 4 dp.

**Worked example (nDCG@3).** Labels `{A: 3, B: 2, C: 0, D: 1}`, returned `[B, C, A]`.
- DCG = (2²−1)/log2 2 + 0/log2 3 + (2³−1)/log2 4 = 3 + 0 + 3.5 = 6.5.
- Ideal order `[A, B, D]`: 7/1 + 3/1.585 + 1/2 = 9.393.
- nDCG@3 = 6.5 / 9.393 = **0.692**.

## Running

```bash
make experiment DESC="what this run tests"                          # HEAD, served defaults, dev splits
make experiment DESC="..." COMMIT=84c6474                            # another commit
make experiment DESC="..." MODEL=BAAI/bge-small-en-v1.5               # another embedding model (one per run)
make experiment DESC="..." HELD_OUT=1                                # also score held-out (final configurations only)
.venv/bin/python eval/experiments.py                                 # the log as a table
```

The runner starts one service process at a time, with one model, and stops it before the next fixture. The code runs in this checkout's virtualenv, so a commit that needs other dependencies can't be run.

## Experiment log

`eval/experiments.json` is a pretty-printed JSON array with one entry per run. It is append-only: entries are never edited or removed, and a wrong run is corrected by a later run whose description says so. **The experiment number identifies a run.** The commit is only metadata, since one commit can be run with several settings (experiments 3–5 share one commit).

| Field | Content |
|---|---|
| `experiment`, `schema`, `date`, `description` | number (last + 1), entry format, UTC time, what the run tests |
| `commit`, `settings` | the commit run, and the service settings passed (e.g. `EMBEDDING_MODEL`) |
| `model` | the embedding model's name, vector size and download size |
| `env` | Python, numpy, scikit-learn, fastembed and onnxruntime versions |
| `inputs` | per fixture: hash of the input files, hash of the golden file, number of queries, k |
| `outputs` | per fixture: path and hash of the captured output |
| `runtime` | per fixture: start-up seconds, memory, latency statistics |
| `results` | per fixture and split: the metrics above (per-target rows stay in the captured output) |

Entry 1 predates the black-box runner: its eval imported the pipeline. It has its own fields, and the table reads both formats. Experiment 2 re-ran that commit as a black box and reproduced it exactly.

Workflow for a change to what is served:

1. Commit the change.
2. Run `make experiment` on that commit.
3. Commit the new entry, its captured output and an interpretation in `eval/results/`.

## Results

See the table at the top of [eval/README.md](../eval/README.md), and the full interpretation in [eval/results/retrieval_embeddings.md](../eval/results/retrieval_embeddings.md).
- **Embeddings beat TF-IDF everywhere.** On the independent fixture, nDCG@10 went from 0.459 to 0.729 on dev and from 0.428 to 0.684 on held-out.
- **MiniLM-L6 is served**, with a near-duplicate threshold of 0.88.
- **Earlier result:** the TF-IDF v1 interpretation is kept at [eval/results/retrieval_tfidf_v1_dev.md](../eval/results/retrieval_tfidf_v1_dev.md).

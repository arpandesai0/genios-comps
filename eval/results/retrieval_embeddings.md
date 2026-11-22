# Retrieval eval: TF-IDF v1 vs local sentence embeddings

Machine-readable results: experiments 2–7 in [`../experiments.json`](../experiments.json); captured pipeline output in `../runs/002`–`007`. Method: [docs/eval.md](../../docs/eval.md).

**What was measured:** the served `/api/peers` output of two commits, run as a black box over HTTP on fixed inputs:
- the TF-IDF commit `84c6474` (experiments 2 and 7);
- the embedding commit, with three models at `e29f320` (experiments 3–5) and the final defaults at `b7aa38c` (experiment 6).

Three fixtures:
- `retrieval_v1`: 57 companies, written by the same agent as the ranker.
- `independent`: 90 companies in 18 businesses, written by a different model (Sonnet) that never saw the ranker. **This is the main one.**
- `dedup`: 160 labelled description pairs, also written by Sonnet.

**These numbers do not come from the hidden dataset.**

## Ranking (nDCG@10, dev)

| | TF-IDF | MiniLM-L6 | bge-small | EmbeddingGemma |
|---|---|---|---|---|
| independent | 0.459 | **0.726** | 0.692 | 0.682 |
| retrieval_v1 | 0.697 | 0.836 | 0.822 | **0.847** |
| independent: paraphrase | 0.47 | **0.78** | 0.71 | 0.77 |
| independent: boilerplate | 0.31 | **0.68** | 0.59 | 0.47 |
| independent: geo_trap | 0.31 | **0.61** | 0.51 | 0.39 |
| independent: cross_country | 0.45 | **0.72** | 0.66 | 0.67 |
| independent: mislabelled | 0.42 | 0.73 | 0.71 | 0.73 |
| independent: jargon | 0.55 | 0.75 | 0.76 | **0.79** |

**Held-out**, scored once, for the final configuration (experiment 6) and the TF-IDF reference (experiment 7):

| Fixture | TF-IDF | MiniLM (0.88) |
|---|---|---|
| independent | 0.428 | **0.684** |
| retrieval_v1 | 0.711 | **0.828** |

The held-out gain matches dev: +0.26 against +0.27 on the independent fixture.

## Near-duplicates

Dedup pairs: duplicate recall at the strictest threshold that flags no non-duplicate (dev / held-out):
- TF-IDF: 0.66 / 0.72
- MiniLM: 0.94 / 0.94
- bge-small: 1.00 (dev)
- EmbeddingGemma: 0.66 (dev)

**Choosing the threshold** (owner rules: tune on the supplied pre-test data, check on synthetic pairs, and treat a false duplicate as the worse error):
1. The 40 most similar issuer pairs in the pre-test data, by MiniLM, scored from 0.873 down to 0.727. I read every one, and all 40 are genuine same-business peers: different names and tickers, sometimes different countries. The labels are in the git-ignored `local_pretest_pairs_minilm.json`.
2. The strictest non-duplicate score is therefore 0.8732 on the pre-test data, against 0.80 on the synthetic dev pairs. That gives **0.88**, the lowest cut with no false duplicate in either set.
3. On the synthetic pairs, 0.88 flags no non-duplicate in either split (precision 1.0). It catches 87.5% of duplicates on dev and 66% on held-out, against 41% and 38% at 0.95. The misses are heavy rewordings and copies padded with a generic corporate paragraph.

**Both copies of one company in one peer list** (independent fixture). The original metric, `duplicate_listing_returned`, also counted a second listing appearing *alone*, which is harmless because it stands in for its original. So `both_copies_returned` was added, computed by rescoring the committed outputs:

| | TF-IDF (0.95) | MiniLM (0.95) | bge-small (0.95) | EmbeddingGemma (0.95) | MiniLM (0.88, served) |
|---|---|---|---|---|---|
| dev | 1 | 5 | 3 | 5 | **0** |
| held-out | 1 | – | – | – | **0** |

The 0.95 threshold inherited from TF-IDF was too strict for embeddings, whose scores run higher. Tuning it removed every double listing.

## Cost

Measured on a laptop CPU (8 cores):

| | TF-IDF | MiniLM | bge-small | EmbeddingGemma |
|---|---|---|---|---|
| Start-up, 90 companies | 2.0 s | 4.5 s | 6.6 s | 23.8 s |
| Start-up, 320 texts | 2.0 s | 8.6 s | 15.7 s | 82 s |
| Latency per request, mean / p95 | 9.1 / 10.1 ms | 1.5 / 1.8 ms | 1.5 / 1.8 ms | 1.6 / 1.9 ms |
| Memory | 155 MB | 487 MB | 523 MB | 575 MB |
| Download | 0 | 90 MB | 67 MB | 1.24 GB |

- **Requests are faster with embeddings**, because a dense 384-value dot product beats sparse TF-IDF.
- **Start-up is slower**, because every description is embedded once.
- **One outlier:** experiment 6's first service start took 35.9 s. That was a cold disk read of the model, right after the laptop restarted; its other two starts took 3.6 and 4.6 s.
- **Parallel workers don't help.** Spreading the embedding over several processes was slower (MiniLM 6.4–6.7 s against 4.8–5.4 s), because ONNX Runtime already uses every core, and each worker loads its own model copy. With EmbeddingGemma this exhausted memory, so it is not used.
- **The Docker image is 973 MB** with the model baked in.

## Interpretation

- **What improved:** every hard case, most of all paraphrase, boilerplate and the shared-country-phrase trap. These are the cases where TF-IDF matched words rather than meaning. Dedup recall improved too, and with the tuned threshold no company appears twice.
- **What got worse:**
  - **Geography leak.** When MiniLM is wrong, the wrong peer shares the target's country more often than chance: lift 2.37 against TF-IDF's 1.52 on the independent fixture. On the `retrieval_v1` fixture it is similar to TF-IDF (1.54 against 1.44).
  - **Start-up, memory and image size:** about 4 s, 0.5 GB and 1 GB.
- **Why MiniLM:** it is best on the independent fixture and on the mean of both fixtures (0.781, against 0.765 for EmbeddingGemma and 0.757 for bge-small), and it is the smallest and fastest to start. EmbeddingGemma's lead on `retrieval_v1` comes from the fixture written by the same agent as the ranker, and EmbeddingGemma would miss the 60 s start-up budget.
- **Worth the complexity?** Yes. The gain (+0.26 nDCG@10 on independent held-out) is far larger than the run-to-run differences between models. The cost is one dependency (fastembed / ONNX Runtime) and a model downloaded at image build.
- **Open (owner decisions):**
  - stripping country phrases before embedding, to reduce the geography leak;
  - whether to catch heavily reworded duplicates, which would need a lower threshold and so risk hiding genuine peers.

# Retrieval eval: `tfidf-description` v1, dev split

Machine-readable result: [`retrieval_tfidf_v1_dev.json`](retrieval_tfidf_v1_dev.json). Reproduce with `make eval`. The fixture and rubric are described in [`eval/README.md`](../README.md).

**What was measured:** the served peer selection (`find_peers`, k = 10), from files through the snapshot, on 30 dev targets in a synthetic 57-company universe. **This is not a measurement on the hidden data**, and the universe was written by the same agent that wrote the ranker, so absolute numbers are optimistic. The comparisons between tags are the useful part. Held-out (27 targets) has not been scored.

## Results

| Metric | @5 | @10 |
|---|---|---|
| nDCG (main) | 0.700 | 0.730 |
| Precision (relevant = same business) | 0.440 (ceiling 0.693) | 0.273 (ceiling 0.347) |
| Recall | 0.636 | 0.792 |

Precision has a ceiling below 1 because a target has only 3–4 same-business companies in this universe.

| Hard case (tag) | Targets | nDCG@10 |
|---|---|---|
| none (plain descriptions) | 10 | **0.880** |
| mislabelled (dataset labels wrong) | 3 | 0.866 |
| cross_country | 10 | 0.816 |
| geo_trap (country phrase shared with unrelated companies) | 6 | 0.790 |
| paraphrase (few words in common with peers) | 3 | **0.401** |
| boilerplate (generic corporate paragraph) | 4 | **0.282** |

- The duplicate listing (`US:WNDX`, a second listing of `US:WNDA`) was never returned as a peer: the near-duplicate skip works.
- **Geography leak:** among irrelevant peers returned, 70% share the target's country, against 44% among all irrelevant candidates, a **lift of 1.61**. Country words ("based in Germany") pull unrelated same-country companies up, but only into slots that relevant peers have already failed to fill.

## Interpretation

- **What works:** plain descriptions, wrong dataset labels (labels are not ranking inputs, so they cannot mislead) and cross-country peers all score well. Business vocabulary dominates the ranking.
- **Paraphrase is the main weakness.** Example: `US:TRKB` ("moves retailers' pallets … using its own big rigs … billing shippers by the load") ranks a container shipper and a driller first; only one of its three trucking peers reaches the top five. Lexical matching cannot connect "big rigs" with "tractors and trailers". This is the gap sentence embeddings are designed to close.
- **Boilerplate is the worst case.** Companies whose descriptions share a long generic paragraph retrieve each other first (`US:CYBD`'s top five are all boilerplate companies from other sectors). The fixture plants the *same* paragraph in all of them, which is an extreme version of templated text. Embeddings would likely suffer too (a long shared paragraph dominates a sentence vector). Mitigations are lexical (down-weighting terms common to many descriptions, or more aggressive document-frequency limits) and need their own measurement.
- **Small samples:** 3 paraphrase and 4 boilerplate targets. The direction is clear; the exact values are not.

## Is this worth acting on?

Yes, for paraphrase: it is the expected failure of a lexical ranker, it is visible on realistic text (the pre-test descriptions are paraphrased), and it is the trigger the owner set for evaluating embeddings. Boilerplate is a separate problem that embeddings may not fix. Both are owner decisions; nothing has been changed in the served ranker.

# Retrieval eval: `tfidf-description` v1, dev split

Machine-readable result: [`retrieval_tfidf_v1_dev.json`](retrieval_tfidf_v1_dev.json). It was produced by the first in-process eval runner, since replaced (see [docs/eval.md](../../docs/eval.md)); experiment 2 reproduced it exactly with the black-box runner. The fixture and rubric are described in [`eval/README.md`](../README.md).

**What was measured:** the served peer selection (`find_peers`, k = 10), from files through the snapshot, on 29 dev targets in a synthetic 57-company universe. **This is not a measurement on the hidden data**, and the universe was written by the same agent that wrote the ranker, so absolute numbers are optimistic. The comparisons between tags are the useful part. Held-out (28 targets) has not been scored.

## Results

| Metric | @5 | @10 |
|---|---|---|
| nDCG (main) | 0.657 | 0.697 |
| Precision (relevant = same business) | 0.414 (ceiling 0.690) | 0.269 (ceiling 0.345) |
| Recall | 0.595 | 0.787 |

Precision has a ceiling below 1 because a target has only 3–4 same-business companies in this universe.

| Hard case (tag) | Targets | nDCG@10 |
|---|---|---|
| none (plain descriptions) | 8 | **0.838** |
| mislabelled (dataset labels wrong) | 2 | 0.814 |
| cross_country | 11 | 0.761 |
| geo_trap (country phrase shared with unrelated companies) | 5 | 0.676 |
| paraphrase (few words in common with peers) | 7 | **0.614** |
| boilerplate (generic corporate paragraph) | 4 | **0.337** |

A target can carry several tags (e.g. `DE:QSRD` is cross_country, geo_trap and boilerplate).

- The duplicate listing (`US:WNDX`, a second listing of `US:WNDA`) was never returned as a peer: the near-duplicate skip works.
- **Geography leak:** among irrelevant peers returned, 58% share the target's country, against 40% among all irrelevant candidates, a **lift of 1.44**. It is not confined to leftover slots: in 8 of 29 targets a same-country irrelevant peer ranks above a same-business peer.

## Interpretation

- **What works:** plain descriptions and wrong dataset labels (labels are not ranking inputs, so they cannot mislead) score well, and cross-country peers are mostly found. Business vocabulary dominates the ranking.
- **Paraphrase is a weakness, unevenly.** When a paraphrase still shares key terms it does fine (`CA:DRLC` 1.00, `US:MTGB` 0.82). When it doesn't, it fails: `US:TRKB` ("moves retailers' pallets … using its own big rigs … billing shippers by the load") ranks a container shipper and a driller first, and only one of its three trucking peers reaches the top five. Lexical matching cannot connect "big rigs" with "tractors and trailers". This is the gap the owner named as the trigger for evaluating sentence embeddings.
- **Boilerplate is the worst case.** Companies whose descriptions share a long generic paragraph retrieve each other first: the top five of `US:ORTD`, `US:SOLD` and `DE:QSRD` are all boilerplate companies from other sectors. The fixture plants the *same* paragraph in all of them, an extreme form of templated text. How to address it, and whether a different ranker changes it, is untested.
- **Country words leak into the ranking** (lift 1.44, and 8 targets where they outrank a true peer). Country phrases were kept on purpose, to be measured; this is that measurement.
- **Small samples:** 7 paraphrase and 4 boilerplate targets. The direction is clear; the exact values are not.

## Is this worth acting on?

Paraphrase, boilerplate and the geography leak are each visible and each an owner decision. Nothing in the served ranker has been changed.

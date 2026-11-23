# Retrieval eval: removing companies' own names before ranking

Machine-readable results: experiments 9–11 in [`../experiments.json`](../experiments.json); captured output in `../runs/009`–`011`. Method: [docs/eval.md](../../docs/eval.md). **These numbers are not from the hidden dataset.**

**Why:** in the supplied pre-test data, Irovaiva Air Group's top peers included a fibre broadband firm and a facilities firm ("Irovaor Fibre", "Irineiva Facilities") ahead of five of its six airlines. Descriptions open with the invented company name, and MiniLM matched the look-alike names, not the business. The existing fixtures didn't have look-alike names, so a new fixture, `lookalike/` (70 companies, 14 businesses, 14 shared name stems; written independently by Sonnet), was added to measure it.

**What changed:** ingestion derives a `business_description` (own names and aliases replaced by "The company"). Ranking uses it, and the near-duplicate test keeps the description as supplied.

## Results (MiniLM, threshold 0.88; nDCG@10, dev / held-out)

| Fixture | Served before (exp. 10) | Names removed (exp. 11) |
|---|---|---|
| lookalike | 0.757 / 0.782 | **0.923 / 0.884** |
| independent | 0.729 / 0.684 | 0.716 / 0.689 |
| retrieval_v1 | 0.836 / 0.828 | 0.839 / 0.870 |
| Both copies of a company in one list | 0 | 0 |
| Dedup pairs, precision / recall at 0.88 (dev; held-out) | 1.0 / 0.875; 1.0 / 0.656 | unchanged |

- **Experiment 9** removed names for the near-duplicate test too. Duplicate listings of one company share a name, so 2 double listings came back on `retrieval_v1`. That is why dedup keeps the supplied text (experiment 11: 0 double listings).
- **Pre-test data (qualitative, labels as a rough proxy):** same-sub-industry recall@10 over all 483 companies went from 0.76 to 0.87, and Irovaiva's top 10 went from 3 to all 6 airlines.

## Interpretation

- **Improved:** look-alike names (+0.17 dev, +0.10 held-out) and `retrieval_v1` held-out (+0.04).
- **Flat:** the independent fixture (−0.013 dev, +0.005 held-out), within run-to-run noise. Its names don't look alike, so there is nothing to gain there.
- **Worse:**
  - start-up, because every description is now embedded twice (e.g. 4.1 → 7.1 s for 90 companies; well inside the 60 s budget);
  - geography lift on `lookalike` (1.77 → 2.06 dev). With the name gone, a country phrase is a larger share of the text. The geography leak stays measure-only (owner decision).
- **Worth it:** yes. It fixes a failure seen in data of the hidden set's format, for the cost of a few seconds of start-up.

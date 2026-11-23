# Retrieval eval: removing invented company names before ranking

Machine-readable results: experiments 9–13 in [`../experiments.json`](../experiments.json); captured output in `../runs/009`–`013`. Method: [docs/eval.md](../../docs/eval.md). **These numbers are not from the hidden dataset.**

**Why:** in the supplied pre-test data, Irovaiva Air Group's top peers included a fibre broadband firm and a facilities firm ("Irovaor Fibre", "Irineiva Facilities") ahead of five of its six airlines. Descriptions open with the invented company name, and MiniLM matched the look-alike names, not the business. The existing fixtures had no look-alike names, so a new fixture was written independently by Sonnet to measure this: `lookalike/` (70 companies, 14 businesses, 14 name stems shared across unrelated businesses).

**Served (experiment 13):** ingestion derives a `business_description`, which is the description without the **distinctive** words of the issuer's own names: name words that no other company's description uses ("Irovaiva", "Velorin"). Name words other descriptions also use describe the business ("Air", "Offshore", "Drilling") and stay. Ranking uses this text; the near-duplicate test keeps the description as supplied.

## Results (MiniLM, threshold 0.88; nDCG@10, dev / held-out)

| Fixture | Served before (10) | Whole names, exact match (11) | Whole names with any suffix (12) | **Distinctive name words (13, served)** |
|---|---|---|---|---|
| lookalike | 0.757 / 0.782 | 0.922 / 0.884 | 0.922 / 0.884 | 0.852 / 0.848 |
| independent | 0.729 / 0.684 | 0.716 / 0.689 | 0.625 / 0.651 | **0.769 / 0.761** |
| retrieval_v1 | 0.836 / 0.828 | 0.839 / 0.870 | 0.839 / 0.870 | 0.858 / 0.864 |
| Both copies of a company in one list (dev, held-out) | 0, 0 | 0, 0 | 0, 0 | 0, 0 |
| Dedup pairs, precision / recall at 0.88 (dev) | 1.0 / 0.875 | same | same | same |

- **Experiment 9** removed names for the near-duplicate test too. Duplicate listings share a name, so 2 double listings came back. Since then, dedup keeps the supplied text.
- **Experiment 11** only looked flat on `independent` because that fixture writes names without their suffix ("Timor Offshore Drilling" for "… Ltd"), so almost nothing was removed there.
- **Experiment 12** matched names with any suffix and removed them whole. That also removed business words in descriptive names, costing −0.09 on `independent`.
- **Experiment 13** keeps those words and removes only the invented ones. It is the best on `independent`, the deciding fixture when fixtures disagree (owner rule). It is +0.04 dev and +0.08 held-out over what was served, and +0.10 / +0.07 on `lookalike`.

## Interpretation

- **Improved:** look-alike names, the independent fixture (dev and held-out) and `retrieval_v1`, with no double listings and unchanged dedup.
- **Worse:**
  - **Geography lift on `lookalike`** (1.77 → 3.52 dev). With the invented name gone, the country phrase is a larger share of the text, so when a wrong peer slips in, it is more often from the same country. On `independent` it fell (2.37 → 1.67). The geography leak stays measure-only (owner decision).
  - **`retrieval_v1` boilerplate tag** (4 targets): 0.527 → 0.485.
  - **Start-up**, because descriptions are embedded twice (ranking and dedup): 4.1 → 7.1 s for 90 companies, and 10.7 → 16.3 s for the 320-text dedup universe. That is within the 60 s budget.
  - **Lower than experiment 11 on `lookalike`** (0.922 → 0.852). A stem shared with another company's description ("Velor" in both "Velorin's" and other text) is not distinctive, so it stays.
- **Not measured:** run-to-run variation. Every run is a single deterministic pass, and no repeat runs are logged.
- **Worth it:** yes. It fixes a failure seen in data of the hidden set's format, improves every ranking fixture over what was served, and costs a few seconds of start-up.

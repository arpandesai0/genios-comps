# Spot check: peers for 36 random companies in the supplied data (k = 5)

A qualitative check, not part of the scored eval: the supplied file is a pre-test, and no labels from it are committed. Only the method and aggregate verdicts are recorded here; company names and descriptions from the supplied data are not.

**Configuration:** commit `83eaf62` (experiment 13 code: MiniLM on business descriptions, near-duplicate threshold 0.88), `GET /api/peers?k=5`, run on the supplied `data/` on 2026-11-23.

**Method**
1. 36 companies were drawn at random (`random.seed(20261123)`) from the 477 issuers.
2. Each target's top-5 peers were saved with names, labels and descriptions to a local, uncommitted file.
3. Three Sonnet sub-agents (12 targets each) read the descriptions and graded every peer on the eval rubric: 3 same business, 2 same industry, 1 same sector, 0 unrelated. They were told labels may be wrong and to judge by the described business.

**Result**

| | Count |
|---|---|
| Peers graded 3 (same business) | 180 of 180 |
| Peers graded 0–2 | 0 |
| Targets whose top-1 peer is grade 3 | 36 of 36 |
| Peers whose sector, industry and sub-industry labels match the target's | 180 of 180 |

The reported Irovaiva Air Group case was also checked: all six airlines rank first, followed by aerospace companies.

**Limits**
- These are model judgements, not human labels.
- The supplied file comes in clusters of about five near-identical companies per business, so a random sample rarely contains hard cases (look-alike names, mislabels, boilerplate). The synthetic fixtures measure those.

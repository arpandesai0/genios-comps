# Time log

A rough breakdown of the time spent, reconstructed from the PR history. The work was spread across two days in several sessions, not continuously; the hours below are active working time only. AI agents did much of the typing in parallel (see [README › AI usage](README.md#ai-usage)). The time went mostly into deciding, reviewing and checking.

## Day 1: foundations (PRs #1–#18)

| Work | PRs | Time |
|---|---|---|
| Reading the brief, glossary and data; planning; repo scaffold, agent guide, first API contract | #1 | 0.75 h |
| Ingestion: validation, USD normalization, entity resolution, findings | #2 | 1.0 h |
| Tooling and CI (ruff, mypy, pytest, repo hygiene); PR review rules | #3, #4 | 0.25 h |
| Web UI against synthetic mocks (built in parallel) | #5 | 0.25 h |
| Finance: glossary metrics, ok / NM / missing, peer statistics, rounding | #6, #9 | 0.75 h |
| Docs (pipeline, ingestion, finance), contract wording | #7, #8 | 0.25 h |
| Read-only API and `make start` (Docker) | #10 | 0.5 h |
| Planted-defects acceptance test | #11 | 0.5 h |
| Contract refinements: currency, lookup vs search, Swagger, UI wording | #12–#18 | 0.25 h |
| **Day 1 total** | | **≈ 4.5 h** |

## Day 2: issuers, retrieval and evaluation (PRs #19–#34)

| Work | PRs | Time |
|---|---|---|
| Share-class contract and merge (disjoint-set union); removing manual additions | #19–#21, #25 | 1.0 h |
| Retrieval contract, peer selection and comps tables (TF-IDF baseline) | #22, #23, #28 | 0.75 h |
| Retrieval eval, experiment log, first result | #24, #29 | 0.5 h |
| Embedding stage: three models compared as a black box, independent fixtures, near-duplicate threshold, offline Docker image | #30 | 1.5 h |
| Config file for thresholds; finishing the UI against the real API; start-up banner | #31, #32 | 0.5 h |
| Look-alike company names: business descriptions, new fixture, experiments 9–13, spot check on the supplied data | #33 | 0.75 h |
| Cleanup, design doc, README sections, this log, review fixes | #34–#37 | 0.5 h |
| **Day 2 total** | | **≈ 5.5 h** |

**Total: about 10 hours over two days.** This is more than the suggested 6 hours. The extra went into evaluation: the independent fixtures, the model comparison, and the look-alike-names fix found by running the service on the supplied data.

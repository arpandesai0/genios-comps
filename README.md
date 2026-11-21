# genios-comps

An offline **comparable-companies (comps table) service**.

An analyst names the company they want to research. The service picks that company's peers from a universe of about 500 public companies and returns a comps table:

- each peer's market cap, enterprise value, EV/Revenue, EV/EBITDA and P/E, all in USD;
- **why each peer was chosen**, so the analyst can trust or adjust the list;
- summary statistics (mean, median, high, low) across the peers.

The service reads its data from a folder it is given at start-up. It runs fully offline and starts with a single command.

This project is under active development. Setup instructions, design notes and evaluation results will be added as each part lands.

## Assumptions

Where the brief is silent, the service assumes the following:

1. **Identity is `country:ticker`.** Record `id`s are internal provenance only, so an `id` reused across records is not treated as a conflict.
2. **A record without a ticker is not a listed company.** The brief describes a universe of public companies, and nothing available offline (no web search or LLM) can verify such a record, so it is excluded and reported as `unlisted_excluded`. This applies whether or not the record has a country.
3. **A missing country becomes the placeholder `*`**, giving keys like `*:ACME`. The company is still served.
4. **Records with the same key are appends to one company.** Each `price_date` is one observation in a time series, and comps use the latest observation. Text fields (name, description, classification) take the latest value; if the latest value is empty, the most recent non-empty value is used and flagged. Numbers are never carried over from another date. Records that are identical apart from their `id` collapse into one.
5. **Supplied numbers are the source of truth.** Unusually large values are used as given. They are not flagged or rescaled. In production, values like these would go through human or automated review.
6. **Stale prices are a warning, not a blocker.** A price more than 90 days older than the latest `price_date` in the dataset is flagged, and the company is still served. The reference date can be fixed with `REFERENCE_DATE` so results are reproducible.
7. **Missing takes precedence over NM.** The glossary says both "a missing input gives blank, not NM" and "a zero or negative denominator gives NM". When both apply, the multiple is reported as missing (blank), with the missing fields listed. NM is used only when every input is present.
8. **A zero or negative enterprise value is used as given.** EV multiples are shown as computed, so they can be negative, and they are included in the summary statistics. An info finding (`nonpositive_ev`) flags it. The glossary defines NM only for denominators.
9. **Rounding.** Every value, including the summary statistics, is computed unrounded (apart from cleaning floating-point noise at 9 decimal places) and rounded to one decimal place only for display. A tie rounds half away from zero (12.25x → 12.3x).
11. **Extreme inputs never break a comps table.** If a value overflows (it is too large to represent), it is shown as blank, excluded from the statistics, and flagged with a `non_finite_result` warning.
10. **Summary statistics.** They cover the three multiples only. With an even number of peers, the median is the average of the two middle values. When no peer has a usable value, the statistics are blank.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
make install     # create .venv and install the package with dev tools
make check       # lint, typecheck and tests (the same checks CI runs)
make format      # apply ruff fixes and formatting
```

CI runs four workflows on every pull request and push to `main`: `lint`, `typecheck`, `tests` (Python 3.11 and 3.12, with a coverage report) and `repo-hygiene` (notebooks cleared, no supplied data or local state committed).

Optional: `pre-commit install` enables hooks that run ruff and strip notebook outputs on each commit (see `.pre-commit-config.yaml`).

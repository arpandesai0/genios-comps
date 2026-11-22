# Finance

How a company's latest observation becomes the comps-table numbers, and how peer summary statistics are computed. The code is `src/comps/finance.py`, and its output types (`MetricValue`, `Metrics`, `SummaryStat`, `Summary`) live in `src/comps/models.py`.

Finance is **pure**: an `Observation` goes in and metric values come out. It doesn't know where the observation came from or how peers were chosen. Its input values are already in USD (see [ingestion.md](ingestion.md#3-validate-and-normalize-each-record)).

All examples use invented companies.

## Formulas (glossary, applied exactly)

```
market cap (USD m)  = price (USD per share) × shares_outstanding (millions)
EV (USD m)          = market cap + total_debt − cash
EV/Revenue          = EV ÷ revenue
EV/EBITDA           = EV ÷ EBITDA
P/E                 = market cap ÷ net_income
```

Revenue, EBITDA and net income are last-twelve-months values, as supplied. Only the company's **latest** observation is used, and fields are never mixed across dates.

**Share classes.** For an issuer with several share classes (see [ingestion.md § 6](ingestion.md#6-merge-share-classes-issuerspy)), market cap is the glossary formula applied to each **counted** class and summed: `Σ price × shares_outstanding`. Debt, cash, revenue, EBITDA and net income come from the issuer's latest observation, once. If any counted class has no usable price or share count, market cap is **missing** (never a partial sum), and `missing_inputs` names the root fields (e.g. `["price"]`); a `share_class_incomplete` finding names the class. `compute_metrics(obs, listings)` takes the counted classes' latest observations as `listings`; a single listing is just `obs`.

## Every value has a status

| Status | When | `value` / `raw` | `display` |
|---|---|---|---|
| `ok` | computed | number | `"12.3x"`, `"4,512.3"` |
| `nm` | all inputs present, and the multiple's denominator is **zero or negative** | `null` | `"NM"` |
| `missing` | an input it needs is unavailable (null, invalid, or impossible to convert) | `null` | `null` (shown blank) |

**Missing wins over NM.** The glossary says both "a missing input gives blank, not NM" and "a zero or negative denominator gives NM". When both apply, the value is **missing**. NM is reserved for multiples whose inputs are all present.

| Example inputs | EV/Revenue | Why |
|---|---|---|
| EV 2,400, revenue 1,000 | `ok`, 2.4x | |
| EV 2,400, revenue 0 | `nm` | zero denominator |
| EV 2,400, revenue −50 | `nm` | negative denominator |
| EV 2,400, revenue null | `missing` (`["revenue"]`) | |
| debt null (so EV missing), revenue −10 | `missing` (`["total_debt"]`) | missing wins over NM |

A missing value is **never zero**. If `cash` is null, EV is blank. It is not computed as market cap + debt.

### `missing_inputs`: why a value is blank

A `missing` value lists the **record fields** that caused it, so the analyst can fix the source:

- the field itself if it is null or invalid, e.g. `["total_debt"]` for a negative debt;
- the root cause if a conversion failed: `["price_currency"]`, `["reporting_currency"]` or `["units"]`;
- both, when the field is unusable (null, absent, wrong type or invalid) and its conversion also failed, e.g. `["total_debt", "reporting_currency"]` for a debt of −5 in an unknown currency. The explanation is never partial.

The order follows the formula: numerator causes first, then denominator causes. Within a field, the field comes before its conversion. Each cause appears once.

### Zero or negative enterprise value

If cash is at least market cap + debt, EV is zero or negative. The glossary defines NM only for denominators, so **EV is used as given**. EV multiples are shown, for example `-2.5x`, and included in the statistics. An info finding `nonpositive_ev` flags it. P/E doesn't use EV and is unaffected.

### Overflow

Extreme but valid inputs, such as revenue = 1e-320, can overflow a float to infinity. Such a value becomes `missing`, with an empty `missing_inputs`, and a warning finding `non_finite_result` lists every value it blanked. When market cap overflows, that includes EV and all three multiples. It is excluded from the statistics and **never crashes the comps table**.

## Rounding and display

1. **Compute unrounded.** Every metric and every summary statistic is computed from unrounded values.
2. **Clean float noise at 9 dp.** Binary floats turn some exact decimals into near-misses, such as `2.05 × 3 = 6.1499999999999995`. Values are first rounded to 9 decimal places, so this one becomes 6.15. `raw` holds this cleaned value, and the EV ≤ 0 check uses it too.
3. **Round to 1 dp for display, ties half away from zero.** 12.25 → 12.3, −12.25 → −12.3, 0.35 → 0.4. The glossary requires 1 dp but doesn't specify a tie rule, so this one was chosen by the owner. `-0.0` is never shown.

Display formats:

| Kind | Examples |
|---|---|
| Money (USD millions) | `4,512.3` · `-1,234.5` · `0.0` |
| Multiple | `12.3x` · `-2.1x` · `1,234.5x` |
| NM | `NM` |
| Missing | `null` (blank) |

The API and UI show `display` as given and never round again.

## Summary statistics

`summarize(peers)` returns the mean, median, high and low for **EV/Revenue, EV/EBITDA and P/E**. Market cap and EV are not summarised.

- **Peers only.** The caller passes peer rows and never the target. The rule is enforced at the call site and documented in tests.
- **Excluded:** NM and missing values. They are counted in `n_nm` and `n_missing`, and `n` is the number of values used.
- **Median** of an even count is the average of the two middle values.
- **No usable values** (`n = 0`): all four stats are `null` and shown blank, and the counts explain why.
- Stats are computed on unrounded values, so they can differ slightly from a hand calculation on the displayed 1-dp numbers. That's intended.

## Worked example

Four invented companies. The target is `US:ACME`, and the other three are its peers.

| Key | Price × shares | Debt | Cash | Revenue | EBITDA | Net income |
|---|---|---|---|---|---|---|
| US:ACME | 20 × 100 | 500 | 100 | 1,000 | 200 | 80 |
| JP:NIPP | 7.00 × 50 (from 1,000 JPY) | 110 | 22 | 330 | 66 | 27.5 |
| *:ZED | 20 × 100 | *null* | 100 | 1,000 | 200 | 80 |
| US:LOSS | 20 × 100 | 500 | 3,000 | 1,000 | 200 | −40 |

| Key | Market cap | EV | EV/Revenue | EV/EBITDA | P/E | Findings |
|---|---|---|---|---|---|---|
| US:ACME *(target)* | 2,000.0 | 2,400.0 | 2.4x | 12.0x | 25.0x | |
| JP:NIPP | 350.0 | 438.0 | 1.3x (1.327…) | 6.6x (6.636…) | 12.7x (12.727…) | |
| *:ZED | 2,000.0 | *blank* `["total_debt"]` | *blank* | *blank* | 25.0x | |
| US:LOSS | 2,000.0 | -500.0 | -0.5x | -2.5x | NM | `nonpositive_ev` |

Peer summary (ACME excluded):

| Multiple | n | n_nm | n_missing | Mean | Median | High | Low |
|---|---|---|---|---|---|---|---|
| EV/Revenue | 2 | 0 | 1 | 0.4x | 0.4x | 1.3x | -0.5x |
| EV/EBITDA | 2 | 0 | 1 | 2.1x | 2.1x | 6.6x | -2.5x |
| P/E | 2 | 1 | 0 | 18.9x | 18.9x | 25.0x | 12.7x |

The arithmetic: EV/Revenue mean = (1.327272727 + (−0.5)) / 2 = 0.4136 → 0.4x. P/E mean = (12.727272727 + 25.0) / 2 = 18.86 → 18.9x. ZED's EV multiples are missing and LOSS's P/E is NM, so neither counts.

One metric serialised (the API shape in `docs/API.md`):

```json
{"status": "ok", "value": 1.3, "display": "1.3x", "raw": 1.327272727, "missing_inputs": []}
{"status": "missing", "value": null, "display": null, "raw": null, "missing_inputs": ["total_debt"]}
{"status": "nm", "value": null, "display": "NM", "raw": null, "missing_inputs": []}
```

## Assumptions

These were decided by the owner where the glossary is silent. They are logged in `AGENTS.md` §4 and README Assumptions.

1. Missing wins over NM.
2. A zero or negative EV is used as given, with a `nonpositive_ev` info finding. Extreme multiples are not flagged.
3. Values are cleaned at 9 dp, then rounded to 1 dp with ties half away from zero. Stats are computed before rounding.
4. Stats cover the three multiples only. An even count takes the mean of the middle two. With no usable values the stats are blank.
5. A non-finite result is missing, with a `non_finite_result` warning.

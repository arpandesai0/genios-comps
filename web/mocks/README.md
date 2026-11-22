# Synthetic HTTP fixtures

`synthetic-companies.json` and `fx-rates.json` are invented for UI development. They contain no supplied assignment data. The record fixture is validated against `RawRecord` on load. `server.ts` is imported only by the Next.js API route, never by browser code.

The mock server implements the documented HTTP endpoints so search, pagination, filtering, exclusions, and CSV can be exercised end to end. Financial values and summary statistics are computed by this server-side test double; the UI consumes their display values without rounding or calculating summaries.

These mocks are not the Python ingestion or retrieval implementation and do not evaluate peer quality. Ranking and similarity are deterministic fixture signals, identified by the response method `Synthetic TF-IDF fixture`. The FX rates and 90-day freshness check are fixture values, not new production policy.

Fixture cases:

- `US:NOMA` / `GB:NOMA`: ticker ambiguity.
- `US:NOMA.B`: duplicate listing of `US:NOMA`. Both class keys resolve to the issuer and the shared shares count once in its market cap.
- `US:NOMA`: two observations, with a historical name alias.
- `US:ARCL`: missing EBITDA.
- `US:MESA`: negative net income, producing NM for P/E.
- `US:ORBT`: model-derived classification warning.
- `DE:LUMA`: stale price.
- `CA:NOVA`: CAD conversion.
- `US:ALTO`: reporting in thousands.

There are 15 records and 13 issuers. The dataset is built from the fixture files.

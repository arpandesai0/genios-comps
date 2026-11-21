# Synthetic HTTP fixtures

`synthetic-companies.json` and `fx-rates.json` are invented for UI development. They contain no supplied assignment data. The record fixture is validated against `RawRecord` on load. `server.ts` is imported only by the Next.js API route, never by browser code.

The mock server implements the documented HTTP endpoints so search, pagination, filtering, exclusions, CSV, and preview/save can be exercised end to end. Financial values and summary statistics are computed by this server-side test double; the UI consumes their display values without rounding or calculating summaries.

These mocks are not the Python ingestion or retrieval implementation and do not evaluate peer quality. Ranking and similarity are deterministic fixture signals, identified by the response method `Synthetic TF-IDF fixture`. The simplified validation and resolution logic exists to exercise UI states; acceptance by this mock does not establish acceptance by the real service. The FX rates and 90-day freshness check are fixture values, not new production policy.

Fixture cases:

- `US:NOMA` / `GB:NOMA`: ticker ambiguity.
- `US:NOMA.B`: possible same issuer, excluded when comparing `US:NOMA`.
- `US:NOMA`: two observations, with a historical name alias.
- `US:ARCL`: missing EBITDA.
- `US:MESA`: negative net income, producing NM for P/E.
- `US:ORBT`: model-derived classification warning.
- `DE:LUMA`: stale price.
- `CA:NOVA`: CAD conversion.
- `US:ALTO`: reporting in thousands.

There are 15 initial records and 14 entities. Additions live in the Next.js server process only, are shared across local browser sessions, and disappear on restart. Preview has no side effects. Duplicate submissions do not create another addition. For predictable repeated tests, restart the mock server.

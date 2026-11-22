# Genios comps web

Next.js App Router, TypeScript, Tailwind and shadcn/ui components. Every table uses the shadcn Table primitives with TanStack Table. The UI consumes the [HTTP contract](../docs/API.md); it never reads Python internals or the supplied data files.

## Run with synthetic mocks

Use Node.js 22 and npm. From this directory:

```bash
npm ci
npm run dev
```

Open <http://localhost:3000>. Mocks are enabled by default; `NEXT_PUBLIC_USE_MOCKS=1` makes the choice explicit. Compare is `/`; dataset health, findings and companies are `/data`.

All browser requests use `/api`. In mock mode, a Next.js route serves synthetic JSON fixtures from `mocks/`. No supplied assignment data is included.

## Run against the Python API

```bash
NEXT_PUBLIC_USE_MOCKS=0 API_URL=http://localhost:8000 npm run dev
```

Next.js rewrites `/api/*` to `${API_URL}/api/*`; the default local API URL is `http://localhost:8000`. No browser CORS configuration is required. For production:

```bash
NEXT_PUBLIC_USE_MOCKS=0 API_URL=http://localhost:8000 npm run build
npm start
```

The mock switch and rewrite destination are build-time settings for production. Rebuild after changing either. The UI passes API errors through to the analyst; it does not fall back to mock data when the real API fails.

## Docker

Build with this directory as context:

```bash
docker build -t genios-web .
docker run --rm -p 3000:3000 genios-web
```

For the API service named `api` on a shared Docker network:

```bash
docker build --build-arg NEXT_PUBLIC_USE_MOCKS=0 --build-arg API_URL=http://api:8000 -t genios-web .
```

The multi-stage image serves the standalone Next.js build on port 3000 as a non-root user. Compose integration belongs to the backend owner. Dependency installation needs network access during build; runtime uses no CDN assets, remote fonts, analytics or external services. Next.js telemetry is disabled in the image.

## Checks

```bash
npm ci
npm run build
npm run lint
npx playwright install chromium
npm test
```

If Chrome is already installed, skip the browser download and run `PLAYWRIGHT_CHANNEL=chrome npm test`. Browser tests start a mock-mode development server when port 3000 is free. Stop any real-API server before running them.

## Display and calculations

The UI renders `display` strings verbatim. Money is USD millions; multiples and money are already rounded by the server. Missing values expose their `missing_inputs`; NM exposes the zero-or-negative-denominator explanation. The calculation drawer shows original inputs, conversion factors, normalized values and unrounded metric values. It does not calculate financial values.

Peer removal and undo request a new comps response. Summary values, counts and CSV always come from the server with the same target, `k` and exclusions. Similarity is labeled as a score. Model-derived findings remain visibly distinct from validation findings.

## Decisions and assumptions

- **2026-11-21, owner confirmed:** peer count is user input, defaulting to 10. The named constant is `DEFAULT_K` in the Compare view. The valid range is 1–50, as specified by the API contract.
- **2026-11-22, owner confirmed:** remove manual additions first, then add share classes, then wire Compare to the real API, with approval before each step.
- **2026-11-22, owner confirmed:** show a compact Share Classes section for multi-class issuers, including whether each class counts toward market cap.
- **2026-11-22, owner confirmed:** show the server note above the Compare table and a collapsed Skipped Companies list below. Keep peer evidence in the Compare drawer.
- UI decisions are recorded here because this task is restricted to `web/`.
- System fonts keep build and runtime independent of font services.
- Mocks support UI development, not a measured retrieval or finance evaluation. They must not be used as evidence of Python backend behavior.

## AI usage

Codex implemented the UI, synthetic mock service, Docker setup and browser checks from the supplied handoff and HTTP contract. Implementation work was split across agents for Compare/shared components, Data, mocks, and documentation/checks. Validation results are reported in the PR; no backend evaluation results are claimed.

## Mock coverage and limits

The fixture contains 15 synthetic records across 14 entities, including two observations and aliases for `US:NOMA`. Searching `NOMA` demonstrates ticker ambiguity (`US:NOMA`, `GB:NOMA`); `US:NOMA.B` demonstrates same-issuer exclusion. Other fixtures cover missing EBITDA (`US:ARCL`), negative net income/NM (`US:MESA`), a model-derived classification warning (`US:ORBT`), stale prices (`DE:LUMA`), thousands-to-millions conversion (`US:ALTO`) and CAD conversion (`CA:NOVA`).

The mock HTTP server computes financial metrics and summaries on the server so exclusions can be exercised end to end. Retrieval uses deterministic fixture order and scores, not a TF-IDF index. Mock FX is limited to the synthetic USD, CAD, GBP and EUR rates in its fixture.

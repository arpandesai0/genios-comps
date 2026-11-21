/** Synthetic HTTP test double. Never imported by client components. Not the production ingestion/retrieval implementation. */
import { createHash } from "node:crypto";
import recordsJson from "./synthetic-companies.json";
import fxRates from "./fx-rates.json";
import type {
  RawRecord,
  EntityDetail,
  EntitySummary,
  Finding,
  Severity,
  MetricValue,
  Metrics,
  Observation,
  SummaryStat,
  CompsResponse,
  DatasetResponse,
  IngestResult,
} from "../lib/api-types";

const numericFields = [
  "price",
  "shares_outstanding",
  "total_debt",
  "cash",
  "revenue",
  "ebitda",
  "net_income",
] as const;
const textFields = [
  "id",
  "ticker",
  "name",
  "description",
  "sector",
  "industry",
  "sub_industry",
  "country",
  "price_currency",
  "reporting_currency",
  "units",
  "fiscal_year_end",
  "price_date",
] as const;
const severityList: Severity[] = ["error", "limitation", "warning", "info"];
const referenceDate = "2026-11-21";
const rates: Record<string, number> = fxRates;
function isRecord(value: unknown): value is RawRecord {
  if (!value || typeof value !== "object") return false;
  const obj = value as Record<string, unknown>;
  return (
    textFields.every((f) => typeof obj[f] === "string") &&
    numericFields.every(
      (f) =>
        obj[f] === null ||
        (typeof obj[f] === "number" && Number.isFinite(obj[f])),
    ) &&
    (obj.units === "millions" || obj.units === "thousands")
  );
}
const fixtureRecords: RawRecord[] = recordsJson.map((record: unknown) => {
  if (!isRecord(record))
    throw new Error("Synthetic fixtures violate RawRecord");
  return record;
});
const stateKey = globalThis as typeof globalThis & {
  __geniosMockRecords?: { record: RawRecord; key: string; added_at: string }[];
};
const additions = (stateKey.__geniosMockRecords ??= []);
const hash = (value: unknown) =>
  createHash("sha256").update(JSON.stringify(value)).digest("hex");
const version = () => hash([fixtureRecords, additions]).slice(0, 12);
const counts = (): Record<Severity, number> => ({
  error: 0,
  limitation: 0,
  warning: 0,
  info: 0,
});
const keyOf = (r: RawRecord) => `${r.country}:${r.ticker}`;
const financialKeys = [
  "market_cap_usd_m",
  "enterprise_value_usd_m",
  "ev_revenue",
  "ev_ebitda",
  "pe",
] as const;
const multipleKeys = ["ev_revenue", "ev_ebitda", "pe"] as const;
function finding(
  record: RawRecord,
  code: string,
  severity: Severity,
  message: string,
  fields: string[],
  affects: string[],
  source: Finding["source"] = "validation",
): Finding {
  return {
    code,
    severity,
    message,
    fields,
    affects,
    source,
    record_ids: [record.id],
    entity_keys: [keyOf(record)],
  };
}
function observe(r: RawRecord, origin: Observation["origin"]): Observation {
  const priceFx = rates[r.price_currency] ?? null;
  const reportingFx = rates[r.reporting_currency] ?? null;
  const unit = r.units === "thousands" ? 0.001 : 1;
  const convert = (v: number | null, fx: number | null, factor = 1) =>
    v === null || fx === null ? null : v * fx * factor;
  return {
    record_id: r.id,
    origin,
    price_date: r.price_date || null,
    original: { ...r },
    usd: {
      price: convert(r.price, priceFx),
      total_debt: convert(r.total_debt, reportingFx, unit),
      cash: convert(r.cash, reportingFx, unit),
      revenue: convert(r.revenue, reportingFx, unit),
      ebitda: convert(r.ebitda, reportingFx, unit),
      net_income: convert(r.net_income, reportingFx, unit),
    },
    conversion: {
      price_fx: priceFx,
      reporting_fx: reportingFx,
      unit_factor: unit,
    },
  };
}
function metric(
  raw: number | null,
  missing: string[],
  multiple = false,
  nm = false,
): MetricValue {
  if (nm)
    return {
      status: "nm",
      value: null,
      display: "NM",
      raw: null,
      missing_inputs: [],
    };
  if (missing.length || raw === null)
    return {
      status: "missing",
      value: null,
      display: null,
      raw: null,
      missing_inputs: missing,
    };
  return {
    status: "ok",
    value: Number(raw.toFixed(1)),
    display: multiple
      ? `${raw.toFixed(1)}x`
      : raw.toLocaleString("en-US", {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        }),
    raw,
    missing_inputs: [],
  };
}
function metrics(r: RawRecord, o: Observation): Metrics {
  const missing = (...fields: (keyof RawRecord)[]) =>
    fields.filter((f) => r[f] === null);
  const pMissing = [
    ...missing("price", "shares_outstanding"),
    ...(o.conversion.price_fx === null ? ["price_fx"] : []),
  ];
  const cap = pMissing.length ? null : o.usd.price! * r.shares_outstanding!;
  const evMissing = [
    ...pMissing,
    ...missing("total_debt", "cash"),
    ...(o.conversion.reporting_fx === null ? ["reporting_fx"] : []),
  ];
  const ev = evMissing.length ? null : cap! + o.usd.total_debt! - o.usd.cash!;
  const ratio = (
    num: number | null,
    fields: string[],
    denom: "revenue" | "ebitda" | "net_income",
  ) => {
    const absent = [
      ...fields,
      ...missing(denom),
      ...(o.conversion.reporting_fx === null ? ["reporting_fx"] : []),
    ];
    return metric(
      absent.length ? null : o.usd[denom]! <= 0 ? 0 : num! / o.usd[denom]!,
      [...new Set(absent)],
      true,
      o.usd[denom] !== null && o.usd[denom]! <= 0,
    );
  };
  return {
    market_cap_usd_m: metric(cap, pMissing),
    enterprise_value_usd_m: metric(ev, evMissing),
    ev_revenue: ratio(ev, evMissing, "revenue"),
    ev_ebitda: ratio(ev, evMissing, "ebitda"),
    pe: ratio(cap, pMissing, "net_income"),
  };
}
function buildEntities(extra?: RawRecord): EntityDetail[] {
  const all = [
    ...fixtureRecords.map((record) => ({ record, origin: "file" as const })),
    ...additions.map(({ record }) => ({ record, origin: "manual" as const })),
    ...(extra ? [{ record: extra, origin: "manual" as const }] : []),
  ];
  const grouped = new Map<string, typeof all>();
  for (const item of all) {
    const group = grouped.get(keyOf(item.record)) ?? [];
    if (
      !group.some(
        ({ record }) => JSON.stringify(record) === JSON.stringify(item.record),
      )
    )
      group.push(item);
    grouped.set(keyOf(item.record), group);
  }
  return [...grouped.entries()].map(([key, group]) => {
    group.sort((a, b) =>
      a.record.price_date.localeCompare(b.record.price_date),
    );
    const r = group.at(-1)!.record;
    // One observation per date, ties resolved by later record; history remains in record provenance.
    const byDate = new Map<string, Observation>();
    for (const item of group)
      byDate.set(item.record.price_date, observe(item.record, item.origin));
    const observations = [...byDate.values()];
    const latest = observations.at(-1)!;
    const resultMetrics = metrics(r, latest);
    const findings: Finding[] = [];
    for (const f of numericFields)
      if (r[f] === null)
        findings.push(
          finding(
            r,
            "missing_value",
            "limitation",
            `${f} is missing.`,
            [f],
            financialKeys.filter((k) =>
              resultMetrics[k].missing_inputs.includes(f),
            ),
          ),
        );
    if (
      latest.conversion.price_fx === null ||
      latest.conversion.reporting_fx === null
    )
      findings.push(
        finding(
          r,
          "unknown_currency",
          "error",
          "Currency is not available in the synthetic FX fixture.",
          ["price_currency", "reporting_currency"],
          [...financialKeys],
        ),
      );
    if (r.price_date < "2026-08-23")
      findings.push(
        finding(
          r,
          "stale_price",
          "warning",
          "The synthetic price is more than 90 days before the reference date.",
          ["price_date"],
          [...financialKeys],
        ),
      );
    if (r.ticker === "ORBT")
      findings.push(
        finding(
          r,
          "classification_conflict",
          "warning",
          "Synthetic description neighbours suggest a possible classification conflict; labels are unchanged.",
          ["sector"],
          ["retrieval"],
          "derived",
        ),
      );
    if (key === "US:NOMA" || key === "US:NOMA.B")
      findings.push(
        finding(
          r,
          "possible_same_issuer",
          "info",
          "Synthetic share classes may represent the same issuer.",
          ["ticker"],
          ["retrieval"],
        ),
      );
    if (group.length > byDate.size)
      findings.push(
        finding(
          r,
          "observation_conflict",
          "warning",
          "Different records share a price date; the later record is used.",
          ["price_date"],
          [...financialKeys],
        ),
      );
    if (
      group.some(
        ({ record }) =>
          record.name !== r.name || record.description !== r.description,
      )
    )
      findings.push(
        finding(
          r,
          "text_updated",
          "info",
          "Text changed across records; previous text remains in observation provenance.",
          ["name", "description"],
          [],
        ),
      );
    const finding_counts = counts();
    for (const f of findings) finding_counts[f.severity]++;
    return {
      key,
      ticker: r.ticker,
      country: r.country,
      name: r.name,
      sector: r.sector,
      industry: r.industry,
      sub_industry: r.sub_industry,
      latest_price_date: latest.price_date,
      finding_counts,
      description: r.description,
      fiscal_year_end: r.fiscal_year_end,
      aliases: [...new Set(group.map(({ record }) => record.name))],
      record_ids: group.map(({ record }) => record.id),
      latest,
      observations,
      metrics: resultMetrics,
      findings,
    };
  });
}
function summaryEntity(e: EntityDetail): EntitySummary {
  return {
    key: e.key,
    ticker: e.ticker,
    country: e.country,
    name: e.name,
    sector: e.sector,
    industry: e.industry,
    sub_industry: e.sub_industry,
    latest_price_date: e.latest_price_date,
    finding_counts: e.finding_counts,
  };
}
function stat(values: MetricValue[]): SummaryStat {
  const sorted = values
    .flatMap((v) => (v.status === "ok" && v.raw !== null ? [v.raw] : []))
    .sort((a, b) => a - b);
  const n = sorted.length;
  const round = (n: number | null) =>
    n === null ? null : Number(n.toFixed(1));
  const mean = n ? sorted.reduce((a, b) => a + b, 0) / n : null;
  const median = n
    ? (sorted[Math.floor((n - 1) / 2)] + sorted[Math.floor(n / 2)]) / 2
    : null;
  const high = n ? sorted[n - 1] : null,
    low = n ? sorted[0] : null;
  const display = (v: number | null) =>
    v === null ? null : `${v.toFixed(1)}x`;
  return {
    n,
    n_nm: values.filter((v) => v.status === "nm").length,
    n_missing: values.filter((v) => v.status === "missing").length,
    mean: round(mean),
    median: round(median),
    high: round(high),
    low: round(low),
    display: {
      mean: display(mean),
      median: display(median),
      high: display(high),
      low: display(low),
    },
  };
}
class MockError extends Error {
  constructor(
    public status: number,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}
function comps(
  params: URLSearchParams,
  entities: EntityDetail[],
): CompsResponse {
  const target = entities.find((e) => e.key === params.get("target"));
  if (!target) throw new MockError(404, "Target company not found.");
  const k = Number(params.get("k") ?? 10);
  if (!Number.isInteger(k) || k < 1 || k > 50)
    throw new MockError(422, "k must be an integer from 1 to 50.");
  const removed = (params.get("exclude") || "").split(",").filter(Boolean);
  if (removed.some((key) => !entities.some((e) => e.key === key)))
    throw new MockError(422, "An excluded company key was not found.");
  const excluded: CompsResponse["excluded"] = [];
  const candidates = entities.filter((e) => {
    if (e.key === target.key) return false;
    const sibling =
      ["US:NOMA", "US:NOMA.B"].includes(target.key) &&
      ["US:NOMA", "US:NOMA.B"].includes(e.key);
    if (sibling || removed.includes(e.key)) {
      excluded.push({
        entity: summaryEntity(e),
        reason: sibling ? "possible_same_issuer" : "user_excluded",
        detail: sibling
          ? "Possible same issuer: synthetic share-class fixture."
          : "Removed by the analyst.",
      });
      return false;
    }
    return true;
  });
  const peers = candidates.slice(0, k).map((e, i) => ({
    rank: i + 1,
    entity: summaryEntity(e),
    metrics: e.metrics,
    findings: e.findings,
    evidence: {
      similarity: Number(
        Math.max(0, 0.94 - entities.indexOf(e) * 0.043).toFixed(3),
      ),
      shared_terms: ["cloud", "software", "enterprise"],
      classification: {
        sector: e.sector === target.sector,
        industry: e.industry === target.industry,
        sub_industry: e.sub_industry === target.sub_industry,
      },
      country_match: e.country === target.country,
      revenue_ratio:
        e.latest.usd.revenue !== null && target.latest.usd.revenue
          ? e.latest.usd.revenue / target.latest.usd.revenue
          : null,
      limitations: e.findings
        .filter((f) => f.affects.length)
        .map((f) => f.code),
    },
  }));
  return {
    dataset_version: version(),
    method: { name: "Synthetic TF-IDF fixture", version: "mock-v1" },
    k,
    target: {
      entity: summaryEntity(target),
      metrics: target.metrics,
      findings: target.findings,
    },
    peers,
    excluded,
    summary: {
      ev_revenue: stat(peers.map((p) => p.metrics.ev_revenue)),
      ev_ebitda: stat(peers.map((p) => p.metrics.ev_ebitda)),
      pe: stat(peers.map((p) => p.metrics.pe)),
    },
  };
}
function preview(record: RawRecord, entities: EntityDetail[]): IngestResult {
  const key = keyOf(record);
  const invalid: Finding[] = [];
  if (
    !record.country.trim() ||
    !record.ticker.trim() ||
    !record.id.trim() ||
    !record.name.trim()
  )
    invalid.push(
      finding(
        record,
        "invalid_identity",
        "error",
        "ID, country, ticker and name are required.",
        ["id", "country", "ticker", "name"],
        [],
      ),
    );
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(record.price_date) ||
    Number.isNaN(Date.parse(record.price_date))
  )
    invalid.push(
      finding(
        record,
        "invalid_date",
        "error",
        "Price date must be an ISO date.",
        ["price_date"],
        [...financialKeys],
      ),
    );
  const entity = buildEntities(record).find((e) => e.key === key)!;
  invalid.push(...entity.findings.filter((f) => f.severity === "error"));
  if (invalid.length)
    return {
      accepted: false,
      resolution: { key, action: "rejected" },
      entity: null,
      findings: invalid,
    };
  const existing = entities.find((e) => e.key === key);
  let action: IngestResult["resolution"]["action"] = "create";
  if (existing) {
    const same = (a: Record<string, unknown>, b: RawRecord) =>
      Object.keys(b)
        .filter((k) => k !== "id")
        .every((k) => a[k] === b[k as keyof RawRecord]);
    if (existing.observations.some((o) => same(o.original, record)))
      action = "duplicate";
    else if (
      existing.observations.some(
        (o) =>
          o.price_date === record.price_date &&
          numericFields.every((f) => o.original[f] === record[f]) &&
          ["price_currency", "reporting_currency", "units"].every(
            (f) => o.original[f] === record[f as keyof RawRecord],
          ),
      )
    )
      action = "update_text";
    else action = "add_observation";
  }
  return {
    accepted: true,
    resolution: { key, action },
    entity: action === "duplicate" ? existing! : entity,
    findings: entity.findings,
  };
}
function page<T>(
  items: T[],
  params: URLSearchParams,
  defaultLimit: number,
  max: number,
) {
  const limit = Number(params.get("limit") ?? defaultLimit),
    offset = Number(params.get("offset") ?? 0);
  if (
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > max ||
    !Number.isInteger(offset) ||
    offset < 0
  )
    throw new MockError(422, "Invalid pagination parameters.");
  return {
    dataset_version: version(),
    total: items.length,
    items: items.slice(offset, offset + limit),
  };
}
function csv(response: CompsResponse) {
  const rows: unknown[][] = [
    [
      "type",
      "key",
      "name",
      "rank",
      "similarity",
      "market_cap_usd_m",
      "enterprise_value_usd_m",
      "ev_revenue",
      "ev_ebitda",
      "pe",
    ],
  ];
  const row = (
    kind: string,
    e: EntitySummary,
    m: Metrics,
    rank: unknown = "",
    similarity: unknown = "",
  ) => [
    kind,
    e.key,
    e.name,
    rank,
    similarity,
    ...financialKeys.map((k) => m[k].display),
  ];
  rows.push(row("target", response.target.entity, response.target.metrics));
  for (const p of response.peers)
    rows.push(row("peer", p.entity, p.metrics, p.rank, p.evidence.similarity));
  for (const s of ["mean", "median", "high", "low"] as const)
    rows.push([
      s,
      "",
      "",
      "",
      "",
      "",
      "",
      ...multipleKeys.map((k) => response.summary[k].display[s]),
    ]);
  for (const s of ["n", "n_nm", "n_missing"] as const)
    rows.push([
      s,
      "",
      "",
      "",
      "",
      "",
      "",
      ...multipleKeys.map((k) => response.summary[k][s]),
    ]);
  return rows
    .map((r) =>
      r.map((v) => `"${String(v ?? "").replaceAll('"', '""')}"`).join(","),
    )
    .join("\r\n");
}
export async function handleMock(
  request: Request,
  path: string,
): Promise<Response> {
  const json = (body: unknown, status = 200) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
  try {
    const entities = buildEntities();
    const params = new URL(request.url).searchParams;
    if (request.method === "GET") {
      if (path === "health")
        return json({
          status: "ok",
          dataset_version: version(),
          entities: entities.length,
          records: fixtureRecords.length + additions.length,
          reference_date: referenceDate,
        });
      if (path === "companies") {
        const q = (params.get("q") ?? "").trim().toLowerCase(),
          sector = params.get("sector"),
          severity = params.get("has_findings");
        if (severity && !severityList.includes(severity as Severity))
          throw new MockError(422, "Invalid severity.");
        const items = entities
          .map((e) => ({
            ...summaryEntity(e),
            match: !q
              ? null
              : e.key.toLowerCase() === q
                ? ("key" as const)
                : e.ticker.toLowerCase() === q
                  ? ("ticker" as const)
                  : e.name.toLowerCase() === q
                    ? ("name_exact" as const)
                    : e.name.toLowerCase().includes(q) ||
                        e.key.toLowerCase().includes(q)
                      ? ("name_partial" as const)
                      : null,
          }))
          .filter(
            (e) =>
              (!q || e.match !== null) &&
              (!sector || e.sector === sector) &&
              (!severity || e.finding_counts[severity as Severity] > 0),
          );
        return json(page(items, params, 20, 200));
      }
      if (path.startsWith("companies/")) {
        const e = entities.find(
          (e) => e.key === decodeURIComponent(path.slice(10)),
        );
        if (!e) throw new MockError(404, "Company not found.");
        return json({ ...e, dataset_version: version() });
      }
      if (path === "comps" || path === "comps.csv") {
        const result = comps(params, entities);
        return path === "comps"
          ? json(result)
          : new Response(csv(result), {
              headers: {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": 'attachment; filename="comps.csv"',
                "Cache-Control": "no-store",
              },
            });
      }
      const findings = entities.flatMap((e) => e.findings);
      if (path === "dataset") {
        const bySeverity = counts();
        const byCode = new Map<
          string,
          DatasetResponse["findings_by_code"][number]
        >();
        for (const f of findings) {
          bySeverity[f.severity]++;
          const key = `${f.code}:${f.severity}:${f.source}`;
          const item = byCode.get(key) ?? {
            code: f.code,
            severity: f.severity,
            source: f.source,
            count: 0,
          };
          item.count++;
          byCode.set(key, item);
        }
        const body: DatasetResponse = {
          dataset_version: version(),
          reference_date: referenceDate,
          source: {
            data_dir: "web/mocks (synthetic)",
            files: [
              {
                name: "synthetic-companies.json",
                sha256: hash(fixtureRecords),
              },
              { name: "fx-rates.json", sha256: hash(fxRates) },
            ],
          },
          counts: {
            records: fixtureRecords.length + additions.length,
            entities: entities.length,
            manual_additions: additions.length,
          },
          findings_by_severity: bySeverity,
          findings_by_code: [...byCode.values()],
        };
        return json(body);
      }
      if (path === "dataset/findings")
        return json(
          page(
            findings.filter(
              (f) =>
                (!params.get("severity") ||
                  f.severity === params.get("severity")) &&
                (!params.get("code") || f.code === params.get("code")) &&
                (!params.get("entity") ||
                  f.entity_keys.includes(params.get("entity")!)),
            ),
            params,
            50,
            500,
          ),
        );
      if (path === "ingest/records")
        return json({ dataset_version: version(), items: additions });
    }
    if (
      request.method === "POST" &&
      (path === "ingest/preview" || path === "ingest/records")
    ) {
      let body: unknown;
      try {
        body = await request.json();
      } catch {
        throw new MockError(422, "Request body must be JSON.");
      }
      if (!isRecord(body))
        throw new MockError(
          422,
          "All RawRecord fields are required with the documented types.",
        );
      const result = preview(body, entities);
      if (path === "ingest/preview")
        return json({ ...result, dataset_version: version() });
      if (!result.accepted)
        throw new MockError(409, "Record rejected.", {
          findings: result.findings,
        });
      if (result.resolution.action !== "duplicate")
        additions.push({
          record: body,
          key: result.resolution.key!,
          added_at: new Date().toISOString(),
        });
      return json({ ...result, dataset_version: version() });
    }
    throw new MockError(404, "Endpoint not found.");
  } catch (error) {
    if (error instanceof MockError)
      return json(
        {
          error: {
            code:
              error.status === 404
                ? "not_found"
                : error.status === 409
                  ? "rejected"
                  : "invalid_request",
            message: error.message,
            details: error.details,
          },
        },
        error.status,
      );
    throw error;
  }
}

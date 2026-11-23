/** Synthetic HTTP test double. Never imported by client components. Not the production ingestion/retrieval implementation. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import recordsJson from "./synthetic-companies.json";
import fxRates from "./fx-rates.json";
import type {
  EntityDetail,
  EntitySummary,
  CompaniesResponse,
  ShareClass,
  Finding,
  Severity,
  MetricValue,
  Metrics,
  Observation,
  SummaryStat,
  CompsResponse,
  PeersResponse,
  DatasetResponse,
} from "../lib/api-types";

interface RawRecord {
  id: string;
  ticker: string;
  name: string;
  description: string;
  sector: string;
  industry: string;
  sub_industry: string;
  country: string;
  price_currency: string;
  reporting_currency: string;
  units: "millions" | "thousands";
  fiscal_year_end: string;
  price: number | null;
  price_date: string;
  shares_outstanding: number | null;
  total_debt: number | null;
  cash: number | null;
  revenue: number | null;
  ebitda: number | null;
  net_income: number | null;
}

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
const files = ["synthetic-companies.json", "fx-rates.json"].map((name) => ({
  name,
  sha256: createHash("sha256")
    .update(readFileSync(join(process.cwd(), "mocks", name)))
    .digest("hex"),
}));
const datasetVersion = createHash("sha256")
  .update(JSON.stringify(files))
  .digest("hex")
  .slice(0, 12);
const counts = (): Record<Severity, number> => ({
  error: 0,
  limitation: 0,
  warning: 0,
  info: 0,
});
const keyOf = (r: RawRecord) => `${r.country.trim() || "*"}:${r.ticker}`;
// This fixture contains one duplicate listing with the same price, currency and shares.
const duplicateListings = new Map([["US:NOMA.B", "US:NOMA"]]);
const issuerKey = (key: string) => duplicateListings.get(key) ?? key;
const financialKeys = [
  "market_cap_m",
  "enterprise_value_m",
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
function observe(r: RawRecord): Observation {
  const priceFx = rates[r.price_currency] ?? null;
  const reportingFx = rates[r.reporting_currency] ?? null;
  const unit = r.units === "thousands" ? 0.001 : 1;
  const convert = (v: number | null, fx: number | null, factor = 1) =>
    v === null || fx === null ? null : v * fx * factor;
  return {
    record_id: r.id,
    price_date: r.price_date || null,
    original: { ...r },
    normalized: {
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
  const cap = pMissing.length ? null : o.normalized.price! * r.shares_outstanding!;
  const evMissing = [
    ...pMissing,
    ...missing("total_debt", "cash"),
    ...(o.conversion.reporting_fx === null ? ["reporting_fx"] : []),
  ];
  const ev = evMissing.length ? null : cap! + o.normalized.total_debt! - o.normalized.cash!;
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
      absent.length ? null : o.normalized[denom]! <= 0 ? 0 : num! / o.normalized[denom]!,
      [...new Set(absent)],
      true,
      o.normalized[denom] !== null && o.normalized[denom]! <= 0,
    );
  };
  return {
    market_cap_m: metric(cap, pMissing),
    enterprise_value_m: metric(ev, evMissing),
    ev_revenue: ratio(ev, evMissing, "revenue"),
    ev_ebitda: ratio(ev, evMissing, "ebitda"),
    pe: ratio(cap, pMissing, "net_income"),
  };
}
function shareClass(record: RawRecord, observation: Observation, counted: boolean): ShareClass {
  const { price } = observation.normalized;
  const shares = record.shares_outstanding;
  const missing_inputs: string[] = [];
  if (price === null) missing_inputs.push("price");
  if (observation.conversion.price_fx === null) missing_inputs.push("price_currency");
  if (shares === null) missing_inputs.push("shares_outstanding");
  return {
    key: keyOf(record),
    ticker: record.ticker,
    name: record.name,
    record_id: record.id,
    price_currency: record.price_currency,
    price,
    shares_outstanding: shares,
    market_value_m: price === null || shares === null ? null : price * shares,
    missing_inputs,
    counted,
  };
}
function buildEntities(): EntityDetail[] {
  const grouped = new Map<string, RawRecord[]>();
  for (const record of fixtureRecords) {
    const key = keyOf(record);
    const group = grouped.get(key) ?? [];
    if (
      !group.some((existing) => JSON.stringify(existing) === JSON.stringify(record))
    )
      group.push(record);
    grouped.set(key, group);
  }
  for (const group of grouped.values())
    group.sort((a, b) => a.price_date.localeCompare(b.price_date));
  const shownListings = [...grouped.entries()].filter(([key]) => issuerKey(key) === key);
  return shownListings.map(([key, group]) => {
    const r = group.at(-1)!;
    // One observation per date, ties resolved by later record; history remains in record provenance.
    const byDate = new Map<string, Observation>();
    for (const record of group) byDate.set(record.price_date, observe(record));
    const observations = [...byDate.values()];
    const latest = observations.at(-1)!;
    const resultMetrics = metrics(r, latest);
    const findings: Finding[] = [];
    const share_classes = [shareClass(r, latest, true)];
    const issuerRecords = [...group];
    for (const [classKey, parent] of duplicateListings) {
      if (parent !== key) continue;
      const records = grouped.get(classKey)!;
      const listing = records.at(-1)!;
      share_classes.push(shareClass(listing, observe(listing), false));
      issuerRecords.push(...records);
      findings.push({
        ...finding(
          listing,
          "duplicate_share_listing",
          "info",
          `${classKey} lists the same shares as ${key}. They are counted once in market cap.`,
          ["price", "price_currency", "shares_outstanding"],
          ["market_cap_m"],
        ),
        entity_keys: [key, classKey],
      });
    }
    if (!r.country.trim()) {
      findings.push(
        finding(
          r,
          "missing_value",
          "warning",
          "Country is missing; the key uses *.",
          ["country"],
          [],
        ),
      );
    }
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
        (record) =>
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
      country: r.country.trim() || "*",
      name: r.name,
      sector: r.sector,
      industry: r.industry,
      sub_industry: r.sub_industry,
      latest_price_date: latest.price_date,
      finding_counts,
      description: r.description,
      fiscal_year_end: r.fiscal_year_end,
      aliases: [...new Set(issuerRecords.map((record) => record.name))],
      record_ids: issuerRecords.map((record) => record.id),
      share_class_keys: share_classes.map((listing) => listing.key),
      share_classes,
      latest,
      observations,
      currency: "USD",
      metrics: resultMetrics,
      findings,
    };
  });
}
function summaryEntity(e: EntityDetail): EntitySummary {
  return {
    key: e.key,
    share_class_keys: e.share_class_keys,
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
const matchOrder = ["key", "ticker", "name_exact", "name_partial", null] as const;
function companyMatch(entity: EntityDetail, query: string): CompaniesResponse["items"][number] {
  const summary = summaryEntity(entity);
  if (query) {
    const classes = entity.share_classes.map((listing) => ({
      listing,
      names: fixtureRecords
        .filter((record) => keyOf(record) === listing.key)
        .map((record) => record.name.toLowerCase()),
    }));
    const matches = [
      classes.find(({ listing }) => listing.key.toLowerCase() === query),
      classes.find(({ listing }) => listing.ticker.toLowerCase() === query),
      classes.find(({ names }) => names.includes(query)),
      classes.find(({ names }) => names.some((name) => name.includes(query))),
    ];
    const index = matches.findIndex(Boolean);
    const key = matches[index]?.listing.key;
    if (key) {
      return {
        ...summary,
        match: matchOrder[index],
        matched_key: key === entity.key ? null : key,
      };
    }
  }
  return { ...summary, match: null, matched_key: null };
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
  ) {
    super(message);
  }
}
function comps(
  params: URLSearchParams,
  entities: EntityDetail[],
): CompsResponse {
  const targetKey = issuerKey(params.get("target") ?? "");
  const target = entities.find((e) => e.key === targetKey);
  if (!target) throw new MockError(404, "Target company not found.");
  const k = Number(params.get("k") ?? 10);
  if (!Number.isInteger(k) || k < 1 || k > 50)
    throw new MockError(422, "k must be an integer from 1 to 50.");
  const removed = (params.get("exclude") || "")
    .split(",")
    .filter(Boolean)
    .map(issuerKey);
  if (removed.some((key) => !entities.some((e) => e.key === key)))
    throw new MockError(422, "An excluded company key was not found.");
  // Deterministic fixture similarity (not a model): earlier fixture rows score higher.
  const similarity = (e: EntityDetail) =>
    Number(Math.max(0, 0.94 - entities.indexOf(e) * 0.043).toFixed(4));
  const skipped: CompsResponse["skipped"] = [];
  const chosen: EntityDetail[] = [];
  for (const e of entities) {
    if (e.key === target.key || chosen.length >= k) continue;
    if (removed.includes(e.key)) {
      skipped.push({
        entity: summaryEntity(e),
        reason: "user_excluded",
        detail: "Removed by the analyst.",
        similarity: similarity(e),
        duplicate_of: null,
      });
      continue;
    }
    chosen.push(e);
  }
  const peers = chosen.map((e, i) => ({
    rank: i + 1,
    entity: summaryEntity(e),
    metrics: e.metrics,
    findings: e.findings,
    evidence: {
      similarity: similarity(e),
      classification: {
        sector: e.sector === target.sector,
        industry: e.industry === target.industry,
        sub_industry: e.sub_industry === target.sub_industry,
      },
      country_match: e.country === target.country,
      revenue_ratio:
        e.latest.normalized.revenue !== null && target.latest.normalized.revenue
          ? Number(
              (
                e.latest.normalized.revenue / target.latest.normalized.revenue
              ).toFixed(2),
            )
          : null,
      limitations: [
        ...new Set(
          e.findings.filter((f) => f.affects.length).map((f) => f.code),
        ),
      ].sort(),
    },
  }));
  return {
    dataset_version: datasetVersion,
    currency: "USD",
    requested_k: k,
    returned_k: peers.length,
    target: {
      entity: summaryEntity(target),
      metrics: target.metrics,
      findings: target.findings,
    },
    peers,
    skipped,
    note:
      peers.length < k
        ? `Only ${peers.length} of the ${k} requested peers could be chosen: the universe ran out of candidates.`
        : null,
    summary: {
      ev_revenue: stat(peers.map((p) => p.metrics.ev_revenue)),
      ev_ebitda: stat(peers.map((p) => p.metrics.ev_ebitda)),
      pe: stat(peers.map((p) => p.metrics.pe)),
    },
  };
}
function peersOf(result: CompsResponse): PeersResponse {
  return {
    dataset_version: result.dataset_version,
    target: result.target.entity,
    requested_k: result.requested_k,
    returned_k: result.returned_k,
    peers: result.peers.map(({ rank, entity, evidence }) => ({
      rank,
      entity,
      evidence: {
        similarity: evidence.similarity,
        classification: evidence.classification,
        country_match: evidence.country_match,
        revenue_ratio: evidence.revenue_ratio,
      },
    })),
    skipped: result.skipped,
    note: result.note,
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
    dataset_version: datasetVersion,
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
      "market_cap_m",
      "enterprise_value_m",
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
export function handleMock(request: Request, path: string): Response {
  const json = (body: unknown, status = 200) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
  try {
    const entities = buildEntities();
    const params = new URL(request.url).searchParams;
    if (path === "health")
      return json({
        status: "ok",
        dataset_version: datasetVersion,
        currency: "USD",
        entities: entities.length,
        records: fixtureRecords.length,
        reference_date: referenceDate,
      });
    if (path === "companies") {
      const q = (params.get("q") ?? "").trim().toLowerCase(),
        sector = params.get("sector"),
        severity = params.get("has_findings");
      if (severity && !severityList.includes(severity as Severity))
        throw new MockError(422, "Invalid severity.");
      const items = entities
        .map((entity) => companyMatch(entity, q))
        .filter(
          (e) =>
            (!q || e.match !== null) &&
            (!sector || e.sector === sector) &&
            (!severity || e.finding_counts[severity as Severity] > 0),
        )
        .sort(
          (a, b) =>
            matchOrder.indexOf(a.match) - matchOrder.indexOf(b.match) ||
            a.key.localeCompare(b.key),
        );
      return json(page(items, params, 20, 200));
    }
    if (path.startsWith("companies/")) {
      const key = decodeURIComponent(path.slice(10)).toUpperCase();
      const e = entities.find((e) => e.key === issuerKey(key));
      if (!e) throw new MockError(404, "Company not found.");
      return json({ ...e, dataset_version: datasetVersion });
    }
    if (path === "peers") return json(peersOf(comps(params, entities)));
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
        dataset_version: datasetVersion,
        currency: "USD",
        fx: { base: "USD" },
        reference_date: referenceDate,
        source: {
          data_dir: "web/mocks (synthetic)",
          files,
        },
        counts: {
          records: fixtureRecords.length,
          entities: entities.length,
        },
        findings_by_severity: bySeverity,
        findings_by_code: [...byCode.values()],
      };
      return json(body);
    }
    if (path === "dataset/findings") {
      const key = params.get("entity");
      const matchingFindings = key
        ? entities.find((entity) => entity.key === issuerKey(key))?.findings ?? []
        : findings;
      return json(
        page(
          matchingFindings.filter(
            (f) =>
              (!params.get("severity") ||
                f.severity === params.get("severity")) &&
              (!params.get("code") || f.code === params.get("code")),
          ),
          params,
          50,
          500,
        ),
      );
    }
    throw new MockError(404, "Endpoint not found.");
  } catch (error) {
    if (error instanceof MockError)
      return json(
        {
          error: {
            code: error.status === 404 ? "not_found" : "invalid_request",
            message: error.message,
            details: {},
          },
        },
        error.status,
      );
    throw error;
  }
}

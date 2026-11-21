export type Severity = "error" | "limitation" | "warning" | "info";

export interface Finding {
  code: string; // e.g. "missing_value", "possible_same_issuer", "stale_price"
  severity: Severity;
  message: string; // human-readable
  fields: string[]; // affected record fields
  affects: string[]; // affected metrics/capabilities, e.g. ["ev_ebitda"], ["retrieval"]
  source: "validation" | "derived"; // "derived" = produced by a model/heuristic, not a fact
  record_ids: string[];
  entity_keys: string[];
}

export type MetricStatus = "ok" | "nm" | "missing"; // NM = zero/negative denominator; missing = input unavailable

export interface MetricValue {
  status: MetricStatus;
  value: number | null; // rounded to 1 dp; null unless status = "ok"
  display: string | null; // "12.3x", "4,512.3", "NM", or null (show blank)
  raw: number | null; // unrounded
  missing_inputs: string[]; // e.g. ["ebitda"] when status = "missing"
}

export interface Metrics {
  market_cap_usd_m: MetricValue;
  enterprise_value_usd_m: MetricValue;
  ev_revenue: MetricValue;
  ev_ebitda: MetricValue;
  pe: MetricValue;
}

export interface EntitySummary {
  key: string; // "US:NOMA"
  ticker: string;
  country: string;
  name: string;
  sector: string | null;
  industry: string | null;
  sub_industry: string | null;
  latest_price_date: string | null; // ISO date
  finding_counts: Record<Severity, number>;
}

export interface Observation {
  record_id: string;
  origin: "file" | "manual";
  price_date: string | null;
  original: Record<string, unknown>; // the record exactly as supplied
  usd: {
    // normalized; null when it can't be computed
    price: number | null;
    total_debt: number | null;
    cash: number | null;
    revenue: number | null;
    ebitda: number | null;
    net_income: number | null;
  };
  conversion: {
    price_fx: number | null;
    reporting_fx: number | null;
    unit_factor: number | null;
  };
}

export interface EntityDetail extends EntitySummary {
  description: string | null;
  fiscal_year_end: string | null;
  aliases: string[]; // every name seen for this key
  record_ids: string[];
  latest: Observation; // the only observation used in calculations
  observations: Observation[]; // full history, oldest first
  metrics: Metrics; // computed from `latest`
  findings: Finding[];
}

export interface SummaryStat {
  n: number; // number of numeric peer values used
  n_nm: number;
  n_missing: number;
  mean: number | null;
  median: number | null;
  high: number | null;
  low: number | null; // rounded 1 dp
  display: {
    mean: string | null;
    median: string | null;
    high: string | null;
    low: string | null;
  };
}

// A record in the original companies.json schema (all fields required; values may be null)
export interface RawRecord {
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

export interface CompsResponse {
  dataset_version: string;
  method: { name: string; version: string };
  k: number;
  target: { entity: EntitySummary; metrics: Metrics; findings: Finding[] };
  peers: {
    rank: number;
    entity: EntitySummary;
    metrics: Metrics;
    findings: Finding[];
    evidence: {
      // why this peer was chosen (provisional shape)
      similarity: number; // description similarity score, 0–1; NOT a probability
      shared_terms: string[]; // description terms that drove the match
      classification: {
        sector: boolean;
        industry: boolean;
        sub_industry: boolean;
      };
      country_match: boolean;
      revenue_ratio: number | null; // peer revenue / target revenue (USD); null if unavailable
      limitations: string[]; // finding codes affecting this peer's metrics
    };
  }[];
  excluded: {
    entity: EntitySummary;
    reason: "possible_same_issuer" | "user_excluded";
    detail: string;
  }[];
  summary: { ev_revenue: SummaryStat; ev_ebitda: SummaryStat; pe: SummaryStat }; // peers only
}

export interface IngestResult {
  accepted: boolean; // false if a blocking error would reject it
  resolution: {
    key: string | null;
    action:
      | "create"
      | "add_observation"
      | "update_text"
      | "duplicate"
      | "rejected";
  };
  entity: EntityDetail | null; // the entity as it would look after saving
  findings: Finding[]; // findings raised by this record
}

export interface DatasetResponse {
  dataset_version: string;
  reference_date: string;
  source: { data_dir: string; files: { name: string; sha256: string }[] };
  counts: { records: number; entities: number; manual_additions: number };
  findings_by_severity: Record<Severity, number>;
  findings_by_code: {
    code: string;
    severity: Severity;
    source: Finding["source"];
    count: number;
  }[];
}
export interface CompaniesResponse {
  dataset_version: string;
  total: number;
  items: (EntitySummary & {
    match: "key" | "ticker" | "name_exact" | "name_partial" | null;
  })[];
}
export interface FindingsResponse {
  dataset_version: string;
  total: number;
  items: Finding[];
}
export interface ApiErrorBody {
  error: {
    code: "not_found" | "invalid_request" | "rejected";
    message: string;
    details: Record<string, unknown>;
  };
}

export type Severity = "error" | "limitation" | "warning" | "info";

export interface Finding {
  code: string; // e.g. "missing_value", "share_classes_merged", "stale_price"
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
  market_cap_m: MetricValue; // millions of the dataset currency
  enterprise_value_m: MetricValue; // millions of the dataset currency
  ev_revenue: MetricValue;
  ev_ebitda: MetricValue;
  pe: MetricValue;
}

export interface EntitySummary {
  key: string; // shown listing of the issuer
  share_class_keys: string[]; // shown key first
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
  price_date: string | null;
  original: Record<string, unknown>; // the record exactly as supplied
  normalized: {
    // in the dataset currency: price per share, other money in millions; null when it can't be computed
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

export interface ShareClass {
  key: string;
  ticker: string;
  name: string | null;
  record_id: string;
  price_currency: string | null; // as supplied
  price: number | null; // per share, dataset currency
  shares_outstanding: number | null; // millions
  market_value_m: number | null; // millions of the dataset currency
  missing_inputs: string[];
  counted: boolean;
}

export interface EntityDetail extends EntitySummary {
  currency: string; // dataset currency of `metrics` and every `normalized` block
  share_classes: ShareClass[];
  description: string | null;
  fiscal_year_end: string | null;
  aliases: string[]; // every name seen across the issuer’s classes
  record_ids: string[];
  latest: Observation; // latest observation of the shown class
  observations: Observation[]; // history of the shown class, oldest first
  metrics: Metrics; // market cap from counted share classes, other inputs from latest
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

export type SkipReason =
  | "near_duplicate_of_target"
  | "near_duplicate_of_peer"
  | "user_excluded"
  | "no_description";

export interface Evidence {
  // why this peer was chosen
  similarity: number; // description similarity, 0–1 (4 dp); NOT a probability
  classification: { sector: boolean; industry: boolean; sub_industry: boolean }; // evidence only
  country_match: boolean; // evidence only
  revenue_ratio: number | null; // peer revenue / target revenue (2 dp)
}

export interface Skipped {
  entity: EntitySummary;
  reason: SkipReason;
  detail: string; // human-readable
  similarity: number | null; // to the target (4 dp)
  duplicate_of: string | null; // shown key it duplicates
}

export interface PeersResponse {
  dataset_version: string;
  target: EntitySummary;
  requested_k: number;
  returned_k: number;
  peers: { rank: number; entity: EntitySummary; evidence: Evidence }[];
  skipped: Skipped[];
  note: string | null; // non-null exactly when returned_k < requested_k
}

export interface CompsResponse {
  dataset_version: string;
  currency: string; // dataset currency of market cap and EV
  requested_k: number;
  returned_k: number;
  target: { entity: EntitySummary; metrics: Metrics; findings: Finding[] };
  peers: {
    rank: number;
    entity: EntitySummary;
    metrics: Metrics;
    findings: Finding[];
    evidence: Evidence & { limitations: string[] }; // finding codes affecting this peer's metrics
  }[];
  skipped: Skipped[];
  note: string | null;
  summary: { ev_revenue: SummaryStat; ev_ebitda: SummaryStat; pe: SummaryStat }; // peers only
}

export interface DatasetResponse {
  dataset_version: string;
  currency: string; // dataset currency
  fx: { base: string }; // base currency as given in fx_rates.json
  reference_date: string | null;
  source: { data_dir: string; files: { name: string; sha256: string }[] };
  counts: { records: number; entities: number };
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
    matched_key: string | null; // matched listing when different from the shown key
  })[];
}
export interface FindingsResponse {
  dataset_version: string;
  total: number;
  items: Finding[];
}
export interface ApiErrorBody {
  error: {
    code: "not_found" | "invalid_request";
    message: string;
    details: Record<string, unknown>;
  };
}

import type { Metrics, MetricValue } from "@/lib/api-types";
export const metricLabels: Record<keyof Metrics, string> = {
  market_cap_m: "Market Cap",
  enterprise_value_m: "Enterprise Value",
  ev_revenue: "EV / Revenue",
  ev_ebitda: "EV / EBITDA",
  pe: "P / E",
};
export function Metric({ metric }: { metric: MetricValue }) {
  return metric.display === null ? (
    <span
      className="missing-value"
      tabIndex={0}
      title={`Missing inputs: ${metric.missing_inputs.join(", ")}`}
      aria-label={`Missing inputs: ${metric.missing_inputs.join(", ")}`}
    >
      —
    </span>
  ) : metric.status === "nm" ? (
    <span
      className="badge nm"
      tabIndex={0}
      title="The denominator is zero or negative."
    >
      {metric.display}
    </span>
  ) : (
    <span className="metric-number">{metric.display}</span>
  );
}
export function MetricsView({ metrics }: { metrics: Metrics }) {
  return (
    <dl className="metrics-grid">
      {(Object.keys(metricLabels) as (keyof Metrics)[]).map((key) => (
        <div key={key}>
          <dt>{metricLabels[key]}</dt>
          <dd>
            <Metric metric={metrics[key]} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

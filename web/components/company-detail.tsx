"use client";
import { titleLabel } from "@/lib/utils";
import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { api } from "@/lib/api";
import type { EntityDetail, Metrics, Observation } from "@/lib/api-types";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { MetricsView, metricLabels } from "@/components/metrics-view";
import { Findings } from "@/components/findings";
import { DataTable } from "@/components/data-table";
function value(v: unknown): string {
  return v === null || v === undefined
    ? "—"
    : typeof v === "object"
      ? JSON.stringify(v)
      : String(v);
}
export function CalculationTrace({
  observation,
  metrics,
}: {
  observation: Observation;
  metrics?: Metrics;
}) {
  const rows = Object.entries(observation.original).map(
    ([field, original]) => ({
      field,
      original: value(original),
      usd:
        field in observation.usd
          ? value(observation.usd[field as keyof Observation["usd"]])
          : "—",
    }),
  );
  const columns: ColumnDef<(typeof rows)[number]>[] = [
    { accessorKey: "field", header: "Original Field" },
    { accessorKey: "original", header: "Original Value" },
    { accessorKey: "usd", header: "USD Value" },
  ];
  return (
    <section className="trace">
      <h3>Calculation Trace</h3>
      <p className="muted">
        USD financials are in millions; price is USD per share. Shares
        outstanding are in millions.
      </p>
      <dl className="factor-grid">
        {Object.entries(observation.conversion).map(([key, v]) => (
          <div key={key}>
            <dt>{titleLabel(key)}</dt>
            <dd>{value(v)}</dd>
          </div>
        ))}
      </dl>
      <DataTable columns={columns} data={rows} />
      {metrics && (
        <>
          <h4>Unrounded Metric Values</h4>
          <dl className="trace-values">
            {(Object.keys(metricLabels) as (keyof Metrics)[]).map((key) => (
              <div key={key}>
                <dt>{metricLabels[key]}</dt>
                <dd>{value(metrics[key].raw)}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </section>
  );
}
export function CompanyDetail({
  companyKey,
  onClose,
}: {
  companyKey: string | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!companyKey) return;
    const controller = new AbortController();
    api<EntityDetail>(`/companies/${encodeURIComponent(companyKey)}`, {
      signal: controller.signal,
    })
      .then((d) => {
        setDetail(d);
        setError("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e.message));
      });
    return () => controller.abort();
  }, [companyKey]);
  const current = detail?.key === companyKey ? detail : null;
  return (
    <Sheet
      open={!!companyKey}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent>
        <SheetHeader>
          <SheetTitle>{current?.name || "Company Detail"}</SheetTitle>
          <SheetDescription>
            {companyKey} · Latest Observation and Provenance
          </SheetDescription>
        </SheetHeader>
        {error ? (
          <p role="alert" className="error">
            {error}
          </p>
        ) : !current ? (
          <p role="status">Loading company…</p>
        ) : (
          <div className="sheet-stack">
            <p>{current.description}</p>
            <p className="muted">
              {[current.sector, current.industry, current.sub_industry]
                .filter(Boolean)
                .join(" / ")}
            </p>
            <MetricsView metrics={current.metrics} />
            <section>
              <h3>Aliases</h3>
              <p>{current.aliases.join(", ") || "—"}</p>
              <p className="muted">
                Fiscal Year End: {current.fiscal_year_end || "—"} · Latest
                Price: {current.latest_price_date || "—"}
              </p>
            </section>
            <CalculationTrace
              observation={current.latest}
              metrics={current.metrics}
            />
            <section>
              <h3>Findings</h3>
              <Findings findings={current.findings} />
            </section>
            <section>
              <h3>Observation History</h3>
              <p className="muted">
                Oldest first. Calculations use only the latest observation.
              </p>
              {current.observations.map((o, i) => (
                <details key={`${o.record_id}-${i}`}>
                  <summary>
                    {o.price_date || "Undated"} · {o.record_id} · {titleLabel(o.origin)}
                  </summary>
                  <CalculationTrace observation={o} />
                </details>
              ))}
            </section>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
